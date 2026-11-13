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

import pandas as pd
from lxml import html as LH

from mwall.common import paths

DATE = re.compile(r"^\d{2}/\d{2}/\d{2}$")
MONEY = re.compile(r"^\(?-?[\d,]+\.\d{2}\)?$")
RATE = re.compile(r"^\d+\.\d+%$")
DIST = re.compile(r"(?<!Next )Distribution Date:\s*(\d{2}/\d{2}/\d{2,4})")  # not "Next Distribution Date"
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
    if len(r) < 15 or not re.fullmatch(r"\d+", r[0]):
        return None
    c = list(r)
    paid_through = c.pop() if DATE.match(c[-1]) else None
    if paid_through is None and c[-1] in ("", "N/A"):
        c.pop()
    end_bal, beg_bal = c.pop(), c.pop()
    adj_mat, orig_mat, ard = c.pop(), c.pop(), c.pop()
    adj, sched_prin, sched_int = c.pop(), c.pop(), c.pop()
    rate = c.pop()
    accrual = c.pop()
    if not (MONEY.match(end_bal) and MONEY.match(beg_bal) and DATE.match(adj_mat) and DATE.match(orig_mat)
            and (DATE.match(ard) or ard == "N/A") and MONEY.match(adj) and MONEY.match(sched_prin)
            and MONEY.match(sched_int) and RATE.match(rate)):
        return None
    if len(c) < 5:
        return None
    pros_id, loan_id, group, prop_type = c[0], c[1], c[2], c[3]
    state = c[-1] if re.fullmatch(r"[A-Z]{2}", c[-1]) and len(c) >= 5 else None
    city = " ".join(c[4:-1]) if state else " ".join(c[4:])
    return {
        "pros_id": pros_id, "loan_id": loan_id, "loan_group": group, "prop_type": prop_type,
        "city": city or None, "state": state, "accrual_type": accrual,
        "gross_rate": float(rate.rstrip("%")) / 100, "sched_interest": _money(sched_int),
        "sched_principal": _money(sched_prin), "principal_adjustments": _money(adj),
        "anticipated_repay_date": _date(ard), "original_maturity_date": _date(orig_mat),
        "adjusted_maturity_date": _date(adj_mat), "beginning_balance": _money(beg_bal),
        "ending_balance": _money(end_bal), "paid_through_date": _date(paid_through),
    }


def parse_prepayment_row(r: list[str]) -> dict | None:
    if len(r) < 3 or not re.fullmatch(r"\d+", r[0]):
        return None
    money = [x for x in r[2:] if MONEY.match(x)]
    if not money:
        return None
    code = next((x for x in r[3:] if re.fullmatch(r"\d{1,2}", x)), None)
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
           "has_part1": False}
    if m:
        d = m.group(1)
        out["distribution_date"] = dt.datetime.strptime(d, "%m/%d/%y" if len(d) == 8 else "%m/%d/%Y").date()
    for t in doc.xpath("//table"):
        rows = _rows(t)
        title = _title(rows)
        if title.startswith("Mortgage Loan Detail (Part 1)"):
            out["has_part1"] = True
            for r in rows:
                if r and re.fullmatch(r"\d+", r[0]):
                    rec = parse_part1_row(r)
                    if rec:
                        out["loans"].append(rec)
                    else:
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
        path = paths.RAW_DIR / str(r.trust_cik) / f"{r.tend_accession}.ex991.htm.gz"
        with gzip.open(path, "rb") as fh:
            res = parse_statement(fh.read())
        base = {"trust_cik": int(r.trust_cik), "accession": r.tend_accession, "date_filed": r.date_filed,
                "distribution_date": res["distribution_date"]}
        loans += [{**base, **x} for x in res["loans"]]
        pre += [{**base, **x} for x in res["prepayments"]]
        summary.append({**base, "has_part1": res["has_part1"], "n_loans": len(res["loans"]),
                        "n_rejected": res["rejected_rows"], "n_prepayments": len(res["prepayments"]),
                        "ending_balance_sum": sum(x["ending_balance"] for x in res["loans"]),
                        "statement_balance": r.tend_sched_balance})
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
