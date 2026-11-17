// Gate 5 accessibility checks: axe-core on every page at desktop and phone width, plus a keyboard walk that tabs
// through the page and confirms each focus stop is visible and has an accessible name.
// usage: node scripts/a11y.mjs <base>
import { readFileSync } from "node:fs";
import puppeteer from "puppeteer-core";

const base = process.argv[2] || "http://localhost:4173";
const axe = readFileSync("node_modules/axe-core/axe.min.js", "utf-8");
const pages = ["/", "/wall.html", "/loans.html", "/loan.html?id=WL2725d11c7fb2", "/lab.html", "/los-angeles.html", "/method.html", "/data.html"];
const b = await puppeteer.launch({ executablePath: "C:/Program Files/Google/Chrome/Application/chrome.exe", headless: true });
let total = 0;
for (const path of pages) {
  for (const width of [1280, 390]) {
    const p = await b.newPage();
    await p.setViewport({ width, height: 900 });
    await p.goto(base + path, { waitUntil: "networkidle0", timeout: 60000 });
    await new Promise((r) => setTimeout(r, 600));
    await p.addScriptTag({ content: axe });
    const res = await p.evaluate(async () => {
      const r = await window.axe.run(document, { runOnly: { type: "tag", values: ["wcag2a", "wcag2aa", "wcag21aa"] } });
      return r.violations.map((v) => ({ id: v.id, impact: v.impact, n: v.nodes.length, help: v.help, eg: v.nodes[0]?.target?.join(" ") }));
    });
    total += res.length;
    let walk = "";
    if (width === 1280) {
      const stops = [];
      for (let i = 0; i < 40; i++) {
        await p.keyboard.press("Tab");
        stops.push(await p.evaluate(() => {
          const e = document.activeElement;
          if (!e || e === document.body) return null;
          const cs = getComputedStyle(e);
          const r = e.getBoundingClientRect();
          const name = (e.getAttribute("aria-label") || e.innerText || e.value || e.getAttribute("placeholder") || e.title || "").trim().slice(0, 30);
          return { tag: e.tagName, name, outline: cs.outlineStyle !== "none" && cs.outlineWidth !== "0px", visible: r.width > 0 && r.height > 0 };
        }));
      }
      const real = stops.filter(Boolean);
      const bad = real.filter((s) => !s.outline || !s.visible || !s.name);
      walk = `; keyboard: ${real.length} stops, first "${real[0]?.name}", ${bad.length} without a visible outline or a name${bad.length ? ` (${bad.slice(0, 3).map((s) => `${s.tag}:${s.name}`).join(", ")})` : ""}`;
    }
    console.log(`${path} @${width}: ${res.length} axe violations${walk}`);
    res.forEach((v) => console.log(`    ${v.impact} ${v.id} x${v.n}: ${v.help} [${v.eg}]`));
    await p.close();
  }
}
await b.close();
console.log(`total violations: ${total}`);
