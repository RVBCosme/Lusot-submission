import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { fileURLToPath } from 'node:url'
import { defineConfig } from 'vite'
import { configDefaults } from 'vitest/config'

// The Tested page reads MS6's results through `@eval-results` (app/src/lib/summary.ts): the repo's eval/results, which
// exists only from the sealed run, so its globs give {} until then. LUSOT_E2E_SUMMARY=<state> points it at
// app/e2e/fixtures/eval-results/<state> for Task 18's builds, one per state. Nothing is ever written under eval/.
function evalResults(state: string | undefined): string {
  if (state === undefined || state === '') return fileURLToPath(new URL('../eval/results', import.meta.url))
  // A plain folder name, so the alias can't point anywhere else.
  if (!/^[a-z0-9-]+$/.test(state)) throw new Error('LUSOT_E2E_SUMMARY takes a fixture folder name: a-z, 0-9 and -')
  return fileURLToPath(new URL(`./e2e/fixtures/eval-results/${state}`, import.meta.url))
}

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
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
})
