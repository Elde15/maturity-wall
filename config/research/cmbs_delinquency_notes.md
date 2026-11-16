# CMBS delinquency and distress rates: sources, definitions, gaps

Companion to `cmbs_delinquency_sources.csv` (same folder). 1,494 rows, accessed 2026-11-16. Every number was read from a page fetched in this session. Raw pages are saved in the session scratchpad at `research_raw\delinquency\` (506 `.html` pages, 32 CRED iQ PDFs, and a `.txt` companion for each). The `quote` column matches the `.txt` companion verbatim, and the `notes` column names that file ("saved as ..."). A check script confirmed all 1,494 quotes are present in their saved file and that each `rate_pct` appears in its quote.

## What was collected

| Publisher | stat | Rows | Months |
|---|---|---|---|
| Trepp | delinquency 30+ (incl. matured non-performing) | 546 | 2019-01 to 2026-10 |
| Trepp | special servicing rate | 572 | 2019-02 to 2026-10 |
| Trepp | seriously delinquent (60+ days, foreclosure, REO, non-performing balloon) | 5 | 2025-03 to 2025-08, overall only |
| CRED iQ | delinquency 30+ (CRED iQ) | 121 | 2021-09 to 2026-08 |
| CRED iQ | special servicing rate (CRED iQ) | 99 | 2021-09 to 2026-08 |
| CRED iQ | distress rate (CRED iQ) | 151 | 2021-09 to 2026-10 |

One row per publisher, stat, month and property group. Not collected on purpose: CMBS 1.0 vs 2.0+ splits, MSA-level rates, CRE CLO, agency and bank series.

### Where the Trepp numbers come from

Most TreppTalk monthly posts from September 2020 on embed an Infogram chart whose data is a 13-month table by property type (Overall, Industrial, Lodging, Multifamily, Office, Retail; the special servicing table adds Mixed-Use). I fetched each chart from `e.infogram.com/<id>` and rendered its data table to text. For each month and property type the CSV keeps one value, picked in this order:

1. The table in that month's own post (latest row): 844 rows.
2. The text of that month's own post: 124 rows (all of January 2019 to October 2020, plus months whose chart was missing or later edited).
3. The same month's row in the next available table, published later: 150 rows. The notes say "Restated value" and give the table's latest month, and `publication_date` is that later post's date.

So 2019 values are contemporaneous text, while property types not named in the 2019 and 2020 text come from tables published 12 or more months later.

`report_month` is the month the data describes. Trepp's delinquency post for month M goes up between the last day of M and about the 6th of M+1 (for example December 2024 was posted 2024-12-31 and October 2026 on 2026-11-02). The special servicing post for M goes up around the 6th to 15th of M+1. CRED iQ posts dated in the first days of a month carry the prior month's data.

## Definitions, as each publisher states them

**Trepp delinquency rate** (from "Breaking Down Trepp's CMBS Delinquency Report", 2023-06-29, saved):
- "Trepp includes the following six statuses in the Delinquency Rate, ranked in ascending severity." The list is 30, 60 and 90 days delinquent, Non-Performing Matured Balloon, Foreclosure and REO.
- "For Trepp’s calculations, we do not include loans that have missed their balloon payment but are current on interest as delinquent in our “headline” number."
- "The delinquency rate is calculated by dividing the delinquent balance by the total balance of loans outstanding." and "For the denominator, Trepp includes loans that have been defeased in the calculation."
- "In the Trepp calculations, we use loans from US CMBS conduit, single-asset, single-borrower, and certain large loan floating rate issues. It does not include CRE CLOs, GSE loans, cell phone tower deals, and other types of non-traditional CRE loans."

I found no published rate excluding defeased loans for 2019 to 2026, so there is no such row.

**Trepp seriously delinquent**: "The percentage of loans that are seriously delinquent (60+ days delinquent, in foreclosure, REO, or non-performing balloons) is now 6.85%..." (June 2025 post). This stat only appears in the March, April, June, July and August 2025 posts.

**Trepp special servicing rate**: the posts describe it as "The percentage of CMBS loans that were in special servicing" (April 2019 post) and "The percentage of loans with the special servicer" (2020 and 2021 delinquency posts). I found no fuller written definition on a public page.

**CRED iQ** (Conduit and SASB loans; "sample universe of $500+ billion in CMBS conduit and single-asset single-borrower (SASB) loans" in 2021 to 2023, "approximately $600 billion in private-label CMBS conduit and SASB loans" in October 2025):
- Delinquency: "the delinquency rate, equal to the percentage of all delinquent specially serviced loans and delinquent non-specially serviced loans".
- Special servicing: "equal to the percentage of CMBS loans that are with the special servicer (delinquent and non-delinquent)".
- Distress (DQ + SS): "...into an overall distressed rate (DQ + SS%) equals 7.81% of CMBS loans that are specially serviced, delinquent, or a combination of both." In 2025: "a composite metric capturing loans 30+ days delinquent (or worse) and those in special servicing". In the October 2026 post the wording becomes "delinquent, past maturity or with a special servicer".

## Definition changes and other traps

- **Trepp in April 2020.** Missed COVID payments sat "in grace period" or "beyond grace period" (status A/B) and were not yet counted as 30+ delinquent, so April 2020 (2.29%) understates the stress that showed up in May (7.15%). Trepp's April 2020 post says it is time "to throw out the old way of looking at the data".
- **Trepp tables get revised and sometimes contradict each other.** January 2021 industrial is 0.26% in the January 2021 table and 0.87% in every later one. October 2021 lodging, office and retail are 9.91/1.27/7.12 in the November 2021 table, 10.04/1.80/8.39 in the December 2021 to March 2022 tables, then back to the first figures. March 2022 lodging is 6.87% vs 6.75% later, and November 2025 retail is 6.45% vs 6.74% later. February 2020 multifamily is 1.60% in that month's text and 1.79% in later tables. The CSV keeps the first-published value in each case.
- **Trepp table errors handled in the build.** Row labels with typos were dated by position and flagged in `notes`; one selected row is affected (the January 2022 row in the January 2022 table is labelled "Jan-21"). The special servicing tables in the August to October 2022 posts skip November 2021. The column order changed in July 2025 (Mixed-Use moved ahead of Retail), and columns were mapped by header name, not position.
- **Infogram charts are live, not frozen.** The data is what the chart serves today. Four charts were later reused or updated: the March 2021 post's chart now shows November 2024 to November 2025, the May 2023 chart now ends in June 2023, and the April and June 2025 charts now show later months. For those months I used the post text, and `publication_date` for table rows is the date of the post whose month matches the chart's latest row.
- **Mixed-use** special servicing exists only from 2022-06 (first published in the June 2023 table). Trepp's delinquency tables have no mixed-use or self-storage column.
- **CRED iQ property-type stat changed in August 2023.** Through June 2023 the posts give property-type delinquency and special servicing rates. From August 2023 on they give property-type distress (DQ + SS) rates only.
- **CRED iQ title months.** Through November 2022 a report titled month M covers month M-1 (the "October 2022 Delinquency Report" says "during the September 2022 reporting period"). From the December 2022 report on, the title month is the data month. The CSV uses the data month.
- **CRED iQ precision** is two decimals through 2023, mostly one decimal from 2024 to July 2025, and two decimals again from August 2025.
- **CRED iQ text errors, handled as noted in the CSV.** The January 2023 post gives distress as both 4.84% and 4.71% (4.71% is the SS rate). The August 2023 post carries a stale "6.56%" sentence from June. The September 2023 post labels the September office figure "August". The January 2025 post's delinquency sentence repeats the distress numbers ("from 10.6% ... to 11.5%"), so January 2025 delinquency (8.9%) comes from the February post instead. Office and multifamily distress for November 2023 are restated in the December post far below the October figures. A September 2024 post ties an industrial spike to "one large SBLL portfolio", which suggests small-balance loans were in the universe at least then.
- **CRED iQ vs Trepp levels.** They are not the same measure. CRED iQ delinquency ran well above Trepp's in 2025 and 2026 (May 2026: CRED iQ 9.53% vs Trepp 7.55%). Treat them as separate series.

## Gaps

**Trepp delinquency.** The overall rate is present for every month from 2019-01 to 2026-10. By property type, every month from 2019-11 on has all five types. January to October 2019 come from post text only. Missing months by type: office 2019-01, 03, 04, 06, 07; retail 2019-06, 07; lodging 2019-01 to 03 and 2019-10; industrial 2019-02, 03, 05, 08; multifamily 2019-01, 04, 09. The only quarter with no value at all is lodging in 2019 Q1. There is no post for October 2025; its values come from the November 2025 table. For September 2025, retail is blank in its own chart and came from a later table.

**Trepp special servicing.** The overall rate is missing for 2019-01 (no post) and 2019-06 (no figure in the post). Office has nothing for 2019 Q2 and Q3; retail and lodging have nothing for 2019 Q3. Industrial and multifamily start in 2019-11. There is no post for May 2025 (taken from the June 2025 table), and the September and November 2024 charts return 404, so those months use post text plus a later table for the remaining types.

**CRED iQ.** There are no national figures before September 2021: the December 2020 to August 2021 reports and PDFs are MSA tables only. Missing overall months:
- delinquency: 2022-11, 2023-07, 2023-10, 2024-01 to 2024-04, 2026-06, 2026-09, 2026-10
- special servicing: 2023-10, 2024-01, 2024-04, 2024-07, 2026-02, 2026-06, 2026-08, 2026-09, 2026-10
- distress: 2026-06, 2026-08, 2026-09

Property-type coverage is patchy: office has 21 distress points, retail 17, multifamily 18, lodging 14, industrial 12, self-storage 8 and mixed-use 2. Twelve rows are prior-month values restated in a later post (flagged in `notes`). The October 2026 property-type distress table is the newest point; its "a year ago" column does not match CRED iQ's own October 2025 post (10.9% vs 11.41% overall), so only the current column was used.

## Skipped or unavailable

- **Gated, not opened.** Trepp's full monthly delinquency and special servicing reports ("Download the ... Delinquency Report" links go to `/instantly-access-cmbs-delinquency-report-...` HubSpot form pages). Also CRED iQ's "Start Free Trial", "Create Free Account" and loan "View Details" pages. No form was filled and no account was created.
- **Not gated, used.** CRED iQ report PDFs linked straight from public posts (`cred-iq.com/blog/wp-content/uploads/...`). The 2022 to 2023 PDFs repeat the blog text; the blog text was used.
- **404 on Infogram** (data gone): charts in the August, September and October 2020 delinquency posts, the September and October 2020 and the September and November 2024 special servicing posts. The August 2020 special servicing chart has no data table.
- **Not searched.** TreppTalk posts whose URL lacks "delinquen" or "special-servicing" (the list came from Trepp's sitemap), news coverage quoting Trepp, and the Internet Archive. Those are the places to look for the missing 2019 property-type values.
