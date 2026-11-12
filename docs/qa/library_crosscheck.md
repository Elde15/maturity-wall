# Parser cross-check against edgartools

edgartools 6.0.0 (`edgar.abs.cmbs.CMBSAssetData`), fed the same local EX-102 files; no network. Shared fields: 48 loan-level and 45 property-level. Every shared field on every row was compared: exact for text, codes, dates, booleans and integers; relative tolerance 1e-9 for decimals.

- Filings: 20 across 7 filer agents and 10 deal families.
- Row counts identical: 20 of 20.
- Cells compared: 177,480. Mismatches: 0.

| accession | family | filer agent | loan rows | property rows | cells | mismatches |
| --- | --- | --- | --- | --- | --- | --- |
| 0001888524-26-019067 | BENCHMARK | 0001888524 | 28 | 91 | 5,439 | 0 |
| 0001888524-26-019476 | BANK5 | 0001888524 | 70 | 70 | 6,510 | 0 |
| 0001056404-19-001922 | MSC | 0001056404 | 89 | 89 | 8,277 | 0 |
| 0001888524-26-015895 | WFCM | 0001888524 | 148 | 148 | 13,764 | 0 |
| 0001056404-20-000642 | WFCM | 0001056404 | 61 | 61 | 5,673 | 0 |
| 0001056404-19-000524 | CD | 0001056404 | 140 | 140 | 13,020 | 0 |
| 0001628297-25-000081 | BMO | 0001628297 | 68 | 68 | 6,324 | 0 |
| 0001539497-18-001460 | BANK | 0001539497 | 145 | 145 | 13,485 | 0 |
| 0001628297-26-000932 | CF | 0001628297 | 41 | 86 | 5,838 | 0 |
| 0001628297-26-000768 | CF | 0001628297 | 41 | 86 | 5,838 | 0 |
| 0001539497-19-001243 | CGCMT | 0001539497 | 107 | 107 | 9,951 | 0 |
| 0001539497-18-001238 | UBS | 0001539497 | 82 | 82 | 7,626 | 0 |
| 0000950131-18-000258 | CGCMT | 0000950131 | 68 | 68 | 6,324 | 0 |
| 0001702746-18-000006 | MSC | 0001702746 | 89 | 89 | 8,277 | 0 |
| 0000950131-17-000065 | CGCMT | 0000950131 | 54 | 94 | 6,822 | 0 |
| 0001706303-18-000002 | BANK | 0001706303 | 222 | 222 | 20,646 | 0 |
| 0001702746-18-000004 | BANK | 0001702746 | 90 | 90 | 8,370 | 0 |
| 0000950131-18-000333 | CGCMT | 0000950131 | 94 | 94 | 8,742 | 0 |
| 0001706303-18-000006 | MSC | 0001706303 | 89 | 89 | 8,277 | 0 |
| 0001702746-18-000008 | MSC | 0001702746 | 89 | 89 | 8,277 | 0 |

Fields the raw XML carries that edgartools does not expose include `liquidationPrepaymentCode`, `liquidationPrepaymentDate`, `realizedLossToTrustAmount`, `mostRecentSpecialServicerTransferDate`, `workoutStrategyCode` and `modificationCode`. Our parser reads all of them, which is why production uses it (SOP section 7).
