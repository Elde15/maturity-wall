"""Model fitting: baselines B0 to B3, stage 1 logistic, stage 2 LightGBM, stage 3 Platt calibration."""
from __future__ import annotations

import lightgbm as lgb
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression

from mwall.model import frame
from mwall.model.metrics import logit

LOGIT_C_GRID = (0.003, 0.03, 0.3)
GBM_PARAMS = {
    "objective": "binary", "learning_rate": 0.05, "num_leaves": 31, "min_data_in_leaf": 300,
    "feature_fraction": 0.8, "bagging_fraction": 0.8, "bagging_freq": 1, "lambda_l2": 10.0, "max_bin": 127,
    "metric": "binary_logloss", "verbose": -1, "num_threads": 12, "seed": 7,
    "monotone_constraints_method": "advanced",
}
# chosen on validation windows of unseen loans (model/select.py, docs/qa/gate3_selection.md)
GBM_STRONG = {"num_leaves": 15, "min_data_in_leaf": 1000, "learning_rate": 0.03, "feature_fraction": 0.7,
              "lambda_l2": 30.0}
GBM_MAX_ROUNDS = 2000
GBM_EARLY_STOP = 100


def matrix(d: pd.DataFrame, num: list[str], cat: list[str]) -> np.ndarray:
    """Numeric features, then categorical codes (NaN where missing), as float32."""
    parts = [d[num].to_numpy(np.float32)]
    for c in cat:
        codes = d[c].cat.codes.to_numpy().astype(np.float32)
        codes[codes < 0] = np.nan
        parts.append(codes[:, None])
    return np.hstack(parts)


class Prep:
    """For the logistic model: clip to the training 1st and 99th percentiles, impute the median with a missing
    indicator, standardize, and one-hot the categoricals."""

    def __init__(self, num: list[str], cat: list[str]):
        self.num, self.cat = num, cat

    def fit(self, X: np.ndarray) -> "Prep":
        n = len(self.num)
        x = X[:, :n]
        with np.errstate(all="ignore"):
            self.lo = np.nanquantile(x, 0.01, axis=0)
            self.hi = np.nanquantile(x, 0.99, axis=0)
            xc = np.clip(x, self.lo, self.hi)
            self.med = np.nan_to_num(np.nanmedian(xc, axis=0))
        self.miss = np.isnan(x).any(axis=0)
        z = np.where(np.isnan(xc), self.med, xc)
        self.mu, self.sd = z.mean(axis=0), z.std(axis=0)
        self.sd[self.sd == 0] = 1.0
        self.levels = [len(frame.CATEGORICAL[c]) for c in self.cat]
        self.names = (list(self.num) + [f"{c}_missing" for c, m in zip(self.num, self.miss) if m]
                      + [f"{c}={v}" for c in self.cat for v in frame.CATEGORICAL[c]])
        return self

    def transform(self, X: np.ndarray) -> np.ndarray:
        n = len(self.num)
        x = X[:, :n]
        xc = np.clip(x, self.lo, self.hi)
        z = (np.where(np.isnan(xc), self.med, xc) - self.mu) / self.sd
        parts = [z.astype(np.float32), np.isnan(x[:, self.miss]).astype(np.float32)]
        for j, L in enumerate(self.levels):
            codes = X[:, n + j]
            oh = np.zeros((len(X), L), dtype=np.float32)
            ok = ~np.isnan(codes)
            oh[np.flatnonzero(ok), codes[ok].astype(int)] = 1.0
            parts.append(oh)
        return np.hstack(parts)


class SignedLogistic:
    """L2-penalized logistic regression whose listed coefficients are held to a sign (D054): bounds[j] is
    (0, None) for a coefficient that must be >= 0, (None, 0) for <= 0, (None, None) otherwise. Minimizes the same
    objective as scikit-learn's: C * sum(weighted log loss) + ||w||^2 / 2, intercept unpenalized."""

    def __init__(self, C: float, bounds: list[tuple]):
        self.C, self.bounds = C, bounds

    def fit(self, Z: np.ndarray, y: np.ndarray, sample_weight=None) -> "SignedLogistic":
        from scipy.optimize import minimize

        y = np.asarray(y, dtype=np.float64)
        s = np.ones_like(y) if sample_weight is None else np.asarray(sample_weight, dtype=np.float64)
        p0 = np.clip(np.average(y, weights=s), 1e-6, 1 - 1e-6)

        def f(theta):
            b, w = theta[0], theta[1:]
            z = (Z @ w.astype(np.float32)).astype(np.float64) + b
            loss = np.sum(s * (np.logaddexp(0, z) - y * z))
            r = s * (1 / (1 + np.exp(-z)) - y)
            g = np.concatenate([[r.sum()], (Z.T @ r.astype(np.float32)).astype(np.float64)])
            return self.C * loss + 0.5 * w @ w, self.C * g + np.concatenate([[0.0], w])

        x0 = np.zeros(Z.shape[1] + 1)
        x0[0] = np.log(p0 / (1 - p0))
        res = minimize(f, x0, jac=True, method="L-BFGS-B", bounds=[(None, None), *self.bounds],
                       options={"maxiter": 2000})
        self.intercept_, self.coef_ = np.array([res.x[0]]), res.x[1:][None, :]
        self.converged = bool(res.success)
        return self

    def decision_function(self, Z: np.ndarray) -> np.ndarray:
        return Z @ self.coef_[0] + self.intercept_[0]

    def predict_proba(self, Z: np.ndarray) -> np.ndarray:
        p = 1 / (1 + np.exp(-self.decision_function(Z)))
        return np.column_stack([1 - p, p])


class Logit:
    def __init__(self, num, cat, C, signs: dict[str, int] | None = None):
        self.prep, self.C, self.signs = Prep(num, cat), C, signs

    def fit(self, X, y, sample_weight=None):
        self.prep.fit(X)
        Z = self.prep.transform(X)
        if self.signs:
            bounds = [((0, None) if self.signs.get(n, 0) > 0 else (None, 0) if self.signs.get(n, 0) < 0
                       else (None, None)) for n in self.prep.names]
            self.m = SignedLogistic(self.C, bounds).fit(Z, y, sample_weight)
        else:
            self.m = LogisticRegression(C=self.C, solver="newton-cholesky", max_iter=200)
            self.m.fit(Z, y, sample_weight=sample_weight)
        self.z_mean = Z.mean(axis=0)
        return self

    def contributions(self, X) -> np.ndarray:
        """Exact SHAP values of a linear model: coefficient times (input minus its training mean), log-odds."""
        return (self.prep.transform(X) - self.z_mean) * self.m.coef_[0]

    def raw(self, X) -> np.ndarray:
        return self.m.decision_function(self.prep.transform(X))

    def coefficients(self) -> pd.Series:
        return pd.Series(self.m.coef_[0], index=self.prep.names)


def tune_logit(Xtr, ytr, Xva, yva, num, cat, signs=None) -> tuple[float, dict]:
    from sklearn.metrics import log_loss

    res = {}
    for C in LOGIT_C_GRID:
        m = Logit(num, cat, C, signs).fit(Xtr, ytr)
        res[C] = log_loss(yva, 1 / (1 + np.exp(-m.raw(Xva))), labels=[0, 1])
    return min(res, key=res.get), res


class GBM:
    def __init__(self, num, cat, params=None, rounds=None):
        self.num, self.cat = num, cat
        self.params = dict(GBM_PARAMS, **(params or {}))
        self.params["monotone_constraints"] = [frame.MONOTONE.get(c, 0) for c in num] + [0] * len(cat)
        self.rounds = rounds

    def fit(self, X, y, Xva=None, yva=None):
        cat_idx = list(range(len(self.num), len(self.num) + len(self.cat)))
        names = [*self.num, *self.cat]
        dtr = lgb.Dataset(X, y, feature_name=names, categorical_feature=cat_idx, free_raw_data=True)
        if self.rounds is None:
            dva = lgb.Dataset(Xva, yva, reference=dtr, feature_name=names, categorical_feature=cat_idx)
            self.b = lgb.train(self.params, dtr, GBM_MAX_ROUNDS, valid_sets=[dva],
                               callbacks=[lgb.early_stopping(GBM_EARLY_STOP, verbose=False)])
            self.rounds = self.b.best_iteration
        else:
            self.b = lgb.train(self.params, dtr, self.rounds)
        return self

    def raw(self, X) -> np.ndarray:
        return self.b.predict(X, num_iteration=self.rounds, raw_score=True)

    def contributions(self, X) -> np.ndarray:
        return self.b.predict(X, num_iteration=self.rounds, pred_contrib=True)


def platt(raw_va: np.ndarray, y_va: np.ndarray, sample_weight=None) -> tuple[float, float]:
    m = LogisticRegression(C=1e6, solver="lbfgs").fit(raw_va.reshape(-1, 1), y_va, sample_weight=sample_weight)
    return float(m.intercept_[0]), float(m.coef_[0, 0])


def apply_platt(raw: np.ndarray, ab: tuple[float, float]) -> np.ndarray:
    return 1 / (1 + np.exp(-(ab[0] + ab[1] * raw)))


# ---------------------------------------------------------------------------------------------- baselines

B1_THRESHOLDS = (0.07, 0.08, 0.09, 0.10)
B2_THRESHOLDS = (1.0, 1.1, 1.25)


def _bucket_rates(bucket_va: np.ndarray, y_va: np.ndarray, bucket_te: np.ndarray) -> np.ndarray:
    """Event rate of each rule bucket in the validation window (one pseudo-observation at the overall rate)."""
    base = y_va.mean()
    s = pd.DataFrame({"b": bucket_va, "y": y_va}).groupby("b")["y"].agg(["sum", "size"])
    rate = (s["sum"] + base) / (s["size"] + 1)
    return pd.Series(bucket_te).map(rate).fillna(base).to_numpy()


def _rule_bucket(x: pd.Series, t: float, below_is_risky: bool = True) -> np.ndarray:
    return np.where(x.isna(), "missing", np.where((x < t) if below_is_risky else (x > t), "risky", "ok"))


def baselines(va: pd.DataFrame, te: pd.DataFrame) -> dict[str, np.ndarray]:
    """B0 to B3 fit on the validation window, scored on te. Rule probabilities are bucket event rates."""
    y = va["y_distress_12m"].to_numpy(float)
    out = {"b0_base_rate": np.full(len(te), y.mean())}
    for t in B1_THRESHOLDS:
        out[f"b1_dy_lt_{int(100 * t)}"] = _bucket_rates(_rule_bucket(va["f_debt_yield_noi"], t), y,
                                                        _rule_bucket(te["f_debt_yield_noi"], t))
    # continuous version: rank by debt yield, a stronger baseline than any one threshold
    dy_va, dy_te = va["f_debt_yield_noi"].clip(0, 0.3), te["f_debt_yield_noi"].clip(0, 0.3)
    xv = np.column_stack([dy_va.fillna(dy_va.median()), dy_va.isna()])
    xt = np.column_stack([dy_te.fillna(dy_va.median()), dy_te.isna()])
    out["b1c_debt_yield"] = LogisticRegression(C=1e6).fit(xv, y).predict_proba(xt)[:, 1]
    dscr_va = va["f_dscr_noi_reported"].fillna(va["f_dscr_noi_recomputed"])
    dscr_te = te["f_dscr_noi_reported"].fillna(te["f_dscr_noi_recomputed"])
    for t in B2_THRESHOLDS:
        out[f"b2_dscr_lt_{int(100 * t)}"] = _bucket_rates(_rule_bucket(dscr_va, t), y, _rule_bucket(dscr_te, t))
    out["b3_refi_gap"] = _bucket_rates(_rule_bucket(va["f_refi_gap"], 0, False), y,
                                       _rule_bucket(te["f_refi_gap"], 0, False))
    return out
