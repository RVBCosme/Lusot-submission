// The licence check for shipped npm code (MS7 Task 8; spec §4.2, C816). It reads
// package-lock.json alone (lockfile v3 records each package's licence) and walks the app's and
// the API's production trees: `dependencies` and `optionalDependencies` from each workspace,
// resolved nested-first as Node does, never `devDependencies`. The build-time code MS5 lists
// in app/scripts/shipped-extra.json, which ships in the page from a development dependency,
// is classed too. Each licence is classed by scripts/licence-policy.json, which
// backend/scripts/licences_py.py reads too:
//   ok      permissive licences
//   review  weak copyleft and custom licences, such as the SAM License, listed for a reviewer
//   fail    strong copyleft, non-commercial, UNLICENSED, and an empty or unknown licence
// Aliases turn the non-SPDX names that metadata really uses into SPDX ids first. Operators are
// upper case, as SPDX writes them; across OR the best alternative wins, across AND the worst
// part, and WITH takes only an exception the policy lists. Anything outside printable ASCII
// fails, so the two tools can't read one string two ways.
//
// Usage: node scripts/licences.mjs [--lock FILE] [--page FILE] [--readme FILE] [--extra FILE]
// It prints a Markdown table of package, version, licence, where it ships and its class, then
// one line per finding. --page takes MS5's built licences page (C636): app/public/licences.txt,
// or app/dist/licences.txt after a build, which `npm run build -w app` writes with
// app/scripts/licences.mjs. Each entry there is a rule of 24 `=`, a `name version` line, any
// `License:` and `Ships:` lines, and a rule of 24 `-`.
// Exit codes: 0 clean, 1 a `fail` licence in shipped code, a direct dependency the README's
// credits table doesn't name, or (with --page) an app package missing from the page at its
// locked version; 2 bad usage, or a lockfile this tool can't walk.
import { existsSync, readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = fileURLToPath(new URL("..", import.meta.url));
const DEFAULT_POLICY = fileURLToPath(new URL("./licence-policy.json", import.meta.url));
const RANK = { fail: 0, review: 1, ok: 2 };
const OPERATOR = /\s(?:AND|OR|WITH)\s/;
const PRINTABLE = /^[\x20-\x7e\t]*$/;
// MS5's page format (app/scripts/licences.mjs).
const RULE = "=".repeat(24);
const THIN = "-".repeat(24);

const escape = (text) => text.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
const pattern = (entry) => new RegExp(`^${entry.split("*").map(escape).join(".*")}$`, "i");
const worst = (a, b) => (RANK[a] <= RANK[b] ? a : b);
const best = (a, b) => (RANK[a] >= RANK[b] ? a : b);

function entryOf(map, key) {
  const lower = key.toLowerCase();
  return Object.entries(map ?? {}).find(([name]) => name.toLowerCase() === lower);
}

// One licence name, with no operator, past any aliases: `ok` exactly, then the lists.
function classifyName(name, policy) {
  let text = name;
  while (/^\(.*\)$/.test(text)) text = text.slice(1, -1).trim(); // "(MIT)" is MIT
  if (policy.ok.some((entry) => entry.toLowerCase() === text.toLowerCase())) return "ok";
  if (policy.fail.some((entry) => pattern(entry).test(text))) return "fail";
  if (policy.review.some((entry) => pattern(entry).test(text))) return "review";
  return "fail"; // unknown
}

// The tokens of an expression: operators, grouping parentheses, and names. A name keeps its
// spaces, and its own parentheses, as in "Mozilla Public License 2.0 (MPL 2.0)": a "(" groups
// only where a name would start, and a ")" groups only when the name holds no open "(".
export function tokenize(text) {
  const tokens = [];
  let leaf = "";
  let own = 0;
  const flush = () => {
    if (leaf.trim()) tokens.push(leaf.trim());
    leaf = "";
    own = 0;
  };
  for (let i = 0; i < text.length; ) {
    const op = own === 0 ? /^\s+(AND|OR|WITH)(?=\s)/.exec(text.slice(i)) : null;
    if (op) {
      flush();
      tokens.push(op[1]);
      i += op[0].length;
      continue;
    }
    const ch = text[i++];
    if (ch === "(" && !leaf.trim()) tokens.push("(");
    else if (ch === ")" && own === 0) {
      flush();
      tokens.push(")");
    } else {
      if (ch === "(") own++;
      if (ch === ")") own--;
      leaf += ch;
    }
  }
  flush();
  return tokens;
}

function parse(text, policy, pkg) {
  const tokens = tokenize(text);
  let at = 0;
  const exceptions = (policy.exceptions ?? []).map((e) => e.toLowerCase());
  const atom = () => {
    if (tokens[at] === "(") {
      at++;
      const inner = either();
      if (tokens[at++] !== ")") throw new SyntaxError("unclosed (");
      return inner;
    }
    const id = tokens[at++];
    if (id === undefined || id === ")" || ["AND", "OR", "WITH"].includes(id)) throw new SyntaxError("expected a licence");
    if (tokens[at] === "WITH") {
      at++;
      const exception = tokens[at++];
      if (exception === undefined || !exceptions.includes(exception.toLowerCase())) throw new SyntaxError("not a listed exception");
    }
    return classifyLeaf(id, policy, pkg); // an exception never makes a licence better
  };
  const both = () => {
    let result = atom();
    while (tokens[at] === "AND") {
      at++;
      result = worst(result, atom());
    }
    return result;
  };
  const either = () => {
    let result = both();
    while (tokens[at] === "OR") {
      at++;
      result = best(result, both());
    }
    return result;
  };
  try {
    const result = either();
    return at === tokens.length ? result : "fail";
  } catch (error) {
    if (error instanceof SyntaxError) return "fail";
    throw error;
  }
}

// The class of a licence expression: 'ok', 'review' or 'fail'. An expression with no AND, OR
// or WITH is one name, so a name with spaces (such as "SAM License" or "SEE LICENSE IN ...")
// stays whole; anything else is parsed as an SPDX expression, and a malformed one fails. An
// alias that policy.aliasPackages ties to named packages gives any other `pkg` review at best.
export function classify(expr, policy, pkg) {
  if (!PRINTABLE.test(expr ?? "")) return "fail"; // before trim, which drops a BOM in JS only
  const text = (expr ?? "").trim();
  if (!text) return "fail";
  if (entryOf(policy.aliases, text) || !OPERATOR.test(text)) return classifyLeaf(text, policy, pkg);
  return parse(text, policy, pkg);
}

// One name: through its alias, if it has one, but never parsed again, so a name that holds an
// operator inside its own parentheses is unknown rather than read twice.
function classifyLeaf(name, policy, pkg) {
  const alias = entryOf(policy.aliases, name);
  let result = classifyName(alias ? alias[1] : name, policy);
  const only = alias && entryOf(policy.aliasPackages, alias[0]);
  if (only && !only[1].includes(pkg)) result = worst(result, "review");
  return result;
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

class LockError extends Error {}

// The packages that ship from one workspace, keyed `name@version`. The root, the workspaces
// and their link entries carry no licence and are left out; a link is followed to its target.
export function productionTree(lock, workspace) {
  const tree = new Map();
  const seen = new Set();
  const walk = (path) => {
    if (seen.has(path)) return;
    seen.add(path);
    const entry = lock.packages[path];
    if (!entry) throw new LockError(`the lockfile has no entry ${path}`);
    if (entry.link) return walk(entry.resolved);
    if (path.includes("node_modules/")) {
      const name = entry.name ?? nameFromPath(path);
      tree.set(`${name}@${entry.version}`, { name, version: entry.version, license: entry.license ?? "" });
    }
    const required = Object.keys(entry.dependencies ?? {});
    const optional = Object.keys(entry.optionalDependencies ?? {});
    for (const dep of [...required, ...optional]) {
      const found = resolve(lock, path, dep);
      if (found) walk(found);
      else if (!optional.includes(dep)) throw new LockError(`${dep}, a dependency of ${path || "the root"}, is not in the lockfile`);
    }
  };
  if (!lock.packages?.[workspace]) throw new LockError(`the lockfile has no workspace ${workspace}`);
  walk(workspace);
  return tree;
}

// The visible text of the first column of the README's credits table, one cell per row: links
// keep their text and lose their address, and code marks are dropped.
export function creditCells(readme) {
  const start = readme.search(/^## Credits\s*$/m);
  if (start < 0) return [];
  const rest = readme.slice(start + 1);
  const end = rest.search(/^## /m);
  const section = end < 0 ? rest : rest.slice(0, end);
  return section
    .split("\n")
    .filter((line) => line.startsWith("|"))
    .map((line) => line.split("|")[1] ?? "")
    .filter((cell) => !/^\s*:?-{3,}:?\s*$/.test(cell) && cell.trim() !== "Component")
    .map((cell) => cell.replace(/\[([^\]]*)\]\([^)]*\)/g, "$1").replace(/`/g, "").replace(/https?:\/\/\S+/g, "").trim());
}

const mentions = (text, words) => new RegExp(`(?<![A-Za-z0-9_@/-])${escape(words)}(?![A-Za-z0-9_-])`, "i").test(text);

// The names the credits table's Component cells don't name. `credits` maps a package, or a
// scope as `@scope/*`, to the credit that covers it, such as "react-dom" to "React".
export function missingCredits(names, readme, credits = {}) {
  const cells = creditCells(readme).join("\n");
  return names.filter((name) => {
    if (mentions(cells, name)) return false;
    const scope = name.startsWith("@") ? `${name.split("/")[0]}/*` : undefined;
    const credit = entryOf(credits, name)?.[1] ?? (scope && entryOf(credits, scope)?.[1]);
    return !(credit && mentions(cells, credit));
  });
}

// The entries on MS5's licences page (C636), each `{name, version}`; an entry the Android
// app lists without a version has `version: undefined`.
export function pageEntries(page) {
  const lines = page.replace(/\r\n?/g, "\n").split("\n");
  const entries = [];
  for (let i = 0; i + 2 < lines.length; i++) {
    if (lines[i] !== RULE || !lines[i + 1].trim()) continue;
    let j = i + 2;
    while (j < lines.length && /^(License|Ships): /.test(lines[j])) j++;
    if (lines[j] !== THIN) continue;
    const head = lines[i + 1].trim();
    const last = head.lastIndexOf(" ");
    const version = last > 0 && /\d/.test(head.slice(last + 1)) ? head.slice(last + 1) : undefined;
    entries.push({ name: version === undefined ? head : head.slice(0, last), version });
  }
  return entries;
}

export function pageNames(page) {
  return pageEntries(page).map((e) => e.name);
}

// The items the page leaves out. An item is a name, or `{name, version}`, which must be on
// the page at that version, so a page built from an older lock doesn't pass.
export function missingFromPage(items, page) {
  const listed = new Set(pageEntries(page).flatMap((e) => [e.name, `${e.name} ${e.version}`]));
  return items
    .map((item) => (typeof item === "string" ? item : `${item.name} ${item.version}`))
    .filter((label) => !listed.has(label));
}

function parseArgs(argv) {
  const opts = { lock: join(ROOT, "package-lock.json"), readme: join(ROOT, "README.md"), page: undefined, policy: DEFAULT_POLICY, extra: undefined };
  const keys = { "--lock": "lock", "--page": "page", "--readme": "readme", "--policy": "policy", "--extra": "extra" };
  for (let i = 0; i < argv.length; i++) {
    const key = keys[argv[i]];
    if (!key || i + 1 >= argv.length) throw new LockError("usage: node scripts/licences.mjs [--lock FILE] [--page FILE] [--readme FILE] [--extra FILE]");
    opts[key] = argv[++i];
  }
  // MS5's list of build-time code that ships, beside the lockfile's app workspace.
  opts.extra ??= join(dirname(opts.lock), "app", "scripts", "shipped-extra.json");
  return opts;
}

function readJson(path, what) {
  try {
    return JSON.parse(readFileSync(path, "utf8"));
  } catch {
    throw new LockError(`cannot read ${what} as JSON`);
  }
}

export function main(argv, out = console.log, err = console.error) {
  try {
    return run(argv, out);
  } catch (error) {
    if (!(error instanceof LockError)) throw error;
    err(`licences: ${error.message}`);
    return 2;
  }
}

function run(argv, out) {
  const opts = parseArgs(argv);
  const lock = readJson(opts.lock, "the lockfile");
  const policy = readJson(opts.policy, "the policy");
  let readme;
  let page;
  try {
    readme = readFileSync(opts.readme, "utf8");
    page = opts.page === undefined ? undefined : readFileSync(opts.page, "utf8");
  } catch {
    throw new LockError("cannot read the README or the page");
  }
  const rows = new Map();
  const add = (pkg, where) => {
    const key = `${pkg.name}@${pkg.version}`;
    const row = rows.get(key) ?? { ...pkg, ships: [] };
    if (!row.ships.includes(where)) row.ships.push(where);
    rows.set(key, row);
  };
  const direct = new Set();
  const appItems = [];
  // The workspaces the lock's root lists: "app" and "backend/api" here.
  for (const workspace of lock.packages?.[""]?.workspaces ?? []) {
    const where = workspace.split("/").at(-1);
    for (const pkg of productionTree(lock, workspace).values()) {
      add(pkg, where);
      if (where === "app") appItems.push({ name: pkg.name, version: pkg.version });
    }
    const entry = lock.packages[workspace];
    for (const dep of [...Object.keys(entry.dependencies ?? {}), ...Object.keys(entry.optionalDependencies ?? {})]) {
      const found = resolve(lock, workspace, dep);
      if (found && !lock.packages[found].link) direct.add(dep); // a workspace needs no credit
    }
  }
  if (existsSync(opts.extra)) {
    const extras = readJson(opts.extra, "shipped-extra.json");
    if (!Array.isArray(extras)) throw new LockError("shipped-extra.json is not a list");
    for (const { package: name } of extras) {
      const entry = lock.packages[`node_modules/${name}`];
      if (!entry) throw new LockError(`${name}, in shipped-extra.json, is not in the lockfile`);
      add({ name, version: entry.version, license: entry.license ?? "" }, "app (build-time code)");
      appItems.push({ name, version: entry.version });
    }
  }

  const sorted = [...rows.values()].sort((a, b) => a.name.localeCompare(b.name) || a.version.localeCompare(b.version));
  out("| package | version | licence | ships in | class |");
  out("|---|---|---|---|---|");
  const findings = [];
  for (const row of sorted) {
    const cls = classify(row.license, policy, row.name);
    out(`| ${row.name} | ${row.version} | ${row.license || "(none)"} | ${row.ships.join(", ")} | ${cls} |`);
    if (cls === "fail") findings.push(`FAIL: ${row.name}@${row.version} (${row.license || "no licence"}) ships in ${row.ships.join(", ")}`);
    else if (cls === "review") out(`REVIEW: ${row.name}@${row.version} (${row.license})`);
  }
  for (const name of missingCredits([...direct].sort(), readme, policy.credits)) findings.push(`NOT IN THE README'S CREDITS: ${name}`);
  if (page !== undefined) for (const label of missingFromPage(appItems, page)) findings.push(`NOT ON THE LICENCES PAGE: ${label}`);
  out("");
  for (const line of findings) out(line);
  const checked = page === undefined ? "" : ", checked against the licences page";
  out(`licences: ${sorted.length} shipped packages, ${direct.size} direct dependencies${checked}: ${findings.length ? `${findings.length} finding(s)` : "clean"}`);
  return findings.length ? 1 : 0;
}

if (import.meta.main === undefined) throw new Error("scripts/licences.mjs needs Node 22.18 or newer");
if (import.meta.main) process.exitCode = main(process.argv.slice(2));
