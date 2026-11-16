"""Rolling-origin evaluation (SOP 10 validation design, SOP 11 procedure; decision D051).

For each origin D and each test group k (a loan fold, or a deal-family fold for the out-of-trust test), the
four other groups are cross-fitted: for each j of them, a model is fit on the training window of the
remaining three, early-stopped and Platt-calibrated on group j's validation window, and scores group k's test
months. The four calibrated probabilities are averaged. Every test month is out of time and out of loan, and
every calibration month is a loan the calibrated model never saw. (Calibrating on loans whose earlier months
were in training overstates the boosted model, because their label windows overlap the training labels.)

Predictions go to data/outputs/model/rolling_{tag}/{origin}.parquet; an origin already on disk is reused.
"""
from __future__ import annotations

import json
import time

import numpy as np
import pandas as pd

from mwall.model import fit, frame

KEEP = ["trust_cik", "root_key", "whole_loan_id", "period_end", "fold", "family", "family_fold", "property_group",
        "vintage", "wl_balance_est", "f_noi_missing", "f_single_asset", "f_months_to_maturity", "labeled",
        "y_distress_12m", "maturity_eff"]
GBM_CONFIG = fit.GBM_STRONG


def run_origin(d: pd.DataFrame, X: np.ndarray, num: list[str], cat: list[str], D: pd.Timestamp, group: str,
               models: tuple[str, ...], with_baselines: bool, shap_rows: int, gbm_params: dict,
               scenarios: dict | None = None, signs: dict | None = None) -> tuple[pd.DataFrame, dict]:
    y = d["y_distress_12m"].to_numpy(float)
    lab, grp = d["labeled"].to_numpy(), d[group].to_numpy()
    w = {k: v.to_numpy() for k, v in frame.windows(D, d["period_end"]).items()}
    tr_all, va_all, te_all = w["train"] & lab, w["valid"] & lab, w["test"]
    od = {"train_rows": int(tr_all.sum()), "train_events": int(y[tr_all].sum()),
          "valid_rows": int(va_all.sum()), "valid_events": int(y[va_all].sum()),
          "test_rows_labeled": int((te_all & lab).sum()), "test_events": int(y[te_all & lab].sum()),
          "gbm_rounds": [], "platt_logit": [], "platt_gbm": []}
    groups = sorted(np.unique(grp))
    C = None
    if "logit" in models:
        C, grid = fit.tune_logit(X[tr_all & ~np.isin(grp, groups[:2])], y[tr_all & ~np.isin(grp, groups[:2])],
                                 X[va_all & (grp == groups[1])], y[va_all & (grp == groups[1])], num, cat, signs)
        od["logit_C"], od["logit_C_grid"] = C, {str(k): v for k, v in grid.items()}
        od["logit_coef"] = fit.Logit(num, cat, C, signs).fit(X[tr_all], y[tr_all]).coefficients().round(5).to_dict()
    shap_sum, shap_n = np.zeros(len(num) + len(cat)), 0
    parts = []
    for k in groups:
        te = te_all & (grp == k)
        if not te.any():
            continue
        out = d.loc[te, KEEP].copy()
        out["origin"] = D.year
        acc = {m: [] for m in models}
        scen_X = {s: fit.matrix(fn(d.loc[te]), num, cat) for s, fn in (scenarios or {}).items()}
        acc_s = {(m, s): [] for m in models for s in scen_X}
        for j in [g for g in groups if g != k]:
            tr, va = tr_all & ~np.isin(grp, [k, j]), va_all & (grp == j)
            if "logit" in models:
                m = fit.Logit(num, cat, C, signs).fit(X[tr], y[tr])
                ab = fit.platt(m.raw(X[va]), y[va])
                acc["logit"].append(fit.apply_platt(m.raw(X[te]), ab))
                od["platt_logit"].append(ab)
                for s, Xs in scen_X.items():
                    acc_s[("logit", s)].append(fit.apply_platt(m.raw(Xs), ab))
            if "gbm" in models:
                g = fit.GBM(num, cat, gbm_params).fit(X[tr], y[tr], X[va], y[va])
                ab = fit.platt(g.raw(X[va]), y[va])
                acc["gbm"].append(fit.apply_platt(g.raw(X[te]), ab))
                od["gbm_rounds"].append(int(g.rounds))
                od["platt_gbm"].append(ab)
                for s, Xs in scen_X.items():
                    acc_s[("gbm", s)].append(fit.apply_platt(g.raw(Xs), ab))
                if shap_rows and j == [g_ for g_ in groups if g_ != k][0]:
                    idx = np.flatnonzero(te & lab)
                    if len(idx):
                        idx = np.random.default_rng(int(k)).choice(idx, min(shap_rows, len(idx)), replace=False)
                        shap_sum += np.abs(g.contributions(X[idx])[:, :-1]).sum(axis=0)
                        shap_n += len(idx)
        for m, ps in acc.items():
            out[f"p_{m}"] = np.mean(ps, axis=0)
        for (m, s), ps in acc_s.items():
            out[f"p_{m}_{s}"] = np.mean(ps, axis=0)
        if with_baselines:
            for name, p in fit.baselines(d.loc[va_all & (grp != k)], d.loc[te]).items():
                out[name] = p
        parts.append(out)
    if shap_n:
        od["mean_abs_shap"] = dict(zip(num + cat, (shap_sum / shap_n).round(6)))
    return pd.concat(parts, ignore_index=True), od


def run(d: pd.DataFrame | None = None, tag: str = "main", drop: list[str] | None = None, group: str = "fold",
        models: tuple[str, ...] = ("logit", "gbm"), with_baselines: bool = True, origins=frame.ORIGINS,
        shap_rows: int = 2000, gbm_params: dict | None = None, scenarios: dict | None = None,
        resume: bool = True, signs: dict | None = None, log=print) -> tuple[pd.DataFrame, dict]:
    """scenarios: name -> function(d) returning a modified copy of the feature frame, scored by the same models."""
    gbm_params = GBM_CONFIG if gbm_params is None else gbm_params
    out_dir = frame.OUT_DIR / f"rolling_{tag}"
    out_dir.mkdir(parents=True, exist_ok=True)
    diag_path = out_dir / "diag.json"
    diag = json.loads(diag_path.read_text()) if (resume and diag_path.exists()) else {}
    diag.update({"tag": tag, "drop": drop or [], "group": group, "models": list(models), "gbm_params": gbm_params,
                 "logit_signs": signs or {}})
    diag.setdefault("origins", {})
    num, cat = frame.feature_list(drop)
    diag["features"] = num + cat
    preds, X = [], None
    for D in origins:
        f = out_dir / f"{D.year}.parquet"
        if resume and f.exists() and str(D.year) in diag["origins"]:
            preds.append(pd.read_parquet(f))
            log(f"[{tag}] origin {D.year}: reused")
            continue
        if X is None:
            d = frame.load() if d is None else d
            X = fit.matrix(d, num, cat)
        t0 = time.time()
        P, od = run_origin(d, X, num, cat, D, group, models, with_baselines, shap_rows, gbm_params, scenarios, signs)
        od["seconds"] = round(time.time() - t0, 1)
        P.to_parquet(f, index=False)
        diag["origins"][str(D.year)] = od
        diag_path.write_text(json.dumps(diag, indent=1, default=float))
        preds.append(P)
        log(f"[{tag}] origin {D.year}: train {od['train_rows']:,} ({od['train_events']:,} events), valid "
            f"{od['valid_rows']:,}, test {od['test_rows_labeled']:,} ({od['test_events']:,}); {od['seconds']}s")
    return pd.concat(preds, ignore_index=True), diag


def load(tag: str = "main") -> tuple[pd.DataFrame, dict]:
    out_dir = frame.OUT_DIR / f"rolling_{tag}"
    P = pd.concat([pd.read_parquet(f) for f in sorted(out_dir.glob("*.parquet"))], ignore_index=True)
    return P, json.loads((out_dir / "diag.json").read_text())
