import { Line, T, useLanguage, useT } from '../i18n'
import type { Pin } from '../lib/api'
import { isOwn, newestFirst } from '../map/pins'
import { pinLines } from '../map/pinWording'
import { routeHash } from '../router'
import { Badge } from './Badge'

// A row is a whole 48 px target. Pressing it fills it with ink and turns every line to the page's colour (S5-R6).
const ROW =
  'group flex min-h-tap w-full flex-col gap-1 rounded-control border border-outline p-3 text-left ' +
  'active:border-ink active:bg-ink active:text-surface'

// The same pins as the map, newest first: the keyboard and screen-reader route to them (C612). A row says the level line
// and the age, as a marker does, and is a link to the pin's own screen. The person's own pin, which the API doesn't
// hold yet, opens their own result in place instead, since its id may never go in a route (C620).
export function PinList({ pins, now, onOpenOwn }: { pins: readonly Pin[]; now: Date; onOpenOwn(): void }) {
  const t = useT()
  const { lang } = useLanguage()
  return (
    <ul aria-label={t('map.listLabel').text} className="space-y-2">
      {newestFirst(pins).map((pin) => {
        const { level, when } = pinLines(t, lang, pin, now)
        const own = isOwn(pin)
        const content = (
          <>
            {(own || pin.mode === 'demo') && (
              <span>
                <Badge>
                  <T k={own ? 'map.own' : 'badge.demo'} />
                </Badge>
              </span>
            )}
            <span data-line className="block text-balance font-bold">
              <Line value={level} />
            </span>
            {when !== undefined && (
              <span data-line className="block text-small text-ink-2 group-active:text-surface">
                <Line value={when} />
              </span>
            )}
          </>
        )
        return (
          <li key={pin.id}>
            {own ? (
              <button type="button" onClick={onOpenOwn} className={ROW}>
                {content}
              </button>
            ) : (
              <a href={routeHash({ name: 'pin', id: pin.id })} className={ROW}>
                {content}
              </a>
            )}
          </li>
        )
      })}
    </ul>
  )
}
