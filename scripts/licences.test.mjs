// Tests for the licence check in licences.mjs (MS7 Task 8). Run: node --test "scripts/*.test.mjs"
import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { test } from "node:test";
import { fileURLToPath } from "node:url";

import { classify, missingCredits, missingFromPage, pageNames, productionTree } from "./licences.mjs";

const script = fileURLToPath(new URL("./licences.mjs", import.meta.url));
const policy = JSON.parse(readFileSync(new URL("./licence-policy.json", import.meta.url), "utf8"));

// The cases test_licences_py.py checks too, so the two tools agree.
const CASES = {
  ok: ["MIT", "(MIT OR Apache-2.0)", "BSD-3-Clause", "Apache License, Version 2.0", "Apache 2.0", "MIT OR GPL-3.0-only", "0BSD AND ISC", "BSD License OR Apache Software License", "mit or apache-2.0"],
  review: ["MPL-2.0", "MIT AND LGPL-2.1-only", "SAM License", "SEE LICENSE IN LICENSE.md", "CC-BY-SA-4.0", "ODbL-1.0", "MPL-2.0 AND MIT"],
  fail: ["GPL-3.0-only", "AGPL-3.0", "CC-BY-NC-4.0", "CC-BY-NC-SA-4.0", "", "Some Custom Licence", "UNLICENSED", "MIT AND GPL-2.0-or-later", "(MIT"],
};

test("classify sorts licences into ok, review and fail", () => {
  for (const [expected, exprs] of Object.entries(CASES)) {
    for (const expr of exprs) assert.equal(classify(expr, policy), expected, `${JSON.stringify(expr)} should be ${expected}`);
  }
});

// A small lockfile v3: two workspaces, a link entry, a dev package, a nested copy at another
// version, an optional package, and an optional one that isn't installed.
const LOCK = {
  name: "demo",
  lockfileVersion: 3,
  packages: {
    "": { name: "demo", workspaces: ["app", "api"] },
    app: {
      name: "@demo/app",
      dependencies: { a: "^1", "@s/b": "^2" },
      optionalDependencies: { opt: "^1", gone: "^1" },
      devDependencies: { devtool: "^1" },
    },
    api: { name: "@demo/api", dependencies: { a: "^1", srv: "^1" } },
    "node_modules/@demo/app": { resolved: "app", link: true },
    "node_modules/@demo/api": { resolved: "api", link: true },
    "node_modules/a": { version: "1.0.0", license: "MIT", dependencies: { c: "^1" } },
    "node_modules/c": { version: "1.5.0", license: "ISC" },
    "node_modules/@s/b": { version: "2.0.0", license: "Apache-2.0", dependencies: { c: "^2" } },
    "node_modules/@s/b/node_modules/c": { version: "2.0.0", license: "BSD-2-Clause" },
    "node_modules/opt": { version: "1.0.0", license: "MIT", optional: true },
    "node_modules/devtool": { version: "1.0.0", license: "GPL-3.0-only", dev: true, dependencies: { devdep: "^1" } },
    "node_modules/devdep": { version: "1.0.0", license: "MIT", dev: true },
    "api/node_modules/srv": { version: "3.0.0", license: "MIT" },
  },
};

test("productionTree walks dependencies nested-first and leaves dev packages out", () => {
  const app = productionTree(LOCK, "app");
  assert.deepEqual(
    [...app.values()].map((p) => `${p.name}@${p.version} ${p.license}`).sort(),
    ["@s/b@2.0.0 Apache-2.0", "a@1.0.0 MIT", "c@1.5.0 ISC", "c@2.0.0 BSD-2-Clause", "opt@1.0.0 MIT"],
  );
  const api = productionTree(LOCK, "api");
  assert.deepEqual([...api.values()].map((p) => `${p.name}@${p.version}`).sort(), ["a@1.0.0", "c@1.5.0", "srv@3.0.0"]);
  for (const tree of [app, api]) {
    for (const p of tree.values()) assert.doesNotMatch(p.name, /^(devtool|devdep|demo|@demo\/.*)$/);
  }
});

test("missingCredits finds a direct dependency the README's credits leave out", () => {
  const readme = "# x\n\n## Credits\n\n| [React](https://react.dev) | ui |\n| [Leaflet](x) | map |\n| `lucide-react` | icons |\n\n## Next\n\nngeohash is named here, outside the credits.\n";
  const credits = { "react-dom": "React", "@capacitor/*": "Capacitor" };
  assert.deepEqual(missingCredits(["react", "react-dom", "leaflet", "lucide-react", "ngeohash", "@capacitor/core"], readme, credits), [
    "ngeohash",
    "@capacitor/core",
  ]);
});

test("missingFromPage finds a shipped package the licences page leaves out", () => {
  const rule = "=".repeat(24);
  const thin = "-".repeat(24);
  const page = [
    "Licences of the code and fonts Lusot is built from.",
    "",
    "PRODUCTION PACKAGES OF THE APP (2)",
    "",
    rule, "leaflet 1.9.4", "License: BSD-2-Clause", thin, "text", "",
    rule, "@capacitor/core 8.5.3", "License: MIT", thin, "text", "",
    "LIBRARIES IN THE ANDROID APP (1)",
    "",
    rule, "Play services basement 18.5.0", "License: Apache-2.0", thin, "text", "",
  ].join("\n");
  assert.deepEqual(pageNames(page), ["leaflet", "@capacitor/core", "Play services basement"]);
  assert.deepEqual(missingFromPage(["leaflet", "@capacitor/core", "react"], page), ["react"]);
});

function withFiles(files, fn) {
  const dir = mkdtempSync(join(tmpdir(), "lusot-licences-"));
  try {
    for (const [name, content] of Object.entries(files)) writeFileSync(join(dir, name), content);
    return fn(dir);
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
}

const cli = (args) => spawnSync(process.execPath, [script, ...args], { encoding: "utf8" });
const README = "## Credits\n\n| a | srv | @s/b | opt |\n";

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
    assert.match(clean.stdout, /^\| srv \| 3\.0\.0 \| MIT \| api \| ok \|$/m);
    const rule = "=".repeat(24);
    const page = [rule, "a 1.0.0", rule, "@s/b 2.0.0", rule, "c 1.5.0", rule, "c 2.0.0", ""].join("\n");
    writeFileSync(join(dir, "licences.txt"), page);
    const missing = cli([...args, "--page", join(dir, "licences.txt")]);
    assert.equal(missing.status, 1);
    assert.match(missing.stdout, /^NOT ON THE LICENCES PAGE: opt$/m);
    writeFileSync(join(dir, "README.md"), "## Credits\n\n| a | srv | opt |\n");
    const uncredited = cli(args);
    assert.equal(uncredited.status, 1);
    assert.match(uncredited.stdout, /^NOT IN THE README'S CREDITS: @s\/b$/m);
  });
});

test("importing runs nothing", () => {
  const probe = `await import(${JSON.stringify(new URL("./licences.mjs", import.meta.url).href)}); console.log("exit", process.exitCode ?? null);`;
  const run = spawnSync(process.execPath, ["--input-type=module", "-e", probe], { cwd: tmpdir(), encoding: "utf8" });
  assert.equal(run.status, 0, run.stderr);
  assert.equal(run.stdout.trim(), "exit null");
});
