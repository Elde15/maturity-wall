# Golden filings

Five real EX-102 exhibits are committed in `tests/golden/` and checked by `tests/test_golden.py`. Each covers a different record layout. Every expected value in the tests was read from the raw XML with a separate regex reader (not this project's parser) and typed into the test by hand, so a parser bug can't confirm itself.

| Accession | Trust | Filer agent | What it tests |
| --- | --- | --- | --- |
| 0001888524-24-001207 | BANK 2017-BNK4 | 0001888524 | Parent record with a portfolio roll-up block plus `1-001` children; split notes `4A`, `4B`, `5A`; a defeased loan |
| 0001056404-18-000188 | GS Mortgage Securities Trust 2017-GS6 | 0001056404 | Replicated layout: 39 property records each repeating the full $72.2M balance of one loan |
| 0000950131-17-000002 | Citigroup Commercial Mortgage Trust 2016-P6 | 0000950131 | Nested layout (one loan record, six property blocks); notes such as `07A2` and `01A21` with no parent record |
| 0001539497-18-001471 | UBS Commercial Mortgage Trust 2018-C13 | 0001539497 | Filer swapped `assetNumber` and `assetTypeNumber` in every record |
| 0001056404-17-001723 | JPMCC 2017 trust (CIK 1695154) | 0001056404 | Dot-numbered children (`27.01` to `27.16`) under a parent whose roll-up equals the sum of its children; occupancy reported as 1.000 |

Checked for each: record counts, balance, rate, maturity, payment status, structure code, property name and type, NOI, appraisal and occupancy on two or three records; then the loan and property counts, layout, roll-up choice and appraisal sum after the clean layer.
