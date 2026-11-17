"""Los Angeles case study (SOP 13): market definition, case-file selection, market tables for the site.

    python -m mwall la --select     # writes docs/la/selection.md and docs/la/candidates.csv (commit before case files)
    python -m mwall la              # writes site/public/data/la.json

Market: the Los Angeles-Long Beach-Anaheim metro (CBSA 31080), which the OMB July 2023 delineation file defines as
Los Angeles County (06037) and Orange County (06059). Properties are assigned by county FIPS from the geocoder, never by
ZIP prefix.
"""
from __future__ import annotations

import datetime as dt

import numpy as np
import pandas as pd

from mwall.common import paths
from mwall.site_export import export

DOCS = paths.REPO_ROOT / "docs" / "la"
COUNTIES = {"06037": "Los Angeles", "06059": "Orange"}
DY_RULE = 0.08   # the B1 debt-yield rule at 8% (a loan under 8% screens as risky)

RULE = """# Los Angeles case files: selection rule

Written and committed {date}, before any case file was drafted (SOP 13 step 5). The candidate list with every rank is
`docs/la/candidates.csv`, produced by `python -m mwall la --select` from the published outputs of {cutoff}.

**Market.** Loans whose property is in the Los Angeles-Long Beach-Anaheim metro (CBSA 31080: Los Angeles and Orange
counties, OMB July 2023 delineation), assigned by the geocoded county FIPS code.

**Eligible.** Single-property loans (multi-property loans can't be tied to one address or one set of local rules) with
a base-scenario value.

**Picks, in this order; a loan already picked is skipped:**

1. Office: the highest opportunity score among eligible office loans with a confidence tier of A or B.
2. Multifamily: the highest opportunity score among eligible multifamily loans with tier A or B.
3. Retail or industrial: the highest opportunity score among eligible retail and industrial loans with tier A or B.
4. Rated safe by the model, risky by a rule of thumb: among eligible performing loans with a debt yield under 8% (the
   B1 rule), the lowest 12-month distress probability.
5. The widest disagreement: among eligible performing loans with both a distress probability and a debt yield, the
   largest gap between the loan's percentile rank by distress probability and its percentile rank by debt yield
   (low debt yield = risky), both ranked within the market.

Ties go to the larger balance. Opportunity scores, tiers, probabilities and debt yields are the published values; none
were changed after this list was drawn.

## Result

{result}
"""


def market(L: pd.DataFrame) -> pd.DataFrame:
    return L[L["county"].isin(COUNTIES)].copy()


def candidates(x: dict) -> pd.DataFrame:
    L = export.loans_table(x)
    d = x["inputs"].set_index("whole_loan_id")
    m = market(L)
    m["n_properties"] = d["n_properties"].reindex(m["id"]).to_numpy()
    m["eligible"] = (m["n_properties"].fillna(1) <= 1) & m["value"].notna()
    perf = m["eligible"] & m["status"].eq("performing") & m["pd"].notna() & m["dy"].notna()
    m["rank_pd"] = np.where(perf, m.loc[perf, "pd"].rank(pct=True).reindex(m.index), np.nan)
    m["rank_dy_risk"] = np.where(perf, (-m.loc[perf, "dy"]).rank(pct=True).reindex(m.index), np.nan)
    m["disagreement"] = (m["rank_pd"] - m["rank_dy_risk"]).abs()
    return m


def select(m: pd.DataFrame) -> list[tuple[str, pd.Series]]:
    picked: list[tuple[str, pd.Series]] = []
    taken: set = set()

    def best(rows: pd.DataFrame, by: str, ascending: bool) -> pd.Series | None:
        rows = rows[~rows["id"].isin(taken)].sort_values([by, "bal"], ascending=[ascending, False])
        return rows.iloc[0] if len(rows) else None

    ab = m["eligible"] & m["tier"].isin(["A", "B"])
    rules = [
        ("1. Top office by opportunity score", m[ab & m["type"].eq("office")], "opp", False),
        ("2. Top multifamily by opportunity score", m[ab & m["type"].eq("multifamily")], "opp", False),
        ("3. Top retail or industrial by opportunity score", m[ab & m["type"].isin(["retail", "industrial"])], "opp", False),
        ("4. Model safe, debt-yield rule risky", m[m["eligible"] & m["status"].eq("performing") & (m["dy"] < DY_RULE)
                                                 & m["pd"].notna()], "pd", True),
        ("5. Widest model and debt-yield disagreement", m[m["disagreement"].notna()], "disagreement", False),
    ]
    for label, rows, by, asc in rules:
        r = best(rows, by, asc)
        if r is not None:
            picked.append((label, r))
            taken.add(r["id"])
    return picked


def write_selection(log=print) -> None:
    x = export.load()
    m = candidates(x)
    picks = select(m)
    DOCS.mkdir(parents=True, exist_ok=True)
    cols = ["id", "name", "city", "county", "type", "status", "tier", "bal", "opp", "pd", "pf", "dy", "rank_pd",
            "rank_dy_risk", "disagreement", "eligible", "n_properties"]
    m.sort_values(["type", "opp"], ascending=[True, False])[cols].to_csv(DOCS / "candidates.csv", index=False,
                                                                         float_format="%.6g")
    lines = []
    for label, r in picks:
        lines.append(f"- {label}: {r['name']} ({r['city']}, {COUNTIES[r['county']]} County), {r['type']}, "
                     f"`{r['id']}`, balance ${r['bal'] / 1e6:,.1f}M, opportunity score {r['opp']:.1f}, "
                     f"distress probability {'n/a' if pd.isna(r['pd']) else f'{r['pd']:.2%}'}, "
                     f"debt yield {'n/a' if pd.isna(r['dy']) else f'{r['dy']:.1%}'}.")
    n_ca = int((export.loans_table(x)["state"] == "CA").sum())
    lines.append(f"\nMarket: {len(m)} scored loans ({int(m['eligible'].sum())} eligible); {n_ca - len(m)} California "
                 f"loans fall outside it.")
    meta = export.meta_block(x)
    (DOCS / "selection.md").write_text(RULE.format(date=dt.date.today().isoformat(), cutoff=meta["data_cutoff"],
                                                   result="\n".join(lines)), encoding="utf-8")
    log(f"LA selection: {len(picks)} picks from {len(m)} market loans -> docs/la/")


# ====================================================================== case study build (after the selection commit)

import json  # noqa: E402
import re  # noqa: E402

from mwall.underwrite import engine  # noqa: E402

MARKET_SRC = paths.CONFIG_DIR / "research" / "la_market_sources.csv"


def _m(v: float) -> str:
    return f"${v / 1e9:,.1f}B" if abs(v) >= 1e9 else f"${v / 1e6:,.1f}M"


def _p(v: float, d: int = 1) -> str:
    return "n/a" if v is None or pd.isna(v) else f"{100 * v:.{d}f}%"


def picks() -> list[tuple[str, str]]:
    """The committed picks, read back from docs/la/selection.md so the page can't drift from the record."""
    text = (DOCS / "selection.md").read_text(encoding="utf-8")
    return [(m.group(1), m.group(2)) for m in re.finditer(r"^- (\d\. [^:]+): .*?`(WL[0-9a-f]+)`", text, re.M)]


class Local:
    """Cited figures from config/research/la_market_sources.csv, addressed by their keys; publisher matches by prefix."""

    def __init__(self):
        self.t = pd.read_csv(MARKET_SRC)

    def get(self, metric, ptype, geo, period, publisher) -> dict:
        t = self.t
        r = t[(t["metric"] == metric) & (t["property_type"] == ptype) & (t["geography"] == geo) & (t["period"] == period)
              & t["source_publisher"].str.startswith(publisher)]
        if not len(r):
            raise KeyError((metric, ptype, geo, period, publisher))
        i, row = r.index[0], r.iloc[0]
        return {"value": float(row["value"]), "unit": row["unit"], "publisher": row["source_publisher"],
                "date": row["publication_date"], "url": row["url"], "row": int(i) + 1, "metric": metric, "geo": geo,
                "period": period, "type": ptype}


def local_context(lc: Local) -> list[dict]:
    q, LA, OC = "2026Q3", "Los Angeles County", "Orange County"
    g = lc.get
    rows = [
        ("Office vacancy, Los Angeles County", "%", [g("overall_vacancy_rate", "office", LA, q, "CBRE"),
            g("overall_vacancy_rate", "office", LA, q, "Cushman"), g("direct_vacancy_rate", "office", LA, q, "Kidder")]),
        ("Office asking rent, Los Angeles County", "$/sf/month, full service", [g("avg_asking_rent", "office", LA, q, "CBRE"),
            g("avg_asking_rent", "office", LA, q, "Cushman"), g("avg_asking_rent", "office", LA, q, "Kidder")]),
        ("Office vacancy, Orange County", "%", [g("overall_vacancy_rate", "office", OC, q, "CBRE"),
            g("overall_vacancy_rate", "office", OC, q, "Cushman")]),
        ("Industrial vacancy, Los Angeles County", "%", [g("overall_vacancy_rate", "industrial", LA, q, "CBRE"),
            g("overall_vacancy_rate", "industrial", LA, q, "Cushman"), g("direct_vacancy_rate", "industrial", LA, q, "Kidder")]),
        ("Multifamily vacancy, Los Angeles County", "%", [g("vacancy_rate", "multifamily", LA, q, "Kidder")]),
        ("Multifamily occupancy, Los Angeles County (market-rate, 5+ units)", "%", [g("occupancy_rate", "multifamily", LA, q, "CBRE")]),
        ("Multifamily asking rent change, Los Angeles County, year over year", "%", [g("avg_asking_rent_change_yoy", "multifamily", LA, q, "Kidder")]),
        ("Retail availability, Los Angeles County", "%", [g("availability_rate", "retail", LA, q, "CBRE"),
            g("vacancy_rate", "retail", LA, q, "Kidder")]),
        ("Hotel RevPAR, Los Angeles market, Q3", "$", [g("revpar", "lodging", "Los Angeles County (STR Los Angeles, CA market)", q, "Cushman")]),
        ("Housing units authorized in 5+ unit buildings, Los Angeles County, January to September", "units",
            [g("housing_units_authorized_5plus", "new_supply", LA, "2026 Jan-Sep", "U.S. Census"),
             g("housing_units_authorized_5plus", "new_supply", LA, "2025 Jan-Sep", "U.S. Census")]),
    ]
    return [{"label": label, "unit": unit, "cites": cites} for label, unit, cites in rows]
