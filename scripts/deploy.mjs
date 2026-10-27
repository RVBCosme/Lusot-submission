// `npm run deploy`: the one-command deploy (spec A4). In order, it:
// 1. installs from the root lockfile (npm ci)
// 2. bundles the API into backend/api/dist from that install (R21); SAM only packages it
// 3. builds and deploys the stack with the git-ignored backend/samconfig.toml (C31)
// 4. applies the analysis image repository's keep-the-last-3 rule (C38)
// It stops at the first step that fails. All output passes through a mask, because
// sam deploy prints change set ARNs and image URIs that carry the AWS account ID.
import { spawn } from "node:child_process";
import { fileURLToPath } from "node:url";

const root = fileURLToPath(new URL("..", import.meta.url));
const backend = fileURLToPath(new URL("../backend", import.meta.url));
const steps = [
  [root, "npm ci"],
  [root, "npm run build -w backend/api"],
  [backend, "sam build --parallel"],
  [backend, "sam deploy"],
  [root, "uv run backend/scripts/apply_ecr_lifecycle.py"],
];

// Masks 12-digit runs (account IDs) in streamed text. Each chunk is written at once, so a
// prompt shows without waiting for a newline, except a trailing run of digits: that is held
// until the next chunk or the flush, in case the next chunk completes an account ID.
export function createMasker(write) {
  let held = "";
  const emit = (text) => {
    if (text) write(text.replace(/[0-9]{12}/g, "<account>"));
  };
  return {
    chunk(text) {
      const all = held + text;
      let cut = all.length;
      while (cut > 0 && all[cut - 1] >= "0" && all[cut - 1] <= "9") cut--;
      emit(all.slice(0, cut));
      held = all.slice(cut);
    },
    flush() {
      emit(held);
      held = "";
    },
  };
}

// Deploys only when run as `node scripts/deploy.mjs`, so a test can import createMasker.
if (import.meta.main === undefined) throw new Error("scripts/deploy.mjs needs Node 22.18 or newer");
if (import.meta.main) {
  for (const [cwd, command] of steps) {
    console.log(`> ${command}`);
    const code = await run(command, cwd);
    if (code !== 0) {
      console.error(`deploy stopped: "${command}" exited with ${code}`);
      process.exit(code);
    }
  }
}

// Through the shell, since npm and sam are .cmd files on Windows. Python tools (sam, uv's
// scripts) write UTF-8 into the pipe, so a non-ASCII character can't crash them on cp1252.
function run(command, cwd) {
  return new Promise((resolve, reject) => {
    const child = spawn(command, {
      cwd,
      shell: true,
      stdio: ["inherit", "pipe", "pipe"],
      env: { ...process.env, PYTHONIOENCODING: "utf-8" },
    });
    pipeMasked(child.stdout, process.stdout);
    pipeMasked(child.stderr, process.stderr);
    child.on("error", reject);
    child.on("close", (code) => resolve(code ?? 1));
  });
}

function pipeMasked(from, to) {
  const masker = createMasker((text) => to.write(text));
  from.setEncoding("utf8");
  from.on("data", masker.chunk);
  from.on("end", masker.flush);
}
