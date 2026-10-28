// Bundles the API Lambda into dist/ from this repo's node_modules, which npm installs from the
// root package-lock.json, so the deployed code uses the versions the tests ran against (R21).
// SAM then only packages dist/: its package.json lists no dependencies, so nothing is installed.
import { rm, writeFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import { build } from "esbuild";

const dist = new URL("./dist/", import.meta.url);

await rm(dist, { recursive: true, force: true });
await build({
  absWorkingDir: fileURLToPath(new URL(".", import.meta.url)),
  entryPoints: ["src/index.ts"],
  bundle: true,
  platform: "node",
  target: "node22",
  format: "cjs",
  minify: true,
  sourcemap: true,
  sourcesContent: false,
  outfile: "dist/index.js",
  logLevel: "warning",
});
await writeFile(new URL("package.json", dist), `${JSON.stringify({ name: "lusot-api", version: "0.0.0", private: true }, null, 2)}\n`);
