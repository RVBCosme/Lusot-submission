import { ChevronLeftIcon } from 'lucide-react'
import { LEVELS, OFF_GAUGE, type Level } from '../copy/levels'
import { Line, T, useT } from '../i18n'
import { FILL } from './depthFill'

// The room a row takes. The seven gauge levels stand one on another and share an edge, so they read as one pole; each
// of the two added levels stands apart from them, above and below.
const LAST = LEVELS.length - 1
function gap(index: number): string {
  if (index === 0) return 'mt-2'
  if (index === LAST) return 'mb-2'
  return index === LAST - 1 ? '' : '-mt-0.5'
}

type State = 'marked' | 'filled' | 'possible' | 'empty'

// The depth gauge (MS5-Q1, direction A, "Panukat"), drawn as the logo is: an L, its rail down the left and its ground line
// along the bottom, in the outline colour. Against the rail stand MMDA's 7 gauge levels as one pole, deepest at the top,
// each with a tick to the rail and its name beside it, with the 2 added levels drawn apart and dashed, labelled as outside
// MMDA's gauge. It fills up to the reading, "no flood seen" leaves it empty, and a floor ("at least") is the reading's step
// with every deeper step drawn as water that may be there: a dashed outline and no fill, since even a faint fill would
// read as a shallow filled cell in the dark theme. It repeats the level line, so screen readers skip it, and no level is
// ever numbered.
//
// The fills can't carry the reading alone: in light, steps 1 to 4 are under 3:1 against the page, and 7 to 9 are under
// 3:1 against the outline (in dark, steps 1 to 3 and 6 to 9; styles/contrast.test.ts pins both). So every cell has an
// outline edge, and what marks the reading is more than its fill: a thicker edge on its cell, a pointer beside it and a
// bold name, all in the text colour, on the page and never on a fill. No name or mark ever sits on a fill.
export function Gauge({ level, isFloor, noFlood = false }: { level?: Level; isFloor: boolean; noFlood?: boolean }) {
  const t = useT()
  const reading = noFlood || level === undefined ? -1 : LEVELS.indexOf(level)
  const open = isFloor && reading >= 0
  // Top to bottom, so the deepest level is at the top.
  const rows = LEVELS.map((name, index) => ({ name, index })).reverse()
  return (
    <div
      aria-hidden="true"
      data-testid="gauge"
      data-open={open ? 'true' : 'false'}
      className="flex w-fit flex-col border-b-4 border-l-4 border-outline pb-1 pl-2"
    >
      {rows.map(({ name, index }) => {
        const off = OFF_GAUGE.includes(name)
        const state: State = index === reading ? 'marked' : index < reading ? 'filled' : open ? 'possible' : 'empty'
        const opened = state === 'marked' && open
        const fill = state === 'empty' ? 'bg-surface' : state === 'possible' ? 'bg-transparent' : FILL[index]
        const edge = `${off || state === 'possible' ? 'border-dashed' : 'border-solid'} ${state === 'marked' ? 'border-4' : 'border-2'}${opened ? ' border-t-0' : ''}`
        const label =
          state === 'marked' ? 'font-bold text-ink' : state === 'filled' ? 'text-ink' : 'text-ink-2'
        return (
          <div key={name} data-row={name} className={`flex items-center gap-2 ${gap(index)}`}>
            <span
              data-cell={name}
              data-state={state}
              data-off-gauge={off ? 'true' : 'false'}
              data-open={opened ? 'true' : undefined}
              className={`relative h-6 w-10 shrink-0 border-outline ${edge} ${fill} before:absolute before:top-1/2 before:right-full before:h-0.5 before:w-2 before:-translate-y-1/2 before:bg-outline`}
            />
            <span className="flex size-5 shrink-0 items-center justify-center">
              {state === 'marked' && <ChevronLeftIcon data-pointer="" className="size-5 text-ink" strokeWidth={3} />}
            </span>
            <span data-label className={`text-small ${label}`}>
              <Line value={t(`result.levelName.${name}`)} />
              {off && (
                <span className="block font-normal text-ink-2">
                  <T k="gauge.outside" />
                </span>
              )}
              {opened && (
                <span className="block font-normal text-ink-2">
                  <T k="gauge.orDeeper" />
                </span>
              )}
            </span>
          </div>
        )
      })}
    </div>
  )
}
