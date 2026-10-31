// Tests for the deny rules in .claude/settings.json (MS7 Task 11; D-a, and D-n's static check).
// Run: node --test "scripts/*.test.mjs". Claude Code reads these rules in every session in this
// repo. This test only reads the settings file: it never tries a rule on a real path, and
// never reads backend/samconfig.toml or a sealed path (C823).
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";

const settings = JSON.parse(readFileSync(new URL("../.claude/settings.json", import.meta.url), "utf8"));
const deny = settings.permissions?.deny ?? [];
const allow = settings.permissions?.allow ?? [];

// Each sealed path in the four spellings Windows opens as the same folder (Rene, Oct 30), and
// the raw Set A and A-neg photos: the rules MS1 and MS2 wrote, which must all stay.
const SPELLINGS = ["sealed", "sealed.", "sealed ", "sealed::$INDEX_ALLOCATION"];
const SEALED_ROOTS = ["./eval/", "//c/Systems/Lusot/lusot/eval/", "//c/Systems/Lusot/lusot-data/**/"];
const EXISTING = [
  ...SEALED_ROOTS.flatMap((root) => SPELLINGS.flatMap((s) => [`Read(${root}${s}/**)`, `Edit(${root}${s}/**)`])),
  ...["set_a", "a_neg"].flatMap((set) => [`Read(//c/Systems/Lusot/lusot-data/${set}/raw/**)`, `Edit(//c/Systems/Lusot/lusot-data/${set}/raw/**)`]),
];
// D-a (R44's R6): the alarm email's config and env files are never read, and lockfiles are
// never edited by hand.
const ADDED = [
  "Read(./backend/samconfig.toml)",
  "Read(./**/.env)",
  "Read(./**/.env.local)",
  "Read(./**/.env.*.local)",
  "Edit(./**/package-lock.json)",
  "Edit(./**/uv.lock)",
  "Edit(./**/*.py.lock)",
  "Edit(./**/requirements.lock.txt)",
];

// Edit rules cover every built-in tool that edits files, and Read rules the tools that read
// them, so an allow for any of those tools counts against the rule's family.
const FAMILY = { Read: "Read", Grep: "Read", Glob: "Read", Edit: "Edit", Write: "Edit", MultiEdit: "Edit", NotebookEdit: "Edit" };

function parseRule(rule) {
  const m = /^([A-Za-z]+)(?:\((.*)\))?$/.exec(rule);
  return m ? { tool: m[1], spec: m[2] } : null;
}

// A rule's pattern as a regular expression, in gitignore's syntax: `**` spans folders, `*` and
// `?` stay inside one name, and both match a name that starts with a dot. Case is ignored, as
// the laptop's file system ignores it.
function globToRegex(glob) {
  let re = "";
  for (let i = 0; i < glob.length; i++) {
    const rest = glob.slice(i);
    if (rest.startsWith("**/")) {
      re += "(?:.*/)?";
      i += 2;
    } else if (rest.startsWith("/**") && i + 3 === glob.length) {
      re += "(?:/.*)?";
      i += 2;
    } else if (rest.startsWith("**")) {
      re += ".*";
      i += 1;
    } else if (glob[i] === "*") re += "[^/]*";
    else if (glob[i] === "?") re += "[^/]";
    else re += glob[i].replace(/[.+^${}()|[\]\\]/g, "\\$&");
  }
  return new RegExp(`^${re}$`, "i");
}

// One place for every path: `P:/` and a project path (from `./x`, `/x`, a bare pattern, or
// the main worktree's absolute path), or `A:/` and an absolute one (from `//x`). A bare
// pattern with no slash matches at any depth, as in gitignore.
const ROOT = "//c/Systems/Lusot/lusot/";
function place(spec) {
  if (spec.toLowerCase().startsWith(ROOT.toLowerCase())) return `P:/${spec.slice(ROOT.length)}`;
  if (spec.startsWith("//")) return `A:/${spec.slice(2)}`;
  if (spec.startsWith("/")) return `P:/${spec.slice(1)}`;
  if (spec.startsWith("./")) return `P:/${spec.slice(2)}`;
  if (spec.startsWith("~/")) return `H:/${spec.slice(2)}`;
  return spec.includes("/") ? `P:/${spec}` : `P:/**/${spec}`;
}

const covers = (spec, path) => globToRegex(place(spec)).test(place(path));

// The real files the deny rules protect, by the family of tools that would reach them.
const SEALED = ["sealed", "sealed.", "sealed ", "sealed::$INDEX_ALLOCATION"].map((s) => `./eval/${s}/answers.json`);
const DATA = ["//c/Systems/Lusot/lusot-data/set_b/sealed/car.jpg", "//c/Systems/Lusot/lusot-data/set_a/raw/post.jpg", "//c/Systems/Lusot/lusot-data/a_neg/raw/post.jpg"];
const PROTECTED = {
  Read: ["./backend/samconfig.toml", "./.env", "./app/.env", "./app/.env.local", "./app/.env.development.local", ...SEALED, ...DATA],
  Edit: [
    "./package-lock.json",
    "./app/package-lock.json",
    "./backend/analysis/uv.lock",
    "./backend/scripts/smoke_upload.py.lock",
    "./eval/data/intake.py.lock",
    "./backend/analysis/requirements.lock.txt",
    ...SEALED,
    ...DATA,
  ],
};

// Whether an allow rule would grant one of the protected files: a bare tool name of a family,
// or a pattern that covers one of that family's files, whatever its anchor.
export function allowGrantsProtected(allowRule) {
  const a = parseRule(allowRule);
  const family = a && FAMILY[a.tool];
  if (!family) return false;
  if (a.spec === undefined || a.spec === "") return true;
  return PROTECTED[family].some((path) => covers(a.spec, path));
}

test("keeps every deny rule", () => {
  for (const rule of [...EXISTING, ...ADDED]) assert.ok(deny.includes(rule), `missing deny rule ${rule}`);
  // Exactly these, once each: a rule added here, such as a broad Edit(./**), changes this test too.
  assert.deepEqual([...new Set(deny)].sort(), [...EXISTING, ...ADDED].sort());
  assert.equal(deny.length, new Set(deny).size, "a deny rule is listed twice");
  for (const entry of allow) assert.ok(!allowGrantsProtected(entry), `allow rule ${entry} would grant a file a deny rule protects`);
});

test("every Read or Edit deny rule names an anchored path", () => {
  for (const rule of deny) {
    const parsed = parseRule(rule);
    if (!parsed || !["Read", "Edit"].includes(parsed.tool)) continue;
    assert.match(parsed.spec ?? "", /^(\.\/|\/)/, `${rule} names no ./, / or // path`);
  }
  // Each sealed or raw folder is closed to both reading and editing.
  for (const rule of deny.filter((r) => /sealed|\/raw\//.test(r))) {
    const twin = rule.startsWith("Read(") ? rule.replace(/^Read/, "Edit") : rule.replace(/^Edit/, "Read");
    assert.ok(deny.includes(twin), `${rule} has no ${twin}`);
  }
});

test("each added rule covers the files it is for", () => {
  const cases = {
    "Read(./**/.env)": ["./.env", "./app/.env"],
    "Read(./**/.env.local)": ["./.env.local", "./app/.env.local"],
    "Read(./**/.env.*.local)": ["./app/.env.development.local", "./.env.production.local"],
    "Edit(./**/package-lock.json)": ["./package-lock.json"],
    "Edit(./**/uv.lock)": ["./backend/analysis/uv.lock"],
    "Edit(./**/*.py.lock)": ["./backend/scripts/smoke_upload.py.lock", "./eval/data/intake.py.lock"],
    "Edit(./**/requirements.lock.txt)": ["./backend/analysis/requirements.lock.txt"],
  };
  for (const [rule, paths] of Object.entries(cases)) {
    for (const path of paths) assert.ok(covers(parseRule(rule).spec, path), `${rule} doesn't cover ${path}`);
  }
  assert.ok(!covers("./**/.env", "./app/.env.example"), "the env rule must leave .env.example readable");
});

test("the allow check finds an allow that would grant a protected file", () => {
  for (const rule of [
    "Read",
    "Edit",
    "Read(./**)",
    "Read(./app/.env*)",
    "Read(*.env)",
    "Read(/backend/**)",
    "Read(//c/Systems/Lusot/lusot/**)",
    "Read(./BACKEND/**)",
    "Read(./**/*.json)",
    "Grep(./eval/**)",
    "Edit(./backend/analysis/*.lock)",
    "Write(./**/*.json)",
    "Read(//c/Systems/Lusot/lusot-data/**)",
  ]) {
    assert.ok(allowGrantsProtected(rule), `${rule} should count as granting a protected file`);
  }
  for (const rule of ["Read(./docs/**)", "Edit(./docs/**)", "Edit(./app/src/*.ts)", "Read(./app/.env.example)", "Bash(npm run check)", "Read(~/notes/**)"]) {
    assert.ok(!allowGrantsProtected(rule), `${rule} grants no protected file`);
  }
});
