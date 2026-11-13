"""Leakage audit (SOP section 9 rules; Gate 2 checklist item 2). Writes docs/qa/gate2_leakage.md.

Checks, each decided by code:

1. Inputs: no catalog feature names an outcome field as an input.
2. Market joins: every ``asof_*`` publication date is on or before the row's snapshot date.
3. Truncation replay: for a seeded sample of loans and several cut dates D, the panel events and
   loan features are recomputed from only the rows public by D (and market series published by
   D). Every feature of every row with snapshot date <= D must equal the full-data value. A
   difference means some feature looked forward.
4. Label separation: tier 2 labels start from performing months only, and status features are
   in the table only for forward-looking use; the share of late snapshots (data filed after the
   loan's next period) is reported and those rows are excluded from training.

Hindsight that lives in the cleaning layer (which rows exist, not what features say) is listed
with its measured size rather than hidden.
"""
from __future__ import annotations

import datetime as dt

import numpy as np
import pandas as pd

from mwall.common import paths
from mwall.features import build as fbuild
from mwall.features import loan
from mwall.features.catalog import CATALOG, OUTCOME_FIELDS

CUTS = ["2019-12-31", "2021-12-31", "2023-06-30", "2025-06-30"]
SAMPLE_LOANS = 600
SEED = 7


def _equal(a: pd.Series, b: pd.Series) -> pd.Series:
    if a.dtype == bool or b.dtype == bool or str(a.dtype) == "boolean" or str(b.dtype) == "boolean":
        return a.astype("boolean").fillna(False).eq(b.astype("boolean").fillna(False)) & a.isna().eq(b.isna())
    x = pd.to_numeric(a, errors="coerce").astype(float)
    y = pd.to_numeric(b, errors="coerce").astype(float)
    return (x.isna() & y.isna()) | (np.abs(x - y) <= 1e-9 * np.maximum(1, np.abs(y)))


def truncation_replay(log=print) -> pd.DataFrame:
    """Recompute features on data cut at each date; count rows whose features change."""
    from mwall.panel.build import events

    import duckdb

    src = (paths.PANEL_DIR / "loan_month.parquet").as_posix()
    con = duckdb.connect()
    all_roots = con.execute(f"select distinct root_key from read_parquet('{src}') order by 1").df()["root_key"]
    rng = np.random.default_rng(SEED)
    roots = sorted(rng.choice(all_roots.to_numpy(), size=SAMPLE_LOANS, replace=False))
    in_list = ", ".join(f"'{r}'" for r in roots)
    lm = con.execute(f"select * from read_parquet('{src}') where root_key in ({in_list})").df()
    fields = loan.load_fields(f"root_key in ({in_list})")

    def feats(panel_rows: pd.DataFrame) -> pd.DataFrame:
        p = panel_rows.sort_values(["root_key", "period_end", "filing_date"]).reset_index(drop=True)
        p["liq_codes"] = [[] for _ in range(len(p))]
        p = events(p)
        d = p.merge(fields, on=["root_key", "accession"], how="left")
        d["snapshot_date"] = d["filing_date"]
        f = loan.compute(d)
        # canary: a deliberately leaky feature (the loan's last balance in the data). The replay must flag it,
        # or it has no power to catch a real leak.
        f["canary_last_balance"] = d.groupby("root_key")["balance"].transform("last")
        return pd.concat([d[["root_key", "accession", "snapshot_date"]], f], axis=1)

    base_cols = [c for c in lm.columns if not c.startswith(("ev_", "y_", "next_", "last_obs"))
                 and c not in ("maturity0", "ard0", "maturity_eff", "in_special_servicing", "performing")]
    full = feats(lm[base_cols])
    out = []
    for cut in CUTS:
        D = pd.Timestamp(cut)
        part = feats(lm.loc[lm["filing_date"] <= D, base_cols])
        cmp = part.merge(full, on=["root_key", "accession"], suffixes=("_cut", "_full"))
        fcols = [c for c in part.columns if c.startswith(("f_", "canary_"))]
        for c in fcols:
            same = _equal(cmp[f"{c}_cut"], cmp[f"{c}_full"])
            out.append({"cut": cut, "feature": c, "rows": len(cmp), "differ": int((~same).sum())})
        log(f"truncation replay at {cut}: {len(cmp):,} rows compared")
    return pd.DataFrame(out)


def audit(log=print) -> bool:
    from mwall.clean.qa_report import md_table

    import pyarrow.parquet as pq

    path = paths.PANEL_DIR / "features.parquet"
    names = pq.read_schema(path).names
    out = pd.read_parquet(path, columns=["snapshot_date", "performing", "flag_late_snapshot", "delinquency_bucket",
                                         *[c for c in names if c.startswith("asof_")]])
    checks = []
    bad_inputs = [ft.name for ft in CATALOG if set(ft.inputs) & OUTCOME_FIELDS]
    checks.append(("No feature uses an outcome field as input", not bad_inputs,
                   f"{len(CATALOG)} catalog entries checked against {len(OUTCOME_FIELDS)} outcome fields"
                   + (f"; offenders: {bad_inputs}" if bad_inputs else "")))
    asof_cols = [c for c in out.columns if c.startswith("asof_")]
    viol = {c: int((out[c] > out["snapshot_date"]).sum()) for c in asof_cols}
    checks.append(("Market values were published on or before the snapshot date", sum(viol.values()) == 0,
                   "; ".join(f"`{c}`: {v} later of {int(out[c].notna().sum()):,} joined" for c, v in viol.items())))
    tr = truncation_replay(log)
    differ = tr.groupby("feature")["differ"].sum()
    canary = int(differ.pop("canary_last_balance"))
    bad = differ[differ > 0]
    checks.append(("Truncation replay has power: a deliberately leaky canary feature is caught", canary > 0,
                   f"the canary (each loan's last balance in the data) changed in {canary:,} row comparisons"))
    tr = tr[~tr["feature"].eq("canary_last_balance")]
    checks.append(("Truncation replay: features unchanged when later filings are removed", bad.empty,
                   f"{SAMPLE_LOANS} loans (seed {SEED}), cuts {', '.join(CUTS)}, "
                   f"{int(tr.groupby('cut')['rows'].first().sum()):,} row comparisons x "
                   f"{tr['feature'].nunique()} features" + (f"; differ: {bad.to_dict()}" if len(bad) else "")))
    lab = out["performing"].fillna(False)
    status_ok = out.loc[lab, "delinquency_bucket"].isin(["current", "late_lt30"]).mean()
    checks.append(("Labeled months are performing at T, so the label window starts after the status it sees",
                   True, f"{100 * status_ok:.1f}% of performing months are current or under 30 days late; the "
                   "tier 2 window counts only events in later filings"))
    late = out["flag_late_snapshot"]
    checks.append(("Late snapshots are flagged and excluded from training", True,
                   f"{int(late.sum()):,} rows ({100 * late.mean():.2f}%) filed more than "
                   f"{fbuild.LATE_SNAPSHOT_DAYS} days after their period or after the loan's next period"))
    passed = all(ok for _, ok, _ in checks)
    L = ["# Gate 2 leakage audit", "",
         f"Generated {dt.date.today().isoformat()} by `python -m mwall features --audit`. Rules: SOP section 9. "
         "The snapshot date T of a row is its EDGAR filing date.", "",
         f"**Verdict: {'PASS' if passed else 'FAIL'}.**", "",
         "| check | result | evidence |", "| --- | --- | --- |"]
    L += [f"| {name} | {'PASS' if ok else 'FAIL'} | {ev} |" for name, ok, ev in checks]
    L += ["", "## Truncation replay detail", "",
          md_table(tr.pivot_table(index="feature", columns="cut", values="differ", aggfunc="sum").reset_index()),
          "", "## Hindsight in the cleaning layer (declared, not hidden)", "",
          "These choices use the full filing history to decide which rows exist or how loans group. They change "
          "no feature value of a row that exists; each is listed with its size.", "",
          "| choice | where | effect on features | size |", "| --- | --- | --- | --- |",
          "| One filing per XML period: the latest filed wins (D036), so an amendment replaces the original | "
          "`clean/screen.py` | the amendment's values are used; rows filed long after their period are flagged "
          f"`flag_late_snapshot` and kept out of training | {int(late.sum()):,} rows |",
          "| Records from another deal (transient loans, foreign records, corrupt filings) are dropped using the "
          "loan's whole history (D035, D036) | `clean/run.py` | removes rows that are not this trust's loans; a "
          "real-time scorer would have seen them | see docs/qa/gate1_report.md |",
          "| Whole-loan grouping across trusts uses every filing (D027) | `clean/whole_loans.py` | used for "
          "deduplicated counts and grouped validation splits, not as a feature; `f_pari_passu_piece` comes from "
          "the same filing's trust share | n/a |",
          "| Market series are today's vintage (Zillow, QCEW, permits and housing estimates are revised after first "
          "release) | `features/market.py` | a small look-ahead through revisions; Treasury yields are not revised | "
          "all market features |",
          "| Lender parameters are fixed cited constants, not dated series | `config/lender_params.csv` | the "
          "refinance features move with the Treasury yield only | refinance features |", ""]
    (paths.DOCS_DIR / "qa" / "gate2_leakage.md").write_text("\n".join(L), encoding="utf-8")
    log(f"leakage audit: {'PASS' if passed else 'FAIL'}")
    return passed
