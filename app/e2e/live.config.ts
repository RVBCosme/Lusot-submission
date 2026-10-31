// MS7's live pass (MS7 Task 10, C820): the deployed site as judges see it. There is no build, no web server and no
// mock: LUSOT_LIVE_URL names the site, and every live-*.spec.ts skips without it, so this config is safe to run bare.
// The specs make no upload and send no question; a guard aborts any request that isn't a read (e2e/live.ts).
//
// Run from app/: npx playwright test --config e2e/live.config.ts, with LUSOT_LIVE_URL set to the site's address.
//
// A pin's id is a report id (MS7's C812). No trace, screenshot or video is kept, and the list reporter only. Playwright
// still writes an error-context file for a failed test, whose page snapshot can list pin links, so its output folder
// is outside the repo (the repo is also an Obsidian vault): the system's temp folder.
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { defineConfig } from '@playwright/test'

export default defineConfig({
  testDir: '.',
  testMatch: /live-.*\.spec\.ts/,
  workers: 1,
  fullyParallel: false,
  forbidOnly: process.env.CI !== undefined,
  retries: 0,
  reporter: 'list',
  timeout: 180_000,
  expect: { timeout: 20_000 },
  outputDir: join(tmpdir(), 'lusot-live-pass'),
  use: {
    baseURL: process.env.LUSOT_LIVE_URL,
    // The app has no service worker (S5-R20); blocking one keeps every request in front of the guard.
    serviceWorkers: 'block',
    trace: 'off',
    screenshot: 'off',
    video: 'off',
    permissions: ['camera'],
  },
  projects: [
    {
      name: 'live',
      use: {
        browserName: 'chromium',
        viewport: { width: 360, height: 640 },
        // MS5's fake-media flags: the camera is Chromium's own test pattern, and its prompt answers itself.
        launchOptions: { args: ['--use-fake-ui-for-media-stream', '--use-fake-device-for-media-stream'] },
      },
    },
  ],
})
