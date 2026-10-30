// Builds a small entry that uses every client function, the way the screens will, and runs the bundle check on it
// exactly as `npm run build -w app` does: the commands that follow `vite build` in app/package.json's build script.
// The app's own build proves little until a screen imports the client (the bundler drops what nothing uses), so
// this is the standing proof that the development mock never reaches a production bundle, with a development build
// as its control. Vite sets import.meta.env.DEV from NODE_ENV, not from the mode, so a build with NODE_ENV set to
// something else keeps the mock; the chained check is what fails that build. Run: node --test "app/scripts/*.test.mjs"
import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { copyFileSync, mkdirSync, mkdtempSync, readFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { test } from "node:test";
import { fileURLToPath } from "node:url";
import { build } from "vite";

const appDir = fileURLToPath(new URL("..", import.meta.url));
const script = fileURLToPath(new URL("./check-bundle.mjs", import.meta.url));

// The commands `npm run build -w app` runs after `vite build`, in order. Empty or missing means no check is chained.
function chainedChecks() {
  const { build: buildScript } = JSON.parse(readFileSync(join(appDir, "package.json"), "utf8")).scripts;
  const steps = buildScript.split("&&").map((step) => step.trim());
  const at = steps.indexOf("vite build");
  assert.notEqual(at, -1, `the build script has no "vite build" step: ${buildScript}`);
  return steps.slice(at + 1);
}

// Runs the chained commands in a scratch folder laid out like app/ (scripts/check-bundle.mjs, with dist/ beside it).
// Stops at the first one that fails, as `&&` does.
function runChain(scratch) {
  const steps = chainedChecks();
  assert.ok(steps.length > 0, "nothing follows `vite build` in the build script, so no bundle check runs");
  assert.ok(
    steps.some((step) => step.includes("check-bundle.mjs dist")),
    `the build script's checks don't include the bundle check on dist: ${steps.join(" && ")}`,
  );
  for (const step of steps) {
    const run = spawnSync(step, { cwd: scratch, encoding: "utf8", shell: true });
    if (run.status !== 0) return { code: run.status, out: run.stdout + run.stderr };
  }
  return { code: 0, out: "" };
}

function scratchApp() {
  const scratch = mkdtempSync(join(tmpdir(), "lusot-mock-bundle-"));
  mkdirSync(join(scratch, "scripts"));
  copyFileSync(script, join(scratch, "scripts", "check-bundle.mjs"));
  return scratch;
}

const ENTRY = "\0virtual:client-probe";
const entryPlugin = {
  name: "client-probe-entry",
  resolveId: (id) => (id === "virtual:client-probe" ? ENTRY : undefined),
  load: (id) =>
    id === ENTRY
      ? `import * as api from "/src/lib/api.ts";
         import { pollReport } from "/src/lib/poll.ts";
         Object.assign(globalThis, { probe: { ...api, pollReport } });`
      : undefined,
};

// Builds the entry into the scratch folder's dist/, with NODE_ENV and the mode as given and the mock switched on in
// the environment, then runs the chained checks.
async function bundleAndCheck({ nodeEnv, mode = nodeEnv }) {
  const scratch = scratchApp();
  const saved = { NODE_ENV: process.env.NODE_ENV, VITE_API_MOCK: process.env.VITE_API_MOCK };
  process.env.NODE_ENV = nodeEnv;
  process.env.VITE_API_MOCK = "1";
  try {
    await build({
      root: appDir,
      configFile: false,
      logLevel: "silent",
      mode,
      plugins: [entryPlugin],
      build: { outDir: join(scratch, "dist"), emptyOutDir: true, rollupOptions: { input: "virtual:client-probe" } },
    });
    return runChain(scratch);
  } finally {
    for (const [name, value] of Object.entries(saved)) {
      if (value === undefined) delete process.env[name];
      else process.env[name] = value;
    }
    rmSync(scratch, { recursive: true, force: true });
  }
}

test("the build script runs the bundle check on dist after vite build", () => {
  assert.deepEqual(chainedChecks(), ["node scripts/check-bundle.mjs dist"]);
});

test("the chained check fails closed: no dist folder is an error, not a pass", () => {
  const scratch = scratchApp();
  try {
    const { code, out } = runChain(scratch);
    assert.equal(code, 2, out);
  } finally {
    rmSync(scratch, { recursive: true, force: true });
  }
});

test("a production bundle that uses the client holds none of the mock, even with VITE_API_MOCK=1", async () => {
  const { code, out } = await bundleAndCheck({ nodeEnv: "production" });
  assert.equal(code, 0, out);
});

test("a build in production mode with NODE_ENV=test keeps the mock, and the chained check fails it", async () => {
  const { code, out } = await bundleAndCheck({ nodeEnv: "test", mode: "production" });
  assert.equal(code, 1, out);
  assert.match(out, /LUSOT_MOCK_API/);
});

test("control: a development bundle with the mock switched on is found by the check", async () => {
  const { code, out } = await bundleAndCheck({ nodeEnv: "development" });
  assert.equal(code, 1, out);
  assert.match(out, /LUSOT_MOCK_API/);
});
