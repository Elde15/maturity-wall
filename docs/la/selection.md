# Los Angeles case files: selection rule

Written and committed 2026-11-16, before any case file was drafted (SOP 13 step 5). The candidate list with every rank is
`docs/la/candidates.csv`, produced by `python -m mwall la --select` from the published outputs of 2026-11-12.

**Market.** Loans whose property is in the Los Angeles-Long Beach-Anaheim metro (CBSA 31080: Los Angeles and Orange
counties, OMB July 2023 delineation), assigned by the geocoded county FIPS code.

**Eligible.** Single-property loans (multi-property loans can't be tied to one address or one set of local rules) with
a base-scenario value.

**Picks, in this order; a loan already picked is skipped:**

1. Office: the highest opportunity score among eligible office loans with a confidence tier of A or B.
2. Multifamily: the highest opportunity score among eligible multifamily loans with tier A or B.
3. Retail or industrial: the highest opportunity score among eligible retail and industrial loans with tier A or B.
4. Rated safe by the model, risky by a rule of thumb: among eligible performing loans with a debt yield under 8% (the
   B1 rule), the lowest 12-month distress probability.
5. The widest disagreement: among eligible performing loans with both a distress probability and a debt yield, the
   largest gap between the loan's percentile rank by distress probability and its percentile rank by debt yield
   (low debt yield = risky), both ranked within the market.

Ties go to the larger balance. Opportunity scores, tiers, probabilities and debt yields are the published values; none
were changed after this list was drawn.

## Result

- 1. Top office by opportunity score: Red Building (West Hollywood, Los Angeles County), office, `WL2725d11c7fb2`, balance $232.5M, opportunity score 84.7, distress probability 9.06%, debt yield 5.7%.
- 2. Top multifamily by opportunity score: RESPARA (Los Angeles, Los Angeles County), multifamily, `WLbf79352ce0cd`, balance $62.2M, opportunity score 84.3, distress probability 4.52%, debt yield 6.9%.
- 3. Top retail or industrial by opportunity score: LA Creative Industrial Portfolio (Los Angeles, Los Angeles County), industrial, `WL5194ef124566`, balance $15.2M, opportunity score 80.7, distress probability 4.19%, debt yield 1.6%.
- 4. Model safe, debt-yield rule risky: SOS Storage Center (Torrance, Los Angeles County), self_storage, `WL70bd49d7ed10`, balance $14.0M, opportunity score 66.2, distress probability 0.55%, debt yield 2.1%.
- 5. Widest model and debt-yield disagreement: Holiday Inn Express Van Nuys (Van Nuys, Los Angeles County), lodging, `WL339ae594e8a7`, balance $10.0M, opportunity score 23.4, distress probability 7.07%, debt yield 21.4%.

Market: 640 scored loans (566 eligible); 1006 California loans fall outside it.
