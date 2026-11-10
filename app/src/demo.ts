// The portfolio demo build (Nov 10, 2026): `npm run build:demo -w app`, which runs `vite build --mode demo`. The live
// system is shut down, so this build answers every API call from the mock (app/src/mock/) and sends no request to any
// API. Vite replaces import.meta.env.MODE with its value, so in any other build DEMO is the constant false and the
// bundler drops the mock and the demo's own parts (app/scripts/check-bundle.mjs proves it on a production build).
export const DEMO = import.meta.env.MODE === 'demo'

// The outcomes the demo banner offers, each a mock scenario (app/src/mock/fixtures.ts), read from `?mock=` on load.
export const DEMO_SCENARIOS = [
  'level_knee',
  'level_below_gutter',
  'level_above_chest',
  'no_flood_seen',
  'refused_references_disagree',
  'failed_model_error',
] as const

export type DemoScenario = (typeof DEMO_SCENARIOS)[number]
