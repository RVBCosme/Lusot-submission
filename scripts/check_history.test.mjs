// Tests for the history scan in check_history.mjs (MS7 Task 7a). Run: node --test "scripts/*.test.mjs"
// Each test builds a throwaway repo. Every planted value (digit runs, email addresses, console
// links, the fake plan's lines) is built at run time, so this file never holds one itself, and
// the scan of this repo's own history stays clean.
import assert from "node:assert/strict";
import { execFileSync, spawnSync } from "node:child_process";
import { randomInt } from "node:crypto";
import { mkdirSync, mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import { test } from "node:test";
import { fileURLToPath } from "node:url";

import { gitRunner, historyEntries, identityDomains, claudeSessionCount, main } from "./check_history.mjs";

const script = fileURLToPath(new URL("./check_history.mjs", import.meta.url));
const at = "@";
const mail = (user, domain) => user + at + domain;
const ID = "1234567" + "89012";
const digits = (n) => Array.from({ length: n }, (_, i) => String(i === 0 ? 1 + randomInt(9) : randomInt(10))).join("");
const AWS_LINK = "https://ap-southeast-1." + "console.aws." + "amazon.com/billing/home";
const SIGNIN_LINK = "https://" + ID + ".signin.aws." + "amazon.com/console";
const META_BILLING = "https://dev.meta." + "ai/billing";
const META_DOCS = "https://dev.meta." + "ai/docs/models";
const META_SUPPORT = "https://dev.meta." + "ai/support";
const IDENTITY = mail("test", "example.com");
const PNG = Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a, 0x00, 0x01]);

// Git's environment for the throwaway repos: no GIT_* variable from a calling hook, and no
// global or system config (which may sign commits or set hooks).
function cleanEnv(home) {
  const env = Object.fromEntries(Object.entries(process.env).filter(([key]) => !key.startsWith("GIT_")));
  delete env.CI;
  delete env.LUSOT_PLAN_TEXT;
  const global = join(home, "gitconfig");
  writeFileSync(global, "");
  return { ...env, GIT_CONFIG_GLOBAL: global, GIT_CONFIG_NOSYSTEM: "1" };
}

function makeRepo() {
  const root = mkdtempSync(join(tmpdir(), "lusot-history-"));
  const dir = join(root, "repo");
  mkdirSync(dir);
  const env = cleanEnv(root);
  const git = (args, input) =>
    execFileSync("git", ["-c", "user.name=test", "-c", `user.email=${IDENTITY}`, ...args], {
      cwd: dir,
      env,
      input,
      encoding: "utf8",
    }).trim();
  git(["init", "-q", "-b", "main"]);
  const repo = {
    root,
    dir,
    env,
    git,
    run: gitRunner(dir, env),
    // Writes `files` (path to text or bytes), stages only those paths, and commits.
    commit(message, files = {}, extra = []) {
      for (const [path, content] of Object.entries(files)) {
        mkdirSync(dirname(join(dir, path)), { recursive: true });
        writeFileSync(join(dir, path), content);
      }
      if (Object.keys(files).length) git(["add", "--", ...Object.keys(files)]);
      git(["commit", "-q", "--allow-empty", ...extra, "-m", message]);
      return git(["rev-parse", "HEAD"]);
    },
    remove(paths, message) {
      git(["rm", "-q", "--", ...paths]);
      git(["commit", "-q", "-m", message]);
      return git(["rev-parse", "HEAD"]);
    },
    // Stages a blob at `path` without writing it to disk, so no folder of that name exists.
    stageBlob(path, content) {
      const blob = git(["hash-object", "-w", "--stdin"], content);
      git(["update-index", "--add", "--cacheinfo", `100644,${blob},${path}`]);
      return blob;
    },
    file(name, content) {
      const path = join(root, name);
      writeFileSync(path, content);
      return path;
    },
    allow(allow = {}) {
      return repo.file("allow.json", JSON.stringify({ blobs: [], images: [], ...allow }));
    },
    // Runs the scan in-process; the default plan path is one that doesn't exist.
    scan(argv, { env = {}, git = repo.run } = {}) {
      const lines = [];
      const code = main(argv, {
        cwd: dir,
        env,
        git,
        out: (line) => lines.push(line),
        err: (line) => lines.push(line),
        defaultPlan: join(root, "no-such-plan.txt"),
      });
      return { code, out: lines.join("\n") };
    },
    cleanup() {
      rmSync(root, { recursive: true, force: true });
    },
  };
  return repo;
}

function withRepo(fn) {
  const repo = makeRepo();
  try {
    return fn(repo);
  } finally {
    repo.cleanup();
  }
}

// A fake plan: random lines of 60 or more characters, with a section 24 holding one number.
function fakePlan(nLines = 20) {
  const letters = "abcdefghijklmnopqrstuvwxyz     ";
  const line = () => Array.from({ length: 64 + randomInt(20) }, () => letters[randomInt(letters.length)]).join("").trim() + "x";
  const lines = Array.from({ length: nLines }, line).map((l) => (l.length >= 60 ? l : l + "y".repeat(60)));
  const number = digits(9);
  const text = [...lines, ["24.", "Manual", "actions"].join(" "), `account ${number}`, ["25.", "Next"].join(" "), ""].join("\n");
  return { lines, number, text };
}

const short = (commit) => commit.slice(0, 7);

test("finds a value that is gone from the working tree", () =>
  withRepo((repo) => {
    const added = repo.commit("add config", { "src/config.ts": `export const acct = "${ID}";\n` });
    repo.commit("drop the value", { "src/config.ts": "export const acct = process.env.ACCT;\n" });
    const { code, out } = repo.scan(["--allow", repo.allow()], { env: { CI: "true" } });
    assert.equal(code, 1);
    assert.match(out, new RegExp(`^${short(added)}:src/config\\.ts twelve-digit$`, "m"));
    assert.doesNotMatch(out, /[0-9]{12}/);
  }));

test("finds plan text and a section-24 number in an old blob", () =>
  withRepo((repo) => {
    const plan = fakePlan();
    const added = repo.commit("notes", {
      "notes/six.md": plan.lines.slice(0, 6).map((l) => `- ${l}`).join("\n") + "\n",
      "notes/five.md": plan.lines.slice(6, 11).join("\n") + "\n",
      "notes/number.md": `see ${plan.number}\n`,
    });
    repo.commit("rewrite", { "notes/six.md": "gone\n", "notes/number.md": "gone\n" });
    const { code, out } = repo.scan(["--allow", repo.allow(), "--plan", repo.file("plan.txt", plan.text)]);
    assert.equal(code, 1);
    assert.match(out, new RegExp(`^${short(added)}:notes/six\\.md plan-lines$`, "m"));
    assert.match(out, new RegExp(`^${short(added)}:notes/number\\.md plan-24$`, "m"));
    assert.doesNotMatch(out, /five\.md/);
  }));

test("finds an email and a console link, but not no-reply ones or example.com", () =>
  withRepo((repo) => {
    const added = repo.commit("docs", {
      "docs/contact.md": `write to ${mail("ops.lead", "lusot-team.test")}\n`,
      "docs/noreply.md": [
        mail("noreply", "anthropic.com"),
        mail("12345+someone", "users.noreply.github.com"),
        mail("someone", "example.com"),
        mail("someone", "mail.example.org"),
        mail("someone", "example.net"),
      ].join("\n"),
      "docs/aws.md": `[billing](${AWS_LINK})\n`,
      "docs/signin.md": `sign in at ${SIGNIN_LINK}\n`,
      "docs/meta.md": `see ${META_BILLING}\n`,
      "docs/public.md": `${META_DOCS} and ${META_SUPPORT}, and the bare host dev.meta.${"ai"}\n`,
      "docs/rule.md": "the rule names the host `console.aws." + "amazon.com` and `signin.aws." + "amazon.com`\n",
    });
    const { code, out } = repo.scan(["--allow", repo.allow()], { env: { CI: "true" } });
    assert.equal(code, 1);
    const c = short(added);
    assert.match(out, new RegExp(`^${c}:docs/contact\\.md email$`, "m"));
    assert.match(out, new RegExp(`^${c}:docs/aws\\.md console-link$`, "m"));
    assert.match(out, new RegExp(`^${c}:docs/signin\\.md console-link$`, "m"));
    assert.match(out, new RegExp(`^${c}:docs/meta\\.md console-link$`, "m"));
    assert.doesNotMatch(out, /noreply\.md|public\.md|rule\.md/);
  }));

test("reads commit messages", () =>
  withRepo((repo) => {
    const digitsCommit = repo.commit(`fix: account ${ID}`);
    const mailCommit = repo.commit(`docs: ask ${mail("someone", "lusot-team.test")}\n\nCo-Authored-By: Bot <${mail("noreply", "anthropic.com")}>`);
    repo.commit(`docs: plain\n\nCo-Authored-By: Bot <${mail("noreply", "anthropic.com")}>`);
    const { code, out } = repo.scan(["--allow", repo.allow()], { env: { CI: "true" } });
    assert.equal(code, 1);
    assert.match(out, new RegExp(`^${short(digitsCommit)} message twelve-digit$`, "m"));
    assert.match(out, new RegExp(`^${short(mailCommit)} message email$`, "m"));
    assert.equal(out.match(/ message /g).length, 2);
    assert.doesNotMatch(out, /[0-9]{12}/);
  }));

test("never reads a sealed path", () =>
  withRepo((repo) => {
    repo.commit("start", { "README.md": "hello\n" });
    const secret = `held ${ID} ${mail("someone", "lusot-team.test")}`;
    const blob = repo.stageBlob("x/sealed/notes.txt", secret);
    const sealedCommit = repo.commit("seal");
    const upper = repo.stageBlob("y/SEALED/answers.txt", "other " + digits(10));
    const upperCommit = repo.commit("seal again");
    const calls = [];
    const spy = (args, input) => {
      calls.push({ args: args.join(" "), input: input === undefined ? "" : String(input) });
      return repo.run(args, input);
    };
    const { code, out } = repo.scan(["--allow", repo.allow()], { env: { CI: "true" }, git: spy });
    assert.equal(code, 1);
    assert.match(out, new RegExp(`^${short(sealedCommit)} sealed-path \\(1 files\\)$`, "m"));
    assert.match(out, new RegExp(`^${short(upperCommit)} sealed-path \\(1 files\\)$`, "m"));
    for (const id of [blob, upper]) {
      assert.ok(calls.every((c) => !c.args.includes(id) && !c.input.includes(id)), "a sealed blob was asked for");
    }
    assert.ok(calls.some((c) => c.args.startsWith("cat-file --batch")), "no blob was read at all");
    assert.doesNotMatch(out, /notes\.txt|answers\.txt|x\/sealed|SEALED/);
    assert.doesNotMatch(out, / email$| twelve-digit$/m);
    // historyEntries hands the sealed blob back unread.
    const entries = [...historyEntries(["main"], spy)];
    assert.equal(entries.find((e) => e.blob === blob).bytes, null);
  }));

test("flags never-commit files", () =>
  withRepo((repo) => {
    const added = repo.commit("files", {
      ".env": "A=1\n",
      "app/.env.local": "A=1\n",
      "backend/samconfig.toml": "x = 1\n",
      "keys/a.keystore": "k",
      "dist/b.apk": "k",
      "data/c.7z": "k",
      "app/.env.example": "A=\n",
    });
    const { code, out } = repo.scan(["--allow", repo.allow()], { env: { CI: "true" } });
    assert.equal(code, 1);
    for (const path of [".env", "app/.env.local", "backend/samconfig.toml", "keys/a.keystore", "dist/b.apk", "data/c.7z"]) {
      assert.match(out, new RegExp(`^${short(added)}:${path.replace(/\./g, "\\.")} never-commit$`, "m"));
    }
    assert.doesNotMatch(out, /\.env\.example/);
  }));

test("flags an image outside the allow-list", () =>
  withRepo((repo) => {
    repo.commit("media", { "docs/media/shot.png": PNG });
    const copied = repo.commit("copy", { "notes/shot.png": PNG });
    const allow = repo.allow({ images: ["docs/media/**"] });
    const { code, out } = repo.scan(["--allow", allow], { env: { CI: "true" } });
    assert.equal(code, 1);
    assert.match(out, new RegExp(`^${short(copied)}:notes/shot\\.png image$`, "m"));
    assert.doesNotMatch(out, /docs\/media/);
  }));

test("allow-lists by exact blob", () =>
  withRepo((repo) => {
    repo.commit("licence", { "models/LICENSE": `Copyright (c) someone <${mail("author", "lusot-team.test")}>\n` });
    const blob = repo.git(["rev-parse", "HEAD:models/LICENSE"]);
    const allow = repo.allow({ blobs: [{ blob, rule: "email", reason: "a notice the licence requires", path: "models/LICENSE" }] });
    const clean = repo.scan(["--allow", allow], { env: { CI: "true" } });
    assert.equal(clean.code, 0, clean.out);
    assert.match(clean.out, /^allow-listed: 1 hit\(s\)$/m);
    const changed = repo.commit("edit", { "models/LICENSE": `Copyright (c) someone else <${mail("author", "lusot-team.test")}>\n` });
    const dirty = repo.scan(["--allow", allow], { env: { CI: "true" } });
    assert.equal(dirty.code, 1);
    assert.match(dirty.out, new RegExp(`^${short(changed)}:models/LICENSE email$`, "m"));
  }));

test("an allow-list entry without a reason, or with an unknown rule, is refused", () =>
  withRepo((repo) => {
    repo.commit("start", { "a.txt": "a\n" });
    const blob = repo.git(["rev-parse", "HEAD:a.txt"]);
    for (const entry of [{ blob, rule: "email", reason: "" }, { blob, rule: "made-up", reason: "x" }, { blob: "abc", rule: "email", reason: "x" }]) {
      const { code } = repo.scan(["--allow", repo.allow({ blobs: [entry] })], { env: { CI: "true" } });
      assert.equal(code, 2);
    }
  }));

test("counts identities without the user part", () =>
  withRepo((repo) => {
    repo.commit("one", { "a.txt": "a\n" });
    repo.commit("two", { "b.txt": "b\n" }, ["--author", `Alice <${mail("alice.author", "dom-a.test")}>`]);
    repo.git(["-c", `user.email=${mail("tom.tagger", "dom-t.test")}`, "tag", "-a", "v1", "-m", "release"]);
    repo.git(["-c", `user.email=${mail("nobody.counted", "dom-x.test")}`, "tag", "-a", "v2", "-m", "not scanned"]);
    const ids = identityDomains(["main", "v1"], repo.run);
    assert.deepEqual(Object.fromEntries(ids.author), { "example.com": 1, "dom-a.test": 1 });
    assert.deepEqual(Object.fromEntries(ids.committer), { "example.com": 2 });
    assert.deepEqual(Object.fromEntries(ids.tagger), { "dom-t.test": 1 });
    const { code, out } = repo.scan(["--refs", "main", "--refs", "v1", "--allow", repo.allow()], { env: { CI: "true" } });
    assert.equal(code, 0, out);
    assert.match(out, /^identities: author dom-a\.test 1, example\.com 1; committer example\.com 2; tagger dom-t\.test 1$/m);
    assert.doesNotMatch(out, /alice\.author|tom\.tagger|dom-x/);
  }));

test("counts Claude-Session trailers", () =>
  withRepo((repo) => {
    const trailer = "Claude-Session: https://claude.ai/code/session_" + "abc";
    repo.commit(`feat: one\n\n${trailer}1`);
    repo.commit("feat: two");
    repo.commit(`feat: three\n\nCo-Authored-By: Bot <${mail("noreply", "anthropic.com")}>\n${trailer}2`);
    assert.equal(claudeSessionCount(["main"], repo.run), 2);
    const { out } = repo.scan(["--allow", repo.allow()], { env: { CI: "true" } });
    assert.match(out, /^Claude-Session trailers: 2 commit\(s\)$/m);
  }));

test("reads a blob that only a merge commit adds", () =>
  withRepo((repo) => {
    repo.commit("base", { "a.txt": "a\n" });
    repo.git(["checkout", "-q", "-b", "side"]);
    repo.commit("side", { "b.txt": "b\n" });
    repo.git(["checkout", "-q", "main"]);
    repo.commit("main", { "c.txt": "c\n" });
    repo.git(["merge", "-q", "--no-ff", "--no-commit", "side"]);
    writeFileSync(join(repo.dir, "evil.txt"), `value ${ID}\n`);
    repo.git(["add", "evil.txt"]);
    repo.git(["commit", "-q", "-m", "merge side"]);
    const merge = repo.git(["rev-parse", "HEAD"]);
    const { code, out } = repo.scan(["--allow", repo.allow()], { env: { CI: "true" } });
    assert.equal(code, 1);
    assert.match(out, new RegExp(`^${short(merge)}:evil\\.txt twelve-digit$`, "m"));
  }));

test("fails closed without the plan", () =>
  withRepo((repo) => {
    repo.commit("start", { "a.txt": "a\n" });
    const allow = repo.allow();
    const exportRun = repo.scan(["--export", "--allow", allow], { env: { CI: "true" } });
    assert.equal(exportRun.code, 2);
    assert.match(exportRun.out, /plan text not found/);
    const ciRun = repo.scan(["--allow", allow], { env: { CI: "true" } });
    assert.equal(ciRun.code, 0, ciRun.out);
    assert.match(ciRun.out, /plan text not found at .*; skipping the plan rules/);
    const laptopRun = repo.scan(["--allow", allow], { env: {} });
    assert.equal(laptopRun.code, 2);
    // A plan path given on purpose must exist, in CI too.
    const named = repo.scan(["--allow", allow, "--plan", join(repo.root, "missing.txt")], { env: { CI: "true" } });
    assert.equal(named.code, 2);
    const fromEnv = repo.scan(["--allow", allow], { env: { CI: "true", LUSOT_PLAN_TEXT: join(repo.root, "missing.txt") } });
    assert.equal(fromEnv.code, 2);
    // A plan with no line of 60 or more characters can't be the plan.
    const short = repo.scan(["--allow", allow, "--plan", repo.file("short.txt", "too short\n")]);
    assert.equal(short.code, 2);
  }));

test("never prints what it found", () =>
  withRepo((repo) => {
    const plan = fakePlan();
    const email = mail("ops.lead", "lusot-team.test");
    repo.commit(`chore: ${ID} ${email}`, {
      "a.md": `${ID}\n${email}\n${AWS_LINK}\n${META_BILLING}\n${plan.number}\n${plan.lines.slice(0, 6).join("\n")}\n`,
      [`exports/bill-${ID}.csv`]: "clean\n",
    });
    const { code, out } = repo.scan(["--allow", repo.allow(), "--plan", repo.file("plan.txt", plan.text)]);
    assert.equal(code, 1);
    assert.match(out, /^[0-9a-f]{7}:exports\/bill-<account>\.csv twelve-digit$/m);
    for (const planted of [ID, email, "ops.lead", AWS_LINK, "console.aws", META_BILLING, plan.number, ...plan.lines.slice(0, 6)]) {
      assert.ok(!out.includes(planted), "the output holds a planted value");
    }
    assert.doesNotMatch(out, /[0-9]{12}/);
  }));

test("a clean history exits 0", () =>
  withRepo((repo) => {
    repo.commit("start", { "README.md": "hello\n", "app/public/icon.png": PNG });
    repo.commit("more", { "src/a.ts": `export const sha = "${"ab".repeat(20)}";\n` });
    const plan = repo.file("plan.txt", fakePlan().text);
    const allow = repo.allow({ images: ["app/public/**"] });
    const inProcess = repo.scan(["--allow", allow, "--plan", plan]);
    assert.equal(inProcess.code, 0, inProcess.out);
    assert.match(inProcess.out, /^history scan: 2 commit\(s\), 3 blob\(s\) read: clean$/m);
    // The command itself, as `node scripts/check_history.mjs` runs it.
    const run = spawnSync(process.execPath, [script, "--refs", "main", "--allow", allow, "--plan", plan], {
      cwd: repo.dir,
      env: repo.env,
      encoding: "utf8",
    });
    assert.equal(run.status, 0, run.stdout + run.stderr);
    assert.match(run.stdout, /: clean$/m);
  }));
