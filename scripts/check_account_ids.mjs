// The account-ID scan (R39, R45), part of `npm run check:secrets`. AWS account IDs are 12
// digits, so any run of exactly 12 digits in the repo's files fails the check. Hex tokens of
// 32 or more characters (commit SHAs, SHA-256 digests) are ignored first: a 12-digit run
// inside one is part of a hash, not an ID. It reads what git lists (tracked and untracked,
// minus ignored files) and skips lockfiles (R15), files that aren't UTF-8 text, and directory
// entries such as a nested repo or worktree. It prints path:line and a count, never the
// digits, so the check itself can't leak what it finds. Exit codes: 0 clean, 1 a run found.
import { execFileSync } from "node:child_process";
import { readFileSync, statSync } from "node:fs";
import { basename } from "node:path";

const LOCKFILES = new Set(["uv.lock", "package-lock.json", "requirements.lock.txt"]);
const LONG_HEX = /(?<![0-9a-f])[0-9a-f]{32,}(?![0-9a-f])/gi;
const TWELVE_DIGITS = /(?<![0-9])[0-9]{12}(?![0-9])/;
const utf8 = new TextDecoder("utf-8", { fatal: true });

const paths = execFileSync("git", ["ls-files", "-c", "-o", "--exclude-standard", "-z"], {
  encoding: "utf8",
})
  .split("\0")
  .filter(Boolean);

let checked = 0;
let lockfiles = 0;
let notText = 0;
let directories = 0;
let hits = 0;
for (const path of paths) {
  const name = basename(path);
  if (LOCKFILES.has(name) || name.endsWith(".py.lock")) {
    lockfiles++;
    continue;
  }
  const stat = statSync(path, { throwIfNoEntry: false });
  if (!stat) continue; // tracked, but deleted in the working tree
  if (stat.isDirectory()) {
    directories++; // git lists a nested repo or worktree as one entry
    continue;
  }
  let text;
  try {
    text = utf8.decode(readFileSync(path));
  } catch (err) {
    if (err.code !== "ERR_ENCODING_INVALID_ENCODED_DATA") throw err;
    notText++;
    continue;
  }
  checked++;
  text.split("\n").forEach((line, i) => {
    if (TWELVE_DIGITS.test(line.replace(LONG_HEX, ""))) {
      console.log(`${path}:${i + 1}`);
      hits++;
    }
  });
}

const result = hits ? `${hits} line(s) with a 12-digit run` : "clean";
console.log(
  `account-ID scan: checked ${checked} files (skipped ${lockfiles} lockfiles, ${notText} non-UTF-8 files and ${directories} directories): ${result}`,
);
process.exitCode = hits ? 1 : 0;
