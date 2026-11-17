"""Run the underwriting engine on every scored loan (SOP 12) and write the Gate 4 evidence.

    python -m mwall underwrite            # inputs, scenarios, opportunity score, sensitivity grid, report

Writes data/outputs/underwriting.parquet (one row per loan and scenario), data/outputs/underwriting_grid.parquet
(rate and cap-rate shifts, base scenario) and docs/qa/gate4_underwriting.md.
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd

from mwall.common import paths
from mwall.underwrite import engine, inputs

OUT = paths.OUTPUT_DIR / "underwriting.parquet"
GRID = paths.OUTPUT_DIR / "underwriting_grid.parquet"
RATE_SHIFTS = (-100, -50, 0, 50, 100, 200)
CAP_SHIFTS = (-100, -50, 0, 50, 100)
KEEP = ["tier", "tier_reason", "jurisdiction", "noi_stressed", "cap_rate", "cap_method", "bench_kind", "value",
        "refi_rate", "loan_constant", "p_ltv", "p_dscr", "p_dy", "p_max", "refi_gap", "refi_gap_pct", "reserve_y1",
        "lease_up", "value_bid", "return_bid", "bid", "discount", "refinanceable_by_sale", "acq_rate", "hurdle",
        "loan_at_bid", "equity", "irr_levered", "irr_unlevered", "equity_multiple", "cash_on_cash", "noi_y1",
        "dscr_y1", "dy_y1", "breakeven_occ", "exit_cap", "exit_price", "exit_cost_rate", "renovation_budget",
        "irr_at_value_bid", "irr_unlevered_at_value_bid", "clears_hurdle_at_value"]
DISTRESSED = {"matured, not repaid", "special servicing", "delinquent 30+"}


def pct_rank(s: pd.Series) -> pd.Series:
    return s.rank(pct=True, method="average")


def opportunity(base: pd.DataFrame) -> pd.Series:
    """Rank-average of six transparent components (SOP 12), each a percentile in [0, 1]; 0 to 100.

    risk: 1 for a loan already in distress, else the percentile of its failure probability among loans that have
    one, else of its 12-month distress probability; gap: refinance gap as a share of balance; discount: implied
    discount to par; returns: the percentile of the levered IRR a buyer earns paying the value bid (0 without a
    cash-flow model), a continuous form of "do returns clear the hurdle", which almost no loan does at market
    value; tier: A 1, B 0.5, C 0; size: balance."""
    x = base[base["bid"].notna()].copy()
    risk = pd.Series(np.nan, index=x.index)
    has_fail = x["p_fail"].notna()
    risk[has_fail] = pct_rank(x.loc[has_fail, "p_fail"])
    rest = ~has_fail & x["p_distress_12m"].notna()
    risk[rest] = pct_rank(x.loc[rest, "p_distress_12m"])
    risk[x["status"].isin(DISTRESSED)] = 1.0
    comp = pd.DataFrame({
        "risk": risk.fillna(0.0),
        "gap": pct_rank(x["refi_gap_pct"].fillna(0.0)),
        "discount": pct_rank(x["discount"].fillna(0.0)),
        "returns": pct_rank(x["irr_at_value_bid"]).fillna(0.0),
        "tier": x["tier"].map({"A": 1.0, "B": 0.5, "C": 0.0}),
        "size": pct_rank(x["wl_balance_est"]),
    })
    return (100 * comp.mean(axis=1)).reindex(base.index)


def run_scenarios(rows: list[dict], d: pd.DataFrame, P: dict, M: dict) -> pd.DataFrame:
    parts = []
    for name, S in P["scenarios"].items():
        r = pd.DataFrame([engine.underwrite(L, S, P, M) for L in rows], index=d.index).reindex(columns=KEEP)
        r.insert(0, "scenario", name)
        parts.append(pd.concat([d[["whole_loan_id", "property_group", "status", "wl_balance_est", "p_fail",
                                   "p_distress_12m", "noi_source"]], r], axis=1))
    out = pd.concat(parts, ignore_index=True)
    base = out["scenario"].eq("base")
    out["opportunity_score"] = np.nan
    out.loc[base, "opportunity_score"] = opportunity(out[base]).to_numpy()
    return out


def run_grid(rows: list[dict], d: pd.DataFrame, P: dict, M: dict) -> pd.DataFrame:
    S = P["scenarios"]["base"]
    keep = [i for i, L in enumerate(rows) if L["group"] is not None and engine._num(L.get("noi")) == engine._num(L.get("noi"))]
    parts = []
    for rs in RATE_SHIFTS:
        for cs in CAP_SHIFTS:
            res = [engine.underwrite(rows[i], S, P, M, rate_shift_bps=rs, cap_shift_bps=cs) for i in keep]
            g = pd.DataFrame(res).reindex(columns=["refi_gap", "refi_gap_pct", "value", "value_bid", "return_bid"])
            g.insert(0, "whole_loan_id", d["whole_loan_id"].to_numpy()[keep])
            g.insert(1, "rate_shift_bps", rs)
            g.insert(2, "cap_shift_bps", cs)
            parts.append(g)
    return pd.concat(parts, ignore_index=True)


def monotone_checks(grid: pd.DataFrame, tol: float = 1e-6) -> pd.DataFrame:
    """SOP 15 Gate 4: higher rates widen gaps and lower bids; higher cap rates lower value (and bids)."""
    checks = [("refi_gap", "rate_shift_bps", +1), ("return_bid", "rate_shift_bps", -1),
              ("value", "cap_shift_bps", -1), ("value_bid", "cap_shift_bps", -1),
              ("return_bid", "cap_shift_bps", -1), ("refi_gap", "cap_shift_bps", +1)]
    rows = []
    for col, axis, sign in checks:
        other = "cap_shift_bps" if axis == "rate_shift_bps" else "rate_shift_bps"
        g = grid.dropna(subset=[col]).sort_values(["whole_loan_id", other, axis])
        step = g.groupby(["whole_loan_id", other])[col].diff()
        scale = g[col].abs().clip(lower=1.0)
        bad = (sign * step < -tol * scale) & step.notna()
        flat = (step.abs() <= tol * scale) & step.notna()
        rows.append({"output": col, "as": axis.replace("_shift_bps", " rises"),
                     "expected": "rises or holds" if sign > 0 else "falls or holds",
                     "steps": int(step.notna().sum()), "moved_the_wrong_way": int(bad.sum()),
                     "held_flat": int(flat.sum()),
                     "loans_with_a_wrong_step": int(g.loc[bad[bad].index, "whole_loan_id"].nunique())})
    return pd.DataFrame(rows)


def main(log=print) -> None:
    d = inputs.build(log=log)
    P, M = engine.load_params(), engine.load_market()
    rows = engine.prepare(d, P)
    out = run_scenarios(rows, d, P, M)
    out.to_parquet(OUT, index=False)
    log(f"underwriting: {len(out):,} loan-scenarios -> {OUT.name}")
    grid = run_grid(rows, d, P, M)
    grid.to_parquet(GRID, index=False)
    log(f"grid: {len(grid):,} rows -> {GRID.name}")
    from mwall.underwrite import report

    report.write(out, grid, monotone_checks(grid), rows, P, M, log=log)


if __name__ == "__main__":
    main()
