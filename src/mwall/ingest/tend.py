"""10-D distribution statements (EX-99.1) for the balance reconciliation (SOP section 8 acceptance).

For each trust and period, the certificate administrator's statement reports the
pool's ending scheduled (and often actual) collateral balance. The sum of loan
balances from the asset-level data must match it within 0.5%.

Statements are stored gzipped under raw/{cik}/{accession}.ex991.htm.gz (the
raw layer stays immutable) and the extracted balances go to
meta/tend_balances.parquet with the pattern that matched, so a format we do
not yet read shows up as 'no_pattern' instead of a silent miss.
"""
from __future__ import annotations

import gzip
import html
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import pandas as pd

from mwall.common import paths
from mwall.ingest import filing_index as fi
from mwall.ingest.sec_client import SecClient

NUM = r"\$?\s*([\d,]+\.\d{2})"
PATTERNS = [
    ("cts_sched", re.compile(r"Ending Scheduled Collateral Balance\s+" + NUM, re.I)),
    ("cts_actual", re.compile(r"Ending Actual Collateral Balance\s+" + NUM, re.I)),
    ("ending_sched_bal", re.compile(r"Ending Scheduled Balance\s+" + NUM, re.I)),
    ("ending_pool_bal", re.compile(r"Ending (?:Pool|Aggregate|Stated) (?:Principal )?Balance\s+" + NUM, re.I)),
    ("stated_prin_bal", re.compile(r"(?:Ending )?Aggregate Stated Principal Balance[^\d$]{0,60}" + NUM, re.I)),
]


def to_text(raw: bytes) -> str:
    t = raw.decode("latin-1", errors="replace")
    t = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", t)
    t = html.unescape(re.sub(r"<[^>]+>", " ", t))
    return re.sub(r"\s+", " ", t)


# Wells Fargo CTS (pre-2021): Principal Reconciliation "Total" row of 9 numbers;
# the 7th is the stated (scheduled) ending balance, the 8th the unpaid (actual) one.
WF_RECON = re.compile(r"Principal Reconciliation.{0,800}?Distribution Amount\s+Total\s+((?:\(?-?[\d,]+\.\d{2}\)?\s+){8})", re.I)
# Citi: stratification tables end with "Total <loans> <balance> 100.00".
STRAT_TOTAL = re.compile(r"Stratification Detail.{0,4000}?Totals?\s+(\d+)\s+([\d,]+\.\d{2})\s+100\.0+", re.I)


def _num(s: str) -> float:
    s = s.strip()
    neg = s.startswith("(") or s.startswith("-")
    v = float(s.strip("()-").replace(",", ""))
    return -v if neg else v


def extract_balances(raw: bytes) -> dict:
    txt = to_text(raw)
    out = {"tend_sched_balance": None, "tend_actual_balance": None, "tend_pattern": "no_pattern",
           "tend_loan_count": None}
    m = WF_RECON.search(txt)
    if m:
        nums = m.group(1).split()
        out.update(tend_sched_balance=_num(nums[6]), tend_actual_balance=_num(nums[7]), tend_pattern="wf_prin_recon")
    m = STRAT_TOTAL.search(txt)
    if m:
        out["tend_loan_count"] = int(m.group(1))
        if out["tend_sched_balance"] is None:
            out.update(tend_sched_balance=_num(m.group(2)), tend_pattern="strat_total")
    if out["tend_sched_balance"] is not None:
        return out
    for name, rx in PATTERNS:
        m = rx.search(txt)
        if not m:
            continue
        v = float(m.group(1).replace(",", ""))
        if name.endswith("actual"):
            out["tend_actual_balance"] = out["tend_actual_balance"] or v
        elif out["tend_sched_balance"] is None:
            out["tend_sched_balance"] = v
            out["tend_pattern"] = name
    return out


def process(client: SecClient, cik: int, accession: str) -> dict:
    rec = {"trust_cik": cik, "tend_accession": accession, "status": "error", "ex991_name": None}
    cached = paths.RAW_DIR / str(cik) / f"{accession}.ex991.htm.gz"
    if cached.exists():  # resume without touching the network
        with gzip.open(cached, "rb") as fh:
            rec.update(extract_balances(fh.read()))
        rec.update(status="ok", ex991_name="(cached)")
        return rec
    st, _period, docs = fi.fetch_filing_docs(client, cik, accession)
    if st != 200:
        rec["status"] = f"index {st}"
        return rec
    ex = [d for d in docs if d["type"].upper().startswith("EX-99") and d["name"].lower().endswith((".htm", ".html", ".txt"))]
    if not ex:
        rec["status"] = "no_ex99"
        return rec
    ex = sorted(ex, key=lambda d: (d["type"] != "EX-99.1", -(d["size"] or 0)))[0]
    dest = paths.RAW_DIR / str(cik) / f"{accession}.ex991.htm.gz"
    if not dest.exists():
        s2, _sha, _size = client.download_gz(fi.doc_url(cik, accession, ex["name"]), dest)
        if s2 != 200:
            rec["status"] = f"ex99 {s2}"
            return rec
    with gzip.open(dest, "rb") as fh:
        rec.update(extract_balances(fh.read()))
    rec.update(status="ok", ex991_name=ex["name"])
    return rec


def targets(per_agent: int | None = None) -> pd.DataFrame:
    """10-D period winners whose trust-period also has an ABS-EE (matched on filing date within 3 days)."""
    f = pd.read_parquet(paths.META_DIR / "filings.parquet")
    tens = f[(f["form_family"] == "10-D") & f["is_period_winner"]].copy()
    if per_agent:
        tens["agent"] = tens["accession"].str[:10]
        tens = tens.sample(frac=1.0, random_state=7).groupby("agent").head(per_agent)
    return tens


def _save(prev: pd.DataFrame, rows: list[dict], out_path) -> pd.DataFrame:
    new = pd.DataFrame(rows)
    allr = pd.concat([prev[~prev["tend_accession"].isin(set(new.get("tend_accession", [])))], new], ignore_index=True)
    tmp = out_path.with_suffix(".tmp.parquet")
    allr.to_parquet(tmp, index=False)
    tmp.replace(out_path)
    return allr


def run(client: SecClient, workers: int = 4, per_agent: int | None = None, budget_s: float | None = None,
        log=print) -> pd.DataFrame:
    out_path = paths.META_DIR / "tend_balances.parquet"
    prev = pd.read_parquet(out_path) if out_path.exists() else pd.DataFrame(columns=["tend_accession", "status"])
    done = set(prev.loc[prev["status"] == "ok", "tend_accession"])
    todo = targets(per_agent)
    todo = todo[~todo["accession"].isin(done)]
    log(f"10-D statements to fetch: {len(todo):,} (already done {len(done):,})")
    t0, rows = time.monotonic(), []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futs = {}
        for r in todo.itertuples():
            if budget_s and time.monotonic() - t0 > budget_s:
                break
            futs[pool.submit(process, client, int(r.trust_cik), r.accession)] = r
        for i, fut in enumerate(as_completed(futs), 1):
            r = futs[fut]
            try:
                rec = fut.result()
            except Exception as exc:
                rec = {"trust_cik": int(r.trust_cik), "tend_accession": r.accession, "status": f"error {exc}"}
            rec["tend_filing_date"] = str(r.filing_date)
            rec["tend_report_date"] = r.report_date
            rows.append(rec)
            if i % 200 == 0:
                log(f"  {i:,}/{len(futs):,} ({time.monotonic() - t0:,.0f}s)")
            if i % 1000 == 0:
                _save(prev, rows, out_path)  # checkpoint
    allr = _save(prev, rows, out_path)
    log(f"statements: {len(allr):,}; patterns: {allr.get('tend_pattern', pd.Series(dtype=str)).value_counts().to_dict()}")
    return allr


def reextract(log=print) -> pd.DataFrame:
    """Re-run extraction over stored statements (after adding a pattern); no network."""
    out_path = paths.META_DIR / "tend_balances.parquet"
    tb = pd.read_parquet(out_path)
    for i, r in tb[tb["status"] == "ok"].iterrows():
        f = paths.RAW_DIR / str(int(r["trust_cik"])) / f"{r['tend_accession']}.ex991.htm.gz"
        if f.exists():
            with gzip.open(f, "rb") as fh:
                for k, v in extract_balances(fh.read()).items():
                    tb.at[i, k] = v
    tb.to_parquet(out_path, index=False)
    log(f"re-extracted; patterns: {tb['tend_pattern'].value_counts().to_dict()}")
    return tb
