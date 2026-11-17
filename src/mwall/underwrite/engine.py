"""Underwriting engine (SOP 12, steps A to D). The method is written out in docs/underwriting.md.

Every function here works on one loan at a time with plain arithmetic, so the site can run the same math in
JavaScript (Gate 5) and a spreadsheet can rebuild it cell by cell (Gate 4 hand check).

    L  one loan's inputs (a dict; ``prepare`` adds the fields that don't depend on the scenario)
    S  a scenario row of config/scenarios.csv
    P  the parameters (``load_params``)
    M  market inputs on the valuation date (data/outputs/underwrite_market.json)
"""
from __future__ import annotations

import json
import math
from datetime import date

import numpy as np
import pandas as pd

from mwall.common import paths

CONFIG = paths.CONFIG_DIR
OWN_SERIES = ("office", "retail", "industrial", "multifamily")  # cap-rate benchmark types with a current series
ROLLOVER_TYPES = ("office", "retail", "industrial")
DOWNGRADE = {"A": "B", "B": "C", "C": "C"}
SPECIAL_CITY = {"santa_monica": ((8_000_000, 5.3), (5_000_000, 0.3)),
                "culver_city": ((10_000_000, 3.55), (3_000_000, 2.55), (1_500_000, 1.05))}
LA_COUNTY, ORANGE_COUNTY = "06037", "06059"
ULA_BASE_DATE = date(2026, 7, 1)
HOLD = 5


# ------------------------------------------------------------------ parameters

def load_params() -> dict:
    u = pd.read_csv(CONFIG / "underwriting_params.csv", dtype={"value": str})
    p: dict = {}
    for r in u.itertuples(index=False):
        v = r.value if r.parameter == "tier" else float(r.value)
        p.setdefault(r.parameter, {})[r.property_group] = v
    la = pd.read_csv(CONFIG / "la_overrides.csv")
    p["la"] = {(r.rule, r.jurisdiction, r.parameter): float(r.value) for r in la.itertuples(index=False)}
    lp = pd.read_csv(CONFIG / "lender_params.csv")
    p["lender"] = {(r.scenario, r.property_group): r._asdict() for r in lp.itertuples(index=False)}
    p["scenarios"] = {r.scenario: r._asdict() for r in pd.read_csv(CONFIG / "scenarios.csv").itertuples(index=False)}
    return p


def par(P: dict, name: str, group: str | None):
    """A parameter for the property group, else its 'all' row, else None."""
    t = P.get(name, {})
    return t.get(group, t.get("all"))


def load_market() -> dict:
    return json.loads((paths.OUTPUT_DIR / "underwrite_market.json").read_text())


# ------------------------------------------------------------------ small pieces (unit-tested)

def loan_constant(r: float, years: float) -> float:
    """Annual debt service per dollar: 12 (r/12) / (1 - (1 + r/12)^(-12 n)); interest-only when n is 0."""
    if not years or years <= 0:
        return r
    i = r / 12
    return 12 * i / (1 - (1 + i) ** (-12 * years))


def npv(rate: float, cfs: list[float]) -> float:
    return sum(cf / (1 + rate) ** t for t, cf in enumerate(cfs))


def irr(cfs: list[float]) -> float:
    """The rate in (-99%, 1000%) that sets the NPV to zero, by bisection on a bracket with a sign change."""
    lo, hi = -0.99, 10.0
    f_lo, f_hi = npv(lo, cfs), npv(hi, cfs)
    if not (np.isfinite(f_lo) and np.isfinite(f_hi)) or f_lo * f_hi > 0:
        return float("nan")
    for _ in range(200):
        mid = (lo + hi) / 2
        f_mid = npv(mid, cfs)
        if f_lo * f_mid <= 0:
            hi = mid
        else:
            lo, f_lo = mid, f_mid
        if hi - lo < 1e-12:
            break
    return (lo + hi) / 2


def add_years(d: date, n: int) -> date:
    try:
        return d.replace(year=d.year + n)
    except ValueError:  # 29 February
        return d.replace(year=d.year + n, day=28)


def rollover_year(expiry: date | None, valuation: date) -> int | None:
    """Hold year (1 to 5) in which a listed lease ends; an expired lease rolls in year 1; None if after the hold."""
    if expiry is None:
        return None
    for t in range(1, HOLD + 1):
        if expiry <= add_years(valuation, t):
            return t
    return None


def ula_indexations(exit_date: date) -> int:
    """July-1 threshold updates after the 2026-07-01 thresholds and on or before the exit date."""
    n = exit_date.year - ULA_BASE_DATE.year - (1 if (exit_date.month, exit_date.day) < (7, 1) else 0)
    return max(n, 0)


def local_transfer_rate(jurisdiction: str, price: float, exit_date: date, P: dict) -> float:
    """Special city transfer tax on the whole price, as a fraction, on top of the generic selling cost."""
    if jurisdiction == "la_city":
        g = P["la"][("ula", "la_city", "threshold_growth")] / 100
        n = ula_indexations(exit_date)
        lo = P["la"][("ula", "la_city", "threshold_lower")] * (1 + g) ** n
        hi = P["la"][("ula", "la_city", "threshold_upper")] * (1 + g) ** n
        if price >= hi:
            return P["la"][("ula", "la_city", "rate_upper")] / 100
        if price > lo:
            return P["la"][("ula", "la_city", "rate_lower")] / 100
        return 0.0
    for floor_, rate in SPECIAL_CITY.get(jurisdiction, ()):
        if price >= floor_:
            return rate / 100
    return 0.0


# ------------------------------------------------------------------ per-loan preparation

def _date(v) -> date | None:
    if v is None or (isinstance(v, float) and math.isnan(v)) or pd.isna(v):
        return None
    return pd.Timestamp(v).date()


def _num(v) -> float:
    try:
        f = float(v)
    except (TypeError, ValueError):
        return float("nan")
    return f


def jurisdiction(L: dict) -> str:
    if _num(L.get("n_properties")) > 1:
        return "multi_property"
    geoid = L.get("place_geoid") if isinstance(L.get("place_geoid"), str) else None
    county = L.get("county_fips")
    if geoid == "0644000":
        return "la_city"
    if geoid == "0670000":
        return "santa_monica"
    if geoid == "0617568":
        return "culver_city"
    if county == LA_COUNTY:
        return "la_unincorporated" if L.get("place_source") == "census_geocoder" and not geoid else "la_county"
    if county == ORANGE_COUNTY:
        return "orange_county"
    return "other"


def clip_spread(raw: float, lo: float, hi: float) -> float:
    """The property's cap-rate spread over its type's benchmark at securitization, held inside [lo, hi]."""
    return min(max(raw, lo), hi) if not math.isnan(raw) else float("nan")


def seller_tax(tau: float, val_sec: float, val_sec_date: date, valuation: date, growth: float) -> float:
    """Tax on the seller's factored base year value under Proposition 13: the securitization appraisal as the base,
    grown at the 2% cap since then (the actual assessed value isn't in the filings). The engine caps it at the tax on
    today's value (Proposition 8)."""
    yrs = (valuation - val_sec_date).days / 365.25
    return tau * val_sec * (1 + growth) ** max(yrs, 0)


def spread_bounds(df: pd.DataFrame, P: dict) -> dict:
    """Percentile bounds (cap_spread_clip_pct: 10th and 90th) of the securitization cap-rate spread by group."""
    q = par(P, "cap_spread_clip_pct", "all") / 100
    out = {}
    for g, x in df.groupby("property_group"):
        s = x["spread_sec_raw"].dropna()
        if len(s) >= 20:
            out[g] = (float(s.quantile(q)), float(s.quantile(1 - q)))
    return out


def prepare(df: pd.DataFrame, P: dict) -> list[dict]:
    """Scenario-free fields per loan: the benchmark pair, the clipped securitization spread, the jurisdiction,
    the base tier and why it moved, and the estimated current property tax where Proposition 13 applies."""
    d = df.copy()
    own = d["property_group"].isin(OWN_SERIES) & d["cap_bench_today"].notna() & d["cap_bench_sec"].notna()
    d["bench_today"] = np.where(own, d["cap_bench_today"], d["cap_composite_today"])
    d["bench_sec"] = np.where(own, d["cap_bench_sec"], d["cap_composite_sec"])
    d["bench_kind"] = np.where(own, "own type", "composite")
    c_sec = (d["noi_sec"] / d["val_sec"]).where((d["noi_sec"] > 0) & (d["val_sec"] > 0))
    d["cap_sec"] = c_sec
    d["spread_sec_raw"] = c_sec - d["bench_sec"]
    bounds = spread_bounds(d, P)
    rows = []
    for L in d.to_dict("records"):
        g = L["property_group"] if isinstance(L["property_group"], str) else None
        L["group"] = g
        lo, hi = bounds.get(g, (-np.inf, np.inf))
        raw = _num(L["spread_sec_raw"])
        L["spread_lo"], L["spread_hi"] = lo, hi
        L["spread_sec"] = clip_spread(raw, lo, hi)
        L["spread_clipped"] = (not math.isnan(raw)) and (raw < lo or raw > hi)
        L["jurisdiction"] = jurisdiction(L)
        L["valuation"] = _date(L["valuation_date"])
        tier, why = (par(P, "tier", g) if g else None), []
        noi = _num(L.get("noi"))
        if tier is None:
            why.append("no property type")
        elif math.isnan(noi):
            tier = None
            why.append("no current NOI")
        elif noi <= 0:
            tier = None
            why.append("NOI zero or negative")
        elif _num(L.get("noi_age_months")) > par(P, "noi_max_age_months", "all"):
            tier = None
            why.append("NOI older than 36 months")
        else:
            if _num(L.get("noi_age_months")) > par(P, "noi_current_max_age_months", "all"):
                why.append("NOI older than 18 months")
            if _num(L.get("fin_months")) < par(P, "noi_partial_min_months", "all"):
                why.append("NOI annualized from under 6 months")
            if bool(L.get("flag_fin_basis_unknown")):
                why.append("partial-year basis unknown")
            if why:
                tier = DOWNGRADE[tier]
            size = _num(L.get("units")) if g == "multifamily" else _num(L.get("sqft"))
            if tier in ("A", "B") and not size > 0:
                tier = "C"
                why.append("no square feet or units")
        L["tier"], L["tier_reason"] = tier, "; ".join(why)
        # Proposition 13: the seller's tax is estimated from the securitization appraisal grown 2% a year
        if L["jurisdiction"] != "multi_property" and L.get("county_fips") in (LA_COUNTY, ORANGE_COUNTY):
            key = "la_county" if L["county_fips"] == LA_COUNTY else "orange_county"
            tau = P["la"][("prop13", key, "tax_rate")] / 100
            vs, vd = _num(L.get("val_sec")), _date(L.get("val_sec_date"))
            if vs > 0 and vd is not None:
                g2 = P["la"][("prop13", "all", "assessed_growth")] / 100
                L["tax_rate"], L["tax_current"] = tau, seller_tax(tau, vs, vd, L["valuation"], g2)
        L.setdefault("tax_rate", float("nan"))
        L.setdefault("tax_current", float("nan"))
        L["rent_cap"] = rent_cap(L, P)
        rows.append(L)
    return rows


def rent_cap(L: dict, P: dict) -> float:
    """Annual growth cap from local rent rules for a single multifamily property, else infinity."""
    if L["group"] != "multifamily" or L["jurisdiction"] == "multi_property":
        return float("inf")
    yb = _num(L.get("year_built"))
    j = L["jurisdiction"]
    if j == "la_city" and yb <= 1978:
        return P["la"][("rent_cap", "la_city_rso", "annual_cap")] / 100
    if j == "la_unincorporated" and yb <= 1994:
        return P["la"][("rent_cap", "la_county_rstpo", "annual_cap")] / 100
    if L.get("county_fips") in (LA_COUNTY, ORANGE_COUNTY) and yb <= L["valuation"].year - 15:
        return P["la"][("rent_cap", "ab1482", "annual_cap")] / 100
    return float("inf")


# ------------------------------------------------------------------ the engine

def underwrite(L: dict, S: dict, P: dict, M: dict, rate_shift_bps: float | None = None,
               cap_shift_bps: float | None = None, hurdle: float | None = None, keep_flows: bool = False) -> dict:
    g, tier = L["group"], L["tier"]
    rs = (S["rate_shift_bps"] if rate_shift_bps is None else rate_shift_bps) / 10_000
    cs = (S["cap_shift_bps"] if cap_shift_bps is None else cap_shift_bps) / 10_000
    out: dict = {"tier": tier, "tier_reason": L["tier_reason"], "jurisdiction": L["jurisdiction"]}
    B = _num(L.get("wl_balance_est"))
    noi0 = _num(L.get("noi"))
    if g is None:
        return out

    # ---- step B: stressed NOI, cap rate and value
    h = par(P, S["noi_haircut"], g) / 100 if S["noi_haircut"] != "none" else 0.0
    noi_s = noi0 * (1 - h)
    bt = _num(L["bench_today"])
    spread = _num(L["spread_sec"])
    c = bt + (spread if not math.isnan(spread) else 0.0) + cs
    c = max(c, par(P, "cap_rate_floor", "all") / 100) if not math.isnan(c) else c
    out.update(noi_stressed=noi_s, cap_rate=c, cap_method="relative value" if not math.isnan(spread) else
               "benchmark only", bench_kind=L["bench_kind"])
    tau, tbase = _num(L["tax_rate"]), _num(L["tax_current"])
    prop13 = not math.isnan(tau) and not math.isnan(tbase)
    if tier is None or math.isnan(c):
        if noi0 <= 0 and not math.isnan(B):  # no lender sizes a loan on zero or negative income
            out.update(p_max=0.0, refi_gap=B, refi_gap_pct=1.0)
        return out
    # Proposition 8 (D064): the seller is taxed on the lower of the factored base year value and today's value, so the
    # seller's tax is capped at the tax on NOI / c; value then solves V c = NOI + T_seller - tau V
    tcur = min(tbase, tau * noi_s / c) if prop13 else float("nan")
    V = (noi_s + tcur) / (c + tau) if prop13 else noi_s / c
    out["seller_tax"] = tcur
    out["value"] = V

    # ---- step A: refinance gap under the scenario's lender set
    lp = P["lender"].get((S["refi_lender_set"], g)) or P["lender"][(S["refi_lender_set"], "other")]
    series = lp["spread_series"]
    r_refi = M["ust10"] + (M["spread_bps"][series] + lp["spread_premium_bps"]) / 10_000 + rs
    k = loan_constant(r_refi, lp["amort_years"])
    p_ltv = lp["ltv_max"] * V
    p_dscr = noi_s / (lp["dscr_min"] * k)
    p_dy = noi_s / lp["dy_min"] if lp["dy_min"] == lp["dy_min"] and lp["dy_min"] else float("inf")
    p_max = max(min(p_ltv, p_dscr, p_dy), 0.0)
    out.update(refi_rate=r_refi, loan_constant=k, p_ltv=p_ltv, p_dscr=p_dscr, p_dy=p_dy, p_max=p_max)
    if not math.isnan(B) and B > 0:
        out.update(refi_gap=max(0.0, B - p_max), refi_gap_pct=max(0.0, B - p_max) / B)

    # ---- capital items and lease-up
    sqft, units, occ = _num(L.get("sqft")), _num(L.get("units")), _num(L.get("occupancy"))
    occ_eff = occ if occ > 0 else 1.0
    rev0 = _num(L.get("revenue"))
    income_full = (rev0 if rev0 > 0 else noi0) / occ_eff
    if g == "multifamily":
        reserve = par(P, "reserve", g) * units if units > 0 else float("nan")
    elif g == "lodging":
        reserve = par(P, "reserve", g) / 100 * rev0 if rev0 > 0 else float("nan")
    else:
        reserve = par(P, "reserve", g) * sqft if sqft > 0 else float("nan")
    roll = g in ROLLOVER_TYPES and sqft > 0
    shares: list[tuple[float, int | None]] = []
    if roll and L["jurisdiction"] != "multi_property":
        for i in (1, 2, 3):
            sq, exp = _num(L.get(f"tenant{i}_sqft")), _date(L.get(f"tenant{i}_lease_exp"))
            if sq > 0 and exp is not None:
                shares.append((sq / sqft, rollover_year(exp, L["valuation"])))
        tot = sum(s for s, _ in shares)
        if tot > occ_eff:
            shares = [(s * occ_eff / tot, y) for s, y in shares]
    listed = sum(s for s, _ in shares)
    unlisted = max(0.0, occ_eff - listed)
    if roll:
        p_ren, dt = par(P, "renewal_prob", g) / 100, par(P, "downtime_months", g) / 12
        ti_cost = sqft * (p_ren * par(P, "ti_lc_renewal_psf", g) + (1 - p_ren) * par(P, "ti_lc_new_psf", g))
        term = par(P, "lease_term_years", g)
        r_t = [sum(s for s, y in shares if y == t) + unlisted / term for t in range(1, HOLD + 1)]
        r1_listed = sum(s for s, y in shares if y == 1)
        lease_up = r1_listed * (ti_cost + (1 - p_ren) * income_full * dt)
    else:
        p_ren = dt = ti_cost = 0.0
        r_t = [0.0] * HOLD
        lease_up = 0.0
    closing = par(P, "buyer_closing_pct", "all") / 100
    res1 = reserve if not math.isnan(reserve) else 0.0
    value_bid = (V - lease_up - res1) / (1 + closing)
    out.update(reserve_y1=reserve, lease_up=lease_up, value_bid=value_bid)
    if tier == "C":
        return _finish(out, value_bid, float("nan"), B)

    # ---- step D: five-year cash flows
    gr = par(P, "noi_growth", g) / 100
    growth = [gr] * (HOLD + 1)  # growth[t] takes S_t to S_{t+1}
    metro = _num(L.get("mf_rent_growth_metro"))
    if g == "multifamily" and not math.isnan(metro):
        growth[1] = metro
    growth = [min(x, L["rent_cap"]) for x in growth]
    S_t = [noi_s]
    for t in range(1, HOLD + 1):
        S_t.append(S_t[-1] * (1 + growth[t]))           # S_t[0] is year 1 ... S_t[5] is year 6
    reno = S["renovation"] == "on" and g == "multifamily" and units > 0 and L["rent_cap"] > 0.05
    budget = par(P, "renovation_cost_per_unit", g) * units if reno else 0.0
    premium = budget * par(P, "renovation_roc", g) / 100 if reno else 0.0
    ren = [0.0] + [premium] * HOLD                       # from year 2
    loss = [(1 - p_ren) * r_t[t] * income_full * dt * (1 + gr) ** t for t in range(HOLD)]
    leasing = [r_t[t] * ti_cost for t in range(HOLD)]
    capex = [res1 + leasing[t] for t in range(HOLD)]
    g2 = P["la"][("prop13", "all", "assessed_growth")] / 100
    c_exit = c + par(P, "exit_cap_spread_bps", "all") / 10_000
    pre_tax_6 = S_t[HOLD] + ren[HOLD] + (tcur * (1 + g2) ** HOLD if prop13 else 0.0)
    exit_price = pre_tax_6 / (c_exit + (tau if prop13 else 0.0))
    exit_date = add_years(L["valuation"], HOLD)
    sell = par(P, "selling_cost_pct_high_tax" if bool(L.get("high_tax_metro")) else "selling_cost_pct", "all") / 100
    local = local_transfer_rate(L["jurisdiction"], exit_price, exit_date, P)
    exit_net = exit_price * (1 - sell - local)
    r_acq = M[f"ust{int(par(P, 'acq_treasury_tenor', 'all'))}"] + par(P, "bridge_spread_bps", g) / 10_000 + rs
    ltc, ltv = par(P, "ltc", g) / 100, par(P, "ltv_asis", g) / 100
    hurdle = (par(P, S["hurdle_param"], "all") / 100) if hurdle is None else hurdle

    def flows(price: float) -> dict:
        cost = price * (1 + closing) + budget
        loan = min(ltc * cost, ltv * V)
        dtax = [((tau * price - tcur) * (1 + g2) ** t) if prop13 else 0.0 for t in range(HOLD)]
        noi = [S_t[t] + ren[t] - dtax[t] - loss[t] for t in range(HOLD)]
        interest = r_acq * loan
        unlev = [-cost] + [noi[t] - capex[t] for t in range(HOLD)]
        unlev[HOLD] += exit_net
        lev = [-cost + loan] + [unlev[t + 1] - interest for t in range(HOLD)]
        lev[HOLD] -= loan
        return {"price": price, "cost": cost, "loan": loan, "noi": noi, "dtax": dtax, "interest": interest,
                "unlev": unlev, "lev": lev}

    # NPV at the hurdle is linear in price on each side of the kink where LTV starts to bind
    kink = (ltv * V / ltc - budget) / (1 + closing)
    f = lambda x: npv(hurdle, flows(x)["lev"])  # noqa: E731
    ret_bid = float("nan")
    if kink > 0:
        f0, fk = f(0.0), f(kink)
        if f0 > 0 >= fk:
            ret_bid = kink * f0 / (f0 - fk)
        elif fk > 0:
            f2 = f(2 * kink)
            if f2 < fk:
                ret_bid = kink + kink * fk / (fk - f2)
    else:
        f0, f1 = f(0.0), f(V)
        if f0 > 0 and f1 < f0:
            ret_bid = V * f0 / (f0 - f1)
    out.update(exit_cap=c_exit, exit_price=exit_price, exit_cost_rate=sell + local, exit_net=exit_net,
               acq_rate=r_acq, hurdle=hurdle, return_bid=ret_bid, renovation_budget=budget, kink=kink)
    if not math.isnan(ret_bid):
        fl = flows(ret_bid)
        eq = -fl["lev"][0]
        ops = [fl["unlev"][t + 1] - fl["interest"] for t in range(HOLD)]
        ops[HOLD - 1] = fl["noi"][HOLD - 1] - capex[HOLD - 1] - fl["interest"]
        out.update(
            loan_at_bid=fl["loan"], equity=eq, irr_levered=irr(fl["lev"]), irr_unlevered=irr(fl["unlev"]),
            equity_multiple=sum(fl["lev"][1:]) / eq, cash_on_cash=sum(ops) / HOLD / eq,
            noi_y1=fl["noi"][0], dscr_y1=fl["noi"][0] / fl["interest"] if fl["interest"] > 0 else float("nan"),
            dy_y1=fl["noi"][0] / fl["loan"] if fl["loan"] > 0 else float("nan"),
            breakeven_occ=((rev0 - fl["noi"][0] + fl["interest"]) / (rev0 / occ_eff)) if rev0 > 0 else float("nan"))
        if keep_flows:
            out["flows"] = fl
    fv = flows(value_bid) if value_bid > 0 else None
    out["irr_at_value_bid"] = irr(fv["lev"]) if fv else float("nan")
    out["irr_unlevered_at_value_bid"] = irr(fv["unlev"]) if fv else float("nan")
    out["clears_hurdle_at_value"] = bool(ret_bid >= value_bid) if not math.isnan(ret_bid) else False
    return _finish(out, value_bid, ret_bid, B)


def _finish(out: dict, value_bid: float, ret_bid: float, B: float) -> dict:
    bids = [b for b in (value_bid, ret_bid) if not math.isnan(b)]
    bid = max(min(bids), 0.0) if bids else float("nan")
    out["bid"] = bid
    if not math.isnan(bid) and B > 0:
        out["refinanceable_by_sale"] = bid >= B
        out["discount"] = max(0.0, 1 - bid / B)
    return out
