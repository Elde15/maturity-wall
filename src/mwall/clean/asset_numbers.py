"""Asset-number grammar (SOP section 8, step 1).

Filers number records in at least these ways (all seen in real EX-102s):

    "15"          loan                         root 15
    "15.00"       loan (dot style)             root 15
    "06"          loan with leading zero       root 6
    "15-001"      property 1 of loan 15        root 15, child 1
    "3.01"        property 1 of loan 3         root 3, child 1
    "4A", "4B"    split notes of loan 4        root 4, note "A" / "B"
    "6A-1"        note A-1 of loan 6           root 6, note "A-1"
    "1-A-1"       note A-1 of loan 1           root 1, note "A-1"
    "15 A-2-C5"   note A-2-C5 of loan 15       root 15, note "A-2-C5"
    "06A2C"       note A2C of loan 6           root 6, note "A2C"
    "A-1-C3"      note with no loan number     root None, note "A-1-C3" (grouped later)

A note is a separate loan record (its own balance) that shares collateral with
the other notes of the same root. A child is a property record. The string is
only half the answer: whether a root has a parent record, and whether its
children repeat loan fields, is decided from the filing's structure in
``clean/structure.py``.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

_LOAN = re.compile(r"^0*(\d+)(?:\.0+)?$")
_CHILD = re.compile(r"^0*(\d+)\s*[-.]\s*0*(\d+)$")
_NOTE = re.compile(r"^0*(\d+)\s*-?\s*([A-Za-z][A-Za-z0-9-]*)$")
_ROOTLESS_NOTE = re.compile(r"^[A-Za-z]\d*(?:-[A-Za-z0-9]+)+$|^[A-Za-z]-?\d+[A-Za-z0-9]*$")


@dataclass(frozen=True)
class AssetNumber:
    raw: str
    root: int | None
    note: str          # "" when not a note
    child: int | None  # None when not a property child
    ok: bool

    @property
    def is_child(self) -> bool:
        return self.child is not None

    @property
    def loan_id(self) -> str | None:
        """Identifier of the loan record this number denotes (None for property children)."""
        if self.child is not None:
            return None
        if self.root is None:
            return f"N-{self.note}" if self.note else None
        return f"{self.root}{self.note}" if not self.note else f"{self.root}-{self.note}"


def parse(raw: str | None) -> AssetNumber:
    s = (raw or "").strip()
    m = _LOAN.match(s)
    if m:
        return AssetNumber(s, int(m.group(1)), "", None, True)
    m = _CHILD.match(s)
    if m:
        child = int(m.group(2))
        if child == 0:  # "2-000" would be odd; treat as the loan itself
            return AssetNumber(s, int(m.group(1)), "", None, True)
        return AssetNumber(s, int(m.group(1)), "", child, True)
    m = _NOTE.match(s)
    if m:
        note = re.sub(r"\s+", "", m.group(2)).upper()
        return AssetNumber(s, int(m.group(1)), note, None, True)
    if _ROOTLESS_NOTE.match(s) and s.lower() != "prospectus loan id":
        return AssetNumber(s, None, s.upper().replace(" ", ""), None, True)
    return AssetNumber(s, None, "", None, False)
