# Model card

Two models score US commercial mortgages held in registered CMBS trusts. Both are screening aids: they rank loans for a closer look. They are not valuations, credit decisions or investment advice, and nothing here says what any loan, note or property is worth to a particular buyer.

Built on data through the November 12, 2026 reports. Design and evidence: `docs/qa/gate3_models.md`; decisions D051 to D055 in `docs/decisions.md`.

## What each model predicts

**12-month distress probability.** For a loan that is performing today (current or under 30 days late, not in special servicing, not past maturity), the chance that within 12 months it goes 60 or more days delinquent, transfers to special servicing, is modified, fails to pay at maturity, or is liquidated. The model is a logistic regression on 63 loan, property, servicing and market inputs plus property type and payment status, with the signs of the credit inputs held to credit logic (D054): more debt yield, DSCR or occupancy can't raise risk, and more leverage or a higher refinance rate can't lower it.

**Failure-to-refinance probability.** For a loan 2.5 to 24 months from maturity, the chance it is not paid in full within 90 days after maturity. A logistic regression on 18 inputs (refinance gap, debt yield, DSCR, LTV, occupancy, NOI against securitization, rate shock, months to maturity, balloon share, structure and servicing status) plus property type, with the same sign rule. Loans further from maturity get the distress probability and the refinance gap, not this number.

The SOP planned a third, combined number (the two models averaged). It did worse than the maturity model on ranking, so it isn't published (D052).

## Training data

Loan-level EX-102 filings of 381 registered CMBS trusts, monthly from 2017. One row per whole loan per month (pari passu pieces counted once), with features dated to the filing date so nothing published later leaks in (leakage audit: `docs/qa/gate2_leakage.md`).

- Distress model: 591,034 performing loan-months through September 28, 2024 (15,987 with a distress event in the next 12 months), calibrated on the 122,516 months of the following year (2,999 events).
- Maturity model: 431 whole loans that reached maturity inside the data, 173 of which failed. Most matured in 2022 to 2026 and were five- or seven-year loans.

The 1,200 labeled maturities of the vintage-2016 deals (read from 10-D statements) have no feature rows, so they aren't used to fit or score.

## How it was tested

Out of time and out of loan. For a test year starting on date D, models were fit only on months whose outcome was public by D, tuned and calibrated on the 12 months before that, and scored on the test year. Whole loans were split into five groups, and each group's test months were scored by models that never saw that loan. Four test years for the distress model (2022 to 2025), three for the maturity model (loans maturing in 2024, 2025 and 2026). Baselines: the base rate, debt yield under 7% to 10% (and debt yield as a continuous rank), DSCR under 1.00 to 1.25, and a positive refinance gap.

## Results

Distress model, out of time and out of loan:

| test year | event rate | PR-AUC | best rule's PR-AUC | Brier | best rule's Brier | events caught in the riskiest 10% | calibration slope |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 2022 | 1.34% | 0.027 | 0.015 | 0.0133 | 0.0152 | 23% | 0.46 |
| 2023 | 2.28% | 0.045 | 0.038 | 0.0221 | 0.0224 | 23% | 1.16 |
| 2024 | 2.72% | 0.063 | 0.041 | 0.0262 | 0.0266 | 23% | 0.75 |
| 2025 | 2.46% | 0.081 | 0.043 | 0.0235 | 0.0239 | 28% | 0.51 |

It beats every baseline on both measures in every year, and the debt-yield rule in every property type, vintage band, structure and NOI cut. Weighted by balance, the riskiest 10% of loan-months held 37% of the 2025 distress balance.

Maturity model, 12 months before maturity:

| maturity year | loans | failed | PR-AUC | best rule's PR-AUC | Brier | base rate's Brier | calibration slope |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 2024 | 124 | 65 | 0.61 | 0.55 | 0.343 | 0.326 | 0.26 |
| 2025 | 58 | 28 | 0.72 | 0.55 | 0.249 | 0.289 | 0.68 |
| 2026 | 47 | 16 | 0.75 | 0.63 | 0.204 | 0.228 | 0.62 |

It ranks better than every rule each year and gets closer six and three months out (pooled PR-AUC 0.66 at six months). In 2024 it lost to the base rate on Brier; that year's model was fit on 89 loans.

## Known failure modes

**Probability levels drift between years.** The calibration slope was inside the SOP's 0.8 to 1.2 band only in 2023. In 2022 the distress model forecast 0.2% on average against a realized 1.3%, because it had been calibrated on the COVID year. The ranking held up every year; the level didn't. Read the distress probability as relative risk, use the rank within property type, and keep the interval in view.

**The distress model carries almost no rate channel.** In the training years distress came mostly from 2020, when rates fell, so the data pointed the wrong way on rates and the sign rule holds those inputs near zero. A 100 bp higher refinance rate raises the average distress probability by under half a percent. Rate risk lives in the refinance gap and the maturity model (rate shock coefficient positive; a 100 bp rise lifts its forecast for 99% of loans).

**A national series is the distress model's largest input.** The 12-month change in the 10-year Treasury ranks first in three of four test years. It is the same for every loan on a date, so it moves every probability together; the site lists it as a market condition and leaves it out of each loan's drivers.

**The maturity model rests on 431 loans.** Its intervals average 26 percentage points wide. With so few loans, property type does much of the work: office loans failed 57% of the time in the sample, self-storage 6%. The sample can't separate leverage from property type, so the sign rule holds the leverage weights at zero: a 10% larger balance leaves its forecast unchanged, while higher NOI lowers it and a higher refinance rate raises it.

**The refinance gap explained little of who failed at maturity.** Loans with a positive gap 12 months out failed 44% of the time against 42% without one, and office failed at 57 to 58% either way. The structural rule (B3) ranked maturity failures no better than chance. Gaps are computed only where NOI and a cap-rate benchmark exist, which leaves out 43% of loans 12 months before maturity (most lodging after 2021, all mixed use and self-storage).

**Current NOI adds little to the distress model.** Removing every NOI-based input changes PR-AUC by 0.003 or less. Reported NOI is often a year old. Servicing history and market inputs carry more.

**Blank payment status is inferred.** 28 trusts leave the status code blank; it is read from the paid-through date (D055). 580 loans in the latest month have no usable status and aren't scored.

**Coverage is not the market.** Registered conduit and single-borrower CMBS from 2017 is a slice of commercial real estate debt; most 2016 deals filed no loan-level data. Delinquency in this data tracks Trepp's published rate closely over time (correlation 0.97 across 94 months) but runs lower, because Trepp's universe includes older deals.

## Segments with too few events

No property type has fewer than 30 distress events in the test years (self-storage, the smallest, has 161). For maturity failure every type is thin: industrial 21 loans, self-storage 18, mixed use 27 and other 7. Those types share one pooled model with a type indicator, as the SOP requires, and their probabilities should be read as type averages with wide intervals.

## Uncertainty

Each published probability has a 90% interval from a bootstrap by whole loan (20 refits of the distress model, 200 of the maturity model), shown on every tear sheet.

## Intended use and limits

Use: screening and research on registered CMBS loans, comparing loans within a property type, and seeing which inputs drive a score. Don't use: pricing a note or property, lending decisions, anything presented as a recommendation to buy or sell, or loans outside the trusts in the data.
