// Underwriting engine, a line-for-line port of src/mwall/underwrite/engine.py (SOP 12).
// Gate 5 requires this to match the Python engine for 50 random loans (tests/test_site.py).
// Dates are ISO strings (YYYY-MM-DD), which compare correctly as strings.

export const OWN_SERIES = ["office", "retail", "industrial", "multifamily"];
export const ROLLOVER_TYPES = ["office", "retail", "industrial"];
const SPECIAL_CITY = {
  santa_monica: [[8_000_000, 5.3], [5_000_000, 0.3]],
  culver_city: [[10_000_000, 3.55], [3_000_000, 2.55], [1_500_000, 1.05]],
};
const HOLD = 5;

const num = (v) => (v === null || v === undefined || v === "" ? NaN : Number(v));
const isNum = (v) => !Number.isNaN(v);

// ------------------------------------------------------------------ parameters

export function makeParams(scen) {
  // scen: the parsed scenarios.json
  const lender = new Map();
  for (const r of scen.engine.lender) lender.set(`${r.scenario}|${r.property_group}`, r);
  const scenarios = {};
  for (const s of scen.scenarios) scenarios[s.scenario] = s;
  return { par: scen.engine.par, la: scen.engine.la, lender, scenarios };
}

export function par(P, name, group) {
  const t = P.par[name] || {};
  if (group !== null && group !== undefined && group in t) return t[group];
  return "all" in t ? t.all : null;
}

const la = (P, rule, j, p) => P.la[`${rule}|${j}|${p}`];

// ------------------------------------------------------------------ small pieces

export function loanConstant(r, years) {
  if (!years || years <= 0) return r;
  const i = r / 12;
  return (12 * i) / (1 - (1 + i) ** (-12 * years));
}

export function npv(rate, cfs) {
  let s = 0;
  for (let t = 0; t < cfs.length; t++) s += cfs[t] / (1 + rate) ** t;
  return s;
}

export function irr(cfs) {
  let lo = -0.99, hi = 10.0;
  let fLo = npv(lo, cfs);
  const fHi = npv(hi, cfs);
  if (!Number.isFinite(fLo) || !Number.isFinite(fHi) || fLo * fHi > 0) return NaN;
  for (let k = 0; k < 200; k++) {
    const mid = (lo + hi) / 2;
    const fMid = npv(mid, cfs);
    if (fLo * fMid <= 0) hi = mid;
    else { lo = mid; fLo = fMid; }
    if (hi - lo < 1e-12) break;
  }
  return (lo + hi) / 2;
}

export function addYears(iso, n) {
  const [y, m, d] = iso.split("-").map(Number);
  const yy = y + n;
  let dd = d;
  if (m === 2 && d === 29) {
    const leap = (yy % 4 === 0 && yy % 100 !== 0) || yy % 400 === 0;
    if (!leap) dd = 28;
  }
  return `${String(yy).padStart(4, "0")}-${String(m).padStart(2, "0")}-${String(dd).padStart(2, "0")}`;
}

export function rolloverYear(expiry, valuation) {
  if (!expiry) return null;
  for (let t = 1; t <= HOLD; t++) if (expiry <= addYears(valuation, t)) return t;
  return null;
}

export function ulaIndexations(exitIso) {
  const [y, m, d] = exitIso.split("-").map(Number);
  const before = m < 7 || (m === 7 && d < 1);
  return Math.max(y - 2026 - (before ? 1 : 0), 0);
}

export function localTransferRate(jurisdiction, price, exitIso, P) {
  if (jurisdiction === "la_city") {
    const g = la(P, "ula", "la_city", "threshold_growth") / 100;
    const n = ulaIndexations(exitIso);
    const lo = la(P, "ula", "la_city", "threshold_lower") * (1 + g) ** n;
    const hi = la(P, "ula", "la_city", "threshold_upper") * (1 + g) ** n;
    if (price >= hi) return la(P, "ula", "la_city", "rate_upper") / 100;
    if (price > lo) return la(P, "ula", "la_city", "rate_lower") / 100;
    return 0;
  }
  for (const [floor, rate] of SPECIAL_CITY[jurisdiction] || []) if (price >= floor) return rate / 100;
  return 0;
}

// ------------------------------------------------------------------ the engine

export function underwrite(L, S, P, M, opts = {}) {
  const g = L.group, tier = L.tier;
  const rs = (opts.rateShiftBps ?? S.rate_shift_bps) / 10000;
  const cs = (opts.capShiftBps ?? S.cap_shift_bps) / 10000;
  const out = { tier, tier_reason: L.tier_reason, jurisdiction: L.jurisdiction };
  const B = num(L.wl_balance_est);
  const noi0 = num(L.noi);
  if (g === null || g === undefined) return out;

  // ---- step B
  const h = S.noi_haircut !== "none" ? par(P, S.noi_haircut, g) / 100 : 0;
  const noiS = noi0 * (1 - h);
  const bt = num(L.bench_today);
  const spread = num(L.spread_sec);
  let c = bt + (isNum(spread) ? spread : 0) + cs;
  if (isNum(c)) c = Math.max(c, par(P, "cap_rate_floor", "all") / 100);
  Object.assign(out, { noi_stressed: noiS, cap_rate: c, cap_method: isNum(spread) ? "relative value" : "benchmark only",
    bench_kind: L.bench_kind });
  const tau = num(L.tax_rate), tbase = num(L.tax_current);
  const prop13 = isNum(tau) && isNum(tbase);
  if (tier === null || tier === undefined || !isNum(c)) {
    if (noi0 <= 0 && isNum(B)) Object.assign(out, { p_max: 0, refi_gap: B, refi_gap_pct: 1 });
    return out;
  }
  // Proposition 8 (D064): the seller's tax is capped at the tax on today's value, NOI / c
  const tcur = prop13 ? Math.min(tbase, (tau * noiS) / c) : NaN;
  const V = prop13 ? (noiS + tcur) / (c + tau) : noiS / c;
  out.value = V;
  out.seller_tax = tcur;

  // ---- step A
  const lp = P.lender.get(`${S.refi_lender_set}|${g}`) || P.lender.get(`${S.refi_lender_set}|other`);
  const rRefi = M.ust10 + (M.spread_bps[lp.spread_series] + lp.spread_premium_bps) / 10000 + rs;
  const k = loanConstant(rRefi, lp.amort_years);
  const pLtv = lp.ltv_max * V;
  const pDscr = noiS / (lp.dscr_min * k);
  const pDy = lp.dy_min ? noiS / lp.dy_min : Infinity;
  const pMax = Math.max(Math.min(pLtv, pDscr, pDy), 0);
  Object.assign(out, { refi_rate: rRefi, loan_constant: k, p_ltv: pLtv, p_dscr: pDscr, p_dy: pDy, p_max: pMax });
  if (isNum(B) && B > 0) Object.assign(out, { refi_gap: Math.max(0, B - pMax), refi_gap_pct: Math.max(0, B - pMax) / B });

  // ---- capital items and lease-up
  const sqft = num(L.sqft), units = num(L.units), occ = num(L.occupancy);
  const occEff = occ > 0 ? occ : 1.0;
  const rev0 = num(L.revenue);
  const incomeFull = (rev0 > 0 ? rev0 : noi0) / occEff;
  let reserve;
  if (g === "multifamily") reserve = units > 0 ? par(P, "reserve", g) * units : NaN;
  else if (g === "lodging") reserve = rev0 > 0 ? (par(P, "reserve", g) / 100) * rev0 : NaN;
  else reserve = sqft > 0 ? par(P, "reserve", g) * sqft : NaN;
  const roll = ROLLOVER_TYPES.includes(g) && sqft > 0;
  let shares = [];
  if (roll && L.jurisdiction !== "multi_property") {
    for (const i of [1, 2, 3]) {
      const sq = num(L[`tenant${i}_sqft`]), exp = L[`tenant${i}_lease_exp`];
      if (sq > 0 && exp) shares.push([sq / sqft, rolloverYear(exp, L.valuation)]);
    }
    const tot = shares.reduce((a, s) => a + s[0], 0);
    if (tot > occEff) shares = shares.map(([s, y]) => [(s * occEff) / tot, y]);
  }
  const listed = shares.reduce((a, s) => a + s[0], 0);
  const unlisted = Math.max(0, occEff - listed);
  let pRen = 0, dt = 0, tiCost = 0, rT = [0, 0, 0, 0, 0], leaseUp = 0;
  if (roll) {
    pRen = par(P, "renewal_prob", g) / 100;
    dt = par(P, "downtime_months", g) / 12;
    tiCost = sqft * (pRen * par(P, "ti_lc_renewal_psf", g) + (1 - pRen) * par(P, "ti_lc_new_psf", g));
    const term = par(P, "lease_term_years", g);
    rT = [1, 2, 3, 4, 5].map((t) => shares.filter((s) => s[1] === t).reduce((a, s) => a + s[0], 0) + unlisted / term);
    const r1 = shares.filter((s) => s[1] === 1).reduce((a, s) => a + s[0], 0);
    leaseUp = r1 * (tiCost + (1 - pRen) * incomeFull * dt);
  }
  const closing = par(P, "buyer_closing_pct", "all") / 100;
  const res1 = isNum(reserve) ? reserve : 0;
  const valueBid = (V - leaseUp - res1) / (1 + closing);
  Object.assign(out, { reserve_y1: reserve, lease_up: leaseUp, value_bid: valueBid });
  if (tier === "C") return finish(out, valueBid, NaN, B);

  // ---- step D
  const gr = par(P, "noi_growth", g) / 100;
  let growth = Array(HOLD + 1).fill(gr);
  const metro = num(L.mf_rent_growth_metro);
  if (g === "multifamily" && isNum(metro)) growth[1] = metro;
  const cap = L.rent_cap === null || L.rent_cap === undefined ? Infinity : num(L.rent_cap);
  growth = growth.map((x) => Math.min(x, cap));
  const St = [noiS];
  for (let t = 1; t <= HOLD; t++) St.push(St[St.length - 1] * (1 + growth[t]));
  const reno = S.renovation === "on" && g === "multifamily" && units > 0 && cap > 0.05;
  const budget = reno ? par(P, "renovation_cost_per_unit", g) * units : 0;
  const premium = reno ? (budget * par(P, "renovation_roc", g)) / 100 : 0;
  const ren = [0, premium, premium, premium, premium, premium];
  const loss = [0, 1, 2, 3, 4].map((t) => (1 - pRen) * rT[t] * incomeFull * dt * (1 + gr) ** t);
  const leasing = [0, 1, 2, 3, 4].map((t) => rT[t] * tiCost);
  const capex = leasing.map((x) => res1 + x);
  const g2 = la(P, "prop13", "all", "assessed_growth") / 100;
  const cExit = c + par(P, "exit_cap_spread_bps", "all") / 10000;
  const preTax6 = St[HOLD] + ren[HOLD] + (prop13 ? tcur * (1 + g2) ** HOLD : 0);
  const exitPrice = preTax6 / (cExit + (prop13 ? tau : 0));
  const exitDate = addYears(L.valuation, HOLD);
  const sell = par(P, L.high_tax_metro ? "selling_cost_pct_high_tax" : "selling_cost_pct", "all") / 100;
  const local = localTransferRate(L.jurisdiction, exitPrice, exitDate, P);
  const exitNet = exitPrice * (1 - sell - local);
  const tenor = par(P, "acq_treasury_tenor", "all");
  const rAcq = M[`ust${Math.trunc(tenor)}`] + par(P, "bridge_spread_bps", g) / 10000 + rs;
  const ltc = par(P, "ltc", g) / 100, ltv = par(P, "ltv_asis", g) / 100;
  const hurdle = opts.hurdle ?? par(P, S.hurdle_param, "all") / 100;

  const flows = (price) => {
    const cost = price * (1 + closing) + budget;
    const loan = Math.min(ltc * cost, ltv * V);
    const dtax = [0, 1, 2, 3, 4].map((t) => (prop13 ? (tau * price - tcur) * (1 + g2) ** t : 0));
    const noi = [0, 1, 2, 3, 4].map((t) => St[t] + ren[t] - dtax[t] - loss[t]);
    const interest = rAcq * loan;
    const unlev = [-cost, ...noi.map((n, t) => n - capex[t])];
    unlev[HOLD] += exitNet;
    const lev = [-cost + loan, ...[0, 1, 2, 3, 4].map((t) => unlev[t + 1] - interest)];
    lev[HOLD] -= loan;
    return { price, cost, loan, noi, dtax, interest, unlev, lev };
  };

  const kink = ((ltv * V) / ltc - budget) / (1 + closing);
  const f = (x) => npv(hurdle, flows(x).lev);
  let retBid = NaN;
  if (kink > 0) {
    const f0 = f(0), fk = f(kink);
    if (f0 > 0 && 0 >= fk) retBid = (kink * f0) / (f0 - fk);
    else if (fk > 0) {
      const f2 = f(2 * kink);
      if (f2 < fk) retBid = kink + (kink * fk) / (fk - f2);
    }
  } else {
    const f0 = f(0), f1 = f(V);
    if (f0 > 0 && f1 < f0) retBid = (V * f0) / (f0 - f1);
  }
  Object.assign(out, { exit_cap: cExit, exit_price: exitPrice, exit_cost_rate: sell + local, exit_net: exitNet,
    acq_rate: rAcq, hurdle, return_bid: retBid, renovation_budget: budget, kink });
  if (isNum(retBid)) {
    const fl = flows(retBid);
    const eq = -fl.lev[0];
    const ops = [0, 1, 2, 3, 4].map((t) => fl.unlev[t + 1] - fl.interest);
    ops[HOLD - 1] = fl.noi[HOLD - 1] - capex[HOLD - 1] - fl.interest;
    Object.assign(out, {
      loan_at_bid: fl.loan, equity: eq, irr_levered: irr(fl.lev), irr_unlevered: irr(fl.unlev),
      equity_multiple: fl.lev.slice(1).reduce((a, b) => a + b, 0) / eq,
      cash_on_cash: ops.reduce((a, b) => a + b, 0) / HOLD / eq,
      noi_y1: fl.noi[0], dscr_y1: fl.interest > 0 ? fl.noi[0] / fl.interest : NaN,
      dy_y1: fl.loan > 0 ? fl.noi[0] / fl.loan : NaN,
      breakeven_occ: rev0 > 0 ? (rev0 - fl.noi[0] + fl.interest) / (rev0 / occEff) : NaN,
    });
    if (opts.keepFlows) out.flows = fl;
  }
  const fv = valueBid > 0 ? flows(valueBid) : null;
  out.irr_at_value_bid = fv ? irr(fv.lev) : NaN;
  out.irr_unlevered_at_value_bid = fv ? irr(fv.unlev) : NaN;
  out.clears_hurdle_at_value = isNum(retBid) ? retBid >= valueBid : false;
  return finish(out, valueBid, retBid, B);
}

function finish(out, valueBid, retBid, B) {
  const bids = [valueBid, retBid].filter(isNum);
  const bid = bids.length ? Math.max(Math.min(...bids), 0) : NaN;
  out.bid = bid;
  if (isNum(bid) && B > 0) {
    out.refinanceable_by_sale = bid >= B;
    out.discount = Math.max(0, 1 - bid / B);
  }
  return out;
}

// columnar uw.json -> one loan's input object
export function loanFromColumns(cols, i) {
  const L = {};
  for (const k of Object.keys(cols)) L[k] = cols[k][i];
  L.group = L.group ?? null;
  L.tier = L.tier ?? null;
  return L;
}
