// Tests for the deny rules in .claude/settings.json (MS7 Task 11; D-a, and D-n's static check).
// Run: node --test "scripts/*.test.mjs". Claude Code reads these rules in every session in this
// repo. This test only reads the settings file: it never tries a rule on a real path, and
// never reads backend/samconfig.toml or a sealed path (C823).
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { posix } from "node:path";
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

// Concrete paths a pattern covers: `**` as no folder and as one, `*` as a name.
function samples(spec) {
  const forms = new Set([spec.replace(/\/\*\*\//g, "/"), spec.replace(/\/\*\*\//g, "/x/")]);
  return [...forms].map((s) => s.replace(/\/\*\*$/, "/x").replace(/\*/g, "x"));
}

// Rules follow gitignore's syntax, where `*` and `**` match a name that starts with a dot too;
// Node's matchesGlob doesn't, so such a name's dot is swapped for a plain letter on both sides.
const bare = (spec) =>
  spec
    .replace(/^\.\//, "")
    .replace(/^\/\//, "/")
    .split("/")
    .map((part) => (part.startsWith(".") && part !== "." && part !== ".." ? `_dot_${part.slice(1)}` : part))
    .join("/");
const covers = (glob, path) => posix.matchesGlob(bare(path), bare(glob));

// Whether an allow rule would grant any path a deny rule refuses: a bare tool name, the same
// pattern, or a pattern either side's sample paths fall under (with the deny's tail tried
// under the allow's folder, for a deny that starts `./**/`).
export function allowMatches(allowRule, denyRule) {
  const a = parseRule(allowRule);
  const d = parseRule(denyRule);
  if (!a || !d || (FAMILY[a.tool] ?? a.tool) !== (FAMILY[d.tool] ?? d.tool)) return false;
  if (a.spec === undefined || a.spec === "" || a.spec === d.spec) return true;
  const tried = [...samples(d.spec)];
  const folder = a.spec.replace(/\/\*\*?$/, "");
  if (d.spec.startsWith("./**/") && folder !== a.spec) tried.push(...samples(`${folder}/${d.spec.slice(5)}`));
  return tried.some((path) => covers(a.spec, path)) || samples(a.spec).some((path) => covers(d.spec, path));
}

test("keeps every deny rule", () => {
  for (const rule of [...EXISTING, ...ADDED]) assert.ok(deny.includes(rule), `missing deny rule ${rule}`);
  for (const rule of [...EXISTING, ...ADDED]) {
    for (const entry of allow) assert.ok(!allowMatches(entry, rule), `allow rule ${entry} matches deny rule ${rule}`);
  }
});

test("every deny rule is a Read or Edit rule on a project or absolute path", () => {
  for (const rule of deny) {
    const parsed = parseRule(rule);
    assert.ok(parsed && ["Read", "Edit"].includes(parsed.tool), `${rule} is not a Read or Edit rule`);
    assert.match(parsed.spec, /^(\.\/|\/\/)/, `${rule} names neither a project path (./) nor an absolute one (//)`);
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

test("the allow check finds an allow that would grant a denied path", () => {
  assert.ok(allowMatches("Read", "Read(./**/.env)"));
  assert.ok(allowMatches("Read(./**)", "Read(./backend/samconfig.toml)"));
  assert.ok(allowMatches("Read(./app/**)", "Read(./**/.env.local)"));
  assert.ok(allowMatches("Write(./**/*.json)", "Edit(./**/package-lock.json)"));
  assert.ok(allowMatches("Grep(./eval/**)", "Read(./eval/sealed/**)"));
  assert.ok(!allowMatches("Read(./docs/**)", "Read(./backend/samconfig.toml)"));
  assert.ok(allowMatches("Edit(./app/src/**)", "Edit(./**/uv.lock)")); // it would grant app/src/uv.lock
  assert.ok(!allowMatches("Edit(./app/src/*.ts)", "Edit(./**/uv.lock)"));
  assert.ok(!allowMatches("Bash(npm run check)", "Read(./**/.env)"));
});
