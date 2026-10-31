// Tests for the licence check in licences.mjs (MS7 Task 8). Run: node --test "scripts/*.test.mjs"
import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import { test } from "node:test";
import { fileURLToPath } from "node:url";

import { classify, missingCredits, missingFromPage, pageEntries, pageNames, productionTree } from "./licences.mjs";

const script = fileURLToPath(new URL("./licences.mjs", import.meta.url));
const policy = JSON.parse(readFileSync(new URL("./licence-policy.json", import.meta.url), "utf8"));
// The cases backend/scripts/test_licences_py.py checks too, so the two tools agree.
const CASES = JSON.parse(readFileSync(new URL("./licence-cases.json", import.meta.url), "utf8"));

test("classify sorts licences into ok, review and fail", () => {
  for (const cls of ["ok", "review", "fail"]) {
    for (const expr of CASES[cls]) assert.equal(classify(expr, policy), cls, `${JSON.stringify(expr)} should be ${cls}`);
  }
});

test("an alias tied to named packages gives any other package review at best", () => {
  for (const { expr, package: pkg, class: cls } of CASES.packaged) assert.equal(classify(expr, policy, pkg), cls, `${expr} for ${pkg}`);
});

// A small lockfile v3: two workspaces, the app depending on the API through its link entry, a
// dev package, a nested copy at another version, an optional package, an optional one that
// isn't installed, and a dependency cycle.
const LOCK = {
  name: "demo",
  lockfileVersion: 3,
  packages: {
    "": { name: "demo", workspaces: ["app", "api"] },
    app: {
      name: "@demo/app",
      dependencies: { a: "^1", "@s/b": "^2", "@demo/api": "*" },
      optionalDependencies: { opt: "^1", gone: "^1" },
      devDependencies: { devtool: "^1" },
    },
    api: { name: "@demo/api", dependencies: { a: "^1", srv: "^1" } },
    "node_modules/@demo/app": { resolved: "app", link: true },
    "node_modules/@demo/api": { resolved: "api", link: true },
    "node_modules/a": { version: "1.0.0", license: "MIT", dependencies: { c: "^1" } },
    "node_modules/c": { version: "1.5.0", license: "ISC", dependencies: { a: "^1" } },
    "node_modules/@s/b": { version: "2.0.0", license: "Apache-2.0", dependencies: { c: "^2" } },
    "node_modules/@s/b/node_modules/c": { version: "2.0.0", license: "BSD-2-Clause" },
    "node_modules/opt": { version: "1.0.0", license: "MIT", optional: true },
    "node_modules/devtool": { version: "1.0.0", license: "GPL-3.0-only", dev: true, dependencies: { devdep: "^1" } },
    "node_modules/devdep": { version: "1.0.0", license: "MIT", dev: true },
    "api/node_modules/srv": { version: "3.0.0", license: "MIT" },
  },
};

test("productionTree walks dependencies nested-first, follows links, and leaves dev packages out", () => {
  const app = productionTree(LOCK, "app");
  assert.deepEqual(
    [...app.values()].map((p) => `${p.name}@${p.version} ${p.license}`).sort(),
    // srv comes through the link to the api workspace, from its own node_modules.
    ["@s/b@2.0.0 Apache-2.0", "a@1.0.0 MIT", "c@1.5.0 ISC", "c@2.0.0 BSD-2-Clause", "opt@1.0.0 MIT", "srv@3.0.0 MIT"],
  );
  const api = productionTree(LOCK, "api");
  assert.deepEqual([...api.values()].map((p) => `${p.name}@${p.version}`).sort(), ["a@1.0.0", "c@1.5.0", "srv@3.0.0"]);
  for (const tree of [app, api]) {
    for (const p of tree.values()) assert.doesNotMatch(p.name, /^(devtool|devdep|demo|@demo\/.*)$/);
  }
  const broken = structuredClone(LOCK);
  delete broken.packages["node_modules/c"];
  assert.throws(() => productionTree(broken, "api"), /c, a dependency of node_modules\/a, is not in the lockfile/);
});

const CREDITS_README = [
  "# x",
  "",
  "## Credits",
  "",
  "| Component | Use | Licence |",
  "|---|---|---|",
  "| [React](https://github.com/facebook/react) | the interface, used without react-leaflet | MIT |",
  "| [Leaflet](https://example.org/leaflet) | the map | BSD-2-Clause |",
  "| [Lucide](x), through `lucide-react` | icons | ISC |",
  "| [Capacitor](https://example.org/capacitor) | wraps the app; marked is a word here | MIT |",
  "",
  "## Next",
  "",
  "| ngeohash | named outside the credits |",
].join("\n");

test("missingCredits reads only the credits table's Component cells", () => {
  const credits = { "react-dom": "React", "@capacitor/core": "Capacitor", "@scope/*": "Leaflet" };
  const names = ["react", "react-dom", "leaflet", "lucide-react", "ngeohash", "@capacitor/core", "@capacitor/camera", "react-leaflet", "facebook", "marked", "@scope/x"];
  assert.deepEqual(missingCredits(names, CREDITS_README, credits), ["ngeohash", "@capacitor/camera", "react-leaflet", "facebook", "marked"]);
});

const rule = "=".repeat(24);
const thin = "-".repeat(24);
const PAGE = [
  "Licences of the code and fonts Lusot is built from.",
  "",
  "PRODUCTION PACKAGES OF THE APP (2)",
  "",
  rule, "leaflet 1.9.4", "License: BSD-2-Clause", thin, "text", rule, "", "more text", "",
  rule, "@capacitor/core 8.5.3", "License: MIT", "Ships: the bridge", thin, "text", "",
  "LIBRARIES IN THE ANDROID APP (1)",
  "",
  rule, "Google Play services", thin, "text", "",
].join("\n");

test("missingFromPage finds a shipped package the licences page leaves out, or lists at another version", () => {
  assert.deepEqual(pageEntries(PAGE), [
    { name: "leaflet", version: "1.9.4" },
    { name: "@capacitor/core", version: "8.5.3" },
    { name: "Google Play services", version: undefined },
  ]);
  assert.deepEqual(pageNames(PAGE), ["leaflet", "@capacitor/core", "Google Play services"]);
  assert.deepEqual(missingFromPage(["leaflet", "@capacitor/core", "react"], PAGE), ["react"]);
  assert.deepEqual(
    missingFromPage([{ name: "leaflet", version: "1.9.4" }, { name: "@capacitor/core", version: "8.6.0" }], PAGE),
    ["@capacitor/core 8.6.0"],
  );
});

function withFiles(files, fn) {
  const dir = mkdtempSync(join(tmpdir(), "lusot-licences-"));
  try {
    for (const [name, content] of Object.entries(files)) {
      mkdirSync(dirname(join(dir, name)), { recursive: true });
      writeFileSync(join(dir, name), content);
    }
    return fn(dir);
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
}

const cli = (args) => spawnSync(process.execPath, [script, ...args], { encoding: "utf8" });
const README = "## Credits\n\n| Component | Use |\n|---|---|\n| a | x |\n| srv | x |\n| @s/b | x |\n| opt | x |\n";

test("the CLI exits 1 on a fake lock with a GPL package, and names it", () => {
  const lock = structuredClone(LOCK);
  lock.packages["node_modules/c"].license = "GPL-3.0-only";
  withFiles({ "package-lock.json": JSON.stringify(lock), "README.md": README }, (dir) => {
    const run = cli(["--lock", join(dir, "package-lock.json"), "--readme", join(dir, "README.md")]);
    assert.equal(run.status, 1, run.stdout + run.stderr);
    assert.match(run.stdout, /^\| c \| 1\.5\.0 \| GPL-3\.0-only \| app, api \| fail \|$/m);
    assert.match(run.stdout, /^FAIL: c@1\.5\.0 \(GPL-3\.0-only\)/m);
  });
});

test("the CLI exits 0 on a clean lock, and 1 when the page or the credits miss a package", () => {
  withFiles({ "package-lock.json": JSON.stringify(LOCK), "README.md": README }, (dir) => {
    const args = ["--lock", join(dir, "package-lock.json"), "--readme", join(dir, "README.md")];
    const clean = cli(args);
    assert.equal(clean.status, 0, clean.stdout + clean.stderr);
    assert.match(clean.stdout, /^\| package \| version \| licence \| ships in \| class \|$/m);
    assert.match(clean.stdout, /^\| a \| 1\.0\.0 \| MIT \| app, api \| ok \|$/m);
    assert.match(clean.stdout, /^\| srv \| 3\.0\.0 \| MIT \| app, api \| ok \|$/m);
    const entry = (head) => [rule, head, thin, "text"];
    const page = [...entry("a 1.0.0"), ...entry("@s/b 2.0.0"), ...entry("c 1.5.0"), ...entry("c 2.0.0"), ...entry("srv 3.0.0"), ""].join("\n");
    writeFileSync(join(dir, "licences.txt"), page);
    const missing = cli([...args, "--page", join(dir, "licences.txt")]);
    assert.equal(missing.status, 1);
    assert.match(missing.stdout, /^NOT ON THE LICENCES PAGE: opt 1\.0\.0$/m);
    writeFileSync(join(dir, "README.md"), README.replace("| @s/b | x |\n", ""));
    const uncredited = cli(args);
    assert.equal(uncredited.status, 1);
    assert.match(uncredited.stdout, /^NOT IN THE README'S CREDITS: @s\/b$/m);
  });
});

test("the CLI classes the build-time code that ships from a development dependency", () => {
  const lock = structuredClone(LOCK);
  const extra = JSON.stringify([{ package: "devtool", ships: "a helper in the page" }]);
  withFiles({ "package-lock.json": JSON.stringify(lock), "README.md": README, "app/scripts/shipped-extra.json": extra }, (dir) => {
    const run = cli(["--lock", join(dir, "package-lock.json"), "--readme", join(dir, "README.md")]);
    assert.equal(run.status, 1, run.stdout + run.stderr);
    assert.match(run.stdout, /^\| devtool \| 1\.0\.0 \| GPL-3\.0-only \| app \(build-time code\) \| fail \|$/m);
  });
});

test("the CLI exits 2 on bad usage or a lockfile it can't walk, with no stack", () => {
  const broken = structuredClone(LOCK);
  broken.packages["node_modules/@demo/api"].resolved = "elsewhere";
  withFiles({ "package-lock.json": JSON.stringify(broken), "README.md": README, "bad.json": "{" }, (dir) => {
    for (const args of [
      ["--lock", join(dir, "package-lock.json"), "--readme", join(dir, "README.md")],
      ["--lock", join(dir, "bad.json")],
      ["--nonsense"],
    ]) {
      const run = cli(args);
      assert.equal(run.status, 2, run.stdout + run.stderr);
      assert.match(run.stderr, /^licences: /m);
      assert.doesNotMatch(run.stderr, /at .*\.mjs:/);
    }
  });
});

test("importing runs nothing", () => {
  const probe = `await import(${JSON.stringify(new URL("./licences.mjs", import.meta.url).href)}); console.log("exit", process.exitCode ?? null);`;
  const run = spawnSync(process.execPath, ["--input-type=module", "-e", probe], { cwd: tmpdir(), encoding: "utf8" });
  assert.equal(run.status, 0, run.stderr);
  assert.equal(run.stdout.trim(), "exit null");
});
