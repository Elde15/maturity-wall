"""Los Angeles case study, built after the selection commit (SOP 13 steps 2, 3, 6 and 7).

    python -m mwall la      # site/public/data/la.json and docs/la/memo.md

Every number in a case file comes from the published outputs or a cited row of config/research/la_market_sources.csv;
the narratives below are templates whose numbers, and whose either-or statements, are filled from those cells. The
second reader's notes (docs/qa/gate6_review.md) shaped the wording: probabilities are given with their rank, every
value shows the NOI and cap rate behind it, and no sentence states a model output as a certainty.
"""
from __future__ import annotations

import json
import subprocess
from decimal import ROUND_HALF_UP, Decimal

import numpy as np
import pandas as pd

from mwall.common import paths
from mwall.site_export import export
from mwall.site_export.la import COUNTIES, DOCS, Local, candidates, local_context, market, select
from mwall.underwrite import engine, run

REPO = "https://github.com/Elde15/maturity-wall/blob/main"


def _r(v: float, nd: int) -> str:
    """Round half up, the way the site's JavaScript does, so the memo and the page print the same figure."""
    return f"{Decimal(str(v)).quantize(Decimal(1).scaleb(-nd), rounding=ROUND_HALF_UP):,}"


def _m(v) -> str:
    if v is None or pd.isna(v):
        return "n/a"
    if abs(v) >= 1e9:
        return f"${_r(v / 1e9, 1)}B"
    return f"${_r(v / 1e6, 1)}M" if abs(v) >= 1e6 else f"${_r(v / 1e3, 0)}K"


def _p(v, d: int = 1) -> str:
    return "n/a" if v is None or pd.isna(v) else f"{_r(100 * v, d)}%"


def picks() -> list[tuple[str, str]]:
    """The committed picks, read back from docs/la/selection.md so the page can't drift from the record."""
    import re

    text = (DOCS / "selection.md").read_text(encoding="utf-8")
    return [(m.group(1), m.group(2)) for m in re.finditer(r"^- (\d\. [^:]+): .*?`(WL[0-9a-f]+)`", text, re.M)]


def display_label(label: str) -> str:
    """The committed rule says 'opportunity score'; the site calls the same number 'review priority'."""
    return label.replace("opportunity score", "review priority")


def band_rule(L: pd.DataFrame) -> tuple[pd.Series, dict]:
    """Same rule as site/src/lib/risk.js."""
    pdv = np.sort(L["pd"].dropna().to_numpy())
    q = lambda p: pdv[min(len(pdv) - 1, int(np.floor(p * len(pdv))))]  # noqa: E731
    q80, q95 = float(q(0.8)), float(q(0.95))
    dist = L["status"].isin(export.DISTRESSED)
    b = np.where(dist, 4, np.where(L["pf"].notna(), np.where(L["pf"] >= 0.5, 3, np.where(L["pf"] >= 0.25, 2, 1)),
                 np.where(L["pd"].notna(), np.where(L["pd"] >= q95, 3, np.where(L["pd"] >= q80, 2, 1)), 0)))
    rule = (f"In distress now: special servicing, 30 or more days delinquent, or past maturity unpaid. Within 24 months "
            f"of maturity, by the maturity model: high at 50% or more, elevated at 25 to 50%. Otherwise by the 12-month "
            f"distress probability: high at {_p(q95)} or more (the riskiest 5% of loans), elevated from {_p(q80)} (the "
            f"next 15%). Not scored: no usable status or inputs.")
    return pd.Series(b, index=L.index), {"q80": q80, "q95": q95, "rule": rule}


def market_tables(x: dict, L: pd.DataFrame, rows: list[dict], P: dict) -> dict:
    D = pd.Timestamp(x["market"]["date"])
    bands, brule = band_rule(L)
    L = L.assign(band=bands, chart_type=L["type"].replace({"mixed_use": "mixed_other", "other": "mixed_other"}))
    m = L.loc[market(L).index]
    out = {"loans": int(len(m)), "balance": float(m["bal"].sum()), "national_balance": float(L["bal"].sum()),
           "counties": [{"county": COUNTIES[c], "loans": int((m["county"] == c).sum()),
                         "balance": float(m.loc[m["county"] == c, "bal"].sum())} for c in COUNTIES],
           "ca_outside": int((L["state"].eq("CA") & ~L["county"].isin(COUNTIES)).sum()),
           "share_of_national_balance": float(m["bal"].sum() / L["bal"].sum()),
           "no_refi_test": int(m["gap"].isna().sum()), "band_rule": brule["rule"]}
    tested = lambda d: d[d["gap"].notna()]  # noqa: E731
    by = []
    for t in export.CHART_TYPES:
        a, n = m[m["chart_type"] == t], L[L["chart_type"] == t]
        if not len(a):
            continue
        ta, tn = tested(a), tested(n)
        by.append({"type": t, "loans": int(len(a)), "balance": float(a["bal"].sum()), "tested": int(len(ta)),
                   "share_of_la_balance": float(a["bal"].sum() / m["bal"].sum()),
                   "share_of_us_balance": float(n["bal"].sum() / L["bal"].sum()),
                   "gap": float(ta["gap"].sum()),
                   "gap_share_la": float(ta.loc[ta["gap"] > 0, "bal"].sum() / ta["bal"].sum()) if len(ta) else None,
                   "gap_share_us": float(tn.loc[tn["gap"] > 0, "bal"].sum() / tn["bal"].sum()) if len(tn) else None})
    out["by_type"] = by
    years = ["past due"] + [str(y) for y in range(D.year, D.year + 10)]
    bucket = np.where(m["mat"] < D, "past due", m["mat"].dt.year.astype("Int64").astype(str))
    pv = m.assign(b=bucket).pivot_table(index="b", columns="chart_type", values="bal", aggfunc="sum").reindex(years).fillna(0)
    types = [t for t in export.CHART_TYPES if t in pv.columns]
    out["wall"] = {"buckets": years, "types": types, "balance": {t: [float(v) for v in pv[t]] for t in types}}
    out["bands"] = {"la": [float((m["band"] == k).mean()) for k in range(5)],
                    "us": [float((L["band"] == k).mean()) for k in range(5)]}
    u = x["uw"]
    ul = u[u["whole_loan_id"].isin(m["id"])]
    out["scenarios"] = {s: {"gap": float(g["refi_gap"].sum()), "loans_with_gap": int((g["refi_gap_pct"] > 0).sum()),
                            "bid_below_balance": int((g["refinanceable_by_sale"] == False).sum())}  # noqa: E712
                        for s, g in ul.groupby("scenario")}
    R = pd.DataFrame(rows)
    R["la"] = R["county_fips"].isin(list(COUNTIES))
    own = R[R["bench_kind"].eq("own type") & R["spread_sec_raw"].notna()]
    out["cap_spreads"] = [{"type": t, "la_loans": int(g["la"].sum()),
                           "la_median": float(g.loc[g["la"], "spread_sec_raw"].median()) if g["la"].sum() >= 10 else None,
                           "us_median": float(g["spread_sec_raw"].median())} for t, g in own.groupby("group")]
    base = ul[ul["scenario"].eq("base")]
    la_city = base[base["jurisdiction"].eq("la_city")]
    Rl = R[R["la"]]
    cap = Rl["rent_cap"].astype(float)
    growth = engine.par(P, "noi_growth", "multifamily") / 100
    metro = Rl["mf_rent_growth_metro"].astype(float).fillna(growth)
    binds = cap < np.maximum(growth, metro)          # a cap below the growth path changes the cash flows
    out["rules"] = {
        "la_city_loans": int(Rl["jurisdiction"].eq("la_city").sum()),
        "ula_upper_at_exit": int((la_city["exit_cost_rate"] >= 0.0749).sum()),
        "ula_lower_at_exit": int(((la_city["exit_cost_rate"] > 0.059) & (la_city["exit_cost_rate"] < 0.0749)).sum()),
        "prop13_loans": int(Rl["tax_current"].notna().sum()),
        "prop13_multi_property": int(Rl["jurisdiction"].eq("multi_property").sum()),
        "prop13_no_appraisal": int((Rl["tax_current"].isna() & ~Rl["jurisdiction"].eq("multi_property")).sum()),
        "rso_loans": int(cap.between(0.029, 0.031).sum()), "rso_binding": int((cap.between(0.029, 0.031) & binds).sum()),
        "rstpo_loans": int((cap < 0.02).sum()), "rstpo_binding": int(((cap < 0.02) & binds).sum()),
        "ab1482_loans": int(((cap > 0.08) & np.isfinite(cap)).sum()),
        "ab1482_binding": int(((cap > 0.08) & np.isfinite(cap) & binds).sum()),
        "mf_growth": growth,
    }
    return out


WLA, HW = "Los Angeles County / West Los Angeles", "Los Angeles County / Hollywood/Wilshire Corridor"
STR = "Los Angeles County (STR Los Angeles, CA market)"
COMPONENT = {"risk": "risk", "gap": "refinance gap", "discount": "discount to the balance",
             "returns": "return to a buyer at market value", "tier": "confidence tier", "size": "loan size"}
NARRATIVE = {
    "WL2725d11c7fb2": {
        "why": "Highest review priority among the market's office loans; it ranks high on {top3}.",
        "story": "A {sqft} square-foot office building from {year_built}, {occ} occupied against {occ_sec} when the loan "
                 "was securitized. Its latest NOI, {noi} a year, is annualized from the first six months of 2026; the "
                 "filing before reported {noi_prev} for a full year, so part of the drop may be seasonal. The loan, "
                 "interest-only at {coupon}, comes due on {maturity}. The maturity model ranks it {rk_f} of {n_f} office "
                 "loans near maturity (estimate {pf}, 90% interval {pf_lo} to {pf_hi}); the rank is the more reliable "
                 "reading.",
        "test": "At the office debt-yield floor of 12.5%, a lender would size a new loan at {p_max}, leaving a refinance "
                "gap of {gap} on a whole-loan balance of {bal}. Capitalizing {noi_cap} of NOI at {cap}{tax_note} gives a "
                "value of {value}. The bid is {bid}, {disc} below the balance; in the downside it falls to {bid_dn}.",
        "local": "West Hollywood sits between two CBRE survey regions: West Los Angeles ({c_wla_v} vacancy, {c_wla_r} a "
                 "square foot a month) and the Hollywood/Wilshire Corridor ({c_hw_v}, {c_hw_r}). The filings don't say "
                 "which one the building belongs to.",
        "risks": "The filing reports no NOI at securitization, so the cap rate is the national office benchmark, not a "
                 "spread over this building's own appraisal; a 2013 West Hollywood building may trade tighter, which "
                 "would raise the value (the tear sheet shows the cap-rate sensitivity). Two of the three listed "
                 "tenants, about {roll_share} of the area, have leases ending in February 2029: the return bid already "
                 "charges for re-leasing that space in year three, while the value bid doesn't, one reason the return "
                 "bid is the lower of the two. The whole-loan balance is estimated: this trust holds a {orig} note of a "
                 "larger loan split across trusts (pari passu).",
        "cites": [("overall_vacancy_rate", "office", WLA, "2026Q3", "CBRE", "c_wla_v"),
                  ("avg_asking_rent", "office", WLA, "2026Q3", "CBRE", "c_wla_r"),
                  ("overall_vacancy_rate", "office", HW, "2026Q3", "CBRE", "c_hw_v"),
                  ("avg_asking_rent", "office", HW, "2026Q3", "CBRE", "c_hw_r")],
    },
    "WLbf79352ce0cd": {
        "why": "Highest review priority among the market's multifamily loans; it ranks high on {top3}, while its own "
               "risk ranks lower.",
        "story": "{units} apartments built in {year_built} in the City of Los Angeles, carrying {bal} of whole-loan debt, "
                 "{per_unit} a unit. The five-year interest-only loan pays {coupon} and matures on {maturity}. Occupancy "
                 "is {occ} against {occ_sec} at securitization, and NOI of {noi} runs below the {noi_sec} underwritten "
                 "then. Its 12-month distress probability of {pd} ranks {rk_d} of {n_type} multifamily loans; the "
                 "model's top drivers are the short loan term and the debt per unit.",
        "test": "At today's {refi_rate} refinance rate the debt service coverage test binds at {p_max}, a gap of {gap}. "
                "Capitalizing {noi_cap} of NOI at {cap}{tax_note} gives a value of {value}, and the bid is {bid}, {disc} "
                "below the balance ({bid_dn} in the downside). A sale in the City of Los Angeles pays Measure ULA: the "
                "modeled sale at the end of a five-year hold clears the indexed upper threshold, so it pays {ula} of the "
                "whole price on top of ordinary selling costs.",
        "local": "Los Angeles County multifamily vacancy is {c_mf_vac} (Kidder Mathews, CoStar data) and asking rents "
                 "rose {c_mf_rent} in a year. Permits for units in buildings of five or more nearly doubled: {c_bps_26} "
                 "units authorized from January to September 2026 against {c_bps_25} a year earlier (Census Bureau), "
                 "supply that would arrive from about 2028.",
        "risks": "Built after October 1978 and less than 15 years old, the building falls under neither the City's rent "
                 "ordinance nor the state cap, so the model caps no rent growth; a new rent rule would lower the sale "
                 "price. At {per_unit} of debt a unit, there is little room if new supply lands nearby.",
        "cites": [("vacancy_rate", "multifamily", "Los Angeles County", "2026Q3", "Kidder", "c_mf_vac"),
                  ("avg_asking_rent_change_yoy", "multifamily", "Los Angeles County", "2026Q3", "Kidder", "c_mf_rent"),
                  ("housing_units_authorized_5plus", "new_supply", "Los Angeles County", "2026 Jan-Sep", "U.S. Census", "c_bps_26"),
                  ("housing_units_authorized_5plus", "new_supply", "Los Angeles County", "2025 Jan-Sep", "U.S. Census", "c_bps_25")],
    },
    "WL5194ef124566": {
        "why": "Highest review priority among the market's retail and industrial loans; it ranks high on {top3}.",
        "story": "A {sqft} square-foot industrial property near downtown Los Angeles, built in {year_built}. Occupancy has "
                 "fallen to {occ} from {occ_sec} at securitization, annualized NOI to {noi}, and reported debt service "
                 "coverage to {dscr}. The servicer reports advances outstanding, yet the loan still files as performing. "
                 "The interest-only loan pays {coupon} and matures on {maturity}. Its 12-month distress probability of "
                 "{pd} looks low for these facts, but it ranks {rk_d} of {n_type} industrial loans, in the riskiest "
                 "{rank_pct}; the rank is the more reliable reading.",
        "test": "On in-place income a lender would lend {p_max} against a balance of {bal}: a gap of {gap}. Capitalizing "
                "{noi_cap} of NOI at the industrial benchmark of {cap}{tax_note} gives a value of {value}, and the bid "
                "of {bid} is {disc} below the balance.",
        "local": "Los Angeles County industrial vacancy runs from {c_ind_cw} (Cushman & Wakefield) to {c_ind_kidder} "
                 "direct (Kidder Mathews), with CBRE at {c_ind_cbre}. At {occ} occupied, this building's trouble is its "
                 "own, not the market's.",
        "risks": "Valuing a building this empty on in-place NOI understates what it would be worth leased: at the "
                 "market's 95% occupancy its rent roll would be about {lease_up_x} today's, before the cost of releasing "
                 "a building built in {year_built}. The filing names it a portfolio but files one property record, and "
                 "NOI at securitization is reported as zero, so there is no appraisal spread to carry forward.",
        "cites": [("overall_vacancy_rate", "industrial", "Los Angeles County", "2026Q3", "Cushman", "c_ind_cw"),
                  ("overall_vacancy_rate", "industrial", "Los Angeles County", "2026Q3", "CBRE", "c_ind_cbre"),
                  ("direct_vacancy_rate", "industrial", "Los Angeles County", "2026Q3", "Kidder", "c_ind_kidder")],
    },
    "WL70bd49d7ed10": {
        "why": "Among performing loans with a debt yield under 8% (the debt-yield rule at 8%), the lowest 12-month "
               "distress probability.",
        "story": "A self-storage facility in Torrance, {units} units, built in {year_built}, {occ_last} occupied in the "
                 "latest report. The loan pays {coupon}, interest only, until {maturity}. Its 12-month distress "
                 "probability is {pd}.",
        "test": "The rule flagged a 2.1% debt yield. That figure was an error in the data: the latest filing reported "
                "three months of NOI ({noi_quarter}) that the cleaning step read as a full year. A later fix (decision "
                "D059) restored the year in the underwriting inputs ({noi}, a debt yield of {dy_fixed}) but not in the "
                "models' inputs, which the rule also reads, so the rule still flags this loan and the models still see "
                "the quarter. On the restored NOI, a lender would lend {p_max} against {bal}, a gap of {gap}. The bid is {bid}; {sale}",
        "local": "No public survey covers Los Angeles self-storage. Nationally, Public Storage guided 2026 same-store "
                 "revenue to 0 to 0.5% and Extra Space Storage to 2.0 to 2.5%, which set the model's growth path for the "
                 "type.",
        "risks": "Its confidence tier is B rather than the A that self-storage normally gets, because the NOI was "
                 "annualized from fewer than six months. The distress model rated the loan safe even on the bad NOI, "
                 "because its NOI inputs carry little weight. A debt-yield screen on raw filings can be wrong for "
                 "reasons that have nothing to do with the property.",
        "cites": [],
        "ucites": [167, 168],
    },
    "WL339ae594e8a7": {
        "why": "The widest disagreement between the distress model's rank and the debt-yield rule's rank.",
        "story": "A {units}-room hotel in Van Nuys, built in {year_built}, {occ} occupied, with annualized NOI of {noi} "
                 "against a {bal} loan: a debt yield of {dy} and debt service coverage of {dscr}. The debt-yield rule "
                 "rates it among the safest loans in the market. The distress model ranks it {rk_d} of {n_type} lodging "
                 "loans ({pd} probability), driven by the loan rather than the hotel: a five-year term, a {coupon} coupon "
                 "and a maturity {mat_months} months away. The maturity model's estimate is {pf}.",
        "test": "At today's terms the engine finds no refinance gap. Lodging gets a value bid only (confidence tier C, no "
                "cash-flow model): capitalizing {noi_cap} of NOI at {cap}{tax_note} gives a value of {value} and a "
                "bid of {bid}; {sale}",
        "local": "Hotels in the Los Angeles market ran {c_occ} occupancy at an average daily rate of {c_adr} in the third "
                 "quarter of 2026, with revenue per available room up {c_revpar_chg} on the year (STR data via Cushman "
                 "& Wakefield).",
        "risks": "Here the debt-yield rule looks right and the model's loan-term inputs over-flag: the model learned "
                 "that short, high-coupon loans run into distress more often, but this property's coverage is far above "
                 "any refinance test. One strong quarter is not a run rate, and a hotel built in {year_built} may need "
                 "capital spending the filings don't show.",
        "cites": [("occupancy_rate", "lodging", STR, "2026Q3", "Cushman", "c_occ"),
                  ("adr", "lodging", STR, "2026Q3", "Cushman", "c_adr"),
                  ("revpar_change_yoy", "lodging", STR, "2026Q3", "Cushman", "c_revpar_chg")],
    },
}
LESSONS = {
    "WL2725d11c7fb2": "Model and rules agree: a half-empty office building near maturity at today's rates.",
    "WLbf79352ce0cd": "A new building can be a refinance problem without being a credit problem: the gap comes from rates "
                      "and the debt per unit, not from the property.",
    "WL5194ef124566": "The model's probability level understates trouble that its rank and the filings make plain.",
    "WL70bd49d7ed10": "The data itself misled: a quarter's NOI read as a year made a sound loan look dangerous to the rule.",
    "WL339ae594e8a7": "Where the model and the rule part, the filings side with the rule: the property covers its debt "
                      "three times over, and the model is reacting to the loan's terms.",
}


def _date(v) -> str:
    t = pd.Timestamp(v)
    return f"{t.strftime('%B')} {t.day}, {t.year}"


def case_context(lid: str, x: dict, L: pd.DataFrame, rows_by_id: dict, lc: Local, comp: pd.DataFrame) -> tuple:
    r = L.set_index("id").loc[lid]
    shard = json.loads((export.OUT / "history" / f"{lid[2:4]}.json").read_text(encoding="utf-8"))["loans"][lid]
    f, s = shard["facts"], shard["series"]
    u = x["uw"].set_index(["whole_loan_id", "scenario"])
    b, dn = u.loc[(lid, "base")], u.loc[(lid, "downside")]
    P = rows_by_id[lid]
    noi_vals = [v for v in s["noi"] if v is not None]
    occ_vals = [v for v in s["occ"] if v is not None]
    roll = None
    if f.get("sqft"):
        late = sum(P.get(f"tenant{i}_sqft") or 0 for i in (1, 2, 3)
                   if str(P.get(f"tenant{i}_lease_exp") or "")[:7] == "2029-02")
        roll = late / f["sqft"] if late else None
    n_f = int(L[L["type"].eq(r["type"]) & L["pf"].notna()].shape[0])
    c = comp.loc[lid].drop("risk", errors="ignore") if lid in comp.index else pd.Series(dtype=float)
    top = [COMPONENT[k] for k in c.sort_values(ascending=False).index[:3]] if len(c) else []
    bal = r["bal"]
    covers = b["bid"] >= bal
    sale = (f"a sale at that bid would cover the {_m(bal)} balance." if covers
            else f"a sale at that bid would fall {_m(bal - b['bid'])} short of the {_m(bal)} balance.")
    ctx = {
        "sqft": f"{int(f['sqft']):,}" if f.get("sqft") else "n/a", "units": f"{int(f['units']):,}" if f.get("units") else "n/a",
        "year_built": f.get("year_built") or "n/a", "occ": _p(r["occ"], 0), "occ_sec": _p(f.get("occ_sec"), 0),
        "occ_last": _p(occ_vals[-1], 0) if occ_vals else "n/a", "noi": _m(P["noi"]), "noi_cap": _m(b["noi_stressed"]),
        "noi_prev": _m(noi_vals[-2]) if len(noi_vals) > 1 else "n/a", "noi_sec": _m(f.get("noi_sec") or 0),
        "noi_quarter": _m(P["noi"] / 4), "coupon": _p(f["coupon"], 2), "maturity": _date(f["maturity"]),
        "pf": _p(r["pf"], 0), "pf_lo": _p(r["pf_lo"], 0), "pf_hi": _p(r["pf_hi"], 0), "pd": _p(r["pd"], 1),
        "rk_f": f"{int(r['rk_f']):,}" if pd.notna(r["rk_f"]) else "n/a", "n_f": f"{n_f:,}",
        "rk_d": f"{int(r['rk_d']):,}" if pd.notna(r["rk_d"]) else "n/a", "n_type": f"{int(r['n_type']):,}",
        "rank_pct": _p(r["rk_d"] / r["n_type"], 0) if pd.notna(r["rk_d"]) else "n/a",
        "bal": _m(bal), "per_unit": f"${_r(bal / f['units'] / 1e6, 2)}M" if f.get("units") else "n/a",
        "orig": _m(f["orig_amount"]), "dscr": f"{_r(r['dscr'], 2)}x" if pd.notna(r["dscr"]) else "n/a",
        "dy": _p(r["dy"], 1), "dy_fixed": _p(P["noi"] / bal, 1), "p_max": _m(b["p_max"]), "gap": _m(b["refi_gap"]),
        "value": _m(b["value"]), "bid": _m(b["bid"]), "bid_dn": _m(dn["bid"]), "disc": _p(b["discount"], 0),
        "cap": _p(b["cap_rate"], 2), "refi_rate": _p(b["refi_rate"], 2), "sale": sale, "tax_note": "",
        "ula": _p(b["exit_cost_rate"] - 0.02, 1) if pd.notna(b["exit_cost_rate"]) else "n/a",
        "mat_months": int(round((pd.Timestamp(f["maturity"]) - pd.Timestamp(x["market"]["date"])).days / 30.4375)),
        "roll_share": _p(roll, 0), "top3": ", ".join(top[:-1]) + (" and " + top[-1] if len(top) > 1 else "".join(top)),
        "lease_up_x": f"{_r(0.95 / r['occ'], 1)} times" if pd.notna(r["occ"]) and r["occ"] > 0 else "n/a",
    }
    # value = NOI / cap rate exactly unless a buyer's Proposition 13 tax change moves it
    if abs(b["value"] * b["cap_rate"] - b["noi_stressed"]) > 1:
        ctx["tax_note"] = ", net of the buyer's property tax reset under Proposition 13,"
    cites = []
    for metric, ptype, geo, period, pub, key in NARRATIVE[lid]["cites"]:
        cc = lc.get(metric, ptype, geo, period, pub)
        unit = str(cc["unit"])
        if "USD/sf" in unit:
            ctx[key] = f"${cc['value']:,.2f}"
        elif metric in ("adr", "revpar"):
            ctx[key] = f"${cc['value']:,.0f}"
        elif metric.startswith("housing"):
            ctx[key] = f"{cc['value']:,.0f}"
        else:
            ctx[key] = f"{cc['value']:.1f}%"
        cites.append(cc)
    if NARRATIVE[lid].get("ucites"):
        u_rows = pd.read_csv(paths.CONFIG_DIR / "research" / "underwriting_sources.csv")
        for n in NARRATIVE[lid]["ucites"]:
            ur = u_rows.iloc[n - 1]
            cites.append({"value": float(ur["value_low"]), "unit": ur["unit"], "publisher": ur["source_publisher"],
                          "date": ur["publication_date"], "url": ur["url"], "row": n, "file": "underwriting_sources.csv"})
    facts = {"name": f.get("name"), "address": ", ".join(str(v) for v in (f.get("address"), f.get("city"), f.get("state")) if v),
             "type": r["type"], "trust": r["trust"], "status": r["status"]}
    return ctx, cites, facts


def summary_lines(out: dict) -> list[str]:
    mk = out["market"]
    sc = mk["scenarios"]
    office = next((t for t in mk["by_type"] if t["type"] == "office"), None)
    return [
        f"The Los Angeles-Long Beach-Anaheim metro holds {mk['loans']:,} of the scored loans, {_m(mk['balance'])} of "
        f"whole-loan balance ({_p(mk['share_of_national_balance'])} of the {_m(mk['national_balance'])} national total).",
        f"By the model's estimate, these loans owe {_m(sc['base']['gap'])} more than lenders would refinance at today's "
        f"terms, across {sc['base']['loans_with_gap']:,} loans ({_m(sc['downside']['gap'])} in the downside)."
        + (f" Office is {_p(office['share_of_la_balance'], 0)} of the market's balance and {_m(office['gap'])} of the gap."
           if office else "")
        + " The gap measures how much new equity a refinance would need; it is not a forecast of defaults.",
        f"{mk['rules']['la_city_loans']:,} loans sit inside the City of Los Angeles, where Measure ULA taxes the whole "
        f"price of a large sale: the modeled sale at the end of a five-year hold pays 5.5% for "
        f"{mk['rules']['ula_upper_at_exit']:,} of them and 4% for {mk['rules']['ula_lower_at_exit']:,}.",
        "Five case files show where the screen and simple rules agree, where they part, and where the data itself "
        "misleads.",
    ]


def rerun_note(changed: list, cand: pd.DataFrame) -> str:
    """What the committed rule picks when rerun on today's outputs, said plainly."""
    head = ("Two fixes came after the selection was committed: three-month NOI that had been read as a full year was "
            "corrected in the underwriting inputs (decision D059), and the seller's estimated property tax was capped at "
            "the tax on current value (Proposition 8, decision D064). ")
    if not changed:
        return head + "Rerun on the corrected outputs, the rule picks the same five loans."
    parts = []
    for lab, old, new in changed:
        slot = lab.split(". ", 1)[1].split(" by ")[0].lower().replace("top ", "")
        why = (f" The Proposition 8 cap lowered {cand.loc[new, 'name']}'s estimated value and put its bid below the "
               "balance, which raised its discount and gap ranks." if new == "WL1263a0857232" else "")
        parts.append(f"for {slot} it now picks {cand.loc[new, 'name']} (review priority {cand.loc[new, 'opp']:.1f}, "
                     f"against {cand.loc[old, 'opp']:.1f} for the committed pick, {cand.loc[old, 'name']}).{why}")
    n = len(changed)
    return (head + f"Rerun on the corrected outputs, the rule picks the same loans in {['five', 'four', 'three', 'two', 'one', 'none'][n]} of five slots; "
            + " ".join(parts) + " The case files keep the committed picks: swapping one after seeing the results would "
            "undo the point of writing the rule down first.")


def write_memo(out: dict, meta: dict) -> None:
    r = out["market"]["rules"]
    lines = [
        "# Los Angeles: the case study memo", "",
        f"Screening research, not investment advice. Bids are indicative economic values for the property, not offers for "
        f"the loan. Data through {meta['data_cutoff']}; values as of {meta['valuation_date']}. Every number below is a "
        "cell of the project's published outputs or a figure from a cited source.", "",
        "## Summary", "", *[f"- {s}" for s in out["summary"]], "",
        "## Three local rules", "",
        f"- Measure ULA: a sale inside the City of Los Angeles above $5.4 million pays 4% of the whole price, and 5.5% at "
        f"$10.9 million or more (thresholds from July 1, 2026, indexed yearly), on top of the usual city and county "
        f"transfer taxes. The model charges it on the modeled sale at the end of the hold: {r['ula_upper_at_exit']} loans "
        f"at 5.5%, {r['ula_lower_at_exit']} at 4%.",
        f"- Proposition 13: a purchase resets the property tax to the price. The seller's tax is estimated from the "
        f"appraisal at securitization grown 2% a year, capped at the tax on today's value (Proposition 8), and the buyer's "
        f"tax follows its own price. Applied to {r['prop13_loans']} loans; {r['prop13_multi_property']} multi-property "
        f"loans and {r['prop13_no_appraisal']} without an appraisal date are left out.",
        f"- Rent caps: 3% under the City's rent ordinance ({r['rso_loans']} loans), 1.919% in unincorporated Los Angeles "
        f"County ({r['rstpo_loans']}), and the state's 8.7% ({r['ab1482_loans']}). Against the model's "
        f"{_p(r['mf_growth'], 1)} growth path only caps below it change the cash flows: {r['rso_binding']}, "
        f"{r['rstpo_binding']} and {r['ab1482_binding']} loans respectively. The two local ordinances also rule out the "
        "renovation program.", "",
        "## Case files", "",
    ]
    for c in out["cases"]:
        lines += [f"### {c['label']}: {c['facts']['name']}", "", f"{c['facts']['address']}. {c['why']}", "",
                  c["story"], "", c["test"], "", f"Local context: {c['local']}", "", f"What would make this wrong: {c['risks']}", ""]
        uniq = list(dict.fromkeys((x["publisher"], x["date"], x["url"]) for x in c["cites"]))
        if uniq:
            lines += ["Sources: " + "; ".join(f"{p}, {d} ({u})" for p, d, u in uniq), ""]
        lines += [f"Tear sheet: search \"{c['facts']['name']}\" on the site's Loans page.", ""]
    lines += ["## What the five cases show", "", *[f"- {c['facts']['name']}: {LESSONS[c['id']]}" for c in out["cases"]], "",
              "## Method and limits", "",
              f"The selection rule and the full candidate list ({REPO}/docs/la/selection.md and "
              f"{REPO}/docs/la/candidates.csv) were committed to the repository ({out['selection']['commit']}) before any "
              f"case file was drafted. {out['selection']['rerun_note']} The decisions are in {REPO}/docs/decisions.md.",
              "", "Local market figures name their publisher, because brokerages measure different building universes and "
              "their figures for one market can differ by several points.", ""]
    (DOCS / "memo.md").write_text("\n".join(lines), encoding="utf-8")


def build(log=print) -> dict:
    x = export.load()
    L = export.loans_table(x)
    P = engine.load_params()
    rows = engine.prepare(x["inputs"], P)
    rows_by_id = {r["whole_loan_id"]: r for r in rows}
    base = x["uw"][x["uw"]["scenario"].eq("base")].reset_index(drop=True)
    comp = run.components(base).set_axis(base.loc[base["bid"].notna(), "whole_loan_id"].to_numpy())
    lc = Local()
    out = {"market": market_tables(x, L, rows, P), "local": local_context(lc), "cases": []}
    for label, lid in picks():
        ctx, cites, facts = case_context(lid, x, L, rows_by_id, lc, comp)
        n = NARRATIVE[lid]
        out["cases"].append({"id": lid, "label": display_label(label), "why": n["why"].format(**ctx), "facts": facts,
                             "n_f": int(ctx["n_f"].replace(",", "")),
                             "cites": cites, "lesson": LESSONS[lid],
                             **{k: n[k].format(**ctx) for k in ("story", "test", "local", "risks")}})
    commit = subprocess.run(["git", "log", "-1", "--format=%h on %ad", "--date=short", "--", "docs/la/selection.md"],
                            capture_output=True, text=True, cwd=paths.REPO_ROOT).stdout.strip()
    cand = candidates(x).set_index("id")
    now = [r["id"] for _, r in select(cand.reset_index())]
    committed = picks()
    changed = [(lab, old, new) for (lab, old), new in zip(committed, now) if old != new]
    out["selection"] = {"rule": "docs/la/selection.md", "commit": commit, "same_on_rerun": not changed,
                        "rerun_note": rerun_note(changed, cand)}
    out["summary"] = summary_lines(out)
    meta = export.meta_block(x)
    export.write("la.json", out, meta)
    write_memo(out, meta)
    log(f"LA: {out['market']['loans']} loans, {len(out['cases'])} case files -> la.json, docs/la/memo.md")
    return out
