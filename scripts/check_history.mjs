// The history scan (MS7 Task 7a; spec §4.2, C829; MS8's C903, C922). It reads every blob,
// commit message and annotated tag message reachable from the refs that will go public, not
// only the working tree, for what must never be published:
// - twelve-digit: a 12-digit run (an AWS account ID), plain or in the console's dashed groups,
//   as the account-ID scan finds it; twelve-digit-path and email-path flag the same in a path
// - plan-24 and plan-lines: plan §24's numbers, and more than MAX_SHARED_LINES of the plan's
//   long lines, as scripts/check_no_plan_leak.py finds them, read from the plan at run time
// - email: any address but no-reply ones, the example.com, .org and .net placeholders, and a
//   git SSH remote (git@host:)
// - console-link: an AWS console or sign-in link, or a dev.meta.ai link outside its public
//   /docs and /support pages. A link is a URL (with a scheme, or starting `//`), or a host
//   followed by a path, query or fragment; a bare host name, as in a rule's description, is
//   not one. A sign-in host with an account alias in front is flagged in any form.
// - never-commit: env files (but .env.example), samconfig.toml, keystores, APKs, archives
// - sealed-path: any path with a part named `sealed`. It is found by its path alone: a blob
//   ever seen at such a path is never read, and it is reported by commit and count, never
//   by name.
// - image: an image outside the allow-list's path globs
// It prints commits, paths and counts, never the matched text, with any 12-digit run in a
// path masked. Exceptions are allowed only by exact blob id and rule, each with a written
// reason, in scripts/history-allow.json. The identity domains and the Claude-Session count
// are printed for MS7-Q8 and MS8-Q1, and don't change the exit code.
//
// Usage: node scripts/check_history.mjs [--refs main]... [--plan PATH] [--allow FILE] [--export]
// --refs takes a branch, tag or commit, or --all, --branches or --tags; it can repeat.
// Without the plan: under CI=true the plan rules are skipped with a notice; anywhere else, or
// with --export, or with a plan path given on purpose, the scan fails closed. --export also
// fails on a plan whose §24 holds no number, and uses only the committed allow-list.
// Exit codes: 0 clean, 1 a hit that isn't allow-listed (a sealed path included), 2 bad usage,
// a bad allow-list, a missing or unusable plan, a git failure, or a blob git can't read.
import { execFileSync } from "node:child_process";
import { existsSync, readFileSync } from "node:fs";
import { posix } from "node:path";
import { fileURLToPath } from "node:url";

import { decodeText, hasTwelveDigits, isLockfile, maskDigits } from "./check_account_ids.mjs";

// The plan-leak check's constants and plan path (scripts/check_no_plan_leak.py).
export const DEFAULT_PLAN = String.raw`C:\Systems\Lusot\Lusot-Staging\docs\plan\lusot-build-plan.txt`;
export const MIN_LINE = 60;
export const MAX_SHARED_LINES = 5;
const ACCOUNT_SECTION = /^\s*24\. Manual actions/m;
const NEXT_SECTION = /^\s*25\. /gm;
const LONG_NUMBER = /(?<!\d)\d{8,}(?!\d)/g;
// Python's str.splitlines() boundaries.
const LINE_BREAK = /\r\n|[\n\r\v\f\x1c-\x1e\x85\u2028\u2029]/;

const DEFAULT_ALLOW = fileURLToPath(new URL("./history-allow.json", import.meta.url));
const CONTENT_RULES = ["twelve-digit", "plan-24", "plan-lines", "email", "console-link"];
const ALLOWABLE_RULES = new Set([...CONTENT_RULES, "never-commit", "image"]);
const REF_OPTIONS = new Set(["--all", "--branches", "--tags"]);
const BATCH = 256; // blobs per `git cat-file --batch` call
// Fixed in every `git log`, so the user's git config can't change what is read: no signature
// lines, no colour, no mailmap rewriting of the addresses that would be published. The raw
// log adds the root commit's diff and each merge diffed against each parent; the others show
// no diff at all.
const LOG_FIXED = ["--no-show-signature", "--no-color", "--no-mailmap"];
const RAW_FIXED = [...LOG_FIXED, "--root", "--diff-merges=separate"];
const NO_DIFF = [...LOG_FIXED, "--no-patch"];

const EMAIL = /(?<![A-Za-z0-9._%+-])([A-Za-z0-9._%+-]+)@((?:[A-Za-z0-9-]+\.)+[A-Za-z]{2,})(?![A-Za-z0-9-])/g;
const PLACEHOLDER_DOMAINS = ["example.com", "example.org", "example.net"];
// A host name ends where no letter, digit or hyphen follows, and no dot that starts a label.
const HOST_END = String.raw`(?![a-z0-9-]|\.[a-z0-9])`;
const AWS_HOST = String.raw`(?:[a-z0-9-]+\.)*(?:console|signin)\.aws\.amazon\.com${HOST_END}`;
const META_PUBLIC_PAGE = String.raw`(?:docs|support)(?![a-z0-9_-]|\.[a-z0-9])`;
const URL_START = String.raw`(?:https?:)?\/\/`; // a scheme, or a protocol-relative link
const BARE_START = String.raw`(?<![a-z0-9_./@-])`;
const CONSOLE_LINKS = [
  new RegExp(`${URL_START}${AWS_HOST}`, "i"),
  new RegExp(String.raw`${BARE_START}${AWS_HOST}[\/?#]`, "i"),
  new RegExp(String.raw`${URL_START}dev\.meta\.ai${HOST_END}(?!\/${META_PUBLIC_PAGE})`, "i"),
  new RegExp(String.raw`${BARE_START}dev\.meta\.ai[\/?#](?!${META_PUBLIC_PAGE})`, "i"),
];
// <labels>.signin.aws.amazon.com in any form: the labels are an account alias or ID, unless
// they are only a region.
const SIGNIN_LABELS = new RegExp(String.raw`(?<![a-z0-9_.-])((?:[a-z0-9-]+\.)+)signin\.aws\.amazon\.com${HOST_END}`, "gi");
const REGION = /^[a-z]{2}(?:-gov)?-[a-z]+-\d$/;
const NEVER_COMMIT = /^(?:samconfig\.toml|.*\.(?:jks|keystore|apk|aab|7z|zip|tar|gz|rar))$/;
const ENV_FILE = /^\.env(?:\..+)?$/;
const IMAGE = /\.(?:png|jpe?g|gif|webp|bmp|tiff?|heic|avif|ico)$/;

class UsageError extends Error {}
// A git command that failed, or git output this scan can't parse: exit 2, naming only the
// subcommand and its exit status, never git's output.
class GitError extends Error {}

// A git runner: `git(args, input)` returns git's stdout as a Buffer. Tests pass a spy.
export function gitRunner(cwd, env = process.env) {
  return (args, input) => {
    try {
      return execFileSync("git", args, { cwd, env, input, maxBuffer: 1 << 30, stdio: ["pipe", "pipe", "pipe"] });
    } catch (error) {
      throw new GitError(`git ${args[0]} failed (${error.status === undefined ? error.code : `exit ${error.status}`})`);
    }
  };
}

function revArgs(refs) {
  return [...refs.filter((r) => REF_OPTIONS.has(r)), "--end-of-options", ...refs.filter((r) => !REF_OPTIONS.has(r)), "--"];
}

// Windows opens `sealed.`, `sealed ` and `sealed::$INDEX_ALLOCATION` as the same folder, so
// a part counts as `sealed` after any stream suffix and trailing dots and spaces are dropped.
function isSealedPart(part) {
  return part.split(":")[0].replace(/[. ]+$/, "").toLowerCase() === "sealed";
}

export function isSealedPath(path) {
  return path.split(/[\\/]/).some(isSealedPart);
}

export function pathRule(path, allow) {
  if (isSealedPath(path)) return "sealed-path";
  const name = posix.basename(path).toLowerCase();
  if ((ENV_FILE.test(name) && name !== ".env.example") || NEVER_COMMIT.test(name)) return "never-commit";
  if (IMAGE.test(name) && !allow.images.some((glob) => posix.matchesGlob(path, glob))) return "image";
  return null;
}

function isPlaceholder(local, domain, after) {
  const user = local.toLowerCase();
  const host = domain.toLowerCase();
  if (user === "noreply" || user === "no-reply") return true;
  if (host === "users.noreply.github.com") return true;
  if (user === "git" && after === ":") return true; // an SSH remote, git@host:owner/repo
  return PLACEHOLDER_DOMAINS.some((d) => host === d || host.endsWith(`.${d}`));
}

function hasEmail(text) {
  for (const m of text.matchAll(EMAIL)) {
    if (!isPlaceholder(m[1], m[2], text[m.index + m[0].length])) return true;
  }
  return false;
}

function hasConsoleLink(text) {
  if (CONSOLE_LINKS.some((re) => re.test(text))) return true;
  for (const m of text.matchAll(SIGNIN_LABELS)) if (!REGION.test(m[1].slice(0, -1).toLowerCase())) return true;
  return false;
}

// The content rules a text breaks, each once. `rules.planNumbers` and `rules.planLines` are
// null when the plan rules are skipped; `rules.skipTwelve` is set for lockfiles (R15).
export function scanText(text, rules = {}) {
  const hits = [];
  if (!rules.skipTwelve && hasTwelveDigits(text)) hits.push({ rule: "twelve-digit" });
  if (rules.planNumbers?.some((n) => text.includes(n))) hits.push({ rule: "plan-24" });
  if (rules.planLines) {
    let shared = 0;
    for (const line of rules.planLines) if (text.includes(line) && ++shared > MAX_SHARED_LINES) break;
    if (shared > MAX_SHARED_LINES) hits.push({ rule: "plan-lines" });
  }
  if (hasEmail(text)) hits.push({ rule: "email" });
  if (hasConsoleLink(text)) hits.push({ rule: "console-link" });
  return hits;
}

export function allowed(hit, allow) {
  return allow.blobs.some((entry) => entry.blob === hit.blob && entry.rule === hit.rule);
}

const OBJECT_ID = /^(?:[0-9a-f]{40}|[0-9a-f]{64})$/;

// Every blob a commit reachable from `refs` adds or changes, with that commit and path, oldest
// first. Each merge is diffed against each parent, so a blob only a merge adds is found too.
// The output is walked field by field: a commit is `\x01` and its id, and each raw entry is
// its `:modes ids status` field, then its path, taken whole, whatever bytes it holds.
function logOccurrences(refs, git) {
  const fields = git(["log", "-z", "--raw", "--no-abbrev", "--no-renames", "--reverse", ...RAW_FIXED, "--format=%x01%H", ...revArgs(refs)])
    .toString("utf8")
    .split("\0");
  const occurrences = [];
  let commit = null;
  for (let i = 0; i < fields.length; i++) {
    const field = fields[i].replace(/^\n/, "");
    if (field.startsWith(":")) {
      const path = fields[++i];
      const [, dstMode, , blob, status] = field.slice(1).split(" ");
      if (commit === null || path === undefined || !OBJECT_ID.test(blob ?? "")) throw new GitError("git log gave output this scan can't read");
      if (status === "D" || dstMode === "160000" || /^0+$/.test(blob)) continue;
      occurrences.push({ blob, path, commit });
      continue;
    }
    const id = field.trim();
    if (!id) continue;
    if (!id.startsWith("\x01") || !OBJECT_ID.test(id.slice(1))) throw new GitError("git log gave output this scan can't read");
    commit = id.slice(1);
  }
  return occurrences;
}

function readBlobs(ids, git) {
  const out = git(["cat-file", "--batch"], ids.join("\n") + "\n");
  const blobs = new Map();
  let at = 0;
  while (at < out.length) {
    const end = out.indexOf(0x0a, at);
    if (end < 0) throw new GitError("git cat-file gave output this scan can't read");
    const [id, type, size] = out.subarray(at, end).toString("utf8").split(" ");
    at = end + 1;
    if (type === "missing") continue;
    blobs.set(id, out.subarray(at, at + Number(size)));
    at += Number(size) + 1;
  }
  const missing = ids.filter((id) => !blobs.has(id)).length;
  if (missing) throw new GitError(`git cat-file couldn't read ${missing} blob(s): is this a partial clone?`);
  return blobs;
}

// Each blob once, with the first commit and path that added it, and its bytes. A blob that is
// ever at a sealed path comes back with `bytes: null`: it is never asked of git.
function* readEntries(occurrences, git) {
  const sealed = new Set(occurrences.filter((o) => isSealedPath(o.path)).map((o) => o.blob));
  const firsts = new Map();
  for (const o of occurrences) if (!firsts.has(o.blob)) firsts.set(o.blob, o);
  const pending = [...firsts.values()];
  for (let start = 0; start < pending.length; start += BATCH) {
    const batch = pending.slice(start, start + BATCH);
    const ids = batch.filter((e) => !sealed.has(e.blob)).map((e) => e.blob);
    const bytes = ids.length ? readBlobs(ids, git) : new Map();
    for (const e of batch) yield { ...e, bytes: sealed.has(e.blob) ? null : bytes.get(e.blob) };
  }
}

export function historyEntries(refs, git) {
  return readEntries(logOccurrences(refs, git), git);
}

function commitMessages(refs, git) {
  const out = git(["log", "-z", ...NO_DIFF, "--format=%H%n%B", ...revArgs(refs)]).toString("utf8");
  return out
    .split("\0")
    .filter((record) => record.trim())
    .map((record) => {
      const newline = record.indexOf("\n");
      return { commit: record.slice(0, newline).trim(), message: record.slice(newline + 1) };
    });
}

// The annotated tags among `refs` (all of them with --all or --tags): their tag object's id,
// and its tagger address.
function annotatedTags(refs, git) {
  const allTags = refs.includes("--all") || refs.includes("--tags");
  const out = git(["for-each-ref", "--format=%(refname)%00%(objecttype)%00%(objectname)%00%(taggeremail)", "refs/tags"]).toString("utf8");
  return out
    .split("\n")
    .filter(Boolean)
    .map((line) => line.split("\0"))
    .filter(([refname, type]) => type === "tag" && (allTags || refs.includes(refname) || refs.includes(refname.replace(/^refs\/tags\//, ""))))
    .map(([, , id, email]) => ({ id, email }));
}

// A tag object's message: what follows its header's first blank line.
function tagMessages(tags, git) {
  return tags.map(({ id }) => {
    const text = git(["cat-file", "tag", id]).toString("utf8");
    const blank = text.indexOf("\n\n");
    return { tag: id, message: blank < 0 ? "" : text.slice(blank + 2) };
  });
}

function domainOf(address) {
  const at = address.lastIndexOf("@");
  return at < 0 ? "(no domain)" : address.slice(at + 1).replace(/>$/, "").toLowerCase();
}

function bump(map, key) {
  map.set(key, (map.get(key) ?? 0) + 1);
}

export function identityDomains(refs, git) {
  const author = new Map();
  const committer = new Map();
  const tagger = new Map();
  const out = git(["log", ...NO_DIFF, "--format=%ae%x00%ce", ...revArgs(refs)]).toString("utf8");
  for (const line of out.split("\n").filter(Boolean)) {
    const [a, c] = line.split("\0");
    bump(author, domainOf(a));
    bump(committer, domainOf(c));
  }
  for (const { email } of annotatedTags(refs, git)) bump(tagger, domainOf(email));
  return { author, committer, tagger };
}

function sessionCount(messages) {
  return messages.filter((m) => /^Claude-Session:/m.test(m.message)).length;
}

export function claudeSessionCount(refs, git) {
  return sessionCount(commitMessages(refs, git));
}

// Reads the plan as check_no_plan_leak.py does. Returns null when the plan rules are skipped.
function loadPlan(explicit, defaultPlan, env, exportMode, err) {
  const path = explicit ?? defaultPlan;
  if (!existsSync(path)) {
    if (explicit === undefined && env.CI === "true" && !exportMode) {
      err(`plan text not found at ${maskDigits(path)}; skipping the plan rules (CI=true)`);
      return null;
    }
    throw new UsageError(`plan text not found at ${maskDigits(path)}`);
  }
  let plan;
  try {
    plan = new TextDecoder("utf-8", { fatal: true }).decode(readFileSync(path));
  } catch {
    throw new UsageError(`plan text at ${maskDigits(path)} is not readable`);
  }
  const start = ACCOUNT_SECTION.exec(plan);
  let section24 = "";
  if (start) {
    NEXT_SECTION.lastIndex = start.index + start[0].length;
    const end = NEXT_SECTION.exec(plan);
    if (end) section24 = plan.slice(start.index, end.index);
  }
  const planNumbers = [...new Set(section24.match(LONG_NUMBER) ?? [])];
  const planLines = [...new Set(plan.split(LINE_BREAK).map((l) => l.trim()).filter((l) => [...l].length >= MIN_LINE))];
  if (!planLines.length) throw new UsageError(`plan text at ${maskDigits(path)} has no line of ${MIN_LINE}+ characters, so it can't be the plan`);
  if (exportMode && !planNumbers.length) throw new UsageError(`plan text at ${maskDigits(path)} has no section-24 number, so plan-24 would check nothing`);
  return { planNumbers, planLines };
}

function loadAllow(path) {
  let allow;
  try {
    allow = JSON.parse(readFileSync(path, "utf8"));
  } catch {
    throw new UsageError(`allow-list ${maskDigits(path)} is not readable JSON`);
  }
  const bad = (why) => new UsageError(`allow-list ${maskDigits(path)}: ${why}`);
  if (!Array.isArray(allow?.blobs) || !Array.isArray(allow?.images)) throw bad("needs `blobs` and `images` arrays");
  for (const [i, entry] of allow.blobs.entries()) {
    if (!OBJECT_ID.test(entry?.blob ?? "")) throw bad(`blobs[${i}] needs a full blob id`);
    if (!ALLOWABLE_RULES.has(entry.rule)) throw bad(`blobs[${i}] names an unknown rule`);
    if (typeof entry.reason !== "string" || !entry.reason.trim()) throw bad(`blobs[${i}] needs a written reason`);
  }
  if (!allow.images.every((g) => typeof g === "string" && g)) throw bad("`images` holds path globs only");
  return allow;
}

function parseArgs(argv) {
  const opts = { refs: [], plan: undefined, allow: undefined, exportMode: false };
  for (let i = 0; i < argv.length; i++) {
    const arg = argv[i];
    const value = () => {
      if (i + 1 >= argv.length) throw new UsageError(`${arg} needs a value`);
      return argv[++i];
    };
    if (arg === "--refs") opts.refs.push(...value().split(",").filter(Boolean));
    else if (arg === "--plan") opts.plan = value();
    else if (arg === "--allow") opts.allow = value();
    else if (arg === "--export") opts.exportMode = true;
    else throw new UsageError(`unknown argument ${maskDigits(arg)}`);
  }
  if (!opts.refs.length) opts.refs.push("main");
  for (const ref of opts.refs) if (ref.startsWith("-") && !REF_OPTIONS.has(ref)) throw new UsageError(`--refs takes a ref, or one of ${[...REF_OPTIONS].join(", ")}`);
  if (opts.exportMode && opts.allow !== undefined) throw new UsageError("--export uses the committed allow-list only, so it takes no --allow");
  return opts;
}

function formatDomains(map) {
  if (!map.size) return "none";
  return [...map.entries()]
    .sort((a, b) => b[1] - a[1] || (a[0] < b[0] ? -1 : 1))
    .map(([domain, n]) => `${maskDigits(domain)} ${n}`)
    .join(", ");
}

const short = (id) => id.slice(0, 7);
const USAGE = "usage: node scripts/check_history.mjs [--refs main]... [--plan PATH] [--allow FILE] [--export]";

export function main(argv, { cwd = process.cwd(), env = process.env, git, out = console.log, err = console.error, defaultPlan = DEFAULT_PLAN } = {}) {
  git ??= gitRunner(cwd);
  let opts;
  let plan;
  let allow;
  try {
    opts = parseArgs(argv);
    allow = loadAllow(opts.allow ?? DEFAULT_ALLOW);
    plan = loadPlan(opts.plan ?? env.LUSOT_PLAN_TEXT, defaultPlan, env, opts.exportMode, err);
  } catch (e) {
    if (!(e instanceof UsageError)) throw e;
    err(e.message);
    err(USAGE);
    return 2;
  }
  try {
    return scan(opts, plan, allow, git, out);
  } catch (e) {
    if (!(e instanceof GitError)) throw e;
    err(`history scan stopped: ${e.message}`);
    return 2;
  }
}

function scan(opts, plan, allow, git, out) {
  const rules = { planNumbers: plan?.planNumbers ?? null, planLines: plan?.planLines ?? null };
  if (plan) out(`plan rules: ${plan.planNumbers.length} section-24 number(s), ${plan.planLines.length} plan line(s) of ${MIN_LINE}+ characters`);

  const occurrences = logOccurrences(opts.refs, git);
  const sealedBlobs = new Set(occurrences.filter((o) => isSealedPath(o.path)).map((o) => o.blob));
  // A blob is a lockfile's only if every path it sits at is a lockfile (R15).
  const atOtherPaths = new Set(occurrences.filter((o) => !isLockfile(o.path)).map((o) => o.blob));
  const hits = [];
  const reported = new Set();
  const allowCounted = new Set();
  // Each hit once per blob and rule (in a blob) or per path and rule (on a path); an
  // allow-listed blob is counted once per rule.
  const record = (hit, key) => {
    if (hit.blob && allowed(hit, allow)) {
      allowCounted.add(`${hit.blob} ${hit.rule}`);
      return;
    }
    if (reported.has(key)) return;
    reported.add(key);
    hits.push(hit);
  };

  // Path rules, on each path with each blob it holds, so a later blob at a path is checked too.
  const seen = new Set();
  const sealedByCommit = new Map();
  for (const o of occurrences) {
    if (isSealedPath(o.path)) {
      const paths = sealedByCommit.get(o.commit) ?? new Set();
      paths.add(o.path);
      sealedByCommit.set(o.commit, paths);
      continue;
    }
    if (seen.has(`${o.path}\0${o.blob}`)) continue;
    seen.add(`${o.path}\0${o.blob}`);
    const pathRules = [];
    if (hasTwelveDigits(o.path)) pathRules.push("twelve-digit-path"); // as the account-ID scan reads names (D-h)
    if (hasEmail(o.path)) pathRules.push("email-path");
    const rule = pathRule(o.path, allow);
    if (rule) pathRules.push(rule);
    for (const r of pathRules) record({ commit: o.commit, path: o.path, blob: o.blob, rule: r }, `path ${o.path} ${r}`);
  }

  // Content rules, on each blob once.
  let read = 0;
  for (const entry of readEntries(occurrences, git)) {
    if (entry.bytes === null) continue;
    read++;
    const text = decodeText(entry.bytes);
    if (text === null) continue;
    for (const { rule } of scanText(text, { ...rules, skipTwelve: !atOtherPaths.has(entry.blob) })) {
      record({ commit: entry.commit, path: entry.path, blob: entry.blob, rule }, `blob ${entry.blob} ${rule}`);
    }
  }

  const messages = commitMessages(opts.refs, git);
  for (const { commit, message } of messages) {
    for (const { rule } of scanText(message, rules)) record({ commit, path: null, blob: null, rule, kind: "message" }, `message ${commit} ${rule}`);
  }
  const tags = annotatedTags(opts.refs, git);
  for (const { tag, message } of tagMessages(tags, git)) {
    for (const { rule } of scanText(message, rules)) record({ commit: tag, path: null, blob: null, rule, kind: "tag-message" }, `tag ${tag} ${rule}`);
  }

  for (const hit of hits) {
    out(hit.path === null ? `${short(hit.commit)} ${hit.kind} ${hit.rule}` : `${short(hit.commit)}:${maskDigits(hit.path)} ${hit.rule}`);
  }
  for (const [commit, paths] of sealedByCommit) out(`${short(commit)} sealed-path (${paths.size} files)`);
  const shared = new Set(occurrences.filter((o) => sealedBlobs.has(o.blob) && !isSealedPath(o.path)).map((o) => o.blob)).size;
  if (shared) out(`${shared} blob(s) not read: also at a sealed path`);
  out(`allow-listed: ${allowCounted.size} hit(s)`);
  const ids = identityDomains(opts.refs, git);
  out(`identities: author ${formatDomains(ids.author)}; committer ${formatDomains(ids.committer)}; tagger ${formatDomains(ids.tagger)}`);
  out(`Claude-Session trailers: ${sessionCount(messages)} commit(s)`);
  const problems = [];
  if (hits.length) problems.push(`${hits.length} hit(s)`);
  if (sealedByCommit.size) problems.push(`${sealedByCommit.size} commit(s) with sealed paths`);
  const skipped = plan ? "" : " (plan rules skipped)";
  out(`history scan: ${messages.length} commit(s), ${tags.length} tag(s), ${read} blob(s) read: ${problems.join(", ") || "clean"}${skipped}`);
  return problems.length ? 1 : 0;
}

if (import.meta.main === undefined) throw new Error("scripts/check_history.mjs needs Node 22.18 or newer");
if (import.meta.main) process.exitCode = main(process.argv.slice(2));
