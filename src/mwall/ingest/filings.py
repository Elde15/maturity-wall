"""Enumerate every 10-D, 10-D/A, ABS-EE and ABS-EE/A per trust (SOP section 7, step 3).

Source: the EDGAR submissions record (data.sec.gov/submissions/CIK##########.json),
including its paged older files. The form index is used as a cross-check: any
filing in the index that the submissions record lacks is added from the index.

Amendment rule: within a trust, form family (10-D or ABS-EE) and report date,
the latest-filed document wins; an /A beats the original on a filing-date tie.
"""
from __future__ import annotations

import gzip
import json
from concurrent.futures import ThreadPoolExecutor, as_completed

import pandas as pd

from mwall.common import paths
from mwall.ingest import state
from mwall.ingest.sec_client import SecClient

KEEP = {"10-D", "10-D/A", "ABS-EE", "ABS-EE/A"}
SUB_URL = "https://data.sec.gov/submissions/{name}"


def _sub_path(name: str):
    return paths.META_DIR / "submissions" / (name + ".gz")


def _fetch_json(client: SecClient, name: str, refresh: bool) -> dict | None:
    p = _sub_path(name)
    if p.exists() and not refresh:
        with gzip.open(p, "rt", encoding="utf-8") as fh:
            return json.load(fh)
    res = client.get(SUB_URL.format(name=name))
    if res.status != 200:
        return None
    p.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(p, "wb") as fh:
        fh.write(res.content)
    return json.loads(res.content)


def _rows(block: dict, cik: int) -> list[dict]:
    out = []
    n = len(block.get("accessionNumber", []))
    for i in range(n):
        form = block["form"][i]
        if form not in KEEP:
            continue
        out.append(
            {
                "trust_cik": cik,
                "accession": block["accessionNumber"][i],
                "form": form,
                "filing_date": block["filingDate"][i],
                "report_date": block.get("reportDate", [""] * n)[i] or None,
                "primary_document": block.get("primaryDocument", [""] * n)[i] or None,
                "source": "submissions",
            }
        )
    return out


def fetch_trust(client: SecClient, cik: int, refresh: bool) -> list[dict]:
    root = _fetch_json(client, f"CIK{cik:010d}.json", refresh)
    if root is None:
        return []
    rows = _rows(root["filings"]["recent"], cik)
    for f in root["filings"].get("files", []):
        page = _fetch_json(client, f["name"], refresh=False)  # older pages never change
        if page:
            rows.extend(_rows(page, cik))
    return rows


def resolve_amendments(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["form_family"] = df["form"].str.replace("/A", "", regex=False)
    df["is_amendment"] = df["form"].str.endswith("/A")
    df["period_key"] = df["report_date"].fillna(df["filing_date"])
    df = df.sort_values(["trust_cik", "form_family", "period_key", "filing_date", "is_amendment", "accession"])
    last = df.groupby(["trust_cik", "form_family", "period_key"]).tail(1).index
    df["is_period_winner"] = df.index.isin(last)
    n_in_period = df.groupby(["trust_cik", "form_family", "period_key"])["accession"].transform("count")
    df["n_versions_for_period"] = n_in_period
    return df


def run(client: SecClient, workers: int = 4, log=print, limit: int | None = None, refresh: bool = True) -> pd.DataFrame:
    trusts = pd.read_parquet(paths.META_DIR / "trusts.parquet")
    idx = pd.read_parquet(paths.META_DIR / "form_index_abs.parquet")
    ciks = trusts["trust_cik"].astype(int).tolist()[:limit]
    rows: list[dict] = []
    conn = state.connect()
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futs = {pool.submit(fetch_trust, client, c, refresh): c for c in ciks}
        for i, fut in enumerate(as_completed(futs), 1):
            cik = futs[fut]
            got = fut.result()
            rows.extend(got)
            conn.execute("INSERT OR REPLACE INTO submissions VALUES (?,?,?)", (cik, state.now(), len(got)))
            if i % 50 == 0:
                conn.commit()
                log(f"  submissions {i}/{len(ciks)}")
    conn.commit()
    df = pd.DataFrame(rows).drop_duplicates(subset=["trust_cik", "accession", "form"])

    # Cross-check against the form index; add anything the submissions record lacks.
    ix = idx[idx["cik"].isin(ciks)].rename(columns={"cik": "trust_cik", "date_filed": "filing_date"})
    ix["filing_date"] = ix["filing_date"].astype(str)
    missing = ix[~ix["accession"].isin(set(df["accession"]))]
    if len(missing):
        log(f"  {len(missing)} filings in the form index but not in submissions; added from the index")
        add = missing[["trust_cik", "accession", "form", "filing_date"]].assign(
            report_date=None, primary_document=None, source="form_index"
        )
        df = pd.concat([df, add], ignore_index=True)
    df = resolve_amendments(df)
    df.to_parquet(paths.META_DIR / "filings.parquet", index=False)
    log(f"filings: {len(df):,} rows; {df['form'].value_counts().to_dict()}")
    log(f"ABS-EE periods with more than one version: "
        f"{int(((df['form_family'] == 'ABS-EE') & (df['n_versions_for_period'] > 1) & df['is_period_winner']).sum())}")
    return df
