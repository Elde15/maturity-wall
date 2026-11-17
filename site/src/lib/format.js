// Number and label formatting. Units are always stated; probabilities are percentages.
export const TYPE_LABEL = {
  office: "Office", retail: "Retail", multifamily: "Multifamily", lodging: "Lodging", industrial: "Industrial",
  self_storage: "Self-storage", mixed_use: "Mixed use", other: "Other", mixed_other: "Mixed use and other",
  "not reported": "Type not reported",
};
export const TYPE_ORDER = ["office", "retail", "multifamily", "lodging", "industrial", "self_storage", "mixed_use", "other"];
export const typeColor = (t) => `var(--t-${!t || t === "not reported" ? "none" : t === "mixed_other" ? "mixed_use" : t})`;
export const typeLabel = (t) => TYPE_LABEL[t] || "Type not reported";

const bad = (v) => v === null || v === undefined || Number.isNaN(v);

export function money(v, { digits } = {}) {
  if (bad(v)) return "n/a";
  const a = Math.abs(v), s = v < 0 ? "-" : "";
  if (a >= 1e9) return `${s}$${(a / 1e9).toFixed(digits ?? 1)}B`;
  if (a >= 1e6) return `${s}$${(a / 1e6).toFixed(digits ?? 1)}M`;
  if (a >= 1e3) return `${s}$${(a / 1e3).toFixed(digits ?? 0)}K`;
  return `${s}$${a.toFixed(0)}`;
}
export const dollars = (v) => (bad(v) ? "n/a"
  : `${v < 0 ? "-" : ""}$${Math.abs(v).toLocaleString("en-US", { maximumFractionDigits: 0 })}`);
export const pct = (v, digits = 1) => (bad(v) ? "n/a" : `${(v * 100).toFixed(digits)}%`);
export const bp = (v) => `${v > 0 ? "+" : ""}${v} bp`;
export const ratio = (v, digits = 2) => (bad(v) ? "n/a" : `${v.toFixed(digits)}x`);
export const int = (v) => (bad(v) ? "n/a" : Number(v).toLocaleString("en-US"));

export function monthYear(iso) {
  if (!iso) return "n/a";
  const [y, m] = iso.split("-").map(Number);
  return new Date(Date.UTC(y, m - 1, 1)).toLocaleDateString("en-US", { month: "short", year: "numeric", timeZone: "UTC" });
}

const GLYPH = {
  critical: '<svg viewBox="0 0 12 12" aria-hidden="true"><path d="M6 1 11 10H1z" fill="currentColor"/></svg>',
  warning: '<svg viewBox="0 0 12 12" aria-hidden="true"><rect x="2" y="2" width="8" height="8" fill="none" stroke="currentColor" stroke-width="1.6"/></svg>',
  neutral: '<svg viewBox="0 0 12 12" aria-hidden="true"><circle cx="6" cy="6" r="3" fill="currentColor"/></svg>',
};
export const STATUS = {
  "matured, not repaid": ["critical", "Matured, not repaid"],
  "special servicing": ["critical", "Special servicing"],
  "delinquent 30+": ["warning", "30+ days delinquent"],
  "past maturity, paying": ["warning", "Past maturity, paying"],
  performing: ["neutral", "Performing"],
  other: ["neutral", "Status not reported"],
};
export function statusHTML(s) {
  const [cls, label] = STATUS[s] || ["neutral", s || "n/a"];
  return `<span class="status ${cls}">${GLYPH[cls]}${label}</span>`;
}
export const escapeHTML = (s) => String(s ?? "").replace(/[&<>"']/g,
  (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

// "BANK 2017-BNK4 Mortgage Trust" style names are long; drop the generic suffix
export const shortTrust = (s) => String(s || "").replace(/\s+(Commercial\s+)?Mortgage\s+(Securities\s+)?Trust.*$/i, "")
  .replace(/\s+Mortgage Securities Corp.*$/i, "").trim();
