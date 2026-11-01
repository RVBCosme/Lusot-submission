// Tests for the link check in check_links.mjs (MS8 Task 2, C922). Run: node --test scripts/check_links.test.mjs
import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { mkdirSync, mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import { test } from "node:test";
import { fileURLToPath } from "node:url";
import { checkLinks } from "./check_links.mjs";

const script = fileURLToPath(new URL("./check_links.mjs", import.meta.url));
const PRIVATE = "RVBCosme/lusot";

// A throwaway folder holding `files`, given to `body`, then removed.
function inFolder(files, body) {
  const dir = mkdtempSync(join(tmpdir(), "lusot-links-"));
  try {
    for (const [path, content] of Object.entries(files)) {
      mkdirSync(dirname(join(dir, path)), { recursive: true });
      writeFileSync(join(dir, path), content);
    }
    return body(dir);
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
}

const check = (markdown, files = {}) => inFolder(files, (dir) => checkLinks(markdown, dir, { privateRepo: PRIVATE }));

test("a relative link to a missing file is found", () => {
  assert.deepEqual(check("See [x](docs/nope.md).\n"), ["1: missing-target"]);
});

test("a relative image, or a reference-style link, to a missing file is found", () => {
  assert.deepEqual(check("Text.\n![overlay](docs/media/nope.gif)\n"), ["2: missing-target"]);
  assert.deepEqual(check("[rules]: eval/rules.md\n"), ["1: missing-target"]);
});

test("an anchor on an existing file passes, and so does a file in a subfolder", () => {
  const files = { "README.md": "# Lusot\n", "eval/rules.md": "# Rules\n" };
  assert.deepEqual(check("[x](README.md#judge-path) [y](./eval/rules.md) [z](<eval/rules.md>)\n", files), []);
});

test("a link to the private repository is found, with or without a path, in any case", () => {
  assert.deepEqual(check("[x](https://github.com/RVBCosme/lusot/blob/main/README.md)\n"), ["1: private-repo"]);
  assert.deepEqual(check("Code: https://github.com/rvbcosme/LUSOT\n"), ["1: private-repo"]);
  assert.deepEqual(check("[x](https://github.com/RVBCosme/lusot)\n[y](https://github.com/RVBCosme/lusot#readme)\n"), [
    "1: private-repo",
    "2: private-repo",
  ]);
});

test("a link to another repository passes, the submission repository included", () => {
  assert.deepEqual(check("[x](https://github.com/RVBCosme/lusot-submission)\n"), []);
  assert.deepEqual(check("git clone https://github.com/RVBCosme/Lusot-submission lusot\n"), []);
  assert.deepEqual(check("[x](https://github.com/RVBCosme/lusot.js)\n"), []);
});

test("external links, mail links and in-page anchors aren't checked as files", () => {
  assert.deepEqual(check("[a](https://example.com/x.md) [b](#top) [c](mailto:x@example.com) [d](//cdn.example.com/a)\n"), []);
});

test("the CLI: 1 with problems, 0 when clean, 2 without --private-repo or a file", () => {
  inFolder({ "bad.md": "[x](nope.md)\n", "good.md": "[x](good.md)\n" }, (dir) => {
    const run = (...args) => spawnSync(process.execPath, [script, ...args], { cwd: dir, encoding: "utf8" });
    const bad = run("--private-repo", PRIVATE, "bad.md");
    assert.equal(bad.status, 1, bad.stdout + bad.stderr);
    assert.match(bad.stdout, /bad\.md:1: missing-target/);
    assert.equal(run("--private-repo", PRIVATE, "good.md").status, 0);
    assert.equal(run("good.md").status, 2);
    assert.equal(run("--private-repo", PRIVATE).status, 2);
    assert.equal(run("--private-repo", PRIVATE, "missing.md").status, 2);
  });
});
