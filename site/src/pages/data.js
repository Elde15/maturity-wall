import { tableHTML } from "../lib/charts.js";
import { getSummary, stampMeta } from "../lib/data.js";
import { int } from "../lib/format.js";

stampMeta();
const s = await getSummary();
document.getElementById("n-rows").textContent = int(s.headline.loans_scored);
const D = [
  ["id", "Loan id on this site: a stable hash of the whole loan (pari passu pieces share one id)"],
  ["name, city, state, county, cbsa", "Largest property's name and address as filed; county FIPS and metro (CBSA) from the Census geocoder"],
  ["type", "Property type group from the filing's property type code"],
  ["status", "Latest month: performing, 30+ days delinquent, special servicing, matured not repaid, past maturity paying, or not reported"],
  ["trust, vintage", "Trust holding the loan's representative piece, and its issue year"],
  ["bal", "Estimated whole-loan balance, dollars"],
  ["mat", "Maturity used by the models (anticipated repayment date where one exists)"],
  ["coupon", "Current interest rate, fraction"],
  ["pf, pf_lo, pf_hi", "Failure-to-refinance probability and 90% interval (loans 2.5 to 24 months from maturity)"],
  ["pd, pd_lo, pd_hi", "12-month distress probability and 90% interval (performing loans)"],
  ["dy, dscr, occ", "Debt yield (NOI over balance), reported DSCR, occupancy"],
  ["tier", "Underwriting confidence tier: A, B or C; blank if not underwritten"],
  ["gap, gap_pct", "Refinance gap in dollars and as a share of balance, base scenario"],
  ["value, vbid, rbid, bid, disc", "Model value, value bid, return bid, implied bid (lower of the two) and discount to balance, base scenario"],
  ["opp", "Opportunity score, 0 to 100"],
  ["lat, lon", "Geocoded property coordinates, three decimals"],
];
document.getElementById("dict").innerHTML = `<h3>Columns</h3>${tableHTML({
  columns: [{ key: "c", label: "Column" }, { key: "d", label: "Meaning" }], rows: D.map(([c, d]) => ({ c, d })) })}`;
