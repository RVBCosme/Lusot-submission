import {
  CircleQuestionMarkIcon,
  CircleXIcon,
  DropletOffIcon,
  HourglassIcon,
  PauseIcon,
  type LucideIcon,
} from 'lucide-react'
import { useState, type ReactNode } from 'react'
import { basisLine, classLine, inchesLine, landmarkLine, levelFromLine, levelLine, reasonLine } from '../copy/wording'
import { Line, T, useLanguage, useT, type Text } from '../i18n'
import type { StringKey } from '../i18n/en'
import type { Pin, ReportResult, Sample } from '../lib/api'
import { OFFICIAL_SITES } from '../lib/officialSites'
import { routeHash } from '../router'
import { ageText, formatDate, photoDateLine } from '../lib/time'
import { Badge } from './Badge'
import { Details } from './Details'
import { Gauge } from './Gauge'

export type ResultCardProps = {
  // A report's answer, or a published pin. A pin is always a level result (MS4's C506).
  result: ReportResult | Pin
  // 'sample' is a card on the Tested page: it has the sample frame and its paused line links to the map only.
  source: 'own' | 'pin' | 'sample'
  sample?: Sample
  photoUrl?: string
  // The phone's own fix, for the accuracy line when the API sends none (N1).
  fixAccuracyM?: number
  // The app's own state when the poll ran out (C601), never an outcome the server reported.
  noResultYet?: boolean
  // A sample run answered from its saved result while analysis is paused (amendment 10, C617).
  savedAt?: string
  onCheckAgain?(): void
  // "Try again" on a failed card: a new photo, never the same one resent (spec §4.2).
  onNewPhoto?(): void
  // Passed on when a photo link fails to load, so the screen can ask the API for a new one.
  onPhotoExpired?(): void
  now?: Date
}

// The six things a card says. They stay apart (CLAUDE.md): "processing failed", "no flood seen" and "can't tell" each
// have their own words, their own icon and their own edge, and a level has the gauge. A pause is a seventh state that
// reads as a pause and never as a failure (C638).
type Outcome = 'level' | 'noFlood' | 'cantTell' | 'failed' | 'paused' | 'noResult'

const OUTCOME_ATTRIBUTE: Record<Outcome, string> = {
  level: 'level',
  noFlood: 'no-flood',
  cantTell: 'cant-tell',
  failed: 'failed',
  paused: 'paused',
  noResult: 'no-result',
}

const EDGE: Record<Outcome, string> = {
  level: 'border-2 border-solid',
  noFlood: 'border-2 border-solid',
  cantTell: 'border-2 border-dashed',
  failed: 'border-4 border-double',
  paused: 'border-2 border-dotted',
  noResult: 'border-2 border-dotted',
}

const ICON: Partial<Record<Outcome, { name: string; Icon: LucideIcon }>> = {
  noFlood: { name: 'no-flood', Icon: DropletOffIcon },
  cantTell: { name: 'cant-tell', Icon: CircleQuestionMarkIcon },
  failed: { name: 'failed', Icon: CircleXIcon },
  paused: { name: 'paused', Icon: PauseIcon },
  noResult: { name: 'no-result', Icon: HourglassIcon },
}

const LINK = 'inline-flex min-h-tap items-center text-action underline underline-offset-4'
const BUTTON =
  'mt-3 inline-flex min-h-tap items-center rounded-control bg-action px-4 font-bold text-on-action ' +
  'active:bg-ink active:text-surface'

function outcomeOf(result: ReportResult | Pin, noResultYet: boolean): Outcome {
  if (noResultYet) return 'noResult'
  if (!('status' in result)) return 'level'
  switch (result.status) {
    case 'done':
      if (result.noFloodSeen === true) return 'noFlood'
      // A finished report with neither a level nor "no flood seen" can't be read, so it is shown as a failure.
      return result.level === undefined ? 'failed' : 'level'
    case 'refused':
      return 'cantTell'
    case 'failed':
      return result.refusalReason === 'model_calls_paused' ? 'paused' : 'failed'
    default:
      // pending or processing: no final status, so no made-up outcome.
      return 'noResult'
  }
}

// The outcome's icon, hidden from screen readers: the words carry the meaning, and the icon and edge tell the
// outcomes apart at a glance without relying on colour.
const usable = (metres: number | null | undefined): metres is number =>
  typeof metres === 'number' && Number.isFinite(metres) && metres > 0

function Mark({ outcome }: { outcome: Outcome }) {
  const mark = ICON[outcome]
  if (mark === undefined) return null
  return (
    <span data-icon={mark.name} className="mt-1 shrink-0">
      <mark.Icon aria-hidden="true" className="size-6" />
    </span>
  )
}

// A line, or nothing, in the card's small ink-2 text.
function Note({ value, className = '' }: { value: Text | undefined; className?: string }) {
  if (value === undefined) return null
  return (
    <p className={`text-pretty ${className}`}>
      <Line value={value} />
    </p>
  )
}

type PausedLink = 'map' | 'tested'
const PAUSED_LINKS: Record<PausedLink, { href: string; label: StringKey }> = {
  map: { href: routeHash({ name: 'map' }), label: 'nav.map' },
  tested: { href: routeHash({ name: 'tested' }), label: 'nav.tested' },
}

// The paused line, with links to the map and the Tested page, leaving out the one it is on (C638). A paused screen has
// no reason line and no "Try again", since a new photo would pause the same way. The card shows it for a report that
// ended paused and for a saved sample; a screen with no result, such as an upload's 503, uses it by itself and adds
// its own note ("Nothing was uploaded.") as children.
export function PausedNotice({ links, children }: { links: readonly PausedLink[]; children?: ReactNode }) {
  return (
    <div>
      <div role="status" className="flex items-start gap-3">
        <Mark outcome="paused" />
        <p className="text-balance text-heading font-bold">
          <T k="result.paused" />
        </p>
      </div>
      {children}
      <ul className="mt-1 flex flex-wrap gap-x-6">
        {links.map((link) => (
          <li key={link}>
            <a href={PAUSED_LINKS[link].href} className={LINK}>
              <T k={PAUSED_LINKS[link].label} />
            </a>
          </li>
        ))}
      </ul>
    </div>
  )
}

export function ResultCard({
  result,
  source,
  sample,
  photoUrl,
  fixAccuracyM,
  noResultYet = false,
  savedAt,
  onCheckAgain,
  onNewPhoto,
  onPhotoExpired,
  now,
}: ResultCardProps) {
  const t = useT()
  const { lang } = useLanguage()
  const outcome = outcomeOf(result, noResultYet)
  const report = 'status' in result ? result : undefined
  const isSample = source === 'sample'
  // A sample and a demo pin are credited photos with their own date and place, never a live report (C617, C618).
  const isExample = isSample || result.mode === 'demo'
  // The age is read once, when the card first shows: a screen that wants it fresh passes `now`.
  const [opened] = useState(() => new Date())
  const clock = now ?? opened
  const photo = photoUrl ?? report?.photoUrl ?? sample?.photoUrl
  const saved = savedAt === undefined ? undefined : formatDate(lang, savedAt)

  // The level and what goes with it.
  const level = result.level
  const landmark = result.landmark === undefined ? undefined : landmarkLine(t, result.landmark)
  // A saved sample answer carries no basis, inches or readings (amendment 10), and the card doesn't rely on the API
  // client having dropped them: it leaves them out whatever it is handed.
  const live = savedAt === undefined
  const hasInches = live && Number.isFinite(result.depthInMin) && Number.isFinite(result.depthInMax)
  const inches = hasInches ? inchesLine(t, result.depthInMin as number, result.depthInMax as number) : undefined
  const count = result.basis
  const basis = live && count !== undefined && count.vehicles + count.people > 0 ? basisLine(t, count) : undefined

  // Your own report and a live pin: how long ago, and how near. The API's accuracy wins over the phone's own fix.
  const capturedAt = result.capturedAt
  const taken =
    capturedAt !== undefined && Number.isFinite(Date.parse(capturedAt))
      ? t('result.photoTaken', { age: ageText(t, capturedAt, clock).text })
      : undefined
  const accuracyM = usable(result.gpsAccuracyM) ? result.gpsAccuracyM : usable(fixAccuracyM) ? fixAccuracyM : undefined
  const accuracy = accuracyM === undefined ? undefined : t('result.accuracy', { m: Math.ceil(accuracyM) })
  const whenAndWhere =
    taken === undefined && accuracy === undefined
      ? undefined
      : {
          text: [taken?.text, accuracy?.text].filter((part) => part !== undefined).join(' '),
          lang: (taken ?? accuracy)?.lang ?? lang,
        }

  // A sample or demo pin: the photo's own date, place and event.
  const credit = sample?.credit ?? result.credit
  const photoFrom = photoDateLine(t, lang, {
    date: sample === undefined ? (result.mode === 'demo' ? capturedAt : undefined) : sample.date,
    place: sample?.place ?? result.place,
    event: sample?.event ?? result.event,
  })

  const showsReading = outcome === 'level' || outcome === 'noFlood' || outcome === 'cantTell'
  const shownPrivate = result.mode === 'private' && showsReading
  const pausedLinks: PausedLink[] = isSample ? ['map'] : ['map', 'tested']

  return (
    <article
      data-outcome={OUTCOME_ATTRIBUTE[outcome]}
      className={`rounded-control bg-surface p-4 ${EDGE[outcome]} border-outline`}
    >
      {(outcome === 'paused' || savedAt !== undefined) && (
        <div className={outcome === 'paused' ? '' : 'mb-4 border-b border-outline pb-2'}>
          <PausedNotice links={pausedLinks} />
        </div>
      )}

      {isExample && (
        <figure className="mb-4">
          <div className="mb-3">
            <Badge>
              <T k={isSample ? 'badge.sample' : 'badge.demo'} />
            </Badge>
          </div>
          {photo !== undefined && (
            <img
              src={photo}
              alt={t('sample.photoAlt').text}
              lang={t('sample.photoAlt').lang}
              onError={() => onPhotoExpired?.()}
              className="w-full rounded-control border border-outline"
            />
          )}
          <figcaption className="mt-2 text-small text-ink-2">
            <Note value={photoFrom} />
            {credit !== undefined && <Note value={{ text: credit, lang: 'en' }} className="mt-1" />}
            <p className="mt-1">
              <T k="sample.edited" />
            </p>
          </figcaption>
        </figure>
      )}

      {outcome === 'level' && level !== undefined && (
        <>
          <div role="status">
            {saved !== undefined && (
              <p className="text-small font-bold">
                <Line value={t('sample.savedFrom', { date: saved })} />
              </p>
            )}
            <p className="text-balance text-title font-bold">
              <Line value={levelLine(t, level, result.levelIsFloor === true)} />
            </p>
          </div>
          <div className="mt-4 flex flex-wrap gap-x-6 gap-y-4">
            <Gauge level={level} isFloor={result.levelIsFloor === true} />
            <div className="min-w-0 flex-1 basis-48 space-y-2">
              <Note value={landmark} />
              <Note value={live ? levelFromLine(t, report?.levelFrom) : undefined} />
              <Note value={inches} />
              <Note value={classLine(t, level)} />
              <Note value={isExample ? undefined : whenAndWhere} className="text-ink-2" />
              <Note value={basis} className="text-ink-2" />
            </div>
          </div>
        </>
      )}

      {outcome === 'noFlood' && (
        <>
          <div role="status">
            {saved !== undefined && (
              <p className="text-small font-bold">
                <Line value={t('sample.savedFrom', { date: saved })} />
              </p>
            )}
            <div className="flex items-start gap-3">
              <Mark outcome="noFlood" />
              <p className="text-balance text-title font-bold">
                <T k="result.noFlood" />
              </p>
            </div>
          </div>
          <div className="mt-4 flex flex-wrap gap-x-6 gap-y-4">
            <Gauge isFloor={false} noFlood />
            <div className="min-w-0 flex-1 basis-48">
              <Note value={isExample ? undefined : whenAndWhere} className="text-ink-2" />
            </div>
          </div>
        </>
      )}

      {outcome === 'cantTell' && (
        <div role="status">
          {saved !== undefined && (
            <p className="text-small font-bold">
              <Line value={t('sample.savedFrom', { date: saved })} />
            </p>
          )}
          <div className="flex items-start gap-3">
            <Mark outcome="cantTell" />
            <div className="min-w-0">
              {/* A sample's refusal doesn't ask a judge to retake a photo they didn't take: D19's line sits in a frame
                  (C637). Your own refusal is D19's line, then why. */}
              {isSample ? (
                <>
                  <p className="text-balance text-heading font-bold">
                    <T k="refusal.sample.cantTell" />
                  </p>
                  <Note value={reasonLine(t, report?.refusalReason ?? '')} className="mt-1" />
                  <p className="mt-3 text-small text-ink-2">
                    <T k="refusal.sample.someoneWouldSee" />
                  </p>
                  <p className="mt-1">
                    <T k="refusal.d19" />
                  </p>
                </>
              ) : (
                <>
                  <p className="font-bold">
                    <T k="refusal.d19" />
                  </p>
                  <Note value={reasonLine(t, report?.refusalReason ?? '')} className="mt-2" />
                </>
              )}
            </div>
          </div>
        </div>
      )}

      {outcome === 'failed' && (
        <>
          <div role="status" className="flex items-start gap-3">
            <Mark outcome="failed" />
            <div className="min-w-0">
              <p className="text-balance text-heading font-bold">
                <T k="result.failed" />
              </p>
              <Note value={reasonLine(t, report?.refusalReason ?? '')} className="mt-1" />
            </div>
          </div>
          {onNewPhoto !== undefined && (
            <button type="button" onClick={() => onNewPhoto()} className={BUTTON}>
              <T k="result.tryAgain" />
            </button>
          )}
        </>
      )}

      {outcome === 'noResult' && (
        <>
          <div role="status" className="flex items-start gap-3">
            <Mark outcome="noResult" />
            <p className="text-balance text-heading font-bold">
              <T k="result.noResult" />
            </p>
          </div>
          {onCheckAgain !== undefined && (
            <button type="button" onClick={() => onCheckAgain()} className={BUTTON}>
              <T k="result.checkAgain" />
            </button>
          )}
        </>
      )}

      {shownPrivate && (
        <p className="mt-4">
          <T k="result.private" />
        </p>
      )}

      {isExample && showsReading && (
        <p className="mt-4 text-small text-ink-2">
          <T k={savedAt === undefined ? 'sample.liveReading' : 'sample.savedReading'} />
        </p>
      )}

      <Details
        reasonCode={report?.refusalReason}
        photoTime={isExample ? undefined : capturedAt}
        references={outcome === 'level' && live ? report?.readings : undefined}
      />

      {/* New tab, so a result that is only in memory isn't lost when someone follows a link. */}
      <ul
        aria-label={t('about.officialTitle').text}
        lang={t('about.officialTitle').lang}
        className="mt-2 flex flex-wrap gap-x-6"
      >
        {OFFICIAL_SITES.map(({ href, label }) => (
          <li key={href}>
            <a href={href} target="_blank" rel="noopener noreferrer" className={LINK}>
              <T k={label} />
            </a>
          </li>
        ))}
      </ul>
    </article>
  )
}
