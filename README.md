# Maturity Wall Acquisition Engine

Which US commercial mortgages won't refinance at today's rates, and what could a buyer pay for the buildings behind them?

This repo answers that from the loan-level data that registered CMBS trusts file with the SEC every month (Form ABS-EE, exhibit EX-102). It ranks loans by the probability they fail at maturity, sizes the refinance gap the way a lender would, and underwrites an indicative bid for the collateral. Scores are screening aids under stated assumptions, not valuations or investment advice.

A research project by Eli Della Bitta. Views are my own.

**Status (November 2026): all six gates passed** (data, features and labels, models, underwriting engine, website, publication). Sign-offs and the limitations they publish: `docs/qa/gate1_signoff.md` to `docs/qa/gate6_signoff.md`; a second reader's 57 notes and what changed are in `docs/qa/gate6_review.md`. The site is built and hosted, but stays private until the author publishes it. The feature dictionary is `docs/features.md`, the label definitions `docs/labels.md`, the model card `docs/model_card.md` and the underwriting method `docs/underwriting.md`. The site is in `site/` (design brief `site/DESIGN.md`); the Los Angeles case study memo is `docs/la/memo.md`. The plan is `docs/SOP.md`; every departure from it is in `docs/decisions.md`.

## What the work found

- **Universe.** 381 registered CMBS trusts, found by checking which ABS-EE filers' EX-102 exhibits use the SEC's CMBS loan template (the XML namespace) since 2017. Of 1,060 ABS-EE filers, 531 turned out to be auto loans and 131 auto leases. Name searches miss trusts; the template check doesn't.
- **Filings.** 23,970 monthly asset-data filings (2.03 million asset records), parsed by our own streaming parser built from the SEC's XSD with zero type failures. On a 20-filing cross-check against edgartools, 177,480 shared fields matched with zero differences.
- **A loan is not a row.** Filers use at least six record layouts. In one, every property of a 39-property loan repeats the full $72.2M balance; summing rows would count it 39 times. `src/mwall/clean/structure.py` resolves each layout, and five hand-checked golden filings pin the behavior down in `tests/`.
- **Pari passu pieces.** Property NOI and debt service cover the whole loan while the trust reports only its piece, so ratios are computed on an estimated whole-loan balance. Whole loans held by one trust come out at a median trust share of 1.000, which is the check that the estimate works. Summing collateral across trusts without grouping pieces would overstate NOI by roughly 150%.
- **Geography.** Every property address gets a county and metro from the Census Geocoder and published crosswalks, never from a ZIP prefix: 42% of California addresses with ZIPs 900 to 935 sit outside the Los Angeles metro.
- **Reconciliation.** Pool balances tie to the certificate administrator's 10-D statement within 0.5% in 20,377 of 22,863 trust-periods (BANK 2017-BNK4, January 2024, to the cent: $859,864,958.46). All but 61 of the rest trace to a named defect in the filings.
- **Models.** A sign-constrained logistic regression ranks 12-month distress out of time and out of loan: in 2025 the riskiest 10% of loan-months held 28% of distress events and 37% of distress balance, against a debt-yield rule's 22% of events. A separate model scores failure to repay at maturity from 431 resolved maturities. Probability levels drift between years, so the site reads them as relative risk (`docs/model_card.md`).
- **Underwriting.** For 9,848 loans with usable NOI the engine sizes today's refinance loan, values the property relative to its securitization appraisal, and solves for the price at which a buyer earns a 20% levered return over five years. Base case: $46.7B of refinance gap across 4,563 loans, $84.2B in the downside; at the implied bid, a sale would fall short of the balance for 1,823 loans (median shortfall 18.7%). The gap is the new equity a refinance would need at today's terms, not a forecast of default: among 431 loans that reached maturity, those with a gap a year out failed 44% of the time against 42% without one, while office failed 58% and self-storage 6%. At today's bridge-loan rates leverage lowers returns: paying market value, the median buyer earns 6.1% unlevered and 2.2% levered. Three loans are rebuilt in an Excel workbook that the engine matches to the cent (`docs/qa/gate4_signoff.md`).
- **The filings are not clean.** 179 filings carry another deal's loans, some trusts list only part of their pool for months at a time, and paid-off loans stay listed at zero balance. `src/mwall/clean/screen.py` catches these and flags them; nothing is silently fixed.

QA reports live in `docs/qa/`.

## Reproduce

Requires Python 3.12 and [uv](https://docs.astral.sh/uv/).

```bash
uv sync --extra model
uv run pytest                      # unit, schema and golden-file tests (site tests skip until `mwall site` has run)
uv run python -m mwall fixture     # two trusts, three snapshots: rebuild and compare with stored outputs
```

The full build pulls tens of thousands of filings from EDGAR and takes several hours. SEC requires a declared contact in the User-Agent, read from an environment variable that never enters the repo:

```bash
export SEC_CONTACT="Your Name you@example.com"
uv run python -m mwall index && uv run python -m mwall discover && uv run python -m mwall filings
uv run python -m mwall download    # resumable; stays under SEC's 10 requests/second
uv run python -m mwall tend        # 10-D statements for the balance check
uv run python -m mwall parse && uv run python -m mwall clean && uv run python -m mwall wholeloans
uv run python -m mwall geo         # Census geocoder + county and metro crosswalks, cached
uv run python -m mwall qa
uv run python -m mwall loandetail --fetch --parse --agent 0001888524 --agent 0001628297   # vintage-2016 10-D loan tables
uv run python -m mwall panel       # loan-month panel, tier 1-3 labels, combined tier 1 gold set
uv run python -m mwall features --fetch --audit   # market series, feature table, dictionary, plots, leakage audit
uv run python -m mwall model       # Gate 3: rolling-origin evaluation, robustness, final scores, docs/qa/gate3_models.md
uv run python -m mwall underwrite --places   # Gate 4: city lookup (Census), scenarios, bids, sensitivity, docs/qa/gate4_underwriting.md
uv run python -m mwall site        # Gate 5: site data files to site/public/data
uv run python -m mwall la          # Los Angeles case study: la.json and docs/la/memo.md
cd site && npm ci && npm run build # static site in site/dist (npm run dev to preview)
```

`make data` runs the same sequence where `make` is available.

## Layout

```text
config/       universe rules, the SEC CMBS XSD, lender, cap-rate and underwriting parameters with their sources
src/mwall/    ingest/ parse/ clean/ panel/ features/ model/ underwrite/ site_export/
site/         the static site: pages, styles, the JavaScript engine, QA scripts
tests/        grammar, golden-file and fixture tests
fixtures/     two trusts, three snapshots, expected outputs
docs/         SOP, decisions log, data dictionary, SEC code tables, QA reports
```

## Limits worth knowing

- **Coverage.** Registered CMBS is a slice of commercial real estate debt, and most 2016-vintage deals, the source of the 2026 ten-year maturities, filed no asset-level data (49 of 55 registered 2016 deals; `docs/decisions.md` D011, D032). Delinquency in this data tracks Trepp's published rate (correlation 0.97) at a lower level, 2.5% against 5.2% on average.
- **Probabilities.** Rankings held up in every test year; probability levels drifted (calibration slope in range in one of four years). Read a probability with its rank within type. The maturity model rests on 431 loans.
- **Values.** Cap rates carry each property's appraisal spread at securitization forward to today's survey benchmark; appraisals run richer than surveys, which pushes values and bids up. Every bid is shown with a cap-rate sensitivity. California property taxes use an estimated seller's tax.
- **Inputs.** Recent NOI is missing for about a third of loan-months, more in early years; only three tenants are listed per property, with no rents. Extensions count as failures at maturity; every refinance is sized as a new fixed-rate conduit loan.
- **Not advice.** Scores, values and bids are model outputs under stated assumptions, not appraisals, credit decisions or offers.

The full list is on the site's method page and in each gate's sign-off.

## Data and rights

The SEC filings are public. `fixtures/raw/` and `tests/golden/` hold eleven small EX-102 filings (228 KB compressed) so a clone can rebuild the fixture and run the golden tests; the bulk filings stay out of the repo. Figures from firms' public reports (cap rates, lending spreads, rating-agency haircuts, REIT disclosures, broker surveys) are cited row by row in `config/research/`, each with its publisher, date, URL and a short verifying quote; the source documents themselves are not redistributed (D056). The SEC contact used for EDGAR requests lives in an environment variable and has never been committed.
