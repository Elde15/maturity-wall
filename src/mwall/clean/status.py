"""Payment status where the filer leaves it blank (decision D055).

28 of 381 trusts leave `paymentStatusLoanCode` blank on most loans (79,659 loan-months, 7% of the panel). Their
`paidThroughDate` says what the code would: across every record with both fields, code 0 (current) is paid
through within 31 days of the period end 99.7% of the time, code B (late, under 30 days) is 32 to 62 days behind
88% of the time, and codes 1 to 3 are further behind. Blank records with a paid-through date are paid through
within 31 days 99.9% of the time. So a blank code is read from the paid-through date: within 31 days is current
(0), 32 to 62 days is late under 30 days (B), and anything else, or no date, stays blank. A reported code always
wins, and no delinquency code is inferred.
"""
from __future__ import annotations

CURRENT_DAYS, LATE_DAYS = 31, 62


def _lag(pe: str) -> str:
    return f"datediff('day', try_cast(paidThroughDate as date), {pe})"


def status_sql(pe: str) -> str:
    """SQL expression: the reported code, else the code implied by the paid-through date at period end `pe`."""
    return (f"coalesce(cast(paymentStatusLoanCode as varchar), case when {_lag(pe)} <= {CURRENT_DAYS} then '0' "
            f"when {_lag(pe)} <= {LATE_DAYS} then 'B' end)")


def inferred_sql(pe: str) -> str:
    """SQL expression: true where the code was blank and has been inferred."""
    return f"(paymentStatusLoanCode is null and {_lag(pe)} <= {LATE_DAYS})"


def bucket_sql(pe: str) -> str:
    """SQL expression: the delinquency bucket, filled from the inferred code where the reported one is blank."""
    return (f"coalesce(delinquency_bucket, case when {_lag(pe)} <= {CURRENT_DAYS} then 'current' "
            f"when {_lag(pe)} <= {LATE_DAYS} then 'late_lt30' end)")
