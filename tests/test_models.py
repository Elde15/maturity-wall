"""Gate 3 model code: windows, metrics, baselines, constrained logistic, scenarios, drivers."""
import json

import numpy as np
import pandas as pd
import pytest
from sklearn.linear_model import LogisticRegression

from mwall.model import fit, frame, logic, maturity, scenario, score
from mwall.model.metrics import calibration_slope_intercept, capture_top


def test_windows_boundaries():
    D = pd.Timestamp(2024, 1, 1)
    pe = pd.Series(pd.to_datetime(["2021-11-17", "2021-11-18", "2022-11-17", "2022-11-18", "2024-01-01",
                                   "2024-12-31", "2025-01-01"]))
    w = frame.windows(D, pe)
    assert w["train"].tolist() == [True, False, False, False, False, False, False]
    assert w["valid"].tolist() == [False, True, True, False, False, False, False]
    assert w["test"].tolist() == [False, False, False, False, True, True, False]
    # the labels of every fitted month are public before the test window starts
    assert pd.Timestamp("2022-11-17") + pd.Timedelta(days=365 + 45) <= D


def test_fold_is_stable_and_spread():
    keys = pd.Series([f"loan{i}" for i in range(5000)])
    a, b = frame.fold_of(keys), frame.fold_of(keys)
    assert (a == b).all()
    assert set(np.unique(a)) == set(range(frame.N_FOLDS))
    assert np.bincount(a).min() > 800


def test_calibration_of_a_calibrated_forecast():
    rng = np.random.default_rng(0)
    p = rng.uniform(0.01, 0.3, 200_000)
    y = rng.binomial(1, p)
    slope, citl = calibration_slope_intercept(y, p)
    assert slope == pytest.approx(1.0, abs=0.05)
    assert citl == pytest.approx(0.0, abs=0.03)
    # an overconfident forecast (log-odds doubled) has slope near 0.5
    z = np.log(p / (1 - p)) * 2
    slope2, _ = calibration_slope_intercept(y, 1 / (1 + np.exp(-z)))
    assert slope2 == pytest.approx(0.5, abs=0.05)


def test_capture_top():
    y = np.array([1, 0, 0, 0, 0, 0, 0, 0, 0, 1])
    p = np.array([0.9, 0.8, 0.7, 0.6, 0.5, 0.4, 0.3, 0.2, 0.1, 0.05])
    assert capture_top(y, p) == 0.5
    w = np.array([300, 1, 1, 1, 1, 1, 1, 1, 1, 100])
    assert capture_top(y, p, w) == pytest.approx(0.75)


def test_bucket_rates_shrink_to_base():
    r = fit._bucket_rates(np.array(["a", "a", "b"]), np.array([1.0, 0.0, 0.0]), np.array(["a", "b", "c"]))
    base = 1 / 3
    assert r == pytest.approx([(1 + base) / 3, base / 2, base])


def test_signed_logistic_matches_sklearn_when_free_and_holds_bounds():
    rng = np.random.default_rng(1)
    Z = rng.normal(size=(5000, 3)).astype(np.float32)
    y = rng.binomial(1, 1 / (1 + np.exp(-(-1 + Z @ np.array([0.8, -0.5, 0.0])))))
    sk = LogisticRegression(C=1.0).fit(Z, y)
    free = fit.SignedLogistic(1.0, [(None, None)] * 3).fit(Z, y)
    assert np.abs(free.coef_ - sk.coef_).max() < 1e-3
    assert free.intercept_[0] == pytest.approx(sk.intercept_[0], abs=1e-3)
    # the second coefficient is truly negative; held to >= 0 it sits on the bound
    held = fit.SignedLogistic(1.0, [(None, None), (0, None), (None, None)]).fit(Z, y)
    assert held.coef_[0, 1] == pytest.approx(0.0, abs=1e-8)
    assert held.coef_[0, 0] > 0.5


def _refi_row(**kw):
    row = {"property_group": "multifamily", "f_refi_rate": 0.06, "f_rate_shock": 0.02, "f_debt_yield_noi": 0.08,
           "f_cap_rate_benchmark": 0.06, "f_refi_gap": 0.1, "f_refi_dscr": 1.0, "f_refi_gap_income": 0.1}
    row.update(kw)
    return pd.DataFrame([row])


def test_shift_refi_hand_example():
    # multifamily base: LTV 75%, DSCR 1.25, DY 9%, 30-year amortization (config/lender_params.csv)
    d = _refi_row()
    base = scenario.shift_refi(d, 0).iloc[0]
    k6 = 12 * (0.06 / 12) / (1 - (1 + 0.06 / 12) ** -360)          # 0.0719461
    assert k6 == pytest.approx(0.0719461, abs=1e-7)
    assert base["f_refi_dscr"] == pytest.approx(0.08 / k6)            # 1.11194
    # income sizing: min(DY / (1.25 k), DY / 0.09) = min(0.88956, 0.88889); value sizing 0.75 * 0.08 / 0.06 = 1.0
    assert base["f_refi_gap_income"] == pytest.approx(1 - 0.08 / 0.09)
    assert base["f_refi_gap"] == pytest.approx(1 - 0.08 / 0.09)
    up = scenario.shift_refi(d, 100).iloc[0]
    k7 = 12 * (0.07 / 12) / (1 - (1 + 0.07 / 12) ** -360)          # 0.0798363
    assert up["f_refi_rate"] == pytest.approx(0.07)
    assert up["f_rate_shock"] == pytest.approx(0.03)
    assert up["f_refi_dscr"] == pytest.approx(0.08 / k7)              # 1.00205
    assert up["f_refi_gap"] == pytest.approx(1 - 0.08 / (1.25 * k7))  # 0.19836


def test_shift_refi_without_value_or_noi():
    d = pd.concat([_refi_row(f_cap_rate_benchmark=np.nan), _refi_row(f_debt_yield_noi=np.nan)], ignore_index=True)
    s = scenario.shift_refi(d, 0)
    assert np.isnan(s.loc[0, "f_refi_gap"]) and s.loc[0, "f_refi_gap_income"] == pytest.approx(1 - 0.08 / 0.09)
    assert np.isnan(s.loc[1, "f_refi_gap"]) and np.isnan(s.loc[1, "f_refi_gap_income"])


def test_noi_shock_moves_every_noi_feature():
    d = _refi_row(f_debt_yield_ncf=0.07, f_dscr_noi_reported=1.3, f_dscr_noi_recomputed=1.3, f_value_model=1e7,
                  f_noi_vs_securitization=-0.1, f_ltv_model=0.9, f_refi_dy_cushion=-0.01)
    lp = scenario.lender_base()
    e = logic.noi_up(d, lp).iloc[0]
    assert e["f_debt_yield_noi"] == pytest.approx(0.088)
    assert e["f_dscr_noi_reported"] == pytest.approx(1.43)
    assert e["f_noi_vs_securitization"] == pytest.approx(0.9 * 1.1 - 1)
    assert e["f_ltv_model"] == pytest.approx(0.9 / 1.1)
    assert e["f_refi_dy_cushion"] == pytest.approx(0.088 - 0.09)
    b = logic.balance_up(d.assign(f_ltv_securitization=0.6, f_ltv_recent=np.nan, f_balance_per_unit=1e5,
                                  f_balance_per_sqft=np.nan), lp).iloc[0]
    assert b["f_debt_yield_noi"] == pytest.approx(0.08 / 1.1)
    assert b["f_ltv_securitization"] == pytest.approx(0.66)
    assert b["f_refi_gap"] > scenario.shift_refi(d, 0, lp).iloc[0]["f_refi_gap"]


def test_horizon_rows_pick_nearest_within_two_months():
    T = pd.DataFrame({"whole_loan_id": ["a", "a", "a", "b"], "h_months": [11.9, 12.5, 6.1, 9.0]})
    r = maturity.horizon_rows(T, 12)
    assert r["h_months"].tolist() == [11.9]       # loan b's nearest snapshot is 3 months off
    assert len(maturity.horizon_rows(T, 3)) == 0


def test_drivers_fold_missing_flags_into_the_feature():
    names = ["f_a", "f_b", "f_a_missing", "property_group=office", "property_group=retail"]
    contrib = np.array([[0.1, -0.5, 0.3, 0.2, 0.0]])
    rows = pd.DataFrame({"f_a": [np.nan], "f_b": [2.0], "property_group": ["office"]})
    out = json.loads(score._drivers(contrib, names, rows)[0])
    assert [o["feature"] for o in out] == ["f_b", "f_a", "property_group"]
    assert out[1]["log_odds"] == pytest.approx(0.4) and out[1]["value"] is None
    assert out[2]["value"] == "office"


def test_credit_signs_cover_the_sop_list():
    for f in ("f_debt_yield_noi", "f_dscr_noi_reported", "f_ltv_model", "f_occupancy", "f_rate_shock"):
        assert f in frame.CREDIT_SIGNS
    assert set(frame.CREDIT_SIGNS) <= set(frame.NUMERIC)
    assert set(maturity.SIGNS) <= set(maturity.FEATURES)
    for name, cols in frame.ABLATIONS.items():
        assert set(cols) <= set(frame.NUMERIC) | set(frame.CATEGORICAL), name


def test_drivers_leave_out_market_wide_series():
    names = ["f_ust10", "f_a", "f_b", "f_c"]
    contrib = np.array([[2.0, 0.1, -0.3, 0.2]])
    rows = pd.DataFrame({"f_ust10": [4.1], "f_a": [1.0], "f_b": [2.0], "f_c": [3.0]})
    out = json.loads(score._drivers(contrib, names, rows)[0])
    assert [o["feature"] for o in out] == ["f_b", "f_c", "f_a"]


def test_driver_contributions_add_by_name_across_folds():
    # two folds whose missing flags differ: summing by name keeps every column
    a = pd.DataFrame([[0.1, 0.2]], columns=["f_a", "f_a_missing"])
    b = pd.DataFrame([[0.3, 0.4]], columns=["f_a", "f_b"])
    tot = a.add(b, fill_value=0.0)
    assert tot.loc[0, "f_a"] == pytest.approx(0.4) and tot.loc[0, "f_b"] == pytest.approx(0.4)
    assert tot.loc[0, "f_a_missing"] == pytest.approx(0.2)
