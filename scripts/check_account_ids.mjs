// The account-ID scan (R39, R45), part of `npm run check:secrets`. AWS account IDs are 12
// digits, so any run of exactly 12 digits in the repo's files, or in their paths, fails the
// check, and so do 12 digits in dashed groups of four, as the AWS console shows an ID. Hex tokens of 32 or more characters (commit SHAs, SHA-256 digests) are ignored
// first: a 12-digit run inside one is part of a hash, not an ID. It reads what git lists
// (tracked and untracked, minus ignored files) and skips lockfiles (R15), files that aren't
// text, and directory entries such as a nested repo or worktree. Text is UTF-8, or UTF-16
// with a byte-order mark (MS7's D-h). It prints path:line and a count, never the digits,
// and masks any 12-digit run in a printed path, so the check itself can't leak what it
// finds. Exit codes: 0 clean, 1 a run found or a path that can't be read.
import { execFileSync } from "node:child_process";
import { readFileSync, statSync } from "node:fs";
import { basename } from "node:path";

// Shared with the history scan (scripts/check_history.mjs, MS7's Task 7a). LONG_HEX carries
// the `g` flag, so use it only with `replace`, never with `test` or `exec`.
export const LONG_HEX = /(?<![0-9a-f])[0-9a-f]{32,}(?![0-9a-f])/gi;
export const TWELVE_DIGITS = /(?<![0-9])[0-9]{12}(?![0-9])/;
// The same 12 digits as the AWS console's account menu shows them, in groups of four. A group
// of a UUID, which a hex digit and a dash sit next to, is left alone.
export const DASHED_ID = /(?<![0-9]|[0-9a-f]-)[0-9]{4}-[0-9]{4}-[0-9]{4}(?![0-9]|-[0-9a-f])/i;

// Replaces each run of exactly 12 digits, dashed or not, with `<account>`, for any path or
// text printed.
export function maskDigits(text) {
  return text
    .replace(new RegExp(DASHED_ID.source, "g"), "<account>")
    .replace(new RegExp(TWELVE_DIGITS.source, "g"), "<account>");
}

// True when `text` holds a 12-digit run, dashed or not, outside a long hex token.
export function hasTwelveDigits(text) {
  const bare = text.replace(LONG_HEX, "");
  return TWELVE_DIGITS.test(bare) || DASHED_ID.test(bare);
}

const LOCKFILES = new Set(["uv.lock", "package-lock.json", "requirements.lock.txt"]);

// Lockfiles are skipped (R15): their hashes hold digit runs that aren't IDs.
export function isLockfile(path) {
  const name = basename(path);
  return LOCKFILES.has(name) || name.endsWith(".py.lock");
}

// Decodes UTF-8 (a UTF-8 BOM is dropped), or UTF-16 when the bytes start with its BOM.
// Returns null for anything else, such as a binary file.
export function decodeText(bytes) {
  let encoding = "utf-8";
  if (bytes[0] === 0xff && bytes[1] === 0xfe) encoding = "utf-16le";
  else if (bytes[0] === 0xfe && bytes[1] === 0xff) encoding = "utf-16be";
  try {
    return new TextDecoder(encoding, { fatal: true }).decode(bytes);
  } catch (err) {
    if (err.code !== "ERR_ENCODING_INVALID_ENCODED_DATA") throw err;
    return null;
  }
}

if (import.meta.main === undefined) throw new Error("scripts/check_account_ids.mjs needs Node 22.18 or newer");
// Scans only when run as `node scripts/check_account_ids.mjs`, so a test or the history scan
// can import the rules above.
if (import.meta.main) {
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
  let names = 0;
  let unreadable = 0;
  for (const path of paths) {
    const shown = maskDigits(path);
    if (hasTwelveDigits(path)) {
      console.log(`${shown} (file name)`);
      names++;
    }
    if (isLockfile(path)) {
      lockfiles++;
      continue;
    }
    // A file system error names the path in its message, so it is reported by its code only.
    let bytes;
    try {
      const stat = statSync(path, { throwIfNoEntry: false });
      if (!stat) continue; // tracked, but deleted in the working tree
      if (stat.isDirectory()) {
        directories++; // git lists a nested repo or worktree as one entry
        continue;
      }
      bytes = readFileSync(path);
    } catch (err) {
      console.log(`${shown}: unreadable (${err.code ?? "error"})`);
      unreadable++;
      continue;
    }
    const text = decodeText(bytes);
    if (text === null) {
      notText++;
      continue;
    }
    checked++;
    text.split("\n").forEach((line, i) => {
      if (hasTwelveDigits(line)) {
        console.log(`${shown}:${i + 1}`);
        hits++;
      }
    });
  }

  const found = [];
  if (hits) found.push(`${hits} line(s) with a 12-digit run`);
  if (names) found.push(`${names} path(s) with one in the name`);
  if (unreadable) found.push(`${unreadable} unreadable path(s)`);
  console.log(
    `account-ID scan: checked ${checked} files (skipped ${lockfiles} lockfiles, ${notText} non-text files and ${directories} directories): ${found.join(", ") || "clean"}`,
  );
  process.exitCode = hits || names || unreadable ? 1 : 0;
}
