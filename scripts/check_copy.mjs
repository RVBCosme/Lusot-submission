// The copy check (MS7 Task 9, C819; spec section 4.4). It reads its rules from scripts/copy-rules.json, which MS5's
// string-table test reads too, so the two can't drift.
//
// It breaks each file into units of text: Markdown and plain text by line; .ts, .tsx, .js, .mjs and .py by string
// literal (an object or dict key is left out), each with the line it starts on; .json by every string value; and an
// answers file (.jsonl) by the fields the rules name. Then:
// - a `fail` rule fails, except in the files its `reviewOnlyIn` lists, where it is a review hit;
// - a level line (one of the 9 levels followed by "deep") fails without "at this spot" or "sa spot na ito";
// - a `review` rule, run after the `allowed` sentences are taken out, is a review hit for Rene's M20, never a fail;
// - a `required` string missing from a file it names, once that file is scanned, fails.
//
// It prints `file:line rule-id "word"` for each hit, with counts, never the line itself; `--sheet OUT` writes the full
// lines, grouped by file, to a file outside the repo, for Rene. Exit codes: 0 clean (review hits allowed), 1 a fail or a
// missing required string, 2 a usage error or an unreadable file.
//
// Usage: node scripts/check_copy.mjs [--answers FILE.jsonl]... [--sheet OUT] [files...]
// With no files it reads the rules' own list, from the repo root.
import { existsSync, mkdirSync, readdirSync, readFileSync, writeFileSync } from "node:fs";
import { basename, dirname, extname, isAbsolute, join, relative, resolve, sep } from "node:path";
import { fileURLToPath } from "node:url";

const HERE = dirname(fileURLToPath(import.meta.url));
export const REPO = dirname(HERE);
export const RULES_PATH = join(HERE, "copy-rules.json");
const utf8 = new TextDecoder("utf-8", { fatal: true });

// The rules

const escapeRe = (s) => s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");

// A glob over forward-slash paths: `**` is any run of characters, `*` any run within one path part.
function globRe(glob) {
  const body = glob
    .split("**")
    .map((part) => part.split("*").map(escapeRe).join("[^/]*"))
    .join(".*");
  return new RegExp(`^${body}$`);
}

function compile(rule, kind) {
  if (typeof rule.id !== "string" || typeof rule.pattern !== "string") throw new Error(`a ${kind} rule needs an id and a pattern`);
  const flags = rule.flags ?? "";
  if (flags.includes("g") || flags.includes("y")) throw new Error(`rule ${rule.id}: no g or y flag`);
  return { ...rule, re: new RegExp(rule.pattern, flags), only: (rule.reviewOnlyIn ?? []).map(globRe) };
}

export function loadRules(path = RULES_PATH) {
  const raw = JSON.parse(readFileSync(path, "utf8"));
  const fail = raw.fail.map((r) => compile(r, "fail"));
  const review = raw.review.map((r) => compile(r, "review"));
  const seen = new Set();
  for (const { id } of [...fail, ...review, { id: "level-line" }]) {
    if (seen.has(id)) throw new Error(`rule id ${id} is used twice`);
    seen.add(id);
  }
  const lv = raw.levelLine;
  return {
    files: raw.files,
    answers: { fields: raw.answers?.fields ?? [], reviewFields: raw.answers?.reviewFields ?? [] },
    fail,
    review,
    required: raw.required,
    levelLine: {
      re: new RegExp(`(?:\\b(?:${lv.levels.map(escapeRe).join("|")})|\\{level\\})[\\s-]+(?:deep|ang lalim)\\b`, "i"),
      mustInclude: lv.mustInclude.map((s) => s.toLowerCase()),
      only: (lv.reviewOnlyIn ?? []).map(globRe),
    },
    // Longest first, so a sentence goes before a phrase inside it.
    allowed: [...raw.allowed].sort((a, b) => b.length - a.length),
  };
}

let defaults;
const defaultRules = () => (defaults ??= loadRules());

// Reading files into units

const SCRIPT_EXT = new Set([".ts", ".tsx", ".js", ".mjs", ".cjs", ".mts", ".cts", ".jsx"]);
const IDENT = /[A-Za-z0-9_$]/;
const REGEX_AFTER = new Set(["(", ",", "=", ":", "[", "!", "&", "|", "?", "{", "}", ";", "+", "-", "*", "%", "<", ">", "~", "^"]);
const REGEX_AFTER_WORD = new Set(["return", "typeof", "case", "in", "of", "void", "delete", "throw", "new", "else", "do", "yield", "await"]);

// The line of each character offset.
function lineIndex(content) {
  const starts = [0];
  for (let i = 0; i < content.length; i++) if (content[i] === "\n") starts.push(i + 1);
  return (offset) => {
    let lo = 0;
    let hi = starts.length - 1;
    while (lo < hi) {
      const mid = (lo + hi + 1) >> 1;
      if (starts[mid] <= offset) lo = mid;
      else hi = mid - 1;
    }
    return lo + 1;
  };
}

// One escape sequence at s[i] (the backslash), for JavaScript or (py) Python. Returns [text, next index].
function unescape(s, i, py) {
  const c = s[i + 1];
  const simple = { n: "\n", t: "\t", r: "\r", b: "\b", f: "\f", v: "\v", 0: "\0", "\\": "\\", "'": "'", '"': '"', "`": "`" };
  if (c === "\n") return ["", i + 2];
  if (c === "\r") return ["", s[i + 2] === "\n" ? i + 3 : i + 2];
  if (c === "x" && /^[0-9a-fA-F]{2}$/.test(s.slice(i + 2, i + 4))) return [String.fromCodePoint(parseInt(s.slice(i + 2, i + 4), 16)), i + 4];
  if (c === "u" && s[i + 2] === "{" && !py) {
    const end = s.indexOf("}", i + 3);
    if (end > 0) return [String.fromCodePoint(parseInt(s.slice(i + 3, end), 16)), end + 1];
  }
  if (c === "u" && /^[0-9a-fA-F]{4}$/.test(s.slice(i + 2, i + 6))) return [String.fromCodePoint(parseInt(s.slice(i + 2, i + 6), 16)), i + 6];
  if (c === "U" && py && /^[0-9a-fA-F]{8}$/.test(s.slice(i + 2, i + 10))) return [String.fromCodePoint(parseInt(s.slice(i + 2, i + 10), 16)), i + 10];
  if (c in simple && !(py && c === "`")) return [simple[c], i + 2];
  // An unknown escape: JavaScript drops the backslash, Python keeps it.
  return [py ? `\\${c ?? ""}` : (c ?? ""), i + 2];
}

// The next character that isn't a space or a tab, from offset i.
function nextSolid(s, i) {
  while (i < s.length && (s[i] === " " || s[i] === "\t")) i++;
  return s[i];
}

// The string literals of a JavaScript or TypeScript source, each with its start offset. An object key (a literal
// after `{` or `,` and before `:`) is left out; a template literal's `${...}` parts become "…".
function jsLiterals(s) {
  const out = [];
  let prev = ""; // the last significant character outside strings and comments
  let prevWord = "";
  let i = 0;

  // A template literal from s[i] (the backtick); returns [text, next index].
  function template(at) {
    let text = "";
    let j = at + 1;
    while (j < s.length && s[j] !== "`") {
      if (s[j] === "\\") {
        const [t, n] = unescape(s, j, false);
        text += t;
        j = n;
      } else if (s[j] === "$" && s[j + 1] === "{") {
        j = skipCode(j + 2, "}");
        text += "…";
      } else text += s[j++];
    }
    return [text, j + 1];
  }

  // A quoted string from s[at]; returns [text, next index].
  function quoted(at) {
    const q = s[at];
    let text = "";
    let j = at + 1;
    while (j < s.length && s[j] !== q && s[j] !== "\n") {
      if (s[j] === "\\") {
        const [t, n] = unescape(s, j, false);
        text += t;
        j = n;
      } else text += s[j++];
    }
    return [text, j + 1];
  }

  // Code inside `${...}`, up to its closing brace; returns the index after it.
  function skipCode(j, close) {
    let depth = 0;
    while (j < s.length) {
      const c = s[j];
      if (c === "'" || c === '"') j = quoted(j)[1];
      else if (c === "`") j = template(j)[1];
      else if (c === "{") {
        depth++;
        j++;
      } else if (c === close && depth === 0) return j + 1;
      else if (c === "}") {
        depth--;
        j++;
      } else j++;
    }
    return j;
  }

  while (i < s.length) {
    const c = s[i];
    if (c === "/" && s[i + 1] === "/") {
      while (i < s.length && s[i] !== "\n") i++;
    } else if (c === "/" && s[i + 1] === "*") {
      const end = s.indexOf("*/", i + 2);
      i = end < 0 ? s.length : end + 2;
    } else if (c === "'" || c === '"' || c === "`") {
      const [text, next] = c === "`" ? template(i) : quoted(i);
      const key = c !== "`" && (prev === "{" || prev === "," || prev === "") && nextSolid(s, next) === ":";
      if (!key) out.push({ offset: i, text });
      i = next;
      prev = c;
      prevWord = "";
    } else if (c === "/" && (REGEX_AFTER.has(prev) || prev === "" || REGEX_AFTER_WORD.has(prevWord))) {
      // A regular expression literal: skip to its closing slash, outside any character class.
      let j = i + 1;
      let inClass = false;
      while (j < s.length && s[j] !== "\n") {
        if (s[j] === "\\") j += 2;
        else if (s[j] === "[") (inClass = true), j++;
        else if (s[j] === "]") (inClass = false), j++;
        else if (s[j] === "/" && !inClass) break;
        else j++;
      }
      i = j + 1;
      while (i < s.length && /[a-z]/.test(s[i])) i++;
      prev = "/";
      prevWord = "";
    } else if (IDENT.test(c)) {
      let j = i;
      while (j < s.length && IDENT.test(s[j])) j++;
      prevWord = s.slice(i, j);
      prev = s[j - 1];
      i = j;
    } else {
      if (!/\s/.test(c)) {
        prev = c;
        prevWord = "";
      }
      i++;
    }
  }
  return out;
}

// The string literals of a Python source, docstrings included, each with its start offset. A dict key (a literal
// after `{` or `,` and before `:`) is left out.
function pyLiterals(s) {
  const out = [];
  let prev = "";
  let i = 0;
  while (i < s.length) {
    const c = s[i];
    if (c === "#") {
      while (i < s.length && s[i] !== "\n") i++;
    } else if (c === "'" || c === '"') {
      const prefix = /([rRbBuUfF]{1,2})$/.exec(s.slice(Math.max(0, i - 2), i));
      const before = prefix ? s[i - prefix[1].length - 1] : undefined;
      const raw = prefix !== null && !(before !== undefined && /[A-Za-z0-9_]/.test(before)) && /r/i.test(prefix[1]);
      const triple = s.slice(i, i + 3) === c.repeat(3);
      const close = triple ? c.repeat(3) : c;
      let j = i + close.length;
      let text = "";
      while (j < s.length && s.slice(j, j + close.length) !== close && (triple || s[j] !== "\n")) {
        if (s[j] === "\\") {
          if (raw) {
            text += s.slice(j, j + 2);
            j += 2;
          } else {
            const [t, n] = unescape(s, j, true);
            text += t;
            j = n;
          }
        } else text += s[j++];
      }
      const next = j + close.length;
      const key = (prev === "{" || prev === ",") && nextSolid(s, next) === ":";
      if (!key) out.push({ offset: i, text });
      i = next;
      prev = c;
    } else {
      if (!/\s/.test(c)) prev = c;
      i++;
    }
  }
  return out;
}

// Every string value of a JSON document (keys left out), with its offset.
function jsonValues(s) {
  const out = [];
  for (const m of s.matchAll(/"(?:[^"\\\n]|\\.)*"/g)) {
    let j = m.index + m[0].length;
    while (j < s.length && /\s/.test(s[j])) j++;
    if (s[j] === ":") continue;
    out.push({ offset: m.index, text: JSON.parse(m[0]) });
  }
  return out;
}

const pick = (obj, path) => path.split(".").reduce((o, k) => (o !== null && typeof o === "object" ? o[k] : undefined), obj);

// The units of text in one file: `{file, line, text}`, plus `field` and `reviewOnly` for an answers file.
export function textUnits(file, content, rules = defaultRules()) {
  const ext = extname(file).toLowerCase();
  const name = file.replaceAll("\\", "/");
  if (ext === ".jsonl") {
    const units = [];
    content.split(/\r?\n/).forEach((line, n) => {
      if (line.trim() === "") return;
      let record;
      try {
        record = JSON.parse(line);
      } catch {
        throw new Error(`${name}:${n + 1}: not a JSON line`);
      }
      if (!rules.answers.fields.some((f) => typeof pick(record, f) === "string")) {
        throw new Error(`${name}:${n + 1}: no answer text (${rules.answers.fields.join(", ")})`);
      }
      for (const [fields, reviewOnly] of [
        [rules.answers.fields, false],
        [rules.answers.reviewFields, true],
      ]) {
        for (const field of fields) {
          const text = pick(record, field);
          if (typeof text !== "string" || text.trim() === "") continue;
          units.push(reviewOnly ? { file: name, line: n + 1, text, field, reviewOnly } : { file: name, line: n + 1, text, field });
        }
      }
    });
    return units;
  }
  const literals = SCRIPT_EXT.has(ext) ? jsLiterals(content) : ext === ".py" ? pyLiterals(content) : ext === ".json" ? jsonValues(content) : null;
  if (literals === null) {
    return content
      .split(/\r?\n/)
      .map((text, n) => ({ file: name, line: n + 1, text }))
      .filter((u) => u.text.trim() !== "");
  }
  const lineOf = lineIndex(content);
  return literals.filter((l) => l.text.trim() !== "").map((l) => ({ file: name, line: lineOf(l.offset), text: l.text }));
}

// Finding hits

// The whole words around a match, for the printed hit.
function word(text, m) {
  let a = m.index;
  let b = m.index + m[0].length;
  const isWord = (ch) => ch !== undefined && /[\p{L}\p{N}_-]/u.test(ch);
  while (a > 0 && isWord(text[a - 1])) a--;
  while (b < text.length && isWord(text[b])) b++;
  return text.slice(a, b);
}

const inAny = (file, globs) => globs.some((g) => g.test(file));

function withoutAllowed(text, allowed) {
  let out = text;
  for (const phrase of allowed) out = out.split(phrase).join(" ".repeat(phrase.length));
  return out;
}

// `{fails, reviews, missing, missingIn}`. Each hit is `{file, line, rule, match, unit}` (unit: its index in `units`),
// with `field` for an answers file. `missing` lists the required strings' ids that a scanned file lacks; `scanned`
// names the files scanned (default: the units' own files), so a scanned file with no units still counts.
export function findHits(units, rules = defaultRules(), { scanned } = {}) {
  const fails = [];
  const reviews = [];
  units.forEach((u, unit) => {
    const hit = (rule, m) => ({ file: u.file, line: u.line, rule, match: word(u.text, m), unit, ...(u.field ? { field: u.field } : {}) });
    for (const r of rules.fail) {
      const m = r.re.exec(u.text);
      if (m) (u.reviewOnly || inAny(u.file, r.only) ? reviews : fails).push(hit(r.id, m));
    }
    const lv = rules.levelLine;
    const m = lv.re.exec(u.text);
    if (m && !lv.mustInclude.some((s) => u.text.toLowerCase().includes(s))) {
      (u.reviewOnly || inAny(u.file, lv.only) ? reviews : fails).push(hit("level-line", m));
    }
    const rest = withoutAllowed(u.text, rules.allowed);
    for (const r of rules.review) {
      const found = r.re.exec(rest);
      if (found) reviews.push(hit(r.id, found));
    }
  });
  const files = new Set(scanned ?? units.map((u) => u.file));
  const missingIn = [];
  for (const req of rules.required) {
    for (const file of req.files) {
      if (files.has(file) && !units.some((u) => u.file === file && u.text.includes(req.text))) missingIn.push({ id: req.id, file });
    }
  }
  return { fails, reviews, missing: [...new Set(missingIn.map((x) => x.id))], missingIn };
}

// The sheet

const plural = (n, one, many) => `${n} ${n === 1 ? one : many}`;
const cell = (s) => s.replaceAll("\\", "\\\\").replaceAll("|", "\\|").replace(/\r?\n/g, "<br>");

// Markdown for Rene's M20: every unit, grouped by file in path order, with its hits marked.
export function sheet(units, hits) {
  const marks = new Map();
  for (const h of hits.fails) marks.set(h.unit, [...(marks.get(h.unit) ?? []), `**FAIL ${h.rule}**`]);
  for (const h of hits.reviews) marks.set(h.unit, [...(marks.get(h.unit) ?? []), `review ${h.rule}`]);
  const byFile = new Map();
  units.forEach((u, i) => byFile.set(u.file, [...(byFile.get(u.file) ?? []), i]));
  const lines = [
    "# Copy sheet",
    "",
    `${plural(units.length, "line", "lines")} in ${plural(byFile.size, "file", "files")}: ${plural(hits.fails.length, "fail", "fails")}, ${plural(hits.reviews.length, "review hit", "review hits")}.`,
  ];
  for (const file of [...byFile.keys()].sort()) {
    lines.push("", `## ${file}`, "", "| Line | Text | Marks |", "|---|---|---|");
    for (const i of byFile.get(file)) {
      const u = units[i];
      const at = u.field ? `${u.line} (${u.field})` : `${u.line}`;
      lines.push(`| ${at} | ${cell(u.text)} | ${(marks.get(i) ?? []).join(" · ")} |`);
    }
  }
  return `${lines.join("\n")}\n`;
}

// The command

class Usage extends Error {}

// A path with a part named `sealed`, in any of the spellings Windows opens as that folder.
const sealedPart = (p) =>
  p
    .split(/[\\/]+/)
    .some((part) => part.toLowerCase().replace(/::\$index_allocation$/, "").replace(/[. ]+$/, "") === "sealed");

const inside = (root, p) => {
  const rel = relative(root, p);
  return rel === "" || (!rel.startsWith("..") && !isAbsolute(rel));
};

function readText(path, label) {
  let bytes;
  try {
    bytes = readFileSync(path);
  } catch (err) {
    throw new Usage(`cannot read ${label}: ${err.code ?? "error"}`);
  }
  try {
    return utf8.decode(bytes);
  } catch {
    throw new Usage(`${label} is not UTF-8 text`);
  }
}

// The default files: the rules' list, from `root`. A `*` may stand in the last part of a path only.
function defaultFiles(rules, root) {
  const found = [];
  const skipped = [];
  for (const entry of rules.files) {
    if (basename(entry).includes("*")) {
      const dir = dirname(entry);
      const re = globRe(basename(entry));
      const names = existsSync(join(root, dir)) ? readdirSync(join(root, dir)).filter((n) => re.test(n)).sort() : [];
      if (names.length === 0) skipped.push(entry);
      for (const n of names) found.push(`${dir}/${n}`);
    } else if (existsSync(join(root, entry))) found.push(entry);
    else skipped.push(entry);
  }
  return { found, skipped };
}

export function main(argv, { root = REPO, cwd = process.cwd(), print = console.log, warn = console.error } = {}) {
  try {
    const answers = [];
    const files = [];
    let sheetOut;
    for (let i = 0; i < argv.length; i++) {
      const a = argv[i];
      if (a === "--answers" || a === "--sheet") {
        const v = argv[++i];
        if (v === undefined) throw new Usage(`${a} needs a path`);
        if (a === "--answers") answers.push(v);
        else sheetOut = v;
      } else if (a.startsWith("--")) throw new Usage(`unknown option ${a}`);
      else files.push(a);
    }
    for (const p of [...answers, ...files, ...(sheetOut ? [sheetOut] : [])]) {
      if (sealedPart(p)) throw new Usage("refused: a path with a part named sealed");
    }
    for (const p of answers) if (extname(p).toLowerCase() !== ".jsonl") throw new Usage("--answers takes a .jsonl file");
    if (sheetOut !== undefined && inside(root, resolve(cwd, sheetOut))) {
      throw new Usage("the sheet holds the full text; write it outside the repo");
    }

    const rules = loadRules();
    const sources = []; // [label, path]
    const scanned = [];
    const skipped = [];
    if (files.length === 0) {
      const d = defaultFiles(rules, root);
      for (const f of d.found) sources.push([f, join(root, f)]);
      const required = new Set(rules.required.flatMap((r) => r.files));
      for (const f of d.skipped) (required.has(f) ? scanned : skipped).push(f);
    } else {
      for (const f of files) {
        const abs = resolve(cwd, f);
        const rel = relative(cwd, abs);
        sources.push([inside(cwd, abs) ? rel.split(sep).join("/") : f.replaceAll("\\", "/"), abs]);
      }
    }
    for (const a of answers) sources.push([a.replaceAll("\\", "/"), resolve(cwd, a)]);

    const units = [];
    for (const [label, path] of sources) {
      scanned.push(label);
      try {
        units.push(...textUnits(label, readText(path, label), rules));
      } catch (err) {
        if (err instanceof Usage) throw err;
        throw new Usage(err.message);
      }
    }
    const hits = findHits(units, rules, { scanned });
    const at = (h) => `${h.file}:${h.line}${h.field ? ` (${h.field})` : ""} ${h.rule} ${JSON.stringify(h.match)}`;
    for (const h of hits.fails) print(`FAIL ${at(h)}`);
    for (const h of hits.reviews) print(`review ${at(h)}`);
    for (const m of hits.missingIn) print(`missing: ${m.id} (${m.file})`);
    if (skipped.length) print(`skipped (not there yet): ${skipped.join(", ")}`);
    if (sheetOut !== undefined) {
      const out = resolve(cwd, sheetOut);
      mkdirSync(dirname(out), { recursive: true });
      writeFileSync(out, sheet(units, hits));
      print(`sheet: ${plural(units.length, "line", "lines")} written`);
    }
    print(
      `copy check: ${plural(sources.length, "file", "files")}, ${plural(units.length, "line", "lines")}: ` +
        `${plural(hits.fails.length, "fail", "fails")}, ${plural(hits.reviews.length, "review hit", "review hits")}, ${hits.missing.length} missing`,
    );
    return hits.fails.length > 0 || hits.missingIn.length > 0 ? 1 : 0;
  } catch (err) {
    if (!(err instanceof Usage)) throw err;
    warn(`copy check: ${err.message}`);
    return 2;
  }
}

if (import.meta.main === undefined) throw new Error("scripts/check_copy.mjs needs Node 22.18 or newer");
if (import.meta.main) process.exitCode = main(process.argv.slice(2));
