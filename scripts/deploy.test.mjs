// Tests for the output mask in deploy.mjs. Run: node --test "scripts/*.test.mjs"
import assert from "node:assert/strict";
import { test } from "node:test";
import { createMasker } from "./deploy.mjs";

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
