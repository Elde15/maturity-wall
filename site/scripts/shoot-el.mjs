// node scripts/shoot-el.mjs <out.png> <url> <selector> [width]
import puppeteer from "puppeteer-core";
const [out, url, sel, w] = process.argv.slice(2);
const b = await puppeteer.launch({ executablePath: "C:/Program Files/Google/Chrome/Application/chrome.exe", headless: true });
const p = await b.newPage();
await p.setViewport({ width: Number(w || 1280), height: 900 });
await p.goto(url, { waitUntil: "networkidle0" });
await new Promise((r) => setTimeout(r, 800));
const el = await p.$(sel);
await el.screenshot({ path: out });
await b.close();
