# Gate 5 sign-off: website

Signed off 2026-11-16. The site is the static build of `site/` (Vite, plain JavaScript and d3), fed by the JSON files that `python -m mwall site` and `python -m mwall la` write to `site/public/data/`. It has eight pages: home, the wall, the loans explorer, the tear sheet, the scenario lab, Los Angeles, method, and data and code. Decisions D060 to D062. The design brief is `site/DESIGN.md`.

## Checklist (SOP section 15)

| item | result | evidence |
| --- | --- | --- |
| Chart numbers reconcile to output tables by an automated sample check | PASS | `tests/test_site.py`: the headline numbers, every column of the maturity wall (balance and gap by bucket), the gap by type and the scenario totals are recomputed from `scores.parquet` and `underwriting.parquet`; 200 random loans in `loans.json` match the output tables (balance, gap, value, bid, distress probability); the Los Angeles totals match the subset of the underwriting table. |
| JavaScript scenario math matches Python for 50 random loans | PASS | `tests/test_site.py` runs `site/src/lib/engine.js` in Node on 50 random loans across the three scenarios and five rate and cap-rate shifts; every dollar output matches the Python engine to the cent and every rate to 1e-9 (over 1,000 comparisons). Summed over all 10,502 loans with NOI, the browser engine reproduces the published base-case gap of $46.7B. |
| Works at phone width; keyboard navigation works; color is never the only signal | PASS | At 390px every page renders with no horizontal overflow. axe-core 4.14.1 (WCAG 2.1 A and AA rules) finds no violations on any page at 1280px or 390px (16 runs). A keyboard walk of 40 tab stops per page starts at the skip link, and every stop has a visible focus ring and an accessible name. Loan status always pairs an icon with a word; risk bands, property types and scenarios carry legends and labels; every chart has a table view. |
| Every link resolves; every score, bid and return carries its scenario and disclaimer | PASS, with exceptions listed below | Rendered-page crawl of 23 pages (the seven main pages, the 404 page, 11 sampled tear sheets and the five case-file tear sheets): 1,606 links. All 96 internal links return 200 and every tear-sheet id exists. SEC EDGAR refuses scripted requests without a declared contact, so EDGAR links are checked against the filings the pipeline downloaded instead: every accession on every tear sheet (more than half a million) matches a downloaded filing of that trust. Of 586 external links, 572 resolve to a script. A banner on every page showing scores, bids or returns says they are model estimates and not investment advice; a footer says so on every page; every gap and bid names its scenario. |

**Links that don't resolve yet (14):**

- Four need publication: the GitHub repository and two files in it (private until Gate 6), and elidellabitta.com (the personal site isn't live). Recheck at Gate 6.
- Ten refuse scripted requests: the California Legislature's code and bill pages (6), commercialsearch.com (1), insideselfstorage.com (2), and the Internet Archive (1). Each was fetched and saved by the research step that cites it (or, for the Internet Archive copy, by the research step that found it); recheck by hand at Gate 6.

## Speed on a mid-range phone (SOP 14)

Lighthouse 13.6, mobile profile (an emulated mid-range Android phone, 412px wide, 150 ms round trips, 1.6 Mbps), on the production build:

| page | performance | accessibility | best practices | SEO | first paint | largest paint | blocking time | bytes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| home | 100 | 100 | 100 | 100 | 1.3 s | 1.3 s | 0 ms | 104 KB |
| the wall | 100 | 100 | 100 | 100 | 0.8 s | 0.8 s | 0 ms | 103 KB |
| loans | 96 | 100 | 100 | 100 | 0.9 s | 0.9 s | 220 ms | 1,075 KB |
| tear sheet | 100 | 100 | 100 | 100 | 0.9 s | 0.9 s | 0 ms | 162 KB |
| scenario lab | 90 | 100 | 100 | 100 | 0.9 s | 0.9 s | 410 ms | 1,573 KB |
| Los Angeles | 100 | 100 | 100 | 100 | 0.9 s | 0.9 s | 0 ms | 384 KB |
| method | 100 | 100 | 100 | 100 | 0.9 s | 0.9 s | 0 ms | 145 KB |

The headline numbers and the hero chart render from a 30 KB summary file. The explorer and the lab load the full loan table on demand.

## SOP 13: the Los Angeles case study

| acceptance item | result |
| --- | --- |
| The market definition is documented and every included property has a county code | PASS: CBSA 31080 (Los Angeles and Orange counties, OMB July 2023 delineation, confirmed against the delineation file); all 640 market loans carry a county FIPS code from the geocoder; 1,006 California loans fall outside. |
| The selection rule is committed before the case files exist | PASS: `docs/la/selection.md` and `docs/la/candidates.csv` (640 rows) were committed in b522998 before any case file was drafted. A data fix made after that commit (D059) doesn't change the picks. |
| Every number in the memo traces to a data cell or a cited source | PASS: `docs/la/memo.md` and the page are generated by `python -m mwall la` from templates whose numbers are filled from the published outputs and from rows of `config/research/la_market_sources.csv` (371 rows, every quote checked against the saved page). |
| Each local override cites its official source and the date it was checked | PASS: `config/la_overrides.csv` (Gate 4). |
| A second reader who did not build the model has reviewed the memo | OPEN: the author is lining up a reader; this is part of Gate 6. |

## Found and fixed at this gate

- Three-month financials read as a full year (D059): found in a case file and fixed in the underwriting inputs; Gate 4 figures restated.
- Measure ULA counts in the Gate 4 report mislabeled loans paying 4% as paying 5.5%; the report's thresholds now include the 2% base selling cost.
- Mixed use and other shared one color in the type legend; charts now fold them into one category.
- The precision-recall chart's first points (a handful of loan-months) made precision look like 100%; the curves now start at 1% recall.
- Chart marks were tab stops without names (up to 99 on one chart); keyboard users now use the table view, and scrolling tables are focusable regions.
