// The end-to-end suite (MS5 Task 18). It runs the built app in Chromium against answers that the tests themselves give
// for every network request (e2e/mocks.ts): the app is built with VITE_API_URL=https://api.e2e.test, so nothing can reach
// the real API, and a request to any other host that no route answers fails the test.
//
// The build goes to the git-ignored .e2e-dist/none, never app/dist, so `cap sync` can't ship a test build. One build
// serves every spec: the Tested page's summary is fixed at build time, and `none` is the state with no sealed run yet.
//
// One project, `street`: Chromium plays a synthetic street scene (e2e/frames.ts) as the camera, and answers its own
// permission prompts. One worker, because the machine that runs this is short of memory.
import { defineConfig } from '@playwright/test'
import { STREET_FRAME } from './e2e/frames'

const PORT = 4871
const ORIGIN = `http://127.0.0.1:${PORT}`

export default defineConfig({
  testDir: './e2e',
  testMatch: '*.spec.ts',
  globalSetup: './e2e/global-setup.ts',
  workers: 1,
  fullyParallel: false,
  forbidOnly: process.env.CI !== undefined,
  retries: 0,
  reporter: 'list',
  timeout: 120_000,
  expect: { timeout: 15_000 },
  outputDir: './test-results',
  use: {
    baseURL: ORIGIN,
    // The app has no service worker (S5-R20); blocking one is harmless and keeps it from answering ahead of the routes.
    serviceWorkers: 'block',
    permissions: ['camera', 'geolocation'],
    // A fixed point in Metro Manila with a fix of 10 m, well inside the 50 m the report flow asks for (C603). Its place
    // is the one the unit tests use.
    geolocation: { latitude: 14.6123456, longitude: 121.0456789, accuracy: 10 },
  },
  projects: [
    {
      name: 'street',
      use: {
        browserName: 'chromium',
        viewport: { width: 360, height: 640 },
        launchOptions: {
          args: [
            '--use-fake-ui-for-media-stream',
            '--use-fake-device-for-media-stream',
            `--use-file-for-fake-video-capture=${STREET_FRAME}`,
          ],
        },
      },
    },
  ],
  webServer: {
    command: `npm run build:e2e && npx vite preview --outDir .e2e-dist/none --host 127.0.0.1 --port ${PORT} --strictPort`,
    url: ORIGIN,
    timeout: 300_000,
    reuseExistingServer: false,
    env: { VITE_API_URL: 'https://api.e2e.test', LUSOT_E2E_SUMMARY: 'none' },
    stdout: 'pipe',
    stderr: 'pipe',
  },
})
