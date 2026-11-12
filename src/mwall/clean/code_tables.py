"""Official code tables, read from the SEC XSD (SOP section 8, step 5; Appendix A).

Each coded simpleType in eis_ABS_CMBSAssetData.xsd lists its legal values as
xs:enumeration and their meanings in xs:documentation ("98: Other, A: ...").
Reading them from the schema means no code meaning is typed by hand. Verified
against the PDF specification in docs/sec_code_tables.md.

Two documented filer quirks are mapped explicitly:
* "98.0" was the spelling of Other in schema versions dated Nov 4 to Dec 12, 2016.
"""
from __future__ import annotations

import re
from functools import lru_cache

from lxml import etree

from mwall.common import paths
from mwall.parse import schema

XS = "{http://www.w3.org/2001/XMLSchema}"
ALIASES = {"98.0": "98"}

# Analysis groupings layered on the official codes (SOP Appendix A, section 8 step 5).
PROPERTY_GROUP = {
    "OF": "office", "RT": "retail", "LO": "lodging", "IN": "industrial", "WH": "industrial",
    "MF": "multifamily", "CH": "multifamily", "MH": "multifamily", "HC": "other", "SS": "self_storage",
    "MU": "mixed_use", "SE": "defeased", "ZZ": "other", "98": "other",
}
DELINQUENCY_BUCKET = {
    "0": "current", "A": "current", "B": "late_lt30", "1": "dq30", "2": "dq60", "3": "dq90plus",
    "4": "matured_performing", "5": "matured_nonperforming",
}


@lru_cache(maxsize=1)
def tables() -> dict[str, dict[str, str]]:
    """{element name: {code: meaning}} for every coded element."""
    tree = etree.parse(str(paths.CONFIG_DIR / "sec_schema" / "eis_ABS_CMBSAssetData.xsd"))
    by_type: dict[str, dict[str, str]] = {}
    for st in tree.iter(f"{XS}simpleType"):
        values = [e.get("value") for e in st.iter(f"{XS}enumeration")]
        if not values:
            continue
        doc = " ".join((d.text or "") for d in st.iter(f"{XS}documentation"))
        doc = doc.split("descriptions:", 1)[-1] if "descriptions:" in doc else doc
        # locate each "CODE: " anchor in order; meaning runs to the next anchor
        anchors = []
        for v in values:
            m = re.search(rf"(?:^|,\s*|\s)({re.escape(v)}):\s", doc)
            if m:
                anchors.append((m.start(1), m.end(), v))
        anchors.sort()
        meanings = {}
        for i, (_s, e, v) in enumerate(anchors):
            end = anchors[i + 1][0] if i + 1 < len(anchors) else len(doc)
            meanings[v] = doc[e:end].strip().rstrip(",").strip()
        by_type[st.get("name")] = {v: meanings.get(v, "") for v in values}
    out = {}
    for parent in ("assets", "property"):
        for name, f in schema.fields()[parent].items():
            if f.kind == "code" and f.xsd_type in by_type:
                out[name] = by_type[f.xsd_type]
    return out


def _norm(code) -> str | None:
    if code is None or (isinstance(code, float) and code != code):
        return None
    s = str(code).strip()
    return ALIASES.get(s, s) if s else None


def decode(field: str, code) -> str | None:
    c = _norm(code)
    if c is None:
        return None
    return tables().get(field, {}).get(c)


def is_valid(field: str, code) -> bool:
    c = _norm(code)
    if c is None:
        return True
    return c in tables().get(field, {})
