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
  // D19's refusal, which Rene confirmed in English.
  'refusal.d19': {
    text: "I can't tell from this photo. Retake it from a dry spot with a parked car's wheel or a person standing still in view. Don't step into the water or the road.",
    reviewed: true,
  },
} satisfies Record<string, Entry>

export type StringKey = keyof typeof EN
