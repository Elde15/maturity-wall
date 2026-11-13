"""The combined tier 1 gold set (D040, D041, D046): maturity outcomes from the EX-102 panel plus the
vintage-2016 loans read from 10-D loan detail tables, one row per whole loan.

Pari passu pieces of one loan sit in several trusts. Within the XML set they are grouped by
``whole_loan_id`` (D027). The 10-D tables carry no cross-trust identifier, so a piece is matched
on what pieces of one loan share: original maturity date, gross rate to five decimals, state,
city and the month the loan paid off (or that it has not). Matching on maturity and rate alone
joins loans in different states, so the address is required; the payoff month separates sibling
loans of one sponsor that share all the rest. A whole loan found in both sources keeps its XML label, the richer source, and the
agreement between the two labels is reported.

Writes panel/tier1_gold.parquet and docs/qa/gate2_gold_set.md.
"""
from __future__ import annotations

import datetime as dt

import duckdb
import numpy as np
import pandas as pd

from mwall.clean.code_tables import PROPERTY_GROUP
from mwall.common import paths

PILOT = paths.PARSED_DIR / "loan_detail" / "tier1.parquet"


def _norm(s: pd.Series) -> pd.Series:
    return (s.astype("string").fillna("").str.upper().str.replace(r"[^A-Z ]", "", regex=True)
            .str.replace(r"\s+", " ", regex=True).str.strip())


def match_key(maturity: pd.Series, rate: pd.Series, state: pd.Series, city: pd.Series) -> pd.Series:
    """What pari passu pieces of one loan share."""
    return (pd.to_datetime(maturity).dt.strftime("%Y-%m-%d").fillna("") + "|"
            + pd.to_numeric(rate, errors="coerce").round(5).astype("string").fillna("") + "|"
            + _norm(state) + "|" + _norm(city))


def xml_whole_loans() -> pd.DataFrame:
    t1 = pd.read_parquet(paths.PANEL_DIR / "tier1.parquet")
    wl = pd.read_parquet(paths.PARSED_DIR / "whole_loans.parquet")[["root_key", "whole_loan_id"]]
    t1 = t1.merge(wl.drop_duplicates("root_key"), on="root_key", how="left")
    t1["whole_loan_id"] = t1["whole_loan_id"].fillna(t1["root_key"])
    lp = (paths.PARSED_DIR / "loan_period" / "*.parquet").as_posix()
    attrs = duckdb.connect().execute(f"""
        select root_key, arg_min(originalInterestRatePercentage, period_end) rate,
               arg_min(prop_city, period_end) city, arg_min(prop_state, period_end) state,
               arg_min(maturityDate, period_end) original_maturity
        from read_parquet('{lp}', union_by_name=true)
        where loan_source in ('loan_record','note_record','replicated_child') group by 1""").df()
    t1 = t1.merge(attrs, on="root_key", how="left")
    t1["match_key"] = match_key(t1["original_maturity"], t1["rate"], t1["state"], t1["city"])
    t1["group_key"] = t1["match_key"] + "|" + payoff_month(t1["payoff_date"])
    return t1.sort_values("balance_first", ascending=False).drop_duplicates("whole_loan_id")


def payoff_month(s: pd.Series) -> pd.Series:
    return pd.to_datetime(s).dt.strftime("%Y-%m").fillna("open")


def pilot_whole_loans() -> pd.DataFrame:
    """Pieces of one loan also pay off in the same month: sibling loans of one sponsor can share rate,
    maturity and city (five Oakland positions at 4.14% due July 2026 are two loans, one paid in April 2026,
    one still outstanding in October)."""
    p = pd.read_parquet(PILOT)
    p["match_key"] = match_key(p["original_maturity"], p["gross_rate"], p["state"], p["city"])
    p["group_key"] = p["match_key"] + "|" + payoff_month(p["payoff_date"])
    p["property_group"] = p["prop_type"].map(PROPERTY_GROUP).fillna("other")
    p["n_pieces"] = p.groupby("group_key")["key"].transform("size")
    p["pieces_disagree"] = p.groupby("group_key")["outcome"].transform("nunique") > 1
    return p.sort_values("balance_first", ascending=False).drop_duplicates("group_key")


def build(log=print) -> pd.DataFrame | None:
    if not PILOT.exists():
        log("no 10-D loan detail labels yet: gold set is the XML set only")
    x = xml_whole_loans()
    cols = ["whole_loan_key", "source", "trust_cik", "loan_ref", "maturity", "maturity_is_ard", "property_group",
            "balance_first", "outcome", "y_fail"]
    xo = pd.DataFrame({"whole_loan_key": "XML:" + x["whole_loan_id"].astype(str), "source": "EX-102",
                       "trust_cik": x["trust_cik"], "loan_ref": x["root_key"], "maturity": x["maturity_eff"],
                       "maturity_is_ard": x["maturity_is_ard"], "property_group": x["property_group"],
                       "balance_first": x["balance_first"], "outcome": x["outcome"], "y_fail": x["y_fail"]})
    overlap = pd.DataFrame()
    parts = [xo]
    p = None
    if PILOT.exists():
        p = pilot_whole_loans()
        overlap = p.merge(x[["group_key", "match_key", "whole_loan_id", "outcome"]], on=["group_key", "match_key"],
                          suffixes=("_10d", "_xml"))
        p_only = p[~p["group_key"].isin(set(x["group_key"]))]
        parts.append(pd.DataFrame({
            "whole_loan_key": "10D:" + p_only["group_key"], "source": "10-D loan detail",
            "trust_cik": p_only["trust_cik"], "loan_ref": p_only["key"], "maturity": p_only["maturity"],
            "maturity_is_ard": p_only["maturity_is_ard"], "property_group": p_only["property_group"],
            "balance_first": p_only["balance_first"], "outcome": p_only["outcome"], "y_fail": p_only["y_fail"]}))
    gold = pd.concat(parts, ignore_index=True)[cols]
    gold.to_parquet(paths.PANEL_DIR / "tier1_gold.parquet", index=False)
    report(gold, x, p, overlap, log)
    return gold


def report(gold: pd.DataFrame, x: pd.DataFrame, p: pd.DataFrame | None, overlap: pd.DataFrame, log=print) -> None:
    from mwall.clean.qa_report import md_table

    lab = gold[gold["y_fail"].notna()]
    by_src = lab.groupby("source")["y_fail"].agg(loans="size", failed="sum", rate="mean")
    by_type = lab.pivot_table(index="property_group", columns="source", values="y_fail", aggfunc=["size", "sum"],
                              fill_value=0)
    by_type.columns = [f"{'loans' if a == 'size' else 'failed'} {b}" for a, b in by_type.columns]
    by_type["failure rate, both"] = lab.groupby("property_group")["y_fail"].mean()
    by_year = lab.groupby([lab["maturity"].dt.year.rename("maturity_year"), "source"])["y_fail"].agg(
        loans="size", failed="sum").unstack(fill_value=0)
    by_year.columns = [f"{a} {b}" for a, b in by_year.columns]
    for t in (by_src, by_type, by_year):
        for c in t.columns:
            if c.startswith(("failed", "loans")):
                t[c] = t[c].astype("int64")
    L = ["# Tier 1 gold set: EX-102 and 10-D loan detail combined", "",
         f"Generated {dt.date.today().isoformat()} by `python -m mwall panel`. One row per whole loan "
         "(`panel/tier1_gold.parquet`). Rules: docs/labels.md; sources D040, D041, D046.", "",
         f"- **Labeled whole loans: {len(lab):,}; failed to pay within 90 days of maturity: {int(lab['y_fail'].sum()):,} "
         f"({100 * lab['y_fail'].mean():.1f}%).**", ""]
    if p is not None:
        lab_both = overlap[overlap["outcome_10d"].isin(["paid", "failed"]) & overlap["outcome_xml"].isin(["paid", "failed"])]
        agree = int((lab_both["outcome_10d"] == lab_both["outcome_xml"]).sum())
        L += [f"- 10-D loan detail: {int(p['n_pieces'].sum()):,} loan positions in the window are {len(p):,} whole "
              f"loans after pari passu matching ({int((p['n_pieces'] > 1).sum()):,} loans held in two or more of the "
              f"vintage-2016 trusts). Pieces of one loan with different outcomes: {int(p['pieces_disagree'].sum()):,}.",
              f"- Whole loans found in both sources: {overlap['group_key'].nunique():,}; they keep the EX-102 label. "
              f"Where both sources label the loan paid or failed, the labels agree in {agree} of {len(lab_both)}.", "",
              md_table(pd.crosstab(overlap["outcome_10d"], overlap["outcome_xml"]).reset_index()), ""]
    L += ["## By source", "", md_table(by_src.reset_index(), floatfmt=".3f"), "",
          "## By property type", "", md_table(by_type.reset_index(), floatfmt=".3f"), "",
          "## By maturity year", "", md_table(by_year.reset_index()), ""]
    (paths.DOCS_DIR / "qa" / "gate2_gold_set.md").write_text("\n".join(L), encoding="utf-8")
    log(f"gold set: {len(lab):,} labeled whole loans, {int(lab['y_fail'].sum()):,} failed")
