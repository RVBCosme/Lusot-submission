import { useMemo } from 'react'
import { Badge } from '../components/Badge'
import { Line, T, useT } from '../i18n'
import type { AskAnswer } from '../lib/api'
import { routeHash } from '../router'
import { type AnswerLine, maskBannedWords, renderAnswer } from './render'

// A card is a whole 48 px target that opens its pin, as a row of the map's list does (PinList).
const CARD =
  'group block min-h-tap rounded-control border border-outline p-3 active:border-ink active:bg-ink active:text-surface'
const SUGGESTION =
  'inline-flex min-h-tap items-center rounded-control border border-outline px-3 text-left active:bg-ink active:text-surface'

type Group = { reportId?: string; lines: AnswerLine[] }

// The lines in order, each card's lines kept together.
function groups(lines: AnswerLine[]): Group[] {
  const out: Group[] = []
  for (const line of lines) {
    const last = out.at(-1)
    if (line.reportId !== undefined && last?.reportId === line.reportId) last.lines.push(line)
    else out.push({ reportId: line.reportId, lines: [line] })
  }
  return out
}

// One answer, worded by render.ts (Ask's spec §4.4). A spoken question's transcript shows above it, masked so no banned
// word reaches the screen (AskL-Q11); a card links to its pin, where the photo and its overlay are; a suggestion fills
// the box with a question about that spot; and a place found through Nominatim carries OpenStreetMap's attribution.
export function AnswerView({
  answer,
  transcript,
  onSuggestion,
}: {
  answer: AskAnswer
  transcript?: string
  onSuggestion(question: string): void
}) {
  const t = useT()
  const lines = useMemo(() => renderAnswer(answer, t, new Date()), [answer, t])
  return (
    <section aria-label={t('ask.ui.answer').text} className="mt-6 space-y-3">
      {transcript !== undefined && (
        <div>
          <p className="text-small text-ink-2">
            <T k="ask.ui.youAsked" />
          </p>
          <p className="font-bold">{maskBannedWords(transcript)}</p>
        </div>
      )}
      {groups(lines).map((group, i) =>
        group.reportId === undefined ? (
          group.lines.map((line, j) => <Loose key={`${i}.${j}`} line={line} onSuggestion={onSuggestion} />)
        ) : (
          <a key={group.reportId} href={routeHash({ name: 'pin', id: group.reportId })} className={CARD}>
            {group.lines[0].used === true && (
              <span className="mb-1 block">
                <Badge>
                  <T k="ask.ui.used" />
                </Badge>
              </span>
            )}
            {group.lines.map((line, j) => (
              <span key={j} data-line className={cardLineClass(line)}>
                <Line value={line.text} />
              </span>
            ))}
            <span className="mt-1 block text-small text-action underline underline-offset-4 group-active:text-surface">
              <T k="ask.ui.openPin" />
            </span>
          </a>
        ),
      )}
      {answer.place?.source === 'nominatim' && (
        <p className="text-small text-ink-2">
          <T k="ask.ui.attribution" />
        </p>
      )}
    </section>
  )
}

// A line outside a card: the crossing line set apart, the summary, a note, or a suggestion to tap.
function Loose({ line, onSuggestion }: { line: AnswerLine; onSuggestion(question: string): void }) {
  if (line.part === 'suggestion') {
    return (
      <button type="button" onClick={() => onSuggestion(line.text.text)} className={SUGGESTION}>
        <Line value={line.text} />
      </button>
    )
  }
  const style =
    line.part === 'crossing'
      ? 'border-l-4 border-outline pl-3 font-bold'
      : line.part === 'summary'
        ? 'text-heading font-bold text-balance'
        : 'text-pretty'
  return (
    <p className={style}>
      <Line value={line.text} />
    </p>
  )
}

function cardLineClass(line: AnswerLine): string {
  if (line.key === 'level') return 'block text-balance font-bold'
  if (line.key === 'ask.answer.crossing') return 'mt-1 block border-l-4 border-outline pl-2 font-bold'
  if (line.key === 'credit' || line.key === 'sample.photoFrom' || line.key === 'ask.answer.demo') {
    return 'block text-small text-ink-2 group-active:text-surface'
  }
  return 'block'
}
