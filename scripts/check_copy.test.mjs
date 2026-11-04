// Tests for the copy check in check_copy.mjs (MS7 Task 9, C819). Run: node --test scripts/check_copy.test.mjs
import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import { test } from "node:test";
import { fileURLToPath, pathToFileURL } from "node:url";
import { findHits, loadRules, main, sheet, textUnits } from "./check_copy.mjs";

const script = fileURLToPath(new URL("./check_copy.mjs", import.meta.url));
const RULES_PATH = fileURLToPath(new URL("./copy-rules.json", import.meta.url));
const REPO = dirname(dirname(script));
const rules = loadRules(RULES_PATH);

const SCREEN_LINE = "Lusot estimates depth at one spot. It is not advice to cross. Follow MMDA and local advisories.";
const CLASS_LINES = [
  "MMDA lists this level as passable to all vehicles (PATV).",
  "MMDA lists this level as not passable to light vehicles (NPLV).",
  "MMDA lists this level as not passable to any vehicle (NPATV).",
  "Shallower than MMDA's gutter level, which MMDA lists as passable to all vehicles (PATV).",
  "Deeper than MMDA's chest level, which MMDA lists as not passable to any vehicle (NPATV).",
];

const hitsOf = (file, content) => findHits(textUnits(file, content), rules);
const ids = (list) => list.map((h) => h.rule);

// Runs the CLI in a throwaway folder holding `files`, with `args`; returns its exit code and output.
function cli(files, args) {
  const dir = mkdtempSync(join(tmpdir(), "lusot-copy-"));
  try {
    for (const [path, content] of Object.entries(files)) {
      mkdirSync(dirname(join(dir, path)), { recursive: true });
      writeFileSync(join(dir, path), content);
    }
    const run = spawnSync(process.execPath, [script, ...args(dir)], { cwd: dir, encoding: "utf8" });
    return { code: run.status, out: run.stdout + run.stderr, dir };
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
}

test("fails on every banned form", () => {
  const forms = [
    ["safe", "banned-safe"],
    ["Safely", "banned-safe"],
    ["UNSAFE", "banned-safe"],
    ["safety", "banned-safe"],
    ["kaligtasan", "banned-ligtas"],
    ["ligtas", "banned-ligtas"],
    ["MMDA's 9 levels", "mmda-9-levels"],
    ["you can cross", "crossing-phrase"],
  ];
  for (const [text, id] of forms) {
    const { fails } = hitsOf("notes.md", `A line: ${text}.\n`);
    assert.deepEqual(ids(fails), [id], text);
  }
});

test("keeps every form MS5's own patterns caught (C608)", () => {
  const forms = [
    ["a safeguard", "banned-safe"],
    ["makaligtas", "banned-ligtas"],
    ["Puwedeng dumaan", "crossing-phrase"],
    ["TUMAWID KA", "crossing-phrase"],
    ["Lusutan mo", "crossing-phrase"],
    ["go ahead", "crossing-phrase"],
    ["MMDA 9 levels", "mmda-9-levels"],
    ["mmda nine levels", "mmda-9-levels"],
    ["MMDA’s nine levels", "mmda-9-levels"],
    ["the 9 MMDA levels", "mmda-9-levels"],
  ];
  for (const [text, id] of forms) {
    const { fails } = hitsOf("notes.md", `${text}\n`);
    assert.ok(ids(fails).includes(id), `${text}: ${ids(fails)}`);
  }
});

test("allows the screen line and the class lines", () => {
  for (const line of [SCREEN_LINE, ...CLASS_LINES, "Not affiliated with MMDA."]) {
    const { fails, reviews } = hitsOf("notes.md", `${line}\n`);
    assert.deepEqual(fails, [], line);
    assert.deepEqual(reviews, [], line);
  }
});

// C639, approved by the tracker under Rene's delegation, Nov 2: the six verdict sentences of the result card, exact and
// case-sensitive, are allowed. A looser variant is still a review hit, so the allowance can't widen the word "passable".
const VERDICT_LINES = [
  "Verdict at this spot: Passable to all vehicles",
  "Verdict at this spot: Not passable to light vehicles",
  "Verdict at this spot: Not passable to any vehicle",
  "Verdict sa spot na ito: Passable sa lahat ng sasakyan",
  "Verdict sa spot na ito: Hindi passable sa light vehicles",
  "Verdict sa spot na ito: Hindi passable sa anumang sasakyan",
];

test("C639, approved by the tracker under Rene's delegation, Nov 2: the six verdict sentences give no review hit", () => {
  assert.equal(VERDICT_LINES.length, 6);
  for (const line of VERDICT_LINES) {
    assert.ok(rules.allowed.includes(line), `${line} is in copy-rules.json's allowed`);
    const { fails, reviews } = hitsOf("notes.md", `${line}\n`);
    assert.deepEqual(fails, [], line);
    assert.deepEqual(reviews, [], line);
  }
  // A looser variant (another wording, another case, another verdict word) still gives a review hit. (The lowercase class
  // phrases above are older allowances, taken out wherever they sit, so "verdict at this spot: passable to all vehicles"
  // is clear through them and not through these six.)
  for (const loose of [
    "Passable to all vehicles here",
    "verdict at this spot: Passable to all vehicles",
    "Verdict at this spot: Passable to all cars",
    "Verdict at this spot: Not Passable to light vehicles",
    "Verdict sa spot na ito: passable sa lahat ng sasakyan",
  ]) {
    const { fails, reviews } = hitsOf("notes.md", `${loose}\n`);
    assert.deepEqual(fails, [], loose);
    assert.deepEqual(ids(reviews), ["crossing-pass"], loose);
  }
});

test("a level line needs at this spot", () => {
  assert.deepEqual(ids(hitsOf("notes.md", "Knee deep.\n").fails), ["level-line"]);
  const ok = hitsOf("notes.md", "Knee deep at this spot (MMDA level).\n");
  assert.deepEqual(ok.fails, []);
  assert.deepEqual(ok.reviews, []);
  assert.deepEqual(hitsOf("notes.md", "Half-knee deep ang tubig sa spot na ito.\n").fails, []);
  assert.deepEqual(ids(hitsOf("notes.md", "Above chest deep\n").fails), ["level-line"]);
});

test("review hits do not fail", () => {
  const { code, out } = cli({ "note.md": "Take the road to España.\n" }, () => ["note.md"]);
  assert.equal(code, 0, out);
  assert.match(out, /note\.md:1 whole-road "road"/);
  assert.doesNotMatch(out, /España/, "the full text is never printed");
  assert.match(out, /0 fails, 1 review hit/);
});

test("lowercase lusot is review, the name is not", () => {
  const name = hitsOf("notes.md", "Lusot estimates depth at one spot.\n");
  assert.deepEqual(name.fails, []);
  assert.deepEqual(name.reviews, []);
  const verb = hitsOf("notes.md", "lusot ba sedan ko\n");
  assert.deepEqual(verb.fails, []);
  assert.deepEqual(ids(verb.reviews), ["crossing-lusot"]);
});

test("string literals keep their line numbers", () => {
  const ts = [
    "// a comment that says safe is never read",
    "export const T = {",
    "  'a.key': { text: 'first line', reviewed: true },",
    "  'b.key': {",
    '    text: "Knee deep.",',
    "  },",
    "  c: `two",
    "lines`,",
    "  d: 'it\\'s',",
    "  e: x ? 'yes' : 'no',",
    "  f: /it's/.test(y) ? 'z' : 'w',",
    "}",
  ].join("\n");
  const units = textUnits("app/src/i18n/en.ts", ts);
  assert.deepEqual(
    units.map((u) => [u.line, u.text]),
    [
      [3, "first line"],
      [5, "Knee deep."],
      [7, "two\nlines"],
      [9, "it's"],
      [10, "yes"],
      [10, "no"],
      [11, "z"],
      [11, "w"],
    ],
  );
  const py = ['"""Docstring', 'line two."""', "WORDS = {", '    "knee": "Knee deep",', "}", "# 'safe' in a comment", "x = r'\\d'"].join("\n");
  assert.deepEqual(
    textUnits("overlay.py", py).map((u) => [u.line, u.text]),
    [
      [1, "Docstring\nline two."],
      [4, "Knee deep"],
      [7, "\\d"],
    ],
  );
  const json = '{\n  "name": "x",\n  "list": ["a", "you can cross"],\n  "n": 3\n}\n';
  assert.deepEqual(
    textUnits("words.json", json).map((u) => [u.line, u.text]),
    [
      [2, "x"],
      [3, "a"],
      [3, "you can cross"],
    ],
  );
});

test("jsonl answers are read from their fields", () => {
  const lines = [
    JSON.stringify({ id: "T1", answer: { kind: "safe" }, rendered: { en: "Knee deep.", fil: "Wala pa." }, transcript: "ligtas ba dito" }),
    JSON.stringify({ id: "T2", rendered: { en: "Not affiliated with MMDA." } }),
  ].join("\n");
  const units = textUnits("/data/ask/2026-11-02/answers.jsonl", `${lines}\n`);
  assert.deepEqual(
    units.map((u) => [u.line, u.field, u.text, u.reviewOnly === true]),
    [
      [1, "rendered.en", "Knee deep.", false],
      [1, "rendered.fil", "Wala pa.", false],
      [1, "transcript", "ligtas ba dito", true],
      [2, "rendered.en", "Not affiliated with MMDA.", false],
    ],
  );
  const { fails, reviews } = findHits(units, rules);
  assert.deepEqual(ids(fails), ["level-line"], "the answer's own words fail; a field it doesn't name isn't read");
  assert.deepEqual(ids(reviews), ["banned-ligtas"], "the speaker's words only review");
  assert.throws(() => textUnits("a.jsonl", "{not json}\n"), /a\.jsonl:1/);
});

test("a missing required string fails", () => {
  const en = "export const EN = {\n  'about.notAffiliated': { text: 'Not affiliated with MMDA.', reviewed: true },\n}\n";
  assert.deepEqual(hitsOf("app/src/i18n/en.ts", en).missing, ["screen-line"]);
  const both = `export const EN = {\n  'layout.screenLine': { text: '${SCREEN_LINE}', reviewed: true },\n  'about.notAffiliated': { text: 'Not affiliated with MMDA.', reviewed: true },\n}\n`;
  assert.deepEqual(hitsOf("app/src/i18n/en.ts", both).missing, []);
  // The README needs both (C922 added the screen line to it).
  assert.deepEqual(hitsOf("README.md", "# Lusot\n").missing, ["screen-line", "not-affiliated"]);
  const { code, out } = cli({ "app/src/i18n/en.ts": en }, () => ["app/src/i18n/en.ts"]);
  assert.equal(code, 1, out);
  assert.match(out, /missing: screen-line \(app\/src\/i18n\/en\.ts\)/);
});

test("banned-safe fails in the README and the app, and only reviews in eval and prompts", () => {
  assert.deepEqual(ids(hitsOf("README.md", "It makes safety decisions.\n").fails), ["banned-safe"]);
  assert.deepEqual(ids(hitsOf("app/src/i18n/en.ts", "const a = { k: 'It makes safety decisions.' }\n").fails), ["banned-safe"]);
  for (const file of ["backend/api/prompts/ask_v1.md", "eval/rules.md"]) {
    const { fails, reviews } = hitsOf(file, "Never say safe.\n");
    assert.deepEqual(fails, [], file);
    assert.deepEqual(ids(reviews), ["banned-safe"], file);
  }
  const words = hitsOf("backend/api/prompts/ask_v1.words.json", '{"crossing": ["ligtas", "makakalusot"]}\n');
  assert.deepEqual(words.fails, [], "the prompt's word lists quote banned words to catch them");
  assert.deepEqual(ids(words.reviews).sort(), ["banned-ligtas", "crossing-phrase"]);
});

// MS8's texts (C922): the README, the write-up, the X post and the video's description carry the screen line, and the
// copy rules read them, the credits file and the captions too.
test("the submission texts need the screen line", () => {
  for (const file of ["README.md", "docs/submission/write-up.md", "docs/submission/x-post.md", "docs/submission/video-description.md"]) {
    assert.ok(hitsOf(file, "Lusot: a live flood map.\n").missing.includes("screen-line"), file);
    assert.ok(!hitsOf(file, `Lusot: a live flood map.\n\n${SCREEN_LINE}\n`).missing.includes("screen-line"), file);
  }
});

test("MS8's texts, credits and captions are read by default, and a banned word in them fails", () => {
  const root = mkdtempSync(join(tmpdir(), "lusot-ms8-"));
  try {
    const put = (path, text) => {
      mkdirSync(dirname(join(root, path)), { recursive: true });
      writeFileSync(join(root, path), text);
    };
    put("docs/submission/x-post.md", `It is a safe spot.\n\n${SCREEN_LINE}\n`);
    put("docs/media/CREDITS.md", "You can cross here.\n");
    put("docs/media/lusot-video.en.srt", "1\n00:00:01,000 --> 00:00:03,000\nGo ahead.\n");
    const lines = [];
    const code = main([], { root, cwd: root, print: (l) => lines.push(l), warn: (l) => lines.push(l) });
    const out = lines.join("\n");
    assert.equal(code, 1, out);
    assert.match(out, /docs\/submission\/x-post\.md:1\b.*banned-safe/);
    assert.match(out, /docs\/media\/CREDITS\.md:1\b.*crossing-phrase/);
    assert.match(out, /docs\/media\/lusot-video\.en\.srt:3\b.*crossing-phrase/);
  } finally {
    rmSync(root, { recursive: true, force: true });
  }
});

test("levels in eval tables only review", () => {
  const { fails, reviews } = hitsOf("eval/results/report/report.md", "| knee deep | 12 |\n");
  assert.deepEqual(fails, []);
  assert.deepEqual(ids(reviews), ["level-line"]);
});

test("the overlay's box labels only review their level words", () => {
  const py = 'LEVEL_WORDS = {\n    "knee": "Knee deep",\n}\n';
  const { fails, reviews } = hitsOf("backend/analysis/src/lusot_analysis/overlay.py", py);
  assert.deepEqual(fails, []);
  assert.deepEqual(ids(reviews), ["level-line"]);
  assert.deepEqual(ids(hitsOf("backend/analysis/src/lusot_analysis/overlay.py", "x = 'safe'\n").fails), ["banned-safe"]);
});

test("the sheet groups by file and marks hits", () => {
  const units = [
    ...textUnits("b.md", "One road | here.\nSafe line.\n"),
    ...textUnits("a.md", "Plain line.\n"),
  ];
  const out = sheet(units, findHits(units, rules));
  const a = out.indexOf("## a.md");
  const b = out.indexOf("## b.md");
  assert.ok(a > 0 && b > a, "grouped by file, in path order");
  assert.match(out, /\| 1 \| One road \\\| here\. \| review whole-road \|/);
  assert.match(out, /\| 2 \| Safe line\. \| \*\*FAIL banned-safe\*\* \|/);
  assert.match(out, /\| 1 \| Plain line\. \| {2}\|/);
  assert.match(out, /1 fail, 1 review hit/);
});

test("the CLI prints the file, line, rule and word, never the line itself", () => {
  const { code, out } = cli({ "copy.md": "Intro.\nThis is unsafe, the note said.\n" }, () => ["copy.md"]);
  assert.equal(code, 1, out);
  assert.match(out, /FAIL copy\.md:2 banned-safe "unsafe"/);
  assert.doesNotMatch(out, /the note said/);
});

test("the sheet is written outside the repo only", () => {
  const { code, out } = cli({ "copy.md": "Plain.\n" }, (dir) => ["--sheet", join(dir, "out", "sheet.md"), "copy.md"]);
  assert.equal(code, 0, out);
  const inside = spawnSync(process.execPath, [script, "--sheet", join(REPO, "copy-sheet.md"), "README.md"], {
    cwd: REPO,
    encoding: "utf8",
  });
  assert.equal(inside.status, 2, inside.stdout + inside.stderr);
  assert.match(inside.stderr, /outside the repo/);
  const sealed = spawnSync(process.execPath, [script, "--answers", join(tmpdir(), "sealed", "a.jsonl")], { cwd: REPO, encoding: "utf8" });
  assert.equal(sealed.status, 2);
  assert.match(sealed.stderr, /sealed/);
});

test("the sheet file holds the full text, grouped by file", () => {
  const dir = mkdtempSync(join(tmpdir(), "lusot-sheet-"));
  try {
    writeFileSync(join(dir, "copy.md"), "The road here.\n");
    const out = join(dir, "sheet.md");
    const code = main(["--sheet", out, "copy.md"], { cwd: dir, print: () => {}, warn: () => {} });
    assert.equal(code, 0);
    assert.match(readFileSync(out, "utf8"), /\| 1 \| The road here\. \| review whole-road \|/);
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
});

test("by default it reads the rules' files: one not there yet is skipped, a required one counts as missing", () => {
  const root = mkdtempSync(join(tmpdir(), "lusot-root-"));
  try {
    const en = `export const EN = {\n  'layout.screenLine': { text: '${SCREEN_LINE}', reviewed: true },\n  'about.notAffiliated': { text: 'Not affiliated with MMDA.', reviewed: true },\n}\n`;
    mkdirSync(join(root, "app/src/i18n"), { recursive: true });
    writeFileSync(join(root, "app/src/i18n/en.ts"), en);
    mkdirSync(join(root, "app/src/content"), { recursive: true });
    writeFileSync(join(root, "app/src/content/consent.en.md"), "Plain.\n");
    const lines = [];
    const code = main([], { root, cwd: root, print: (l) => lines.push(l), warn: (l) => lines.push(l) });
    const out = lines.join("\n");
    assert.equal(code, 1, out);
    assert.match(out, /missing: not-affiliated \(README\.md\)/);
    assert.match(out, /skipped \(not there yet\): .*eval\/results\/report\/report\.md/);
    // The app's string table has the screen line; the README, named in the files, counts as missing it (C922). MS8's
    // submission texts come in through a pattern, so until they are written (Nov 4) they are skipped, not missing.
    assert.doesNotMatch(out, /missing: screen-line \(app\/src\/i18n\/en\.ts\)/);
    assert.match(out, /missing: screen-line \(README\.md\)/);
    assert.match(out, /skipped \(not there yet\): .*docs\/submission\/\*\.md/);
  } finally {
    rmSync(root, { recursive: true, force: true });
  }
});

test("importing the module runs no check", () => {
  const run = spawnSync(process.execPath, ["--input-type=module", "-e", `await import(${JSON.stringify(pathToFileURL(script).href)})`], {
    cwd: tmpdir(),
    encoding: "utf8",
  });
  assert.equal(run.status, 0, run.stderr);
  assert.equal(run.stdout, "");
});

// After Task 9's review.

test("a level line is caught in the tables' {level} templates, in both languages", () => {
  assert.deepEqual(ids(hitsOf("app/src/i18n/en.ts", "const a = { k: '{level} deep (MMDA level).' }\n").fails), ["level-line"]);
  assert.deepEqual(ids(hitsOf("app/src/i18n/fil.ts", "const a = { k: '{level} ang lalim (MMDA level).' }\n").fails), ["level-line"]);
  assert.deepEqual(hitsOf("app/src/i18n/fil.ts", "const a = { k: '{level} ang lalim sa spot na ito (MMDA level).' }\n").fails, []);
  for (const file of ["app/src/i18n/en.ts", "app/src/i18n/fil.ts"]) {
    const { fails } = hitsOf(file, readFileSync(join(REPO, file), "utf8"));
    assert.deepEqual(fails, [], file);
  }
});

test("a review hit names the word it matched, even after an allowed sentence", () => {
  const line = "I can't tell you whether to cross or go through. The water at España is knee level, and the road beyond it is dangerous.";
  const { reviews } = hitsOf("notes.md", `${line}\n`);
  assert.deepEqual(
    reviews.map((h) => [h.rule, h.match]),
    [
      ["whole-road", "road"],
      ["claim-danger", "dangerous"],
    ],
  );
});

test("JSON with Windows line ends keeps its keys out and its values in", () => {
  const json = '{\r\n  "a": "x",\r\n  "c":\r\n    "you can cross"\r\n}\r\n';
  const units = textUnits("words.json", json);
  assert.deepEqual(
    units.map((u) => [u.line, u.text]),
    [
      [2, "x"],
      [4, "you can cross"],
    ],
  );
  assert.deepEqual(ids(findHits(units, rules).fails), ["crossing-phrase"]);
});

test("an answers record with no answer text is refused, so --answers can't pass on nothing", () => {
  assert.throws(() => textUnits("a.jsonl", `${JSON.stringify({ id: "T1", answer: { text: "It is safe" } })}\n`), /a\.jsonl:1: no answer text/);
  const { code, out } = cli(
    { "answers.jsonl": `${JSON.stringify({ id: "T1", answer: {} })}\n`, "copy.md": "Plain.\n" },
    () => ["--answers", "answers.jsonl", "copy.md"],
  );
  assert.equal(code, 2, out);
  assert.match(out, /no answer text/);
});
