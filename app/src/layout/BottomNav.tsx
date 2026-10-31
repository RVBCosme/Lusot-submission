import { CameraIcon, ClipboardCheckIcon, InfoIcon, MapIcon, type LucideIcon } from 'lucide-react'
import { T } from '../i18n'
import type { StringKey } from '../i18n/en'
import { routeHash, type Route } from '../router'

type Section = 'map' | 'report' | 'tested' | 'about'

// MS6 adds Ask as the fifth (spec §4.1). Lucide's icons are hidden from screen readers, so each link's name is
// its text label.
const ITEMS: { section: Section; label: StringKey; Icon: LucideIcon }[] = [
  { section: 'map', label: 'nav.map', Icon: MapIcon },
  { section: 'report', label: 'nav.report', Icon: CameraIcon },
  { section: 'tested', label: 'nav.tested', Icon: ClipboardCheckIcon },
  { section: 'about', label: 'nav.about', Icon: InfoIcon },
]

// A pin sits on the map, and the privacy policy and the licences are reached from About.
const SECTION: Record<Route['name'], Section> = {
  map: 'map',
  pin: 'map',
  report: 'report',
  tested: 'tested',
  about: 'about',
  privacy: 'about',
  licences: 'about',
}

// The current section is underlined and in the action colour, not bolded, so its label keeps its width and doesn't wrap.
const LINK =
  'flex min-h-tap flex-col items-center justify-center gap-0.5 px-1 py-1 text-small active:opacity-70 aria-[current=page]:text-action aria-[current=page]:underline aria-[current=page]:decoration-2 aria-[current=page]:underline-offset-4'

export function BottomNav({ route, reportDisabled }: { route: Route; reportDisabled: boolean }) {
  const current = SECTION[route.name]
  return (
    <nav>
      {/* At large text sizes the links wrap to a second row rather than run off the screen. */}
      <ul className="flex flex-wrap">
        {ITEMS.map(({ section, label, Icon }) => {
          const content = (
            <>
              <Icon />
              <T k={label} />
            </>
          )
          return (
            <li key={section} className="flex-1">
              {section === 'report' && reportDisabled ? (
                // A link with no address can't be followed (WAI-ARIA's disabled link). The banner says why.
                <a role="link" aria-disabled="true" className={`${LINK} cursor-not-allowed opacity-50`}>
                  {content}
                </a>
              ) : (
                <a
                  href={routeHash({ name: section })}
                  aria-current={section === current ? 'page' : undefined}
                  className={LINK}
                >
                  {content}
                </a>
              )}
            </li>
          )
        })}
      </ul>
    </nav>
  )
}
