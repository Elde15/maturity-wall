// Fetch helpers: every data file is JSON with a meta block (schema version, build date, data cut-off).
const cache = new Map();

export function getJSON(path) {
  if (!cache.has(path)) {
    cache.set(path, fetch(path).then((r) => {
      if (!r.ok) throw new Error(`${path}: ${r.status}`);
      return r.json();
    }));
  }
  return cache.get(path);
}

export const getSummary = () => getJSON("/data/summary.json");
export const getMeta = () => getJSON("/data/meta.json");
export const getScenarios = () => getJSON("/data/scenarios.json");

// columnar {col: [...]} -> array of row objects
export function rows(cols) {
  const keys = Object.keys(cols);
  const n = cols[keys[0]].length;
  const out = new Array(n);
  for (let i = 0; i < n; i++) {
    const r = {};
    for (const k of keys) r[k] = cols[k][i];
    out[i] = r;
  }
  return out;
}

export async function getLoans() {
  const j = await getJSON("/data/loans.json");
  if (!j._rows) j._rows = rows(j.loans);
  return { meta: j.meta, loans: j._rows };
}

export async function getUW() {
  const j = await getJSON("/data/uw.json");
  if (!j._rows) j._rows = rows(j.loans);
  return { meta: j.meta, loans: j._rows };
}

export async function getHistory(id) {
  const j = await getJSON(`/data/history/${id.slice(2, 4)}.json`);
  return j.loans[id] || null;
}

export function longDate(iso) {
  const [y, m, d] = iso.split("-").map(Number);
  return new Date(Date.UTC(y, m - 1, d)).toLocaleDateString("en-US",
    { month: "long", day: "numeric", year: "numeric", timeZone: "UTC" });
}

// fill <span data-meta="key"> from meta.json (footer build facts)
export async function stampMeta() {
  try {
    const m = (await getMeta()).meta;
    document.querySelectorAll("[data-meta]").forEach((el) => {
      const k = el.dataset.meta, v = m[k];
      if (v) el.textContent = k.endsWith("date") || k === "data_cutoff" ? longDate(v) : v;
    });
  } catch { /* the footer keeps its fallback text */ }
}
