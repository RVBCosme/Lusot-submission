// Tests for the web app manifest, its icons and the page's links to them (Task 16: the web app can be installed). The
// app has no service worker, so none of this is about offline use. Run: node --test "app/scripts/*.test.mjs"
// Node's file API is fine here: unlike the app's own tests, these scripts aren't type-checked against the browser.
import assert from "node:assert/strict";
import { existsSync, readFileSync } from "node:fs";
import { test } from "node:test";
import { fileURLToPath } from "node:url";

const app = (path) => fileURLToPath(new URL(`../${path}`, import.meta.url));
const read = (path) => readFileSync(app(path), "utf8");
const manifest = () => JSON.parse(read("public/manifest.webmanifest"));
const html = () => read("index.html");

// Task 3's tokens: the first --lusot-surface is the light theme's, the one after the dark media block is the dark's.
const tokens = read("src/styles/tokens.css");
const LIGHT_SURFACE = /--lusot-surface:\s*(#[0-9A-Fa-f]{6})/.exec(tokens)[1].toUpperCase();
const DARK_SURFACE = /:root\[data-theme="dark"\]\s*\{[^}]*--lusot-surface:\s*(#[0-9A-Fa-f]{6})/.exec(tokens)[1].toUpperCase();
const TOKEN_COLOURS = new Set([...tokens.matchAll(/--lusot-[\w-]+:\s*(#[0-9A-Fa-f]{6})\b/g)].map((m) => m[1].toUpperCase()));

// A PNG's size, from its header: the signature, then the IHDR chunk's width and height.
function pngSize(path) {
  const bytes = readFileSync(app(path));
  assert.deepEqual([...bytes.subarray(0, 8)], [0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a], `${path} is a PNG`);
  assert.equal(bytes.subarray(12, 16).toString("latin1"), "IHDR");
  return { width: bytes.readUInt32BE(16), height: bytes.readUInt32BE(20) };
}

test("the manifest names the app and opens it on the map, standalone, from its own folder", () => {
  const m = manifest();
  assert.equal(m.name, "Lusot");
  assert.equal(m.short_name, "Lusot");
  assert.equal(m.start_url, "./#/map");
  assert.equal(m.scope, "./");
  assert.equal(m.display, "standalone");
});

test("the manifest's colours are the light theme's page colour from the tokens", () => {
  const m = manifest();
  assert.equal(m.theme_color.toUpperCase(), LIGHT_SURFACE);
  assert.equal(m.background_color.toUpperCase(), LIGHT_SURFACE);
});

test("the manifest lists a 192 and a 512 icon, and a maskable 512, each a PNG of that size", () => {
  const { icons } = manifest();
  const want = [
    { sizes: "192x192", purpose: "any" },
    { sizes: "512x512", purpose: "any" },
    { sizes: "512x512", purpose: "maskable" },
  ];
  for (const { sizes, purpose } of want) {
    const icon = icons.find((i) => i.sizes === sizes && i.purpose === purpose);
    assert.ok(icon, `an icon of ${sizes} for ${purpose}`);
    assert.equal(icon.type, "image/png");
    const size = pngSize(`public/${icon.src.replace(/^\.?\//, "")}`);
    assert.deepEqual([size.width, size.height], sizes.split("x").map(Number), icon.src);
  }
  assert.equal(icons.length, want.length, "no icon beyond these");
});

test("the page links the manifest, an Apple touch icon, and a theme colour for each scheme", () => {
  const page = html();
  assert.match(page, /<link rel="manifest" href="\/manifest\.webmanifest"\s*\/?>/);
  assert.match(page, /<link rel="apple-touch-icon" href="\/icons\/apple-touch-icon\.png"\s*\/?>/);
  const themes = [...page.matchAll(/<meta name="theme-color" content="(#[0-9A-Fa-f]{6})" media="([^"]+)"\s*\/?>/g)];
  const byScheme = Object.fromEntries(themes.map((m) => [m[2], m[1].toUpperCase()]));
  assert.equal(byScheme["(prefers-color-scheme: light)"], LIGHT_SURFACE);
  assert.equal(byScheme["(prefers-color-scheme: dark)"], DARK_SURFACE);
});

test("the Apple touch icon is a 180 px PNG", () => {
  assert.deepEqual(pngSize("public/icons/apple-touch-icon.png"), { width: 180, height: 180 });
});

test("the icons' SVG source uses only the tokens' colours, and its first shape fills the whole square", () => {
  assert.ok(existsSync(app("public/icons/icon.svg")), "the SVG source is committed with the PNGs");
  const svg = read("public/icons/icon.svg");
  const colours = [...svg.matchAll(/#[0-9A-Fa-f]{6}\b/g)].map((m) => m[0].toUpperCase());
  assert.ok(colours.length > 0);
  for (const colour of colours) assert.ok(TOKEN_COLOURS.has(colour), `${colour} is one of Task 3's colours`);
  assert.match(svg, /<rect width="512" height="512" fill="#[0-9A-Fa-f]{6}"\s*\/>/);
  assert.match(svg, /viewBox="0 0 512 512"/);
});
