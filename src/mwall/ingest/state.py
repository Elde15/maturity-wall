"""SQLite job state for the resumable ingest.

Only the main thread writes; worker threads return results. That keeps sqlite
simple and lets a killed run resume from whatever was committed.
"""
from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path

from mwall.common import paths

SCHEMA = """
CREATE TABLE IF NOT EXISTS filing_docs (
    accession TEXT PRIMARY KEY,
    cik INTEGER NOT NULL,
    status INTEGER NOT NULL,
    period_of_report TEXT,
    docs_json TEXT,
    fetched_at TEXT
);
CREATE TABLE IF NOT EXISTS candidates (
    cik INTEGER PRIMARY KEY,
    company_name TEXT,
    probe_accession TEXT,
    ex102_name TEXT,
    root_tag TEXT,
    namespace TEXT,
    is_cmbs INTEGER,
    note TEXT,
    checked_at TEXT
);
CREATE TABLE IF NOT EXISTS submissions (
    cik INTEGER PRIMARY KEY,
    fetched_at TEXT,
    n_filings INTEGER
);
CREATE TABLE IF NOT EXISTS downloads (
    accession TEXT PRIMARY KEY,
    cik INTEGER NOT NULL,
    form TEXT,
    ex102_name TEXT,
    raw_path TEXT,
    sha256 TEXT,
    raw_bytes INTEGER,
    ex103_name TEXT,
    ex103_path TEXT,
    ex103_sha256 TEXT,
    status TEXT NOT NULL,
    note TEXT,
    downloaded_at TEXT
);
"""


def connect(path: Path | None = None) -> sqlite3.Connection:
    paths.ensure_dirs()
    conn = sqlite3.connect(path or (paths.STATE_DIR / "ingest.sqlite"), timeout=60)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.executescript(SCHEMA)
    return conn


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S")


def put_filing_docs(conn, accession: str, cik: int, status: int, period: str | None, docs: list[dict]) -> None:
    conn.execute(
        "INSERT OR REPLACE INTO filing_docs VALUES (?,?,?,?,?,?)",
        (accession, cik, status, period, json.dumps(docs), now()),
    )


def get_filing_docs(conn, accession: str) -> tuple[str | None, list[dict]] | None:
    row = conn.execute(
        "SELECT period_of_report, docs_json FROM filing_docs WHERE accession=? AND status=200", (accession,)
    ).fetchone()
    if row is None:
        return None
    return row[0], json.loads(row[1])
