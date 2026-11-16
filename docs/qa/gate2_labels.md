# Gate 2 label counts

Generated 2026-11-16 by `python -m mwall panel`. Definitions: `docs/labels.md`. Counts use one representative position per whole loan and month, so pari passu pieces in several trusts count once.

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

- Labeled loan-months with the whole 12-month window inside the data: 729,724; with an event in the next 12 months: 19,442 (2.7%). Tables below use these rows only.
- Labeled months whose window runs past the end of the data: 3,217, of which 1,523 positive (47.3%). A month there gets a label early only if an event has already happened, so these are left out of model training and testing.
- Performing months censored (the loan's observation ends inside the window with no event): 130,860.

| property_group | rows | events | rate |
| --- | --- | --- | --- |
| industrial | 51785 | 780 | 0.015 |
| lodging | 82506 | 6333 | 0.077 |
| mixed_use | 47343 | 1455 | 0.031 |
| multifamily | 152615 | 2668 | 0.017 |
| office | 126308 | 3908 | 0.031 |
| other | 7641 | 214 | 0.028 |
| retail | 197407 | 3821 | 0.019 |
| self_storage | 63318 | 236 | 0.004 |
|  | 801 | 27 | 0.034 |

| vintage | rows | events | rate |
| --- | --- | --- | --- |
| 2016 | 23736 | 845 | 0.036 |
| 2017 | 182579 | 5556 | 0.030 |
| 2018 | 149159 | 4990 | 0.033 |
| 2019 | 153851 | 4418 | 0.029 |
| 2020 | 65225 | 1050 | 0.016 |
| 2021 | 78375 | 947 | 0.012 |
| 2022 | 38904 | 585 | 0.015 |
| 2023 | 15289 | 634 | 0.041 |
| 2024 | 17283 | 324 | 0.019 |
| 2025 | 5323 | 93 | 0.017 |

## Tier 1: maturity outcome (gold set)

- Whole loans whose maturity plus 90 days falls inside the data: 587. Outcomes: {'paid': 258, 'failed': 173, 'excluded_defeased': 91, 'excluded_early_payoff': 32, 'unknown': 30, 'excluded_early_liquidation': 2, 'excluded_removed': 1}.
- **Tier 1 events (failed to pay within 90 days of maturity): 173 of 431 labeled loans (40.1%).** Maturity dates moved later by extension at some point: 34. Maturity taken from an anticipated repayment date: 26.

| property_group | loans | failed | rate |
| --- | --- | --- | --- |
| industrial | 25 | 6 | 0.240 |
| lodging | 77 | 28 | 0.364 |
| mixed_use | 30 | 16 | 0.533 |
| multifamily | 63 | 23 | 0.365 |
| office | 131 | 77 | 0.588 |
| other | 10 | 4 | 0.400 |
| retail | 77 | 18 | 0.234 |
| self_storage | 18 | 1 | 0.056 |

| maturity_year | loans | failed | rate |
| --- | --- | --- | --- |
| 2021 | 18 | 1 | 0.056 |
| 2022 | 108 | 29 | 0.269 |
| 2023 | 76 | 34 | 0.447 |
| 2024 | 124 | 65 | 0.524 |
| 2025 | 58 | 28 | 0.483 |
| 2026 | 47 | 16 | 0.340 |

| vintage | loans | failed | rate |
| --- | --- | --- | --- |
| 2016 | 21 | 4 | 0.190 |
| 2017 | 144 | 48 | 0.333 |
| 2018 | 97 | 42 | 0.433 |
| 2019 | 102 | 55 | 0.539 |
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

