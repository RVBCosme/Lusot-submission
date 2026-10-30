// Tests for licences.mjs. Run: node --test "app/scripts/*.test.mjs"
// Each test builds a small repo in a temporary folder outside this repo: a root package.json with the `app`
// workspace, a junction for the workspace link (npm ls needs it), and the packages under node_modules. The script runs
// against it with --root, so the real `npm ls` reads the fixture. Nothing here touches the repo's own node_modules.
import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { existsSync, mkdirSync, mkdtempSync, readFileSync, rmSync, symlinkSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import { test } from "node:test";
import { fileURLToPath } from "node:url";

const script = fileURLToPath(new URL("./licences.mjs", import.meta.url));

const MIT = (who) => `MIT License\n\nCopyright (c) ${who}\n\nPermission is hereby granted, free of charge.\n`;

function put(root, path, content) {
  mkdirSync(dirname(join(root, path)), { recursive: true });
  writeFileSync(join(root, path), content);
}

// `packages` maps "where under the root" (node_modules/alpha, app/node_modules/delta, ...) to
// { name, version, deps, license, files }. `appDeps` are the app's production dependencies, `devDeps` its dev ones.
function makeRepo({ packages, appDeps = {}, devDeps = {}, extra, apk }) {
  const root = mkdtempSync(join(tmpdir(), "lusot-licences-"));
  put(root, "package.json", JSON.stringify({ name: "fixture", private: true, workspaces: ["app"] }));
  put(
    root,
    "app/package.json",
    JSON.stringify({ name: "@fixture/app", version: "1.0.0", dependencies: appDeps, devDependencies: devDeps }),
  );
  mkdirSync(join(root, "node_modules", "@fixture"), { recursive: true });
  symlinkSync(join(root, "app"), join(root, "node_modules", "@fixture", "app"), "junction");
  for (const [where, pkg] of Object.entries(packages)) {
    const { name, version, deps, license, files = {} } = pkg;
    put(root, `${where}/package.json`, JSON.stringify({ name, version, dependencies: deps, license }));
    for (const [file, content] of Object.entries(files)) put(root, `${where}/${file}`, content);
  }
  if (extra !== undefined) put(root, "app/scripts/shipped-extra.json", JSON.stringify(extra));
  if (apk !== undefined) put(root, "app/scripts/apk-licences.json", typeof apk === "string" ? apk : JSON.stringify(apk));
  return root;
}

function run(root) {
  const result = spawnSync(process.execPath, [script, "--root", root], { encoding: "utf8" });
  const out = join(root, "app", "public", "licences.txt");
  return {
    code: result.status,
    log: result.stdout + result.stderr,
    text: existsSync(out) ? readFileSync(out, "utf8") : undefined,
  };
}

function withRepo(options, check) {
  const root = makeRepo(options);
  try {
    check(root, run(root));
  } finally {
    rmSync(root, { recursive: true, force: true });
  }
}

const ALPHA = { name: "alpha", version: "1.2.3", deps: { gamma: "3.0.0" }, license: "MIT", files: { LICENSE: MIT("Alpha Authors") } };
const BETA = {
  name: "@scope/beta",
  version: "2.0.0",
  license: "ISC",
  files: { "LICENSE.md": "ISC License\n\nCopyright (c) Beta Authors\n" },
};
const GAMMA = { name: "gamma", version: "3.0.0", license: "BSD-2-Clause", files: { license: "BSD 2-Clause for gamma\n" } };

test("every production dependency, direct or nested, is written with its name, version and full licence text", () => {
  const options = {
    packages: {
      "node_modules/alpha": ALPHA,
      "node_modules/@scope/beta": BETA,
      "node_modules/gamma": GAMMA,
      "app/node_modules/delta": {
        name: "delta",
        version: "4.0.0",
        files: { COPYING: "Delta copying terms, line one\nline two\n" },
      },
    },
    appDeps: { alpha: "1.2.3", "@scope/beta": "2.0.0", delta: "4.0.0" },
  };
  withRepo(options, (_root, { code, log, text }) => {
    assert.equal(code, 0, log);
    assert.ok(text, "app/public/licences.txt was written");
    for (const [name, version] of [
      ["alpha", "1.2.3"],
      ["@scope/beta", "2.0.0"],
      ["gamma", "3.0.0"],
      ["delta", "4.0.0"],
    ]) {
      assert.ok(text.includes(`${name} ${version}`), `${name} ${version} is named`);
    }
    assert.ok(text.includes(MIT("Alpha Authors")), "alpha's text, whole");
    assert.ok(text.includes("ISC License\n\nCopyright (c) Beta Authors"), "beta's text");
    assert.ok(text.includes("BSD 2-Clause for gamma"), "gamma's text, from a nested dependency");
    assert.ok(text.includes("Delta copying terms, line one\nline two"), "delta's text, from COPYING");
    assert.ok(text.includes("MIT"), "the licence name from package.json is shown");
  });
});

test("a development dependency of the app is not listed", () => {
  const options = {
    packages: {
      "node_modules/alpha": { ...ALPHA, deps: undefined },
      "node_modules/devonly": { name: "devonly", version: "9.9.9", files: { LICENSE: "dev only terms\n" } },
    },
    appDeps: { alpha: "1.2.3" },
    devDeps: { devonly: "9.9.9" },
  };
  withRepo(options, (_root, { code, log, text }) => {
    assert.equal(code, 0, log);
    assert.ok(!text.includes("devonly"));
    assert.ok(!text.includes("dev only terms"));
  });
});

test("a package that two parents share is written once", () => {
  const options = {
    packages: {
      "node_modules/alpha": ALPHA,
      "node_modules/gamma": GAMMA,
      "node_modules/zeta": { name: "zeta", version: "1.0.0", deps: { gamma: "3.0.0" }, files: { LICENSE: "zeta terms\n" } },
    },
    appDeps: { alpha: "1.2.3", zeta: "1.0.0" },
  };
  withRepo(options, (_root, { code, log, text }) => {
    assert.equal(code, 0, log);
    assert.equal(text.split("BSD 2-Clause for gamma").length - 1, 1);
  });
});

test("two versions of one package, one nested under its parent, are each written with their own text", () => {
  const options = {
    packages: {
      "node_modules/alpha": ALPHA,
      "node_modules/alpha/node_modules/gamma": GAMMA,
      "node_modules/gamma": { name: "gamma", version: "2.0.0", files: { LICENSE: "gamma two terms\n" } },
      "node_modules/zeta": { name: "zeta", version: "1.0.0", deps: { gamma: "2.0.0" }, files: { LICENSE: "zeta terms\n" } },
    },
    appDeps: { alpha: "1.2.3", zeta: "1.0.0" },
  };
  withRepo(options, (_root, { code, log, text }) => {
    assert.equal(code, 0, log);
    assert.ok(text.includes("gamma 2.0.0"));
    assert.ok(text.includes("gamma two terms"));
    assert.ok(text.includes("gamma 3.0.0"));
    assert.ok(text.includes("BSD 2-Clause for gamma"));
  });
});

for (const file of ["LICENSE", "LICENCE", "COPYING", "license", "Licence.md", "LICENSE.txt", "copying.TXT"]) {
  test(`${file} is read as a package's licence file`, () => {
    const options = {
      packages: { "node_modules/alpha": { name: "alpha", version: "1.0.0", files: { [file]: `terms in ${file}\n` } } },
      appDeps: { alpha: "1.0.0" },
    };
    withRepo(options, (_root, { code, log, text }) => {
      assert.equal(code, 0, log);
      assert.ok(text.includes(`terms in ${file}`));
    });
  });
}

test("a licence file's line endings are made plain, and its words are left alone", () => {
  const options = {
    packages: { "node_modules/alpha": { name: "alpha", version: "1.0.0", files: { LICENSE: "line one\r\n  indented line\r\n" } } },
    appDeps: { alpha: "1.0.0" },
  };
  withRepo(options, (_root, { code, log, text }) => {
    assert.equal(code, 0, log);
    assert.ok(text.includes("line one\n  indented line"));
    assert.ok(!text.includes("\r"));
  });
});

test("a package with no licence file fails the script, names the package, and writes nothing", () => {
  const options = {
    packages: {
      "node_modules/alpha": ALPHA,
      "node_modules/gamma": { name: "gamma", version: "3.0.0", files: { "README.md": "not a licence\n", "LICENSE-NOTES.txt": "no\n" } },
    },
    appDeps: { alpha: "1.2.3" },
  };
  withRepo(options, (_root, { code, log, text }) => {
    assert.notEqual(code, 0);
    assert.match(log, /gamma@3\.0\.0/);
    assert.match(log, /no licence file/i);
    assert.equal(text, undefined);
  });
});

test("a failed run leaves no old licences.txt standing in for a current one", () => {
  const options = {
    packages: { "node_modules/alpha": { name: "alpha", version: "1.0.0", files: { "README.md": "none\n" } } },
    appDeps: { alpha: "1.0.0" },
  };
  const root = makeRepo(options);
  try {
    put(root, "app/public/licences.txt", "stale");
    const { code } = run(root);
    assert.notEqual(code, 0);
    assert.equal(existsSync(join(root, "app", "public", "licences.txt")), false);
  } finally {
    rmSync(root, { recursive: true, force: true });
  }
});

test("each shipped-extra.json entry is written with its licence text and what it ships", () => {
  const options = {
    packages: {
      "node_modules/alpha": { ...ALPHA, deps: undefined },
      "node_modules/buildtool": { name: "buildtool", version: "7.0.0", license: "MIT", files: { "LICENSE.md": MIT("Buildtool Authors") } },
    },
    appDeps: { alpha: "1.2.3" },
    devDeps: { buildtool: "7.0.0" },
    extra: [{ package: "buildtool", ships: "the preload helper the build adds to the page" }],
  };
  withRepo(options, (_root, { code, log, text }) => {
    assert.equal(code, 0, log);
    assert.ok(text.includes("buildtool 7.0.0"));
    assert.ok(text.includes("the preload helper the build adds to the page"));
    assert.ok(text.includes(MIT("Buildtool Authors")));
  });
});

test("an entry's stopAt cuts its licence file before the marker line", () => {
  const long = `${MIT("Buildtool Authors")}\n# Licenses of bundled dependencies\nthird party terms that do not ship\n`;
  const options = {
    packages: { "node_modules/buildtool": { name: "buildtool", version: "7.0.0", files: { "LICENSE.md": long } } },
    devDeps: { buildtool: "7.0.0" },
    extra: [{ package: "buildtool", ships: "its helper", stopAt: "# Licenses of bundled dependencies" }],
  };
  withRepo(options, (_root, { code, log, text }) => {
    assert.equal(code, 0, log);
    assert.ok(text.includes(MIT("Buildtool Authors").trimEnd()));
    assert.ok(!text.includes("third party terms that do not ship"));
    assert.ok(!text.includes("# Licenses of bundled dependencies"));
  });
});

test("a stopAt marker the file doesn't hold fails, naming the package", () => {
  const options = {
    packages: { "node_modules/buildtool": { name: "buildtool", version: "7.0.0", files: { LICENSE: "plain\n" } } },
    devDeps: { buildtool: "7.0.0" },
    extra: [{ package: "buildtool", ships: "its helper", stopAt: "# Not in the file" }],
  };
  withRepo(options, (_root, { code, log, text }) => {
    assert.notEqual(code, 0);
    assert.match(log, /buildtool/);
    assert.equal(text, undefined);
  });
});

test("a shipped-extra.json entry that isn't installed fails, naming it", () => {
  const options = {
    packages: { "node_modules/alpha": { ...ALPHA, deps: undefined } },
    appDeps: { alpha: "1.2.3" },
    extra: [{ package: "ghost", ships: "nothing" }],
  };
  withRepo(options, (_root, { code, log, text }) => {
    assert.notEqual(code, 0);
    assert.match(log, /ghost/);
    assert.equal(text, undefined);
  });
});

test("an entry of shipped-extra.json with no licence file fails, naming it", () => {
  const options = {
    packages: { "node_modules/buildtool": { name: "buildtool", version: "7.0.0", files: { "README.md": "x\n" } } },
    devDeps: { buildtool: "7.0.0" },
    extra: [{ package: "buildtool", ships: "its helper" }],
  };
  withRepo(options, (_root, { code, log }) => {
    assert.notEqual(code, 0);
    assert.match(log, /buildtool@7\.0\.0/);
  });
});

test("apk-licences.json, when it is there, adds the APK's section", () => {
  const options = {
    packages: { "node_modules/alpha": { ...ALPHA, deps: undefined } },
    appDeps: { alpha: "1.2.3" },
    apk: [
      { name: "AndroidX libraries", version: "1.x", licence: "Apache-2.0", text: "Apache terms for the APK\nline two" },
      { name: "Play services location", licence: "Google terms", text: "Google's terms for location" },
    ],
  };
  withRepo(options, (_root, { code, log, text }) => {
    assert.equal(code, 0, log);
    assert.ok(text.includes("AndroidX libraries 1.x"));
    assert.ok(text.includes("Apache terms for the APK\nline two"));
    assert.ok(text.includes("Play services location"));
    assert.ok(text.includes("Google's terms for location"));
    assert.ok(text.indexOf("Apache terms for the APK") > text.indexOf("alpha 1.2.3"), "the APK's section follows the web packages");
  });
});

test("without apk-licences.json, nothing about an APK is written", () => {
  const options = { packages: { "node_modules/alpha": { ...ALPHA, deps: undefined } }, appDeps: { alpha: "1.2.3" } };
  withRepo(options, (_root, { code, log, text }) => {
    assert.equal(code, 0, log);
    assert.ok(!/android/i.test(text));
  });
});

for (const [why, apk] of [
  ["isn't JSON", "{ not json"],
  ["isn't a list", { name: "x", text: "y" }],
  ["holds an entry with no text", [{ name: "AndroidX" }]],
]) {
  test(`an apk-licences.json that ${why} fails the script`, () => {
    const options = { packages: { "node_modules/alpha": { ...ALPHA, deps: undefined } }, appDeps: { alpha: "1.2.3" }, apk };
    withRepo(options, (_root, { code, log, text }) => {
      assert.notEqual(code, 0);
      assert.match(log, /apk-licences\.json/);
      assert.equal(text, undefined);
    });
  });
}

test("the log names counts, never a licence's text", () => {
  const options = { packages: { "node_modules/alpha": { ...ALPHA, deps: undefined } }, appDeps: { alpha: "1.2.3" } };
  withRepo(options, (_root, { code, log }) => {
    assert.equal(code, 0, log);
    assert.match(log, /1 package/);
    assert.ok(!log.includes("Permission is hereby granted"));
  });
});
