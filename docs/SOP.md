# Maturity Wall Acquisition Engine: Project SOP

Nov 11, 2026 · @Eli

## 1. Purpose and deliverable

This project builds a public, data-driven model that finds US commercial mortgages likely to fail at maturity, then shows what a buyer could pay for the assets behind them. It joins the capital-markets view (can this loan refinance?) with the acquisitions view (what is the basis, and what does the deal return?) in one pipeline on real loan-level data.

**Thesis.** Roughly a trillion dollars of commercial debt is repricing from low-rate loans to today's rates. Loans that cannot be refinanced become forced sellers, recapitalizations or note sales. A model that ranks those loans, sizes the refinance gap and underwrites the resulting opportunity is the daily work of debt-advisory, capital-markets and acquisitions teams.

**Audience.** Recruiters and analysts at JLL, CBRE, Eastdil Secured and similar firms; acquisitions and credit teams at funds. They will skim the site for two minutes and may read the repo for twenty.

**What the finished project contains**

- A public GitHub repository with a reproducible pipeline, tests, a data dictionary and a model card.
- A static interactive site: national map, ranked loan list, loan tear-sheets, and a scenario lab with live sliders.
- A Los Angeles case study written as an investment memo, with three to five loan-level case files.
- A methodology and backtest page that states what the model can and cannot do.

**What it should signal**

- Large-data engineering: millions of loan-month records parsed from raw SEC filings, not a downloaded spreadsheet.
- Credit and valuation fluency: debt yield, DSCR, LTV, loan sizing, cap rates, levered returns.
- Statistical rigor: time-based validation, calibration, baselines, no leakage.
- Communication: a memo and a site a non-technical MD can read.

## 2. Scope, definitions and non-goals

The project covers US registered CMBS from 2017 onward, across all property types, scored for maturity risk, with an acquisition lens on the riskiest loans.

**In scope**

- Universe: CMBS trusts that file Form 10-D with an EX-102 asset-data exhibit on SEC EDGAR (Regulation AB II asset-level disclosure).
- Property types: office, retail, lodging, industrial, multifamily, self-storage, mixed use, other.
- Outputs per loan: probability of failing to refinance, refinance gap in dollars and as a share of balance, stressed value, implied bid discount to par, and buyer returns.
- Geography: a national model plus a Los Angeles metro case study.
- History: every monthly 10-D from each trust's first filing to the latest available at build time.

**Out of scope**

- Unregistered (144A) deals, bank balance-sheet loans, debt-fund loans and agency multifamily, except agency data as an optional benchmark.
- Paid datasets (CoStar, MSCI/RCA, Trepp loan data). Free and public data only.
- Trading signals, price quotes, or anything presented as investment advice.
- Borrower credit research beyond what appears in the filings.

**Definitions used throughout**

| Term | Definition |
| --- | --- |
| NOI | Property-level net operating income from the latest reported financials |
| DSCR | NOI ÷ annual debt service (the filings report both NOI and NCF versions) |
| Debt yield | NOI ÷ loan balance |
| LTV | Loan balance ÷ property value |
| Max refinance proceeds | The smaller of the LTV, DSCR and debt-yield constraints at a market rate and underwriting standard |
| Refinance gap | Loan balance − max refinance proceeds, floored at zero |
| Distress event | 60+ days delinquent, special-servicing transfer, modification, or realized loss |
| Maturity failure | Not paid in full at or before maturity (defined operationally in section 10) |
| Implied discount to par | 1 − (bid price ÷ loan balance) |

## 3. Research questions and hypotheses

The project answers five questions. Each hypothesis below is stated so the data can reject it, and the site reports the result whichever way it falls.

| # | Question | Hypothesis to test |
| --- | --- | --- |
| Q1 | Which maturing loans cannot refinance at today's rates? | A structural loan-sizing test (what a lender would fund today) identifies a large share of loans that later show distress. |
| Q2 | What drives failure, and does it differ by property type? | H1: debt yield and DSCR a year before maturity carry the most signal. H2: at the same debt yield, office and lodging fail more often than multifamily and industrial. |
| Q3 | Does the rate shock add information beyond coverage ratios? | H3: the gap between the loan's coupon and today's market rate improves out-of-time prediction after controlling for DSCR and debt yield. |
| Q4 | Is collateral value overstated in the data? | H4: LTV computed on the securitization appraisal understates true LTV; a model-adjusted value predicts distress better than the stale appraisal. |
| Q5 | Where does the implied bid clear a buyer's return hurdle? | H5: only a minority of high-risk loans clear a stated levered-IRR hurdle at the implied bid, concentrated in a few property types and metros. |

**Secondary hypotheses**

- H6: NOI trend (change over the prior four quarters) adds signal beyond the NOI level.
- H7: loans already modified or extended carry a different hazard from unmodified loans at the same coverage.
- H8: metro-level fundamentals (rent growth, vacancy, permits) add signal for multifamily and industrial more than for office.
- H9: single-asset loans fail at different rates from diversified pools, so the model reports them separately.

**What counts as a useful result**

- The model beats a rule-of-thumb baseline (debt yield below a fixed threshold) on out-of-time precision-recall and Brier score.
- Predicted probabilities are calibrated: a calibration slope near 1 on held-out periods.
- A null result is still published. "Coverage ratios alone explain most of it" is a legitimate finding and shows judgment.

## 4. What the feasibility sample proved

The approach works: a test pull of 57 trusts returned 168,046 loan rows and 206,850 property rows from filings dated 2018-05-24 to 2026-11-02, and it also exposed four design constraints. All numbers below come from a quarterly-snapshot sample of 2017–2021 vintages, not the full universe.

| Check | Result | Design consequence |
| --- | --- | --- |
| EDGAR access | An anonymous request returned HTTP 403; the same request with a declared contact string in the User-Agent returned 200 | Every request must carry a contact string, kept out of the public repo (section 16) |
| Trust discovery | 168 trusts found by name search across 18 deal families; COMM, CSAIL, CFCRE, DBJPM, MSBAM, BMO and CSMC added none | Name search is incomplete. Use the EDGAR quarterly form index for a systematic universe (section 7) |
| Ingest throughput | 56 trusts, up to 44 quarterly 10-Ds each, parsed in 4 min 50 s with 3 workers; output was 14 MB of parquet | The full monthly history is a local, resumable job, not a notebook cell |
| Row structure | 47% of parsed loan rows have every loan field empty. In the raw XML they are property-level records (asset numbers like 1-001) under a parent loan (asset 1). 3,566 true loans remain | Parent loan = asset number before the hyphen. Never count rows as loans (section 8) |
| Library coverage | The parser exposes 48 loan and 46 property fields but not liquidation code, liquidation date or realized loss, which the raw XML contains | Write our own XML parser for production; use the library only to prototype (section 7) |
| Pre-2017 deals | One 2016 trust (Wells Fargo 2016-BNK1) filed 10-Ds with no EX-102 exhibit | Most 2016-vintage deals, the source of the 2026 ten-year maturities, are likely outside the structured data. Verify on more trusts |
| Property mix | Office, retail, lodging, industrial, multifamily and self-storage all appear in volume | The all-types scope is supported; multifamily is thinner than in agency data |
| Appraisal source | 178,688 of about 178,900 valuations are tagged MAI; valuation is 97.8% populated | Values are securitization-date appraisals. Current value must be modeled (H4) |
| NOI coverage | `noi_current` is 66% populated overall: 48% in 2018, a 75% peak in 2022, 58% in 2026 | Missing NOI is common and rising. Treat missingness as a feature and report coverage |

**Maturity profile in the sample.** Of roughly 3,070 loans with a maturity date, 79 matured in 2021–2025, 87 mature in 2026, and 642, 617 and 828 mature in 2027, 2028 and 2029. Ten-year terms dominate; only about 170 loans have 60-month and about 40 have 84-month terms among those with a populated term field.

**Why this matters.** Loans that have already reached maturity are scarce in 2017+ registered data, because most were written for ten years. A model trained only on completed maturities would have little to learn from. Section 10 and section 11 are built around that constraint.

## 5. Data source inventory

One core dataset (SEC CMBS asset data) carries the project; every other source is context for rents, rates, cap rates, supply and geography. Reachability was tested from the build workspace where noted. Verify license and terms for each source before publishing derived data.

| # | Source | What it provides | Access | Grain | Role and caveat |
| --- | --- | --- | --- | --- | --- |
| 1 | SEC EDGAR Form 10-D, EX-102 (CMBS asset data) | Loan terms, balances, rates, payment status, property NOI, DSCR, occupancy, appraisal, tenants | Public, needs a declared User-Agent; tested | Loan and property, monthly | Core dataset. Registered CMBS only; 2017+ vintages |
| 2 | SEC EDGAR quarterly form index | Filings by form type, company name and CIK | Public file download | Filing | Systematic trust discovery (section 7) |
| 3 | SEC EDGAR prospectus filings (FWP, 424B) | Deal terms, at-issuance underwriting, property detail | Public | Deal | Optional cross-check of at-issuance NOI and value |
| 4 | FRED | Treasury yields (5-, 7-, 10-year), SOFR, bank CRE delinquency, CRE price indexes | Public CSV and API; tested | Daily to quarterly | Rate scenarios and macro context. Confirm series IDs when building |
| 5 | CBRE U.S. Cap Rate Survey (H1 2026, published August 2026) | Cap rate estimates by property type, class and market | Public report; tables partly gated | Semiannual | Anchor for market cap rates. Transcribe minimal values with attribution; check terms |
| 6 | Zillow Research (ZORI, ZHVI) | Rent and home value indexes by metro and ZIP | Public CSV; tested | Monthly | Multifamily rent growth. Asking rents, not in-place |
| 7 | Census ACS 5-year | Income, rent, population, housing by tract, ZIP, metro | Public API | Annual | Demand fundamentals. Needs a ZIP-to-tract crosswalk |
| 8 | Census Building Permits Survey | Permits by county and metro | Public download | Monthly | Multifamily supply pipeline |
| 9 | BLS QCEW | Employment and wages by county and industry | Public download | Quarterly | Office-using employment as an office demand proxy |
| 10 | HUD Fair Market Rents and ZIP crosswalks | Rents; ZIP-to-county and ZIP-to-metro mappings | Public download | ZIP, county | Geography joins; rent sanity check |
| 11 | Census Geocoder and TIGER/Line | Address-to-coordinate lookup; map boundaries | Public | Address; polygon | Map layer. Cache results; respect rate limits |
| 12 | FHFA Public Use Database and Freddie Mac MLPD | Agency multifamily loan-level data | Public download | Loan | Optional multifamily benchmark and loan-sizing check |
| 13 | LA County Assessor, LA City open data (permits, zoning) | Parcels, permits, ownership | Public portals | Parcel, permit | Los Angeles case study only |
| 14 | Brokerage quarterly market reports (CBRE, JLL, Cushman & Wakefield, Colliers) | Vacancy, rent and absorption by submarket | Public PDFs | Submarket, quarterly | LA case study context. Cite each report; do not copy tables |
| 15 | Trepp, CRED iQ and CREFC public summaries | Aggregate CMBS delinquency and distress rates | Public articles and PDFs | Monthly aggregate | External benchmark for model back-checks. Cite; do not scrape |

**Source hierarchy.** If a free source conflicts with the filings, the filings win for loan facts. For market-level facts (cap rates, vacancy) use at least two sources and show the range, not a single point.

## 6. Architecture, storage and repository layout

Data moves through four layers, each stored as parquet and queried with DuckDB, so every number on the site traces back to a raw SEC filing.

| Layer | Contents | Format | Rule |
| --- | --- | --- | --- |
| Raw | Untouched EX-102 XML plus filing metadata, one file per accession number | Gzipped XML | Immutable. Never edited or re-saved |
| Parsed | One row per loan-period and per property-period, typed and decoded | Parquet, partitioned by filing year | Schema versioned; rebuilt only from raw |
| Panel | Loan-month rows with features, labels and market joins | Parquet | Rebuilt deterministically from parsed |
| Outputs | Model scores, scenario grids, site JSON | Parquet and JSON | The only layer the website reads |

&#91;embedded content: data architecture · 4 stored layers, 3 side inputs\]

Raw filings flow down to site files. Market data and scenario configuration join at the panel and model stages, and the website reads only the outputs layer.

**Keys and conventions**

- `trust_cik`: the issuing trust. `accession`: the filing. `period_end`: the reporting period end date.
- `loan_key` = `trust_cik` + parent asset number. `property_key` = `loan_key` + the property suffix (for example `1-001`).
- Every stage skips work whose output already exists with a matching input hash, so a failed run resumes instead of restarting.
- Random seeds are fixed and package versions are pinned in a lockfile.
- The SEC contact string comes from an environment variable (`SEC_CONTACT`) and is never written to a file inside the repository.

**Tooling (proposed)**

- Python: `lxml` for XML, `pyarrow` and DuckDB for storage and SQL, scikit-learn, LightGBM, statsmodels and lifelines for modeling.
- Site: static HTML with MapLibre GL for the map, D3 or Observable Plot for charts, and optionally DuckDB-WASM so the browser can query parquet directly.
- Storage budget: one inspected EX-102 was about 390,000 characters. Plan raw storage in the tens of gigabytes uncompressed, kept out of git.

**Repository layout**

```text
maturity-wall/
  README.md            thesis, results, how to reproduce
  MODEL_CARD.md        intended use, data, metrics, limits
  Makefile             data, features, train, score, site
  config/              YAML: universe, scenarios, lender-sizing parameters
  src/
    ingest/            discover trusts, list filings, download raw XML
    parse/             XML to parquet, code tables, schema checks
    clean/             entity resolution, de-duplication, QA flags
    features/          panel builder, market joins
    labels/            outcome definitions
    models/            baseline, hazard, boosted, calibration
    underwrite/        refinance gap, valuation, cash flow, returns
    site_export/       JSON and parquet for the website
  tests/               parser golden files, schema, metric tests
  fixtures/            two trusts, three snapshots (under 5 MB)
  docs/                SOP, data dictionary, decisions log
  site/                static website (HTML, JS, CSS, data/)
```

**Reproducibility standard.** A stranger can clone the repo, run the fixture build in one command, and get the same outputs. Full-universe builds are documented, resumable, and clearly marked as long-running.

## 7. EDGAR ingestion procedure

Ingestion is a resumable seven-step job that turns EDGAR filings into typed parquet. Production should use our own XML parser, because the library tested exposes 48 loan fields while the raw filings carry more, including liquidation and realized-loss data.

1. **Declare identity and throttle.**
   - Read the contact string from `SEC_CONTACT`; send it as the User-Agent on every request.
   - Stay under SEC's published request-rate limit (10 requests per second) with a shared limiter. The sample used 3 workers.
   - Back off exponentially on HTTP 403 and 429. Log every request with status and bytes.
2. **Discover the trust universe.**
   - Download the EDGAR quarterly form index for each quarter from 2017 Q1 to the latest. Keep 10-D and ABS-EE rows.
   - Filter by name patterns for CMBS trusts, then confirm each candidate by fetching its latest EX-102 and checking that the root XML namespace is `.../absee/cmbs/assetdata`. That namespace test is the definitive CMBS flag.
   - Write a `trusts` table: CIK, name, deal family, vintage year parsed from the name, first and last filing date.
   - Acceptance: all 168 trusts found by the sample's name search also appear here. Investigate any that do not.
3. **Enumerate filings per trust.**
   - Use each trust's EDGAR submissions record. Keep every 10-D and 10-D/A with accession number, filing date and period end.
   - An amendment supersedes the original for the same period. Record which one wins.
4. **Download raw exhibits.**
   - Find the EX-102 attachment (file names vary, for example `exh_102.xml`). Save gzipped to `raw/{cik}/{accession}.xml.gz` with a SHA-256 hash.
   - If a 10-D has no EX-102, check for a separate ABS-EE filing for the same period before marking it missing.
   - Also record the EX-103 exhibit's presence; inspect its contents once and decide whether it is needed.
5. **Parse with our own parser.**
   - Stream each file with `lxml.iterparse` over the `<assets>` elements. Each element is a loan record or a property-level record.
   - First run a tag census over a stratified sample (each depositor family and vintage) to list every tag that occurs. Build an explicit schema of loan and property fields from it.
   - Any tag not in the schema goes into an `extras` JSON column, so nothing is silently dropped.
   - Convert dates (the raw format is MM-DD-YYYY), numerics and coded fields; keep the original code alongside the decoded label.
6. **Validate and write.**
   - Row counts must reconcile: assets in the XML equal rows written. Rejects go to a quarantine file with a reason.
   - Write parquet partitioned by filing year; record the schema version in file metadata.
7. **Refresh incrementally.** Each run lists new filings since the last successful accession and processes only those.

**Known pitfalls to handle explicitly**

- Months with no filing, late filings and amendments leave gaps in a loan's history. The panel builder must see gaps, not assume continuity.
- Trusts wind down; the final period may hold zero balances or only liquidated loans.
- Liquidated loans stay in the data with a liquidation date and realized loss. They are the loss-severity labels, so they must be kept.
- Property records for one loan can number in the dozens (portfolio loans). Parse them all.

**Acceptance criteria for ingestion**

- Every discovered trust has at least one parsed filing or a recorded reason it has none.
- Row counts reconcile for 100% of filings.
- A field-coverage report exists by vintage and depositor family.
- Five hand-checked filings across three depositor families parse to the expected values (golden tests).
- On 20 filings, our parser matches the library on every field they share.

## 8. Cleaning and entity resolution

Cleaning turns raw records into one trustworthy row per real loan and property per period. The sample showed the main trap: nearly half of parsed loan rows were property-level records, so counting rows would roughly double the number of loans.

1. **Classify every record.**
   - Asset numbers without a hyphen (for example `1`) are loan records. Asset numbers with a suffix (for example `1-001`) are property records for loan `1`.
   - Set `parent_loan = asset number before the hyphen`. Confirm on three trusts per depositor family that no loan ID itself contains a hyphen. Where it does, use the structure of the XML, not the string.
   - Join property records to their parent loan on `trust_cik`, `accession` and `parent_loan`.
2. **Resolve pari passu and note structures.**
   - The sample's `loan_structure` shows whole loans (WL), pari passu pieces (PP) and A/B notes (A1, A2, B1). One whole loan can be split across several trusts, and each trust reports its own piece.
   - Build a `whole_loan_id` by matching property address, ZIP, original balance of the whole loan and origination date across trusts. Do not double-count property NOI or value when summing across trusts.
   - Acceptance: report how many properties appear in more than one trust, and size the effect on any aggregate before publishing it.
3. **Collapse to one row per loan-period.** If an amendment exists, keep the latest. Flag gaps in the monthly history rather than filling them.
4. **Aggregate properties to the loan.**
   - NOI, NCF, revenue, expenses: sum across properties that report the same financial period. If properties report different periods, flag the loan and do not sum.
   - Valuation: sum securitization appraisals. Occupancy and rent: weight by square feet or units.
   - Keep the largest property's type, state, MSA and age as loan attributes, plus a `multi_property` flag and the property count.
5. **Decode and standardize.**
   - Property type codes (OF, RT, LO, IN, MF, SS, MU, CH, MH, SE, WH, 98) map to named groups. Map payment status codes to delinquency buckets. Confirm both against the SEC asset-data specification for each code before use (appendix).
   - Compute term from maturity minus origination date. Do not rely on the original-term field alone; it was blank for many loans in the sample.
   - Normalize rates to decimals and dates to ISO format.
6. **Geography.**
   - Clean addresses, then geocode with the Census Geocoder for latitude and longitude. Cache every result.
   - Assign ZIP to county and metro with a published crosswalk. A ZIP-prefix test is not a valid metro filter. For example, California prefixes 900–935 include San Diego and the Inland Empire as well as Los Angeles.
7. **Flag, do not silently fix.**
   - Add QA flags: NOI missing, NOI stale (financials period ended more than 18 months before the filing), DSCR inconsistent with recomputation, valuation older than five years, negative or zero balance with active status.
   - Never impute NOI or value inside the parsed or panel layers. Imputation, if used, happens in a named modeling step and is reported.

**Cleaning acceptance criteria**

- Loans per trust equal the count reported in the prospectus at issuance, less payoffs, within a documented tolerance.
- Sum of loan balances per trust and period reconciles to the balance in the 10-D body within 0.5%.
- A recomputed DSCR (NOI ÷ annual debt service) matches the reported DSCR within a stated tolerance for 95% of loans; the rest are listed.
- Every flag has a count in a QA report committed to the repo.

## 9. Feature engineering catalog

Features fall into seven families. Every feature gets a dictionary entry with formula, unit, source field, lag and null policy, and every feature is computed using only information that was public on the snapshot's filing date.

| Family | Feature | Definition | Note |
| --- | --- | --- | --- |
| Leverage and coverage | Debt yield | Loan NOI ÷ current balance | Also computed on NCF. Primary risk driver in industry studies |
|  | DSCR (reported and recomputed) | NOI ÷ annual debt service | Keep both; flag disagreement |
|  | LTV on appraisal | Balance ÷ securitization appraisal | Stale by construction |
|  | Model-adjusted value and LTV | Current NOI ÷ market cap rate for type and date | Tests H4; see section 12 |
|  | Refinance DSCR | NOI ÷ debt service on a new loan at today's rate and amortization | Core structural feature |
|  | Refinance debt-yield cushion | Debt yield − lender minimum for the property type | Negative means a gap |
| Cash flow trend | NOI vs securitization | Current NOI ÷ NOI at securitization − 1 | Level of erosion since issue |
|  | NOI year-over-year | Change versus the same period a year earlier | Needs the panel, not one snapshot |
|  | Expense ratio | Operating expenses ÷ revenue | Rising ratio signals margin pressure |
|  | NOI age | Months from financials end date to filing date | Staleness; reporting lags are common |
| Occupancy and tenants | Occupancy and change | Current occupancy; change since securitization | Office and retail matter most |
|  | Tenant concentration | Largest tenant's square feet ÷ property square feet | From tenant fields |
|  | Near-term rollover | Share of listed tenant space with lease expiry in the next 24 months | Top three tenants only |
| Loan terms | Months to maturity, term, seasoning | Computed from dates | Term from dates, not the term field |
|  | Rate shock | Market refinance rate − loan coupon | Tests H3 |
|  | Interest-only remaining, balloon share | Interest-only months left; maturity balance ÷ original balance | Balloon size drives the gap |
|  | Structure | Whole loan, pari passu piece, A/B note; single-asset flag; property count | Section 8 |
| Property | Type, state, metro, age, renovation | From property fields | Metro uses a proper crosswalk |
|  | Size and basis | Balance per unit or per square foot | Units for multifamily and lodging; square feet otherwise |
| Servicing and status | Delinquency bucket, modification flag | Decoded payment status; modified indicator | Current status is a feature only for forecasting at a later date |
|  | Advances outstanding | Principal and interest or tax and insurance advances above zero | Early stress signal |
| Market and macro | Rent growth, permits per 1,000 units, employment growth | Metro-level joins from Zillow, Census, BLS | Lagged by publication delay |
|  | Treasury level and change, curve slope, cap-rate benchmark | FRED yields; CBRE survey by property type | Survey used only after its publication date |

**Leakage rules**

- A feature for snapshot date T may use only data published on or before T. Market series are lagged by their release delay; the CBRE survey enters on its publication date (the H1 2026 edition was published in August 2026), not its late-June survey date.
- Outcome fields (liquidation, realized loss, final payoff) never appear as features for earlier periods.
- Current delinquency status is a legitimate feature only when the label looks strictly forward from T, and the label window must not overlap the status period.

**Missing data policy.** Missing NOI is frequent and rising, so missingness is information. Add an explicit missing-indicator, never fill NOI with a guess in the panel layer, and report model performance separately for loans with and without current NOI.

**Acceptance.** Each feature has a unit test on a hand-built example, a dictionary row, and a distribution plot by property type in the QA report.

## 10. Outcome labels, panel design and validation

Because completed maturities are scarce, labels come from three tiers, the panel is a loan-month table, and validation is strictly out-of-time. The panel has one row per loan per reporting month, from the first snapshot to a terminal event or the last observation.

**Terminal events (competing outcomes)**

- Paid in full: balance reaches zero with a payoff or prepayment code.
- Distress event: 60+ days delinquent, special-servicing transfer, modification, or matured non-performing status.
- Liquidation with loss: a liquidation date and a realized loss.
- Censored: still performing at the last observation.

**Three label tiers**

| Tier | Label | Unit | Use |
| --- | --- | --- | --- |
| 1. Maturity outcome | 1 if not paid in full within 90 days after maturity; 0 if paid in full at or before it | One row per loan that has reached or passed maturity | Gold set. Small, so used for calibration and final testing, plus a maturity-window model |
| 2. Forward distress | 1 if a distress event occurs within 12 months after the snapshot date | Every performing loan-month | Main training set. Large |
| 3. Loss severity | Realized loss ÷ balance at liquidation | Liquidated loans | Feeds the acquisition layer's downside case |

**How the tiers combine.** The core model predicts 12-month forward distress (tier 2) with time-varying features, including months to maturity and the refinance metrics. A second model trained on tier 1, restricted to loans within 12 months of maturity, predicts maturity failure directly. The published "fails to refinance" probability is an ensemble of the two, and the site reports how many tier 1 events stand behind it.

**Codes to resolve before labeling.** Confirm against the SEC asset-data specification: the meaning of payment status codes 4 and 5 (they appear in the sample and likely mark matured balloon loans that are performing or not), the liquidation and prepayment codes, and the field that marks special-servicing transfer. The label code must not be written until these are documented in the appendix.

**Horizons.** Maturity-window features are computed at 12, 6 and 3 months before maturity. The 12-month horizon is primary because it is when a debt advisor can still act.

**Validation design**

- Rolling-origin evaluation: train on the earliest period, validate on the next 12 months, test on the 12 months after that; then roll forward and repeat across at least three origins. Report each origin, not only an average.
- Group by loan: no loan appears in both training and test data. Also test with whole trusts held out, to measure generalization across deals.
- A final forward check scores loans whose outcomes have not yet occurred; it is published as a forecast, clearly marked.

**Baselines to beat**

- B0: the base rate.
- B1: a debt-yield rule. Industry reviews report that loans with debt yields below about 8% show the highest refinance and delinquency risk ([CRE Daily](https://www.credaily.com/?p=217769)); test that threshold and neighbors.
- B2: DSCR below a fixed threshold.
- B3: the structural rule (refinance gap above zero).

**Metrics**

- Discrimination: precision-recall AUC (primary, for imbalance), ROC AUC.
- Calibration: Brier score, log loss, calibration slope and intercept, reliability plot by decile.
- Business: share of failures captured in the top 10% ranked loans, and the same weighted by balance.
- Cuts: by property type, vintage, single-asset versus pool, and with versus without current NOI.

**External sanity check.** Aggregate predicted distress by property type and month is compared with published CMBS delinquency and distress rates (Trepp, CRED iQ). It is a back-check, never training data.

**Bias controls**

- Survivorship: loans paid off early are the healthy ones; censor them correctly and report the share.
- Small segments: if a property type has fewer than about 30 events, do not fit a separate model. Pool with a type indicator and show wide intervals.
- Imbalance: keep natural class frequencies and recalibrate; avoid resampling that distorts probabilities.

## 11. Modeling procedure

Models are built from simple to complex, and each stage must beat the one before on out-of-time data or it is dropped. The interpretable model is always published beside the boosted one.

| Stage | Model | Purpose | Pass criterion |
| --- | --- | --- | --- |
| 1 | Regularized logistic regression as a discrete-time hazard on loan-months | Interpretable benchmark; signs and sizes of effects | Coefficient signs match credit logic (higher debt yield, lower risk); beats baselines B0–B3 |
| 2 | LightGBM with monotonic constraints on debt yield, DSCR, LTV and occupancy | Capture interactions and non-linearity | Beats stage 1 on precision-recall AUC and Brier score in a majority of rolling origins |
| 3 | Probability calibration (isotonic or Platt) on a held-out calibration window | Make probabilities usable | Calibration slope within 0.8–1.2 on the test window |
| 4 | SHAP explanations | Per-loan drivers; global importance | Importance ranking stable across origins; no feature that leaks outcomes |
| 5 (stretch) | Cause-specific hazards for payoff and distress | Cumulative probability of each outcome through maturity | Agrees with the ensemble within a stated tolerance or the gap is explained |
| 6 | Ensemble of forward-distress model and maturity-window model | Final failure-to-refinance probability | Beats each component on the tier 1 gold set |

**Procedure for each model**

1. Build features for each origin using only data available then (section 9).
2. Tune with time-aware cross-validation inside the training window only. The test window is not touched until the model is frozen.
3. Fit, calibrate, and score the test window. Log metrics by property type, vintage and with-or-without current NOI.
4. Record every run (git commit, data hash, parameters, metrics) in an experiment log file committed to the repo.
5. Freeze, then run the robustness suite below.

**Robustness suite**

- Ablations: drop market features; drop NOI features; drop servicing-status features. Report the loss in performance for each.
- Label sensitivity: re-run with 60-, 90- and 120-day maturity grace windows.
- Out-of-trust generalization: hold out whole deal families.
- Stability: feature importance and calibration across rolling origins.
- Scenario sensitivity: how rankings change when the refinance-rate assumption moves by 100 basis points.

**Uncertainty.** Publish intervals, not only point probabilities: bootstrap by loan for the logistic model, and a conformal or bootstrap interval for the boosted model. The site shows the interval on every tear-sheet.

**Output table (one row per loan, latest snapshot)**

- Identifiers: loan key, trust, whole-loan group, property type, metro, balance, maturity date.
- Scores: probability of failing to refinance, interval low and high, 12-month distress probability, rank within property type.
- Structural: refinance DSCR, debt yield, refinance gap in dollars and percent of balance.
- Explanations: top three drivers with direction and size.
- Data quality: NOI age, missing flags, multi-property flag.

**Documentation deliverable.** A model card stating intended use, training data, metrics by segment, known failure modes, and an explicit statement that scores are screening aids, not valuations or investment advice.

## 12. Refinance gap and acquisition underwriting

Every high-risk loan goes through four calculations: what a lender would fund today, what the asset is worth, what a buyer could pay and still earn the target return, and what that return looks like year by year. The engine is deliberately simple enough to run live in the browser.

**Step A. Refinance gap**

Maximum new loan is the smallest of three lender constraints. The loan constant k is annual debt service per dollar of loan at the refinance rate r and amortization n years.

```latex
P_{max} = \min\left( LTV_{max} \cdot V,\ \frac{NOI}{DSCR_{min} \cdot k},\ \frac{NOI}{DY_{min}} \right), \quad k = 12 \cdot \frac{r/12}{1-(1+r/12)^{-12n}}, \quad Gap = \max(0,\ B - P_{max})
```

Here B is the current balance, V is value, and r = Treasury yield + spread by property type. LTV\_max, DSCR\_min, DY\_min, amortization years and spreads live in a config file, one row per property type and scenario. **Every parameter needs a cited source** (lender surveys, published market commentary) in the config; none should be typed from memory.

**Step B. Stressed NOI and value**

- Stressed NOI = current NOI × (1 − haircut by scenario). Office and retail also apply a rollover adjustment using the listed tenants' lease expiries.
- Value = stressed NOI ÷ cap rate. Cap rate uses a relative-value method: the property's spread at securitization (NOI at securitization ÷ appraisal, minus the benchmark for its type and year) is added to today's benchmark for its type (CBRE survey), then shifted by the scenario.
- Appraisal-implied and broker-survey cap rates are not the same measure. Document it as a limitation and publish sensitivity at ±50 and ±100 basis points.

**Step C. Implied bid**

Two bids are reported and the difference is shown.

- Value bid: value less capital reserves, lease-up and carry costs, and transaction costs.
- Return bid: the price at which levered IRR equals the hurdle, found by root-finding on the cash-flow model below.

```latex
Discount_{par} = 1 - \frac{Bid}{B}
```

If the bid exceeds the balance, the loan is flagged "refinanceable by sale" and shown with no discount.

**Step D. Buyer cash-flow model (five-year hold, annual periods)**

- Year-one NOI is stressed NOI; later years follow the property-type growth path and vacancy assumptions.
- Deduct capital items (tenant improvements and leasing commissions, per-unit renovation, reserves) and management fees.
- Acquisition debt: loan-to-cost, rate = Treasury + spread, interest-only period, amortization.
- Exit: year-six NOI ÷ (entry cap + exit spread), less selling costs.
- Outputs: unlevered and levered IRR, equity multiple, average cash-on-cash yield, year-one DSCR and debt yield, break-even occupancy, equity required.

**Property-type templates and confidence tiers**

| Type | Revenue driver | Capital items | Tier |
| --- | --- | --- | --- |
| Multifamily | Metro rent growth (Zillow), vacancy | Renovation per unit with a rent premium | A with current NOI |
| Industrial | Metro rent growth, low vacancy | Low | A with current NOI |
| Self-storage | Occupancy and rate | Low | A with current NOI |
| Office | Lease-by-lease rollover, downtime | TI and LC per square foot | B |
| Retail | Anchor rollover | TI and LC | B |
| Lodging | RevPAR-style NOI margin | FF&E reserve, renovation | C |
| Mixed use, other | Direct capitalization only | None | C |

A tier C result is shown with a low-confidence badge and no cash-flow model.

**Opportunity score.** Ranking uses transparent components: failure probability, gap size, implied discount, whether returns clear the hurdle, confidence tier and asset size as a liquidity proxy. The formula is a rank-average of those components, published on the methodology page. It is not a black box.

**Execution realism.** A loan inside a CMBS trust is controlled by the special servicer, and buyers rarely purchase it directly. Routes include buying the note from the trust, buying the property after foreclosure, a discounted payoff negotiated with the servicer, or recapitalizing the sponsor. The implied bid is therefore labeled an indicative economic bid for the asset, not an executable offer.

**Validation of the engine.** Rebuild three loans by hand in a spreadsheet, commit it to the repo, and require the code to match its NOI, loan sizing, bid and IRR to the cent.

## 13. Los Angeles case study procedure

The case study takes the national model into one market that employers know and shows three to five loans in full: filing facts, model view, local context and underwriting. It is also where local rules that change the economics are modeled explicitly.

1. **Define the market by geography code, not ZIP prefix.**
   - Use the Census metro delineation for Los Angeles–Long Beach–Anaheim (Los Angeles and Orange counties); confirm the county list against the current delineation file.
   - Assign each property by county from the crosswalk. Record how many CA properties fall outside the market.
2. **Market-level analysis from the dataset.**
   - Loans and balance by property type, and the maturity schedule by year.
   - Distribution of model scores versus the national distribution, and total refinance gap under each scenario.
   - Securitization-implied cap rates for the market versus the benchmark.
3. **Local context (cited, not copied).**
   - Vacancy, asking rent and absorption from free brokerage quarterly reports for the market and submarket.
   - New supply from Los Angeles city permit data and the Census permits survey.
   - Ownership and last-sale facts from public assessor records, only where needed for a case file.
4. **Local overrides in the underwriting engine.** Add these as named, documented parameters and verify the current rule and rate from the official source before use.
   - City of Los Angeles transfer taxes on larger sales (Measure ULA) in transaction costs.
   - California Proposition 13 property tax reassessment on change of ownership in the buyer's expenses.
   - Rent stabilization and tenant protections for older multifamily buildings in the revenue growth cap.
5. **Select case files by a rule written down first.**
   - Pick the top-ranked loan by opportunity score in each of three groups: office, multifamily, retail or industrial.
   - Add one loan the model rates safe that looks risky to a rule of thumb, and one where the model and the debt-yield rule disagree most.
   - Record the rule and the full candidate list in the repo before opening any case file, so selection cannot be tuned to look good.
6. **Write each case file on one page** using the template below.

| Case file block | Content |
| --- | --- |
| Header | Property name, address, type, size, year built, trust, loan key |
| Loan facts | Original and current balance, coupon, maturity, status, structure |
| Performance | Chart of NOI, DSCR and occupancy since securitization |
| Valuation | Appraisal at securitization versus model value; cap rates used |
| Refinance test | Lender sizing table and the refinance gap |
| Model view | Failure probability, interval, top three drivers |
| Local context | Vacancy, rent trend, supply, with citations |
| Underwriting | Implied bid, returns, sensitivity grid |
| Risks | What would make the view wrong; data gaps |
| Sources | Every filing accession and every outside source linked |

7. **Assemble the memo.** A two-to-three page investment-memo-style document: summary, market overview, the case files, a methods note and limitations.

**Tone and legal guardrails**

- State only facts that appear in public filings or cited sources. Do not speculate about owners' intentions or conduct, and do not name individuals.
- Use screening language ("screens as high risk"), never recommendation language ("buy", "sell").
- Include the not-investment-advice disclaimer on every page that shows a score, bid or return.

**Acceptance criteria**

- The market definition is documented and every included property has a county code.
- The selection rule is committed before the case files exist.
- Every number in the memo traces to a data cell in the repo or a cited source.
- Each local override cites its official source and the date it was checked.
- A second reader who did not build the model has reviewed the memo for clarity.

## 14. Website specification

The site is a static, precomputed research product: heavy modeling happens offline, and the browser only filters, maps and recomputes the light underwriting math. It should read like a research publication first and a data tool second.

**Hosting and size constraints**

- Static hosting only (for example GitHub Pages). No server, no database, no API keys in the browser.
- Keep the site folder well under the host's size limits; check the current limits when building. Publish aggregates and loan-level outputs, not raw XML.
- Target a fast first view: headline numbers and the map should render from a small JSON file; larger parquet files load on demand.

**Pages**

| Page | Purpose | Key elements |
| --- | --- | --- |
| Home | The thesis in two minutes | Headline findings with numbers, one hero chart, links to the explorer and the memo |
| Explorer | Find loans | Map of loans sized by balance and colored by failure probability; filters for type, metro, maturity year, balance, score; sortable ranked table |
| Loan tear-sheet | One loan in full | Filing facts, NOI and DSCR history, refinance test, model drivers, underwriting, sensitivity grid, source accession links |
| Scenario lab | What if | Sliders for Treasury yield, spread, cap-rate shift, NOI haircut; live recalculation of gap, value, bid and IRR for a selected loan or a whole segment |
| Maturity wall | The aggregate picture | Balance maturing by year and property type; share at risk; total refinance gap by scenario |
| Los Angeles | The case study | Market charts and the memo with the case files |
| Methodology | Trust | Data, definitions, model card, backtest results, baselines, calibration, limitations |
| Data and code | Reproducibility | Data dictionary, repo link, how to rerun |

**Headline charts (each answers one question)**

- Maturing balance by year, stacked by property type: when is the wall?
- Share of balance with a positive refinance gap, by property type: where is it worst?
- Calibration plot: do 30% probabilities fail about 30% of the time?
- Model versus debt-yield rule on precision-recall: is the model worth it?
- Refinance gap by scenario: how sensitive is the aggregate to rates?
- Distribution of implied discount to par for high-risk loans, with the share clearing the return hurdle.

**Interaction rules**

- Scenario sliders recompute only the underwriting layer (loan sizing, value, bid, IRR) in JavaScript. The failure probabilities are precomputed and are labeled as such, so the page never implies the model reran.
- Every number links to its definition. Every loan links to its SEC filing accession.
- Default view shows the base scenario; the scenario and its assumptions are always printed next to any bid or return.

**Design standards**

- Restrained, editorial look: one accent color, consistent units, labeled axes, no decorative charts.
- Works on a phone. The map and table must remain usable at narrow widths.
- Accessible: color is never the only signal, text contrast meets standard guidelines, charts have text summaries.
- Disclaimers: a persistent footer note and a banner on any page showing scores, bids or returns.

**Data contract between model and site**

- `summary.json`: headline numbers and chart series.
- `loans.parquet` (or split JSON by metro): one row per loan from the output table in section 11.
- `history/{loan_key}.json`: per-loan NOI, DSCR and occupancy series, loaded on demand.
- `scenarios.json`: scenario definitions and the parameters table from section 12.
- Every file carries a build date, data cut-off date and schema version.

**Acceptance criteria**

- Every chart's numbers reconcile to the output tables (an automated check compares a sample).
- Slider recomputation in JavaScript matches the Python engine for 50 random loans within rounding.
- First meaningful view loads quickly on a mid-range phone connection; record the measurement.
- All links resolve; the methodology page lists every outside source.

## 15. QA gates and acceptance criteria

Work passes through six gates in order. A gate must pass before the next stage starts, and each gate leaves a written artifact in the repo. These checklists add cross-cutting checks to the acceptance criteria already stated in sections 7 to 14.

**Gate 1. Data**

- [ ] Trust universe table reconciles to the sample's name-search list and to the form index.
- [ ] Row-count reconciliation passes for every filing; rejects are quarantined with reasons.
- [ ] Loan versus property records are classified; loan counts per trust match the prospectus less payoffs.
- [ ] Pari passu duplicates are measured and handled; their effect on aggregates is reported.
- [ ] Field coverage report by vintage and depositor family is committed.
- [ ] Code tables (property type, payment status, liquidation and prepayment) are verified against the SEC specification.

**Gate 2. Features and labels**

- [ ] Every feature has a dictionary row, a unit test and a distribution plot by property type.
- [ ] A leakage audit confirms no feature uses data published after its snapshot date.
- [ ] Label counts by tier, property type and vintage are published, including the number of tier 1 events.
- [ ] A hand check of 20 loans confirms labels match what the filings show.

**Gate 3. Models**

- [ ] Baselines B0 to B3 are scored on every rolling origin.
- [ ] The final model beats the best baseline on out-of-time precision-recall AUC and Brier score, or the result is published as a null finding.
- [ ] Calibration slope and reliability plots are in range on the test window.
- [ ] The robustness suite is complete and its results are on the methodology page.
- [ ] The model card is written, including failure modes and segments with too few events.

**Gate 4. Underwriting engine**

- [ ] Three loans reproduced by hand in a spreadsheet match the code to the cent.
- [ ] Every config parameter has a cited source and a check date.
- [ ] Sensitivity grids behave sensibly: higher rates widen gaps and lower bids; higher cap rates lower value.
- [ ] Edge cases handled: zero or missing NOI, negative NOI, bid above balance, multi-property loans, partial-year financials.

**Gate 5. Website**

- [ ] Chart numbers reconcile to output tables by an automated sample check.
- [ ] JavaScript scenario math matches Python for 50 random loans.
- [ ] Works at phone width; keyboard navigation works; color is never the only signal.
- [ ] Every link resolves; every score, bid and return carries its scenario and disclaimer.

**Gate 6. Publication**

- [ ] A fresh clone builds the fixture dataset with one command and matches stored outputs.
- [ ] The repo contains no secrets, no contact email, no raw XML, and no restricted third-party data.
- [ ] A second reader outside the project has read the methodology page and the Los Angeles memo and noted anything unclear.
- [ ] README states the thesis, headline results, limitations and how to reproduce.

**Definition of done.** All six gates pass, the site is live, and the repo can be cloned and rebuilt by someone else. A gate that fails is fixed or the limitation is published; it is never waived silently.

## 16. Risks, limitations and compliance

The biggest risks are data coverage and label scarcity, both already visible in the sample, and the project's credibility depends on stating them plainly on the site.

| Risk | Why it matters | Mitigation |
| --- | --- | --- |
| Coverage bias | Registered CMBS is only part of commercial debt. One industry source puts CMBS at about 13% of roughly $4.8 trillion outstanding ([CoStar](https://www.costar.com/article/1122236114/)). Most 2016-vintage deals, the source of the 2026 ten-year maturities, are likely outside the structured data | State coverage on the home and methodology pages. Compare covered balance with published totals. Never call results "the market" |
| Label scarcity | Few 2017+ loans have reached ten-year maturity | Three label tiers (section 10); publish tier 1 counts beside every probability |
| Stale appraisal and lagged NOI | Securitization appraisals are the only value in the data; NOI can be months old or missing | NOI age and missing flags as features; model-adjusted value; segment results by NOI availability |
| Cap rate mismatch | Appraisal-implied cap rates and broker-survey cap rates measure different things | Relative-value method; sensitivity at ±50 and ±100 basis points shown on every bid |
| Extensions and modifications hide distress | A loan can look current while its terms were softened | Broad distress definition; modification flag as a feature and a cut |
| Double counting | The same asset can appear in several trusts | Whole-loan grouping (section 8); effect sized before any aggregate is published |
| Leakage and overfitting | Inflated backtests destroy credibility | Time-based splits, group-by-loan, leakage audit, null results published |
| Small segments | Few events per property type give unstable models | Pool with indicators below the event threshold; show wide intervals |
| Misuse | A score or bid could be read as advice | Screening language, scenario and disclaimer on every output, model card limits |
| Parser and code-table errors | A wrong code silently corrupts labels | Own parser with golden tests; codes verified against the SEC specification before use |
| Scope creep | Complexity can outrun finishing | Out-of-scope list (section 2) and a decisions log in `docs/` |

**Compliance and legal checklist**

- **SEC access.** Identify yourself in the User-Agent, throttle requests, and follow the SEC's fair-access guidance. EDGAR filings are public; cite them.
- **Contact string.** It lives in an environment variable and never in code, config, notebooks, logs or git history. Run a secret scan before the first push; if it was ever committed, rewrite history before publishing.
- **Third-party licenses.** Check terms for Zillow, CBRE, FRED series sources, Census and BLS before publishing derived data. Attribute, and do not redistribute raw tables you do not have rights to.
- **Employer separation.** Use no employer data, code, templates or time, and check any current employer's or internship's policy on outside publications before the site goes live.
- **Reputation and privacy.** Publish property-level facts from filings only. Omit tenant names on the site and show concentration metrics instead. Do not name individuals.
- **Disclaimers.** Not investment advice; scores and bids are model outputs under stated assumptions; past filings do not predict outcomes; no affiliation with any firm named in the project.

## Appendix A. Field dictionary and code tables

This appendix records what the feasibility sample showed. Fields are those exposed by the library used in the test (48 loan, 46 property); the raw XML holds more. Code meanings marked "verify" are likely readings and must be confirmed against the SEC asset-data specification before any label or feature uses them.

**Loan fields exposed by the test library**

| Group | Fields |
| --- | --- |
| Identity and period | loan\_id, loan\_id\_type, period\_start, period\_end, originator, primary\_servicer |
| Origination terms | origination\_date, original\_amount, original\_term\_months, maturity\_date, first\_payment\_date, io\_term\_months |
| Rate and structure | original\_rate, securitization\_rate, current\_rate, accrual\_method, rate\_type, lien\_position, loan\_structure, payment\_type, is\_interest\_only, is\_balloon, is\_modified, num\_properties, num\_properties\_securitization |
| Balances and payments | period\_begin\_balance, scheduled\_balance, scheduled\_end\_balance, actual\_balance, scheduled\_pi\_due, scheduled\_interest, scheduled\_principal, unscheduled\_principal, servicer\_fee\_rate |
| Status and advances | payment\_status, paid\_through\_date, pi\_advances\_outstanding, ti\_advances\_outstanding, other\_advances\_outstanding, servicing\_advance\_method, grace\_days, subject\_to\_demand |
| Prepayment terms | has\_prepayment\_premium, lockout\_end\_date, yield\_maintenance\_end\_date, prepayment\_premium\_end\_date, has\_negative\_amortization |

**Property fields exposed by the test library**

| Group | Fields |
| --- | --- |
| Identity and location | loan\_id, name, address, city, state, zip, county, property\_type, status, defeased\_status |
| Physical | units, units\_securitization, sqft, sqft\_securitization, year\_built, year\_renovated |
| Valuation | valuation, valuation\_source, valuation\_date |
| Occupancy and tenants | occupancy\_securitization, occupancy\_current, tenant\_1/2/3 name, square feet and lease expiry |
| Financials | financials\_date\_securitization, financials\_start\_date, financials\_end\_date, revenue, opex, noi, ncf (each at securitization and current), debt\_service\_current |
| Coverage | dscr\_noi and dscr\_ncf (each at securitization and current) |

**Fields in the raw XML that the test library did not expose (examples seen)**

- Liquidation or prepayment code and date, and realized loss to trust.
- Likely also special-servicing, workout and modification detail; the tag census in section 7 must list them.

**Raw file conventions seen**

- Root namespace `.../absee/cmbs/assetdata`; one `<assets>` element per loan or property record; property detail nested in a `<property>` block.
- Asset type is "Prospectus Loan ID"; dates are MM-DD-YYYY text.

**Property type codes observed (property-period rows in the sample)**

| Code | Likely meaning | Rows |
| --- | --- | --- |
| OF | Office | 34,844 |
| RT | Retail | 33,441 |
| LO | Lodging | 30,210 |
| IN | Industrial | 28,332 |
| MF | Multifamily | 16,860 |
| SS | Self-storage | 15,076 |
| MU | Mixed use | 7,259 |
| CH | Cooperative housing (verify) | 4,802 |
| MH | Mobile home park | 3,954 |
| SE | Securities (verify) | 2,802 |
| 98 | Other | 2,393 |
| WH | Warehouse | 1,800 |

**Payment status codes observed (populated loan rows)**

| Code | Rows | Likely meaning (verify) |
| --- | --- | --- |
| 0 | 75,330 | Current |
| A | 273 | Not yet received, within grace period |
| B | 1,661 | Late, under 30 days |
| 1 | 373 | 30–59 days delinquent |
| 2 | 213 | 60–89 days delinquent |
| 3 | 1,443 | 90 or more days delinquent |
| 4 | 63 | Matured balloon, performing or non-performing |
| 5 | 270 | Matured balloon, performing or non-performing |

**Loan structure codes observed:** WL whole loan (65,613 rows), PP pari passu piece (16,734), A1 (4,462), A2 (420), B1 (1). **Valuation source:** MAI appraisal (178,688), non-MAI (200), other code 98 (28).

**Observed non-null rates, property rows:** valuation 97.8%, NOI at securitization 86.4%, current occupancy 74.3%, current NOI 66.1%, current DSCR (NOI) 66.0%, square feet 60.9%, largest tenant name 52.7%, units 37.6%.

## Appendix B. Open decisions

Ten decisions shape the build; each has a recommended default, so none blocks starting.

| # | Decision | Options | Recommended default | Why it matters |
| --- | --- | --- | --- | --- |
| 1 | Universe depth | Full monthly history for all registered CMBS 2017+, or a stratified subset of deal families | Full universe | Coverage is the credibility claim; ingestion is resumable |
| 2 | Where the full pull runs | Your own computer, or a cloud machine | Your own computer, with the contact string in an environment variable | Multi-gigabyte raw storage; keeps the contact string off shared systems |
| 3 | Agency multifamily benchmark | Skip, or add FHFA and Freddie Mac loan-level data | Skip at first; add if multifamily depth looks thin | Agency loans are a different, healthier population |
| 4 | Second case-study market | Los Angeles only, or LA plus one contrast market | Los Angeles only | Depth beats breadth in a memo |
| 5 | Underwriting depth | Full cash flow for tier A and B types only, or all types | Tier A and B, with direct cap only for the rest | Lodging and mixed use need specialist inputs |
| 6 | Source for lender-sizing parameters | Published lender surveys and commentary, or a practitioner's view | Cited public sources, then a practitioner review | These parameters drive the refinance gap |
| 7 | Site technology | Plain JavaScript with D3 and MapLibre over JSON, or add DuckDB-WASM | Plain JavaScript and JSON first | Simpler to host and debug; add WASM only if file sizes require it |
| 8 | Loan-level exposure | Show property addresses, or aggregate to ZIP and submarket | Show property facts from filings, hide tenant names | Balances usefulness against reputational risk |
| 9 | Publication clearance | Publish under your name now, or after confirming employer or internship policies | Confirm policies before any public page goes live | Avoids a conflict you cannot undo after publishing |
| 10 | Methodology reviewer | Self-review only, or one practitioner reads the methodology page | One practitioner review, for example a contact at a brokerage or lender | The single most credible quality signal to the target audience |

**Verified so far, so no re-checking is needed.** EDGAR access works with a declared contact string; 57 trusts and about 375,000 loan and property rows were parsed; the loan-versus-property record structure and the library's field gap were traced to the raw XML.

**Not yet verified, to resolve in the build.** Code meanings (payment status, liquidation, special servicing); the rate of pari passu duplicates across trusts; the share of 2016-vintage deals with structured data; how many tier 1 maturity outcomes exist in the full universe; and current availability and terms of each outside data source.
