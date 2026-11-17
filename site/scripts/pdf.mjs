// Print pages to PDF for an offline reviewer: node scripts/pdf.mjs <base> <outdir> <page> [page...]
import { mkdirSync } from "node:fs";
import puppeteer from "puppeteer-core";

const [base, outDir, ...pages] = process.argv.slice(2);
mkdirSync(outDir, { recursive: true });
const b = await puppeteer.launch({ executablePath: "C:/Program Files/Google/Chrome/Application/chrome.exe", headless: true });
for (const path of pages) {
  const p = await b.newPage();
  await p.setViewport({ width: 760, height: 1100 });   // the printed page width, so charts draw to fit it
  await p.emulateMediaFeatures([{ name: "prefers-reduced-motion", value: "reduce" }]);
  await p.emulateMediaType("screen");
  await p.goto(`${base}/${path}`, { waitUntil: "networkidle0", timeout: 60000 });
  await p.$$eval("details", (ds) => ds.forEach((d) => { d.open = true; }));
  await new Promise((r) => setTimeout(r, 1000));
  const name = path.replace(/\.html.*$/, "") || "home";
  await p.pdf({ path: `${outDir}/${name}.pdf`, format: "Letter", printBackground: true, margin: { top: "0.4in", bottom: "0.4in", left: "0.3in", right: "0.3in" } });
  console.log("wrote", `${outDir}/${name}.pdf`);
  await p.close();
}
await b.close();
