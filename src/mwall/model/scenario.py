"""Refinance-rate scenarios for the robustness suite (SOP 11: rankings when the rate moves 100 bp).

Recomputes the rate-dependent features from the stored ones, with the same lender parameters as
features/build.attach_refi (base scenario). With NOI/B = debt yield and value/B = debt yield / cap rate:

    k' = loan_constant(r + shift, amort)
    refi DSCR' = DY / k'
    income proceeds / B = max(0, min(DY / (DSCR_min k'), DY / DY_min))
    refi gap' = max(0, 1 - min(income proceeds / B, LTV_max DY / cap rate))
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from mwall.features import loan
from mwall.features.build import LENDER_PARAMS


def lender_base() -> pd.DataFrame:
    lp = pd.read_csv(LENDER_PARAMS)
    return lp[lp["scenario"].eq("base")].set_index("property_group")


def shift_refi(d: pd.DataFrame, bps: float, lp: pd.DataFrame | None = None) -> pd.DataFrame:
    lp = lender_base() if lp is None else lp
    out = d.copy()
    pg = d["property_group"].astype(object).where(d["property_group"].astype(object).isin(lp.index), "other")
    par = lp.reindex(pg.to_numpy())
    rate = d["f_refi_rate"].to_numpy(float) + bps / 10_000
    k = loan.loan_constant(rate, par["amort_years"].to_numpy(float))
    dy = d["f_debt_yield_noi"].to_numpy(float)
    p_income = np.clip(np.minimum(dy / (par["dscr_min"].to_numpy() * k), dy / par["dy_min"].to_numpy()), 0, None)
    out["f_refi_rate"] = rate
    out["f_rate_shock"] = d["f_rate_shock"].to_numpy(float) + bps / 10_000
    out["f_refi_dscr"] = dy / k
    out["f_refi_gap_income"] = np.where(np.isnan(dy), np.nan, np.clip(1 - p_income, 0, None))
    v_over_b = dy / d["f_cap_rate_benchmark"].to_numpy(float)
    has_v = (dy > 0) & ~np.isnan(v_over_b)
    p_max = np.minimum(p_income, par["ltv_max"].to_numpy() * v_over_b)
    out["f_refi_gap"] = np.where(has_v, np.clip(1 - p_max, 0, None), np.nan)
    return out


def rate_scenarios(bps: tuple[int, ...] = (-100, 100)) -> dict:
    lp = lender_base()
    return {f"rate_{'up' if b > 0 else 'down'}_{abs(b)}": (lambda x, b=b: shift_refi(x, b, lp)) for b in bps}
