"""Underwriting inputs (SOP 12): one row per scored whole loan, from its latest filing.

The rows are the loans in data/outputs/scores.parquet (Gate 3). Each takes the filing fields of the position's
largest record in that filing, the same choice the feature table makes (features/loan.py), plus:

- market inputs as of the valuation date: Treasury yields, CBRE's lending spread, the cap-rate benchmarks;
- the metro's Zillow multifamily rent change from the feature table;
- the property's place from data/parsed/places.parquet (underwrite/places.py) where it has been looked up.

Writes data/outputs/underwrite_inputs.parquet.
"""
from __future__ import annotations

import json

import duckdb
import numpy as np
import pandas as pd

from mwall.clean.geography import addr_key
from mwall.common import paths
from mwall.features import market
from mwall.features.build import CAP_RATES, LENDER_SPREADS

OUT = paths.OUTPUT_DIR / "underwrite_inputs.parquet"
PLACES = paths.PARSED_DIR / "places.parquet"
MARKET = paths.OUTPUT_DIR / "underwrite_market.json"

FIELDS = {
    "fin_noi_annual": "noi", "fin_revenue_annual": "revenue", "fin_opex_annual": "opex", "fin_ncf_annual": "ncf",
    "fin_noi_sec": "noi_sec", "fin_start": "fin_start", "fin_end": "fin_end", "fin_months": "fin_months",
    "fin_basis": "fin_basis", "flag_fin_basis_unknown": "flag_fin_basis_unknown",
    "flag_mixed_fin_periods": "flag_mixed_fin_periods", "noi_age_months": "noi_age_months",
    "val_securitization": "val_sec", "val_securitization_date": "val_sec_date", "val_recent": "val_recent",
    "val_recent_date": "val_recent_date", "sqft": "sqft", "units": "units",
    "occupancy_current": "occupancy", "n_properties": "n_properties", "year_built": "year_built",
    "tenant1_sqft": "tenant1_sqft", "tenant1_lease_exp": "tenant1_lease_exp",
    "tenant2_sqft": "tenant2_sqft", "tenant2_lease_exp": "tenant2_lease_exp",
    "tenant3_sqft": "tenant3_sqft", "tenant3_lease_exp": "tenant3_lease_exp",
    "prop_name": "prop_name", "prop_address": "prop_address", "prop_city": "prop_city",
    "prop_state": "prop_state_filed", "prop_zip": "prop_zip", "reportPeriodInterestRatePercentage": "coupon",
}
HIGH_TAX_COUNTIES = {"36005", "36047", "36061", "36081", "36085",  # New York City's five boroughs
                     "06075",  # San Francisco
                     "42101"}  # Philadelphia


def filing_fields(keys: pd.DataFrame) -> pd.DataFrame:
    lp = (paths.PARSED_DIR / "loan_period" / "*.parquet").as_posix()
    con = duckdb.connect()
    con.register("k", keys[["root_key", "accession"]].drop_duplicates())
    pick = ", ".join(f"arg_max(p.{src}, coalesce(p.balance, 0)) {dst}" for src, dst in FIELDS.items())
    return con.execute(f"""
        select p.root_key, p.accession, {pick}
        from read_parquet('{lp}', union_by_name=true) p join k using (root_key, accession)
        where p.loan_source in ('loan_record','note_record','replicated_child')
          and not coalesce(p.flag_filing_corrupt, false) and not coalesce(p.flag_transient_loan, false)
          and not coalesce(p.flag_foreign_record, false)
        group by 1, 2""").df()


FIN = {"fin_noi_annual": "noi", "fin_revenue_annual": "revenue", "fin_opex_annual": "opex",
       "fin_ncf_annual": "ncf", "fin_start": "fin_start", "fin_end": "fin_end", "fin_months": "fin_months",
       "fin_basis": "fin_basis", "flag_fin_basis_unknown": "flag_fin_basis_unknown"}


def earlier_noi(d: pd.DataFrame) -> pd.DataFrame:
    """Some servicers fill the financial fields only in some months. Where the latest filing has no NOI, take the
    financials of the loan's latest earlier filing that has one (the age test in the engine still applies)."""
    lp = (paths.PARSED_DIR / "loan_period" / "*.parquet").as_posix()
    miss = d.loc[d["noi"].isna() & d["property_group"].notna(), ["root_key", "period_end"]]
    con = duckdb.connect()
    con.register("m", miss)
    pick = ", ".join(f"arg_max(p.{src}, p.period_end) {dst}" for src, dst in FIN.items())
    return con.execute(f"""
        select m.root_key, {pick}, max(p.period_end) noi_filing_period
        from m join read_parquet('{lp}', union_by_name=true) p
          on p.root_key = m.root_key and p.period_end < m.period_end
        where p.fin_noi_annual is not null
          and p.loan_source in ('loan_record','note_record','replicated_child')
          and not coalesce(p.flag_filing_corrupt, false) and not coalesce(p.flag_transient_loan, false)
          and not coalesce(p.flag_foreign_record, false)
        group by 1""").df()


def quarter_fix(d: pd.DataFrame, log=print) -> pd.DataFrame:
    """D059: three-month financials that the servicer vote (D021) marked as already annualized are, for most loans,
    a quarter's figures (median 0.25 of the loan's earlier NOI). Each such loan takes whichever reading, as filed or
    times four, sits closer (in log terms) to its latest earlier NOI from a period of six months or more; without
    one, to its NOI at securitization; without either, the quarter reading (times four)."""
    q = d["fin_months"].eq(3) & d["fin_basis"].eq("annualized") & d["noi"].gt(0)
    d["noi_quarter_fix"] = False
    if not q.any():
        return d
    lp = (paths.PARSED_DIR / "loan_period" / "*.parquet").as_posix()
    con = duckdb.connect()
    con.register("k", d.loc[q, ["root_key", "period_end"]])
    prev = con.execute(f"""
        select k.root_key, arg_max(p.fin_noi_annual, p.period_end) prev_noi
        from k join read_parquet('{lp}', union_by_name=true) p on p.root_key = k.root_key
        where p.period_end < k.period_end - interval 100 day and p.fin_noi_annual > 0 and p.fin_months >= 6
        group by 1""").df().set_index("root_key")["prev_noi"]
    anchor = d.loc[q, "root_key"].map(prev)
    anchor = anchor.where(anchor.notna(), d.loc[q, "noi_sec"].where(d.loc[q, "noi_sec"] > 0))
    as_filed = np.abs(np.log(d.loc[q, "noi"] / anchor))
    times4 = np.abs(np.log(4 * d.loc[q, "noi"] / anchor))
    use4 = anchor.isna() | (times4 < as_filed)
    idx = use4[use4].index
    for c in ("noi", "revenue", "opex", "ncf"):
        d.loc[idx, c] = d.loc[idx, c] * 4
    d.loc[idx, "noi_quarter_fix"] = True
    log(f"quarter NOI read as annual (D059): {int(q.sum())} loans checked, {len(idx)} re-annualized")
    return d


def feature_fields(keys: pd.DataFrame) -> pd.DataFrame:
    f = (paths.PANEL_DIR / "features.parquet").as_posix()
    con = duckdb.connect()
    con.register("k", keys[["root_key", "accession"]].drop_duplicates())
    return con.execute(f"""
        select root_key, accession, any_value(f_mf_rent_growth_yoy) mf_rent_growth_metro,
               any_value(county_fips) county_fips
        from read_parquet('{f}') join k using (root_key, accession) group by 1, 2""").df()


def market_asof(D: pd.Timestamp) -> dict:
    """Yields, spreads and cap-rate benchmarks public on the valuation date D."""
    tr = market.treasury()
    t = tr[tr["available"] <= D].iloc[-1]
    sp = pd.read_csv(LENDER_SPREADS, parse_dates=["publication_date"])
    sp = sp[sp["publication_date"] <= D].sort_values(["publication_date", "as_of_quarter"])
    spreads = sp.groupby("series").tail(1).set_index("series")
    cr = pd.read_csv(CAP_RATES, parse_dates=["publication_date", "period_date"])
    return {
        "date": D, "treasury_date": t["date"], "ust5": t["DGS5"] / 100, "ust10": t["DGS10"] / 100,
        "spread_bps": spreads["spread_bps"].to_dict(), "spread_quarter": spreads["as_of_quarter"].to_dict(),
        "spread_publication": spreads["publication_date"].dt.date.astype(str).to_dict(), "cap_rates": cr,
    }


def benchmark_at(cr: pd.DataFrame, group: pd.Series, when: pd.Series, by: str) -> pd.Series:
    """Cap-rate benchmark for each row's property group: the latest survey whose ``by`` date (period_date for a
    past market level, publication_date for what was public) is on or before ``when``."""
    out = pd.Series(np.nan, index=group.index)
    w = pd.to_datetime(when)
    for g, s in cr.sort_values(by).groupby("property_group"):
        rows = group.eq(g) & w.notna()
        if not rows.any():
            continue
        idx = np.searchsorted(s[by].to_numpy(), w[rows].to_numpy(), side="right") - 1
        vals = s["cap_rate"].to_numpy()
        out[rows] = np.where(idx >= 0, vals[np.clip(idx, 0, None)], np.nan)
    return out


def build(D: pd.Timestamp | None = None, log=print) -> pd.DataFrame:
    from mwall.model.score import deployment_date

    D = deployment_date() if D is None else D
    s = pd.read_parquet(paths.OUTPUT_DIR / "scores.parquet")
    keep = ["whole_loan_id", "root_key", "trust_cik", "accession", "deal_family", "vintage", "property_group",
            "prop_state", "cbsa_code", "wl_balance_est", "piece_balance", "maturity_eff", "period_end", "status",
            "p_fail", "p_fail_lo", "p_fail_hi", "p_distress_12m", "f_refi_gap", "refi_gap_usd", "snapshot_date"]
    d = s[keep].merge(filing_fields(s), on=["root_key", "accession"], how="left")
    d["noi_source"] = np.where(d["noi"].notna(), "latest filing", None)
    e = earlier_noi(d).set_index("root_key")
    fill = d["noi"].isna() & d["root_key"].isin(e.index)
    for c in FIN.values():
        d.loc[fill, c] = e.loc[d.loc[fill, "root_key"], c].to_numpy()
    d.loc[fill, "noi_source"] = "filing of " + e.loc[d.loc[fill, "root_key"], "noi_filing_period"].dt.strftime(
        "%Y-%m").to_numpy()
    d.loc[fill, "noi_age_months"] = ((d.loc[fill, "snapshot_date"] - pd.to_datetime(d.loc[fill, "fin_end"]))
                                     .dt.days / 30.4375).to_numpy()
    log(f"NOI from an earlier filing: {int(fill.sum()):,} loans")
    d = quarter_fix(d, log)
    d = d.merge(feature_fields(s), on=["root_key", "accession"], how="left")
    geo = pd.read_parquet(paths.PARSED_DIR / "geography.parquet", columns=["addr_key", "lat", "lon"])
    d["addr_key"] = [addr_key(*r) for r in d[["prop_address", "prop_city", "prop_state_filed", "prop_zip"]]
                     .itertuples(index=False)]
    d = d.merge(geo.drop_duplicates("addr_key"), on="addr_key", how="left")
    if PLACES.exists():
        pl = pd.read_parquet(PLACES)[["addr_key", "place_name", "place_geoid", "place_source"]]
        d = d.merge(pl.drop_duplicates("addr_key"), on="addr_key", how="left")
    else:
        d["place_name"] = d["place_geoid"] = d["place_source"] = None
        log("data/parsed/places.parquet not present: Los Angeles overrides not applied")
    d["property_group"] = d["property_group"].astype(object)
    mk = market_asof(D)
    cr = mk["cap_rates"]
    d["cap_bench_today"] = benchmark_at(cr, d["property_group"], pd.Series(D, index=d.index), "publication_date")
    d["cap_bench_sec"] = benchmark_at(cr, d["property_group"], d["val_sec_date"], "period_date")
    # composite benchmark (mean of the four types with a current series) for types with no series of their own
    comp = ["office", "retail", "industrial", "multifamily"]
    today_c = [benchmark_at(cr, pd.Series(g, index=d.index), pd.Series(D, index=d.index), "publication_date")
               for g in comp]
    sec_c = [benchmark_at(cr, pd.Series(g, index=d.index), d["val_sec_date"], "period_date") for g in comp]
    d["cap_composite_today"] = pd.concat(today_c, axis=1).mean(axis=1, skipna=False)
    d["cap_composite_sec"] = pd.concat(sec_c, axis=1).mean(axis=1, skipna=False)
    d["high_tax_metro"] = d["county_fips"].isin(HIGH_TAX_COUNTIES)
    d["valuation_date"] = D
    d.to_parquet(OUT, index=False)
    meta = {k: (str(v.date()) if isinstance(v, pd.Timestamp) else v) for k, v in mk.items() if k != "cap_rates"}
    MARKET.write_text(json.dumps(meta, indent=1))
    log(f"underwriting inputs: {len(d):,} loans; with NOI {int(d['noi'].notna().sum()):,}; "
        f"valuation date {D.date()}; 10-yr {mk['ust10']:.4f} 5-yr {mk['ust5']:.4f} ({mk['treasury_date'].date()})")
    return d
