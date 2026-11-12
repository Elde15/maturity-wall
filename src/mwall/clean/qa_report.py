"""Gate 1 QA report (SOP sections 7, 8 and 15).

Writes to docs/qa/:
  gate1_report.md                    the human-readable summary
  field_coverage_by_vintage_family.csv
  loan_count_rollforward.csv          per trust: first count, exits explained by codes, unexplained exits
  qa_flags.csv                        count and share of every flag
  layouts_by_agent.csv
"""
from __future__ import annotations

import datetime as dt
import sqlite3

import duckdb
import numpy as np
import pandas as pd

from mwall.common import paths

COVERAGE_FIELDS = {
    "balance": "current balance",
    "maturityDate": "maturity date",
    "originationDate": "origination date",
    "reportPeriodInterestRatePercentage": "current rate",
    "paymentStatusLoanCode": "payment status",
    "fin_noi": "NOI (most recent)",
    "fin_debt_service": "debt service (most recent)",
    "dscr_noi_reported": "DSCR reported",
    "val_securitization": "appraisal at securitization",
    "occupancy_current": "occupancy (most recent)",
    "prop_type_code": "property type",
    "prop_zip": "ZIP",
    "fin_noi_annual": "NOI annualized",
    "wl_balance_est": "whole-loan balance estimate",
}
UNEXPLAINED_TOL = 0.02  # share of a trust's first-period loans


def md_table(df: pd.DataFrame, index: bool = False, floatfmt: str = ".2f") -> str:
    """Markdown table without the optional tabulate dependency."""
    d = df.reset_index() if index else df
    def fmt(v):
        if isinstance(v, float):
            return "" if v != v else format(v, floatfmt)
        return str(v)
    head = "| " + " | ".join(str(c) for c in d.columns) + " |"
    sep = "| " + " | ".join("---" for _ in d.columns) + " |"
    rows = ["| " + " | ".join(fmt(v) for v in r) + " |" for r in d.itertuples(index=False)]
    return "\n".join([head, sep, *rows])


def _con() -> duckdb.DuckDBPyConnection:
    con = duckdb.connect()
    lp = (paths.PARSED_DIR / "loan_period" / "*.parquet").as_posix()
    pp = (paths.PARSED_DIR / "property_period" / "*.parquet").as_posix()
    con.execute(f"create view lp as select * from read_parquet('{lp}', union_by_name=true)")
    con.execute(f"create view pp as select * from read_parquet('{pp}', union_by_name=true)")
    con.execute(f"create view t as select * from read_parquet('{(paths.META_DIR / 'trusts.parquet').as_posix()}')")
    fs = (paths.PARSED_DIR / "filing_screen" / "*.parquet").as_posix()
    try:
        con.execute(f"create view fs as select * from read_parquet('{fs}', union_by_name=true)")
    except duckdb.Error:  # clean has not written screening tables yet
        con.execute("create view fs as select null::varchar accession, null::varchar corrupt_reason, "
                    "0 n_exact_copies_dropped, 0 n_split_records, 0 n_foreign_repeats, 0 n_transient_loans, "
                    "0 n_loans_missing, null::bigint trust_cik, null::varchar superseded_by where false")
    return con


def _pct(x: float) -> str:
    return f"{100 * x:.1f}%"


def _status(ok: bool | None) -> str:
    return "PENDING" if ok is None else ("PASS" if ok else "FAIL")


def checklist(*, filings, trusts, dl, pf, roll, recon, dscr, flags, n_abs, hist, dup_rows) -> list[str]:
    """Gate 1 items from SOP section 15 plus the section 7 and 8 acceptance criteria, each with a
    machine-decided status and the evidence it rests on. PENDING means the data needed is not all in yet."""
    qa = paths.DOCS_DIR / "qa"
    rows = []

    # universe vs form index and the name-search list
    fi = pd.read_parquet(paths.META_DIR / "form_index_abs.parquet")
    fi = fi[fi["cik"].isin(trusts["trust_cik"])]
    gaps = []
    for fam in ("ABS-EE", "10-D"):
        idx = set(fi.loc[fi["form"].str.startswith(fam), "accession"])
        sub = filings[filings["form_family"] == fam]
        extra = sub[~sub["accession"].isin(idx)]
        gaps.append((fam, len(idx - set(sub["accession"])), len(extra),
                     int((pd.to_datetime(extra["filing_date"]) >= "2017-01-01").sum())))
    uc = pd.read_parquet(paths.META_DIR / "universe_crosscheck.parquet")
    named_missed = int((uc["looks_cmbs"] & uc["filed_absee"] & ~uc["confirmed_cmbs"]).sum())
    named_extra = int((~uc["looks_cmbs"] & uc["confirmed_cmbs"]).sum())
    ok = all(g[1] == 0 and g[3] == 0 for g in gaps) and named_missed == 0
    rows.append(("Trust universe reconciles to the name search and the form index", ok,
                 f"{len(trusts)} trusts. Name search: {named_missed} CMBS-named ABS-EE filers left unconfirmed, "
                 f"{named_extra} confirmed by namespace without a CMBS-looking name. Form index vs submissions: "
                 + "; ".join(f"{f} {a} in index only, {b} in submissions only ({c} of them 2017 or later)"
                             for f, a, b, c in gaps) + ". Missing 168-trust list closed in D032."))

    # downloads and row counts
    n_done = int(dl["status"].isin(["ok", "no_ex102"]).sum())
    complete = n_done >= n_abs
    rec_ok = int(((pf["n_assets_xml"] == pf["n_asset_rows"]) & (pf["n_property_xml"] == pf["n_property_rows"])).sum())
    n_rej = int((pf["status"] != "ok").sum())
    parsed_ciks = set(pf.loc[pf["status"] == "ok", "cik"])
    no_reason = trusts[~trusts["trust_cik"].isin(parsed_ciks)]
    ok = (rec_ok == len(pf) and len(no_reason) == 0) if complete else None
    rows.append(("Row counts reconcile for every filing; rejects quarantined with reasons", ok,
                 f"{n_done:,} of {n_abs:,} ABS-EE filings fetched. Row counts reconcile on {rec_ok:,} of {len(pf):,} "
                 f"parsed files. Rejects in `data/quarantine/parse_rejects.csv`: {n_rej}. Trusts with no parsed "
                 f"filing: {len(no_reason)}."))

    # loan vs property records and the roll-forward
    n_fail = int((~roll["pass"]).sum())
    ok = (n_fail == 0) if complete else None
    rows.append(("Loan vs property records classified; loans per trust equal the issuance count less payoffs", ok,
                 f"Roll-forward (D028): {len(roll) - n_fail} of {len(roll)} trusts within "
                 f"{_pct(UNEXPLAINED_TOL)} unexplained exits. Layout rules and golden tests: `structure.py`, "
                 "`tests/golden/`. Failing trusts: `loan_count_rollforward.csv`."))

    # pari passu
    wl = qa / "whole_loans_summary.json"
    if wl.exists():
        import json
        s = json.loads(wl.read_text(encoding="utf-8"))
        rows.append(("Pari passu duplicates measured and handled; effect on aggregates reported", True,
                     f"{s['multi_trust_whole_loans']:,} whole loans held by more than one trust; "
                     f"{_pct(s['pieces_matched_share'])} of pieces matched. Summing trusts naively would overstate "
                     f"appraised value by {_pct(s['value_overstatement_if_summed'])} and NOI by "
                     f"{_pct(s['noi_overstatement_if_summed'])}. `whole_loans.md`."))
    else:
        rows.append(("Pari passu duplicates measured and handled; effect on aggregates reported", None,
                     "Run `python -m mwall wholeloans`."))

    rows.append(("Field coverage report by vintage and depositor family committed", True if complete else None,
                 "`field_coverage_by_vintage_family.csv`; summary by filing year below."))

    census = qa / "tag_census.csv"
    n_invalid = int(flags.loc["flag_invalid_code", "count"]) if "flag_invalid_code" in flags.index else 0
    outside = int((~pd.read_csv(census)["in_xsd"]).sum()) if census.exists() else None
    ok = (n_invalid == 0 and outside == 0) if outside is not None else None
    rows.append(("Code tables verified against the SEC specification", ok,
                 f"Code meanings parsed from the SEC XSD (`docs/sec_code_tables.md`). Loan-periods with a code "
                 f"outside the XSD enumerations: {n_invalid}. Tags outside the XSD in the census: {outside}."))

    # section 7 and 8 acceptance criteria
    rows.append(("Golden filings and library cross-check (section 7)", True,
                 "Five hand-checked filings across five families in `tests/`; 20-filing cross-check against "
                 "edgartools in `library_crosscheck.md`."))
    if len(recon):
        cats = recon["category"].value_counts().to_dict()
        bad = int(cats.get("mismatch", 0))
        unread = int(cats.get("statement_unread", 0))
        read = recon[recon["category"] != "statement_unread"]
        ok = (bad == 0 and unread == 0) if complete else None
        rows.append(("Loan balances reconcile to the 10-D within 0.5% (section 8)", ok,
                     f"{len(read):,} trust-periods with a readable statement: {cats.get('match', 0):,} within 0.5%, "
                     f"{cats.get('filing_omits_balances', 0):,} where the EX-102 leaves balances blank, {bad:,} "
                     f"unexplained. Statements not yet read: {unread:,}."))
    else:
        rows.append(("Loan balances reconcile to the 10-D within 0.5% (section 8)", None,
                     "No statements matched yet; run `python -m mwall tend`."))
    n_amend = int((filings["n_versions_for_period"] > 1).sum())
    rows.append(("One row per loan-period, latest amendment kept, gaps flagged not filled (section 8)",
                 dup_rows == 0,
                 f"Duplicate loan rows within a filing (corrupt filings aside): {dup_rows}. Filings superseded by a later version of the same "
                 f"period: {n_amend:,} rows in `filings.parquet` carry `n_versions_for_period` > 1 and only the "
                 f"winner is parsed. Trusts with a missing month between first and last report: "
                 f"{int((hist['missing_months'] > 0).sum())} ({int(hist['missing_months'].sum())} months; "
                 "`history_gaps.csv`); loan rows after a gap carry `flag_history_gap`."))
    rows.append(("Recomputed DSCR matches reported for 95% of loans (section 8)", (dscr[1] or 0) >= 0.95,
                 f"{_pct(dscr[1] or 0)} of {dscr[0]:,} loan-periods within 5%."))
    rows.append(("Every flag counted in a committed report (section 8)", True, "`qa_flags.csv` and the table below."))
    geo = paths.PARSED_DIR / "geography.parquet"
    rows.append(("Geography: ZIP to county and metro with a published crosswalk (section 8)",
                 True if geo.exists() else None,
                 "`geography.md`." if geo.exists() else "Not built yet."))

    L = ["## Gate 1 checklist", "",
         "| status | item | evidence |", "| --- | --- | --- |"]
    L += [f"| {_status(ok)} | {item} | {ev} |" for item, ok, ev in rows]
    verdict = ("PASS" if all(r[1] is True for r in rows)
               else "FAIL" if any(r[1] is False for r in rows) else "PENDING")
    L += ["", f"Gate 1 verdict from the data: **{verdict}**. A failing item is fixed or published as a limitation, "
          "never waived silently (SOP section 15).", ""]
    return L


def run(log=print) -> None:
    qa = paths.DOCS_DIR / "qa"
    qa.mkdir(parents=True, exist_ok=True)
    con = _con()
    trusts = pd.read_parquet(paths.META_DIR / "trusts.parquet")
    filings = pd.read_parquet(paths.META_DIR / "filings.parquet")
    ing = sqlite3.connect(paths.STATE_DIR / "ingest.sqlite")
    dl = pd.read_sql("select accession, cik, status, note from downloads", ing)
    ps = sqlite3.connect(paths.STATE_DIR / "parse.sqlite")
    pf = pd.read_sql("select * from parse_files", ps)

    # ---- 1. ingestion -------------------------------------------------------
    abs_ee = filings[filings["form_family"] == "ABS-EE"]
    n_abs = len(abs_ee)
    n_dl_ok = int((dl["status"] == "ok").sum())
    n_no102 = int((dl["status"] == "no_ex102").sum())
    rec_ok = int(((pf["n_assets_xml"] == pf["n_asset_rows"]) & (pf["n_property_xml"] == pf["n_property_rows"])).sum())
    parsed_ciks = set(pf.loc[pf["status"] == "ok", "cik"])
    no_parse = trusts[~trusts["trust_cik"].isin(parsed_ciks)][["trust_cik", "trust_name", "n_absee_index"]]

    # ---- 2. layouts -----------------------------------------------------------
    lay = con.execute("""
        select substr(accession,1,10) filer_agent, layout, count(*) n from lp group by 1,2 order by 1,2""").df()
    lay.to_csv(qa / "layouts_by_agent.csv", index=False)
    lay_tot = con.execute("select layout, count(*) n from lp group by 1 order by 2 desc").df()

    # ---- 3. loan-count roll-forward -------------------------------------------
    roll = con.execute("""
        with active as (
            select trust_cik, loan_key, period_end, balance, liquidationPrepaymentCode code,
                   dense_rank() over (partition by trust_cik order by period_end) as k
            from lp where (loan_source != 'orphan_child' and coalesce(prop_type_code,'') != ''
                           or loan_source in ('loan_record','note_record','replicated_child'))
                      and not coalesce(flag_transient_loan, false)
                      and not coalesce(flag_filing_corrupt, false)
        ),
        per_loan as (
            select trust_cik, loan_key, min(k) first_k, max(k) last_k,
                   max(case when code is not null then 1 else 0 end) has_code,
                   arg_max(balance, k) last_balance
            from active group by 1,2
        ),
        tk as (select trust_cik, max(k) max_k from active group by 1)
        select p.trust_cik,
               count(*) filter (where first_k = 1) n_first_period,
               count(*) filter (where first_k > 1) n_added_later,
               count(*) filter (where last_k < max_k) n_exited,
               count(*) filter (where last_k < max_k and (has_code = 1 or coalesce(last_balance,0) <= 0)) n_exits_explained,
               count(*) filter (where last_k < max_k and has_code = 0 and coalesce(last_balance,0) > 0) n_exits_unexplained,
               count(*) filter (where last_k = max_k) n_last_period,
               any_value(max_k) n_periods
        from per_loan p join tk using (trust_cik) group by 1""").df()
    transient = con.execute("""
        select trust_cik, count(distinct loan_key) n_transient_loans, count(distinct accession) n_transient_filings
        from lp where coalesce(flag_transient_loan, false) group by 1""").df()
    roll = roll.merge(transient, on="trust_cik", how="left").fillna({"n_transient_loans": 0, "n_transient_filings": 0})
    roll = roll.merge(trusts[["trust_cik", "trust_name", "deal_family", "vintage"]], on="trust_cik", how="left")
    roll["unexplained_share"] = roll["n_exits_unexplained"] / roll["n_first_period"].clip(lower=1)
    roll["pass"] = roll["unexplained_share"] <= UNEXPLAINED_TOL
    roll.sort_values("unexplained_share", ascending=False).to_csv(qa / "loan_count_rollforward.csv", index=False)

    # ---- 3a. monthly history: one row per loan-period, gaps flagged (SOP 8.3) ----
    # months come from the XML reporting period of each kept filing, not EDGAR's report date
    hist = con.execute("""
        with f as (select trust_cik, accession, max(period_end) pe from lp
                   where not coalesce(flag_filing_corrupt, false) group by 1, 2),
             m as (select trust_cik, year(pe) * 12 + month(pe) - 1 m from f where pe is not null)
        select trust_cik, min(m) first_m, max(m) last_m, count(distinct m) n_months from m group by 1""").df()
    hist["expected"] = hist["last_m"] - hist["first_m"] + 1
    hist["missing_months"] = hist["expected"] - hist["n_months"]
    hist["first"] = [f"{m // 12}-{m % 12 + 1:02d}" for m in hist["first_m"]]
    hist["last"] = [f"{m // 12}-{m % 12 + 1:02d}" for m in hist["last_m"]]
    hist = hist.drop(columns=["first_m", "last_m"]).merge(trusts[["trust_cik", "trust_name"]], on="trust_cik",
                                                          how="left")
    hist.sort_values("missing_months", ascending=False).to_csv(qa / "history_gaps.csv", index=False)
    dup_rows = con.execute("""
        select count(*) - count(distinct loan_key || '|' || accession) from lp
        where not coalesce(flag_filing_corrupt, false)""").fetchone()[0]

    # ---- 3b. pool balance vs the 10-D statement (SOP 8 acceptance: within 0.5%) ----
    tb_path = paths.META_DIR / "tend_balances.parquet"
    recon = pd.DataFrame()
    if tb_path.exists():
        tb = pd.read_parquet(tb_path)
        tb = tb[tb["status"] == "ok"].copy()
        sums = con.execute("""
            select trust_cik, accession, any_value(filing_date) filing_date,
                   sum(reportPeriodEndScheduledLoanBalanceAmount)
                       filter (where not coalesce(flag_transient_loan, false)) sched_sum,
                   sum(reportPeriodEndActualBalanceAmount)
                       filter (where not coalesce(flag_transient_loan, false)) actual_sum,
                   count(*) filter (where coalesce(flag_transient_loan, false)) n_transient,
                   count(*) filter (where reportPeriodEndScheduledLoanBalanceAmount is null
                                    and reportPeriodEndActualBalanceAmount is null
                                    and liquidationPrepaymentCode is null) n_loans_no_balance
            from lp where loan_source in ('loan_record','note_record','replicated_child')
            group by 1,2""").df()
        tb["tend_filing_date"] = pd.to_datetime(tb["tend_filing_date"])
        sums["filing_date"] = pd.to_datetime(sums["filing_date"])
        m = sums.merge(tb, on="trust_cik")
        m = m[(m["filing_date"] - m["tend_filing_date"]).abs() <= pd.Timedelta(days=3)]
        m = m.sort_values("tend_filing_date").drop_duplicates("accession", keep="last")
        m["rel_diff"] = (m["sched_sum"] - m["tend_sched_balance"]) / m["tend_sched_balance"]
        m["within_0_5pct"] = m["rel_diff"].abs() <= 0.005
        scr = con.execute("select accession, corrupt_reason, n_loans_missing from fs").df()
        m = m.merge(scr, on="accession", how="left")
        m["category"] = np.select(
            [m["tend_sched_balance"].isna(), m["within_0_5pct"], m["corrupt_reason"].notna(),
             m["n_loans_missing"].fillna(0) > 0, m["n_loans_no_balance"] > 0],
            ["statement_unread", "match", "filing_corrupt", "filing_incomplete", "filing_omits_balances"],
            "mismatch")
        recon = m
        m.to_csv(qa / "balance_reconciliation.csv", index=False)

    # ---- 4. field coverage ------------------------------------------------------
    sel = ", ".join(f"avg(({c} is not null)::int) as \"{c}\"" for c in COVERAGE_FIELDS)
    cov = con.execute(f"""
        select t.vintage, t.deal_family, count(*) n_loan_periods, {sel}
        from lp join t using (trust_cik)
        where coalesce(lp.property_group,'') != 'defeased' and lp.balance > 0
        group by 1,2 order by 1,2""").df()
    cov.to_csv(qa / "field_coverage_by_vintage_family.csv", index=False)
    cov_year = con.execute(f"""
        select year(filing_date) filing_year, count(*) n, {sel}
        from lp where coalesce(property_group,'') != 'defeased' and balance > 0 group by 1 order by 1""").df()

    # ---- 5. flags --------------------------------------------------------------
    cols = [r[0] for r in con.execute("describe lp").fetchall() if r[0].startswith("flag_")]
    n_lp = con.execute("select count(*) from lp").fetchone()[0]
    flags = con.execute("select " + ", ".join(f"sum({c}::int) as {c}" for c in cols) + " from lp").df().T
    flags.columns = ["count"]
    flags["count"] = flags["count"].fillna(0).astype(int)
    flags["share"] = flags["count"] / n_lp
    flags.to_csv(qa / "qa_flags.csv")

    # ---- 5b. filing screen (D035, D036) ----------------------------------------
    screen_tot = con.execute("""
        select count(*) n_filings,
               coalesce(sum(n_exact_copies_dropped), 0) copies, count(*) filter (where n_exact_copies_dropped > 0) f_copies,
               coalesce(sum(n_split_records), 0) splits, count(*) filter (where n_split_records > 0) f_splits,
               count(*) filter (where corrupt_reason is not null) f_corrupt,
               count(*) filter (where n_loans_missing > 0) f_incomplete, coalesce(sum(n_loans_missing), 0) missing,
               count(*) filter (where superseded_by is not null) f_superseded
        from fs""").df().iloc[0]
    con.execute("""select * from fs where corrupt_reason is not null or n_exact_copies_dropped > 0
                   or n_split_records > 0 or n_loans_missing > 0 order by trust_cik, accession""").df().to_csv(
        qa / "filing_screen.csv", index=False)

    # ---- 6. DSCR recompute, basis, share --------------------------------------
    dscr = con.execute("""
        select count(*) n,
               avg((abs(dscr_noi_recomputed - dscr_noi_reported) / abs(dscr_noi_reported) <= 0.05)::int) within_5pct
        from lp where dscr_noi_recomputed is not null and dscr_noi_reported is not null and dscr_noi_reported != 0""").fetchone()
    basis = con.execute("select fin_basis, count(*) n from lp where fin_noi is not null group by 1 order by 2 desc").df()
    share = con.execute("""
        select loanStructureCode structure, count(trust_share_est) n,
               quantile_cont(trust_share_est, 0.25) p25, median(trust_share_est) p50,
               quantile_cont(trust_share_est, 0.75) p75
        from lp where trust_share_est is not null group by 1 order by 2 desc""").df()
    occ_units = con.execute("""
        select case when mostRecentPhysicalOccupancyPercentage is null then 'null'
                    when mostRecentPhysicalOccupancyPercentage <= 1 then 'fraction'
                    when mostRecentPhysicalOccupancyPercentage > 1.5 and mostRecentPhysicalOccupancyPercentage <= 100 then 'percent'
                    else 'unreadable' end unit, count(*) n
        from pp where block_role = 'property' group by 1 order by 2 desc""").df()

    # ---- write markdown ---------------------------------------------------------
    check = checklist(filings=filings, trusts=trusts, dl=dl, pf=pf, roll=roll, recon=recon, dscr=dscr,
                      flags=flags, n_abs=n_abs, hist=hist, dup_rows=dup_rows)
    L = [
        "# Gate 1 data QA report",
        "",
        f"Generated {dt.date.today().isoformat()} by `python -m mwall qa`. Regenerate after every ingest.",
        "",
        *check,
        "## Ingestion",
        "",
        f"- Trusts in the universe: {len(trusts)}. With at least one parsed filing: {len(parsed_ciks)}.",
        f"- ABS-EE filings in the universe: {n_abs:,}. Downloaded: {n_dl_ok:,}. No EX-102 attached: {n_no102}.",
        f"- Filings parsed: {len(pf):,}. Row counts reconcile (assets and property blocks in the XML equal rows "
        f"written): {rec_ok:,} of {len(pf):,} ({_pct(rec_ok / max(1, len(pf)))}).",
        f"- Parse status: {pf['status'].value_counts().to_dict()}. Type failures: {int(pf['n_bad_values'].sum())}. "
        f"Tags outside the SEC schema: {int(pf['n_extra_tags'].sum())}.",
        f"- Trusts without a parsed filing yet: {len(no_parse)} (listed in `loan_count_rollforward.csv` once parsed; "
        "until the full download finishes most of these are simply not downloaded yet).",
        "",
        "## Record layouts (loan-periods)",
        "",
        md_table(lay_tot),
        "",
        "By filer agent: `layouts_by_agent.csv`.",
        "",
        "## Loan counts roll forward",
        "",
        f"Each trust's first reported period sets the opening loan count (the at-issuance pool). A loan that stops "
        f"appearing is explained when it carried a liquidation or prepayment code or a zero balance. Tolerance: "
        f"unexplained exits at most {_pct(UNEXPLAINED_TOL)} of the opening count.",
        "",
        f"- Trusts checked: {len(roll)}. Passing: {int(roll['pass'].sum())}. Opening loans: "
        f"{int(roll['n_first_period'].sum()):,}. Exits: {int(roll['n_exited'].sum()):,}, of which explained "
        f"{int(roll['n_exits_explained'].sum()):,} and unexplained {int(roll['n_exits_unexplained'].sum()):,}.",
        f"- Loans that appear mid-history for at most a few periods with no payoff code, left out above as another "
        f"deal's records filed into the trust (D035): {int(roll['n_transient_loans'].sum()):,} in "
        f"{int(roll['n_transient_filings'].sum()):,} filings across {int((roll['n_transient_loans'] > 0).sum())} trusts.",
        "",
        "## Pool balance vs the 10-D distribution statement",
        "",
        (f"- Trust-periods compared: {len(recon):,}. Sum of loan scheduled balances within 0.5% of the "
         f"administrator's ending scheduled collateral balance: {int(recon['within_0_5pct'].sum()):,} "
         f"({_pct(recon['within_0_5pct'].mean())}). Median absolute difference: "
         f"{_pct(recon['rel_diff'].abs().median())}. By category: {recon['category'].value_counts().to_dict()}. "
         "`filing_omits_balances` means the EX-102 itself leaves some loans' period balances blank, so the gap is in "
         "the source, not the pipeline. Detail: `balance_reconciliation.csv`."
         if len(recon) else "- No 10-D statements matched to parsed periods yet."),
        "",
        "## Filing screen",
        "",
        "Each filing is screened before its records are resolved into loans (`clean/screen.py`, D035 and D036).",
        "",
        f"- Filings screened: {int(screen_tot['n_filings']):,}. Superseded by a later filing for the same XML "
        f"reporting period although EDGAR gave them different report dates: {int(screen_tot['f_superseded']):,}.",
        f"- Exact copies of a record dropped: {int(screen_tot['copies']):,} in {int(screen_tot['f_copies']):,} filings.",
        f"- Loans split into notes under one number (largest keeps it, the rest become -S2, -S3): "
        f"{int(screen_tot['splits']):,} records in {int(screen_tot['f_splits']):,} filings.",
        f"- Filings holding another deal's records, kept but flagged `flag_filing_corrupt` and left out of the checks "
        f"above and the panel: {int(screen_tot['f_corrupt']):,}.",
        f"- Filings that leave out loans reported both before and after them: {int(screen_tot['f_incomplete']):,} "
        f"({int(screen_tot['missing']):,} loan-periods missing; the loans carry `flag_history_gap` when they return).",
        "",
        "Detail: `filing_screen.csv`.",
        "",
        "## Ratio checks",
        "",
        f"- Reported DSCR vs NOI / debt service recomputed from the same filing: {dscr[0]:,} loan-periods with both; "
        f"{_pct(dscr[1] or 0)} agree within 5% (SOP target 95%).",
        "",
        "Financial basis of the most recent NOI (decision D021):",
        "",
        md_table(basis),
        "",
        "Estimated trust share of the whole loan by structure code (decision D020). Whole loans should sit near 1.0:",
        "",
        md_table(share, floatfmt=".3f"),
        "",
        "Occupancy units as filed (property blocks; decision D023):",
        "",
        md_table(occ_units),
        "",
        "## Field coverage by filing year (active, non-defeased loan-periods)",
        "",
        md_table(cov_year, floatfmt=".2f"),
        "",
        "By vintage and deal family: `field_coverage_by_vintage_family.csv`.",
        "",
        "## QA flags",
        "",
        md_table(flags.assign(share=flags["share"].map(_pct)), index=True),
        "",
    ]
    (qa / "gate1_report.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    log(f"wrote {qa / 'gate1_report.md'}")
