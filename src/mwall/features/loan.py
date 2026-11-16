"""Loan-level features from the filings (SOP section 9, families 1 to 6).

One row per loan position and filing, the same grain as panel/loan_month.parquet. Every input
is a field of that filing or of an earlier filing of the same loan, so the snapshot date is the
filing date. Ratios use the whole-loan balance (``wl_balance_est``) because NOI, value and
reported DSCR describe the whole collateral, while ``balance`` is only the trust's piece.

Nothing is imputed: a feature whose inputs are missing stays null and keeps its missing flag.
"""
from __future__ import annotations

import duckdb
import numpy as np
import pandas as pd

from mwall.clean import status
from mwall.common import paths

DAYS_PER_MONTH = 30.4375
ROLLOVER_MONTHS = 24
UNIT_TYPES = {"multifamily", "lodging"}  # basis per unit; square feet for every other type


def load_fields(where: str = "true") -> pd.DataFrame:
    """Inputs per (root_key, accession): attributes of the position's largest record, sums of
    advances across its notes. Same row filter as the panel; ``where`` narrows it further (SQL)."""
    lp = (paths.PARSED_DIR / "loan_period" / "*.parquet").as_posix()
    cols = {
        "reportPeriodInterestRatePercentage": "coupon", "originalInterestRatePercentage": "coupon_orig",
        "originalAmortizationTermNumber": "amort_months", "originalInterestOnlyTermNumber": "io_months",
        "interestOnlyIndicator": "io_indicator", "firstLoanPaymentDueDate": "first_payment_date",
        "originalLoanAmount": "original_amount", "term_months_from_dates": "term_months",
        "fin_noi_annual": "noi", "fin_ncf_annual": "ncf", "fin_revenue_annual": "revenue",
        "fin_opex_annual": "opex", "fin_noi_sec": "noi_sec", "fin_end": "fin_end",
        "dscr_noi_reported": "dscr_noi_reported", "dscr_noi_recomputed": "dscr_noi_recomputed",
        "flag_dscr_inconsistent": "flag_dscr_inconsistent", "flag_noi_missing": "flag_noi_missing",
        "noi_age_months": "noi_age_months", "val_securitization": "val_securitization",
        "val_securitization_date": "val_securitization_date", "val_recent": "val_recent",
        "val_recent_date": "val_recent_date", "sqft": "sqft", "units": "units", "largest_sqft": "largest_sqft",
        "year_built": "year_built", "year_renovated": "year_renovated",
        "tenant1_sqft": "tenant1_sqft", "tenant1_lease_exp": "tenant1_lease_exp",
        "tenant2_sqft": "tenant2_sqft", "tenant2_lease_exp": "tenant2_lease_exp",
        "tenant3_sqft": "tenant3_sqft", "tenant3_lease_exp": "tenant3_lease_exp",
        "occupancy_current": "occupancy", "occupancy_securitization": "occupancy_sec",
        "wl_balance_est": "wl_balance", "trust_share_est": "trust_share", "wl_balance_method": "wl_balance_method",
        "loanStructureCode": "structure_code", "n_properties": "n_properties",
        "prop_address": "prop_address", "prop_city": "prop_city", "prop_state": "prop_state",
        "prop_zip": "prop_zip", "bucket_eff": "delinquency_bucket",
    }
    pick = ", ".join(f"arg_max({src}, coalesce(balance, 0)) {dst}" for src, dst in cols.items())
    con = duckdb.connect()
    return con.execute(f"""
        select root_key, accession, {pick},
               count(*) n_notes_in_trust,
               sum(coalesce(totalPrincipalInterestAdvancedOutstandingAmount, 0)) adv_pi,
               sum(coalesce(totalTaxesInsuranceAdvancesOutstandingAmount, 0)) adv_ti,
               sum(coalesce(otherExpensesAdvancedOutstandingAmount, 0)) adv_other
        from (select *, {status.bucket_sql('max(period_end) over (partition by accession)')} bucket_eff
              from read_parquet('{lp}', union_by_name=true))
        where loan_source in ('loan_record','note_record','replicated_child')
          and not coalesce(flag_filing_corrupt, false) and not coalesce(flag_transient_loan, false)
          and not coalesce(flag_foreign_record, false) and ({where})
        group by 1, 2""").df()


# ---------------------------------------------------------------- building blocks (unit-tested)

def loan_constant(rate, amort_years) -> np.ndarray:
    """Annual debt service per dollar of loan: 12 * (r/12) / (1 - (1 + r/12)^(-12n)).
    Interest-only (n missing or 0) gives r. Rates are fractions (0.065)."""
    r = np.asarray(rate, dtype=float)
    n = np.asarray(amort_years, dtype=float)
    i = r / 12
    with np.errstate(divide="ignore", invalid="ignore", over="ignore"):
        amort = np.where(i > 0, 12 * i / (1 - (1 + i) ** (-12 * n)), 12 / (12 * n))
    return np.where(np.isnan(n) | (n <= 0), r, amort)


def balloon_share(rate, amort_months, io_months, term_months) -> np.ndarray:
    """Scheduled balance at maturity as a share of the original amount. Interest-only for
    ``io_months``, then level payments that would retire the loan over ``amort_months``."""
    r = np.asarray(rate, dtype=float) / 12
    M = np.asarray(amort_months, dtype=float)
    io = np.nan_to_num(np.asarray(io_months, dtype=float), nan=0.0)
    T = np.asarray(term_months, dtype=float)
    paid = np.clip(T - io, 0, None)
    with np.errstate(divide="ignore", invalid="ignore", over="ignore"):
        g_M, g_m = (1 + r) ** M, (1 + r) ** paid
        level = np.where(r > 0, (g_M - g_m) / (g_M - 1), 1 - paid / M)
    out = np.where(np.isnan(M) | (M <= 0) | (paid <= 0), 1.0, np.clip(level, 0, 1))
    return np.where(np.isnan(T) | np.isnan(r), np.nan, out)


def months_between(later: pd.Series, earlier: pd.Series) -> pd.Series:
    return (pd.to_datetime(later) - pd.to_datetime(earlier)).dt.days / DAYS_PER_MONTH


def rollover_share(d: pd.DataFrame, asof: pd.Series, months: int = ROLLOVER_MONTHS) -> pd.Series:
    """Share of the top-three tenants' listed square feet whose lease ends within ``months`` of the
    snapshot. A listed lease already past its end date counts as rolling (holdover or stale roster)."""
    horizon = pd.to_datetime(asof) + pd.DateOffset(months=months)
    listed = pd.Series(0.0, index=d.index)
    rolling = pd.Series(0.0, index=d.index)
    for k in (1, 2, 3):
        sq = pd.to_numeric(d[f"tenant{k}_sqft"], errors="coerce")
        exp = pd.to_datetime(d[f"tenant{k}_lease_exp"], errors="coerce")
        ok = sq.gt(0) & exp.notna()
        listed += sq.where(ok, 0)
        rolling += sq.where(ok & (exp <= horizon), 0)
    return (rolling / listed).where(listed > 0)


def first_reported(d: pd.DataFrame, value: str, period: str) -> pd.DataFrame:
    """For each loan and financial period, the value as first reported and when."""
    x = d.loc[d[value].notna() & d[period].notna(), ["root_key", period, "snapshot_date", value]]
    return x.sort_values("snapshot_date").drop_duplicates(["root_key", period], keep="first")


def noi_yoy(d: pd.DataFrame, tol_days: int = 45) -> pd.Series:
    """NOI over NOI for the period ending about a year before this one's financials end, as that
    earlier period was first reported. Only earlier filings qualify."""
    hist = first_reported(d, "noi", "fin_end").rename(
        columns={"fin_end": "prev_end", "snapshot_date": "prev_snapshot", "noi": "prev_noi"})
    cur = d.loc[d["noi"].notna() & d["fin_end"].notna(), ["root_key", "fin_end", "snapshot_date", "noi"]].copy()
    cur["target"] = cur["fin_end"] - pd.DateOffset(years=1)
    cur = cur.reset_index().sort_values("target")
    m = pd.merge_asof(cur, hist.sort_values("prev_end"), left_on="target", right_on="prev_end", by="root_key",
                      direction="nearest", tolerance=pd.Timedelta(days=tol_days))
    ok = m["prev_snapshot"] <= m["snapshot_date"]
    m["yoy"] = np.where(ok & (m["prev_noi"] > 0), m["noi"] / m["prev_noi"] - 1, np.nan)
    return m.set_index("index")["yoy"].reindex(d.index)


def _safe_div(a, b) -> pd.Series:
    a = pd.to_numeric(a, errors="coerce")
    b = pd.to_numeric(b, errors="coerce")
    return (a / b).where(b > 0)


# ---------------------------------------------------------------- features

def compute(d: pd.DataFrame) -> pd.DataFrame:
    """Add the f_* columns. ``d`` needs the load_fields columns plus snapshot_date, period_end,
    maturity_date, maturity0, origination_date, property_group, balance and the panel event columns."""
    T = d["snapshot_date"]
    f = pd.DataFrame(index=d.index)
    # leverage and coverage
    f["f_debt_yield_noi"] = _safe_div(d["noi"], d["wl_balance"])
    f["f_debt_yield_ncf"] = _safe_div(d["ncf"], d["wl_balance"])
    f["f_dscr_noi_reported"] = pd.to_numeric(d["dscr_noi_reported"], errors="coerce")
    f["f_dscr_noi_recomputed"] = pd.to_numeric(d["dscr_noi_recomputed"], errors="coerce")
    f["f_dscr_disagree"] = d["flag_dscr_inconsistent"].astype("boolean")
    f["f_ltv_securitization"] = _safe_div(d["wl_balance"], d["val_securitization"])
    recent_ok = pd.to_datetime(d["val_recent_date"]) <= T
    f["f_ltv_recent"] = _safe_div(d["wl_balance"], d["val_recent"].where(recent_ok))
    f["f_reappraised"] = recent_ok & (pd.to_datetime(d["val_recent_date"])
                                      > pd.to_datetime(d["val_securitization_date"]) + pd.Timedelta(days=365))
    # cash-flow trend
    f["f_noi_vs_securitization"] = _safe_div(d["noi"], d["noi_sec"]) - 1
    f["f_noi_yoy"] = noi_yoy(d)
    f["f_expense_ratio"] = _safe_div(d["opex"], d["revenue"])
    f["f_noi_age_months"] = pd.to_numeric(d["noi_age_months"], errors="coerce")
    f["f_noi_missing"] = d["noi"].isna()
    # occupancy and tenants
    f["f_occupancy"] = pd.to_numeric(d["occupancy"], errors="coerce")
    f["f_occupancy_change"] = f["f_occupancy"] - pd.to_numeric(d["occupancy_sec"], errors="coerce")
    share = _safe_div(d["tenant1_sqft"], d["largest_sqft"])
    f["f_tenant1_share"] = share.where(share <= 1)
    f["f_rollover_24m"] = rollover_share(d, T)
    # loan terms
    f["f_months_to_maturity"] = months_between(d["maturity_date"], d["period_end"])
    f["f_term_months"] = pd.to_numeric(d["term_months"], errors="coerce")
    f["f_seasoning_months"] = months_between(d["period_end"], d["origination_date"])
    f["f_coupon"] = pd.to_numeric(d["coupon"], errors="coerce")
    io = pd.to_numeric(d["io_months"], errors="coerce")
    io_end = pd.to_datetime(d["origination_date"]) + pd.to_timedelta(io * DAYS_PER_MONTH, unit="D")
    f["f_io_remaining_months"] = months_between(io_end, d["period_end"]).clip(lower=0).where(io.notna())
    f["f_full_term_io"] = (io >= f["f_term_months"] - 1) | (pd.to_numeric(d["amort_months"], errors="coerce") == 0)
    f["f_balloon_share"] = balloon_share(d["coupon_orig"], d["amort_months"], io, d["term_months"])
    f["f_extended"] = pd.to_datetime(d["maturity_date"]) > pd.to_datetime(d["maturity0"])
    ts = pd.to_numeric(d["trust_share"], errors="coerce")
    whole = d["wl_balance_method"].eq("trust_holds_whole_loan") & d["structure_code"].fillna("WL").eq("WL")
    f["f_trust_share"] = ts.where(ts.notna(), np.where(whole, 1.0, np.nan)).clip(upper=1)
    code = d["structure_code"].astype("string")
    piece = code.isin(["PP", "A1", "A2", "B1", "B2", "C2"]) | (ts < 0.99)
    f["f_pari_passu_piece"] = (code.eq("PP") | (ts < 0.99)).astype("boolean").where(code.notna() | ts.notna())
    f["f_ab_structure"] = code.isin(["A1", "A2", "B1", "B2", "C2"]).astype("boolean").where(code.notna())
    f["f_debt_outside_trust"] = piece.astype("boolean").where(code.notna() | ts.notna())
    f["f_n_notes_in_trust"] = d["n_notes_in_trust"]
    f["f_n_properties"] = pd.to_numeric(d["n_properties"], errors="coerce")
    f["f_single_asset"] = f["f_n_properties"].eq(1)
    # property
    yb = pd.to_numeric(d["year_built"], errors="coerce")
    yr = pd.to_numeric(d["year_renovated"], errors="coerce")
    year = pd.to_datetime(d["period_end"]).dt.year
    f["f_property_age_years"] = (year - yb).where((yb > 1700) & (yb <= year))
    last_work = pd.concat([yb, yr.where(yr <= year)], axis=1).max(axis=1)
    f["f_years_since_renovation"] = (year - last_work).where((last_work > 1700) & (last_work <= year))
    f["f_cooperative"] = d["prop_type_code"].astype("string").eq("CH").fillna(False).astype(bool)
    by_unit = d["property_group"].isin(UNIT_TYPES)
    f["f_balance_per_unit"] = _safe_div(d["wl_balance"], d["units"]).where(by_unit)
    f["f_balance_per_sqft"] = _safe_div(d["wl_balance"], d["sqft"]).where(~by_unit)
    # servicing and status
    f["f_ever_modified"] = d["ev_modification"].astype(int).groupby(d["root_key"]).cummax().astype(bool)
    f["f_ever_special_serviced"] = d["ss_transfer_date"].notna().astype(int).groupby(d["root_key"]).cummax().astype(bool)
    f["f_in_special_servicing"] = d["in_special_servicing"].astype(bool)
    f["f_advances_pi"] = d["adv_pi"] > 0
    f["f_advances_ti"] = d["adv_ti"] > 0
    f["f_advances_other"] = d["adv_other"] > 0
    f["f_advances_pct"] = _safe_div(d[["adv_pi", "adv_ti", "adv_other"]].sum(axis=1), d["balance"])
    return f
