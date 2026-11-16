"""Credit-logic check for SOP 11 stage 1 (decision D053).

Debt yield, its cash-flow version, the debt-yield cushion, refinance DSCR and the refinance gaps are near-copies
of each other, so one coefficient's sign says little: the model can put a positive weight on one and a larger
negative weight on another. The check therefore moves the inputs together, the way a real change would, and
asks whether the predicted risk moves the way credit logic says:

    NOI up 10%        risk down    (debt yields, DSCRs, NOI vs securitization, model value, refinance features)
    balance up 10%    risk up      (debt yields and DSCRs down, LTVs and balance per unit up, refinance features)
    occupancy +5 pts  risk down
    refi rate +100bp  risk up      (rate shock and refinance features)

For each test year it reports the mean change in log-odds over the test months and the share of months that
move the expected way.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from mwall.model import fit, frame, rolling, scenario

NOI_SCALED = ["f_debt_yield_noi", "f_debt_yield_ncf", "f_dscr_noi_reported", "f_dscr_noi_recomputed",
              "f_value_model"]


def _refresh(d: pd.DataFrame, lp: pd.DataFrame) -> pd.DataFrame:
    """Recompute the refinance features and the debt-yield cushion from the (changed) debt yield."""
    out = scenario.shift_refi(d, 0, lp)
    pg = d["property_group"].astype(object).where(d["property_group"].astype(object).isin(lp.index), "other")
    out["f_refi_dy_cushion"] = d["f_debt_yield_noi"].to_numpy(float) - lp["dy_min"].reindex(pg.to_numpy()).to_numpy()
    return out


def noi_up(d, lp, k=1.10):
    e = d.copy()
    for c in NOI_SCALED:
        e[c] = e[c] * k
    e["f_noi_vs_securitization"] = (1 + e["f_noi_vs_securitization"]) * k - 1
    e["f_ltv_model"] = e["f_ltv_model"] / k
    return _refresh(e, lp)


def balance_up(d, lp, k=1.10):
    e = d.copy()
    for c in ["f_debt_yield_noi", "f_debt_yield_ncf", "f_dscr_noi_reported", "f_dscr_noi_recomputed"]:
        e[c] = e[c] / k
    for c in ["f_ltv_securitization", "f_ltv_recent", "f_ltv_model", "f_balance_per_unit", "f_balance_per_sqft"]:
        e[c] = e[c] * k
    return _refresh(e, lp)


def occupancy_up(d, lp, pts=0.05):
    e = d.copy()
    e["f_occupancy"] = (e["f_occupancy"] + pts).clip(upper=1.0)
    return e


def rate_up(d, lp, bps=100):
    return scenario.shift_refi(d, bps, lp)


SHOCKS = {"NOI up 10%": (noi_up, -1), "balance up 10%": (balance_up, 1), "occupancy up 5 points": (occupancy_up, -1),
          "refinance rate up 100 bp": (rate_up, 1)}


def run(d: pd.DataFrame | None = None, log=print) -> pd.DataFrame:
    d = frame.load() if d is None else d
    lp = scenario.lender_base()
    num, cat = frame.feature_list()
    X = fit.matrix(d, num, cat)
    y = d["y_distress_12m"].to_numpy(float)
    lab = d["labeled"].to_numpy()
    diag = rolling.load("main")[1]
    rows = []
    for D in frame.ORIGINS:
        w = {k: v.to_numpy() for k, v in frame.windows(D, d["period_end"]).items()}
        tr, va, te = w["train"] & lab, w["valid"] & lab, w["test"] & lab
        C = diag["origins"][str(D.year)]["logit_C"]
        models = {"logistic": fit.Logit(num, cat, C).fit(X[tr], y[tr]),
                  "logistic, sign-constrained": fit.Logit(num, cat, C, frame.CREDIT_SIGNS).fit(X[tr], y[tr]),
                  "boosted": fit.GBM(num, cat, rolling.GBM_CONFIG).fit(X[tr], y[tr], X[va], y[va])}
        base_rows = d.loc[te]
        for name, (fn, sign) in SHOCKS.items():
            Xs = fit.matrix(fn(base_rows, lp), num, cat)
            for mname, m in models.items():
                delta = m.raw(Xs) - m.raw(X[te])
                rows.append({"origin": D.year, "shock": name, "model": mname, "expected": "down" if sign < 0 else "up",
                             "mean_log_odds_change": float(delta.mean()),
                             "share_expected_way": float((np.sign(delta) == sign).mean()),
                             "share_unchanged": float((np.abs(delta) < 1e-9).mean()),
                             "pass": bool(np.sign(delta.mean()) == sign)})
        log(f"credit-logic check {D.year} done")
    out = pd.DataFrame(rows)
    out.to_csv(frame.OUT_DIR / "credit_logic.csv", index=False)
    return out
