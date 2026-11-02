// Draws Lusot's icon PNGs from the two SVGs, with Playwright's Chromium: the web app's icons (app/public/icons/) and,
// further down, the Android launcher icons and splash images. Run it by hand after the mark or the navy changes, and
// commit what it writes; CI never runs it. It needs the browser once: `npx playwright install chromium`.
//   node app/scripts/render-icons.mjs
//
// The sources are app/brand/lusot-mark.svg, the mark on a transparent square, and the navy in
// app/src/styles/tokens.css. A canvas is a navy background (a full square, a rounded one, a circle, or none) with the
// mark centred on it. `scale` is the mark's square as a fraction of the canvas's shorter side. The mark itself reaches
// 37.4% of its square's width from the centre, so a scale of 1 puts it inside a mask's 40% (the web icons) and a
// smaller scale puts it inside a smaller circle: render-icons's numbers are checked by pwa-assets.test.mjs.
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { chromium } from "@playwright/test";

const app = (path) => fileURLToPath(new URL(`../${path}`, import.meta.url));

const mark = readFileSync(app("brand/lusot-mark.svg"), "utf8");
const navy = /--lusot-brand-navy:\s*(#[0-9A-Fa-f]{6})/.exec(readFileSync(app("src/styles/tokens.css"), "utf8"))?.[1];
if (navy === undefined) throw new Error("tokens.css has no --lusot-brand-navy");

// The picture as a page: `shape` is the navy's outline ("square", "rounded", "circle") or null for a transparent canvas.
function page({ width, height, shape, scale }) {
  const side = Math.min(width, height) * scale;
  const radius = { square: "0", rounded: "16%", circle: "50%" }[shape];
  const background = shape === null ? "" : `<div style="position:absolute;inset:0;background:${navy};border-radius:${radius}"></div>`;
  return `<!doctype html><meta charset="utf-8"><style>
    html,body{margin:0;width:${width}px;height:${height}px;background:transparent;overflow:hidden}
    .mark{position:absolute;left:${(width - side) / 2}px;top:${(height - side) / 2}px;width:${side}px;height:${side}px}
    .mark svg{display:block;width:100%;height:100%}
  </style>${background}<div class="mark">${mark}</div>`;
}

// Every file to write: its path under app/, and how to draw it.
const jobs = [];
const add = (path, spec) => jobs.push({ path, ...spec });

// The web app's icons. The maskable one is the same picture: its mark already sits inside the central 80% circle.
for (const [name, size] of [["icon-192", 192], ["icon-512", 512], ["icon-maskable-512", 512], ["apple-touch-icon", 180]]) {
  add(`public/icons/${name}.png`, { width: size, height: size, shape: "square", scale: 1 });
}

// The Android app (Android's documentation, checked with Context7 on Nov 2, 2026):
// - The legacy launcher icons (48 dp) show on Android 7.x only, which has no adaptive icons: a rounded navy square and a
//   navy circle, the mark at the artwork's scale.
// - An adaptive icon's layers are 108 dp, and the system may cut everything outside the middle 66 dp circle, so the
//   foreground's mark must stay inside it: 78% of the square puts the mark's reach at 29.3% of the width, 31.6 dp of
//   the circle's 33. The navy is the background layer, a colour resource.
// - The Android 12 splash icon is 288 dp, and the system shows only its middle 192 dp circle (Theme.SplashScreen, no
//   icon background): 85% of the square puts the mark's reach at 31.9% of the width, 91.8 dp of the circle's 96.
const DENSITIES = { mdpi: 1, hdpi: 1.5, xhdpi: 2, xxhdpi: 3, xxxhdpi: 4 };
const RES = "android/app/src/main/res";
for (const [density, factor] of Object.entries(DENSITIES)) {
  const legacy = 48 * factor;
  add(`${RES}/mipmap-${density}/ic_launcher.png`, { width: legacy, height: legacy, shape: "rounded", scale: 1 });
  add(`${RES}/mipmap-${density}/ic_launcher_round.png`, { width: legacy, height: legacy, shape: "circle", scale: 1 });
  add(`${RES}/mipmap-${density}/ic_launcher_foreground.png`, { width: 108 * factor, height: 108 * factor, shape: null, scale: 0.78 });
  add(`${RES}/drawable-${density}/splash_icon.png`, { width: 288 * factor, height: 288 * factor, shape: null, scale: 0.85 });
}

// Capacitor's launch splash images, at the sizes its template uses: navy, the mark a third of the shorter side tall. The
// mark's height is 60.8% of its square (its box runs from 99.2 to 410.7 of 512), so its square is 0.34 / 0.608 of the side.
const SPLASH_MARK_HEIGHT = 0.34;
const MARK_HEIGHT = (410.7 - 99.2) / 512;
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
for (const [file, [width, height]] of Object.entries(SPLASH_SIZES)) {
  add(`${RES}/${file}`, { width, height, shape: "square", scale: SPLASH_MARK_HEIGHT / MARK_HEIGHT });
}

const browser = await chromium.launch();
try {
  const tab = await browser.newPage();
  for (const { path, width, height, shape, scale } of jobs) {
    await tab.setViewportSize({ width, height });
    await tab.setContent(page({ width, height, shape, scale }));
    mkdirSync(dirname(app(path)), { recursive: true });
    // omitBackground keeps a transparent canvas transparent; a navy one covers the page anyway.
    writeFileSync(app(path), await tab.screenshot({ type: "png", omitBackground: true }));
    console.log(`${path} ${width}x${height}`);
  }
} finally {
  await browser.close();
}
