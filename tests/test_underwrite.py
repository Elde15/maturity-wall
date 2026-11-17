"""Gate 4: the underwriting engine against the Excel hand check, edge cases, and its cited parameters."""
import csv
import math
from datetime import date
from statistics import median

import pandas as pd
import pytest

from mwall.common import paths
from mwall.underwrite import engine, handcheck

P = engine.load_params()
M = {"ust10": 0.045, "ust5": 0.042, "spread_bps": {"commercial": 190.0, "multifamily": 160.0}}
CFG = paths.CONFIG_DIR


def _loan(**kw) -> dict:
    row = {"whole_loan_id": "WLtest", "property_group": "multifamily", "wl_balance_est": 20e6, "noi": 2.0e6,
           "revenue": 3.5e6, "occupancy": 0.95, "sqft": None, "units": 200, "noi_sec": 1.8e6, "val_sec": 30e6,
           "val_sec_date": pd.Timestamp("2018-03-01"), "cap_bench_today": 0.055, "cap_bench_sec": 0.050,
           "cap_composite_today": 0.07, "cap_composite_sec": 0.065, "noi_age_months": 4.0, "fin_months": 12.0,
           "flag_fin_basis_unknown": False, "n_properties": 1, "place_geoid": None, "place_source": None,
           "county_fips": "48201", "year_built": 1990, "mf_rent_growth_metro": None, "high_tax_metro": False,
           "valuation_date": pd.Timestamp("2026-11-12"), "prop_state": "TX"}
    for i in (1, 2, 3):
        row[f"tenant{i}_sqft"], row[f"tenant{i}_lease_exp"] = None, None
    row.update(kw)
    return engine.prepare(pd.DataFrame([row]), P)[0]


def _run(L, scen="base", **kw):
    return engine.underwrite(L, P["scenarios"][scen], P, M, **kw)


# ------------------------------------------------------------------ small pieces

def test_loan_constant_and_irr():
    assert engine.loan_constant(0.06, 30) == pytest.approx(0.0719461, abs=1e-7)
    assert engine.loan_constant(0.06, 0) == 0.06
    assert engine.irr([-100, 110]) == pytest.approx(0.10, abs=1e-10)
    assert engine.irr([-100, 0, 121]) == pytest.approx(0.10, abs=1e-10)
    assert math.isnan(engine.irr([100, 50]))


def test_rollover_year():
    D = date(2026, 11, 12)
    assert engine.rollover_year(date(2025, 1, 31), D) == 1        # expired: holdover, rolls now
    assert engine.rollover_year(date(2027, 11, 12), D) == 1
    assert engine.rollover_year(date(2027, 11, 13), D) == 2
    assert engine.rollover_year(date(2031, 11, 12), D) == 5
    assert engine.rollover_year(date(2031, 11, 13), D) is None
    assert engine.rollover_year(None, D) is None
    assert engine.add_years(date(2028, 2, 29), 1) == date(2029, 2, 28)


def test_ula_thresholds_index_and_tax_the_whole_price():
    assert engine.ula_indexations(date(2027, 6, 30)) == 0
    assert engine.ula_indexations(date(2027, 7, 1)) == 1
    assert engine.ula_indexations(date(2031, 11, 12)) == 5
    D0 = date(2027, 1, 1)                                        # no indexation yet: $5.4M / $10.9M
    assert engine.local_transfer_rate("la_city", 5_400_000, D0, P) == 0.0
    assert engine.local_transfer_rate("la_city", 5_400_001, D0, P) == pytest.approx(0.04)
    assert engine.local_transfer_rate("la_city", 10_899_999, D0, P) == pytest.approx(0.04)
    assert engine.local_transfer_rate("la_city", 10_900_000, D0, P) == pytest.approx(0.055)
    D5 = date(2031, 11, 12)                                      # five indexations at 2.6%
    lo5 = 5_400_000 * 1.026 ** 5
    assert engine.local_transfer_rate("la_city", lo5 - 1, D5, P) == 0.0
    assert engine.local_transfer_rate("la_city", lo5 + 1, D5, P) == pytest.approx(0.04)
    assert engine.local_transfer_rate("santa_monica", 8_000_000, D0, P) == pytest.approx(0.053)
    assert engine.local_transfer_rate("santa_monica", 4_999_999, D0, P) == 0.0
    assert engine.local_transfer_rate("culver_city", 3_000_000, D0, P) == pytest.approx(0.0255)
    assert engine.local_transfer_rate("other", 50_000_000, D0, P) == 0.0


def test_prop13_value_is_the_fixed_point():
    L = _loan(property_group="office", sqft=100_000, units=None, county_fips="06037", place_geoid="0644000",
              place_source="census_geocoder")
    assert L["jurisdiction"] == "la_city" and L["tax_rate"] == pytest.approx(0.01179)
    r = _run(L)
    V, c = r["value"], r["cap_rate"]
    yrs = (date(2026, 11, 12) - date(2018, 3, 1)).days / 365.25
    assert L["tax_current"] == pytest.approx(0.01179 * 30e6 * 1.02 ** yrs)     # tax on the factored base
    # today's value (NOI / c, about $30.8M) is below the factored base (about $35M), so Proposition 8 caps the seller's
    # tax at the tax on today's value, and the buyer's tax change nets to zero
    assert r["noi_stressed"] / c < 30e6 * 1.02 ** yrs
    assert V == pytest.approx(r["noi_stressed"] / c)
    assert r["seller_tax"] == pytest.approx(0.01179 * r["noi_stressed"] / c)
    # a property worth more than its factored base: the buyer pays more tax than the seller, so value is lower
    up = _run(_loan(property_group="office", sqft=100_000, units=None, county_fips="06037", place_geoid="0644000",
                    place_source="census_geocoder", noi=4.0e6))
    T = 0.01179 * 30e6 * 1.02 ** yrs
    assert up["seller_tax"] == pytest.approx(T)
    assert up["value"] * up["cap_rate"] == pytest.approx(up["noi_stressed"] + T - 0.01179 * up["value"])
    assert up["value"] < up["noi_stressed"] / up["cap_rate"]


# ------------------------------------------------------------------ edge cases (SOP 15, Gate 4)

def test_missing_noi_is_not_underwritten():
    L = _loan(noi=None)
    r = _run(L)
    assert L["tier"] is None and L["tier_reason"] == "no current NOI"
    assert "value" not in r and "bid" not in r and "refi_gap" not in r


def test_zero_or_negative_noi_has_a_full_gap_and_no_bid():
    for noi in (0.0, -250_000.0):
        L = _loan(noi=noi)
        r = _run(L)
        assert L["tier"] is None and L["tier_reason"] == "NOI zero or negative"
        assert r["refi_gap"] == 20e6 and r["refi_gap_pct"] == 1.0 and "bid" not in r


def test_bid_above_balance_is_refinanceable_by_sale():
    r = _run(_loan(wl_balance_est=5e6))
    assert r["bid"] > 5e6 and r["refinanceable_by_sale"] and r["discount"] == 0.0
    r2 = _run(_loan(wl_balance_est=80e6))
    assert not r2["refinanceable_by_sale"] and r2["discount"] == pytest.approx(1 - r2["bid"] / 80e6)


def test_multi_property_loans_skip_listed_tenants_and_local_rules():
    kw = dict(property_group="office", sqft=200_000, units=None, county_fips="06037", place_geoid="0644000",
              place_source="census_geocoder", tenant1_sqft=80_000, tenant1_lease_exp=pd.Timestamp("2027-03-31"))
    single, multi = _loan(**kw), _loan(n_properties=4, **kw)
    assert single["jurisdiction"] == "la_city" and multi["jurisdiction"] == "multi_property"
    assert math.isnan(multi["tax_rate"])
    assert _run(single)["lease_up"] > 0 and _run(multi)["lease_up"] == 0.0


def test_partial_year_and_stale_noi_drop_a_tier():
    assert _loan()["tier"] == "A"
    assert _loan(fin_months=3.0)["tier"] == "B"
    assert _loan(noi_age_months=20.0)["tier"] == "B"
    assert _loan(property_group="office", sqft=1e5, units=None, fin_months=3.0)["tier"] == "C"
    L = _loan(noi_age_months=40.0)
    assert L["tier"] is None and "36 months" in L["tier_reason"]
    assert _loan(units=None)["tier"] == "C"                      # no size measure: no cash-flow model


def test_tier_c_gets_a_value_bid_only():
    L = _loan(property_group="lodging", units=150, sqft=None)
    r = _run(L)
    assert L["tier"] == "C" and L["bench_kind"] == "composite"
    assert r["value_bid"] > 0 and "return_bid" not in r and r["bid"] == pytest.approx(r["value_bid"])


def test_rates_and_cap_rates_move_the_right_way():
    L = _loan(wl_balance_est=26e6)
    base, up = _run(L), _run(L, rate_shift_bps=100)
    assert up["refi_gap"] >= base["refi_gap"] and up["return_bid"] < base["return_bid"]
    wide = _run(L, cap_shift_bps=50)
    assert wide["value"] < base["value"] and wide["value_bid"] < base["value_bid"]
    assert wide["return_bid"] < base["return_bid"]


def test_rent_control_caps_growth_and_blocks_renovation():
    kw = dict(county_fips="06037", place_geoid="0644000", place_source="census_geocoder", mf_rent_growth_metro=0.06)
    rso = _loan(year_built=1965, **kw)
    assert rso["rent_cap"] == pytest.approx(0.03)
    assert _run(rso, "value_add")["renovation_budget"] == 0.0
    free = _loan(year_built=2016, **kw)
    assert free["rent_cap"] == math.inf
    assert _run(free, "value_add")["renovation_budget"] == pytest.approx(19661 * 200)


# ------------------------------------------------------------------ hand check: Excel to the cent

CENT = 0.005
DOLLARS = ["value", "p_ltv", "p_dscr", "p_dy", "p_max", "refi_gap", "lease_up", "value_bid", "exit_price",
           "exit_net", "kink", "return_bid", "equity", "bid"]
SHEET_NAME = {"lease_up": "lease_up", "loan_at_bid": "bid:loan"}


def _sheet_case(v: dict) -> tuple[dict, str]:
    def d(x):
        return x.date() if hasattr(x, "date") else x

    L = {k: v.get(k) for k in ("whole_loan_id", "group", "tier", "jurisdiction", "wl_balance_est", "noi", "revenue",
                               "occupancy", "sqft", "units", "mf_rent_growth_metro", "bench_today")}
    L.update(valuation=d(v["valuation"]), tier_reason="", bench_kind="", high_tax_metro=bool(v["high_tax_metro"]),
             rent_cap=math.inf if v["rent_cap"] == 1 else v["rent_cap"])
    raw = v["noi_sec"] / v["val_sec"] - v["bench_sec"]
    L["spread_sec"] = engine.clip_spread(raw, v["spread_lo"], v["spread_hi"])
    if v["tax_rate"]:
        L["tax_rate"] = v["tax_rate"]
        L["tax_current"] = engine.seller_tax(v["tax_rate"], v["val_sec"], d(v["val_sec_date"]), L["valuation"],
                                             v["la:prop13_growth"] / 100)
    else:
        L["tax_rate"] = L["tax_current"] = float("nan")
    for i in (1, 2, 3):
        cells = v[f"tenant{i}@row"]
        L[f"tenant{i}_sqft"], L[f"tenant{i}_lease_exp"] = cells[0], d(cells[1]) if cells[1] else None
    return L, v["scenario"]


@pytest.fixture(scope="module")
def book():
    if not handcheck.BOOK.exists():
        pytest.skip("hand-check workbook not built")
    return handcheck.read()


def test_handcheck_workbook_carries_no_personal_metadata(book):
    import re
    import zipfile

    core = zipfile.ZipFile(handcheck.BOOK).read("docProps/core.xml").decode("utf-8")
    for tag in ("dc:creator", "cp:lastModifiedBy"):
        m = re.search(f"<{tag}>(.*?)</{tag}>", core)
        assert m is None or m.group(1) == "mwall", (tag, "author metadata must be scrubbed")
    for name in zipfile.ZipFile(handcheck.BOOK).namelist():
        assert "absPath" not in zipfile.ZipFile(handcheck.BOOK).read(name).decode("utf-8", "replace"), name


def test_handcheck_parameters_match_config(book):
    for name, v in book.items():
        g = v["group"]
        S = P["scenarios"][v["scenario"]]
        for p in ("noi_growth", "renewal_prob", "downtime_months", "ti_lc_new_psf", "ti_lc_renewal_psf",
                  "lease_term_years", "reserve", "bridge_spread_bps", "ltc", "ltv_asis"):
            assert v["param:" + p] == (engine.par(P, p, g) or 0), (name, p)
        assert v["param:hurdle"] == engine.par(P, S["hurdle_param"], "all")
        lp = P["lender"][(S["refi_lender_set"], g)]
        for p in ("ltv_max", "dscr_min", "dy_min", "amort_years", "spread_premium_bps"):
            assert v[p] == lp[p], (name, p)


@pytest.mark.parametrize("case", [c for c, _ in handcheck.CASES])
def test_engine_matches_the_excel_hand_check(book, case):
    v = book[case]
    L, scen = _sheet_case(v)
    Mx = {"ust10": v["ust10"], "ust5": v["ust5"],
          "spread_bps": {"commercial": v["cbre_spread_bps"], "multifamily": v["cbre_spread_bps"]}}
    r = engine.underwrite(L, P["scenarios"][scen], P, Mx, keep_flows=True)
    assert r["cap_rate"] == pytest.approx(v["cap_rate"], abs=1e-14)
    assert r["noi_stressed"] == pytest.approx(v["noi_stressed"], abs=CENT)
    for k in DOLLARS:
        assert abs(r[k] - v[k]) < CENT, (case, k, r[k], v[k])
    assert abs(r["reserve_y1"] - v["reserve"]) < CENT
    assert abs(r["loan_at_bid"] - v["bid:loan"]) < CENT
    noi_row = v["bid:noi@row"][1:6]
    for t in range(5):
        assert abs(r["flows"]["noi"][t] - noi_row[t]) < CENT, (case, "noi", t)
    lev_row, unlev_row = v["bid:levered@row"][0:6], v["bid:unlevered@row"][0:6]
    for t in range(6):
        assert abs(r["flows"]["lev"][t] - lev_row[t]) < CENT, (case, "levered", t)
        assert abs(r["flows"]["unlev"][t] - unlev_row[t]) < CENT, (case, "unlevered", t)
    for k in ("irr_levered", "irr_unlevered"):
        assert r[k] == pytest.approx(v[k], abs=1e-7), (case, k)
    assert r["irr_levered"] == pytest.approx(v["param:hurdle"] / 100, abs=1e-7)
    for k in ("equity_multiple", "cash_on_cash", "dscr_y1", "dy_y1", "breakeven_occ", "discount", "refi_rate",
              "loan_constant", "acq_rate", "exit_cap"):
        assert r[k] == pytest.approx(v[k], rel=1e-12, abs=1e-12), (case, k)


# ------------------------------------------------------------------ every parameter cites a source and a date

def _rows(name):
    with open(CFG / "research" / name, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def test_every_parameter_has_a_source_and_check_date():
    research = {"underwriting_sources.csv": _rows("underwriting_sources.csv"),
                "la_rules_sources.csv": _rows("la_rules_sources.csv")}
    for fname in ("underwriting_params.csv", "la_overrides.csv"):
        for r in csv.DictReader(open(CFG / fname, encoding="utf-8", newline="")):
            assert r["sources"].strip() and r["checked"] == "2026-11-16", (fname, r)
            current = None
            for ref in r["sources"].split(";"):
                if ":" in ref:
                    current, ref = ref.split(":", 1)
                if current in research and ref.isdigit():  # "file.csv:12;13" cites rows 12 and 13 of file.csv
                    assert 1 <= int(ref) <= len(research[current]), (fname, current, ref)


def test_derived_parameters_recompute_from_their_sources():
    u = _rows("underwriting_sources.csv")
    val = lambda n: float(u[n - 1]["value_low"])  # noqa: E731
    cfg = {(r["parameter"], r["property_group"]): r for r in csv.DictReader(open(CFG / "underwriting_params.csv", encoding="utf-8"))}
    for (p, g), r in cfg.items():
        if p == "noi_haircut_downside":
            rows = [int(x) for x in r["sources"].split(":")[1].split(";")]
            assert float(r["value"]) == pytest.approx(median(val(n) for n in rows)), g
    assert float(cfg[("ti_lc_new_psf", "retail")]["value"]) == pytest.approx(10.61 + 7.88)
    assert float(cfg[("ti_lc_renewal_psf", "retail")]["value"]) == pytest.approx(1.08 + 0.11)
    assert float(cfg[("lease_term_years", "retail")]["value"]) == pytest.approx(
        (10.7 * 2_853_327 + 7.0 * 2_815_490) / (2_853_327 + 2_815_490), abs=0.005)
    assert float(cfg[("lease_term_years", "industrial")]["value"]) == pytest.approx(
        (5.5 * 3_404_696 + 4.8 * 14_376_660) / (3_404_696 + 14_376_660), abs=0.005)
    for n, quote_bit in ((107, "10.7"), (108, "7.0"), (111, "5.5"), (113, "4.8"), (261, "6.7 years")):
        assert quote_bit in u[n - 1]["quote"], n
    assert (5.4 / 5.0) ** (1 / 3) - 1 == pytest.approx(0.026, abs=0.0005)
