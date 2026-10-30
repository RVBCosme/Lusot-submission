import { EN, type Entry, type StringKey } from './en'

// The Taglish string table: every key of en.ts, each with its own review mark (C609). The drafts are Claude's
// and wait for Rene's copy review (M20). A screen-line key shows its English line until its Taglish is
// reviewed (C619).
export const FIL: Record<StringKey, Entry> = {
  'nav.map': { text: 'Mapa', reviewed: false },
  'nav.report': { text: 'Mag-report', reviewed: false },
  'nav.tested': { text: 'Tested', reviewed: false },
  'nav.about': { text: 'Tungkol', reviewed: false },
  // The two locked lines are the English entries themselves, so the tables can't drift apart (C619).
  'layout.screenLine': EN['layout.screenLine'],
  'about.notAffiliated': EN['about.notAffiliated'],
  'lang.en': { text: 'English', reviewed: false },
  'lang.fil': { text: 'Taglish', reviewed: false },
  'lang.switch': { text: 'Wika', reviewed: false },
  'layout.noApi': { text: 'Walang API address ang build na ito, kaya hindi ito makakapag-upload.', reviewed: false },
  'layout.noApiDetail': {
    text: 'Hindi naka-set ang VITE_API_URL. Ilagay ito sa app/.env.local, saka i-build ulit.',
    reviewed: false,
  },
  'layout.errorFallback': { text: 'Hindi maipakita ang screen na ito. Pumili ng ibang screen sa bar sa ibaba.', reviewed: false },
  // A privacy key: it shows its English line until its Taglish is reviewed (C619).
  'privacy.title': { text: 'Privacy policy', reviewed: false },
  'licences.title': { text: 'Mga open-source na lisensya', reviewed: false },
  'pin.title': { text: 'Detalye ng pin', reviewed: false },
  // The draft of D19's line from the Oct 28 log.
  'refusal.d19': {
    text: 'Hindi ko masabi mula sa photo na ito. Kunan ulit mula sa tuyong lugar, kita ang gulong ng nakaparadang sasakyan o isang taong nakatayo. Huwag lumusong sa baha o pumunta sa kalsada.',
    reviewed: false,
  },
}
