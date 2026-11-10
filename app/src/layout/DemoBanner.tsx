import { useId } from 'react'
import { DEMO_SCENARIOS, type DemoScenario } from '../demo'
import { T, useT } from '../i18n'

// The outcome the page was loaded with (`?mock=`), or the first one.
function currentScenario(): DemoScenario {
  const asked = new URLSearchParams(location.search).get('mock') ?? ''
  return (DEMO_SCENARIOS as readonly string[]).includes(asked) ? (asked as DemoScenario) : DEMO_SCENARIOS[0]
}

// The portfolio demo's notice (app/src/demo.ts), shown only in that build, in the layout's notice row like the
// offline banner. The title stays in view; the details open on a tap. The outcome picker reloads the page with
// `?mock=<scenario>`, which the mock reads on load, so a report, a photo of your own or a drawn sample ends that way.
export function DemoBanner() {
  const t = useT()
  const selectId = useId()
  const choose = (scenario: string) => {
    const url = new URL(location.href)
    url.searchParams.set('mock', scenario)
    location.assign(url.href)
  }
  return (
    <section aria-label={t('demo.title').text} className="mt-2 rounded-control border border-outline p-2">
      <div className="flex flex-wrap items-center justify-between gap-x-3 gap-y-2">
        <details className="min-w-0 flex-1 basis-64">
          <summary className="cursor-pointer font-bold">
            <T k="demo.title" />
          </summary>
          <p className="mt-1 text-small text-ink-2">
            <T k="demo.body" />
          </p>
        </details>
        <div className="flex items-center gap-2">
          <label htmlFor={selectId} className="text-small">
            <T k="demo.outcome" />
          </label>
          <select
            id={selectId}
            defaultValue={currentScenario()}
            onChange={(event) => choose(event.target.value)}
            className="min-h-tap rounded-control border border-outline bg-surface px-2"
          >
            {DEMO_SCENARIOS.map((scenario) => (
              <option key={scenario} value={scenario}>
                {t(`demo.scenario.${scenario}` as const).text}
              </option>
            ))}
          </select>
        </div>
      </div>
    </section>
  )
}
