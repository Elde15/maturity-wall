"""Gate 3 report: docs/qa/gate3_models.md, figures in docs/qa/models/, and the experiment log.

Every number comes from the prediction files written by rolling.py, maturity.py, logic.py and external.py.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import subprocess

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from sklearn.metrics import precision_recall_curve  # noqa: E402

from mwall.clean.qa_report import md_table  # noqa: E402
from mwall.common import paths  # noqa: E402
from mwall.model import external, frame, maturity, rolling  # noqa: E402
from mwall.model.metrics import reliability, score  # noqa: E402

FIG_DIR = paths.DOCS_DIR / "qa" / "models"
REPORT = paths.DOCS_DIR / "qa" / "gate3_models.md"
LOG = paths.DOCS_DIR / "experiments.jsonl"
INK, INK2, MUTED, SURFACE, GRID = "#0b0b0b", "#52514e", "#8a8984", "#fcfcfb", "#e7e6e2"
BLUE, ORANGE, AQUA = "#2a78d6", "#eb6834", "#1baf7a"
MIN_EVENTS = 30

FINAL = "p_final"
T2_MODELS = {FINAL: "Logistic, sign-constrained (final)", "p_logit": "Logistic, unconstrained (first spec)",
             "p_gbm": "Boosted trees (LightGBM)"}
T2_BASELINES = {
    "b0_base_rate": "B0 base rate", "b1_dy_lt_7": "B1 debt yield < 7%", "b1_dy_lt_8": "B1 debt yield < 8%",
    "b1_dy_lt_9": "B1 debt yield < 9%", "b1_dy_lt_10": "B1 debt yield < 10%",
    "b1c_debt_yield": "B1c debt yield, continuous", "b2_dscr_lt_100": "B2 DSCR < 1.00",
    "b2_dscr_lt_110": "B2 DSCR < 1.10", "b2_dscr_lt_125": "B2 DSCR < 1.25", "b3_refi_gap": "B3 refinance gap > 0",
}
KEYS = ["origin", "whole_loan_id", "period_end"]


def _style(ax):
    ax.set_facecolor(SURFACE)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    for s in ("left", "bottom"):
        ax.spines[s].set_color(MUTED)
    ax.tick_params(colors=INK2, labelsize=8)
    ax.grid(color=GRID, linewidth=0.6)
    ax.set_axisbelow(True)


def load_predictions(main: str = "main", signed: str = "signed") -> tuple[pd.DataFrame, dict, dict]:
    """The first-specification predictions with the final (sign-constrained) model's columns joined on."""
    P, diag = rolling.load(main)
    S, sdiag = rolling.load(signed)
    cols = {c: c.replace("p_logit", FINAL) for c in S if c.startswith("p_logit")}
    P = P.merge(S[KEYS + list(cols)].rename(columns=cols), on=KEYS, how="left", validate="one_to_one")
    return P, diag, sdiag


def table(P: pd.DataFrame, cols: dict, by: list[str] | None = None) -> pd.DataFrame:
    lab = P[P["labeled"]]
    rows = []
    groups = lab.groupby(by, observed=True) if by else [((), lab)]
    for key, g in groups:
        key = key if isinstance(key, tuple) else (key,)
        for c, name in cols.items():
            if c not in g:
                continue
            s = score(g["y_distress_12m"], g[c], g["wl_balance_est"])
            rows.append({**dict(zip(by or [], key)), "model": name, **s})
    return pd.DataFrame(rows)


def _fmt(t: pd.DataFrame, keep: list[str]) -> pd.DataFrame:
    t = t[[c for c in keep if c in t]].copy()
    for c in ("n", "events", "loans", "months"):
        if c in t:
            t[c] = t[c].astype(int)
    return t


# -------------------------------------------------------------------------------------------- experiment log

def _git() -> str:
    try:
        sha = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True,
                             cwd=paths.REPO_ROOT).stdout.strip()
        dirty = subprocess.run(["git", "status", "--porcelain", "--", "src", "config"], capture_output=True,
                               text=True, cwd=paths.REPO_ROOT).stdout.strip()
        return sha + ("+dirty" if dirty else "")
    except OSError:
        return "unknown"


def data_hash() -> str:
    h = hashlib.sha256()
    for f in (frame.FEATURES_FILE, frame.LABELS_FILE):
        with open(f, "rb") as fh:
            for chunk in iter(lambda: fh.read(1 << 20), b""):
                h.update(chunk)
    return h.hexdigest()[:16]


def log_experiments(entries: list[dict]) -> None:
    seen = set()
    if LOG.exists():
        for line in LOG.read_text(encoding="utf-8").splitlines():
            e = json.loads(line)
            seen.add((e["tag"], e.get("origin"), e["data_hash"], e["commit"]))
    commit, dh = _git(), data_hash()
    with LOG.open("a", encoding="utf-8") as fh:
        for e in entries:
            if (e["tag"], e.get("origin"), dh, commit) in seen:
                continue
            e = {"logged": dt.datetime.now().isoformat(timespec="seconds"), "commit": commit, "data_hash": dh, **e}
            fh.write(json.dumps(e, default=float) + "\n")


# ------------------------------------------------------------------------------------------------- figures

def fig_reliability(P: pd.DataFrame, out) -> None:
    lab = P[P["labeled"]]
    origins = sorted(lab["origin"].unique())
    fig, axes = plt.subplots(1, len(origins), figsize=(3.1 * len(origins), 3.2), facecolor=SURFACE)
    for ax, o in zip(np.atleast_1d(axes), origins):
        g = lab[lab["origin"] == o]
        hi = 0
        for c, color, name in ((FINAL, BLUE, "Final (logistic)"), ("p_gbm", ORANGE, "Boosted")):
            r = reliability(g["y_distress_12m"], g[c])
            ax.plot(r["mean_p"], r["observed"], "-o", color=color, ms=4, lw=1.6, label=name)
            hi = max(hi, r["mean_p"].max(), r["observed"].max())
        ax.plot([0, hi], [0, hi], color=MUTED, lw=1, ls="--")
        _style(ax)
        ax.set_title(f"Test year {o}", fontsize=9, color=INK)
        ax.set_xlabel("Forecast (decile mean)", fontsize=8, color=INK2)
    np.atleast_1d(axes)[0].set_ylabel("Observed 12-month distress rate", fontsize=8, color=INK2)
    np.atleast_1d(axes)[0].legend(frameon=False, fontsize=8)
    fig.tight_layout()
    fig.savefig(out, dpi=150, facecolor=SURFACE)
    plt.close(fig)


def fig_pr(P: pd.DataFrame, out) -> None:
    lab = P[P["labeled"]]
    origins = sorted(lab["origin"].unique())
    fig, axes = plt.subplots(1, len(origins), figsize=(3.1 * len(origins), 3.2), facecolor=SURFACE)
    for ax, o in zip(np.atleast_1d(axes), origins):
        g = lab[lab["origin"] == o]
        y = g["y_distress_12m"]
        for c, color, name, lw in ((FINAL, BLUE, "Final (logistic)", 1.6), ("p_gbm", ORANGE, "Boosted", 1.6),
                                   ("b1c_debt_yield", MUTED, "Debt yield rank", 1.2)):
            pr, rc, _ = precision_recall_curve(y, g[c])
            ax.plot(rc, pr, color=color, lw=lw, label=name)
        ax.axhline(y.mean(), color=MUTED, lw=1, ls=":")
        _style(ax)
        ax.set_ylim(0, None)
        ax.set_title(f"Test year {o}", fontsize=9, color=INK)
        ax.set_xlabel("Recall", fontsize=8, color=INK2)
    np.atleast_1d(axes)[0].set_ylabel("Precision", fontsize=8, color=INK2)
    np.atleast_1d(axes)[0].legend(frameon=False, fontsize=8)
    fig.tight_layout()
    fig.savefig(out, dpi=150, facecolor=SURFACE)
    plt.close(fig)


def fig_importance(imp: pd.DataFrame, out, xlabel: str, top: int = 15) -> None:
    m = imp.mean(axis=1).sort_values(ascending=True).tail(top)
    fig, ax = plt.subplots(figsize=(6.2, 0.28 * top + 0.8), facecolor=SURFACE)
    ax.barh(m.index, m.values, color=BLUE, height=0.6)
    _style(ax)
    ax.grid(axis="y", visible=False)
    ax.set_xlabel(xlabel, fontsize=8, color=INK2)
    fig.tight_layout()
    fig.savefig(out, dpi=150, facecolor=SURFACE)
    plt.close(fig)


def fig_external(m: pd.DataFrame, out) -> None:
    types = [t for t in ["all", "office", "lodging", "retail", "multifamily", "industrial"]
             if t in set(m["property_group"])]
    fig, axes = plt.subplots(2, 3, figsize=(10, 5.4), facecolor=SURFACE, sharex=True)
    for ax, t in zip(axes.ravel(), types):
        x = m[m["property_group"] == t].sort_values("month")
        ax.plot(x["month"], x["rate_pct_trepp"], color=MUTED, lw=1.4, marker="o", ms=2.5, label="Trepp, published")
        ax.plot(x["month"], x["rate_pct_ours"], color=BLUE, lw=1.6, marker="o", ms=2.5, label="This data")
        _style(ax)
        ax.set_title(t, fontsize=9, color=INK)
    for ax in axes.ravel()[len(types):]:
        ax.set_visible(False)
    axes[0, 0].set_ylabel("30+ days delinquent, % of balance", fontsize=8, color=INK2)
    axes[0, 0].legend(frameon=False, fontsize=8)
    fig.tight_layout()
    fig.savefig(out, dpi=150, facecolor=SURFACE)
    plt.close(fig)


# -------------------------------------------------------------------------------------------------- checks

def stage_checks(T: pd.DataFrame, logic: pd.DataFrame | None) -> dict:
    out = {}
    for o, g in T.groupby("origin"):
        g = g.set_index("model")
        base = g.loc[[v for v in T2_BASELINES.values() if v in g.index]]
        lg, gb, fin = g.loc[T2_MODELS["p_logit"]], g.loc[T2_MODELS["p_gbm"]], g.loc[T2_MODELS[FINAL]]

        def beats(m):
            return bool(m["pr_auc"] > base["pr_auc"].max() and m["brier"] < base["brier"].min())

        lo = {}
        if logic is not None:
            x = logic[logic["origin"] == o]
            for mdl in x["model"].unique():
                y = x[x["model"] == mdl]
                lo[mdl] = f"{int(y['pass'].sum())} of {len(y)}" + (
                    f" (fails: {', '.join(y.loc[~y['pass'], 'shock'])})" if (~y["pass"]).any() else "")
        out[o] = {"best_baseline_pr_auc": base["pr_auc"].max(), "best_baseline_brier": base["brier"].min(),
                  "stage1_beats_baselines": beats(lg), "stage2_beats_stage1": bool(
                      gb["pr_auc"] > lg["pr_auc"] and gb["brier"] < lg["brier"]),
                  "final_beats_baselines": beats(fin), "final_slope": fin["cal_slope"],
                  "final_slope_ok": bool(0.8 <= fin["cal_slope"] <= 1.2), "gbm_slope": gb["cal_slope"],
                  "logic": lo}
    return out


def importance_logit(diag: dict) -> pd.DataFrame:
    """Standardized coefficient size per test year: inputs are standardized, so |coefficient| is the change in
    log-odds for a one-standard-deviation move."""
    c = pd.DataFrame({o: d["logit_coef"] for o, d in diag["origins"].items() if "logit_coef" in d})
    return c.abs()


def importance_gbm(diag: dict) -> pd.DataFrame:
    return pd.DataFrame({o: d["mean_abs_shap"] for o, d in diag["origins"].items() if "mean_abs_shap" in d})


def scenario_table(P: pd.DataFrame, cols=(FINAL, "p_gbm")) -> pd.DataFrame:
    rows = []
    for col in cols:
        for o, g in P.groupby("origin"):
            base = g[col]
            top = base >= base.quantile(0.9)
            for s in ("rate_down_100", "rate_up_100"):
                c = f"{col}_{s}"
                if c not in g:
                    continue
                alt = g[c]
                rows.append({"model": T2_MODELS[col], "origin": o, "scenario": s.replace("_", " "),
                             "rank_corr": base.rank().corr(alt.rank()),
                             "top_decile_kept": float((alt[top] >= alt.quantile(0.9)).mean()),
                             "mean_p_change_pct": 100 * (alt.mean() / base.mean() - 1),
                             "share_up": float((alt > base + 1e-12).mean())})
    return pd.DataFrame(rows)


def maturity_tables(R: pd.DataFrame) -> pd.DataFrame:
    cols = {"p_A": "A maturity model", "p_C": "C ensemble", "p_B": "B distress, recalibrated",
            "b0_base_rate": "B0 base rate", "b1_dy_lt_8": "B1 debt yield < 8%", "b2_dscr_lt_125": "B2 DSCR < 1.25",
            "b3_refi_gap": "B3 refinance gap > 0"}
    rows = []
    for h in maturity.HORIZONS:
        H = maturity.horizon_rows(R, h)
        for Y in ["all", *sorted(H["test_year"].unique())]:
            g = H if Y == "all" else H[H["test_year"] == Y]
            both = g[g["p_B"].notna()]
            for c, name in cols.items():
                for sub, gg in (("all loans", g), ("loans with a distress score", both)):
                    if c in ("p_B", "p_C") and sub == "all loans":
                        continue
                    if not len(gg) or gg["y_fail"].nunique() < 2:
                        continue
                    rows.append({"horizon": h, "test_year": str(Y), "sample": sub, "model": name,
                                 **score(gg["y_fail"], gg[c])})
    return pd.DataFrame(rows)


# -------------------------------------------------------------------------------------------------- report

def write(log=print) -> dict:
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    P, diag, sdiag = load_predictions()
    T = table(P, T2_MODELS | T2_BASELINES, ["origin"])
    Tall = table(P, T2_MODELS | T2_BASELINES)
    logic_path = frame.OUT_DIR / "credit_logic.csv"
    logic = pd.read_csv(logic_path) if logic_path.exists() else None
    checks = stage_checks(T, logic)
    fig_reliability(P, FIG_DIR / "reliability.png")
    fig_pr(P, FIG_DIR / "precision_recall.png")
    imp_l, imp_g = importance_logit(sdiag), importance_gbm(diag)
    fig_importance(imp_l, FIG_DIR / "importance.png", "|standardized coefficient| (log-odds per s.d.), mean over test years")
    if not imp_g.empty:
        fig_importance(imp_g, FIG_DIR / "importance_boosted.png", "Mean |SHAP| (log-odds), mean over test years")
    cut_cols = {FINAL: T2_MODELS[FINAL], "p_gbm": T2_MODELS["p_gbm"],
                "b1c_debt_yield": T2_BASELINES["b1c_debt_yield"]}
    P = P.assign(noi_status=np.where(P["f_noi_missing"] > 0, "no current NOI", "current NOI"),
                 structure=np.where(P["f_single_asset"] > 0, "single asset", "pool / portfolio"),
                 vintage_band=pd.cut(P["vintage"], [0, 2016, 2018, 2020, 2022, 2030],
                                     labels=["2016 or earlier", "2017-18", "2019-20", "2021-22", "2023+"]))
    cuts = {name: table(P, cut_cols, [col]) for name, col in (
        ("property type", "property_group"), ("vintage", "vintage_band"), ("structure", "structure"),
        ("NOI", "noi_status"))}
    entries = [{"tag": "main+signed", "origin": int(o), "gbm_params": diag.get("gbm_params"),
                "metrics": T[T["origin"] == o].set_index("model")[["pr_auc", "brier", "cal_slope"]].round(5).to_dict("index")}
               for o in sorted(T["origin"].unique())]
    robust = {}
    for tag in [*(f"signed_ablation_{a}" for a in frame.ABLATIONS), "signed_family_holdout",
                *(f"ablation_{a}" for a in frame.ABLATIONS), "family_holdout"]:
        try:
            Q, qd = rolling.load(tag)
        except (FileNotFoundError, ValueError):
            continue
        Q = Q.rename(columns={"p_logit": FINAL} if tag.startswith("signed") else {})
        cols = {c: n for c, n in (T2_MODELS | {"b1c_debt_yield": T2_BASELINES["b1c_debt_yield"]}).items() if c in Q}
        robust[tag] = table(Q, cols, ["origin"])
        entries += [{"tag": tag, "origin": int(o), "drop": qd.get("drop"), "group": qd.get("group"),
                     "metrics": robust[tag][robust[tag]["origin"] == o].set_index("model")[["pr_auc", "brier"]].round(5).to_dict("index")}
                    for o in sorted(robust[tag]["origin"].unique())]
    scen = scenario_table(P)
    mats = {}
    for name in ("grace90", "grace60", "grace120", "grace90_unconstrained"):
        f = frame.OUT_DIR / f"maturity_eval_{name}.parquet"
        if f.exists():
            mats[name] = maturity_tables(pd.read_parquet(f))
            h12 = mats[name][(mats[name]["horizon"] == 12) & (mats[name]["test_year"] == "all")]
            entries.append({"tag": f"maturity_{name}", "metrics": h12[["sample", "model", "n", "events", "pr_auc",
                                                                      "brier"]].round(5).to_dict("records")})
    ext = external.compare()
    if not ext.empty:
        fig_external(ext, FIG_DIR / "external_check.png")
    log_experiments(entries)
    _write_md(P, T, Tall, checks, diag, sdiag, imp_l, imp_g, cuts, robust, scen, mats, logic, ext)
    log(f"wrote {REPORT}")
    return {"checks": checks, "T": T, "Tall": Tall, "robust": robust, "scen": scen, "mats": mats, "cuts": cuts,
            "imp_l": imp_l, "imp_g": imp_g, "logic": logic, "ext": ext}


def _rank_stability(imp: pd.DataFrame) -> tuple[pd.DataFrame, str]:
    r = imp.rank(ascending=False)
    top = imp.mean(axis=1).sort_values(ascending=False).head(15).index
    tt = r.loc[top].astype(int).reset_index().rename(columns={"index": "feature"})
    corr = r.corr(method="spearman")
    pairs = "; ".join(f"{a} vs {b}: {corr.loc[a, b]:.2f}" for a, b in zip(corr.index[:-1], corr.index[1:]))
    return tt, pairs


def _write_md(P, T, Tall, checks, diag, sdiag, imp_l, imp_g, cuts, robust, scen, mats, logic, ext) -> None:
    keep = ["model", "events", "rate", "mean_p", "pr_auc", "roc_auc", "brier", "log_loss", "cal_slope",
            "cal_intercept", "top10_capture", "top10_capture_balance"]
    L = ["# Gate 3: models", "",
         f"Generated {dt.date.today().isoformat()} by `python -m mwall model` (stages in `src/mwall/model/run.py`). "
         "Design: `src/mwall/model/frame.py` (D051). Every test month below is out of time and out of loan. "
         "Final 12-month distress model: the sign-constrained logistic regression (D053, D054). Final "
         "failure-to-refinance model: the maturity-window model (D052).", "",
         "Metrics: `pr_auc` is average precision (primary); `cal_slope` is the slope of the outcome on the forecast's "
         "log-odds (1 is ideal; below 1 means overconfident); `cal_intercept` is calibration in the large (0 is "
         "ideal; above 0 means the forecast is too low on average); `top10_capture` is the share of events in the "
         "10% of loan-months ranked riskiest, and `_balance` the same share of event balance.", ""]
    L += ["## Windows", "", "| test year | training months | validation months | test months |",
          "| --- | --- | --- | --- |"]
    for o, od in diag["origins"].items():
        D = pd.Timestamp(int(o), 1, 1)
        L.append(f"| {o} | to {(D - frame.TRAIN_LAG).date()}: {od['train_rows']:,} ({od['train_events']:,} events) | "
                 f"to {(D - frame.VALID_LAG).date()}: {od['valid_rows']:,} ({od['valid_events']:,}) | "
                 f"{o}: {od['test_rows_labeled']:,} ({od['test_events']:,}) |")
    L += ["", "## Stage checks (SOP 11 and the Gate 3 checklist)", "",
          "| test year | stage 1 (unconstrained logistic) beats every baseline | stage 2 (boosted) beats stage 1 on "
          "PR-AUC and Brier | final beats every baseline | final calibration slope (0.8 to 1.2) | credit-logic "
          "shocks passed |", "| --- | --- | --- | --- | --- | --- |"]
    for o, c in checks.items():
        lo = "; ".join(f"{k}: {v}" for k, v in c["logic"].items())
        L.append(f"| {o} | {'yes' if c['stage1_beats_baselines'] else 'no'} | "
                 f"{'yes' if c['stage2_beats_stage1'] else 'no'} | {'yes' if c['final_beats_baselines'] else 'no'} | "
                 f"{c['final_slope']:.2f} {'in range' if c['final_slope_ok'] else 'out of range'} | {lo} |")
    L += ["", "## Results by test year", ""]
    for o in sorted(T["origin"].unique()):
        L += [f"### {o}", "", md_table(_fmt(T[T["origin"] == o], keep), floatfmt=".4f"), ""]
    L += ["### All four test years pooled", "", md_table(_fmt(Tall, keep), floatfmt=".4f"), "",
          "![Precision and recall](models/precision_recall.png)", "", "![Reliability](models/reliability.png)", ""]
    if logic is not None:
        L += ["## Credit logic (consistent shocks, D054)", "",
              "Each shock moves every input it touches together (`src/mwall/model/logic.py`); the table gives the "
              "mean change in log-odds over the test months and the share of months moving the expected way.", "",
              md_table(logic.drop(columns=["share_unchanged"]), floatfmt=".3f"), ""]
    L += ["## Cuts, all test years pooled", "",
          f"Segments with fewer than {MIN_EVENTS} events are marked; their metrics are too noisy to read.", ""]
    for name, t in cuts.items():
        t = t.copy()
        col = t.columns[0]
        t["note"] = np.where(t["events"] < MIN_EVENTS, "too few events", "")
        L += [f"### By {name}", "", md_table(_fmt(t, [col, "model", "n", "events", "rate", "mean_p", "pr_auc",
                                                       "roc_auc", "brier", "cal_slope", "note"]), floatfmt=".4f"), ""]
    tt, pairs = _rank_stability(imp_l)
    L += ["## Importance and its stability (SOP 11 stage 4)", "",
          "Final model: inputs are standardized, so a coefficient's size is the change in log-odds for a one "
          "standard deviation move, and the per-loan drivers on the site are exact SHAP values of this linear model "
          "(coefficient times the input's distance from its training mean).", "", "![Importance](models/importance.png)",
          "", "Rank of the 15 largest in each test year:", "", md_table(tt), "",
          f"Rank correlation of all inputs between consecutive test years: {pairs}.", ""]
    if not imp_g.empty:
        tg, pg = _rank_stability(imp_g)
        L += ["Boosted model, mean absolute SHAP:", "", "![Importance, boosted](models/importance_boosted.png)", "",
              md_table(tg), "", f"Rank correlation between consecutive test years: {pg}.", ""]
    L += ["## Robustness suite (SOP 11)", ""]
    for tag, t in robust.items():
        model = T2_MODELS[FINAL] if tag.startswith("signed") else T2_MODELS["p_gbm"]
        ref = T[T["model"] == model].set_index("origin")
        g = t[t["model"] == model].set_index("origin")
        d = pd.DataFrame({"PR-AUC": g["pr_auc"], "PR-AUC, full model": ref["pr_auc"], "Brier": g["brier"],
                          "Brier, full model": ref["brier"]}).reset_index()
        L += [f"### {tag.replace('_', ' ')} ({model})", "", md_table(d, floatfmt=".4f"), ""]
        if "family" in tag:
            L += [md_table(_fmt(t, ["origin", "model", "n", "events", "pr_auc", "brier", "cal_slope"]),
                           floatfmt=".4f"), ""]
    if not scen.empty:
        L += ["### Refinance rate moved 100 bp", "",
              "Same fitted models; the rate-dependent features are recomputed (`model/scenario.py`).", "",
              md_table(scen, floatfmt=".3f"), ""]
    L += ["## Maturity outcome (tier 1, D052)", ""]
    for name, t in mats.items():
        L += [f"### {name.replace('_', ', ').replace('grace', 'grace ')} days, 12 months before maturity", "",
              md_table(_fmt(t[t["horizon"] == 12], ["test_year", "sample", "model", "n", "events", "pr_auc",
                                                    "roc_auc", "brier", "cal_slope"]), floatfmt=".3f"), ""]
        if name == "grace90":
            other = t[(t["horizon"] != 12) & (t["test_year"] == "all")]
            L += ["Horizons 6 and 3 months, test years pooled:", "",
                  md_table(_fmt(other, ["horizon", "sample", "model", "n", "events", "pr_auc", "roc_auc", "brier",
                                        "cal_slope"]), floatfmt=".3f"), ""]
    if not ext.empty:
        L += ["## External check against published delinquency rates (SOP 10)", "",
              "Trepp's published 30+ day delinquency rate beside the same stock measure in this data. A back-check "
              "only; the published figures never enter training.", "", "![External check](models/external_check.png)",
              "", md_table(external.summary(ext), floatfmt=".2f"), ""]
    REPORT.write_text("\n".join(L), encoding="utf-8")
