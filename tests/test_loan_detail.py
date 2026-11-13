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
