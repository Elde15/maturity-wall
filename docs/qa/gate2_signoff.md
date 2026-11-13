# Gate 2 sign-off: features and labels

Signed off 2026-11-13. Every checklist item below is decided by a committed artifact. The numbers come from the full panel built on the Gate 1 data (`python -m mwall panel`, `python -m mwall features --audit`).

## Checklist (SOP section 15)

| item | result | evidence |
| --- | --- | --- |
| Every feature has a dictionary row, a unit test and a distribution plot by property type | PASS | 64 features plus 5 categorical keys in seven families, all generated from `src/mwall/features/catalog.py` into `docs/features.md`. `tests/test_features.py` checks every loan feature against a hand-worked example (`test_golden_row_every_loan_feature`), the market, refinance and cap-rate joins on hand-built tables, and fails if any catalog entry has no test (`test_every_catalog_feature_has_a_unit_test`). One figure per family in `docs/qa/features/`, with coverage by type in `docs/qa/gate2_features.md`. The categorical keys (type, state, metro, status) get coverage tables, not plots. |
| A leakage audit confirms no feature uses data published after its snapshot date | PASS | `docs/qa/gate2_leakage.md`. No outcome field is an input. Every market value joined (Treasury, rents, employment, permits, lender spreads, cap rates) was published on or before the filing date, with 0 exceptions. A truncation replay recomputes the loan features with later filings removed, at four cut dates over 600 loans (64,144 row comparisons), and finds no change. A deliberately leaky canary changes in 39,170 of those comparisons, so the replay has the power to catch a leak. |
| Label counts by tier, property type and vintage are published, including the number of tier 1 events | PASS | `docs/qa/gate2_labels.md` and `docs/qa/gate2_gold_set.md`. |
| A hand check of 20 loans confirms labels match what the filings show | PASS | `docs/qa/gate2_hand_check.md`: 20 of 20, after two positives were redrawn under D045 (both were NCB co-op loans flagged by a modification indicator that carried no modification). |

## What the labels say

- **Tier 2 (12-month distress):** 676,532 labeled loan-months with the whole window inside the data, 18,067 with an event (2.7%). Lodging runs highest at 7.7%, self-storage lowest at 0.4%. Office is 3.0% and multifamily 1.8%.
- **Tier 1 (maturity outcome):** 173 of 431 EX-102 whole loans failed to pay within 90 days of maturity (40.1%). Adding the vintage-2016 loans read from 10-D tables gives a gold set of 1,631 labeled whole loans and 357 failures (21.9%), most of them maturing in 2025 and 2026. The two sources overlap on 7 loans and agree on all 8 labeled pairs.
- **Tier 3 (loss severity):** 220 liquidated positions, 151 with a reported loss, median severity 0.43.

## Changes made during Gate 2 that move numbers

- **D045:** the modification indicator alone no longer counts. One servicer set it on co-op loans with nothing behind it, and it made 44% of the first count of tier 2 positives.
- **D045:** months whose window runs past the data are flagged. They were 45.8% positive, because only an early event can label them.
- **D050:** a payoff after the 90-day grace window is a failure, as the definition says. That adds 9 failed EX-102 maturities.
- **D050:** "Partial Liquidation (Curtailment)" is not a liquidation.
- **D050:** Citibank's older layout printed loan numbers with a leading zero, which split one loan into two keys.

## Limitations to publish

1. **Market series are today's vintage.** Zillow, QCEW, permit and housing-unit figures are revised after release; a revision after the snapshot date is a small look-ahead. Treasury yields are not revised.
2. **Lender limits are constants** (LTV, DSCR, debt yield, amortization, property-type spread premiums) from sources published mostly between 2022 and 2026, with the OCC handbook (2013) as the pre-2017 anchor. Only the spread itself is dated (CBRE's quarterly series). CBRE printed no level for 2016Q2 to 2018Q1 or 2018Q3 to 2020Q1, so 2017 and 2018 refinance rates use the wide 2016Q1 spread.
3. **The cap-rate benchmark is chain-linked:** CBRE survey averages to 2019 (retail to 2022), then CoStar's monthly changes. Survey and transaction cap rates measure different things, so the level is less certain than the changes. There is no benchmark for self-storage or mixed use, and lodging lapses after 2021.
4. **Office-using employment ends at 2025 Q2.** BLS stopped publishing metro rows by industry in Q3 2025.
5. **There's no usable current NOI in 36% of loan-months** (44% for multifamily, where co-op loans rarely report it). That's higher than the 29% with NOI missing at Gate 1, because a partial-year figure whose year-to-date or annualized basis can't be told (D021) also counts. The model reports performance with and without current NOI, as the SOP requires.
6. **Two of the 49 vintage-2016 trusts are unread.** COMM 2016-DC2 and CFCRE 2016-C4 publish statements as positioned page text. The 10-D loans carry fewer fields than the XML ones, so they serve as labels for calibration and testing; they get no full feature rows.
7. **7,229 loan-months (0.66%) are late snapshots,** filed after the loan's next period. They keep their features but stay out of training.

## Open for Eli before anything is published (Gate 6)

The cap-rate benchmark uses CBRE survey values and CoStar figures as NAR published them, and the lender parameters quote CBRE, Greystone, Freddie Mac, the OCC and others. The SOP says to transcribe minimal values with attribution and check each source's terms. The model uses these numbers internally; whether the site may show them (for example the benchmark line on a chart) needs a terms check per source. PwC and IRR figures were found but not used: PwC only as re-hosted subscriber copies, IRR only through its registration library.
