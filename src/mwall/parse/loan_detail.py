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
        with gzip.open(path, "rb") as fh:
            res = parse_statement(fh.read())
        base = {"trust_cik": int(r.trust_cik), "accession": r.tend_accession, "date_filed": r.date_filed,
                "distribution_date": res["distribution_date"]}
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
    L["key"] = L["trust_cik"].astype(str) + ":" + L["loan_id"].fillna(L["pros_id"]).astype(str)
    P["key"] = P["trust_cik"].astype(str) + ":" + P["loan_id"].fillna(P["pros_id"]).astype(str)
    P["distribution_date"] = pd.to_datetime(P["distribution_date"])
    code = P["prepayment_code"].fillna("").str.lower()
    pay = P[code.str.startswith(PAYOFF_TEXT)].groupby("key")["distribution_date"].min()
    # A balloon paid on schedule never shows in Prepayment Detail (it is scheduled principal): the loan's
    # row pays its whole beginning balance and ends at zero.
    balloon = L[(L["ending_balance"] <= 1) & (L["beginning_balance"] > 1)
                & (L["sched_principal"] + L["principal_adjustments"] >= L["beginning_balance"] - 1)]
    balloon = balloon.groupby("key")["distribution_date"].min()
    pay = pd.concat([pay, balloon]).groupby(level=0).min()
    liq = P[code.map(lambda c: any(t in c for t in LIQ_TEXT))].groupby("key")["distribution_date"].min()
    last_stmt = L.groupby("trust_cik")["distribution_date"].max()
    g = L.sort_values("distribution_date").groupby("key")
    d = pd.DataFrame({"trust_cik": g["trust_cik"].first(), "maturity": g["original_maturity_date"].first(),
                      "first_seen": g["distribution_date"].min(), "last_seen": g["distribution_date"].max(),
                      "max_adjusted_maturity": g["adjusted_maturity_date"].max(), "prop_type": g["prop_type"].first(),
                      "state": g["state"].first(), "city": g["city"].first(), "gross_rate": g["gross_rate"].first(),
                      "balance_first": g["ending_balance"].first()})
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
         d.index.isin(late) | d["liquidation_date"].notna() | (d["max_adjusted_maturity"] > d["maturity"])],
        ["excluded_early_payoff", "excluded_early_liquidation", "paid", "failed"], "unknown")
    d["y_fail"] = d["outcome"].map({"paid": 0.0, "failed": 1.0})
    d["source"] = "10-D loan detail (Computershare)"
    d.reset_index().to_parquet(OUT / "tier1.parquet", index=False)
    lab = d[d["y_fail"].notna()]
    by_year = lab.groupby(lab["maturity"].dt.year)["y_fail"].agg(loans="size", failed="sum")
    by_type = lab.groupby("prop_type")["y_fail"].agg(loans="size", failed="sum", rate="mean").sort_values(
        "loans", ascending=False)
    S = pd.read_parquet(OUT / "statements.parquet")
    S = S[S["is_period_winner"]]
    exact = int(((S["ending_balance_sum"] - S["part1_total"]).abs() <= 1).sum())
    from mwall.clean.qa_report import md_table
    lines = [
        "# 10-D loan detail pilot (D033, D040)",
        "",
        "Vintage-2016 trusts with no EX-102 still file a monthly 10-D whose statement carries a Mortgage Loan "
        "Detail table. The pilot reads the Computershare format (`src/mwall/parse/loan_detail.py`).",
        "",
        f"- Statements: {len(S):,} from {S['trust_cik'].nunique()} trusts, "
        f"{S['distribution_date'].min()} to {S['distribution_date'].max()}. Loan rows: {len(L):,}; rows that "
        f"failed validation: {int(S['n_rejected'].sum()):,}.",
        f"- Parsed loan balances equal the table's own Totals row to the dollar in {exact:,} of "
        f"{int(S['part1_total'].notna().sum()):,} statements.",
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
        "Not yet done: the 9 trusts filed through other administrators, matching these loans to pari passu pieces "
        "in the XML trusts, and features from these tables for the maturity-window model.",
        "",
    ]
    (paths.DOCS_DIR / "qa" / "loan_detail_pilot.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    log(f"pilot tier 1: {len(d):,} loans; {d['outcome'].value_counts().to_dict()}")
    return d
