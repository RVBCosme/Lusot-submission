// Builds a small entry that uses every client function, the way the screens will, and runs check-bundle.mjs on it.
// The app's own build proves little until a screen imports the client (the bundler drops what nothing uses), so
// this is the standing proof that the development mock never reaches a production bundle, with a development build
// as its control. Run: node --test "app/scripts/*.test.mjs"
import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { test } from "node:test";
import { fileURLToPath } from "node:url";
import { build } from "vite";

const appDir = fileURLToPath(new URL("..", import.meta.url));
const script = fileURLToPath(new URL("./check-bundle.mjs", import.meta.url));

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

// Builds the entry in `nodeEnv`, with the mock switched on in the environment either way, and checks the output.
async function bundleAndCheck(nodeEnv) {
  const outDir = mkdtempSync(join(tmpdir(), "lusot-mock-bundle-"));
  const saved = { NODE_ENV: process.env.NODE_ENV, VITE_API_MOCK: process.env.VITE_API_MOCK };
  process.env.NODE_ENV = nodeEnv;
  process.env.VITE_API_MOCK = "1";
  try {
    await build({
      root: appDir,
      configFile: false,
      logLevel: "silent",
      mode: nodeEnv,
      plugins: [entryPlugin],
      build: { outDir, emptyOutDir: true, rollupOptions: { input: "virtual:client-probe" } },
    });
    const run = spawnSync(process.execPath, [script, outDir], { encoding: "utf8" });
    return { code: run.status, out: run.stdout + run.stderr };
  } finally {
    for (const [name, value] of Object.entries(saved)) {
      if (value === undefined) delete process.env[name];
      else process.env[name] = value;
    }
    rmSync(outDir, { recursive: true, force: true });
  }
}

test("a production bundle that uses the client holds none of the mock, even with VITE_API_MOCK=1", async () => {
  const { code, out } = await bundleAndCheck("production");
  assert.equal(code, 0, out);
});

test("control: a development bundle with the mock switched on is found by the check", async () => {
  const { code, out } = await bundleAndCheck("development");
  assert.equal(code, 1, out);
  assert.match(out, /LUSOT_MOCK_API/);
});
