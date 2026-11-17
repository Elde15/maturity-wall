"""Site data (SOP 14 data contract): the JSON files the static site reads.

    python -m mwall site               # writes site/public/data/

Files, each carrying build date, data cut-off and schema version:
  meta.json        build facts and market inputs
  summary.json     headline numbers and every chart series on the home, wall and method pages
  loans.json       one row per scored loan (columnar), for the explorer
  uw.json          underwriting inputs per loan (columnar, full precision), for the JavaScript engine
  scenarios.json   scenarios, engine parameters, and the parameter table with each source
  history/xx.json  per-loan filing history and facts, sharded by the id's first two hex digits
"""
from __future__ import annotations

import csv
import datetime as dt
import json
import math
import subprocess

import duckdb
import numpy as np
import pandas as pd

from mwall.common import paths
from mwall.underwrite import engine

SITE = paths.REPO_ROOT / "site"
OUT = SITE / "public" / "data"
SCHEMA = "1.0"
TYPES = ["office", "retail", "multifamily", "lodging", "industrial", "self_storage", "mixed_use", "other"]
DISTRESSED = {"matured, not repaid", "special servicing", "delinquent 30+"}
# charts fold mixed use and other into one category (seven validated colors; site/DESIGN.md)
CHART_TYPES = ["office", "retail", "multifamily", "lodging", "industrial", "self_storage", "mixed_other"]


# ------------------------------------------------------------------ helpers

def _clean(v, nd: int | None = None):
    if v is None:
        return None
    if isinstance(v, (np.bool_, bool)):
        return bool(v)
    if isinstance(v, (pd.Timestamp, dt.date)):
        return None if pd.isna(v) else pd.Timestamp(v).strftime("%Y-%m-%d")
    if isinstance(v, (np.integer,)):
        return int(v)
    if isinstance(v, (float, np.floating)):
        f = float(v)
        if math.isnan(f) or math.isinf(f):
            return None
        return round(f, nd) if nd is not None else f
    try:
        if pd.isna(v):
            return None
    except (TypeError, ValueError):
        pass
    return v


def columnar(df: pd.DataFrame, digits: dict | None = None) -> dict:
    digits = digits or {}
    return {c: [_clean(v, digits.get(c)) for v in df[c].tolist()] for c in df.columns}


def write(name: str, obj: dict, meta: dict) -> int:
    path = OUT / name
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps({"meta": meta, **obj}, separators=(",", ":"), allow_nan=False)
    path.write_text(text, encoding="utf-8")
    return len(text)


def git_commit() -> str:
    r = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, cwd=paths.REPO_ROOT)
    return r.stdout.strip() or "unknown"


# ------------------------------------------------------------------ inputs

def load() -> dict:
    s = pd.read_parquet(paths.OUTPUT_DIR / "scores.parquet")
    d = pd.read_parquet(paths.OUTPUT_DIR / "underwrite_inputs.parquet")
    u = pd.read_parquet(paths.OUTPUT_DIR / "underwriting.parquet")
    g = pd.read_parquet(paths.OUTPUT_DIR / "underwriting_grid.parquet")
    t = pd.read_parquet(paths.META_DIR / "trusts.parquet", columns=["trust_cik", "trust_name"])
    M = engine.load_market()
    return {"scores": s, "inputs": d, "uw": u, "grid": g, "trusts": t, "market": M}


def meta_block(x: dict) -> dict:
    s = x["scores"]
    return {"schema_version": SCHEMA, "build_date": dt.date.today().isoformat(),
            "data_cutoff": pd.Timestamp(s["period_end"].max()).strftime("%Y-%m-%d"),
            "valuation_date": x["market"]["date"], "commit": git_commit()}


# ------------------------------------------------------------------ loans.json

def loans_table(x: dict) -> pd.DataFrame:
    s, d, t = x["scores"], x["inputs"], x["trusts"]
    base = x["uw"][x["uw"]["scenario"].eq("base")].set_index("whole_loan_id")
    L = s.merge(t, on="trust_cik", how="left").merge(
        d[["whole_loan_id", "prop_name", "prop_city", "lat", "lon", "county_fips", "noi", "coupon"]],
        on="whole_loan_id", how="left")
    b = base.reindex(L["whole_loan_id"])
    out = pd.DataFrame({
        "id": L["whole_loan_id"], "name": L["prop_name"], "city": L["prop_city"], "state": L["prop_state"],
        "cbsa": L["cbsa_code"], "county": L["county_fips"], "type": L["property_group"].astype(object),
        "status": L["status"], "trust": L["trust_name"], "vintage": L["vintage"],
        "bal": L["wl_balance_est"], "mat": L["maturity_eff"], "coupon": L["coupon"],
        "pf": L["p_fail"], "pf_lo": L["p_fail_lo"], "pf_hi": L["p_fail_hi"],
        "pd": L["p_distress_12m"], "pd_lo": L["p_distress_12m_lo"], "pd_hi": L["p_distress_12m_hi"],
        "rk_d": L["rank_in_type_distress"], "rk_f": L["rank_in_type_fail"],
        "dy": L["f_debt_yield_noi"], "dscr": L["f_dscr_noi_reported"], "occ": L["f_occupancy"],
        "tier": b["tier"].to_numpy(), "gap": b["refi_gap"].to_numpy(), "gap_pct": b["refi_gap_pct"].to_numpy(),
        "value": b["value"].to_numpy(), "vbid": b["value_bid"].to_numpy(), "rbid": b["return_bid"].to_numpy(),
        "bid": b["bid"].to_numpy(), "disc": b["discount"].to_numpy(), "opp": b["opportunity_score"].to_numpy(),
        "irr_v": b["irr_at_value_bid"].to_numpy(),
        "lat": L["lat"], "lon": L["lon"],
    })
    n_type = out.groupby("type")["id"].transform("size")
    out["n_type"] = n_type
    return out


LOAN_DIGITS = {"bal": 0, "coupon": 5, "pf": 4, "pf_lo": 4, "pf_hi": 4, "pd": 5, "pd_lo": 5, "pd_hi": 5, "dy": 4,
               "dscr": 3, "occ": 3, "gap": 0, "gap_pct": 4, "value": 0, "vbid": 0, "rbid": 0, "bid": 0, "disc": 4,
               "opp": 1, "irr_v": 4, "lat": 3, "lon": 3}


# ------------------------------------------------------------------ uw.json and scenarios.json

UW_KEYS = ["whole_loan_id", "group", "tier", "tier_reason", "jurisdiction", "wl_balance_est", "noi", "revenue",
           "occupancy", "sqft", "units", "bench_today", "spread_sec", "bench_kind", "tax_rate", "tax_current",
           "rent_cap", "high_tax_metro", "mf_rent_growth_metro", "valuation"] + \
          [f"tenant{i}_{k}" for i in (1, 2, 3) for k in ("sqft", "lease_exp")]


def uw_table(x: dict, P: dict) -> pd.DataFrame:
    rows = engine.prepare(x["inputs"], P)
    keep = [r for r in rows if r["group"] is not None and not math.isnan(engine._num(r.get("noi")))]
    df = pd.DataFrame([{k: r.get(k) for k in UW_KEYS} for r in keep])
    df["rent_cap"] = df["rent_cap"].where(np.isfinite(df["rent_cap"].astype(float)), None)
    for i in (1, 2, 3):
        c = f"tenant{i}_lease_exp"
        df[c] = pd.to_datetime(df[c], errors="coerce").dt.strftime("%Y-%m-%d")
    df["valuation"] = pd.to_datetime(df["valuation"]).dt.strftime("%Y-%m-%d")
    return df


def _research_rows(name: str) -> list[dict]:
    with open(paths.CONFIG_DIR / "research" / name, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def _cite(sources: str, research: dict) -> list[dict]:
    """'underwriting_sources.csv:12;13' -> the cited rows' publisher, title, date and URL."""
    out, current = [], None
    for ref in sources.split(";"):
        if ":" in ref:
            current, ref = ref.split(":", 1)
        rows = research.get(current)
        if rows and ref.isdigit():
            r = rows[int(ref) - 1]
            out.append({"row": f"{current}:{ref}", "publisher": r.get("source_publisher"),
                        "title": r.get("title") or r.get("source_title"), "date": r.get("publication_date"),
                        "url": r.get("url")})
        elif not rows:
            out.append({"row": (current + ":" + ref) if current and current not in research else ref})
    return out


def scenarios_obj(P: dict, M: dict) -> dict:
    research = {"underwriting_sources.csv": _research_rows("underwriting_sources.csv"),
                "la_rules_sources.csv": _research_rows("la_rules_sources.csv")}
    params = []
    for fname in ("underwriting_params.csv", "la_overrides.csv"):
        for r in csv.DictReader(open(paths.CONFIG_DIR / fname, encoding="utf-8", newline="")):
            params.append({**{k: r[k] for k in r if k != "sources"}, "file": fname,
                           "sources": _cite(r["sources"], research)})
    lender = [{k: _clean(v) for k, v in row.items() if k in (
        "scenario", "property_group", "ltv_max", "dscr_min", "dy_min", "amort_years", "spread_series",
        "spread_premium_bps")} for row in P["lender"].values()]
    par = {k: v for k, v in P.items() if k not in ("la", "lender", "scenarios")}
    return {
        "scenarios": [{k: _clean(v) for k, v in s.items() if k != "Index"} for s in P["scenarios"].values()],
        "engine": {"par": par, "la": {"|".join(k): v for k, v in P["la"].items()}, "lender": lender},
        "market": M, "parameters": params,
    }


# ------------------------------------------------------------------ history shards

HIST_FIELDS = {"period_end": "period_end", "accession": "accession", "fin_noi_annual": "noi",
               "dscr_noi_reported": "dscr", "occupancy_current": "occ", "wl_balance_est": "bal"}
FACTS = {"originalLoanAmount": "orig_amount", "originationDate": "orig_date", "maturityDate": "maturity",
         "reportPeriodInterestRatePercentage": "coupon", "originalAmortizationTermNumber": "amort_months",
         "originalInterestOnlyTermNumber": "io_months", "loanStructureCode": "structure", "prop_name": "name",
         "prop_address": "address", "prop_city": "city", "prop_state": "state", "prop_zip": "zip",
         "year_built": "year_built", "sqft": "sqft", "units": "units", "n_properties": "n_properties",
         "val_securitization": "appraisal_sec", "val_securitization_date": "appraisal_sec_date",
         "fin_noi_sec": "noi_sec", "occupancy_securitization": "occ_sec", "paymentStatusLoanCode": "status_code"}


def history(x: dict, L: pd.DataFrame | None = None, uw: pd.DataFrame | None = None, log=print) -> int:
    s = x["scores"][["whole_loan_id", "root_key", "accession", "drivers_distress", "drivers_maturity",
                      "trust_cik"]].copy()
    lp = (paths.PARSED_DIR / "loan_period" / "*.parquet").as_posix()
    con = duckdb.connect()
    con.register("k", s[["whole_loan_id", "root_key", "accession"]])
    pick_h = ", ".join(f"arg_max(p.{a}, coalesce(p.balance, 0)) {b}" for a, b in HIST_FIELDS.items()
                       if a not in ("period_end", "accession"))
    h = con.execute(f"""
        select k.whole_loan_id id, p.period_end, p.accession, {pick_h}
        from k join read_parquet('{lp}', union_by_name=true) p on p.root_key = k.root_key
        where p.loan_source in ('loan_record','note_record','replicated_child')
          and not coalesce(p.flag_filing_corrupt, false) and not coalesce(p.flag_foreign_record, false)
        group by 1, 2, 3 order by 1, 2""").df()
    pick_f = ", ".join(f"arg_max(p.{a}, coalesce(p.balance, 0)) {b}" for a, b in FACTS.items())
    f = con.execute(f"""
        select k.whole_loan_id id, {pick_f}
        from k join read_parquet('{lp}', union_by_name=true) p using (root_key, accession)
        group by 1""").df()
    filings = pd.read_parquet(paths.META_DIR / "filings.parquet")
    fd = filings.drop_duplicates("accession").set_index("accession")["filing_date"]
    facts = f.set_index("id")
    drv = s.set_index("whole_loan_id")
    # the tear sheet reads one shard: the loan's table row and its underwriting inputs ride along
    row_of = {} if L is None else {r["id"]: r for r in pd.DataFrame(columnar(L, LOAN_DIGITS)).to_dict("records")}
    uw_of = {} if uw is None else {r["whole_loan_id"]: r for r in pd.DataFrame(columnar(uw)).to_dict("records")}
    shards: dict[str, dict] = {}
    for lid, g in h.groupby("id"):
        g = g.drop_duplicates("period_end", keep="last")
        rec = {"series": columnar(g[["period_end", "accession", "noi", "dscr", "occ", "bal"]],
                                  {"noi": 0, "dscr": 3, "occ": 3, "bal": 0})}
        rec["series"]["filed"] = [_clean(fd.get(a)) for a in g["accession"]]
        if lid in facts.index:
            rec["facts"] = {k: _clean(v) for k, v in facts.loc[lid].items()}
        rec["cik"] = int(drv.loc[lid, "trust_cik"])
        for c in ("drivers_distress", "drivers_maturity"):
            v = drv.loc[lid, c]
            rec[c] = json.loads(v) if isinstance(v, str) else None
        if lid in row_of:
            rec["row"] = {k: (None if isinstance(v, float) and math.isnan(v) else v) for k, v in row_of[lid].items()}
        if lid in uw_of:
            rec["uw"] = {k: (None if isinstance(v, float) and math.isnan(v) else v) for k, v in uw_of[lid].items()}
        shards.setdefault(lid[2:4], {})[lid] = rec
    for key, obj in shards.items():
        write(f"history/{key}.json", {"loans": obj}, {"schema_version": SCHEMA})
    log(f"history: {len(h):,} loan-months in {len(shards)} shards")
    return len(shards)


# ------------------------------------------------------------------ summary.json (charts)

def wall(x: dict, L: pd.DataFrame) -> dict:
    D = pd.Timestamp(x["market"]["date"])
    y = L["mat"].dt.year
    bucket = np.where(L["mat"] < D, "past due", y.astype("Int64").astype(str))
    t = L["type"].replace({"mixed_use": "mixed_other", "other": "mixed_other"}).fillna("not reported")
    df = pd.DataFrame({"bucket": bucket, "type": t, "bal": L["bal"], "gap": L["gap"].fillna(0.0)})
    df = df[df["bucket"].isin(["past due"] + [str(v) for v in range(D.year, D.year + 10)])]
    years = ["past due"] + [str(v) for v in range(D.year, D.year + 10)]
    pv = df.pivot_table(index="bucket", columns="type", values="bal", aggfunc="sum").reindex(years).fillna(0)
    gap = df.groupby("bucket")["gap"].sum().reindex(years).fillna(0)
    n = df.groupby("bucket").size().reindex(years).fillna(0)
    types = [c for c in CHART_TYPES + ["not reported"] if c in pv.columns]
    return {"buckets": years, "types": types,
            "balance": {c: [round(float(v)) for v in pv[c]] for c in types},
            "gap": [round(float(v)) for v in gap], "loans": [int(v) for v in n]}


def gap_by_type(L: pd.DataFrame) -> list[dict]:
    """Over loans with a refinance test: those with a value, plus negative-NOI loans (gap = balance)."""
    v = L[L["gap"].notna()].assign(type=lambda d: d["type"].replace({"mixed_use": "mixed_other", "other": "mixed_other"}))
    rows = []
    for t in CHART_TYPES:
        g = v[v["type"].eq(t)]
        if not len(g):
            continue
        rows.append({"type": t, "loans": int(len(g)), "balance": round(float(g["bal"].sum())),
                     "balance_with_gap": round(float(g.loc[g["gap"] > 0, "bal"].sum())),
                     "share_with_gap": float(g.loc[g["gap"] > 0, "bal"].sum() / g["bal"].sum()),
                     "gap": round(float(g["gap"].sum())), "loans_with_gap": int((g["gap"] > 0).sum())})
    return rows


def scenario_series(x: dict) -> dict:
    g, u = x["grid"], x["uw"]
    by_rate = g[g["cap_shift_bps"] == 0].groupby("rate_shift_bps")["refi_gap"].sum()
    by_cap = g[g["rate_shift_bps"] == 0].groupby("cap_shift_bps")["refi_gap"].sum()
    grid = g.pivot_table(index="rate_shift_bps", columns="cap_shift_bps", values="refi_gap", aggfunc="sum")
    sc = u.groupby("scenario").agg(gap=("refi_gap", "sum"), with_gap=("refi_gap_pct", lambda s: int((s > 0).sum())),
                                   below=("refinanceable_by_sale", lambda s: int((s == False).sum())))  # noqa: E712
    return {"by_rate": {"shift_bps": [int(i) for i in by_rate.index], "gap": [round(float(v)) for v in by_rate]},
            "by_cap": {"shift_bps": [int(i) for i in by_cap.index], "gap": [round(float(v)) for v in by_cap]},
            "grid": {"rate": [int(i) for i in grid.index], "cap": [int(c) for c in grid.columns],
                     "gap": [[round(float(v)) for v in row] for row in grid.to_numpy()]},
            "scenarios": {k: {"gap": round(float(r["gap"])), "loans_with_gap": int(r["with_gap"]),
                              "bid_below_balance": int(r["below"])} for k, r in sc.iterrows()}}


def high_risk(L: pd.DataFrame) -> pd.Series:
    top_decile = L["pd"] >= L["pd"].quantile(0.9)
    return L["status"].isin(DISTRESSED) | (L["pf"] >= 0.5) | top_decile


def discounts(L: pd.DataFrame, hurdle: float) -> dict:
    v = L[high_risk(L) & L["bid"].notna() & L["bal"].gt(0)]
    edges = [0, 1e-9, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.8, 1.0001]
    labels = ["no discount", "0-10%", "10-20%", "20-30%", "30-40%", "40-50%", "50-60%", "60-80%", "80-100%"]
    cut = pd.cut(v["disc"], edges, labels=labels, right=False, include_lowest=True)
    counts = cut.value_counts().reindex(labels).fillna(0)
    bal = v.groupby(cut, observed=False)["bal"].sum().reindex(labels).fillna(0)
    clears = v["irr_v"] >= hurdle
    return {"bins": labels, "loans": [int(c) for c in counts], "balance": [round(float(b)) for b in bal],
            "n": int(len(v)), "median_discount_below_par": float(v.loc[v["disc"] > 0, "disc"].median()),
            "share_clearing_hurdle_at_value": float(clears.mean()), "hurdle": hurdle,
            "definition": "in special servicing, 30+ days delinquent or past maturity unpaid; or failure "
                          "probability of 50% or more; or 12-month distress probability in the top decile"}


def model_charts(log=print) -> dict:
    """Calibration and precision-recall series for the final 12-month distress model, from the Gate 3 runs."""
    from sklearn.metrics import precision_recall_curve

    from mwall.model import report as mreport
    from mwall.model.metrics import reliability, score

    P, _, _ = mreport.load_predictions()
    lab = P[P["labeled"]]
    out = {"years": [], "calibration": {}, "pr": {}, "metrics": []}
    for o in sorted(lab["origin"].unique()):
        g = lab[lab["origin"] == o]
        y = g["y_distress_12m"].to_numpy()
        year = int(pd.Timestamp(o).year) if not isinstance(o, (int, np.integer)) else int(o)
        out["years"].append(year)
        r = reliability(g["y_distress_12m"], g[mreport.FINAL])
        out["calibration"][year] = {"forecast": [float(v) for v in r["mean_p"]],
                                    "observed": [float(v) for v in r["observed"]],
                                    "n": [int(v) for v in r["n"]] if "n" in r else None}
        curves = {}
        for col, name in ((mreport.FINAL, "model"), ("b1c_debt_yield", "debt_yield_rank")):
            pr, rc, _ = precision_recall_curve(y, g[col])
            idx = np.unique(np.linspace(0, len(rc) - 1, 120).astype(int))
            curves[name] = {"recall": [round(float(v), 4) for v in rc[idx]],
                            "precision": [round(float(v), 4) for v in pr[idx]]}
        curves["base_rate"] = float(y.mean())
        out["pr"][year] = curves
        codes, uniq = pd.factorize(g["whole_loan_id"])
        rng = np.random.default_rng(year)
        for col, name in ((mreport.FINAL, "model"), ("b1c_debt_yield", "debt yield rank"),
                          ("b1_dy_lt_10", "debt yield < 10%"), ("b2_dscr_lt_125", "DSCR < 1.25"),
                          ("b3_refi_gap", "refinance gap > 0"), ("b0_base_rate", "base rate")):
            if col in g:
                sc = score(g["y_distress_12m"], g[col], g["wl_balance_est"])
                row = {"year": year, "model": name, **{k: _clean(v) for k, v in sc.items()}}
                if name in ("model", "debt yield rank"):   # 90% range on PR-AUC, resampling whole loans
                    from sklearn.metrics import average_precision_score
                    draws = []
                    for _ in range(200):
                        w = rng.multinomial(len(uniq), np.full(len(uniq), 1 / len(uniq)))[codes]
                        draws.append(average_precision_score(y, g[col].to_numpy(), sample_weight=w))
                    row["pr_auc_lo"], row["pr_auc_hi"] = (float(v) for v in np.percentile(draws, [5, 95]))
                out["metrics"].append(row)
    log(f"model charts: {len(out['years'])} test years")
    return out


def maturity_findings() -> dict:
    """What failure at maturity followed, 12 months out, across the 431 resolved maturities (model card)."""
    from mwall.model import maturity

    h = maturity.horizon_rows(maturity.snapshots(maturity.labels(90)), 12)
    g = h[h["f_refi_gap"].notna()]
    by_type = h.groupby("property_group")["y_fail"].agg(["mean", "size"])
    return {"loans": int(h["whole_loan_id"].nunique()), "failed": int(h["y_fail"].sum()),
            "gap_positive": {"loans": int((g["f_refi_gap"] > 0).sum()), "failed_share": float(g.loc[g["f_refi_gap"] > 0, "y_fail"].mean())},
            "gap_zero": {"loans": int((g["f_refi_gap"] == 0).sum()), "failed_share": float(g.loc[g["f_refi_gap"] == 0, "y_fail"].mean())},
            "gap_missing_share": float(h["f_refi_gap"].isna().mean()),
            "by_type": [{"type": t, "loans": int(r["size"]), "failed_share": float(r["mean"])} for t, r in by_type.iterrows()]}


def summary(x: dict, L: pd.DataFrame, P: dict, log=print) -> dict:
    base = x["uw"][x["uw"]["scenario"].eq("base")]
    hurdle = engine.par(P, "hurdle_levered_irr", "all") / 100
    rb = base.dropna(subset=["return_bid"])
    head = {
        "loans_scored": int(len(L)), "balance_scored": round(float(L["bal"].sum())),
        "trusts": int(x["scores"]["trust_cik"].nunique()),
        "loans_valued": int(base["value"].notna().sum()),
        "gap_base": round(float(base["refi_gap"].sum())), "loans_with_gap": int((base["refi_gap_pct"] > 0).sum()),
        "gap_office": round(float(base.loc[base["property_group"].eq("office"), "refi_gap"].sum())),
        "gap_downside": round(float(x["uw"].loc[x["uw"]["scenario"].eq("downside"), "refi_gap"].sum())),
        "bid_below_balance": int((base["refinanceable_by_sale"] == False).sum()),  # noqa: E712
        "median_discount_below": float(base.loc[base["discount"] > 0, "discount"].median()),
        "median_irr_unlevered_at_value": float(rb["irr_unlevered_at_value_bid"].median()),
        "median_irr_levered_at_value": float(rb["irr_at_value_bid"].median()),
        "hurdle": hurdle,
        "binding": {k: float(v) for k, v in pd.Series(np.select(
            [base["p_ltv"] <= base[["p_dscr", "p_dy"]].min(axis=1), base["p_dscr"] <= base["p_dy"]],
            ["ltv", "dscr"], "debt_yield")[base["p_max"].notna() & base["value"].notna()]).value_counts(normalize=True).items()},
        "distressed_now": {k: int(v) for k, v in L.loc[L["status"].isin(DISTRESSED), "status"].value_counts().items()},
        "with_failure_probability": int(L["pf"].notna().sum()),
    }
    t = L.assign(chart_type=L["type"].replace({"mixed_use": "mixed_other", "other": "mixed_other"}).fillna("not reported"))
    head["by_type_all"] = [{"type": k, "loans": int(len(g)), "balance": round(float(g["bal"].sum()))}
                           for k, g in t.groupby("chart_type")]
    valued = base[base["value"].notna()]
    head["cap_benchmark_only"] = int(valued["cap_method"].eq("benchmark only").sum())
    head["cap_composite"] = int(valued["bench_kind"].eq("composite").sum())
    head["tiers"] = {k: int(v) for k, v in base["tier"].value_counts().items()}
    return {"headline": head, "wall": wall(x, L), "gap_by_type": gap_by_type(L), "scenario_gap": scenario_series(x),
            "discounts": discounts(L, hurdle), "model": model_charts(log), "maturity": maturity_findings()}


DATA_SOURCES = [
    ("SEC EDGAR: Form ABS-EE asset-level filings (exhibit EX-102) and form indexes", "U.S. Securities and Exchange Commission",
     "https://www.sec.gov/Archives/edgar/full-index/"),
    ("SEC EDGAR submissions API (filer histories)", "U.S. Securities and Exchange Commission", "https://data.sec.gov/submissions/"),
    ("Form 10-D distribution statements (EX-99.1), for the balance check and vintage-2016 loan tables",
     "Certificate administrators via SEC EDGAR", "https://www.sec.gov/Archives/edgar/data/"),
    ("Treasury constant-maturity yields (DGS2, DGS5, DGS7, DGS10)", "Federal Reserve Bank of St. Louis, FRED",
     "https://fred.stlouisfed.org/"),
    ("Zillow Observed Rent Index, metro, all homes and multifamily", "Zillow Research", "https://www.zillow.com/research/data/"),
    ("Quarterly Census of Employment and Wages", "U.S. Bureau of Labor Statistics", "https://www.bls.gov/cew/"),
    ("Building Permits Survey, county files", "U.S. Census Bureau", "https://www.census.gov/construction/bps/"),
    ("Housing unit estimates, 2020 and 2024 vintages", "U.S. Census Bureau", "https://www.census.gov/programs-surveys/popest.html"),
    ("Census Geocoder (addresses to counties and tracts; coordinates to incorporated places)", "U.S. Census Bureau",
     "https://geocoding.geo.census.gov/geocoder/"),
    ("ZCTA-to-county relationship file (2020) and metro delineation file (July 2023)", "U.S. Census Bureau and OMB",
     "https://www.census.gov/geographies/reference-files.html"),
    ("US state and county boundaries (us-atlas, from Census cartographic boundaries)", "us-atlas / U.S. Census Bureau",
     "https://github.com/topojson/us-atlas"),
]
RESEARCH_GROUPS = [
    ("lender_params_sources.csv", "Lender sizing terms and lending spreads", "source_publisher", "source_title"),
    ("cap_rates_sources.csv", "Cap-rate benchmarks", "source_publisher", "title"),
    ("underwriting_sources.csv", "Buyer underwriting assumptions", "source_publisher", "title"),
    ("la_rules_sources.csv", "Los Angeles transfer taxes, property tax and rent rules", "source_publisher", "title"),
    ("la_market_sources.csv", "Los Angeles market context", "source_publisher", "title"),
    ("cmbs_delinquency_sources.csv", "Published CMBS delinquency rates (external check)", "source_publisher", "title"),
]


def sources_obj() -> dict:
    """Every outside source: the data feeds, then each research file's documents (one row per URL)."""
    groups = [{"group": "Data feeds", "file": None,
               "items": [{"title": t, "publisher": p, "url": u, "date": None, "rows": None} for t, p, u in DATA_SOURCES]}]
    for fname, label, pub, title in RESEARCH_GROUPS:
        path = paths.CONFIG_DIR / "research" / fname
        if not path.exists():
            continue
        rows = _research_rows(fname)
        by_url: dict = {}
        for r in rows:
            u = r.get("url") or ""
            if not u:
                continue
            t = r.get(title) or r.get("title") or r.get("source_title") or r.get("edition")
            if not t and r.get("report_month"):
                t = f"CMBS delinquency report, data for {r['report_month']} (published {r.get('publication_date')})"
            if not t and r.get("rule"):
                t = f"{r['rule'].replace('_', ' ')}, {r.get('jurisdiction', '')}"
            d = by_url.setdefault(u, {"title": t,
                                      "publisher": r.get(pub) or r.get("publisher") or r.get("source"),
                                      "url": u, "date": r.get("publication_date"), "rows": 0})
            d["rows"] += 1
        groups.append({"group": label, "file": f"config/research/{fname}",
                       "items": sorted(by_url.values(), key=lambda x: (str(x["publisher"]), str(x["date"])))})
    return {"groups": groups}


def feature_labels() -> dict:
    """Feature name -> definition and unit (features/catalog.py), for the tear sheet's model drivers."""
    from mwall.features.catalog import CATALOG

    out = {f.name: {"definition": f.definition, "unit": f.unit, "family": f.family} for f in CATALOG}
    out["property_group"] = {"definition": "Property type", "unit": "category", "family": "Property"}
    out["delinquency_bucket"] = {"definition": "Payment status this month", "unit": "category", "family": "Servicing and status"}
    for t in TYPES:
        out[f"is_{t}"] = {"definition": f"Property type is {t.replace('_', ' ')}", "unit": "0/1", "family": "Property"}
    return out


# ------------------------------------------------------------------ main

def main(log=print) -> None:
    x = load()
    P = engine.load_params()
    meta = meta_block(x)
    L = loans_table(x)
    U = uw_table(x, P)
    sizes = {
        "loans.json": write("loans.json", {"loans": columnar(L, LOAN_DIGITS)}, meta),
        "uw.json": write("uw.json", {"loans": columnar(U)}, meta),
        "scenarios.json": write("scenarios.json", scenarios_obj(P, x["market"]), meta),
        "summary.json": write("summary.json", summary(x, L, P, log), meta),
        "meta.json": write("meta.json", {"market": x["market"], "features": feature_labels()}, meta),
        "sources.json": write("sources.json", sources_obj(), meta),
    }
    csv_cols = ["id", "name", "city", "state", "county", "cbsa", "type", "status", "trust", "vintage", "bal", "mat", "coupon",
                "pf", "pf_lo", "pf_hi", "pd", "pd_lo", "pd_hi", "dy", "dscr", "occ", "tier", "gap", "gap_pct", "value", "vbid",
                "rbid", "bid", "disc", "opp", "lat", "lon"]
    L[csv_cols].to_csv(OUT / "loans.csv", index=False, float_format="%.6g", date_format="%Y-%m-%d")
    history(x, L, U, log)
    for k, v in sizes.items():
        log(f"{k}: {v / 1e6:.2f} MB")
