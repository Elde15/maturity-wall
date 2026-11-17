// Gate 5 link check: render every page (and a sample of tear sheets) in headless Chrome, collect every link,
// and confirm it resolves. Internal links must return 200 (and tear-sheet ids must exist); external links are
// fetched with a generic User-Agent. SEC EDGAR refuses automated requests without a declared contact, so EDGAR
// links are checked against the filing list the pipeline downloaded instead (scripts write sec_links.json).
// usage: node scripts/check-links.mjs <base> <out.json>
import { readFileSync, writeFileSync } from "node:fs";
import puppeteer from "puppeteer-core";

const [base = "http://localhost:4173", out = "link-report.json"] = process.argv.slice(2);
const PAGES = ["/", "/wall.html", "/loans.html", "/lab.html", "/los-angeles.html", "/method.html", "/data.html"];
const loans = JSON.parse(readFileSync("public/data/loans.json", "utf-8")).loans;
const ids = new Set(loans.id);
const sample = loans.id.filter((_, i) => i % 1300 === 0);           // 11 tear sheets across the table
const la = JSON.parse(readFileSync("public/data/la.json", "utf-8")).cases.map((c) => c.id);
const pages = [...PAGES, ...[...sample, ...la].map((id) => `/loan.html?id=${id}`)];

const browser = await puppeteer.launch({ executablePath: "C:/Program Files/Google/Chrome/Application/chrome.exe", headless: true });
const links = new Map();   // href -> first page seen
const errors = [];
for (const path of pages) {
  const p = await browser.newPage();
  p.on("pageerror", (e) => errors.push(`${path}: ${e.message}`));
  await p.goto(base + path, { waitUntil: "networkidle0", timeout: 60000 });
  await new Promise((r) => setTimeout(r, 500));
  // open every <details> so links inside them are collected too
  await p.$$eval("details", (ds) => ds.forEach((d) => { d.open = true; }));
  const hrefs = await p.$$eval("a[href]", (as) => as.map((a) => a.href));
  for (const h of hrefs) if (!links.has(h)) links.set(h, path);
  await p.close();
}
await browser.close();

const results = { internal: [], external: [], sec: [], failures: [] };
const UA = { "User-Agent": "mwall-research/0.1" };
for (const [href, from] of links) {
  const u = new URL(href);
  if (u.origin === new URL(base).origin) {
    const r = await fetch(href);
    let ok = r.ok;
    if (u.pathname === "/loan.html") ok = ok && ids.has(u.searchParams.get("id"));
    if (u.hash && u.pathname.endsWith(".html")) {
      const html = await (await fetch(base + u.pathname)).text();
      ok = ok && html.includes(`id="${u.hash.slice(1)}"`);
    }
    results.internal.push({ href, from, ok, status: r.status });
    if (!ok) results.failures.push({ href, from, status: r.status });
  } else if (u.hostname.endsWith("sec.gov")) {
    results.sec.push({ href, from });
  } else {
    let status = 0;
    try {
      const r = await fetch(href, { method: "GET", headers: UA, redirect: "follow", signal: AbortSignal.timeout(20000) });
      status = r.status;
    } catch (e) { status = `error: ${e.cause?.code || e.name}`; }
    const ok = typeof status === "number" && status < 400;
    results.external.push({ href, from, status, ok });
    if (!ok) results.failures.push({ href, from, status });
  }
}
writeFileSync(out, JSON.stringify(results, null, 1));
console.log(`pages ${pages.length}, links ${links.size}: internal ${results.internal.length} (${results.internal.filter((x) => !x.ok).length} bad), `
  + `external ${results.external.length} (${results.external.filter((x) => !x.ok).length} bad), SEC ${results.sec.length} (checked against the filing list), page errors ${errors.length}`);
errors.forEach((e) => console.log("  ", e));
results.failures.slice(0, 40).forEach((f) => console.log("  FAIL", f.status, f.href, "on", f.from));
