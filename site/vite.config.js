import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { defineConfig } from "vite";

const PAGES = ["index", "wall", "loans", "loan", "lab", "los-angeles", "method", "data"];
const NAV = [
  ["wall", "The wall"], ["loans", "Loans"], ["lab", "Scenario lab"], ["los-angeles", "Los Angeles"],
  ["method", "Method"], ["data", "Data and code"],
];

// <!-- @header --> and <!-- @footer --> are filled from partials at build time, with the current page marked
function partials() {
  const read = (name) => readFileSync(resolve(__dirname, "partials", `${name}.html`), "utf-8");
  return {
    name: "partials",
    transformIndexHtml(html, ctx) {
      const page = ctx.filename.replace(/\\/g, "/").split("/").pop().replace(".html", "");
      const active = page === "loan" ? "loans" : page;
      const nav = NAV.map(([href, label]) =>
        `<li><a href="/${href}.html"${href === active ? ' aria-current="page"' : ""}>${label}</a></li>`).join("");
      return html
        .replace("<!-- @header -->", read("header").replace("<!-- @nav -->", nav))
        .replace("<!-- @footer -->", read("footer"))
        .replace("<!-- @banner -->", read("banner"));
    },
  };
}

export default defineConfig({
  plugins: [partials()],
  build: {
    outDir: "dist",
    emptyOutDir: true,
    rollupOptions: { input: Object.fromEntries(PAGES.map((p) => [p, resolve(__dirname, `${p}.html`)])) },
  },
});
