// Writes app/public/licences.txt: the name, version and full licence text of every production dependency of the app
// and of the build-time code that ships in the page, plus the Android app's libraries once Task 17 lists them. The
// licences page shows this file (C636), because BSD-2-Clause, the OFL and the other licences ask for their text to
// travel with a bundled copy. `npm run build -w app` runs it first (the `prebuild` script); the file is generated and
// git-ignored.
//
// Usage: node app/scripts/licences.mjs [--root <repo root>]
//   The root is found from this file's place; --root is for the tests, which build a repo in a temporary folder.
// Where the data comes from:
//   - `npm ls --workspace app --omit=dev --all --json`, run from the root: the production packages, nested ones too.
//     Each is found by Node's rules (its parent's folder first, then up, but never above the repo root) and must be the
//     version npm lists.
//   - app/scripts/shipped-extra.json, optional: [{ "package", "ships", "stopAt"? }], code from a development
//     dependency that ends up in the page. The text is that package's licence file, cut before the line `stopAt`
//     when the file goes on to licences of code that doesn't ship.
//   - app/scripts/apk-licences.json, optional, written by Task 17: [{ "name", "version"?, "licence"?, "text" }].
// A package's text is its licence file (LICENSE, LICENCE or COPYING), then any third-party notice file
// (THIRD-PARTY-LICENSE) and NOTICE file it carries, each labelled when there is more than one, because the notices of
// code a package adapted must travel with it too. A package without a licence file fails the run, naming the
// package. A failed run leaves no licences.txt behind, so a
// stale file never stands in for a current one. The log holds counts and file names, never a licence's text.
import { spawnSync } from "node:child_process";
import { existsSync, mkdirSync, readdirSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { basename, dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

class LicencesError extends Error {}

// LICENSE, LICENCE and COPYING, in any case, with or without an extension (LICENSE.md, copying.TXT).
const LICENCE_FILE = /^(licen[cs]e|copying)(\.[a-z0-9]+)?$/i;
// What rides with it, and never stands in for it: THIRD-PARTY-LICENSE, ThirdPartyLicenses.md, THIRD_PARTY_NOTICES, NOTICE.
const NOTICE_FILE = /^(third[-_]?party[-_]?(licen[cs]es?|notices?)|notices?)(\.[a-z0-9]+)?$/i;
// Short enough not to wrap on a 360 px phone, where the page shows this file.
const RULE = "=".repeat(24);
const THIN = "-".repeat(24);

function readJson(path, what) {
  let raw;
  try {
    raw = readFileSync(path, "utf8");
  } catch {
    throw new LicencesError(`cannot read ${what}`);
  }
  try {
    return JSON.parse(raw);
  } catch {
    throw new LicencesError(`${what} is not valid JSON`);
  }
}

// Node's lookup for `name`: the folder's own node_modules, then each folder above it up to the repo root, and no
// further (a folder called node_modules is skipped). With a version, a copy at another version is passed over, as
// npm's own tree would.
function locate(name, version, fromDir, root) {
  for (let dir = fromDir; ; dir = dirname(dir)) {
    if (basename(dir) !== "node_modules") {
      const candidate = join(dir, "node_modules", name);
      if (existsSync(join(candidate, "package.json"))) {
        const installed = readJson(join(candidate, "package.json"), `${name}'s package.json`);
        if (version === undefined || installed.version === version) return { dir: candidate, version: installed.version };
      }
    }
    if (dir === root || dirname(dir) === dir) break;
  }
  throw new LicencesError(`${name}${version === undefined ? "" : `@${version}`} is not installed under the repo`);
}

function licenceName(pkg) {
  if (typeof pkg.license === "string") return pkg.license;
  if (typeof pkg.license?.type === "string") return pkg.license.type;
  if (Array.isArray(pkg.licenses)) return pkg.licenses.map((entry) => entry?.type).filter(Boolean).join(" OR ");
  return undefined;
}

// The package's licence files, whole, then its third-party notice and NOTICE files, each group in name order. Line
// endings are made plain; the words are never touched. With more than one file, each starts with its name.
function licenceText(name, version, dir) {
  const names = readdirSync(dir, { withFileTypes: true })
    .filter((entry) => entry.isFile())
    .map((entry) => entry.name);
  const licences = names.filter((file) => LICENCE_FILE.test(file)).sort();
  if (licences.length === 0) throw new LicencesError(`no licence file for ${name}@${version} (looked in ${dir})`);
  const files = [...licences, ...names.filter((file) => NOTICE_FILE.test(file)).sort()];
  const read = (file) => readFileSync(join(dir, file), "utf8").replace(/\r\n?/g, "\n").trim();
  if (files.length === 1) return read(files[0]);
  return files.map((file) => `File: ${file}\n${read(file)}`).join("\n\n");
}

function npmLs(root) {
  const run = spawnSync("npm ls --workspace app --omit=dev --all --json", {
    cwd: root,
    encoding: "utf8",
    shell: true,
    maxBuffer: 256 * 1024 * 1024,
  });
  try {
    return JSON.parse(run.stdout);
  } catch {
    throw new LicencesError(`npm ls gave no JSON (${(run.stderr || "no error text").trim().split("\n")[0]})`);
  }
}

// Every production package, once each, in name order.
function productionPackages(root) {
  const appDir = join(root, "app");
  const found = new Map();
  const walk = (dependencies, fromDir) => {
    for (const [name, node] of Object.entries(dependencies ?? {})) {
      if (typeof node?.version !== "string") throw new LicencesError(`npm ls lists ${name} with no version: is it installed?`);
      const { dir } = locate(name, node.version, fromDir, root);
      const key = `${name}@${node.version}`;
      if (!found.has(key)) found.set(key, { name, version: node.version, dir });
      walk(node.dependencies, dir);
    }
  };
  for (const workspace of Object.values(npmLs(root).dependencies ?? {})) walk(workspace.dependencies, appDir);
  return [...found.values()]
    .sort((a, b) => a.name.localeCompare(b.name) || a.version.localeCompare(b.version))
    .map(({ name, version, dir }) => ({
      name,
      version,
      licence: licenceName(readJson(join(dir, "package.json"), `${name}'s package.json`)),
      text: licenceText(name, version, dir),
    }));
}

function shippedExtras(root) {
  const file = join(root, "app", "scripts", "shipped-extra.json");
  if (!existsSync(file)) return [];
  const entries = readJson(file, "shipped-extra.json");
  if (!Array.isArray(entries)) throw new LicencesError("shipped-extra.json is not a list");
  return entries.map((entry, at) => {
    if (typeof entry?.package !== "string" || typeof entry.ships !== "string") {
      throw new LicencesError(`shipped-extra.json entry ${at + 1} needs a "package" and what it "ships"`);
    }
    const { dir, version } = locate(entry.package, undefined, join(root, "app"), root);
    const pkg = readJson(join(dir, "package.json"), `${entry.package}'s package.json`);
    let text = licenceText(entry.package, version, dir);
    if (entry.stopAt !== undefined) {
      const lines = text.split("\n");
      const cut = lines.indexOf(entry.stopAt);
      if (cut === -1) throw new LicencesError(`${entry.package}'s licence file has no line "${entry.stopAt}" to stop at`);
      text = lines.slice(0, cut).join("\n").trim();
    }
    return { name: entry.package, version, licence: licenceName(pkg), ships: entry.ships, text };
  });
}

function apkEntries(root) {
  const file = join(root, "app", "scripts", "apk-licences.json");
  if (!existsSync(file)) return [];
  const entries = readJson(file, "apk-licences.json");
  if (!Array.isArray(entries)) throw new LicencesError("apk-licences.json is not a list");
  return entries.map((entry, at) => {
    if (typeof entry?.name !== "string" || typeof entry.text !== "string" || entry.text.trim() === "") {
      throw new LicencesError(`apk-licences.json entry ${at + 1} needs a "name" and its licence "text"`);
    }
    for (const field of ["version", "licence"]) {
      if (entry[field] !== undefined && typeof entry[field] !== "string") {
        throw new LicencesError(`apk-licences.json entry ${at + 1}: "${field}" must be a string`);
      }
    }
    return { name: entry.name, version: entry.version, licence: entry.licence, text: entry.text.replace(/\r\n?/g, "\n").trim() };
  });
}

function section({ name, version, licence, ships, text }) {
  const head = [`${name}${version === undefined ? "" : ` ${version}`}`];
  if (licence !== undefined) head.push(`License: ${licence}`);
  if (ships !== undefined) head.push(`Ships: ${ships}`);
  return [RULE, ...head, THIN, text, ""].join("\n");
}

function render(packages, extras, apk) {
  const parts = [
    "Licences of the code and fonts Lusot is built from.",
    "Generated by app/scripts/licences.mjs from the installed packages. Each text is the package's own licence file, with its third-party notice or NOTICE file where it has one.",
    "",
    `PRODUCTION PACKAGES OF THE APP (${packages.length})`,
    "",
    ...packages.map(section),
  ];
  if (extras.length > 0) parts.push(`BUILD-TIME CODE THAT SHIPS IN THE WEB APP (${extras.length})`, "", ...extras.map(section));
  if (apk.length > 0) parts.push(`LIBRARIES IN THE ANDROID APP (${apk.length})`, "", ...apk.map(section));
  return `${parts.join("\n")}\n`;
}

function main() {
  const args = process.argv.slice(2);
  const at = args.indexOf("--root");
  const given = at === -1 ? fileURLToPath(new URL("../..", import.meta.url)) : args[at + 1];
  if (given === undefined) throw new LicencesError("--root needs a folder");
  const root = resolve(given);
  const out = join(root, "app", "public", "licences.txt");
  rmSync(out, { force: true });

  const packages = productionPackages(root);
  const extras = shippedExtras(root);
  const apk = apkEntries(root);
  mkdirSync(dirname(out), { recursive: true });
  writeFileSync(out, render(packages, extras, apk));
  const count = (n, one, many) => `${n} ${n === 1 ? one : many}`;
  console.log(
    `licences: wrote app/public/licences.txt (${count(packages.length, "package", "packages")}, ` +
      `${count(extras.length, "build-time entry", "build-time entries")}, ${count(apk.length, "APK entry", "APK entries")})`,
  );
}

try {
  main();
} catch (error) {
  if (!(error instanceof LicencesError)) throw error;
  console.error(`licences: ${error.message}`);
  process.exit(1);
}
