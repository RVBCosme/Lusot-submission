// Tests for the web app manifest, its icons and the page's links to them (Task 16: the web app can be installed). The
// app has no service worker, so none of this is about offline use. Run: node --test "app/scripts/*.test.mjs"
// Node's file API is fine here: unlike the app's own tests, these scripts aren't type-checked against the browser.
import assert from "node:assert/strict";
import { existsSync, readdirSync, readFileSync } from "node:fs";
import { inflateSync } from "node:zlib";
import { test } from "node:test";
import { fileURLToPath } from "node:url";

const app = (path) => fileURLToPath(new URL(`../${path}`, import.meta.url));
const read = (path) => readFileSync(app(path), "utf8");
const manifest = () => JSON.parse(read("public/manifest.webmanifest"));
const html = () => read("index.html");

// Task 3's tokens.
const tokens = read("src/styles/tokens.css");
const TOKEN_COLOURS = new Set([...tokens.matchAll(/--lusot-[\w-]+:\s*(#[0-9A-Fa-f]{6})\b/g)].map((m) => m[1].toUpperCase()));
// The brand colours the logo artwork gives (tokens.css's shared block).
const token = (name) => new RegExp(`${name}:\\s*(#[0-9A-Fa-f]{6})`).exec(tokens)[1].toUpperCase();
const NAVY = token("--lusot-brand-navy");
const PALE = token("--lusot-brand-pale");
const WATER = token("--lusot-brand-water");

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

// The manifest's colours are the brand navy, not the page colour: a browser draws the launch splash of an installed app
// from background_color and the icon before any page loads, and index.html's loading screen carries on from it in the
// same navy. A light splash would flash between two navy screens. Once the page is up, its own theme-color tags (the
// next test) carry the same navy for both schemes, so the browser's toolbar matches the navy header, which is navy in the
// light and the dark theme alike.
test("the manifest's colours are the brand navy, the colour of the launch splash and of the loading screen after it", () => {
  const m = manifest();
  assert.equal(m.theme_color.toUpperCase(), NAVY);
  assert.equal(m.background_color.toUpperCase(), NAVY);
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

test("the page links the manifest, an Apple touch icon, and the brand navy as the theme colour for each scheme", () => {
  const page = html();
  assert.match(page, /<link rel="manifest" href="\/manifest\.webmanifest"\s*\/?>/);
  assert.match(page, /<link rel="apple-touch-icon" href="\/icons\/apple-touch-icon\.png"\s*\/?>/);
  const themes = [...page.matchAll(/<meta name="theme-color" content="(#[0-9A-Fa-f]{6})" media="([^"]+)"\s*\/?>/g)];
  const byScheme = Object.fromEntries(themes.map((m) => [m[2], m[1].toUpperCase()]));
  assert.equal(byScheme["(prefers-color-scheme: light)"], NAVY);
  assert.equal(byScheme["(prefers-color-scheme: dark)"], NAVY);
  assert.equal(themes.length, 2, "one tag for each scheme, no other");
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

const hexes = (svg) => [...svg.matchAll(/#[0-9A-Fa-f]{6}\b/g)].map((m) => m[0].toUpperCase());
// Everything from <defs> to the last </g>: the mark itself, with no background.
const markBody = (svg) => /<defs>[\s\S]*<\/g>/.exec(svg)?.[0];

test("the master mark is the logo's L-shaped gauge on a transparent square, in the brand's pale and water colours", () => {
  assert.ok(existsSync(app("brand/lusot-mark.svg")), "the master is committed beside the artwork it was drawn from");
  const svg = read("brand/lusot-mark.svg");
  assert.match(svg, /viewBox="0 0 512 512"/);
  assert.deepEqual([...new Set(hexes(svg))].sort(), [PALE, WATER].sort());
  assert.doesNotMatch(svg, /<rect width="512" height="512"/, "no background: the foreground layers are cut from it");
  assert.match(svg, /<clipPath id="mark-clip">/, "one outline clips the pale gauge and the water");
  assert.ok(markBody(svg), "the mark sits between <defs> and the closing </g>");
});

test("the icon is the master's drawing on the brand navy, so the favicon, the PNGs and the master can't drift apart", () => {
  const icon = read("public/icons/icon.svg");
  assert.match(icon, new RegExp(`<rect width="512" height="512" fill="${NAVY}"\\s*/>`, "i"), "the first shape is the navy square");
  assert.deepEqual([...new Set(hexes(icon))].sort(), [NAVY, PALE, WATER].sort());
  assert.equal(markBody(icon), markBody(read("brand/lusot-mark.svg")));
});

test("the page's icon is Lusot's own, and Vite's template icon is gone", () => {
  assert.match(html(), /<link rel="icon" type="image\/svg\+xml" href="\/icons\/icon\.svg"\s*\/?>/);
  assert.doesNotMatch(html(), /favicon\.svg/);
  assert.equal(existsSync(app("public/favicon.svg")), false);
});

// ---- The icons' pixels (render-icons.mjs draws them from the two SVGs and commits them) ----

// Decodes a PNG file as Chromium writes it (8 bits per channel, RGB or RGBA, no interlacing) into a pixel reader. It is
// only here to check what the icons hold, so it takes nothing else.
function decodePng(path) {
  const bytes = readFileSync(app(path));
  assert.deepEqual([...bytes.subarray(0, 8)], [0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a], `${path} is a PNG`);
  let width = 0;
  let height = 0;
  let colourType = -1;
  const idat = [];
  for (let at = 8; at < bytes.length; ) {
    const length = bytes.readUInt32BE(at);
    const type = bytes.subarray(at + 4, at + 8).toString("latin1");
    const data = bytes.subarray(at + 8, at + 8 + length);
    if (type === "IHDR") {
      width = data.readUInt32BE(0);
      height = data.readUInt32BE(4);
      assert.equal(data[8], 8, `${path}: 8 bits per channel`);
      colourType = data[9];
      assert.equal(data[12], 0, `${path}: not interlaced`);
    } else if (type === "IDAT") idat.push(data);
    at += 12 + length;
  }
  assert.ok(colourType === 2 || colourType === 6, `${path}: RGB or RGBA, not colour type ${colourType}`);
  const channels = colourType === 6 ? 4 : 3;
  const stride = width * channels;
  const raw = inflateSync(Buffer.concat(idat));
  const pixels = Buffer.alloc(height * stride);
  for (let y = 0; y < height; y++) {
    const filter = raw[y * (stride + 1)];
    for (let i = 0; i < stride; i++) {
      const x = raw[y * (stride + 1) + 1 + i];
      const left = i >= channels ? pixels[y * stride + i - channels] : 0;
      const up = y > 0 ? pixels[(y - 1) * stride + i] : 0;
      const upLeft = y > 0 && i >= channels ? pixels[(y - 1) * stride + i - channels] : 0;
      const p = left + up - upLeft;
      const [pa, pb, pc] = [Math.abs(p - left), Math.abs(p - up), Math.abs(p - upLeft)];
      const paeth = pa <= pb && pa <= pc ? left : pb <= pc ? up : upLeft;
      pixels[y * stride + i] = (x + [0, left, up, (left + up) >> 1, paeth][filter]) & 255;
    }
  }
  const at = (x, y) => {
    const o = y * stride + x * channels;
    return [pixels[o], pixels[o + 1], pixels[o + 2], channels === 4 ? pixels[o + 3] : 255];
  };
  return { width, height, at };
}

const rgb = (hex) => [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16));
const NAVY_RGB = rgb(NAVY);
// How far a pixel is from the navy, summed over the channels (0 to 765). The mark's pale is 631 away and its blue 315,
// so over 150 is a pixel the mark covers by about half or more: its edge, to within half a pixel.
const awayFromNavy = ([r, g, b]) => Math.abs(r - NAVY_RGB[0]) + Math.abs(g - NAVY_RGB[1]) + Math.abs(b - NAVY_RGB[2]);

// The farthest any drawn pixel lies from the picture's centre, as a fraction of its width, and how many pixels are
// drawn: `drawn` says which pixels belong to the mark. A mark inside a circle of radius R keeps this at or under R.
function reach(img, drawn) {
  const cx = img.width / 2;
  const cy = img.height / 2;
  let far = 0;
  let count = 0;
  for (let y = 0; y < img.height; y++) {
    for (let x = 0; x < img.width; x++) {
      if (!drawn(img.at(x, y))) continue;
      count += 1;
      // The pixel's centre: with `drawn` meaning half covered or more, the edge is found to within half a pixel.
      far = Math.max(far, Math.hypot(x + 0.5 - cx, y + 0.5 - cy));
    }
  }
  return { fraction: far / img.width, count };
}

const everyPixel = (img, test) => {
  for (let y = 0; y < img.height; y++) for (let x = 0; x < img.width; x++) if (!test(img.at(x, y))) return false;
  return true;
};

test("the web icons are opaque, full-bleed navy squares of the sizes the manifest and Apple name", () => {
  for (const [path, size] of [
    ["public/icons/icon-192.png", 192],
    ["public/icons/icon-512.png", 512],
    ["public/icons/icon-maskable-512.png", 512],
    ["public/icons/apple-touch-icon.png", 180],
  ]) {
    const img = decodePng(path);
    assert.deepEqual([img.width, img.height], [size, size], path);
    assert.ok(everyPixel(img, ([, , , a]) => a === 255), `${path} has no transparent pixel (Apple fills one with black)`);
    for (const [x, y] of [[0, 0], [size - 1, 0], [0, size - 1], [size - 1, size - 1]]) {
      assert.deepEqual(img.at(x, y).slice(0, 3), NAVY_RGB, `${path}'s corner ${x},${y} is the navy, edge to edge`);
    }
  }
});

test("the maskable icon keeps its whole mark inside the central 80% circle, and still draws the mark large", () => {
  const img = decodePng("public/icons/icon-maskable-512.png");
  const { fraction, count } = reach(img, (p) => awayFromNavy(p) > 150);
  assert.ok(count > 0, "the mark is drawn");
  assert.ok(fraction <= 0.4, `the mark reaches ${(fraction * 100).toFixed(1)}% of the width from the centre; a mask can cut beyond 40%`);
  assert.ok(fraction >= 0.33, `the mark is not shrunk (it reaches ${(fraction * 100).toFixed(1)}%)`);
});

test("the Apple touch icon draws the same mark as the web icons, scaled", () => {
  const touch = decodePng("public/icons/apple-touch-icon.png");
  const big = decodePng("public/icons/icon-512.png");
  // The water blue sits at the same relative place in each: inside the foot, 75% down and 60% across.
  const water = (img) => img.at(Math.round(img.width * 0.6), Math.round(img.height * 0.75));
  assert.deepEqual(water(touch).slice(0, 3), rgb(WATER));
  assert.deepEqual(water(big).slice(0, 3), rgb(WATER));
});

// ---- The Android app's icons and splash screens (app/android/app/src/main/res) ----

const RES = "android/app/src/main/res";
// Android's density buckets and the factor each multiplies a dp size by.
const DENSITIES = { mdpi: 1, hdpi: 1.5, xhdpi: 2, xxhdpi: 3, xxxhdpi: 4 };
const half = (alphaPixel) => alphaPixel[3] > 127;
// Whether the picture holds a pixel of exactly this colour: the logo's own pale and water blue, so an icon drawn from
// anything else (the old gauge, say) fails.
const has = (img, [r, g, b]) => !everyPixel(img, (p) => !(p[0] === r && p[1] === g && p[2] === b && p[3] === 255));
const drawsLogo = (img) => has(img, rgb(PALE)) && has(img, rgb(WATER));
// The colour a values file gives a name: `<color name="x">#RRGGBB</color>`, in any file of res/values.
const colourNamed = (name) => {
  for (const file of readdirSync(app(`${RES}/values`))) {
    const found = new RegExp(`<color name="${name}">(#[0-9A-Fa-f]{6})</color>`).exec(read(`${RES}/values/${file}`));
    if (found) return found[1].toUpperCase();
  }
  return undefined;
};

test("the legacy launcher icons come in five densities: a rounded navy square, and a navy circle", () => {
  for (const [density, factor] of Object.entries(DENSITIES)) {
    const size = 48 * factor;
    for (const name of ["ic_launcher", "ic_launcher_round"]) {
      const path = `${RES}/mipmap-${density}/${name}.png`;
      const img = decodePng(path);
      assert.deepEqual([img.width, img.height], [size, size], path);
      assert.ok(img.at(0, 0)[3] < 128, `${path}: the corner is cut away`);
      assert.deepEqual(img.at(size >> 1, 2).slice(0, 4), [...NAVY_RGB, 255], `${path}: the top edge is solid navy`);
      assert.ok(drawsLogo(img), `${path} draws the logo's pale gauge and water`);
    }
  }
});

test("the adaptive launcher icon layers are 108 dp, transparent, and keep the whole mark inside the 66 dp safe circle", () => {
  for (const [density, factor] of Object.entries(DENSITIES)) {
    const size = 108 * factor;
    const path = `${RES}/mipmap-${density}/ic_launcher_foreground.png`;
    const img = decodePng(path);
    assert.deepEqual([img.width, img.height], [size, size], path);
    for (const [x, y] of [[0, 0], [size - 1, 0], [0, size - 1], [size - 1, size - 1], [size >> 1, 0]]) {
      assert.equal(img.at(x, y)[3], 0, `${path}: ${x},${y} is transparent`);
    }
    const { fraction } = reach(img, half);
    assert.ok(drawsLogo(img), `${path} draws the logo's pale gauge and water`);
    assert.ok(fraction <= 33 / 108, `${path}: the mark reaches ${(fraction * 108).toFixed(1)} dp from the centre; the safe circle's radius is 33 dp`);
    assert.ok(fraction >= 0.9 * (33 / 108), `${path}: the mark is not shrunk (it reaches ${(fraction * 108).toFixed(1)} dp)`);
  }
});

test("both adaptive icon files put the foreground layer on the navy colour resource", () => {
  for (const name of ["ic_launcher", "ic_launcher_round"]) {
    const xml = read(`${RES}/mipmap-anydpi-v26/${name}.xml`);
    assert.match(xml, /<adaptive-icon\b/);
    assert.match(xml, /<background android:drawable="@color\/ic_launcher_background"\s*\/>/);
    assert.match(xml, /<foreground android:drawable="@mipmap\/ic_launcher_foreground"\s*\/>/);
  }
  assert.equal(colourNamed("ic_launcher_background"), NAVY);
});

// Capacitor's launch splash images (drawable/splash.png and its port and land sizes): navy edge to edge, the mark
// centred and a third of the shorter side tall.
const SPLASH_SIZES = {
  "drawable/splash.png": [480, 320],
  "drawable-port-mdpi/splash.png": [320, 480],
  "drawable-port-hdpi/splash.png": [480, 800],
  "drawable-port-xhdpi/splash.png": [720, 1280],
  "drawable-port-xxhdpi/splash.png": [960, 1600],
  "drawable-port-xxxhdpi/splash.png": [1280, 1920],
  "drawable-land-mdpi/splash.png": [480, 320],
  "drawable-land-hdpi/splash.png": [800, 480],
  "drawable-land-xhdpi/splash.png": [1280, 720],
  "drawable-land-xxhdpi/splash.png": [1600, 960],
  "drawable-land-xxxhdpi/splash.png": [1920, 1280],
};

test("the splash images are navy with the mark centred, at the sizes Capacitor's template uses", () => {
  for (const [file, [width, height]] of Object.entries(SPLASH_SIZES)) {
    const path = `${RES}/${file}`;
    const img = decodePng(path);
    assert.deepEqual([img.width, img.height], [width, height], path);
    for (const [x, y] of [[0, 0], [width - 1, 0], [0, height - 1], [width - 1, height - 1]]) {
      assert.deepEqual(img.at(x, y).slice(0, 3), NAVY_RGB, `${path}: corner ${x},${y}`);
    }
    // The mark's box: every pixel it covers by about half or more.
    let [left, top, right, bottom] = [width, height, -1, -1];
    for (let y = 0; y < height; y++) {
      for (let x = 0; x < width; x++) {
        if (awayFromNavy(img.at(x, y)) <= 150) continue;
        [left, top, right, bottom] = [Math.min(left, x), Math.min(top, y), Math.max(right, x + 1), Math.max(bottom, y + 1)];
      }
    }
    assert.ok(right > left && drawsLogo(img), `${path} draws the logo's pale gauge and water`);
    assert.ok(Math.abs((left + right) / 2 - width / 2) <= width * 0.01, `${path}: the mark is centred across`);
    assert.ok(Math.abs((top + bottom) / 2 - height / 2) <= height * 0.01, `${path}: the mark is centred down`);
    const tall = (bottom - top) / Math.min(width, height);
    assert.ok(Math.abs(tall - 0.34) <= 0.012, `${path}: the mark is ${(tall * 100).toFixed(1)}% of the shorter side tall, not 34%`);
  }
});

test("the launch theme is Android 12's splash: navy background, the mark as its icon, then the app's own theme", () => {
  const styles = read(`${RES}/values/styles.xml`);
  const block = /<style name="AppTheme\.NoActionBarLaunch" parent="Theme\.SplashScreen">([\s\S]*?)<\/style>/.exec(styles)?.[1];
  assert.ok(block, "the launch theme keeps Capacitor's parent, Theme.SplashScreen (androidx.core:core-splashscreen)");
  const item = (name) => new RegExp(`<item name="${name}">([^<]*)</item>`).exec(block)?.[1];
  const background = /^@color\/(\w+)$/.exec(item("windowSplashScreenBackground") ?? "")?.[1];
  assert.ok(background, "windowSplashScreenBackground names a colour resource");
  assert.equal(colourNamed(background), NAVY, "and that colour is the brand navy");
  assert.equal(item("windowSplashScreenAnimatedIcon"), "@drawable/splash_icon");
  assert.equal(item("postSplashScreenTheme"), "@style/AppTheme.NoActionBar");
  assert.equal(item("android:background"), "@drawable/splash", "Capacitor's own splash image stays for the plugin and older code");
  assert.match(styles, /<style name="AppTheme\.NoActionBar"/, "the theme the launch theme hands over to exists");
});

test("the splash icon is 288 dp, transparent, and keeps the whole mark inside the 192 dp circle Android 12 shows", () => {
  for (const [density, factor] of Object.entries(DENSITIES)) {
    const size = 288 * factor;
    const path = `${RES}/drawable-${density}/splash_icon.png`;
    const img = decodePng(path);
    assert.deepEqual([img.width, img.height], [size, size], path);
    for (const [x, y] of [[0, 0], [size - 1, 0], [0, size - 1], [size - 1, size - 1]]) {
      assert.equal(img.at(x, y)[3], 0, `${path}: ${x},${y} is transparent`);
    }
    const { fraction } = reach(img, half);
    assert.ok(drawsLogo(img), `${path} draws the logo's pale gauge and water`);
    assert.ok(fraction <= 96 / 288, `${path}: the mark reaches ${(fraction * 288).toFixed(1)} dp from the centre; the circle's radius is 96 dp`);
    assert.ok(fraction >= 0.9 * (96 / 288), `${path}: the mark is not shrunk (it reaches ${(fraction * 288).toFixed(1)} dp)`);
  }
});

test("the Android values files are well-formed XML: no comment holds a double hyphen, which XML forbids and aapt refuses", () => {
  for (const file of readdirSync(app(`${RES}/values`))) {
    const xml = read(`${RES}/values/${file}`);
    assert.match(xml, /^<\?xml version=["']1\.0["'] encoding=["']utf-8["']\?>\s*<resources>/, file);
    for (const [, comment] of xml.matchAll(/<!--([\s\S]*?)-->/g)) assert.ok(!comment.includes("--"), `${file}: a comment holds "--"`);
    assert.equal((xml.match(/<!--/g) ?? []).length, (xml.match(/-->/g) ?? []).length, `${file}: every comment closes`);
  }
});
