// Charts: thin marks, labeled axes, hairline grid, a hover and focus tooltip on every mark, and a table view.
import { axisBottom, axisLeft, max, scaleBand, scaleLinear, select, line as d3line } from "d3";
import "d3-transition";
import { escapeHTML } from "./format.js";

const prefersReduced = () => window.matchMedia("(prefers-reduced-motion: reduce)").matches;

// ------------------------------------------------------------------ figure shell

/** Builds <figure> with question, takeaway, chart area, source line and a table toggle. Returns the chart div. */
export function figure(host, { q, take, src, table }) {
  const fig = document.createElement("figure");
  fig.className = "fig";
  fig.innerHTML = `${q ? `<p class="fig-q">${q}</p>` : ""}${take ? `<p class="fig-take">${take}</p>` : ""}
    <div class="fig-legend"></div><div class="fig-chart"></div>
    <div class="fig-table" hidden></div>
    <figcaption class="fig-foot"><span class="src">${src || ""}</span>
    ${table ? '<button type="button" class="toggle" aria-expanded="false">Show table</button>' : ""}</figcaption>`;
  host.appendChild(fig);
  if (table) {
    const btn = fig.querySelector(".toggle"), box = fig.querySelector(".fig-table");
    btn.addEventListener("click", () => {
      const open = box.hidden;
      if (open && !box.dataset.done) { box.innerHTML = tableHTML(table()); box.dataset.done = "1"; }
      box.hidden = !open;
      btn.setAttribute("aria-expanded", String(open));
      btn.textContent = open ? "Hide table" : "Show table";
    });
  }
  return { chart: fig.querySelector(".fig-chart"), legend: fig.querySelector(".fig-legend"), fig };
}

export function tableHTML({ columns, rows, caption }) {
  const head = columns.map((c) => `<th${c.r ? ' class="r"' : ""} scope="col">${c.label}</th>`).join("");
  const body = rows.map((r) => `<tr>${columns.map((c, i) =>
    `${i === 0 ? '<th scope="row"' : "<td"}${c.r ? ' class="r"' : ""}>${escapeHTML(c.f ? c.f(r[c.key], r) : r[c.key])}${i === 0 ? "</th>" : "</td>"}`).join("")}</tr>`).join("");
  return `<div class="table-wrap" tabindex="0" role="region" aria-label="${escapeHTML(columns.map((c) => c.label).filter(Boolean).slice(0, 3).join(", ") || "Table")}"><table class="data">${caption ? `<caption>${caption}</caption>` : ""}<thead><tr>${head}</tr></thead><tbody>${body}</tbody></table></div>`;
}

export function legendHTML(items) {
  return `<ul class="legend">${items.map((i) =>
    `<li><span class="sw" style="background:${i.color}${i.outline ? ";outline:1px solid var(--wall)" : ""}"></span>${i.label}</li>`).join("")}</ul>`;
}

// ------------------------------------------------------------------ tooltip

function tooltip(container) {
  let tip = container.querySelector(":scope > .tip");
  if (!tip) {
    tip = document.createElement("div");
    tip.className = "tip";
    tip.setAttribute("role", "status");
    container.appendChild(tip);
  }
  return {
    show(html, x, y) {
      tip.innerHTML = html;
      const w = container.clientWidth;
      tip.classList.add("on");
      const tw = tip.offsetWidth;
      tip.style.left = `${Math.max(0, Math.min(x + 12, w - tw))}px`;
      tip.style.top = `${Math.max(0, y - tip.offsetHeight - 10)}px`;
    },
    hide() { tip.classList.remove("on"); },
  };
}

// marks get a hover tooltip; keyboard and screen-reader users read the same numbers in the table view
function bindTip(sel, tip, html, container) {
  sel.on("mousemove", (e, d) => {
    const r = container.getBoundingClientRect();
    tip.show(html(d), e.clientX - r.left, e.clientY - r.top);
  }).on("mouseleave", () => tip.hide());
}

function responsive(container, draw) {
  let w = 0;
  const run = () => {
    const nw = Math.round(container.clientWidth);
    if (nw && nw !== w) { w = nw; draw(w); }
  };
  new ResizeObserver(run).observe(container);
  run();
}

// ------------------------------------------------------------------ stacked columns (the wall)

/**
 * series: [{key, label, color, values: [...per bucket]}] stacked bottom to top.
 * opts: {buckets, labels (x tick text), height, fmt, tipTitle(i), animate, onClick(i)}
 */
export function stackedColumns(container, series, opts) {
  const tip = tooltip(container);
  const { buckets, fmt, height = 340 } = opts;
  let first = opts.animate && !prefersReduced();
  responsive(container, (width) => {
    select(container).select("svg").remove();
    const m = { t: 16, r: 8, b: 30, l: 56 };
    const W = width, H = width < 520 ? Math.min(height, 260) : height;
    const svg = select(container).insert("svg", ":first-child").attr("width", W).attr("height", H)
      .attr("role", "img").attr("aria-label", opts.aria || "Stacked column chart");
    const totals = buckets.map((_, i) => series.reduce((a, s) => a + (s.values[i] || 0), 0));
    const x = scaleBand().domain(buckets.map(String)).range([m.l, W - m.r]).paddingInner(0.18).paddingOuter(0.05);
    const y = scaleLinear().domain([0, max(totals) * 1.08]).nice().range([H - m.b, m.t]);
    svg.append("g").attr("class", "gridline").attr("transform", `translate(${m.l},0)`)
      .call(axisLeft(y).ticks(5).tickSize(-(W - m.l - m.r)).tickFormat(""));
    svg.append("g").attr("class", "axis").attr("transform", `translate(${m.l},0)`)
      .call(axisLeft(y).ticks(5).tickFormat(fmt).tickSizeOuter(0));
    const labels = opts.labels || buckets;
    const xa = svg.append("g").attr("class", "axis").attr("transform", `translate(0,${H - m.b})`)
      .call(axisBottom(x).tickSizeOuter(0).tickFormat((d, i) => (W < 520 && i % 2 && i !== 0 ? "" : labels[i])));
    xa.selectAll("line").remove();
    const segs = [];
    buckets.forEach((b, i) => {
      let y0 = 0;
      series.forEach((s) => {
        const v = s.values[i] || 0;
        if (v > 0) segs.push({ i, b, s, v, y0, y1: y0 + v });
        y0 += v;
      });
    });
    const g = svg.append("g");
    const rects = g.selectAll("rect").data(segs).join("rect")
      .attr("x", (d) => x(String(d.b))).attr("width", x.bandwidth())
      .attr("fill", (d) => d.s.color)
      .attr("y", (d) => y(d.y1)).attr("height", (d) => Math.max(0, y(d.y0) - y(d.y1) - (d.y1 < totals[d.i] ? 1.5 : 0)));
    if (first) {
      const finalY = (d) => y(d.y1), finalH = (d) => Math.max(0, y(d.y0) - y(d.y1) - (d.y1 < totals[d.i] ? 1.5 : 0));
      rects.attr("y", (d) => y(d.y0)).attr("height", 0)
        .transition().delay((d) => d.i * 40 + (d.s.key === "gap" ? 260 : 0)).duration(280)
        .attr("y", finalY).attr("height", finalH);
      first = false;
    }
    bindTip(rects, tip, (d) => opts.tip(d.i, d.s), container);
    if (opts.onClick) rects.style("cursor", "pointer").on("click", (e, d) => opts.onClick(d.i));
    if (opts.annotate) opts.annotate(svg, { x, y, totals, m, W, H });
  });
}

// ------------------------------------------------------------------ horizontal bars

/** rows: [{label, value, color, note}] ; opts: {fmt, max, height per row} */
export function hbars(container, rows, opts = {}) {
  const tip = tooltip(container);
  responsive(container, (width) => {
    select(container).select("svg").remove();
    const rowH = 30, m = { t: 4, r: 64, b: 24, l: Math.min(140, width * 0.34) };
    const H = m.t + m.b + rows.length * rowH;
    const svg = select(container).insert("svg", ":first-child").attr("width", width).attr("height", H)
      .attr("role", "img").attr("aria-label", opts.aria || "Bar chart");
    const x = scaleLinear().domain([0, opts.max ?? max(rows, (r) => r.value)]).nice().range([m.l, width - m.r]);
    const y = scaleBand().domain(rows.map((r) => r.label)).range([m.t, H - m.b]).paddingInner(0.32);
    svg.append("g").attr("class", "gridline").attr("transform", `translate(0,${H - m.b})`)
      .call(axisBottom(x).ticks(4).tickSize(-(H - m.t - m.b)).tickFormat(""));
    svg.append("g").attr("class", "axis").attr("transform", `translate(0,${H - m.b})`)
      .call(axisBottom(x).ticks(4).tickFormat(opts.fmt).tickSizeOuter(0));
    svg.append("g").selectAll("text").data(rows).join("text").attr("class", "dlabel")
      .attr("x", m.l - 8).attr("y", (r) => y(r.label) + y.bandwidth() / 2).attr("dy", "0.35em")
      .attr("text-anchor", "end").text((r) => r.label);
    const bars = svg.append("g").selectAll("rect").data(rows).join("rect")
      .attr("x", m.l).attr("y", (r) => y(r.label)).attr("height", y.bandwidth())
      .attr("width", (r) => Math.max(0, x(r.value) - m.l)).attr("fill", (r) => r.color || "var(--water)");
    svg.append("g").selectAll("text").data(rows).join("text").attr("class", "dlabel")
      .attr("x", (r) => x(r.value) + 6).attr("y", (r) => y(r.label) + y.bandwidth() / 2).attr("dy", "0.35em")
      .text((r) => opts.fmt(r.value));
    bindTip(bars, tip, (r) => opts.tip ? opts.tip(r) : `<b>${r.label}</b><br>${opts.fmt(r.value)}`, container);
  });
}

// ------------------------------------------------------------------ lines (calibration, precision-recall)

/** series: [{label, color, points: [[x,y],...], dash, dots}] ; opts: {xfmt, yfmt, xmax, ymax, xlabel, ylabel, diagonal} */
export function lines(container, series, opts = {}) {
  const tip = tooltip(container);
  responsive(container, (width) => {
    select(container).select("svg").remove();
    const m = { t: 12, r: 12, b: 40, l: 52 };
    const H = opts.height || Math.min(320, Math.max(220, width * 0.62));
    const svg = select(container).insert("svg", ":first-child").attr("width", width).attr("height", H)
      .attr("role", "img").attr("aria-label", opts.aria || "Line chart");
    const allX = series.flatMap((s) => s.points.map((p) => p[0])), allY = series.flatMap((s) => s.points.map((p) => p[1]));
    const x = scaleLinear().domain([opts.xmin ?? 0, opts.xmax ?? max(allX)]).range([m.l, width - m.r]);
    if (opts.xmin === undefined) x.nice();
    const y = scaleLinear().domain([opts.ymin ?? 0, opts.ymax ?? max(allY)]).nice().range([H - m.b, m.t]);
    svg.append("g").attr("class", "gridline").attr("transform", `translate(${m.l},0)`)
      .call(axisLeft(y).ticks(5).tickSize(-(width - m.l - m.r)).tickFormat(""));
    svg.append("g").attr("class", "axis").attr("transform", `translate(${m.l},0)`).call(axisLeft(y).ticks(5).tickFormat(opts.yfmt).tickSizeOuter(0));
    svg.append("g").attr("class", "axis").attr("transform", `translate(0,${H - m.b})`).call(axisBottom(x).ticks(opts.xticks || 5).tickFormat(opts.xfmt).tickSizeOuter(0));
    if (opts.xlabel) svg.append("text").attr("class", "dlabel").attr("x", width - m.r).attr("y", H - 4).attr("text-anchor", "end").text(opts.xlabel);
    if (opts.ylabel) svg.append("text").attr("class", "dlabel").attr("x", m.l).attr("y", m.t - 2).text(opts.ylabel);
    if (opts.diagonal) {
      const d = Math.min(x.domain()[1], y.domain()[1]);
      svg.append("line").attr("x1", x(0)).attr("y1", y(0)).attr("x2", x(d)).attr("y2", y(d))
        .attr("stroke", "var(--wall)").attr("stroke-dasharray", "4 4").attr("stroke-width", 1);
    }
    if (opts.hline !== undefined) {
      svg.append("line").attr("x1", m.l).attr("x2", width - m.r).attr("y1", y(opts.hline.y)).attr("y2", y(opts.hline.y))
        .attr("stroke", "var(--wall)").attr("stroke-dasharray", "2 3");
      svg.append("text").attr("class", "dlabel").attr("x", width - m.r).attr("y", y(opts.hline.y) - 4).attr("text-anchor", "end").text(opts.hline.label);
    }
    const ln = d3line().defined((p) => p[1] !== null && p[1] !== undefined && !Number.isNaN(p[1])).x((p) => x(p[0])).y((p) => y(p[1]));
    series.forEach((s) => {
      svg.append("path").attr("d", ln(s.points)).attr("fill", "none").attr("stroke", s.color).attr("stroke-width", 2)
        .attr("stroke-dasharray", s.dash || null);
      if (s.dots) {
        const dots = svg.append("g").selectAll("circle").data(s.points).join("circle")
          .attr("cx", (p) => x(p[0])).attr("cy", (p) => y(p[1])).attr("r", 4.5).attr("fill", s.color)
          .attr("stroke", "var(--paper)").attr("stroke-width", 2);
        bindTip(dots, tip, (p) => opts.tip ? opts.tip(s, p) : `<b>${s.label}</b><br>${opts.xfmt(p[0])}, ${opts.yfmt(p[1])}`, container);
      }
    });
  });
}

// ------------------------------------------------------------------ columns (histogram)

export function columns(container, rows, opts = {}) {
  const tip = tooltip(container);
  responsive(container, (width) => {
    select(container).select("svg").remove();
    const m = { t: 16, r: 8, b: 44, l: 48 };
    const H = opts.height || 260;
    const svg = select(container).insert("svg", ":first-child").attr("width", width).attr("height", H)
      .attr("role", "img").attr("aria-label", opts.aria || "Column chart");
    const x = scaleBand().domain(rows.map((r) => r.label)).range([m.l, width - m.r]).paddingInner(0.2);
    const y = scaleLinear().domain([0, max(rows, (r) => r.value) * 1.1]).nice().range([H - m.b, m.t]);
    svg.append("g").attr("class", "gridline").attr("transform", `translate(${m.l},0)`)
      .call(axisLeft(y).ticks(4).tickSize(-(width - m.l - m.r)).tickFormat(""));
    svg.append("g").attr("class", "axis").attr("transform", `translate(${m.l},0)`).call(axisLeft(y).ticks(4).tickFormat(opts.yfmt).tickSizeOuter(0));
    const xa = svg.append("g").attr("class", "axis").attr("transform", `translate(0,${H - m.b})`).call(axisBottom(x).tickSizeOuter(0));
    xa.selectAll("line").remove();
    if (width < 560) xa.selectAll("text").attr("transform", "rotate(-35)").attr("text-anchor", "end").attr("dx", "-0.4em").attr("dy", "0.6em");
    const bars = svg.append("g").selectAll("rect").data(rows).join("rect")
      .attr("x", (r) => x(r.label)).attr("width", x.bandwidth()).attr("y", (r) => y(r.value))
      .attr("height", (r) => y(0) - y(r.value)).attr("fill", (r) => r.color || "var(--water)");
    bindTip(bars, tip, (r) => opts.tip ? opts.tip(r) : `<b>${r.label}</b><br>${opts.yfmt(r.value)}`, container);
  });
}
