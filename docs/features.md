# Feature dictionary

Generated from `src/mwall/features/catalog.py`; do not edit by hand. SOP section 9. The snapshot date T of a row is its filing date. Every feature is computed from information public on or before T; `lag` says how. Nothing is imputed: a missing input leaves the feature null, and `f_noi_missing` marks rows without current NOI. Ratios use the whole-loan balance (`wl_balance_est`), because NOI, value and reported DSCR describe the whole collateral.

## Leverage and coverage

| feature | definition | unit | inputs | lag | nulls | coverage |
| --- | --- | --- | --- | --- | --- | --- |
| `f_debt_yield_noi` | Annualized most-recent NOI / whole-loan balance | ratio | `fin_noi_annual`, `wl_balance_est` | same filing (public on T) | null when an input is missing | 63% |
| `f_debt_yield_ncf` | Annualized most-recent NCF / whole-loan balance | ratio | `fin_ncf_annual`, `wl_balance_est` | same filing (public on T) | null when an input is missing | 63% |
| `f_dscr_noi_reported` | Most recent NOI DSCR as reported by the servicer | x | `mostRecentDebtServiceCoverageNetOperatingIncomePercentage` | same filing (public on T) | null when an input is missing | 68% |
| `f_dscr_noi_recomputed` | Most recent NOI / most recent debt service, both as reported | x | `mostRecentNetOperatingIncomeAmount`, `mostRecentDebtServiceAmount` | same filing (public on T) | null when an input is missing | 65% |
| `f_dscr_disagree` | Reported and recomputed DSCR differ by more than 5% | flag | `dscr_noi_reported`, `dscr_noi_recomputed` | same filing (public on T) | null when an input is missing | 100% |
| `f_ltv_securitization` | Whole-loan balance / appraised value at securitization (stale by construction) | ratio | `wl_balance_est`, `valuationSecuritizationAmount` | same filing (public on T) | null when an input is missing | 95% |
| `f_ltv_recent` | Whole-loan balance / most recent valuation, when that valuation is dated on or before T | ratio | `wl_balance_est`, `mostRecentValuationAmount`, `mostRecentValuationDate` | same filing (public on T) | null when an input is missing | 41% |
| `f_reappraised` | A valuation dated more than a year after the securitization appraisal and on or before T | flag | `mostRecentValuationDate`, `valuationSecuritizationDate` | same filing (public on T) | null when an input is missing | 100% |
| `f_value_model` | Annualized NOI / benchmark cap rate for the property type at T | USD | `fin_noi_annual`, `cap_rate_benchmark` | cap rate survey from its publication date | null when an input is missing | 46% |
| `f_ltv_model` | Whole-loan balance / f_value_model (tests H4) | ratio | `wl_balance_est`, `fin_noi_annual`, `cap_rate_benchmark` | cap rate survey from its publication date | null when an input is missing | 46% |
| `f_refi_rate` | 10-year Treasury at T + CBRE's quarterly permanent-loan spread (commercial or multifamily series), the latest published by T, + a fixed property-type premium (config/lender_params.csv, base scenario) | rate | `DGS10`, `config/lender_spreads.csv`, `spread premium` | Treasury from the next day; spread from its publication date; premium is a fixed cited parameter | null when an input is missing | 100% |
| `f_refi_dscr` | Annualized NOI / (whole-loan balance x loan constant at f_refi_rate and the type's amortization) | x | `fin_noi_annual`, `wl_balance_est`, `f_refi_rate` | as f_refi_rate | null when an input is missing | 63% |
| `f_refi_dy_cushion` | f_debt_yield_noi - lender minimum debt yield for the type | ratio | `f_debt_yield_noi`, `lender dy_min` | same filing (public on T) | null when an input is missing | 63% |
| `f_refi_gap_income` | max(0, B - min(NOI/(DSCRmin x k), NOI/DYmin)) / B: share of the whole-loan balance a new loan sized on income could not cover | share of balance | `fin_noi_annual`, `wl_balance_est`, `lender params` | same filing (public on T) | null when an input is missing | 63% |
| `f_refi_gap` | As f_refi_gap_income with LTVmax x f_value_model as a third constraint (SOP 12 step A, unstressed NOI) | share of balance | `f_refi_gap_income`, `f_value_model` | same filing (public on T) | null when an input is missing | 46% |

## Cash-flow trend

| feature | definition | unit | inputs | lag | nulls | coverage |
| --- | --- | --- | --- | --- | --- | --- |
| `f_noi_vs_securitization` | Annualized NOI / underwritten NOI at securitization - 1 | ratio | `fin_noi_annual`, `netOperatingIncomeSecuritizationAmount` | same filing (public on T) | null when an input is missing | 59% |
| `f_noi_yoy` | NOI / NOI for the financial period ending a year earlier (+-45 days), that period as first reported | ratio | `fin_noi_annual`, `fin_end` | same filing and earlier filings of the loan (all public on or before T) | null when an input is missing | 43% |
| `f_expense_ratio` | Annualized operating expenses / annualized revenue | ratio | `fin_opex_annual`, `fin_revenue_annual` | same filing (public on T) | null when an input is missing | 64% |
| `f_noi_age_months` | Months from the financials end date to the filing date | months | `mostRecentFinancialsEndDate`, `filing_date` | same filing (public on T) | null when an input is missing | 66% |
| `f_noi_missing` | No usable current NOI (missing, or financial basis unknown) | flag | `fin_noi_annual` | same filing (public on T) | never null | 100% |

## Occupancy and tenants

| feature | definition | unit | inputs | lag | nulls | coverage |
| --- | --- | --- | --- | --- | --- | --- |
| `f_occupancy` | Most recent physical occupancy | fraction | `physicalOccupancyMostRecentPercentage` | same filing (public on T) | null when an input is missing | 67% |
| `f_occupancy_change` | f_occupancy - occupancy at securitization | fraction points | `physicalOccupancyMostRecentPercentage`, `physicalOccupancySecuritizationPercentage` | same filing (public on T) | null when an input is missing | 66% |
| `f_tenant1_share` | Largest tenant's square feet / the largest property's square feet | fraction | `squareFeetLargestTenantNumber`, `netRentableSquareFeetNumber` | same filing (public on T) | null when no tenant is listed (multifamily, lodging) or the share exceeds 1 | 51% |
| `f_rollover_24m` | Share of the top three tenants' listed square feet with a lease ending within 24 months of T (leases already past their end date count) | fraction | `squareFeet*TenantNumber`, `leaseExpiration*TenantDate` | same filing (public on T) | null when an input is missing | 53% |

## Loan terms

| feature | definition | unit | inputs | lag | nulls | coverage |
| --- | --- | --- | --- | --- | --- | --- |
| `f_months_to_maturity` | Months from the reporting period end to the maturity date as reported at T | months | `maturityDate`, `reportingPeriodEndDate` | same filing (public on T) | null when an input is missing | 98% |
| `f_term_months` | Original term from origination and maturity dates (SOP 8.5) | months | `originationDate`, `maturityDate` | same filing (public on T) | null when an input is missing | 97% |
| `f_seasoning_months` | Months from origination to the reporting period end | months | `originationDate`, `reportingPeriodEndDate` | same filing (public on T) | null when an input is missing | 99% |
| `f_coupon` | Current interest rate | rate | `reportPeriodInterestRatePercentage` | same filing (public on T) | null when an input is missing | 99% |
| `f_rate_shock` | f_refi_rate - f_coupon (tests H3) | rate | `f_refi_rate`, `f_coupon` | as f_refi_rate | null when an input is missing | 99% |
| `f_ust10_change_since_origination` | 10-year Treasury at T - 10-year Treasury at origination (parameter-free version of the rate shock) | rate | `DGS10`, `originationDate` | Treasury from the next day | null when an input is missing | 99% |
| `f_io_remaining_months` | Interest-only months left: origination + IO term - period end, floored at 0 | months | `originationDate`, `originalInterestOnlyTermNumber` | same filing (public on T) | null when an input is missing | 90% |
| `f_full_term_io` | Interest-only for the whole term (IO term within a month of the term, or zero amortization) | flag | `originalInterestOnlyTermNumber`, `originalAmortizationTermNumber` | same filing (public on T) | null when an input is missing | 89% |
| `f_balloon_share` | Scheduled balance at maturity / original balance, from the original rate, IO period, amortization term and term from dates | fraction | `originalInterestRatePercentage`, `originalInterestOnlyTermNumber`, `originalAmortizationTermNumber` | same filing (public on T) | null when an input is missing | 97% |
| `f_extended` | Maturity date at T is later than the first reported maturity date | flag | `maturityDate` | same filing and earlier filings of the loan (all public on or before T) | null when an input is missing | 100% |
| `f_trust_share` | The trust's share of the whole loan (D020); 1 for a whole loan (code WL) with no evidence of debt outside the trust | fraction | `trust_share_est`, `loanStructureCode` | same filing (public on T) | null when an input is missing | 95% |
| `f_pari_passu_piece` | Loan structure code PP (pari passu debt outside the trust), or a trust share below 0.99 | flag | `loanStructureCode`, `trust_share_est` | same filing (public on T) | null when an input is missing | 98% |
| `f_ab_structure` | Loan structure code A1, A2, B1, B2 or C2 (an A/B or A/B/C participation) | flag | `loanStructureCode` | same filing (public on T) | null when an input is missing | 98% |
| `f_debt_outside_trust` | Either of the two above: part of the loan's debt sits outside this trust | flag | `loanStructureCode`, `trust_share_est` | same filing (public on T) | null when an input is missing | 99% |
| `f_n_notes_in_trust` | Note records of this loan in this trust | count | `assetNumber` | same filing (public on T) | null when an input is missing | 100% |
| `f_n_properties` | Properties securing the loan | count | `property blocks` | same filing (public on T) | null when an input is missing | 100% |
| `f_single_asset` | Secured by one property | flag | `property blocks` | same filing (public on T) | null when an input is missing | 100% |

## Property

| feature | definition | unit | inputs | lag | nulls | coverage |
| --- | --- | --- | --- | --- | --- | --- |
| `property_group` | Property type group (D024) | category | `propertyTypeCode` | same filing (public on T) | null when an input is missing | 95% |
| `prop_type_code` | Property type code as filed (largest property) | category | `propertyTypeCode` | same filing (public on T) | null when an input is missing | 95% |
| `f_cooperative` | Cooperative housing (code CH): a co-op blanket loan, with low leverage and DSCR often reported as 0, inside the multifamily group | flag | `propertyTypeCode` | same filing (public on T) | null when an input is missing | 100% |
| `prop_state` | State of the largest property | category | `propertyState` | same filing (public on T) | null when an input is missing | 94% |
| `cbsa_code` | OMB 2023 metro of the largest property (D034) | category | `propertyAddress`, `geography` | same filing (public on T) | null when an input is missing | 92% |
| `f_property_age_years` | Reporting year - year built | years | `yearBuiltNumber` | same filing (public on T) | null when an input is missing | 97% |
| `f_years_since_renovation` | Reporting year - later of year built and year last renovated | years | `yearBuiltNumber`, `yearLastRenovated` | same filing (public on T) | null when an input is missing | 97% |
| `f_balance_per_unit` | Whole-loan balance / units (multifamily and lodging only) | USD per unit | `wl_balance_est`, `unitsBedsRoomsNumber` | same filing (public on T) | null when an input is missing | 30% |
| `f_balance_per_sqft` | Whole-loan balance / net rentable square feet (all other types) | USD per sq ft | `wl_balance_est`, `netRentableSquareFeetNumber` | same filing (public on T) | null when an input is missing | 56% |

## Servicing and status

| feature | definition | unit | inputs | lag | nulls | coverage |
| --- | --- | --- | --- | --- | --- | --- |
| `delinquency_bucket` | Decoded payment status at T. Used only for labels that look strictly forward from T | category | `paymentStatusLoanCode` | same filing (public on T) | null when an input is missing | 96% |
| `f_ever_modified` | A modification event at or before T (indicator switch-on or a new modification date) | flag | `reportPeriodModificationIndicator`, `lastModificationDate` | same filing and earlier filings of the loan (all public on or before T) | null when an input is missing | 100% |
| `f_ever_special_serviced` | A special-servicing transfer date reported at or before T | flag | `mostRecentSpecialServicerTransferDate` | same filing and earlier filings of the loan (all public on or before T) | null when an input is missing | 100% |
| `f_in_special_servicing` | Transferred and not yet returned at T | flag | `mostRecentSpecialServicerTransferDate`, `mostRecentMasterServicerReturnDate` | same filing (public on T) | null when an input is missing | 100% |
| `f_advances_pi` | P&I advances outstanding above zero | flag | `totalPrincipalInterestAdvancedOutstandingAmount` | same filing (public on T) | null when an input is missing | 100% |
| `f_advances_ti` | Tax and insurance advances outstanding above zero | flag | `totalTaxesInsuranceAdvancesOutstandingAmount` | same filing (public on T) | null when an input is missing | 100% |
| `f_advances_other` | Other expense advances outstanding above zero | flag | `otherExpensesAdvancedOutstandingAmount` | same filing (public on T) | null when an input is missing | 100% |
| `f_advances_pct` | All advances outstanding / the trust's balance | ratio | `advances`, `balance` | same filing (public on T) | null when an input is missing | 96% |

## Market and macro

| feature | definition | unit | inputs | lag | nulls | coverage |
| --- | --- | --- | --- | --- | --- | --- |
| `f_ust10` | 10-year constant-maturity Treasury yield | rate | `FRED DGS10` | value of the day before T or earlier | null when an input is missing | 100% |
| `f_ust5` | 5-year constant-maturity Treasury yield | rate | `FRED DGS5` | value of the day before T or earlier | null when an input is missing | 100% |
| `f_ust10_change_12m` | f_ust10 - the 10-year yield a year before T | rate | `FRED DGS10` | as f_ust10 | null when an input is missing | 100% |
| `f_curve_10y2y` | 10-year minus 2-year Treasury yield | rate | `FRED DGS10`, `FRED DGS2` | as f_ust10 | null when an input is missing | 100% |
| `f_cap_rate_benchmark` | National cap rate for the property type: CBRE survey averages through H2 2019 (retail H1 2022), carried forward by CoStar's monthly changes, the latest value published on or before T; none for self-storage, and lodging lapses two years after its last survey period (D048) | rate | `config/cap_rates.csv` | survey value from its publication date | null for self-storage and other types, and when the latest value describes a period more than two years before T | 69% |
| `f_rent_growth_yoy` | Zillow Observed Rent Index (all homes), metro, 12-month change | ratio | `Zillow ZORI` | month used from the end of the next month | null when an input is missing | 88% |
| `f_mf_rent_growth_yoy` | Zillow Observed Rent Index (multifamily), metro, 12-month change | ratio | `Zillow ZORI multifamily` | month used from the end of the next month | null when an input is missing | 85% |
| `f_emp_growth_yoy` | QCEW total covered employment, metro, change on the same quarter a year earlier (third month) | ratio | `BLS QCEW industry 10` | quarter used from six months after it ends | null when an input is missing | 90% |
| `f_office_emp_growth_yoy` | QCEW private information, financial and professional and business services employment, metro, change on a year earlier | ratio | `BLS QCEW 1022, 1023, 1024` | as f_emp_growth_yoy | null when an input is missing | 70% |
| `f_permits_per_1k_units` | Housing units permitted in the trailing 12 months per 1,000 existing housing units, metro | per 1,000 units | `Census BPS county`, `Census housing-unit estimates` | month used from the end of the second month after it; housing stock from July 1 of the next year | null when an input is missing | 85% |
| `f_permits_5plus_per_1k_units` | As f_permits_per_1k_units for units in 5+ unit buildings | per 1,000 units | `Census BPS county`, `Census housing-unit estimates` | as f_permits_per_1k_units | null when an input is missing | 85% |

Coverage: share of representative loan-months (one per whole loan and month) where the feature is not null. Columns `asof_*` in panel/features.parquet hold the publication date of each market value used, for the leakage audit.
