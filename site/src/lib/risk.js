// Risk bands for the map and tables: one ordinal blue ramp. A loan near maturity (2.5 to 24 months) is banded by
// its failure-to-refinance probability; any other performing loan by where its 12-month distress probability
// ranks among all scored loans. A loan already in distress is the top band.
export const DISTRESSED = new Set(["matured, not repaid", "special servicing", "delinquent 30+"]);
export const BANDS = [
  { k: 0, label: "Not scored", color: "#b9bec1" },
  { k: 1, label: "Lower", color: "#86b6ef" },
  { k: 2, label: "Elevated", color: "#3987e5" },
  { k: 3, label: "High", color: "#1c5cab" },
  { k: 4, label: "In distress now", color: "#0d366b" },
];

export function bander(loans) {
  const pd = loans.map((l) => l.pd).filter((v) => v !== null).sort((a, b) => a - b);
  const q = (p) => pd[Math.min(pd.length - 1, Math.floor(p * pd.length))];
  const q80 = q(0.8), q95 = q(0.95);
  const band = (l) => {
    if (DISTRESSED.has(l.status)) return 4;
    if (l.pf !== null && l.pf !== undefined) return l.pf >= 0.5 ? 3 : l.pf >= 0.25 ? 2 : 1;
    if (l.pd !== null && l.pd !== undefined) return l.pd >= q95 ? 3 : l.pd >= q80 ? 2 : 1;
    return 0;
  };
  band.rule = "In distress now: special servicing, 30+ days delinquent or past maturity unpaid. Within 24 months of maturity: "
    + "high at a failure probability of 50% or more, elevated at 25 to 50%. Otherwise by the 12-month distress probability: "
    + `high in the top 5% of loans (${(q95 * 100).toFixed(1)}% or more), elevated in the next 15% (${(q80 * 100).toFixed(1)}% or more).`;
  return band;
}
