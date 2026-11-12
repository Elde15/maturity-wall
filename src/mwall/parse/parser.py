"""Streaming parser for one CMBS EX-102 file (SOP section 7, step 5).

One ``<assets>`` element becomes one asset row. Each ``<property>`` block inside
it becomes one property row, numbered by ``property_seq`` within its asset.
Values are typed per the XSD. Nothing is dropped silently:

* a tag the schema does not know goes into the row's ``extras`` JSON;
* a value that fails its type goes to ``extras`` under ``_bad.<tag>`` and the
  typed column is left null;
* repeatable code elements are joined with ``|`` in document order.

Units are NOT normalized here (occupancy arrives as both 0.83 and 93.9); that
is the clean layer's job, so the parsed layer stays a faithful copy.
"""
from __future__ import annotations

import datetime as dt
import gzip
import json
from dataclasses import dataclass, field
from pathlib import Path

from lxml import etree

from mwall.parse import schema

NSB = "{" + schema.NS + "}"
KIND_OVERRIDES = {"GroupID": "string"}  # rule says alphanumeric; XSD says integer


def _local(tag: str) -> str:
    return tag[len(NSB):] if tag.startswith(NSB) else tag.split("}")[-1]


def convert(kind: str, text: str):
    """Typed value, or raise ValueError."""
    t = text.strip()
    if t == "":
        return None
    if kind == "decimal":
        return float(t)
    if kind == "integer":
        return int(float(t)) if "." in t else int(t)
    if kind == "date":
        m, d, y = t.split("-")
        return dt.date(int(y), int(m), int(d))
    if kind == "boolean":
        lt = t.lower()
        if lt in ("true", "1", "y", "yes"):
            return True
        if lt in ("false", "0", "n", "no"):
            return False
        raise ValueError(t)
    return t  # code / string kept verbatim


@dataclass
class ParseResult:
    assets: list[dict] = field(default_factory=list)
    properties: list[dict] = field(default_factory=list)
    root_tag: str | None = None
    namespace: str | None = None
    n_assets_seen: int = 0
    n_property_seen: int = 0
    n_bad_values: int = 0
    n_extra_tags: int = 0


def _typed_children(elem, known: dict, res: ParseResult, row: dict, extras: dict, repeat: set) -> list:
    props = []
    for child in elem:
        if not isinstance(child.tag, str):  # comments / processing instructions
            continue
        name = _local(child.tag)
        if name == "property":
            props.append(child)
            continue
        text = child.text or ""
        if name in repeat:
            prev = row.get(name)
            row[name] = text.strip() if prev is None else f"{prev}|{text.strip()}"
            continue
        f = known.get(name)
        if f is None:
            res.n_extra_tags += 1
            extras[name] = text.strip() if len(child) == 0 else etree.tostring(child, encoding="unicode")
            continue
        kind = KIND_OVERRIDES.get(name, f.kind)
        try:
            row[name] = convert(kind, text)
        except (ValueError, TypeError):
            res.n_bad_values += 1
            row[name] = None
            extras[f"_bad.{name}"] = text.strip()
    return props


def parse_file(path: Path | str) -> ParseResult:
    afields, pfields = schema.asset_fields(), schema.property_fields()
    res = ParseResult()
    opener = gzip.open if str(path).endswith(".gz") else open
    with opener(path, "rb") as fh:
        ctx = etree.iterparse(fh, events=("start", "end"), huge_tree=True, recover=False)
        depth = 0
        for event, elem in ctx:
            if event == "start":
                depth += 1
                if depth == 1:
                    res.root_tag = _local(elem.tag)
                    res.namespace = elem.tag[1:].split("}")[0] if elem.tag.startswith("{") else None
                continue
            depth -= 1
            if depth != 1 or _local(elem.tag) != "assets":
                continue
            seq = res.n_assets_seen
            res.n_assets_seen += 1
            row: dict = {"asset_seq": seq}
            extras: dict = {}
            props = _typed_children(elem, afields, res, row, extras, schema.REPEATABLE)
            row["n_property_blocks"] = len(props)
            row["extras"] = json.dumps(extras, sort_keys=True) if extras else None
            res.assets.append(row)
            for j, p in enumerate(props):
                res.n_property_seen += 1
                prow: dict = {"asset_seq": seq, "asset_number": row.get("assetNumber"), "property_seq": j}
                pextras: dict = {}
                _typed_children(p, pfields, res, prow, pextras, set())
                prow["extras"] = json.dumps(pextras, sort_keys=True) if pextras else None
                res.properties.append(prow)
            elem.clear()
            parent = elem.getparent()
            if parent is not None:
                while elem.getprevious() is not None:
                    del parent[0]
    return res


def count_elements(path: Path | str) -> tuple[int, int]:
    """Independent count of <assets> and <property> start tags, for reconciliation."""
    opener = gzip.open if str(path).endswith(".gz") else open
    n_a = n_p = 0
    with opener(path, "rb") as fh:
        for _event, elem in etree.iterparse(fh, events=("start",), huge_tree=True):
            name = _local(elem.tag)
            if name == "assets":
                n_a += 1
            elif name == "property":
                n_p += 1
    return n_a, n_p
