import { tableHTML } from "../lib/charts.js";
import { getLoans, getScenarios, getUW, stampMeta } from "../lib/data.js";
import { makeParams, underwrite } from "../lib/engine.js";
import { escapeHTML, int, money, pct, TYPE_ORDER, typeLabel } from "../lib/format.js";

stampMeta();
const $ = (s) => document.getElementById(s);
$("seg-status").textContent = "Loading the underwriting inputs for every loan...";
const [scen, uwj, lj] = await Promise.all([getScenarios(), getUW(), getLoans()]);
const P0 = makeParams(scen), M0 = scen.market;
const rowOf = new Map(lj.loans.map((l) => [l.id, l]));
const U = uwj.loans.map((u) => ({ ...u, _row: rowOf.get(u.whole_loan_id) || {} }));

// ------------------------------------------------------------------ controls
$("scenario").innerHTML = scen.scenarios.map((s) => `<option value="${s.scenario}">${s.label}</option>`).join("");
const types = TYPE_ORDER.filter((t) => U.some((u) => u.group === t));
$("seg-type").insertAdjacentHTML("beforeend", types.map((t) => `<option value="${t}">${typeLabel(t)}</option>`).join(""));
const states = [...new Set(U.map((u) => u._row.state).filter(Boolean))].sort();
$("seg-state").insertAdjacentHTML("beforeend", states.map((s) => `<option value="${s}">${s}</option>`).join(""));

const sl = { tsy: $("tsy"), spr: $("spr"), cap: $("cap"), hc: $("hc"), hur: $("hur") };
const sgn = (v) => `${v > 0 ? "+" : ""}${v}`;
function S0() { return P0.scenarios[$("scenario").value]; }
function resetSliders() {
  const S = S0();
  sl.tsy.value = S.rate_shift_bps; sl.spr.value = 0; sl.cap.value = S.cap_shift_bps; sl.hc.value = 0;
  sl.hur.value = Math.round(P0.par[S.hurdle_param].all);
  labels();
}
function labels() {
  const S = S0();
  $("o-tsy").textContent = `${sgn(+sl.tsy.value)} bp`;
  $("h-tsy").textContent = `10-year ${pct(M0.ust10 + sl.tsy.value / 1e4, 2)}, 5-year ${pct(M0.ust5 + sl.tsy.value / 1e4, 2)}. Moves the refinance rate and the bridge-loan rate.`;
  $("o-spr").textContent = `${sgn(+sl.spr.value)} bp`;
  $("h-spr").textContent = `CBRE commercial spread ${M0.spread_bps.commercial + +sl.spr.value} bp, multifamily ${M0.spread_bps.multifamily + +sl.spr.value} bp. Refinance rate only.`;
  $("o-cap").textContent = `${sgn(+sl.cap.value)} bp`;
  $("o-hc").textContent = `${sl.hc.value}%`;
  $("h-hc").textContent = S.noi_haircut === "none" ? "Cut to in-place NOI before sizing and valuation." : "Added to the scenario's KBRA haircut for each property type.";
  $("o-hur").textContent = `${sl.hur.value}%`;
  $("assume").textContent = `Inputs now: ${S.label} scenario lender tests; 10-year Treasury ${pct(M0.ust10 + sl.tsy.value / 1e4, 2)}; 5-year ${pct(M0.ust5 + sl.tsy.value / 1e4, 2)}; lending spread ${sgn(+sl.spr.value)} bp; cap rates ${sgn(+sl.cap.value)} bp; NOI haircut ${sl.hc.value}%${S.noi_haircut === "none" ? "" : " on top of KBRA's"}; levered hurdle ${sl.hur.value}%. Values as of ${M0.date}. Indicative economic values for the property, not offers for the loan; not investment advice.`;
}

function setup() {
  const S = S0(), extra = +sl.hc.value;
  const base = S.noi_haircut === "none" ? { all: 0 } : P0.par[S.noi_haircut];
  const P = { ...P0, par: { ...P0.par, lab_haircut: Object.fromEntries(Object.entries(base).map(([k, v]) => [k, v + extra])) } };
  const t = sl.tsy.value / 1e4, s = +sl.spr.value;
  const M = { ...M0, ust10: M0.ust10 + t, ust5: M0.ust5 + t,
    spread_bps: Object.fromEntries(Object.entries(M0.spread_bps).map(([k, v]) => [k, v + s])) };
  return { S: { ...S, rate_shift_bps: 0, cap_shift_bps: +sl.cap.value, noi_haircut: "lab_haircut" }, P, M, hurdle: sl.hur.value / 100 };
}
const baseCache = new Map();
function baseOf(u) {
  const key = `${$("scenario").value}|${u.whole_loan_id}`;
  if (!baseCache.has(key)) baseCache.set(key, underwrite(u, S0(), P0, M0));
  return baseCache.get(key);
}

// ------------------------------------------------------------------ segment
function agg(list) {
  const below = list.filter((x) => x.refinanceable_by_sale === false);
  const d = below.map((x) => x.discount).sort((a, b) => a - b);
  return { gap: list.reduce((a, x) => a + (x.refi_gap || 0), 0), withGap: list.filter((x) => (x.refi_gap_pct || 0) > 0).length,
    below: below.length, medDisc: d.length ? d[Math.floor(d.length / 2)] : NaN,
    value: list.reduce((a, x) => a + (x.value || 0), 0) };
}
const delta = (now, base, f, worse = 1) => {
  const dv = now - base;
  if (!dv || Number.isNaN(dv)) return '<span class="d">no change from the starting scenario</span>';
  return `<span class="d ${dv * worse > 0 ? "up" : "down"}">${dv > 0 ? "+" : "-"}${f(Math.abs(dv))} vs the starting scenario</span>`;
};
function runSegment() {
  const t0 = performance.now();
  const ty = $("seg-type").value, st = $("seg-state").value;
  const seg = U.filter((u) => (!ty || u.group === ty) && (!st || u._row.state === st));
  const { S, P, M, hurdle } = setup();
  const now = seg.map((u) => underwrite(u, S, P, M, { hurdle }));
  const base = seg.map(baseOf);
  const a = agg(now), b = agg(base);
  $("seg-stats").innerHTML = [
    [money(a.gap), "refinance gap", delta(a.gap, b.gap, money)],
    [int(a.withGap), "loans with a gap", delta(a.withGap, b.withGap, int)],
    [int(a.below), "loans whose bid is below the balance", delta(a.below, b.below, int)],
    [pct(a.medDisc, 0), "median discount where the bid is below", delta(a.medDisc, b.medDisc, (v) => `${(v * 100).toFixed(1)} pts`)],
  ].map(([v, k, d]) => `<li><span class="v">${v}</span><span class="k">${k}</span>${d}</li>`).join("");
  if (!ty) {
    const rows = types.map((t) => {
      const i = seg.map((u, j) => (u.group === t ? j : -1)).filter((j) => j >= 0);
      const an = agg(i.map((j) => now[j])), ab = agg(i.map((j) => base[j]));
      return { t, n: i.length, gb: ab.gap, gn: an.gap, bb: ab.below, bn: an.below };
    }).filter((r) => r.n);
    $("seg-table").innerHTML = tableHTML({
      columns: [{ key: "t", label: "Type", f: typeLabel }, { key: "n", label: "Loans", r: 1, f: int },
        { key: "gb", label: "Gap, start", r: 1, f: (v) => money(v) }, { key: "gn", label: "Gap, now", r: 1, f: (v) => money(v) },
        { key: "bb", label: "Bid below balance, start", r: 1, f: int }, { key: "bn", label: "Now", r: 1, f: int }],
      rows, caption: "Loans with usable NOI. Starting scenario as published; now = the sliders.",
    });
  } else $("seg-table").innerHTML = "";
  $("seg-status").textContent = `Recomputed ${int(seg.length)} loans in your browser in ${Math.round(performance.now() - t0)} ms.`;
}

// ------------------------------------------------------------------ one loan
let picked = U.slice().sort((a, b) => (b._row.opp ?? -1) - (a._row.opp ?? -1))[0];
function runOne() {
  if (!picked) return;
  const { S, P, M, hurdle } = setup();
  const n = underwrite(picked, S, P, M, { hurdle }), b = baseOf(picked);
  const r = picked._row;
  const row = (k, f) => ({ k, b: f(b), n: f(n) });
  const m = (key) => (x) => (x[key] === undefined || Number.isNaN(x[key]) ? "n/a" : money(x[key]));
  const p = (key, d = 1) => (x) => (x[key] === undefined || Number.isNaN(x[key]) ? "n/a" : pct(x[key], d));
  $("one-out").innerHTML = `<h3 style="margin-top:var(--sp-5)"><a href="/loan.html?id=${picked.whole_loan_id}">${escapeHTML(r.name || "Unnamed property")}</a></h3>
    <p class="small muted">${escapeHTML(r.city || "")}, ${r.state || ""} &middot; ${typeLabel(picked.group)} &middot; balance ${money(picked.wl_balance_est)} &middot; tier ${picked.tier || "n/a"}${r.pf !== null && r.pf !== undefined ? ` &middot; failure probability ${pct(r.pf, 0)} (precomputed)` : r.pd !== null && r.pd !== undefined ? ` &middot; 12-month distress probability ${pct(r.pd)} (precomputed)` : ""}</p>
    ${tableHTML({
      columns: [{ key: "k", label: "" }, { key: "b", label: "Starting scenario", r: 1 }, { key: "n", label: "Now", r: 1 }],
      rows: [row("Refinance gap", m("refi_gap")), row("Value", m("value")), row("Value bid", m("value_bid")), row("Return bid", m("return_bid")),
        row("Implied bid", m("bid")), row("Discount to balance", (x) => (x.refinanceable_by_sale ? "none" : p("discount", 0)(x))),
        row("Unlevered IRR at the return bid", p("irr_unlevered")), row("Levered IRR at the value bid", p("irr_at_value_bid"))],
    }).replace('<table class="data">', '<table class="data cmp">')}`;
}
function pickList(q) {
  const s = q.trim().toLowerCase();
  const hits = s.length < 2 ? [] : U.filter((u) => `${u._row.name || ""} ${u._row.city || ""} ${u._row.state || ""}`.toLowerCase().includes(s)).slice(0, 30);
  $("one-list").innerHTML = hits.map((u) => `<li role="option" tabindex="0" data-id="${u.whole_loan_id}">${escapeHTML(u._row.name || "Unnamed")}
    <small>${escapeHTML(u._row.city || "")}, ${u._row.state || ""} &middot; ${typeLabel(u.group)} &middot; ${money(u.wl_balance_est)}</small></li>`).join("");
}
$("one-q").addEventListener("input", (e) => pickList(e.target.value));
const choose = (li) => { picked = U.find((u) => u.whole_loan_id === li.dataset.id); $("one-list").innerHTML = ""; $("one-q").value = ""; runOne(); };
$("one-list").addEventListener("click", (e) => { const li = e.target.closest("li"); if (li) choose(li); });
$("one-list").addEventListener("keydown", (e) => { const li = e.target.closest("li"); if (li && (e.key === "Enter" || e.key === " ")) { e.preventDefault(); choose(li); } });

// ------------------------------------------------------------------ wiring
let mode = "seg", timer;
function run() { mode === "seg" ? runSegment() : runOne(); }
function schedule() {
  labels();
  clearTimeout(timer);
  if (mode === "seg") $("seg-status").textContent = "Recomputing...";
  timer = setTimeout(run, mode === "seg" ? 160 : 0);
}
$("panel").addEventListener("input", (e) => { if (e.target.id === "scenario") resetSliders(); schedule(); });
$("reset").addEventListener("click", () => { resetSliders(); schedule(); });
$("seg-type").addEventListener("change", schedule);
$("seg-state").addEventListener("change", schedule);
for (const [tab, m] of [["tab-seg", "seg"], ["tab-one", "one"]]) {
  $(tab).addEventListener("click", () => {
    mode = m;
    $("tab-seg").setAttribute("aria-selected", String(m === "seg")); $("tab-one").setAttribute("aria-selected", String(m === "one"));
    $("seg").hidden = m !== "seg"; $("one").hidden = m !== "one";
    run();
  });
}
resetSliders();
run();
