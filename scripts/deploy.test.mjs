// Tests for the output mask and the WebHosting check in deploy.mjs. Run: node --test "scripts/*.test.mjs"
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import { createMasker, webHosting } from "./deploy.mjs";

const overrides = (value) => `[default.deploy.parameters]\nparameter_overrides = "${value}"\n`;

test("WebHosting is read from samconfig.toml's parameter_overrides", () => {
  assert.equal(webHosting(overrides("AlarmEmail=a BucketSuffix=abc123 WebHosting=off")), "off");
  assert.equal(webHosting(overrides("WebHosting=on AlarmEmail=a BucketSuffix=abc123")), "on");
  // Nov 2: the website on Amplify Hosting instead, while CloudFront waits for the account's check.
  assert.equal(webHosting(overrides("AlarmEmail=a WebHosting=amplify BucketSuffix=abc123")), "amplify");
});

test("a samconfig.toml that doesn't set WebHosting=on, off or amplify by name gives null", () => {
  for (const text of [
    overrides("AlarmEmail=a BucketSuffix=abc123"),
    overrides("AlarmEmail=a WebHosting=true"),
    overrides("AlarmEmail=a WebHosting=On"),
    overrides("AlarmEmail=a WebHosting=Amplify"),
    overrides("AlarmEmail=a WebHosting=cloudfront"),
    overrides("AlarmEmail=a NoWebHosting=off"),
    overrides("WebHosting=on WebHosting=off"),
    `# WebHosting=on\n${overrides("AlarmEmail=a")}`,
    "",
  ]) {
    assert.equal(webHosting(text), null, text);
  }
});

test("the example samconfig sets WebHosting=on", () => {
  const example = readFileSync(new URL("../backend/samconfig.example.toml", import.meta.url), "utf8");
  assert.equal(webHosting(example), "on");
});

// Feeds chunks to a masker and records what it writes.
function feed(...chunks) {
  const writes = [];
  const masker = createMasker((text) => writes.push(text));
  for (const chunk of chunks) masker.chunk(chunk);
  return { writes, masker };
}

test("a 12-digit ID split across two chunks is masked", () => {
  // The ID is split in the source too, so the repo's 12-digit scan never meets one.
  const { writes, masker } = feed(
    "Changeset arn:aws:cloudformation:ap-southeast-1:1234567",
    "89012:changeSet/x\n",
  );
  masker.flush();
  assert.equal(
    writes.join(""),
    "Changeset arn:aws:cloudformation:ap-southeast-1:<account>:changeSet/x\n",
  );
});

test("a trailing prompt with no newline is written at once", () => {
  const { writes } = feed("Deploy this changeset? [y/N]: ");
  assert.deepEqual(writes, ["Deploy this changeset? [y/N]: "]);
});

test("a trailing digit run is held until the next chunk or the flush", () => {
  const { writes, masker } = feed("pushed 4096");
  assert.equal(writes.join(""), "pushed ");
  masker.chunk("0 bytes\n");
  assert.equal(writes.join(""), "pushed 40960 bytes\n");
  masker.chunk("layer 77");
  assert.equal(writes.join(""), "pushed 40960 bytes\nlayer ");
  masker.flush();
  assert.equal(writes.join(""), "pushed 40960 bytes\nlayer 77");
});

test("a clean line passes through unchanged", () => {
  const line = "Successfully created/updated stack - lusot in ap-southeast-1\n";
  const { writes } = feed(line);
  assert.deepEqual(writes, [line]);
});
