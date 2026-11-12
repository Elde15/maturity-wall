import pytest

from mwall.clean.asset_numbers import parse


@pytest.mark.parametrize(
    "raw,root,note,child",
    [
        ("15", 15, "", None),
        ("15.00", 15, "", None),
        ("2.0", 2, "", None),
        ("06", 6, "", None),
        ("15-001", 15, "", 1),
        ("3.01", 3, "", 1),
        ("2.138", 2, "", 138),
        ("26.001", 26, "", 1),
        ("4A", 4, "A", None),
        ("4B", 4, "B", None),
        ("6A-1", 6, "A-1", None),
        ("1-A-1", 1, "A-1", None),
        ("23-A-9", 23, "A-9", None),
        ("15 A-2-C5", 15, "A-2-C5", None),
        ("6 A-1", 6, "A-1", None),
        ("06A2C", 6, "A2C", None),
        ("13A1B3", 13, "A1B3", None),
        ("4A2B", 4, "A2B", None),
    ],
)
def test_grammar(raw, root, note, child):
    a = parse(raw)
    assert a.ok
    assert (a.root, a.note, a.child) == (root, note, child)


def test_loan_ids_distinguish_notes():
    assert parse("4").loan_id == "4"
    assert parse("4.00").loan_id == "4"
    assert parse("4A").loan_id == "4-A"
    assert parse("6A-1").loan_id == "6-A-1"
    assert parse("6 A-1").loan_id == "6-A-1"
    assert parse("4-001").loan_id is None


@pytest.mark.parametrize("raw", ["", None, "ABC", "1-2-3-4", "1..2"])
def test_unparseable(raw):
    assert not parse(raw).ok
