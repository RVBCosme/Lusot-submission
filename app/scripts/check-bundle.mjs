// Checks a built bundle for what must never ship: the development mock's marker, the end-to-end fixture's marker
// (Task 18), the Meta API's host and the name of the Meta key's variable.
// Usage: node app/scripts/check-bundle.mjs <dist dir> [--demo]
// --demo checks the portfolio demo build (`npm run build:demo -w app`, Nov 10, 2026), which answers every API call
// from the mock by design: there the mock's marker must be present, and the other three markers still fail it.
// Exit 0: clean. Exit 1: a built file holds a marker, or dist has no licences.txt. Exit 2: nothing was checked (no
// folder, or no files in it), so "clean" would mean nothing.
// It prints only file names, marker names and counts, never the text around a marker.
import { readdirSync, readFileSync, statSync } from "node:fs";
import { join, relative } from "node:path";

const MOCK_MARKER = "LUSOT_MOCK_API";
const ALL_MARKERS = [MOCK_MARKER, "LUSOT_E2E_FIXTURE", "api.meta.ai", "MODEL_API_KEY"];

// Every regular file under `dir`, in a stable order. Links aren't followed.
function* filesUnder(dir) {
  const entries = readdirSync(dir, { withFileTypes: true }).sort((a, b) => a.name.localeCompare(b.name));
  for (const entry of entries) {
    const path = join(dir, entry.name);
    if (entry.isDirectory()) yield* filesUnder(path);
    else if (entry.isFile()) yield path;
  }
}

function countIn(bytes, marker) {
  const needle = Buffer.from(marker);
  let count = 0;
  for (let at = bytes.indexOf(needle); at !== -1; at = bytes.indexOf(needle, at + needle.length)) count += 1;
  return count;
}

const args = process.argv.slice(2);
const demo = args.includes("--demo");
const [dir, ...extra] = args.filter((arg) => arg !== "--demo");
if (dir === undefined || extra.length > 0) {
  console.error("usage: node app/scripts/check-bundle.mjs <dist dir> [--demo]");
  process.exit(2);
}
const MARKERS = demo ? ALL_MARKERS.filter((marker) => marker !== MOCK_MARKER) : ALL_MARKERS;
let isDir = false;
try {
  isDir = statSync(dir).isDirectory();
} catch {
  // Left false: reported below.
}
if (!isDir) {
  console.error("bundle check: not a folder");
  process.exit(2);
}

let scanned = 0;
let mockFiles = 0;
const hits = [];
for (const file of filesUnder(dir)) {
  scanned += 1;
  const bytes = readFileSync(file);
  if (demo && countIn(bytes, MOCK_MARKER) > 0) mockFiles += 1;
  for (const marker of MARKERS) {
    const count = countIn(bytes, marker);
    if (count > 0) hits.push(`${relative(dir, file)}: ${marker} x${count}`);
  }
}

if (scanned === 0) {
  console.error("bundle check: no files to check");
  process.exit(2);
}
// The licences page needs licences.txt at the top of dist (C636). `prebuild` writes it into public/, so a build that
// skipped prebuild would ship the page with no text, or with a stale copy.
let licences = "";
try {
  licences = readFileSync(join(dir, "licences.txt"), "utf8");
} catch {
  // Left empty: reported below.
}
if (licences.trim() === "") hits.push("licences.txt: missing or empty (npm run build -w app writes it first)");
// A demo build without the mock would send its calls to whatever API address it was given.
if (demo && mockFiles === 0) hits.push(`${MOCK_MARKER}: missing, so this demo build doesn't answer from the mock`);
if (hits.length > 0) {
  console.error(`bundle check FAILED, ${hits.length} hit${hits.length === 1 ? "" : "s"} in ${scanned} files:`);
  for (const hit of hits) console.error(`  ${hit}`);
  process.exit(1);
}
console.log(`bundle check${demo ? " (demo)" : ""}: clean (${scanned} files)`);
