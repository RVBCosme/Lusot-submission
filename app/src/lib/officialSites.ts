import type { StringKey } from '../i18n/en'

// MMDA's and PAGASA's own sites, each checked when it was added (C633). About and every result card link to them, so
// the two lists can't drift apart.
export const OFFICIAL_SITES: readonly { href: string; label: StringKey }[] = [
  { href: 'https://mmda.gov.ph/', label: 'about.mmda' },
  { href: 'https://www.pagasa.dost.gov.ph/', label: 'about.pagasa' },
]
