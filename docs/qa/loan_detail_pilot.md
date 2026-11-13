# 10-D loan detail pilot (D033, D040)

Vintage-2016 trusts with no EX-102 still file a monthly 10-D whose statement carries a Mortgage Loan Detail table. The pilot reads the Computershare format (`src/mwall/parse/loan_detail.py`).

- Statements: 2,382 from 40 trusts, 2021-10-13 to 2026-10-19. Loan rows: 104,864; rows that failed validation: 36.
- Parsed loan balances equal the table's own Totals row to the dollar in 2,372 of 2,379 statements.
- Prepayment rows with a written code: 998 ({'Payoff Prior to Maturity': 659, 'Partial Liquidation (Curtailment)': 152, 'Disposition': 76, 'Payoff w/ yield maintenance': 57, 'Payoff w/ penalty': 23, 'DPO': 13, 'Curtailment w/ Penalty': 7, 'Curtailment w/ yield maintenance': 6, 'Full Payoff at Maturity': 5}).

## Maturity outcomes

Loans whose original maturity plus 90 days falls inside the statement window: 1,196. Outcomes: {'paid': 916, 'failed': 203, 'excluded_early_payoff': 44, 'excluded_early_liquidation': 28, 'unknown': 5}. Same rules as the XML gold set: paid needs a payoff code, or a row that pays the whole balance as scheduled principal (a balloon paid on time never appears in Prepayment Detail), no more than 12 months before maturity and no later than 90 days after it; failed means a balance still outstanding after the grace window, an adjusted maturity date later than the original, or a disposition or discounted payoff.

| maturity_year | loans | failed |
| --- | --- | --- |
| 2021 | 3 | 2.00 |
| 2022 | 13 | 4.00 |
| 2023 | 9 | 1.00 |
| 2024 | 1 | 1.00 |
| 2025 | 361 | 58.00 |
| 2026 | 732 | 137.00 |

| prop_type | loans | failed | rate |
| --- | --- | --- | --- |
| RT | 329 | 71.00 | 0.22 |
| OF | 175 | 67.00 | 0.38 |
| LO | 173 | 30.00 | 0.17 |
| MF | 168 | 7.00 | 0.04 |
| SS | 81 | 0.00 | 0.00 |
| IN | 58 | 3.00 | 0.05 |
| MH | 43 | 1.00 | 0.02 |
| MU | 40 | 9.00 | 0.23 |
| 98 | 2 | 1.00 | 0.50 |

Not yet done: the 9 trusts filed through other administrators, matching these loans to pari passu pieces in the XML trusts, and features from these tables for the maturity-window model.

