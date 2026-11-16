# Outcome labels

Definitions for SOP section 10, written before any label code (SOP: "the label code must not be written until these are documented"). Code meanings come from the SEC XSD and are listed in `docs/sec_code_tables.md`; the section numbers below point there.

## Panel unit

One row per loan position per reporting month, from its first appearance to a terminal event or the trust's last filing. A loan position is a root number in a trust (`root_key`), so notes of one loan held by the same trust count once. Rows from filings flagged corrupt, and records flagged transient or foreign, are left out (D035, D036, D039).

The same whole loan can sit in several trusts as pari passu pieces. Those positions share property, NOI and outcome, so for modeling and validation they are one loan: every row carries `whole_loan_id`, folds are grouped on it, and `is_representative` marks one position per whole loan and month (the largest trust balance) for fitting and for event counts.

Defeased loans (property type `SE`, or `DefeasedStatusCode` set) carry no refinance risk and are excluded from tiers 1 and 2. Their share is reported.

## Events (section 3 references are to `sec_code_tables.md`)

| Event | Rule | Fields |
| --- | --- | --- |
| Paid in full | Balance reaches zero with `liquidationPrepaymentCode` 2 (payoff before maturity), 5 (full payoff at maturity), 8 (payoff with penalty) or 9 (payoff with yield maintenance) | 3.3 |
| Liquidation | Code 3 (disposition/liquidation) or 6 (discounted payoff), or `realizedLossToTrustAmount` above zero | 3.3 |
| Removed | Code 4 (repurchase/substitution): censored, not an outcome | 3.3 |
| 60+ days delinquent | `paymentStatusLoanCode` 2 or 3 | 3.1 |
| Matured, not paying | `paymentStatusLoanCode` 5 | 3.1 |
| Special servicing transfer | `mostRecentSpecialServicerTransferDate` takes a value later than any the loan carried before | 3.4 |
| Modification | `reportPeriodModificationIndicator` switches on together with at least one detail of the modification (`modificationCode`, `lastModificationDate` or a post-modification term), or `lastModificationDate` takes a new value (D045) | 3.5 |

Distress is any of: 60+ days delinquent, matured not paying, special servicing transfer, modification, liquidation.

## Tier 1: maturity outcome (gold set)

Unit: one loan position whose maturity date falls on or before the last filing date less 90 days. The maturity date is the one the loan carried in its first filing, so an extension cannot hide a failure; for a loan with an anticipated repayment date, that date is used instead, since it is when the borrower is expected to refinance.

- 0: paid in full at most 12 months before maturity, or by 90 days after it.
- 1: still outstanding 90 days after maturity (balance above zero in a filing whose period ends more than 90 days past it), or liquidated after the 12 months before maturity began. A loan that shows code 5 but pays in full inside the 90 days is a 0, as the SOP defines it.
- Excluded: loans paid off or liquidated more than 12 months before maturity (reported as the survivorship share), loans removed (code 4), defeased loans, and loans whose last appearance comes before maturity plus 90 days with no payoff code (outcome unknown, counted).

The 90-day grace window is the SOP default; the robustness suite reruns at 60 and 120 days.

## Tier 2: forward distress (main training set)

Unit: every loan-month T where the loan is performing: payment status 0, A or B (a blank status is read from the paid-through date, D055); not in special servicing (no transfer date after the last return date); not matured; not defeased.

- 1: a distress event occurs in the 12 months after T (filings dated after T and up to T + 12 months).
- 0: no distress event in that window, and the loan is observed through T + 12 months or paid in full inside it.
- Censored (no label): the loan's observation ends before T + 12 months without an event or payoff.
- `label_window_complete`: T + 12 months falls inside the trust's data. Near the end of the data a month can only be labeled early when an event has already happened (47.3% positive against 2.7% for complete windows), so models train and test on complete windows only.

Status at T is a feature, never part of the label window.

## Tier 3: loss severity

Unit: each liquidated loan. Severity = cumulative `realizedLossToTrustAmount` ÷ balance at the last filing before liquidation. Loans with a liquidation code but no reported loss are kept at severity 0 and flagged, since losses are often booked in later periods.

## Counts

Label counts by tier, property type and vintage, including the number of tier 1 events, are published in `docs/qa/gate2_labels.md`.
