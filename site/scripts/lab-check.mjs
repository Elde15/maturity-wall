// The lab's sliders recompute: +100 bp on Treasuries must raise the segment's refinance gap.
import puppeteer from "puppeteer-core";
const b = await puppeteer.launch({ executablePath: "C:/Program Files/Google/Chrome/Application/chrome.exe", headless: true });
const p = await b.newPage();
await p.goto((process.argv[2] || "http://localhost:4173") + "/lab.html", { waitUntil: "networkidle0" });
await p.waitForFunction(() => document.querySelector("#seg-status").textContent.startsWith("Recomputed"));
const read = () => p.$eval("#seg-stats", (el) => [...el.querySelectorAll(".v")].map((v) => v.textContent));
const before = await read();
await p.$eval("#tsy", (el) => { el.value = 100; el.dispatchEvent(new Event("input", { bubbles: true })); });
await p.waitForFunction(() => document.querySelector("#seg-status").textContent.startsWith("Recomputed") && document.querySelector("#o-tsy").textContent === "+100 bp", { timeout: 20000 });
await new Promise((r) => setTimeout(r, 300));
const after = await read();
const status = await p.$eval("#seg-status", (el) => el.textContent);
console.log("start", before.join(" | "), "\n+100bp", after.join(" | "), "\n", status);
await b.close();
