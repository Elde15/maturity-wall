import { readFileSync } from "node:fs";
import { makeParams, underwrite } from "../src/lib/engine.js";
const scen = JSON.parse(readFileSync("public/data/scenarios.json", "utf-8"));
const uw = JSON.parse(readFileSync("public/data/uw.json", "utf-8")).loans;
const P = makeParams(scen), M = scen.market, S = P.scenarios.base;
const n = uw.whole_loan_id.length, keys = Object.keys(uw);
const L = Array.from({ length: n }, (_, i) => Object.fromEntries(keys.map((k) => [k, uw[k][i]])));
let t = performance.now(), gap = 0;
for (const l of L) { const u = underwrite(l, S, P, M); gap += u.refi_gap || 0; }
console.log(n, "loans", (performance.now() - t).toFixed(0), "ms first pass; gap", (gap / 1e9).toFixed(2));
t = performance.now();
for (const l of L) underwrite(l, S, P, M, { rateShiftBps: 100 });
console.log((performance.now() - t).toFixed(0), "ms second pass");
