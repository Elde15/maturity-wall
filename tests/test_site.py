"""Gate 5: the site's JavaScript engine against the Python engine, and the site data against the output tables."""
import json
import math
import shutil
import subprocess

import numpy as np
import pandas as pd
import pytest

from mwall.common import paths
from mwall.site_export import export
from mwall.underwrite import engine

DATA = export.OUT
NODE = shutil.which("node")
DOLLARS = ["noi_stressed", "value", "p_ltv", "p_dscr", "p_dy", "p_max", "refi_gap", "lease_up", "value_bid",
           "exit_price", "exit_net", "return_bid", "loan_at_bid", "equity", "bid", "noi_y1"]
RATES = ["cap_rate", "refi_rate", "loan_constant", "refi_gap_pct", "irr_levered", "irr_unlevered",
         "equity_multiple", "cash_on_cash", "dscr_y1", "dy_y1", "breakeven_occ", "discount", "exit_cap",
         "acq_rate", "irr_at_value_bid", "irr_unlevered_at_value_bid"]
FLAGS = ["tier", "refinanceable_by_sale", "clears_hurdle_at_value", "cap_method"]

needs_data = pytest.mark.skipif(not (DATA / "uw.json").exists(), reason="site data not exported")


def _py_loan(row: dict) -> dict:
    L = dict(row)
    L["valuation"] = pd.Timestamp(row["valuation"]).date()
    L["rent_cap"] = math.inf if row["rent_cap"] is None else row["rent_cap"]
    for k in ("tax_rate", "tax_current", "spread_sec", "bench_today"):
        L[k] = float("nan") if row[k] is None else row[k]
    L["high_tax_metro"] = bool(row["high_tax_metro"])
    return L


@needs_data
@pytest.mark.skipif(NODE is None, reason="node not installed")
def test_javascript_engine_matches_python_for_50_random_loans(tmp_path):
    uw = json.loads((DATA / "uw.json").read_text(encoding="utf-8"))["loans"]
    n = len(uw["whole_loan_id"])
    rng = np.random.default_rng(2026)
    idx = rng.choice(n, size=50, replace=False)
    P, M = engine.load_params(), engine.load_market()
    scen = list(P["scenarios"])
    cases, expected = [], []
    for j, i in enumerate(idx):
        row = {k: uw[k][int(i)] for k in uw}
        s = scen[j % 3]
        rs, cs = [(0, 0), (100, 0), (-50, 50), (200, -100), (0, 100)][j % 5]
        cases.append({"L": row, "scenario": s, "rate_shift_bps": rs, "cap_shift_bps": cs})
        expected.append(engine.underwrite(_py_loan(row), P["scenarios"][s], P, M, rate_shift_bps=rs,
                                          cap_shift_bps=cs))
    (tmp_path / "cases.json").write_text(json.dumps(cases))
    subprocess.run([NODE, str(paths.REPO_ROOT / "site" / "scripts" / "parity.mjs"), str(tmp_path / "cases.json"),
                    str(DATA / "scenarios.json"), str(tmp_path / "out.json")], check=True)
    got = json.loads((tmp_path / "out.json").read_text())
    compared = 0
    for c, py, js in zip(cases, expected, got):
        lid = c["L"]["whole_loan_id"]
        for k in DOLLARS + RATES + FLAGS:
            a, b = py.get(k), js.get(k)
            if isinstance(a, float) and math.isnan(a):
                a = None
            if a is None or b is None:
                assert a is None and b is None, (lid, k, a, b)
                continue
            if k in DOLLARS:
                assert abs(a - b) < 0.005, (lid, k, a, b)
            elif k in RATES:
                assert abs(a - b) <= 1e-9 * max(1.0, abs(a)), (lid, k, a, b)
            else:
                assert a == b, (lid, k, a, b)
            compared += 1
    assert compared > 1000
    assert sum(r.get("return_bid") is not None for r in got) >= 25   # most cases exercise the cash-flow model


# ------------------------------------------------------------------ chart numbers reconcile to the output tables

def _json(name):
    return json.loads((DATA / name).read_text(encoding="utf-8"))


@needs_data
def test_headline_and_chart_numbers_reconcile_to_output_tables():
    s = _json("summary.json")
    u = pd.read_parquet(paths.OUTPUT_DIR / "underwriting.parquet")
    sc = pd.read_parquet(paths.OUTPUT_DIR / "scores.parquet")
    base = u[u["scenario"].eq("base")]
    h = s["headline"]
    assert h["loans_scored"] == len(sc)
    assert h["gap_base"] == pytest.approx(base["refi_gap"].sum(), abs=1)
    assert h["gap_downside"] == pytest.approx(u.loc[u["scenario"].eq("downside"), "refi_gap"].sum(), abs=1)
    assert h["loans_with_gap"] == int((base["refi_gap_pct"] > 0).sum())
    assert h["bid_below_balance"] == int((base["refinanceable_by_sale"] == False).sum())  # noqa: E712
    # the wall: every bucket's balance and gap recomputed from the scores and the base scenario
    w = s["wall"]
    D = pd.Timestamp(engine.load_market()["date"])
    m = sc.merge(base[["whole_loan_id", "refi_gap"]], on="whole_loan_id", how="left")
    bucket = np.where(m["maturity_eff"] < D, "past due", m["maturity_eff"].dt.year.astype("Int64").astype(str))
    for i, b in enumerate(w["buckets"]):
        sel = bucket == b
        assert sum(w["balance"][t][i] for t in w["types"]) == pytest.approx(m.loc[sel, "wl_balance_est"].sum(), rel=1e-9, abs=2)
        assert w["gap"][i] == pytest.approx(m.loc[sel, "refi_gap"].fillna(0).sum(), abs=2)
    # gap by type and scenario totals
    for r in s["gap_by_type"]:
        types = ["mixed_use", "other"] if r["type"] == "mixed_other" else [r["type"]]
        g = base[base["property_group"].isin(types)]
        assert r["gap"] == pytest.approx(g["refi_gap"].sum(), abs=2), r["type"]
    for k, v in s["scenario_gap"]["scenarios"].items():
        assert v["gap"] == pytest.approx(u.loc[u["scenario"].eq(k), "refi_gap"].sum(), abs=2)


@needs_data
def test_loan_table_sample_matches_outputs():
    L = _json("loans.json")["loans"]
    u = pd.read_parquet(paths.OUTPUT_DIR / "underwriting.parquet")
    base = u[u["scenario"].eq("base")].set_index("whole_loan_id")
    sc = pd.read_parquet(paths.OUTPUT_DIR / "scores.parquet").set_index("whole_loan_id")
    rng = np.random.default_rng(5)
    for i in rng.choice(len(L["id"]), size=200, replace=False):
        lid = L["id"][i]
        b = sc.loc[lid, "wl_balance_est"]
        assert (L["bal"][i] is None) == bool(pd.isna(b)), lid
        if L["bal"][i] is not None:
            assert L["bal"][i] == pytest.approx(b, abs=1)
        for col, src, tol in (("gap", "refi_gap", 1), ("bid", "bid", 1), ("value", "value", 1)):
            v = base.loc[lid, src] if lid in base.index else float("nan")
            assert (L[col][i] is None) == bool(pd.isna(v)), (lid, col)
            if L[col][i] is not None:
                assert L[col][i] == pytest.approx(v, abs=tol), (lid, col)
        p = sc.loc[lid, "p_distress_12m"]
        if not pd.isna(p):
            assert L["pd"][i] == pytest.approx(p, abs=1e-5)


@needs_data
def test_los_angeles_numbers_reconcile():
    la = _json("la.json")
    loans = _json("loans.json")["loans"]
    ids = {i for i, c in zip(loans["id"], loans["county"]) if c in ("06037", "06059")}
    assert la["market"]["loans"] == len(ids)
    u = pd.read_parquet(paths.OUTPUT_DIR / "underwriting.parquet")
    for k, v in la["market"]["scenarios"].items():
        g = u[u["scenario"].eq(k) & u["whole_loan_id"].isin(ids)]
        assert v["gap"] == pytest.approx(g["refi_gap"].sum(), abs=2)


@needs_data
def test_every_sec_link_points_to_a_downloaded_filing():
    """The tear sheets link each filing's EDGAR index page from the trust's CIK and the accession number; both must
    match a filing the pipeline downloaded (EDGAR itself refuses scripted requests without a declared contact)."""
    import glob

    filings = pd.read_parquet(paths.META_DIR / "filings.parquet", columns=["trust_cik", "accession"])
    known = set(zip(filings["trust_cik"].astype(int), filings["accession"]))
    n = 0
    for f in glob.glob(str(DATA / "history" / "*.json")):
        for lid, rec in json.loads(open(f, encoding="utf-8").read())["loans"].items():
            for acc in rec["series"]["accession"]:
                assert (int(rec["cik"]), acc) in known, (lid, acc)
                n += 1
    assert n > 500_000
