// Tests for the Android app's file provider (MS7 Task 15, D-k). Run: node --test "scripts/*.test.mjs"
// It reads the manifest and the provider's paths file only; nothing here builds the APK.
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";

const MAIN = new URL("../app/android/app/src/main/", import.meta.url);
const manifest = readFileSync(new URL("AndroidManifest.xml", MAIN), "utf8");

// The <provider> elements, each with its attributes and its <meta-data> children.
function providers(xml) {
  return [...xml.matchAll(/<provider\b([^>]*)>([\s\S]*?)<\/provider>/g)].map(([, attrs, body]) => ({ attrs, body }));
}

const attr = (attrs, name) => new RegExp(`\\b${name}="([^"]*)"`).exec(attrs)?.[1];

test("exposes no broad file path", () => {
  const fileProviders = providers(manifest).filter((p) => attr(p.attrs, "android:name") === "androidx.core.content.FileProvider");
  // Kept: Capacitor's WebView client names the <package>.fileprovider authority for a file input.
  assert.equal(fileProviders.length, 1, "the FileProvider is kept, once");
  const [provider] = fileProviders;
  assert.equal(attr(provider.attrs, "android:authorities"), "${applicationId}.fileprovider");
  assert.equal(attr(provider.attrs, "android:exported"), "false");
  const resource = /android:name="android\.support\.FILE_PROVIDER_PATHS"\s+android:resource="@xml\/([A-Za-z0-9_]+)"/.exec(provider.body)?.[1];
  assert.ok(resource, "the provider names its paths file");

  const paths = readFileSync(new URL(`res/xml/${resource}.xml`, MAIN), "utf8").replace(/<!--[\s\S]*?-->/g, "");
  assert.doesNotMatch(paths, /<external-path\b/);
  assert.doesNotMatch(paths, /\bpath="\.?\/?"/, 'no path="." (or an empty one) at a root');
  const entries = [...paths.matchAll(/<([a-z-]+-path)\b([^>]*)\/?>/g)].map(([, tag, attrs]) => ({ tag, path: attr(attrs, "path") }));
  assert.ok(entries.length > 0, "the paths file shares something, or the provider would have no use");
  for (const { tag, path } of entries) {
    // Only the app's own cache: never files, external storage, media or the device root.
    assert.equal(tag, "cache-path", `<${tag}> points outside the app's cache`);
    assert.ok(path && !path.startsWith("/") && !path.split("/").includes("..") && !/^\.?\/?$/.test(path), `cache path "${path}" is not one subfolder`);
  }
});
