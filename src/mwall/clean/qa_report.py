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
    return con


def _pct(x: float) -> str:
    return f"{100 * x:.1f}%"


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
            from lp where loan_source != 'orphan_child' and coalesce(prop_type_code,'') != ''
               or loan_source in ('loan_record','note_record','replicated_child')
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
    roll = roll.merge(trusts[["trust_cik", "trust_name", "deal_family", "vintage"]], on="trust_cik", how="left")
    roll["unexplained_share"] = roll["n_exits_unexplained"] / roll["n_first_period"].clip(lower=1)
    roll["pass"] = roll["unexplained_share"] <= UNEXPLAINED_TOL
    roll.sort_values("unexplained_share", ascending=False).to_csv(qa / "loan_count_rollforward.csv", index=False)

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
    flags["share"] = flags["count"] / n_lp
    flags.to_csv(qa / "qa_flags.csv")

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
    L = [
        "# Gate 1 data QA report",
        "",
        f"Generated {dt.date.today().isoformat()} by `python -m mwall qa`. Regenerate after every ingest.",
        "",
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
