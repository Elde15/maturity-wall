"""Discover the registered CMBS trust universe (SOP section 7, step 2).

1. Every CIK that filed ABS-EE since 2017Q1 is a candidate (the form index).
2. Each candidate's latest EX-102 is probed: we stream only its first 4 KB and
   read the root namespace. ``.../absee/cmbs/assetdata`` is the definitive flag.
   Probing every ABS-EE filer (auto, equipment, RMBS included) is cheap and
   catches CMBS trusts whose names no pattern list would match.
3. Name patterns are kept as a cross-check, and to list CMBS-looking 10-D filers
   that never filed asset-level data (the 2016-vintage coverage question).
"""
from __future__ import annotations

import re
from concurrent.futures import ThreadPoolExecutor, as_completed

import pandas as pd
import yaml

from mwall.common import paths
from mwall.ingest import filing_index as fi
from mwall.ingest import state
from mwall.ingest.sec_client import SecClient


def load_universe_config() -> dict:
    with open(paths.CONFIG_DIR / "universe.yaml", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


SERIES_RE = re.compile(r"\b((?:19|20)\d{2})-([A-Z0-9]+)\b", re.I)


def parse_trust_name(name: str, cfg: dict) -> tuple[str, int | None, str | None]:
    """Return (deal family, vintage year, series code) from a trust name."""
    m = SERIES_RE.search(name)
    vintage = int(m.group(1)) if m else None
    series = m.group(2).upper() if m else None
    rest = SERIES_RE.sub(" ", name)
    rest = re.sub(r"[^A-Za-z0-9 ]", " ", rest)
    stop = {w.upper() for w in cfg["family_stopwords"]}
    words = [w for w in rest.upper().split() if w not in stop]
    norm = " ".join(words)
    family = cfg["family_aliases"].get(norm, norm or "UNKNOWN")
    return str(family), vintage, series


def name_looks_cmbs(name: str, cfg: dict) -> bool:
    return any(re.search(p, name, re.I) for p in cfg["cmbs_name_patterns"])


def _probe(client: SecClient, cik: int, accession: str) -> dict:
    out = {"cik": cik, "probe_accession": accession, "ex102_name": None, "root_tag": None,
           "namespace": None, "note": "", "status": None, "period": None, "docs": []}
    status, period, docs = fi.fetch_filing_docs(client, cik, accession)
    out.update(status=status, period=period, docs=docs)
    if status != 200:
        out["note"] = f"index status {status}"
        return out
    ex = fi.pick(docs, "EX-102")
    if ex is None:
        out["note"] = "no EX-102 in filing"
        return out
    out["ex102_name"] = ex["name"]
    head = client.head_bytes(fi.doc_url(cik, accession, ex["name"]), nbytes=4096)
    if head.status != 200:
        out["note"] = f"ex102 status {head.status}"
        return out
    out["root_tag"], out["namespace"] = fi.root_namespace(head.content)
    return out


def probe_candidates(client: SecClient, idx: pd.DataFrame, workers: int = 4, log=print) -> None:
    cfg = load_universe_config()
    conn = state.connect()
    absee = idx[idx["form"].isin(["ABS-EE", "ABS-EE/A"])].sort_values("date_filed")
    latest = absee.groupby("cik").tail(1)
    done = {r[0] for r in conn.execute("SELECT cik FROM candidates WHERE namespace IS NOT NULL OR note LIKE 'no EX-102%'")}
    todo = latest[~latest["cik"].isin(done)]
    log(f"ABS-EE filers: {latest['cik'].nunique()}, already probed: {len(done)}, to probe: {len(todo)}")
    suffix = cfg["cmbs_namespace_suffix"]
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futs = {pool.submit(_probe, client, int(r.cik), r.accession): r for r in todo.itertuples()}
        for i, fut in enumerate(as_completed(futs), 1):
            r = futs[fut]
            try:
                res = fut.result()
            except Exception as exc:  # recorded, retried next run
                conn.execute(
                    "INSERT OR REPLACE INTO candidates VALUES (?,?,?,?,?,?,?,?,?)",
                    (int(r.cik), r.company_name, r.accession, None, None, None, None, f"error: {exc}", state.now()),
                )
                continue
            if res["status"] == 200:
                state.put_filing_docs(conn, r.accession, int(r.cik), 200, res["period"], res["docs"])
            ns = res["namespace"]
            is_cmbs = None if ns is None else int(ns.endswith(suffix))
            conn.execute(
                "INSERT OR REPLACE INTO candidates VALUES (?,?,?,?,?,?,?,?,?)",
                (int(r.cik), r.company_name, r.accession, res["ex102_name"], res["root_tag"], ns, is_cmbs,
                 res["note"], state.now()),
            )
            if i % 50 == 0:
                conn.commit()
                log(f"  probed {i}/{len(todo)}")
    conn.commit()


def build_trusts(idx: pd.DataFrame) -> pd.DataFrame:
    """Write the trusts table and the name-pattern cross-check report."""
    cfg = load_universe_config()
    conn = state.connect()
    cand = pd.read_sql("SELECT * FROM candidates", conn)
    cmbs = cand[cand["is_cmbs"] == 1].copy()

    span = idx.groupby("cik").agg(first_filing_date=("date_filed", "min"), last_filing_date=("date_filed", "max"))
    n_absee = idx[idx["form"].isin(["ABS-EE", "ABS-EE/A"])].groupby("cik").size().rename("n_absee_index")
    n_10d = idx[idx["form"].isin(["10-D", "10-D/A"])].groupby("cik").size().rename("n_10d_index")
    latest_name = idx.sort_values("date_filed").groupby("cik")["company_name"].last().rename("trust_name")

    trusts = cmbs[["cik"]].merge(latest_name, left_on="cik", right_index=True, how="left")
    parsed = trusts["trust_name"].apply(lambda n: parse_trust_name(n, cfg))
    trusts["deal_family"] = [p[0] for p in parsed]
    trusts["vintage"] = [p[1] for p in parsed]
    trusts["series"] = [p[2] for p in parsed]
    trusts = trusts.join(span, on="cik").join(n_absee, on="cik").join(n_10d, on="cik")
    trusts = trusts.rename(columns={"cik": "trust_cik"}).sort_values(["vintage", "trust_name"])
    # Depositor entities (no "YYYY-SERIES" token) file the pre-offering ABS-EE
    # under their own CIK. They are not trusts; keep them in a separate table.
    is_depositor = trusts["series"].isna()
    trusts.loc[is_depositor].to_parquet(paths.META_DIR / "depositors.parquet", index=False)
    trusts = trusts.loc[~is_depositor].copy()
    # Deals issued before Reg AB II asset-level reporting (Nov 2016) that show a
    # stray CMBS ABS-EE are kept but flagged, so the parse stage records why.
    trusts["flag_pre_regab2_vintage"] = trusts["vintage"] < 2016
    trusts.to_parquet(paths.META_DIR / "trusts.parquet", index=False)

    # Cross-check: names that look CMBS but are not confirmed, and the reverse.
    all_names = latest_name.rename("company_name").reset_index()
    all_names["looks_cmbs"] = all_names["company_name"].apply(lambda n: name_looks_cmbs(n, cfg))
    filers_absee = set(idx.loc[idx["form"].isin(["ABS-EE", "ABS-EE/A"]), "cik"])
    all_names["filed_absee"] = all_names["cik"].isin(filers_absee)
    all_names["confirmed_cmbs"] = all_names["cik"].isin(set(cmbs["cik"]))
    all_names = all_names.merge(cand[["cik", "namespace", "note"]], on="cik", how="left")
    all_names.to_parquet(paths.META_DIR / "universe_crosscheck.parquet", index=False)
    return trusts
