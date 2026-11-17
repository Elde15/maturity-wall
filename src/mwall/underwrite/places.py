"""Which city a property sits in, for the Los Angeles overrides (SOP 13 step 4).

Postal city names don't settle it: Van Nuys, Sherman Oaks and North Hollywood are inside the City of Los Angeles,
whose transfer tax (Measure ULA) and rent ordinance apply there. So each Los Angeles and Orange County property
with coordinates is looked up in the Census Bureau's geocoder (incorporated places layer, current vintage). A
property in no incorporated place is in an unincorporated area. Properties without coordinates fall back to an
exact match of the filed city name, flagged.

Writes data/parsed/places.parquet (addr_key, place_geoid, place_name, place_source).
"""
from __future__ import annotations

import json
import time
import urllib.parse
import urllib.request

import pandas as pd

from mwall.common import paths

URL = "https://geocoding.geo.census.gov/geocoder/geographies/coordinates"
UA = "mwall-research/0.1"
COUNTIES = {"06037", "06059"}  # Los Angeles, Orange
JURISDICTION = {"0644000": "la_city", "0670000": "santa_monica", "0617568": "culver_city"}
CITY_NAME = {"LOS ANGELES": "0644000", "SANTA MONICA": "0670000", "CULVER CITY": "0617568"}


def lookup(lat: float, lon: float, tries: int = 3) -> tuple[str | None, str | None]:
    q = urllib.parse.urlencode({"x": lon, "y": lat, "benchmark": "Public_AR_Current", "vintage": "Current_Current",
                                "layers": "Incorporated Places", "format": "json"})
    for k in range(tries):
        try:
            req = urllib.request.Request(f"{URL}?{q}", headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=30) as r:
                g = json.load(r)["result"]["geographies"].get("Incorporated Places", [])
            return (g[0]["GEOID"], g[0]["NAME"]) if g else ("", "")
        except Exception:  # noqa: BLE001 - network hiccup: retry, then give up on this one
            time.sleep(2 * (k + 1))
    return None, None


def build(log=print) -> pd.DataFrame:
    d = pd.read_parquet(paths.OUTPUT_DIR / "underwrite_inputs.parquet",
                        columns=["addr_key", "county_fips", "lat", "lon", "prop_city"])
    d = d[d["county_fips"].isin(COUNTIES)].drop_duplicates("addr_key")
    old = pd.read_parquet(paths.PARSED_DIR / "places.parquet") if (paths.PARSED_DIR / "places.parquet").exists() \
        else pd.DataFrame(columns=["addr_key"])
    done = set(old.loc[old.get("place_source", pd.Series(dtype=str)).eq("census_geocoder"), "addr_key"])
    rows = []
    for i, r in enumerate(d.itertuples(index=False)):
        if r.addr_key in done:
            continue
        if pd.notna(r.lat) and pd.notna(r.lon):
            geoid, name = lookup(r.lat, r.lon)
            if geoid is not None:
                rows.append({"addr_key": r.addr_key, "place_geoid": geoid or None, "place_name": name or None,
                             "place_source": "census_geocoder"})
                time.sleep(0.2)
                continue
        geoid = CITY_NAME.get(str(r.prop_city or "").strip().upper())
        rows.append({"addr_key": r.addr_key, "place_geoid": geoid, "place_name": None, "place_source": "filed_city"})
        if (i + 1) % 100 == 0:
            log(f"places: {i + 1}/{len(d)}")
    new = pd.DataFrame(rows)
    out = pd.concat([old[old["addr_key"].isin(done)], new], ignore_index=True) if len(old) else new
    out.to_parquet(paths.PARSED_DIR / "places.parquet", index=False)
    log(f"places: {len(out):,} Los Angeles and Orange County addresses; "
        f"{int(out['place_source'].eq('census_geocoder').sum()):,} from the geocoder; "
        f"City of Los Angeles {int(out['place_geoid'].eq('0644000').sum()):,}; "
        f"unincorporated {int((out['place_source'].eq('census_geocoder') & out['place_geoid'].isna()).sum()):,}")
    return out
