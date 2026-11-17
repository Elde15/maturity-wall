import { figure, lines, tableHTML } from "../lib/charts.js";
import { getHistory, getMeta, getScenarios, stampMeta } from "../lib/data.js";
import { makeParams, underwrite } from "../lib/engine.js";
import { dollars, escapeHTML, int, money, monthYear, pct, ratio, shortTrust, statusHTML, typeColor, typeLabel } from "../lib/format.js";
import { DISTRESSED } from "../lib/risk.js";

stampMeta();
const id = new URLSearchParams(location.search).get("id") || "";
const $ = (s) => document.getElementById(s);
const rec = /^WL[0-9a-f]{2}/i.test(id) ? await getHistory(id) : null;
if (!rec) {
  $("t-name").textContent = "Loan not found";
  $("t-where").innerHTML = `No scored loan has the id "${escapeHTML(id)}". <a href="/loans.html">Find a loan</a>.`;
  document.querySelectorAll("section.section").forEach((s) => { s.hidden = true; });
  throw new Error("no loan");
}
const [scen, meta] = await Promise.all([getScenarios(), getMeta()]);
const FEAT = meta.features;
const r = rec.row || {}, f = rec.facts || {};
const name = f.name || r.name || "Unnamed property";
document.title = `${name}: CMBS loan tear sheet`;

// ------------------------------------------------------------------ header
$("t-name").textContent = name;
$("t-where").textContent = [f.address, f.city, f.state, f.zip].filter(Boolean).join(", ") + (f.n_properties > 1 ? ` (largest of ${int(f.n_properties)} properties)` : "");
$("t-chips").innerHTML = `<span class="chip"><i style="background:${typeColor(r.type)}"></i>${typeLabel(r.type)}</span> ${statusHTML(r.status)}
  <span class="chip">${escapeHTML(r.trust || "")}</span>`;
const distressed = DISTRESSED.has(r.status);
const probStat = distressed ? ["In distress now", "special servicing, delinquency or past maturity"]
  : r.pf !== null && r.pf !== undefined ? [pct(r.pf, 0), `chance of failing to refinance at maturity (${int(r.rk_f)} of ${int(r.n_type)} ${typeLabel(r.type).toLowerCase()} loans by rank)`]
  : r.pd !== null && r.pd !== undefined ? [pct(r.pd), "chance of distress in the next 12 months"] : ["Not scored", "no usable status or inputs"];
$("t-stats").innerHTML = [
  [money(r.bal), "whole-loan balance"], [monthYear(r.mat), "maturity"], probStat,
  [r.gap_pct === null || r.gap_pct === undefined ? "n/a" : pct(r.gap_pct, 0), "refinance gap, base scenario"],
].map(([v, k]) => `<li><span class="v">${v}</span><span class="k">${k}</span></li>`).join("");

// ------------------------------------------------------------------ 01 facts
const STRUCT = { WL: "Whole loan in this trust", PP: "Pari passu piece", AB: "A/B structure" };
const factRows = [
  ["Original amount (this trust's note)", dollars(f.orig_amount)], ["Balance (whole loan)", dollars(r.bal)],
  ["Coupon", f.coupon ? pct(f.coupon, 3) : "n/a"], ["Originated", f.orig_date || "n/a"],
  ["Maturity", f.maturity && r.mat && f.maturity !== r.mat ? `${f.maturity} in this filing; the model uses ${r.mat} (first-filed date or anticipated repayment date)` : f.maturity || r.mat || "n/a"],
  ["Amortization", f.amort_months ? `${Math.round(f.amort_months / 12)} years${f.io_months ? `, ${f.io_months} months interest-only` : ""}` : f.io_months ? "Interest-only" : "n/a"],
  ["Structure", STRUCT[f.structure] || f.structure || "n/a"], ["Property type", typeLabel(r.type)],
  ["Size", f.units ? `${int(f.units)} units` : f.sqft ? `${int(f.sqft)} sq ft` : "n/a"], ["Year built", f.year_built || "n/a"],
  ["Appraisal at securitization", f.appraisal_sec ? `${dollars(f.appraisal_sec)} (${f.appraisal_sec_date || "date n/a"})` : "n/a"],
  ["NOI at securitization", f.noi_sec === 0 ? "0 as filed (not reported)" : dollars(f.noi_sec)], ["Occupancy at securitization", f.occ_sec ? pct(f.occ_sec, 0) : "n/a"],
  ["Latest NOI (annualized)", dollars(rec.uw?.noi)], ["Debt yield", r.dy ? pct(r.dy) : "n/a"], ["DSCR (reported)", r.dscr ? ratio(r.dscr) : "n/a"],
  ["Trust", `${escapeHTML(shortTrust(r.trust))}, vintage ${r.vintage ?? "n/a"}`], ["Loan id (this site)", escapeHTML(id)],
];
$("facts").innerHTML = factRows.map(([k, v]) => `<div><dt>${k}</dt><dd>${v}</dd></div>`).join("");

// ------------------------------------------------------------------ 02 performance
{
  const s = rec.series;
  const t = s.period_end.map((d) => { const [y, m] = d.split("-").map(Number); return y + (m - 0.5) / 12; });
  const xmin = Math.floor(Math.min(...t)), xmax = Math.ceil(Math.max(...t));
  const host = $("perf");
  const mk = (q, vals, yfmt, color, src) => {
    const pts = t.map((x, i) => [x, vals[i]]);
    const ok = pts.filter((p) => p[1] !== null).length;
    const { chart } = figure(host, { q, src: ok ? src : "Not reported in the filings.",
      table: () => ({ columns: [{ key: "d", label: "Period" }, { key: "v", label: q, r: 1, f: (v) => (v === null ? "n/a" : yfmt(v)) }],
        rows: s.period_end.map((d, i) => ({ d, v: vals[i] })) }) });
    if (ok) lines(chart, [{ label: q, color, points: pts }], { xmin, xmax, xfmt: (v) => String(Math.round(v)), yfmt, height: 200, xticks: 4,
      aria: `${q} by filing month` });
  };
  mk("NOI, annualized", s.noi, (v) => money(v), "var(--ink)", "Servicer-reported, annualized from year-to-date where needed.");
  mk("DSCR", s.dscr, (v) => `${v.toFixed(2)}x`, "var(--water)", "As reported by the servicer.");
  mk("Occupancy", s.occ, (v) => pct(v, 0), "var(--wall)", "Most recent physical occupancy reported.");
}

// ------------------------------------------------------------------ 03 model view
{
  const drv = (list, kind) => (list || []).map((d) => {
    const def = FEAT[d.feature] || { definition: d.feature, unit: "" };
    const v = d.value;
    const fmtv = v === null || v === undefined ? "missing" : ["ratio", "share", "rate"].includes(def.unit) ? pct(v)
      : def.unit === "x" ? ratio(v) : def.unit === "0/1" ? (v ? "yes" : "no") : typeof v === "number" ? (Math.abs(v) < 10 ? v.toFixed(2) : int(Math.round(v))) : escapeHTML(v);
    const up = d.log_odds > 0;
    const short = def.definition.split(/[:(;]/)[0].trim();
    return `<li><span><b>${escapeHTML(short)}</b>: ${fmtv}</span><span class="dir ${up ? "up" : "down"}">${up ? "raises" : "lowers"} ${kind} risk</span>
      <span class="def">${escapeHTML(def.definition)}${def.unit ? ` (${def.unit})` : ""}. Effect ${d.log_odds > 0 ? "+" : ""}${d.log_odds.toFixed(2)} on the log-odds.</span></li>`;
  }).join("");
  const iv = (p, lo, hi) => {
    const sc = (v) => Math.min(100, Math.max(0, v * 100));
    return `<div class="interval" aria-hidden="true"><span class="band" style="left:${sc(lo)}%;width:${sc(hi) - sc(lo)}%"></span><span class="pt" style="left:${sc(p)}%"></span></div>`;
  };
  const parts = [];
  if (distressed) parts.push(`<p class="note-c">This loan is already in distress (${escapeHTML(r.status)}), so the models, which score loans that are still performing, don't apply. The underwriting below still sizes a refinance and a bid.</p>`);
  const probs = [];
  if (r.pf !== null && r.pf !== undefined) probs.push(`<div class="prob"><span class="label">Maturity model: failure at maturity</span><br><span class="v">${pct(r.pf, 0)}</span>
    <span class="iv">90% interval ${pct(r.pf_lo, 0)} to ${pct(r.pf_hi, 0)}</span>${iv(r.pf, r.pf_lo, r.pf_hi)}
    <ul class="drivers">${drv(rec.drivers_maturity, "failure")}</ul></div>`);
  if (r.pd !== null && r.pd !== undefined) probs.push(`<div class="prob"><span class="label">Distress in the next 12 months</span><br><span class="v">${pct(r.pd)}</span>
    <span class="iv">90% interval ${pct(r.pd_lo)} to ${pct(r.pd_hi)}; rank ${int(r.rk_d)} of ${int(r.n_type)} ${typeLabel(r.type).toLowerCase()} loans</span>${iv(r.pd * 10, r.pd_lo * 10, r.pd_hi * 10)}
    <ul class="drivers">${drv(rec.drivers_distress, "distress")}</ul></div>`);
  if (probs.length) parts.push(`<div class="probs">${probs.join("")}</div>`);
  parts.push(`<p class="small muted">Probabilities are precomputed by the models on the latest filing; the scenario controls below don't change them. Drivers are the three inputs that move this loan's score most (market-wide series such as Treasury yields are left out because they move every loan together). The distress bar is drawn on a 0 to 10% scale. Read levels with care: they drift between years, and the rankings are what held up out of time (<a href="/method.html#models">method</a>).</p>`);
  $("model").innerHTML = parts.join("");
}

// ------------------------------------------------------------------ 04 underwriting, live in the browser
const P = makeParams(scen), M = scen.market;
const L = rec.uw;
const SC = scen.scenarios;
let cur = "base";
$("scen-pick").innerHTML = SC.map((s) => `<button type="button" role="radio" aria-checked="${s.scenario === cur}" data-s="${s.scenario}">${s.label}</button>`).join("");
$("scen-pick").addEventListener("click", (e) => {
  const b = e.target.closest("button");
  if (!b) return;
  cur = b.dataset.s;
  $("scen-pick").querySelectorAll("button").forEach((x) => x.setAttribute("aria-checked", String(x === b)));
  drawUW();
});

function drawUW() {
  const S = P.scenarios[cur];
  $("scen-note").textContent = `${S.label} scenario: ${S.notes}. Valued ${M.date}; 10-year Treasury ${pct(M.ust10, 2)}, 5-year ${pct(M.ust5, 2)}.`;
  if (!L) {
    $("uw").innerHTML = `<p class="note-c">Not underwritten: the filings carry no usable NOI for this loan, so the engine doesn't size a refinance or value the property.</p>`;
    return;
  }
  const u = underwrite(L, S, P, M, { keepFlows: true });
  if (!u.value && u.value !== 0) {
    $("uw").innerHTML = `<p class="note-c">Not valued: ${escapeHTML(L.tier_reason || "no usable NOI")}.${u.refi_gap !== undefined ? ` With income at or below zero no lender would size a new loan, so the refinance gap is the whole balance, ${money(u.refi_gap)}.` : ""}</p>`;
    return;
  }
  const bind = Math.min(u.p_ltv, u.p_dscr, u.p_dy);
  const sizingRows = [["Loan to value", u.p_ltv], ["Debt service coverage", u.p_dscr], ["Debt yield", u.p_dy]];
  const sizingHTML = `<div class="table-wrap" tabindex="0" role="region" aria-label="Table"><table class="data"><thead><tr><th scope="col">Lender test</th><th scope="col" class="r">Largest new loan</th></tr></thead><tbody>
    ${sizingRows.map(([k, v]) => `<tr class="${v === bind ? "binding" : ""}"><th scope="row">${k}${v === bind ? " (binds)" : ""}</th><td class="r">${money(v)}</td></tr>`).join("")}
    <tr><th scope="row">Loan balance today</th><td class="r">${money(L.wl_balance_est)}</td></tr>
    <tr class="binding"><th scope="row">Refinance gap</th><td class="r">${money(u.refi_gap)}</td></tr></tbody></table></div>`;
  const value = `<div class="table-wrap" tabindex="0" role="region" aria-label="Table"><table class="data"><tbody>
    <tr><th scope="row">Stressed NOI</th><td class="r">${dollars(u.noi_stressed)}</td></tr>
    <tr><th scope="row">Cap rate (${escapeHTML(u.cap_method)}, ${escapeHTML(L.bench_kind)} benchmark)</th><td class="r">${pct(u.cap_rate, 2)}</td></tr>
    <tr><th scope="row">Value</th><td class="r">${money(u.value)}</td></tr>
    <tr><th scope="row">Value bid (after lease-up, reserves, closing)</th><td class="r">${money(u.value_bid)}</td></tr>
    <tr><th scope="row">Return bid (levered IRR = ${pct(u.hurdle ?? (P.par.hurdle_levered_irr.all / 100), 0)})</th><td class="r">${u.return_bid === undefined || Number.isNaN(u.return_bid) ? "n/a (tier C)" : money(u.return_bid)}</td></tr>
    <tr class="binding"><th scope="row">Implied bid</th><td class="r">${money(u.bid)}</td></tr>
    <tr><th scope="row">Discount to the loan balance</th><td class="r">${u.refinanceable_by_sale ? "None: a sale at the bid would cover the loan" : pct(u.discount, 0)}</td></tr></tbody></table></div>`;
  let returns = "";
  if (u.flows) {
    const fl = u.flows;
    returns = `<h3>Five-year buyer cash flows at the return bid</h3>${tableHTML({
      columns: [{ key: "k", label: "" }, ...[0, 1, 2, 3, 4, 5].map((t) => ({ key: `y${t}`, label: `Year ${t}`, r: 1, f: (v) => (v === null ? "" : money(v)) }))],
      rows: [
        { k: "NOI", ...Object.fromEntries([0, 1, 2, 3, 4, 5].map((t) => [`y${t}`, t === 0 ? null : fl.noi[t - 1]])) },
        { k: "Unlevered cash flow", ...Object.fromEntries(fl.unlev.map((v, t) => [`y${t}`, v])) },
        { k: "Interest", ...Object.fromEntries([0, 1, 2, 3, 4, 5].map((t) => [`y${t}`, t === 0 ? null : -fl.interest])) },
        { k: "Levered cash flow", ...Object.fromEntries(fl.lev.map((v, t) => [`y${t}`, v])) },
      ],
      caption: `Year 0 is the purchase (price plus closing costs${u.renovation_budget ? " and the renovation budget" : ""}, less the bridge loan); year 5 includes the sale at a ${pct(u.exit_cap, 2)} exit cap rate less ${pct(u.exit_cost_rate, 1)} selling costs and transfer taxes, and repays the loan.`,
    })}
    <div class="table-wrap" tabindex="0" role="region" aria-label="Table"><table class="data"><tbody>
      <tr><th scope="row">Levered IRR / unlevered IRR</th><td class="r">${pct(u.irr_levered)} / ${pct(u.irr_unlevered)}</td></tr>
      <tr><th scope="row">Equity required / multiple</th><td class="r">${money(u.equity)} / ${u.equity_multiple.toFixed(2)}x</td></tr>
      <tr><th scope="row">Average cash-on-cash yield</th><td class="r">${pct(u.cash_on_cash)}</td></tr>
      <tr><th scope="row">Bridge loan, year-one DSCR and debt yield</th><td class="r">${money(u.loan_at_bid)}, ${ratio(u.dscr_y1)}, ${pct(u.dy_y1)}</td></tr>
      <tr><th scope="row">Break-even occupancy</th><td class="r">${pct(u.breakeven_occ, 0)}</td></tr>
      <tr><th scope="row">Levered IRR if the buyer pays the value bid</th><td class="r">${pct(u.irr_at_value_bid)}</td></tr></tbody></table></div>`;
  } else {
    returns = `<p class="note-c">Confidence tier C (${escapeHTML(L.tier_reason || typeLabel(L.group) + " is valued by direct capitalization only")}): no cash-flow model, so the implied bid is the value bid.</p>`;
  }
  // sensitivity: implied bid and refinance gap as rates and cap rates move
  const rates = [-100, 0, 100, 200], caps = [-100, -50, 0, 50, 100];
  const grid = rates.map((rs) => caps.map((cs) => underwrite(L, S, P, M, { rateShiftBps: S.rate_shift_bps + rs, capShiftBps: S.cap_shift_bps + cs })));
  const gridTable = (key, label) => `<div class="table-wrap" tabindex="0" role="region" aria-label="Table"><table class="data sens"><caption>${label}: rows shift the refinance and acquisition rates, columns shift cap rates, both from the ${S.label.toLowerCase()} scenario. The outlined cell is the scenario itself.</caption>
    <thead><tr><th scope="col">Rate shift</th>${caps.map((c) => `<th scope="col" class="r">Cap ${c > 0 ? "+" : ""}${c} bp</th>`).join("")}</tr></thead><tbody>
    ${grid.map((row, i) => `<tr><th scope="row">${rates[i] > 0 ? "+" : ""}${rates[i]} bp</th>${row.map((g, j) => `<td class="r${rates[i] === 0 && caps[j] === 0 ? " cur" : ""}">${money(g[key])}</td>`).join("")}</tr>`).join("")}
    </tbody></table></div>`;
  $("uw").innerHTML = `<div class="uw-grid"><div><h3>Refinance test</h3>${sizingHTML}<p class="small muted">Refinance rate ${pct(u.refi_rate, 2)}; loan constant ${pct(u.loan_constant, 2)}.</p></div>
    <div><h3>Value and bids</h3>${value}</div></div>${returns}
    <h3 style="margin-top:var(--sp-6)">Sensitivity</h3>${gridTable("bid", "Implied bid")}${gridTable("refi_gap", "Refinance gap")}
    <p class="small muted">Computed in your browser by the same engine that produced the published tables (it matches the Python engine to the cent; method). Indicative economic bid for the property, not an offer for the loan.</p>`;
}
drawUW();

// ------------------------------------------------------------------ 05 sources
{
  const s = rec.series, cik = rec.cik;
  const url = (acc) => `https://www.sec.gov/Archives/edgar/data/${cik}/${acc.replace(/-/g, "")}/${acc}-index.htm`;
  const n = s.accession.length;
  const latest = s.accession[n - 1];
  $("sources").innerHTML = `<p>Latest filing: <a href="${url(latest)}">Form ABS-EE ${latest}</a>, period ending ${s.period_end[n - 1]}, filed ${s.filed[n - 1] || "n/a"}. Every number on this page comes from exhibit EX-102 of these filings, from the market sources listed under <a href="/method.html#sources">method</a>, or from the models.</p>
    <details class="filings"><summary>All ${int(n)} filings for this loan</summary>${tableHTML({
      columns: [{ key: "p", label: "Period" }, { key: "f", label: "Filed" }, { key: "a", label: "Accession" }],
      rows: s.accession.map((a, i) => ({ p: s.period_end[i], f: s.filed[i] || "", a })).reverse(),
    }).replace(/(\d{10}-\d{2}-\d{6})(<\/td>)/g, (m, acc, end) => `<a href="${url(acc)}">${acc}</a>${end}`)}</details>`;
}
