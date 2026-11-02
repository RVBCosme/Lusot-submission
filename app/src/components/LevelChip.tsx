import { LEVELS, type Level } from '../copy/levels'
import { Line, T, useT } from '../i18n'
import { FILL } from './depthFill'

// The level of a sample's reading, as a small chip beside its Sample badge: the level's step of the depth ramp as a swatch
// with its own edge, and the level's name in the words the gauge and the level line use, with "or deeper" for a floor. It
// is a glance at what the card says in full a little below, so screen readers skip it, and it never carries a number. A
// name sits on the page, beside the swatch and never on it, as in the gauge (C624).
export function LevelChip({ level, isFloor }: { level: Level; isFloor: boolean }) {
  const t = useT()
  return (
    <span
      data-chip="level"
      aria-hidden="true"
      className="inline-flex min-h-8 items-center gap-2 rounded-control border border-outline px-2 text-small font-bold"
    >
      <span data-swatch className={`size-3 shrink-0 border-2 border-outline ${FILL[LEVELS.indexOf(level)]}`} />
      <span>
        <Line value={t(`result.levelName.${level}`)} />
        {isFloor && (
          <>
            {' '}
            <T k="gauge.orDeeper" />
          </>
        )}
      </span>
    </span>
  )
}
