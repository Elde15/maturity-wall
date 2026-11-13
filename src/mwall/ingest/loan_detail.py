"""10-D statements of the vintage-2016 trusts that filed no EX-102 (decisions D033, D040).

These trusts still file a monthly 10-D whose EX-99.1 carries an HTML Mortgage Loan Detail table.
This module fetches the statements; ``mwall.parse.loan_detail`` reads them. The pilot covers the
Computershare filer agent (0001888524); ``agents`` widens it.

Statements land beside the others as raw/{cik}/{accession}.ex991.htm.gz, and the fetch log goes
to meta/loan_detail_statements.parquet.
"""
from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import pandas as pd

from mwall.common import paths
from mwall.ingest import tend
from mwall.ingest.sec_client import SecClient

TRUSTS = paths.CONFIG_DIR / "vintage2016_trusts.csv"
LOG = paths.META_DIR / "loan_detail_statements.parquet"
PILOT_AGENTS = ("0001888524",)


def targets(agents: tuple[str, ...] | None = PILOT_AGENTS) -> pd.DataFrame:
    trusts = pd.read_csv(TRUSTS)
    idx = pd.read_parquet(paths.META_DIR / "form_index_abs.parquet")
    t = idx[idx["cik"].isin(trusts["cik"]) & idx["form"].str.startswith("10-D")].copy()
    if agents:
        t = t[t["accession"].str[:10].isin(agents)]
    return t.sort_values(["cik", "date_filed", "accession"])


def fetch(client: SecClient, workers: int = 8, agents: tuple[str, ...] | None = PILOT_AGENTS,
          budget_s: float | None = None, log=print) -> pd.DataFrame:
    prev = pd.read_parquet(LOG) if LOG.exists() else pd.DataFrame(columns=["tend_accession", "status"])
    done = set(prev.loc[prev["status"] == "ok", "tend_accession"])
    todo = targets(agents)
    todo = todo[~todo["accession"].isin(done)]
    log(f"loan-detail statements to fetch: {len(todo):,} (already done {len(done):,})")
    t0, rows = time.monotonic(), []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futs = {}
        for r in todo.itertuples():
            if budget_s and time.monotonic() - t0 > budget_s:
                break
            futs[pool.submit(tend.process, client, int(r.cik), r.accession)] = r
        for i, fut in enumerate(as_completed(futs), 1):
            r = futs[fut]
            try:
                rec = fut.result()
            except Exception as exc:  # recorded, retried on the next run
                rec = {"trust_cik": int(r.cik), "tend_accession": r.accession, "status": f"error {exc}"}
            rec["form"] = r.form
            rec["date_filed"] = str(r.date_filed)
            rows.append(rec)
            if i % 200 == 0:
                log(f"  {i:,}/{len(futs):,} ({time.monotonic() - t0:,.0f}s)")
                tend._save(prev, rows, LOG)
    return tend._save(prev, rows, LOG)
