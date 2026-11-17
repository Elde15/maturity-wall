import { figure, legendHTML, lines, tableHTML } from "../lib/charts.js";
import { getJSON, getScenarios, getSummary, stampMeta } from "../lib/data.js";
import { escapeHTML, int, pct, typeLabel } from "../lib/format.js";

stampMeta();
const $ = (s) => document.getElementById(s);
const [s, scen, src] = await Promise.all([getSummary(), getScenarios(), getJSON("/data/sources.json")]);
const h = s.headline;
document.querySelectorAll("[data-h]").forEach((el) => { const v = h[el.dataset.h]; if (v !== undefined) el.textContent = int(v); });

// ------------------------------------------------------------------ test metrics
{
  const order = ["model", "debt yield rank", "debt yield < 10%", "DSCR < 1.25", "refinance gap > 0", "base rate"];
  const label = { model: "Distress model", "debt yield rank": "Debt yield, ranked", "debt yield < 10%": "Debt yield under 10%",
    "DSCR < 1.25": "DSCR under 1.25", "refinance gap > 0": "Refinance gap above zero", "base rate": "Base rate" };
  const rows = s.model.metrics.filter((r) => order.includes(r.model))
    .sort((a, b) => a.year - b.year || order.indexOf(a.model) - order.indexOf(b.model))
    .map((r) => ({ ...r, name: `${r.year}: ${label[r.model]}` }));
  $("metrics").innerHTML = `<figure class="fig"><p class="fig-q">Test results by year, distress model against the rules</p>
    <p class="fig-take">PR-AUC rewards ranking the rare distress events first (higher is better; the base rate is the event rate). Brier score measures probability error (lower is better). Top 10% is the share of the year's events among the riskiest tenth of loan-months.</p>
    ${tableHTML({
      columns: [{ key: "name", label: "Test year and model" }, { key: "events", label: "Events", r: 1, f: int }, { key: "pr_auc", label: "PR-AUC", r: 1, f: (v) => v.toFixed(3) },
        { key: "brier", label: "Brier", r: 1, f: (v) => v.toFixed(4) }, { key: "top10_capture", label: "Top 10%", r: 1, f: (v) => pct(v, 0) },
        { key: "cal_slope", label: "Calibration slope", r: 1, f: (v) => (v === null ? "" : v.toFixed(2)) }],
      rows,
    })}<figcaption class="fig-foot"><span class="src">Out of time and out of loan; ${int(rows.find((r) => r.model === "model").n)} or more loan-months a year. Source: project Gate 3 runs.</span></figcaption></figure>`;
}

// ------------------------------------------------------------------ precision-recall, latest year
{
  const y = Math.max(...s.model.years), c = s.model.pr[y];
  const m = s.model.metrics.find((r) => r.year === y && r.model === "model"), d = s.model.metrics.find((r) => r.year === y && r.model === "debt yield rank");
  const { chart, legend } = figure($("pr"), {
    q: `Does the model find distress better than debt yield? (${y} test year)`,
    take: `Among the loans each method flags first, the model's are far more often the ones that went into distress; past about half of all events the two converge on the ${pct(c.base_rate)} event rate (dotted). Area under the curve ${m.pr_auc.toFixed(3)} against ${d.pr_auc.toFixed(3)} for debt yield ranked low to high.`,
    src: "Precision: share of flagged loan-months that went into distress within 12 months. Recall: share of all distress events flagged.",
    table: () => ({ columns: [{ key: "r", label: "Recall", f: (v) => pct(v, 0) }, { key: "m", label: "Model precision", r: 1, f: (v) => pct(v) }],
      rows: c.model.recall.map((r, i) => ({ r, m: c.model.precision[i] })).filter((_, i) => i % 6 === 0) }),
  });
  legend.innerHTML = legendHTML([{ color: "var(--water)", label: "Distress model" }, { color: "var(--wall)", label: "Debt yield, ranked" }]);
  // the first few flagged loan-months make precision jump around near zero recall; start the curves at 1%
  const pts = (cv) => cv.recall.map((r, i) => [r, cv.precision[i]]).filter((p) => p[0] >= 0.01);
  const mp = pts(c.model), dp = pts(c.debt_yield_rank);
  lines(chart, [
    { label: "Debt yield, ranked", color: "var(--wall)", points: dp },
    { label: "Distress model", color: "var(--water)", points: mp },
  ], { xmax: 1, ymax: Math.min(1, Math.max(...mp.map((p) => p[1]), ...dp.map((p) => p[1])) * 1.1), xfmt: (v) => pct(v, 0), yfmt: (v) => pct(v, 0),
    xlabel: "Recall", ylabel: "Precision", hline: { y: c.base_rate, label: "event rate" }, aria: "Precision-recall curves" });
}

// ------------------------------------------------------------------ calibration
{
  const yrs = s.model.years;
  const host = document.createElement("div");
  host.className = "calib-grid";
  const intro = figure($("calib"), {
    q: "Do the probabilities mean what they say?",
    take: "Each dot is a tenth of the test year's loan-months: the model's average forecast against the share that went into distress. On the dashed line the forecasts are right. The 2022 dots sit above it (the model was calibrated on the COVID year and forecast too little distress); the ranking still held.",
    src: "Decile reliability, distress model, each test year.",
    table: () => ({ columns: [{ key: "y", label: "Year" }, { key: "f", label: "Forecast", r: 1, f: (v) => pct(v, 2) }, { key: "o", label: "Observed", r: 1, f: (v) => pct(v, 2) }],
      rows: yrs.flatMap((y) => s.model.calibration[y].forecast.map((f, i) => ({ y, f, o: s.model.calibration[y].observed[i] }))) }),
  });
  intro.chart.appendChild(host);
  host.style.cssText = "display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:24px";
  const top = Math.max(...yrs.flatMap((y) => [...s.model.calibration[y].forecast, ...s.model.calibration[y].observed])) * 1.05;
  yrs.forEach((y) => {
    const cell = document.createElement("div");
    cell.innerHTML = `<p class="label">${y}</p>`;
    const area = document.createElement("div");
    area.style.position = "relative";
    cell.appendChild(area);
    host.appendChild(cell);
    const c = s.model.calibration[y];
    lines(area, [{ label: String(y), color: "var(--water)", dots: true, points: c.forecast.map((f, i) => [f, c.observed[i]]) }],
      { xmax: top, ymax: top, diagonal: true, xfmt: (v) => pct(v, 0), yfmt: (v) => pct(v, 0), height: 220, aria: `Calibration, ${y}`,
        tip: (ser, p) => `<b>${y}</b><br>Forecast ${pct(p[0], 2)}<br>Observed ${pct(p[1], 2)}` });
  });
}

// ------------------------------------------------------------------ maturity finding
{
  const m = s.maturity, off = m.by_type.find((r) => r.type === "office");
  $("mat-gap").textContent = `Loans with a positive gap 12 months before maturity failed ${pct(m.gap_positive.failed_share, 0)} of the time (${int(m.gap_positive.loans)} loans) against ${pct(m.gap_zero.failed_share, 0)} without one (${int(m.gap_zero.loans)}), and office failed ${pct(off.failed_share, 0)} of the time. Gaps can't be computed for ${pct(m.gap_missing_share, 0)} of loans a year from maturity, mostly where no cap-rate benchmark or NOI exists.`;
}

// ------------------------------------------------------------------ scenarios
$("scen-table").innerHTML = `<h3>Scenarios</h3>${tableHTML({
  columns: [{ key: "label", label: "Scenario" }, { key: "notes", label: "Definition" }],
  rows: scen.scenarios.map((x) => ({ label: x.label, notes: x.notes })),
})}`;

// ------------------------------------------------------------------ parameters
{
  const rows = scen.parameters.filter((p) => p.parameter !== "tier");
  const appliesTo = (p) => {
    const g = p.property_group ?? p.jurisdiction ?? "all";
    if (g === "all") return "all types";
    const t = typeLabel(g);
    return escapeHTML(t !== "Type not reported" ? t : g.replace(/_/g, " "));
  };
  const cite = (srcs) => srcs.map((c) => (c.url ? `<a href="${escapeHTML(c.url)}">${escapeHTML(c.publisher || c.row)}${c.date ? `, ${escapeHTML(c.date)}` : ""}</a>`
    : escapeHTML(c.row))).join("; ");
  $("params").innerHTML = `<div class="table-wrap"><table class="data params"><thead><tr><th scope="col">Parameter</th><th scope="col">Applies to</th>
    <th scope="col" class="r">Value</th><th scope="col">How chosen and source</th></tr></thead><tbody>${rows.map((p) => `<tr>
    <th scope="row">${escapeHTML(((p.file === "la_overrides.csv" ? `${p.rule} ` : "") + p.parameter).replace(/_/g, " "))}</th><td>${appliesTo(p)}</td>
    <td class="r v">${escapeHTML(p.value)} <span class="s">${escapeHTML((p.unit || "").replace(/_/g, " "))}</span></td>
    <td>${escapeHTML(p.file === "la_overrides.csv" ? "" : p.rule || "")}${p.notes ? `${p.file === "la_overrides.csv" ? "" : ": "}${escapeHTML(p.notes)}` : ""}<span class="s">${cite(p.sources)}; checked ${escapeHTML(p.checked)}</span></td></tr>`).join("")}
    </tbody><caption>Underwriting and Los Angeles parameters. Lender sizing terms (LTV, DSCR, debt yield floors, amortization, spread premiums) follow the same rule and are listed under sources.</caption></table></div>`;
}

// ------------------------------------------------------------------ sources
$("src-list").innerHTML = src.groups.map((g) => `<details class="src-group"${g.file === null ? " open" : ""}><summary>${escapeHTML(g.group)} <span>${int(g.items.length)} documents</span></summary>
  <ol>${g.items.map((i) => `<li><a href="${escapeHTML(i.url)}">${escapeHTML(i.title || i.url)}</a> <span class="m">${escapeHTML(i.publisher || "")}${i.date ? `, ${escapeHTML(i.date)}` : ""}${i.rows ? `; ${i.rows} figure${i.rows > 1 ? "s" : ""} used` : ""}</span></li>`).join("")}</ol></details>`).join("");
