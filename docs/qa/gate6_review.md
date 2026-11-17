# Gate 6: second reader's review

A reader outside the project read three documents cold, in order: the method page and the Los Angeles page (printed to
PDF) and the Los Angeles memo. The brief asked for clarity, not a math check: anything read twice, undefined, unsupported,
contradictory, missing for a commercial real estate or credit reader, more certain than its evidence, or hard to read.
They returned 57 notes on 2026-11-16. Every note was acted on; none was waived. Decisions D064 (an engine fix the reader's
notes exposed) and D065 (the review itself) record the changes that go beyond wording.

## The reader's three priorities

1. **Deal with the refinance-gap tension up front.** The method page now opens with three lines on how far to trust the
   numbers (rankings held up, probability levels drift, the gap measures exposure rather than default), and the Los
   Angeles summary and the home page say the same in their own words (notes 16, 17, 27).
2. **Make every case-file number follow from the sentence before it.** Each case file names the NOI capitalized and the
   cap rate behind each value, says which model the table's "Model" row shows, and states its probabilities with their
   rank. Two values didn't follow because the engine overstated them (D064); they now equal NOI over the cap rate
   (notes 38, 40, 44, 47, 48).
3. **Add the missing reference material and strip internal labels.** Definitions of the base ratios, a table of today's
   refinance terms, the risk-band cutoffs, the direction of each review-priority rank, and plain links in place of
   project labels (notes 3, 13, 20, 23, 31).

## Every note

| # | Where | Note, in short | Disposition |
|---|---|---|---|
| 1 | Method, data | "Namespace" is jargon | Fixed: "checking which filers' exhibits use the SEC's CMBS loan template" |
| 2 | Method, data | No national balance or split by type | Fixed: $313.2B and the balance and loan count of each type |
| 3 | Method, definitions | Base ratios and abbreviations undefined | Fixed: NOI, cap rate, LTV, DSCR and debt yield defined first; pari passu, Form 10-D, KBRA, IRT and Greystone spelled out |
| 4 | Method, value | "Stressed NOI" contradicts Base | Fixed: "NOI after the scenario's haircut (none in Base)", with a worked spread example |
| 5 | Method, value | Benchmark fallback unstated | Fixed: stated, with counts (1,171 loans on today's benchmark alone; 3,028 on the composite) |
| 6 | Method, implied bid | Two definitions in one; "refinanceable by sale" | Fixed: separate entries; "a sale at the bid would cover the loan" (also on the tear sheet) |
| 7 | Method, tier | Tier definition contradicts the parameter table | Fixed: definition now matches the code (stale or partial NOI drops one tier; no square feet or units drops to C; zero, negative or 36-month-old NOI gets no tier) |
| 8 | Method, models | One model, three names; 2.5 months unexplained | Fixed: "maturity model" everywhere (method, loans page, tear sheet, data dictionary); the 2.5-month cutoff is stated as a design choice with its reason |
| 9 | Method, test design | Timeline hard to follow | Fixed: four-step timeline (train, tune and calibrate, D on January 1, test) |
| 10 | Method vs LA | Three debt-yield thresholds | Fixed: lists every threshold tested, which the table shows, and why the maturity tests and the Los Angeles rule use 8% |
| 11 | Method, distress table | Calibration slope unexplained, shown for rules | Fixed: defined above the table; shown for the model only |
| 12 | Method, distress table | Fourth-decimal Brier, no PR-AUC ranges | Fixed: Brier skill column (improvement on the base rate) and a 90% PR-AUC range from 200 whole-loan resamples for the model and the debt-yield rank |
| 13 | Method | Internal labels (Gate 3 runs, model card, D057, SOP 12, row 44) | Fixed: plain links to the files in the repository; the plan reference and row numbers are gone from reader-facing text |
| 14 | Method, calibration | Axes unlabeled; "the COVID year" ambiguous | Fixed: axes labeled; the calibration window named (late 2019 to late 2020) |
| 15 | Method, maturity table | Final vs test models; best rule unnamed; strong claim | Fixed: one sentence on final versus test models; the best rule named each year; the claim gives its margins (0.06 to 0.17) and calls them rough |
| 16 | Method vs LA | "Relative risk" while case files quote levels | Fixed: case files lead with the rank (for example, rank 90 of 529 office loans, estimate 88%) |
| 17 | Method, failures | Gap barely predicts failure, yet headlines | Fixed: a paragraph on what the gap measures and why it still leads, plus the trust lines at the top of the page |
| 18 | Method, coverage | How much lower than Trepp? | Fixed: 2.5% against Trepp's 5.2% on average |
| 19 | Method, step 1 | "Value solves for it" cryptic; direction unstated | Fixed: explained plainly, with the direction. The reader's suspicion behind rows 40 and 44 was right: the engine is fixed (D064) |
| 20 | Method, step 2 | Sizing floors and rates nowhere | Fixed: table of today's terms by type (LTV, DSCR, debt yield, amortization, spread, refinance rate) with the Treasury and spread dates |
| 21 | Method, step 3 | Solver detail | Moved to small print |
| 22 | Method, verification | "To the cent" read as proof | Fixed: "That checks the arithmetic, not the assumptions" |
| 23 | Method, score | Rank directions; buy-list framing | Fixed: every rank's direction given, equal weights explained; shown as "review priority" (Loans column "Priority", case labels) |
| 24 | Method, limitations | Direction of appraisal bias | Fixed: richer appraisals mean lower cap rates and higher values and bids; Los Angeles runs richer still |
| 25 | Method, limitations | Missing CRE items | Fixed: extensions count as failure, fixed versus floating, DSCR on an amortizing payment, defeased loans excluded, and the weakest assumptions named |
| 26 | Method, sources | Labels look like copy errors | Fixed: delinquency reports labeled by data month and publication date |
| 27 | LA, summary | "Would" too certain | Fixed: "By the model's estimate"; page title "an estimated $2.7B" |
| 28 | LA, summary | "Modeled exit" undefined | Fixed: "the modeled sale at the end of a five-year hold" |
| 29 | LA, maturity chart | Thin 2026, 2029 spike | Fixed: caption explains both |
| 30 | LA, gap chart | Question unanswered; denominator | Fixed: takeaway names the exceptions (lodging 60% against 32%; self-storage 13% against 45%) and the 61 loans with no refinance test |
| 31 | LA, risk bands | Cutoffs undefined | Fixed: cutoffs stated (50% and 25%; 6.2% and 2.9%) |
| 32 | LA, scenarios | Value-add equals Base | Fixed: one line on why |
| 33 | LA, scenarios | Gap count vs bid-below count unremarked | Fixed: about 176 loans have a refinancing problem, not a value problem (290 with a gap, 114 with a bid below the balance after D064) |
| 34 | LA, cap spreads | Caption placement; missing types; no "so what" | Fixed: explanation above the table, missing types explained, direction sentence added |
| 35 | LA, Proposition 13 | 604 of 640 | Fixed: 31 multi-property loans and 5 without an appraisal date |
| 36 | LA, rent caps | Which caps bind? | Fixed: only the County ordinance binds (2 loans); 3% and 8.7% sit above the 2.0% growth path |
| 37 | LA and memo | Committed rule said four times | Fixed: once, with the commit, in the case-files introduction |
| 38 | LA, case 1 | Two models in one sentence; Model row switches | Fixed: one sentence on which model the row shows; the row gives "rank N of M" |
| 39 | LA, case 1 | Is the NOI drop real? | Fixed: the latest NOI is annualized from six months against a full prior year, and may be seasonal |
| 40 | LA, case 1 | $173.3M doesn't follow | Fixed by D064: $150.7M, which is $13.3M over 8.83%, shown in the text |
| 41 | LA, case 1 | Direction of the 2029 rollover | Fixed: the return bid already charges for it; the value bid doesn't |
| 42 | LA, case 2 | Why RESPARA tops the list | Fixed: the three ranks that drive it are named |
| 43 | LA, case 3 | $15.2M vs $15.3M | Fixed: the memo now rounds half up like the site ($15.3M) |
| 44 | LA, case 3 | $8.6M doesn't follow | Fixed by D064: $3.9M, which is $249K over 6.43% |
| 45 | LA, case 3 | 4.2% implausibly low | Fixed: rank 25 of 817 industrial loans, the riskiest 3%; the rank is the more reliable reading |
| 46 | LA, case 3 | Vacancy range omits 4.3% | Fixed: 4.3% (Cushman & Wakefield) to 6.0% (Kidder Mathews), CBRE 5.0% |
| 47 | LA, case 4 | 8.5% debt yield vs an under-8% rule | Fixed: the rule reads the models' filed debt yield (2.1%), which D059 did not change |
| 48 | LA, case 4 | Which inputs D059 fixed | Fixed: underwriting inputs, not the models' inputs, said in one sentence |
| 49 | LA, case 4 | Tier B for self-storage | Fixed: NOI annualized from under six months |
| 50 | LA, cases 4 and 5 | Certain phrasing | Fixed: "a sale at that bid would cover (or fall short of) the balance", written from the data; after D064 the storage loan falls $412K short |
| 51 | LA, case 5 | 7.1% read as a percentile | Fixed: "(7.1% probability)" |
| 52 | LA, case 5 | "Direct-capitalization value only" | Fixed: "value bid only" |
| 53 | Memo | No conclusion | Fixed: "What the five cases show", one lesson a case (also on the page) |
| 54 | Memo | Local rules section dropped | Fixed: "Three local rules" section |
| 55 | Memo | Row numbers; one URL four times | Fixed: one link a source, no row numbers |
| 56 | Memo | Relative links and repo paths | Fixed: full repository URLs; tear sheets described in words. The repository links resolve once the repository is public |
| 57 | Memo | Missing "not offers for the loan" | Fixed: in the header |

## Found while making the changes

- **The committed Los Angeles rule now picks a different third loan.** D064 lowered Vernon Industrial's value from
  $38.3M to $34.1M and put its bid below the balance; its review priority rose from 75.2 to 82.4, past the committed
  LA Creative Industrial Portfolio (80.9). The case files keep the committed pick, and the page and memo say what a
  rerun picks and why (D065).

## Checks after the changes

- `pytest`: 124 tests pass, including the hand-check workbook and the JavaScript engine matching Python on 50 loans.
- axe-core: 0 violations on all eight pages at 1280 and 390px; keyboard walk finds no stop without a visible outline
  or a name.
- Link crawl: 1,614 links on 23 rendered pages. 21 fail: the 14 known at Gate 5 (bot-blocked government and publisher
  pages, and the author's domain, not yet registered) and 7 links to files in this repository, which return 404 only
  because the repository is still private.
- Screenshots of the changed pages at both widths: no horizontal overflow, no console errors.

## Still open

- The reader has not seen the revised documents; the regenerated PDFs and memo are ready for a second pass.
- The repository links on the site start working when the repository is made public, a Gate 6 step that needs the
  author's approval.
