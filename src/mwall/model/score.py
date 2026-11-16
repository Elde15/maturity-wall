"""Final models and the loan-level output table (SOP 11; decisions D051 to D053).

Deployment date D is the last reporting date in the data. The 12-month distress model is fit exactly as in the
rolling evaluation: five cross-fitted models, each fit without one loan fold and calibrated on that fold's
validation window, averaged. Every loan still in a reporting trust is scored at its latest month.

The published distress probability is the logistic model's; the boosted model failed its stage 2 rule (D053)
and its probability is kept beside it.

Intervals (SOP 11 uncertainty) come from a bootstrap by whole loan: each replicate reweights the training and
calibration loans with multinomial counts and refits. The interval is the 5th to 95th percentile.

Failure-to-refinance probability comes from the maturity-window model (the ensemble failed stage 6, D052) and is
published for loans 2.5 to 24 months from maturity, the range that model is fit on. Loans further out carry the
12-month distress probability and the refinance gap only.

Writes data/outputs/scores.parquet and data/outputs/model/final.json.
"""
from __future__ import annotations

import json

import duckdb
import numpy as np
import pandas as pd

from mwall.common import paths
from mwall.model import fit, frame, maturity, rolling

N_BOOT = 20
N_BOOT_MATURITY = 200
SCORES = paths.OUTPUT_DIR / "scores.parquet"
FINAL_JSON = frame.OUT_DIR / "final.json"
H_MIN, H_MAX = 2.5, 24.0


def deployment_date() -> pd.Timestamp:
    return pd.Timestamp(duckdb.connect().execute(
        f"select max(period_end) from '{frame.LABELS_FILE.as_posix()}'").fetchone()[0]).normalize()


def current_rows(D: pd.Timestamp) -> pd.DataFrame:
    """Each whole loan's latest representative month, if that is its trust's latest report and the trust
    reported in the last 62 days."""
    extra = ("f.performing", "f.delinquency_bucket dq_raw", "cast(f.f_in_special_servicing as float) ss_now",
             "f.accession", "l.balance piece_balance")
    lm = frame.LABELS_FILE.as_posix()
    where = (f"f.period_end >= date '{(D - pd.Timedelta(days=62)).date()}' and f.period_end = "
             f"(select max(period_end) from '{lm}' x where x.trust_cik = f.trust_cik)")
    d = frame.load(where=where, extra=extra, performing_only=False)
    d = d.sort_values("period_end").drop_duplicates("whole_loan_id", keep="last").reset_index(drop=True)
    past = d["maturity_eff"].notna() & (d["period_end"] > d["maturity_eff"])
    d["status"] = np.select(
        [d["dq_raw"].eq("matured_nonperforming") | past & ~d["performing"],
         d["ss_now"].fillna(0) > 0,
         d["dq_raw"].isin(["dq30", "dq60", "dq90plus"]),
         d["dq_raw"].eq("matured_performing") | past,
         d["performing"]],
        ["matured, not repaid", "special servicing", "delinquent 30+", "past maturity, paying", "performing"],
        "other")
    return d


def _boot_weights(keys: pd.Series, rng) -> np.ndarray:
    u, inv = np.unique(keys.to_numpy(), return_inverse=True)
    counts = rng.multinomial(len(u), np.full(len(u), 1 / len(u)))
    return counts[inv].astype(float)


def _jsonable(v):
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return None
    if isinstance(v, str):
        return v
    try:
        return round(float(v), 4)
    except (TypeError, ValueError):
        return str(v)


def _base_feature(name: str) -> str:
    """'f_noi_age_months_missing' -> 'f_noi_age_months'; 'property_group=office' -> 'property_group'."""
    return name.split("=")[0].removesuffix("_missing")


# national series are the same for every loan on a date: they move every probability together and are reported
# as market conditions, not as a loan's drivers
MARKET_WIDE = {"f_ust10", "f_ust5", "f_ust10_change_12m", "f_curve_10y2y"}


def _drivers(contrib: np.ndarray, names: list[str], rows: pd.DataFrame, exclude=MARKET_WIDE) -> list[str]:
    """Top three inputs by absolute contribution in log-odds; a missing flag is folded into its feature, and
    market-wide series are left out."""
    base = [_base_feature(n) for n in names]
    agg = pd.DataFrame(contrib, columns=base).T.groupby(level=0, sort=False).sum().T
    agg = agg.drop(columns=[c for c in agg.columns if c in set(exclude)])
    cols = agg.columns.to_list()
    vals = rows.reindex(columns=cols).astype(object).to_numpy()
    A = agg.to_numpy()
    top = np.argsort(-np.abs(A), axis=1)[:, :3]
    return [json.dumps([{"feature": cols[i], "value": _jsonable(vals[r, i]), "log_odds": round(float(A[r, i]), 3)}
                        for i in top[r]]) for r in range(len(A))]


def distress_models(d: pd.DataFrame, D: pd.Timestamp, cur: pd.DataFrame, log=print) -> dict:
    num, cat = frame.feature_list()
    X = fit.matrix(d, num, cat)
    y = d["y_distress_12m"].to_numpy(float)
    lab, grp = d["labeled"].to_numpy(), d["fold"].to_numpy()
    w = {k: v.to_numpy() for k, v in frame.windows(D, d["period_end"]).items()}
    tr_all, va_all = w["train"] & lab, w["valid"] & lab
    perf = cur["performing"].to_numpy()
    Xc = fit.matrix(cur[perf], num, cat)
    info = {"train_rows": int(tr_all.sum()), "train_events": int(y[tr_all].sum()), "valid_rows": int(va_all.sum()),
            "valid_events": int(y[va_all].sum()), "gbm": [], "logit": []}
    C, _ = fit.tune_logit(X[tr_all & ~np.isin(grp, [0, 1])], y[tr_all & ~np.isin(grp, [0, 1])],
                          X[va_all & (grp == 1)], y[va_all & (grp == 1)], num, cat, frame.CREDIT_SIGNS)
    pg, pl, contrib = [], [], None
    for j in range(frame.N_FOLDS):
        tr, va = tr_all & (grp != j), va_all & (grp == j)
        m = fit.Logit(num, cat, C, frame.CREDIT_SIGNS).fit(X[tr], y[tr])
        abl = fit.platt(m.raw(X[va]), y[va])
        pl.append(fit.apply_platt(m.raw(Xc), abl))
        # log-odds after the calibration slope; folds can differ in which missing flags they carry, so add by name
        c = pd.DataFrame(m.contributions(Xc) * abl[1] / frame.N_FOLDS, columns=m.prep.names)
        contrib = c if contrib is None else contrib.add(c, fill_value=0.0)
        info["logit"].append({"fold": j, "C": C, "platt": abl, "coef": m.coefficients().round(5).to_dict()})
        g = fit.GBM(num, cat, rolling.GBM_CONFIG).fit(X[tr], y[tr], X[va], y[va])
        ab = fit.platt(g.raw(X[va]), y[va])
        pg.append(fit.apply_platt(g.raw(Xc), ab))
        info["gbm"].append({"fold": j, "rounds": int(g.rounds), "platt": ab})
        log(f"final distress models, fold {j}: logistic C={C}, boosted {g.rounds} rounds")
    out = pd.DataFrame(index=cur.index[perf])
    out["p_distress_12m"] = np.mean(pl, axis=0)
    out["p_distress_12m_gbm"] = np.mean(pg, axis=0)
    rng = np.random.default_rng(2026)
    keys = d["whole_loan_id"]
    boot = []
    for b in range(N_BOOT):
        j = b % frame.N_FOLDS
        tr, va = tr_all & (grp != j), va_all & (grp == j)
        m = fit.Logit(num, cat, C, frame.CREDIT_SIGNS).fit(X[tr], y[tr], sample_weight=_boot_weights(keys[tr], rng))
        ab = fit.platt(m.raw(X[va]), y[va], sample_weight=_boot_weights(keys[va], rng))
        boot.append(fit.apply_platt(m.raw(Xc), ab))
        if b % 5 == 4:
            log(f"bootstrap {b + 1}/{N_BOOT}")
    boot = np.array(boot)
    out["p_distress_12m_lo"] = np.quantile(boot, 0.05, axis=0)
    out["p_distress_12m_hi"] = np.quantile(boot, 0.95, axis=0)
    out["drivers_distress"] = _drivers(contrib.fillna(0.0).to_numpy(), list(contrib.columns), cur[perf])
    info["n_boot"] = N_BOOT
    return {"scores": out, "info": info}


def maturity_scores(cur: pd.DataFrame, log=print) -> tuple[pd.DataFrame, dict]:
    L = maturity.labels()
    S = maturity.snapshots(L)
    c = cur.copy()
    c["h_months"] = (c["maturity_eff"] - c["period_end"]).dt.days / 30.44
    win = c["h_months"].between(H_MIN, H_MAX) & ~c["status"].isin(["matured, not repaid"])
    c = c[win].copy()
    c["f_dq30plus"] = c["dq_raw"].isin(["dq30", "dq60", "dq90plus", "matured_nonperforming"]).astype(float)
    c["f_in_special_servicing"] = c["ss_now"].fillna(0)
    for g_ in maturity.GROUPS:
        c[f"is_{g_}"] = c["property_group"].astype(object).eq(g_).astype(float)
    for col in maturity.NUM:
        c[col] = pd.to_numeric(c[col], errors="coerce").astype(float)
    A = maturity.MaturityModel().fit(S)
    c["p_fail"] = A.predict(c)
    rng = np.random.default_rng(7)
    reps = []
    for _ in range(N_BOOT_MATURITY):
        Sb = S.assign(w=S["w"] * _boot_weights(S["whole_loan_id"], rng))
        Sb = Sb[Sb["w"] > 0]
        reps.append(maturity.MaturityModel(A.C, A.signs).fit(Sb).predict(c))
    reps = np.array(reps)
    c["p_fail_lo"] = np.quantile(reps, 0.05, axis=0)
    c["p_fail_hi"] = np.quantile(reps, 0.95, axis=0)
    Xs = A.prep.transform(c[maturity.FEATURES].to_numpy(np.float32))
    z_mean = A.prep.transform(S[maturity.FEATURES].to_numpy(np.float32)).mean(axis=0)
    c["drivers_maturity"] = _drivers((Xs - z_mean) * A.m.coef_[0], A.prep.names, c)
    info = {"maturity_C": A.C, "maturity_coef": A.coefficients().round(4).to_dict(), "labeled_loans": int(len(L)),
            "labeled_failed": int(L["y_fail"].sum()), "n_boot_maturity": N_BOOT_MATURITY}
    log(f"maturity-window scores: {len(c):,} loans")
    return c[["p_fail", "p_fail_lo", "p_fail_hi", "h_months", "drivers_maturity"]], info


def run(log=print) -> pd.DataFrame:
    D = deployment_date()
    frame.OUT_DIR.mkdir(parents=True, exist_ok=True)
    cur = current_rows(D)
    log(f"deployment date {D.date()}: {len(cur):,} whole loans in reporting trusts; "
        f"{int(cur['performing'].sum()):,} performing")
    d = frame.load()
    dist = distress_models(d, D, cur, log)
    del d
    mat, minfo = maturity_scores(cur, log)
    out = cur.join(dist["scores"]).join(mat)
    out["refi_gap_usd"] = out["f_refi_gap"] * out["wl_balance_est"]
    out["rank_in_type_distress"] = out.groupby("property_group", observed=True)["p_distress_12m"].rank(
        ascending=False, method="min")
    out["rank_in_type_fail"] = out.groupby("property_group", observed=True)["p_fail"].rank(ascending=False,
                                                                                            method="min")
    keep = ["whole_loan_id", "root_key", "trust_cik", "accession", "deal_family", "vintage", "property_group",
            "prop_state", "cbsa_code", "wl_balance_est", "piece_balance", "maturity_eff", "period_end",
            "snapshot_date", "status", "p_fail", "p_fail_lo", "p_fail_hi", "h_months",
            "p_distress_12m", "p_distress_12m_lo", "p_distress_12m_hi", "p_distress_12m_gbm",
            "rank_in_type_distress", "rank_in_type_fail", "f_refi_dscr", "f_debt_yield_noi", "f_refi_gap",
            "refi_gap_usd", "f_refi_gap_income", "f_ltv_model", "f_dscr_noi_reported", "f_occupancy",
            "f_months_to_maturity", "f_noi_age_months", "f_noi_missing", "f_n_properties", "f_single_asset",
            "drivers_distress", "drivers_maturity"]
    out = out[keep]
    out.to_parquet(SCORES, index=False)
    FINAL_JSON.write_text(json.dumps({"deployment_date": str(D.date()), "train_through": str(
        (D - frame.TRAIN_LAG).date()), "valid_through": str((D - frame.VALID_LAG).date()), **dist["info"],
        **minfo, "n_scored": int(len(out)), "status_counts": out["status"].value_counts().to_dict()},
        indent=1, default=float))
    log(f"wrote {SCORES}: {len(out):,} loans; failure probability for {out['p_fail'].notna().sum():,}")
    return out
