"""Resolve each filing's records into loans and properties (SOP section 8, steps 1, 3, 4).

Input: parsed asset and property rows for one trust (winning filing per period).
Output: one row per loan-period and one row per property-period.

Layouts seen in real filings, decided per (filing, root loan number):

  single           one loan record with one <property> block
  nested           one loan record with several <property> blocks
  parent_children  loan record "15" (with a portfolio roll-up block) plus
                   property records "15-001", "15-002" (allocated amounts)
  replicated       no loan record: every property record "4-001".. repeats the
                   full loan fields (balance, rate, status)
  notes            split notes "4A", "4B" (each its own loan) sharing collateral,
                   with or without a plain "4" and with or without children
  orphan           property records with no loan record and no loan fields

Property block roles: ``property`` (a real property, counted once),
``rollup`` (the parent's portfolio summary block), ``note_block`` (a duplicate
of collateral already counted under a sibling note).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from mwall.clean import asset_numbers, units

LOAN_SIGNAL = ["maturityDate", "reportPeriodEndActualBalanceAmount", "paymentStatusLoanCode", "originationDate"]
CONSISTENCY_KEYS = ["reportPeriodEndActualBalanceAmount", "maturityDate", "paymentStatusLoanCode",
                    "reportPeriodInterestRatePercentage"]
RATE_FIELDS = ["originalInterestRatePercentage", "interestRateSecuritizationPercentage",
               "reportPeriodInterestRatePercentage", "nextInterestRatePercentage", "servicerTrusteeFeeRatePercentage"]

FIN_SUM = {
    "mostRecentRevenueAmount": "fin_revenue",
    "operatingExpensesAmount": "fin_opex",
    "mostRecentNetOperatingIncomeAmount": "fin_noi",
    "mostRecentNetCashFlowAmount": "fin_ncf",
    "mostRecentDebtServiceAmount": "fin_debt_service",
    "revenueSecuritizationAmount": "fin_revenue_sec",
    "operatingExpensesSecuritizationAmount": "fin_opex_sec",
    "netOperatingIncomeSecuritizationAmount": "fin_noi_sec",
    "netCashFlowFlowSecuritizationAmount": "fin_ncf_sec",
}
VALUE_SUM = {
    "valuationSecuritizationAmount": "val_securitization",
    "mostRecentValuationAmount": "val_recent",
    "netRentableSquareFeetNumber": "sqft",
    "netRentableSquareFeetSecuritizationNumber": "sqft_sec",
    "unitsBedsRoomsNumber": "units",
    "unitsBedsRoomsSecuritizationNumber": "units_sec",
}
ROLLUP_ONLY = {
    "mostRecentDebtServiceCoverageNetOperatingIncomePercentage": "dscr_noi_reported",
    "mostRecentDebtServiceCoverageNetCashFlowpercentage": "dscr_ncf_reported",
    "debtServiceCoverageNetOperatingIncomeSecuritizationPercentage": "dscr_noi_sec_reported",
    "debtServiceCoverageNetCashFlowSecuritizationPercentage": "dscr_ncf_sec_reported",
    "mostRecentFinancialsStartDate": "fin_start",
    "mostRecentFinancialsEndDate": "fin_end",
    "financialsSecuritizationDate": "fin_sec_date",
    "valuationSecuritizationDate": "val_securitization_date",
    "mostRecentValuationDate": "val_recent_date",
    "netOperatingIncomeNetCashFlowCode": "noi_ncf_basis",
    "mostRecentDebtServiceCoverageCode": "dscr_code",
}
LARGEST_ATTRS = {
    "propertyName": "prop_name", "propertyAddress": "prop_address", "propertyCity": "prop_city",
    "propertyState": "prop_state", "propertyZip": "prop_zip", "propertyCounty": "prop_county",
    "propertyTypeCode": "prop_type_code", "yearBuiltNumber": "year_built", "yearLastRenovated": "year_renovated",
    "largestTenant": "tenant1_name", "squareFeetLargestTenantNumber": "tenant1_sqft",
    "leaseExpirationLargestTenantDate": "tenant1_lease_exp",
    "secondLargestTenant": "tenant2_name", "squareFeetSecondLargestTenantNumber": "tenant2_sqft",
    "leaseExpirationSecondLargestTenantDate": "tenant2_lease_exp",
    "thirdLargestTenant": "tenant3_name", "squareFeetThirdLargestTenantNumber": "tenant3_sqft",
    "leaseExpirationThirdLargestTenantDate": "tenant3_lease_exp",
    "netRentableSquareFeetNumber": "largest_sqft",
}


def _fix_swapped_numbers(a: pd.DataFrame) -> pd.DataFrame:
    """One filer swapped assetNumber and assetTypeNumber in a whole filing."""
    swapped = (a["assetNumber"].str.strip().str.lower() == "prospectus loan id") & a["assetTypeNumber"].notna()
    a = a.copy()
    a["flag_swapped_asset_number"] = swapped
    a.loc[swapped, ["assetNumber", "assetTypeNumber"]] = a.loc[swapped, ["assetTypeNumber", "assetNumber"]].values
    return a


def _number_cols(df: pd.DataFrame, col: str) -> pd.DataFrame:
    parsed = df[col].map(asset_numbers.parse)
    df = df.copy()
    df["root"] = parsed.map(lambda x: x.root).astype("Int64")
    df["note"] = parsed.map(lambda x: x.note)
    df["child"] = parsed.map(lambda x: x.child).astype("Int64")
    df["number_ok"] = parsed.map(lambda x: x.ok)
    df["loan_id"] = parsed.map(lambda x: x.loan_id)
    return df


def resolve(assets: pd.DataFrame, props: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return (loan_period, property_period) for one trust."""
    a = _number_cols(_fix_swapped_numbers(assets), "assetNumber")
    a = a[a["number_ok"]].copy() if a["number_ok"].all() else a  # unparsed numbers kept and flagged below
    a["is_child"] = a["child"].notna()
    a["is_note"] = (a["note"] != "") & ~a["is_child"]
    a["is_parent"] = ~a["is_child"] & ~a["is_note"] & a["root"].notna()
    a["has_loan_fields"] = a[LOAN_SIGNAL].notna().any(axis=1)

    g = a.groupby(["accession", "root"], dropna=False)
    root_info = pd.DataFrame({
        "has_parent": g["is_parent"].any(),
        "n_notes": g["is_note"].sum(),
        "n_children": g["is_child"].sum(),
        "children_loan_fields": g.apply(lambda x: bool((x["is_child"] & x["has_loan_fields"]).any()),
                                        include_groups=False),
        "parent_blocks": g.apply(lambda x: int(x.loc[x["is_parent"], "n_property_blocks"].sum()),
                                 include_groups=False),
    }).reset_index()

    def layout(r) -> str:
        if r.n_notes > 0:
            return "notes"
        if r.has_parent and r.n_children > 0:
            return "parent_children"
        if r.has_parent:
            return "nested" if r.parent_blocks > 1 else "single"
        if r.n_children > 0:
            return "replicated" if r.children_loan_fields else "orphan"
        return "unparsed"

    root_info["layout"] = root_info.apply(layout, axis=1)
    a = a.merge(root_info[["accession", "root", "layout", "has_parent", "n_notes", "n_children"]],
                on=["accession", "root"], how="left")

    # ---- loan records ------------------------------------------------------
    explicit = a[a["is_parent"] | a["is_note"]].copy()
    explicit["loan_source"] = np.where(explicit["is_note"], "note_record", "loan_record")
    synth_src = a[a["is_child"] & ~a["has_parent"] & (a["n_notes"] == 0)]
    synth = synth_src.sort_values("asset_seq").groupby(["accession", "root"]).head(1).copy()
    synth["loan_id"] = synth["root"].astype(str)
    synth["loan_source"] = np.where(synth["layout"] == "replicated", "replicated_child", "orphan_child")
    # consistency of the replicated loan fields across children
    if len(synth_src):
        nun = synth_src.groupby(["accession", "root"])[CONSISTENCY_KEYS].nunique(dropna=True)
        incons = (nun > 1).any(axis=1).rename("flag_replicated_inconsistent").reset_index()
        synth = synth.merge(incons, on=["accession", "root"], how="left")
    unparsed = a[a["root"].isna()].copy()
    unparsed["loan_id"] = "X" + unparsed["assetNumber"].astype(str)
    unparsed["loan_source"] = "unparsed_number"
    loans = pd.concat([explicit, synth, unparsed], ignore_index=True)
    loans["flag_replicated_inconsistent"] = loans.get("flag_replicated_inconsistent", False)
    loans["flag_replicated_inconsistent"] = loans["flag_replicated_inconsistent"].fillna(False).astype(bool)
    loans["flag_unparsed_number"] = loans["loan_source"] == "unparsed_number"

    # ---- property blocks and roles ----------------------------------------
    p = props.merge(a[["accession", "asset_seq", "root", "note", "child", "is_child", "is_note", "is_parent",
                       "layout", "n_children", "has_parent"]], on=["accession", "asset_seq"], how="left")
    role = np.where(p["is_child"], "property", None)
    role = np.where(p["is_parent"] & (p["n_children"] > 0), "rollup", role)
    role = np.where(p["is_parent"] & (p["n_children"] == 0), "property", role)
    # notes: their blocks count only when nothing else at the root carries collateral
    first_note = (p[p["is_note"]].sort_values("asset_seq").groupby(["accession", "root"])["asset_seq"].min()
                  .rename("first_note_seq").reset_index())
    p = p.merge(first_note, on=["accession", "root"], how="left")
    note_counts = p["is_note"] & ~p["has_parent"].fillna(False) & (p["n_children"].fillna(0) == 0) & \
        (p["asset_seq"] == p["first_note_seq"])
    role = np.where(p["is_note"], np.where(note_counts, "property", "note_block"), role)
    role = np.where(pd.isna(role), "property", role)  # unparsed numbers: keep as property
    p["block_role"] = role

    occ_cur, bad_cur = units.occupancy(p["mostRecentPhysicalOccupancyPercentage"])
    occ_sec, bad_sec = units.occupancy(p["physicalOccupancySecuritizationPercentage"])
    p["occupancy_current"], p["occupancy_securitization"] = occ_cur, occ_sec
    p["flag_occupancy_unreadable"] = bad_cur | bad_sec

    # ---- loan-level financials per (accession, root) ------------------------
    real = p[p["block_role"] == "property"].copy()
    keys = ["accession", "root"]
    agg = real.groupby(keys).agg(
        n_properties=("property_seq", "size"),
        n_fin_end_dates=("mostRecentFinancialsEndDate", "nunique"),
        n_with_noi=("mostRecentNetOperatingIncomeAmount", "count"),
        **{v: (k, lambda s: s.sum(min_count=1)) for k, v in {**FIN_SUM, **VALUE_SUM}.items()},
    )
    w_sqft = real["netRentableSquareFeetNumber"].fillna(real["unitsBedsRoomsNumber"]).fillna(1.0)
    real["_w"] = w_sqft
    real["_wocc"] = real["occupancy_current"] * w_sqft
    real["_wocc_sec"] = real["occupancy_securitization"] * w_sqft
    occ = real.groupby(keys).apply(
        lambda x: pd.Series({
            "occ_current_w": x["_wocc"].sum(min_count=1) / x.loc[x["occupancy_current"].notna(), "_w"].sum()
            if x["occupancy_current"].notna().any() else np.nan,
            "occ_sec_w": x["_wocc_sec"].sum(min_count=1) / x.loc[x["occupancy_securitization"].notna(), "_w"].sum()
            if x["occupancy_securitization"].notna().any() else np.nan,
        }), include_groups=False)
    agg = agg.join(occ)
    # largest property by appraisal, else by square feet
    real["_size"] = real["valuationSecuritizationAmount"].fillna(real["netRentableSquareFeetNumber"]).fillna(0)
    largest = real.sort_values(["_size", "property_seq"], ascending=[False, True]).groupby(keys).head(1)
    largest = largest.set_index(keys)[list(LARGEST_ATTRS) + list(ROLLUP_ONLY)].rename(
        columns={**LARGEST_ATTRS, **{k: "single_" + v for k, v in ROLLUP_ONLY.items()}})
    agg = agg.join(largest)

    rollup = p[p["block_role"] == "rollup"].sort_values("property_seq").groupby(keys).head(1).set_index(keys)
    roll = rollup[list(FIN_SUM) + list(VALUE_SUM) + list(ROLLUP_ONLY)].rename(
        columns={**{k: "roll_" + v for k, v in FIN_SUM.items()}, **{k: "roll_" + v for k, v in VALUE_SUM.items()},
                 **{k: "roll_" + v for k, v in ROLLUP_ONLY.items()}})
    roll["roll_occ_current"] = rollup["occupancy_current"]
    roll["roll_occ_sec"] = rollup["occupancy_securitization"]
    fin = agg.join(roll, how="outer").reset_index()

    has_roll = fin.get("roll_fin_noi", pd.Series(np.nan, index=fin.index)).notna()
    single = fin["n_properties"] == 1
    same_period = fin["n_fin_end_dates"].fillna(0) <= 1
    all_noi = fin["n_with_noi"] == fin["n_properties"]
    fin["fin_source"] = np.select(
        [has_roll, single, same_period & all_noi, fin["n_with_noi"].fillna(0) == 0],
        ["rollup", "single", "sum", "none"], default="mixed")
    use_roll = fin["fin_source"] == "rollup"
    use_props = fin["fin_source"].isin(["single", "sum"])
    for v in FIN_SUM.values():
        rv = fin.get("roll_" + v, pd.Series(np.nan, index=fin.index))
        fin[v] = np.where(use_roll, rv, np.where(use_props, fin[v], np.nan))
    for v in VALUE_SUM.values():  # value and size: roll-up when present, else the property sum
        rv = fin.get("roll_" + v, pd.Series(np.nan, index=fin.index))
        fin[v] = rv.where(rv.notna(), fin[v])
    for k, v in ROLLUP_ONLY.items():
        rv = fin.get("roll_" + v, pd.Series(np.nan, index=fin.index))
        sv = fin.get("single_" + v, pd.Series(np.nan, index=fin.index))
        fin[v] = np.where(use_roll, rv, np.where(single, sv, np.nan)) if v.startswith("dscr") else \
            rv.where(rv.notna(), sv)
    fin["occupancy_current"] = fin.get("roll_occ_current", np.nan)
    fin["occupancy_current"] = fin["occupancy_current"].where(fin["occupancy_current"].notna(), fin["occ_current_w"])
    fin["occupancy_securitization"] = fin.get("roll_occ_sec", np.nan)
    fin["occupancy_securitization"] = fin["occupancy_securitization"].where(
        fin["occupancy_securitization"].notna(), fin["occ_sec_w"])
    fin["flag_mixed_fin_periods"] = fin["fin_source"] == "mixed"
    drop = [c for c in fin.columns if c.startswith(("roll_", "single_", "occ_"))]
    fin = fin.drop(columns=drop)

    loans = loans.merge(fin, on=keys, how="left")
    loans["n_notes_sharing_collateral"] = loans["n_notes"].fillna(0).astype(int) + loans["has_parent"].fillna(False).astype(int)
    for c in RATE_FIELDS:
        if c in loans:
            loans[c], bad = units.rate(loans[c])
            loans["flag_rate_unreadable"] = loans.get("flag_rate_unreadable", False) | bad
    loans["loan_key"] = loans["trust_cik"].astype(str) + ":" + loans["loan_id"].astype(str)
    loans["root_key"] = loans["trust_cik"].astype(str) + ":" + loans["root"].astype("string")
    p["property_key"] = (p["trust_cik"].astype(str) + ":" + p["root"].astype("string") + "-"
                         + p["child"].astype("string").fillna("0") + "-" + p["property_seq"].astype(str))
    return loans, p
