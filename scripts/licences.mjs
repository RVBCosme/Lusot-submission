// The licence check for shipped npm code (MS7 Task 8; spec §4.2, C816). It reads
// package-lock.json alone (lockfile v3 records each package's licence) and walks the app's and
// the API's production trees: `dependencies` and `optionalDependencies` from each workspace,
// resolved nested-first as Node does, never `devDependencies`. Each licence is classed by
// scripts/licence-policy.json, which backend/scripts/licences_py.py reads too:
//   ok      permissive licences
//   review  weak copyleft and custom licences, such as the SAM License, listed for a reviewer
//   fail    strong copyleft, non-commercial, UNLICENSED, and an empty or unknown licence
// Aliases turn the non-SPDX names that metadata really uses into SPDX ids first. Across OR the
// best alternative wins; across AND the worst part.
//
// Usage: node scripts/licences.mjs [--lock FILE] [--page FILE] [--readme FILE]
// It prints a Markdown table of package, version, licence, where it ships and its class, then
// one line per finding. --page takes MS5's built licences page (C636): app/public/licences.txt,
// or app/dist/licences.txt after a build, which `npm run build -w app` writes with
// app/scripts/licences.mjs.
// Exit codes: 0 clean, 1 a `fail` licence in a shipped tree, a direct dependency missing from
// the README's credits, or (with --page) an app package missing from the page; 2 bad usage.
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

const ROOT = fileURLToPath(new URL("..", import.meta.url));
const DEFAULT_POLICY = fileURLToPath(new URL("./licence-policy.json", import.meta.url));
const RANK = { fail: 0, review: 1, ok: 2 };

const escape = (text) => text.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
const pattern = (entry) => new RegExp(`^${entry.split("*").map(escape).join(".*")}$`, "i");

function lookup(map, key) {
  const lower = key.toLowerCase();
  for (const [name, value] of Object.entries(map ?? {})) if (name.toLowerCase() === lower) return value;
  return undefined;
}

// One licence id or name, with no operator: aliases first, then the lists, `ok` exactly.
function classifyId(id, policy) {
  const name = lookup(policy.aliases, id) ?? id;
  if (policy.ok.some((entry) => entry.toLowerCase() === name.toLowerCase())) return "ok";
  if (policy.fail.some((entry) => pattern(entry).test(name))) return "fail";
  if (policy.review.some((entry) => pattern(entry).test(name))) return "review";
  return "fail"; // unknown
}

// The class of a licence expression: 'ok', 'review' or 'fail'. An expression with no AND, OR
// or WITH is classed whole, so a name with spaces (such as "SAM License" or "SEE LICENSE IN
// ...") stays one name; anything else is parsed as an SPDX expression, and a malformed one fails.
export function classify(expr, policy) {
  const text = (expr ?? "").trim();
  if (!text) return "fail";
  const whole = lookup(policy.aliases, text) ?? text;
  if (!/\s(?:AND|OR|WITH)\s/i.test(whole)) return classifyId(whole, policy);
  // Split at the operators and parentheses only, so a name with spaces stays one leaf.
  const tokens = whole
    .split(/(\(|\)|\s+(?:AND|OR|WITH)\s+)/i)
    .map((token) => token.trim())
    .filter(Boolean);
  let at = 0;
  const peek = () => tokens[at]?.toUpperCase();
  const worst = (a, b) => (RANK[a] <= RANK[b] ? a : b);
  const best = (a, b) => (RANK[a] >= RANK[b] ? a : b);
  const atom = () => {
    if (tokens[at] === "(") {
      at++;
      const inner = orExpr();
      if (tokens[at++] !== ")") throw new SyntaxError("unclosed (");
      return inner;
    }
    const id = tokens[at++];
    if (id === undefined || id === ")" || ["AND", "OR", "WITH"].includes(id.toUpperCase())) throw new SyntaxError("expected a licence");
    if (peek() === "WITH") {
      at++;
      if (tokens[at++] === undefined) throw new SyntaxError("expected an exception");
    }
    return classifyId(id, policy); // an exception never makes a licence better
  };
  const andExpr = () => {
    let result = atom();
    while (peek() === "AND") {
      at++;
      result = worst(result, atom());
    }
    return result;
  };
  const orExpr = () => {
    let result = andExpr();
    while (peek() === "OR") {
      at++;
      result = best(result, andExpr());
    }
    return result;
  };
  try {
    const result = orExpr();
    return at === tokens.length ? result : "fail";
  } catch (error) {
    if (error instanceof SyntaxError) return "fail";
    throw error;
  }
}

const nameFromPath = (path) => path.slice(path.lastIndexOf("node_modules/") + "node_modules/".length);

// Where Node finds `name` from the package at `from`: its own node_modules, then each folder
// above, up to the root's. A workspace (such as "app") looks in its own folder, then the root's.
function resolve(lock, from, name) {
  for (let base = from; ; ) {
    const candidate = `${base ? `${base}/` : ""}node_modules/${name}`;
    if (lock.packages[candidate]) return candidate;
    if (!base) return null;
    const at = base.lastIndexOf("/node_modules/");
    base = at >= 0 ? base.slice(0, at) : ""; // "node_modules/a" and a workspace's folder end at the root
  }
}

// The packages that ship from one workspace, keyed `name@version`. The root, the workspaces
// and their link entries carry no licence and are left out; a link is followed to its target.
export function productionTree(lock, workspace) {
  const tree = new Map();
  const seen = new Set();
  const walk = (path) => {
    if (seen.has(path)) return;
    seen.add(path);
    const entry = lock.packages[path];
    const isPackage = path.includes("node_modules/") && !entry.link;
    if (entry.link) return walk(entry.resolved);
    if (isPackage) {
      const name = entry.name ?? nameFromPath(path);
      tree.set(`${name}@${entry.version}`, { name, version: entry.version, license: entry.license ?? "" });
    }
    const required = Object.keys(entry.dependencies ?? {});
    const optional = Object.keys(entry.optionalDependencies ?? {});
    for (const dep of [...required, ...optional]) {
      const found = resolve(lock, path, dep);
      if (found) walk(found);
      else if (!optional.includes(dep)) throw new Error(`${dep}, a dependency of ${path || "the root"}, is not in the lockfile`);
    }
  };
  if (!lock.packages?.[workspace]) throw new Error(`the lockfile has no workspace ${workspace}`);
  walk(workspace);
  return tree;
}

// The README's credits section, from its "## Credits" heading to the next heading of that level.
function creditsSection(readme) {
  const start = readme.search(/^## Credits\s*$/m);
  if (start < 0) return "";
  const rest = readme.slice(start + 1);
  const end = rest.search(/^## /m);
  return end < 0 ? rest : rest.slice(0, end);
}

const mentions = (text, words) => new RegExp(`(?<![A-Za-z0-9_-])${escape(words)}(?![A-Za-z0-9_-])`, "i").test(text);

// The names the README's credits don't mention. `credits` maps a package, or a scope as
// `@scope/*`, to the credit that covers it, such as "react-dom" to "React".
export function missingCredits(names, readme, credits = {}) {
  const section = creditsSection(readme);
  return names.filter((name) => {
    if (mentions(section, name)) return false;
    const scope = name.startsWith("@") ? `${name.split("/")[0]}/*` : undefined;
    const credit = lookup(credits, name) ?? (scope && lookup(credits, scope));
    return !(credit && mentions(section, credit));
  });
}

// The names on MS5's licences page (C636): the first line after each rule of `=`, which holds
// the name and, after a space, the version.
export function pageNames(page) {
  const lines = page.replace(/\r\n?/g, "\n").split("\n");
  const names = [];
  for (let i = 0; i + 1 < lines.length; i++) {
    if (/^={3,}$/.test(lines[i]) && lines[i + 1].trim()) names.push(lines[i + 1].trim().replace(/ [^ ]*\d[^ ]*$/, ""));
  }
  return names;
}

export function missingFromPage(names, page) {
  const listed = new Set(pageNames(page));
  return names.filter((name) => !listed.has(name));
}

function parseArgs(argv) {
  const opts = { lock: `${ROOT}package-lock.json`, readme: `${ROOT}README.md`, page: undefined, policy: DEFAULT_POLICY };
  for (let i = 0; i < argv.length; i++) {
    const key = { "--lock": "lock", "--page": "page", "--readme": "readme", "--policy": "policy" }[argv[i]];
    if (!key || i + 1 >= argv.length) throw new Error(`usage: node scripts/licences.mjs [--lock FILE] [--page FILE] [--readme FILE]`);
    opts[key] = argv[++i];
  }
  return opts;
}

export function main(argv, out = console.log) {
  let opts;
  let lock;
  let policy;
  let readme;
  let page;
  try {
    opts = parseArgs(argv);
    lock = JSON.parse(readFileSync(opts.lock, "utf8"));
    policy = JSON.parse(readFileSync(opts.policy, "utf8"));
    readme = readFileSync(opts.readme, "utf8");
    page = opts.page === undefined ? undefined : readFileSync(opts.page, "utf8");
  } catch (error) {
    console.error(error.message);
    return 2;
  }
  const rows = new Map();
  const direct = new Set();
  const appNames = new Set();
  // The workspaces the lock's root lists: "app" and "backend/api" here.
  for (const workspace of lock.packages?.[""]?.workspaces ?? []) {
    const where = workspace.split("/").at(-1);
    for (const pkg of productionTree(lock, workspace).values()) {
      const key = `${pkg.name}@${pkg.version}`;
      const row = rows.get(key) ?? { ...pkg, ships: [] };
      row.ships.push(where);
      rows.set(key, row);
      if (where === "app") appNames.add(pkg.name);
    }
    const entry = lock.packages[workspace];
    for (const dep of [...Object.keys(entry.dependencies ?? {}), ...Object.keys(entry.optionalDependencies ?? {})]) {
      if (resolve(lock, workspace, dep)) direct.add(dep);
    }
  }

  const sorted = [...rows.values()].sort((a, b) => a.name.localeCompare(b.name) || a.version.localeCompare(b.version));
  out("| package | version | licence | ships in | class |");
  out("|---|---|---|---|---|");
  const findings = [];
  for (const row of sorted) {
    const cls = classify(row.license, policy);
    out(`| ${row.name} | ${row.version} | ${row.license || "(none)"} | ${row.ships.join(", ")} | ${cls} |`);
    if (cls === "fail") findings.push(`FAIL: ${row.name}@${row.version} (${row.license || "no licence"}) ships in ${row.ships.join(", ")}`);
    else if (cls === "review") out(`REVIEW: ${row.name}@${row.version} (${row.license})`);
  }
  for (const name of missingCredits([...direct].sort(), readme, policy.credits)) findings.push(`NOT IN THE README'S CREDITS: ${name}`);
  if (page !== undefined) for (const name of missingFromPage([...appNames].sort(), page)) findings.push(`NOT ON THE LICENCES PAGE: ${name}`);
  out("");
  for (const line of findings) out(line);
  out(`licences: ${sorted.length} shipped packages, ${direct.size} direct dependencies${page === undefined ? "" : ", checked against the licences page"}: ${findings.length ? `${findings.length} finding(s)` : "clean"}`);
  return findings.length ? 1 : 0;
}

if (import.meta.main === undefined) throw new Error("scripts/licences.mjs needs Node 22.18 or newer");
if (import.meta.main) process.exitCode = main(process.argv.slice(2));
