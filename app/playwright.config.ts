// The end-to-end suite (MS5 Task 18). It runs the built app in Chromium against answers that the tests themselves give
// for every network request (e2e/mocks.ts): the app is built with VITE_API_URL=https://api.e2e.test, so nothing can reach
// the real API, and a request to any other host that no route answers fails the test.
//
// The builds go to the git-ignored .e2e-dist/<state>, never app/dist, so `cap sync` can't ship a test build. The Tested
// page's summary is fixed at build time, so there are four builds, one per Tested state, each served on its own port
// (e2e/fixtures/eval-results/<state>): `none` (no sealed run yet) serves every spec, and the other three serve only
// tested.spec.ts. Only `none` runs the bundle check, since the other fixtures carry the marker it fails on; each build
// writes its own licences.txt first.
//
// The projects. `street`: Chromium plays a synthetic street scene (e2e/frames.ts) as the camera, and answers its own
// permission prompts. `dark`: the same scene at night, for the tests tagged @dark only. `ask`, for Ask Lusot's spec only: the street scene, with a synthetic tone (e2e/tone.ts) as the microphone.
// `tested-<state>`: tested.spec.ts against each build. One worker, because the machine that runs this is short of memory.
import { defineConfig, type PlaywrightTestConfig } from '@playwright/test'
import { DARK_FRAME, STREET_FRAME } from './e2e/frames'
import { TONE_WAV } from './e2e/tone'

const HOST = '127.0.0.1'
// The Tested states, each with its own build and port.
const STATES = [
  { state: 'none', port: 4871 },
  { state: 'sealed-run', port: 4872 },
  { state: 'rerun', port: 4873 },
  { state: 'synthetic', port: 4874 },
] as const
const ORIGIN = `http://${HOST}:${STATES[0].port}`
// The tests the night scene's camera runs, and no other project does.
const DARK = /@dark/

const camera = (frame: string) => [
  '--use-fake-ui-for-media-stream',
  '--use-fake-device-for-media-stream',
  `--use-file-for-fake-video-capture=${frame}`,
]

type WebServer = Extract<NonNullable<PlaywrightTestConfig['webServer']>, { command: string }>

function server({ state, port }: (typeof STATES)[number]): WebServer {
  const out = `.e2e-dist/${state}`
  const build = state === 'none' ? 'npm run build:e2e' : `node scripts/licences.mjs && npx vite build --outDir ${out} --emptyOutDir`
  return {
    command: `${build} && npx vite preview --outDir ${out} --host ${HOST} --port ${port} --strictPort`,
    url: `http://${HOST}:${port}`,
    timeout: 300_000,
    reuseExistingServer: false,
    env: { VITE_API_URL: 'https://api.e2e.test', LUSOT_E2E_SUMMARY: state },
    stdout: 'pipe',
    stderr: 'pipe',
  }
}

export default defineConfig({
  testDir: './e2e',
  testMatch: '*.spec.ts',
  globalSetup: './e2e/global-setup.ts',
  workers: 1,
  fullyParallel: false,
  forbidOnly: process.env.CI !== undefined,
  retries: 0,
  // CI also writes the HTML report, which the job uploads with the traces when a run fails (.github/workflows/ci.yml).
  reporter: process.env.CI === undefined ? 'list' : [['list'], ['html', { open: 'never' }]],
  timeout: 120_000,
  expect: { timeout: 15_000 },
  outputDir: './test-results',
  use: {
    baseURL: ORIGIN,
    // The app's service worker (Task 16) is blocked, so it can't answer ahead of the routes in mocks.ts.
    serviceWorkers: 'block',
    // What a failed run leaves to read: the trace and a screenshot, in the git-ignored test-results. The pictures are the
    // synthetic street scene and the answers are the suite's own, so they hold nothing real.
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
    permissions: ['camera', 'geolocation'],
    // A fixed point in Metro Manila with a fix of 10 m, well inside the 50 m the report flow asks for (C603). Its place
    // is the one the unit tests use.
    geolocation: { latitude: 14.6123456, longitude: 121.0456789, accuracy: 10 },
  },
  projects: [
    {
      name: 'street',
      testIgnore: ['ask.spec.ts', 'tested.spec.ts'],
      grepInvert: DARK,
      use: {
        browserName: 'chromium',
        viewport: { width: 360, height: 640 },
        launchOptions: { args: camera(STREET_FRAME) },
      },
    },
    {
      name: 'dark',
      testMatch: 'outcomes.spec.ts',
      grep: DARK,
      use: {
        browserName: 'chromium',
        viewport: { width: 360, height: 640 },
        launchOptions: { args: camera(DARK_FRAME) },
      },
    },
    {
      name: 'ask',
      testMatch: 'ask.spec.ts',
      use: {
        browserName: 'chromium',
        viewport: { width: 360, height: 640 },
        permissions: ['camera', 'geolocation', 'microphone'],
        launchOptions: { args: [...camera(STREET_FRAME), `--use-file-for-fake-audio-capture=${TONE_WAV}`] },
      },
    },
    ...STATES.map(({ state, port }) => ({
      name: `tested-${state}`,
      testMatch: 'tested.spec.ts',
      metadata: { summary: state },
      use: { browserName: 'chromium' as const, viewport: { width: 360, height: 640 }, baseURL: `http://${HOST}:${port}` },
    })),
  ],
  webServer: STATES.map(server),
})
