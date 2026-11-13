# Gate 2 leakage audit

Generated 2026-11-13 by `python -m mwall features --audit`. Rules: SOP section 9. The snapshot date T of a row is its EDGAR filing date.

**Verdict: PASS.**

| check | result | evidence |
| --- | --- | --- |
| No feature uses an outcome field as input | PASS | 69 catalog entries checked against 12 outcome fields |
| Market values were published on or before the snapshot date | PASS | `asof_treasury`: 0 later of 1,102,379 joined; `asof_zori`: 0 later of 977,925 joined; `asof_zori_mf`: 0 later of 948,658 joined; `asof_qcew`: 0 later of 1,004,721 joined; `asof_qcew_office`: 0 later of 789,808 joined; `asof_permits`: 0 later of 950,963 joined; `asof_cap_rate`: 0 later of 774,913 joined; `asof_spread`: 0 later of 1,102,379 joined |
| Truncation replay has power: a deliberately leaky canary feature is caught | PASS | the canary (each loan's last balance in the data) changed in 39,170 row comparisons |
| Truncation replay: features unchanged when later filings are removed | PASS | 600 loans (seed 7), cuts 2019-12-31, 2021-12-31, 2023-06-30, 2025-06-30, 64,144 row comparisons x 44 features |
| Labeled months are performing at T, so the label window starts after the status it sees | PASS | 100.0% of performing months are current or under 30 days late; the tier 2 window counts only events in later filings |
| Late snapshots are flagged and excluded from training | PASS | 7,229 rows (0.66%) filed more than 60 days after their period or after the loan's next period |

## Truncation replay detail

| feature | 2019-12-31 | 2021-12-31 | 2023-06-30 | 2025-06-30 |
| --- | --- | --- | --- | --- |
| f_ab_structure | 0 | 0 | 0 | 0 |
| f_advances_other | 0 | 0 | 0 | 0 |
| f_advances_pct | 0 | 0 | 0 | 0 |
| f_advances_pi | 0 | 0 | 0 | 0 |
| f_advances_ti | 0 | 0 | 0 | 0 |
| f_balance_per_sqft | 0 | 0 | 0 | 0 |
| f_balance_per_unit | 0 | 0 | 0 | 0 |
| f_balloon_share | 0 | 0 | 0 | 0 |
| f_cooperative | 0 | 0 | 0 | 0 |
| f_coupon | 0 | 0 | 0 | 0 |
| f_debt_outside_trust | 0 | 0 | 0 | 0 |
| f_debt_yield_ncf | 0 | 0 | 0 | 0 |
| f_debt_yield_noi | 0 | 0 | 0 | 0 |
| f_dscr_disagree | 0 | 0 | 0 | 0 |
| f_dscr_noi_recomputed | 0 | 0 | 0 | 0 |
| f_dscr_noi_reported | 0 | 0 | 0 | 0 |
| f_ever_modified | 0 | 0 | 0 | 0 |
| f_ever_special_serviced | 0 | 0 | 0 | 0 |
| f_expense_ratio | 0 | 0 | 0 | 0 |
| f_extended | 0 | 0 | 0 | 0 |
| f_full_term_io | 0 | 0 | 0 | 0 |
| f_in_special_servicing | 0 | 0 | 0 | 0 |
| f_io_remaining_months | 0 | 0 | 0 | 0 |
| f_ltv_recent | 0 | 0 | 0 | 0 |
| f_ltv_securitization | 0 | 0 | 0 | 0 |
| f_months_to_maturity | 0 | 0 | 0 | 0 |
| f_n_notes_in_trust | 0 | 0 | 0 | 0 |
| f_n_properties | 0 | 0 | 0 | 0 |
| f_noi_age_months | 0 | 0 | 0 | 0 |
| f_noi_missing | 0 | 0 | 0 | 0 |
| f_noi_vs_securitization | 0 | 0 | 0 | 0 |
| f_noi_yoy | 0 | 0 | 0 | 0 |
| f_occupancy | 0 | 0 | 0 | 0 |
| f_occupancy_change | 0 | 0 | 0 | 0 |
| f_pari_passu_piece | 0 | 0 | 0 | 0 |
| f_property_age_years | 0 | 0 | 0 | 0 |
| f_reappraised | 0 | 0 | 0 | 0 |
| f_rollover_24m | 0 | 0 | 0 | 0 |
| f_seasoning_months | 0 | 0 | 0 | 0 |
| f_single_asset | 0 | 0 | 0 | 0 |
| f_tenant1_share | 0 | 0 | 0 | 0 |
| f_term_months | 0 | 0 | 0 | 0 |
| f_trust_share | 0 | 0 | 0 | 0 |
| f_years_since_renovation | 0 | 0 | 0 | 0 |

## Hindsight in the cleaning layer (declared, not hidden)

These choices use the full filing history to decide which rows exist or how loans group. They change no feature value of a row that exists; each is listed with its size.

| choice | where | effect on features | size |
| --- | --- | --- | --- |
| One filing per XML period: the latest filed wins (D036), so an amendment replaces the original | `clean/screen.py` | the amendment's values are used; rows filed long after their period are flagged `flag_late_snapshot` and kept out of training | 7,229 rows |
| Records from another deal (transient loans, foreign records, corrupt filings) are dropped using the loan's whole history (D035, D036) | `clean/run.py` | removes rows that are not this trust's loans; a real-time scorer would have seen them | see docs/qa/gate1_report.md |
| Whole-loan grouping across trusts uses every filing (D027) | `clean/whole_loans.py` | used for deduplicated counts and grouped validation splits, not as a feature; `f_pari_passu_piece` comes from the same filing's trust share | n/a |
| Market series are today's vintage (Zillow, QCEW, permits and housing estimates are revised after first release) | `features/market.py` | a small look-ahead through revisions; Treasury yields are not revised | all market features |
| Lender limits (LTV, DSCR, debt yield, amortization) and property-type spread premiums are fixed cited constants; most sources date from 2022 to 2026, with the OCC handbook (2013) as the pre-2017 anchor | `config/lender_params.csv` | a structural assumption applied to every year, not data about any loan; the spread itself is CBRE's dated series, used from its publication date (`asof_spread`) | refinance features |
| CBRE published no spread level for 2016Q2 to 2018Q1 and 2018Q3 to 2020Q1, so the last published value carries forward | `config/lender_spreads.csv` | stale, not forward-looking: 2017 and 2018 refinance rates use the wide 2016Q1 spread | refinance features in those years |
