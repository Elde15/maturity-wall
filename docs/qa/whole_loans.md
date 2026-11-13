# Whole loans across trusts

Pieces of one whole loan held by different trusts are grouped on property ZIP, origination date, maturity date and coupon (`clean/whole_loans.py`).

- Loans (latest record each): 19,020; with a usable match key: 16,258.
- Whole loans held by more than one registered trust: 1,650 (by trust count: {2: 1112, 3: 332, 4: 84, 5: 56, 6: 32, 7: 11, 8: 9, 10: 3, 11: 3, 12: 1, 13: 3, 14: 3, 19: 1}).
- Trust-level records that belong to a multi-trust whole loan: 4,400 of 17,470.
- Pari passu or A/B-note pieces matched to at least one other registered trust: 82.0%. The rest have their companion notes in unregistered (144A) deals or in trusts not yet ingested.

Effect on aggregates if trusts were simply summed:

- Appraised value at securitization: $2,110.0B summed vs $917.1B counting each whole loan once (130.1% overstatement).
- Annualized NOI: $80.51B summed vs $30.11B (167.4% overstatement).

Rule for every published aggregate of collateral (NOI, value, square feet, property counts): count each `whole_loan_id` once. Balances are not affected, because each trust reports only its own piece.

