"""Filesystem layout for the four data layers (SOP section 6).

Everything under DATA_DIR is kept out of git. Point MW_DATA_DIR somewhere else
to keep the multi-gigabyte raw layer on another drive.
"""
from __future__ import annotations

import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
DATA_DIR = Path(os.environ.get("MW_DATA_DIR", REPO_ROOT / "data")).resolve()

RAW_DIR = DATA_DIR / "raw"            # immutable gzipped EX-102 / EX-103, one per accession
META_DIR = DATA_DIR / "meta"          # form indexes, submissions JSON, trusts, filings
PARSED_DIR = DATA_DIR / "parsed"      # typed parquet, partitioned by filing year
PANEL_DIR = DATA_DIR / "panel"        # loan-month features + labels
OUTPUT_DIR = DATA_DIR / "outputs"     # scores, scenario grids, site JSON
STATE_DIR = DATA_DIR / "state"        # sqlite job state, request logs
QUARANTINE_DIR = DATA_DIR / "quarantine"

CONFIG_DIR = REPO_ROOT / "config"
DOCS_DIR = REPO_ROOT / "docs"
FIXTURES_DIR = REPO_ROOT / "fixtures"
SITE_DIR = REPO_ROOT / "site"


def ensure_dirs() -> None:
    for d in (RAW_DIR, META_DIR, PARSED_DIR, PANEL_DIR, OUTPUT_DIR, STATE_DIR, QUARANTINE_DIR):
        d.mkdir(parents=True, exist_ok=True)
