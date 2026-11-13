# Gate 2 hand check: 20 labels against the filings

Checked 2026-11-12. Twenty labels drawn with fixed seeds from `panel/tier1.parquet` (5 failed and 5 paid, seed 11) and from the representative rows of `panel/loan_month.parquet` (5 positive and 5 negative 12-month distress labels, seed 5; two positives redrawn with seed 13 after D045, see the end). For each, the loan's EX-102 records were read straight from `parsed/loan_period/` around the dates that decide the label. All 20 match the definitions in `docs/labels.md`.

## Tier 1: maturity outcome

| loan position | maturity | label | what the filings show |
| --- | --- | --- | --- |
| 1802215:7 | 2025-02-05 | failed | $50.0M; status B in January 2025, 5 (matured, not paying) in February and March, then 4 (matured, paying); still outstanding until a payoff in February 2026 |
| 1716187:16 | 2022-05-06 | failed | Maturity reported as 2022-05-06 at issuance, already moved to 2024-05-06 by November 2021; $12.9M still outstanding in July 2022. An extension granted ahead of maturity counts as a failure by design |
| 1872347:17 | 2026-06-01 | failed | $30.0M; status 4 in June 2026, then 5 from July, balance unchanged after the 90-day grace |
| 1827183:31 | 2025-12-06 | failed | $8.0M at status 3 (90+ days delinquent) for the six months before maturity, then 5 |
| 1705163:9 | 2022-05-06 | failed | $37.0M still amortizing in June and July 2022 at status 0, past maturity with no payoff code |
| 1690577:39 | 2026-07-01 | paid | Balance to zero with code 5 (full payoff at maturity) in the July 2026 filing |
| 1792905:35 | 2024-11-01 | paid | $7.0M to zero with code 5 in November 2024 |
| 1771501:15 | 2024-02-06 | paid | Zero balance from August 2023 with code 8 (payoff with penalty): eight months early, inside the 12-month window |
| 1707817:72 | 2022-06-11 | paid | Code 2 (payoff before maturity) one month before maturity |
| 1851115:24 | 2026-03-06 | paid | $19.3M to zero with code 2 five days after maturity, then code 5 |

## Tier 2: distress within 12 months of a performing month

| loan position | month T | label | what the filings show in the 12 months after T |
| --- | --- | --- | --- |
| 1803308:2 | 2024-10 | 1 | Status B then 1 in September and October 2025; special servicing transfer dated 2025-09-04, first reported September 2025 |
| 1732963:40 | 2022-11 | 1 | Special servicing transfer dated 2023-07-14, first reported August 2023 |
| 1732963:30 | 2022-08 | 1 | Special servicing transfer dated 2023-03-28, first reported April 2023 |
| 1715846:39 | 2024-09 | 1 | Status runs B, 1, 2, 3; special servicing transfer dated 2025-03-07 |
| 1699099:1 | 2019-05 | 1 | Special servicing transfer dated 2019-12-24 |
| 1706303:3 | 2019-08 | 0 | Status 0 in all 13 filings; no transfer, modification or payoff code |
| 1742383:63 | 2023-04 | 0 | Same: status 0 throughout, no event |
| 1775756:2 | 2020-06 | 0 | Same |
| 1774801:21 | 2024-02 | 0 | Same |
| 1942599:7 | 2024-11 | 0 | Same |

## Revision, 2026-11-13 (D045)

The first draw had two positives, 1803308:64 (2020-07) and 1710261:68 (2017-11), that rested on the modification indicator alone. Both matched the definition as written, but both are NCB co-op loans (`propertyTypeCode` CH), and NCB sets the indicator with no modification code, date or new terms, in a yearly pattern (1710261:68 switches it on every July from 2018 to 2021). Across all filers, 15,931 of 15,933 indicator rows from other servicers carry modification details; NCB's 1,408 carry none. The definition now requires a detail, which removed 15,432 tier 2 positives (44% of the first count) and moved the multifamily rate from 12.8% to 1.8%. Both loans are labeled 0 for those months under the revised definition, and the filings agree: no other event follows. They were replaced by two positives drawn with seed 13 from the revised labels (rows 1 and 3 of the tier 2 table), both read from the filings as above. All 20 labels match the revised definitions.
