// `npm run deploy`: the one-command deploy (spec A4). In order, it:
// 1. installs from the root lockfile (npm ci)
// 2. bundles the API into backend/api/dist from that install (R21); SAM only packages it
// 3. builds and deploys the stack with the git-ignored backend/samconfig.toml (C31)
// 4. applies the analysis image repository's keep-the-last-3 rule (C38)
// It stops at the first step that fails. Every line of output passes through a mask, because
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

for (const [cwd, command] of steps) {
  console.log(`> ${command}`);
  const code = await run(command, cwd);
  if (code !== 0) {
    console.error(`deploy stopped: "${command}" exited with ${code}`);
    process.exit(code);
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
    maskLines(child.stdout, process.stdout);
    maskLines(child.stderr, process.stderr);
    child.on("error", reject);
    child.on("close", (code) => resolve(code ?? 1));
  });
}

// Writes whole lines only, so an account ID split across two chunks is still masked.
function maskLines(from, to) {
  let rest = "";
  from.setEncoding("utf8");
  from.on("data", (chunk) => {
    const text = rest + chunk;
    const end = text.lastIndexOf("\n") + 1;
    to.write(mask(text.slice(0, end)));
    rest = text.slice(end);
  });
  from.on("end", () => to.write(mask(rest)));
}

function mask(text) {
  return text.replace(/[0-9]{12}/g, "<account>");
}
