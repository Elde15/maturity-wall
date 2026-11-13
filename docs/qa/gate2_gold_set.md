# Tier 1 gold set: EX-102 and 10-D loan detail combined

Generated 2026-11-13 by `python -m mwall panel`. One row per whole loan (`panel/tier1_gold.parquet`). Rules: docs/labels.md; sources D040, D041, D046.

- **Labeled whole loans: 1,421; failed to pay within 90 days of maturity: 315 (22.2%).**

- 10-D loan detail: 1,196 loan positions in the window are 1,075 whole loans after pari passu matching (77 loans held in two or more of the vintage-2016 trusts). Pieces of one loan with different outcomes: 1.
- Whole loans found in both sources: 7; they keep the EX-102 label. Where both sources label the loan paid or failed, the labels agree in 8 of 8.

| outcome_10d | excluded_defeased | failed | paid |
| --- | --- | --- | --- |
| failed | 0 | 4 | 0 |
| paid | 1 | 0 | 4 |

## By source

| source | loans | failed | rate |
| --- | --- | --- | --- |
| 10-D loan detail | 999 | 151 | 0.151 |
| EX-102 | 422 | 164 | 0.389 |

## By property type

| property_group | loans 10-D loan detail | loans EX-102 | failed 10-D loan detail | failed EX-102 | failure rate, both |
| --- | --- | --- | --- | --- | --- |
| industrial | 56 | 20 | 2 | 1 | 0.039 |
| lodging | 160 | 75 | 27 | 26 | 0.226 |
| mixed_use | 38 | 30 | 8 | 16 | 0.353 |
| multifamily | 204 | 62 | 8 | 22 | 0.113 |
| office | 143 | 130 | 48 | 76 | 0.454 |
| other | 31 | 10 | 10 | 4 | 0.341 |
| retail | 289 | 77 | 48 | 18 | 0.180 |
| self_storage | 78 | 18 | 0 | 1 | 0.010 |

## By maturity year

| maturity_year | loans 10-D loan detail | loans EX-102 | failed 10-D loan detail | failed EX-102 |
| --- | --- | --- | --- | --- |
| 2021 | 1 | 18 | 1 | 1 |
| 2022 | 9 | 106 | 4 | 27 |
| 2023 | 9 | 76 | 1 | 34 |
| 2024 | 1 | 117 | 1 | 58 |
| 2025 | 338 | 58 | 45 | 28 |
| 2026 | 641 | 47 | 99 | 16 |
