"""The modeling frame and the out-of-time design (SOP 10 and 11; decision D051).

One row per whole loan per month: the representative piece (D027), performing at the snapshot, with its
features and the tier 2 label. Defeased loans are left out (their collateral is Treasuries, not property),
as are late snapshots (D044) and months whose 12-month window runs past the data (D045).

Out-of-time windows. A model deployed on date D may only be fit on months whose label was known by D: the
12-month window plus 45 days for the last filing. The latest 12 such months are the validation window
(tuning and calibration); everything before is training; the test window is the 12 months from D:

    train:      period_end <= D - 775 days
    validation: D - 775 days < period_end <= D - 410 days
    test:       D <= period_end < D + one year

Loan groups. Whole loans are split into five folds by a hash of their id. Each fold's test months are
scored by models fit and calibrated without that fold, so no loan is in both the fit and the test.
"""
from __future__ import annotations

import zlib

import duckdb
import numpy as np
import pandas as pd

from mwall.common import paths
from mwall.features.catalog import CATALOG

FEATURES_FILE = paths.PANEL_DIR / "features.parquet"
LABELS_FILE = paths.PANEL_DIR / "loan_month.parquet"
OUT_DIR = paths.OUTPUT_DIR / "model"

ORIGINS = [pd.Timestamp(y, 1, 1) for y in (2022, 2023, 2024, 2025)]
TRAIN_LAG = pd.Timedelta(days=775)
VALID_LAG = pd.Timedelta(days=410)
N_FOLDS = 5

# performing loans are never in special servicing, so that flag is constant here
NUMERIC = [f.name for f in CATALOG if f.name.startswith("f_") and f.kind in ("num", "bool")
           and f.name != "f_in_special_servicing"]
CATEGORICAL = {
    "property_group": ["office", "retail", "lodging", "industrial", "multifamily", "self_storage", "mixed_use",
                       "other"],
    "delinquency_bucket": ["current", "late_lt30"],
}

# SOP 11 stage 2: monotone in debt yield, DSCR, LTV and occupancy (-1: more is safer)
MONOTONE = {
    "f_debt_yield_noi": -1, "f_debt_yield_ncf": -1, "f_dscr_noi_reported": -1, "f_dscr_noi_recomputed": -1,
    "f_refi_dscr": -1, "f_occupancy": -1, "f_ltv_securitization": 1, "f_ltv_recent": 1, "f_ltv_model": 1,
}
# signs credit logic expects for the stage 1 check
EXPECTED_SIGN = {**MONOTONE, "f_refi_gap": 1, "f_refi_gap_income": 1, "f_refi_dy_cushion": -1,
                 "f_noi_vs_securitization": -1, "f_ever_modified": 1, "f_ever_special_serviced": 1}
# sign constraints for the logistic models (D054): credit logic, plus the rate channel
CREDIT_SIGNS = {**EXPECTED_SIGN, "f_rate_shock": 1, "f_refi_rate": 1}

# ablation sets (SOP 11 robustness suite)
_MARKET_INPUTS = ("f_ust", "f_curve", "f_cap_rate", "f_rent", "f_mf_rent", "f_emp", "f_office_emp", "f_permits",
                  "f_refi_", "f_rate_shock", "f_value_model", "f_ltv_model")
ABLATIONS = {
    "no_market": [c for c in NUMERIC if c.startswith(_MARKET_INPUTS)],
    "no_noi": ["f_debt_yield_noi", "f_debt_yield_ncf", "f_dscr_noi_reported", "f_dscr_noi_recomputed",
               "f_dscr_disagree", "f_noi_vs_securitization", "f_noi_yoy", "f_expense_ratio", "f_noi_age_months",
               "f_noi_missing", "f_value_model", "f_ltv_model", "f_refi_dscr", "f_refi_dy_cushion",
               "f_refi_gap_income", "f_refi_gap"],
    "no_servicing": ["delinquency_bucket", "f_ever_modified", "f_ever_special_serviced", "f_advances_pi",
                     "f_advances_ti", "f_advances_other", "f_advances_pct"],
}


def fold_of(keys: pd.Series, n: int = N_FOLDS) -> np.ndarray:
    return np.array([zlib.crc32(str(k).encode()) % n for k in keys], dtype=np.int8)


def load(where: str = "true", extra: tuple[str, ...] = (), performing_only: bool = True) -> pd.DataFrame:
    """Performing (unless performing_only is False), representative, non-defeased loan-months with features,
    label and cut variables."""
    num = ", ".join(f"cast(f.{c} as float) {c}" for c in NUMERIC)
    trusts = (paths.META_DIR / "trusts.parquet").as_posix()
    extra_sql = "".join(f", {e}" for e in extra)
    q = f"""
        select f.trust_cik, f.root_key, coalesce(f.whole_loan_id, f.root_key) whole_loan_id, f.period_end,
               f.snapshot_date, f.flag_late_snapshot, f.property_group, f.delinquency_bucket, f.cbsa_code,
               f.prop_state, l.y_distress_12m, l.label_window_complete, l.wl_balance_est, l.maturity_eff,
               t.deal_family, cast(t.vintage as int) vintage, {num}{extra_sql}
        from '{FEATURES_FILE.as_posix()}' f
        join '{LABELS_FILE.as_posix()}' l using (trust_cik, root_key, accession)
        left join '{trusts}' t on t.trust_cik = f.trust_cik
        where {"f.performing and " if performing_only else ""}f.is_representative
          and not coalesce(l.defeased, false) and {where}"""
    d = duckdb.connect().execute(q).df()
    d["fold"] = fold_of(d["whole_loan_id"])
    d["labeled"] = d["y_distress_12m"].notna() & d["label_window_complete"].fillna(False) & ~d["flag_late_snapshot"]
    # a whole loan keeps the deal family of its first representative trust, for the out-of-trust test
    first = d.sort_values("period_end").drop_duplicates("whole_loan_id").set_index("whole_loan_id")["deal_family"]
    d["family"] = d["whole_loan_id"].map(first).fillna("unknown")
    d["family_fold"] = fold_of(d["family"])
    for c, levels in CATEGORICAL.items():
        d[c] = pd.Categorical(d[c], categories=levels)
    return d


def windows(D: pd.Timestamp, pe: pd.Series) -> dict[str, pd.Series]:
    return {"train": pe <= D - TRAIN_LAG,
            "valid": (pe > D - TRAIN_LAG) & (pe <= D - VALID_LAG),
            "test": (pe >= D) & (pe < D + pd.DateOffset(years=1))}


def feature_list(drop: list[str] | None = None) -> tuple[list[str], list[str]]:
    drop = set(drop or [])
    return [c for c in NUMERIC if c not in drop], [c for c in CATEGORICAL if c not in drop]
