# Gate 1 sign-off: data

Gate 1 passed on 2026-11-12. Every item on the SOP section 15 checklist, plus the section 7 and 8 acceptance criteria, is decided by `python -m mwall qa` from the full data, and the machine verdict is at the top of `gate1_report.md`. Nothing was waived. Where the source itself is wrong, the defect is flagged, kept out of the checks it would distort, and listed below so it reaches the methodology page.

## What is in the data

381 registered CMBS trusts and every ABS-EE filing they made from 2017 through October 2026: 23,970 filings, 2.03 million asset records and 2.72 million property blocks, parsed with zero type failures and zero tags outside the SEC schema. That resolves to 18,058 loans and notes, 16,810 of them in their trust's opening pool. In each trust's latest period the 10-D statements carry $296.5B of collateral.

The pool balance ties to the certificate administrator's 10-D within 0.5% in 20,377 of 22,863 trust-periods. Of the rest, all but 61 (0.3%) trace to a named cause in the source, listed below. Loan counts roll forward from issuance in all 381 trusts: of 224 loans that stop appearing, 2 have no explanation.

## Limitations to publish

The 2016 vintage is mostly missing. 49 of the 55 registered 2016 deals filed no asset-level data, and those deals hold most of the 2026 ten-year maturities (D011, D032). Decision D033 is about recovering them from 10-D statements.

The filings themselves contain defects that the pipeline flags rather than fixes:

- 179 filings carry another deal's loans, either alongside the trust's own or under its loan numbers (Benchmark 2021-B26's October 2023 filing is a 2020 deal's 32 loans). They stay in the tables with `flag_filing_corrupt` and are left out of every check and of the panel.
- 368 filings leave out loans that appear before and after them (5,351 loan-periods), and some trusts stop listing whole blocks for good: BANK 2019-BNK22 has filed 18, 53 or 70 of its loans from month to month since early 2025. The 10-D still carries them.
- 1,048 trust-periods list some loans with blank balances, mostly Wells-filed reports from 2017 to 2020. The gap matches those loans' earlier balances.
- Seven trusts show a fixed dollar gap to the 10-D, identical every month while balances amortize: $895M in the latest period, 0.3% of the pool. Each is listed in `constant_offsets.csv`. Which asset sits behind each gap is not yet identified.
- Four trusts hold non-pooled notes ($35.0M to $72.0M) that the 10-D pool total leaves out. These are explained to the dollar.

Coverage limits in the fields: recent NOI is missing for 29% of loan-periods. In 2017 filings two thirds lack it, because new loans have no operating history yet; from 2020 on it is about a quarter. And 30% of loan-periods carry an appraisal more than five years old, because appraisals are as of securitization. 121 trusts have at least one missing month (179 in all), flagged and never filled.

Pari passu pieces: 1,650 whole loans are split across more than one registered trust, and 82% of pieces find their companions. Summing collateral by trust without grouping would overstate appraised value by 130% and NOI by 167%, so every collateral aggregate counts each whole loan once.

## What Gate 2 inherits

The tier 1 gold set is small, as the SOP expected. 689 loans reached their original maturity date inside the data window, and 207 of them were still outstanding 90 days later. Most are five- and seven-year loans maturing from 2022 to 2026. The ten-year 2017 wave starts in 2027.

Two decisions come before label code. D033 (whether to parse 2016-vintage 10-D loan tables) would add many tier 1 outcomes in exactly the 2026 window. And the panel must decide how to treat loan-periods whose balance the source left blank. The SOP bars imputation in the panel layer, so the default is to keep them flagged and drop them from balance-weighted figures.

Detail behind every number: `gate1_report.md`, `balance_reconciliation.csv`, `loan_exits.csv`, `filing_screen.csv`, `constant_offsets.csv`, `whole_loans.md`, `geography.md`. Decisions D001 to D039 are in `docs/decisions.md`.
