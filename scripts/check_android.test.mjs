// Tests for the Android app's file provider (MS7 Task 15, D-k). Run: node --test "scripts/*.test.mjs"
// It reads the manifest and the provider's paths file only; nothing here builds the APK, so the
// library manifests merged in at build time aren't seen.
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";

const MAIN = new URL("../app/android/app/src/main/", import.meta.url);
const stripComments = (xml) => xml.replace(/<!--[\s\S]*?-->/g, "");
const manifest = stripComments(readFileSync(new URL("AndroidManifest.xml", MAIN), "utf8"));

// An attribute's value, in either quote and with any spaces around `=`. The name must stand
// alone, so `path` is never read out of `data-path` or `android:path`.
function attr(attrs, name) {
  const m = new RegExp(`(?:^|\\s)${name.replace(/[.:]/g, "\\$&")}\\s*=\\s*(["'])(.*?)\\1`).exec(attrs);
  return m?.[2];
}

test("exposes no broad file path", () => {
  // Every <provider>, however it is written: exactly one, the FileProvider.
  const providers = [...manifest.matchAll(/<provider\b([^>]*)>([\s\S]*?)<\/provider>/g)].map(([, attrs, body]) => ({ attrs, body }));
  assert.equal((manifest.match(/<provider\b/g) ?? []).length, 1, "exactly one provider, in its long form");
  assert.equal(providers.length, 1);
  const [provider] = providers;
  // Kept, as D-k decided; Capacitor's WebView client names this authority for a capture input.
  assert.equal(attr(provider.attrs, "android:name"), "androidx.core.content.FileProvider");
  assert.equal(attr(provider.attrs, "android:authorities"), "${applicationId}.fileprovider");
  assert.equal(attr(provider.attrs, "android:exported"), "false");
  const meta = [...provider.body.matchAll(/<meta-data\b([^>]*)>/g)].map(([, attrs]) => attrs);
  assert.equal(meta.length, 1, "one meta-data, the paths file");
  assert.equal(attr(meta[0], "android:name"), "android.support.FILE_PROVIDER_PATHS");
  const resource = /^@xml\/([A-Za-z0-9_]+)$/.exec(attr(meta[0], "android:resource") ?? "")?.[1];
  assert.ok(resource, "the provider names its paths file");

  const raw = readFileSync(new URL(`res/xml/${resource}.xml`, MAIN), "utf8");
  const paths = stripComments(raw);
  assert.doesNotMatch(paths, /&/, "no entity, which the build would decode into another path");
  assert.doesNotMatch(paths, /<external-path\b/);
  assert.doesNotMatch(paths, /\bpath\s*=\s*(["'])\.?\/?\1/, 'no path="." (or an empty one) at a root');
  const entries = [...paths.matchAll(/<([A-Za-z-]+-path)\b([^>]*)\/?>/g)].map(([, tag, attrs]) => ({ tag, path: attr(attrs, "path") }));
  // One subfolder of the app's own cache, named plainly: never files, external storage, media,
  // the device root, the cache root, or a way out of it.
  assert.equal(entries.length, 1, "the provider shares one folder");
  assert.equal(entries[0].tag, "cache-path", `<${entries[0].tag}> points outside the app's cache`);
  assert.match(entries[0].path ?? "", /^[A-Za-z0-9_-]+\/$/, `cache path "${entries[0].path}" is not one plain subfolder`);
});
