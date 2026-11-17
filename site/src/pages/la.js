import { figure, hbars, legendHTML, lines, stackedColumns, tableHTML } from "../lib/charts.js";
import { getHistory, getJSON, getScenarios, stampMeta } from "../lib/data.js";
import { dollars, escapeHTML, int, money, monthYear, pct, statusHTML, typeColor, typeLabel } from "../lib/format.js";
import { BANDS } from "../lib/risk.js";

stampMeta();
const $ = (s) => document.getElementById(s);
const [la, scen] = await Promise.all([getJSON("/data/la.json"), getScenarios()]);
const mk = la.market;
const REPO = "https://github.com/Elde15/maturity-wall/blob/main";

// ------------------------------------------------------------------ 01 summary
$("la-h").textContent = `Los Angeles: an estimated ${money(mk.scenarios.base.gap)} refinance gap, and the local taxes that change a buyer's math`;
$("sum").innerHTML = la.summary.map((s) => `<li>${escapeHTML(s)}</li>`).join("");

// ------------------------------------------------------------------ 02 market
{
  const host = $("mkt");
  const w = mk.wall, labels = w.buckets.map((b) => (b === "past due" ? "Past due" : b));
  const total = w.buckets.map((_, i) => w.types.reduce((a, t) => a + w.balance[t][i], 0));
  const f1 = figure(host, {
    q: "When does Los Angeles debt come due?",
    take: `${int(mk.loans)} loans, ${money(mk.balance)}: ${mk.counties.map((c) => `${c.county} County ${int(c.loans)} (${money(c.balance)})`).join(", ")}. Another ${int(mk.ca_outside)} California loans sit outside the metro. 2026 looks thin because most deals issued in 2016, whose ten-year loans mature now, filed no loan-level data; 2029 stacks ten-year loans from 2019 deals on five-year loans from 2024.`,
    src: "Whole-loan balance by maturity year. Source: SEC EX-102 filings; county from the Census geocoder.",
    table: () => ({ columns: [{ key: "b", label: "Maturity" }, ...w.types.map((t) => ({ key: t, label: typeLabel(t), r: 1, f: (v) => money(v) }))],
      rows: w.buckets.map((b, i) => ({ b: labels[i], ...Object.fromEntries(w.types.map((t) => [t, w.balance[t][i]])) })) }),
  });
  f1.legend.innerHTML = legendHTML(w.types.map((t) => ({ color: typeColor(t), label: typeLabel(t) })));
  stackedColumns(f1.chart, w.types.map((t) => ({ key: t, label: typeLabel(t), color: typeColor(t), values: w.balance[t] })), {
    buckets: w.buckets, labels, fmt: (v) => (v === 0 ? "0" : `$${(v / 1e9).toFixed(1)}B`), height: 300,
    aria: "Los Angeles maturing balance by year and type", tip: (i, s) => `<b>${labels[i]}, ${s.label}</b><br>${money(s.values[i])} of ${money(total[i])}` });

  const bt = mk.by_type.filter((t) => t.gap_share_la !== null);
  const diff = bt.map((t) => ({ ...t, d: t.gap_share_la - t.gap_share_us })).sort((a, b) => b.d - a.d);
  const worse = diff[0], better = diff[diff.length - 1];
  const rows = bt.flatMap((t) => [
    { label: `${typeLabel(t.type)}, LA`, value: t.gap_share_la, color: "var(--water)", t },
    { label: "national", value: t.gap_share_us, color: "var(--wall-light)", t }]);
  const f2 = figure(host, {
    q: "Is the gap worse here than nationally?",
    take: `Mostly not: for most types Los Angeles sits near the national share or below it. The exceptions run both ways. ${typeLabel(worse.type)} is worse here (${pct(worse.gap_share_la, 0)} of balance in loans with a gap, against ${pct(worse.gap_share_us, 0)} nationally); ${typeLabel(better.type).toLowerCase()} is better (${pct(better.gap_share_la, 0)} against ${pct(better.gap_share_us, 0)}). A share counts every loan with a gap of any size. ${int(mk.no_refi_test)} of the ${int(mk.loans)} Los Angeles loans have no refinance test (no usable NOI) and are left out.`,
    src: "Base scenario. Share of each type's balance, among loans with a refinance test.",
    table: () => ({ columns: [{ key: "type", label: "Type", f: typeLabel }, { key: "tested", label: "LA loans tested", r: 1, f: int },
      { key: "gap_share_la", label: "Share with a gap, LA", r: 1, f: (v) => pct(v) }, { key: "gap_share_us", label: "National", r: 1, f: (v) => pct(v) },
      { key: "gap", label: "LA gap", r: 1, f: (v) => money(v) }], rows: mk.by_type }),
  });
  f2.legend.innerHTML = legendHTML([{ color: "var(--water)", label: "Los Angeles" }, { color: "var(--wall-light)", label: "National" }]);
  hbars(f2.chart, rows, { fmt: (v) => pct(v, 0), max: 1, aria: "Share of balance with a refinance gap, Los Angeles against the national figure",
    tip: (d) => `<b>${typeLabel(d.t.type)}</b><br>Los Angeles ${pct(d.t.gap_share_la)}<br>National ${pct(d.t.gap_share_us)}` });

  const sc = mk.scenarios;
  const notSold = sc.base.loans_with_gap - sc.base.bid_below_balance;
  host.insertAdjacentHTML("beforeend", `
    <figure class="fig"><p class="fig-q">How do Los Angeles loans fall into the risk bands?</p>
    <p class="fig-take">${escapeHTML(mk.band_rule)}</p>${tableHTML({
      columns: [{ key: "k", label: "Risk band" }, { key: "la", label: "Los Angeles", r: 1 }, { key: "us", label: "National", r: 1 }],
      rows: BANDS.slice().reverse().map((b) => ({ k: b.label, la: pct(mk.bands.la[b.k]), us: pct(mk.bands.us[b.k]) })),
    })}</figure>
    <figure class="fig"><p class="fig-q">The scenarios in Los Angeles</p>
    <p class="fig-take">In the base case ${int(sc.base.loans_with_gap)} loans couldn't refinance in full, but at the modeled bid a sale would cover the balance for all but ${int(sc.base.bid_below_balance)} of them: for about ${int(notSold)} loans the shortfall is a refinancing problem, not a value problem. The value-add scenario changes only the buyer's plan (a multifamily renovation program), not the refinance test, so its gap matches the base case.</p>${tableHTML({
      columns: [{ key: "s", label: "Scenario" }, { key: "gap", label: "Refinance gap", r: 1, f: (v) => money(v) },
        { key: "n", label: "Loans with a gap", r: 1, f: int }, { key: "b", label: "Bid below balance", r: 1, f: int }],
      rows: scen.scenarios.map((x) => ({ s: x.label, gap: sc[x.scenario].gap, n: sc[x.scenario].loans_with_gap, b: sc[x.scenario].bid_below_balance })),
    })}</figure>
    <figure class="fig"><p class="fig-q">Were Los Angeles properties appraised richer than the market?</p>
    <p class="fig-take">The table compares each property's cap rate at securitization (its NOI over its appraisal) with the survey benchmark for its type at the time. A negative spread means the appraisal was richer than the survey; the model carries that spread into today's cap rate, so a rich appraisal means a lower cap rate and a higher value and bid. Lodging, self-storage and mixed use have no benchmark series of their own and aren't shown.${mk.cap_spreads.filter((t) => t.la_median !== null).every((t) => t.la_median < t.us_median) ? " In every type shown, Los Angeles appraisals ran richer than the national median, so the model's Los Angeles values sit higher than a survey cap rate alone would put them." : ""}</p>${tableHTML({
      columns: [{ key: "type", label: "Type", f: typeLabel }, { key: "la_loans", label: "LA loans", r: 1, f: int },
        { key: "la_median", label: "LA median spread", r: 1, f: (v) => (v === null ? "too few" : `${(v * 100).toFixed(2)} pts`) },
        { key: "us_median", label: "National median spread", r: 1, f: (v) => `${(v * 100).toFixed(2)} pts` }],
      rows: mk.cap_spreads,
    })}</figure>`);
}

// ------------------------------------------------------------------ 03 local context
$("local").innerHTML = `<div class="table-wrap" tabindex="0" role="region" aria-label="Local market figures"><table class="data loc-table"><thead><tr><th scope="col">Measure, third quarter 2026</th><th scope="col">Figures</th></tr></thead><tbody>
  ${la.local.map((r) => `<tr><th scope="row">${escapeHTML(r.label)}</th><td>${r.cites.map((c) => {
    const v = r.unit === "%" ? `${c.value.toFixed(1)}%` : r.unit === "units" ? int(c.value) : r.unit === "$" ? `$${c.value.toFixed(0)}` : `$${c.value.toFixed(2)}`;
    return `<b>${v}</b> <a href="${escapeHTML(c.url)}">${escapeHTML(c.publisher)}</a><span class="m">${escapeHTML(c.metric.replace(/_/g, " "))}, ${escapeHTML(c.period)}; published ${escapeHTML(c.date)}</span>`;
  }).join("")}</td></tr>`).join("")}</tbody></table></div>`;

// ------------------------------------------------------------------ 04 rules
{
  const L = scen.engine.la, r = mk.rules;
  const lo = L["ula|la_city|threshold_lower"], hi = L["ula|la_city|threshold_upper"];
  const base = 0.0011 + 0.0045;
  const tax = (p) => p * (base + (p >= hi ? 0.055 : p > lo ? 0.04 : 0));
  const bind = r.rso_binding + r.rstpo_binding + r.ab1482_binding;
  $("rules").innerHTML = `
    <p><b>Measure ULA.</b> Inside the City of Los Angeles, a sale above ${dollars(lo)} pays 4% of the whole price, and 5.5% at ${dollars(hi)} or more (thresholds from July 1, 2026, indexed each year), on top of the city's 0.45% and the county's 0.11%. The cliff is sharp: the transfer taxes on a ${dollars(lo)} sale come to ${dollars(tax(lo))}; one dollar more costs ${dollars(tax(lo + 1))}. The model charges ULA on the modeled sale at the end of a five-year hold: ${int(r.ula_upper_at_exit)} of the ${int(r.la_city_loans)} City loans would pay 5.5% and ${int(r.ula_lower_at_exit)} would pay 4%.</p>
    <p><b>Proposition 13.</b> A purchase resets the property tax to the price, at the county's average rate (1.179% in Los Angeles County, 1.058% in Orange County), and it then grows at most 2% a year. The seller's tax isn't in the filings, so the model estimates it from the appraisal at securitization grown 2% a year and caps it at the tax on the property's current value, because an assessment can't exceed market value (Proposition 8). The buyer pays tax on its own price. For a property worth less than its old assessment, the seller is already taxed on current value and a sale changes little; for one worth more, the buyer's higher tax lowers the value. Applied to ${int(r.prop13_loans)} loans; the other ${int(r.prop13_multi_property + r.prop13_no_appraisal)} are multi-property loans (${int(r.prop13_multi_property)}) or have no appraisal date (${int(r.prop13_no_appraisal)}).</p>
    <p><b>Rent caps.</b> Multifamily rent growth is capped at 3% for City of Los Angeles buildings from 1978 or earlier (${int(r.rso_loans)} loans), at 1.919% in unincorporated Los Angeles County for buildings from 1995 or earlier (${int(r.rstpo_loans)}), and at the state's 8.7% for other buildings 15 or more years old (${int(r.ab1482_loans)}). Against the model's ${pct(r.mf_growth, 1)} growth path, only a cap below it changes the cash flows: ${int(bind)} loan${bind === 1 ? "" : "s"}, all under the County's ordinance. The two local ordinances matter more another way: under them the model runs no renovation program, because the rent premium can't be charged to sitting tenants.</p>
    <p class="small">Every rule cites its official source and the date it was checked (<a href="/method.html#parameters">parameters</a>). City limits come from the Census geocoder at each property's coordinates, not from postal names: Van Nuys and Sherman Oaks are inside the City.</p>`;
}

// ------------------------------------------------------------------ 05 cases
$("sel").innerHTML = `Picked by a rule committed to the repository (${escapeHTML(la.selection.commit)}) before any case file was written: the top review-priority loan in office, in multifamily, and in retail or industrial; the loan the distress model rates safest among those a debt-yield rule (under 8%) flags; and the widest disagreement between the model's rank and that rule's. <a href="${REPO}/docs/la/selection.md">The rule and the full candidate list</a>. In each case's table, "Model" shows the maturity model for a loan within 24 months of maturity and the 12-month distress model otherwise.`;
const host = $("cases");
for (const c of la.cases) {
  const rec = await getHistory(c.id);
  const r = rec.row;
  const div = document.createElement("article");
  div.className = "case";
  const prob = r.pf !== null ? `maturity model ${pct(r.pf, 0)}, rank ${int(r.rk_f)} of ${int(c.n_f)}` : r.pd !== null ? `distress ${pct(r.pd)}, rank ${int(r.rk_d)} of ${int(r.n_type)}` : "not scored";
  div.innerHTML = `<p class="why">${escapeHTML(c.label)}</p><h3>${escapeHTML(c.facts.name)}</h3>
    <p class="addr">${escapeHTML(c.facts.address)} &middot; <span class="chip"><i style="background:${typeColor(r.type)}"></i>${typeLabel(r.type)}</span> ${statusHTML(r.status)}</p>
    <div class="case-grid"><div>
      <p class="k"><b>Why it's here.</b> ${escapeHTML(c.why)}</p>
      <p class="k">${escapeHTML(c.story)}</p>
      <p class="k"><b>Refinance and bid.</b> ${escapeHTML(c.test)}</p>
      <p class="k"><b>Local context.</b> ${escapeHTML(c.local)}</p>
      <p class="k"><b>What would make this wrong.</b> ${escapeHTML(c.risks)}</p>
    </div><div>
      ${tableHTML({ columns: [{ key: "k", label: "Base scenario" }, { key: "v", label: "", r: 1 }], rows: [
        { k: "Whole-loan balance", v: money(r.bal) }, { k: "Maturity", v: monthYear(r.mat) }, { k: "Model", v: prob },
        { k: "Refinance gap", v: r.gap === null ? "n/a" : money(r.gap) }, { k: "Value", v: money(r.value) },
        { k: "Implied bid", v: money(r.bid) }, { k: "Discount to balance", v: r.disc === null ? "n/a" : r.disc === 0 ? "none" : pct(r.disc, 0) },
        { k: "Confidence tier", v: r.tier || "n/a" }] }).replace('<table class="data">', '<table class="data kv">')}
      <div class="mini"></div>
      <p class="small"><a href="/loan.html?id=${c.id}">Full tear sheet, sensitivity and filings</a></p>
      ${c.cites.length ? `<ol class="cites">${[...new Map(c.cites.map((x) => [x.url, x])).values()].map((x) => `<li><a href="${escapeHTML(x.url)}">${escapeHTML(x.publisher)}</a>, ${escapeHTML(x.date)}</li>`).join("")}</ol>` : ""}
    </div></div>`;
  host.appendChild(div);
  const s = rec.series;
  const t = s.period_end.map((d) => { const [y, m] = d.split("-").map(Number); return y + (m - 0.5) / 12; });
  const pts = t.map((x, i) => [x, s.noi[i]]);
  if (pts.some((p) => p[1] !== null)) {
    const { chart } = figure(div.querySelector(".mini"), { q: "", src: "Annualized NOI by filing month, as reported." });
    lines(chart, [{ label: "NOI", color: "var(--ink)", points: pts }], { xmin: Math.floor(Math.min(...t)), xmax: Math.ceil(Math.max(...t)),
      xfmt: (v) => String(Math.round(v)), yfmt: (v) => money(v), height: 160, xticks: 3, aria: `NOI history for ${c.facts.name}` });
  }
}
host.insertAdjacentHTML("beforeend", `<div class="case"><h3>What the five cases show</h3><ul class="fails">${la.cases.map((c) =>
  `<li><b>${escapeHTML(c.facts.name)}.</b> ${escapeHTML(c.lesson)}</li>`).join("")}</ul></div>`);

// ------------------------------------------------------------------ 06 method
$("meth").innerHTML = `
  <p>The market is the Los Angeles-Long Beach-Anaheim metro (CBSA 31080), which the July 2023 federal delineation defines as Los Angeles and Orange counties. Each property is assigned by the county code from the Census geocoder, never by ZIP prefix.</p>
  <p>${escapeHTML(la.selection.rerun_note)} Both fixes are in the <a href="${REPO}/docs/decisions.md">decision log</a>; the Torrance storage file is the first one's clearest example.</p>
  <p>Case files state only what the filings and cited sources show. Bids are indicative economic values for the property, not offers for the loan; a buyer reaches a CMBS asset through the special servicer, a note sale, a foreclosure sale, a discounted payoff or a recapitalization. The full memo is <a href="${REPO}/docs/la/memo.md">in the repository</a>.</p>`;
