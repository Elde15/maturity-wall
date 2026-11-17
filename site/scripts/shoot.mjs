// QA screenshots with the installed Chrome (headless): node scripts/shoot.mjs <outdir> <base> <page> [page...]
// Each page is shot at 1280px and 390px wide, full height; console errors and page errors are printed.
import { mkdirSync } from "node:fs";
import puppeteer from "puppeteer-core";

const [outDir, base, ...pages] = process.argv.slice(2);
const CHROME = process.env.CHROME || "C:/Program Files/Google/Chrome/Application/chrome.exe";
mkdirSync(outDir, { recursive: true });
const browser = await puppeteer.launch({ executablePath: CHROME, headless: true, args: ["--no-first-run"] });
for (const p of pages) {
  for (const width of [1280, 390]) {
    const page = await browser.newPage();
    const errors = [];
    page.on("console", (m) => { if (m.type() === "error" || m.type() === "warning") errors.push(`${m.type()}: ${m.text()}`); });
    page.on("pageerror", (e) => errors.push(`pageerror: ${e.message}`));
    await page.setViewport({ width, height: 900, deviceScaleFactor: 1 });
    const t0 = Date.now();
    await page.goto(`${base}/${p}`, { waitUntil: "networkidle0", timeout: 60000 });
    await new Promise((r) => setTimeout(r, 900));
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
    const name = `${p.replace(/[^a-z0-9]+/gi, "_")}_${width}.png`;
    await page.screenshot({ path: `${outDir}/${name}`, fullPage: true });
    console.log(`${p} @${width}: ${Date.now() - t0} ms, horizontal overflow ${overflow}px, ${errors.length} console issues`);
    errors.slice(0, 8).forEach((e) => console.log("   ", e));
    await page.close();
  }
}
await browser.close();
