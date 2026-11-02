import { FlaskConicalIcon } from 'lucide-react'
import { basisLine, depthLine, landmarkLine, levelLine, verdictLines } from '../copy/wording'
import { Line, T, useT } from '../i18n'
import { routeHash } from '../router'
import { Badge } from './Badge'
import { Gauge } from './Gauge'

const BUTTON =
  'inline-flex min-h-tap items-center gap-2 rounded-control bg-action px-4 font-bold text-on-action ' +
  'active:bg-ink active:text-surface'

// One fixed reading, taken from Task 6's mock knee-deep result: a parked car's wheel and a person, geometry reading the
// level. It is made up and says so; it is never a pin, and it is the only reading shown when there is no report.
const EXAMPLE = { level: 'knee', landmark: 'rim_three_quarters', basis: { vehicles: 1, people: 1 } } as const

// What the map shows when there are no pins (C618): the plain fact, a way in, and one card that says it is an example.
// "No reports" is never a statement about a spot, so the note says a spot with no report may still be flooded. From lg it
// keeps to a line of 65 characters, centred, rather than running across the width of a wide window under the map.
export function EmptyMap() {
  const t = useT()
  const landmark = landmarkLine(t, EXAMPLE.landmark)
  // Worded as a result card words a level (C639): the verdict, whose class it is, the level line, and the depth range.
  const verdict = verdictLines(t, EXAMPLE.level, false)
  const depth = depthLine(t, EXAMPLE.level, false)
  return (
    <section className="space-y-4 lg:mx-auto lg:w-full lg:max-w-prose lg:p-4">
      <div>
        <h2 className="text-balance text-heading font-bold">
          <T k="map.empty.title" />
        </h2>
        <p className="mt-1 text-pretty">
          <T k="map.empty.note" />
        </p>
        <p className="mt-3">
          <a href={routeHash({ name: 'tested' })} className={BUTTON}>
            <FlaskConicalIcon aria-hidden="true" className="size-5 shrink-0" />
            <T k="map.trySample" />
          </a>
        </p>
      </div>
      <article className="rounded-control border-2 border-solid border-outline bg-surface p-4">
        <div className="mb-3">
          <Badge>
            <T k="badge.example" />
          </Badge>
        </div>
        <p className="text-balance text-title font-bold">
          <Line value={verdict.verdict} />
        </p>
        {verdict.sub !== undefined && (
          <p className="mt-1 text-pretty text-small text-ink-2">
            <Line value={verdict.sub} />
          </p>
        )}
        <p className="mt-3 text-balance text-heading font-bold">
          <Line value={levelLine(t, EXAMPLE.level, false)} />
        </p>
        <div className="mt-4 flex flex-wrap gap-x-6 gap-y-4">
          <Gauge level={EXAMPLE.level} isFloor={false} />
          <div className="min-w-0 flex-1 basis-48 space-y-2">
            {landmark !== undefined && (
              <p className="text-pretty">
                <Line value={landmark} />
              </p>
            )}
            {depth !== undefined && (
              <p className="text-pretty">
                <Line value={depth} />
              </p>
            )}
            <p className="text-pretty text-ink-2">
              <Line value={basisLine(t, EXAMPLE.basis)} />
            </p>
          </div>
        </div>
        <p className="mt-4 text-small text-ink-2">
          <T k="map.example.note" />
        </p>
      </article>
    </section>
  )
}
