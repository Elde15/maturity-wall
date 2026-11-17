# Los Angeles market context, Q3 2026 vs Q3 2025

Status as of 2026-11-16. Companion to `la_market_sources.csv` (same folder), which has 371 rows. Every value was read from a page, PDF or data file saved under `data/meta/research_raw/la_market/` (git-ignored), and each row's `quote` matches the saved text once whitespace is collapsed and curly quotes and dashes are straightened. A script checked all 371 quotes and all 371 pass. Each row's `notes` starts with `file=` and names the extraction it was read from. PDFs have two extractions: `name.txt` (pdftotext `-layout`, keeps table rows on one line) and `name_flow.txt` (reading order, keeps sentences and table columns intact). Where a row's value is my own arithmetic (a sum of Census unit columns, a year-ago level implied by a bps change), the notes say so.

Three brokerages measure three different office and industrial universes, and the gaps are large. Never splice one publisher's Q3 2025 onto another's Q3 2026.

## The short version

Q3 2026 first, Q3 2025 second where the publisher gives it. "Restated" means the Q3 2025 number printed in the Q3 2026 report, which is the one to use for a year-over-year change.

| Type | Geography | Kidder Mathews (CoStar data) | CBRE | Cushman & Wakefield |
|---|---|---|---|---|
| Office vacancy | LA County | 16.4% direct (15.9% restated); total 17.7% | 25.3% overall (24.8%); direct 23.2% (22.3%) | 23.2% overall (+80 bps YoY); direct 21.3% |
| Office availability | LA County | 19.3% (20.0%) | 30.0% (30.3%) | n/a |
| Office asking rent, $/sf/mo FSG | LA County | $3.50 direct ($3.49) | $4.07 ($4.09) | $3.70 (+2.8% YoY) |
| Office net absorption, Q3 | LA County | +235,290 sf (−548,995) | −155,000 (−709,000 restated) | −432,758 (+326,014) |
| Office under construction | LA County | 2.31 msf (2.8 msf) | 1.7 msf (2.3 msf) | 1.90 msf |
| Office vacancy | Orange County | 11.5% direct (12.3%); total 12.4% | 12.1% (14.8%) | 14.2% (−280 bps YoY) |
| Office asking rent | Orange County | $2.98 ($2.78) | $3.00 direct | $2.93 (+1.1% YoY) |
| Industrial vacancy | LA County | 6.0% direct (5.7%); total 6.7% | 5.0% (−20 bps YoY) | 4.3% (−10 bps YoY) |
| Industrial asking rent, $/sf/mo NNN | LA County | $1.36 ($1.41) | $1.19 direct | $1.33 ($0.02 below year-ago) |
| Industrial net absorption, Q3 | LA County | −686,385 sf | +1.91 msf (−2.40 msf) | −1,473,242 sf |
| Industrial under construction | LA County | n/a | 4.48 msf (5.36 msf) | 6.5 msf |
| Industrial vacancy | Orange County | 6.0% direct (5.5%); total 6.7% | 5.5% | 6.0% (+110 bps YoY) |
| Industrial asking rent | Orange County | $1.45 ($1.48) | $1.51 | $1.47 (−3.4% YoY) |
| Multifamily vacancy | LA County | 5.4% (5.2%) | 4.8% (95.2% occupied) | n/a |
| Multifamily rent, $/unit/mo | LA County | $2,323, +0.6% YoY | $2,913 | n/a |
| Multifamily under construction / delivered | LA County | 24,325 units UC (27,324); 10,643 delivered Jan to Sep (13,038) | 4,165 delivered in Q3 | n/a |
| Multifamily vacancy | Orange County | 3.9% (3.9%) | 3.5% (96.5% occupied) | n/a |
| Multifamily rent | Orange County | $2,762, +2.4% YoY | $2,999 | n/a |
| Retail | LA County | 5.7% vacancy (5.6%); $2.75 ($2.82) | 6.1% availability; $2.87 NNN | n/a |
| Retail | Orange County | 3.3% vacancy (3.5%); $2.77 ($2.65) | 3.7% availability; $2.69 NNN | 3.7% vacancy (−50 bps YoY); $2.68 NNN (+5.5%) |

Other series, one publisher each:

| Series | Value |
|---|---|
| Hotels, STR "Los Angeles, CA" market, Q3 2026 (C&W table) | Occupancy 75.9% (+4.5%), ADR $211 (+6.7%), RevPAR $160 (+11.5%) |
| Hotels, STR "Orange County, CA" market, Q3 2026 | Occupancy 77.9% (+3.3%), ADR $232 (+5.8%), RevPAR $181 (+9.3%) |
| Hotels, City of LA Tourism Marketing District, Jan to Sep | Occupancy 74.5% (72.7%), ADR $219.53 ($204.77), RevPAR $163.52 ($148.92) |
| Zillow ZORI multifamily, LA-Long Beach-Anaheim MSA | $2,665 in Sep 2026, +1.2% YoY (Oct: +1.5%) |
| Census BPS units authorized, LA County | 2025: 22,250 (10,633 in 5+ unit buildings). 2024: 19,809. Jan to Sep 2026: 22,318 vs 15,523 a year earlier; 5+ units 13,550 vs 6,717 |
| Census BPS units authorized, Orange County | 2025: 4,992 (1,892 in 5+). 2024: 6,972. Jan to Sep 2026: 4,619 vs 4,018; 5+ units 2,363 vs 1,724 |
| City of LA new-building permits issued (LADBS, Bldg-New) | 2020: 3,073; 2021: 3,518; 2022: 4,629; 2023: 3,836; 2024: 3,679; 2025: 4,424; 2026 to Nov 13: 4,083 vs 3,815 same period 2025. Apartment permits 212 vs 128 |

The one clear supply signal: LA County multifamily permitting nearly doubled in 2026 (5+ unit units authorized up 102% through September) while Orange County's rose 37% from a low base. LADBS apartment permits in the City point the same way. Deliveries are still falling (Kidder: 10,643 LA units delivered Jan to Sep 2026 vs 13,038 a year earlier), so at typical two-to-three-year build times the new permits become supply in 2028 or later, not next year.

## Which publisher to use for what

**Office levels for a CMBS loan: CBRE.** Its survey is Class A and B multi-tenant buildings of 30,000 sf or more, excluding owner-user and medical (216.9 msf in LA). That is closest to the buildings in a conduit or SASB pool. It also prints availability and a full submarket table. Its Q3 2025 numbers come from a differently scoped report (Greater LA, which adds Ventura), so use the "Total L.A. County" row of that report, and note that CBRE's Q3 2026 text restates Q3 2025 absorption from −666,011 to −709,000 and Q3 2025 construction from 1.69 msf to 2.3 msf.

**Office submarket trend and Long Beach: Kidder Mathews.** Kidder republishes CoStar's full LA inventory (377 msf, all classes, every building size) with the same columns in both years, and it is the only source here that breaks out Downtown and Suburban Long Beach. Its vacancy is direct only. Use the restated 3Q25 column in the 3Q 2026 report for changes, because CoStar revises history: LA direct vacancy for 3Q25 went from 16.0% as published to 15.9%, and the LA inventory shrank from 390.1 msf to 377.0 msf.

**Cushman & Wakefield as the cross-check.** Its LA office universe (210.5 msf) is close to CBRE's in size, but its regions are coarser (LA North, LA South) and the PDF does not define them. I read LA North as the San Fernando Valley area and LA South as South Bay plus Long Beach; that mapping is unverified. Only the current edition is linked, so its year-ago values are the ones stated in the Q3 2026 text.

**Industrial: CBRE for level, all three for direction.** The three disagree on the sign of LA absorption (below), so a case study should quote a range or say which survey it uses.

**Multifamily: Kidder for change, CBRE for level.** CBRE Econometric Advisors counts market-rate units in 5+ unit buildings, which matches institutional collateral and gives a higher rent ($2,913 vs $2,323 in LA). CBRE prints no market-level year-over-year rent change. Kidder (CoStar) gives the YoY change and the construction pipeline in both years. Zillow's multifamily ZORI is a third, monthly read on rent growth and covers LA and Orange together.

**Retail: CBRE availability, Kidder vacancy.** C&W covers Orange County shopping centers only; it has no public LA County retail MarketBeat. Kidder does not state whether its retail asking rent is NNN; CBRE and C&W say NNN.

**Lodging: STR via the C&W hospitality table.** It is the only county-level quarterly source found. The LA Tourism figures cover the City's Tourism Marketing District hotels and are year-to-date, so they are not the county.

**New supply: Census BPS for units, LADBS for City permit counts.** They measure different things. BPS counts housing units authorized across every jurisdiction in the county (imputed for non-reporters). LADBS counts permits issued for new buildings in the City of LA, residential and commercial, and a single apartment permit can carry hundreds of units.

## Conflicts between publishers

- **LA office vacancy spans 9 points.** Direct vacancy is 16.4% (Kidder), 21.3% (C&W) and 23.2% (CBRE). Overall is 17.7%, 23.2% and 25.3%. The cause is the universe: CoStar's count includes small, Class C and owner-occupied buildings that are mostly full. None of the three is wrong.
- **LA office absorption has opposite signs.** Q3 2026: Kidder +235,290 sf, CBRE −155,000, C&W −432,758. Q3 2025 flips the other way: C&W +326,014 against Kidder −548,995 and CBRE −666,011. Downtown LA alone: Kidder +398,252, CBRE +85,000, C&W −299,454 for its CBD.
- **LA office rent direction.** Year over year Kidder is flat ($3.49 to $3.50), C&W is up 2.8% ($3.70) and CBRE is down 0.7% ($4.07).
- **Orange County office moved in opposite directions in the quarter.** CBRE has vacancy falling 130 bps to 12.1%; C&W has it rising 30 bps to 14.2%. Absorption: CBRE +300,000, Kidder +95,112, C&W −8,765. All three agree vacancy is lower than a year ago.
- **LA industrial absorption.** CBRE +1.91 msf, Kidder −686,385, C&W −1.47 msf. Vacancy ranges from 4.3% (C&W) to 6.0% direct (Kidder), and Kidder has it up 30 bps on the year while CBRE and C&W have it down. CBRE's $1.19 asking rent is a direct rate; C&W ($1.33) and Kidder ($1.36) are higher.
- **Orange County industrial absorption.** Kidder +366,128 and CBRE +280,000 against C&W −849,136. C&W's own PDF shows 465,446 and 534,944 side by side in the construction columns of its totals line; I used the 534,944 in its text.
- **Orange County retail absorption.** C&W +156,404 against CBRE −114,000 and Kidder −141,281.
- **Multifamily rent level.** CBRE's market-rate figure runs $590 a month above Kidder's in LA and $237 above in Orange County. Pick one and stay with it.
- **CoStar restatements inside Kidder.** Orange County office direct vacancy for 3Q25 was 11.8% when published and 12.3% a year later; OC multifamily vacancy 3.6% then 3.9%; LA multifamily under construction 25,884 then 27,324 units; LA multifamily deliveries Jan to Sep 2025 11,993 then 13,038. The CSV keeps both, labelled.

## Smaller cautions

- Kidder's LA and OC retail PDFs were created on 2026-09-24 and its LA office PDF on 2026-09-30, before or at the quarter's close, so those Q3 figures may be early cuts.
- CBRE's LA office cover tile calls $4.07 a "Direct Lease Rate"; its table calls the same number "Avg. Total Asking Rate". Page 1 says the pipeline is 1.65 msf, page 3 says 1.7 msf.
- Kidder's LA and OC multifamily tables label construction rows "(SF)" in the 3Q 2025 edition; the values are units.
- LADBS's DU_CHANGED field is blank on about half of new-building permits, so its unit sums (5,965 on 2025 apartment permits, 9,342 in 2026 to date) undercount and should not be compared with Census units.
- C&W's hospitality table extracts with rows misaligned in the layout text. The LA values were read from the column-order extraction and checked by arithmetic (75.9% x $211 = $160; 1.045 x 1.067 = 1.115).

## What I could not find

- **C&W Q3 2025 MarketBeats** for LA office, LA industrial and the OC reports. The pages link only the current edition and the Internet Archive has no captures of them. Year-ago C&W figures are limited to what the Q3 2026 text states.
- **CBRE Q3 2025 figures** for industrial, OC office, multifamily and retail. The Q3 2025 page addresses redirect to CBRE's search page. Year-ago CBRE values come from the Q3 2026 text where it gives them.
- **LA County hotel levels for Q3 2025.** Only the year-over-year changes are public in the C&W table. CoStar's own LA hotel article returned 403 to a script, and the Matthews Q3 2026 LA hospitality page does not exist (404). Visit Anaheim's figures were not checked.
- **C&W LA County retail and multifamily, and OC multifamily.** C&W does not publish them on its public MarketBeat pages.
- **Lee & Associates, NAI Capital, Colliers, JLL, Avison Young and Marcus & Millichap** were not used. Three brokerages already disagreed enough to bracket each number, so I did not open their reports or test whether they are gated.
- **Census BPS October 2026** (co2610y.txt) was not yet posted on 2026-11-16.
- **Orange County city permit data.** Only the Census county totals were collected; no OC city open-data portal was checked.

## Access notes

Nothing gated was met. CBRE's figures pages and C&W's MarketBeat pages link their PDFs directly, and Kidder's PDFs sit at stable addresses. No forms were filled and no accounts were created. Every scripted request used the User-Agent `mwall-research/0.1`. The City of LA counts come from the public Socrata API (dataset pi9x-tg5x, no app token), and the exact SoQL queries are in the `url` column.
