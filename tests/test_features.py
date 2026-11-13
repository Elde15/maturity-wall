"""Hand-built examples for every feature family (SOP section 9 acceptance)."""
import numpy as np
import pandas as pd
import pytest

from mwall.features import loan, market
from mwall.features.catalog import BY_NAME, CATALOG, OUTCOME_FIELDS


def _row(**kw):
    base = dict(
        root_key="1:1", snapshot_date=pd.Timestamp("2023-03-27"), period_end=pd.Timestamp("2023-03-10"),
        noi=900_000.0, ncf=850_000.0, revenue=2_000_000.0, opex=1_100_000.0, noi_sec=1_000_000.0,
        fin_end=pd.Timestamp("2022-12-31"), wl_balance=10_000_000.0, balance=5_000_000.0,
        dscr_noi_reported=1.40, dscr_noi_recomputed=1.41, flag_dscr_inconsistent=False, noi_age_months=2.9,
        val_securitization=15_000_000.0, val_securitization_date=pd.Timestamp("2016-10-01"),
        val_recent=12_000_000.0, val_recent_date=pd.Timestamp("2022-06-01"),
        occupancy=0.85, occupancy_sec=0.95,
        tenant1_sqft=40_000.0, tenant1_lease_exp=pd.Timestamp("2024-01-31"),
        tenant2_sqft=20_000.0, tenant2_lease_exp=pd.Timestamp("2027-06-30"),
        tenant3_sqft=10_000.0, tenant3_lease_exp=pd.Timestamp("2022-12-31"),
        largest_sqft=100_000.0, sqft=100_000.0, units=np.nan,
        maturity_date=pd.Timestamp("2026-11-06"), maturity0=pd.Timestamp("2026-11-06"),
        origination_date=pd.Timestamp("2016-11-06"), term_months=120.0, coupon=0.045, coupon_orig=0.045,
        io_months=60.0, amort_months=360.0, trust_share=0.5, wl_balance_method="debt_service_share",
        structure_code="PP", n_notes_in_trust=2, n_properties=1.0,
        year_built=1985, year_renovated=2015, property_group="office", prop_type_code="OF", ev_modification=False,
        ss_transfer_date=pd.NaT, in_special_servicing=False, adv_pi=0.0, adv_ti=1_000.0, adv_other=0.0,
    )
    base.update(kw)
    return base


def _frame(*rows):
    return pd.DataFrame([_row(**r) for r in rows])


def test_loan_constant_matches_a_mortgage_table():
    # $100,000 at 6% over 30 years pays $599.55 a month
    assert loan.loan_constant(0.06, 30) == pytest.approx(12 * 599.55 / 100_000, abs=1e-6)
    assert loan.loan_constant(0.06, 0) == pytest.approx(0.06)       # interest only
    assert loan.loan_constant(0.0, 25) == pytest.approx(1 / 25)


def test_balloon_share():
    # 10-year term on a 30-year schedule at 6%: 83.69% of the loan is left at maturity
    assert loan.balloon_share(0.06, 360, 0, 120) == pytest.approx(0.836857, abs=1e-5)
    # five years interest-only first leaves more
    assert loan.balloon_share(0.06, 360, 60, 120) == pytest.approx(0.930543, abs=1e-5)
    assert loan.balloon_share(0.06, 360, 120, 120) == 1.0           # full-term IO
    assert loan.balloon_share(0.06, 0, 0, 120) == 1.0               # no amortization
    assert loan.balloon_share(0.0, 360, 0, 120) == pytest.approx(2 / 3)


def test_rollover_counts_leases_ending_within_24_months_and_past_due_ones():
    d = _frame({})
    # 40k ends 2024-01 (inside), 20k ends 2027-06 (outside), 10k already ended 2022-12 (counts)
    assert loan.rollover_share(d, d["snapshot_date"]).iloc[0] == pytest.approx(50 / 70)


def test_leverage_coverage_and_trend_features():
    f = loan.compute(_frame({}))
    r = f.iloc[0]
    assert r["f_debt_yield_noi"] == pytest.approx(0.09)              # 900k / 10M whole loan, not the 5M piece
    assert r["f_debt_yield_ncf"] == pytest.approx(0.085)
    assert r["f_ltv_securitization"] == pytest.approx(10 / 15)
    assert r["f_ltv_recent"] == pytest.approx(10 / 12)
    assert bool(r["f_reappraised"])
    assert r["f_noi_vs_securitization"] == pytest.approx(-0.1)
    assert r["f_expense_ratio"] == pytest.approx(0.55)
    assert r["f_occupancy_change"] == pytest.approx(-0.10)
    assert r["f_tenant1_share"] == pytest.approx(0.4)
    assert not bool(r["f_noi_missing"])


def test_valuation_dated_after_the_snapshot_is_not_used():
    f = loan.compute(_frame({"val_recent_date": pd.Timestamp("2023-05-01")}))
    assert np.isnan(f.loc[0, "f_ltv_recent"]) and not bool(f.loc[0, "f_reappraised"])


def test_loan_terms_and_property_features():
    r = loan.compute(_frame({})).iloc[0]
    assert r["f_months_to_maturity"] == pytest.approx((pd.Timestamp("2026-11-06") - pd.Timestamp("2023-03-10")).days
                                                      / 30.4375)
    assert r["f_seasoning_months"] == pytest.approx(76.1, abs=0.1)
    assert r["f_io_remaining_months"] == 0                          # IO ended in late 2021
    assert not bool(r["f_full_term_io"]) and not bool(r["f_extended"])
    assert bool(r["f_pari_passu_piece"]) and r["f_trust_share"] == 0.5 and bool(r["f_single_asset"])
    assert bool(r["f_debt_outside_trust"]) and not bool(r["f_ab_structure"])
    wl = loan.compute(_frame({"trust_share": np.nan, "wl_balance_method": "trust_holds_whole_loan",
                              "structure_code": "WL"})).iloc[0]
    assert wl["f_trust_share"] == 1.0 and not bool(wl["f_pari_passu_piece"]) and not bool(wl["f_debt_outside_trust"])
    ab = loan.compute(_frame({"trust_share": np.nan, "wl_balance_method": "unknown", "structure_code": "A1"})).iloc[0]
    assert np.isnan(ab["f_trust_share"]) and bool(ab["f_ab_structure"]) and bool(ab["f_debt_outside_trust"])
    assert r["f_property_age_years"] == 38 and r["f_years_since_renovation"] == 8
    assert r["f_balance_per_sqft"] == pytest.approx(100.0) and np.isnan(r["f_balance_per_unit"])
    mf = loan.compute(_frame({"property_group": "multifamily", "units": 200.0})).iloc[0]
    assert mf["f_balance_per_unit"] == pytest.approx(50_000) and np.isnan(mf["f_balance_per_sqft"])
    assert not bool(mf["f_cooperative"])
    assert bool(loan.compute(_frame({"property_group": "multifamily", "prop_type_code": "CH"})).loc[0, "f_cooperative"])
    ext = loan.compute(_frame({"maturity_date": pd.Timestamp("2027-11-06")})).iloc[0]
    assert bool(ext["f_extended"])


def test_servicing_history_only_looks_back():
    d = _frame({"period_end": pd.Timestamp("2023-01-10"), "snapshot_date": pd.Timestamp("2023-01-27")},
               {"period_end": pd.Timestamp("2023-02-10"), "snapshot_date": pd.Timestamp("2023-02-27"),
                "ev_modification": True, "ss_transfer_date": pd.Timestamp("2023-02-01"),
                "in_special_servicing": True, "adv_pi": 50_000.0},
               {"period_end": pd.Timestamp("2023-03-10"), "snapshot_date": pd.Timestamp("2023-03-27")})
    f = loan.compute(d)
    assert f["f_ever_modified"].tolist() == [False, True, True]
    assert f["f_ever_special_serviced"].tolist() == [False, True, True]
    assert f["f_advances_pi"].tolist() == [False, True, False]
    assert f.loc[1, "f_advances_pct"] == pytest.approx(51_000 / 5_000_000)


def test_noi_yoy_uses_the_first_report_of_the_earlier_period_and_never_a_later_filing():
    d = _frame(
        {"snapshot_date": pd.Timestamp("2022-03-27"), "fin_end": pd.Timestamp("2021-12-31"), "noi": 100.0},
        {"snapshot_date": pd.Timestamp("2022-06-27"), "fin_end": pd.Timestamp("2021-12-31"), "noi": 90.0},
        {"snapshot_date": pd.Timestamp("2023-03-27"), "fin_end": pd.Timestamp("2022-12-31"), "noi": 110.0},
    )
    y = loan.noi_yoy(d)
    assert y.iloc[2] == pytest.approx(0.10) and np.isnan(y.iloc[0])
    # if the earlier period had only been reported after T, there is no comparison
    late = _frame(
        {"snapshot_date": pd.Timestamp("2023-06-27"), "fin_end": pd.Timestamp("2021-12-31"), "noi": 100.0},
        {"snapshot_date": pd.Timestamp("2023-03-27"), "fin_end": pd.Timestamp("2022-12-31"), "noi": 110.0},
    )
    assert np.isnan(loan.noi_yoy(late).iloc[1])


def test_asof_takes_the_latest_value_published_on_or_before_the_snapshot():
    left = pd.DataFrame({"cbsa_code": ["31080", "31080", "35620"],
                         "snapshot_date": pd.to_datetime(["2024-02-27", "2024-03-01", "2024-03-01"])})
    right = pd.DataFrame({"cbsa_code": ["31080", "31080", "35620"],
                          "available": pd.to_datetime(["2024-01-31", "2024-02-29", "2024-03-02"]),
                          "x": [1.0, 2.0, 3.0]})
    out = market.asof(left, right, ["x"], by="cbsa_code")
    assert out["x"].tolist()[:2] == [1.0, 2.0] and np.isnan(out["x"].iloc[2])
    assert (out["asof"].dropna() <= out.loc[out["asof"].notna(), "snapshot_date"]).all()


def test_zillow_names_map_to_cbsa_by_first_city_and_state():
    cb = pd.DataFrame({"cbsa_code": ["31080", "35620", "14460"],
                       "cbsa_title": ["Los Angeles-Long Beach-Anaheim, CA", "New York-Newark-Jersey City, NY-NJ",
                                      "Boston-Cambridge-Newton, MA-NH"]})
    m = market.zillow_metro_map(cb, pd.Series(["Los Angeles, CA", "New York, NY", "Boston, MA", "Austin, TX"]))
    assert dict(zip(m["zname"], m["cbsa_code"])) == {"Los Angeles, CA": "31080", "New York, NY": "35620",
                                                     "Boston, MA": "14460"}


def test_qcew_area_code():
    assert market.qcew_area(pd.Series(["31080", "35620"])).tolist() == ["C3108", "C3562"]


def test_catalog_inputs_never_include_outcome_fields():
    assert len(BY_NAME) == len(CATALOG)
    for ft in CATALOG:
        assert not set(ft.inputs) & OUTCOME_FIELDS, ft.name


def test_qcew_unpublished_and_suppressed_rows_are_missing_not_zero(tmp_path, monkeypatch):
    monkeypatch.setattr(market, "MKT_DIR", tmp_path)
    (tmp_path / "qcew").mkdir()
    head = '"area_fips","own_code","industry_code","agglvl_code","size_code","year","qtr","disclosure_code","month3_emplvl"'
    rows = {"10": [("C3108", "0", "2024", "3", "", "100"), ("C3108", "0", "2025", "3", "", "103")],
            "1022": [("C3108", "5", "2024", "3", "", "10"), ("C3108", "5", "2025", "3", "-", "0")],
            "1023": [("C3108", "5", "2024", "3", "", "20"), ("C3108", "5", "2025", "3", "-", "0")],
            "1024": [("C3108", "5", "2024", "3", "", "30"), ("C3108", "5", "2025", "3", "N", "0")]}
    for q in ("2024q3", "2025q3"):
        for ind, rs in rows.items():
            body = [head] + [",".join(f'"{x}"' for x in (a, o, ind, "40", "0", y, qt, dc, e))
                             for a, o, y, qt, dc, e in rs if y == q[:4]]
            (tmp_path / "qcew" / f"{q}_{ind}.csv").write_text("\n".join(body) + "\n")
    out = market.qcew().set_index("quarter_end")
    r = out.loc[pd.Timestamp("2025-09-30")]
    assert r["emp_total_yoy"] == pytest.approx(0.03) and np.isnan(r["emp_office"]) and np.isnan(r["emp_office_yoy"])
    assert out.loc[pd.Timestamp("2024-09-30"), "emp_office"] == 60
    assert r["available"] == pd.Timestamp("2026-03-31")


def test_zori_growth_needs_the_month_a_year_earlier(tmp_path, monkeypatch):
    monkeypatch.setattr(market, "MKT_DIR", tmp_path)
    (tmp_path / "zillow").mkdir()
    months = [d.strftime("%Y-%m-%d") for d in pd.date_range("2023-01-31", periods=14, freq="ME")]
    vals = [100.0 + i for i in range(14)]
    vals[12] = np.nan  # a missing month leaves its 12-month change empty
    line = ",".join(["1", "0", '"Los Angeles, CA"', "msa", "CA", *["" if np.isnan(v) else str(v) for v in vals]])
    for name in market.ZORI:
        (tmp_path / "zillow" / f"{name}.csv").write_text(
            ",".join(["RegionID", "SizeRank", "RegionName", "RegionType", "StateName", *months]) + "\n" + line + "\n")
    cb = pd.DataFrame({"cbsa_code": ["31080"], "cbsa_title": ["Los Angeles-Long Beach-Anaheim, CA"]})
    z = market.zori(cb).set_index("month")
    assert z.loc[pd.Timestamp("2024-02-29"), "zori_all_yoy"] == pytest.approx(113 / 101 - 1)
    assert np.isnan(z.loc[pd.Timestamp("2024-01-31"), "zori_all_yoy"])
    assert z.loc[pd.Timestamp("2024-02-29"), "available"] == pd.Timestamp("2024-03-31")


# Golden row: every loan feature of the default hand-built office loan, worked by hand.
# $10M whole loan ($5M trust piece), NOI $900k, NCF $850k, appraised $15M at issue and $12M in June 2022,
# 4.5% coupon, 5 years interest-only then a 30-year schedule, 10-year term, filed 2023-03-27.
GOLDEN = {
    "f_debt_yield_noi": 0.09, "f_debt_yield_ncf": 0.085, "f_dscr_noi_reported": 1.40, "f_dscr_noi_recomputed": 1.41,
    "f_dscr_disagree": False, "f_ltv_securitization": 10 / 15, "f_ltv_recent": 10 / 12, "f_reappraised": True,
    "f_noi_vs_securitization": -0.1, "f_noi_yoy": np.nan, "f_expense_ratio": 0.55, "f_noi_age_months": 2.9,
    "f_noi_missing": False, "f_occupancy": 0.85, "f_occupancy_change": -0.10, "f_tenant1_share": 0.4,
    "f_rollover_24m": 50 / 70, "f_months_to_maturity": 1337 / 30.4375, "f_term_months": 120,
    "f_seasoning_months": 2315 / 30.4375, "f_coupon": 0.045, "f_io_remaining_months": 0.0, "f_full_term_io": False,
    "f_balloon_share": 0.911579, "f_extended": False, "f_trust_share": 0.5, "f_pari_passu_piece": True,
    "f_ab_structure": False, "f_debt_outside_trust": True, "f_n_notes_in_trust": 2, "f_n_properties": 1,
    "f_single_asset": True, "f_cooperative": False, "f_property_age_years": 38, "f_years_since_renovation": 8,
    "f_balance_per_unit": np.nan, "f_balance_per_sqft": 100.0, "f_ever_modified": False,
    "f_ever_special_serviced": False, "f_in_special_servicing": False, "f_advances_pi": False,
    "f_advances_ti": True, "f_advances_other": False, "f_advances_pct": 1_000 / 5_000_000,
}


def test_golden_row_every_loan_feature():
    f = loan.compute(_frame({})).iloc[0]
    assert set(GOLDEN) == {c for c in f.index}, "a loan feature was added without a golden value"
    for name, want in GOLDEN.items():
        got = f[name]
        if isinstance(want, bool):
            assert bool(got) is want, name
        elif np.isnan(want):
            assert pd.isna(got), name
        else:
            assert got == pytest.approx(want, rel=1e-5), name


def _mk():
    tsy = pd.DataFrame({"date": pd.to_datetime(["2016-11-04", "2022-03-25", "2023-03-24"]),
                        "DGS2": [0.8, 2.3, 3.8], "DGS5": [1.3, 2.4, 3.6], "DGS7": [1.6, 2.4, 3.6],
                        "DGS10": [1.8, 2.5, 4.0]})
    tsy["available"] = tsy["date"] + pd.Timedelta(days=1)
    z = pd.DataFrame({"cbsa_code": ["31080"] * 2, "month": pd.to_datetime(["2023-01-31", "2023-02-28"]),
                      "zori_all_yoy": [0.05, 0.04], "zori_mf_yoy": [0.03, 0.02]})
    z["available"] = z["month"] + pd.offsets.MonthEnd(1)
    q = pd.DataFrame({"qcew_area": ["C3108"], "quarter_end": [pd.Timestamp("2022-09-30")],
                      "available": [pd.Timestamp("2023-03-31")], "emp_total_yoy": [0.02], "emp_office_yoy": [0.01]})
    q2 = q.assign(quarter_end=pd.Timestamp("2022-06-30"), available=pd.Timestamp("2022-12-31"),
                  emp_total_yoy=0.03, emp_office_yoy=-0.01)
    pm = pd.DataFrame({"cbsa_code": ["31080"], "month": [pd.Timestamp("2023-01-31")],
                       "available": [pd.Timestamp("2023-03-31")], "permits_per_1k_units": [7.0],
                       "permits_5plus_per_1k_units": [4.0]})
    pm2 = pm.assign(month=pd.Timestamp("2022-12-31"), available=pd.Timestamp("2023-02-28"),
                    permits_per_1k_units=6.5, permits_5plus_per_1k_units=3.5)
    return {"treasury": tsy, "zori": z, "qcew": pd.concat([q, q2]), "permits": pd.concat([pm, pm2])}


def test_market_features_join_as_of_the_snapshot():
    from mwall.features import build

    d = _frame({})
    d["cbsa_code"] = "31080"
    d, f = build.attach_market(d, loan.compute(d), _mk())
    r = f.iloc[0]
    assert r["f_ust10"] == pytest.approx(0.040) and r["f_ust5"] == pytest.approx(0.036)   # 2023-03-24, known 3/25
    assert r["f_ust10_change_12m"] == pytest.approx(0.015)                                # vs 2022-03-25
    assert r["f_curve_10y2y"] == pytest.approx(0.002)
    assert r["f_ust10_change_since_origination"] == pytest.approx(0.022)                  # vs 2016-11-04
    assert r["f_rent_growth_yoy"] == pytest.approx(0.05)    # February is only usable from March 31
    assert r["f_mf_rent_growth_yoy"] == pytest.approx(0.03)
    assert r["f_emp_growth_yoy"] == pytest.approx(0.03)     # Q3 2022 is only usable from March 31, 2023
    assert r["f_office_emp_growth_yoy"] == pytest.approx(-0.01)
    assert r["f_permits_per_1k_units"] == pytest.approx(6.5) and r["f_permits_5plus_per_1k_units"] == pytest.approx(3.5)


def test_refinance_features_on_hand_parameters(tmp_path, monkeypatch):
    from mwall.features import build

    lp = tmp_path / "lender_params.csv"
    lp.write_text("property_group,scenario,ltv_max,dscr_min,dy_min,amort_years,treasury_tenor,spread_series,"
                  "spread_premium_bps\noffice,base,0.65,1.35,0.08,30,10,commercial,40\n"
                  "other,base,0.6,1.4,0.1,25,10,commercial,0\n")
    sp = tmp_path / "lender_spreads.csv"
    # two quarters published the same day: the later quarter wins; a quarter published after T is not used
    sp.write_text("series,as_of_quarter,publication_date,spread_bps\ncommercial,2022Q2,2022-08-15,150\n"
                  "commercial,2022Q3,2022-08-15,160\ncommercial,2023Q1,2023-05-15,250\n")
    monkeypatch.setattr(build, "LENDER_SPREADS", sp)
    cr = tmp_path / "cap_rates.csv"
    cr.write_text("property_group,period_date,publication_date,cap_rate\noffice,2022-06-30,2022-08-15,0.075\n"
                  "office,2023-06-30,2023-08-15,0.09\n")
    monkeypatch.setattr(build, "LENDER_PARAMS", lp)
    monkeypatch.setattr(build, "CAP_RATES", cr)
    d = _frame({})
    d["cbsa_code"] = "31080"
    d, f = build.attach_market(d, loan.compute(d), _mk())
    r = build.attach_refi(d, f, log=lambda m: None).iloc[0]
    # rate 4.00% + 160 bp CBRE (2022Q3, the latest published by T) + 40 bp office premium = 6%; constant 0.0719461
    assert r["f_refi_rate"] == pytest.approx(0.06) and r["f_rate_shock"] == pytest.approx(0.015)
    assert r["f_refi_dscr"] == pytest.approx(1.250937, rel=1e-5)
    assert r["f_refi_dy_cushion"] == pytest.approx(0.01)
    # DSCR sizing binds: $900k / (1.35 x 0.0719461) = $9.27M against a $10M loan
    assert r["f_refi_gap_income"] == pytest.approx(0.0733799, rel=1e-5)
    # the August 2023 survey is not out yet, so 7.5% applies: value $12M, 65% LTV = $7.8M
    assert r["f_cap_rate_benchmark"] == pytest.approx(0.075) and r["f_value_model"] == pytest.approx(12_000_000)
    assert r["f_ltv_model"] == pytest.approx(10 / 12) and r["f_refi_gap"] == pytest.approx(0.22)


def test_geography_joins_the_largest_property_address_to_its_metro():
    from mwall.clean.geography import addr_key
    from mwall.features import build

    d = _frame({}, {"root_key": "1:2"})
    d[["prop_address", "prop_city", "prop_state", "prop_zip"]] = [["1 Main St", "Los Angeles", "CA", "90012"],
                                                                  [None, None, None, None]]
    geo = pd.DataFrame({"addr_key": [addr_key("1 Main St", "Los Angeles", "CA", "90012")],
                        "county_fips": ["06037"], "cbsa_code": ["31080"]})
    out = build.attach_geography(d, geo)
    assert out["cbsa_code"].tolist()[0] == "31080" and pd.isna(out["cbsa_code"].tolist()[1])


def test_every_catalog_feature_has_a_unit_test():
    import pathlib

    src = pathlib.Path(__file__).read_text(encoding="utf-8")
    passthrough = {"property_group", "prop_state", "prop_type_code", "delinquency_bucket"}  # filing fields, Gate 1 tests
    missing = [ft.name for ft in CATALOG if ft.name not in passthrough and f'"{ft.name}"' not in src]
    assert not missing, missing


def test_cap_rate_survey_periods_and_late_publications():
    from mwall.features.caprates import period_date

    assert period_date("H1 2016") == pd.Timestamp("2016-06-30") and period_date("H2 2019") == pd.Timestamp("2019-12-31")
    assert period_date("2021Q3") == pd.Timestamp("2021-09-30") and period_date("2023-01") == pd.Timestamp("2023-01-31")
    assert period_date("2021-12-18") == pd.Timestamp("2021-12-18") and pd.isna(period_date("2017Q1-Q3 (average)"))


def test_cap_rate_benchmark_lapses_two_years_after_its_period(tmp_path, monkeypatch):
    from mwall.features import build

    cr = tmp_path / "cap_rates.csv"
    cr.write_text("property_group,period_date,publication_date,cap_rate\nlodging,2019-12-31,2020-01-31,0.0827\n")
    monkeypatch.setattr(build, "CAP_RATES", cr)
    monkeypatch.setattr(build, "LENDER_PARAMS", tmp_path / "absent.csv")
    d = _frame({"property_group": "lodging", "snapshot_date": pd.Timestamp("2021-06-28")},
               {"property_group": "lodging", "snapshot_date": pd.Timestamp("2022-03-28")})
    f = build.attach_refi(d, loan.compute(d), log=lambda m: None)
    assert f.loc[0, "f_cap_rate_benchmark"] == pytest.approx(0.0827) and np.isnan(f.loc[1, "f_cap_rate_benchmark"])
