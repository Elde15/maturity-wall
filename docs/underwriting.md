# Underwriting method

For each loan with usable NOI the engine asks four questions: what a lender would lend against the property today, what the property is worth, what a buyer could pay for it, and what that buyer earns over five years. The answers are an indicative economic bid for the property, not an offer for the loan. A CMBS loan is controlled by its special servicer, and a buyer gets to the asset by buying the note, buying the property after foreclosure, negotiating a discounted payoff or recapitalizing the sponsor. None of this is investment advice.

Code: `src/mwall/underwrite/engine.py`. Parameters, each with its source rows and check date: `config/underwriting_params.csv`, `config/la_overrides.csv`, `config/lender_params.csv`, `config/scenarios.csv`. Decisions D056 to D058. Evidence: `docs/qa/gate4_underwriting.md`.

The valuation date is the scoring date (November 12, 2026). Market inputs are what was public that day: Treasury yields of November 10 (10-year 4.98%, 5-year 4.81%), CBRE's 2026 Q3 lending spreads (published November 9) and the latest cap-rate benchmarks (CoStar via NAR, September 2026, published November 5).

## Inputs from the filing

Whole-loan balance B (pari passu pieces added up, D020), annualized NOI and revenue from the latest filing that reports them, NOI and appraised value at securitization, square feet or units, occupancy, the three largest tenants' square feet and lease end dates, number of properties, year built, and the property's location. If the latest filing leaves NOI blank, the latest earlier filing's NOI is used and marked as such.

## Confidence tier

The SOP assigns a tier by type: A for multifamily, industrial and self-storage, B for office and retail (rollover matters and only three tenants are listed), C for lodging, mixed use and other (direct capitalization only, no cash-flow model). A tier drops one step when the NOI is more than 18 months old, was annualized from under six months, or was filed on an unknown basis. A loan without square feet or units falls to C. A loan with no NOI, NOI of zero or less, or NOI more than 36 months old isn't underwritten.

## Step B first: cap rate, stressed NOI, value

The cap rate is set relative to the market. At securitization the property's cap rate was its NOI over its appraisal. Its spread over the benchmark for its type at that date, held to the 10th to 90th percentile of spreads within the type, is added to today's benchmark:

    c = benchmark_today + clip(NOI_sec / V_sec - benchmark_at_securitization) + scenario cap shift

Self-storage, lodging, mixed use and other have no current benchmark series of their own, so they use the mean of the office, retail, industrial and multifamily series on both dates. Appraisal cap rates and survey cap rates aren't the same measure (appraisals run lower: the median office spread is -0.7 points). The relative-value method carries that difference forward, which is why every result is also shown at plus and minus 50 and 100 bp.

Stressed NOI is in-place NOI times one minus the scenario's haircut (zero in the base case; KBRA's median gap between its sustainable cash flow and the issuer's, by type, in the downside). Value is stressed NOI over the cap rate.

In Los Angeles and Orange counties, a sale resets the property tax to the price (Proposition 13). The seller's current tax isn't in the filings, so it is estimated as the county's average rate times the securitization appraisal grown 2% a year. A buyer paying V pays tax at rate t on V instead, so value solves V c = NOI + T_current - t V:

    V = (NOI_stressed + T_current) / (c + t)

## Step A: refinance gap

A lender sizes a new loan by the tightest of three tests, at a rate equal to the 10-year Treasury plus CBRE's spread (commercial or multifamily series) plus a premium by type:

    P_max = min(LTV_max V, NOI_stressed / (DSCR_min k), NOI_stressed / DY_min)
    k = 12 (r/12) / (1 - (1 + r/12)^(-12 n))
    gap = max(0, B - P_max)

The base case uses today's conduit floors (Greystone's 2025-26 schedule: debt yield 12.5% for office, 9% retail and industrial, 8.25% multifamily and self-storage, 12% lodging; 75% LTV; 1.25x DSCR, 1.30x lodging). The downside tests DSCR at 1.40x (Fitch's interest-only test). A loan with negative NOI has a gap equal to its balance.

## Step C: two bids

The value bid is what the market would pay for the property as it stands: value less a year of capital reserves and the cost of leasing listed tenant space that rolls within a year (expected leasing commissions and tenant improvements, plus rent lost during downtime for tenants expected to leave), grossed down for the buyer's 2% closing and financing costs.

The return bid is the price at which the buyer's levered IRR over five years equals the hurdle (20%, Knight Frank's opportunistic mean). The implied bid is the lower of the two, and the discount to par is one minus the bid over the balance. A bid at or above the balance is flagged "refinanceable by sale" and shown with no discount.

## Step D: five-year cash flows (tiers A and B)

Year-one NOI is stressed NOI less downtime losses and, under Proposition 13, the change in property tax. Later years grow at the type's rate: office 1.0%, retail 1.7%, industrial 1.8%, multifamily 2.0% (the first growth year uses the metro's Zillow multifamily rent change where it exists), self-storage 1.25%. Local rent rules cap that growth for multifamily: 3% under the City of Los Angeles rent ordinance (buildings from 1978 or earlier), 1.919% in unincorporated Los Angeles County (1994 or earlier), 8.7% under the state cap for other buildings 15 or more years old in the two counties.

Rollover (office, retail, industrial): each listed tenant's space rolls in the year its lease ends (an expired lease rolls in year one). The rest of the occupied space rolls evenly at one over the average lease term (office 6.7 years, retail 8.9, industrial 4.9). Rolling space renews with the type's probability (office 52%, retail 79%, industrial 76%) at the renewal leasing cost; otherwise it sits empty for the downtime (9, 4.5 and 4.5 months) and is re-let at the new-lease cost. Capital items are those leasing costs plus annual reserves ($0.25 a square foot for office, $0.175 for retail, industrial and self-storage, $250 a unit for multifamily). Reported NOI already deducts management fees, so they aren't taken again.

The value-add scenario adds a multifamily renovation program at IRT's 2025 cost of $19,661 a unit, paid at closing and earning its 15.3% return on cost from year two. It is off where a local rent ordinance blocks the rent premium.

Acquisition debt is a bridge loan, interest-only for the hold, sized at the lower of 75% of cost and 65% of value (60% for office), at the 5-year Treasury plus 300 to 425 bp by type.

Exit is at the end of year five at year-six NOI over the going-in cap rate plus 50 bp, less 2% selling costs (4% in New York City, San Francisco and Philadelphia counties). In the City of Los Angeles, Measure ULA adds 4% of the whole price above $5.4 million and 5.5% at $10.9 million or more, with both thresholds grown 2.6% a year to the exit date; Santa Monica and Culver City add the part of their tiered rates above the first tier. Under Proposition 13 the next buyer reassesses at its own price, so the exit price uses the same formula as value.

Outputs at the return bid: unlevered and levered IRR, equity multiple, average cash-on-cash yield, year-one DSCR and debt yield on the bridge loan, break-even occupancy and equity required. The levered and unlevered IRRs at the value bid are reported too.

Solving for the return bid: the levered NPV at the hurdle is a straight line in price below the price where the 65% value test starts to bind the loan, and another straight line above it. The engine evaluates the NPV at a price of zero, at that kink and at twice the kink, and solves the right line exactly. No iteration is needed, and a spreadsheet can do the same.

## Opportunity score

The average of six percentile ranks, scaled to 0 to 100: risk (1 for a loan already in special servicing, 30 or more days delinquent or past maturity unpaid; else the failure-to-refinance probability's percentile, or the 12-month distress probability's where there's no failure probability), refinance gap as a share of balance, discount to par, the levered IRR a buyer earns paying the value bid, tier (A 1, B 0.5, C 0) and balance as a liquidity proxy.

## What the engine can't see

- Lease-level detail beyond the three largest tenants, and any tenant's rent. Rent is spread evenly over occupied space.
- The property's actual assessed value and tax bill in California; the estimate assumes the property was last reassessed near its securitization appraisal.
- Property condition, deferred maintenance, ground leases and the loan's own reserves.
- Sale comparables. Values rest on survey and appraisal cap rates.
- For multi-property loans, which property is which: they're valued on pooled NOI with no listed-tenant rollover and no local rules.
- Whether any buyer can actually reach the property. The bid is economic, not executable.
