# Acquisition underwriting assumptions: source notes

Companion to `underwriting_sources.csv` (260 data rows, accessed 2026-11-16). Every value was copied from a page or PDF fetched that day and read with a local text extractor (pdftotext or an HTML stripper), not a summarizer. The `notes` column of each row starts with `file=<name>;`, the saved text file the quote comes from. The raw pages (.html/.pdf plus .txt extractions) are archived under `data/meta/research_raw/underwriting/`, which is git-ignored: the source documents are not redistributed.

How quotes were checked: a script collapses whitespace, straightens curly quotes and dashes, splits the quote on ` ... `, and confirms each fragment appears in the saved file. All 260 rows pass. Where a PDF table came out scrambled in layout mode, a second plain extraction was saved as `*_raw.txt` and the quote points at that. Rows marked DERIVED in `notes` are arithmetic on printed numbers, and the arithmetic is written out.

## Recommended base case

These are my picks for a five-year hold of distressed CMBS collateral. The reasoning is in the sections below.

| parameter | office | retail | industrial | multifamily | lodging | self_storage | mixed_use |
|---|---|---|---|---|---|---|---|
| levered IRR hurdle, gross | 20 (opportunistic); 16 as the value-add case | same | same | same | same | same | same |
| unlevered discount rate | 8.5 stabilized; 10.0-12.5 distressed | 7.75 | 7.45 | 7.15 | 10.9 | 8.5 | no source; blend by rent share |
| exit cap spread over going-in | +50 bp | +50 | +50 | +50 | +50 | +50 | +50 |
| LTC / as-is LTV | 75 / 60 | 75 / 65 | 75 / 65 | 75 / 65 | 75 / 60 | 75 / 65 | 75 / 65 |
| bridge spread over SOFR | 400-450 | 350 | 300 (375-400 heavy value-add) | 300 (375-400 heavy value-add) | 400-450 | 350 | 350 |
| bridge structure | IO, 3 yr + two 1-yr extensions | same | same | same | same | same | same |
| selling cost, % of price | 2.0 (4.0 in NYC/SF/LA/Philadelphia) | 2.0 | 2.0 | 2.0 | 2.0 | 2.0 | 2.0 |
| buyer closing cost, % of price | 2.0 | 2.0 | 2.0 | 2.0 | 2.0 | 2.0 | 2.0 |
| management fee, % of EGI | 3.0 | 3.0 (by analogy) | 3.0 | 3.0 | 3.0 base | 6.0 | 3.0 |
| capital reserve | $0.25/sf | $0.15/sf (range 0.10-0.25) | $0.15/sf (range 0.10-0.25) | $250/unit ($200 floor) | 4% of revenue | no source | blend |
| new-lease TI+LC, $/sf | 42 | 18.5 | 3.5 | n/a | n/a | n/a | blend |
| renewal TI+LC, $/sf | 23 | 1.2 | 1.4 | n/a | n/a | n/a | blend |
| downtime, months | 6-12 | 3-6 | 3-6 | n/a | n/a | n/a | blend |
| renewal probability | 52 | 80 | 76 | n/a | n/a | n/a | 50-65 |
| renovation | n/a | n/a | n/a | $15,000-17,500/unit, ~15% premium, 15-16% return on cost | n/a | n/a | n/a |
| NOI haircut to issuer NCF (stress) | 13 | 9 | 11 | 5.6 | 9 | 10 | 12 (conduit) |

## 1. Levered IRR hurdle

Range: core 9.5%, core-plus 11.7%, value-add 9-16.1%, opportunistic 14-20.1%. Knight Frank's Active Capital Survey 2026 (January 2026) gives the survey means: 9.5 / 11.7 / 16.1 / 20.1. Fund targets reported by IPE Real Assets from US pension board documents: Crow Holdings Realty Partners XI targets 16% gross and 12% net at 65% leverage, TA Realty Value-Add XIV 10-12% at 50% leverage, PGIM PRISA III 9-12% net, Carlyle Realty Partners X 14-17% net. Meketa's 10-year assumptions for Rhode Island ERSRI (4.8 / 5.8 / 8.8% net) are in the file for contrast and labelled as not hurdles.

Base: 20% gross for a distressed buyer, 16% as the softer value-add case. The model works at deal level before fees, so gross is the right basis, and Crow XI's 16% gross lands 0.1 point from the Knight Frank value-add mean. Net targets run about 400 bp under gross (Crow XI).

Conflicts and gaps: Knight Frank doesn't say gross or net and the survey is global. None of the sources splits hurdles by property type, so every row is `all`. No US pension policy I could open states absolute targets by style; CalSTRS states them relative to ODCE.

## 2. Unlevered discount rate and exit cap rate

Non-traded REIT NAV disclosures are the cleanest open source. BREIT (September 30, 2026 NAV, discount / exit): multifamily 7.2 / 5.4, industrial 7.5 / 5.5, office 8.1 / 5.6, retail 7.9 / 6.3, hospitality 10.9 / 9.3, self-storage 8.5 / 6.5 (April 30, 2026, the last print before BREIT sold out of storage). JLL Income Property Trust (March 31, 2026): multifamily 7.1 / 5.4, industrial 7.4 / 5.7, office 8.5 / 6.9, retail 7.6 / 6.0. CBRE's Q4 2025 multifamily survey puts unlevered IRR targets at 7.70% core and 9.36% value-add.

Distressed office comes from impairment disclosures: Peakstone's FY2025 10-K (10 impaired office properties) used a 10.00-12.50% discount rate and 8.25-10.50% terminal cap; Highwoods used 16.7-19.9% and 9.5% on one Pittsburgh CBD building.

Base: midpoint of BREIT and JLL for multifamily, industrial and retail (they agree within 0.3 point). Office: JLL's 8.5 / 6.9 for stabilized assets, Peakstone's ranges for distressed ones. BREIT's 5.6% office exit cap is too low for the office this model will see. Lodging and self-storage rest on BREIT alone. For a value-add or distressed buyer, add 150-200 bp to the NAV discount rates; CBRE's survey gap between core and value-add multifamily is 166 bp.

Gaps: no mixed-use rate anywhere. These are appraiser marks on stabilized institutional assets, so they lag trades and sit below what a distressed buyer demands. SEC EDGAR returned 403 to our user agent, so 10-K figures came from issuer sites or Boardroom Alpha copies (accession numbers in `notes`).

## 3. Acquisition and bridge debt

LTC: 70-80% of total cost, multifamily only. Arbor (September 2025) and NewPoint (March 2025) say up to 80%; NewPoint's April 2026 sheet says up to 75%; CLS CRE's mid-2026 survey says 70-75%. Base 75%, with 80% as the aggressive case.

As-is LTV at origination: KREF's senior book 65% (Q3 2026), TRTX 65.9% book and 70.2% on Q3 2026 originations, Granite Point 69.0%. A broker page caps office and hotel bridge at 60-65%. Base 65% for multifamily, industrial, retail and storage, 60% for office and lodging. The lower of LTC and LTV sizes the loan, and on collateral bought below appraisal LTC will usually bind.

Spread over SOFR: institutional books run 290-310 (KREF 290, TRTX 302 on Q3 2026 originations, 308 book), Granite Point's legacy book 362, and the broker universe 350-600 (CLS CRE, October 2026). By type: multifamily 230-390 at KREF, 275-350 light and 350-450 heavy value-add (CLS), 375-425 small balance (Greystone); industrial 240-280 (KREF) and 275-375 (CLS); office 260-320 at KREF but only at 48-60% LTV, and 410 on one TRTX loan at 70% LTV; lodging 300-330. Base: 300 for multifamily and industrial, 375-400 for a heavy value-add plan, 400-450 for office and lodging, 350 for types with no data.

Structure: interest-only for the whole term (Greystone, Arbor, CLS). Granite Point's 10-K: typically a three-year initial term plus two one-year extensions. Permanent takeout at 30-year amortization (Freddie Mac conventional via NewPoint, January 2026). Fees seen: 1% origination, 1-2% exit, 0.50% per six-month extension (Greystone).

Gaps: no LTC for any non-multifamily type, and no institutional spread for retail, self-storage or mixed use.

## 4. Exit cap spread over going-in

Range: 12-60 bp. CBRE's Q4 2025 multifamily survey calls 50-60 bp the "more typical level" while measuring only 20 bp for core and 12 bp for value-add; the pre-pandemic (Q4 2019) spread was 58 bp. Wall Street Prep's rule of 10 bp per hold year gives 50 bp over five years (DERIVED).

Base: +50 bp for every type, with +25 and +75 as sensitivities. Today's thin spreads reflect buyers expecting cap rates to fall, and that optimism doesn't belong in a distressed underwrite. No source states a spread for office, retail, industrial, lodging or storage.

## 5. Selling costs and buyer closing costs

Selling costs: Altus Group (September 2025) says resale cost assumptions run from below 1% to more than 6%, calls 2.00% the generic assumption, and puts Manhattan office at about 4.00%. Transfer tax is under 1% of price in most states, with large outliers (NYC above 3.25%, San Francisco up to 6.00%, Los Angeles up to 5.95%). Matthews (October 2026) puts NYC seller costs at 7-11% all-in.

Brokerage: Marcus & Millichap's average commission rate was 1.82% in FY 2025. Split by deal size (DERIVED from its revenue and volume table) it falls from 2.78% on $1-10M deals to 1.86% on $10-20M and 0.72% on $20M and up. Matthews quotes a 2-6% fee schedule for small NYC deals.

Base: 2.0% of sale price nationally. A CMBS-size asset pays roughly 0.7% to the broker, plus transfer tax under 1% in most states, plus legal and closing. Use 4% where the metro carries a heavy transfer tax.

Buyer closing costs are the weakest item in the file. The only number is DERIVED from Matthews' Brooklyn example: total cash need of 29.25% of price at 75% LTV leaves 4.25% for closing and financing costs, of which about 2.1 points is NYC mortgage recording tax, so about 2.15% elsewhere. Matthews also puts title insurance at 0.4-0.6%. I'd use 2.0% and treat it as probably high for large deals. No national survey of buyer closing costs turned up; the other hits were lender and marketplace blogs with no numbers worth citing.

## 6. Management fee

Multifamily: Fannie Mae's conventional underwritten NCF takes the greatest of 3% of EGI, the actual fee, or the appraiser's market fee; 2.5% is allowed on loans over $9M with at least $500 per unit. Office and industrial: the RMR agreements in the Office Properties Income Trust and ILPT 10-Ks pay 3.0% of gross collected rents. Lodging base fees: Sunstone 2.5-3.0% of total revenue, Apple Hospitality 2.5-3.5% of gross revenue on its variable structure, with incentive fees on top where thresholds are met. Self-storage: 6% of property revenue (a CubeSmart executive in 2012) and 6-7% for a single store, as low as 4% for multi-store clients (2008 operator survey). Both storage sources are old; the convention hasn't moved much, but treat them as old.

Base: 3.0% for every type except self-storage at 6.0%. Retail has no open source and takes 3.0% by analogy. Kimco's and Regency's 10-Ks describe fee income from joint ventures without a percentage.

## 7. Capital reserves

Multifamily: Fannie Mae's floor is $200 per unit per year, or more if the property condition assessment says so. CLS CRE's glossary (2026) gives the market convention as $250-300 per unit. Base $250.

Lodging FF&E: Sunstone's agreements require 3.0-5.5% of revenue, Apple's up to 5%, and CLS says about 4%. Base 4%.

Office, retail, industrial: CLS gives $0.10-0.25 per square foot. A 2025 Missouri State Tax Commission decision records a CBD St. Louis office survey average of $0.29 and an appraiser's concluded $0.25 (valuation date 2019). Base $0.25 for office and $0.15 for retail and industrial. These rest on a broker glossary and one tax case; the rating-agency schedules that would settle it are behind logins (see gated list).

Self-storage: no open source.

## 8. TI, leasing commissions, downtime and renewal probability

Office. CBRE (March 2025): new-lease TI averaged $87.51/sf in 2024 across 12 markets, down from $97.55 in 2023, with 8.9 months of free rent. Highwoods (Q2 2026): $34.16/sf TI and $10.51/sf commissions on second-generation leases, new and renewal combined. Office Properties Income Trust (FY 2025): $42.09/sf all-in leasing cost (TI, commissions, free rent) on new leases over 6.2 years and $22.92/sf on renewals over 7.0 years. Base: $42/sf new and $23/sf renewal all-in, from OPI, which is itself a distressed landlord. CBRE's $87.51 is a 12-market sample and runs high for secondary office.

Retail. Brixmor (twelve months to June 30, 2026): new leases $10.61/sf TI and $7.88/sf third-party commissions on a 10.7-year term; renewals $1.08 TI and $0.11 commissions. DERIVED commission rate on new leases: 3.1% of aggregate base rent.

Industrial. STAG (FY 2025): total leasing cost $3.54/sf on new leases (5.5-year term) and $1.41/sf on renewals (4.8 years). The renewal row needed a check because the PDF prints it misaligned; the weighted average of the two reproduces the printed total.

Commission percentages: no filing states one. Apers, a software vendor, gives illustrative rates (office Class A 4-6% new, 2-3% renewal; industrial 2-4% and 1-2.5%; inline retail 4-6% and 2-3%) and says itself they aren't survey data. Brixmor's realized 3.1% sits under the Apers retail range.

Downtime: the only open statement is Apers' primer, 6-12 months for office and 3-6 for retail and industrial. STAG's 10-K says it uses downtime assumptions but doesn't print them. Low weight.

Renewal probability: Brandywine's 2026 guidance is 51-53% for office (its Q2 2026 actual was 85%, so quarters are noisy). Brixmor retained 79.4% of expiring leases by count and 86.7% by area. STAG's industrial retention was 75.8% year to date and 90.3% in Q3 2026; that figure comes from an Earnings Whispers write-up of the call because SEC blocks our user agent. Apers puts local and regional tenants at 50-65%, which fits Class B/C office and mixed use. Base: office 52%, retail 80%, industrial 76%, mixed use 50-65%.

## 9. Multifamily renovation

Cost per unit: $6,080 (MAA 2025, light kitchen and bath) to $20,430 (IRT first half of 2026). NXRT program to date $9,115; IRT life to date $15,431 interior and $17,372 including exterior and amenity work; IRT 2025 $19,661. Premium: $95 to $272 a month; stated percentages are 6.9% (MAA), 13.5% (NXRT) and 19.9% (IRT, measured against market rent excluding concessions). Return on cost: 15.3% (IRT 2025) to 20.8% (NXRT).

Base: $15,000-17,500 per unit for a full interior program, or $20,000 at 2026 cost; about a 15% rent premium; 15-16% return on cost, with IRT's concession-adjusted 11.3-12.6% as the stress case. All three REITs run Sunbelt garden assets, so these don't fit urban high-rise. No 2023-2026 renovation disclosures were found for Camden, UDR, AvalonBay, Equity Residential, Elme, Centerspace or BRT.

## 10. Rent growth and vacancy

Read this before using any vacancy row: publishers measure different universes. In the same quarter office vacancy is 13.8% from NAR (CoStar data) and 19.8% from Cushman & Wakefield; multifamily is 4.9% from CBRE and 7.8% from NAR. Pick one series per property and don't splice.

Office: CBRE forecasts 2.7% rent growth for 2026 and 18.0% vacancy at year end. Industrial: CBRE about 1.8% rent growth for 2026; current readings run from 0.5% (Marcus & Millichap) to 4.0% (Cushman & Wakefield); vacancy 6.8-7.8%. Retail: CBRE's five-year rent CAGR is 1.7%; vacancy 4.3-5.9%, with C&W's historical average of 7.4% as the stress level. Multifamily: CBRE 1.4% for 2026 and a 2.8% five-year CAGR; Yardi (via NAR) 1.2% for 2026 and 2.0% for 2027; Freddie Mac's latest outlook is 2025 (2.2%, 6.2% vacancy). Lodging: CBRE RevPAR 2.5% for 2026 and 2.1% for 2027, occupancy 62.8-63.0%; Marcus & Millichap 3.8% for 2026; CoStar's long-term RevPAR average 3.0%. CBRE says the World Cup adds 0.5-0.8 point to 2026 RevPAR, so year 1 shouldn't be extrapolated. Self-storage: only REIT guidance, 2026 same-store revenue of 0.0-0.5% (Public Storage) and 2.0-2.5% (Extra Space), occupancy 92.2-94.3%.

Two longer-horizon numbers come from appraisal and underwriting practice rather than forecasts. JLL Income Property Trust's March 2026 DCFs assume annual market rent growth of 3.1% industrial, 2.7% office, 3.1% residential and 3.0% retail. CBRE's Q4 2025 survey has buyers underwriting 2.7% (core) and 3.1% (value-add) multifamily rent growth for three years.

Base: office 0-1% (distressed office is mostly non-prime and CBRE says prime space drives its 2.7%), industrial 1.8% then 2.5%, retail 1.7%, multifamily 2.0-2.5% flat, lodging RevPAR 2.5% / 2.1% then 2-3%, self-storage 1%. Vacancy from one series per asset. Nothing open gives a 2028-2030 forecast by year; the five-year CAGRs and long-run averages are the only items that reach that far. ULI's consensus forecast would have filled the gap but returned 403.

## 11. NOI haircut (stressed underwriting)

The rating agencies' haircut schedules sit inside methodologies that need a login (see gated list), but KBRA's preliminary-rating press releases are public and state how far its sustainable NCF (KNCF) sits below the issuer's NCF on every deal. Thirty-five 2025-26 releases were collected:

| group | deals | haircut range | median |
|---|---|---|---|
| conduit pools (all types) | 14 | 10.5-14.2% | 12.2% |
| office SASB | 4 | 7.3-16.3% | 12.9% |
| industrial SASB | 6 | 9.0-11.9% | 10.7% |
| self-storage SASB | 3 | 4.4-11.5% | 10.3% |
| lodging SASB | 4 | 6.9-10.0% | 9.0% |
| retail-heavy SASB (BX 2026-ALOHA) | 1 | 9.1% | 9.1% |
| multifamily SASB | 3 | 3.5-5.6% | 5.6% |

The same releases put KBRA's value 28-43% under the appraisal (31 rows as `value_haircut_vs_appraisal_pct`; conduit median 38.4%), because KBRA also uses long-run cap rates.

Base: haircut issuer or in-place NOI by the type median above (office 13%, industrial 11%, self-storage 10%, lodging 9%, retail 9%, multifamily 5.6%, mixed use 12% from the conduit median) for the stress case. These haircuts apply to new, institutional, mostly SASB originations, where the issuer's NCF is already lender-scrubbed. Distressed loans' reported NOI may need more. I dropped one hotel-casino deal (BX 2026-CSMO, 16.6%) because its saved text had an encoding fault, and a data-center deal as out of scope.

## Gated or blocked (skipped, no account or form used)

- Rating-agency methodologies with the NCF schedules (management fee, reserves, TI/LC, downtime by type): KBRA's North American CMBS Property Evaluation Methodology (January 2026) needs a free login; Morningstar DBRS's property analysis criteria download needs sign-in; S&P's site returned 403 ("Security Controls Triggered"); Fitch and Moody's need registration. The KBRA press releases above are the open substitute for haircuts only.
- SEC EDGAR returns 403 unless the user agent carries an email address, which the rules forbid. Filings came from issuer sites (q4cdn, sponsor PDFs) or Boardroom Alpha copies.
- Investor sites on the gcs-web/Akamai host blocked our user agent: Piedmont, Brandywine's supplemental, First Industrial. Barchart returned empty pages.
- ULI Real Estate Economic Forecast (403), yardi.com (403), CoStar's forecast release (403), Cushman & Wakefield's national office MarketBeat PDF (403), Marcus & Millichap full research (sign-in), CBRE US Cap Rate Survey H1 2026 (download form).
- Skipped on purpose: the SitusAMC/RERC sample report, which says quoting needs a subscription or consent; Integra (irr.com) per the brief; PeerSense, a lead-generation site.

## Couldn't find in the open

- A property-type split of IRR hurdles.
- Any mixed-use value: discount rate, exit cap, rent growth, haircut. Blend components by rent share.
- Exit cap spreads for anything other than multifamily.
- LTC for non-multifamily bridge loans, and institutional bridge spreads for retail, self-storage and mixed use.
- A national buyer closing cost figure.
- A retail management fee percent, and any self-storage reserve.
- Filing-grade leasing commission percentages, downtime months, and a filing-grade industrial retention rate.
- Rent or vacancy forecasts by year for 2028-2030.
