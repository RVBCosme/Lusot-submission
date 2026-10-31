// Tests for check-bundle.mjs. Run: node --test "app/scripts/*.test.mjs"
import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { mkdirSync, mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import { test } from "node:test";
import { fileURLToPath } from "node:url";

const script = fileURLToPath(new URL("./check-bundle.mjs", import.meta.url));
const MARKERS = ["LUSOT_MOCK_API", "LUSOT_E2E_FIXTURE", "api.meta.ai", "MODEL_API_KEY"];

// Runs the check on a throwaway folder holding `files` (path to text or bytes).
function check(files, args) {
  const dir = mkdtempSync(join(tmpdir(), "lusot-bundle-"));
  try {
    for (const [path, content] of Object.entries(files)) {
      mkdirSync(dirname(join(dir, path)), { recursive: true });
      writeFileSync(join(dir, path), content);
    }
    const run = spawnSync(process.execPath, [script, ...(args ?? [dir])], { encoding: "utf8" });
    return { code: run.status, out: run.stdout + run.stderr, dir };
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
}

// A built folder holds licences.txt, which `prebuild` writes (C636).
const CLEAN = {
  "index.html": "<html></html>",
  "assets/index-abc.js": 'console.log("hello");',
  "licences.txt": "leaflet 1.9.4\nBSD 2-Clause License\n",
};

test("a folder with none of the markers passes", () => {
  const { code, out } = check(CLEAN);
  assert.equal(code, 0, out);
  assert.match(out, /clean/);
});

test("a folder with no licences.txt fails, so a skipped prebuild can't ship a missing page", () => {
  const { "licences.txt": _licences, ...without } = CLEAN;
  const { code, out } = check(without);
  assert.equal(code, 1, out);
  assert.match(out, /licences\.txt/);
  assert.match(out, /missing or empty/);
});

test("a licences.txt with nothing in it fails too", () => {
  const { code, out } = check({ ...CLEAN, "licences.txt": "  \n" });
  assert.equal(code, 1, out);
  assert.match(out, /licences\.txt/);
});

test("a licences.txt inside a folder doesn't stand in for the one at the top of dist", () => {
  const { "licences.txt": _licences, ...without } = CLEAN;
  const { code, out } = check({ ...without, "assets/licences.txt": "text\n" });
  assert.equal(code, 1, out);
});

for (const marker of MARKERS) {
  test(`${marker} in a built file fails the check`, () => {
    const { code, out } = check({ ...CLEAN, "assets/app-123.js": `var a="${marker}";` });
    assert.equal(code, 1, out);
    assert.match(out, /assets[\\/]app-123\.js/);
    assert.match(out, new RegExp(marker));
  });
}

test("a marker in a nested folder, inside a larger minified file, still fails", () => {
  const filler = "x".repeat(200_000);
  const hidden = `${filler}headers.set("x","LUSOT_MOCK_API");${filler}`;
  const { code, out } = check({ ...CLEAN, "assets/deep/er/chunk.js": hidden });
  assert.equal(code, 1, out);
  assert.match(out, /chunk\.js/);
});

test("a marker in a binary file fails the check", () => {
  const bytes = Buffer.concat([Buffer.from([0, 255, 1, 2]), Buffer.from("MODEL_API_KEY"), Buffer.from([0, 9])]);
  const { code, out } = check({ ...CLEAN, "assets/blob.bin": bytes });
  assert.equal(code, 1, out);
  assert.match(out, /blob\.bin/);
});

test("the report names files and counts, and never the text around a marker", () => {
  const { code, out } = check({
    ...CLEAN,
    "assets/a.js": 'secret-looking-neighbour LUSOT_MOCK_API another-neighbour LUSOT_MOCK_API',
    "assets/b.js": "api.meta.ai/v1/responses",
  });
  assert.equal(code, 1, out);
  assert.match(out, /a\.js: LUSOT_MOCK_API x2/);
  assert.match(out, /b\.js: api\.meta\.ai x1/);
  assert.doesNotMatch(out, /neighbour/);
  assert.doesNotMatch(out, /v1\/responses/);
});

test("every file with a marker is listed, not only the first", () => {
  const { code, out } = check({ ...CLEAN, "one.js": "LUSOT_E2E_FIXTURE", "two.js": "MODEL_API_KEY" });
  assert.equal(code, 1, out);
  assert.match(out, /one\.js/);
  assert.match(out, /two\.js/);
});

test("a folder that doesn't exist, no folder named, or an empty folder never counts as clean", () => {
  assert.equal(check({}, []).code, 2);
  assert.equal(check({}, [join(tmpdir(), "lusot-bundle-no-such-folder")]).code, 2);
  assert.equal(check({}).code, 2);
});
