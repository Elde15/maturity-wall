"""Discrimination, calibration and business metrics (SOP 10)."""
from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score, brier_score_loss, log_loss, roc_auc_score

EPS = 1e-6


def logit(p) -> np.ndarray:
    p = np.clip(np.asarray(p, dtype=float), EPS, 1 - EPS)
    return np.log(p / (1 - p))


def _newton_logistic(x: np.ndarray, y: np.ndarray, offset: np.ndarray, iters: int = 50) -> np.ndarray:
    """Unpenalized logistic fit of y on columns x with an offset."""
    b = np.zeros(x.shape[1])
    for _ in range(iters):
        p = 1 / (1 + np.exp(-(x @ b + offset)))
        g = x.T @ (y - p)
        h = (x * (p * (1 - p))[:, None]).T @ x + 1e-9 * np.eye(x.shape[1])
        step = np.linalg.solve(h, g)
        b += step
        if np.abs(step).max() < 1e-8:
            break
    return b


def calibration_slope_intercept(y, p) -> tuple[float, float]:
    """Slope from y ~ a + b*logit(p); intercept is calibration-in-the-large, y ~ a + offset logit(p).
    A perfectly calibrated forecast has slope 1 and intercept 0."""
    y = np.asarray(y, dtype=float)
    lp = logit(p)
    slope = _newton_logistic(np.column_stack([np.ones_like(lp), lp]), y, np.zeros_like(lp))[1]
    citl = _newton_logistic(np.ones((len(lp), 1)), y, lp)[0]
    return float(slope), float(citl)


def capture_top(y, p, weight=None, share: float = 0.10) -> float:
    """Share of events (or of event balance) in the top `share` of rows ranked by p."""
    y = np.asarray(y, dtype=float)
    w = np.ones_like(y) if weight is None else np.nan_to_num(np.asarray(weight, dtype=float))
    order = np.argsort(-np.asarray(p, dtype=float), kind="stable")
    n = max(1, int(round(share * len(y))))
    top = order[:n]
    tot = (y * w).sum()
    return float((y[top] * w[top]).sum() / tot) if tot > 0 else np.nan


def score(y, p, weight=None) -> dict:
    y = np.asarray(y, dtype=float)
    p = np.clip(np.asarray(p, dtype=float), EPS, 1 - EPS)
    out = {"n": int(len(y)), "events": int(y.sum()), "rate": float(y.mean()) if len(y) else np.nan,
           "mean_p": float(p.mean()) if len(y) else np.nan}
    if len(y) == 0 or y.min() == y.max():
        return out | {"pr_auc": np.nan, "roc_auc": np.nan, "brier": np.nan, "log_loss": np.nan,
                      "cal_slope": np.nan, "cal_intercept": np.nan, "top10_capture": np.nan,
                      "top10_capture_balance": np.nan}
    slope, citl = calibration_slope_intercept(y, p)
    return out | {
        "pr_auc": float(average_precision_score(y, p)), "roc_auc": float(roc_auc_score(y, p)),
        "brier": float(brier_score_loss(y, p)), "log_loss": float(log_loss(y, p, labels=[0, 1])),
        "cal_slope": slope, "cal_intercept": citl, "top10_capture": capture_top(y, p),
        "top10_capture_balance": capture_top(y, p, weight)}


def reliability(y, p, bins: int = 10) -> pd.DataFrame:
    """Mean forecast and observed rate by decile of the forecast."""
    d = pd.DataFrame({"y": np.asarray(y, dtype=float), "p": np.asarray(p, dtype=float)})
    d["bin"] = pd.qcut(d["p"].rank(method="first"), bins, labels=False)
    return d.groupby("bin").agg(n=("y", "size"), mean_p=("p", "mean"), observed=("y", "mean")).reset_index()
