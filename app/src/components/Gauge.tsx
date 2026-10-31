import { ChevronLeftIcon } from 'lucide-react'
import { LEVELS, OFF_GAUGE, type Level } from '../copy/levels'
import { Line, T, useT } from '../i18n'

// One class per depth step, written out in full because Tailwind finds a class by reading this file. The ramp is one
// hue that grows stronger with depth (C624), so a cell's fill is its own level's step.
const FILL = [
  'bg-depth-1',
  'bg-depth-2',
  'bg-depth-3',
  'bg-depth-4',
  'bg-depth-5',
  'bg-depth-6',
  'bg-depth-7',
  'bg-depth-8',
  'bg-depth-9',
] as const
// A floor's cell fades out at the top, as water that could be deeper.
const FADE = [
  'from-depth-1',
  'from-depth-2',
  'from-depth-3',
  'from-depth-4',
  'from-depth-5',
  'from-depth-6',
  'from-depth-7',
  'from-depth-8',
  'from-depth-9',
] as const

// The depth gauge (MS5-Q1, direction A, "Panukat"): MMDA's 7 gauge levels as a vertical scale, deepest at the top,
// with the 2 added levels drawn apart and dashed, labelled as outside MMDA's gauge. It fills up to the reading, a
// floor is open at the top, and "no flood seen" leaves it empty. It repeats the level line, so screen readers skip it.
//
// The fills can't carry the reading alone: in light, steps 1 to 4 are under 3:1 against the page, and 7 to 9 are under
// 3:1 against the outline (in dark, steps 1 to 3 and 6 to 9; styles/contrast.test.ts pins both). So every cell has an
// outline edge, and what marks the reading sits on the page, beside the cells: a thicker edge on its cell, a pointer
// and a bold label, all in the text colour. No name or mark ever sits on a fill.
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
      className="flex w-fit flex-col gap-1"
    >
      {rows.map(({ name, index }) => {
        const off = OFF_GAUGE.includes(name)
        const marked = index === reading
        const filled = index < reading
        const state = marked ? 'marked' : filled ? 'filled' : 'empty'
        const opened = marked && open
        const fill = opened
          ? `bg-linear-to-t ${FADE[index]} to-transparent border-t-0`
          : state === 'empty'
            ? 'bg-surface'
            : FILL[index]
        // The two added levels sit apart from MMDA's seven.
        const apart = index === 0 ? 'mt-2' : index === LEVELS.length - 1 ? 'mb-2' : ''
        const edge = `${off ? 'border-dashed' : 'border-solid'} ${marked ? 'border-4' : 'border-2'}`
        const label = marked ? 'font-bold text-ink' : filled ? 'text-ink' : 'text-ink-2'
        return (
          <div key={name} data-row={name} className={`flex items-center gap-2 ${apart}`}>
            <span
              data-cell={name}
              data-state={state}
              data-off-gauge={off ? 'true' : 'false'}
              data-open={opened ? 'true' : undefined}
              className={`h-5 w-12 shrink-0 border-outline ${edge} ${fill}`}
            />
            <span className="flex size-5 shrink-0 items-center justify-center">
              {marked && <ChevronLeftIcon data-pointer="" className="size-5 text-ink" strokeWidth={3} />}
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
