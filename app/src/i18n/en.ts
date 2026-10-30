// The English string table (C609). Every line carries Rene's review mark (M20): the lines he has already fixed
// start reviewed, and every new line starts unreviewed until his copy review. `npm run copy:review -w app`
// prints the lines still waiting.
export type Entry = { text: string; reviewed: boolean }

export const EN = {
  'nav.map': { text: 'Map', reviewed: false },
  'nav.report': { text: 'Report', reviewed: false },
  'nav.tested': { text: 'Tested', reviewed: false },
  'nav.about': { text: 'About', reviewed: false },
  // CLAUDE.md's exact line, on every screen. It stays in English in both languages (C619).
  'layout.screenLine': {
    text: 'Lusot estimates depth at one spot. It is not advice to cross. Follow MMDA and local advisories.',
    reviewed: true,
  },
  // CLAUDE.md's line. It stays in English in both languages (C619).
  'about.notAffiliated': { text: 'Not affiliated with MMDA.', reviewed: true },
  'lang.en': { text: 'English', reviewed: false },
  'lang.fil': { text: 'Taglish', reviewed: false },
  // The header's language switch, as a group of two buttons.
  'lang.switch': { text: 'Language', reviewed: false },
  // MS1's banner for a build made without VITE_API_URL (R31).
  'layout.noApi': { text: 'This build has no API address, so it cannot upload.', reviewed: false },
  'layout.noApiDetail': { text: 'VITE_API_URL is not set. Put it in app/.env.local, then build again.', reviewed: false },
  // The fallback where a screen that crashed would have been (S5-R5). The nav and the screen line stay.
  'layout.errorFallback': { text: 'This screen could not be shown. Choose another screen from the bar below.', reviewed: false },
  // Screen headings without a nav label.
  'privacy.title': { text: 'Privacy policy', reviewed: false },
  'licences.title': { text: 'Open-source licences', reviewed: false },
  'pin.title': { text: 'Pin detail', reviewed: false },
  // D19's refusal, which Rene confirmed in English.
  'refusal.d19': {
    text: "I can't tell from this photo. Retake it from a dry spot with a parked car's wheel or a person standing still in view. Don't step into the water or the road.",
    reviewed: true,
  },
} satisfies Record<string, Entry>

export type StringKey = keyof typeof EN
