"""Loan-month panel and outcome labels (SOP section 10; definitions in docs/labels.md).

Unit: a loan position (root number in a trust, ``root_key``) per reporting month. Notes of one loan
in the same trust are summed; the worst payment status among them is kept. Rows from corrupt
filings and transient or foreign records are left out. ``whole_loan_id`` groups pari passu pieces
across trusts and ``is_representative`` marks one position per whole loan and month.

Writes panel/loan_month.parquet, panel/tier1.parquet, panel/tier3.parquet and
docs/qa/gate2_labels.md.
"""
from __future__ import annotations

import datetime as dt

import duckdb
import numpy as np
import pandas as pd

from mwall.common import paths

GRACE_DAYS = 90          # tier 1 grace after maturity (SOP default; robustness reruns at 60 and 120)
EARLY_DAYS = 365         # payoff this long before maturity still counts as a maturity outcome
HORIZON_DAYS = 365       # tier 2 forward window
SLACK_DAYS = 10          # reporting dates wander a few days around the month
PAYOFF_CODES = {"2", "5", "8", "9"}
LIQ_CODES = {"3", "6"}
SEVERITY = {"0": 0, "A": 1, "B": 2, "1": 3, "4": 4, "2": 5, "3": 6, "5": 7}  # worst status wins
PERFORMING = {"0", "A", "B"}


def _norm_code(s: pd.Series) -> pd.Series:
    return s.astype("string").str.replace(r"\.0$", "", regex=True).str.strip()


def load_rows() -> pd.DataFrame:
    """One row per (root_key, filing): sums across notes, attributes from the largest record."""
    con = duckdb.connect()
    lp = (paths.PARSED_DIR / "loan_period" / "*.parquet").as_posix()
    pp = (paths.PARSED_DIR / "property_period" / "*.parquet").as_posix()
    rows = con.execute(f"""
        with l as (
            select *, max(period_end) over (partition by accession) acc_pe,
                   case cast(paymentStatusLoanCode as varchar)
                        when '0' then 0 when 'A' then 1 when 'B' then 2 when '1' then 3 when '4' then 4
                        when '2' then 5 when '3' then 6 when '5' then 7 end sev
            from read_parquet('{lp}', union_by_name=true)
            where loan_source in ('loan_record','note_record','replicated_child')
              and not coalesce(flag_filing_corrupt, false) and not coalesce(flag_transient_loan, false)
              and not coalesce(flag_foreign_record, false))
        select trust_cik, root_key, accession, any_value(acc_pe) period_end, any_value(filing_date) filing_date,
               count(*) n_records,
               sum(balance) balance,
               count(*) filter (where balance is null and liquidationPrepaymentCode is null) n_blank_balance,
               arg_max(paymentStatusLoanCode, sev) payment_status,
               list_distinct(list(cast(liquidationPrepaymentCode as varchar))) liq_codes,
               sum(realizedLossToTrustAmount) realized_loss,
               max(mostRecentSpecialServicerTransferDate) ss_transfer_date,
               max(mostRecentMasterServicerReturnDate) ss_return_date,
               -- the indicator counts only with some detail of the modification (D045): one servicer (NCB) sets
               -- it on co-op loans with no code, date or new terms, in a yearly pattern
               bool_or(coalesce(reportPeriodModificationIndicator, false) and (
                   modificationCode is not null or lastModificationDate is not null
                   or postModificationInterestPercentage is not null or postModificationPaymentAmount is not null
                   or postModificationMaturityDate is not null
                   or postModificationAmortizationPeriodAmount is not null)) mod_this_period,
               bool_or(coalesce(reportPeriodModificationIndicator, false)) mod_indicator_raw,
               max(lastModificationDate) last_mod_date,
               max(maturityDate) maturity_date,
               max(hyperAmortizingDate) ard_date,
               arg_max(prop_type_code, coalesce(balance, 0)) prop_type_code,
               arg_max(property_group, coalesce(balance, 0)) property_group,
               max(wl_balance_est) wl_balance_est,
               min(originationDate) origination_date
        from l group by 1, 2, 3""").df()
    defe = con.execute(f"""
        select accession, cast(trust_cik as varchar) || ':' || cast(root as varchar) root_key,
               bool_or(DefeasedStatusCode = 'F') defeased
        from read_parquet('{pp}', union_by_name=true)
        where block_role in ('property', 'rollup') group by 1, 2""").df()
    rows = rows.merge(defe, on=["accession", "root_key"], how="left")
    rows["defeased"] = rows["defeased"].fillna(False).astype(bool) | rows["property_group"].eq("defeased")
    rows["payment_status"] = _norm_code(rows["payment_status"])
    for c in ["period_end", "filing_date", "ss_transfer_date", "ss_return_date", "last_mod_date", "maturity_date",
              "ard_date", "origination_date"]:
        rows[c] = pd.to_datetime(rows[c], errors="coerce")
    return rows.sort_values(["root_key", "period_end", "filing_date"]).reset_index(drop=True)


def events(p: pd.DataFrame) -> pd.DataFrame:
    g = p.groupby("root_key", sort=False)
    codes = p["liq_codes"].map(lambda xs: {str(x).replace(".0", "") for x in xs if x is not None}
                               if xs is not None else set())
    p["ev_payoff"] = codes.map(lambda s: bool(s & PAYOFF_CODES)) & (p["balance"].fillna(0) <= 0)
    p["ev_removed"] = codes.map(lambda s: "4" in s)
    p["ev_liquidation"] = codes.map(lambda s: bool(s & LIQ_CODES)) | (p["realized_loss"].fillna(0) > 0)
    p["ev_dq60"] = p["payment_status"].isin(["2", "3"])
    p["ev_matured_np"] = p["payment_status"].eq("5")
    first = g.cumcount() == 0
    prev_ss = g["ss_transfer_date"].transform(lambda s: s.cummax().shift())
    p["ev_ss_transfer"] = ~first & p["ss_transfer_date"].notna() & (prev_ss.isna() | (p["ss_transfer_date"] > prev_ss))
    # Some filers leave the modification indicator on for months after one modification, so the event is
    # the indicator switching on, or a new last-modification date.
    prev_mod = g["last_mod_date"].transform(lambda s: s.cummax().shift())
    prev_flag = g["mod_this_period"].shift().fillna(False).astype(bool)
    p["ev_modification"] = (p["mod_this_period"] & ~prev_flag) | (
        ~first & p["last_mod_date"].notna() & (prev_mod.isna() | (p["last_mod_date"] > prev_mod)))
    p["ev_distress"] = p[["ev_dq60", "ev_matured_np", "ev_ss_transfer", "ev_modification", "ev_liquidation"]].any(axis=1)
    # loan state at T
    p["maturity0"] = g["maturity_date"].transform("first")
    p["ard0"] = g["ard_date"].transform("first")
    p["maturity_eff"] = p["ard0"].fillna(p["maturity0"])
    in_ss = p["ss_transfer_date"].notna() & (p["ss_return_date"].isna() | (p["ss_return_date"] < p["ss_transfer_date"]))
    p["in_special_servicing"] = in_ss
    p["performing"] = (p["payment_status"].isin(PERFORMING) & ~in_ss & (p["period_end"] < p["maturity_eff"])
                       & ~p["defeased"] & (p["balance"].fillna(0) > 0))
    return p


def tier2(p: pd.DataFrame) -> pd.DataFrame:
    g = p.groupby("root_key", sort=False)
    nd = p["period_end"].where(p["ev_distress"])
    npay = p["period_end"].where(p["ev_payoff"])
    p["next_distress"] = nd.groupby(p["root_key"]).shift(-1).groupby(p["root_key"]).bfill()
    p["next_payoff"] = npay.groupby(p["root_key"]).shift(-1).groupby(p["root_key"]).bfill()
    p["last_obs"] = g["period_end"].transform("max")
    end = p["period_end"] + pd.Timedelta(days=HORIZON_DAYS + SLACK_DAYS)
    full = p["last_obs"] >= p["period_end"] + pd.Timedelta(days=HORIZON_DAYS - SLACK_DAYS)
    y = np.where(p["next_distress"].notna() & (p["next_distress"] <= end), 1.0,
                 np.where(full | (p["next_payoff"].notna() & (p["next_payoff"] <= end)), 0.0, np.nan))
    p["y_distress_12m"] = np.where(p["performing"], y, np.nan)
    # near the end of the data a month can be labeled early only when an event has already happened, which
    # leans recent labels positive; models train and test only on months whose whole window is in the data
    data_end = p.groupby("trust_cik")["period_end"].transform("max")
    p["label_window_complete"] = p["period_end"] + pd.Timedelta(days=HORIZON_DAYS - SLACK_DAYS) <= data_end
    return p


def tier1(p: pd.DataFrame, trust_last: pd.Series) -> pd.DataFrame:
    out = []
    for rk, d in p.groupby("root_key", sort=False):
        mat = d["maturity_eff"].iloc[0]
        if pd.isna(mat):
            continue
        tl = trust_last.get(d["trust_cik"].iloc[0])
        if pd.isna(tl) or mat > tl - pd.Timedelta(days=GRACE_DAYS) or mat < d["period_end"].iloc[0]:
            continue  # maturity plus grace not inside the data window, or before the loan was first seen
        rec = {"root_key": rk, "trust_cik": d["trust_cik"].iloc[0], "maturity_eff": mat,
               "maturity_is_ard": pd.notna(d["ard0"].iloc[0]), "property_group": d["property_group"].iloc[0],
               "prop_type_code": d["prop_type_code"].iloc[0], "balance_first": d["balance"].iloc[0]}
        window_start = mat - pd.Timedelta(days=EARLY_DAYS)
        pay = d.loc[d["ev_payoff"], "period_end"]
        liq = d.loc[d["ev_liquidation"], "period_end"]
        pay_first = pay.min() if len(pay) else pd.NaT
        liq_first = liq.min() if len(liq) else pd.NaT
        late = d[(d["period_end"] > mat + pd.Timedelta(days=GRACE_DAYS)) & (d["balance"].fillna(0) > 0)]
        if d["defeased"].any():
            rec["outcome"] = "excluded_defeased"
        elif d["ev_removed"].any():
            rec["outcome"] = "excluded_removed"
        elif pd.notna(pay_first) and pay_first < window_start:
            rec["outcome"] = "excluded_early_payoff"
        elif pd.notna(liq_first) and liq_first < window_start:
            rec["outcome"] = "excluded_early_liquidation"
        elif pd.notna(pay_first) and pay_first <= mat + pd.Timedelta(days=GRACE_DAYS) and (
                pd.isna(liq_first) or liq_first > pay_first):
            rec["outcome"] = "paid"
        elif len(late) or pd.notna(liq_first) or pd.notna(pay_first):
            # a payoff later than the grace window is a failure to pay within it (D050), even when the next
            # filing after the window already shows the payoff
            rec["outcome"] = "failed"
        else:
            rec["outcome"] = "unknown"
        rec["y_fail"] = {"paid": 0.0, "failed": 1.0}.get(rec["outcome"], np.nan)
        rec["payoff_date"] = pay_first
        rec["extended"] = bool((d["maturity_date"] > d["maturity0"].iloc[0]).any())
        out.append(rec)
    return pd.DataFrame(out)


def tier3(p: pd.DataFrame) -> pd.DataFrame:
    out = []
    for rk, d in p[p["root_key"].isin(set(p.loc[p["ev_liquidation"], "root_key"]))].groupby("root_key", sort=False):
        i = d.index[d["ev_liquidation"]][0]
        before = d.loc[: i - 1] if i > d.index[0] else d.loc[:i]
        # the balance just before liquidation can be junk (a $1.00 placeholder); use the last balance above 1%
        # of the loan's first reported balance
        floor = 0.01 * (d["balance"].dropna().iloc[0] if d["balance"].notna().any() else 0)
        bal = before["balance"].where(before["balance"] > floor).dropna()
        base = bal.iloc[-1] if len(bal) else np.nan
        loss = d["realized_loss"].max()  # reported cumulatively and repeated every month the loan stays listed
        loss = 0.0 if pd.isna(loss) else float(loss)
        out.append({"root_key": rk, "trust_cik": d["trust_cik"].iloc[0], "liquidation_period": d.loc[i, "period_end"],
                    "balance_at_liquidation": base, "realized_loss": loss,
                    "severity": loss / base if base and base > 0 else np.nan,
                    "flag_no_loss_reported": loss == 0, "property_group": d["property_group"].iloc[0]})
    return pd.DataFrame(out)


def build(log=print) -> pd.DataFrame:
    t0 = dt.datetime.now()
    p = load_rows()
    log(f"panel rows {len(p):,} for {p['root_key'].nunique():,} loan positions")
    p = events(p)
    p = tier2(p)
    wl = pd.read_parquet(paths.PARSED_DIR / "whole_loans.parquet")[["root_key", "whole_loan_id"]].drop_duplicates("root_key")
    p = p.merge(wl, on="root_key", how="left")
    p["whole_loan_id"] = p["whole_loan_id"].fillna(p["root_key"])
    p["ym"] = p["period_end"].dt.to_period("M")
    rank = p.sort_values(["balance", "trust_cik"], ascending=[False, True]).groupby(["whole_loan_id", "ym"]).cumcount()
    p["is_representative"] = rank.reindex(p.index) == 0
    trust_last = p.groupby("trust_cik")["period_end"].max()
    t1 = tier1(p, trust_last)
    t3 = tier3(p)
    out = paths.PANEL_DIR
    out.mkdir(parents=True, exist_ok=True)
    p.drop(columns=["liq_codes", "ym"]).to_parquet(out / "loan_month.parquet", index=False)
    t1.to_parquet(out / "tier1.parquet", index=False)
    t3.to_parquet(out / "tier3.parquet", index=False)
    report(p, t1, t3, log)
    from mwall.panel import gold

    gold.build(log)
    log(f"panel built in {(dt.datetime.now() - t0).seconds}s")
    return p


def _counts(t: pd.DataFrame) -> pd.DataFrame:
    """Event counts are sums of 0/1 labels; print them as integers."""
    return t.astype({c: "int64" for c in ("events", "failed") if c in t.columns})


def report_from_disk(log=print) -> None:
    cols = ["root_key", "trust_cik", "whole_loan_id", "is_representative", "y_distress_12m", "label_window_complete",
            "property_group",
            "performing", "defeased", "n_blank_balance", "ev_distress", "ev_dq60", "ev_matured_np", "ev_ss_transfer",
            "ev_modification", "ev_liquidation"]
    p = pd.read_parquet(paths.PANEL_DIR / "loan_month.parquet", columns=cols)
    report(p, pd.read_parquet(paths.PANEL_DIR / "tier1.parquet"), pd.read_parquet(paths.PANEL_DIR / "tier3.parquet"), log)
    from mwall.panel import gold

    gold.build(log)


def report(p: pd.DataFrame, t1: pd.DataFrame, t3: pd.DataFrame, log=print) -> None:
    from mwall.clean.qa_report import md_table

    trusts = pd.read_parquet(paths.META_DIR / "trusts.parquet")[["trust_cik", "vintage"]]
    trusts["vintage"] = pd.to_numeric(trusts["vintage"], errors="coerce").astype("Int64")
    rep = p[p["is_representative"]].merge(trusts, on="trust_cik", how="left")
    t2 = rep[rep["y_distress_12m"].notna() & rep["label_window_complete"]]
    t2_partial = rep[rep["y_distress_12m"].notna() & ~rep["label_window_complete"]]
    by_type = t2.groupby("property_group", dropna=False)["y_distress_12m"].agg(rows="size", events="sum", rate="mean")
    by_vint = t2.groupby("vintage", dropna=False)["y_distress_12m"].agg(rows="size", events="sum", rate="mean")
    t1 = t1.merge(trusts, on="trust_cik", how="left")
    wl = pd.read_parquet(paths.PARSED_DIR / "whole_loans.parquet")[["root_key", "whole_loan_id"]].drop_duplicates("root_key")
    t1 = t1.merge(wl, on="root_key", how="left")
    t1["whole_loan_id"] = t1["whole_loan_id"].fillna(t1["root_key"])
    t1u = t1.sort_values("balance_first", ascending=False).drop_duplicates("whole_loan_id")
    lab = t1u[t1u["y_fail"].notna()]
    t1_type = lab.groupby("property_group", dropna=False)["y_fail"].agg(loans="size", failed="sum", rate="mean")
    t1_year = lab.groupby(lab["maturity_eff"].dt.year)["y_fail"].agg(loans="size", failed="sum", rate="mean")
    t1_vint = lab.groupby("vintage", dropna=False)["y_fail"].agg(loans="size", failed="sum", rate="mean")
    t3 = t3.merge(trusts, on="trust_cik", how="left")
    t3r = t3[~t3["flag_no_loss_reported"]] if len(t3) else t3
    t3_type = t3.groupby("property_group", dropna=False).agg(
        liquidated=("severity", "size"), loss_reported=("flag_no_loss_reported", lambda s: int((~s).sum())))
    t3_type["median_severity"] = t3r.groupby("property_group", dropna=False)["severity"].median()
    t3_vint = t3.groupby("vintage", dropna=False).agg(
        liquidated=("severity", "size"), loss_reported=("flag_no_loss_reported", lambda s: int((~s).sum())))
    t3_vint["median_severity"] = t3r.groupby("vintage", dropna=False)["severity"].median()
    ev_cols = ["ev_dq60", "ev_matured_np", "ev_ss_transfer", "ev_modification", "ev_liquidation"]
    first_ev = rep[rep["ev_distress"]]
    L = [
        "# Gate 2 label counts",
        "",
        f"Generated {dt.date.today().isoformat()} by `python -m mwall panel`. Definitions: `docs/labels.md`. "
        "Counts use one representative position per whole loan and month, so pari passu pieces in several trusts "
        "count once.",
        "",
        "## Panel",
        "",
        f"- Loan-months: {len(p):,} across {p['root_key'].nunique():,} loan positions and "
        f"{p['whole_loan_id'].nunique():,} whole loans; representative rows {int(p['is_representative'].sum()):,}.",
        f"- Defeased loan-months (excluded from tiers 1 and 2): {int(p['defeased'].sum()):,}. Loan-months with a "
        f"blank balance in the source: {int((p['n_blank_balance'] > 0).sum()):,}.",
        "",
        "Distress events by type (representative rows; one month can carry several):",
        "",
        md_table(pd.DataFrame({"event": ev_cols, "loan_months": [int(first_ev[c].sum()) for c in ev_cols]})),
        "",
        "## Tier 2: distress within 12 months of a performing month",
        "",
        f"- Labeled loan-months with the whole 12-month window inside the data: {len(t2):,}; with an event in the "
        f"next 12 months: {int(t2['y_distress_12m'].sum()):,} ({100 * t2['y_distress_12m'].mean():.1f}%). Tables "
        "below use these rows only.",
        f"- Labeled months whose window runs past the end of the data: {len(t2_partial):,}, of which "
        f"{int(t2_partial['y_distress_12m'].sum()):,} positive ({100 * t2_partial['y_distress_12m'].mean():.1f}%). "
        "A month there gets a label early only if an event has already happened, so these are left out of model "
        "training and testing.",
        f"- Performing months censored (the loan's observation ends inside the window with no event): "
        f"{int((rep['performing'] & rep['y_distress_12m'].isna()).sum()):,}.",
        "",
        md_table(_counts(by_type).reset_index(), floatfmt=".3f"),
        "",
        md_table(_counts(by_vint).reset_index(), floatfmt=".3f"),
        "",
        "## Tier 1: maturity outcome (gold set)",
        "",
        f"- Whole loans whose maturity plus {GRACE_DAYS} days falls inside the data: {len(t1u):,}. Outcomes: "
        f"{t1u['outcome'].value_counts().to_dict()}.",
        f"- **Tier 1 events (failed to pay within {GRACE_DAYS} days of maturity): {int(lab['y_fail'].sum()):,} of "
        f"{len(lab):,} labeled loans ({100 * lab['y_fail'].mean():.1f}%).** Maturity dates moved later by "
        f"extension at some point: {int(t1u['extended'].sum()):,}. Maturity taken from an anticipated repayment "
        f"date: {int(t1u['maturity_is_ard'].sum()):,}.",
        "",
        md_table(_counts(t1_type).reset_index(), floatfmt=".3f"),
        "",
        md_table(_counts(t1_year).reset_index().rename(columns={"maturity_eff": "maturity_year"}), floatfmt=".3f"),
        "",
        md_table(_counts(t1_vint).reset_index(), floatfmt=".3f"),
        "",
        "## Tier 3: loss severity",
        "",
        f"- Liquidated loan positions: {len(t3):,}; with a realized loss reported: "
        f"{int((~t3['flag_no_loss_reported']).sum()) if len(t3) else 0:,}. Median severity where reported: "
        f"{t3.loc[~t3['flag_no_loss_reported'], 'severity'].median() if len(t3) else float('nan'):.2f}.",
        "",
        md_table(t3_type.reset_index(), floatfmt=".3f"),
        "",
        md_table(t3_vint.reset_index(), floatfmt=".3f"),
        "",
    ]
    (paths.DOCS_DIR / "qa" / "gate2_labels.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    log("\n".join(L[6:9]))
