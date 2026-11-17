import { columns, figure, hbars, legendHTML, stackedColumns, tableHTML } from "../lib/charts.js";
import { getSummary, stampMeta } from "../lib/data.js";
import { bp, int, money, pct, typeColor, typeLabel } from "../lib/format.js";

stampMeta();
const s = await getSummary();
const h = s.headline, w = s.wall;
const labels = w.buckets.map((b) => (b === "past due" ? "Past due" : b));
const SRC = "Source: SEC Form ABS-EE, exhibit EX-102 loan-level filings. Whole-loan balances (pari passu pieces counted once).";

// ------------------------------------------------------------------ 01 by type
{
  const total = w.buckets.map((_, i) => w.types.reduce((a, t) => a + w.balance[t][i], 0));
  const peak = total.indexOf(Math.max(...total));
  const { chart, legend } = figure(document.getElementById("by-type"), {
    q: "How much comes due each year, by property type?",
    take: `${labels[peak]} is the peak year: ${money(total[peak])} of whole-loan balance matures. Five- and ten-year loans from the 2019 and 2024 deals stack up in the same year.`,
    src: `${SRC} "Past due" is balance whose maturity date has passed.`,
    table: () => ({
      columns: [{ key: "b", label: "Maturity" }, ...w.types.map((t) => ({ key: t, label: typeLabel(t), r: 1, f: (v) => money(v) })),
        { key: "tot", label: "Total", r: 1, f: (v) => money(v) }],
      rows: w.buckets.map((b, i) => ({ b: labels[i], ...Object.fromEntries(w.types.map((t) => [t, w.balance[t][i]])), tot: total[i] })),
    }),
  });
  legend.innerHTML = legendHTML(w.types.map((t) => ({ color: typeColor(t), label: typeLabel(t) })));
  stackedColumns(chart, w.types.map((t) => ({ key: t, label: typeLabel(t), color: typeColor(t), values: w.balance[t] })), {
    buckets: w.buckets, labels, fmt: (v) => (v === 0 ? "0" : `$${v / 1e9}B`), height: 380,
    aria: "Stacked columns of maturing balance by year and property type",
    tip: (i, ser) => `<b>${labels[i]}, ${ser.label}</b><br>${money(ser.values[i])} of ${money(total[i])}`,
  });
}

// ------------------------------------------------------------------ 02 share with a gap
{
  const rows = s.gap_by_type.slice().sort((a, b) => b.share_with_gap - a.share_with_gap);
  const top = rows[0];
  const { chart } = figure(document.getElementById("share"), {
    q: "What share of each type's balance sits in loans a lender wouldn't refinance in full?",
    take: `${typeLabel(top.type)} leads: ${pct(top.share_with_gap, 0)} of its balance is in loans with a refinance gap, ${money(top.gap)} in all. The gap is measured on every loan as if it had to refinance at November 2026 terms, whatever its maturity date.`,
    src: "Loans with a refinance test (current NOI, or NOI at or below zero). Base scenario: today's Treasury yields, CBRE lending spreads, CoStar and CBRE cap-rate benchmarks, current conduit sizing floors.",
    table: () => ({
      columns: [{ key: "type", label: "Type", f: typeLabel }, { key: "loans", label: "Loans", r: 1, f: int },
        { key: "balance", label: "Balance", r: 1, f: (v) => money(v) }, { key: "share_with_gap", label: "Share with a gap", r: 1, f: (v) => pct(v) },
        { key: "loans_with_gap", label: "Loans with a gap", r: 1, f: int }, { key: "gap", label: "Refinance gap", r: 1, f: (v) => money(v) }],
      rows,
    }),
  });
  hbars(chart, rows.map((r) => ({ label: typeLabel(r.type), value: r.share_with_gap, color: "var(--water)", r })), {
    fmt: (v) => pct(v, 0), max: 1, aria: "Share of balance with a refinance gap by property type",
    tip: (d) => `<b>${d.label}</b><br>${pct(d.value)} of ${money(d.r.balance)}<br>Gap ${money(d.r.gap)} across ${int(d.r.loans_with_gap)} loans`,
  });
}

// ------------------------------------------------------------------ 03 rates and scenarios
{
  const g = s.scenario_gap;
  const base = g.by_rate.gap[g.by_rate.shift_bps.indexOf(0)];
  const up100 = g.by_rate.gap[g.by_rate.shift_bps.indexOf(100)];
  const { chart } = figure(document.getElementById("rates"), {
    q: "How much does the gap grow if rates rise?",
    take: `Each 100 bp on the refinance rate adds roughly ${money(up100 - base)} to the gap. Cap rates matter less, because ${pct(h.binding.dscr + h.binding.debt_yield, 0)} of loans are sized by an income test (DSCR or debt yield), not by value.`,
    src: "Refinance rate = 10-year Treasury + CBRE lending spread + a property-type premium, shifted as shown. All other inputs at the base scenario.",
    table: () => ({
      columns: [{ key: "r", label: "Rate shift", f: bp }, ...g.grid.cap.map((c, j) => ({ key: `c${j}`, label: `Cap ${bp(c)}`, r: 1, f: (v) => money(v) }))],
      rows: g.grid.rate.map((r, i) => ({ r, ...Object.fromEntries(g.grid.cap.map((c, j) => [`c${j}`, g.grid.gap[i][j]])) })),
      caption: "Total refinance gap by refinance-rate shift (rows) and cap-rate shift (columns).",
    }),
  });
  columns(chart, g.by_rate.shift_bps.map((b, i) => ({
    label: bp(b), value: g.by_rate.gap[i], color: b === 0 ? "var(--water-ink)" : "var(--water)",
  })), { yfmt: (v) => (v === 0 ? "0" : `$${v / 1e9}B`), height: 280, aria: "Refinance gap by refinance-rate shift",
    tip: (r) => `<b>Rate ${r.label}</b><br>Refinance gap ${money(r.value)}` });

  const sc = g.scenarios;
  document.getElementById("scen").innerHTML = `<figure class="fig"><p class="fig-q">The three named scenarios</p>
    ${tableHTML({
      columns: [{ key: "n", label: "Scenario" }, { key: "d", label: "What changes" }, { key: "gap", label: "Refinance gap", r: 1, f: (v) => money(v) },
        { key: "lw", label: "Loans with a gap", r: 1, f: int }, { key: "bb", label: "Bid below balance", r: 1, f: int }],
      rows: [
        { n: "Base", d: "Today's yields, spreads and cap-rate benchmarks; in-place NOI", gap: sc.base.gap, lw: sc.base.loans_with_gap, bb: sc.base.bid_below_balance },
        { n: "Downside", d: "Rates +100 bp, cap rates +50 bp, NOI cut by KBRA's haircut for the type, refinance DSCR test at 1.40x", gap: sc.downside.gap, lw: sc.downside.loans_with_gap, bb: sc.downside.bid_below_balance },
        { n: "Value-add", d: "Base, plus a multifamily unit renovation program", gap: sc.value_add.gap, lw: sc.value_add.loans_with_gap, bb: sc.value_add.bid_below_balance },
      ],
    })}<figcaption class="fig-foot"><span class="src">Scenario definitions and every parameter's source: <a href="/method.html#parameters">method</a>.</span></figcaption></figure>`;
}

// ------------------------------------------------------------------ 04 discounts
{
  const d = s.discounts;
  const { chart } = figure(document.getElementById("disc"), {
    q: "For loans in trouble, how far below the balance would a buyer's bid land?",
    take: `${int(d.n)} high-risk loans have a bid. ${pct(d.loans[0] / d.n, 0)} could be repaid in full by selling the property; for the rest the median implied discount is ${pct(d.median_discount_below_par, 0)}. None reaches a ${pct(d.hurdle, 0)} levered return at the value bid (${pct(d.share_clearing_hurdle_at_value, 1)}).`,
    src: `High risk: ${d.definition}. Bid = the lower of the value bid and the return bid; discount = 1 - bid / balance. Base scenario.`,
    table: () => ({
      columns: [{ key: "b", label: "Discount to par" }, { key: "n", label: "Loans", r: 1, f: int }, { key: "bal", label: "Balance", r: 1, f: (v) => money(v) }],
      rows: d.bins.map((b, i) => ({ b, n: d.loans[i], bal: d.balance[i] })),
    }),
  });
  columns(chart, d.bins.map((b, i) => ({ label: b, value: d.loans[i], color: i === 0 ? "var(--wall)" : "var(--water)" })),
    { yfmt: (v) => int(v), aria: "Number of high-risk loans by implied discount to par",
      tip: (r) => `<b>${r.label}</b><br>${int(r.value)} loans` });
}
