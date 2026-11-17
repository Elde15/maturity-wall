// Runs the JavaScript engine on cases written by tests/test_site.py and writes the results.
// usage: node site/scripts/parity.mjs cases.json scenarios.json out.json
import { readFileSync, writeFileSync } from "node:fs";
import { makeParams, underwrite } from "../src/lib/engine.js";

const [casesPath, scenPath, outPath] = process.argv.slice(2);
const cases = JSON.parse(readFileSync(casesPath, "utf-8"));
const scen = JSON.parse(readFileSync(scenPath, "utf-8"));
const P = makeParams(scen);
const M = scen.market;
const clean = (o) => JSON.parse(JSON.stringify(o, (k, v) => (typeof v === "number" && !Number.isFinite(v) ? null : v)));
const out = cases.map((c) => clean(underwrite(c.L, P.scenarios[c.scenario], P, M,
  { rateShiftBps: c.rate_shift_bps, capShiftBps: c.cap_shift_bps })));
writeFileSync(outPath, JSON.stringify(out));
