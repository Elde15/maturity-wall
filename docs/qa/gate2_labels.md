# Gate 2 label counts

Generated 2026-11-13 by `python -m mwall panel`. Definitions: `docs/labels.md`. Counts use one representative position per whole loan and month, so pari passu pieces in several trusts count once.

## Panel

- Loan-months: 1,102,379 across 16,835 loan positions and 14,502 whole loans; representative rows 970,517.
- Defeased loan-months (excluded from tiers 1 and 2): 39,426. Loan-months with a blank balance in the source: 7,284.

Distress events by type (representative rows; one month can carry several):

| event | loan_months |
| --- | --- |
| ev_dq60 | 15007 |
| ev_matured_np | 1509 |
| ev_ss_transfer | 1504 |
| ev_modification | 872 |
| ev_liquidation | 5204 |

## Tier 2: distress within 12 months of a performing month

- Labeled loan-months with the whole 12-month window inside the data: 676,532; with an event in the next 12 months: 18,067 (2.7%). Tables below use these rows only.
- Labeled months whose window runs past the end of the data: 3,128, of which 1,434 positive (45.8%). A month there gets a label early only if an event has already happened, so these are left out of model training and testing.
- Performing months censored (the loan's observation ends inside the window with no event): 119,617.

| property_group | rows | events | rate |
| --- | --- | --- | --- |
| industrial | 47190 | 699 | 0.015 |
| lodging | 77116 | 5948 | 0.077 |
| mixed_use | 43934 | 1387 | 0.032 |
| multifamily | 141926 | 2495 | 0.018 |
| office | 115362 | 3492 | 0.030 |
| other | 6971 | 177 | 0.025 |
| retail | 185225 | 3616 | 0.020 |
| self_storage | 58265 | 235 | 0.004 |
|  | 543 | 18 | 0.033 |

| vintage | rows | events | rate |
| --- | --- | --- | --- |
| 2016 | 23678 | 842 | 0.036 |
| 2017 | 178444 | 5373 | 0.030 |
| 2018 | 135718 | 4471 | 0.033 |
| 2019 | 143140 | 4073 | 0.028 |
| 2020 | 65198 | 1049 | 0.016 |
| 2021 | 64820 | 851 | 0.013 |
| 2022 | 31467 | 478 | 0.015 |
| 2023 | 13024 | 548 | 0.042 |
| 2024 | 15978 | 289 | 0.018 |
| 2025 | 5065 | 93 | 0.018 |

## Tier 1: maturity outcome (gold set)

- Whole loans whose maturity plus 90 days falls inside the data: 587. Outcomes: {'paid': 258, 'failed': 164, 'excluded_defeased': 91, 'unknown': 39, 'excluded_early_payoff': 32, 'excluded_early_liquidation': 2, 'excluded_removed': 1}.
- **Tier 1 events (failed to pay within 90 days of maturity): 164 of 422 labeled loans (38.9%).** Maturity dates moved later by extension at some point: 34. Maturity taken from an anticipated repayment date: 26.

| property_group | loans | failed | rate |
| --- | --- | --- | --- |
| industrial | 20 | 1 | 0.050 |
| lodging | 75 | 26 | 0.347 |
| mixed_use | 30 | 16 | 0.533 |
| multifamily | 62 | 22 | 0.355 |
| office | 130 | 76 | 0.585 |
| other | 10 | 4 | 0.400 |
| retail | 77 | 18 | 0.234 |
| self_storage | 18 | 1 | 0.056 |

| maturity_year | loans | failed | rate |
| --- | --- | --- | --- |
| 2021 | 18 | 1 | 0.056 |
| 2022 | 106 | 27 | 0.255 |
| 2023 | 76 | 34 | 0.447 |
| 2024 | 117 | 58 | 0.496 |
| 2025 | 58 | 28 | 0.483 |
| 2026 | 47 | 16 | 0.340 |

| vintage | loans | failed | rate |
| --- | --- | --- | --- |
| 2016 | 21 | 4 | 0.190 |
| 2017 | 138 | 42 | 0.304 |
| 2018 | 96 | 41 | 0.427 |
| 2019 | 100 | 53 | 0.530 |
| 2020 | 41 | 15 | 0.366 |
| 2021 | 26 | 9 | 0.346 |

## Tier 3: loss severity

- Liquidated loan positions: 220; with a realized loss reported: 151. Median severity where reported: 0.43.

| property_group | liquidated | loss_reported | median_severity |
| --- | --- | --- | --- |
| industrial | 10 | 7 | 0.134 |
| lodging | 56 | 45 | 0.326 |
| mixed_use | 20 | 13 | 0.376 |
| multifamily | 24 | 15 | 0.425 |
| office | 58 | 42 | 0.653 |
| other | 1 | 0 |  |
| retail | 48 | 29 | 0.550 |
| self_storage | 3 | 0 |  |

| vintage | liquidated | loss_reported | median_severity |
| --- | --- | --- | --- |
| 2016 | 12 | 6 | 0.518 |
| 2017 | 92 | 65 | 0.425 |
| 2018 | 64 | 37 | 0.287 |
| 2019 | 31 | 24 | 0.445 |
| 2020 | 10 | 10 | 0.865 |
| 2021 | 8 | 6 | 0.302 |
| 2022 | 1 | 1 | 0.999 |
| 2023 | 1 | 1 | 0.230 |
| 2024 | 1 | 1 | 0.218 |

