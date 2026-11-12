# Data dictionary

Layers follow SOP section 6. Raw: gzipped EX-102 per accession. Parsed: `parsed/assets` and `parsed/properties` (one row per `<assets>` record and per `<property>` block, every SEC field typed as filed). Clean: `parsed/loan_period` (one row per loan per reporting period) and `parsed/property_period` (one row per property block, with `block_role`).

## Fields from the filing

Every element of the SEC CMBS asset-data schema keeps its XML name, so any value traces back to the filing. The full list with Schedule AL item numbers is `config/sec_cmbs_schema_elements.csv`; code meanings are in `docs/sec_code_tables.md`. Units are as filed in the parsed layer and normalized only in the clean layer (D014, D023).

## Derived fields (clean layer)

| Field | Unit | Definition | Source |
| --- | --- | --- | --- |
| `loan_key` | string | trust_cik + ':' + loan_id. One loan within one trust. | `clean/structure.py` |
| `loan_id` | string | Normalized loan number: '15', a note '4-A', or a rootless note 'N-A-1-C3'. | `clean/asset_numbers.py` |
| `root` | int | Loan number shared by a loan, its notes and its property records; negative for rootless notes. | `clean/structure.py` |
| `root_key` | string | trust_cik + ':' + root. All notes and properties of one loan within one trust. | `clean/structure.py` |
| `layout` | string | single, nested, parent_children, replicated, first_child, notes, orphan (D022, D030). | `clean/structure.py` |
| `loan_source` | string | Which record supplied the loan fields: loan_record, note_record, replicated_child, orphan_child, unparsed_number. | `clean/structure.py` |
| `period_end` | date | reportingPeriodEndDate of the filing. | `clean/run.py` |
| `balance` | USD | Actual ending balance, else scheduled ending balance. The trust's piece only. | `clean/run.py` |
| `months_to_maturity` | months | (maturityDate - period_end) / 30.4375. | `clean/run.py` |
| `term_months_from_dates` | months | Months from origination to maturity, from dates (SOP 8.5). | `clean/run.py` |
| `fin_source` | string | Where loan financials came from: rollup, single, sum, mixed, none. | `clean/structure.py` |
| `fin_noi / fin_ncf / fin_revenue / fin_opex / fin_debt_service` | USD | Most recent financials for the loan's collateral, for the period fin_start to fin_end, as reported. | `clean/structure.py` |
| `fin_months` | months | Length of the most recent financial period. | `clean/run.py` |
| `fin_basis` | string | full_year, ytd, annualized or unknown (D021). | `clean/run.py` |
| `fin_*_annual` | USD/yr | Annualized financials: x 12/fin_months when ytd, as reported when annualized or full year, null when unknown. | `clean/run.py` |
| `dscr_noi_reported / dscr_ncf_reported` | ratio | Reported DSCR from the roll-up or single property block. | `clean/structure.py` |
| `dscr_noi_recomputed` | ratio | fin_noi / fin_debt_service. | `clean/run.py` |
| `val_securitization` | USD | Appraisal at securitization: roll-up block, else sum of properties. | `clean/structure.py` |
| `occupancy_current / occupancy_securitization` | fraction | Normalized per value (D023); roll-up, else weighted by square feet or units. | `clean/structure.py, clean/units.py` |
| `prop_*` | various | Attributes of the largest property (by appraisal, else square feet): name, address, city, state, ZIP, county, type, year built, top-3 tenants. | `clean/structure.py` |
| `property_group` | string | office, retail, lodging, industrial, multifamily, self_storage, mixed_use, defeased, other (D024). | `clean/code_tables.py` |
| `delinquency_bucket` | string | Payment status grouped: current, late_lt30, dq30, dq60, dq90plus, matured_performing, matured_nonperforming. | `clean/code_tables.py` |
| `*_label` | string | Official meaning of a coded field, read from the SEC XSD. | `clean/code_tables.py` |
| `root_trust_balance / root_trust_pi_annual` | USD | Sum over the trust's notes at this root of balance / scheduled P&I x 12. | `clean/run.py` |
| `trust_share_est` | fraction | root_trust_pi_annual / fin_debt_service_annual: the trust's share of the whole loan (D020). | `clean/run.py` |
| `wl_balance_est` | USD | Estimated whole-loan balance: root_trust_balance / trust_share_est, or the trust balance when the trust holds the whole loan. | `clean/run.py` |
| `noi_age_months` | months | Filing date minus fin_end. | `clean/run.py` |
| `valuation_age_years` | years | Filing date minus the latest valuation date. | `clean/run.py` |
| `flag_*` | bool | QA flags (SOP 8.7): noi_missing, noi_stale (>18 months), dscr_inconsistent (>5%), valuation_old (>5 years), zero_balance_active, mixed_fin_periods, fin_basis_unknown, fin_period_assumed, occupancy_unreadable, rate_unreadable, invalid_code, replicated_inconsistent, swapped_asset_number, unparsed_number, rootless_note. | `clean/run.py, clean/structure.py` |
| `whole_loan_id` | string | Cross-trust whole-loan group (parsed/whole_loans.parquet; D027). | `clean/whole_loans.py` |

### Screening and history fields (D035, D036)

| Field | Definition |
| --- | --- |
| `flag_transient_loan` | Loan first seen after the opening period, seen in at most three periods, gone before the latest, never coded as liquidated or prepaid |
| `flag_filing_corrupt` | Every row of a filing that holds another deal's records; excluded from the roll-forward, the 10-D check and the panel |
| `months_since_prev_report` | Months between this XML reporting period and the loan's previous one (corrupt filings aside) |
| `flag_history_gap` | `months_since_prev_report` above 1: at least one month missing, never filled |

`parsed/filing_screen/{cik}.parquet`, one row per filing: `n_exact_copies_dropped`, `n_split_records`, `n_foreign_repeats`, `n_transient_loans`, `n_loans_missing` (loans reported before and after but not in this filing), `corrupt_reason`, `superseded_by` (the filing that replaced it for the same XML reporting period).

## Property blocks (`property_period`)

| Field | Definition |
| --- | --- |
| `block_role` | `property` (a real property, counted once), `rollup` (a parent's portfolio summary), `note_block` (collateral already counted under a sibling note) |
| `property_key` | trust_cik:root-child-property_seq |
| `occupancy_current`, `occupancy_securitization` | Normalized to a fraction (D023) |
| `property_group` | As for loans |

## Geography (`parsed/geography.parquet`, one row per distinct address)

Join from a property record on `addr_key(propertyAddress, propertyCity, propertyState, propertyZip)` and from a loan on `addr_key(prop_address, prop_city, prop_state, prop_zip)` (the largest property), both in `mwall.clean.geography`.

| Field | Definition |
| --- | --- |
| `addr_key` | First 16 hex characters of SHA-1 over upper-cased, space-collapsed address, city, state and 5-digit ZIP |
| `zip5` | ZIP normalized to five digits; a 4-digit ZIP gets its leading zero back |
| `lat`, `lon` | Census Geocoder point; null unless the match lies in the filer's state or the ZIP's state |
| `gc_status`, `gc_match_type` | Geocoder result (`Match`, `No_Match`, `Tie`, `Skipped` for no street) and `Exact` or `Non_Exact` |
| `county_fips` | 5-digit county FIPS (2023 county equivalents; Connecticut planning regions) |
| `county_source` | `geocoder`, `reported_name`, `zip_crosswalk` or `none` (D034) |
| `zip_county_share` | Share of the ZIP's land area in its assigned county (ZIP crosswalk) |
| `cbsa_code`, `cbsa_title`, `cbsa_type` | OMB July 2023 metro or micro area; `cbsa_type` is `metro`, `micro`, or `none` for a county outside any CBSA |
| `metro_division_code`, `metro_division_title` | Metropolitan division where the metro has them (Los Angeles: 31084 Los Angeles-Long Beach-Glendale, 11244 Anaheim-Santa Ana-Irvine) |
| `csa_code`, `csa_title` | Combined statistical area |
| `flag_geocode_other_state` | Geocoder match outside both the filer's state and the ZIP's state; discarded |
