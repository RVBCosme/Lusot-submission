// Tests for the account-ID scan in check_account_ids.mjs. Run: node --test "scripts/*.test.mjs"
import assert from "node:assert/strict";
import { execFileSync, spawnSync } from "node:child_process";
import { existsSync, mkdirSync, mkdtempSync, rmSync, symlinkSync, writeFileSync } from "node:fs";
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
// A calling git hook sets GIT_DIR, GIT_INDEX_FILE and the like, which would point these
// git commands at the real repo, so every child gets the environment without them.
function cleanGitEnv() {
  return Object.fromEntries(Object.entries(process.env).filter(([key]) => !key.startsWith("GIT_")));
}

function scan(files, { tracked = [], deleted = [], repos = [] } = {}) {
  const env = cleanGitEnv();
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
  assert.match(out, /1 non-text files/);
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

// UTF-16 with a byte-order mark: little-endian (FF FE) or big-endian (FE FF).
function utf16(text, endian) {
  const le = Buffer.from(text, "utf16le");
  if (endian === "le") return Buffer.concat([Buffer.from([0xff, 0xfe]), le]);
  const be = Buffer.from(le);
  be.swap16();
  return Buffer.concat([Buffer.from([0xfe, 0xff]), be]);
}

test("scans UTF-16 text", () => {
  const { code, out } = scan({
    "res/strings-le.txt": utf16(`first\r\nid ${ID}\r\n`, "le"),
    "res/strings-be.txt": utf16(`first\nsecond\nid ${ID}\n`, "be"),
  });
  assert.equal(code, 1);
  assert.match(out, /^res\/strings-le\.txt:2$/m);
  assert.match(out, /^res\/strings-be\.txt:3$/m);
  assert.match(out, /checked 2 files .*0 non-text files.*: 2 line\(s\) with a 12-digit run/);
  assert.doesNotMatch(out, /[0-9]{12}/);
});

test("flags a 12-digit file name without printing it", () => {
  const { code, out } = scan(
    {
      [`exports/billing-${ID}.csv`]: "clean\n",
      [`exports/notes-${ID}.md`]: `also ${ID}\n`,
      [`exports/photo-${ID}.jpg`]: Buffer.from([0xff, 0xd8, 0xff, 0x00, 0xc3]),
      [`${ID}/twice-${ID}.md`]: "clean\n",
      [`backend/scripts/x-${ID}.py.lock`]: "clean\n",
      [`gone-${ID}.md`]: "clean\n",
      [`repo-${ID}/inner.txt`]: "clean\n",
      "exports/ok.md": "fine\n",
    },
    { tracked: [`gone-${ID}.md`], deleted: [`gone-${ID}.md`], repos: [`repo-${ID}`] },
  );
  assert.equal(code, 1);
  assert.match(out, /^exports\/billing-<account>\.csv \(file name\)$/m);
  assert.match(out, /^exports\/photo-<account>\.jpg \(file name\)$/m);
  assert.match(out, /^exports\/notes-<account>\.md \(file name\)$/m);
  assert.match(out, /^exports\/notes-<account>\.md:1$/m);
  assert.match(out, /^<account>\/twice-<account>\.md \(file name\)$/m);
  assert.match(out, /^backend\/scripts\/x-<account>\.py\.lock \(file name\)$/m);
  assert.match(out, /^gone-<account>\.md \(file name\)$/m);
  assert.match(out, /^repo-<account>\/ \(file name\)$/m);
  assert.match(out, /: 1 line\(s\) with a 12-digit run, 7 path\(s\) with one in the name$/m);
  assert.doesNotMatch(out, /[0-9]{12}/);
});

test("a path that can't be read is reported by its error code alone", { skip: process.platform === "win32" }, () => {
  const dir = mkdtempSync(join(tmpdir(), "lusot-loop-"));
  try {
    // A symlink to itself: stat fails with ELOOP, whose message names the path.
    execFileSync("git", ["init", "--quiet"], { cwd: dir, stdio: "ignore", env: cleanGitEnv() });
    symlinkSync(`loop-${ID}`, join(dir, `loop-${ID}`));
    const run = spawnSync(process.execPath, [script], { cwd: dir, env: cleanGitEnv(), encoding: "utf8" });
    const out = run.stdout + run.stderr;
    assert.equal(run.status, 1, out);
    assert.match(out, /^loop-<account>: unreadable \(ELOOP\)$/m);
    assert.match(out, /1 unreadable path\(s\)$/m);
    assert.doesNotMatch(out, /[0-9]{12}/);
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
});

test("a file name's hex token of 32 or more characters is not flagged", () => {
  const digest = "ab" + ID + "c".repeat(50); // 64 characters, like a SHA-256 digest
  const { code, out } = scan({ [`cache/${digest}.bin`]: "ok\n" });
  assert.equal(code, 0);
  assert.match(out, /: clean$/m);
});

test("still skips binary files", () => {
  const { code, out } = scan({
    "blob.bin": Buffer.concat([Buffer.from([0x00, 0xc3, 0x28, 0xa0]), Buffer.from(ID)]),
    "bad-utf16.txt": Buffer.from([0xff, 0xfe, 0x00, 0xd8, 0x41]), // odd length, lone surrogate
  });
  assert.equal(code, 0);
  assert.match(out, /checked 0 files \(skipped 0 lockfiles, 2 non-text files and 0 directories\): clean$/m);
});

test("importing runs nothing", () => {
  // From a folder that isn't a git repo, a scan run on import would fail on `git ls-files`
  // and print its summary; a clean import prints only what the probe prints.
  const dir = mkdtempSync(join(tmpdir(), "lusot-import-"));
  try {
    const probe = [
      `const m = await import(${JSON.stringify(new URL("./check_account_ids.mjs", import.meta.url).href)});`,
      `const id = "1234567" + "89012";`,
      `console.log(JSON.stringify({`,
      `  exitCode: process.exitCode ?? null,`,
      `  twelve: m.TWELVE_DIGITS.test("x" + id + "y"),`,
      `  hex: ("a".repeat(20) + id).replace(m.LONG_HEX, "") === "",`,
      `  masked: m.maskDigits("a" + id + "-b" + id + "1-c" + id.slice(1) + "/" + id),`,
      `}));`,
    ].join("\n");
    const run = spawnSync(process.execPath, ["--input-type=module", "-e", probe], {
      cwd: dir,
      encoding: "utf8",
    });
    assert.equal(run.status, 0, run.stderr);
    assert.deepEqual(JSON.parse(run.stdout.trim()), {
      exitCode: null,
      twelve: true,
      hex: true,
      masked: `a<account>-b${ID}1-c${ID.slice(1)}/<account>`,
    });
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
});
