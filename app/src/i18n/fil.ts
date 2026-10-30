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
  // The wording of results (MS5 Task 4). Claude's drafts, all waiting for Rene's review (M20). MMDA's own level
  // names stay in English, as people say them. The reason lines show their English text until reviewed (C619).
  'result.levelName.below_gutter': { text: 'mas mababa sa gutter', reviewed: false },
  'result.levelName.gutter': { text: 'gutter', reviewed: false },
  'result.levelName.half_knee': { text: 'half-knee', reviewed: false },
  'result.levelName.half_tire': { text: 'half-tire', reviewed: false },
  'result.levelName.knee': { text: 'knee', reviewed: false },
  'result.levelName.tire': { text: 'tire', reviewed: false },
  'result.levelName.waist': { text: 'waist', reviewed: false },
  'result.levelName.chest': { text: 'chest', reviewed: false },
  'result.levelName.above_chest': { text: 'lampas chest', reviewed: false },
  'result.level.exact': { text: '{level} ang lalim sa spot na ito (MMDA level).', reviewed: false },
  'result.level.floor': { text: 'Hindi bababa sa {level} ang lalim sa spot na ito (MMDA level).', reviewed: false },
  'result.level.off': { text: '{level} ang lalim sa spot na ito.', reviewed: false },
  'result.level.offFloor': { text: 'Hindi bababa sa {level} ang lalim sa spot na ito.', reviewed: false },
  'result.class.patv': {
    text: 'Inililista ng MMDA ang level na ito bilang passable sa lahat ng sasakyan (PATV).',
    reviewed: false,
  },
  'result.class.nplv': {
    text: 'Inililista ng MMDA ang level na ito bilang hindi passable sa light vehicles (NPLV).',
    reviewed: false,
  },
  'result.class.npatv': {
    text: 'Inililista ng MMDA ang level na ito bilang hindi passable sa anumang sasakyan (NPATV).',
    reviewed: false,
  },
  'result.class.belowGutter': {
    text: 'Mas mababa sa gutter level ng MMDA, na inililista ng MMDA bilang passable sa lahat ng sasakyan (PATV).',
    reviewed: false,
  },
  'result.class.aboveChest': {
    text: 'Mas malalim sa chest level ng MMDA, na inililista ng MMDA bilang hindi passable sa anumang sasakyan (NPATV).',
    reviewed: false,
  },
  'result.landmark.tire_only': {
    text: 'Umaabot ang tubig sa gulong lang ng nakaparadang sasakyan, hindi sa rim.',
    reviewed: false,
  },
  'result.landmark.rim_quarter': {
    text: 'Umaabot ang tubig sa isang kapat ng taas ng rim ng gulong ng nakaparadang sasakyan.',
    reviewed: false,
  },
  'result.landmark.hub': {
    text: 'Umaabot ang tubig sa hub, mga kalahati ng taas ng gulong ng nakaparadang sasakyan.',
    reviewed: false,
  },
  'result.landmark.rim_three_quarters': {
    text: 'Umaabot ang tubig sa tatlong kapat ng taas ng rim ng gulong ng nakaparadang sasakyan.',
    reviewed: false,
  },
  'result.landmark.rim_top': {
    text: 'Umaabot ang tubig sa tuktok ng rim ng gulong ng nakaparadang sasakyan.',
    reviewed: false,
  },
  'result.landmark.wheel_covered': {
    text: 'Natatakpan ng tubig ang buong gulong ng nakaparadang sasakyan.',
    reviewed: false,
  },
  'result.landmark.mid_door': {
    text: 'Umaabot ang tubig sa gitna ng pinto ng nakaparadang sasakyan.',
    reviewed: false,
  },
  'result.landmark.window': {
    text: 'Umaabot ang tubig sa mga bintana ng nakaparadang sasakyan.',
    reviewed: false,
  },
  'result.landmark.ankle': { text: 'Umaabot ang tubig sa bukong-bukong ng isang adult sa photo.', reviewed: false },
  'result.landmark.mid_shin': {
    text: 'Umaabot ang tubig sa gitna ng ibabang binti ng isang adult sa photo.',
    reviewed: false,
  },
  'result.landmark.knee': { text: 'Umaabot ang tubig sa tuhod ng isang adult sa photo.', reviewed: false },
  'result.landmark.mid_thigh': { text: 'Umaabot ang tubig sa gitna ng hita ng isang adult sa photo.', reviewed: false },
  'result.landmark.waist': { text: 'Umaabot ang tubig sa baywang ng isang adult sa photo.', reviewed: false },
  'result.landmark.chest': { text: 'Umaabot ang tubig sa dibdib ng isang adult sa photo.', reviewed: false },
  'result.landmark.above_chest': {
    text: 'Umaabot ang tubig sa itaas ng dibdib ng isang adult sa photo.',
    reviewed: false,
  },
  'result.basis.one': { text: 'Mula sa {count} reference object.', reviewed: false },
  'result.basis.other': { text: 'Mula sa {count} reference object.', reviewed: false },
  'result.inches.range': { text: 'Tinatayang {min} hanggang {max} in.', reviewed: false },
  'result.inches.same': { text: 'Tinatayang {min} in.', reviewed: false },
  'result.levelFrom.geometry': { text: 'Sinukat mula sa laki ng rim ng gulong.', reviewed: false },
  'result.noFlood': { text: 'Walang bahang nakita sa spot na ito.', reviewed: false },
  'result.failed': { text: 'Hindi natapos ang pagproseso, subukan ulit.', reviewed: false },
  'result.private': {
    text: 'Kinunan sa labas ng Metro Manila, kaya ikaw lang ang makakakita ng result na ito. Wala ito sa mapa.',
    reviewed: false,
  },
  'result.noResult': { text: 'Wala pang result. Mas matagal kaysa dati ang analysis.', reviewed: false },
  'result.checkAgain': { text: 'Tingnan ulit', reviewed: false },
  'result.tryAgain': { text: 'Subukan ulit', reviewed: false },
  'reason.too_dark': { text: 'Masyadong madilim ang photo para mabasa.', reviewed: false },
  'reason.too_blurry': { text: 'Masyadong malabo ang photo para mabasa.', reviewed: false },
  'reason.photo_unusable': { text: 'Hindi mababasa ng Lusot ang spot sa photo na ito.', reviewed: false },
  'reason.water_unsure': { text: 'Hindi masabi ng Lusot kung may nakatigil na tubig sa photo.', reviewed: false },
  'reason.no_water_found': { text: 'Hindi matukoy ng Lusot ang hugis ng tubig sa photo.', reviewed: false },
  'reason.no_usable_reference': {
    text: 'Walang kotse o tao sa photo na magagamit para basahin ang lalim.',
    reviewed: false,
  },
  'reason.references_disagree': {
    text: 'Higit sa isang level ang pagitan ng lalim na ibinibigay ng mga kotse at tao sa photo.',
    reviewed: false,
  },
  'reason.model_declined': { text: 'Tumanggi ang reading model na sumagot para sa photo na ito.', reviewed: false },
  'reason.model_calls_paused': { text: 'Naka-pause muna ang mga bagong analysis ngayon.', reviewed: false },
  'reason.photo_missing': { text: 'Hindi makita ng Lusot ang na-upload na photo.', reviewed: false },
  'reason.bad_file': { text: 'Hindi mabasa ang file ng photo.', reviewed: false },
  'reason.model_error': { text: 'May error ang reading model.', reviewed: false },
  'reason.pipeline_error': { text: 'May error ang Lusot habang sinusuri ang photo.', reviewed: false },
  'reason.pipeline_not_built': {
    text: 'Galing ang report na ito sa isang maagang test build na hindi pa nagsusuri ng photo.',
    reviewed: false,
  },
  'reason.other': { text: 'Wala nang ibang dahilan na maibibigay.', reviewed: false },
}
