"""Clean stage: parsed asset/property rows -> loan_period and property_period.

Per trust (one worker each):
1. keep the winning filing per reporting period (amendments supersede);
2. resolve layouts into loans and properties (structure.py);
3. decode codes from the SEC tables and add analysis groupings;
4. annualize "most recent" financials, which are often year-to-date;
5. estimate the whole-loan balance behind pari passu pieces (decision D020);
6. add the SOP section 8 QA flags. Nothing is imputed.

Writes parsed/loan_period/{cik}.parquet and parsed/property_period/{cik}.parquet.
"""
from __future__ import annotations

import time
import traceback
from concurrent.futures import ProcessPoolExecutor, as_completed

import duckdb
import numpy as np
import pandas as pd

from mwall.clean import code_tables, structure
from mwall.common import paths

DSCR_TOL = 0.05          # relative tolerance for reported vs recomputed DSCR
NOI_STALE_MONTHS = 18
VALUATION_OLD_YEARS = 5
SHARE_WHOLE = 0.90       # trust share above this = the whole loan is in the trust


def _months_between(start: pd.Series, end: pd.Series) -> pd.Series:
    d = (pd.to_datetime(end) - pd.to_datetime(start)).dt.days + 1
    return (d / 30.4375).round()


BASIS_TOL = 0.08


def infer_fin_basis(loans: pd.DataFrame) -> pd.Series:
    """'full_year', 'ytd', 'annualized' or 'unknown' for each loan-period.

    Evidence comes from whole loans held entirely in the trust, where the
    reported debt service must equal the scheduled payment times either the
    period length (year-to-date) or 12 (annualized). Votes are pooled per
    filing and primary servicer, then per filing.
    """
    fm = loans["fin_months"]
    out = pd.Series(np.where(fm == 12, "full_year", "unknown"), index=loans.index, dtype=object)
    monthly = loans["root_trust_pi_annual"] / 12.0
    ds = loans["fin_debt_service"]
    ok = (loans["loanStructureCode"].fillna("WL") == "WL") & (loans["n_notes"].fillna(0) == 0) & \
        fm.between(1, 11) & (ds > 0) & (monthly > 0)
    r_ytd = ds / (monthly * fm)
    r_ann = ds / (monthly * 12.0)
    votes = pd.DataFrame({
        "accession": loans["accession"],
        "servicer": loans["primaryServicerName"].fillna("?"),
        "ytd": (ok & ((r_ytd - 1).abs() < BASIS_TOL)).astype(int),
        "ann": (ok & ((r_ann - 1).abs() < BASIS_TOL)).astype(int),
    })
    by_srv = votes.groupby(["accession", "servicer"])[["ytd", "ann"]].transform("sum")
    by_acc = votes.groupby("accession")[["ytd", "ann"]].transform("sum")

    def pick(v: pd.DataFrame) -> pd.Series:
        return pd.Series(np.select([v["ytd"] > v["ann"], v["ann"] > v["ytd"]], ["ytd", "annualized"], "unknown"),
                         index=v.index)

    srv, acc = pick(by_srv), pick(by_acc)
    partial = fm.between(1, 11)
    out = out.where(~partial, srv.where(srv != "unknown", acc))
    return out


def _read(cik: int, kind: str) -> pd.DataFrame:
    con = duckdb.connect()
    glob = (paths.PARSED_DIR / kind / "*" / f"{cik}.parquet").as_posix()
    try:
        return con.execute(f"select * from read_parquet('{glob}', union_by_name=true)").df()
    finally:
        con.close()


def clean_trust(cik: int) -> dict:
    a, p = _read(cik, "assets"), _read(cik, "properties")
    a = a[a["is_period_winner"]]
    p = p[p["is_period_winner"]]
    if a.empty:
        return {"cik": cik, "loans": 0, "properties": 0, "note": "no winning filings"}
    loans, props = structure.resolve(a, p)

    # ---- period ------------------------------------------------------------
    loans["period_end"] = pd.to_datetime(loans["reportingPeriodEndDate"])
    pe = loans.groupby("accession")["period_end"].transform("max")
    loans["period_end"] = loans["period_end"].fillna(pe)
    loans["filing_date"] = pd.to_datetime(loans["filing_date"])

    # ---- decode -------------------------------------------------------------
    for f in ["paymentStatusLoanCode", "liquidationPrepaymentCode", "loanStructureCode", "paymentTypeCode",
              "interestAccrualMethodCode"]:
        loans[f + "_label"] = loans[f].map(lambda c, f=f: code_tables.decode(f, c))
    loans["delinquency_bucket"] = loans["paymentStatusLoanCode"].map(code_tables.DELINQUENCY_BUCKET)
    loans["prop_type_code"] = loans["prop_type_code"].map(lambda c: code_tables.ALIASES.get(c, c) if c else c)
    loans["property_group"] = loans["prop_type_code"].map(code_tables.PROPERTY_GROUP)
    props["property_group"] = props["propertyTypeCode"].map(
        lambda c: code_tables.PROPERTY_GROUP.get(code_tables.ALIASES.get(c, c)) if c else None)
    coded = [f for f in code_tables.tables() if f in loans.columns]
    invalid = np.zeros(len(loans), dtype=bool)
    for f in coded:
        invalid |= ~loans[f].map(lambda c, f=f: code_tables.is_valid(f, c)).to_numpy(dtype=bool)
    loans["flag_invalid_code"] = invalid

    # ---- terms --------------------------------------------------------------
    loans["term_months_from_dates"] = _months_between(loans["originationDate"], loans["maturityDate"]) - 1
    loans["months_to_maturity"] = ((pd.to_datetime(loans["maturityDate"]) - loans["period_end"]).dt.days / 30.4375)
    loans["balance"] = loans["reportPeriodEndActualBalanceAmount"].fillna(
        loans["reportPeriodEndScheduledLoanBalanceAmount"])

    # ---- annualize financials (D021) ----------------------------------------
    # A partial-year period is reported either year-to-date or already
    # annualized, depending on the servicer. infer_fin_basis decides which.
    loans = loans.copy()
    fm = _months_between(loans["fin_start"], loans["fin_end"])
    loans["flag_fin_period_assumed"] = fm.isna() & loans["fin_end"].notna()
    loans["fin_months"] = fm.where(fm.between(1, 24), np.where(loans["fin_end"].notna() & fm.isna(), 12, np.nan))
    root = loans.groupby(["accession", "root"], dropna=False)
    loans["root_trust_balance"] = root["balance"].transform(lambda s: s.sum(min_count=1))
    loans["root_trust_pi_annual"] = root["totalScheduledPrincipalInterestDueAmount"].transform(
        lambda s: s.sum(min_count=1)) * 12.0
    loans["fin_basis"] = infer_fin_basis(loans)
    ann = pd.Series(np.select([loans["fin_basis"] == "full_year", loans["fin_basis"] == "ytd",
                               loans["fin_basis"] == "annualized"],
                              [12.0 / loans["fin_months"], 12.0 / loans["fin_months"], 1.0], np.nan),
                    index=loans.index)
    loans["flag_fin_basis_unknown"] = loans["fin_noi"].notna() & loans["fin_basis"].eq("unknown")
    for c in ["fin_revenue", "fin_opex", "fin_noi", "fin_ncf", "fin_debt_service"]:
        loans[c + "_annual"] = loans[c] * ann

    # ---- whole-loan balance behind pari passu pieces (D020) ----------------
    share = loans["root_trust_pi_annual"] / loans["fin_debt_service_annual"]
    loans["trust_share_est"] = share.where(share.between(0.01, 1.5))
    whole = (loans["trust_share_est"] >= SHARE_WHOLE) | (
        loans["trust_share_est"].isna() & (loans["loanStructureCode"].fillna("WL") == "WL"))
    loans["wl_balance_method"] = np.select(
        [whole, loans["trust_share_est"].notna()], ["trust_holds_whole_loan", "debt_service_share"], "unknown")
    loans["wl_balance_est"] = np.where(
        whole, loans["root_trust_balance"],
        np.where(loans["trust_share_est"].notna(), loans["root_trust_balance"] / loans["trust_share_est"], np.nan))

    # ---- QA flags (SOP 8.7) --------------------------------------------------
    loans["flag_noi_missing"] = loans["fin_noi"].isna()
    age = (loans["filing_date"] - pd.to_datetime(loans["fin_end"])).dt.days / 30.4375
    loans["noi_age_months"] = age
    loans["flag_noi_stale"] = age > NOI_STALE_MONTHS
    dscr_re = loans["fin_noi"] / loans["fin_debt_service"]
    loans["dscr_noi_recomputed"] = dscr_re.where(loans["fin_debt_service"] > 0)
    rel = (loans["dscr_noi_recomputed"] - loans["dscr_noi_reported"]).abs() / loans["dscr_noi_reported"].abs()
    loans["flag_dscr_inconsistent"] = rel > DSCR_TOL
    val_date = pd.to_datetime(loans["val_recent_date"]).fillna(pd.to_datetime(loans["val_securitization_date"]))
    loans["valuation_age_years"] = (loans["filing_date"] - val_date).dt.days / 365.25
    loans["flag_valuation_old"] = loans["valuation_age_years"] > VALUATION_OLD_YEARS
    active = loans["paymentStatusLoanCode"].notna() & loans["liquidationPrepaymentCode"].isna()
    loans["flag_zero_balance_active"] = active & (loans["balance"].fillna(0) <= 0)

    # property-level flags
    props["flag_noi_missing"] = props["mostRecentNetOperatingIncomeAmount"].isna()

    out_l = paths.PARSED_DIR / "loan_period" / f"{cik}.parquet"
    out_p = paths.PARSED_DIR / "property_period" / f"{cik}.parquet"
    out_l.parent.mkdir(parents=True, exist_ok=True)
    out_p.parent.mkdir(parents=True, exist_ok=True)
    keep_p = props.drop(columns=[c for c in ["first_note_seq"] if c in props.columns])
    loans.to_parquet(out_l, index=False, compression="zstd")
    keep_p.to_parquet(out_p, index=False, compression="zstd")
    return {"cik": cik, "loans": len(loans), "properties": int((props["block_role"] == "property").sum()),
            "note": ""}


def run(log=print, workers: int = 3, ciks: list[int] | None = None) -> pd.DataFrame:
    done_parse = sorted({int(f.stem) for f in (paths.PARSED_DIR / "assets").glob("*/*.parquet")})
    todo = [c for c in done_parse if not ciks or c in ciks]
    log(f"cleaning {len(todo)} trusts")
    t0, results = time.monotonic(), []
    with ProcessPoolExecutor(max_workers=workers) as pool:
        futs = {pool.submit(clean_trust, c): c for c in todo}
        for i, fut in enumerate(as_completed(futs), 1):
            try:
                results.append(fut.result())
            except Exception:
                log(f"  trust {futs[fut]} failed:\n{traceback.format_exc()}")
                results.append({"cik": futs[fut], "loans": 0, "properties": 0, "note": "failed"})
            if i % 25 == 0:
                log(f"  cleaned {i}/{len(todo)} ({time.monotonic()-t0:.0f}s)")
    res = pd.DataFrame(results)
    log(f"loan-periods: {res['loans'].sum():,}; property-periods: {res['properties'].sum():,}; "
        f"failed: {(res['note']=='failed').sum()}")
    return res
