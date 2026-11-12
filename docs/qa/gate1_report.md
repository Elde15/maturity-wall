# Gate 1 data QA report

Generated 2026-11-12 by `python -m mwall qa`. Regenerate after every ingest.

## Ingestion

- Trusts in the universe: 381. With at least one parsed filing: 285.
- ABS-EE filings in the universe: 23,970. Downloaded: 3,320. No EX-102 attached: 0.
- Filings parsed: 1,845. Row counts reconcile (assets and property blocks in the XML equal rows written): 1,845 of 1,845 (100.0%).
- Parse status: {'ok': 1845}. Type failures: 0. Tags outside the SEC schema: 0.
- Trusts without a parsed filing yet: 96 (listed in `loan_count_rollforward.csv` once parsed; until the full download finishes most of these are simply not downloaded yet).

## Record layouts (loan-periods)

| layout | n |
| --- | --- |
| single | 71015 |
| parent_children | 7090 |
| notes | 5161 |
| nested | 3837 |
| replicated | 1414 |
| orphan | 8 |

By filer agent: `layouts_by_agent.csv`.

## Loan counts roll forward

Each trust's first reported period sets the opening loan count (the at-issuance pool). A loan that stops appearing is explained when it carried a liquidation or prepayment code or a zero balance. Tolerance: unexplained exits at most 2.0% of the opening count.

- Trusts checked: 280. Passing: 249. Opening loans: 13,289. Exits: 282, of which explained 2 and unexplained 280.

## Pool balance vs the 10-D distribution statement

- Trust-periods compared: 5. Sum of loan scheduled balances within 0.5% of the administrator's ending scheduled collateral balance: 3 (60.0%). Median absolute difference: 0.0%. By category: {'match': 3, 'filing_omits_balances': 2}. `filing_omits_balances` means the EX-102 itself leaves some loans' period balances blank, so the gap is in the source, not the pipeline. Detail: `balance_reconciliation.csv`.

## Ratio checks

- Reported DSCR vs NOI / debt service recomputed from the same filing: 53,588 loan-periods with both; 99.7% agree within 5% (SOP target 95%).

Financial basis of the most recent NOI (decision D021):

| fin_basis | n |
| --- | --- |
| ytd | 27577 |
| full_year | 14357 |
| annualized | 12404 |
| unknown | 3982 |

Estimated trust share of the whole loan by structure code (decision D020). Whole loans should sit near 1.0:

| structure | n | p25 | p50 | p75 |
| --- | --- | --- | --- | --- |
| WL | 39173 | 1.000 | 1.000 | 1.019 |
| PP | 9984 | 0.213 | 0.352 | 0.517 |
| A1 | 2269 | 0.056 | 0.131 | 0.293 |
|  | 983 | 0.527 | 1.000 | 1.018 |
| A2 | 213 | 0.045 | 0.134 | 0.253 |
| B1 | 25 | 0.319 | 0.979 | 1.015 |
| B2 | 6 | 0.180 | 0.248 | 0.252 |
| MZ | 3 | 1.019 | 1.019 | 1.019 |
| C2 | 1 | 0.372 | 0.372 | 0.372 |

Occupancy units as filed (property blocks; decision D023):

| unit | n |
| --- | --- |
| fraction | 124278 |
| null | 67391 |
| percent | 2017 |
| unreadable | 13 |

## Field coverage by filing year (active, non-defeased loan-periods)

| filing_year | n | balance | maturityDate | originationDate | reportPeriodInterestRatePercentage | paymentStatusLoanCode | fin_noi | fin_debt_service | dscr_noi_reported | val_securitization | occupancy_current | prop_type_code | prop_zip | fin_noi_annual | wl_balance_est |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2016 | 435 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 0.57 | 0.59 | 0.57 | 1.00 | 0.40 | 1.00 | 1.00 | 0.56 | 0.91 |
| 2017 | 4294 | 1.00 | 1.00 | 1.00 | 1.00 | 0.94 | 0.31 | 0.36 | 0.31 | 1.00 | 0.36 | 1.00 | 1.00 | 0.31 | 0.84 |
| 2018 | 8934 | 1.00 | 1.00 | 1.00 | 1.00 | 0.93 | 0.35 | 0.38 | 0.34 | 1.00 | 0.42 | 1.00 | 0.99 | 0.29 | 0.84 |
| 2019 | 13752 | 1.00 | 1.00 | 1.00 | 1.00 | 0.93 | 0.52 | 0.54 | 0.51 | 1.00 | 0.58 | 1.00 | 1.00 | 0.46 | 0.88 |
| 2020 | 9734 | 1.00 | 1.00 | 1.00 | 1.00 | 0.94 | 0.68 | 0.67 | 0.67 | 1.00 | 0.68 | 1.00 | 0.99 | 0.64 | 0.90 |
| 2021 | 10585 | 1.00 | 1.00 | 1.00 | 1.00 | 0.96 | 0.76 | 0.77 | 0.74 | 1.00 | 0.79 | 1.00 | 0.99 | 0.74 | 0.94 |
| 2022 | 11571 | 1.00 | 1.00 | 0.99 | 1.00 | 0.94 | 0.80 | 0.80 | 0.77 | 1.00 | 0.81 | 1.00 | 0.97 | 0.75 | 0.94 |
| 2023 | 12009 | 1.00 | 1.00 | 0.99 | 1.00 | 0.93 | 0.86 | 0.86 | 0.83 | 1.00 | 0.81 | 1.00 | 0.97 | 0.80 | 0.95 |
| 2024 | 9645 | 1.00 | 1.00 | 0.99 | 1.00 | 0.93 | 0.89 | 0.89 | 0.85 | 1.00 | 0.84 | 0.97 | 0.96 | 0.84 | 0.96 |
| 2026 | 4031 | 1.00 | 1.00 | 0.97 | 1.00 | 0.92 | 0.77 | 0.77 | 0.74 | 1.00 | 0.73 | 0.95 | 0.95 | 0.73 | 0.93 |

By vintage and deal family: `field_coverage_by_vintage_family.csv`.

## QA flags

| index | count | share |
| --- | --- | --- |
| flag_swapped_asset_number | 0 | 0.0% |
| flag_replicated_inconsistent | 0 | 0.0% |
| flag_unparsed_number | 0 | 0.0% |
| flag_mixed_fin_periods | 1511 | 1.7% |
| flag_rate_unreadable | 0 | 0.0% |
| flag_invalid_code | 0 | 0.0% |
| flag_fin_period_assumed | 0 | 0.0% |
| flag_fin_basis_unknown | 3982 | 4.5% |
| flag_noi_missing | 30205 | 34.1% |
| flag_noi_stale | 1173 | 1.3% |
| flag_dscr_inconsistent | 167 | 0.2% |
| flag_valuation_old | 12485 | 14.1% |
| flag_zero_balance_active | 59 | 0.1% |
| flag_rootless_note | 12 | 0.0% |

