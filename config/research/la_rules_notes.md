# Los Angeles rules that change a buyer's numbers

Status as of 2026-11-16. Companion to `la_rules_sources.csv` (same folder), which has 83 rows. Every value in the CSV was read from a page saved under `research_raw/la_rules/` in the session scratchpad, and its `quote` column matches the saved text once runs of whitespace are collapsed (PDF extractions wrap lines). Each row's `notes` names the raw file and says when the source was published.

## The short version

| Rule | Where it stands on 2026-11-16 | Where it enters the model |
|---|---|---|
| Measure ULA (City of LA) | 4% of the whole price above $5.4M, 5.5% at $10.9M or more, for deals closing after June 30, 2026 (FY 2025-26 notches were $5.3M / $10.6M) | Transaction cost at sale (and at purchase if the buyer agrees to carry it) |
| City of LA base transfer tax | 0.45% of net value ($2.25 per $500) | Transaction cost |
| LA County transfer tax | 0.11% ($1.10 per $1,000) | Transaction cost |
| Other cities | Santa Monica up to 5.6%, Culver City up to 4%, Pomona and Redondo Beach 0.22%; everyone else adds nothing; no Orange County city surcharge found | Transaction cost |
| Prop 13 | 1% plus voter debt on the purchase price; assessed value grows at most 2% a year (2% applies for the 2026 roll); LA County average total rate 1.179%, Orange 1.058% | Property tax line |
| LA RSO (pre-Oct 1978 buildings) | 3% for July 2026 to June 2027 (3% the year before, 4% before that); new formula since Feb 2, 2026 is 90% of CPI, floor 1%, ceiling 4%, no utility add-on | Cap on renewal rent growth; market reset on turnover |
| AB 1482 | 5% + CPI, max 10%; LA/OC cap 8.7% for Aug 2026 to Jul 2027 (8.0% the year before); sunsets Jan 1, 2030 | Cap on renewal rent growth for non-RSO units 15+ years old |
| Unincorporated LA County RSTPO | 1.919% for July 2026 to June 2027 (2.919% small landlord, 3.919% luxury) | Cap on renewal rent growth |

## 1. Measure ULA (House LA tax)

ULA is a second City of Los Angeles transfer tax stacked on the 0.45% base tax. It applies to any deed conveying real property in the City, of any property type, when the price crosses a threshold. The rates are fixed by the measure. The two dollar thresholds re-index every July 1 to the national chained CPI.

| Period (transactions closing) | Lower notch (4%) | Upper notch (5.5%) | Source |
|---|---|---|---|
| Apr 1, 2023 as enacted | > $5,000,000 | >= $10,000,000 | Ordinance 187692 |
| FY 2024-25 (in force June 2025) | > $5,150,000 | >= $10,300,000 | Office of Finance FAQ, archived 2025-06-14 |
| July 1, 2025 to June 30, 2026 | > $5,300,000 | >= $10,600,000 | Office of Finance FAQ, archived 2025-11-13; County Recorder |
| From July 1, 2026 | > $5,400,000 | >= $10,900,000 | Office of Finance FAQ (live); County Recorder |

Three mechanics matter for the model:

- **The tax hits the whole price.** It is not marginal. The County Recorder's table says "4 Percent of the total transaction value". So the all-in City of LA rate jumps from 0.56% to 4.56% at the lower notch and to 6.06% at the upper one.
- **The base is gross.** ULA is computed on the full consideration including any loan the buyer assumes. The base tax and County tax use net value (liens remaining excluded). An assumption structure lowers the base tax but not ULA.
- **The date that counts is closing.** The Office of Finance applies each year's thresholds to "transactions closing after June 30".

My arithmetic on the cliffs, assuming no assumed debt so net equals gross:

| Price | All-in rate (County + City base + ULA) | Tax |
|---|---|---|
| $5,000,000 | 0.56% | $28,000 |
| $5,400,000 | 0.56% | $30,240 |
| $5,400,001 | 4.56% | $246,240 |
| $10,899,999 | 4.56% | $497,040 |
| $10,900,000 | 6.06% | $660,540 |
| $20,000,000 | 6.06% | $1,212,000 |

A seller who bears the tax nets more at $5.4M than at any price up to about $5.63M, and more at $10,899,999 than at any price up to about $11.07M. Expect bunching just under the notches and few closed comps inside those two bands. If the model's exit price lands in a band, test the price just below the notch.

Exemptions turn on who the buyer is, not on the property. A for-profit commercial or multifamily buyer has no exemption. The exempt buyers are affordable-housing nonprofits, community land trusts and limited-equity co-ops with an affordable-housing track record (LAMC 21.9.14, LAHD decides), 501(c)(3)s whose IRS letter is at least 10 years old and with assets under $1 billion (21.9.15), and government. A property straddling the City line is taxed pro rata by value, or by square footage if no valuation exists.

**Where it enters the cash flows.** Model ULA as a sale cost on exit, keyed to the exit price and the exit year's thresholds. Grow the thresholds by an assumed chained CPI from $5.4M / $10.9M. At acquisition it matters only if the purchase contract puts the tax on the buyer. The title-company guide says the seller customarily pays transfer taxes in LA and Orange counties, but that guide isn't an official source and the split is negotiable. For a value-add plan with a short hold, ULA on exit can wipe out a large share of the profit, so it belongs in the base case.

**Litigation and pending changes:**

- The Court of Appeal upheld ULA on December 15, 2025 (Howard Jarvis Taxpayers Assn. v. City of Los Angeles, B334071). It held that the people kept the power to pass a special transfer tax by majority-vote initiative.
- Both sides say the California Supreme Court then denied review: HJTA's own newsletter and the City's outside counsel. I couldn't reach the Supreme Court docket (the appellate case site returned 403), so that point rests on the parties' statements.
- The City Attorney drafted a ballot measure (report R26-0374, June 26, 2026) to exempt sales of new multifamily and mixed-use projects within 10 years of completion. It did not make the November 3, 2026 ballot. The County's official list of measures (revised 8/20/26) shows only Proposition TE among City of LA items touching ULA. Press reports say the Council shelved it on July 1. I found no official record of that vote.
- Proposition TE, on the November 3 ballot, gives a one-time ULA exemption for residential properties damaged in the Palisades Fire, sold by the January 7, 2025 owner before January 6, 2030. It doesn't touch commercial or multifamily deals. The result wasn't certified on the check date.
- AB 736 would have capped combined local transfer taxes at 1.5% from January 1, 2027. Only general taxes in effect by June 30, 2026 were grandfathered, so ULA, a special tax, would have been cut back. Its last action on leginfo is "In committee: Hearing postponed by committee" on June 25, 2026, with nothing after it.
- The HJTA statewide initiative that would have repealed ULA is not on the Secretary of State's list of November 3, 2026 measures. Press reports say it was withdrawn in a June deal.
- Proposition 43 (ACA 22), which is on that list, raises the vote needed for voter-proposed local special taxes to two-thirds, but only from January 1, 2027. It does not reach ULA whichever way the vote went. Press reports projected it failed. I couldn't confirm that officially because the SOS results site blocks automated requests.

The CLA's May 13, 2026 report summarizes the studies on ULA's effect on sales volume (UCLA: commercial, industrial and multifamily transactions down 30 to 50% over its first 20 months; Occidental disputes the housing findings). It also confirms that Culver City's Measure RE and Santa Monica's Measure GS had no pending amendments as of that date.

## 2. City of Los Angeles base transfer tax

0.45% of net consideration, written in the code as $2.25 per $500 or fraction. Value rounds up to the next $500. The County Recorder collects it at recording. Before April 1, 2023 the County bulletin showed it as $4.50 per $1,000, which is the same rate. Model it as a sale cost with the County tax.

## 3. Los Angeles County documentary transfer tax

$0.55 per $500, which is $1.10 per $1,000 or 0.11%, on net value, under R&T 11911. In ordinary cities the city levies half and the county credits it (R&T 11931), so the parties still pay 0.11% in total. In the five "special" cities (Culver City, Los Angeles, Pomona, Redondo Beach, Santa Monica) the County charges the full $1.10 and the city tax stacks on top.

The County also taxes transfers of a controlling interest (more than 50%) in an entity that owns LA County real estate. It has a separate declaration form for those deals, one per economic unit. That form predates ULA and lists only $4.50 for Los Angeles. I found nothing official saying whether ULA reaches an entity-level deal with no deed. Treat that as open and ask counsel before relying on an entity structure to avoid ULA.

Orange County charges the same statutory $0.55 per $500 (County Ordinance 2183), per an old Clerk-Recorder handout (REV 5/22/13).

## 4. Other cities in the metro

| City | Rate on top of the County 0.11% | All-in |
|---|---|---|
| Los Angeles | 0.45% + ULA (above) | 0.56% / 4.56% / 6.06% |
| Santa Monica (Measure GS, from Mar 1, 2023) | $3 per $1,000 under $5M; $6 per $1,000 from $5M to $7,999,999.99; $56 per $1,000 at $8M or more | 0.41% / 0.71% / 5.71% |
| Culver City (Measure RE, from Apr 1, 2021) | 0.45% up to $1,499,999; 1.5% to $2,999,999; 3% to $9,999,999; 4% at $10M or more | 0.56% / 1.61% / 3.11% / 4.11% |
| Pomona | $2.20 per $1,000 | 0.33% |
| Redondo Beach | $2.20 per $1,000 | 0.33% |
| Every other LA County city, incl. Pasadena and Long Beach | none | 0.11% |
| Orange County cities | none found | 0.11% |

Santa Monica's tier applies to the whole price; the city's own example taxes an $8M sale $448,000. Its tiers aren't indexed. Qualifying affordable-housing transfers can be exempt from tiers 2 and 3. For Culver City I have the brackets from the County Recorder and the CLA, but neither says whether each rate applies to the whole price or only the slice. Culver City's page (culvercity.org/rptt) returned 403 to automated requests. I'd assume whole-price, like Santa Monica and ULA, and flag it.

Pasadena's FY 2026 fee schedule lists a real property transfer tax of $0.55 per $500 with the footnote "established by State code." Pasadena isn't on the County Recorder's list of cities with special rates, so I read that as the standard statutory rate, not a surcharge. There's mild ambiguity because R&T 11911(b) sets a city's share at half of $0.55.

For Orange County cities, the only list I found is a title insurer's 2026 guide (not official). It shows the $1.10 county tax and no city tax for Orange County.

## 5. Proposition 13

- **Rate:** 1% of full cash value (Cal. Const. art. XIII A, sec. 1(a)), plus voter-approved debt rates.
- **Reset:** the base value resets to market "when purchased, newly constructed, or a change in ownership has occurred" (sec. 2(a)). Buying more than 50% of an entity that owns the property is also a change in ownership (R&T 64(c)(1)). The cumulative more-than-50% rule in 64(d) catches property that came into the entity in an excluded transfer.
- **Growth:** at most 2% a year (sec. 2(b)), or less if California CPI is lower. The BOE told assessors to use 1.02 for the 2026 roll (CCPI was up 3.3%).
- **Supplemental bill:** the County enrolls the new value right away and bills the difference, prorated over the months left in the July to June fiscal year, to the new owner.
- **Typical total rate:** the BOE's 2024-25 county averages are 1.179% for Los Angeles and 1.058% for Orange. The Auditor-Controller's FY 2025-26 Taxpayers' Guide says that "in most of Los Angeles County, the total tax rate does not exceed 1.25%." The FY 2025-26 countywide general levy is 1.000000 (Board of Supervisors resolution, September 2, 2025).

**Where it enters the cash flows.** Year-1 property tax equals purchase price times the parcel's total rate, plus direct assessments (lighting, stormwater parcel tax, BIDs, CFDs). Those assessments are billed on top and aren't in the rate. Grow assessed value by 2% a year; the rate itself drifts as debt levies change. Book a one-time supplemental bill in the first year. Don't carry the seller's tax bill forward, because the seller's assessed value is usually far below the price.

**Not confirmed.** I didn't get an official total rate for a specific City of Los Angeles tax rate area. The Auditor-Controller's TRA lookup is a submit form, so I didn't use it. The school-district rate table in the Taxpayers' Guide extracts with its columns misaligned, so I didn't rebuild a City of LA total from its parts. Pull the parcel's actual bill or TRA rate before closing. 1.18% to 1.25% is a reasonable placeholder for City of LA parcels.

## 6. Los Angeles Rent Stabilization Ordinance (RSO)

**Coverage:** rental properties "first built on or before October 1, 1978" (LAHD), plus replacement units. That covers apartments, duplexes, two or more houses on one parcel, ADUs, and condos and townhomes, though rent on condos and townhomes is unregulated for tenancies that began after 1995. Newer units in the City fall under the Just Cause Ordinance, which doesn't cap rent, and under AB 1482 if they're 15 or more years old. State law (Costa-Hawkins) bars local caps on units with a certificate of occupancy after February 1, 1995.

**Allowable increase:**

| Period | Allowed |
|---|---|
| July 1, 2026 to June 30, 2027 | 3% |
| July 1, 2025 to June 30, 2026 | 3% |
| July 1, 2024 to June 30, 2025 | 4% |
| March 2020 to January 2024 | increases prohibited |

**Formula change.** Ordinance 188795 took effect February 2, 2026. The annual increase is now 90% of the change in the average LA-Long Beach-Anaheim CPI-U (12 months to September 30 against the prior 12), rounded to a whole number, with a 1% floor and a 4% ceiling. The old rule was 100% of CPI with a 3% floor and an 8% ceiling, plus 1% for each utility the landlord paid. The utility add-on and the 10% bump for an added dependent are gone. Increases not noticed between June 1, 2025 and June 30, 2026 were capped at 3% with no utility add-on. Ordinance 188911 (effective April 20, 2026) confirms that any increase taking effect after February 2, 2026 follows the new rule. Landlords can also pass through $1.61 (RSO fee) and $2.83 (SCEP fee) per unit per month with notice.

**Where it enters the cash flows.** For RSO units, cap in-place rent growth at the published rate: 3% now, and 1% to 4% in later years. Let units reset to market on turnover (voluntary move-out, for-cause eviction, or a buyout). A pre-1978 building's revenue growth therefore depends mostly on assumed turnover and the gap between in-place and market rent, not on the cap.

**Pending.** LAHD publishes the July 2027 to June 2028 figure by May 30, 2027. My own rough read of BLS data, which is missing October 2025, puts the CPI input near 3.5%. Depending on how the double rounding in the ordinance is applied, that gives 3% or 4%. Treat that as my estimate, not LAHD's.

## 7. AB 1482 (Tenant Protection Act, Civil Code 1947.12)

The cap is "5 percent plus the percentage change in the cost of living, or 10 percent, whichever is lower," measured from the lowest rent in the prior 12 months, with at most two increases in 12 months. For increases effective on or after August 1, the CPI change is April to April, rounded to 0.1%. LA and Orange counties use the LA-Long Beach-Anaheim CPI-U.

| Period | LA/OC cap | CPI component |
|---|---|---|
| Aug 1, 2026 to Jul 31, 2027 | 8.7% | 3.7% |
| Aug 1, 2025 to Jul 31, 2026 | 8.0% | 3.0% |

Both figures come from the County DCBA, and LAHD's October 2026 notice gives the same 8.7%. I checked them against BLS: April 2026 was 355.166 and April 2025 was 342.565, up 3.68%, which rounds to 3.7%. April 2024 was 332.572, which gives the 3.0%. No state agency (HCD or DRE) publishes the regional figure.

**Exempt:** buildings with a certificate of occupancy within the past 15 years (a rolling test, so a 2012 building enters coverage in 2027); units under stricter local rent control (such as RSO or RSTPO units); single-family homes and condos not owned by a REIT, a corporation or an LLC with a corporate member, if tenants got the statutory notice; owner-occupied duplexes; deed-restricted affordable housing; dorms. A new tenancy can start at any rent. The section repeals itself on January 1, 2030.

**Where it enters the cash flows.** For covered units, cap renewal growth at min(5% + CPI, 10%), which is 8.7% today. That cap rarely binds in a normal market. Its practical bite comes after a spike in market rents or on a mark-to-market plan for below-market tenants. Model the 2030 sunset as a scenario, not a certainty.

## 8. Unincorporated Los Angeles County (RSTPO, County Code Chapter 8.52)

**Coverage:** two or more rental units on a property (and ADUs) in unincorporated areas, with a certificate of occupancy on or before February 1, 1995.

**Formula since January 1, 2025:** 60% of the change in average CPI over the 12 months ending in September. The cap is 3%, rising to 4% for qualifying small landlords (10 or fewer units, self-certified) and 5% for "luxury" units.

| Period | General | Small landlord | Luxury |
|---|---|---|---|
| July 1, 2026 to June 30, 2027 | 1.919% | 2.919% | 3.919% |
| July 1, 2025 to June 30, 2026 | 1.930% | 2.930% | 3.930% |
| January 1 to June 30, 2025 | 2.565% | 3.565% | 4.565% |

An increase is allowed only if the units are registered with DCBA and fees are paid. This is the tightest cap in the metro: below 2% a year for most units.

## What I could not confirm from an official source

- California Supreme Court denial of review in the ULA case, and its date. Only the parties' own statements say so.
- Final results for Proposition 43 (state) and Proposition TE (City of LA) on November 3, 2026. Neither is certified. The SOS results site blocked automated requests.
- The City Council vote that dropped the new-construction ULA exemption. The ballot list shows it isn't on the ballot, but I found no record of the vote.
- Whether the City's ULA tax applies to entity-level changes of control with no deed. The County taxes those for its own DTT; the City's position isn't on the Office of Finance FAQ.
- Whether Culver City's brackets apply to the whole price or only the slice above each bracket (city site blocked).
- Pomona and Redondo Beach rates come from the County Recorder's table, not the cities' own codes.
- No official list of Orange County city transfer taxes. "None" rests on the County handout's silence and a title insurer's guide.
- A parcel-level total property tax rate for the City of Los Angeles. I report the BOE county average and the Auditor's 1.25% statement instead.
- Who pays transfer tax by custom (seller in LA and OC) comes from a title insurer's guide, not an official source.
- FY 2026-27 County tax rate resolution and Taxpayers' Guide. Neither was found; the latest official rate data is FY 2025-26.

## Access notes

leginfo.legislature.ca.gov rate-limits scripted requests and returned 403 at random. Every statute here was saved on a retry. culvercity.org, the Court of Appeal docket site (appellatecases.courtinfo.ca.gov), and the SOS election-results site returned 403 or a bot challenge. The LA County Assessor site is a JavaScript app that returns an empty page to a script; the Auditor-Controller's Taxpayers' Guide covered the same Prop 13 ground. No forms were filled and no accounts were created. Every request used the User-Agent `mwall-research/0.1`.
