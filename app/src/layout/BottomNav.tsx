import { CameraIcon, ClipboardCheckIcon, InfoIcon, MapIcon, MessageCircleQuestionIcon, type LucideIcon } from 'lucide-react'
import { T } from '../i18n'
import type { StringKey } from '../i18n/en'
import { routeHash, type Route } from '../router'

type Section = 'map' | 'report' | 'tested' | 'about' | 'ask'

// Ask Lusot is the fifth (spec §4.1; Ask's C723). Lucide's icons are hidden from screen readers, so each link's name
// is its text label.
const ITEMS: { section: Section; label: StringKey; Icon: LucideIcon }[] = [
  { section: 'map', label: 'nav.map', Icon: MapIcon },
  { section: 'report', label: 'nav.report', Icon: CameraIcon },
  { section: 'tested', label: 'nav.tested', Icon: ClipboardCheckIcon },
  { section: 'about', label: 'nav.about', Icon: InfoIcon },
  { section: 'ask', label: 'nav.ask', Icon: MessageCircleQuestionIcon },
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
  ask: 'ask',
}

// The current section is underlined and in the action colour, not bolded, so its label keeps its width and doesn't wrap.
// Each label stays on one line: at 360 px, Taglish's "Mag-report" broke at its hyphen (Rene's phone test, Nov 1). A
// label that doesn't fit widens its link, and the row wraps instead (see the <ul>). From lg each link is an icon beside its
// label, with the same underline for the current section.
const LINK =
  'flex min-h-tap flex-col items-center justify-center gap-0.5 whitespace-nowrap px-1 py-1 text-small active:opacity-70 aria-[current=page]:underline aria-[current=page]:decoration-2 aria-[current=page]:underline-offset-4 lg:flex-row lg:gap-2 lg:px-3 lg:text-body'
// The bar of tabs sits on the page, where the current section takes the action colour. In the top bar (`onBrand`) it sits on
// the brand navy, so the links are the brand's mist and the current one its pale, with a water-blue underline, which each
// hold the contrast the navy needs (styles/contrast.test.ts); the underline still tells the current section without colour.
const ON_PAGE = 'aria-[current=page]:text-action'
const ON_BRAND = 'text-brand-mist aria-[current=page]:text-brand-pale aria-[current=page]:decoration-brand-water'

// The nav, which Layout.tsx draws twice: the phone's bar of tabs along the bottom, and from lg the same links in the top
// bar. Each copy is not displayed at the other width (`display: none`, out of the tab order and the accessibility tree), so
// a screen reader finds one navigation landmark at any width and the keyboard follows the order the eye sees. The caller's
// className says which copy this is and where it goes.
export function BottomNav({
  route,
  reportDisabled,
  className,
  onBrand = false,
}: {
  route: Route
  reportDisabled: boolean
  className: string
  onBrand?: boolean
}) {
  const current = SECTION[route.name]
  const link = `${LINK} ${onBrand ? ON_BRAND : ON_PAGE}`
  return (
    <nav className={className}>
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
            <li key={section} className="flex-1 lg:flex-none">
              {section === 'report' && reportDisabled ? (
                // A link with no address can't be followed (WAI-ARIA's disabled link). The banner says why.
                <a role="link" aria-disabled="true" className={`${link} cursor-not-allowed opacity-50`}>
                  {content}
                </a>
              ) : (
                <a
                  href={routeHash({ name: section })}
                  aria-current={section === current ? 'page' : undefined}
                  className={link}
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
