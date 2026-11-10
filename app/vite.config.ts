import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { defineConfig, type Plugin } from 'vite'
import { VitePWA } from 'vite-plugin-pwa'
import { configDefaults } from 'vitest/config'
import { pwaOptions } from './pwa.config.ts'

// The Tested page reads MS6's results through `@eval-results` (app/src/lib/summary.ts): the repo's eval/results, which
// exists only from the sealed run, so its globs give {} until then. LUSOT_E2E_SUMMARY=<state> points it at
// app/e2e/fixtures/eval-results/<state> for Task 18's builds, one per state. Nothing is ever written under eval/.
function evalResults(state: string | undefined): string {
  if (state === undefined || state === '') return fileURLToPath(new URL('../eval/results', import.meta.url))
  // A plain folder name, so the alias can't point anywhere else.
  if (!/^[a-z0-9-]+$/.test(state)) throw new Error('LUSOT_E2E_SUMMARY takes a fixture folder name: a-z, 0-9 and -')
  return fileURLToPath(new URL(`./e2e/fixtures/eval-results/${state}`, import.meta.url))
}

// The portfolio demo's two pictures (app/demo/, Nov 10, 2026), written to dist/demo/ by a `--mode demo` build only. An
// image the source imports is emitted even when the bundler then drops the code that uses it, so the mock can't import
// them without every production build carrying them too; app/src/mock/real/ondoy.ts names these paths instead.
const DEMO_FILES = ['ondoy-photo.jpg', 'ondoy-overlay.jpg']
function demoFiles(mode: string): Plugin {
  return {
    name: 'lusot-demo-files',
    apply: 'build',
    generateBundle() {
      if (mode !== 'demo') return
      for (const name of DEMO_FILES) {
        this.emitFile({ type: 'asset', fileName: `demo/${name}`, source: readFileSync(new URL(`./demo/${name}`, import.meta.url)) })
      }
    },
  }
}

// https://vite.dev/config/
export default defineConfig(({ mode }) => ({
  plugins: [react(), tailwindcss(), VitePWA(pwaOptions), demoFiles(mode)],
  resolve: {
    alias: { '@eval-results': evalResults(process.env.LUSOT_E2E_SUMMARY) },
  },
  test: {
    environment: 'jsdom',
    setupFiles: ['src/test/setup.ts'],
    // The Playwright suite (e2e/) and the Node scripts (scripts/) aren't Vitest tests.
    exclude: [...configDefaults.exclude, 'e2e/**', 'scripts/**'],
    // Vitest swaps every CSS file for an empty string, a ?raw read included. The token tests read tokens.css and
    // index.css as text, so those reads return the real file. Imported as styles, CSS stays empty.
    css: { include: [/\.css\?raw$/] },
  },
}))
