"""Cap-rate benchmark by property type and date (SOP 9 and 12; decision D048).

Input: config/research/cap_rates_sources.csv (every value quoted from its source). Output:
config/cap_rates.csv, one row per type and survey period, with the date the value became public.

Construction:

1. CBRE U.S. Cap Rate Survey, national stabilized averages, first publication of each edition only
   (later editions restate history; a restated value is public only from the later date). A type's
   value is the mean of a fixed set of subtypes, and an edition counts only when all are present:
   office CBD and suburban; industrial; multifamily infill and suburban; retail neighborhood/
   community and power center; lodging CBD and suburban.
2. CBRE stopped publishing national by-type averages on its open pages after H2 2019 (later
   editions are behind a form). CoStar's monthly national figures (published by NAR) carry each
   type forward from its last CBRE value: benchmark = CBRE last + (CoStar now - CoStar at the link).
   The link is CoStar's first value; for industrial and multifamily that is 2020Q1, next to CBRE
   H2 2019. For office and retail CoStar starts in late 2021, so the link assumes no change from
   H2 2019 to then; RCA's transaction averages for 2020 and 2021 move by 0.1 point or less for both.
3. Lodging has no source after 2019 and self-storage none at all. A value is used for at most
   MAX_AGE_DAYS after its survey period, so lodging lapses rather than going stale.

Excluded: PwC issues found only as re-hosted subscriber copies, IRR's registration library, NAR's
member survey (deals mostly under $2.5M, another market), and RCA (definitions shift between
reports), which is cited only for the office and retail link assumption.
"""
from __future__ import annotations

import re

import numpy as np
import pandas as pd

from mwall.common import paths

SOURCES = paths.CONFIG_DIR / "research" / "cap_rates_sources.csv"
OUT = paths.CONFIG_DIR / "cap_rates.csv"
MAX_AGE_DAYS = 730
SUBTYPES = {
    "office": ["CBD", "suburban"],
    "industrial": [None],
    "multifamily": ["infill", "suburban"],
    "retail": ["neighborhood/community center", "power center"],
    "lodging": ["CBD", "suburban"],
}


def period_date(s: str) -> pd.Timestamp:
    """'H1 2016' -> 2016-06-30; '2021Q3' -> 2021-09-30; '2023-01' -> 2023-01-31; a date stays a date."""
    s = str(s).strip()
    if m := re.match(r"^H([12]) (\d{4})", s):
        return pd.Timestamp(int(m[2]), 6 if m[1] == "1" else 12, 30 if m[1] == "1" else 31)
    if m := re.match(r"^(\d{4})Q([1-4])$", s):
        return pd.Timestamp(int(m[1]), 3 * int(m[2]), 1) + pd.offsets.MonthEnd(0)
    if m := re.match(r"^(\d{4})-(\d{2})$", s):
        return pd.Timestamp(int(m[1]), int(m[2]), 1) + pd.offsets.MonthEnd(0)
    if m := re.match(r"^(\d{4}-\d{2}-\d{2})$", s):
        return pd.Timestamp(m[1])
    return pd.NaT


def cbre_types(src: pd.DataFrame) -> pd.DataFrame:
    c = src[src["source_publisher"].str.startswith("CBRE") & src["market"].eq("U.S.") & src["class"].isna()
            & src["stat"].str.startswith("national average, stabilized", na=False)
            & ~src["stat"].str.contains("history as shown|restated|prior-period", case=False, na=False)
            & ~src["edition"].str.contains("prior-period", case=False, na=False)].copy()
    c["period"] = c["edition"].str.extract(r"^(H[12] \d{4})")[0]
    c["publication_date"] = pd.to_datetime(c["publication_date"].astype(str).str[:10], errors="coerce")
    rows = []
    for (period, pub), e in c.groupby(["period", "publication_date"]):
        for t, subs in SUBTYPES.items():
            x = e[e["property_group"].eq(t)]
            vals = [x.loc[x["subtype"].isna() if s is None else x["subtype"].eq(s), "cap_rate_pct"] for s in subs]
            if all(len(v) for v in vals):
                rows.append({"property_group": t, "survey_period": period, "publication_date": pub,
                             "cap_rate": np.mean([v.mean() for v in vals]) / 100, "source": "CBRE"})
    out = pd.DataFrame(rows).sort_values("publication_date")
    # an Advance Review and the final report of one edition are both first publications; keep both,
    # each from its own date
    return out.drop_duplicates(["property_group", "survey_period", "publication_date"])


def costar(src: pd.DataFrame) -> pd.DataFrame:
    c = src[src["source_publisher"].str.startswith("CoStar") & src["market"].eq("U.S.")].copy()
    c["publication_date"] = pd.to_datetime(c["publication_date"].astype(str).str[:10], errors="coerce")
    c = c.sort_values("publication_date").drop_duplicates(["property_group", "survey_period"], keep="first")
    return pd.DataFrame({"property_group": c["property_group"], "survey_period": c["survey_period"],
                         "publication_date": c["publication_date"], "cap_rate": c["cap_rate_pct"] / 100,
                         "source": "CoStar via NAR"})


def build(log=print) -> pd.DataFrame:
    src = pd.read_csv(SOURCES)
    cb, cs = cbre_types(src), costar(src)
    for d in (cb, cs):
        d["period_date"] = d["survey_period"].map(period_date)
    parts = [cb.assign(link_offset=0.0)]
    for t in SUBTYPES:
        a = cb[cb["property_group"].eq(t)].sort_values(["period_date", "publication_date"])
        b = cs[cs["property_group"].eq(t)].sort_values("period_date")
        if a.empty or b.empty:
            continue
        last, first = a.iloc[-1], b.iloc[0]
        # CoStar values are used after CBRE's last period, shifted so the series join at the link point
        offset = last["cap_rate"] - first["cap_rate"]
        b = b[b["period_date"] > last["period_date"]].assign(link_offset=offset)
        b["cap_rate"] = b["cap_rate"] + offset
        b["publication_date"] = b["publication_date"].clip(lower=max(first["publication_date"],
                                                                     last["publication_date"]))
        parts.append(b)
        log(f"{t}: CBRE {last['survey_period']} {100 * last['cap_rate']:.2f}% linked to CoStar "
            f"{first['survey_period']} {100 * first['cap_rate']:.2f}% (offset {100 * offset:+.2f})")
    out = pd.concat(parts, ignore_index=True).sort_values(["property_group", "publication_date", "period_date"])
    # an older period published after a newer one (CoStar's April 2024 figure came out after December's)
    # must not replace the newer value: keep only rows that advance the latest period known at publication
    newest = out.groupby("property_group")["period_date"].cummax()
    out = out[out["period_date"].ge(newest)]
    out = out.drop_duplicates(["property_group", "publication_date"], keep="last")
    out = out[["property_group", "survey_period", "period_date", "publication_date", "cap_rate", "source",
               "link_offset"]]
    out.to_csv(OUT, index=False, float_format="%.5f", date_format="%Y-%m-%d")
    return out
