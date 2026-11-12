"""Download raw EX-102 (and EX-103) exhibits (SOP section 7, step 4).

* Every ABS-EE and ABS-EE/A is downloaded, superseded ones included: the raw
  layer is a complete, immutable copy, and the parse layer decides which wins.
* Files land at raw/{cik}/{accession}.xml.gz (EX-102) and
  raw/{cik}/{accession}.ex103.xml.gz, written via a temp name and renamed.
* The SHA-256 of the uncompressed bytes is recorded in the state database.
* A filing with no EX-102 is recorded with status 'no_ex102'. The 10-D for that
  period is checked for an attached EX-102 before the filing is called missing.
* Resumable: anything with status 'ok' or a terminal status is skipped. A
  ``budget_s`` stops the run cleanly between filings.
"""
from __future__ import annotations

import time
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait

import pandas as pd

from mwall.common import paths
from mwall.ingest import filing_index as fi
from mwall.ingest import state
from mwall.ingest.sec_client import SecClient

TERMINAL = ("ok", "no_ex102")


def raw_path(cik: int, accession: str, kind: str = "ex102"):
    suffix = ".xml.gz" if kind == "ex102" else ".ex103.xml.gz"
    return paths.RAW_DIR / str(cik) / f"{accession}{suffix}"


def _docs(client: SecClient, conn_cache: dict, cik: int, accession: str):
    if accession in conn_cache:
        return 200, conn_cache[accession][0], conn_cache[accession][1]
    return fi.fetch_filing_docs(client, cik, accession)


def process(client: SecClient, cached_docs: dict, cik: int, accession: str, form: str,
            ten_d_for_period: str | None) -> dict:
    rec = {"accession": accession, "cik": cik, "form": form, "ex102_name": None, "raw_path": None,
           "sha256": None, "raw_bytes": None, "ex103_name": None, "ex103_path": None,
           "ex103_sha256": None, "status": "error", "note": "", "period": None, "docs": None}
    status, period, docs = _docs(client, cached_docs, cik, accession)
    rec["period"], rec["docs"] = period, docs
    if status != 200:
        rec["note"] = f"index status {status}"
        return rec
    ex102 = fi.pick(docs, "EX-102")
    if ex102 is None and ten_d_for_period:
        s2, _, docs2 = fi.fetch_filing_docs(client, cik, ten_d_for_period)
        if s2 == 200 and fi.pick(docs2, "EX-102"):
            ex102 = fi.pick(docs2, "EX-102")
            rec["note"] = f"EX-102 found on 10-D {ten_d_for_period}"
            accession_src = ten_d_for_period
        else:
            accession_src = accession
    else:
        accession_src = accession
    if ex102 is None:
        rec["status"] = "no_ex102"
        rec["note"] = rec["note"] or "no EX-102 on ABS-EE or its period's 10-D"
        return rec
    dest = raw_path(cik, accession)
    st, sha, size = client.download_gz(fi.doc_url(cik, accession_src, ex102["name"]), dest)
    if st != 200:
        rec["note"] = f"ex102 status {st}"
        return rec
    rec.update(ex102_name=ex102["name"], raw_path=dest.relative_to(paths.DATA_DIR).as_posix(), sha256=sha, raw_bytes=size)
    ex103 = fi.pick(docs, "EX-103")
    if ex103 is not None:
        d3 = raw_path(cik, accession, "ex103")
        st3, sha3, _ = client.download_gz(fi.doc_url(cik, accession, ex103["name"]), d3)
        if st3 == 200:
            rec.update(ex103_name=ex103["name"], ex103_path=d3.relative_to(paths.DATA_DIR).as_posix(), ex103_sha256=sha3)
    rec["status"] = "ok"
    return rec


def run(client: SecClient, workers: int = 4, log=print, budget_s: float | None = None,
        ciks: list[int] | None = None, max_filings: int | None = None) -> None:
    t_start = time.monotonic()
    filings = pd.read_parquet(paths.META_DIR / "filings.parquet")
    conn = state.connect()
    done = {r[0] for r in conn.execute(
        f"SELECT accession FROM downloads WHERE status IN ({','.join('?' * len(TERMINAL))})", TERMINAL)}
    cached_docs = {
        r[0]: (r[1], __import__("json").loads(r[2]))
        for r in conn.execute("SELECT accession, period_of_report, docs_json FROM filing_docs WHERE status=200")
    }
    abs_ee = filings[filings["form_family"] == "ABS-EE"]
    ten_d = filings[filings["form_family"] == "10-D"].set_index(["trust_cik", "period_key"])["accession"]
    ten_d = ten_d[~ten_d.index.duplicated(keep="last")].to_dict()
    todo = abs_ee[~abs_ee["accession"].isin(done)]
    if ciks:
        todo = todo[todo["trust_cik"].isin(ciks)]
    # Order: a stratified head start first (each trust's earliest filing plus one
    # filing per trust per filing year), so the tag census sees every family,
    # vintage and schema era early. Then everything else, newest first, because
    # recent filings are the scoring snapshot.
    todo = todo.sort_values("filing_date")
    year = todo["filing_date"].astype(str).str[:4]
    strat = todo.groupby([todo["trust_cik"], year]).head(1).index
    todo = pd.concat([
        todo.loc[strat].sort_values("filing_date"),
        todo.drop(index=strat).sort_values("filing_date", ascending=False),
    ])
    if max_filings:
        todo = todo.head(max_filings)
    total = len(todo)
    log(f"ABS-EE filings: {len(abs_ee):,}; done: {len(done):,}; to download now: {total:,}")
    if total == 0:
        return

    it = iter(todo.itertuples())
    n_done = n_ok = n_bytes = 0
    with ThreadPoolExecutor(max_workers=workers) as pool:
        pending = set()

        def submit_next() -> bool:
            if budget_s is not None and time.monotonic() - t_start > budget_s:
                return False
            r = next(it, None)
            if r is None:
                return False
            pending.add(pool.submit(process, client, cached_docs, int(r.trust_cik), r.accession, r.form,
                                    ten_d.get((int(r.trust_cik), r.period_key))))
            return True

        for _ in range(workers * 2):
            if not submit_next():
                break
        while pending:
            finished, _ = wait(pending, return_when=FIRST_COMPLETED)
            for fut in finished:
                pending.discard(fut)
                try:
                    rec = fut.result()
                except Exception as exc:  # logged; retried next run
                    log(f"  error: {exc}")
                    submit_next()
                    continue
                if rec["docs"] is not None and rec["accession"] not in cached_docs:
                    state.put_filing_docs(conn, rec["accession"], rec["cik"], 200, rec["period"], rec["docs"])
                conn.execute(
                    "INSERT OR REPLACE INTO downloads VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (rec["accession"], rec["cik"], rec["form"], rec["ex102_name"], rec["raw_path"], rec["sha256"],
                     rec["raw_bytes"], rec["ex103_name"], rec["ex103_path"], rec["ex103_sha256"], rec["status"],
                     rec["note"], state.now()),
                )
                n_done += 1
                n_ok += rec["status"] == "ok"
                n_bytes += rec["raw_bytes"] or 0
                if n_done % 25 == 0:
                    conn.commit()
                if n_done % 200 == 0:
                    rate = n_done / max(1e-9, time.monotonic() - t_start)
                    log(f"  {n_done:,}/{total:,} filings ({n_ok:,} ok, {n_bytes/1e9:.2f} GB raw, "
                        f"{rate:.2f} filings/s, ~{(total - n_done)/max(rate,1e-9)/3600:.1f} h left)")
                submit_next()
    conn.commit()
    log(f"done this run: {n_done:,} filings, {n_ok:,} ok, {n_bytes/1e9:.2f} GB raw")
