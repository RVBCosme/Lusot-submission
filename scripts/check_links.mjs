// The link check (MS8 Task 2, C922): what a link in a public Markdown file would break once the repository is public.
// - missing-target: a relative link, image or reference-style link whose target, without its #anchor or ?query, isn't
//   there under the file's own folder
// - private-repo: any link to the private development repository, with or without a path, in any case (GitHub's owner
//   and repository names aren't case-sensitive). A repository whose name only starts the same, such as
//   lusot-submission, passes.
// External links (any scheme, or starting `//`) and in-page anchors are not checked as files.
//
// Usage: node scripts/check_links.mjs --private-repo <owner/name> <file>...
// It prints `<file>:<line>: <rule>` per problem. Exit codes: 0 clean, 1 problems, 2 bad usage or an unreadable file.
import { existsSync, readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";

// An inline link or image: [text](target "title"), the target optionally in <angle brackets>.
const INLINE = /!?\[[^\]]*\]\(\s*(<[^>]*>|[^\s)]+)(?:\s+"[^"]*")?\s*\)/g;
// A reference definition: [label]: target
const REFERENCE = /^\s{0,3}\[[^\]]+\]:\s*(<[^>]*>|\S+)/;
const SCHEME = /^[a-z][a-z0-9+.-]*:/i;

const escape = (text) => text.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");

function isMissing(target, baseDir) {
  const bare = target.replace(/^<|>$/g, "");
  if (bare === "" || bare.startsWith("#") || bare.startsWith("//") || SCHEME.test(bare)) return false;
  const path = bare.split("#")[0].split("?")[0];
  if (path === "") return false;
  let decoded;
  try {
    decoded = decodeURIComponent(path);
  } catch {
    decoded = path;
  }
  return !existsSync(resolve(baseDir, decoded.replace(/^\/+/, "")));
}

// The problems in `markdown`, a file in `baseDir`, as "<line>: <rule>", in line order.
export function checkLinks(markdown, baseDir, { privateRepo }) {
  const privateLink = new RegExp(`https?://(?:www\\.)?github\\.com/${escape(privateRepo)}(?![A-Za-z0-9._-])`, "gi");
  const problems = [];
  String(markdown)
    .split(/\r?\n/)
    .forEach((line, index) => {
      const at = index + 1;
      for (const match of line.matchAll(INLINE)) if (isMissing(match[1], baseDir)) problems.push(`${at}: missing-target`);
      const reference = REFERENCE.exec(line);
      if (reference && isMissing(reference[1], baseDir)) problems.push(`${at}: missing-target`);
      for (const _ of line.matchAll(privateLink)) problems.push(`${at}: private-repo`);
    });
  return problems;
}

export function main(argv, { out = console.log, err = console.error } = {}) {
  const at = argv.indexOf("--private-repo");
  const privateRepo = at >= 0 ? argv[at + 1] : undefined;
  const files = argv.filter((_, i) => i !== at && i !== at + 1);
  if (!privateRepo || !/^[^/\s]+\/[^/\s]+$/.test(privateRepo) || files.length === 0) {
    err("usage: node scripts/check_links.mjs --private-repo <owner/name> <file>...");
    return 2;
  }
  let found = 0;
  for (const file of files) {
    let text;
    try {
      text = readFileSync(file, "utf8");
    } catch {
      err(`can't read ${file}`);
      return 2;
    }
    for (const problem of checkLinks(text, dirname(resolve(file)), { privateRepo })) {
      out(`${file}:${problem}`);
      found += 1;
    }
  }
  out(`link check: ${files.length} file(s), ${found} problem(s)`);
  return found > 0 ? 1 : 0;
}

if (import.meta.main === undefined) throw new Error("scripts/check_links.mjs needs Node 22.18 or newer");
if (import.meta.main) process.exit(main(process.argv.slice(2)));
