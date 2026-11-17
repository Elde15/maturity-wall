"""Gate 4 hand check (SOP 12): three loans rebuilt in a spreadsheet, every step an Excel formula.

The workbook is laid out from the written method (docs/underwriting.md), not from the engine's code: inputs are
typed values, and every calculation, from the cap rate to the return bid and the IRRs, is a formula that Excel
evaluates. Excel recalculates the file (``recalc``), which stores the computed values in it. The test suite reads
those stored values and requires the engine to match them to the cent (tests/test_underwrite.py), so the check runs
on a fresh clone without Excel.

    python -m mwall underwrite --handcheck

Loans are chosen by a fixed rule, the largest known whole-loan balance meeting each case's conditions:
  1. office in the City of Los Angeles with listed tenants rolling in the hold (base scenario): rollover,
     Proposition 13, Measure ULA;
  2. multifamily outside California with a metro rent index (value-add scenario): renovation program;
  3. retail outside California with listed tenants rolling in the hold (downside scenario): haircut, stress
     lender set, rate and cap-rate shifts.
"""
from __future__ import annotations

import math
import subprocess
from datetime import date

import pandas as pd
from openpyxl import Workbook, load_workbook
from openpyxl.styles import Font

from mwall.common import paths
from mwall.underwrite import engine

BOOK = paths.REPO_ROOT / "docs" / "qa" / "handcheck" / "underwriting_handcheck.xlsx"
CASES = [("office_la", "base"), ("multifamily", "value_add"), ("retail", "downside")]
YEARS = "CDEFG"            # hold years 1 to 5; column H is year 6, column B year 0


def _rolls(L: dict) -> bool:
    for i in (1, 2, 3):
        exp = engine._date(L.get(f"tenant{i}_lease_exp"))
        if engine._num(L.get(f"tenant{i}_sqft")) > 0 and engine.rollover_year(exp, L["valuation"]):
            return True
    return False


def select(rows: list[dict], P: dict, M: dict) -> list[dict]:
    def ok(L, S):
        r = engine.underwrite(L, P["scenarios"][S], P, M)
        return (L["tier"] in ("A", "B") and engine._num(L.get("wl_balance_est")) > 0
                and not math.isnan(r.get("return_bid", float("nan"))) and r["kink"] > 0)

    rules = {
        "office_la": lambda L: L["group"] == "office" and L["jurisdiction"] == "la_city" and _rolls(L)
        and engine._num(L.get("revenue")) > 0 and not math.isnan(engine._num(L["tax_current"])),
        "multifamily": lambda L: L["group"] == "multifamily" and L.get("prop_state") != "CA"
        and L["jurisdiction"] != "multi_property" and not math.isnan(engine._num(L.get("mf_rent_growth_metro")))
        and engine._num(L.get("units")) > 0,
        "retail": lambda L: L["group"] == "retail" and L.get("prop_state") != "CA"
        and L["jurisdiction"] != "multi_property" and _rolls(L) and engine._num(L.get("revenue")) > 0,
    }
    chosen = []
    for case, scen in CASES:
        c = [L for L in rows if rules[case](L) and ok(L, scen)]
        chosen.append(max(c, key=lambda L: engine._num(L["wl_balance_est"])))  # largest known balance
    return chosen


class Sheet:
    """Rows of (label, value or formula, note) in columns A to C; ``{label}`` in a formula is that row's cell."""

    def __init__(self, ws):
        self.ws, self.row, self.at = ws, 1, {}

    def head(self, text: str):
        self.row += 1
        self.ws.cell(self.row, 1, text).font = Font(bold=True)
        self.row += 1

    def put(self, label: str, value, note: str = ""):
        if isinstance(value, str) and value.startswith("="):
            value = self.f(value)
        self.ws.cell(self.row, 1, label)
        c = self.ws.cell(self.row, 2, value)
        if isinstance(value, date):
            c.number_format = "yyyy-mm-dd"
        self.ws.cell(self.row, 3, note)
        self.at[label] = f"$B${self.row}"
        self.row += 1

    def f(self, formula: str) -> str:
        out = formula
        for k in sorted(self.at, key=len, reverse=True):
            out = out.replace("{" + k + "}", self.at[k])
        assert "{" not in out, out
        return out


def _v(x):
    if x is None:
        return None
    if isinstance(x, float) and math.isnan(x):
        return None
    if isinstance(x, pd.Timestamp):
        return x.date()
    return x


def build_case(ws, L: dict, scen: str, P: dict, M: dict) -> None:
    S = P["scenarios"][scen]
    g = L["group"]
    lp = P["lender"].get((S["refi_lender_set"], g)) or P["lender"][(S["refi_lender_set"], "other")]
    sh = Sheet(ws)
    ws.column_dimensions["A"].width = 34
    for col in "BCDEFGH":
        ws.column_dimensions[col].width = 16
    ws.cell(1, 1, f"Hand check: {L['whole_loan_id']} ({g}, {scen} scenario)").font = Font(bold=True, size=13)
    sh.row = 2
    sh.head("Loan inputs (from the filing; typed values)")
    for k in ("whole_loan_id", "group", "tier", "jurisdiction", "valuation", "wl_balance_est", "noi", "revenue", "occupancy",
              "sqft", "units", "noi_sec", "val_sec", "val_sec_date", "bench_today", "bench_sec", "spread_lo",
              "spread_hi", "mf_rent_growth_metro", "tax_rate", "rent_cap", "high_tax_metro"):
        if k == "valuation":
            sh.put(k, L["valuation"])
        elif k in ("spread_lo", "spread_hi"):
            sh.put(k, L[k])
        elif k == "high_tax_metro":
            sh.put(k, 1 if bool(L.get(k)) else 0)
        elif k == "rent_cap":
            sh.put(k, L[k] if math.isfinite(L[k]) else 1.0, "1.0 means no cap")
        elif k == "tax_rate":
            sh.put(k, _v(L[k]) or 0, "0 means Proposition 13 not modeled")
        else:
            sh.put(k, _v(L.get(k)))
    sh.head("Scenario and market inputs")
    sh.put("scenario", scen)
    sh.put("rate_shift", S["rate_shift_bps"] / 10_000)
    sh.put("cap_shift", S["cap_shift_bps"] / 10_000)
    sh.put("haircut", par_or0(P, S["noi_haircut"], g) / 100)
    sh.put("ust10", M["ust10"])
    sh.put("ust5", M["ust5"])
    sh.put("cbre_spread_bps", M["spread_bps"][lp["spread_series"]], f"CBRE {lp['spread_series']} series")
    sh.put("spread_premium_bps", lp["spread_premium_bps"])
    sh.put("ltv_max", lp["ltv_max"])
    sh.put("dscr_min", lp["dscr_min"])
    sh.put("dy_min", lp["dy_min"])
    sh.put("amort_years", lp["amort_years"])
    sh.head("Parameters (config/underwriting_params.csv, config/la_overrides.csv)")
    roll = 1 if g in engine.ROLLOVER_TYPES else 0
    for name in ("noi_growth", "renewal_prob", "downtime_months", "ti_lc_new_psf", "ti_lc_renewal_psf",
                 "lease_term_years", "reserve", "bridge_spread_bps", "ltc", "ltv_asis"):
        v = engine.par(P, name, g)
        sh.put("param:" + name, v if v is not None else 0)
    for name in ("buyer_closing_pct", "selling_cost_pct", "selling_cost_pct_high_tax", "exit_cap_spread_bps",
                 "cap_rate_floor"):
        sh.put("param:" + name, engine.par(P, name, "all"))
    sh.put("param:hurdle", engine.par(P, S["hurdle_param"], "all"))
    sh.put("param:renovation_cost_per_unit", engine.par(P, "renovation_cost_per_unit", "multifamily"))
    sh.put("param:renovation_roc", engine.par(P, "renovation_roc", "multifamily"))
    la = P["la"]
    sh.put("la:prop13_growth", la[("prop13", "all", "assessed_growth")])
    for p_ in ("threshold_lower", "threshold_upper", "rate_lower", "rate_upper", "threshold_growth"):
        sh.put("la:ula_" + p_, la[("ula", "la_city", p_)])
    sh.put("renovation_on", 1 if S["renovation"] == "on" and g == "multifamily" and L["rent_cap"] > 0.05 else 0)
    sh.put("rollover_type", roll)

    sh.head("Step B: cap rate, stressed NOI, value")
    sh.put("cap_sec", "={noi_sec}/{val_sec}", "NOI at securitization / appraisal")
    sh.put("spread_raw", "={cap_sec}-{bench_sec}")
    sh.put("spread", "=MIN(MAX({spread_raw},{spread_lo}),{spread_hi})", "clipped to the 5th-95th percentile")
    sh.put("cap_rate", "=MAX({bench_today}+{spread}+{cap_shift},{param:cap_rate_floor}/100)")
    sh.put("noi_stressed", "={noi}*(1-{haircut})")
    sh.put("prop13", "=IF({tax_rate}>0,1,0)")
    sh.put("tax_current", "=IF({prop13}=1,{tax_rate}*{val_sec}*(1+{la:prop13_growth}/100)^(({valuation}-{val_sec_date})"
           "/365.25),0)", "seller's tax: appraisal grown 2% a year")
    sh.put("value", "=IF({prop13}=1,({noi_stressed}+{tax_current})/({cap_rate}+{tax_rate}),{noi_stressed}/{cap_rate})")

    sh.head("Step A: refinance test")
    sh.put("refi_rate", "={ust10}+({cbre_spread_bps}+{spread_premium_bps})/10000+{rate_shift}")
    sh.put("loan_constant", "=12*({refi_rate}/12)/(1-(1+{refi_rate}/12)^(-12*{amort_years}))")
    sh.put("p_ltv", "={ltv_max}*{value}")
    sh.put("p_dscr", "={noi_stressed}/({dscr_min}*{loan_constant})")
    sh.put("p_dy", "={noi_stressed}/{dy_min}")
    sh.put("p_max", "=MAX(MIN({p_ltv},{p_dscr},{p_dy}),0)")
    sh.put("refi_gap", "=MAX(0,{wl_balance_est}-{p_max})")

    sh.head("Listed tenants (sqft, lease end, share of area, hold year, share after scaling)")
    first = sh.row
    for i in (1, 2, 3):
        r = sh.row
        ws.cell(r, 1, f"tenant{i}")
        ws.cell(r, 2, _v(engine._num(L.get(f"tenant{i}_sqft"))) or 0)
        exp = engine._date(L.get(f"tenant{i}_lease_exp"))
        c = ws.cell(r, 3, exp)
        c.number_format = "yyyy-mm-dd"
        ws.cell(r, 4, sh.f(f'=IF(AND(B{r}>0,C{r}<>"",{{rollover_type}}=1),B{r}/{{sqft}},0)'))
        yr = "0"
        for t in (5, 4, 3, 2, 1):
            yr = f"IF(C{r}<=EDATE({{valuation}},{12 * t}),{t},{yr})"
        ws.cell(r, 5, sh.f(f"=IF(D{r}=0,0,{yr})"))
        sh.row += 1
    last = sh.row - 1
    sh.put("occ_eff", "=IF({occupancy}>0,{occupancy},1)")
    for r in range(first, last + 1):
        ws.cell(r, 6, sh.f(f"=IF(SUM($D${first}:$D${last})>{{occ_eff}},D{r}*{{occ_eff}}/SUM($D${first}:$D${last}),D{r})"))
    sh.put("listed", f"=SUM(F{first}:F{last})")
    sh.put("unlisted", "=MAX(0,{occ_eff}-{listed})")
    sh.put("income_full", "=IF({revenue}>0,{revenue},{noi})/{occ_eff}")
    sh.put("ti_cost", "={sqft}*({param:renewal_prob}/100*{param:ti_lc_renewal_psf}"
           "+(1-{param:renewal_prob}/100)*{param:ti_lc_new_psf})")
    sh.put("lease_up", f"={{rollover_type}}*SUMIF(E{first}:E{last},1,F{first}:F{last})*({{ti_cost}}"
           "+(1-{param:renewal_prob}/100)*{income_full}*{param:downtime_months}/12)")
    sh.put("reserve", "=IF({group}=\"multifamily\",{param:reserve}*{units},{param:reserve}*{sqft})")
    sh.put("value_bid", "=({value}-{lease_up}-{reserve})/(1+{param:buyer_closing_pct}/100)")

    sh.head("Step D: year table (B = year 0, C to G = hold years 1 to 5, H = year 6)")
    hdr = sh.row
    ws.cell(hdr, 1, "year")
    for j, col in enumerate("BCDEFGH"):
        ws.cell(hdr, j + 2, j)
    sh.row += 1
    rows = {}

    def yrow(name, fn, cols="CDEFGH"):
        r = sh.row
        ws.cell(r, 1, name)
        for col in cols:
            t = "BCDEFGH".index(col)
            ws.cell(r, "BCDEFGH".index(col) + 2, sh.f(fn(col, t, r)))
        rows[name] = r
        sh.row += 1

    grow = "MIN(IF(AND({group}=\"multifamily\",{mf_rent_growth_metro}<>\"\"),{mf_rent_growth_metro},{param:noi_growth}/100),{rent_cap})"
    yrow("growth_into_year", lambda c, t, r: "=0" if t == 1 else
         (f"={grow}" if t == 2 else "=MIN({param:noi_growth}/100,{rent_cap})"))
    yrow("noi_path_S", lambda c, t, r: "={noi_stressed}" if t == 1 else
         f"={'BCDEFGH'[t - 1]}{r}*(1+{c}{rows['growth_into_year']})")
    sh.put("renovation_budget", "={renovation_on}*{param:renovation_cost_per_unit}*{units}")
    sh.put("renovation_premium", "={renovation_budget}*{param:renovation_roc}/100")
    yrow("renovation", lambda c, t, r: "=0" if t == 1 else "={renovation_premium}")
    yrow("rollover_share", lambda c, t, r: f"=IF({{rollover_type}}=1,SUMIF($E${first}:$E${last},{t},$F${first}:$F${last})"
         "+{unlisted}/{param:lease_term_years},0)", cols=YEARS)
    yrow("downtime_loss", lambda c, t, r: f"=(1-{{param:renewal_prob}}/100)*{c}{rows['rollover_share']}*{{income_full}}"
         f"*{{param:downtime_months}}/12*(1+{{param:noi_growth}}/100)^{t - 1}", cols=YEARS)
    yrow("leasing_cost", lambda c, t, r: f"={c}{rows['rollover_share']}*{{ti_cost}}", cols=YEARS)
    yrow("capex", lambda c, t, r: f"={{reserve}}+{c}{rows['leasing_cost']}", cols=YEARS)

    sh.head("Exit and debt")
    sh.put("exit_cap", "={cap_rate}+{param:exit_cap_spread_bps}/10000")
    sh.put("pre_tax_noi_6", f"=H{rows['noi_path_S']}+H{rows['renovation']}"
           "+IF({prop13}=1,{tax_current}*(1+{la:prop13_growth}/100)^5,0)")
    sh.put("exit_price", "={pre_tax_noi_6}/({exit_cap}+IF({prop13}=1,{tax_rate},0))")
    sh.put("exit_date", "=EDATE({valuation},60)")
    sh.put("ula_indexations", "=MAX(0,YEAR({exit_date})-2026-IF({exit_date}<DATE(YEAR({exit_date}),7,1),1,0))")
    sh.put("ula_lower", "={la:ula_threshold_lower}*(1+{la:ula_threshold_growth}/100)^{ula_indexations}")
    sh.put("ula_upper", "={la:ula_threshold_upper}*(1+{la:ula_threshold_growth}/100)^{ula_indexations}")
    sh.put("local_tax_rate", "=IF({jurisdiction}=\"la_city\",IF({exit_price}>={ula_upper},{la:ula_rate_upper}/100,"
           "IF({exit_price}>{ula_lower},{la:ula_rate_lower}/100,0)),0)",
           "only the City of Los Angeles among the hand-check loans")
    sh.put("selling_cost", "=IF({high_tax_metro}=1,{param:selling_cost_pct_high_tax},{param:selling_cost_pct})/100")
    sh.put("exit_net", "={exit_price}*(1-{selling_cost}-{local_tax_rate})")
    sh.put("acq_rate", "={ust5}+{param:bridge_spread_bps}/10000+{rate_shift}")
    sh.put("kink", "=({param:ltv_asis}/100*{value}/({param:ltc}/100)-{renovation_budget})"
           "/(1+{param:buyer_closing_pct}/100)", "price where the as-is LTV starts to bind")

    def price_table(tag: str, price_formula: str):
        sh.head(f"Cash flows at price {tag}")
        sh.put(f"{tag}:price", price_formula)
        sh.put(f"{tag}:cost", f"={{{tag}:price}}*(1+{{param:buyer_closing_pct}}/100)+{{renovation_budget}}")
        sh.put(f"{tag}:loan", f"=MIN({{param:ltc}}/100*{{{tag}:cost}},{{param:ltv_asis}}/100*{{value}})")
        sh.put(f"{tag}:interest", f"={{acq_rate}}*{{{tag}:loan}}")
        yrow(f"{tag}:tax_change", lambda c, t, r: f"={{prop13}}*({{tax_rate}}*{{{tag}:price}}-{{tax_current}})"
             f"*(1+{{la:prop13_growth}}/100)^{t - 1}", cols=YEARS)
        yrow(f"{tag}:noi", lambda c, t, r: f"={c}{rows['noi_path_S']}+{c}{rows['renovation']}-{c}{rows[tag + ':tax_change']}"
             f"-{c}{rows['downtime_loss']}", cols=YEARS)
        yrow(f"{tag}:unlevered", lambda c, t, r: f"=-{{{tag}:cost}}" if t == 0 else
             f"={c}{rows[tag + ':noi']}-{c}{rows['capex']}" + ("+{exit_net}" if t == 5 else ""), cols="B" + YEARS)
        yrow(f"{tag}:levered", lambda c, t, r: f"=-{{{tag}:cost}}+{{{tag}:loan}}" if t == 0 else
             f"={c}{rows[tag + ':unlevered']}-{{{tag}:interest}}" + (f"-{{{tag}:loan}}" if t == 5 else ""),
             cols="B" + YEARS)
        lv = rows[f"{tag}:levered"]
        sh.put(f"{tag}:npv_at_hurdle", f"=B{lv}+NPV({{param:hurdle}}/100,C{lv}:G{lv})")

    price_table("p0", "=0")
    price_table("pk", "={kink}")
    price_table("p2k", "=2*{kink}")
    sh.head("Return bid: NPV at the hurdle is a straight line in price on each side of the kink")
    sh.put("return_bid", "=IF(AND({p0:npv_at_hurdle}>0,{pk:npv_at_hurdle}<=0),"
           "{kink}*{p0:npv_at_hurdle}/({p0:npv_at_hurdle}-{pk:npv_at_hurdle}),"
           "IF(AND({pk:npv_at_hurdle}>0,{p2k:npv_at_hurdle}<{pk:npv_at_hurdle}),"
           "{kink}+{kink}*{pk:npv_at_hurdle}/({pk:npv_at_hurdle}-{p2k:npv_at_hurdle}),NA()))")
    price_table("bid", "={return_bid}")
    lv, uv, nv = rows["bid:levered"], rows["bid:unlevered"], rows["bid:noi"]
    sh.head("Results at the return bid")
    sh.put("irr_levered", f"=IRR(B{lv}:G{lv})", "equals the hurdle by construction")
    sh.put("irr_unlevered", f"=IRR(B{uv}:G{uv})")
    sh.put("equity", f"=-B{lv}")
    sh.put("equity_multiple", f"=SUM(C{lv}:G{lv})/{{equity}}")
    sh.put("cash_on_cash", f"=(SUM(C{lv}:G{lv})-{{exit_net}}+{{bid:loan}})/5/{{equity}}")
    sh.put("noi_y1", f"=C{nv}")
    sh.put("dscr_y1", "={noi_y1}/{bid:interest}")
    sh.put("dy_y1", "={noi_y1}/{bid:loan}")
    sh.put("breakeven_occ", "=({revenue}-{noi_y1}+{bid:interest})/({revenue}/{occ_eff})")
    sh.put("bid", "=MAX(MIN({value_bid},{return_bid}),0)")
    sh.put("discount", "=MAX(0,1-{bid}/{wl_balance_est})")


def par_or0(P: dict, name: str, g: str) -> float:
    return 0.0 if name == "none" else engine.par(P, name, g)


def build(log=print) -> list[dict]:
    d = pd.read_parquet(paths.OUTPUT_DIR / "underwrite_inputs.parquet")
    P, M = engine.load_params(), engine.load_market()
    rows = engine.prepare(d, P)
    chosen = select(rows, P, M)
    wb = Workbook()
    wb.remove(wb.active)
    for (case, scen), L in zip(CASES, chosen):
        build_case(wb.create_sheet(case), L, scen, P, M)
        log(f"hand check {case}: {L['whole_loan_id']} ({L.get('prop_city')}, {L.get('prop_state')}), {scen}")
    BOOK.parent.mkdir(parents=True, exist_ok=True)
    wb.save(BOOK)
    return chosen


def recalc(path=BOOK) -> None:
    """Open the workbook in Excel, recalculate every formula and save, so the computed values are stored."""
    ps = (f"$x = New-Object -ComObject Excel.Application; $x.Visible = $false; $x.DisplayAlerts = $false; "
          f"$w = $x.Workbooks.Open('{path}'); $x.CalculateFull(); $w.Save(); $w.Close($false); $x.Quit(); "
          f"[System.Runtime.InteropServices.Marshal]::ReleaseComObject($x) | Out-Null")
    subprocess.run(["powershell", "-NoProfile", "-Command", ps], check=True)
    scrub_metadata(path)


def scrub_metadata(path=BOOK) -> None:
    """Excel stamps the local user's name into docProps/core.xml and the file's folder into xl/workbook.xml on
    save; replace the author fields with 'mwall' and drop the folder."""
    import re
    import zipfile

    with zipfile.ZipFile(path) as z:
        items = [(i, z.read(i.filename)) for i in z.infolist()]
    tmp = path.with_suffix(".tmp")
    with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as out:
        for info, data in items:
            if info.filename == "docProps/core.xml":
                text = data.decode("utf-8")
                for tag in ("dc:creator", "cp:lastModifiedBy"):
                    text = re.sub(f"<{tag}>.*?</{tag}>", f"<{tag}>mwall</{tag}>", text)
                data = text.encode("utf-8")
            if info.filename == "xl/workbook.xml":
                text = re.sub(r'<mc:AlternateContent[^>]*>\s*<mc:Choice Requires="x15">\s*<x15ac:absPath[^>]*/>'
                              r'\s*</mc:Choice>\s*</mc:AlternateContent>', "", data.decode("utf-8"))
                text = re.sub(r"<x15ac:absPath[^>]*/>", "", text)
                data = text.encode("utf-8")
            out.writestr(info, data)
    tmp.replace(path)


def read(path=BOOK) -> dict[str, dict]:
    """label -> computed value, per sheet (column A label, column B value)."""
    wb = load_workbook(path, data_only=True)
    out = {}
    for ws in wb.worksheets:
        vals = {}
        for r in ws.iter_rows(min_col=1, max_col=8):
            if isinstance(r[0].value, str):
                vals[r[0].value] = r[1].value
                vals[r[0].value + "@row"] = [c.value for c in r[1:8]]
        out[ws.title] = vals
    return out
