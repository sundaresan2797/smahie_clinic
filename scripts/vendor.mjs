// Copies the browser builds of npm dependencies into app/static so the site
// serves every script and font from its own origin (strict CSP, no CDN calls).
// Run after `npm ci`:  npm run vendor
import { copyFileSync, mkdirSync, readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const nm = (p) => join(root, "node_modules", p);
const out = (p) => join(root, "app", "static", p);

const files = [
  ["bootstrap/dist/css/bootstrap.min.css", "vendor/bootstrap/bootstrap.min.css"],
  ["bootstrap/dist/js/bootstrap.bundle.min.js", "vendor/bootstrap/bootstrap.bundle.min.js"],
  ["gsap/dist/gsap.min.js", "vendor/gsap/gsap.min.js"],
  ["gsap/dist/ScrollTrigger.min.js", "vendor/gsap/ScrollTrigger.min.js"],
  ["gsap/dist/SplitText.min.js", "vendor/gsap/SplitText.min.js"],
  ["lenis/dist/lenis.min.js", "vendor/lenis/lenis.min.js"],
  ["@fontsource-variable/manrope/files/manrope-latin-wght-normal.woff2", "fonts/manrope-latin-wght-normal.woff2"],
  ["@fontsource-variable/manrope/files/manrope-latin-ext-wght-normal.woff2", "fonts/manrope-latin-ext-wght-normal.woff2"],
  ["@fontsource-variable/playfair-display/files/playfair-display-latin-wght-normal.woff2", "fonts/playfair-display-latin-wght-normal.woff2"],
  ["@fontsource-variable/playfair-display/files/playfair-display-latin-wght-italic.woff2", "fonts/playfair-display-latin-wght-italic.woff2"],
];

for (const [from, to] of files) {
  mkdirSync(dirname(out(to)), { recursive: true });
  copyFileSync(nm(from), out(to));
  console.log(`copied ${to}`);
}

const pkg = JSON.parse(readFileSync(join(root, "package.json"), "utf8"));
console.log("\nversions:", pkg.dependencies);
