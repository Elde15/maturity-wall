"""Mortgage Loan Detail tables from 10-D statements (decisions D033, D040).

Pilot format: the Computershare (CTSLink) statement. Its "Mortgage Loan Detail (Part 1)" table has
one row per loan:

    Pros ID | Loan ID | Group | Prop Type | City | State | Accrual Type | Gross Rate | Scheduled
    Interest | Scheduled Principal | Principal Adjustments | Anticipated Repay Date | Original
    Maturity Date | Adjusted Maturity Date | Beginning Scheduled Balance | Ending Scheduled Balance
    | Paid Through Date

Spacer cells and blank cities make column positions unreliable, so a row is read from its right
end, where every field has a fixed shape (dates, money, a rate ending in %), and each field is
validated. A row that fails validation is counted, not guessed. "Principal Prepayment Detail" lists
the loans that paid principal early or off in the period, with the prepayment or liquidation code.

Writes parsed/loan_detail/loans.parquet, parsed/loan_detail/prepayments.parquet and
docs/qa/loan_detail_pilot.md.
"""
from __future__ import annotations

import datetime as dt
import gzip
import html
import re

import numpy as np
import pandas as pd
from lxml import html as LH

from mwall.common import paths

DATE = re.compile(r"^\d{2}/\d{2}/\d{2}$")
MONEY = re.compile(r"^\(?-?[\d,]+\.\d{2}\)?$")
RATE = re.compile(r"^\d+\.\d+%$")
PROS = re.compile(r"^\d+[A-Za-z0-9-]*$")  # prospectus ID: 12, 3A, 3-B
DIST = re.compile(r"(?<!Next )Distribution Date:\s*(\d{1,2}/\d{1,2}/\d{2,4})")  # not "Next Distribution Date"
DATE4 = re.compile(r"^\d{2}/\d{2}/\d{4}$")
CTS_AGENTS = ("0001888524", "0001056404")   # Computershare, and Wells Fargo's CTSLink before 2021
CITI_AGENT = "0001628297"                   # Citibank, certificate administrator of the Citigroup 2016 deals
OUT = paths.PARSED_DIR / "loan_detail"


def _date(s: str | None):
    if not s or not DATE.match(s):
        return None
    return dt.datetime.strptime(s, "%m/%d/%y").date()


def _money(s: str) -> float:
    neg = s.startswith("(") or s.startswith("-")
    v = float(s.strip("()-").replace(",", ""))
    return -v if neg else v


def _rows(table) -> list[list[str]]:
    out = []
    for tr in table.xpath(".//tr"):
        cells = [re.sub(r"\s+", " ", c.text_content()).strip() for c in tr.xpath("./td|./th")]
        out.append([c for c in cells if c])
    return out


def _title(rows: list[list[str]]) -> str:
    for r in rows[:4]:
        if r:
            return r[0]
    return ""


def parse_part1_row(r: list[str]) -> dict | None:
    """One Part 1 data row, read from the right; None when the shape does not fit."""
    # a cell can hold two values ("0.00 02/06/26") when the statement merged columns
    c = []
    for x in r:
        parts = x.split(" ")
        if len(parts) > 1 and all(MONEY.match(t) or DATE.match(t) or t in ("N/A", "--") for t in parts):
            c.extend(parts)
        else:
            c.append(x)
    if len(c) < 12 or not PROS.match(c[0]):
        return None
    paid_through = c.pop() if DATE.match(c[-1]) else None
    if paid_through is None and c[-1] in ("", "N/A"):
        c.pop()
    end_bal, beg_bal = c.pop(), c.pop()
    adj_mat, orig_mat, ard = c.pop(), c.pop(), c.pop()
    adj, sched_prin, sched_int = c.pop(), c.pop(), c.pop()
    rate = c.pop()
    accrual = c.pop()
    blank = ("N/A", "--", "")
    if not (MONEY.match(end_bal) and MONEY.match(beg_bal) and (DATE.match(adj_mat) or adj_mat in blank)
            and DATE.match(orig_mat) and (DATE.match(ard) or ard in blank) and MONEY.match(adj)
            and MONEY.match(sched_prin) and MONEY.match(sched_int) and RATE.match(rate)):
        return None
    if not c:
        return None
    if len(c) == 1:
        # one identifier left: a long number is the loan ID with the prospectus ID cell left blank
        pros_id, loan_id = (None, c[0]) if len(c[0]) >= 6 else (c[0], None)
        group, prop_type, rest = None, None, []
    elif len(c) == 2:
        # a note row ("2B"): the property sits on the lead note's row
        pros_id, loan_id, group, prop_type, rest = c[0], c[1], None, None, []
    # the Loan Group column is present in some statements and not others; a group is a number where the
    # property type would be two letters
    elif re.fullmatch(r"\d+", c[2]) and len(c) >= 5:
        pros_id, loan_id, group, prop_type, rest = c[0], c[1], c[2], c[3], c[4:]
    else:
        pros_id, loan_id, group, prop_type, rest = c[0], c[1], None, c[2], c[3:]
    # a property type is a two-character code (OF, RT, 98); anything else means the cell was blank
    if prop_type is not None and not re.fullmatch(r"[A-Z]{2}|\d{2}", prop_type):
        rest, prop_type = [prop_type] + rest, None
    state = rest[-1] if rest and re.fullmatch(r"[A-Z]{2}", rest[-1]) else None
    city = " ".join(rest[:-1]) if state else " ".join(rest)
    return {
        "pros_id": pros_id, "loan_id": loan_id, "loan_group": group, "prop_type": prop_type,
        "city": city or None, "state": state, "accrual_type": accrual,
        "gross_rate": float(rate.rstrip("%")) / 100, "sched_interest": _money(sched_int),
        "sched_principal": _money(sched_prin), "principal_adjustments": _money(adj),
        "anticipated_repay_date": _date(ard), "original_maturity_date": _date(orig_mat),
        "adjusted_maturity_date": _date(adj_mat), "beginning_balance": _money(beg_bal),
        "ending_balance": _money(end_bal), "paid_through_date": _date(paid_through),
    }


def _date4(s: str | None):
    return dt.datetime.strptime(s, "%m/%d/%Y").date() if s and DATE4.match(s) else None


def _money_dash(s: str) -> float | None:
    """Citibank prints a zero amount as '-'."""
    if s == "-":
        return 0.0
    return _money(s) if MONEY.match(s) else None


OMCR = re.compile(r"^([A-Za-z0-9-]+|N/A)$")   # can start with a letter (A62); one loan prints N/A
VALUE = re.compile(r"^(\(?-?[\d,]+\.\d{2}\)?|\d{1,2}/\d{1,2}/\d{2,4}|N/A|-)$")


def citi_cells(r: list[str]) -> list[str]:
    """Re-attach a coupon's split '%', split cells that merged two values ('30,000,000.00 10/11/18') and
    split a prospectus ID fused with the property type ('08A RT')."""
    c: list[str] = []
    for i, x in enumerate(r):
        if x == "%" and c:
            c[-1] += "%"
            continue
        parts = x.split(" ")
        if len(parts) > 1 and all(VALUE.match(p) for p in parts):
            c.extend(parts)
        elif i == 1 and re.fullmatch(r"\S+ [A-Z]{2}", x):
            c.extend(x.split(" "))
        else:
            c.append(x)
    return c


def _citi_left(mid: list[str]) -> tuple:
    """Property type, city and state from the cells between the IDs and the first amount. A one- or
    two-character note letter can precede the type ('B', 'A1')."""
    is_type = lambda x: bool(re.fullmatch(r"[A-Z]{2}|\d{2}", x))  # noqa: E731
    if len(mid) >= 2 and not is_type(mid[0]) and is_type(mid[1]) and len(mid[0]) <= 2:
        mid = mid[1:]
    prop_type = mid[0] if mid and is_type(mid[0]) else None
    rest = mid[1:] if prop_type else mid
    state = rest[-1] if rest and re.fullmatch(r"[A-Z]{2}", rest[-1]) else None
    city = " ".join(rest[:-1]) if state else " ".join(rest)
    return prop_type, city or None, None if state == "XX" else state


def parse_citi_row(r: list[str]) -> dict | None:
    """One row of Citibank's Mortgage Loan Detail:

        Loan ID | OMCR | Prop Type | City | State | Paid Through Date | Gross Coupon | Interest Payment |
        Principal Payment | Beginning Scheduled Balance | Ending Scheduled Balance | Maturity Date |
        Payment Status | Workout Strategy | Mod Code

    Read from both ends, since a blank city or code shortens the row; every field's shape is checked."""
    r = citi_cells(r)
    if len(r) < 11 or not re.fullmatch(r"\d{5,}", r[0]) or not OMCR.match(r[1]):
        return None
    # right end: maturity date, then up to three short codes
    j = max((i for i, x in enumerate(r) if DATE4.match(x)), default=-1)
    if j < 8:
        return None
    mat, codes = r[j], r[j + 1:]
    end_bal, beg_bal, prin, intr, coupon = r[j - 1], r[j - 2], r[j - 3], r[j - 4], r[j - 5]
    ptd = r[j - 6]
    mid = r[2:j - 6] if (DATE4.match(ptd) or ptd == "-") else r[2:j - 5]
    if ptd != "-" and not DATE4.match(ptd):
        ptd = None
    vals = [_money_dash(x) for x in (end_bal, beg_bal, prin, intr)]
    if any(v is None for v in vals) or not RATE.match(coupon) or len(codes) > 3:
        return None
    end_v, beg_v, prin_v, int_v = vals
    prop_type, city, state = _citi_left(mid)
    return {
        "pros_id": None if r[1] == "N/A" else r[1], "loan_id": r[0], "loan_group": None, "prop_type": prop_type,
        "city": city, "state": state, "accrual_type": None,
        "gross_rate": float(coupon.rstrip("%")) / 100, "sched_interest": int_v, "sched_principal": prin_v,
        "principal_adjustments": 0.0, "anticipated_repay_date": None, "original_maturity_date": _date4(mat),
        # the one maturity column moves when a loan is extended; kept as the adjusted date too
        "adjusted_maturity_date": _date4(mat), "beginning_balance": beg_v, "ending_balance": end_v,
        "paid_through_date": _date4(ptd) if ptd else None, "payment_status": codes[0] if codes else None,
    }


DATE_SHORT = re.compile(r"^\d{1,2}/\d{1,2}/\d{2}$")


def _date_short(s: str | None):
    return dt.datetime.strptime(s, "%m/%d/%y").date() if s and DATE_SHORT.match(s) else None


def parse_citi_old_row(r: list[str]) -> dict | None:
    """Citibank's layout until late 2026:

        Loan Number | OMCR | Prop Type | City | State | Interest Payment | Principal Payment | Gross Coupon |
        Maturity Date | Neg Am Flag | Beginning Scheduled Balance | Ending Scheduled Balance | Paid Through
        Date | Appraisal Reduction Date | Appraisal Reduction Amount | Payment Status | Workout | Mod Type

    The coupon arrives split from its % sign; rows are anchored on the coupon cell."""
    c = citi_cells(r)
    if len(c) < 14 or not re.fullmatch(r"\d{5,}", c[0]) or not OMCR.match(c[1]):
        return None
    k = next((i for i, x in enumerate(c) if RATE.match(x)), None)
    if k is None or k < 4 or len(c) < k + 6:
        return None
    intr, prin = _money_dash(c[k - 2]), _money_dash(c[k - 1])
    mat, beg, end, ptd = c[k + 1], _money_dash(c[k + 3]), _money_dash(c[k + 4]), c[k + 5]
    if None in (intr, prin, beg, end) or not DATE_SHORT.match(mat):
        return None
    codes = c[k + 8:]
    prop_type, city, state = _citi_left(c[2:k - 2])
    return {
        "pros_id": None if c[1] == "N/A" else c[1], "loan_id": c[0], "loan_group": None, "prop_type": prop_type,
        "city": city, "state": state, "accrual_type": None,
        "gross_rate": float(c[k].rstrip("%")) / 100, "sched_interest": intr, "sched_principal": prin,
        "principal_adjustments": 0.0, "anticipated_repay_date": None, "original_maturity_date": _date_short(mat),
        "adjusted_maturity_date": _date_short(mat), "beginning_balance": beg, "ending_balance": end,
        "paid_through_date": _date_short(ptd), "payment_status": codes[0] if codes else None,
    }


CITI_HIST = re.compile(r"Distribution Date Count Balance.{0,400}?(\d{1,2}/\d{1,2}/\d{2,4})")


def citi_layout(r: list[str]) -> str:
    """'old' when the maturity date follows the coupon, 'new' when amounts do (paid-through date first)."""
    c = citi_cells(r)
    k = next((i for i, x in enumerate(c) if RATE.match(x)), None)
    if k is None or k + 1 >= len(c):
        return "unknown"
    return "old" if (DATE_SHORT.match(c[k + 1]) or DATE4.match(c[k + 1])) else "new"


def parse_citi_statement(raw: bytes) -> dict:
    text = raw.decode("utf-8", errors="replace")
    flat = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", text)))
    out = {"distribution_date": None, "loans": [], "prepayments": [], "rejected_rows": 0,
           "has_part1": False, "part1_total": None}
    # some statements print no "Distribution Date:" header; their delinquency history table then starts with
    # the current distribution date (checked against the statement file name's year and month in all 276)
    if m := DIST.search(flat) or CITI_HIST.search(flat):
        d = m.group(1)
        out["distribution_date"] = dt.datetime.strptime(d, "%m/%d/%Y" if len(d.split("/")[2]) == 4 else "%m/%d/%y").date()
    total = 0.0
    for t in LH.fromstring(raw).xpath("//table"):
        rows = _rows(t)
        head = " ".join(" ".join(x) for x in rows[:5])
        if not ("OMCR" in head and "Coupon" in head and "Maturity" in head):
            continue
        out["has_part1"] = True
        for r in rows:
            if r and r[0] == "Total":
                money = [x for x in r if MONEY.match(x)]
                if money:
                    total += _money(money[-1])
                    out["part1_total"] = total
            elif r and re.fullmatch(r"\d{5,}", r[0]):
                rec = parse_citi_old_row(r) if citi_layout(r) == "old" else parse_citi_row(r)
                if rec:
                    out["loans"].append(rec)
                else:
                    out["rejected_rows"] += 1
    return out


def parse_prepayment_row(r: list[str]) -> dict | None:
    if len(r) < 3 or not PROS.match(r[0]):
        return None
    money = [x for x in r[2:] if MONEY.match(x)]
    if not money:
        return None
    # the code is written out ("Disposition", "Payoff Prior to Maturity"): the first non-numeric cell after the
    # amount; some statements put a Loan Group number between the loan number and the amount
    i = r.index(money[0])
    code = next((x for x in r[i + 1:] if not MONEY.match(x)), None)
    return {"pros_id": r[0], "loan_id": r[1], "unscheduled_principal": _money(money[0]),
            "prepayment_code": code,
            "prepayment_premium": _money(money[1]) if len(money) > 1 else None,
            "yield_maintenance": _money(money[2]) if len(money) > 2 else None}


def parse_statement(raw: bytes) -> dict:
    text = raw.decode("utf-8", errors="replace")
    # entities such as &nbsp; sit between the label and the date; \s matches the unescaped space
    flat = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", text)))
    m = DIST.search(flat)
    doc = LH.fromstring(raw)
    out = {"distribution_date": None, "loans": [], "prepayments": [], "rejected_rows": 0,
           "has_part1": False, "part1_total": None}
    if m:
        d = m.group(1)
        out["distribution_date"] = dt.datetime.strptime(d, "%m/%d/%y" if len(d) == 8 else "%m/%d/%Y").date()
    for t in doc.xpath("//table"):
        rows = _rows(t)
        title = _title(rows)
        if title.startswith("Mortgage Loan Detail (Part 1)"):
            out["has_part1"] = True
            for r in rows:
                if r and r[0] == "Totals":
                    money = [x for x in r if MONEY.match(x)]
                    if money:
                        out["part1_total"] = _money(money[-1])
                if r and PROS.match(r[0]):
                    rec = parse_part1_row(r)
                    if rec:
                        out["loans"].append(rec)
                    elif len(r) >= 6:  # shorter fragments are layout debris, not loan rows
                        out["rejected_rows"] += 1
        elif title.startswith("Principal Prepayment Detail"):
            for r in rows:
                rec = parse_prepayment_row(r)
                if rec:
                    out["prepayments"].append(rec)
    return out


def run(log=print) -> tuple[pd.DataFrame, pd.DataFrame]:
    from mwall.ingest.loan_detail import LOG

    st = pd.read_parquet(LOG)
    st = st[st["status"] == "ok"]
    loans, pre, summary = [], [], []
    for r in st.itertuples():
        path = paths.RAW_DIR / str(int(r.trust_cik)) / f"{r.tend_accession}.ex991.htm.gz"
        agent = r.tend_accession[:10]
        if agent in CTS_AGENTS:
            fmt, parser = "cts", parse_statement
        elif agent == CITI_AGENT:
            fmt, parser = "citi", parse_citi_statement
        else:
            continue  # formats without a parser yet (D049)
        with gzip.open(path, "rb") as fh:
            res = parser(fh.read())
        base = {"trust_cik": int(r.trust_cik), "accession": r.tend_accession, "date_filed": r.date_filed,
                "distribution_date": res["distribution_date"], "format": fmt}
        loans += [{**base, **x} for x in res["loans"]]
        pre += [{**base, **x} for x in res["prepayments"]]
        summary.append({**base, "has_part1": res["has_part1"], "n_loans": len(res["loans"]),
                        "n_rejected": res["rejected_rows"], "n_prepayments": len(res["prepayments"]),
                        "ending_balance_sum": sum(x["ending_balance"] for x in res["loans"]),
                        "statement_balance": r.tend_sched_balance, "part1_total": res["part1_total"]})
    OUT.mkdir(parents=True, exist_ok=True)
    L, P, S = pd.DataFrame(loans), pd.DataFrame(pre), pd.DataFrame(summary)
    # one statement per trust and distribution date: the latest filed wins (an amendment over its original)
    S = S.sort_values(["trust_cik", "distribution_date", "date_filed", "accession"])
    S["is_period_winner"] = ~S.duplicated(["trust_cik", "distribution_date"], keep="last")
    keep = set(S.loc[S["is_period_winner"], "accession"])
    L = L[L["accession"].isin(keep)]
    P = P[P["accession"].isin(keep)] if len(P) else P
    L.to_parquet(OUT / "loans.parquet", index=False)
    P.to_parquet(OUT / "prepayments.parquet", index=False)
    S.to_parquet(OUT / "statements.parquet", index=False)
    log(f"statements {len(S):,} (winners {int(S['is_period_winner'].sum()):,}); loan rows {len(L):,}; "
        f"prepayment rows {len(P):,}; rejected rows {int(S['n_rejected'].sum()):,}; "
        f"statements without Part 1 {int((~S['has_part1']).sum()):,}")
    return L, P


PAYOFF_TEXT = ("payoff prior to maturity", "full payoff at maturity", "payoff w/ yield maintenance", "payoff w/ penalty")
LIQ_TEXT = ("disposition", "dpo", "liquidation")
GRACE_DAYS, EARLY_DAYS = 90, 365  # same rules as the XML tier 1 (docs/labels.md)


def maturity_outcomes(log=print) -> pd.DataFrame:
    """Tier 1 outcomes from the loan detail tables, with the XML gold set's evidence rules."""
    L = pd.read_parquet(OUT / "loans.parquet")
    P = pd.read_parquet(OUT / "prepayments.parquet")
    for c in ["distribution_date", "original_maturity_date", "adjusted_maturity_date"]:
        L[c] = pd.to_datetime(L[c])
    # Citibank's older layout prints loan numbers with a leading zero (030311655), the newer one without
    L["key"] = L["trust_cik"].astype(str) + ":" + L["loan_id"].fillna(L["pros_id"]).astype(str).str.lstrip("0")
    P["key"] = P["trust_cik"].astype(str) + ":" + P["loan_id"].fillna(P["pros_id"]).astype(str).str.lstrip("0")
    P["distribution_date"] = pd.to_datetime(P["distribution_date"])
    code = P["prepayment_code"].fillna("").str.lower()
    pay = P[code.str.startswith(PAYOFF_TEXT)].groupby("key")["distribution_date"].min()
    # A balloon paid on schedule never shows in Prepayment Detail (it is scheduled principal): the loan's
    # row pays its whole beginning balance and ends at zero.
    balloon = L[(L["ending_balance"] <= 1) & (L["beginning_balance"] > 1)
                & (L["sched_principal"] + L["principal_adjustments"] >= L["beginning_balance"] - 1)]
    balloon = balloon.groupby("key")["distribution_date"].min()
    pay = pd.concat([pay, balloon]).groupby(level=0).min()
    # "Partial Liquidation (Curtailment)" is a partial prepayment, not a liquidation (D050)
    liq = P[code.map(lambda c: any(t in c for t in LIQ_TEXT) and not c.startswith("partial"))].groupby(
        "key")["distribution_date"].min()
    # Citibank's statements carry no prepayment codes: a balance that ends at zero with less principal paid
    # than was owed left the trust through a liquidation or a discounted payoff
    if "format" in L:
        short = L[L["format"].eq("citi") & (L["ending_balance"] <= 1) & (L["beginning_balance"] > 1)
                  & (L["sched_principal"] + L["principal_adjustments"] < L["beginning_balance"] - 1)]
        liq = pd.concat([liq, short.groupby("key")["distribution_date"].min()]).groupby(level=0).min()
    last_stmt = L.groupby("trust_cik")["distribution_date"].max()
    g = L.sort_values("distribution_date").groupby("key")
    # as in the XML tier 1: a loan with an anticipated repayment date is judged at that date (D046)
    ard = pd.to_datetime(g["anticipated_repay_date"].first())
    orig = pd.to_datetime(g["original_maturity_date"].first())
    d = pd.DataFrame({"trust_cik": g["trust_cik"].first(), "maturity": ard.fillna(orig),
                      "maturity_is_ard": ard.notna(), "original_maturity": orig,
                      "first_seen": g["distribution_date"].min(), "last_seen": g["distribution_date"].max(),
                      "max_adjusted_maturity": g["adjusted_maturity_date"].max(), "prop_type": g["prop_type"].first(),
                      "state": g["state"].first(), "city": g["city"].first(), "gross_rate": g["gross_rate"].first(),
                      "balance_first": g["ending_balance"].first(),
                      "format": g["format"].first() if "format" in L else "cts"})
    d = d[(d["maturity"] >= d["first_seen"])
          & (d["maturity"] <= d["trust_cik"].map(last_stmt) - pd.Timedelta(days=GRACE_DAYS))].copy()
    d["payoff_date"], d["liquidation_date"] = d.index.map(pay), d.index.map(liq)
    grace = d["maturity"] + pd.Timedelta(days=GRACE_DAYS)
    late = L.merge(d[["maturity"]], left_on="key", right_index=True)
    late = set(late.loc[(late["distribution_date"] > late["maturity"] + pd.Timedelta(days=GRACE_DAYS))
                        & (late["ending_balance"] > 0), "key"])
    start = d["maturity"] - pd.Timedelta(days=EARLY_DAYS)
    d["outcome"] = np.select(
        [d["payoff_date"].notna() & (d["payoff_date"] < start),
         d["liquidation_date"].notna() & (d["liquidation_date"] < start),
         d["payoff_date"].notna() & (d["payoff_date"] <= grace)
         & (d["liquidation_date"].isna() | (d["liquidation_date"] > d["payoff_date"])),
         d.index.isin(late) | d["liquidation_date"].notna() | (d["max_adjusted_maturity"] > d["maturity"])
         | (d["payoff_date"] > grace)],  # paid, but after the grace window (D050)
        ["excluded_early_payoff", "excluded_early_liquidation", "paid", "failed"], "unknown")
    d["y_fail"] = d["outcome"].map({"paid": 0.0, "failed": 1.0})
    d["source"] = d["format"].map({"cts": "10-D loan detail (Computershare)", "citi": "10-D loan detail (Citibank)"})
    d.reset_index().to_parquet(OUT / "tier1.parquet", index=False)
    lab = d[d["y_fail"].notna()]
    by_year = lab.groupby(lab["maturity"].dt.year)["y_fail"].agg(loans="size", failed="sum")
    by_type = lab.groupby("prop_type")["y_fail"].agg(loans="size", failed="sum", rate="mean").sort_values(
        "loans", ascending=False)
    S = pd.read_parquet(OUT / "statements.parquet")
    S = S[S["is_period_winner"]]
    # check against the table's own Totals row where it prints one, else the statement's pool balance
    S["check_total"] = S["part1_total"].fillna(S["statement_balance"])
    S["exact"] = (S["ending_balance_sum"] - S["check_total"]).abs() <= 1
    by_fmt = S.groupby("format").agg(trusts=("trust_cik", "nunique"), statements=("accession", "size"),
                                     with_check=("check_total", "count"), exact=("exact", "sum"),
                                     rejected_rows=("n_rejected", "sum"))
    exact = int(S["exact"].sum())
    from mwall.clean.qa_report import md_table
    lines = [
        "# 10-D loan detail (D033, D040, D049)",
        "",
        "Vintage-2016 trusts with no EX-102 still file a monthly 10-D whose statement carries a loan-level table. "
        "Two formats are read (`src/mwall/parse/loan_detail.py`): Computershare's Mortgage Loan Detail (40 trusts) "
        "and Citibank's (7 Citigroup trusts, two layouts).",
        "",
        f"- Statements: {len(S):,} from {S['trust_cik'].nunique()} trusts, "
        f"{S['distribution_date'].min()} to {S['distribution_date'].max()}. Loan rows: {len(L):,}; rows that "
        f"failed validation: {int(S['n_rejected'].sum()):,}.",
        f"- Parsed loan balances equal the table's own Totals row (or, where none is printed, the statement's pool "
        f"balance) to the dollar in {exact:,} of {int(S['check_total'].notna().sum()):,} statements.",
        "",
        md_table(by_fmt.reset_index()),
        "",
        f"- Prepayment rows with a written code: {int(P['prepayment_code'].notna().sum()):,} "
        f"({P['prepayment_code'].value_counts().to_dict()}).",
        "",
        "## Maturity outcomes",
        "",
        f"Loans whose original maturity plus {GRACE_DAYS} days falls inside the statement window: {len(d):,}. "
        f"Outcomes: {d['outcome'].value_counts().to_dict()}. Same rules as the XML gold set: paid needs a payoff "
        "code, or a row that pays the whole balance as scheduled principal (a balloon paid on time never appears "
        "in Prepayment Detail), no more than 12 months before maturity and no later than 90 days after it; "
        "failed means a balance "
        "still outstanding after the grace window, an adjusted maturity date later than the original, or a "
        "disposition or discounted payoff.",
        "",
        md_table(by_year.reset_index().rename(columns={"maturity": "maturity_year"})),
        "",
        md_table(by_type.reset_index(), floatfmt=".2f"),
        "",
        "Not yet read: COMM 2016-DC2 and CFCRE 2016-C4, whose statements are page images converted to positioned "
        "text (D049). Pari passu matching to the XML loans is in docs/qa/gate2_gold_set.md.",
        "",
    ]
    (paths.DOCS_DIR / "qa" / "loan_detail_pilot.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    log(f"pilot tier 1: {len(d):,} loans; {d['outcome'].value_counts().to_dict()}")
    return d
