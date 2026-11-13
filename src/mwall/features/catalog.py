"""The feature catalog: one entry per feature, the single source for the dictionary
(docs/features.md), the distribution plots and the leakage audit's input check.

``inputs`` names filing fields (their XML or clean-layer names) or market series. ``lag`` says
when the inputs become usable relative to the snapshot date T, which is the filing date.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Feature:
    name: str
    family: str
    definition: str
    unit: str
    inputs: tuple[str, ...]
    lag: str = "same filing (public on T)"
    nulls: str = "null when an input is missing"
    kind: str = "num"           # num, bool, cat
    clip: tuple[float, float] | None = None   # plot range; values outside are counted, not drawn
    tags: tuple[str, ...] = field(default_factory=tuple)


LEV, CF, OCC, TERMS, PROP, SERV, MKT = (
    "Leverage and coverage", "Cash-flow trend", "Occupancy and tenants", "Loan terms", "Property",
    "Servicing and status", "Market and macro")
EARLIER = "same filing and earlier filings of the loan (all public on or before T)"

CATALOG: list[Feature] = [
    # leverage and coverage
    Feature("f_debt_yield_noi", LEV, "Annualized most-recent NOI / whole-loan balance", "ratio",
            ("fin_noi_annual", "wl_balance_est"), clip=(0, 0.4)),
    Feature("f_debt_yield_ncf", LEV, "Annualized most-recent NCF / whole-loan balance", "ratio",
            ("fin_ncf_annual", "wl_balance_est"), clip=(0, 0.4)),
    Feature("f_dscr_noi_reported", LEV, "Most recent NOI DSCR as reported by the servicer", "x",
            ("mostRecentDebtServiceCoverageNetOperatingIncomePercentage",), clip=(0, 5)),
    Feature("f_dscr_noi_recomputed", LEV, "Most recent NOI / most recent debt service, both as reported", "x",
            ("mostRecentNetOperatingIncomeAmount", "mostRecentDebtServiceAmount"), clip=(0, 5)),
    Feature("f_dscr_disagree", LEV, "Reported and recomputed DSCR differ by more than 5%", "flag",
            ("dscr_noi_reported", "dscr_noi_recomputed"), kind="bool"),
    Feature("f_ltv_securitization", LEV, "Whole-loan balance / appraised value at securitization (stale by "
            "construction)", "ratio", ("wl_balance_est", "valuationSecuritizationAmount"), clip=(0, 1.2)),
    Feature("f_ltv_recent", LEV, "Whole-loan balance / most recent valuation, when that valuation is dated on or "
            "before T", "ratio", ("wl_balance_est", "mostRecentValuationAmount", "mostRecentValuationDate"),
            clip=(0, 2)),
    Feature("f_reappraised", LEV, "A valuation dated more than a year after the securitization appraisal and on "
            "or before T", "flag", ("mostRecentValuationDate", "valuationSecuritizationDate"), kind="bool"),
    Feature("f_value_model", LEV, "Annualized NOI / benchmark cap rate for the property type at T", "USD",
            ("fin_noi_annual", "cap_rate_benchmark"), lag="cap rate survey from its publication date",
            tags=("needs_cap_rates",), clip=(0, 150_000_000)),
    Feature("f_ltv_model", LEV, "Whole-loan balance / f_value_model (tests H4)", "ratio",
            ("wl_balance_est", "fin_noi_annual", "cap_rate_benchmark"), lag="cap rate survey from its "
            "publication date", tags=("needs_cap_rates",), clip=(0, 2)),
    Feature("f_refi_rate", LEV, "10-year Treasury at T + CBRE's quarterly permanent-loan spread (commercial or "
            "multifamily series), the latest published by T, + a fixed property-type premium (config/"
            "lender_params.csv, base scenario)", "rate", ("DGS10", "config/lender_spreads.csv", "spread premium"),
            lag="Treasury from the next day; spread from its publication date; premium is a fixed cited parameter",
            tags=("needs_lender_params",), clip=(0, 0.12)),
    Feature("f_refi_dscr", LEV, "Annualized NOI / (whole-loan balance x loan constant at f_refi_rate and the "
            "type's amortization)", "x", ("fin_noi_annual", "wl_balance_est", "f_refi_rate"),
            lag="as f_refi_rate", tags=("needs_lender_params",), clip=(0, 5)),
    Feature("f_refi_dy_cushion", LEV, "f_debt_yield_noi - lender minimum debt yield for the type", "ratio",
            ("f_debt_yield_noi", "lender dy_min"), tags=("needs_lender_params",), clip=(-0.2, 0.3)),
    Feature("f_refi_gap_income", LEV, "max(0, B - min(NOI/(DSCRmin x k), NOI/DYmin)) / B: share of the whole-loan "
            "balance a new loan sized on income could not cover", "share of balance",
            ("fin_noi_annual", "wl_balance_est", "lender params"), tags=("needs_lender_params",), clip=(0, 1)),
    Feature("f_refi_gap", LEV, "As f_refi_gap_income with LTVmax x f_value_model as a third constraint (SOP 12 "
            "step A, unstressed NOI)", "share of balance", ("f_refi_gap_income", "f_value_model"),
            tags=("needs_lender_params", "needs_cap_rates"), clip=(0, 1)),
    # cash-flow trend
    Feature("f_noi_vs_securitization", CF, "Annualized NOI / underwritten NOI at securitization - 1", "ratio",
            ("fin_noi_annual", "netOperatingIncomeSecuritizationAmount"), clip=(-1, 1.5)),
    Feature("f_noi_yoy", CF, "NOI / NOI for the financial period ending a year earlier (+-45 days), that period as "
            "first reported", "ratio", ("fin_noi_annual", "fin_end"), lag=EARLIER, clip=(-1, 1.5)),
    Feature("f_expense_ratio", CF, "Annualized operating expenses / annualized revenue", "ratio",
            ("fin_opex_annual", "fin_revenue_annual"), clip=(0, 1.2)),
    Feature("f_noi_age_months", CF, "Months from the financials end date to the filing date", "months",
            ("mostRecentFinancialsEndDate", "filing_date"), clip=(0, 36)),
    Feature("f_noi_missing", CF, "No usable current NOI (missing, or financial basis unknown)", "flag",
            ("fin_noi_annual",), nulls="never null", kind="bool"),
    # occupancy and tenants
    Feature("f_occupancy", OCC, "Most recent physical occupancy", "fraction",
            ("physicalOccupancyMostRecentPercentage",), clip=(0, 1)),
    Feature("f_occupancy_change", OCC, "f_occupancy - occupancy at securitization", "fraction points",
            ("physicalOccupancyMostRecentPercentage", "physicalOccupancySecuritizationPercentage"), clip=(-0.6, 0.4)),
    Feature("f_tenant1_share", OCC, "Largest tenant's square feet / the largest property's square feet", "fraction",
            ("squareFeetLargestTenantNumber", "netRentableSquareFeetNumber"), nulls="null when no tenant is "
            "listed (multifamily, lodging) or the share exceeds 1", clip=(0, 1)),
    Feature("f_rollover_24m", OCC, "Share of the top three tenants' listed square feet with a lease ending within "
            "24 months of T (leases already past their end date count)", "fraction",
            ("squareFeet*TenantNumber", "leaseExpiration*TenantDate"), clip=(0, 1)),
    # loan terms
    Feature("f_months_to_maturity", TERMS, "Months from the reporting period end to the maturity date as reported "
            "at T", "months", ("maturityDate", "reportingPeriodEndDate"), clip=(-12, 132)),
    Feature("f_term_months", TERMS, "Original term from origination and maturity dates (SOP 8.5)", "months",
            ("originationDate", "maturityDate"), clip=(0, 180)),
    Feature("f_seasoning_months", TERMS, "Months from origination to the reporting period end", "months",
            ("originationDate", "reportingPeriodEndDate"), clip=(0, 144)),
    Feature("f_coupon", TERMS, "Current interest rate", "rate", ("reportPeriodInterestRatePercentage",),
            clip=(0, 0.1)),
    Feature("f_rate_shock", TERMS, "f_refi_rate - f_coupon (tests H3)", "rate", ("f_refi_rate", "f_coupon"),
            lag="as f_refi_rate", tags=("needs_lender_params",), clip=(-0.04, 0.06)),
    Feature("f_ust10_change_since_origination", TERMS, "10-year Treasury at T - 10-year Treasury at origination "
            "(parameter-free version of the rate shock)", "rate", ("DGS10", "originationDate"),
            lag="Treasury from the next day", clip=(-0.03, 0.04)),
    Feature("f_io_remaining_months", TERMS, "Interest-only months left: origination + IO term - period end, "
            "floored at 0", "months", ("originationDate", "originalInterestOnlyTermNumber"), clip=(0, 120)),
    Feature("f_full_term_io", TERMS, "Interest-only for the whole term (IO term within a month of the term, or "
            "zero amortization)", "flag", ("originalInterestOnlyTermNumber", "originalAmortizationTermNumber"),
            kind="bool"),
    Feature("f_balloon_share", TERMS, "Scheduled balance at maturity / original balance, from the original rate, "
            "IO period, amortization term and term from dates", "fraction",
            ("originalInterestRatePercentage", "originalInterestOnlyTermNumber", "originalAmortizationTermNumber"),
            clip=(0, 1)),
    Feature("f_extended", TERMS, "Maturity date at T is later than the first reported maturity date", "flag",
            ("maturityDate",), lag=EARLIER, kind="bool"),
    Feature("f_trust_share", TERMS, "The trust's share of the whole loan (D020); 1 for a whole loan (code WL) "
            "with no evidence of debt outside the trust", "fraction", ("trust_share_est", "loanStructureCode"),
            clip=(0, 1)),
    Feature("f_pari_passu_piece", TERMS, "Loan structure code PP (pari passu debt outside the trust), or a trust "
            "share below 0.99", "flag", ("loanStructureCode", "trust_share_est"), kind="bool"),
    Feature("f_ab_structure", TERMS, "Loan structure code A1, A2, B1, B2 or C2 (an A/B or A/B/C participation)",
            "flag", ("loanStructureCode",), kind="bool"),
    Feature("f_debt_outside_trust", TERMS, "Either of the two above: part of the loan's debt sits outside this "
            "trust", "flag", ("loanStructureCode", "trust_share_est"), kind="bool"),
    Feature("f_n_notes_in_trust", TERMS, "Note records of this loan in this trust", "count", ("assetNumber",),
            clip=(1, 6)),
    Feature("f_n_properties", TERMS, "Properties securing the loan", "count", ("property blocks",), clip=(1, 20)),
    Feature("f_single_asset", TERMS, "Secured by one property", "flag", ("property blocks",), kind="bool"),
    # property
    Feature("property_group", PROP, "Property type group (D024)", "category", ("propertyTypeCode",), kind="cat"),
    Feature("prop_type_code", PROP, "Property type code as filed (largest property)", "category",
            ("propertyTypeCode",), kind="cat"),
    Feature("f_cooperative", PROP, "Cooperative housing (code CH): a co-op blanket loan, with low leverage and "
            "DSCR often reported as 0, inside the multifamily group", "flag", ("propertyTypeCode",), kind="bool"),
    Feature("prop_state", PROP, "State of the largest property", "category", ("propertyState",), kind="cat"),
    Feature("cbsa_code", PROP, "OMB 2023 metro of the largest property (D034)", "category",
            ("propertyAddress", "geography"), kind="cat"),
    Feature("f_property_age_years", PROP, "Reporting year - year built", "years", ("yearBuiltNumber",),
            clip=(0, 120)),
    Feature("f_years_since_renovation", PROP, "Reporting year - later of year built and year last renovated",
            "years", ("yearBuiltNumber", "yearLastRenovated"), clip=(0, 80)),
    Feature("f_balance_per_unit", PROP, "Whole-loan balance / units (multifamily and lodging only)", "USD per unit",
            ("wl_balance_est", "unitsBedsRoomsNumber"), clip=(0, 600_000)),
    Feature("f_balance_per_sqft", PROP, "Whole-loan balance / net rentable square feet (all other types)",
            "USD per sq ft", ("wl_balance_est", "netRentableSquareFeetNumber"), clip=(0, 800)),
    # servicing and status
    Feature("delinquency_bucket", SERV, "Decoded payment status at T. Used only for labels that look strictly "
            "forward from T", "category", ("paymentStatusLoanCode",), kind="cat"),
    Feature("f_ever_modified", SERV, "A modification event at or before T (indicator switch-on or a new "
            "modification date)", "flag", ("reportPeriodModificationIndicator", "lastModificationDate"),
            lag=EARLIER, kind="bool"),
    Feature("f_ever_special_serviced", SERV, "A special-servicing transfer date reported at or before T", "flag",
            ("mostRecentSpecialServicerTransferDate",), lag=EARLIER, kind="bool"),
    Feature("f_in_special_servicing", SERV, "Transferred and not yet returned at T", "flag",
            ("mostRecentSpecialServicerTransferDate", "mostRecentMasterServicerReturnDate"), kind="bool"),
    Feature("f_advances_pi", SERV, "P&I advances outstanding above zero", "flag",
            ("totalPrincipalInterestAdvancedOutstandingAmount",), kind="bool"),
    Feature("f_advances_ti", SERV, "Tax and insurance advances outstanding above zero", "flag",
            ("totalTaxesInsuranceAdvancesOutstandingAmount",), kind="bool"),
    Feature("f_advances_other", SERV, "Other expense advances outstanding above zero", "flag",
            ("otherExpensesAdvancedOutstandingAmount",), kind="bool"),
    Feature("f_advances_pct", SERV, "All advances outstanding / the trust's balance", "ratio",
            ("advances", "balance"), clip=(0, 0.1)),
    # market and macro
    Feature("f_ust10", MKT, "10-year constant-maturity Treasury yield", "rate", ("FRED DGS10",),
            lag="value of the day before T or earlier", clip=(0, 0.06)),
    Feature("f_ust5", MKT, "5-year constant-maturity Treasury yield", "rate", ("FRED DGS5",),
            lag="value of the day before T or earlier", clip=(0, 0.06)),
    Feature("f_ust10_change_12m", MKT, "f_ust10 - the 10-year yield a year before T", "rate", ("FRED DGS10",),
            lag="as f_ust10", clip=(-0.03, 0.04)),
    Feature("f_curve_10y2y", MKT, "10-year minus 2-year Treasury yield", "rate", ("FRED DGS10", "FRED DGS2"),
            lag="as f_ust10", clip=(-0.02, 0.03)),
    Feature("f_cap_rate_benchmark", MKT, "National cap rate for the property type: CBRE survey averages through "
            "H2 2019 (retail H1 2022), carried forward by CoStar's monthly changes, the latest value published on or "
            "before T; none for self-storage, and lodging lapses two years after its last survey period (D048)",
            "rate", ("config/cap_rates.csv",), lag="survey value from its publication date",
            nulls="null for self-storage and other types, and when the latest value describes a period more than "
            "two years before T", tags=("needs_cap_rates",), clip=(0.03, 0.12)),
    Feature("f_rent_growth_yoy", MKT, "Zillow Observed Rent Index (all homes), metro, 12-month change", "ratio",
            ("Zillow ZORI",), lag="month used from the end of the next month", clip=(-0.1, 0.2)),
    Feature("f_mf_rent_growth_yoy", MKT, "Zillow Observed Rent Index (multifamily), metro, 12-month change",
            "ratio", ("Zillow ZORI multifamily",), lag="month used from the end of the next month",
            clip=(-0.1, 0.2)),
    Feature("f_emp_growth_yoy", MKT, "QCEW total covered employment, metro, change on the same quarter a year "
            "earlier (third month)", "ratio", ("BLS QCEW industry 10",), lag="quarter used from six months after "
            "it ends", clip=(-0.15, 0.1)),
    Feature("f_office_emp_growth_yoy", MKT, "QCEW private information, financial and professional and business "
            "services employment, metro, change on a year earlier", "ratio", ("BLS QCEW 1022, 1023, 1024",),
            lag="as f_emp_growth_yoy", clip=(-0.15, 0.15)),
    Feature("f_permits_per_1k_units", MKT, "Housing units permitted in the trailing 12 months per 1,000 existing "
            "housing units, metro", "per 1,000 units", ("Census BPS county", "Census housing-unit estimates"),
            lag="month used from the end of the second month after it; housing stock from July 1 of the next "
            "year", clip=(0, 40)),
    Feature("f_permits_5plus_per_1k_units", MKT, "As f_permits_per_1k_units for units in 5+ unit buildings",
            "per 1,000 units", ("Census BPS county", "Census housing-unit estimates"),
            lag="as f_permits_per_1k_units", clip=(0, 25)),
]

BY_NAME = {f.name: f for f in CATALOG}

# Fields that describe how a loan ended. They feed labels and must never be a feature input.
OUTCOME_FIELDS = {
    "realizedLossToTrustAmount", "liquidationPrepaymentCode", "liquidationPrepaymentDate",
    "prepaymentPremiumYieldMaintenanceReceivedAmount", "y_distress_12m", "y_fail", "next_distress",
    "next_payoff", "payoff_date", "severity", "outcome", "last_obs",
}
