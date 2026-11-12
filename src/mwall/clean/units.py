"""Per-value unit normalization for percentage fields (decision D014, D021).

The SEC never states a unit (docs/sec_code_tables.md section 2). Real filings
mix fractions (0.83) and whole percents (93.9), sometimes inside one record, so
the rule works value by value:

occupancy: v <= 1.0 is a fraction; 1.5 < v <= 100 is a whole percent (v/100);
           anything else is implausible and set to null with a flag.
rates:     v <= 0.25 is a fraction; 1.0 <= v <= 25 is a whole percent (v/100);
           anything else is implausible and set to null with a flag.

A value in the gap (1.0 < occupancy <= 1.5, 0.25 < rate < 1.0) cannot be
read either way, so it is nulled and flagged, never guessed.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def occupancy(s: pd.Series) -> tuple[pd.Series, pd.Series]:
    v = pd.to_numeric(s, errors="coerce")
    frac = v.where(v.between(0.0, 1.0))
    pct = (v / 100.0).where((v > 1.5) & (v <= 100.0))
    out = frac.fillna(pct)
    bad = v.notna() & out.isna()
    return out, bad


def rate(s: pd.Series) -> tuple[pd.Series, pd.Series]:
    v = pd.to_numeric(s, errors="coerce")
    frac = v.where(v.between(0.0, 0.25))
    pct = (v / 100.0).where(v.between(1.0, 25.0))
    out = frac.fillna(pct)
    bad = v.notna() & out.isna()
    return out, bad


def unit_used(s: pd.Series, kind: str) -> pd.Series:
    """'fraction', 'percent' or None, for the QA report."""
    v = pd.to_numeric(s, errors="coerce")
    lim = 1.0 if kind == "occupancy" else 0.25
    return pd.Series(np.where(v.isna(), None, np.where(v <= lim, "fraction", "percent")), index=s.index)
