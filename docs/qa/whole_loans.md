# Whole loans across trusts

Pieces of one whole loan held by different trusts are grouped on property ZIP, origination date, maturity date and coupon (`clean/whole_loans.py`).

- Loans (latest record each): 13,973; with a usable match key: 12,214.
- Whole loans held by more than one registered trust: 933 (by trust count: {2: 620, 3: 172, 4: 64, 5: 32, 6: 22, 7: 6, 8: 4, 10: 3, 11: 2, 12: 1, 13: 3, 14: 2, 15: 1, 19: 1}).
- Trust-level records that belong to a multi-trust whole loan: 2,560 of 13,258.
- Pari passu or A/B-note pieces matched to at least one other registered trust: 77.9%. The rest have their companion notes in unregistered (144A) deals or in trusts not yet ingested.

Effect on aggregates if trusts were simply summed:

- Appraised value at securitization: $1,626.8B summed vs $728.0B counting each whole loan once (123.5% overstatement).
- Annualized NOI: $68.13B summed vs $27.29B (149.6% overstatement).

Rule for every published aggregate of collateral (NOI, value, square feet, property counts): count each `whole_loan_id` once. Balances are not affected, because each trust reports only its own piece.

