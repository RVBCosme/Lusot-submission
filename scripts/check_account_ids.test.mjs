// Tests for the account-ID scan in check_account_ids.mjs. Run: node --test "scripts/*.test.mjs"
import assert from "node:assert/strict";
import { execFileSync, spawnSync } from "node:child_process";
import { existsSync, mkdirSync, mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import { test } from "node:test";
import { fileURLToPath } from "node:url";

const script = fileURLToPath(new URL("./check_account_ids.mjs", import.meta.url));
// Built at run time, so this file never holds a 12-digit run itself.
const ID = "1234567" + "89012";

// Runs the scan in a throwaway git repo holding `files` (path to text or bytes). The paths
// in `tracked` are added to git's index (the rest stay untracked), the paths in `deleted`
// are then removed from the working tree, and each folder in `repos` is a nested repo.
function scan(files, { tracked = [], deleted = [], repos = [] } = {}) {
  // A calling git hook sets GIT_DIR, GIT_INDEX_FILE and the like, which would point these
  // git commands at the real repo, so every child gets the environment without them.
  const env = Object.fromEntries(
    Object.entries(process.env).filter(([key]) => !key.startsWith("GIT_")),
  );
  const dir = mkdtempSync(join(tmpdir(), "lusot-scan-"));
  const git = (args, cwd = dir) => execFileSync("git", args, { cwd, env, stdio: "ignore" });
  try {
    git(["init", "--quiet"]);
    for (const repo of repos) {
      mkdirSync(join(dir, repo), { recursive: true });
      git(["init", "--quiet"], join(dir, repo));
    }
    for (const [path, content] of Object.entries(files)) {
      mkdirSync(dirname(join(dir, path)), { recursive: true });
      writeFileSync(join(dir, path), content);
    }
    if (tracked.length) git(["add", "--", ...tracked]);
    for (const path of deleted) rmSync(join(dir, path));
    const run = spawnSync(process.execPath, [script], { cwd: dir, env, encoding: "utf8" });
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
    { tracked: ["docs/note.md"] },
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

test("hex tokens of 32 or more characters are ignored, even with a 12-digit run inside", () => {
  const commit = "ab" + ID + "c".repeat(26); // 40 characters, like a git commit SHA
  const sha256 = "F".repeat(20) + ID + "E".repeat(32); // 64, upper case as Get-FileHash prints it
  const { code, out } = scan({ "docs/evidence.md": `commit ${commit}\nSHA-256 \`${sha256}\`\n` });
  assert.equal(code, 0);
  assert.match(out, /: clean$/m);
});

test("a hex token shorter than 32 characters is still scanned", () => {
  const { code, out } = scan({ "notes.txt": `${"a".repeat(19)}${ID}\n${"a".repeat(20)}${ID}\n` });
  assert.equal(code, 1);
  assert.match(out, /^notes\.txt:1$/m);
  assert.doesNotMatch(out, /^notes\.txt:2$/m);
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

test("directory entries, such as a nested repo, are skipped and counted", () => {
  const { code, out } = scan({ "inner/deep.txt": ID, "top.txt": "ok\n" }, { repos: ["inner"] });
  assert.equal(code, 0);
  assert.match(out, /checked 1 files .*1 directories\): clean$/m);
});

test("a tracked file deleted from the working tree is skipped", () => {
  const { code, out } = scan(
    { "gone.txt": ID, "kept.txt": "ok\n" },
    { tracked: ["gone.txt"], deleted: ["gone.txt"] },
  );
  assert.equal(code, 0);
  assert.match(out, /checked 1 files .*: clean$/m);
});

test("git-ignored files are not scanned", () => {
  const { code, out } = scan({ ".gitignore": "samconfig.toml\n", "samconfig.toml": ID });
  assert.equal(code, 0);
  assert.match(out, /: clean$/m);
});

test("GIT_* variables from a calling git hook never reach the throwaway repo's git", () => {
  const parent = mkdtempSync(join(tmpdir(), "lusot-decoy-"));
  const decoy = join(parent, "decoy.git");
  const before = { GIT_DIR: process.env.GIT_DIR, GIT_INDEX_FILE: process.env.GIT_INDEX_FILE };
  process.env.GIT_DIR = decoy;
  process.env.GIT_INDEX_FILE = join(decoy, "index");
  try {
    const { code, out } = scan({ "docs/note.md": `${ID}\n` }, { tracked: ["docs/note.md"] });
    assert.equal(existsSync(decoy), false, "git wrote to the repo named by GIT_DIR");
    assert.equal(code, 1);
    assert.match(out, /^docs\/note\.md:1$/m);
  } finally {
    for (const [key, value] of Object.entries(before)) {
      if (value === undefined) delete process.env[key];
      else process.env[key] = value;
    }
    rmSync(parent, { recursive: true, force: true });
  }
});
