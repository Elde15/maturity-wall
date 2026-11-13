"""Market and macro series for the feature layer (SOP section 9, family 7).

Every series is stored as tidy rows with the date its value became public (``available``), and
joins to a loan-month only through ``asof``: the latest value with ``available`` on or before the
snapshot date. Release lags are set conservatively where the publisher gives no fixed schedule.
All series are today's vintage, so later revisions are a small look-ahead that the leakage audit
lists rather than hides.

Sources (cached under data/meta/market/ with fetch date and SHA-256):

  FRED H.15 constant-maturity Treasury yields DGS2, DGS5, DGS7, DGS10 (daily, fredgraph.csv).
      A day's yield is used from the next calendar day.
  Zillow Observed Rent Index, metro, smoothed: all homes (sfrcondomfr) and multifamily (mfr).
      A month's value is used from the last day of the following month.
  BLS QCEW open-data slices by industry and quarter: total covered employment (industry 10,
      all owners) and private office-using employment (1022 information, 1023 financial
      activities, 1024 professional and business services). Metro rows only. A quarter is used
      from six months after it ends.
  Census Building Permits Survey, county monthly files (units in all structures and in 5+ unit
      structures). A month is used from the last day of the second month after it.
  Census county housing-unit estimates, vintage 2020 (2010-2020) and vintage 2024 (2020-2024).
      The July 1 estimate for year Y is used from July 1 of Y+1.

County series reach metros through the OMB July 2023 delineation already used by geography.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import io
import json
import subprocess

import numpy as np
import pandas as pd

from mwall.common import paths

MKT_DIR = paths.META_DIR / "market"
UA = {"User-Agent": "mwall-research/0.1"}
FRED = "https://fred.stlouisfed.org/graph/fredgraph.csv?id={sid}"
TREASURY = ("DGS2", "DGS5", "DGS7", "DGS10")
ZORI = {
    "zori_all": "https://files.zillowstatic.com/research/public_csvs/zori/Metro_zori_uc_sfrcondomfr_sm_month.csv",
    "zori_mf": "https://files.zillowstatic.com/research/public_csvs/zori/Metro_zori_uc_mfr_sm_month.csv",
}
QCEW = "https://data.bls.gov/cew/data/api/{y}/{q}/industry/{ind}.csv"
QCEW_IND = {"10": "0", "1022": "5", "1023": "5", "1024": "5"}  # industry -> ownership code kept
BPS = "https://www2.census.gov/econ/bps/County/co{yy:02d}{mm:02d}c.txt"
HU_2020 = "https://www2.census.gov/programs-surveys/popest/datasets/2010-2020/housing/HU-EST2020_{st}.csv"
HU_2024 = "https://www2.census.gov/programs-surveys/popest/tables/2020-2024/housing/totals/CO-EST2024-HU-{st:02d}.xlsx"
STATES = [1, 2, 4, 5, 6, 8, 9, 10, 11, 12, 13, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31,
          32, 33, 34, 35, 36, 37, 38, 39, 40, 41, 42, 44, 45, 46, 47, 48, 49, 50, 51, 53, 54, 55, 56]
FIRST_YEAR = 2015

LAG = {  # how a value's period maps to the first date it may be used; see the module docstring
    "treasury": "next calendar day",
    "zori": "last day of the following month",
    "qcew": "six months after the quarter ends",
    "bps": "last day of the second month after the month",
    "housing_units": "July 1 of the following year",
}


# ---------------------------------------------------------------- fetching

def _meta() -> dict:
    p = MKT_DIR / "sources.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


def _save_meta(meta: dict) -> None:
    (MKT_DIR / "sources.json").write_text(json.dumps(meta, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _download(url: str) -> tuple[int, bytes]:
    """FRED stalls Python's HTTP client (the request hangs until timeout) but answers curl with the
    same User-Agent, so every download goes through the system curl."""
    tmp = MKT_DIR / ".download.tmp"
    r = subprocess.run(["curl", "-s", "-L", "--max-time", "300", "-A", UA["User-Agent"], "-o", str(tmp),
                        "-w", "%{http_code}", url], capture_output=True, text=True, check=False)
    code = int(r.stdout.strip() or 0)
    body = tmp.read_bytes() if tmp.exists() else b""
    tmp.unlink(missing_ok=True)
    return code, body


def _get(url: str, dest, meta: dict, name: str, refresh: bool = False, log=print) -> bool:
    if dest.exists() and not refresh:
        return True
    code, body = _download(url)
    if code == 404 or body.lstrip()[:15].lower().startswith((b"<html", b"<!doctype")):
        return False  # not published yet (Census answers some missing files with an HTML rejection page)
    if code != 200 or not body:
        raise RuntimeError(f"{name}: HTTP {code} from {url}")
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(body)
    meta[name] = {"url": url, "file": dest.relative_to(MKT_DIR).as_posix(), "fetched": dt.date.today().isoformat(),
                  "sha256": hashlib.sha256(body).hexdigest(), "bytes": len(body)}
    log(f"fetched {name} ({len(body):,} bytes)")
    return True


def fetch(refresh: bool = False, log=print) -> None:
    """Download every source not already cached. ``refresh`` re-pulls the series that update."""
    MKT_DIR.mkdir(parents=True, exist_ok=True)
    meta = _meta()
    try:
        for sid in TREASURY:
            _get(FRED.format(sid=sid), MKT_DIR / "fred" / f"{sid}.csv", meta, f"fred_{sid}", refresh, log)
        for name, url in ZORI.items():
            _get(url, MKT_DIR / "zillow" / f"{name}.csv", meta, name, refresh, log)
        today = dt.date.today()
        for y in range(FIRST_YEAR - 1, today.year + 1):
            for q in range(1, 5):
                if dt.date(y, 3 * q, 1) > today:
                    break
                for ind in QCEW_IND:
                    dest = MKT_DIR / "qcew" / f"{y}q{q}_{ind}.csv"
                    if not _get(QCEW.format(y=y, q=q, ind=ind), dest, meta, f"qcew_{y}q{q}_{ind}", False, log):
                        break
        for y in range(FIRST_YEAR - 1, today.year + 1):
            for m in range(1, 13):
                if dt.date(y, m, 1) >= today.replace(day=1):
                    break
                dest = MKT_DIR / "bps" / f"co{y % 100:02d}{m:02d}c.txt"
                _get(BPS.format(yy=y % 100, mm=m), dest, meta, f"bps_{y}{m:02d}", False, log)
        for st in STATES:
            _get(HU_2020.format(st=st), MKT_DIR / "housing" / f"HU-EST2020_{st}.csv", meta, f"hu2020_{st}", False, log)
            _get(HU_2024.format(st=st), MKT_DIR / "housing" / f"CO-EST2024-HU-{st:02d}.xlsx", meta, f"hu2024_{st}",
                 False, log)
    finally:
        _save_meta(meta)


# ---------------------------------------------------------------- tidy series

def month_end(p: pd.Series) -> pd.Series:
    return (pd.to_datetime(p) + pd.offsets.MonthEnd(0)).dt.normalize()


def treasury() -> pd.DataFrame:
    """Wide daily table: date, available, DGS2..DGS10 in percent."""
    out = None
    for sid in TREASURY:
        d = pd.read_csv(MKT_DIR / "fred" / f"{sid}.csv")
        d.columns = ["date", sid]
        d["date"] = pd.to_datetime(d["date"])
        d[sid] = pd.to_numeric(d[sid], errors="coerce")  # '.' marks holidays
        out = d if out is None else out.merge(d, on="date", how="outer")
    out = out.sort_values("date").dropna(how="all", subset=list(TREASURY)).reset_index(drop=True)
    out["available"] = out["date"] + pd.Timedelta(days=1)
    return out


def zillow_metro_map(cbsa: pd.DataFrame, names: pd.Series) -> pd.DataFrame:
    """Zillow names a metro by its first principal city and first state ('Los Angeles, CA')."""
    t = cbsa.drop_duplicates("cbsa_code")[["cbsa_code", "cbsa_title"]].copy()
    city = t["cbsa_title"].str.split(",").str[0].str.split("-").str[0].str.strip()
    state = t["cbsa_title"].str.split(",").str[1].str.strip().str.split("-").str[0]
    t["zname"] = city + ", " + state
    t = t[~t["zname"].duplicated(keep=False)]
    return t.merge(pd.DataFrame({"zname": names.unique()}), on="zname")[["zname", "cbsa_code"]]


def zori(cbsa: pd.DataFrame) -> pd.DataFrame:
    """Long table: cbsa_code, month, available, zori_all, zori_mf, and their 12-month growth."""
    parts = []
    for name in ZORI:
        w = pd.read_csv(MKT_DIR / "zillow" / f"{name}.csv")
        w = w[w["RegionType"].eq("msa")]
        m = zillow_metro_map(cbsa, w["RegionName"])
        w = w.merge(m, left_on="RegionName", right_on="zname")
        long = w.melt(id_vars=["cbsa_code"], value_vars=[c for c in w.columns if c[:2] in ("19", "20")],
                      var_name="month", value_name=name)
        long["month"] = month_end(long["month"])
        parts.append(long.set_index(["cbsa_code", "month"]))
    z = pd.concat(parts, axis=1).reset_index().sort_values(["cbsa_code", "month"])
    for name in ZORI:
        prev = z.groupby("cbsa_code")[name].shift(12)
        same_gap = z.groupby("cbsa_code")["month"].shift(12) == z["month"] - pd.offsets.MonthEnd(12)
        z[f"{name}_yoy"] = np.where(same_gap, z[name] / prev - 1, np.nan)
    z["available"] = z["month"] + pd.offsets.MonthEnd(1)
    return z.reset_index(drop=True)


def qcew() -> pd.DataFrame:
    """cbsa_code, quarter end, available, total employment, office-using employment, and YoY growth."""
    rows = []
    for f in sorted((MKT_DIR / "qcew").glob("*.csv")):
        ind = f.stem.split("_")[1]
        d = pd.read_csv(f, dtype=str, usecols=["area_fips", "own_code", "year", "qtr", "disclosure_code",
                                               "month3_emplvl"])
        d = d[d["area_fips"].str.startswith("C") & ~d["area_fips"].str.startswith("CS")
              & d["own_code"].eq(QCEW_IND[ind])]
        # 'N' is suppressed for confidentiality; '-' (all metro industry rows from 2025 Q3) is not published.
        # Both come with zeros, which must not read as a collapse in employment.
        emp = pd.to_numeric(d["month3_emplvl"], errors="coerce").where(d["disclosure_code"].fillna("").eq(""))
        d = d.assign(year=d["year"].astype(int), qtr=d["qtr"].astype(int))
        rows.append(pd.DataFrame({"qcew_area": d["area_fips"], "year": d["year"], "qtr": d["qtr"],
                                  "industry": ind, "emp": emp}))
    q = pd.concat(rows, ignore_index=True)
    w = q.pivot_table(index=["qcew_area", "year", "qtr"], columns="industry", values="emp", aggfunc="sum",
                      min_count=1).reset_index()
    office = [c for c in ("1022", "1023", "1024") if c in w.columns]
    w["emp_total"] = w.get("10")
    # all three office supersectors must be disclosed, or the sum would fall for a disclosure reason
    w["emp_office"] = w[office].sum(axis=1, min_count=len(office)) if len(office) == 3 else np.nan
    w["quarter_end"] = pd.to_datetime(dict(year=w["year"], month=3 * w["qtr"], day=1)) + pd.offsets.MonthEnd(0)
    w = w.sort_values(["qcew_area", "quarter_end"])
    # match the same quarter a year earlier directly; an area can skip quarters, so a row shift is unsafe
    prev = w[["qcew_area", "quarter_end", "emp_total", "emp_office"]].copy()
    prev["quarter_end"] = prev["quarter_end"] + pd.offsets.MonthEnd(12)
    w = w.merge(prev, on=["qcew_area", "quarter_end"], how="left", suffixes=("", "_prev"))
    for c in ("emp_total", "emp_office"):
        w[f"{c}_yoy"] = (w[c] / w[f"{c}_prev"] - 1).where(w[f"{c}_prev"] > 0)
    w["available"] = w["quarter_end"] + pd.offsets.MonthEnd(6)
    return w[["qcew_area", "quarter_end", "available", "emp_total", "emp_office", "emp_total_yoy",
              "emp_office_yoy"]].reset_index(drop=True)


def qcew_area(cbsa_code: pd.Series) -> pd.Series:
    """QCEW names a metro 'C' plus the first four digits of its CBSA code."""
    return "C" + cbsa_code.astype("string").str[:4]


def bps_county() -> pd.DataFrame:
    rows = []
    for f in sorted((MKT_DIR / "bps").glob("co*c.txt")):
        txt = f.read_text(encoding="latin-1").splitlines()
        body = [ln for ln in txt[2:] if ln.strip()]
        d = pd.read_csv(io.StringIO("\n".join(body)), header=None, dtype=str)
        units = sum(pd.to_numeric(d[c], errors="coerce").fillna(0) for c in (7, 10, 13, 16))
        rows.append(pd.DataFrame({
            "county_fips": d[1].str.zfill(2) + d[2].str.zfill(3),
            "month": pd.Timestamp(2000 + int(f.stem[2:4]), int(f.stem[4:6]), 1) + pd.offsets.MonthEnd(0),
            "units_all": units, "units_5plus": pd.to_numeric(d[16], errors="coerce").fillna(0)}))
    return pd.concat(rows, ignore_index=True)


def housing_units() -> pd.DataFrame:
    """county_fips, year, housing units (July 1 estimate). The later vintage wins where both exist."""
    parts = []
    for f in sorted((MKT_DIR / "housing").glob("HU-EST2020_*.csv")):
        d = pd.read_csv(f, dtype={"STATE": str, "COUNTY": str}, encoding="latin-1")
        d = d[d["SUMLEV"].astype(str).str.zfill(3).eq("050")]
        for y in range(2010, 2020):
            parts.append(pd.DataFrame({"county_fips": d["STATE"].str.zfill(2) + d["COUNTY"].str.zfill(3),
                                       "year": y, "hu": pd.to_numeric(d[f"HUESTIMATE{y}"], errors="coerce"),
                                       "vintage": 2020}))
    names = None
    for f in sorted((MKT_DIR / "housing").glob("CO-EST2024-HU-*.xlsx")):
        st = f.stem.rsplit("-", 1)[1]
        x = pd.read_excel(f, header=None)
        # rows are '.County Name, State' with the 2020 base, then July 1 2020..2024 estimates
        x = x[x[0].astype(str).str.startswith(".")]
        if names is None:
            names = _county_names()
        from mwall.clean.geography import _county_name

        x = x.assign(cname=x[0].str[1:].str.split(",").str[0].map(_county_name))
        x = x.merge(names[names["state_fips"].eq(st)], on="cname", how="left")
        for i, y in enumerate(range(2020, 2025)):
            parts.append(pd.DataFrame({"county_fips": x["county_fips"], "year": y,
                                       "hu": pd.to_numeric(x[2 + i], errors="coerce"), "vintage": 2024}))
    hu = pd.concat(parts, ignore_index=True).dropna(subset=["county_fips", "hu"])
    hu = hu.sort_values("vintage").drop_duplicates(["county_fips", "year"], keep="last")
    hu["available"] = pd.to_datetime(dict(year=hu["year"] + 1, month=7, day=1))
    return hu.reset_index(drop=True)


def _county_names() -> pd.DataFrame:
    """(state FIPS, normalized county name) -> county FIPS. The 2023 delineation carries Connecticut's
    planning regions, which the vintage 2024 estimates use; the 2020 relationship file covers the rest."""
    from mwall.clean.geography import _county_name, cbsa, county_names

    c = cbsa()
    a = pd.DataFrame({"state_fips": c["county_fips"].str[:2], "cname": c["cbsa_county_name"].map(_county_name),
                      "county_fips": c["county_fips"]})
    n = county_names().rename(columns={"name_norm": "cname"})[["state_fips", "cname", "county_fips"]]
    return pd.concat([a, n], ignore_index=True).drop_duplicates(["state_fips", "cname"])


def permits(county_cbsa: pd.DataFrame) -> pd.DataFrame:
    """Metro trailing-12-month permits per 1,000 housing units, all structures and 5+ units."""
    b = bps_county().merge(county_cbsa, on="county_fips")
    m = b.groupby(["cbsa_code", "month"])[["units_all", "units_5plus"]].sum().reset_index()
    m = m.sort_values(["cbsa_code", "month"])
    g = m.groupby("cbsa_code")
    full = g["month"].shift(11) == m["month"] - pd.offsets.MonthEnd(11)
    for c in ("units_all", "units_5plus"):
        m[f"{c}_t12"] = np.where(full, g[c].transform(lambda s: s.rolling(12).sum()), np.nan)
    m["available"] = m["month"] + pd.offsets.MonthEnd(2)
    hu = housing_units().merge(county_cbsa, on="county_fips")
    hu = hu.groupby(["cbsa_code", "year"]).agg(hu=("hu", "sum"), hu_available=("available", "max")).reset_index()
    # the housing stock in the denominator must itself be public by the permit's availability date
    m = m.sort_values("available")
    hu = hu.sort_values("hu_available")
    m = pd.merge_asof(m, hu[["cbsa_code", "hu_available", "hu"]], left_on="available", right_on="hu_available",
                      by="cbsa_code", direction="backward")
    m["permits_per_1k_units"] = 1000 * m["units_all_t12"] / m["hu"]
    m["permits_5plus_per_1k_units"] = 1000 * m["units_5plus_t12"] / m["hu"]
    m["available"] = m[["available", "hu_available"]].max(axis=1)
    return m[["cbsa_code", "month", "available", "permits_per_1k_units", "permits_5plus_per_1k_units"]]


def county_cbsa() -> pd.DataFrame:
    from mwall.clean.geography import cbsa

    c = cbsa()
    return c[["county_fips", "cbsa_code"]].dropna().drop_duplicates("county_fips")


# ---------------------------------------------------------------- as-of join

def asof(left: pd.DataFrame, right: pd.DataFrame, cols: list[str], by: str | None = None,
         on: str = "snapshot_date", prefix: str = "", max_age_days: int | None = None) -> pd.DataFrame:
    """Attach the latest ``right`` row with ``available`` <= left[on] and every column in ``cols``
    present; keeps its available date as ``{prefix}asof`` so the leakage audit can check it. With
    ``max_age_days``, a value published longer ago than that is not used."""
    r = right[[*([by] if by else []), "available", *cols]].dropna(subset=["available", *cols]).sort_values("available")
    r = r.rename(columns={c: f"{prefix}{c}" for c in cols} | {"available": f"{prefix}asof"})
    lt = left[[*([by] if by else []), on]].reset_index().sort_values(on)
    has = lt[on].notna() & (lt[by].notna() if by else True)
    lt = lt[has]
    if by:  # parquet and CSV strings arrive as different string dtypes; merge_asof needs one
        lt = lt.assign(**{by: lt[by].astype(str).astype(object)})
        r = r.assign(**{by: r[by].astype(str).astype(object)})
    m = pd.merge_asof(lt, r, left_on=on, right_on=f"{prefix}asof", by=by, direction="backward")
    if max_age_days is not None:
        old = (m[on] - m[f"{prefix}asof"]).dt.days > max_age_days
        m.loc[old, [f"{prefix}asof", *[f"{prefix}{c}" for c in cols]]] = np.nan
    m = m.set_index("index").reindex(left.index)
    return left.join(m[[f"{prefix}asof", *[f"{prefix}{c}" for c in cols]]])
