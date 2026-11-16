# Tier 1 gold set: EX-102 and 10-D loan detail combined

Generated 2026-11-16 by `python -m mwall panel`. One row per whole loan (`panel/tier1_gold.parquet`). Rules: docs/labels.md; sources D040, D041, D046.

- **Labeled whole loans: 1,631; failed to pay within 90 days of maturity: 357 (21.9%).**

- 10-D loan detail: 1,439 loan positions in the window are 1,278 whole loans after pari passu matching (100 loans held in two or more of the vintage-2016 trusts). Pieces of one loan with different outcomes: 1.
- Whole loans found in both sources: 7; they keep the EX-102 label. Where both sources label the loan paid or failed, the labels agree in 8 of 8.

| outcome_10d | excluded_defeased | failed | paid |
| --- | --- | --- | --- |
| failed | 0 | 4 | 0 |
| paid | 1 | 0 | 4 |

## By source

| source | loans | failed | rate |
| --- | --- | --- | --- |
| 10-D loan detail | 1200 | 184 | 0.153 |
| EX-102 | 431 | 173 | 0.401 |

## By property type

| property_group | loans 10-D loan detail | loans EX-102 | failed 10-D loan detail | failed EX-102 | failure rate, both |
| --- | --- | --- | --- | --- | --- |
| industrial | 62 | 25 | 2 | 6 | 0.092 |
| lodging | 185 | 77 | 32 | 28 | 0.229 |
| mixed_use | 43 | 30 | 10 | 16 | 0.356 |
| multifamily | 235 | 63 | 10 | 23 | 0.111 |
| office | 164 | 131 | 57 | 77 | 0.454 |
| other | 51 | 10 | 15 | 4 | 0.311 |
| retail | 361 | 77 | 58 | 18 | 0.174 |
| self_storage | 99 | 18 | 0 | 1 | 0.009 |

## By maturity year

| maturity_year | loans 10-D loan detail | loans EX-102 | failed 10-D loan detail | failed EX-102 |
| --- | --- | --- | --- | --- |
| 2020 | 2 | 0 | 0 | 0 |
| 2021 | 13 | 18 | 5 | 1 |
| 2022 | 9 | 108 | 4 | 29 |
| 2023 | 9 | 76 | 1 | 34 |
| 2024 | 1 | 124 | 1 | 65 |
| 2025 | 364 | 58 | 46 | 28 |
| 2026 | 802 | 47 | 127 | 16 |
