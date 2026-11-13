"""Feature table (SOP section 9): panel/features.parquet, one row per loan position and filing.

Snapshot date T is the filing date: the day the row's data became public. Loan features come
from that filing and the loan's earlier filings (features/loan.py); market series join as of T
through their own publication lags (features/market.py); refinance features need the cited lender
parameters in config/lender_params.csv and the cap-rate benchmark in config/cap_rates.csv, and are
left out, with a note in the report, until those files exist.

Writes panel/features.parquet. The dictionary and QA report are in features/report.py.
"""
from __future__ import annotations

import datetime as dt

import duckdb
import numpy as np
import pandas as pd

from mwall.common import paths
from mwall.features import loan, market
from mwall.features.catalog import BY_NAME, CATALOG

LATE_SNAPSHOT_DAYS = 60
PANEL_COLS = ["trust_cik", "root_key", "accession", "period_end", "filing_date", "balance", "n_blank_balance",
              "payment_status",
              "maturity_date", "maturity0", "origination_date", "property_group", "prop_type_code", "ss_transfer_date",
              "in_special_servicing", "ev_modification", "whole_loan_id", "is_representative", "performing",
              "y_distress_12m"]
LENDER_PARAMS = paths.CONFIG_DIR / "lender_params.csv"
LENDER_SPREADS = paths.CONFIG_DIR / "lender_spreads.csv"
CAP_RATES = paths.CONFIG_DIR / "cap_rates.csv"
TENOR = {5: "DGS5", 7: "DGS7", 10: "DGS10"}
# a market value older than this (counted from its publication date) is too stale to use
MAX_AGE = {"treasury": 10, "zori": 120, "qcew": 365, "bps": 180}


N_CHUNKS = 6  # loans are processed in groups to keep memory low; every feature is per loan or per row


def _chunk_sql(k: int, n: int) -> str:
    return f"hash(root_key) % {n} = {k}"


def load(chunk: tuple[int, int] = (0, 1), log=print) -> pd.DataFrame:
    where = _chunk_sql(*chunk)
    lm = (paths.PANEL_DIR / "loan_month.parquet").as_posix()
    p = duckdb.connect().execute(f"select {', '.join(PANEL_COLS)} from read_parquet('{lm}') where {where}").df()
    fields = loan.load_fields(where)
    d = p.merge(fields, on=["root_key", "accession"], how="left", validate="one_to_one")
    log(f"chunk {chunk[0] + 1}/{chunk[1]}: panel rows {len(p):,}; with filing fields {int(d['coupon'].notna().sum()):,}")
    d["snapshot_date"] = d["filing_date"]
    # D044: a note filed with a blank balance makes the position's summed balance partial, so balance-based
    # features stay null for that month instead of using an understated figure
    blank = d["n_blank_balance"].fillna(0) > 0
    d.loc[blank, ["balance", "wl_balance"]] = np.nan
    d = d.sort_values(["root_key", "period_end", "filing_date"]).reset_index(drop=True)
    nxt = d.groupby("root_key")["period_end"].shift(-1)
    # an amendment filed long after its period, or after the next period ended, carries data that was not
    # public when the loan was in that month; such rows stay in the table but are kept out of training
    d["flag_late_snapshot"] = ((d["snapshot_date"] - d["period_end"]).dt.days > LATE_SNAPSHOT_DAYS) | (
        nxt.notna() & (d["snapshot_date"] >= nxt))
    return d


def attach_geography(d: pd.DataFrame, geo: pd.DataFrame) -> pd.DataFrame:
    from mwall.clean.geography import addr_key

    a = d[["prop_address", "prop_city", "prop_state", "prop_zip"]].drop_duplicates()
    a["addr_key"] = [addr_key(*r) for r in a.itertuples(index=False)]
    a = a.merge(geo.drop_duplicates("addr_key"), on="addr_key", how="left")
    return d.merge(a, on=["prop_address", "prop_city", "prop_state", "prop_zip"], how="left")


def market_tables() -> dict:
    from mwall.clean.geography import cbsa as cbsa_table

    return {"treasury": market.treasury(), "zori": market.zori(cbsa_table()), "qcew": market.qcew(),
            "permits": market.permits(market.county_cbsa()),
            "geo": pd.read_parquet(paths.PARSED_DIR / "geography.parquet",
                                   columns=["addr_key", "county_fips", "cbsa_code"]).drop_duplicates("addr_key")}


def attach_market(d: pd.DataFrame, f: pd.DataFrame, mk: dict) -> tuple[pd.DataFrame, pd.DataFrame]:
    tr = mk["treasury"]
    cols = list(market.TREASURY)
    d = market.asof(d, tr, cols, prefix="tsy_", max_age_days=MAX_AGE["treasury"])
    d["snap_minus_1y"] = d["snapshot_date"] - pd.DateOffset(years=1)
    d = market.asof(d, tr, ["DGS10"], on="snap_minus_1y", prefix="tsy1y_")
    d = market.asof(d, tr, ["DGS10"], on="origination_date", prefix="tsyorig_")
    f["f_ust10"] = d["tsy_DGS10"] / 100
    f["f_ust5"] = d["tsy_DGS5"] / 100
    f["f_ust10_change_12m"] = f["f_ust10"] - d["tsy1y_DGS10"] / 100
    f["f_curve_10y2y"] = (d["tsy_DGS10"] - d["tsy_DGS2"]) / 100
    f["f_ust10_change_since_origination"] = f["f_ust10"] - d["tsyorig_DGS10"] / 100
    f["asof_treasury"] = d["tsy_asof"]

    z = mk["zori"]
    d = market.asof(d, z, ["zori_all_yoy"], by="cbsa_code", prefix="z_", max_age_days=MAX_AGE["zori"])
    d = market.asof(d, z, ["zori_mf_yoy"], by="cbsa_code", prefix="zmf_", max_age_days=MAX_AGE["zori"])
    f["f_rent_growth_yoy"] = d["z_zori_all_yoy"]
    f["f_mf_rent_growth_yoy"] = d["zmf_zori_mf_yoy"]
    f["asof_zori"] = d["z_asof"]
    f["asof_zori_mf"] = d["zmf_asof"]

    q = mk["qcew"]
    d["qcew_area"] = market.qcew_area(d["cbsa_code"])
    d = market.asof(d, q, ["emp_total_yoy"], by="qcew_area", prefix="q_", max_age_days=MAX_AGE["qcew"])
    d = market.asof(d, q, ["emp_office_yoy"], by="qcew_area", prefix="qo_", max_age_days=MAX_AGE["qcew"])
    f["f_emp_growth_yoy"] = d["q_emp_total_yoy"]
    f["f_office_emp_growth_yoy"] = d["qo_emp_office_yoy"]
    f["asof_qcew"] = d["q_asof"]
    f["asof_qcew_office"] = d["qo_asof"]

    pm = mk["permits"]
    d = market.asof(d, pm, ["permits_per_1k_units", "permits_5plus_per_1k_units"], by="cbsa_code", prefix="bp_",
                    max_age_days=MAX_AGE["bps"])
    f["f_permits_per_1k_units"] = d["bp_permits_per_1k_units"]
    f["f_permits_5plus_per_1k_units"] = d["bp_permits_5plus_per_1k_units"]
    f["asof_permits"] = d["bp_asof"]
    return d, f


def attach_refi(d: pd.DataFrame, f: pd.DataFrame, log=print) -> pd.DataFrame:
    """SOP 12 step A on unstressed NOI, base scenario. Needs config/lender_params.csv; the cap-rate
    benchmark adds the value constraint when config/cap_rates.csv exists."""
    if CAP_RATES.exists():
        cr = pd.read_csv(CAP_RATES, parse_dates=["publication_date"])
        cr = cr.rename(columns={"publication_date": "available"})
        d2 = market.asof(d, cr, ["cap_rate"], by="property_group", prefix="cr_")
        f["f_cap_rate_benchmark"] = d2["cr_cap_rate"]
        f["asof_cap_rate"] = d2["cr_asof"]
        f["f_value_model"] = (d["noi"] / f["f_cap_rate_benchmark"]).where(d["noi"] > 0)
        f["f_ltv_model"] = (d["wl_balance"] / f["f_value_model"]).where(f["f_value_model"] > 0)
    else:
        log("config/cap_rates.csv not present: cap-rate features skipped")
    if not LENDER_PARAMS.exists():
        log("config/lender_params.csv not present: refinance features skipped")
        return f
    lp = pd.read_csv(LENDER_PARAMS)
    lp = lp[lp["scenario"].eq("base")].set_index("property_group")
    pg = d["property_group"].where(d["property_group"].isin(lp.index), "other")
    par = lp.reindex(pg.values).set_index(d.index)
    ust = pd.Series(np.nan, index=d.index)
    for tenor, col in TENOR.items():
        ust = ust.where(par["treasury_tenor"].ne(tenor), d[f"tsy_{col}"] / 100)
    # the spread is CBRE's quarterly series as of its publication date, plus a fixed property-type premium
    sp = pd.read_csv(LENDER_SPREADS, parse_dates=["publication_date"]).sort_values(
        ["series", "publication_date", "as_of_quarter"])
    sp = sp.drop_duplicates(["series", "publication_date"], keep="last").rename(
        columns={"publication_date": "available", "series": "spread_series"})
    d2 = market.asof(d.assign(spread_series=par["spread_series"].values), sp, ["spread_bps"], by="spread_series",
                     prefix="sp_")
    f["asof_spread"] = d2["sp_asof"]
    rate = ust + (d2["sp_spread_bps"] + par["spread_premium_bps"]) / 10_000
    k = loan.loan_constant(rate, par["amort_years"])
    B = d["wl_balance"].where(d["wl_balance"] > 0)
    noi = d["noi"]
    f["f_refi_rate"] = rate
    f["f_rate_shock"] = rate - f["f_coupon"]
    f["f_refi_dscr"] = noi / (B * k)
    f["f_refi_dy_cushion"] = f["f_debt_yield_noi"] - par["dy_min"]
    p_income = np.minimum(noi / (par["dscr_min"] * k), noi / par["dy_min"]).clip(lower=0)
    f["f_refi_gap_income"] = ((B - p_income).clip(lower=0) / B).where(noi.notna())
    if "f_value_model" in f:
        p_val = (par["ltv_max"] * f["f_value_model"]).where(f["f_value_model"].notna())
        p_max = np.minimum(p_income, p_val)
        f["f_refi_gap"] = ((B - p_max).clip(lower=0) / B).where(noi.notna() & p_val.notna())
    return f


def build(log=print, n_chunks: int = N_CHUNKS) -> None:
    import gc

    t0 = dt.datetime.now()
    mk = market_tables()
    part_dir = paths.PANEL_DIR / "features_parts"
    part_dir.mkdir(parents=True, exist_ok=True)
    for old in part_dir.glob("*.parquet"):
        old.unlink()
    for k in range(n_chunks):
        d = load((k, n_chunks), log)
        d = attach_geography(d, mk["geo"])
        f = loan.compute(d)
        d, f = attach_market(d, f, mk)
        f = attach_refi(d, f, log if k == 0 else (lambda m: None))
        keys = d[["trust_cik", "root_key", "accession", "whole_loan_id", "period_end", "snapshot_date",
                  "is_representative", "performing", "flag_late_snapshot", "property_group", "prop_type_code", "prop_state",
                  "cbsa_code", "county_fips", "delinquency_bucket"]]
        pd.concat([keys, f], axis=1).to_parquet(part_dir / f"part{k}.parquet", index=False)
        del d, f, keys
        gc.collect()
    con = duckdb.connect()
    con.execute(f"copy (select * from read_parquet('{part_dir.as_posix()}/*.parquet', union_by_name=true)) "
                f"to '{(paths.PANEL_DIR / 'features.parquet').as_posix()}' (format parquet)")
    n = con.execute(f"select count(*) from read_parquet('{(paths.PANEL_DIR / 'features.parquet').as_posix()}')").fetchone()[0]
    for old in part_dir.glob("*.parquet"):
        old.unlink()
    part_dir.rmdir()
    log(f"features: {n:,} rows in {(dt.datetime.now() - t0).seconds}s")

