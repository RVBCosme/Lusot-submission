// `npm run deploy:web`: puts the web app on the stack's web bucket, behind CloudFront (MS5 Task 19, C622). The stack
// must already hold the web resources, so `npm run deploy` comes first. In order, it:
// 1. reads the stack name from the git-ignored backend/samconfig.toml, and stops unless it sets WebHosting=on (with it
//    off the stack has no web resources); then reads the stack's outputs
// 2. builds the app with VITE_API_URL set to the stack's ApiUrl, through the app's build script, so prebuild writes
//    licences.txt and the bundle check runs. Vite reads VITE_PRIVACY_CONTACT from the git-ignored app/.env.local
//    itself (an environment variable already set wins over the file), so this script never reads the contact.
// 3. runs the bundle check again on its own, so a change to the build script can't let an unchecked bundle out
// 4. lists app/dist and stops if any file's type has no Content-Type in CONTENT_TYPES
// 5. uploads assets/ (content-hashed names) cached for a year, then everything else as no-cache, deleting what the
//    build no longer has outside assets/. Each type goes in its own sync with its own --content-type.
// 6. invalidates the no-cache paths and waits for it
// 7. only then deletes old assets, so a visitor who loaded the old index.html a moment earlier still gets its files
// It stops at the first step that fails, with that step's exit code. It prints each step's status and the web URL.
// A command's output is kept back and shown only when its step fails, masked: ARNs, email addresses and runs of
// 12 digits (account IDs), as deploy.mjs masks them.
import { spawn } from "node:child_process";
import { readFileSync, readdirSync } from "node:fs";
import { join, posix, relative, sep } from "node:path";
import { fileURLToPath } from "node:url";
import { webHosting } from "./deploy.mjs";

const root = fileURLToPath(new URL("..", import.meta.url));
const AWS_FLAGS = ["--region", "ap-southeast-1", "--profile", "lusot", "--no-cli-pager"];
const IMMUTABLE = "public, max-age=31536000, immutable";
// Every type the build emits, and the Content-Type it is served as (S5-R26; .woff added, as the build emits it too).
// Left to itself, the AWS CLI guesses types with Python's mimetypes, which on Windows reads the registry; and the
// distribution's SecurityHeadersPolicy sends nosniff, so a script or stylesheet served as text/plain blanks the page.
// A file of any other type, compared case by case, stops the deploy before the first upload.
const CONTENT_TYPES = new Map([
  [".js", "text/javascript"],
  [".mjs", "text/javascript"],
  [".css", "text/css"],
  [".html", "text/html; charset=utf-8"],
  [".json", "application/manifest+json"],
  [".webmanifest", "application/manifest+json"],
  [".txt", "text/plain; charset=utf-8"],
  [".svg", "image/svg+xml"],
  [".png", "image/png"],
  [".woff2", "font/woff2"],
  [".woff", "font/woff"],
]);
// app/dist outside assets/: the page (also cached as the root object), the manifest, the licences text and the icons.
const NO_CACHE_PATHS = ["/", "/index.html", "/manifest.webmanifest", "/licences.txt", "/icons/*"];
const OUTPUT_KEYS = ["ApiUrl", "WebBucketName", "WebDistributionId", "WebUrl"];

const aws = (...args) => ["aws", ...args, ...AWS_FLAGS];

export function scrub(text) {
  return String(text)
    .replace(/arn:[^\s"'`,;)\]}]+/g, "<arn>")
    .replace(/[^\s@"'`<>(),;]+@[^\s@"'`<>(),;]+\.[A-Za-z]{2,}/g, "<email>")
    .replace(/[0-9]{12}/g, "<account>");
}

class Stop extends Error {
  constructor(message, result) {
    super(message);
    this.result = result;
  }
}

// run(argv, { env }) gives { code, stdout, stderr }; readText(path) reads a file under the repo root; listFiles(dir)
// gives the paths of every file under a folder of the repo, relative to it, with `/`; out and err each write one
// line. Returns the exit code.
export async function deployWeb({ run, env, readText, listFiles, out, err }) {
  const say = (line) => out(scrub(line));
  const step = async (name, argv, options) => {
    const result = await run(argv, options);
    if (result.code !== 0) throw new Stop(`${name} exited with ${result.code}`, result);
    return result;
  };
  try {
    let samconfig;
    try {
      samconfig = readText("backend/samconfig.toml");
    } catch {
      throw new Stop("backend/samconfig.toml is missing: copy backend/samconfig.example.toml (CLAUDE.md, Commands)");
    }
    const stack = /^\s*stack_name\s*=\s*"([^"]+)"/m.exec(samconfig)?.[1];
    if (!stack) throw new Stop("backend/samconfig.toml has no stack_name");
    if (webHosting(samconfig) !== "on") {
      throw new Stop(
        "WebHosting isn't on in backend/samconfig.toml, so the stack has no website: set WebHosting=on, " +
          "run npm run deploy, then deploy:web",
      );
    }

    const read = await step(
      "reading the stack's outputs",
      aws("cloudformation", "describe-stacks", "--stack-name", stack, "--query", "Stacks[0].Outputs", "--output", "json"),
    );
    let outputs;
    try {
      outputs = Object.fromEntries((JSON.parse(read.stdout) ?? []).map((o) => [o.OutputKey, o.OutputValue]));
    } catch {
      throw new Stop("the stack's outputs couldn't be read as JSON");
    }
    const missing = OUTPUT_KEYS.filter((key) => !outputs[key]);
    if (missing.length > 0) {
      throw new Stop(`the stack has no ${missing.join(", ")} output: deploy the template first (npm run deploy)`);
    }
    const { ApiUrl: apiUrl, WebBucketName: bucket, WebDistributionId: distribution, WebUrl: webUrl } = outputs;
    say(`stack ${stack}: outputs read`);

    await step("build", ["npm", "run", "build", "-w", "app"], { env: { ...env, VITE_API_URL: apiUrl } });
    say("build: ok");
    await step("bundle check", ["node", "app/scripts/check-bundle.mjs", "app/dist"]);
    say("bundle check: ok");

    const files = listFiles("app/dist");
    const unknown = files.filter((file) => !CONTENT_TYPES.has(posix.extname(file))).sort();
    if (unknown.length > 0) {
      const named = unknown.map((file) => `app/dist/${file}`).join(", ");
      throw new Stop(`no Content-Type is set for the type of ${named}: add it to CONTENT_TYPES in scripts/deploy_web.mjs`);
    }
    // The types present in assets/ (or outside it), in the table's order.
    const typesIn = (inAssets) =>
      [...CONTENT_TYPES.keys()].filter((ext) =>
        files.some((file) => file.startsWith("assets/") === inAssets && posix.extname(file) === ext));
    const assetTypes = typesIn(true);
    const pageTypes = typesIn(false);

    // The CLI's filters: the last pattern that matches a path decides, and "files excluded by filters are excluded
    // from deletion". So a sync that lets in one type uploads only that type, with its own --content-type, and its
    // --delete reaches only stale files of that type. A clean-up sync excludes every type present, so it uploads
    // nothing (step 4 saw every file's type) and deletes stale files of every other type.
    const only = (ext) => ["--exclude", "*", "--include", `*${ext}`];
    const typed = (ext, cacheControl) =>
      ["--content-type", CONTENT_TYPES.get(ext), "--cache-control", cacheControl, "--only-show-errors"];
    const cleanUp = (types) => [...types.flatMap((ext) => ["--exclude", `*${ext}`]), "--only-show-errors"];
    const assets = ["app/dist/assets", `s3://${bucket}/assets`];
    const pages = ["app/dist", `s3://${bucket}`];
    const assetsSync = (ext, ...del) => aws("s3", "sync", ...assets, ...del, ...only(ext), ...typed(ext, IMMUTABLE));

    for (const ext of assetTypes) await step(`assets upload (${ext})`, assetsSync(ext));
    say("assets upload: ok");
    for (const ext of pageTypes) {
      await step(
        `pages upload (${ext})`,
        aws("s3", "sync", ...pages, "--delete", ...only(ext), "--exclude", "assets/*", ...typed(ext, "no-cache")),
      );
    }
    await step("pages clean-up", aws("s3", "sync", ...pages, "--delete", "--exclude", "assets/*", ...cleanUp(pageTypes)));
    say("pages upload: ok");

    const created = await step(
      "invalidation",
      aws("cloudfront", "create-invalidation", "--distribution-id", distribution, "--paths", ...NO_CACHE_PATHS,
        "--query", "Invalidation.Id", "--output", "text"),
    );
    await step(
      "invalidation wait",
      aws("cloudfront", "wait", "invalidation-completed", "--distribution-id", distribution, "--id", created.stdout.trim()),
    );
    say("invalidation: done");

    const removal = "old assets removal (the new site is already live)";
    for (const ext of assetTypes) await step(removal, assetsSync(ext, "--delete"));
    await step(removal, aws("s3", "sync", ...assets, "--delete", ...cleanUp(assetTypes)));
    say("old assets: removed");
    say(`web: ${webUrl}`);
    return 0;
  } catch (error) {
    if (!(error instanceof Stop)) throw error;
    const detail = error.result ? `${error.result.stdout ?? ""}${error.result.stderr ?? ""}`.trim() : "";
    if (detail) err(scrub(detail));
    err(scrub(`deploy:web stopped: ${error.message}`));
    return error.result?.code || 1;
  }
}

// Deploys only when run as `node scripts/deploy_web.mjs`, so a test can import deployWeb.
if (import.meta.main === undefined) throw new Error("scripts/deploy_web.mjs needs Node 22.18 or newer");
if (import.meta.main) {
  const code = await deployWeb({
    run,
    env: process.env,
    readText: (path) => readFileSync(join(root, path), "utf8"),
    listFiles,
    out: (line) => process.stdout.write(`${line}\n`),
    err: (line) => process.stderr.write(`${line}\n`),
  });
  process.exit(code);
}

// Everything under a folder of the repo that isn't a folder, links included, so the type check sees all that sync
// would upload.
function listFiles(dir) {
  const base = join(root, dir);
  return readdirSync(base, { recursive: true, withFileTypes: true })
    .filter((entry) => !entry.isDirectory())
    .map((entry) => relative(base, join(entry.parentPath, entry.name)).split(sep).join("/"));
}

// From the repo root, output kept for the caller. npm is a .cmd file on Windows, which Node starts only through a
// shell; its words here are fixed. aws (aws.exe) and node start directly, so no shell reads a bucket name or a path.
// The AWS CLI is a Python tool, so PYTHONIOENCODING keeps a non-ASCII character from crashing it on cp1252.
function run(argv, { env = process.env } = {}) {
  return new Promise((resolve) => {
    const [file, ...args] = argv;
    const options = { cwd: root, env: { ...env, PYTHONIOENCODING: "utf-8" }, stdio: ["ignore", "pipe", "pipe"] };
    const child =
      file === "npm"
        ? spawn(argv.join(" "), { ...options, shell: true })
        : spawn(file === "node" ? process.execPath : file, args, options);
    let stdout = "";
    let stderr = "";
    child.stdout.setEncoding("utf8").on("data", (text) => (stdout += text));
    child.stderr.setEncoding("utf8").on("data", (text) => (stderr += text));
    child.on("error", (error) => resolve({ code: 1, stdout, stderr: `${stderr}${error.message}\n` }));
    child.on("close", (code) => resolve({ code: code ?? 1, stdout, stderr }));
  });
}
