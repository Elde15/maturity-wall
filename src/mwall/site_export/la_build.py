"""Los Angeles case study, built after the selection commit (SOP 13 steps 2, 3, 6 and 7).

    python -m mwall la      # site/public/data/la.json and docs/la/memo.md

Every number in a case file comes from the published outputs or a cited row of config/research/la_market_sources.csv;
the narratives below are templates whose numbers are filled from those cells.
"""
from __future__ import annotations

import json
import subprocess

import numpy as np
import pandas as pd

from mwall.common import paths
from mwall.site_export import export
from mwall.site_export.la import COUNTIES, DOCS, Local, candidates, local_context, market, select
from mwall.underwrite import engine


def _m(v) -> str:
    if v is None or pd.isna(v):
        return "n/a"
    if abs(v) >= 1e9:
        return f"${v / 1e9:,.1f}B"
    return f"${v / 1e6:,.1f}M" if abs(v) >= 1e6 else f"${v / 1e3:,.0f}K"


def _p(v, d: int = 1) -> str:
    return "n/a" if v is None or pd.isna(v) else f"{100 * v:.{d}f}%"


def picks() -> list[tuple[str, str]]:
    """The committed picks, read back from docs/la/selection.md so the page can't drift from the record."""
    import re

    text = (DOCS / "selection.md").read_text(encoding="utf-8")
    return [(m.group(1), m.group(2)) for m in re.finditer(r"^- (\d\. [^:]+): .*?`(WL[0-9a-f]+)`", text, re.M)]


def _bands(L: pd.DataFrame) -> pd.Series:
    """Same rule as site/src/lib/risk.js."""
    pdv = np.sort(L["pd"].dropna().to_numpy())
    q = lambda p: pdv[min(len(pdv) - 1, int(np.floor(p * len(pdv))))]  # noqa: E731
    q80, q95 = q(0.8), q(0.95)
    dist = L["status"].isin(export.DISTRESSED)
    b = np.where(dist, 4, np.where(L["pf"].notna(), np.where(L["pf"] >= 0.5, 3, np.where(L["pf"] >= 0.25, 2, 1)),
                 np.where(L["pd"].notna(), np.where(L["pd"] >= q95, 3, np.where(L["pd"] >= q80, 2, 1)), 0)))
    return pd.Series(b, index=L.index)


def market_tables(x: dict, L: pd.DataFrame, rows: list[dict]) -> dict:
    D = pd.Timestamp(x["market"]["date"])
    L = L.assign(band=_bands(L), chart_type=L["type"].replace({"mixed_use": "mixed_other", "other": "mixed_other"}))
    m = L.loc[market(L).index]
    out = {"loans": int(len(m)), "balance": float(m["bal"].sum()),
           "counties": [{"county": COUNTIES[c], "loans": int((m["county"] == c).sum()),
                         "balance": float(m.loc[m["county"] == c, "bal"].sum())} for c in COUNTIES],
           "ca_outside": int((L["state"].eq("CA") & ~L["county"].isin(COUNTIES)).sum()),
           "share_of_national_balance": float(m["bal"].sum() / L["bal"].sum())}
    tested = lambda d: d[d["gap"].notna()]  # noqa: E731
    by = []
    for t in export.CHART_TYPES:
        a, n = m[m["chart_type"] == t], L[L["chart_type"] == t]
        if not len(a):
            continue
        ta, tn = tested(a), tested(n)
        by.append({"type": t, "loans": int(len(a)), "balance": float(a["bal"].sum()),
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
    cap = R["rent_cap"].astype(float)
    out["rules"] = {
        "la_city_loans": int((R["la"] & R["jurisdiction"].eq("la_city")).sum()),
        "ula_upper_at_exit": int((la_city["exit_cost_rate"] >= 0.0749).sum()),
        "ula_lower_at_exit": int(((la_city["exit_cost_rate"] > 0.059) & (la_city["exit_cost_rate"] < 0.0749)).sum()),
        "prop13_loans": int((R["la"] & R["tax_current"].notna()).sum()),
        "rso_loans": int((R["la"] & cap.between(0.029, 0.031)).sum()),
        "rstpo_loans": int((R["la"] & (cap < 0.02)).sum()),
        "ab1482_loans": int((R["la"] & (cap > 0.08) & np.isfinite(cap)).sum()),
    }
    return out


WLA, HW = "Los Angeles County / West Los Angeles", "Los Angeles County / Hollywood/Wilshire Corridor"
STR = "Los Angeles County (STR Los Angeles, CA market)"
NARRATIVE = {
    "WL2725d11c7fb2": {
        "why": "Highest opportunity score among the market's office loans.",
        "story": "A {sqft} square-foot office building from {year_built}, {occ} occupied against {occ_sec} when the loan "
                 "was securitized. Annualized NOI fell to {noi} in the latest filing from {noi_prev} the month before, "
                 "and the loan, interest-only at {coupon}, comes due on {maturity}. The maturity model puts the chance it "
                 "fails to pay off then at {pf} (90% interval {pf_lo} to {pf_hi}); among {n_type} office loans it ranks "
                 "{rk_d} on 12-month distress.",
        "test": "At the office debt-yield floor of 12.5%, a lender would size a new loan at {p_max}, leaving a refinance "
                "gap of {gap} on a whole-loan balance of {bal}. The engine values the building at {value} and bids "
                "{bid}, {disc} below the balance; in the downside the bid falls to {bid_dn}.",
        "local": "West Hollywood sits between two CBRE survey regions: West Los Angeles ({c_wla_v} vacancy, {c_wla_r} a "
                 "square foot a month) and the Hollywood/Wilshire Corridor ({c_hw_v}, {c_hw_r}). The filings don't say "
                 "which one the building belongs to.",
        "risks": "The filing reports no NOI at securitization, so the cap rate is the national office benchmark of "
                 "{cap}, not a spread over this building's own appraisal; a 2013 West Hollywood building may trade "
                 "tighter, which the cap-rate sensitivity on the tear sheet shows. Two of the three listed tenants, "
                 "about {roll_share} of the area, have leases ending in February 2029, after maturity. The whole-loan "
                 "balance is estimated: this trust holds a {orig} note of a larger pari passu loan.",
        "cites": [("overall_vacancy_rate", "office", WLA, "2026Q3", "CBRE", "c_wla_v"),
                  ("avg_asking_rent", "office", WLA, "2026Q3", "CBRE", "c_wla_r"),
                  ("overall_vacancy_rate", "office", HW, "2026Q3", "CBRE", "c_hw_v"),
                  ("avg_asking_rent", "office", HW, "2026Q3", "CBRE", "c_hw_r")],
    },
    "WLbf79352ce0cd": {
        "why": "Highest opportunity score among the market's multifamily loans.",
        "story": "{units} apartments built in {year_built} in the City of Los Angeles, carrying {bal} of whole-loan debt, "
                 "{per_unit} a unit. The five-year interest-only loan pays {coupon} and matures on {maturity}. Occupancy "
                 "is {occ} against {occ_sec} at securitization, and NOI of {noi} runs below the {noi_sec} underwritten "
                 "then. Its 12-month distress probability is {pd}, rank {rk_d} of {n_type} multifamily loans; the "
                 "model's top drivers are the short loan term and the debt per unit.",
        "test": "At today's {refi_rate} refinance rate the debt service coverage test binds at {p_max}, a gap of {gap}. "
                "The engine values the property at {value} and bids {bid}, {disc} below the balance ({bid_dn} in the "
                "downside). Selling in the City of Los Angeles adds Measure ULA: the modeled exit price clears the "
                "indexed upper threshold, so the sale pays {ula} of the whole price on top of ordinary selling costs.",
        "local": "Los Angeles County multifamily vacancy is {c_mf_vac} (Kidder Mathews, CoStar data) and asking rents "
                 "rose {c_mf_rent} in a year. Permits for units in buildings of five or more nearly doubled: {c_bps_26} "
                 "units authorized from January to September 2026 against {c_bps_25} a year earlier (Census Bureau), "
                 "supply that would arrive from about 2028.",
        "risks": "Built after October 1978 and less than 15 years old, the building falls under neither the City's rent "
                 "ordinance nor AB 1482, so the model caps no rent growth; a new rent rule would cut the exit price. At "
                 "{per_unit} of debt a unit, there is little room if new supply lands nearby.",
        "cites": [("vacancy_rate", "multifamily", "Los Angeles County", "2026Q3", "Kidder", "c_mf_vac"),
                  ("avg_asking_rent_change_yoy", "multifamily", "Los Angeles County", "2026Q3", "Kidder", "c_mf_rent"),
                  ("housing_units_authorized_5plus", "new_supply", "Los Angeles County", "2026 Jan-Sep", "U.S. Census", "c_bps_26"),
                  ("housing_units_authorized_5plus", "new_supply", "Los Angeles County", "2025 Jan-Sep", "U.S. Census", "c_bps_25")],
    },
    "WL5194ef124566": {
        "why": "Highest opportunity score among the market's retail and industrial loans.",
        "story": "A {sqft} square-foot industrial property near downtown Los Angeles, built in {year_built}. Occupancy has "
                 "fallen to {occ} from {occ_sec} at securitization, annualized NOI to {noi}, and reported debt service "
                 "coverage to {dscr}. The servicer reports advances outstanding, yet the loan still files as performing. "
                 "The interest-only loan pays {coupon} and matures on {maturity}. Its 12-month distress probability of "
                 "{pd} ranks {rk_d} of {n_type} industrial loans.",
        "test": "On in-place income a lender would lend {p_max} against a balance of {bal}: a gap of {gap}. Valued on that "
                "income at the industrial benchmark ({cap}), the property is worth {value}, and the bid of {bid} is "
                "{disc} below the balance.",
        "local": "Los Angeles County industrial vacancy runs from {c_ind_cbre} (CBRE) to {c_ind_kidder} direct (Kidder "
                 "Mathews). At {occ} occupied, this building's trouble is its own, not the market's.",
        "risks": "Valuing a building this empty on in-place NOI understates what it would be worth leased: at the "
                 "market's 95% occupancy its rent roll would be about {lease_up_x} today's, before the cost of releasing a "
                 "building built in {year_built}. The filing names it a portfolio but files one property record, and NOI "
                 "at securitization is reported as zero, so there is no appraisal spread to carry forward.",
        "cites": [("overall_vacancy_rate", "industrial", "Los Angeles County", "2026Q3", "CBRE", "c_ind_cbre"),
                  ("direct_vacancy_rate", "industrial", "Los Angeles County", "2026Q3", "Kidder", "c_ind_kidder")],
    },
    "WL70bd49d7ed10": {
        "why": "Among performing loans with a debt yield under 8% (the rule of thumb's warning), the lowest 12-month "
               "distress probability.",
        "story": "A self-storage facility in Torrance, {units} units, built in {year_built}, {occ_last} occupied in the "
                 "latest report. The loan pays {coupon}, interest only, until {maturity}. Its 12-month distress "
                 "probability is {pd}.",
        "test": "The rule of thumb flagged a 2.1% debt yield. That figure was an error in the data: the latest filing "
                "reported three months of NOI ({noi_quarter}) that the cleaning step read as a full year. With the year "
                "restored ({noi}; decision D059), the debt yield is {dy_fixed}. A refinance would still fall {gap} short "
                "(a lender would lend {p_max} against {bal}), but the bid of {bid} is above the balance: a sale would "
                "repay the loan.",
        "local": "No public survey covers Los Angeles self-storage. Nationally, Public Storage guided 2026 same-store "
                 "revenue to 0 to 0.5% and Extra Space Storage to 2.0 to 2.5%, which set the model's growth path for the "
                 "type.",
        "ucites": [167, 168],
        "risks": "The models still read the quarter as a year; their NOI inputs carry little weight, which is why the "
                 "distress model rated the loan safe anyway. The lesson runs the other way too: a debt-yield screen on "
                 "raw filings can be wrong for reasons that have nothing to do with the property.",
        "cites": [],
    },
    "WL339ae594e8a7": {
        "why": "The widest disagreement between the distress model's rank and the debt-yield rule's rank.",
        "story": "A {units}-room hotel in Van Nuys, built in {year_built}, {occ} occupied, with annualized NOI of {noi} "
                 "against a {bal} loan: a debt yield of {dy} and debt service coverage of {dscr}. The rule of thumb rates "
                 "it among the safest loans in the market. The distress model ranks it {rk_d} of {n_type} lodging loans "
                 "({pd}), driven by the loan rather than the hotel: a five-year term, a {coupon} coupon and a maturity "
                 "{mat_months} months away. The maturity model puts failure at {pf}.",
        "test": "The hotel would refinance easily: no gap at today's terms, and a value of {value} gives a bid of {bid}, "
                "about twice the balance. Lodging gets a direct-capitalization value only (confidence tier C).",
        "local": "Hotels in the Los Angeles market ran {c_occ} occupancy at an average daily rate of {c_adr} in the third "
                 "quarter of 2026, with revenue per available room up {c_revpar_chg} on the year (STR data via Cushman "
                 "& Wakefield).",
        "risks": "Here the debt-yield rule looks right and the model's loan-term inputs over-flag: the model learned "
                 "that short, high-coupon loans run into distress more often, but this property's coverage is far above any "
                 "refinance test. One strong quarter is not a run rate, and a hotel built in {year_built} invites "
                 "capital spending the filings don't show.",
        "cites": [("occupancy_rate", "lodging", STR, "2026Q3", "Cushman", "c_occ"),
                  ("adr", "lodging", STR, "2026Q3", "Cushman", "c_adr"),
                  ("revpar_change_yoy", "lodging", STR, "2026Q3", "Cushman", "c_revpar_chg")],
    },
}


def _date(v) -> str:
    t = pd.Timestamp(v)
    return f"{t.strftime('%B')} {t.day}, {t.year}"


def case_context(lid: str, x: dict, L: pd.DataFrame, rows_by_id: dict, lc: Local) -> tuple[dict, list[dict], dict]:
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
    ctx = {
        "sqft": f"{int(f['sqft']):,}" if f.get("sqft") else "n/a", "units": f"{int(f['units']):,}" if f.get("units") else "n/a",
        "year_built": f.get("year_built") or "n/a", "occ": _p(r["occ"], 0), "occ_sec": _p(f.get("occ_sec"), 0),
        "occ_last": _p(occ_vals[-1], 0) if occ_vals else "n/a", "noi": _m(P["noi"]),
        "noi_prev": _m(noi_vals[-2]) if len(noi_vals) > 1 else "n/a", "noi_sec": _m(f.get("noi_sec") or 0),
        "noi_quarter": _m(P["noi"] / 4), "coupon": _p(f["coupon"], 2), "maturity": _date(f["maturity"]),
        "pf": _p(r["pf"], 0), "pf_lo": _p(r["pf_lo"], 0), "pf_hi": _p(r["pf_hi"], 0), "pd": _p(r["pd"], 1),
        "rk_d": f"{int(r['rk_d']):,}" if pd.notna(r["rk_d"]) else "n/a", "n_type": f"{int(r['n_type']):,}",
        "bal": _m(r["bal"]), "per_unit": f"${r['bal'] / f['units'] / 1e6:,.2f}M" if f.get("units") else "n/a",
        "orig": _m(f["orig_amount"]), "dscr": f"{r['dscr']:.2f}x" if pd.notna(r["dscr"]) else "n/a",
        "dy": _p(r["dy"], 1), "dy_fixed": _p(P["noi"] / r["bal"], 1), "p_max": _m(b["p_max"]), "gap": _m(b["refi_gap"]),
        "value": _m(b["value"]), "bid": _m(b["bid"]), "bid_dn": _m(dn["bid"]), "disc": _p(b["discount"], 0),
        "cap": _p(b["cap_rate"], 2), "refi_rate": _p(b["refi_rate"], 2),
        "ula": _p(b["exit_cost_rate"] - 0.02, 1) if pd.notna(b["exit_cost_rate"]) else "n/a",
        "mat_months": int(round((pd.Timestamp(f["maturity"]) - pd.Timestamp(x["market"]["date"])).days / 30.4375)),
        "roll_share": _p(roll, 0),
        "lease_up_x": f"{0.95 / r['occ']:.1f} times" if pd.notna(r["occ"]) and r["occ"] > 0 else "n/a",
    }
    cites = []
    for metric, ptype, geo, period, pub, key in NARRATIVE[lid]["cites"]:
        c = lc.get(metric, ptype, geo, period, pub)
        unit = str(c["unit"])
        if "USD/sf" in unit:
            ctx[key] = f"${c['value']:,.2f}"
        elif metric in ("adr", "revpar"):
            ctx[key] = f"${c['value']:,.0f}"
        elif metric.startswith("housing"):
            ctx[key] = f"{c['value']:,.0f}"
        else:
            ctx[key] = f"{c['value']:.1f}%"
        cites.append(c)
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
        f"whole-loan balance ({_p(mk['share_of_national_balance'])} of the national total).",
        f"At today's terms, lenders would refinance {_m(sc['base']['gap'])} less than these loans owe, across "
        f"{sc['base']['loans_with_gap']:,} loans; in the downside, {_m(sc['downside']['gap'])}."
        + (f" Office is {_p(office['share_of_la_balance'], 0)} of the market's balance and {_m(office['gap'])} of its gap."
           if office else ""),
        f"{mk['rules']['la_city_loans']:,} loans sit inside the City of Los Angeles, where Measure ULA taxes the whole "
        f"price of a large sale: the modeled exit pays 5.5% for {mk['rules']['ula_upper_at_exit']:,} of them and 4% for "
        f"{mk['rules']['ula_lower_at_exit']:,}.",
        "Five case files, picked by a rule committed before any was drafted, show where the screen and simple rules "
        "agree, where they part, and where the data itself misleads.",
    ]


def write_memo(out: dict, meta: dict) -> None:
    lines = [
        "# Los Angeles: the case study memo", "",
        f"Screening research, not investment advice. Data through {meta['data_cutoff']}; values as of "
        f"{meta['valuation_date']}. Generated by `python -m mwall la` from the published outputs; every number below is a "
        "data cell or a cited source row.", "",
        "## Summary", "", *[f"- {s}" for s in out["summary"]], "",
        "## Case files", "",
    ]
    for c in out["cases"]:
        lines += [f"### {c['label']}: {c['facts']['name']}", "", f"{c['facts']['address']}. {c['why']}", "",
                  c["story"], "", c["test"], "", f"Local context: {c['local']}", "", f"Risks and data gaps: {c['risks']}", ""]
        if c["cites"]:
            lines += ["Sources: " + "; ".join(f"{x['publisher']}, {x['date']} ({x['url']}, row {x['row']})" for x in c["cites"]), ""]
        lines += [f"Tear sheet: /loan.html?id={c['id']}", ""]
    lines += ["## Method and limits", "",
              f"Selection rule and full candidate list: `docs/la/selection.md` and `docs/la/candidates.csv`, committed "
              f"{out['selection']['commit']} before any case file. After the commit, decision D059 corrected quarter "
              f"NOI read as annual in the underwriting inputs; rerun on the corrected data, the rule picks "
              f"{'the same five loans' if out['selection']['same_under_d059'] else 'a different set, and the memo keeps the committed one'}.",
              "", "Local transfer taxes, Proposition 13 and rent caps follow `config/la_overrides.csv`; local market figures "
              "follow `config/research/la_market_sources.csv`. Publishers measure different building universes, so the "
              "memo quotes ranges and names the publisher of each figure.", ""]
    (DOCS / "memo.md").write_text("\n".join(lines), encoding="utf-8")


def build(log=print) -> dict:
    x = export.load()
    L = export.loans_table(x)
    P = engine.load_params()
    rows = engine.prepare(x["inputs"], P)
    rows_by_id = {r["whole_loan_id"]: r for r in rows}
    lc = Local()
    out = {"market": market_tables(x, L, rows), "local": local_context(lc), "cases": []}
    for label, lid in picks():
        ctx, cites, facts = case_context(lid, x, L, rows_by_id, lc)
        n = NARRATIVE[lid]
        out["cases"].append({"id": lid, "label": label, "why": n["why"], "facts": facts, "cites": cites,
                             **{k: n[k].format(**ctx) for k in ("story", "test", "local", "risks")}})
    commit = subprocess.run(["git", "log", "-1", "--format=%h on %ad", "--date=short", "--", "docs/la/selection.md"],
                            capture_output=True, text=True, cwd=paths.REPO_ROOT).stdout.strip()
    now = [r["id"] for _, r in select(candidates(x))]
    out["selection"] = {"rule": "docs/la/selection.md", "commit": commit, "same_under_d059": now == [i for _, i in picks()]}
    out["summary"] = summary_lines(out)
    meta = export.meta_block(x)
    export.write("la.json", out, meta)
    write_memo(out, meta)
    log(f"LA: {out['market']['loans']} loans, {len(out['cases'])} case files -> la.json, docs/la/memo.md")
    return out
