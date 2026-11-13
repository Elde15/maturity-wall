# Gate 2 label counts

Generated 2026-11-12 by `python -m mwall panel`. Definitions: `docs/labels.md`. Counts use one representative position per whole loan and month, so pari passu pieces in several trusts count once.

## Panel

- Loan-months: 1,102,379 across 16,835 loan positions and 14,502 whole loans; representative rows 970,517.
- Defeased loan-months (excluded from tiers 1 and 2): 39,426. Loan-months with a blank balance in the source: 7,284.

Distress events by type (representative rows; one month can carry several):

| event | loan_months |
| --- | --- |
| ev_dq60 | 15007 |
| ev_matured_np | 1509 |
| ev_ss_transfer | 1504 |
| ev_modification | 2251 |
| ev_liquidation | 5204 |

## Tier 2: distress within 12 months of a performing month

- Labeled loan-months: 679,660; with an event in the next 12 months: 34,933 (5.1%). Performing months censored (observation ends inside the window): 119,617.

| property_group | rows | events | rate |
| --- | --- | --- | --- |
| industrial | 47456 | 797.000 | 0.017 |
| lodging | 77510 | 6167.000 | 0.080 |
| mixed_use | 44172 | 1534.000 | 0.035 |
| multifamily | 142519 | 18257.000 | 0.128 |
| office | 115992 | 3874.000 | 0.033 |
| other | 7030 | 225.000 | 0.032 |
| retail | 186108 | 3794.000 | 0.020 |
| self_storage | 58327 | 266.000 | 0.005 |
|  | 546 | 19.000 | 0.035 |

| vintage | rows | events | rate |
| --- | --- | --- | --- |
| 2016.000 | 24261 | 957.000 | 0.039 |
| 2017.000 | 179169 | 10233.000 | 0.057 |
| 2018.000 | 136063 | 8628.000 | 0.063 |
| 2019.000 | 143486 | 8004.000 | 0.056 |
| 2020.000 | 65329 | 2467.000 | 0.038 |
| 2021.000 | 65177 | 2822.000 | 0.043 |
| 2022.000 | 31655 | 549.000 | 0.017 |
| 2023.000 | 13175 | 597.000 | 0.045 |
| 2024.000 | 16131 | 434.000 | 0.027 |
| 2025.000 | 5205 | 233.000 | 0.045 |
| 2026.000 | 9 | 9.000 | 1.000 |

## Tier 1: maturity outcome (gold set)

- Whole loans whose maturity plus 90 days falls inside the data: 587. Outcomes: {'paid': 258, 'failed': 164, 'excluded_defeased': 91, 'unknown': 39, 'excluded_early_payoff': 32, 'excluded_early_liquidation': 2, 'excluded_removed': 1}.
- **Tier 1 events (failed to pay within 90 days of maturity): 164 of 422 labeled loans (38.9%).** Maturity dates moved later by extension at some point: 34. Maturity taken from an anticipated repayment date: 26.

| property_group | loans | failed | rate |
| --- | --- | --- | --- |
| industrial | 20 | 1.000 | 0.050 |
| lodging | 75 | 26.000 | 0.347 |
| mixed_use | 30 | 16.000 | 0.533 |
| multifamily | 62 | 22.000 | 0.355 |
| office | 130 | 76.000 | 0.585 |
| other | 10 | 4.000 | 0.400 |
| retail | 77 | 18.000 | 0.234 |
| self_storage | 18 | 1.000 | 0.056 |

| maturity_year | loans | failed | rate |
| --- | --- | --- | --- |
| 2021 | 18 | 1.000 | 0.056 |
| 2022 | 106 | 27.000 | 0.255 |
| 2023 | 76 | 34.000 | 0.447 |
| 2024 | 117 | 58.000 | 0.496 |
| 2025 | 58 | 28.000 | 0.483 |
| 2026 | 47 | 16.000 | 0.340 |

## Tier 3: loss severity

- Liquidated loan positions: 220; with a realized loss reported: 151. Median severity where reported: 0.43.

