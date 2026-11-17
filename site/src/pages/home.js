import { figure, legendHTML, stackedColumns } from "../lib/charts.js";
import { getSummary, stampMeta } from "../lib/data.js";
import { int, money, pct } from "../lib/format.js";

stampMeta();

const s = await getSummary();
const h = s.headline;

// headline numbers come from the data, never from the page source
const fill = {
  gap_base: `$${(h.gap_base / 1e9).toFixed(1)} billion`, loans_scored: int(h.loans_scored), trusts: int(h.trusts),
  hurdle: pct(h.hurdle, 0),
};
document.querySelectorAll("[data-h]").forEach((el) => { if (fill[el.dataset.h]) el.textContent = fill[el.dataset.h]; });

// ------------------------------------------------------------------ hero: the wall, with the gap as water
const w = s.wall;
const total = w.buckets.map((_, i) => w.types.reduce((a, t) => a + w.balance[t][i], 0));
const gap = w.gap.map((g, i) => Math.min(g, total[i]));
const wallPart = total.map((t, i) => t - gap[i]);
const labels = w.buckets.map((b) => (b === "past due" ? "Past due" : b));
const host = document.getElementById("hero-fig");
const { chart, legend } = figure(host, {
  q: "When the debt comes due, and how much of it a lender wouldn't refinance today",
  take: `Balance of the ${int(h.loans_scored)} scored loans by maturity year. The blue is the refinance gap: what each loan owes beyond the largest new loan a lender would make at November 2026 rates, spreads and cap rates.`,
  src: "Source: SEC Form ABS-EE, exhibit EX-102 loan-level filings; refinance test in the base scenario (method). Loans maturing after 2035 not shown.",
  table: () => ({
    columns: [{ key: "b", label: "Maturity" }, { key: "n", label: "Loans", r: 1, f: int },
      { key: "t", label: "Balance", r: 1, f: (v) => money(v) }, { key: "g", label: "Refinance gap", r: 1, f: (v) => money(v) },
      { key: "p", label: "Gap share", r: 1, f: (v) => pct(v) }],
    rows: w.buckets.map((b, i) => ({ b: labels[i], n: w.loans[i], t: total[i], g: gap[i], p: total[i] ? gap[i] / total[i] : 0 })),
  }),
});
legend.innerHTML = legendHTML([{ color: "var(--wall)", label: "Refinanceable at today's terms" },
  { color: "var(--water)", label: "Refinance gap" }]);
stackedColumns(chart, [
  { key: "wall", label: "Refinanceable at today's terms", color: "var(--wall)", values: wallPart },
  { key: "gap", label: "Refinance gap", color: "var(--water)", values: gap },
], {
  buckets: w.buckets, labels, fmt: (v) => (v === 0 ? "0" : `$${v / 1e9}B`), animate: true, height: 380,
  aria: "Columns of maturing CMBS balance by year, with the refinance gap at the top of each column",
  tip: (i) => `<b>${labels[i]}</b><br>${int(w.loans[i])} loans, ${money(total[i])}<br>Refinance gap ${money(gap[i])} (${pct(gap[i] / total[i])})`,
  onClick: () => { window.location.href = "/wall.html"; },
});

// ------------------------------------------------------------------ findings
const office = s.gap_by_type.find((r) => r.type === "office");
const allBal = s.gap_by_type.reduce((a, r) => a + r.balance, 0);
const m25 = s.model.metrics.filter((r) => r.year === Math.max(...s.model.years));
const model = m25.find((r) => r.model === "model"), dy = m25.find((r) => r.model === "debt yield rank");
const mat = s.maturity;
const officeMat = mat.by_type.find((r) => r.type === "office");
const storageMat = mat.by_type.find((r) => r.type === "self_storage");
const items = [
  {
    v: money(office.gap), small: `of the ${money(h.gap_base)} gap`,
    h: "Office is half the problem on a third of the debt.",
    p: `Office loans hold ${pct(office.balance / allBal, 0)} of the balance with a refinance test but ${pct(office.gap / h.gap_base, 0)} of the gap. ${pct(office.share_with_gap, 0)} of office balance sits in loans a lender would not refinance in full today.`,
    a: ["/wall.html", "The gap by property type"],
  },
  {
    v: pct(h.median_irr_levered_at_value), small: `levered, against ${pct(h.median_irr_unlevered_at_value)} before debt`,
    h: "At market value, borrowing makes the return worse.",
    p: `That is the median five-year return to a buyer paying the model's value for the property and financing it with a bridge loan. Bridge debt at the 5-year Treasury plus 3 to 4.25 points costs more than these properties yield, so no loan reaches a ${pct(h.hurdle, 0)} hurdle at market value. The price that does is the return bid.`,
    a: ["/method.html#underwriting", "How bids are set"],
  },
  {
    v: pct(model.top10_capture, 0), small: `of ${Math.max(...s.model.years)} distress events, against ${pct(dy.top10_capture, 0)} for a debt-yield rank`,
    h: "The model finds trouble a debt-yield rule misses.",
    p: `The riskiest tenth of loan-months by the 12-month distress model held ${pct(model.top10_capture, 0)} of the next year's distress events and ${pct(model.top10_capture_balance, 0)} of the distressed balance, scored out of time on loans it never saw. Probability levels drift between years, so read them as rankings.`,
    a: ["/method.html#models", "How the models were tested"],
  },
  {
    v: `${pct(mat.gap_positive.failed_share, 0)} vs ${pct(mat.gap_zero.failed_share, 0)}`, small: "failed at maturity, with and without a gap",
    h: "A refinance gap barely predicted who failed at maturity. Property type did.",
    p: `Of ${int(mat.loans)} loans that reached maturity in the data, those with a refinance gap a year out failed about as often as those without. Office failed ${pct(officeMat.failed_share, 0)} of the time and self-storage ${pct(storageMat.failed_share, 0)}. The gap measures exposure to rates; failure also depends on who will lend against the property type at all.`,
    a: ["/method.html#models", "The maturity model"],
  },
];
document.getElementById("findings").innerHTML = items.map((it) => `
  <li><div class="v">${it.v}<small>${it.small}</small></div>
  <div><h3>${it.h}</h3><p>${it.p}</p><a class="more" href="${it.a[0]}">${it.a[1]}</a></div></li>`).join("");
