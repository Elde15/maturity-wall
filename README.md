# Maturity Wall Acquisition Engine

Which US commercial mortgages won't refinance at today's rates, and what could a buyer pay for the buildings behind them?

This repo answers that from the loan-level data that registered CMBS trusts file with the SEC every month (Form ABS-EE, exhibit EX-102). It ranks loans by the probability they fail at maturity, sizes the refinance gap the way a lender would, and underwrites an indicative bid for the collateral. Scores are screening aids under stated assumptions, not valuations or investment advice.

**Status (November 2026): Gate 1 of 6, data.** The ingest, parser and cleaning layer are built and tested. The model, underwriting engine and site come next. The plan is `docs/SOP.md`; every departure from it is in `docs/decisions.md`.

## What's in the data so far

- **Universe.** 381 registered CMBS trusts, found by reading the root namespace of every ABS-EE filer's EX-102 since 2017. Of 1,060 ABS-EE filers, 531 turned out to be auto loans and 131 auto leases. Name searches miss trusts; the namespace doesn't.
- **Filings.** 23,970 monthly asset-data filings, parsed by our own streaming parser built from the SEC's XSD. On a 20-filing cross-check against edgartools, 177,480 shared fields matched with zero differences.
- **A loan is not a row.** Filers use at least six record layouts. In one, every property of a 39-property loan repeats the full $72.2M balance; summing rows would count it 39 times. `src/mwall/clean/structure.py` resolves each layout, and five hand-checked golden filings pin the behavior down in `tests/`.
- **Pari passu pieces.** Property NOI and debt service cover the whole loan while the trust reports only its piece, so ratios are computed on an estimated whole-loan balance. Whole loans held by one trust come out at a median trust share of 1.000, which is the check that the estimate works. Summing collateral across trusts without grouping pieces would overstate NOI by roughly 150%.
- **Reconciliation.** Pool balances tie to the certificate administrator's 10-D statement. For BANK 2017-BNK4, January 2024, they agree to the cent ($859,864,958.46).

QA reports live in `docs/qa/`.

## Reproduce

Requires Python 3.12 and [uv](https://docs.astral.sh/uv/).

```bash
uv sync --extra model
uv run pytest                      # unit, schema and golden-file tests
uv run python -m mwall fixture     # two trusts, three snapshots: rebuild and compare with stored outputs
```

The full build pulls tens of thousands of filings from EDGAR and takes several hours. SEC requires a declared contact in the User-Agent, read from an environment variable that never enters the repo:

```bash
export SEC_CONTACT="Your Name you@example.com"
uv run python -m mwall index && uv run python -m mwall discover && uv run python -m mwall filings
uv run python -m mwall download    # resumable; stays under SEC's 10 requests/second
uv run python -m mwall tend        # 10-D statements for the balance check
uv run python -m mwall parse && uv run python -m mwall clean && uv run python -m mwall wholeloans
uv run python -m mwall qa
```

`make data` runs the same sequence where `make` is available.

## Layout

```text
config/       universe rules, the SEC CMBS XSD, schema element list
src/mwall/    ingest/ parse/ clean/ (features, labels, models, underwrite, site_export to come)
tests/        grammar, golden-file and fixture tests
fixtures/     two trusts, three snapshots, expected outputs
docs/         SOP, decisions log, data dictionary, SEC code tables, QA reports
```

## Limits worth knowing now

Registered CMBS is a slice of commercial real estate debt, and most 2016-vintage deals, the source of the 2026 ten-year maturities, filed no asset-level data (49 of 55 registered 2016 deals; `docs/decisions.md` D011, D032). Appraisals are as of securitization. Recent NOI is missing for about a third of loan-months, more in early years.
