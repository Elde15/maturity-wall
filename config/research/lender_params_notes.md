# Lender sizing parameters: source notes

Companion to `lender_params_sources.csv` (198 data rows). "Row N" below means the Nth data row, so row 1 is the first line after the header. Every value in the CSV was copied from page or PDF text I fetched on 2026-11-13 and pulled out with a local text extractor, not from a summarizer. Curly quotes, en and em dashes, and cp1252 mojibake in the source text were normalized to plain ASCII, and `...` marks a cut. Rows whose number is not printed in the source say `DERIVED` in the notes. Two rows read chart data labels and say `MEDIUM CONFIDENCE`.

## How to read the model inputs

`P_max = min(LTV_max * Value, NOI / (DSCR_min * k), NOI / DY_min)`

The structural limits below (LTV, DSCR, DY, amortization) come from published floors and ceilings: term sheets, supervisory guidance and refinance stress tests. The `avg_*` rows describe loans that actually closed. They sit well inside the floors and shouldn't be used as minimums. Trepp's 2019H2 conduit average debt yield was 14.4% (row 81) when the published floors were 9 to 10%.

## Recommended base values

The base case is a CMBS conduit takeout, since the loans being scored are CMBS loans. LTV, DSCR and DY come from a published conduit term sheet (Greystone) and the OCC handbook. Amortization uses the OCC's property-type guidance because it's the only property-specific, pre-2017 source I found. Agency multifamily terms are listed as a sensitivity.

| property | ltv_max | dscr_min | dy_min | amort_years | spread_bps (vs 10-yr UST) |
|---|---|---|---|---|---|
| multifamily | 75 | 1.25 | 9.0 through 2024; 8.25 for 2025-26 | 30 | CBRE multifamily series |
| office | 75 | 1.25 | 10.0 through 2024; 12.5 for 2025-26 | 25 | CBRE commercial series + 40 (derived) |
| retail | 75 | 1.25 | 10.0 through 2024; 9.0 for 2025-26 | 25 | CBRE commercial series + 0 (derived) |
| industrial | 75 | 1.25 | 10.0 through 2024; 9.0 for 2025-26 | 25 | CBRE commercial series - 20 (derived) |
| lodging | 75 | 1.30 | 12.0 | 20 | CBRE commercial series, no hotel premium sourced |
| self_storage | 75 | 1.25 | 9.0 through 2024; 8.25 for 2025-26 | 25 | CBRE commercial series, no premium sourced |
| mixed_use | 75 | 1.25 | 10.0 | 25 | CBRE commercial series |

Where each number comes from:

**ltv_max = 75 for every type.** Greystone's CMBS term sheet sets "75% of appraised value" for multifamily, retail, office, hotel, industrial, mixed-use and self-storage (row 26). The 2025 and 2026 versions keep it. Fitch's 2022 refinance stress test uses the same 75% cap (row 103), and an older self-storage source puts CMBS leverage at "up to 75 percent" (row 42). The supervisory ceiling of 85% (row 1) is an outer bound, not market practice. Multifamily agency sensitivity: 80% (Freddie Mac rows 10 and 14; Fannie Mae via lenders, rows 16 and 19). For lodging, the 2021 hotel lender survey average max LTV was 66.2% (row 54), so 75 is generous for hotels during COVID.

**dscr_min = 1.25.** Greystone CMBS (row 27), Fitch's refinance test for an amortizing loan (row 101), Freddie Mac (rows 11 and 15), Fannie Mae via lenders (rows 17 and 20), and a 2013 self-storage bank floor (row 45) all agree. **Lodging gets 1.30**, from HVS's "1.30x to 1.50x" (row 49) and the 2021 hotel survey average of 1.3x (row 53). Use 1.50 as a stress case. If the model ever sizes a full-term interest-only refinance, Fitch tests those at 1.40x (row 102).

**dy_min** is time-split because the one property-type floor schedule I found changed in 2025:
- Through 2024: multifamily 9 (row 28), self-storage 9 (rows 29 and 41), office, retail and industrial 10 (rows 30, 31 and 32), lodging 12 (row 33). The 10% figure also matches the OCC handbook's "10 percent is generally considered a minimum acceptable yield" (row 3), which was in force from 2013 to 2022. That's the best pre-2017 anchor.
- 2025-26: multifamily and self-storage 8.25 (rows 34 and 35), retail and industrial 9.0 (rows 37 and 38), office 12.5 (row 36), lodging 12.0 (row 39).
- Mixed use: 10 from the OCC general minimum (row 3). No source gives a mixed-use floor.
- Lodging alternative for 2017-2019 snapshots: 9.7, the 2019 hotel lender survey average (row 51). The 2021 survey's 7.4 (row 52) is COVID-distorted, so don't use it.

**amort_years.** OCC handbook (Version 1.0 2013, 1.1 2017, same text in 2.0 2022): multifamily up to 30, office/retail/industrial generally 25, hotels generally not more than 20 (rows 4 to 8, row 9). Self-storage 25 comes from bank practice of "20 or 25 years" (row 44). Mixed use 25 is by analogy to office/retail and has no direct source. Sensitivity: CMBS lenders offer "amortizations up to 30 years" (row 43), and agencies amortize multifamily over 30 (rows 13, 18 and 21). For hotels, HVS reports banks offering 20 to 25 years (row 50).

**spread_bps**, quoted over the **10-year Treasury**. CBRE's Q1 2024 release defines its series as "Credit spreads between the 10-year Treasury yield and seven-to-10-year fixed-rate permanent commercial loans with loan-to-value ratios of 55% to 65%" (row 143). The 2016 report says "equivalent-term U.S. Treasury rate" (row 105 notes). CRED iQ also quotes over the 10-year (row 77).
- Multifamily: CBRE multifamily series, rows 106, 110, 111, 114, 116, 118, 120, 122, 124, 126, 128, 130, 132, 134, 136, 138, 140, 142, 144, 147, 149, 151, 153, 155, 157, 160, 162.
- Commercial (non-multifamily, all types pooled): CBRE commercial series, rows 105, 107, 108, 109, 112, 113, 115, 117, 119, 121, 123, 125, 127, 129, 131, 133, 135, 137, 139, 141, 143, 145, 146, 148, 150, 152, 154, 156, 158, 159, 161.
- Gaps: 2016Q2 to 2018Q1 and 2018Q3 to 2020Q1 have no printed CBRE level. The only fill points are DERIVED from printed changes: rows 107, 108, 110 and 112. I'd carry the last observed value forward rather than interpolate across the March 2020 break.
- Base change: from Q2 2026 CBRE switched to "fixed-rate, five-to-10-year permanent loans" (rows 159 to 162). On the new base, Q3 2025 restates to about 220 (commercial) and 174 (multifamily), against 197 and 141 published on the old base. Use the old-base rows through 2026Q1 and treat 2026Q2 onward as a new series.
- Property premiums over the CBRE commercial series are DERIVED by comparing CRED iQ's property-type spreads with the CBRE commercial level for the same period. For 2026Q1, CBRE commercial was 181 (row 158) against CRED iQ office 220, retail 176 and industrial 162 (rows 77, 75 and 73). For Q2 2025 it was 193 (row 152) against 237, 193 and 174 (rows 78, 76 and 74). That gives office about +40, retail about 0, industrial about -20, stable across both dates. Only two dates support it, both after 2024, so applying it to 2017 is an assumption.
- Lodging and self-storage: no Treasury spread found. The only pricing is mid-2025 CMBS coupons: hotel 7.3%, self-storage 6.47%, office 6.61%, multifamily 6.5% (rows 95, 94, 91 and 90). That points to a hotel premium of very roughly +70 bps over office and none for self-storage, but it's one CMBS sample and I haven't put it in the table as a spread.
- Life companies price tighter: about 170 against about 250 for CMBS conduit in April 2026 (rows 69 and 70). ACLI life company spreads read off chart labels give 216 for 2023 and 187 for 2025 (rows 64 and 65, medium confidence).

## Sources used

- **Regulatory and supervisory:** 12 CFR 34 App. A, 2017 CFR edition from govinfo; OCC Comptroller's Handbook, CRE Lending, v1.1 (2017) and v2.0 (2022).
- **Agency:** Freddie Mac's own fixed-rate term sheets, January 2019 (Wayback) and April 2026. Fannie Mae DUS terms via lender term sheets from NewPoint (2024) and Greystone (2025). HUD Mortgagee Letter 2025-03 for FHA 223(f).
- **CMBS term sheets:** Greystone CMBS fixed-rate, April 2024 (Wayback) and March 2026, with an identical May 2025 version.
- **CBRE Lending Momentum:** CBRE press releases 2023Q4 to 2026Q3. Archived cbre.us and cbre.com "U.S. Lending Figures" pages 2019Q3 to 2023Q4 via the Wayback Machine. MBA NewsLink and Commercial Property Executive coverage for 2016 to 2019.
- **Market data:** CRED iQ property-type spreads (April 2026 post) and Commercial Observer CRED iQ columns (June 2025, June 2026). Trepp conduit averages via REBusinessOnline (2020). Philadelphia Fed WP 23-27. Fitch refinance test via Connect CRE. Trepp's 8% debt-yield risk threshold via CRE Daily.
- **Life companies:** ACLI averages via CorAmerica (2016) and Nassau CorAmerica (2024, 2026) white papers. NAIC primer (2019). CBRE/IREI life company LTVs.
- **Lodging and self-storage:** HVS (April 2026), RobertDouglas 2021 Hotel Lender Survey, MBA NewsLink on the 2019 survey, Inside Self Storage (Dec 2013, Nov 2018).

## Gated or blocked (skipped, no account or form used)

- **ACLI Commercial Mortgage Commitments (CMC-Q):** paid bulletin ($600 per quarter on ACLI's order form). This is the real life-company spread and LTV/DSCR-by-property-type series. I used the secondary citations above instead.
- **Fannie Mae Form 4660 and multifamily.fanniemae.com term sheets:** 403 to automated fetch. The Guide sections I could fetch only say "Per Form 4660", so Fannie values come from lender reproductions.
- **eCFR** redirected to a bot check, so I used the govinfo 2017 CFR PDF.
- **Returned 403:** S&P Global conduit updates, GlobeSt 2017 articles, Multifamily Dive, STR and TravelDailyNews hotel-survey releases, Hotel Management, and the Regions Fannie term sheet.
- **Other failures:** CBRE APAC research page (530), Lument Fannie PDF (served HTML), HUD MAP Guide PDF (damaged file).
- **Not reached in the time available:** Moody's, KBRA, Morningstar DBRS conduit-metric reports (KBRA search only surfaced deal-level releases), MSCI/RCA, Chatham, Newmark, JLL, Walker & Dunlop, Berkadia and Marcus & Millichap. The Fed SLOOS is directional only and I didn't use it.

## Conflicts and data-quality flags

1. **CBRE base change in Q2 2026.** See spreads above. CBRE's LTV reporting also moved from an all-loan average (e.g. 64.1% for Q4 2024, row 174) to separate commercial and multifamily averages (e.g. rows 178 and 179). Those aren't comparable.
2. **CBRE Q3 2026 DSCR.** The press release says 1.32 "from 1.34", but MBA NewsLink says "from 1.38", and DY "held steady at 9.5%" against "fell to 9.5% from 9.9%" (rows 183 and 184).
3. **CBRE Q4 2024 LTV.** 64.1% in the Q4 release, restated as 63.0% in the Q1 2025 release (row 174).
4. **CBRE Q1 2024 loan constant.** 6.92% described as "a 50 bps decline from Q4 2024", but the prior quarter was 6.72% (rows 170 and 169). The source is internally inconsistent.
5. **Freddie Mac terms moved.** For 5 to under-7-year loans: 75% / 1.30x in 2019, 75% / 1.25x in 2026. Full-term IO minimum DCR: 1.35x in 2019, 1.25x in 2026 (rows 10 and 14 notes). A 2022 NewPoint reproduction (not in the CSV) shows 80% / 1.25x for the 5 to under-7-year band, which disagrees with both.
6. **Greystone DY floors moved in 2025.** Office went up from 10 to 12.5, multifamily and self-storage went down from 9 to 8.25, retail and industrial went down from 10 to 9. This is a single lender, so the schedule may reflect its appetite rather than the market's.
7. **Self-storage DY** bounces between 9% (2013, row 41; 2024, row 29) and 8.25% (2018, row 47; 2025-26, row 35).
8. **Hotel DY:** Greystone 12% against the 2019 survey average of 9.7% against 7.4% in the 2021 COVID survey. **Hotel DSCR:** Greystone 1.25x for all types against HVS 1.30x to 1.50x. **Hotel amortization:** OCC 20 or less against HVS 20 to 25.
9. **OCC dropped its 10% debt-yield number** in Version 2.0 (2022). Row 3 is dated to the period it was in force.
10. **Life company LTV:** ACLI averages of 58 to 63% (rows 56 to 62), CBRE "up to 65%" (row 67), NAIC "usually 60% to 70%" (row 66). These are averages and quotes, not hard caps.
11. **HUD 223(f)** (rows 22 to 25) is a fully amortizing FHA product with an 85-87% cap. It's listed for completeness. It isn't a realistic takeout for most CMBS multifamily loans because of HUD processing times.

## What I could not verify

- **Treasury spreads for lodging, self-storage and mixed use.** None found. They're priced off the CBRE commercial series here, with no premium.
- **CBRE spread levels for 2016Q2 to 2018Q1 and 2018Q3 to 2020Q1.** The four DERIVED rows are arithmetic on printed changes. The Q2 2018 quarter (row 109) is inferred from the article date, because the sentence doesn't print the year.
- **CBRE multifamily Q1 2026 level.** A search snippet said 136 bps, but I couldn't confirm it in fetched text, so it isn't in the CSV.
- **ACLI chart labels** (rows 64 and 65). I read them as final-year CML spreads, and that needs a visual check of the chart.
- **Fannie Mae's own Form 4660 values.** The 80% / 1.25x rows come from lender reproductions.
- **A mixed-use debt-yield floor and mixed-use amortization.** Both are set by analogy.
- **Full-term interest-only share by year.** Only one full-term split was found (23.3% in 2021Q3, row 195). The other io_share rows are partial plus full IO combined.
