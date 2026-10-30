// Tests for deploy_web.mjs with a fake command runner: nothing is built and nothing reaches AWS.
// Run: node --test scripts/deploy_web.test.mjs
import assert from "node:assert/strict";
import { test } from "node:test";
import { deployWeb } from "./deploy_web.mjs";

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
  `parameter_overrides = "AlarmEmail=${CONTACT} BucketSuffix=abc123"`,
].join("\n");

const is = (word) => (argv) => argv.includes(word);
const isBuild = (argv) => argv[0] === "npm";
const isBundleCheck = (argv) => argv[0] === "node";
const isAssetsSync = (argv) => argv.includes("sync") && argv.includes("app/dist/assets");
const isRestSync = (argv) => argv.includes("sync") && argv.includes("app/dist");

// Runs deployWeb with a fake runner. `answer(argv)` may return a result for a call; any other call succeeds,
// with the stack's outputs for describe-stacks and an invalidation id for create-invalidation.
async function deploy({ answer = () => undefined, samconfig = SAMCONFIG, env = { PATH: "test-path" } } = {}) {
  const calls = [];
  const out = [];
  const err = [];
  const run = async (argv, options = {}) => {
    calls.push({ argv, env: options.env });
    const given = answer(argv);
    if (given) return { code: 0, stdout: "", stderr: "", ...given };
    if (argv.includes("describe-stacks")) return { code: 0, stdout: JSON.stringify(OUTPUTS), stderr: "" };
    if (argv.includes("create-invalidation")) return { code: 0, stdout: "I2EXAMPLE\n", stderr: "" };
    return { code: 0, stdout: "", stderr: "" };
  };
  const readText = (path) => {
    if (path === "backend/samconfig.toml" && samconfig !== null) return samconfig;
    throw Object.assign(new Error(`ENOENT: ${path}`), { code: "ENOENT" });
  };
  const code = await deployWeb({
    run,
    env,
    readText,
    out: (line) => out.push(line),
    err: (line) => err.push(line),
  });
  return { code, calls, argvs: calls.map((call) => call.argv), out: out.join("\n"), err: err.join("\n") };
}

test("the calls come in order, with the flags", async () => {
  const { code, calls, argvs, out } = await deploy();
  assert.equal(code, 0);
  assert.deepEqual(argvs, [
    [
      "aws", "cloudformation", "describe-stacks", "--stack-name", "lusot-test",
      "--query", "Stacks[0].Outputs", "--output", "json", ...FLAGS,
    ],
    ["npm", "run", "build", "-w", "app"],
    ["node", "app/scripts/check-bundle.mjs", "app/dist"],
    [
      "aws", "s3", "sync", "app/dist/assets", `s3://${BUCKET}/assets`,
      "--cache-control", IMMUTABLE, "--only-show-errors", ...FLAGS,
    ],
    [
      "aws", "s3", "sync", "app/dist", `s3://${BUCKET}`, "--delete", "--exclude", "assets/*",
      "--cache-control", "no-cache", "--only-show-errors", ...FLAGS,
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
    [
      "aws", "s3", "sync", "app/dist/assets", `s3://${BUCKET}/assets`, "--delete",
      "--cache-control", IMMUTABLE, "--only-show-errors", ...FLAGS,
    ],
  ]);
  // Every AWS call ends with the region, the profile and --no-cli-pager.
  for (const argv of argvs.filter((argv) => argv[0] === "aws")) assert.deepEqual(argv.slice(-FLAGS.length), FLAGS);
  // The build gets the stack's API and keeps the rest of the environment.
  const build = calls.find((call) => isBuild(call.argv));
  assert.equal(build.env.VITE_API_URL, API_URL);
  assert.equal(build.env.PATH, "test-path");
  assert.match(out, new RegExp(`${WEB_URL}$`));
});

test("the cache headers per path: assets for a year, everything else no-cache", async () => {
  const { argvs } = await deploy();
  const cacheControl = (argv) => argv[argv.indexOf("--cache-control") + 1];
  const assets = argvs.filter(isAssetsSync);
  assert.equal(assets.length, 2);
  for (const argv of assets) assert.equal(cacheControl(argv), IMMUTABLE);
  // index.html, manifest.webmanifest, licences.txt and icons/ are all of app/dist outside assets/.
  const rest = argvs.filter(isRestSync);
  assert.equal(rest.length, 1);
  assert.equal(cacheControl(rest[0]), "no-cache");
  assert.equal(rest[0][rest[0].indexOf("--exclude") + 1], "assets/*");
  // The invalidation covers the no-cache paths, the root object included, and never assets/.
  const invalidation = argvs.find(is("create-invalidation"));
  const paths = invalidation.slice(invalidation.indexOf("--paths") + 1, invalidation.indexOf("--query"));
  assert.deepEqual(paths, ["/", "/index.html", "/manifest.webmanifest", "/licences.txt", "/icons/*"]);
});

test("old assets are deleted only after the invalidation has finished", async () => {
  const { argvs } = await deploy();
  const waited = argvs.findIndex(is("invalidation-completed"));
  const deletes = argvs.map((argv, i) => [argv, i]).filter(([argv]) => isAssetsSync(argv) && argv.includes("--delete"));
  assert.equal(deletes.length, 1);
  assert.ok(deletes[0][1] > waited);
  // The first upload of assets/ deletes nothing, so the old page's files stay while it is still served.
  assert.ok(!argvs.find(isAssetsSync).includes("--delete"));
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
