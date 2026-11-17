# Cap rate benchmarks: sources, dates, gaps

Companion to `cap_rates_sources.csv` (same folder). Every number in the CSV was read from a fetched PDF, a fetched page, or the data table behind a CBRE chart, and the `quote` column holds the exact row or sentence it came from. Accessed 2026-11-13.

## The short version

CBRE published full national tables (every type, segment and class) through H2 2019. After that the public record thins out fast. There was no regular survey in 2020. From H2 2021 on, CBRE's public pages give only an all-property average plus scattered sector figures, and from H2 2022 on, the all-property average is the only national number that is public at all. National averages by property type for 2022H2 to 2026H1 are not on any CBRE page I could reach, and the full reports I found for those years give market-level ranges, not national averages. So the CBRE leg is strong for 2017-2019, patchy for 2020-2022, and all-property-only after that. The second source has to carry the by-type series from late 2022 onward.

## CBRE edition coverage

Dates are when the numbers became public, as best I could verify. "Adv." is CBRE's Advance Review, a short early release with the headline national figures, which came out three to six weeks before the full report.

| Edition | First public date used | What is public | Source of the numbers |
|---|---|---|---|
| H1 2016 | 2016-09-19 | Full national table (41 cells) | Full report PDF, re-hosted on tlcollect |
| H2 2016 | 2017-02-22 | Full national table | Full report PDF, re-hosted on tlcollect |
| H1 2017 | 2017-07-14 (Adv.), 2017-08-24 (final) | Headline averages only, 9 to 10 cells | LinkedIn copy of the Advance Review; World Property Journal |
| H2 2017 | 2018-01-31 (Adv.), 2018-02-27 | Headline averages plus LA market table | Advance Review PDF (Texas A&M re-host); Bisnow |
| H1 2018 | 2018-08-27 (headlines), 2019-02-27 (full table) | Headlines in press; full table only as the prior-period column of the H2 2018 report | Commercial Observer; H2 2018 PDF |
| H2 2018 | 2019-02-27 | Full national table plus LA | Full report PDF (tlcollect) |
| H1 2019 | 2019-08-20 | Full national table plus LA | Full report PDF (tlcollect) |
| H2 2019 | 2020-01-31 (Adv.), 2020-02-25 (final) | Full national table plus LA | Advance Review PDF; full report PDF (identical table) |
| H1 2020 | none | No regular survey. CBRE ran a COVID "Special Report" with no national averages and with hotels dropped | |
| H2 2020 | none | No regular survey (an October 2020 pricing-sentiment survey, qualitative) | |
| H1 2021 | none | Published 2021-08-13, but compared H1 2021 to H2 2019 by market and gave no national averages that I could find; full PDF not found | |
| H2 2021 | 2022-03-07 | Sector cap rates (CBD office, suburban office, industrial, multifamily, retail) from Figure 14 chart data; all-property average; LA Class A ranges | CBRE page chart data (Infogram); full PDF on cbre-ea.com |
| H1 2022 | 2022-08-24 | All-property; neighborhood and power-center retail; office by market tier (not national) | CBRE page chart data |
| H2 2022 | 2023-03-07 | All-property only | CBRE page chart data |
| H1 2023 | 2023-07-26 | Nothing national in numbers (chart is an unlabelled image); LA Class A ranges from the full PDF | Full PDF (tlcollect) |
| H2 2023 | 2024-03-05 | All-property (page text: "from 6.4% to 7%") | CBRE page text |
| H1 2024 | 2024-07-31 | Nothing national in numbers (unlabelled chart image) | |
| H2 2024 | 2025-02-12 | All-property (also restates H1 2024) | CBRE page chart data |
| H1 2025 | 2025-08-20 | All-property | CBRE page chart data |
| H2 2025 | 2026-02-10 | All-property; LA Class A ranges from the full PDF | CBRE page chart data; full PDF on CBRE's media server |
| H1 2026 | 2026-08-12 | All-property (also restates H2 2025) | CBRE page chart data |

Gated or missing: every CBRE page from 2021 on offers "Download the full report" through cloud.cbrecommunications.com, which is a form. I did not fill it in. Where a copy of the full report sat on an open URL (cbre-ea.com, a CBRE broker team folder on mediaassets.cbre.com, tlcollect, university and association sites) I used it. Not found anywhere open: the full H1 2017, H2 2017, H1 2018, H1 2021 and H2 2022 to H1 2026 reports except H1 2023 and H2 2025. The Internet Archive was offline when this was compiled, so archived copies of old cbre.us pages were not checked. That is the first place to look for the missing 2017-2018 full reports.

How publication dates were set, in order of preference:
1. The date printed on CBRE's own report page (all 2021-2026 editions; checked in the page HTML under the title).
2. Article metadata (`datePublished`) of press coverage that quotes the numbers: World Property Journal, Bisnow, Commercial Observer, Mile High CRE, IREI, MBA NewsLink.
3. For Advance Reviews that print only a month ("JANUARY 2018"), the last day of that month, because the exact release day was not verified. PDF metadata (created/modified) is recorded in the notes column as a lower bound, never used as the date itself.
4. One LA source (a CBRE MarketFlash email for H1 2017) has no date at all. Its `publication_date` is blank on purpose. Don't use it until it can be dated.

When a later edition restates an earlier period, the row carries the later edition's publication date, and the stat column says "restated" or "history as shown in ...". Those rows are for checking revisions and for backtests; they are not usable before their own date.

## Series breaks and revisions

1. **2009 to H2 2019: CBRE North America Cap Rate Survey (CBRE Research).** Market-level ranges from CBRE capital markets and valuation staff, averaged nationally across all tiers, for stabilized and value-add deals, by segment and class. Tables are consistent across these editions (same 41-cell layout every time, which the parser checks).
2. **2020: no survey.** The H1 2020 point in CBRE's later all-property chart is unstable across vintages: 6.3 (marked with an asterisk in the H2 2021 edition), 6.36%/6.4 (H1 2022), 6.47% (H2 2022), 5.62% (H2 2024, H1 2025), 5.60% (H1 2026). Treat 2020H1 as missing.
3. **H1 2021: methodology change.** CBRE compared H1 2021 to H2 2019 rather than H2 2020 and analysed the top 25 markets.
4. **H2 2021 on: "U.S. Cap Rate Survey", run by CBRE Econometric Advisors from H2 2022.** About 3,600 estimates from 200 to 250 professionals in 50+ markets. The public product is an all-property average and sentiment charts; the full report lists Class A market ranges. The H2 2021 Figure 14 sector values (industrial 4.72%, multifamily 4.36%) do not split infill/suburban or retail subtypes and are not defined on the chart, so I would not splice them onto the 2016-2019 segment series without a note.
5. **Advance vs final.** Advance Review figures can move in the final report. H1 2017 industrial was 6.69% in the Advance Review and 6.66% in the final; H1 2017 power centers were 7.31% in the Advance Review, while the H2 2017 Advance Review gives the H1 2017 base as 7.54%.
6. **Normal restatements are small.** Comparing each report's prior-period column with the previous report: H1 2016 to H2 2016, 11 cells restated, at most 3 bps; H2 2018 to H1 2019, 26 cells, at most 5 bps; H1 2019 to H2 2019, 12 cells, at most 2 bps.
7. **Back-history in the 2022+ charts is recomputed.** The H1 2022 retail chart reproduces the 2019 report values exactly, but its 2016 power-center values differ from the original reports (H2 2016: 6.99% in the chart vs 7.54% in the H2 2016 report). The all-property average for the same half-year also shifts by a few bps between vintages (H2 2025: 6.87% in the H2 2025 edition, 6.84% in H1 2026; H2 2022: 6.14%, 6.11%, 6.13% across three vintages).

## Los Angeles

LA values are market estimates, given as ranges ("S. CA: Los Angeles 4.50 - 5.50"), not averages. The CSV has Class A, B and C stabilized ranges (low and high as separate rows) for office CBD and suburban, industrial, neighborhood and power-center retail, high-street retail, infill and suburban multifamily, and full-service hotels for H2 2017, H2 2018, H1 2019 and H2 2019. For H2 2021, H1 2023 and H2 2025 only Class A stabilized ranges exist, and not every type has an LA row. The undated H1 2017 MarketFlash gives LA averages. PwC adds LA office rows for 2016 and 2017 (21 rows). The H1 2016 and H2 2016 reports have no LA rows in their extractable text.

Oddities to know: in the H2 2025 report the office downtown and office suburban LA rows are identical, and the H1 2017 MarketFlash power-center sentence is word for word the same as the Orange County version, which looks like a template carry-over.

## Second source

No single public series covers 2016 to 2026, so the second leg is a relay of five sources. A parallel research pass collected them; every row has its quote and URL like the CBRE rows.

| Source | Rows | Periods | Types | What it measures |
|---|---|---|---|---|
| PwC Real Estate Investor Survey | 264 (21 are LA office) | 2016Q1, Q2, Q4; 2017Q1 to Q4 (issues released 2017-03-15, 2017-06-15, 2017-12-15) | office CBD/suburban/secondary/medical, warehouse, flex, regional mall, power, strip, apartment, net lease, composite | Institutional investor survey, unleveraged going-in rates, average plus range low/high. Closest to CBRE. |
| MSCI Real Capital Analytics, quoted by NAR and by the Situs RERC/NAR/Deloitte "Expectations & Market Realities" reports | 67 | 2017Q3 to mid-2021, scattered | office, industrial, retail, multifamily, hotel, plus all-property | Transaction average, deals of $2.5M and up, often year-to-date. Moves with deal mix; thin in 2020. |
| NAR member survey (Market Trends; Trends & Outlook) | 108 | 2016Q4 to 2021Q1 | all five types, by class or subtype | Small deals, mostly under $2.5M. Averages through 2019Q2, medians from 2019Q3. |
| CoStar, as published monthly by NAR | 117 | late 2021 to Nov 2026 | office, multifamily, retail, industrial | Modelled all-quality market estimate. Runs one to two points above institutional surveys for office and industrial (office about 9% in 2025). |
| Integra Realty Resources (IRR) Viewpoint | 40 | 2021Q4 full table; mid-year points 2022 to 2026 | office CBD/suburban A/B, multifamily urban/suburban A/B, retail, industrial | Appraiser opinion survey, about 60 markets. Methodology closest to CBRE after 2017. |

Holes in the second leg: 2018 to mid-2021 has only RCA and NAR survey points. CoStar months 2022Q2, 2022Q4 and 2023Q2 to 2024Q1 are missing because NAR's files now return 404 and the Internet Archive was down; IRR covers 2023 with one mid-year point. Self storage has no national cap rate in any source found.

Gated: pwc.com (paid; the three 2017 issues used are subscriber copies re-hosted on an open appraiser-group URL, and that group's "Members Only" page was not touched), Situs RERC (subscription; its one public sample forbids quoting, so nothing was taken from it), MSCI/RCA US Capital Trends (form), IRR research library (free registration; only the openly indexed Viewpoint 2022 PDF, press releases and trade reprints were used). Not researched: Marcus & Millichap, NCREIF, Fed/FDIC, Newmark, JLL, Cushman & Wakefield, Altus.

Two things to decide before the model goes public. The PwC copies are stamped for subscribers and IRR's library sits behind registration, so redistributing those numbers in a public repo may need permission even though the files were reachable without a login. And some second-source dates are inferred: older PwC quarters seen only in later issues' "last quarter" columns carry the later issue's date; five NAR rows had month-only dates, which the merged CSV sets to month-end with a note; NAR's "Cap rate" lines cite only "NAR analysis of CoStar data" at page level, and the Dec 2021 and Jan 2022 rows are attributed to CoStar by analogy. Two conflicts are kept, not resolved: RCA 2019Q2 is 6.8% in one NAR report and 6.1% in a later one, and CoStar "as of Dec 18, 2021" is 4.9%/7.0% in one report and 5.1%/6.9% in the next.

## Recommended monthly benchmark

The rule that makes this leakage-proof is an as-of join on `publication_date`, never on `survey_period`.

1. **Scoring date.** For loan-month t, the information set is every row with `publication_date` strictly before the first day of t. Rows with a blank date (the undated LA MarketFlash) are excluded. That one rule handles the rest: a restated or back-filled value enters only from the date of the edition that printed it.
2. **CBRE leg by type.** For each type, take the row with the latest `survey_period` in the information set, and among those the latest `publication_date`. In practice the Advance Review value enters first and the final-report value replaces it a few weeks later. Use the class-blank (all classes) national average. The mapping I'd use for CMBS loan types: office to the mean of CBD and suburban unless the loan's location is known; retail to neighborhood/community center, power center for big-box anchored; multifamily to suburban, infill for urban core; lodging to CBD or suburban (all segments) by location; industrial to industrial. Self storage, healthcare and manufactured housing get no benchmark and should be flagged, not filled.
3. **Track staleness.** Store the age of the CBRE value in months since its survey period ended. By-type CBRE values stop at H2 2019 (in force from 2020-01-31), resume for office, industrial, multifamily and retail on 2022-03-07 (H2 2021 Figure 14, no segment split), get a retail update on 2022-08-24, and then stop for good. Lodging never updates after H2 2019. Without a bridge the CBRE leg would carry pre-COVID office values into 2026, which is useless.
4. **Bridge stale periods with type-specific changes, not levels.** Once the CBRE value is more than 12 months old, set CBRE-bridged(t) = last CBRE level + the change in a second-source series for the same type since that CBRE edition's date, using only second-source rows in the information set. Use CoStar-via-NAR changes from late 2021 on (monthly, four main types) and RCA/NAR changes for 2020 to 2021. Don't bridge with the CBRE all-property average: office widened far more than the average from 2022 on, and the average would understate it.
5. **Range, per the two-source rule.** For each type and month, low = min and high = max over the CBRE (or CBRE-bridged) value and the latest second-source level available as of t (PwC average for 2017, NAR/RCA for 2018 to 2021, IRR and CoStar from 2022). Value the property at the low and the high cap rate for the range and at the CBRE-based figure for the point. Ranges will be wide after 2022 because CoStar sits well above the institutional surveys. That width is real disagreement between sources; don't smooth it away.
6. **Checks to automate.** Assert that no row used has `publication_date` on or after the scoring date; assert that every loan type maps to a property group or gets flagged; log, per month and type, which source supplied the low, the high and the point, plus the CBRE age. Give 2020 a manual look: CBRE ran no survey, RCA's 2020 averages rest on few deals, and CBRE's own H1 2020 all-property point ranges from 5.60% to 6.47% depending on vintage.
