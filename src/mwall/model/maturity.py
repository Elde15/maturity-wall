"""Maturity-window model and the ensemble (SOP 10 tiers, SOP 11 stage 6; decision D052).

Sample: whole loans with a tier 1 outcome (EX-102; the vintage-2016 10-D loans carry no feature rows). Each
loan contributes its monthly snapshots from 24 to 2.5 months before maturity, weighted so every loan counts
once, and the model takes months to maturity as an input, so it scores a loan at any point in that range.
SOP horizons 12 (primary), 6 and 3 months are read off the snapshot nearest each.

Components, all logistic:
  A. maturity model: a short list of credit, structure and status features;
  B. the 12-month forward-distress probability, recalibrated to the maturity outcome;
  C. the ensemble: the mean of A and B in log-odds (A alone where B has no score: a loan not performing at
     the snapshot, or a month the rolling evaluation did not score).

Out of time: loans maturing in year Y are scored by models fit on loans whose outcome was public by the start
of year Y-1 (maturity plus 90 days grace plus 45 days to file). Forward-distress scores come from the rolling
evaluation, so they are out of time and out of loan themselves; B can only be fit where those exist (snapshots
from 2022), which leaves test years 2025 and 2026 for B and C and adds 2024 for A.
"""
from __future__ import annotations

import duckdb
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import log_loss

from mwall.common import paths
from mwall.model import fit, frame, rolling
from mwall.model.metrics import logit
from mwall.panel import build as panel

WINDOW_FAR, WINDOW_NEAR = pd.Timedelta(days=745), pd.Timedelta(days=75)
KNOWN_LAG = pd.Timedelta(days=90 + 45)
TEST_YEARS = (2024, 2025, 2026)
HORIZONS = (12, 6, 3)
C_GRID = (0.01, 0.1, 1.0)
GROUPS = ["office", "retail", "lodging", "multifamily", "industrial", "self_storage", "mixed_use"]
NUM = ["f_refi_gap", "f_refi_gap_income", "f_debt_yield_noi", "f_dscr_noi_reported", "f_ltv_model",
       "f_ltv_securitization", "f_occupancy", "f_noi_missing", "f_noi_vs_securitization", "f_rate_shock",
       "f_months_to_maturity", "f_balloon_share", "f_single_asset", "f_ever_special_serviced", "f_ever_modified",
       "f_in_special_servicing", "f_extended", "f_dq30plus"]
FEATURES = NUM + [f"is_{g}" for g in GROUPS]
# credit logic held by sign (D054): the distress model's list plus current status
SIGNS = {**{k: v for k, v in frame.CREDIT_SIGNS.items() if k in NUM}, "f_in_special_servicing": 1,
         "f_dq30plus": 1}


def labels(grace: int = panel.GRACE_DAYS) -> pd.DataFrame:
    """One labeled row per whole loan (the largest piece's outcome), as in the gold set."""
    if grace == panel.GRACE_DAYS:
        t1 = pd.read_parquet(paths.PANEL_DIR / "tier1.parquet")
    else:
        p = pd.read_parquet(frame.LABELS_FILE)
        t1 = panel.tier1(p, p.groupby("trust_cik")["period_end"].max(), grace=grace)
    wl = pd.read_parquet(frame.LABELS_FILE, columns=["root_key", "whole_loan_id"]).drop_duplicates("root_key")
    t1 = t1.merge(wl, on="root_key", how="left")
    t1["whole_loan_id"] = t1["whole_loan_id"].fillna(t1["root_key"])
    t1 = t1.sort_values("balance_first", ascending=False).drop_duplicates("whole_loan_id")
    return t1[t1["y_fail"].notna()].reset_index(drop=True)


def snapshots(L: pd.DataFrame) -> pd.DataFrame:
    keys = L[["whole_loan_id", "maturity_eff", "y_fail"]]
    con = duckdb.connect()
    con.register("keys", keys)
    want = list(dict.fromkeys([c for c in NUM if c != "f_dq30plus"] + frame.NUMERIC))
    cols = ", ".join(f"cast(f.{c} as double) {c}" for c in want)
    S = con.execute(f"""
        select k.whole_loan_id, k.maturity_eff, k.y_fail, f.period_end, f.performing, f.property_group,
               f.delinquency_bucket, {cols}
        from '{frame.FEATURES_FILE.as_posix()}' f
        join keys k on coalesce(f.whole_loan_id, f.root_key) = k.whole_loan_id
        where f.is_representative and not f.flag_late_snapshot
          and f.period_end between k.maturity_eff - interval 745 day and k.maturity_eff - interval 75 day""").df()
    S["f_dq30plus"] = S["delinquency_bucket"].isin(["dq30", "dq60", "dq90plus", "matured_nonperforming"]).astype(float)
    for g in GROUPS:
        S[f"is_{g}"] = S["property_group"].eq(g).astype(float)
    S["h_months"] = (S["maturity_eff"] - S["period_end"]).dt.days / 30.44
    S["w"] = 1.0 / S.groupby("whole_loan_id")["period_end"].transform("size")
    return S.sort_values(["whole_loan_id", "period_end"]).reset_index(drop=True)


def attach_distress(S: pd.DataFrame, col: str = "p_gbm", tag: str = "main") -> pd.DataFrame:
    P, _ = rolling.load(tag)
    P = P[["whole_loan_id", "period_end", col]].rename(columns={col: "p_distress"})
    return S.merge(P.drop_duplicates(["whole_loan_id", "period_end"]), on=["whole_loan_id", "period_end"],
                   how="left")


class MaturityModel:
    def __init__(self, C: float | None = None, signs: dict | None = SIGNS):
        self.C, self.signs = C, signs

    def _X(self, S):
        return S[FEATURES].to_numpy(np.float32)

    def fit(self, S: pd.DataFrame) -> "MaturityModel":
        X, y, w = self._X(S), S["y_fail"].to_numpy(float), S["w"].to_numpy(float)
        if self.C is None:
            folds = frame.fold_of(S["whole_loan_id"])
            loss = {}
            for C in C_GRID:
                pr = np.zeros(len(S))
                for k in range(frame.N_FOLDS):
                    tr = folds != k
                    m = MaturityModel(C, self.signs).fit(S[tr])
                    pr[~tr] = m.predict(S[~tr])
                loss[C] = log_loss(y, pr, sample_weight=w, labels=[0, 1])
            self.C = min(loss, key=loss.get)
        self.prep = fit.Prep(FEATURES, []).fit(X)
        Z = self.prep.transform(X)
        if self.signs:
            bounds = [((0, None) if self.signs.get(n, 0) > 0 else (None, 0) if self.signs.get(n, 0) < 0
                       else (None, None)) for n in self.prep.names]
            self.m = fit.SignedLogistic(self.C, bounds).fit(Z, y, w)
        else:
            self.m = LogisticRegression(C=self.C, solver="lbfgs", max_iter=2000)
            self.m.fit(Z, y, sample_weight=w)
        return self

    def predict(self, S: pd.DataFrame) -> np.ndarray:
        return self.m.predict_proba(self.prep.transform(self._X(S)))[:, 1]

    def coefficients(self) -> pd.Series:
        return pd.Series(self.m.coef_[0], index=self.prep.names)


class Recalibrated:
    """Component B: the maturity outcome on logit(12-month distress probability) and months to maturity."""

    def fit(self, S):
        S = S[S["p_distress"].notna()]
        self.m = LogisticRegression(C=1e6).fit(self._X(S), S["y_fail"], sample_weight=S["w"])
        return self

    @staticmethod
    def _X(S):
        return np.column_stack([logit(S["p_distress"]), S["h_months"] / 12])

    def predict(self, S):
        out = np.full(len(S), np.nan)
        ok = S["p_distress"].notna().to_numpy()
        if ok.any():
            out[ok] = self.m.predict_proba(self._X(S[ok]))[:, 1]
        return out


def ensemble(pA: np.ndarray, pB: np.ndarray) -> np.ndarray:
    z = np.where(np.isnan(pB), logit(pA), (logit(pA) + logit(np.nan_to_num(pB, nan=0.5))) / 2)
    return 1 / (1 + np.exp(-z))


def tier1_baselines(train: pd.DataFrame, test: pd.DataFrame) -> dict[str, np.ndarray]:
    """B0 to B3 on the maturity outcome, bucket rates from training loans' snapshots."""
    y, w = train["y_fail"].to_numpy(float), train["w"].to_numpy(float)
    base = np.average(y, weights=w)
    out = {"b0_base_rate": np.full(len(test), base)}

    def rule(xtr, xte, t, below=True):
        btr = fit._rule_bucket(xtr, t, below)
        bte = fit._rule_bucket(xte, t, below)
        s = pd.DataFrame({"b": btr, "y": y * w, "w": w}).groupby("b")[["y", "w"]].sum()
        rate = (s["y"] + base) / (s["w"] + 1)
        return pd.Series(bte).map(rate).fillna(base).to_numpy()

    out["b1_dy_lt_8"] = rule(train["f_debt_yield_noi"], test["f_debt_yield_noi"], 0.08)
    out["b2_dscr_lt_125"] = rule(train["f_dscr_noi_reported"], test["f_dscr_noi_reported"], 1.25)
    out["b3_refi_gap"] = rule(train["f_refi_gap"], test["f_refi_gap"], 0, below=False)
    return out


def horizon_rows(T: pd.DataFrame, h: int) -> pd.DataFrame:
    """Each loan's snapshot nearest h months before maturity, within 62 days."""
    t = T.assign(dist=(T["h_months"] - h).abs())
    t = t[t["dist"] <= 62 / 30.44]
    return t.sort_values("dist").drop_duplicates("whole_loan_id")


def evaluate(grace: int = panel.GRACE_DAYS, dist_col: str = "p_logit", test_years=TEST_YEARS, signs=SIGNS,
             dist_tag: str = "signed", tag: str = "", log=print) -> pd.DataFrame:
    L = labels(grace)
    S = attach_distress(snapshots(L), dist_col, dist_tag)
    out = []
    for Y in test_years:
        cutoff = pd.Timestamp(Y - 1, 1, 1) - KNOWN_LAG
        tr = S[S["maturity_eff"] <= cutoff]
        te = S[S["maturity_eff"].dt.year == Y].copy()
        if tr["whole_loan_id"].nunique() < 30 or te.empty:
            continue
        A = MaturityModel(signs=signs).fit(tr)
        te["p_A"] = A.predict(te)
        trB = tr[tr["p_distress"].notna()]
        if trB["whole_loan_id"].nunique() >= 30 and trB["y_fail"].nunique() == 2:
            te["p_B"] = Recalibrated().fit(trB).predict(te)
        else:
            te["p_B"] = np.nan
        te["p_C"] = ensemble(te["p_A"].to_numpy(), te["p_B"].to_numpy())
        for name, p in tier1_baselines(tr, te).items():
            te[name] = p
        te["test_year"], te["grace"], te["C"] = Y, grace, A.C
        te["train_loans"], te["train_failed"] = tr["whole_loan_id"].nunique(), int(
            tr.drop_duplicates("whole_loan_id")["y_fail"].sum())
        out.append(te)
        log(f"maturity model grace {grace}, test {Y}: train {tr['whole_loan_id'].nunique()} loans, "
            f"test {te['whole_loan_id'].nunique()} loans, C={A.C}")
    R = pd.concat(out, ignore_index=True)
    frame.OUT_DIR.mkdir(parents=True, exist_ok=True)
    R.to_parquet(frame.OUT_DIR / f"maturity_eval_grace{grace}{tag}.parquet", index=False)
    return R
