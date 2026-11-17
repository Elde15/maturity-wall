// Loan map on canvas (13,000 points stay fast): states or counties from us-atlas (pre-projected Albers USA,
// 975 x 610), loans projected with the same projection. Hover shows a tooltip; click opens the tear sheet.
import { geoAlbersUsa, geoPath, quadtree } from "d3";
import { feature, mesh } from "topojson-client";
import statesUrl from "us-atlas/states-albers-10m.json?url";
import countiesUrl from "us-atlas/counties-albers-10m.json?url";

const proj = geoAlbersUsa().scale(1300).translate([487.5, 305]);
const atlasCache = {};
async function atlas(kind) {
  if (!atlasCache[kind]) atlasCache[kind] = fetch(kind === "counties" ? countiesUrl : statesUrl).then((r) => r.json());
  return atlasCache[kind];
}

export const project = (lon, lat) => (lon === null || lat === null ? null : proj([lon, lat]));

/**
 * opts: {color(p), radius(p), tip(p) -> html, onClick(p), kind: "states"|"counties", focus: [[x0,y0],[x1,y1]] in
 * atlas units, countyFilter: (id) => bool, aria}
 */
export async function loanMap(container, opts) {
  const topo = await atlas(opts.kind || "states");
  const land = feature(topo, topo.objects.nation || topo.objects.states);
  const borders = mesh(topo, topo.objects.states, (a, b) => a !== b);
  const counties = opts.kind === "counties" ? mesh(topo, topo.objects.counties, (a, b) => a !== b && (!opts.countyFilter || opts.countyFilter(a.id) || opts.countyFilter(b.id))) : null;
  const focusLand = opts.countyFilter ? feature(topo, topo.objects.counties).features.filter((f) => opts.countyFilter(f.id)) : null;

  const canvas = document.createElement("canvas");
  canvas.setAttribute("role", "img");
  canvas.setAttribute("aria-label", opts.aria || "Map of loans");
  canvas.style.display = "block";
  canvas.style.width = "100%";
  canvas.tabIndex = -1;
  container.appendChild(canvas);
  const tip = document.createElement("div");
  tip.className = "tip";
  container.appendChild(tip);

  let points = [], placed = [], tree = null, k = 1, ox = 0, oy = 0, W = 0, H = 0;
  const [[fx0, fy0], [fx1, fy1]] = opts.focus || [[0, 0], [975, 610]];

  function draw() {
    W = container.clientWidth;
    k = W / (fx1 - fx0);
    H = Math.round((fy1 - fy0) * k);
    ox = -fx0 * k; oy = -fy0 * k;
    const dpr = window.devicePixelRatio || 1;
    canvas.width = Math.round(W * dpr); canvas.height = Math.round(H * dpr);
    canvas.style.height = `${H}px`;
    const ctx = canvas.getContext("2d");
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, W, H);
    ctx.save();
    ctx.translate(ox, oy); ctx.scale(k, k);
    const path = geoPath(null, ctx);
    ctx.fillStyle = "#e8eae5"; ctx.beginPath(); path(land); ctx.fill();
    if (focusLand) { ctx.fillStyle = "#dfe2dc"; focusLand.forEach((f) => { ctx.beginPath(); path(f); ctx.fill(); }); }
    ctx.lineWidth = 0.8 / k;
    if (counties) { ctx.strokeStyle = "#cdd1cb"; ctx.beginPath(); path(counties); ctx.stroke(); }
    ctx.strokeStyle = "#b9bdb7"; ctx.lineWidth = 1 / k; ctx.beginPath(); path(borders); ctx.stroke();
    ctx.restore();
    placed = [];
    // draw larger, lower-risk points first so small, risky ones stay on top
    const order = points.slice().sort((a, b) => (opts.zorder ? opts.zorder(a) - opts.zorder(b) : 0));
    for (const p of order) {
      const xy = p._xy;
      if (!xy) continue;
      const x = xy[0] * k + ox, y = xy[1] * k + oy;
      if (x < -10 || y < -10 || x > W + 10 || y > H + 10) continue;
      const r = opts.radius(p);
      ctx.beginPath(); ctx.arc(x, y, r, 0, 2 * Math.PI);
      ctx.fillStyle = opts.color(p); ctx.globalAlpha = 0.85; ctx.fill();
      ctx.globalAlpha = 1; ctx.lineWidth = 0.75; ctx.strokeStyle = "#f4f5f2"; ctx.stroke();
      placed.push({ x, y, r, p });
    }
    tree = quadtree().x((d) => d.x).y((d) => d.y).addAll(placed);
  }

  function nearest(ev) {
    const b = canvas.getBoundingClientRect();
    const x = ev.clientX - b.left, y = ev.clientY - b.top;
    const hit = tree && tree.find(x, y, 12);
    return hit ? { hit, x, y } : null;
  }
  canvas.addEventListener("mousemove", (ev) => {
    const n = nearest(ev);
    canvas.style.cursor = n ? "pointer" : "default";
    if (!n) { tip.classList.remove("on"); return; }
    tip.innerHTML = opts.tip(n.hit.p);
    tip.classList.add("on");
    const tw = tip.offsetWidth;
    tip.style.left = `${Math.min(n.x + 14, W - tw)}px`;
    tip.style.top = `${Math.max(0, n.y - tip.offsetHeight - 12)}px`;
  });
  canvas.addEventListener("mouseleave", () => tip.classList.remove("on"));
  canvas.addEventListener("click", (ev) => { const n = nearest(ev); if (n && opts.onClick) opts.onClick(n.hit.p); });

  let w0 = 0;
  new ResizeObserver(() => { const w = container.clientWidth; if (w && w !== w0) { w0 = w; draw(); } }).observe(container);

  return {
    update(ps) {
      points = ps;
      for (const p of points) if (p._xy === undefined) p._xy = project(p.lon, p.lat);
      if (container.clientWidth) draw();
    },
  };
}
