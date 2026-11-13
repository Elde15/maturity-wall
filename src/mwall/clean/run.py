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

from mwall.clean import code_tables, screen, structure
from mwall.common import paths

DSCR_TOL = 0.05          # relative tolerance for reported vs recomputed DSCR
NOI_STALE_MONTHS = 18
VALUATION_OLD_YEARS = 5
SHARE_WHOLE = 0.90       # trust share above this = the whole loan is in the trust
TRANSIENT_MAX_PERIODS = 3  # a mid-history loan seen this many periods or fewer, never coded = foreign record
FOREIGN_ORIG_DAYS = 60   # origination date this far from the loan's usual one marks a foreign record


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
    a, p, superseded = screen.one_filing_per_period(a, p)
    a, p, fq = screen.screen(a, p)
    fq = pd.concat([fq, superseded], ignore_index=True)
    counts = ["n_exact_copies_dropped", "n_split_records", "n_foreign_repeats"]
    fq[counts] = fq[counts].fillna(0).astype(int)
    if "superseded_by" not in fq.columns:
        fq["superseded_by"] = None
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

    # A CMBS pool takes no new loans after issuance. A loan that first appears after the trust's opening
    # period and is gone again within a few periods, with no liquidation or prepayment code, is another
    # deal's record filed into this trust (D035). It stays in the table, flagged, and is left out of the
    # loan-count roll-forward and the panel.
    # One period per filing: a filing's rows can carry period-end dates a day apart.
    loans = loans.reset_index(drop=True)
    acc_pe = loans["period_end"].fillna(loans["filing_date"]).groupby(loans["accession"]).transform("max")
    k = acc_pe.rank(method="dense").astype(int)

    # A CMBS pool takes no new loans after issuance. A loan that first appears after the trust's opening
    # period and is gone again within a few periods, with no liquidation or prepayment code, is another
    # deal's record filed into this trust (D035).
    by_loan = loans.assign(_k=k, _coded=loans["liquidationPrepaymentCode"].notna()).groupby("loan_key")
    first, last = by_loan["_k"].transform("min"), by_loan["_k"].transform("max")
    n_seen = by_loan["_k"].transform("nunique")
    coded = by_loan["_coded"].transform("any")
    loans["flag_transient_loan"] = ((first > 1) & (last < k.max()) & (n_seen <= TRANSIENT_MAX_PERIODS)
                                    & ~coded).to_numpy()

    # Another deal's record can also arrive under one of this trust's loan numbers: the number keeps its
    # history but, for a filing or a few, carries an origination date far from its own. A deviation that
    # persists for more than three filings is a corrected date instead (D036).
    orig = pd.to_datetime(loans["originationDate"], errors="coerce")
    usual = orig.groupby(loans["loan_key"]).transform(lambda s: s.mode().iloc[0] if s.notna().any() else pd.NaT)
    n_usual = (orig == usual).groupby(loans["loan_key"]).transform("sum")
    off = (orig - usual).abs() > pd.Timedelta(days=FOREIGN_ORIG_DAYS)
    n_off = loans["accession"].where(off).groupby(loans["loan_key"]).transform("nunique")
    # the usual date must be backed by at least three filings and by more filings than the deviation
    loans["flag_foreign_record"] = (off & (n_off <= TRANSIENT_MAX_PERIODS) & (n_usual >= 3)
                                    & (n_usual > n_off)).to_numpy()

    # Filings holding another deal's records are flagged whole (D036).
    tr = loans.loc[loans["flag_transient_loan"], "accession"].value_counts()
    fq["n_transient_loans"] = fq["accession"].map(tr).fillna(0).astype(int)
    fr = loans.loc[loans["flag_foreign_record"], "accession"].value_counts()
    fq["n_foreign_records"] = fq["accession"].map(fr).fillna(0).astype(int)
    fq.loc[fq["corrupt_reason"].isna() & (fq["n_transient_loans"] > 0), "corrupt_reason"] = (
        "loans from another deal present for a few periods only")
    fq.loc[fq["corrupt_reason"].isna() & (fq["n_foreign_records"] > 0), "corrupt_reason"] = (
        "records under this trust's loan numbers with another loan's origination date")
    fq.insert(0, "trust_cik", cik)
    corrupt = set(fq.loc[fq["corrupt_reason"].notna(), "accession"])
    loans["flag_filing_corrupt"] = loans["accession"].isin(corrupt)
    props["flag_filing_corrupt"] = props["accession"].isin(corrupt)

    # Gaps in a loan's monthly history are flagged, never filled (SOP 8.3). A filing that leaves out
    # loans reported both before and after it is counted as incomplete (D036).
    good = ~loans["flag_filing_corrupt"] & ~loans["flag_transient_loan"]
    mi = acc_pe.dt.year * 12 + acc_pe.dt.month
    seq = pd.DataFrame({"lk": loans["loan_key"], "mi": mi})[good].sort_values(["lk", "mi"])
    seq["prev"] = seq.groupby("lk")["mi"].shift()
    loans["months_since_prev_report"] = seq["mi"] - seq["prev"]  # aligns on the index
    loans["flag_history_gap"] = loans["months_since_prev_report"] > 1
    present = pd.DataFrame({"lk": loans["loan_key"], "k": k})[good].drop_duplicates()
    span = present.groupby("lk")["k"].agg(["min", "max"])
    good_k = sorted(present["k"].unique())
    seen = set(zip(present["lk"], present["k"]))
    missing = {}
    for lk, lo, hi in span.itertuples():
        for kk in good_k:
            if lo < kk < hi and (lk, kk) not in seen:
                missing[kk] = missing.get(kk, 0) + 1
    acc_k = pd.Series(k.to_numpy(), index=loans["accession"]).groupby(level=0).first()
    fq["n_loans_missing"] = fq["accession"].map(acc_k).map(missing).fillna(0).astype(int)

    # property-level flags
    props["flag_noi_missing"] = props["mostRecentNetOperatingIncomeAmount"].isna()

    out_l = paths.PARSED_DIR / "loan_period" / f"{cik}.parquet"
    out_p = paths.PARSED_DIR / "property_period" / f"{cik}.parquet"
    out_l.parent.mkdir(parents=True, exist_ok=True)
    out_p.parent.mkdir(parents=True, exist_ok=True)
    keep_p = props.drop(columns=[c for c in ["first_note_seq"] if c in props.columns])
    loans.to_parquet(out_l, index=False, compression="zstd")
    out_s = paths.PARSED_DIR / "filing_screen" / f"{cik}.parquet"
    out_s.parent.mkdir(parents=True, exist_ok=True)
    fq.to_parquet(out_s, index=False)
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
