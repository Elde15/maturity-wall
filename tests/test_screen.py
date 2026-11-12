import pandas as pd

from mwall.clean.screen import one_filing_per_period, screen


def _asset(acc, seq, num, bal, orig="2019-09-12", mat="2029-10-01", end="2026-10-13", filed="2026-10-25", form="ABS-EE"):
    return {"accession": acc, "asset_seq": seq, "assetNumber": num, "form": form, "filing_date": filed,
            "reportPeriodEndScheduledLoanBalanceAmount": bal, "reportPeriodEndActualBalanceAmount": bal,
            "originationDate": orig, "maturityDate": mat, "reportingPeriodEndDate": end}


def _prop(acc, seq, name):
    return {"accession": acc, "asset_seq": seq, "property_seq": 0, "propertyName": name}


def test_exact_copies_dropped_with_their_properties():
    a = pd.DataFrame([_asset("A", 0, "1", 10.0), _asset("A", 1, "2", 5.0), _asset("A", 2, "1", 10.0)])
    p = pd.DataFrame([_prop("A", 0, "X"), _prop("A", 1, "Y"), _prop("A", 2, "X")])
    a2, p2, per = screen(a, p)
    assert sorted(a2["asset_seq"]) == [0, 1]
    assert sorted(p2["asset_seq"]) == [0, 1]
    assert per.loc[0, "n_exact_copies_dropped"] == 1
    assert per.loc[0, "corrupt_reason"] is None


def test_same_number_different_property_is_not_an_exact_copy():
    a = pd.DataFrame([_asset("A", 0, "1", 10.0), _asset("B", 0, "1", 10.0), _asset("B", 1, "1", 10.0)])
    p = pd.DataFrame([_prop("A", 0, "X"), _prop("B", 0, "X"), _prop("B", 1, "Z")])
    _, _, per = screen(a, p)
    assert per.set_index("accession").loc["B", "n_exact_copies_dropped"] == 0


def test_split_keeps_largest_and_renames_the_rest():
    a = pd.DataFrame([
        _asset("A", 0, "1", 68.0, end="2024-01-11"),           # history: loan 1 alone
        _asset("B", 0, "1", 5.05), _asset("B", 1, "1", 37.88),  # same dates, two balances
    ])
    a2, _, per = screen(a, pd.DataFrame(columns=["accession", "asset_seq", "property_seq"]))
    b = a2[a2["accession"] == "B"].set_index("asset_seq")
    assert b.loc[1, "assetNumber"] == "1" and b.loc[0, "assetNumber"] == "1-S2"
    row = per.set_index("accession").loc["B"]
    assert row["n_split_records"] == 1 and row["corrupt_reason"] is None


def test_repeat_with_foreign_dates_marks_the_filing_corrupt():
    a = pd.DataFrame([
        _asset("A", 0, "13", 15.9, orig="2018-04-24", end="2021-01-11"),
        _asset("B", 0, "13", 15.9, orig="2018-04-24"), _asset("B", 1, "13", 40.7, orig="2018-08-31"),
    ])
    _, _, per = screen(a, pd.DataFrame(columns=["accession", "asset_seq", "property_seq"]))
    row = per.set_index("accession").loc["B"]
    assert row["n_foreign_repeats"] == 1 and row["corrupt_reason"] is not None


def test_one_filing_per_xml_period():
    a = pd.DataFrame([
        _asset("orig", 0, "1", 1.0, end="2022-04-11", filed="2022-04-29"),
        _asset("amend", 0, "1", 1.0, end="2022-04-11", filed="2022-05-19", form="ABS-EE/A"),
        # EDGAR mislabels the next month's report date; the XML period differs, so both stay
        _asset("nov", 0, "1", 1.0, end="2019-11-12", filed="2019-12-02"),
        _asset("dec", 0, "1", 1.0, end="2019-12-11", filed="2019-12-31"),
    ])
    kept, _, sup = one_filing_per_period(a, pd.DataFrame(columns=["accession", "asset_seq"]))
    assert sorted(kept["accession"]) == ["amend", "dec", "nov"]
    assert sup.set_index("accession").loc["orig", "superseded_by"] == "amend"
