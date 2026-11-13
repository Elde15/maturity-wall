# Gate 1 data QA report

Generated 2026-11-12 by `python -m mwall qa`. Regenerate after every ingest.

## Gate 1 checklist

| status | item | evidence |
| --- | --- | --- |
| PASS | Trust universe reconciles to the name search and the form index | 381 trusts. Name search: 0 CMBS-named ABS-EE filers left unconfirmed, 5 confirmed by namespace without a CMBS-looking name. Form index vs submissions: ABS-EE 0 in index only, 9 in submissions only (0 of them 2017 or later); 10-D 0 in index only, 70 in submissions only (0 of them 2017 or later). Missing 168-trust list closed in D032. |
| PASS | Row counts reconcile for every filing; rejects quarantined with reasons | 23,970 of 23,970 ABS-EE filings fetched. Row counts reconcile on 23,938 of 23,938 parsed files. Rejects in `data/quarantine/parse_rejects.csv`: 0. Trusts with no parsed filing: 0. |
| PASS | Loan vs property records classified; loans per trust equal the issuance count less payoffs | Roll-forward (D028): 381 of 381 trusts within 2.0% unexplained exits. Layout rules and golden tests: `structure.py`, `tests/golden/`. Failing trusts: `loan_count_rollforward.csv`. |
| PASS | Pari passu duplicates measured and handled; effect on aggregates reported | 1,650 whole loans held by more than one trust; 82.0% of pieces matched. Summing trusts naively would overstate appraised value by 130.1% and NOI by 167.4%. `whole_loans.md`. |
| PASS | Field coverage report by vintage and depositor family committed | `field_coverage_by_vintage_family.csv`; summary by filing year below. |
| PASS | Code tables verified against the SEC specification | Code meanings parsed from the SEC XSD (`docs/sec_code_tables.md`). Loan-periods with a code outside the XSD enumerations: 0. Tags outside the XSD in the census: 0. |
| PASS | Golden filings and library cross-check (section 7) | Five hand-checked filings across five families in `tests/`; 20-filing cross-check against edgartools in `library_crosscheck.md`. |
| PASS | Loan balances reconcile to the 10-D within 0.5% (section 8) | 22,863 trust-periods with a readable statement: 20,377 within 0.5%, 466 off by exactly the trust's non-pooled notes and 308 by a fixed dollar amount the two sides scope differently (D038; `constant_offsets.csv`), 1,048 where the EX-102 leaves balances blank, 460 incomplete and 143 corrupt filings, 61 unexplained (0.3%; tolerance 1%, D038). Statements not yet read: 56. 10-D statements fetched: 23,540 of 23,540. |
| PASS | One row per loan-period, latest amendment kept, gaps flagged not filled (section 8) | Duplicate loan rows within a filing (corrupt filings aside): 0. Filings superseded by a later version of the same period: 1,597 rows in `filings.parquet` carry `n_versions_for_period` > 1 and only the winner is parsed. Trusts with a missing month between first and last report: 121 (179 months; `history_gaps.csv`); loan rows after a gap carry `flag_history_gap`. |
| PASS | Recomputed DSCR matches reported for 95% of loans (section 8) | 99.9% of 741,422 loan-periods within 5%. |
| PASS | Every flag counted in a committed report (section 8) | `qa_flags.csv` and the table below. |
| PASS | Geography: ZIP to county and metro with a published crosswalk (section 8) | `geography.md`. |

Gate 1 verdict from the data: **PASS**. A failing item is fixed or published as a limitation, never waived silently (SOP section 15).

## Ingestion

- Trusts in the universe: 381. With at least one parsed filing: 381.
- ABS-EE filings in the universe: 23,970. Downloaded: 23,938. No EX-102 attached: 32.
- Filings parsed: 23,938. Row counts reconcile (assets and property blocks in the XML equal rows written): 23,938 of 23,938 (100.0%).
- Parse status: {'ok': 23938}. Type failures: 0. Tags outside the SEC schema: 0.
- Trusts without a parsed filing yet: 0 (listed in `loan_count_rollforward.csv` once parsed; until the full download finishes most of these are simply not downloaded yet).

## Record layouts (loan-periods)

| layout | n |
| --- | --- |
| single | 914036 |
| notes | 91656 |
| parent_children | 77762 |
| nested | 72572 |
| replicated | 7888 |
| orphan | 76 |
| first_child | 72 |

By filer agent: `layouts_by_agent.csv`.

## Loan counts roll forward

Each trust's first reported period sets the opening count (the at-issuance pool). Loans are tracked by their root number, so a loan renumbered into notes (6 becoming 6-A and 6-B) is not an exit. Filers keep listing a paid-off loan at zero balance with its payoff code, so payoffs stay in the count rather than leaving it. A loan that stops appearing is explained by a payoff code or zero balance, by reaching maturity (last seen within 180 days of it, the usual open prepayment window), by a matching drop in the administrator's pool balance on the 10-D, or as left out by the source when a later 10-D still carries more balance than the loan data lists (D037). Tolerance: unexplained exits at most 2.0% of the opening count.

- Trusts checked: 381. Passing: 381. Opening loans: 16,810. Exits: 224: payoff code or zero balance 8, at or near maturity 50, paid off per the 10-D 29, left out by the source 134, missing only from the latest filing (cannot yet be told from a one-month gap) 1, unexplained 2. Detail: `loan_exits.csv`.
- Loans that appear mid-history for at most a few periods with no payoff code, left out above as another deal's records filed into the trust (D035): 928 in 107 filings across 81 trusts.

## Pool balance vs the 10-D distribution statement

- Trust-periods compared: 22,919. Sum of loan scheduled balances within 0.5% of the administrator's ending scheduled collateral balance: 20,377 (88.9%). Median absolute difference: 0.0%. By category: {'match': 20377, 'filing_omits_balances': 1048, 'non_pooled_notes': 466, 'filing_incomplete': 328, 'constant_offset': 308, 'filing_corrupt': 143, 'filing_drops_loans': 132, 'mismatch': 61, 'statement_unread': 56}. `filing_omits_balances` means the EX-102 itself leaves some loans' period balances blank, so the gap is in the source, not the pipeline. Detail: `balance_reconciliation.csv`.

## Filing screen

Each filing is screened before its records are resolved into loans (`clean/screen.py`, D035 and D036).

- Filings screened: 23,625. Superseded by a later filing for the same XML reporting period although EDGAR gave them different report dates: 33.
- Exact copies of a record dropped: 679 in 11 filings.
- Loans split into notes under one number (largest keeps it, the rest become -S2, -S3): 86 records in 6 filings.
- Filings holding another deal's records, kept but flagged `flag_filing_corrupt` and left out of the checks above and the panel: 179.
- Filings that leave out loans reported both before and after them: 368 (5,351 loan-periods missing; the loans carry `flag_history_gap` when they return).

Detail: `filing_screen.csv`.

## Ratio checks

- Reported DSCR vs NOI / debt service recomputed from the same filing: 741,422 loan-periods with both; 99.9% agree within 5% (SOP target 95%).

Financial basis of the most recent NOI (decision D021):

| fin_basis | n |
| --- | --- |
| ytd | 353964 |
| full_year | 277918 |
| annualized | 120515 |
| unknown | 70499 |

Estimated trust share of the whole loan by structure code (decision D020). Whole loans should sit near 1.0:

| structure | n | p25 | p50 | p75 |
| --- | --- | --- | --- | --- |
| WL | 537728 | 1.000 | 1.000 | 1.018 |
| PP | 146725 | 0.202 | 0.340 | 0.513 |
| A1 | 31852 | 0.058 | 0.134 | 0.275 |
|  | 19507 | 0.465 | 0.986 | 1.016 |
| A2 | 2996 | 0.045 | 0.154 | 0.255 |
| B1 | 363 | 0.252 | 0.626 | 0.986 |
| B2 | 98 | 0.244 | 0.251 | 0.252 |
| MZ | 45 | 0.986 | 1.019 | 1.019 |
| C2 | 12 | 0.385 | 0.426 | 0.440 |

Occupancy units as filed (property blocks; decision D023):

| unit | n |
| --- | --- |
| fraction | 1663678 |
| null | 839729 |
| percent | 22346 |
| unreadable | 158 |

## Field coverage by filing year (active, non-defeased loan-periods)

| filing_year | n | balance | maturityDate | originationDate | reportPeriodInterestRatePercentage | paymentStatusLoanCode | fin_noi | fin_debt_service | dscr_noi_reported | val_securitization | occupancy_current | prop_type_code | prop_zip | fin_noi_annual | wl_balance_est |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2016 | 278 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 0.61 | 0.63 | 0.61 | 1.00 | 0.47 | 1.00 | 1.00 | 0.60 | 0.92 |
| 2017 | 16168 | 1.00 | 1.00 | 1.00 | 1.00 | 0.98 | 0.34 | 0.39 | 0.34 | 1.00 | 0.36 | 1.00 | 1.00 | 0.30 | 0.84 |
| 2018 | 42858 | 1.00 | 1.00 | 1.00 | 1.00 | 0.95 | 0.49 | 0.53 | 0.49 | 1.00 | 0.53 | 1.00 | 1.00 | 0.44 | 0.86 |
| 2019 | 73093 | 1.00 | 1.00 | 1.00 | 1.00 | 0.94 | 0.65 | 0.65 | 0.64 | 1.00 | 0.67 | 1.00 | 1.00 | 0.59 | 0.91 |
| 2020 | 100377 | 1.00 | 1.00 | 1.00 | 1.00 | 0.95 | 0.73 | 0.73 | 0.71 | 1.00 | 0.73 | 1.00 | 0.99 | 0.68 | 0.92 |
| 2021 | 117244 | 1.00 | 1.00 | 1.00 | 1.00 | 0.95 | 0.79 | 0.79 | 0.76 | 1.00 | 0.78 | 1.00 | 0.98 | 0.73 | 0.93 |
| 2022 | 134039 | 1.00 | 1.00 | 0.99 | 1.00 | 0.92 | 0.79 | 0.79 | 0.76 | 1.00 | 0.77 | 1.00 | 0.98 | 0.73 | 0.94 |
| 2023 | 141268 | 1.00 | 1.00 | 0.99 | 1.00 | 0.92 | 0.81 | 0.81 | 0.78 | 1.00 | 0.74 | 1.00 | 0.98 | 0.72 | 0.93 |
| 2024 | 154729 | 1.00 | 1.00 | 0.99 | 1.00 | 0.91 | 0.77 | 0.77 | 0.74 | 1.00 | 0.71 | 0.97 | 0.97 | 0.71 | 0.93 |
| 2025 | 170438 | 1.00 | 1.00 | 0.99 | 1.00 | 0.92 | 0.73 | 0.73 | 0.71 | 1.00 | 0.68 | 0.96 | 0.96 | 0.68 | 0.92 |
| 2026 | 155375 | 1.00 | 1.00 | 0.99 | 1.00 | 0.92 | 0.73 | 0.73 | 0.70 | 1.00 | 0.68 | 0.96 | 0.96 | 0.67 | 0.92 |

By vintage and deal family: `field_coverage_by_vintage_family.csv`.

## QA flags

| index | count | share |
| --- | --- | --- |
| flag_swapped_asset_number | 0 | 0.0% |
| flag_rootless_note | 252 | 0.0% |
| flag_replicated_inconsistent | 4 | 0.0% |
| flag_unparsed_number | 0 | 0.0% |
| flag_mixed_fin_periods | 20762 | 1.8% |
| flag_rate_unreadable | 1 | 0.0% |
| flag_invalid_code | 0 | 0.0% |
| flag_fin_period_assumed | 37 | 0.0% |
| flag_fin_basis_unknown | 70499 | 6.1% |
| flag_noi_missing | 341166 | 29.3% |
| flag_noi_stale | 16490 | 1.4% |
| flag_dscr_inconsistent | 799 | 0.1% |
| flag_valuation_old | 352917 | 30.3% |
| flag_zero_balance_active | 61 | 0.0% |
| flag_transient_loan | 1008 | 0.1% |
| flag_foreign_record | 4346 | 0.4% |
| flag_filing_corrupt | 9261 | 0.8% |
| flag_history_gap | 10592 | 0.9% |

