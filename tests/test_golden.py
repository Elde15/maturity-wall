"""Golden-file tests (SOP section 7 acceptance; Gate 1).

Five real EX-102 filings from four deal families and four filer agents, one per
record layout. Every expected value below was read from the raw XML with an
independent regex reader, not from this project's parser, and typed in by hand.
See docs/qa/golden_filings.md.
"""
from __future__ import annotations

import datetime as dt
from pathlib import Path

import pandas as pd
import pytest

from mwall.clean import structure
from mwall.parse import parser

GOLDEN = Path(__file__).parent / "golden"


def _parse(acc: str):
    return parser.parse_file(GOLDEN / f"{acc}.xml.gz")


def _resolve(acc: str, cik: int):
    res = _parse(acc)
    meta = {"trust_cik": cik, "accession": acc, "form": "ABS-EE", "filing_date": dt.date(2020, 1, 1),
            "is_period_winner": True}
    a = pd.DataFrame([{**meta, **r} for r in res.assets])
    p = pd.DataFrame([{**meta, **r} for r in res.properties])
    return res, *structure.resolve(a, p)


def _asset(res, number):
    return next(r for r in res.assets if r.get("assetNumber") == number)


def _prop(res, asset_number, seq=0):
    return next(p for p in res.properties if p["asset_number"] == asset_number and p["property_seq"] == seq)


# ---- 1. BANK 2017-BNK4, January 2024 (agent 0001888524): parent + children, split notes
def test_bnk4_parse():
    res = _parse("0001888524-24-001207")
    assert (res.n_assets_seen, len(res.properties)) == (72, 72)
    a = _asset(res, "1")
    assert a["reportPeriodEndActualBalanceAmount"] == 68677812.16
    assert a["paymentStatusLoanCode"] == "0"
    assert a["maturityDate"] == dt.date(2027, 3, 1)
    assert a["reportPeriodInterestRatePercentage"] == 0.04757905
    assert a["loanStructureCode"] == "PP"
    p = _prop(res, "1")
    assert p["propertyName"] == "D.C. Office Portfolio"
    assert p["mostRecentNetOperatingIncomeAmount"] == 3990480.75
    assert p["valuationSecuritizationAmount"] == 186800000.0
    assert p["mostRecentPhysicalOccupancyPercentage"] == 0.7
    p = _prop(res, "19-001")
    assert (p["propertyName"], p["propertyTypeCode"]) == ("SPRINGHILL SUITES BOCA RATON", "LO")
    assert p["mostRecentNetOperatingIncomeAmount"] == 1718436.95
    a = _asset(res, "48")
    assert a["reportPeriodEndActualBalanceAmount"] == 1672188.0
    assert _prop(res, "48")["propertyName"] == "Defeased"


def test_bnk4_structure():
    _res, loans, props = _resolve("0001888524-24-001207", 1698685)
    # 48 numbered loans plus notes 4A, 4B, 5A
    assert len(loans) == 51
    assert set(loans.loc[loans["note"] != "", "loan_id"]) == {"4-A", "4-B", "5-A"}
    # 21 child properties under roots 1, 15, 19, 30, 36 plus 43 single-property loans
    assert int((props["block_role"] == "property").sum()) == 64
    assert int((props["block_role"] == "rollup").sum()) == 5
    assert int((props["block_role"] == "note_block").sum()) == 3
    root1 = loans[loans["loan_id"] == "1"].iloc[0]
    assert root1["layout"] == "parent_children"
    assert root1["n_properties"] == 3
    assert root1["fin_source"] == "rollup"
    assert root1["fin_noi"] == 3990480.75          # the roll-up block, not a sum over children
    assert root1["val_securitization"] == 186800000.0


# ---- 2. GSMS 2017-GS6, 2018 (agent 0001056404): replicated layout
def test_gs6_parse():
    res = _parse("0001056404-18-000188")
    assert (res.n_assets_seen, len(res.properties)) == (73, 73)
    a = _asset(res, "1")
    assert (a["reportPeriodEndActualBalanceAmount"], a["loanStructureCode"]) == (95500000.0, "A1")
    p = _prop(res, "1")
    assert p["propertyName"] == "1999 Avenue of the Stars"
    assert p["mostRecentNetOperatingIncomeAmount"] == 24948139.32
    assert p["valuationSecuritizationAmount"] == 860000000.0
    a = _asset(res, "4-034")
    assert a["reportPeriodEndActualBalanceAmount"] == 72167759.68
    assert a["maturityDate"] == dt.date(2026, 9, 4)
    assert _prop(res, "4-034")["propertyName"] == "Progressive Metal"


def test_gs6_structure_counts_replicated_balance_once():
    _res, loans, props = _resolve("0001056404-18-000188", 1704459)
    root4 = loans[loans["root"] == 4]
    assert len(root4) == 1
    r = root4.iloc[0]
    assert r["layout"] == "replicated"
    assert r["reportPeriodEndActualBalanceAmount"] == 72167759.68
    assert r["n_properties"] == 39
    assert not r["flag_replicated_inconsistent"]
    # the loan's balance counted once, not 39 times
    assert loans["reportPeriodEndActualBalanceAmount"].sum() < 1.5e9


# ---- 3. CGCMT 2016-P6, January 2017 (agent 0000950131): nested property blocks, notes without parents
def test_p6_parse():
    res = _parse("0000950131-17-000002")
    assert (res.n_assets_seen, len(res.properties)) == (54, 94)
    a = _asset(res, "16")
    assert a["reportPeriodEndActualBalanceAmount"] == 19492637.71
    assert a["n_property_blocks"] == 6
    assert _prop(res, "16", 1)["propertyName"] == "Walgreens Decatur"
    a = _asset(res, "07A2")
    assert (a["reportPeriodEndActualBalanceAmount"], a["reportPeriodInterestRatePercentage"]) == (35000000.0, 0.03668)


def test_p6_structure():
    _res, loans, _props = _resolve("0000950131-17-000002", 1690255)
    r = loans[loans["loan_id"] == "16"].iloc[0]
    assert r["layout"] == "nested"
    assert r["n_properties"] == 6
    assert r["val_securitization"] == pytest.approx(
        6050000 + 4475000 + 5650000 + 4300000 + 4650000 + 5100000)
    n = loans[loans["loan_id"] == "7-A2"].iloc[0]
    assert n["layout"] == "notes"
    assert n["prop_name"] == "2 Columbus Drive a.k.a 2 Exchange Place"


# ---- 4. UBS 2018-C13, 2018 (agent 0001539497): asset number and type swapped by the filer
def test_c13_swapped_numbers():
    res = _parse("0001539497-18-001471")
    assert (res.n_assets_seen, len(res.properties)) == (72, 72)
    assert res.assets[0]["assetNumber"] == "Prospectus Loan ID"  # parsed layer stays faithful
    _res, loans, _props = _resolve("0001539497-18-001471", 1749360)
    assert loans["flag_swapped_asset_number"].all()
    r = loans[loans["loan_id"] == "1"].iloc[0]
    assert r["reportPeriodEndActualBalanceAmount"] == 48000000.0
    assert r["prop_name"] == "1670 Broadway"
    assert r["fin_noi"] == 11894938.05


# ---- 5. JPMCC 2017 trust, 2017 (agent 0001056404): dot-numbered children
def test_jpmcc_dot_children():
    res = _parse("0001056404-17-001723")
    assert (res.n_assets_seen, len(res.properties)) == (61, 61)
    a = _asset(res, "43")
    assert a["paymentStatusLoanCode"] == "A"
    assert a["reportPeriodEndActualBalanceAmount"] == 2786929.64
    _res, loans, props = _resolve("0001056404-17-001723", 1695154)
    assert len(loans) == 43
    r = loans[loans["loan_id"] == "27"].iloc[0]
    assert r["layout"] == "parent_children"
    assert r["n_properties"] == 16
    assert r["fin_noi"] == 683261.0
    assert r["val_securitization"] == 15750000.0
    # occupancy 1.000 is a fraction (fully let), not 1%
    p = props[(props["root"] == 27) & (props["child"] == 4)].iloc[0]
    assert p["occupancy_current"] == 1.0
