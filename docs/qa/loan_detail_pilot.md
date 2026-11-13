# 10-D loan detail (D033, D040, D049)

Vintage-2016 trusts with no EX-102 still file a monthly 10-D whose statement carries a loan-level table. Two formats are read (`src/mwall/parse/loan_detail.py`): Computershare's Mortgage Loan Detail (40 trusts) and Citibank's (7 Citigroup trusts, two layouts).

- Statements: 3,103 from 47 trusts, 2018-04-12 to 2026-10-19. Loan rows: 136,634; rows that failed validation: 48.
- Parsed loan balances equal the table's own Totals row (or, where none is printed, the statement's pool balance) to the dollar in 3,090 of 3,103 statements.

| format | trusts | statements | with_check | exact | rejected_rows |
| --- | --- | --- | --- | --- | --- |
| citi | 7 | 721 | 721 | 718 | 12 |
| cts | 40 | 2382 | 2382 | 2372 | 36 |

- Prepayment rows with a written code: 998 ({'Payoff Prior to Maturity': 659, 'Partial Liquidation (Curtailment)': 152, 'Disposition': 76, 'Payoff w/ yield maintenance': 57, 'Payoff w/ penalty': 23, 'DPO': 13, 'Curtailment w/ Penalty': 7, 'Curtailment w/ yield maintenance': 6, 'Full Payoff at Maturity': 5}).

## Maturity outcomes

Loans whose original maturity plus 90 days falls inside the statement window: 1,439. Outcomes: {'paid': 1113, 'failed': 248, 'excluded_early_payoff': 55, 'excluded_early_liquidation': 19, 'unknown': 4}. Same rules as the XML gold set: paid needs a payoff code, or a row that pays the whole balance as scheduled principal (a balloon paid on time never appears in Prepayment Detail), no more than 12 months before maturity and no later than 90 days after it; failed means a balance still outstanding after the grace window, an adjusted maturity date later than the original, or a disposition or discounted payoff.

| maturity_year | loans | failed |
| --- | --- | --- |
| 2020 | 2 | 0.00 |
| 2021 | 16 | 7.00 |
| 2022 | 13 | 4.00 |
| 2023 | 9 | 1.00 |
| 2024 | 1 | 1.00 |
| 2025 | 388 | 59.00 |
| 2026 | 932 | 176.00 |

| prop_type | loans | failed | rate |
| --- | --- | --- | --- |
| RT | 410 | 84.00 | 0.20 |
| LO | 210 | 36.00 | 0.17 |
| OF | 206 | 84.00 | 0.41 |
| MF | 192 | 7.00 | 0.04 |
| SS | 102 | 0.00 | 0.00 |
| IN | 69 | 3.00 | 0.04 |
| MH | 50 | 3.00 | 0.06 |
| MU | 47 | 11.00 | 0.23 |
| 98 | 2 | 1.00 | 0.50 |

Not yet read: COMM 2016-DC2 and CFCRE 2016-C4, whose statements are page images converted to positioned text (D049). Pari passu matching to the XML loans is in docs/qa/gate2_gold_set.md.

