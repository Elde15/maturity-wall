import datetime as dt

from mwall.parse.loan_detail import parse_part1_row, parse_prepayment_row

FULL = ["12", "10104328", "1", "LO", "Weehawken", "NJ", "Actual/360", "4.990%", "70,362.47", "0.00", "0.00", "N/A",
        "10/06/25", "10/06/27", "16,375,000.00", "16,375,000.00", "09/06/26"]


def test_full_row_with_loan_group():
    r = parse_part1_row(FULL)
    assert r["loan_group"] == "1" and r["prop_type"] == "LO" and r["city"] == "Weehawken" and r["state"] == "NJ"
    assert r["original_maturity_date"] == dt.date(2025, 10, 6) and r["adjusted_maturity_date"] == dt.date(2027, 10, 6)
    assert r["ending_balance"] == 16_375_000.0 and abs(r["gross_rate"] - 0.0499) < 1e-12


def test_row_without_group_and_dash_for_unadjusted_maturity():
    r = parse_part1_row(["1", "310937980", "OF", "Jersey City", "NJ", "Actual/360", "3.117%", "143,598.46", "0.00",
                         "0.00", "N/A", "10/11/26", "--", "53,500,000.00", "53,500,000.00", "04/11/23"])
    assert r["loan_group"] is None and r["city"] == "Jersey City" and r["adjusted_maturity_date"] is None


def test_note_row_and_lettered_id():
    r = parse_part1_row(["2B", "656100518", "Actual/360", "4.229%", "109,249.17", "0.00", "0.00", "N/A", "02/06/26",
                         "--", "30,000,000.00", "30,000,000.00", "06/06/23"])
    assert r["pros_id"] == "2B" and r["prop_type"] is None and r["ending_balance"] == 30_000_000.0


def test_merged_cell_is_split():
    r = parse_part1_row(["90", "28000841", "RT", "Mercedes", "TX", "Actual/360", "5.440%", "3,867.01", "0.00",
                         "0.00 02/06/26", "02/06/31", "--", "825,500.00", "825,500.00", "02/06/24"])
    assert r["anticipated_repay_date"] == dt.date(2026, 2, 6) and r["original_maturity_date"] == dt.date(2031, 2, 6)


def test_missing_property_type_moves_to_city():
    r = parse_part1_row(["7", "123456", "Various", "Baton Rouge", "LA", "Actual/360", "4.000%", "1.00", "0.00", "0.00",
                         "N/A", "01/01/26", "--", "5.00", "5.00", "12/01/25"])
    assert r["prop_type"] is None and r["city"] == "Various Baton Rouge" and r["state"] == "LA"


def test_bad_shape_is_rejected_not_guessed():
    bad = list(FULL)
    bad[7] = "4.990"  # rate without %
    assert parse_part1_row(bad) is None


def test_prepayment_row_reads_written_code():
    r = parse_prepayment_row(["17", "10104332", "1", "10,113,308.80", "Disposition", "0.00", "0.00"])
    assert r["unscheduled_principal"] == 10_113_308.80 and r["prepayment_code"] == "Disposition"


def test_citi_new_layout_with_split_percent_and_dash_amounts():
    from mwall.parse.loan_detail import citi_layout, parse_citi_row

    r = ["306291111", "1", "RT", "Nashville", "TN", "06/01/2023", "4.09200", "%", "246,656.67", "-",
         "70,000,000.00", "70,000,000.00", "07/01/2026", "0", "0", "0"]
    assert citi_layout(r) == "new"
    x = parse_citi_row(r)
    assert x["gross_rate"] == 0.04092 and x["sched_principal"] == 0.0 and x["ending_balance"] == 70_000_000.0
    assert x["original_maturity_date"] == dt.date(2026, 7, 1) and x["paid_through_date"] == dt.date(2023, 6, 1)
    assert (x["prop_type"], x["city"], x["state"]) == ("RT", "Nashville", "TN")


def test_citi_payoff_row_and_unknown_state():
    from mwall.parse.loan_detail import parse_citi_row

    x = parse_citi_row(["30311806", "16", "OF", "Various", "XX", "10/06/2026", "3.70000%", "44,708.33",
                        "14,500,000.00", "14,500,000.00", "-", "10/06/2026", "0", "0", "0"])
    assert x["sched_principal"] == x["beginning_balance"] == 14_500_000.0 and x["ending_balance"] == 0.0
    assert x["state"] is None and x["city"] == "Various"


def test_citi_old_layout_merged_cell_note_letter_and_lettered_id():
    from mwall.parse.loan_detail import citi_layout, parse_citi_old_row

    merged = ["030311419", "005", "MF", "Dallas", "TX", "120,500.00", "0.00", "4.82000", "%", "8/6/26", "N",
              "30,000,000.00", "30,000,000.00 10/11/18", "N/A", "0.00", "0", "0", "0"]
    assert citi_layout(merged) == "old"
    x = parse_citi_old_row(merged)
    assert x["ending_balance"] == 30_000_000.0 and x["paid_through_date"] == dt.date(2018, 10, 11)
    assert x["original_maturity_date"] == dt.date(2026, 8, 6)
    note = parse_citi_old_row(["030311654", "A5", "B", "RT", "Nashville", "TN", "68,200.00", "0.00", "4.09200", "%",
                               "7/1/26", "N", "20,000,000.00", "20,000,000.00", "11/1/18", "N/A", "0.00", "B", "0", "0"])
    assert note["pros_id"] == "A5" and note["prop_type"] == "RT" and note["city"] == "Nashville"
    fused = parse_citi_old_row(["656120487", "08A RT", "New York", "NY", "78,166.67", "574,861.68", "4.69000", "%",
                                "1/6/26", "N", "20,000,000.00", "19,425,138.32", "6/6/19", "N/A", "0.00", "B", "1", "4"])
    assert fused["pros_id"] == "08A" and fused["prop_type"] == "RT" and fused["sched_principal"] == 574_861.68


def test_citi_row_without_prospectus_id_or_property():
    from mwall.parse.loan_detail import parse_citi_row

    x = parse_citi_row(["305711058", "N/A", "01/01/2025", "5.05000%", "18,800.40", "4,839.73", "4,323,311.77",
                        "4,318,472.04", "03/01/2026", "0", "0", "0"])
    assert x["pros_id"] is None and x["ending_balance"] == 4_318_472.04 and x["prop_type"] is None
