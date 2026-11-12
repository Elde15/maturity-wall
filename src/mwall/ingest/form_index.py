"""EDGAR quarterly full-index download and parse (SOP section 7, step 2).

Uses master.idx (pipe-delimited CIK|Company|Form|Date|File), which carries the
same rows as form.idx without fixed-width parsing. Closed quarters are cached
forever; the current quarter is refetched on every run.
"""
from __future__ import annotations

import datetime as dt
import gzip
from pathlib import Path

import pandas as pd

from mwall.common import paths
from mwall.ingest.sec_client import SecClient

KEEP_FORMS = {"10-D", "10-D/A", "ABS-EE", "ABS-EE/A"}
FIRST_QUARTER = (2017, 1)


def quarters(start: tuple[int, int] = FIRST_QUARTER, today: dt.date | None = None) -> list[tuple[int, int]]:
    today = today or dt.date.today()
    cur = (today.year, (today.month - 1) // 3 + 1)
    out, (y, q) = [], start
    while (y, q) <= cur:
        out.append((y, q))
        y, q = (y, q + 1) if q < 4 else (y + 1, 1)
    return out


def _cache_path(y: int, q: int) -> Path:
    return paths.META_DIR / "form_index" / f"master_{y}Q{q}.idx.gz"


def fetch_quarter(client: SecClient, y: int, q: int, is_current: bool) -> Path:
    dest = _cache_path(y, q)
    if dest.exists() and not is_current:
        return dest
    url = f"https://www.sec.gov/Archives/edgar/full-index/{y}/QTR{q}/master.idx"
    res = client.get(url, timeout=180)
    if res.status != 200:
        raise RuntimeError(f"master.idx {y}Q{q} returned {res.status}")
    dest.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(dest, "wb") as fh:
        fh.write(res.content)
    return dest


def parse_master(path: Path) -> pd.DataFrame:
    rows = []
    with gzip.open(path, "rt", encoding="latin-1") as fh:
        started = False
        for line in fh:
            if not started:
                if line.startswith("-----"):
                    started = True
                continue
            parts = line.rstrip("\n").split("|")
            if len(parts) != 5:
                continue
            cik, name, form, date, fname = parts
            if form in KEEP_FORMS:
                rows.append((int(cik), name.strip(), form, date, fname))
    df = pd.DataFrame(rows, columns=["cik", "company_name", "form", "date_filed", "file_name"])
    df["accession"] = df["file_name"].str.extract(r"(\d{10}-\d{2}-\d{6})\.txt$")[0]
    return df


def build(client: SecClient) -> pd.DataFrame:
    qs = quarters()
    frames = []
    for i, (y, q) in enumerate(qs):
        p = fetch_quarter(client, y, q, is_current=(i == len(qs) - 1))
        df = parse_master(p)
        df["index_quarter"] = f"{y}Q{q}"
        frames.append(df)
    out = pd.concat(frames, ignore_index=True)
    out["date_filed"] = pd.to_datetime(out["date_filed"]).dt.date
    out = out.drop_duplicates(subset=["accession", "form", "cik"])
    dest = paths.META_DIR / "form_index_abs.parquet"
    out.to_parquet(dest, index=False)
    return out
