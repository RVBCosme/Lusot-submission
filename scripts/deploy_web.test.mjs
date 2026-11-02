// Tests for deploy_web.mjs with a fake command runner: nothing is built and nothing reaches AWS.
// Run: node --test scripts/deploy_web.test.mjs
import assert from "node:assert/strict";
import { posix } from "node:path";
import { test } from "node:test";
import { deployWeb, scrub } from "./deploy_web.mjs";

// Built at run time, so neither the repo's 12-digit scan nor a reader meets a literal one here.
const ACCOUNT = "1234" + "5678" + "9012";
const ARN = `arn:aws:cloudfront::${ACCOUNT}:distribution/E2EXAMPLE`;
const CONTACT = ["privacy", "example.org"].join("@");

const FLAGS = ["--region", "ap-southeast-1", "--profile", "lusot", "--no-cli-pager"];
const IMMUTABLE = "public, max-age=31536000, immutable";
const API_URL = "https://abc123.execute-api.ap-southeast-1.amazonaws.com";
const WEB_URL = "https://d111111abcdef8.cloudfront.net";
const BUCKET = "lusot-webbucket-abc123";
const OUTPUTS = [
  { OutputKey: "ApiUrl", OutputValue: API_URL },
  { OutputKey: "WebBucketName", OutputValue: BUCKET },
  { OutputKey: "WebDistributionId", OutputValue: "E2EXAMPLE" },
  { OutputKey: "WebUrl", OutputValue: WEB_URL },
  { OutputKey: "Other", OutputValue: ARN },
];
// A stack name other than the example's, so the test shows it is read; and the alarm email, never printed.
const SAMCONFIG = [
  "version = 0.1",
  "[default.global.parameters]",
  'stack_name = "lusot-test"',
  'region = "ap-southeast-1"',
  "[default.deploy.parameters]",
  `parameter_overrides = "AlarmEmail=${CONTACT} BucketSuffix=abc123 WebHosting=on"`,
].join("\n");

// WebHosting=amplify (Nov 2): the same stack, with Amplify's outputs in place of CloudFront's. The upload link is a
// presigned URL, so it carries a signature that must never be printed.
const AMPLIFY_SAMCONFIG = SAMCONFIG.replace("WebHosting=on", "WebHosting=amplify");
const AMPLIFY_URL = "https://main.d2abcdef123456.amplifyapp.com";
const AMPLIFY_OUTPUTS = [
  { OutputKey: "ApiUrl", OutputValue: API_URL },
  { OutputKey: "WebAmplifyAppId", OutputValue: "d2abcdef123456" },
  { OutputKey: "WebAmplifyBranchName", OutputValue: "main" },
  { OutputKey: "WebAmplifyUrl", OutputValue: AMPLIFY_URL },
];
const UPLOAD_URL = "https://aws-amplify-prod-ap-southeast-1-artifacts.s3.amazonaws.com/d2abcdef123456/main/7/artifacts.zip?X-Amz-Signature=SECRETSIG";
const ZIP = "C:/tmp/lusot-web.zip";

// app/dist as the build leaves it today, in kind: the page, the licences, the manifest and the icons, and under
// assets/ the bundle, a lazy chunk, the styles and both font formats (the CSS lists .woff after each .woff2).
const DIST = [
  "index.html",
  "licences.txt",
  "manifest.webmanifest",
  "icons/icon-192.png",
  "icons/icon.svg",
  "assets/index-NEW.js",
  "assets/web-NEW.js",
  "assets/index-NEW.css",
  "assets/font-NEW.woff2",
  "assets/font-NEW.woff",
];
// The Content-Type each type is served as (S5-R26, plus .woff, which the build emits too).
const SERVED_AS = {
  ".js": "text/javascript",
  ".mjs": "text/javascript",
  ".css": "text/css",
  ".html": "text/html; charset=utf-8",
  ".json": "application/manifest+json",
  ".webmanifest": "application/manifest+json",
  ".txt": "text/plain; charset=utf-8",
  ".svg": "image/svg+xml",
  ".png": "image/png",
  ".woff2": "font/woff2",
  ".woff": "font/woff",
};

const is = (word) => (argv) => argv.includes(word);
const isBuild = (argv) => argv[0] === "npm";
const isBundleCheck = (argv) => argv[0] === "node";
const isAssetsSync = (argv) => argv.includes("sync") && argv.includes("app/dist/assets");
const isRestSync = (argv) => argv.includes("sync") && argv.includes("app/dist");
const valueOf = (argv, flag) => (argv.includes(flag) ? argv[argv.indexOf(flag) + 1] : undefined);

// The AWS CLI's filters ("Use of Exclude and Include Filters" in its s3 reference): a path starts included, and the
// last --exclude or --include whose pattern matches it decides. `*` matches anything, slashes included. The script
// uses no other pattern symbol, so this model covers `*` only.
function included(argv, path) {
  let keep = true;
  argv.forEach((word, i) => {
    if (word !== "--exclude" && word !== "--include") return;
    const pattern = argv[i + 1];
    assert.doesNotMatch(pattern, /[?[]/, "the filter model covers * only");
    const glob = pattern.split("*").map((part) => part.replace(/[.+^$|(){}\]\\]/g, "\\$&")).join(".*");
    if (new RegExp(`^${glob}$`).test(path)) keep = word === "--include";
  });
  return keep;
}

// What each `aws s3 sync` in a run could upload, and what it would delete from a bucket holding `remote`. A file
// under the sync's source that its filters let in may go up. With --delete, an object under its destination that has
// no file behind it and that its filters let in is deleted ("files excluded by filters are excluded from deletion").
function syncEffects(argvs, files, remote) {
  const uploads = [];
  const deletes = [];
  const under = (base) => (base === "" ? "" : `${base}/`);
  argvs.forEach((argv, at) => {
    if (argv[0] !== "aws" || argv[1] !== "s3" || argv[2] !== "sync") return;
    const source = under(argv[3].replace(/^app\/dist\/?/, ""));
    const target = under(argv[4].replace(/^s3:\/\/[^/]+\/?/, ""));
    for (const file of files.filter((file) => file.startsWith(source))) {
      const path = file.slice(source.length);
      if (included(argv, path)) {
        uploads.push({ at, key: target + path, type: valueOf(argv, "--content-type"), cache: valueOf(argv, "--cache-control") });
      }
    }
    if (!argv.includes("--delete")) return;
    for (const key of remote.filter((key) => key.startsWith(target))) {
      const path = key.slice(target.length);
      if (!files.includes(source + path) && included(argv, path)) deletes.push({ at, key });
    }
  });
  return { uploads, deletes };
}

// Runs deployWeb with a fake runner. `answer(argv)` may return a result for a call; any other call succeeds,
// with the stack's outputs for describe-stacks and an invalidation id for create-invalidation. `files` is what
// listing app/dist gives.
async function deploy({
  answer = () => undefined,
  samconfig = SAMCONFIG,
  env = { PATH: "test-path" },
  files = DIST,
  outputs = OUTPUTS,
  uploaded = async () => ({ ok: true, status: 200 }),
} = {}) {
  const calls = [];
  const listed = [];
  const uploads = [];
  const out = [];
  const err = [];
  const run = async (argv, options = {}) => {
    calls.push({ argv, env: options.env });
    const given = answer(argv);
    if (given) return { code: 0, stdout: "", stderr: "", ...given };
    if (argv.includes("describe-stacks")) return { code: 0, stdout: JSON.stringify(outputs), stderr: "" };
    if (argv.includes("create-invalidation")) return { code: 0, stdout: "I2EXAMPLE\n", stderr: "" };
    if (argv.includes("create-deployment")) return { code: 0, stdout: JSON.stringify({ jobId: "7", zipUploadUrl: UPLOAD_URL }), stderr: "" };
    if (argv.includes("get-job")) return { code: 0, stdout: "SUCCEED\n", stderr: "" };
    return { code: 0, stdout: "", stderr: "" };
  };
  const upload = async (url, path) => {
    uploads.push({ url, path, after: calls.length });
    return uploaded(url, path);
  };
  const readText = (path) => {
    if (path === "backend/samconfig.toml" && samconfig !== null) return samconfig;
    throw Object.assign(new Error(`ENOENT: ${path}`), { code: "ENOENT" });
  };
  const listFiles = (dir) => {
    listed.push({ dir, after: calls.length });
    return files;
  };
  const code = await deployWeb({
    run,
    env,
    readText,
    listFiles,
    upload,
    zipPath: ZIP,
    sleep: async () => {},
    out: (line) => out.push(line),
    err: (line) => err.push(line),
  });
  return { code, calls, listed, uploads, argvs: calls.map((call) => call.argv), out: out.join("\n"), err: err.join("\n") };
}

const ASSETS = ["app/dist/assets", `s3://${BUCKET}/assets`];
const PAGES = ["app/dist", `s3://${BUCKET}`];
const asset = (ext, type, ...del) => [
  "aws", "s3", "sync", ...ASSETS, ...del, "--exclude", "*", "--include", `*${ext}`,
  "--content-type", type, "--cache-control", IMMUTABLE, "--only-show-errors", ...FLAGS,
];
const page = (ext, type) => [
  "aws", "s3", "sync", ...PAGES, "--delete", "--exclude", "*", "--include", `*${ext}`, "--exclude", "assets/*",
  "--content-type", type, "--cache-control", "no-cache", "--only-show-errors", ...FLAGS,
];

test("the calls come in order, with the flags", async () => {
  const { code, calls, listed, argvs, out } = await deploy();
  assert.equal(code, 0);
  assert.deepEqual(argvs, [
    [
      "aws", "cloudformation", "describe-stacks", "--stack-name", "lusot-test",
      "--query", "Stacks[0].Outputs", "--output", "json", ...FLAGS,
    ],
    ["npm", "run", "build", "-w", "app"],
    ["node", "app/scripts/check-bundle.mjs", "app/dist"],
    // assets/, one type at a time, deleting nothing yet
    asset(".js", "text/javascript"),
    asset(".css", "text/css"),
    asset(".woff2", "font/woff2"),
    asset(".woff", "font/woff"),
    // everything else, one type at a time, each deleting only its own type's stale files outside assets/
    page(".html", "text/html; charset=utf-8"),
    page(".webmanifest", "application/manifest+json"),
    page(".txt", "text/plain; charset=utf-8"),
    page(".svg", "image/svg+xml"),
    page(".png", "image/png"),
    // uploads nothing; deletes stale files of the other types outside assets/
    [
      "aws", "s3", "sync", ...PAGES, "--delete", "--exclude", "assets/*", "--exclude", "*.html",
      "--exclude", "*.webmanifest", "--exclude", "*.txt", "--exclude", "*.svg", "--exclude", "*.png",
      "--only-show-errors", ...FLAGS,
    ],
    [
      "aws", "cloudfront", "create-invalidation", "--distribution-id", "E2EXAMPLE",
      "--paths", "/", "/index.html", "/manifest.webmanifest", "/licences.txt", "/icons/*",
      "--query", "Invalidation.Id", "--output", "text", ...FLAGS,
    ],
    [
      "aws", "cloudfront", "wait", "invalidation-completed", "--distribution-id", "E2EXAMPLE",
      "--id", "I2EXAMPLE", ...FLAGS,
    ],
    // old assets, type by type, then those of any other type
    asset(".js", "text/javascript", "--delete"),
    asset(".css", "text/css", "--delete"),
    asset(".woff2", "font/woff2", "--delete"),
    asset(".woff", "font/woff", "--delete"),
    [
      "aws", "s3", "sync", ...ASSETS, "--delete", "--exclude", "*.js", "--exclude", "*.css",
      "--exclude", "*.woff2", "--exclude", "*.woff", "--only-show-errors", ...FLAGS,
    ],
  ]);
  // app/dist is listed once, after the build and the bundle check and before the first upload.
  assert.deepEqual(listed, [{ dir: "app/dist", after: 3 }]);
  // Every AWS call ends with the region, the profile and --no-cli-pager.
  for (const argv of argvs.filter((argv) => argv[0] === "aws")) assert.deepEqual(argv.slice(-FLAGS.length), FLAGS);
  // The build gets the stack's API and keeps the rest of the environment.
  const build = calls.find((call) => isBuild(call.argv));
  assert.equal(build.env.VITE_API_URL, API_URL);
  assert.equal(build.env.PATH, "test-path");
  assert.match(out, new RegExp(`${WEB_URL}$`));
});

test("the cache headers per path: each file goes up with its type's Content-Type, assets for a year, the rest no-cache", async () => {
  // One file of every type in the table, some in both places.
  const files = [
    "index.html", "manifest.webmanifest", "manifest.json", "licences.txt", "icons/icon.svg", "icons/icon-192.png",
    "assets/index-NEW.js", "assets/chunk-NEW.mjs", "assets/index-NEW.css", "assets/logo-NEW.svg",
    "assets/tile-NEW.png", "assets/font-NEW.woff2", "assets/font-NEW.woff",
  ];
  const { code, argvs } = await deploy({ files });
  assert.equal(code, 0);
  const { uploads } = syncEffects(argvs, files, []);
  const invalidation = argvs.findIndex(is("create-invalidation"));
  for (const file of files) {
    const mine = uploads.filter((upload) => upload.key === file);
    assert.ok(mine.some((upload) => upload.at < invalidation), `${file} goes up before the invalidation`);
    // Every sync that could upload the file sets its type and its cache header, so none leaves either to a guess.
    for (const upload of mine) {
      assert.equal(upload.type, SERVED_AS[posix.extname(file)], file);
      assert.equal(upload.cache, file.startsWith("assets/") ? IMMUTABLE : "no-cache", file);
    }
  }
  // No sync could upload anything that isn't one of the build's files under its own key.
  assert.ok(uploads.every((upload) => files.includes(upload.key)));
  // The invalidation covers the no-cache paths, the root object included, and never assets/.
  const paths = argvs[invalidation].slice(argvs[invalidation].indexOf("--paths") + 1, argvs[invalidation].indexOf("--query"));
  assert.deepEqual(paths, ["/", "/index.html", "/manifest.webmanifest", "/licences.txt", "/icons/*"]);
});

test("stale files of every type go, and old assets only after the invalidation has finished", async () => {
  // What an earlier deploy may have left: types the build still has, types it no longer has, in both places.
  const stale = [
    "old.html", "robots.txt", "sw.js", "icons/icon-old.png", "icons/old.ico",
    "assets/index-OLD.js", "assets/index-OLD.css", "assets/font-OLD.woff2", "assets/font-OLD.ttf",
    "assets/index-OLD.js.map", "assets/logo-OLD.svg",
  ];
  const { argvs } = await deploy();
  const { deletes } = syncEffects(argvs, DIST, [...DIST, ...stale]);
  // Every stale file goes, and nothing else does.
  assert.deepEqual([...new Set(deletes.map((d) => d.key))].sort(), [...stale].sort());
  const waited = argvs.findIndex(is("invalidation-completed"));
  for (const { key, at } of deletes) if (key.startsWith("assets/")) assert.ok(at > waited, `${key} goes after the wait`);
  // The first uploads of assets/ delete nothing, so the old page's files stay while it is still served.
  assert.ok(argvs.slice(0, waited).every((argv) => !(isAssetsSync(argv) && argv.includes("--delete"))));
});

for (const unknown of ["assets/index-NEW.js.map", "assets/INDEX-NEW.JS", "icons/LICENSE"]) {
  test(`a file of a type with no set Content-Type (${unknown}) stops the run before any upload`, async () => {
    const { code, argvs, listed, err } = await deploy({ files: [...DIST, unknown] });
    assert.equal(code, 1);
    assert.equal(listed.length, 1);
    assert.equal(argvs.length, 3);
    assert.ok(!argvs.some(is("s3")) && !argvs.some(is("cloudfront")));
    assert.ok(err.includes(`app/dist/${unknown}`), err);
  });
}

test("a failed describe-stacks stops the run with its own code, masked, before any other call", async () => {
  const { code, argvs, out, err } = await deploy({
    answer: (argv) =>
      argv.includes("describe-stacks")
        ? { code: 255, stderr: `An error occurred (ExpiredToken) when calling the DescribeStacks operation: ${ARN}\n` }
        : undefined,
  });
  assert.equal(code, 255);
  assert.equal(argvs.length, 1);
  assert.equal(out, "");
  assert.match(err, /ExpiredToken/);
  assert.match(err, /<arn>/);
  assert.ok(!err.includes("arn:") && !/[0-9]{12}/.test(err), err);
  assert.match(err, /reading the stack's outputs exited with 255/);
});

test("a failed build stops the run before any upload", async () => {
  const { code, argvs, err } = await deploy({
    answer: (argv) => (isBuild(argv) ? { code: 2, stderr: "error TS2322: nope" } : undefined),
  });
  assert.equal(code, 2);
  assert.equal(argvs.length, 2);
  assert.ok(!argvs.some(is("s3")) && !argvs.some(is("cloudfront")));
  assert.match(err, /build/);
});

test("a failed bundle check stops the run before any upload", async () => {
  const { code, argvs } = await deploy({
    answer: (argv) => (isBundleCheck(argv) ? { code: 1, stderr: "bundle check FAILED, 1 hit" } : undefined),
  });
  assert.equal(code, 1);
  assert.equal(argvs.length, 3);
  assert.ok(!argvs.some(is("s3")) && !argvs.some(is("cloudfront")));
});

for (const [name, isFailing] of [
  ["the assets upload", isAssetsSync],
  ["the rest's upload", isRestSync],
]) {
  test(`a failed sync (${name}) exits 1 before the invalidation`, async () => {
    const { code, argvs, out } = await deploy({
      answer: (argv) => (isFailing(argv) ? { code: 1, stderr: "upload failed" } : undefined),
    });
    assert.equal(code, 1);
    assert.ok(!argvs.some(is("cloudfront")));
    assert.doesNotMatch(out, /cloudfront\.net/);
  });
}

test("a failed invalidation exits non-zero and leaves the old assets", async () => {
  const { code, argvs } = await deploy({
    answer: (argv) => (argv.includes("invalidation-completed") ? { code: 255, stderr: "Max attempts exceeded" } : undefined),
  });
  assert.equal(code, 255);
  assert.ok(!argvs.some((argv) => isAssetsSync(argv) && argv.includes("--delete")));
});

test("no 12-digit run, ARN or contact address reaches stdout or stderr", async () => {
  const noisy = `${ARN} account ${ACCOUNT} contact ${CONTACT}\n`;
  const loud = (argv) =>
    argv.includes("describe-stacks") || argv.includes("create-invalidation") ? undefined : { stdout: noisy, stderr: noisy };
  const clean = await deploy({ answer: loud, env: { PATH: "test-path", VITE_PRIVACY_CONTACT: CONTACT } });
  const failed = await deploy({
    answer: (argv) => (isRestSync(argv) ? { code: 1, stdout: noisy, stderr: noisy } : loud(argv)),
  });
  assert.equal(clean.code, 0);
  assert.equal(failed.code, 1);
  // A failed step's output is shown, masked.
  assert.match(failed.err, /<arn>/);
  assert.match(failed.err, /<account>/);
  assert.match(failed.err, /<email>/);
  for (const text of [clean.out, clean.err, failed.out, failed.err]) {
    assert.ok(!/[0-9]{12}/.test(text), text);
    assert.ok(!text.includes("arn:"), text);
    assert.ok(!text.includes(CONTACT), text);
  }
  // A step that succeeds shows only its status.
  assert.doesNotMatch(clean.out, /account|contact/);
});

test("a missing samconfig.toml stops the run before any call", async () => {
  const { code, argvs, err } = await deploy({ samconfig: null });
  assert.equal(code, 1);
  assert.deepEqual(argvs, []);
  assert.match(err, /samconfig\.toml/);
});

test("with WebHosting off, or not set, the run stops before any call and says why", async () => {
  for (const samconfig of [
    SAMCONFIG.replace("WebHosting=on", "WebHosting=off"),
    SAMCONFIG.replace(" WebHosting=on", ""),
  ]) {
    const { code, argvs, err } = await deploy({ samconfig });
    assert.equal(code, 1);
    assert.deepEqual(argvs, []);
    assert.match(err, /WebHosting isn't on or amplify in backend\/samconfig\.toml/);
    assert.ok(!err.includes(CONTACT), err);
  }
});

test("a stack without the web outputs stops the run before the build", async () => {
  const { code, argvs, err } = await deploy({
    answer: (argv) =>
      argv.includes("describe-stacks")
        ? { stdout: JSON.stringify(OUTPUTS.filter((o) => o.OutputKey !== "WebBucketName")) }
        : undefined,
  });
  assert.equal(code, 1);
  assert.equal(argvs.length, 1);
  assert.match(err, /WebBucketName/);
});

// The web app's service worker (MS5 Task 16). A browser that fetched the new sw.js while the old pages were still
// live would precache the old page under the new revision, and blank once the old assets went. So sw.js goes up
// alone, after the new pages are live and invalidated, is invalidated itself, and only then do the old assets go.
test("the service worker goes up last, after the new pages are live, and before the old assets go", async () => {
  const files = [...DIST, "sw.js", "workbox-NEW.js"];
  const { code, argvs } = await deploy({ files });
  assert.equal(code, 0);
  const { uploads } = syncEffects(argvs, files, files);
  assert.equal(uploads.some((upload) => upload.key === "sw.js"), false, "no sync uploads sw.js");
  // Its Workbox chunk goes up with the pages, no-cache.
  assert.deepEqual(
    uploads.filter((upload) => upload.key === "workbox-NEW.js").map(({ type, cache }) => ({ type, cache })),
    [{ type: "text/javascript", cache: "no-cache" }],
  );
  const at = (find) => argvs.findIndex(find);
  const pagesWait = at((argv) => argv.includes("invalidation-completed"))
  const worker = at((argv) => argv[1] === "s3" && argv[2] === "cp")
  assert.deepEqual(argvs[worker], [
    "aws", "s3", "cp", "app/dist/sw.js", `s3://${BUCKET}/sw.js`,
    "--content-type", "text/javascript", "--cache-control", "no-cache", "--only-show-errors", ...FLAGS,
  ]);
  const workerInvalidation = at((argv) => argv.includes("create-invalidation") && argv.includes("/sw.js"));
  const workerWait = argvs.findLastIndex((argv) => argv.includes("invalidation-completed"));
  const removal = at((argv, i) => i > pagesWait && isAssetsSync(argv) && argv.includes("--delete"));
  assert.ok(pagesWait < worker && worker < workerInvalidation && workerInvalidation < workerWait && workerWait < removal,
    "pages live, then sw.js, its invalidation and its wait, then the old assets");
  assert.deepEqual(argvs[workerInvalidation].slice(argvs[workerInvalidation].indexOf("--paths"), -FLAGS.length - 4), ["--paths", "/sw.js"]);
  // No sync deletes the live sw.js before the new one replaces it.
  const { deletes } = syncEffects(argvs, files.filter((file) => file !== "sw.js"), files);
  assert.equal(deletes.some((gone) => gone.key === "sw.js"), false);
});

// WebHosting=amplify (Nov 2, while CloudFront waits for the account's check): the same build and checks, then the
// built app goes to Amplify as one zip, through a manual deployment, with no S3 sync and no CloudFront call.
const DIST_WITH_WORKER = [...DIST, "sw.js", "workbox-NEW.js"];
const amplify = (...args) => ["aws", "amplify", ...args, ...FLAGS];

test("with WebHosting=amplify: build, check, zip, create the deployment, upload to its link, start it, and wait", async () => {
  const { code, calls, argvs, uploads, out } = await deploy({
    samconfig: AMPLIFY_SAMCONFIG,
    outputs: AMPLIFY_OUTPUTS,
    files: DIST_WITH_WORKER,
  });
  assert.equal(code, 0);
  assert.deepEqual(argvs, [
    ["aws", "cloudformation", "describe-stacks", "--stack-name", "lusot-test", "--query", "Stacks[0].Outputs", "--output", "json", ...FLAGS],
    ["npm", "run", "build", "-w", "app"],
    ["node", "app/scripts/check-bundle.mjs", "app/dist"],
    // Every file of app/dist, at the zip's root, so index.html is where Amplify serves it from.
    ["tar", "-a", "-c", "-f", ZIP, "-C", "app/dist", ...DIST_WITH_WORKER],
    amplify("create-deployment", "--app-id", "d2abcdef123456", "--branch-name", "main", "--output", "json"),
    amplify("start-deployment", "--app-id", "d2abcdef123456", "--branch-name", "main", "--job-id", "7"),
    amplify("get-job", "--app-id", "d2abcdef123456", "--branch-name", "main", "--job-id", "7",
      "--query", "job.summary.status", "--output", "text"),
  ]);
  assert.equal(calls[1].env.VITE_API_URL, API_URL);
  // The zip goes to the deployment's own link, after create-deployment and before start-deployment.
  assert.deepEqual(uploads, [{ url: UPLOAD_URL, path: ZIP, after: 5 }]);
  assert.ok(!argvs.some((argv) => argv[1] === "s3" || argv[1] === "cloudfront"), "no S3 sync and no CloudFront call");
  assert.ok(out.includes(`web: ${AMPLIFY_URL}`), out);
});

test("with WebHosting=amplify, the job is polled until it ends, and a failed job stops the run", async () => {
  let reads = 0;
  const pending = await deploy({
    samconfig: AMPLIFY_SAMCONFIG,
    outputs: AMPLIFY_OUTPUTS,
    answer: (argv) => (argv.includes("get-job") ? { stdout: ++reads < 3 ? "RUNNING\n" : "SUCCEED\n" } : undefined),
  });
  assert.equal(pending.code, 0);
  assert.equal(pending.argvs.filter((argv) => argv.includes("get-job")).length, 3);

  const failed = await deploy({
    samconfig: AMPLIFY_SAMCONFIG,
    outputs: AMPLIFY_OUTPUTS,
    answer: (argv) => (argv.includes("get-job") ? { stdout: "FAILED\n" } : undefined),
  });
  assert.notEqual(failed.code, 0);
  assert.match(failed.err, /FAILED/);

  const stuck = await deploy({
    samconfig: AMPLIFY_SAMCONFIG,
    outputs: AMPLIFY_OUTPUTS,
    answer: (argv) => (argv.includes("get-job") ? { stdout: "RUNNING\n" } : undefined),
  });
  assert.notEqual(stuck.code, 0);
  assert.match(stuck.err, /still RUNNING/);
});

test("with WebHosting=amplify, a failed upload stops the run before the deployment starts, and its link is never shown", async () => {
  const { code, argvs, out, err } = await deploy({
    samconfig: AMPLIFY_SAMCONFIG,
    outputs: AMPLIFY_OUTPUTS,
    uploaded: async () => ({ ok: false, status: 403 }),
  });
  assert.notEqual(code, 0);
  assert.ok(!argvs.some((argv) => argv.includes("start-deployment")));
  assert.match(err, /upload.*403/);
  for (const text of [out, err]) {
    assert.ok(!text.includes("SECRETSIG") && !text.includes(UPLOAD_URL), text);
  }
});

// Every stop after create-deployment names the job, so a run that stopped midway can be found and checked.
const JOB_HINT = "aws amplify get-job --app-id d2abcdef123456 --branch-name main --job-id 7";

test("with WebHosting=amplify, each stop after create-deployment names the job and how to check it", async () => {
  const stops = {
    "a failed upload": { uploaded: async () => ({ ok: false, status: 403 }) },
    "a failed start": { answer: (argv) => (argv.includes("start-deployment") ? { code: 254, stderr: "boom" } : undefined) },
    "a failed job": { answer: (argv) => (argv.includes("get-job") ? { stdout: "FAILED\n" } : undefined) },
    "a job still running": { answer: (argv) => (argv.includes("get-job") ? { stdout: "RUNNING\n" } : undefined) },
  };
  for (const [name, options] of Object.entries(stops)) {
    const { code, err } = await deploy({ samconfig: AMPLIFY_SAMCONFIG, outputs: AMPLIFY_OUTPUTS, ...options });
    assert.notEqual(code, 0, name);
    assert.ok(err.includes(JOB_HINT), `${name}: ${err}`);
  }
});

test("with WebHosting=amplify, a network error during the upload stops the run, masked, before the deployment starts", async () => {
  const { code, argvs, out, err } = await deploy({
    samconfig: AMPLIFY_SAMCONFIG,
    outputs: AMPLIFY_OUTPUTS,
    uploaded: async () => {
      throw new TypeError(`fetch failed: ${UPLOAD_URL}`);
    },
  });
  assert.equal(code, 1);
  assert.ok(!argvs.some((argv) => argv.includes("start-deployment")));
  assert.match(err, /deploy:web stopped: the zip's upload failed: fetch failed/);
  assert.ok(err.includes(JOB_HINT), err);
  for (const text of [out, err]) assert.ok(!text.includes("SECRETSIG"), text);
});

test("with WebHosting=amplify, create-deployment output that isn't a job stops the run before any upload", async () => {
  for (const stdout of ["not json", JSON.stringify({ jobId: "7" }), "null"]) {
    const { code, argvs, uploads, err } = await deploy({
      samconfig: AMPLIFY_SAMCONFIG,
      outputs: AMPLIFY_OUTPUTS,
      answer: (argv) => (argv.includes("create-deployment") ? { stdout } : undefined),
    });
    assert.equal(code, 1, stdout);
    assert.equal(uploads.length, 0, stdout);
    assert.ok(!argvs.some((argv) => argv.includes("start-deployment")), stdout);
    assert.match(err, /create-deployment gave no job id or upload link/);
  }
});

test("with WebHosting=amplify, a file of a type with no set Content-Type stops the run before the zip", async () => {
  const { code, argvs, err } = await deploy({
    samconfig: AMPLIFY_SAMCONFIG,
    outputs: AMPLIFY_OUTPUTS,
    files: [...DIST, "icons/LICENSE"],
  });
  assert.equal(code, 1);
  assert.equal(argvs.length, 3);
  assert.ok(!argvs.some((argv) => argv[0] === "tar" || argv[1] === "amplify"));
  assert.ok(err.includes("app/dist/icons/LICENSE"), err);
});

test("scrub masks a presigned link whole, its signature included", () => {
  assert.equal(scrub(`PUT ${UPLOAD_URL} failed`), "PUT <presigned link> failed");
  assert.equal(scrub("see https://example.org/page"), "see https://example.org/page");
});

test("with WebHosting=amplify, a stack without Amplify's outputs stops the run before the build", async () => {
  const { code, argvs, err } = await deploy({ samconfig: AMPLIFY_SAMCONFIG, outputs: OUTPUTS });
  assert.equal(code, 1);
  assert.equal(argvs.length, 1);
  assert.match(err, /WebAmplifyAppId/);
});
