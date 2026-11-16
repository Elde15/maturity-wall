"""Configuration choice on validation data only (D051).

Models fit on the training-window months of folds 2 to 4. Fold 1's validation-window months serve early
stopping and calibration and fold 0's validation-window months are scored, so both are loans the model never
saw. (A first version scored loans whose earlier months were in training; their 12-month label windows overlap
the training labels and the boosted model's scores on them ran two to three times better than on unseen loans.)
No test window is used. The configuration with the best mean
precision-recall AUC across origins is used, provided its Brier score is no worse than the reference
configuration's by more than 1%.
"""
from __future__ import annotations

import json

import numpy as np
import pandas as pd

from mwall.model import fit, frame
from mwall.model.metrics import score

NATIONAL_MACRO = ["f_ust10", "f_ust5", "f_ust10_change_12m", "f_curve_10y2y"]
STRONG = fit.GBM_STRONG
CONFIGS = {
    "logit_all": ("logit", [], None),
    "logit_no_national_macro": ("logit", NATIONAL_MACRO, None),
    "gbm_all": ("gbm", [], None),
    "gbm_no_national_macro": ("gbm", NATIONAL_MACRO, None),
    "gbm_all_strong": ("gbm", [], STRONG),
    "gbm_no_national_macro_strong": ("gbm", NATIONAL_MACRO, STRONG),
}


def run(d: pd.DataFrame | None = None, log=print) -> pd.DataFrame:
    d = frame.load() if d is None else d
    y = d["y_distress_12m"].to_numpy(float)
    lab, g = d["labeled"].to_numpy(), d["fold"].to_numpy()
    rows = []
    for name, (kind, drop, params) in CONFIGS.items():
        num, cat = frame.feature_list(drop)
        X = fit.matrix(d, num, cat)
        for D in frame.ORIGINS:
            w = {k: v.to_numpy() for k, v in frame.windows(D, d["period_end"]).items()}
            tr = w["train"] & lab & np.isin(g, [2, 3, 4])
            va_fit = w["valid"] & lab & (g == 1)
            va_score = w["valid"] & lab & (g == 0)
            if kind == "logit":
                C, _ = fit.tune_logit(X[tr], y[tr], X[va_fit], y[va_fit], num, cat)
                m = fit.Logit(num, cat, C).fit(X[tr], y[tr])
            else:
                m = fit.GBM(num, cat, params).fit(X[tr], y[tr], X[va_fit], y[va_fit])
            ab = fit.platt(m.raw(X[va_fit]), y[va_fit])
            s = score(y[va_score], fit.apply_platt(m.raw(X[va_score]), ab))
            rows.append({"config": name, "origin": D.year, **s})
            log(f"{name} {D.year}: valid PR-AUC {s['pr_auc']:.4f} Brier {s['brier']:.5f} slope {s['cal_slope']:.2f}")
    r = pd.DataFrame(rows)
    frame.OUT_DIR.mkdir(parents=True, exist_ok=True)
    r.to_csv(frame.OUT_DIR / "select_validation.csv", index=False)
    return r


def choose(r: pd.DataFrame, kind: str, reference: str) -> str:
    m = r[r["config"].str.startswith(kind)].groupby("config")[["pr_auc", "brier"]].mean()
    ok = m[m["brier"] <= m.loc[reference, "brier"] * 1.01]
    return ok["pr_auc"].idxmax()


if __name__ == "__main__":
    res = run()
    summary = res.groupby("config")[["pr_auc", "roc_auc", "brier", "cal_slope"]].mean().round(5)
    print(summary.to_string())
    print(json.dumps({"logit": choose(res, "logit", "logit_all"), "gbm": choose(res, "gbm", "gbm_all")}))
