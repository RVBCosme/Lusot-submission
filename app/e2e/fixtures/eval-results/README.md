# The Tested page's end-to-end fixtures

The e2e builds point `@eval-results` at one of these folders (`LUSOT_E2E_SUMMARY=<folder>`, `app/vite.config.ts`), one
build per Tested state (MS5 Task 18):

- `none`: no sealed run yet, so the page shows no figure
- `sealed-run`: a sealed run's summary and `run.json`; named `sealed-run`, never `sealed`, because the project keeps
  agents out of any folder named exactly `sealed` (C39), and these are made-up figures, not sealed data
- `rerun`: the first run's pair, as in `sealed-run`, and a disclosed rerun's pair under `rerun/`, as MS6 lays them out;
  the rerun wins over the first run (MS6's C421)
- `synthetic`: a run marked `synthetic: true`, which the page never shows (MS6's C422)

Every figure is made up (dates in 2000), copied from `app/src/lib/__fixtures__`. Each file carries the marker
`LUSOT_E2E_FIXTURE`, so `app/scripts/check-bundle.mjs` fails a production build that picked one up.
