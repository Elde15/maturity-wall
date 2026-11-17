import { getLoans, stampMeta } from "../lib/data.js";
import { escapeHTML, int, money, pct, shortTrust, statusHTML, STATUS, TYPE_ORDER, typeColor, typeLabel } from "../lib/format.js";
import { loanMap } from "../lib/map.js";
import { BANDS, bander } from "../lib/risk.js";

stampMeta();
const { loans } = await getLoans();
const band = bander(loans);
for (const l of loans) {
  l.band = band(l);
  l.risk = l.band * 10 + (l.pf ?? (l.pd ?? 0) * 5);
  l.year = l.mat ? Number(l.mat.slice(0, 4)) : null;
  l.hay = `${l.name || ""} ${l.city || ""} ${l.state || ""} ${l.trust || ""}`.toLowerCase();
}

// ------------------------------------------------------------------ filters
const form = document.getElementById("filters");
const opt = (sel, items) => { form.elements[sel].insertAdjacentHTML("beforeend", items.map(([v, t]) => `<option value="${escapeHTML(v)}">${escapeHTML(t)}</option>`).join("")); };
opt("type", TYPE_ORDER.filter((t) => loans.some((l) => l.type === t)).map((t) => [t, typeLabel(t)]));
opt("state", [...new Set(loans.map((l) => l.state).filter(Boolean))].sort().map((s) => [s, s]));
opt("status", Object.keys(STATUS).filter((s) => loans.some((l) => l.status === s)).map((s) => [s, STATUS[s][1]]));
const years = [...new Set(loans.map((l) => l.year).filter(Boolean))].sort();
opt("mat", years.filter((y) => y >= 2026 && y <= 2036).map((y) => [y, String(y)]).concat([["past", "Past maturity"]]));
opt("band", BANDS.slice().reverse().map((b) => [b.k, b.label]));

const params = new URLSearchParams(location.search);
for (const [k, v] of params) if (form.elements[k]) form.elements[k].type === "checkbox" ? (form.elements[k].checked = v === "1") : (form.elements[k].value = v);

const state = { sort: "opp", dir: -1, shown: 50 };
function current() {
  const f = Object.fromEntries(new FormData(form));
  const q = (f.q || "").trim().toLowerCase();
  return loans.filter((l) => (!q || l.hay.includes(q))
    && (!f.type || l.type === f.type) && (!f.state || l.state === f.state) && (!f.status || l.status === f.status)
    && (!f.mat || (f.mat === "past" ? l.year && l.year < 2026 || l.status === "matured, not repaid" : l.year === Number(f.mat)))
    && (f.band === "" || f.band === undefined || l.band === Number(f.band))
    && (!f.bal || (l.bal ?? 0) >= Number(f.bal)) && (!f.gap || (l.gap_pct ?? 0) > 0));
}

// ------------------------------------------------------------------ map
document.getElementById("map-legend").innerHTML = BANDS.slice().reverse().map((b) =>
  `<li><span class="sw" style="background:${b.color};border-radius:50%"></span>${b.label}</li>`).join("");
document.getElementById("band-rule").textContent = `Risk bands: ${band.rule}`;
const r = (p) => Math.max(1.6, Math.min(14, Math.sqrt((p.bal || 0) / 4e6)));
const map = await loanMap(document.getElementById("map"), {
  color: (p) => BANDS[p.band].color, radius: r, zorder: (p) => p.band * 1e12 - (p.bal || 0),
  aria: "Map of scored loans, dot size by balance, shade by risk band. The table below lists the same loans.",
  tip: (p) => `<b>${escapeHTML(p.name || "Unnamed property")}</b><br>${escapeHTML(p.city || "")}, ${p.state || ""}<br>
    ${typeLabel(p.type)}, ${money(p.bal)}<br>${BANDS[p.band].label}${p.pf !== null ? `, failure ${pct(p.pf, 0)}` : p.pd !== null ? `, 12-month distress ${pct(p.pd)}` : ""}`,
  onClick: (p) => { location.href = `/loan.html?id=${p.id}`; },
});

// ------------------------------------------------------------------ table
const tbody = document.querySelector("#tbl tbody");
const cmp = (k, dir) => (a, b) => {
  const x = a[k], y = b[k];
  if (x === null || x === undefined) return 1;
  if (y === null || y === undefined) return -1;
  return (x < y ? -1 : x > y ? 1 : 0) * dir;
};
function row(l) {
  const prob = l.band === 4 ? "In distress" : l.pf !== null ? `${pct(l.pf, 0)}<span class="tag">F</span>` : l.pd !== null ? `${pct(l.pd)}<span class="tag">D</span>` : "n/a";
  return `<tr>
    <td><a href="/loan.html?id=${l.id}">${escapeHTML(l.name || "Unnamed property")}</a><span class="sub">${escapeHTML(l.city || "")}${l.state ? `, ${l.state}` : ""} &middot; ${escapeHTML(shortTrust(l.trust))}</span></td>
    <td><span class="chip"><i style="background:${typeColor(l.type)}"></i>${typeLabel(l.type)}</span></td>
    <td>${statusHTML(l.status)}</td>
    <td class="r">${money(l.bal)}</td>
    <td class="r">${l.mat ? l.mat.slice(0, 7) : "n/a"}</td>
    <td class="r">${prob}</td>
    <td class="r">${l.gap_pct === null ? "n/a" : pct(l.gap_pct, 0)}</td>
    <td class="r">${l.disc === null ? "n/a" : pct(l.disc, 0)}</td>
    <td class="r">${l.opp === null ? "n/a" : l.opp.toFixed(0)}</td></tr>`;
}
let rows = [];
function render() {
  const sel = current();
  rows = sel.slice().sort(cmp(state.sort, state.dir));
  tbody.innerHTML = rows.slice(0, state.shown).map(row).join("");
  document.getElementById("more").hidden = rows.length <= state.shown;
  const bal = sel.reduce((a, l) => a + (l.bal || 0), 0), gap = sel.reduce((a, l) => a + (l.gap || 0), 0);
  const ng = sel.filter((l) => (l.gap_pct ?? 0) > 0).length;
  document.getElementById("count").innerHTML = `<b>${int(sel.length)}</b> loans, <b>${money(bal)}</b> balance. Refinance gap <b>${money(gap)}</b> across ${int(ng)} loans (base scenario).`;
  map.update(sel);
  const qs = new URLSearchParams([...new FormData(form)].filter(([, v]) => v !== "" && v !== "on").concat(form.elements.gap.checked ? [["gap", "1"]] : []));
  history.replaceState(null, "", qs.toString() ? `?${qs}` : location.pathname);
}
document.querySelectorAll("#tbl th[data-k]").forEach((th) => {
  th.querySelector("button").addEventListener("click", () => {
    const k = th.dataset.k;
    state.dir = state.sort === k ? -state.dir : (k === "name" || k === "type" || k === "status" || k === "mat" ? 1 : -1);
    state.sort = k;
    document.querySelectorAll("#tbl th[data-k]").forEach((t) => t.removeAttribute("aria-sort"));
    th.setAttribute("aria-sort", state.dir > 0 ? "ascending" : "descending");
    state.shown = 50;
    render();
  });
});
document.getElementById("more").addEventListener("click", () => { state.shown += 50; render(); });
let timer;
form.addEventListener("input", () => { clearTimeout(timer); timer = setTimeout(() => { state.shown = 50; render(); }, 120); });
form.addEventListener("submit", (e) => e.preventDefault());
render();
