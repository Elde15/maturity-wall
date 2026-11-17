// Social preview image (1200 x 630) from the rendered home page: node scripts/og.mjs <base>
// A compact layout is applied before the page draws, so the whole wall chart fits under the headline.
import puppeteer from "puppeteer-core";

const base = process.argv[2] || "http://localhost:5175";
const css = `.banner,.hero-cta,.lede,.hero-label,.fig-take,.fig-foot,.fig-legend,.fig-q,.section{display:none!important}
  .hero{padding-top:20px!important}.hero h1{font-size:56px!important;grid-column:1/-1!important}
  #hero-fig{margin-top:14px!important}#hero-fig .fig{padding-top:8px!important;border-top:0!important}`;
const b = await puppeteer.launch({ executablePath: "C:/Program Files/Google/Chrome/Application/chrome.exe", headless: true });
const p = await b.newPage();
await p.setViewport({ width: 1200, height: 630, deviceScaleFactor: 1 });
await p.emulateMediaFeatures([{ name: "prefers-reduced-motion", value: "reduce" }]);
await p.evaluateOnNewDocument((c) => {
  document.addEventListener("DOMContentLoaded", () => { const s = document.createElement("style"); s.textContent = c; document.head.appendChild(s); });
}, css);
await p.goto(`${base}/`, { waitUntil: "networkidle0" });
await new Promise((r) => setTimeout(r, 1200));
await p.screenshot({ path: "public/og.png", clip: { x: 0, y: 0, width: 1200, height: 630 } });
await b.close();
