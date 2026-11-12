"""Parse raw EX-102 files to typed parquet (SOP section 7, step 6).

Unit of work = one trust. A trust is re-parsed only when its input hash (the
sorted accession:sha256 list plus the parser schema version) changes, so a run
resumes instead of restarting and a monthly refresh touches only trusts with
new filings.

Output (hive-partitioned by filing year, one file per trust per year):
  parsed/assets/filing_year=YYYY/{cik}.parquet
  parsed/properties/filing_year=YYYY/{cik}.parquet

Reconciliation: for every filing, <assets> and <property> elements counted by
an independent pass must equal the rows written. A filing that fails, that is
not CMBS by namespace, or that does not parse goes to quarantine with a reason
and is not written.
"""
from __future__ import annotations

import hashlib
import shutil
import sqlite3
import time
import traceback
from concurrent.futures import ProcessPoolExecutor, as_completed

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from mwall.common import paths
from mwall.parse import parser, schema

ARROW = {"decimal": pa.float64(), "integer": pa.int64(), "date": pa.date32(), "boolean": pa.bool_(),
         "code": pa.string(), "string": pa.string()}

META_ASSET = [("trust_cik", pa.int64()), ("accession", pa.string()), ("form", pa.string()),
              ("filing_date", pa.date32()), ("is_period_winner", pa.bool_()), ("asset_seq", pa.int32()),
              ("n_property_blocks", pa.int32())]
META_PROP = [("trust_cik", pa.int64()), ("accession", pa.string()), ("form", pa.string()),
             ("filing_date", pa.date32()), ("is_period_winner", pa.bool_()), ("asset_seq", pa.int32()),
             ("asset_number", pa.string()), ("property_seq", pa.int32())]


def _kind(f) -> str:
    return parser.KIND_OVERRIDES.get(f.name, f.kind)


def asset_schema() -> pa.Schema:
    cols = META_ASSET + [(n, ARROW[_kind(f)]) for n, f in schema.asset_fields().items()]
    cols += [(n, pa.string()) for n in sorted(schema.REPEATABLE) if n not in dict(cols)]
    cols = [(n, pa.string()) if n in schema.REPEATABLE else (n, t) for n, t in cols]
    cols.append(("extras", pa.string()))
    return pa.schema(cols, metadata={"schema_version": schema.SCHEMA_VERSION})


def property_schema() -> pa.Schema:
    cols = META_PROP + [(n, ARROW[_kind(f)]) for n, f in schema.property_fields().items()]
    cols.append(("extras", pa.string()))
    return pa.schema(cols, metadata={"schema_version": schema.SCHEMA_VERSION})


MANIFEST_SQL = """
CREATE TABLE IF NOT EXISTS parse_trusts (cik INTEGER PRIMARY KEY, input_hash TEXT, n_files INTEGER, parsed_at TEXT);
CREATE TABLE IF NOT EXISTS parse_files (
    accession TEXT PRIMARY KEY, cik INTEGER, status TEXT, reason TEXT,
    n_assets_xml INTEGER, n_property_xml INTEGER, n_asset_rows INTEGER, n_property_rows INTEGER,
    n_bad_values INTEGER, n_extra_tags INTEGER, reporting_period_end TEXT, schema_version TEXT);
"""


def _table(rows: list[dict], sch: pa.Schema) -> pa.Table:
    cols = {}
    for f in sch:
        cols[f.name] = pa.array([r.get(f.name) for r in rows], type=f.type)
    return pa.table(cols, schema=sch)


def parse_trust(cik: int, files: list[dict]) -> list[dict]:
    """Worker: parse every file of one trust, write parquet, return manifest rows."""
    a_sch, p_sch = asset_schema(), property_schema()
    by_year_a: dict[str, list[dict]] = {}
    by_year_p: dict[str, list[dict]] = {}
    manifest = []
    for f in files:
        m = {"accession": f["accession"], "cik": cik, "status": "ok", "reason": "", "n_assets_xml": None,
             "n_property_xml": None, "n_asset_rows": None, "n_property_rows": None, "n_bad_values": None,
             "n_extra_tags": None, "reporting_period_end": None, "schema_version": schema.SCHEMA_VERSION}
        path = paths.DATA_DIR / f["raw_path"]
        try:
            res = parser.parse_file(path)
            n_a, n_p = parser.count_elements(path)
        except Exception as exc:
            m.update(status="quarantined", reason=f"parse error: {type(exc).__name__}: {exc}"[:500])
            manifest.append(m)
            continue
        m.update(n_assets_xml=n_a, n_property_xml=n_p, n_asset_rows=len(res.assets),
                 n_property_rows=len(res.properties), n_bad_values=res.n_bad_values, n_extra_tags=res.n_extra_tags)
        ends = {a.get("reportingPeriodEndDate") for a in res.assets if a.get("reportingPeriodEndDate")}
        if ends:
            m["reporting_period_end"] = max(ends).isoformat()
        if res.namespace != schema.NS:
            m.update(status="quarantined", reason=f"namespace {res.namespace}")
        elif n_a != len(res.assets) or n_p != len(res.properties):
            m.update(status="quarantined", reason=f"count mismatch assets {n_a}/{len(res.assets)} "
                                                  f"property {n_p}/{len(res.properties)}")
        elif n_a == 0:
            m.update(status="empty", reason="no <assets> records")
        manifest.append(m)
        if m["status"] != "ok":
            continue
        year = str(f["filing_date"])[:4]
        meta = {"trust_cik": cik, "accession": f["accession"], "form": f["form"],
                "filing_date": pd.Timestamp(f["filing_date"]).date(), "is_period_winner": bool(f["is_period_winner"])}
        by_year_a.setdefault(year, []).extend({**meta, **r} for r in res.assets)
        by_year_p.setdefault(year, []).extend({**meta, **r} for r in res.properties)

    for kind, by_year, sch in (("assets", by_year_a, a_sch), ("properties", by_year_p, p_sch)):
        base = paths.PARSED_DIR / kind
        for old in base.glob(f"filing_year=*/{cik}.parquet"):
            old.unlink()
        for year, rows in by_year.items():
            out = base / f"filing_year={year}" / f"{cik}.parquet"
            out.parent.mkdir(parents=True, exist_ok=True)
            tmp = out.with_suffix(".parquet.part")
            pq.write_table(_table(rows, sch), tmp, compression="zstd")
            shutil.move(tmp, out)
    return manifest


def _input_hash(files: list[dict]) -> str:
    h = hashlib.sha256(schema.SCHEMA_VERSION.encode())
    for f in sorted(files, key=lambda x: x["accession"]):
        h.update(f"{f['accession']}:{f['sha256']}:{int(f['is_period_winner'])}".encode())
    return h.hexdigest()


def run(log=print, workers: int = 2, ciks: list[int] | None = None) -> None:
    ingest = sqlite3.connect(paths.STATE_DIR / "ingest.sqlite")
    dl = pd.read_sql("SELECT accession, cik, raw_path, sha256 FROM downloads WHERE status='ok'", ingest)
    filings = pd.read_parquet(paths.META_DIR / "filings.parquet")[
        ["accession", "form", "filing_date", "is_period_winner"]]
    df = dl.merge(filings, on="accession", how="left")
    if ciks:
        df = df[df["cik"].isin(ciks)]
    conn = sqlite3.connect(paths.STATE_DIR / "parse.sqlite", timeout=60)
    conn.executescript(MANIFEST_SQL)
    prev = dict(conn.execute("SELECT cik, input_hash FROM parse_trusts").fetchall())
    jobs = []
    for cik, g in df.groupby("cik"):
        files = g.to_dict("records")
        h = _input_hash(files)
        if prev.get(int(cik)) != h:
            jobs.append((int(cik), files, h))
    log(f"trusts with downloads: {df['cik'].nunique()}; to (re)parse: {len(jobs)}")
    t0 = time.monotonic()
    with ProcessPoolExecutor(max_workers=workers) as pool:
        futs = {pool.submit(parse_trust, cik, files): (cik, files, h) for cik, files, h in jobs}
        for i, fut in enumerate(as_completed(futs), 1):
            cik, files, h = futs[fut]
            try:
                manifest = fut.result()
            except Exception:
                log(f"  trust {cik} failed:\n{traceback.format_exc()}")
                continue
            conn.executemany(
                "INSERT OR REPLACE INTO parse_files VALUES (:accession,:cik,:status,:reason,:n_assets_xml,"
                ":n_property_xml,:n_asset_rows,:n_property_rows,:n_bad_values,:n_extra_tags,"
                ":reporting_period_end,:schema_version)", manifest)
            conn.execute("INSERT OR REPLACE INTO parse_trusts VALUES (?,?,?,datetime('now'))", (cik, h, len(files)))
            conn.commit()
            if i % 20 == 0:
                log(f"  parsed {i}/{len(jobs)} trusts ({time.monotonic()-t0:.0f}s)")
    rej = pd.read_sql("SELECT * FROM parse_files WHERE status != 'ok'", conn)
    paths.QUARANTINE_DIR.mkdir(parents=True, exist_ok=True)
    rej.to_csv(paths.QUARANTINE_DIR / "parse_rejects.csv", index=False)
    summ = pd.read_sql("SELECT status, count(*) n, sum(n_asset_rows) assets, sum(n_property_rows) props, "
                       "sum(n_bad_values) bad, sum(n_extra_tags) extra FROM parse_files GROUP BY status", conn)
    log("parse summary:\n" + summ.to_string(index=False))
