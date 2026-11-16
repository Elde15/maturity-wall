"""External sanity check (SOP 10): our data and model against published CMBS delinquency rates.

Published rates (Trepp, CRED iQ) are a stock: the share of outstanding CMBS balance 30+ days delinquent at
month end, matured loans that did not pay included. Two series from this project are set beside them:

1. Observed: the same stock measure in our loan data, every trust piece at its own balance (as a trust-level
   index counts it), defeased loans out. This checks the data and the labels, not the model.
2. Predicted: the model's mean 12-month distress probability over performing loans in each test month, with
   the realized 12-month event rate for the same loans. This is a flow (new distress among loans current today),
   so its level is not comparable with a stock; its ranking across property types and its direction over time
   are.

Published figures are a back-check only and never enter training (SOP 10).
"""
from __future__ import annotations

import duckdb
import numpy as np
import pandas as pd

from mwall.common import paths
from mwall.model import frame, rolling

SOURCES = paths.CONFIG_DIR / "research" / "cmbs_delinquency_sources.csv"
DQ = ("dq30", "dq60", "dq90plus", "matured_nonperforming")
TYPES = ["office", "retail", "lodging", "industrial", "multifamily"]


def observed_stock() -> pd.DataFrame:
    """Share of outstanding piece balance 30+ days delinquent (incl. matured non-performing), by month and type."""
    q = f"""
        select date_trunc('month', f.period_end) as "month", f.property_group,
               sum(l.balance) filter (where f.delinquency_bucket in {DQ}) dq_balance, sum(l.balance) balance
        from '{frame.FEATURES_FILE.as_posix()}' f
        join '{frame.LABELS_FILE.as_posix()}' l using (trust_cik, root_key, accession)
        where not coalesce(l.defeased, false) and l.balance > 0 and not f.flag_late_snapshot
        group by 1, 2"""
    d = duckdb.connect().execute(q).df()
    tot = d.groupby("month")[["dq_balance", "balance"]].sum().reset_index().assign(property_group="all")
    d = pd.concat([d, tot], ignore_index=True)
    d["rate_pct"] = 100 * d["dq_balance"] / d["balance"]
    d["month"] = pd.to_datetime(d["month"])
    return d[d["property_group"].isin(["all", *TYPES])]


def predicted_flow(tag: str = "signed", col: str = "p_logit") -> pd.DataFrame:
    P, _ = rolling.load(tag)
    if col not in P:
        raise KeyError(col)
    lab = P[P["labeled"]].copy()
    lab["month"] = lab["period_end"].dt.to_period("M").dt.to_timestamp()
    rows = []
    for (m, g), x in lab.groupby(["month", "property_group"], observed=True):
        rows.append({"month": m, "property_group": g, "predicted_pct": 100 * x[col].mean(),
                     "realized_pct": 100 * x["y_distress_12m"].mean(), "n": len(x)})
    out = pd.DataFrame(rows)
    allm = lab.groupby("month").apply(lambda x: pd.Series({"predicted_pct": 100 * x[col].mean(),
                                                           "realized_pct": 100 * x["y_distress_12m"].mean(),
                                                           "n": len(x)}), include_groups=False).reset_index()
    return pd.concat([out, allm.assign(property_group="all")], ignore_index=True)


def published() -> pd.DataFrame | None:
    if not SOURCES.exists():
        return None
    s = pd.read_csv(SOURCES)
    s["month"] = pd.to_datetime(s["report_month"].astype(str) + "-01", errors="coerce")
    s["rate_pct"] = pd.to_numeric(s["rate_pct"], errors="coerce")
    return s.dropna(subset=["month", "rate_pct"])


def compare(stat_prefix: str = "delinquency 30+") -> pd.DataFrame:
    """Published Trepp rate beside our observed stock for the same month and type."""
    pub = published()
    obs = observed_stock()
    if pub is None:
        return pd.DataFrame()
    t = pub[pub["publisher"].str.contains("Trepp", case=False) & pub["stat"].str.startswith(stat_prefix)]
    t = t.groupby(["month", "property_group"], as_index=False)["rate_pct"].first()
    m = t.merge(obs[["month", "property_group", "rate_pct"]], on=["month", "property_group"],
                suffixes=("_trepp", "_ours"))
    m["gap_pts"] = m["rate_pct_ours"] - m["rate_pct_trepp"]
    return m


def summary(m: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for g, x in m.groupby("property_group"):
        rows.append({"property_group": g, "months": len(x), "trepp_mean": x["rate_pct_trepp"].mean(),
                     "ours_mean": x["rate_pct_ours"].mean(), "mean_gap_pts": x["gap_pts"].mean(),
                     "correlation": x["rate_pct_trepp"].corr(x["rate_pct_ours"]) if len(x) > 2 else np.nan})
    return pd.DataFrame(rows)
