"""Geography (SOP section 8, step 6): latitude, longitude, county and metro for every property address.

Sources, all public and cached under data/meta/geo/ with their fetch date and hash:

  Census Geocoder, batch "geographies" endpoint (benchmark Public_AR_Current, vintage
      Current_Current): street address -> point, state and county FIPS, tract.
  Census 2020 ZCTA-to-county relationship file: ZIP -> county where the geocoder finds no
      match. A ZIP is assigned to the county holding most of its land area; the share is kept.
  Census 2022 Connecticut county-subdivision-to-ZCTA file: Connecticut replaced its eight
      counties with nine planning regions in 2022, and the 2023 metro delineation uses the
      regions, so Connecticut ZIPs are assigned from this file instead.
  OMB metropolitan and micropolitan delineation, July 2023 (Census list1_2023.xlsx):
      county -> CBSA, metropolitan division and CSA.

County source order: geocoder match, then ZIP crosswalk, then the county name the filer
reported (matched within the state), else none. A ZIP-prefix rule is never used: California
prefixes 900-935 cover San Diego and the Inland Empire as well as Los Angeles, and the report
counts how many properties that rule would put in the wrong metro.

The join key is ``addr_key(address, city, state, zip)``, so property records and the largest-
property attributes on loan records share one lookup. Writes parsed/geography.parquet and
docs/qa/geography.md.
"""
from __future__ import annotations

import csv
import datetime as dt
import hashlib
import html
import io
import json
import re
import time

import duckdb
import numpy as np
import pandas as pd
import requests

from mwall.common import paths

GEO_DIR = paths.META_DIR / "geo"
CACHE = GEO_DIR / "geocode_cache.parquet"
SOURCES = {
    "zcta_county_2020": "https://www2.census.gov/geo/docs/maps-data/data/rel2020/zcta520/tab20_zcta520_county20_natl.txt",
    "ct_cousub_zcta_2022": "https://www2.census.gov/geo/docs/maps-data/data/rel2022/acs22_cousub22_zcta520_st09.txt",
    "cbsa_delineation_2023": "https://www2.census.gov/programs-surveys/metro-micro/geographies/reference-files/2023/delineation-files/list1_2023.xlsx",
}
GEOCODER = "https://geocoding.geo.census.gov/geocoder/geographies/addressbatch"
UA = {"User-Agent": "mwall-research/0.1"}  # the Census API asks for no contact details
BATCH = 1000
LA_CBSA = "31080"

_SKIP = re.compile(r"^(VARIOUS|N/?A|NONE|TBD|UNKNOWN|DEFEASED|MULTIPLE|-+)$")
_RANGE = re.compile(r"^(\d+)[A-Z]?\s*-\s*\d+[A-Z]?\s+")
_LIST = re.compile(r"^(\d+)[A-Z]?(?:\s*,\s*\d+[A-Z]?)*\s*(?:&|AND|,)\s*\d+[A-Z]?\s+")
_PARENS = re.compile(r"\([^)]*\)")
_AKA = re.compile(r"\b(A/?K/?A|F/?K/?A)\b.*$")


# ---------------------------------------------------------------- normalization
def zip5(z) -> str | None:
    if z is None or (isinstance(z, float) and np.isnan(z)):
        return None
    d = re.sub(r"\D", "", str(z).split("-")[0].split(".")[0])
    if len(d) == 4:
        d = "0" + d  # leading zero dropped by a spreadsheet (New England, New Jersey)
    return d[:5] if len(d) >= 5 else None


def _up(s) -> str:
    if s is None or (isinstance(s, float) and np.isnan(s)):
        return ""
    return re.sub(r"\s+", " ", str(s)).strip().upper()


def addr_key(address, city, state, zipc) -> str:
    raw = "|".join([_up(address), _up(city), _up(state), zip5(zipc) or ""])
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]


def clean_street(address, state: str = "") -> tuple[str | None, str]:
    """Light cleaning for the geocoder; returns (street or None, note).

    Hyphenated house numbers are kept in New York, where Queens addresses such as 67-76 Booth Street
    are real house numbers rather than ranges."""
    a = _up(html.unescape(str(address)) if isinstance(address, str) else address)
    if not a or _SKIP.match(a):
        return None, "no street address"
    a = _AKA.sub("", _PARENS.sub("", a)).strip(" ,;")
    first = re.split(r"\s*;\s*|\s+/\s+", a)[0]
    note = "first of several" if first != a else ""
    for rx, why in ((_RANGE, "range to first number"), (_LIST, "list to first number")):
        if rx is _RANGE and _up(state) == "NY":
            continue
        if rx.match(first):
            first = rx.sub(r"\1 ", first)
            note = why
    return (first or None), note


def _county_name(s) -> str:
    s = _up(s).replace(".", "").replace("SAINT ", "ST ").replace("STE ", "STE ")
    s = re.sub(r"\b(COUNTY|PARISH|BOROUGH|CITY AND BOROUGH|CENSUS AREA|MUNICIPALITY|MUNICIPIO)\b", "", s)
    return re.sub(r"[^A-Z0-9 ]", "", re.sub(r"\s+", " ", s)).strip()


# ---------------------------------------------------------------- reference files
def fetch_refs(log=print) -> dict:
    GEO_DIR.mkdir(parents=True, exist_ok=True)
    meta_path = GEO_DIR / "sources.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.exists() else {}
    for name, url in SOURCES.items():
        dest = GEO_DIR / url.rsplit("/", 1)[1]
        if not dest.exists():
            r = requests.get(url, headers=UA, timeout=300)
            r.raise_for_status()
            dest.write_bytes(r.content)
            meta[name] = {"url": url, "file": dest.name, "fetched": dt.date.today().isoformat(),
                          "sha256": hashlib.sha256(r.content).hexdigest(), "bytes": len(r.content)}
            log(f"fetched {dest.name} ({len(r.content):,} bytes)")
    meta_path.write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
    return meta


def zip_county() -> pd.DataFrame:
    """ZCTA -> county (2023 county equivalents) with the land-area share of the chosen county."""
    nat = pd.read_csv(GEO_DIR / "tab20_zcta520_county20_natl.txt", sep="|", dtype=str)
    nat = nat[nat["GEOID_ZCTA5_20"].notna()]
    nat = pd.DataFrame({"zcta": nat["GEOID_ZCTA5_20"], "county_fips": nat["GEOID_COUNTY_20"],
                        "area": pd.to_numeric(nat["AREALAND_PART"], errors="coerce").fillna(0)})
    nat = nat[~nat["county_fips"].str.startswith("09")]
    ct = pd.read_csv(GEO_DIR / "acs22_cousub22_zcta520_st09.txt", sep="|", dtype=str)
    zcol = next(c for c in ct.columns if c.startswith("GEOID_ZCTA5"))
    ccol = next(c for c in ct.columns if c.startswith("GEOID_COUSUB"))
    acol = next(c for c in ct.columns if c.startswith("AREALAND_PART"))
    ct = ct[ct[zcol].notna()]
    ct = pd.DataFrame({"zcta": ct[zcol], "county_fips": ct[ccol].str[:5],
                       "area": pd.to_numeric(ct[acol], errors="coerce").fillna(0)})
    z = pd.concat([nat, ct]).groupby(["zcta", "county_fips"], as_index=False)["area"].sum()
    z["share"] = z["area"] / z.groupby("zcta")["area"].transform("sum").replace(0, np.nan)
    z["n_counties"] = z.groupby("zcta")["county_fips"].transform("size")
    return (z.sort_values(["zcta", "area"], ascending=[True, False]).drop_duplicates("zcta")
            .rename(columns={"share": "zip_county_share"})[["zcta", "county_fips", "zip_county_share", "n_counties"]])


def cbsa() -> pd.DataFrame:
    d = pd.read_excel(GEO_DIR / "list1_2023.xlsx", skiprows=2, dtype=str)
    d = d[d["FIPS State Code"].notna() & d["FIPS County Code"].notna()]
    out = pd.DataFrame({
        "county_fips": d["FIPS State Code"].str.zfill(2) + d["FIPS County Code"].str.zfill(3),
        "cbsa_code": d["CBSA Code"], "cbsa_title": d["CBSA Title"],
        "cbsa_type": d["Metropolitan/Micropolitan Statistical Area"].str.extract(r"^(Metro|Micro)")[0].str.lower(),
        "metro_division_code": d["Metropolitan Division Code"], "metro_division_title": d["Metropolitan Division Title"],
        "csa_code": d["CSA Code"], "csa_title": d["CSA Title"],
        "cbsa_county_name": d["County/County Equivalent"], "central_outlying": d["Central/Outlying County"],
    })
    return out.drop_duplicates("county_fips")


def county_names() -> pd.DataFrame:
    """(state FIPS, normalized county name) -> county FIPS, from the 2020 relationship file."""
    nat = pd.read_csv(GEO_DIR / "tab20_zcta520_county20_natl.txt", sep="|", dtype=str,
                      usecols=["GEOID_COUNTY_20", "NAMELSAD_COUNTY_20"]).dropna().drop_duplicates()
    nat["state_fips"] = nat["GEOID_COUNTY_20"].str[:2]
    nat["name_norm"] = nat["NAMELSAD_COUNTY_20"].map(_county_name)
    return nat.rename(columns={"GEOID_COUNTY_20": "county_fips"})[["state_fips", "name_norm", "county_fips"]]


STATE_FIPS = {
    "AL": "01", "AK": "02", "AZ": "04", "AR": "05", "CA": "06", "CO": "08", "CT": "09", "DE": "10", "DC": "11",
    "FL": "12", "GA": "13", "HI": "15", "ID": "16", "IL": "17", "IN": "18", "IA": "19", "KS": "20", "KY": "21",
    "LA": "22", "ME": "23", "MD": "24", "MA": "25", "MI": "26", "MN": "27", "MS": "28", "MO": "29", "MT": "30",
    "NE": "31", "NV": "32", "NH": "33", "NJ": "34", "NM": "35", "NY": "36", "NC": "37", "ND": "38", "OH": "39",
    "OK": "40", "OR": "41", "PA": "42", "RI": "44", "SC": "45", "SD": "46", "TN": "47", "TX": "48", "UT": "49",
    "VT": "50", "VA": "51", "WA": "53", "WV": "54", "WI": "55", "WY": "56", "PR": "72", "GU": "66", "VI": "78",
}


# ---------------------------------------------------------------- addresses
def addresses() -> pd.DataFrame:
    """Every distinct property address, from property records and the largest-property fields on loans."""
    con = duckdb.connect()
    pp = (paths.PARSED_DIR / "property_period" / "*.parquet").as_posix()
    lp = (paths.PARSED_DIR / "loan_period" / "*.parquet").as_posix()
    a = con.execute(f"""
        select propertyAddress address, propertyCity city, propertyState state, propertyZip zip,
               propertyCounty county
        from read_parquet('{pp}', union_by_name=true)
        where block_role = 'property' and propertyState is not null
        union all
        select prop_address, prop_city, prop_state, prop_zip, prop_county
        from read_parquet('{lp}', union_by_name=true) where prop_state is not null""").df()
    a["addr_key"] = [addr_key(*r) for r in zip(a["address"], a["city"], a["state"], a["zip"])]
    a["zip5"] = a["zip"].map(zip5)
    a["state"] = a["state"].map(_up)
    # one row per key; keep the most common reported county name for the fallback
    county = (a.dropna(subset=["county"]).groupby(["addr_key", "county"]).size().rename("n").reset_index()
              .sort_values("n", ascending=False).drop_duplicates("addr_key").set_index("addr_key")["county"])
    a = a.drop_duplicates("addr_key").drop(columns="county").set_index("addr_key")
    a["county_reported"] = county
    return a.reset_index()


# ---------------------------------------------------------------- geocoding
def _post_batch(rows: list[tuple]) -> list[dict]:
    buf = io.StringIO()
    csv.writer(buf).writerows(rows)
    for attempt in range(4):
        try:
            r = requests.post(GEOCODER, headers=UA, timeout=900,
                              files={"addressFile": ("batch.csv", buf.getvalue().encode("utf-8"), "text/csv")},
                              data={"benchmark": "Public_AR_Current", "vintage": "Current_Current"})
            r.raise_for_status()
            break
        except requests.RequestException:
            if attempt == 3:
                raise
            time.sleep(30 * (attempt + 1))
    out = []
    for rec in csv.reader(io.StringIO(r.text)):
        if not rec:
            continue
        rec += [""] * (12 - len(rec))
        lon, lat = (rec[5].split(",") + [""])[:2] if rec[5] else ("", "")
        out.append({"addr_key": rec[0], "gc_status": rec[2], "gc_match_type": rec[3] or None,
                    "gc_matched_address": rec[4] or None,
                    "lon": float(lon) if lon else np.nan, "lat": float(lat) if lat else np.nan,
                    "gc_state_fips": rec[8] or None, "gc_county3": rec[9] or None, "gc_tract": rec[10] or None})
    return out


def geocode(addrs: pd.DataFrame, budget_s: float | None = None, log=print) -> pd.DataFrame:
    """Geocode addresses not yet in the cache, a batch at a time; the cache is rewritten after every batch."""
    cache = pd.read_parquet(CACHE) if CACHE.exists() else pd.DataFrame(columns=["addr_key"])
    if "street_sent" not in cache.columns:
        cache["street_sent"] = None
    todo = addrs.copy()
    cleaned = [clean_street(a, s) for a, s in zip(todo["address"], todo["state"])]
    todo["street"] = [c[0] for c in cleaned]
    todo["clean_note"] = [c[1] for c in cleaned]
    # send what is not cached, plus earlier misses whose cleaned street has since changed
    prev = todo[["addr_key", "street"]].merge(cache[["addr_key", "gc_status", "street_sent"]], on="addr_key", how="left")
    retry = prev["gc_status"].isin(["No_Match", "Tie"]) & (prev["street_sent"].isna() | (prev["street_sent"] != prev["street"]))
    todo = todo[(prev["gc_status"].isna() | retry).to_numpy()]
    skip = todo[todo["street"].isna()]
    if len(skip):
        cache = pd.concat([cache, pd.DataFrame({"addr_key": skip["addr_key"], "gc_status": "Skipped",
                                                "clean_note": skip["clean_note"],
                                                "geocoded_at": dt.date.today().isoformat()})], ignore_index=True)
        cache.to_parquet(CACHE, index=False)
    todo = todo[todo["street"].notna()]
    log(f"geocoder: {len(todo):,} addresses to send ({len(cache):,} cached, {len(skip):,} skipped without a street)")
    t0 = time.time()
    for i in range(0, len(todo), BATCH):
        if budget_s and time.time() - t0 > budget_s:
            log("time budget reached; rerun to continue")
            break
        chunk = todo.iloc[i:i + BATCH]
        rows = [(k, s, _up(c), st, z or "") for k, s, c, st, z in
                zip(chunk["addr_key"], chunk["street"], chunk["city"], chunk["state"], chunk["zip5"])]
        res = pd.DataFrame(_post_batch(rows))
        res = res.merge(chunk[["addr_key", "clean_note", "street"]].rename(columns={"street": "street_sent"}),
                        on="addr_key", how="left")
        res["geocoded_at"] = dt.date.today().isoformat()
        cache = pd.concat([cache, res], ignore_index=True).drop_duplicates("addr_key", keep="last")
        cache.to_parquet(CACHE, index=False)
        log(f"  batch {i // BATCH + 1}: {len(res):,} sent, {int((res['gc_status'] == 'Match').sum()):,} matched "
            f"({time.time() - t0:,.0f}s)")
    return cache


# ---------------------------------------------------------------- assembly
def build(budget_s: float | None = None, log=print) -> pd.DataFrame:
    fetch_refs(log)
    a = addresses()
    cache = geocode(a, budget_s=budget_s, log=log)
    g = a.merge(cache, on="addr_key", how="left")

    zc = zip_county()
    g = g.merge(zc.rename(columns={"zcta": "zip5", "county_fips": "zip_county_fips"}), on="zip5", how="left")
    names = county_names()
    g["state_fips"] = g["state"].map(STATE_FIPS)
    g["name_norm"] = g["county_reported"].map(_county_name)
    g = g.merge(names.rename(columns={"county_fips": "name_county_fips"}), on=["state_fips", "name_norm"], how="left")

    matched = g["gc_status"].eq("Match") & g["gc_county3"].notna()
    gc_fips = g["gc_state_fips"].fillna("") + g["gc_county3"].fillna("")
    # a geocode outside both the filer's state and the ZIP's state is a wrong match; one that agrees with
    # the ZIP but not the state is a state typo (PN for PA, FL with a Pennsylvania ZIP)
    gc_ok = matched & ((g["gc_state_fips"] == g["state_fips"])
                       | (g["gc_state_fips"] == g["zip_county_fips"].fillna("").str[:2]))
    # the filer's county name beats the ZIP crosswalk where both can be checked against the geocoder
    # (decision D034); Connecticut filers report the pre-2022 counties, which the 2023 delineation dropped
    use_name = g["name_county_fips"].notna() & (g["state_fips"] != "09")
    conds = [gc_ok, use_name, g["zip_county_fips"].notna()]
    g["county_fips"] = np.select(conds, [gc_fips, g["name_county_fips"], g["zip_county_fips"]], None)
    g["county_source"] = np.select(conds, ["geocoder", "reported_name", "zip_crosswalk"], "none")
    g.loc[~gc_ok, ["lat", "lon"]] = np.nan
    g["flag_geocode_other_state"] = matched & ~gc_ok

    cb = cbsa()
    g = g.merge(cb, on="county_fips", how="left")
    g.loc[g["cbsa_type"].isna() & g["county_fips"].notna(), "cbsa_type"] = "none"  # rural county, no CBSA

    # checks for the report
    g["zip_agrees"] = np.where(g["zip_county_fips"].notna() & gc_ok, g["zip_county_fips"] == gc_fips, np.nan)
    g["name_agrees"] = np.where(g["name_county_fips"].notna() & gc_ok, g["name_county_fips"] == gc_fips, np.nan)

    keep = ["addr_key", "address", "city", "state", "zip5", "county_reported", "lat", "lon", "gc_status",
            "gc_match_type", "gc_tract", "county_fips", "county_source", "zip_county_share", "cbsa_code",
            "cbsa_title", "cbsa_type", "metro_division_code", "metro_division_title", "csa_code", "csa_title",
            "flag_geocode_other_state", "zip_agrees", "name_agrees"]
    out = g[keep].copy()
    out.to_parquet(paths.PARSED_DIR / "geography.parquet", index=False)
    report(out, log)
    return out


def report(g: pd.DataFrame, log=print) -> None:
    from mwall.clean.qa_report import md_table

    n = len(g)
    src = g["county_source"].value_counts().rename_axis("county source").reset_index(name="addresses")
    src["share"] = (src["addresses"] / n).map(lambda x: f"{100 * x:.1f}%")
    gc = g["gc_status"].fillna("not sent").value_counts().rename_axis("geocoder result").reset_index(name="addresses")
    zip_ag = g["zip_agrees"].dropna()
    name_ag = g["name_agrees"].dropna()
    ca = g[(g["state"] == "CA") & g["zip5"].fillna("").str[:3].between("900", "935") & g["cbsa_code"].notna()]
    ca_not_la = ca[ca["cbsa_code"] != LA_CBSA]
    top = (ca_not_la["cbsa_title"].value_counts().head(6).rename_axis("metro").reset_index(name="addresses"))
    L = [
        "# Geography",
        "",
        "Every distinct property address (from property records and the largest-property fields on loan records) "
        "gets a county and a metro (`clean/geography.py`). Sources are the Census Geocoder, the Census 2020 "
        "ZCTA-to-county relationship file (Connecticut from the 2022 planning-region file) and the OMB July 2023 "
        "metropolitan delineation. Fetch dates and hashes: `data/meta/geo/sources.json`.",
        "",
        f"- Distinct addresses: {n:,}. With a county: {int(g['county_fips'].notna().sum()):,} "
        f"({100 * g['county_fips'].notna().mean():.1f}%). In a metro or micro area: "
        f"{int(g['cbsa_code'].notna().sum()):,}. With a point (geocoder match): {int(g['lat'].notna().sum()):,}.",
        f"- Geocoder matches outside the filer's own state, discarded: {int(g['flag_geocode_other_state'].sum()):,}.",
        f"- Where the geocoder matched, the ZIP crosswalk names the same county {100 * zip_ag.mean():.1f}% of the time "
        f"(n={len(zip_ag):,}) and the filer's reported county name {100 * name_ag.mean():.1f}% (n={len(name_ag):,}).",
        "",
        md_table(src),
        "",
        md_table(gc),
        "",
        "## Why not a ZIP prefix",
        "",
        f"California ZIPs starting 900 to 935 are often treated as Los Angeles. Of {len(ca):,} such addresses here, "
        f"{len(ca_not_la):,} ({100 * len(ca_not_la) / max(1, len(ca)):.0f}%) sit outside the Los Angeles-Long "
        "Beach-Anaheim metro:",
        "",
        md_table(top) if len(top) else "(none)",
        "",
    ]
    (paths.DOCS_DIR / "qa" / "geography.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    log("\n".join(L[6:10]))
