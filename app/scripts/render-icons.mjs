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
