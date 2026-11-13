import numpy as np
import pandas as pd

from mwall.panel.build import events, tier1, tier2


def _loan(rk, months, status, balance, codes=None, maturity="2024-06-06", ss=None, mod=None, loss=None):
    n = len(months)
    return pd.DataFrame({
        "root_key": rk, "trust_cik": 1, "period_end": pd.to_datetime(months), "filing_date": pd.to_datetime(months),
        "balance": balance, "payment_status": status,
        "liq_codes": [[c] if c else [] for c in (codes or [None] * n)],
        "realized_loss": loss or [0.0] * n,
        "ss_transfer_date": pd.to_datetime(ss or [None] * n), "ss_return_date": pd.NaT,
        "mod_this_period": mod or [False] * n, "last_mod_date": pd.NaT,
        "maturity_date": pd.to_datetime(maturity), "ard_date": pd.NaT, "defeased": False,
        "property_group": "office", "prop_type_code": "OF",
    })


def _months(start, n):
    return [d.strftime("%Y-%m-11") for d in pd.date_range(start, periods=n, freq="MS")]


def test_distress_within_12_months():
    m = _months("2022-01-01", 14)
    status = ["0"] * 8 + ["1", "2", "3", "3", "3", "3"]
    p = tier2(events(_loan("a", m, status, [10.0] * 14)))
    # January 2022 is performing and the loan is 60+ days delinquent in October 2022
    assert p.loc[0, "y_distress_12m"] == 1.0
    # months already delinquent are not performing, so they carry no label
    assert np.isnan(p.loc[10, "y_distress_12m"])


def test_quiet_year_is_zero_and_short_tail_is_censored():
    m = _months("2022-01-01", 18)
    p = tier2(events(_loan("b", m, ["0"] * 18, [10.0] * 18)))
    assert p.loc[0, "y_distress_12m"] == 0.0
    assert np.isnan(p.loc[10, "y_distress_12m"])  # only 7 months left in the data


def test_sticky_modification_flag_counts_once():
    m = _months("2022-01-01", 6)
    p = events(_loan("c", m, ["0"] * 6, [10.0] * 6, mod=[False, True, True, True, True, True]))
    assert p["ev_modification"].tolist() == [False, True, False, False, False, False]


def test_special_servicing_transfer_is_an_event_only_when_new():
    m = _months("2022-01-01", 4)
    ss = [None, "2022-02-03", "2022-02-03", "2022-02-03"]
    p = events(_loan("d", m, ["0"] * 4, [10.0] * 4, ss=ss))
    assert p["ev_ss_transfer"].tolist() == [False, True, False, False]


def test_tier1_paid_failed_and_early():
    m = _months("2023-01-01", 24)
    paid = _loan("paid", m, ["0"] * 24, [10.0] * 17 + [0.0] * 7, codes=[None] * 17 + ["5"] * 7)
    failed = _loan("failed", m, ["0"] * 17 + ["5"] * 7, [10.0] * 24)
    early = _loan("early", m, ["0"] * 24, [10.0] * 2 + [0.0] * 22, codes=[None] * 2 + ["2"] * 22)
    p = events(pd.concat([paid, failed, early], ignore_index=True))
    t1 = tier1(p, pd.Series({1: pd.Timestamp("2024-12-11")})).set_index("root_key")
    assert t1.loc["paid", "outcome"] == "paid" and t1.loc["paid", "y_fail"] == 0.0
    assert t1.loc["failed", "outcome"] == "failed" and t1.loc["failed", "y_fail"] == 1.0
    assert t1.loc["early", "outcome"] == "excluded_early_payoff"
