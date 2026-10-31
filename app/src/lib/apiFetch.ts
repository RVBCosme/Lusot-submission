// Where the client's calls go: the development mock in a development build with VITE_API_MOCK=1, and the browser's
// fetch everywhere else. `import.meta.env.DEV` is false in a production build, which lets the bundler drop the mock
// and everything under app/src/mock/; app/scripts/check-bundle.mjs proves it on the built files.
// Chosen when this module loads, so a test that wants the other one sets the environment, then imports.
import { mockFetch } from '../mock/mockFetch'

export const apiFetch: typeof fetch = import.meta.env.DEV && import.meta.env.VITE_API_MOCK === '1' ? mockFetch : fetch
