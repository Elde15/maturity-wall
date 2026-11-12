"""Explicit field schema for CMBS EX-102, built from the SEC's own XSD.

The XSD (EDGAR ABS XML Technical Specification v3.1, eis_ABS_CMBSAssetData.xsd,
copied to config/sec_schema/) is the source of truth for element names and
types. The tag census (parse/census.py) checks it against real filings; any
tag in a filing that is not listed here goes to the ``extras`` JSON column.
"""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

from lxml import etree

from mwall.common import paths

NS = "http://www.sec.gov/edgar/document/absee/cmbs/assetdata"
XS = "{http://www.w3.org/2001/XMLSchema}"
SCHEMA_VERSION = "parsed-v1"

# Elements that may repeat inside one <assets> record (XSD maxOccurs="unbounded").
REPEATABLE = {"workoutStrategyCode", "modificationCode", "repurchaseReplacementReasonCode"}


@dataclass(frozen=True)
class Field:
    name: str
    parent: str        # "assets" or "property"
    kind: str          # decimal | date | integer | boolean | code | string
    xsd_type: str
    item: str          # Schedule AL item from the XSD comment, e.g. "Item 2(e)(17)"


def _kind(xsd_type: str) -> str:
    t = xsd_type.split(":")[-1]
    if t.startswith("DECIMAL"):
        return "decimal"
    if t == "DATE_TYPE":
        return "date"
    if t.startswith("INTEGER"):
        return "integer"
    if t == "TRUE_FALSE_TYPE":
        return "boolean"
    if t.endswith("_CODE_TYPE"):
        return "code"
    return "string"


@lru_cache(maxsize=1)
def fields() -> dict[str, dict[str, Field]]:
    tree = etree.parse(str(paths.CONFIG_DIR / "sec_schema" / "eis_ABS_CMBSAssetData.xsd"))
    out: dict[str, dict[str, Field]] = {"assets": {}, "property": {}}
    for ctype, parent in (("ASSET_TYPE", "assets"), ("PROPERTY_TYPE", "property")):
        node = tree.find(f"{XS}complexType[@name='{ctype}']")
        seq = node.find(f"{XS}sequence")
        item = ""
        for child in seq:
            if isinstance(child, etree._Comment):
                txt = str(child.text or "").strip()
                item = txt.split(" - ")[0].strip() if txt.startswith("Item") else item
                continue
            if child.tag != f"{XS}element":
                continue
            name, xtype = child.get("name"), child.get("type", "")
            if name == "property":
                continue
            out[parent][name] = Field(name, parent, _kind(xtype), xtype, item)
    return out


def asset_fields() -> dict[str, Field]:
    return fields()["assets"]


def property_fields() -> dict[str, Field]:
    return fields()["property"]
