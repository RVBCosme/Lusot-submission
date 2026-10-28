// Tests for the account-ID scan in check_account_ids.mjs. Run: node --test "scripts/*.test.mjs"
import assert from "node:assert/strict";
import { execFileSync, spawnSync } from "node:child_process";
import { mkdirSync, mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import { test } from "node:test";
import { fileURLToPath } from "node:url";

const script = fileURLToPath(new URL("./check_account_ids.mjs", import.meta.url));
// Built at run time, so this file never holds a 12-digit run itself.
const ID = "1234567" + "89012";

// Runs the scan in a throwaway git repo holding `files` (path to text or bytes).
// The paths in `tracked` are added to git's index; the rest stay untracked.
function scan(files, tracked = []) {
  const dir = mkdtempSync(join(tmpdir(), "lusot-scan-"));
  try {
    execFileSync("git", ["init", "--quiet"], { cwd: dir, stdio: "ignore" });
    for (const [path, content] of Object.entries(files)) {
      mkdirSync(dirname(join(dir, path)), { recursive: true });
      writeFileSync(join(dir, path), content);
    }
    if (tracked.length) execFileSync("git", ["add", "--", ...tracked], { cwd: dir, stdio: "ignore" });
    const run = spawnSync(process.execPath, [script], { cwd: dir, encoding: "utf8" });
    return { code: run.status, out: run.stdout + run.stderr };
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
}

test("12-digit runs are reported by path and line, never by their digits", () => {
  const { code, out } = scan(
    {
      "docs/note.md": `intro\narn:aws:iam::${ID}:root\n`,
      "src/a.ts": `const account = "acct${ID}x";\n`,
    },
    ["docs/note.md"],
  );
  assert.equal(code, 1);
  assert.match(out, /^docs\/note\.md:2$/m);
  assert.match(out, /^src\/a\.ts:1$/m);
  assert.match(out, /2 line\(s\) with a 12-digit run/);
  assert.doesNotMatch(out, /[0-9]{12}/);
});

test("longer and shorter digit runs pass", () => {
  const { code, out } = scan({ "notes.txt": `${ID}3\n${ID.slice(1)}\n` });
  assert.equal(code, 0);
  assert.match(out, /checked 1 files .*: clean$/m);
});

test("lockfiles are skipped, and only lockfiles", () => {
  const { code, out } = scan({
    "backend/analysis/uv.lock": ID,
    "package-lock.json": ID,
    "backend/scripts/smoke_upload.py.lock": ID,
    "backend/analysis/requirements.lock.txt": ID,
    "backend/analysis/requirements.txt": ID,
  });
  assert.equal(code, 1);
  assert.match(out, /^backend\/analysis\/requirements\.txt:1$/m);
  assert.match(out, /skipped 4 lockfiles/);
  assert.match(out, /1 line\(s\) with a 12-digit run/);
});

test("files that aren't UTF-8 text are skipped; UTF-8 beyond ASCII is scanned", () => {
  const { code, out } = scan({
    "photo.jpg": Buffer.concat([Buffer.from([0xff, 0xd8, 0xff]), Buffer.from(ID)]),
    "docs/plan-notes.md": `España, depth ≤ ${ID}\n`,
  });
  assert.equal(code, 1);
  assert.match(out, /^docs\/plan-notes\.md:1$/m);
  assert.doesNotMatch(out, /photo\.jpg/);
  assert.match(out, /1 non-UTF-8 files/);
});

test("git-ignored files are not scanned", () => {
  const { code, out } = scan({ ".gitignore": "samconfig.toml\n", "samconfig.toml": ID });
  assert.equal(code, 0);
  assert.match(out, /: clean$/m);
});
