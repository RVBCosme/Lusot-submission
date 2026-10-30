import { useId, useRef, type ReactNode } from 'react'
import { SampleList } from '../components/SampleList'
import { Line, T, useLanguage, useT, type Text } from '../i18n'
import type { StringKey } from '../i18n/en'
import { useHeadingFocus } from '../lib/focus'
import { type ConfigurationName, rateText, REPORT_URL, SUMMARY, type Summary } from '../lib/summary'
import { formatDate } from '../lib/time'

const LINK = 'inline-flex min-h-tap items-center text-action underline underline-offset-4'

// The shipped configuration's figures, in the order the rules report them first (rules §7): the three headline rates,
// then M1's level agreement when the summary has it.
const FIGURES = [
  { name: 'underestimation', label: 'tested.figure.underestimation' },
  { name: 'passability', label: 'tested.figure.passability' },
  { name: 'coverage', label: 'tested.figure.coverage' },
  { name: 'exact', label: 'tested.figure.exact' },
  { name: 'within_one', label: 'tested.figure.withinOne' },
] as const

const SHIPPED: Record<ConfigurationName, StringKey> = {
  landmark: 'tested.shipped.landmark',
  geometry: 'tested.shipped.geometry',
}

const LIMITS: StringKey[] = ['tested.limits.night', 'tested.limits.rain', 'tested.limits.blur', 'tested.limits.faceBlur']

type Figure = { label: StringKey; value: Text }

function Section({ title, children }: { title: StringKey; children: ReactNode }) {
  const id = useId()
  return (
    <section aria-labelledby={id} className="mt-8">
      <h2 id={id} className="text-heading font-bold">
        <T k={title} />
      </h2>
      {children}
    </section>
  )
}

// Each figure as a reading on a scale: what it counts, then k of n with its share, and "indicative" beside every one
// (C616, W19). The rule down the left is the gauge's own edge.
function FigureList({ figures }: { figures: Figure[] }) {
  return (
    <dl className="mt-4 space-y-4">
      {figures.map(({ label, value }) => (
        <div key={label} className="border-l-4 border-outline pl-3">
          <dt className="text-pretty">
            <T k={label} />
          </dt>
          <dd className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1">
            <span className="text-title font-bold tabular-nums">
              <Line value={value} />
            </span>
            <span className="rounded-control border border-outline px-2 text-small text-ink-2">
              <T k="tested.indicative" />
            </span>
          </dd>
        </div>
      ))}
    </dl>
  )
}

// The sealed run's figures, from MS6's summary only: never a number typed here (W17).
function Figures({ summary, reportUrl }: { summary: Summary; reportUrl: string | undefined }) {
  const t = useT()
  const { lang } = useLanguage()
  const date = formatDate(lang, summary.date) ?? summary.date
  const shipped = summary.shipped
  const config = shipped === null ? undefined : summary.configurations?.[shipped]
  const figures: Figure[] = []
  for (const { name, label } of FIGURES) {
    const rate = config?.[name]
    if (rate !== undefined) figures.push({ label, value: rateText(t, rate) })
  }
  // Set B's figures, whenever Set B ran. The median's n is the wheels measured.
  const setB = summary.set_b
  const wheels: Figure[] = []
  if (setB !== null && setB.median_error_in !== null && setB.measured !== undefined) {
    wheels.push({
      label: 'tested.setB.median',
      value: t('tested.setB.medianValue', { inches: setB.median_error_in, n: setB.measured.k }),
    })
  }
  if (setB?.measured !== undefined) wheels.push({ label: 'tested.setB.measured', value: rateText(t, setB.measured) })

  return (
    <>
      <p className="mt-2">
        <Line value={t(summary.rerun ? 'tested.results.rerunFrom' : 'tested.results.from', { date })} />
      </p>
      <p className="mt-2">
        <T k="tested.results.intro" />
      </p>
      {shipped !== null && figures.length > 0 && (
        <>
          <p className="mt-4">
            <T k={SHIPPED[shipped]} />
          </p>
          <FigureList figures={figures} />
        </>
      )}
      {summary.inches_shown !== null && (
        <p className="mt-4">
          <T k={summary.inches_shown ? 'tested.inches.shown' : 'tested.inches.notShown'} />
        </p>
      )}
      {wheels.length > 0 && (
        <>
          <h3 className="mt-6 font-bold">
            <T k="tested.setB.title" />
          </h3>
          <FigureList figures={wheels} />
        </>
      )}
      {reportUrl !== undefined && (
        <p className="mt-4">
          {/* A new tab, so a sample's result on this page isn't lost. */}
          <a href={reportUrl} target="_blank" rel="noopener noreferrer" className={LINK}>
            <T k="tested.reportLink" />
          </a>
        </p>
      )}
    </>
  )
}

// The Tested page (C616, C617): the sealed run's figures once there are some, how Lusot is tested, its known limits and
// the samples. The figures come from MS6's summary at build time; `summary` and `reportUrl` are for tests.
export function TestedScreen({
  apiUrl,
  summary = SUMMARY,
  reportUrl = REPORT_URL,
}: {
  apiUrl: string
  summary?: Summary | null
  reportUrl?: string
}) {
  const heading = useRef<HTMLHeadingElement>(null)
  useHeadingFocus(heading, undefined)
  return (
    <div className="max-w-prose">
      <h1 ref={heading} className="text-title font-bold outline-none">
        <T k="nav.tested" />
      </h1>

      <Section title="tested.results.title">
        {summary === null ? (
          <p className="mt-2">
            <T k="tested.pending" />
          </p>
        ) : (
          <Figures summary={summary} reportUrl={reportUrl} />
        )}
      </Section>

      <Section title="tested.how.title">
        <p className="mt-2">
          <T k="tested.how.labels" />
        </p>
        <p className="mt-2">
          <T k="tested.how.sealed" />
        </p>
        <p className="mt-2">
          <T k="tested.how.rules" />
        </p>
        <p className="mt-2">
          <T k="tested.how.cars" />
        </p>
      </Section>

      <Section title="tested.limits.title">
        <ul className="mt-2 list-disc space-y-1 pl-5">
          {LIMITS.map((key) => (
            <li key={key}>
              <T k={key} />
            </li>
          ))}
        </ul>
      </Section>

      <Section title="tested.samples.title">
        <p className="mt-2">
          <T k="tested.samples.intro" />
        </p>
        <SampleList apiUrl={apiUrl} />
      </Section>

      <p className="mt-8 text-small text-ink-2">
        <T k="about.notAffiliated" />
      </p>
    </div>
  )
}
