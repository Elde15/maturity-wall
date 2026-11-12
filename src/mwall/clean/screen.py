"""Record screening before layout resolution (decision D036).

A filing should list each asset number once. Three departures turn up in the data:

1. Exact copies. Every field of the asset record and of its property blocks repeats an earlier
   record in the same filing (whole filings listed twice). The copies are dropped.
2. A split. The repeated asset number carries the loan's own origination and maturity dates but a
   different balance, as when a modification splits a loan into A and B notes. The largest record
   keeps the number; the others become notes "<n>-S2", "<n>-S3" of the same loan, so the loan's
   history continues and the pool balance still adds up.
3. Foreign records. The repeated number carries origination or maturity dates the loan has never
   had: another deal's records were filed into this trust. The filing is marked corrupt.

Before any of that, filings are reduced to one per reporting period, the period read from the XML
(``reportingPeriodEndDate``) rather than EDGAR's report date: EDGAR's date is mistyped often enough
that two months can share one date, or one month two dates. Where two filings report the same
period month, the later-filed one (an amendment on a tie) wins and the other is recorded as
superseded.

A filing is also marked corrupt after resolution when it holds transient loans (D035). Rows of a
corrupt filing stay in the tables with ``flag_filing_corrupt``; the roll-forward, the 10-D
reconciliation and the panel leave them out.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

A_META = {"trust_cik", "accession", "form", "filing_date", "is_period_winner", "asset_seq", "n_property_blocks",
          "filing_year"}
P_META = {"trust_cik", "accession", "form", "filing_date", "is_period_winner", "asset_seq", "property_seq",
          "filing_year"}


def _row_hash(df: pd.DataFrame, cols: list[str]) -> np.ndarray:
    if not cols or df.empty:
        return np.zeros(len(df), dtype="uint64")
    return pd.util.hash_pandas_object(df[cols].astype(str), index=False).to_numpy()


def screen(a: pd.DataFrame, p: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Return (assets, properties, per-filing counts with a ``corrupt_reason`` where one applies)."""
    a = a.copy()
    p = p.copy()
    a["_an"] = a["assetNumber"].astype("string").str.strip()
    a["_h"] = _row_hash(a, sorted(c for c in a.columns if c not in A_META and not c.startswith("_")))
    if len(p):
        p["_h"] = (_row_hash(p, sorted(c for c in p.columns if c not in P_META)) & np.uint64(0xFFFFFFFF)).astype("int64")
        ph = p.groupby(["accession", "asset_seq"])["_h"].agg(_psum="sum", _pn="size")
        p = p.drop(columns="_h")
        a = a.join(ph, on=["accession", "asset_seq"])
    else:
        a["_psum"], a["_pn"] = 0, 0
    a[["_psum", "_pn"]] = a[["_psum", "_pn"]].fillna(0)

    per = pd.DataFrame(index=pd.Index(sorted(a["accession"].unique()), name="accession"))

    # 1. exact copies (asset fields and property blocks identical)
    exact = a.duplicated(["accession", "_an", "_h", "_psum", "_pn"], keep="first")
    per["n_exact_copies_dropped"] = a.loc[exact, "accession"].value_counts()
    if exact.any() and len(p):
        gone = pd.MultiIndex.from_frame(a.loc[exact, ["accession", "asset_seq"]])
        p = p[~pd.MultiIndex.from_frame(p[["accession", "asset_seq"]]).isin(gone)]
    a = a[~exact]

    # 2 and 3. asset numbers still repeated within a filing
    rep = a.duplicated(["accession", "_an"], keep=False) & a["_an"].notna()
    per["n_split_records"] = 0
    per["n_foreign_repeats"] = 0
    if rep.any():
        once = a[~rep]
        mode = lambda s: s.dropna().astype(str).mode().iloc[0] if s.notna().any() else None  # noqa: E731
        hist = once.groupby("_an").agg(_orig=("originationDate", mode), _mat=("maturityDate", mode))
        r = a[rep].join(hist, on="_an")
        r["_same"] = ((r["originationDate"].astype(str) == r["_orig"]) & (r["maturityDate"].astype(str) == r["_mat"]))
        verdict = r.groupby(["accession", "_an"])["_same"].all()
        split = verdict[verdict].index
        foreign = verdict[~verdict].index
        per["n_foreign_repeats"] = pd.Series(foreign.get_level_values(0)).value_counts()
        if len(split):
            s = r[pd.MultiIndex.from_frame(r[["accession", "_an"]]).isin(split)].copy()
            bal = s["reportPeriodEndActualBalanceAmount"].fillna(s["reportPeriodEndScheduledLoanBalanceAmount"])
            s["_bal"] = pd.to_numeric(bal, errors="coerce").fillna(-1)
            s = s.sort_values(["accession", "_an", "_bal", "asset_seq"], ascending=[True, True, False, True])
            rank = s.groupby(["accession", "_an"]).cumcount()
            moved = rank[rank > 0]
            a.loc[moved.index, "assetNumber"] = s.loc[moved.index, "_an"] + "-S" + (moved + 1).astype(str)
            per["n_split_records"] = pd.Series(s.loc[moved.index, "accession"]).value_counts()

    per = per.fillna(0).astype(int)
    per["corrupt_reason"] = np.where(per["n_foreign_repeats"] > 0, "repeated asset numbers with another loan's dates",
                                     None)
    return a.drop(columns=["_an", "_h", "_psum", "_pn"]), p, per.reset_index()


def one_filing_per_period(a: pd.DataFrame, p: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Keep one filing per XML reporting-period month; return the superseded ones as screening rows."""
    end = pd.to_datetime(a["reportingPeriodEndDate"], errors="coerce")
    acc = pd.DataFrame({"accession": a["accession"], "end": end, "filing_date": pd.to_datetime(a["filing_date"]),
                        "amend": a["form"].astype(str).str.endswith("/A")})
    acc = acc.groupby("accession").agg(end=("end", "max"), filing_date=("filing_date", "max"), amend=("amend", "max"))
    acc["month"] = acc["end"].fillna(acc["filing_date"] - pd.Timedelta(days=15)).dt.to_period("M")
    acc = acc.reset_index().sort_values(["month", "filing_date", "amend", "accession"])
    keep = acc.groupby("month").tail(1)["accession"]
    lost = acc[~acc["accession"].isin(keep)]
    if lost.empty:
        return a, p, pd.DataFrame(columns=["accession"])
    winner = acc.groupby("month").tail(1).set_index("month")["accession"]
    sup = pd.DataFrame({"accession": lost["accession"].to_numpy(),
                        "superseded_by": lost["month"].map(winner).to_numpy(),
                        "corrupt_reason": None})
    return (a[a["accession"].isin(keep)], p[p["accession"].isin(keep)] if len(p) else p, sup)
