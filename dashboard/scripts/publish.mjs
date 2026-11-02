// Copy the static export (out/) to docs/dashboard/, which GitHub Pages serves at
// https://rashmi049-clutch.github.io/kilnwatch/dashboard/
import { cpSync, existsSync, rmSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const out = join(here, "..", "out");
const dest = join(here, "..", "..", "docs", "dashboard");
if (!existsSync(out)) throw new Error("No out/ folder: run `next build` first");
// local-only data (e.g. Rashmi's Google Maps scrape) must never reach the public site
rmSync(join(out, "local"), { recursive: true, force: true });
rmSync(dest, { recursive: true, force: true });
cpSync(out, dest, { recursive: true });
writeFileSync(join(dest, "..", ".nojekyll"), ""); // site root: stops Jekyll hiding the _next/ folder
console.log(`Published ${out} -> ${dest}`);
