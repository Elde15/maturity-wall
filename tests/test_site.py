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
