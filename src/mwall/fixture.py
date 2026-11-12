"""Fixture build (SOP section 6 reproducibility standard; Gate 6).

Two trusts, three snapshots each, committed under fixtures/ (well under 5 MB).
``python -m mwall fixture`` copies them into a throwaway data directory, runs
the pipeline stages on them, and compares a summary of the outputs with
fixtures/expected/summary.json. ``--update`` rewrites the expected file after
an intended change; ``--make`` re-copies the fixture inputs from data/.
"""
from __future__ import annotations

import json
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path

import pandas as pd

from mwall.common import paths

FIXTURE = {
    1698685: ["0001539497-17-000524", "0001056404-21-000844", "0001888524-26-019268"],  # BANK 2017-BNK4
    1704459: ["0001539497-17-000720", "0001056404-21-000317", "0001888524-26-018800"],  # GSMS 2017-GS6
}
FX = paths.FIXTURES_DIR
STAGES = [["parse", "--workers", "1"], ["clean", "--workers", "1"]]


def make() -> None:
    """Copy the fixture inputs out of the full data directory (maintainer step)."""
    accs = [a for v in FIXTURE.values() for a in v]
    conn = sqlite3.connect(paths.STATE_DIR / "ingest.sqlite")
    dl = pd.read_sql(f"select * from downloads where accession in ({','.join('?' * len(accs))})", conn, params=accs)
    if len(dl) != len(accs):
        raise SystemExit(f"only {len(dl)} of {len(accs)} fixture filings are downloaded")
    for r in dl.itertuples():
        dest = FX / "raw" / str(r.cik) / f"{r.accession}.xml.gz"
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(paths.DATA_DIR / r.raw_path.replace("\\", "/"), dest)
    dl["raw_path"] = [f"raw/{c}/{a}.xml.gz" for c, a in zip(dl["cik"], dl["accession"])]
    (FX / "meta").mkdir(parents=True, exist_ok=True)
    dl[["accession", "cik", "form", "ex102_name", "raw_path", "sha256", "raw_bytes", "status"]].to_csv(
        FX / "meta" / "downloads.csv", index=False)
    trusts = pd.read_parquet(paths.META_DIR / "trusts.parquet")
    trusts[trusts["trust_cik"].isin(FIXTURE)].to_parquet(FX / "meta" / "trusts.parquet", index=False)
    filings = pd.read_parquet(paths.META_DIR / "filings.parquet")
    filings[filings["accession"].isin(accs)].to_parquet(FX / "meta" / "filings.parquet", index=False)


def _seed(tmp: Path) -> None:
    shutil.copytree(FX / "raw", tmp / "raw")
    shutil.copytree(FX / "meta", tmp / "meta", ignore=shutil.ignore_patterns("downloads.csv"))
    (tmp / "state").mkdir()
    from mwall.ingest import state

    conn = state.connect(tmp / "state" / "ingest.sqlite")
    dl = pd.read_csv(FX / "meta" / "downloads.csv")
    for r in dl.itertuples():
        conn.execute("INSERT INTO downloads (accession, cik, form, ex102_name, raw_path, sha256, raw_bytes, status) "
                     "VALUES (?,?,?,?,?,?,?,?)",
                     (r.accession, int(r.cik), r.form, r.ex102_name, r.raw_path, r.sha256, int(r.raw_bytes), r.status))
    conn.commit()
    conn.close()


def summarize(data_dir: Path) -> dict:
    out = {}
    for f in sorted((data_dir / "parsed" / "loan_period").glob("*.parquet")):
        lp = pd.read_parquet(f)
        for acc, g in lp.groupby("accession"):
            out[acc] = {
                "loans": int(len(g)),
                "scheduled_balance": round(float(g["reportPeriodEndScheduledLoanBalanceAmount"].sum()), 2),
                "layouts": {k: int(v) for k, v in g["layout"].value_counts().sort_index().items()},
                "fin_basis": {k: int(v) for k, v in g["fin_basis"].value_counts().sort_index().items()},
                "noi_annual": round(float(g["fin_noi_annual"].sum()), 2),
                "flags": {c: int(g[c].sum()) for c in sorted(g.columns) if c.startswith("flag_") and g[c].sum()},
            }
    for f in sorted((data_dir / "parsed" / "property_period").glob("*.parquet")):
        pp = pd.read_parquet(f)
        for acc, g in pp.groupby("accession"):
            out.setdefault(acc, {})["properties"] = int((g["block_role"] == "property").sum())
    return out


def build(update: bool = False, log=print) -> bool:
    with tempfile.TemporaryDirectory(prefix="mwall-fixture-") as td:
        tmp = Path(td)
        _seed(tmp)
        env = {**os.environ, "MW_DATA_DIR": str(tmp), "PYTHONWARNINGS": "ignore"}
        for st in STAGES:
            r = subprocess.run([sys.executable, "-m", "mwall", *st], env=env, capture_output=True, text=True)
            if r.returncode != 0:
                log(r.stdout[-2000:] + r.stderr[-2000:])
                raise SystemExit(f"fixture stage {st[0]} failed")
        got = summarize(tmp)
    exp_path = FX / "expected" / "summary.json"
    if update or not exp_path.exists():
        exp_path.parent.mkdir(parents=True, exist_ok=True)
        exp_path.write_text(json.dumps(got, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        log(f"wrote {exp_path} ({len(got)} snapshots)")
        return True
    expected = json.loads(exp_path.read_text(encoding="utf-8"))
    ok = got == expected
    if ok:
        log(f"fixture build matches stored outputs ({len(got)} snapshots)")
    else:
        for acc in sorted(set(got) | set(expected)):
            if got.get(acc) != expected.get(acc):
                log(f"DIFF {acc}:\n  expected {expected.get(acc)}\n  got      {got.get(acc)}")
    return ok
