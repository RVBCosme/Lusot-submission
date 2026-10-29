import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'
import { configDefaults } from 'vitest/config'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  test: {
    environment: 'jsdom',
    setupFiles: ['src/test/setup.ts'],
    // The Playwright suite (e2e/) and the Node scripts (scripts/) aren't Vitest tests.
    exclude: [...configDefaults.exclude, 'e2e/**', 'scripts/**'],
  },
})
