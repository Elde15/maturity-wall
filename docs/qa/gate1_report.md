# Gate 1 data QA report

Generated 2026-11-12 by `python -m mwall qa`. Regenerate after every ingest.

## Gate 1 checklist

| status | item | evidence |
| --- | --- | --- |
| PASS | Trust universe reconciles to the name search and the form index | 381 trusts. Name search: 0 CMBS-named ABS-EE filers left unconfirmed, 5 confirmed by namespace without a CMBS-looking name. Form index vs submissions: ABS-EE 0 in index only, 9 in submissions only (0 of them 2017 or later); 10-D 0 in index only, 70 in submissions only (0 of them 2017 or later). Missing 168-trust list closed in D032. |
| PENDING | Row counts reconcile for every filing; rejects quarantined with reasons | 22,695 of 23,970 ABS-EE filings fetched. Row counts reconcile on 2,132 of 2,132 parsed files. Rejects in `data/quarantine/parse_rejects.csv`: 0. Trusts with no parsed filing: 96. |
| PENDING | Loan vs property records classified; loans per trust equal the issuance count less payoffs | Roll-forward (D028): 251 of 280 trusts within 2.0% unexplained exits. Layout rules and golden tests: `structure.py`, `tests/golden/`. Failing trusts: `loan_count_rollforward.csv`. |
| PASS | Pari passu duplicates measured and handled; effect on aggregates reported | 933 whole loans held by more than one trust; 77.9% of pieces matched. Summing trusts naively would overstate appraised value by 123.6% and NOI by 150.0%. `whole_loans.md`. |
| PENDING | Field coverage report by vintage and depositor family committed | `field_coverage_by_vintage_family.csv`; summary by filing year below. |
| PASS | Code tables verified against the SEC specification | Code meanings parsed from the SEC XSD (`docs/sec_code_tables.md`). Loan-periods with a code outside the XSD enumerations: 0. Tags outside the XSD in the census: 0. |
| PASS | Golden filings and library cross-check (section 7) | Five hand-checked filings across five families in `tests/`; 20-filing cross-check against edgartools in `library_crosscheck.md`. |
| PENDING | Loan balances reconcile to the 10-D within 0.5% (section 8) | 5 trust-periods with a readable statement: 3 within 0.5%, 2 where the EX-102 leaves balances blank, 0 unexplained. Statements not yet read: 0. |
| PASS | One row per loan-period, latest amendment kept, gaps flagged not filled (section 8) | Duplicate loan rows within a filing (corrupt filings aside): 0. Filings superseded by a later version of the same period: 1,597 rows in `filings.parquet` carry `n_versions_for_period` > 1 and only the winner is parsed. Trusts with a missing month between first and last report: 246 (13373 months; `history_gaps.csv`); loan rows after a gap carry `flag_history_gap`. |
| PASS | Recomputed DSCR matches reported for 95% of loans (section 8) | 99.7% of 64,787 loan-periods within 5%. |
| PASS | Every flag counted in a committed report (section 8) | `qa_flags.csv` and the table below. |
| PASS | Geography: ZIP to county and metro with a published crosswalk (section 8) | `geography.md`. |

Gate 1 verdict from the data: **PENDING**. A failing item is fixed or published as a limitation, never waived silently (SOP section 15).

## Ingestion

- Trusts in the universe: 381. With at least one parsed filing: 285.
- ABS-EE filings in the universe: 23,970. Downloaded: 22,690. No EX-102 attached: 5.
- Filings parsed: 2,132. Row counts reconcile (assets and property blocks in the XML equal rows written): 2,132 of 2,132 (100.0%).
- Parse status: {'ok': 2132}. Type failures: 0. Tags outside the SEC schema: 0.
- Trusts without a parsed filing yet: 96 (listed in `loan_count_rollforward.csv` once parsed; until the full download finishes most of these are simply not downloaded yet).

## Record layouts (loan-periods)

| layout | n |
| --- | --- |
| single | 80873 |
| parent_children | 9008 |
| notes | 6601 |
| nested | 3605 |
| replicated | 1414 |
| orphan | 8 |

By filer agent: `layouts_by_agent.csv`.

## Loan counts roll forward

Each trust's first reported period sets the opening loan count (the at-issuance pool). A loan that stops appearing is explained when it carried a liquidation or prepayment code or a zero balance. Tolerance: unexplained exits at most 2.0% of the opening count.

- Trusts checked: 280. Passing: 251. Opening loans: 13,289. Exits: 265, of which explained 2 and unexplained 263.
- Loans that appear mid-history for at most a few periods with no payoff code, left out above as another deal's records filed into the trust (D035): 23 in 3 filings across 3 trusts.

## Pool balance vs the 10-D distribution statement

- Trust-periods compared: 5. Sum of loan scheduled balances within 0.5% of the administrator's ending scheduled collateral balance: 3 (60.0%). Median absolute difference: 0.0%. By category: {'match': 3, 'filing_omits_balances': 2}. `filing_omits_balances` means the EX-102 itself leaves some loans' period balances blank, so the gap is in the source, not the pipeline. Detail: `balance_reconciliation.csv`.

## Filing screen

Each filing is screened before its records are resolved into loans (`clean/screen.py`, D035 and D036).

- Filings screened: 155. Superseded by a later filing for the same XML reporting period although EDGAR gave them different report dates: 1.
- Exact copies of a record dropped: 211 in 3 filings.
- Loans split into notes under one number (largest keeps it, the rest become -S2, -S3): 7 records in 2 filings.
- Filings holding another deal's records, kept but flagged `flag_filing_corrupt` and left out of the checks above and the panel: 3.
- Filings that leave out loans reported both before and after them: 6 (52 loan-periods missing; the loans carry `flag_history_gap` when they return).

Detail: `filing_screen.csv`.

## Ratio checks

- Reported DSCR vs NOI / debt service recomputed from the same filing: 64,787 loan-periods with both; 99.7% agree within 5% (SOP target 95%).

Financial basis of the most recent NOI (decision D021):

| fin_basis | n |
| --- | --- |
| ytd | 34568 |
| full_year | 18340 |
| annualized | 12404 |
| unknown | 4023 |

Estimated trust share of the whole loan by structure code (decision D020). Whole loans should sit near 1.0:

| structure | n | p25 | p50 | p75 |
| --- | --- | --- | --- | --- |
| WL | 47615 | 1.000 | 1.000 | 1.019 |
| PP | 11871 | 0.211 | 0.351 | 0.532 |
| A1 | 2884 | 0.043 | 0.082 | 0.232 |
|  | 983 | 0.527 | 1.000 | 1.018 |
| A2 | 213 | 0.045 | 0.134 | 0.253 |
| B1 | 25 | 0.319 | 0.979 | 1.015 |
| B2 | 6 | 0.180 | 0.248 | 0.252 |
| MZ | 3 | 1.019 | 1.019 | 1.019 |
| C2 | 1 | 0.372 | 0.372 | 0.372 |

Occupancy units as filed (property blocks; decision D023):

| unit | n |
| --- | --- |
| fraction | 146935 |
| null | 68715 |
| percent | 2017 |
| unreadable | 13 |

## Field coverage by filing year (active, non-defeased loan-periods)

| filing_year | n | balance | maturityDate | originationDate | reportPeriodInterestRatePercentage | paymentStatusLoanCode | fin_noi | fin_debt_service | dscr_noi_reported | val_securitization | occupancy_current | prop_type_code | prop_zip | fin_noi_annual | wl_balance_est |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2016 | 372 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 0.66 | 0.69 | 0.66 | 1.00 | 0.46 | 1.00 | 1.00 | 0.65 | 0.92 |
| 2017 | 4294 | 1.00 | 1.00 | 1.00 | 1.00 | 0.94 | 0.31 | 0.36 | 0.31 | 1.00 | 0.36 | 1.00 | 1.00 | 0.31 | 0.84 |
| 2018 | 8934 | 1.00 | 1.00 | 1.00 | 1.00 | 0.93 | 0.35 | 0.38 | 0.34 | 1.00 | 0.42 | 1.00 | 0.99 | 0.29 | 0.84 |
| 2019 | 13752 | 1.00 | 1.00 | 1.00 | 1.00 | 0.93 | 0.52 | 0.54 | 0.51 | 1.00 | 0.58 | 1.00 | 1.00 | 0.46 | 0.88 |
| 2020 | 10744 | 1.00 | 1.00 | 1.00 | 1.00 | 0.95 | 0.62 | 0.62 | 0.61 | 1.00 | 0.64 | 1.00 | 0.99 | 0.58 | 0.89 |
| 2021 | 12614 | 1.00 | 1.00 | 1.00 | 1.00 | 0.96 | 0.76 | 0.77 | 0.75 | 1.00 | 0.79 | 0.99 | 0.96 | 0.75 | 0.94 |
| 2022 | 13543 | 1.00 | 1.00 | 0.99 | 1.00 | 0.95 | 0.82 | 0.82 | 0.80 | 1.00 | 0.83 | 1.00 | 0.98 | 0.78 | 0.95 |
| 2023 | 13985 | 1.00 | 1.00 | 0.99 | 1.00 | 0.94 | 0.88 | 0.88 | 0.85 | 1.00 | 0.83 | 1.00 | 0.97 | 0.83 | 0.96 |
| 2024 | 11697 | 1.00 | 1.00 | 0.99 | 1.00 | 0.94 | 0.90 | 0.90 | 0.87 | 1.00 | 0.86 | 0.97 | 0.96 | 0.86 | 0.97 |
| 2025 | 2083 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 0.96 | 0.96 | 0.96 | 1.00 | 0.96 | 0.96 | 0.96 | 0.96 | 1.00 |
| 2026 | 5792 | 1.00 | 1.00 | 0.98 | 1.00 | 0.94 | 0.82 | 0.82 | 0.79 | 1.00 | 0.79 | 0.94 | 0.94 | 0.79 | 0.95 |

By vintage and deal family: `field_coverage_by_vintage_family.csv`.

## QA flags

| index | count | share |
| --- | --- | --- |
| flag_swapped_asset_number | 0 | 0.0% |
| flag_replicated_inconsistent | 0 | 0.0% |
| flag_unparsed_number | 0 | 0.0% |
| flag_mixed_fin_periods | 1511 | 1.5% |
| flag_rate_unreadable | 0 | 0.0% |
| flag_invalid_code | 0 | 0.0% |
| flag_fin_period_assumed | 0 | 0.0% |
| flag_fin_basis_unknown | 4023 | 4.0% |
| flag_noi_missing | 32174 | 31.7% |
| flag_noi_stale | 1341 | 1.3% |
| flag_dscr_inconsistent | 167 | 0.2% |
| flag_valuation_old | 16348 | 16.1% |
| flag_zero_balance_active | 59 | 0.1% |
| flag_rootless_note | 12 | 0.0% |
| flag_transient_loan | 23 | 0.0% |
| flag_filing_corrupt | 210 | 0.2% |
| flag_history_gap | 2735 | 2.7% |

