"""Cross-check our parser against edgartools on 20 filings (SOP section 7 acceptance).

edgartools (dev dependency only) is the library used in the feasibility test.
Its CMBSAssetData class parses an EX-102 string with no network access and
emits one loan row per <assets> and one property row per <property>, the same
grain as ours, so rows align by position. Every field the two share is
compared: exact for text, codes, dates, booleans and integers; 1e-9 relative
for decimals.

Writes docs/qa/library_crosscheck.md.
"""
from __future__ import annotations

import datetime as dt
import gzip
import math
import sqlite3

import pandas as pd

from mwall.common import paths
from mwall.parse import parser


def _norm(v):
    if v is None:
        return None
    if isinstance(v, float) and math.isnan(v):
        return None
    if isinstance(v, (pd.Timestamp, dt.datetime)):
        return v.date() if hasattr(v, "date") else v
    if isinstance(v, str):
        v = v.strip()
        return v or None
    return v


def _equal(a, b) -> bool:
    a, b = _norm(a), _norm(b)
    if a is None or b is None:
        return a is None and b is None
    if isinstance(a, float) or isinstance(b, float):
        try:
            fa, fb = float(a), float(b)
        except (TypeError, ValueError):
            return False
        return math.isclose(fa, fb, rel_tol=1e-9, abs_tol=1e-9)
    if isinstance(a, bool) or isinstance(b, bool):
        return bool(a) == bool(b)
    if isinstance(a, int) and isinstance(b, int):
        return a == b
    return str(a) == str(b)


def pick_filings(n: int = 20) -> pd.DataFrame:
    conn = sqlite3.connect(paths.STATE_DIR / "ingest.sqlite")
    dl = pd.read_sql("select accession, cik, raw_path from downloads where status='ok'", conn)
    dl["agent"] = dl["accession"].str[:10]
    trusts = pd.read_parquet(paths.META_DIR / "trusts.parquet")[["trust_cik", "deal_family"]]
    dl = dl.merge(trusts, left_on="cik", right_on="trust_cik")
    dl = dl.sample(frac=1.0, random_state=20261112)
    # spread across filer agents first, then families
    picked = dl.groupby("agent").head(3)
    rest = dl[~dl["accession"].isin(picked["accession"])].groupby("deal_family").head(1)
    return pd.concat([picked, rest]).head(n)


def compare_file(path) -> dict:
    from edgar.abs.cmbs import CMBSAssetData

    with gzip.open(path, "rb") as fh:
        xml = fh.read().decode("utf-8", errors="replace")
    lib = CMBSAssetData(xml)
    lib_loans, lib_props = lib.loans, lib.properties
    ours = parser.parse_file(path)
    out = {"lib_loan_rows": len(lib_loans), "our_asset_rows": len(ours.assets),
           "lib_property_rows": len(lib_props), "our_property_rows": len(ours.properties),
           "cells_compared": 0, "mismatches": []}
    if len(lib_loans) != len(ours.assets) or len(lib_props) != len(ours.properties):
        out["mismatches"].append(("row_count", None, None, None))
        return out
    for tag, col in CMBSAssetData.LOAN_FIELDS.items():
        if col not in lib_loans.columns:
            continue
        for i, our in enumerate(ours.assets):
            out["cells_compared"] += 1
            if not _equal(our.get(tag), lib_loans.iloc[i][col]):
                out["mismatches"].append(("loan", tag, our.get(tag), lib_loans.iloc[i][col]))
    for tag, col in CMBSAssetData.PROPERTY_FIELDS.items():
        if col not in lib_props.columns:
            continue
        for i, our in enumerate(ours.properties):
            out["cells_compared"] += 1
            if not _equal(our.get(tag), lib_props.iloc[i][col]):
                out["mismatches"].append(("property", tag, our.get(tag), lib_props.iloc[i][col]))
    return out


def run(n: int = 20, log=print) -> pd.DataFrame:
    from edgar.abs.cmbs import CMBSAssetData

    files = pick_filings(n)
    rows, examples = [], []
    for r in files.itertuples():
        res = compare_file(paths.DATA_DIR / r.raw_path)
        rows.append({"accession": r.accession, "family": r.deal_family, "agent": r.agent,
                     "loan_rows": res["our_asset_rows"], "property_rows": res["our_property_rows"],
                     "rows_match": res["lib_loan_rows"] == res["our_asset_rows"]
                     and res["lib_property_rows"] == res["our_property_rows"],
                     "cells_compared": res["cells_compared"], "mismatches": len(res["mismatches"])})
        examples += [(r.accession, *m) for m in res["mismatches"][:5]]
    df = pd.DataFrame(rows)
    shared_loan = len(CMBSAssetData.LOAN_FIELDS)
    shared_prop = len(CMBSAssetData.PROPERTY_FIELDS)
    L = [
        "# Parser cross-check against edgartools",
        "",
        f"edgartools {__import__('edgar').__version__} (`edgar.abs.cmbs.CMBSAssetData`), fed the same local EX-102 "
        f"files; no network. Shared fields: {shared_loan} loan-level and {shared_prop} property-level. Every shared "
        "field on every row was compared: exact for text, codes, dates, booleans and integers; relative "
        "tolerance 1e-9 for decimals.",
        "",
        f"- Filings: {len(df)} across {df['agent'].nunique()} filer agents and {df['family'].nunique()} deal families.",
        f"- Row counts identical: {int(df['rows_match'].sum())} of {len(df)}.",
        f"- Cells compared: {int(df['cells_compared'].sum()):,}. Mismatches: {int(df['mismatches'].sum()):,}.",
        "",
        "| accession | family | filer agent | loan rows | property rows | cells | mismatches |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    L += [f"| {r.accession} | {r.family} | {r.agent} | {r.loan_rows} | {r.property_rows} | {r.cells_compared:,} | "
          f"{r.mismatches} |" for r in df.itertuples()]
    if examples:
        L += ["", "First mismatches:", "", "| accession | level | tag | ours | edgartools |", "| --- | --- | --- | --- | --- |"]
        L += [f"| {e[0]} | {e[1]} | {e[2]} | {e[3]} | {e[4]} |" for e in examples[:40]]
    L += ["", "Fields the raw XML carries that edgartools does not expose include `liquidationPrepaymentCode`, "
          "`liquidationPrepaymentDate`, `realizedLossToTrustAmount`, `mostRecentSpecialServicerTransferDate`, "
          "`workoutStrategyCode` and `modificationCode`. Our parser reads all of them, which is why production "
          "uses it (SOP section 7)."]
    (paths.DOCS_DIR / "qa" / "library_crosscheck.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    log("\n".join(L[4:7]))
    return df
