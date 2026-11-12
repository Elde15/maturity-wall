"""Cross-trust whole-loan grouping (SOP section 8, step 2).

A large loan is often split into pari passu notes held by several trusts, and
each trust reports the same property, NOI and appraisal for its own piece.
Pieces of one whole loan share the borrower's terms, so they are matched on:

    property ZIP (5 digits) + origination date + maturity date + coupon (4 dp)

using each loan's latest reported record. The key is deliberately strict: a
false match would merge two different loans, which is worse than a missed one.
The report sizes how much a naive cross-trust sum would double count.

Writes parsed/whole_loans.parquet (loan_key -> whole_loan_id) and
docs/qa/whole_loans.md.
"""
from __future__ import annotations

import hashlib

import duckdb
import pandas as pd

from mwall.common import paths


def build(log=print) -> pd.DataFrame:
    con = duckdb.connect()
    lp = (paths.PARSED_DIR / "loan_period" / "*.parquet").as_posix()
    latest = con.execute(f"""
        select * from (
            select trust_cik, loan_key, root_key, loanStructureCode, prop_zip, prop_name, prop_city, prop_state,
                   originationDate, maturityDate, round(interestRateSecuritizationPercentage, 4) coupon,
                   balance, originalLoanAmount, fin_noi_annual, val_securitization, wl_balance_est, period_end,
                   row_number() over (partition by loan_key order by period_end desc) rn
            from read_parquet('{lp}', union_by_name=true)
            where loan_source in ('loan_record', 'note_record', 'replicated_child')
        ) where rn = 1""").df()
    latest["zip5"] = latest["prop_zip"].astype(str).str.extract(r"(\d{5})")[0]
    ok = latest["zip5"].notna() & latest["originationDate"].notna() & latest["maturityDate"].notna()
    latest["match_key"] = None
    latest.loc[ok, "match_key"] = (latest.loc[ok, "zip5"] + "|" + latest.loc[ok, "originationDate"].astype(str) + "|"
                                   + latest.loc[ok, "maturityDate"].astype(str) + "|"
                                   + latest.loc[ok, "coupon"].round(4).astype(str))
    # notes of one loan inside one trust share a root; collapse to one row per (trust, root) first
    latest["whole_loan_id"] = latest["match_key"].map(
        lambda k: "WL" + hashlib.sha1(k.encode()).hexdigest()[:12] if isinstance(k, str) else None)
    latest["whole_loan_id"] = latest["whole_loan_id"].fillna("WL-" + latest["root_key"].astype(str))
    n_trusts = latest.groupby("whole_loan_id")["trust_cik"].transform("nunique")
    latest["n_trusts_holding"] = n_trusts
    out = latest[["loan_key", "root_key", "trust_cik", "whole_loan_id", "n_trusts_holding", "match_key"]]
    out.to_parquet(paths.PARSED_DIR / "whole_loans.parquet", index=False)

    # sizing the double count: one row per (trust, root) for collateral fields
    per_root = latest.sort_values("balance", ascending=False).groupby(["trust_cik", "root_key"]).head(1)
    multi = per_root[per_root["n_trusts_holding"] > 1]
    naive_val = per_root["val_securitization"].sum()
    dedup_val = per_root.drop_duplicates("whole_loan_id")["val_securitization"].sum()
    naive_noi = per_root["fin_noi_annual"].sum()
    dedup_noi = per_root.drop_duplicates("whole_loan_id")["fin_noi_annual"].sum()
    split = per_root.groupby("whole_loan_id")["trust_cik"].nunique()
    pieces = latest[latest["loanStructureCode"].isin(["PP", "A1", "A2", "B1", "B2", "C2"])]
    pieces_matched = (pieces["n_trusts_holding"] > 1).mean() if len(pieces) else float("nan")

    L = [
        "# Whole loans across trusts",
        "",
        "Pieces of one whole loan held by different trusts are grouped on property ZIP, origination date, "
        "maturity date and coupon (`clean/whole_loans.py`).",
        "",
        f"- Loans (latest record each): {len(latest):,}; with a usable match key: {int(ok.sum()):,}.",
        f"- Whole loans held by more than one registered trust: {int((split > 1).sum()):,} "
        f"(by trust count: {split[split > 1].value_counts().sort_index().to_dict()}).",
        f"- Trust-level records that belong to a multi-trust whole loan: {len(multi):,} of {len(per_root):,}.",
        f"- Pari passu or A/B-note pieces matched to at least one other registered trust: "
        f"{100 * pieces_matched:.1f}%. The rest have their companion notes in unregistered (144A) deals or "
        "in trusts not yet ingested.",
        "",
        "Effect on aggregates if trusts were simply summed:",
        "",
        f"- Appraised value at securitization: ${naive_val / 1e9:,.1f}B summed vs ${dedup_val / 1e9:,.1f}B "
        f"counting each whole loan once ({100 * (naive_val / dedup_val - 1):.1f}% overstatement).",
        f"- Annualized NOI: ${naive_noi / 1e9:,.2f}B summed vs ${dedup_noi / 1e9:,.2f}B "
        f"({100 * (naive_noi / dedup_noi - 1):.1f}% overstatement).",
        "",
        "Rule for every published aggregate of collateral (NOI, value, square feet, property counts): count each "
        "`whole_loan_id` once. Balances are not affected, because each trust reports only its own piece.",
        "",
    ]
    (paths.DOCS_DIR / "qa" / "whole_loans.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    log("\n".join(L[4:13]))
    return out
