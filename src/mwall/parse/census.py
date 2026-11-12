"""Tag census over a stratified sample of raw EX-102 files (SOP section 7, step 5).

Lists every tag that occurs, per parent (assets / property), with the share of
files and records carrying it, and compares that list with the SEC XSD. Also
records the distinct values of every code field, which is how we check that
filers only use codes the specification allows.

Writes docs/qa/tag_census.csv, docs/qa/code_values.csv and docs/qa/tag_census.md.
"""
from __future__ import annotations

import collections
import gzip

import pandas as pd
from lxml import etree

from mwall.common import paths
from mwall.parse import schema
from mwall.parse.parser import _local


def _sample(per_group: int) -> pd.DataFrame:
    import sqlite3

    conn = sqlite3.connect(paths.STATE_DIR / "ingest.sqlite")
    dl = pd.read_sql("SELECT accession, cik, raw_path FROM downloads WHERE status='ok'", conn)
    filings = pd.read_parquet(paths.META_DIR / "filings.parquet")[["accession", "filing_date"]]
    trusts = pd.read_parquet(paths.META_DIR / "trusts.parquet")[["trust_cik", "deal_family", "vintage"]]
    df = dl.merge(filings, on="accession").merge(trusts, left_on="cik", right_on="trust_cik")
    df["filing_year"] = df["filing_date"].astype(str).str[:4]
    df = df.sample(frac=1.0, random_state=20261112)
    return df.groupby(["deal_family", "vintage", "filing_year"]).head(per_group)


def run(sample_per_group: int = 3, log=print) -> None:
    sample = _sample(sample_per_group)
    log(f"census sample: {len(sample)} files across {sample.groupby(['deal_family','vintage','filing_year']).ngroups} "
        f"family x vintage x filing-year groups")
    code_fields = {n for p in ("assets", "property") for n, f in schema.fields()[p].items() if f.kind == "code"}
    files_with = collections.Counter()
    records_with = collections.Counter()
    n_records = collections.Counter()
    values = collections.defaultdict(collections.Counter)
    years_with = collections.defaultdict(set)
    for r in sample.itertuples():
        seen = set()
        with gzip.open(paths.DATA_DIR / r.raw_path, "rb") as fh:
            for _ev, elem in etree.iterparse(fh, events=("end",), huge_tree=True):
                name = _local(elem.tag)
                if name not in ("assets", "property"):
                    continue
                parent = name
                n_records[parent] += 1
                rec_tags = set()
                for child in elem:
                    if not isinstance(child.tag, str):
                        continue
                    t = _local(child.tag)
                    if t == "property":
                        continue
                    rec_tags.add(t)
                    if t in code_fields:
                        values[(parent, t)][(child.text or "").strip()] += 1
                for t in rec_tags:
                    records_with[(parent, t)] += 1
                    seen.add((parent, t))
                if name == "assets":
                    elem.clear()
        for key in seen:
            files_with[key] += 1
            years_with[key].add(r.filing_year)

    known = {(p, n) for p in ("assets", "property") for n in schema.fields()[p]}
    keys = sorted(set(files_with) | known)
    rows = []
    for parent, tag in keys:
        rows.append({
            "parent": parent,
            "tag": tag,
            "in_xsd": (parent, tag) in known,
            "files_with_tag": files_with.get((parent, tag), 0),
            "share_files": round(files_with.get((parent, tag), 0) / max(1, len(sample)), 4),
            "share_records": round(records_with.get((parent, tag), 0) / max(1, n_records[parent]), 4),
            "filing_years": ",".join(sorted(years_with.get((parent, tag), []))),
        })
    out = pd.DataFrame(rows).sort_values(["parent", "in_xsd", "share_records"], ascending=[True, True, False])
    qa = paths.DOCS_DIR / "qa"
    qa.mkdir(parents=True, exist_ok=True)
    out.to_csv(qa / "tag_census.csv", index=False)

    vrows = [{"parent": p, "tag": t, "value": v, "count": c} for (p, t), cnt in values.items() for v, c in cnt.items()]
    pd.DataFrame(vrows).sort_values(["tag", "count"], ascending=[True, False]).to_csv(qa / "code_values.csv", index=False)

    not_in_xsd = out[~out["in_xsd"]]
    never_seen = out[out["in_xsd"] & (out["files_with_tag"] == 0)]
    lines = [
        "# Tag census",
        "",
        f"Sample: {len(sample)} EX-102 files, up to {sample_per_group} per deal family x vintage x filing year "
        f"({sample['deal_family'].nunique()} families, filing years {sample['filing_year'].min()} to "
        f"{sample['filing_year'].max()}). Records: {n_records['assets']:,} assets, {n_records['property']:,} property blocks.",
        "",
        f"Tags observed that are not in the SEC XSD v3.1: {len(not_in_xsd)}",
        "",
    ]
    lines += [f"- `{r.parent}/{r.tag}` in {r.files_with_tag} files ({r.filing_years})" for r in not_in_xsd.itertuples()]
    lines += ["", f"XSD tags never observed in the sample: {len(never_seen)}", ""]
    lines += [f"- `{r.parent}/{r.tag}`" for r in never_seen.itertuples()]
    (qa / "tag_census.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    log(f"tags not in XSD: {len(not_in_xsd)}; XSD tags never seen: {len(never_seen)}; wrote {qa}")
