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
  // A privacy key: it shows its English line until its Taglish is reviewed (C619). Window 4's draft keeps the
  // policy's title in English.
  'privacy.title': { text: 'Lusot privacy policy', reviewed: false },
  'licences.title': { text: 'Mga open-source na lisensya', reviewed: false },
  'pin.title': { text: 'Detalye ng pin', reviewed: false },
  'privacy.contactPending': { text: 'idadagdag kapag na-publish na ang page', reviewed: false },
  // The gates' controls, from Window 4's draft of the notice (M20). Consent keys show their English line until
  // their Taglish is reviewed (C619).
  'consent.adultTitle': { text: 'Kumpirmahin ang edad mo', reviewed: false },
  'consent.adultBody': { text: 'Para lang sa mga adult ang Lusot, 18 taong gulang pataas.', reviewed: false },
  'consent.adult': { text: 'Ako ay 18 taong gulang pataas.', reviewed: false },
  'consent.required': { text: '(kailangan)', reviewed: false },
  'consent.continue': { text: 'Magpatuloy', reviewed: false },
  'consent.notNow': { text: 'Mamaya na lang', reviewed: false },
  'consent.readPolicy': { text: 'Basahin ang privacy policy', reviewed: false },
  'camera.title': { text: 'Kumuha ng photo', reviewed: false },
  'camera.hint': {
    text: 'Mula sa tuyong lugar, itutok ang camera sa tubig, at isama sa kuha ang gulong ng nakaparadang kotse o taong nakatayo lang.',
    reviewed: false,
  },
  'camera.starting': { text: 'Binubuksan ang camera. Kung magtanong ang phone mo, payagan ito.', reviewed: false },
  'camera.preview': { text: 'Live na kuha mula sa camera', reviewed: false },
  'camera.shutter': { text: 'Kumuha ng photo', reviewed: false },
  'camera.taking': { text: 'Inihahanda ang photo', reviewed: false },
  'camera.samples': { text: 'Tingnan na lang ang mga sample', reviewed: false },
  'camera.denied': {
    text: 'Hindi magamit ng Lusot ang camera. Payagan ang camera para sa page na ito sa settings ng browser o phone mo, saka subukan ulit.',
    reviewed: false,
  },
  'camera.noCamera': {
    text: 'Hindi nakapagbukas ng camera ang Lusot sa device na ito. Isara ang ibang app na gumagamit ng camera, saka subukan ulit.',
    reviewed: false,
  },
  'camera.unsupported': {
    text: 'Hindi mabuksan ng browser na ito ang camera para sa Lusot. Subukan ang Chrome o Safari.',
    reviewed: false,
  },
  'camera.timeout': {
    text: 'Hindi nagsimula ang camera. Isara ang ibang app na gumagamit nito, saka subukan ulit.',
    reviewed: false,
  },
  'camera.capture': { text: 'Hindi nakuha ng Lusot ang photo. Subukan ulit.', reviewed: false },
  'camera.inApp': { text: 'Buksan ang page na ito sa Chrome o Safari para makakuha ng photo.', reviewed: false },
  'place.title': { text: 'Tingnan ang pin', reviewed: false },
  'place.hint': {
    text: 'Nasa pin kung nasaan ka ayon sa phone mo. I-drag ito, o i-tap ang mapa, para ilagay sa spot sa photo mo. Hanggang 100 m lang ang puwede nitong gumalaw.',
    reviewed: false,
  },
  'place.legend': {
    text: 'Ipinapakita ng bilog kung gaano katumpak ang pagtukoy ng phone mo sa lugar mo.',
    reviewed: false,
  },
  'place.map': { text: 'Mapa na may pin', reviewed: false },
  'place.pin': { text: 'Pin. Gamitin ang mga arrow key para igalaw ito nang 10 m bawat pindot.', reviewed: false },
  'place.moved': { text: 'Inilipat mo ang pin nang {metres} m.', reviewed: false },
  'place.atLimit': { text: 'Hanggang 100 m lang ang layo ng pin.', reviewed: false },
  'place.reset': { text: 'Ibalik ang pin', reviewed: false },
  'place.send': { text: 'Ipadala', reviewed: false },
  'location.retry': { text: 'Subukan ulit ang location', reviewed: false },
  'location.poor': {
    text: 'Hindi nakakuha ang Lusot ng sapat na tumpak na location mo. Mas madaling mahanap ng phone ang lokasyon mo kapag kita ang langit. Subukan ulit ang location. Sa Android 12 o mas bago, payagan din ang precise location, hindi lang approximate, sa settings ng page o app na ito.',
    reviewed: false,
  },
  'location.denied': {
    text: 'Hindi magamit ng Lusot ang location mo. Payagan ang location para sa page o app na ito sa settings ng browser o phone mo, saka subukan ulit.',
    reviewed: false,
  },
  'location.servicesOff': {
    text: 'Naka-off ang location sa phone na ito. I-on ito sa settings ng phone, saka subukan ulit.',
    reviewed: false,
  },
  'location.enableDenied': {
    text: 'Kailangan ng Lusot na naka-on ang location para mailagay ang pin. I-on ito kapag nagtanong ang phone mo, saka subukan ulit.',
    reviewed: false,
  },
  'location.allOff': {
    text: 'Hindi mahanap ng Lusot ang location mo dahil naka-off ang location at ang network. I-on ang location, saka subukan ulit.',
    reviewed: false,
  },
  'location.unavailable': { text: 'Hindi nakuha ng Lusot ang location mo. Subukan ulit.', reviewed: false },
  // The report flow (MS5 Task 12). Drafts for Rene's copy review (M20).
  'report.noApi': { text: 'Hindi makakapagpadala ng photo ang build na ito.', reviewed: false },
  'report.locationTitle': { text: 'Ang location mo', reviewed: false },
  'report.locating': { text: 'Hinahanap kung nasaan ka.', reviewed: false },
  'report.smallStill': {
    text: 'Mas maliit ang photo na binigay ng camera mo kaysa sa hinihingi ng Lusot, kaya baka mas mahirap itong basahin. Puwede mo itong ipadala, o kumuha ng bagong photo.',
    reviewed: false,
  },
  'report.newPhoto': { text: 'Kumuha ng bagong photo', reviewed: false },
  'report.tooOld': { text: 'Lampas na sa 15 minuto ang photo na ito.', reviewed: false },
  'report.sendingTitle': { text: 'Pinapadala ang photo mo', reviewed: false },
  'report.sendingHint': { text: 'Huwag munang isara ang Lusot hanggang maipadala ang photo.', reviewed: false },
  'report.waitingTitle': { text: 'Binabasa ang photo mo', reviewed: false },
  'report.waitingHint': {
    text: 'Naipadala na ang photo mo. Puwede kang umalis sa screen na ito, at nandito ang resulta pagbalik mo.',
    reviewed: false,
  },
  'report.elapsed': { text: '{seconds} s na', reviewed: false },
  'report.queue': { text: 'Baka may ibang photo na nauna sa iyo.', reviewed: false },
  'report.resultTitle': { text: 'Ang resulta mo', reviewed: false },
  'report.notSent': { text: 'Hindi naipadala ang photo', reviewed: false },
  'report.nothingUploaded': { text: 'Walang na-upload.', reviewed: false },
  'report.uploadFailed': { text: 'Tingnan ang connection mo, saka subukan ulit.', reviewed: false },
  'report.sendFailed': { text: 'Hindi naipadala ng Lusot ang photo.', reviewed: false },
  'report.limit.device_limit': {
    text: 'Naabot na ng phone na ito ang dami ng photo na tinatanggap ng Lusot sa isang oras. Subukan ulit mamaya.',
    reviewed: false,
  },
  'report.limit.global_cap': {
    text: 'Naabot na ng Lusot ang dami ng photo na kaya nito sa ngayon. Subukan ulit mamaya.',
    reviewed: false,
  },
  'report.refused.capture_in_future': {
    text: 'Mas advanced ang oras ng photo kaysa sa orasan ng Lusot. Tingnan ang date at time ng phone na ito, saka kumuha ng bagong photo.',
    reviewed: false,
  },
  'report.refused.gps_too_coarse': {
    text: 'Hindi sapat na tumpak ang location ng phone mo para mailagay ang pin.',
    reviewed: false,
  },
  'report.refused.nudge_too_far': {
    text: 'Lampas sa 100 m ang pin mula sa kung saan ka inilagay ng phone mo.',
    reviewed: false,
  },
  'about.what': {
    text: 'Tinatantya ng Lusot ang lalim ng baha sa isang spot mula sa photo na kinunan mo. Binabasa nito ang lalim ayon sa flood gauge ng MMDA at ipinapakita ang ebidensya, o sinasabi nitong hindi nito masabi.',
    reviewed: false,
  },
  'about.theme': { text: 'Tema', reviewed: false },
  'about.theme.system': { text: 'Gaya ng device na ito', reviewed: false },
  'about.theme.light': { text: 'Light', reviewed: false },
  'about.theme.dark': { text: 'Dark', reviewed: false },
  'about.officialTitle': { text: 'Mga opisyal na abiso', reviewed: false },
  'about.mmda': { text: 'Opisyal na site ng MMDA', reviewed: false },
  'about.pagasa': { text: 'Opisyal na site ng PAGASA', reviewed: false },
  'about.creditsTitle': { text: 'Credits', reviewed: false },
  'about.credits.maker': {
    text: 'Ginawa ni Rene Vincent Cosme, bilang solo entry sa Meta Global AI Developer Hackathon.',
    reviewed: false,
  },
  'about.credits.models': { text: 'Binabasa ng Lusot ang mga photo gamit ang SAM 3.1 at Muse Spark ng Meta.', reviewed: false },
  'about.credits.levels': {
    text: 'Ang 9 na level ng Lusot ay ang 7 gauge level ng MMDA, dagdag ang dalawang sariling level ng Lusot: below gutter at above chest. Sa MMDA ang mga passability class na PATV, NPLV at NPATV.',
    reviewed: false,
  },
  'about.legalTitle': { text: 'Privacy at mga lisensya', reviewed: false },
  // The draft of D19's line from the Oct 28 log.
  'refusal.d19': {
    text: 'Hindi ko masabi mula sa photo na ito. Kunan ulit mula sa tuyong lugar, kita ang gulong ng nakaparadang sasakyan o isang taong nakatayo. Huwag lumusong sa baha o pumunta sa kalsada.',
    reviewed: false,
  },
  // The wording of results (MS5 Task 4). Claude's drafts, all waiting for Rene's review (M20). MMDA's own level
  // names stay in English, as people say them. The reason lines show their English text until reviewed (C619).
  // C637's two lines, drafted for Rene. Refusal keys show English on a Taglish screen until reviewed (C619).
  'refusal.sample.cantTell': { text: 'Hindi masabi ng Lusot mula sa photo na ito.', reviewed: false },
  'refusal.sample.someoneWouldSee': {
    text: 'Ito ang makikita ng sinumang magre-report sa spot na ito:',
    reviewed: false,
  },
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
  // Spec C638's own draft.
  'result.paused': {
    text: 'Naka-pause ngayon ang mga bagong analysis. Gumagana pa rin ang mapa at ang Tested page.',
    reviewed: false,
  },
  'result.photoTaken': { text: 'Kinunan ang photo {age}.', reviewed: false },
  'result.accuracy': { text: 'Nasa loob ng {m} m ang lokasyon.', reviewed: false },
  'result.age.justNow': { text: 'ngayon lang', reviewed: false },
  'result.age.minutes': { text: '{min} min na ang nakalipas', reviewed: false },
  'result.age.hours': { text: '{h} h na ang nakalipas', reviewed: false },
  'result.age.hoursMinutes': { text: '{h} h {min} min na ang nakalipas', reviewed: false },
  'result.details': { text: 'Mga detalye', reviewed: false },
  'result.details.reason': { text: 'Reason code: {code}', reviewed: false },
  'result.details.photoTime': { text: 'Oras ng photo: {time}', reviewed: false },
  'result.details.references': { text: 'Mga reference object', reviewed: false },
  'result.reference': { text: 'Reference {id}:', reviewed: false },
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
  'dropped.vehicle_unanswered': {
    text: 'Hindi ginamit, dahil walang sagot ang reading model para sa sasakyang ito.',
    reviewed: false,
  },
  'dropped.vehicle_moving': { text: 'Hindi ginamit, dahil maaaring gumagalaw ang sasakyan.', reviewed: false },
  'dropped.vehicle_type': {
    text: 'Hindi ginamit, dahil hindi makapagbibigay ng reading ang ganitong uri ng sasakyan.',
    reviewed: false,
  },
  'dropped.vehicle_body_below_covered_wheel': {
    text: 'Hindi ginamit, dahil hindi magkatugma ang reading sa katawan at sa mga gulong ng sasakyang ito.',
    reviewed: false,
  },
  'dropped.vehicle_wheels_disagree': {
    text: 'Hindi ginamit, dahil magkaiba ang reading ng mga gulong ng sasakyang ito.',
    reviewed: false,
  },
  'dropped.vehicle_no_reading': {
    text: 'Hindi ginamit, dahil walang reading ng lalim mula sa sasakyang ito.',
    reviewed: false,
  },
  'dropped.wheel_vehicle_dropped': {
    text: 'Hindi ginamit, dahil hindi ginamit ang sasakyan ng gulong na ito.',
    reviewed: false,
  },
  'dropped.wheel_unanswered': {
    text: 'Hindi ginamit, dahil walang sagot ang reading model para sa gulong na ito.',
    reviewed: false,
  },
  'dropped.wheel_methods_disagree': {
    text: 'Hindi ginamit, dahil magkaiba ang lalim na nabasa sa dalawang paraan para sa gulong na ito.',
    reviewed: false,
  },
  'dropped.person_unanswered': {
    text: 'Hindi ginamit, dahil walang sagot ang reading model para sa taong ito.',
    reviewed: false,
  },
  'dropped.person_not_adult': { text: 'Hindi ginamit, dahil maaaring hindi adult ang taong ito.', reviewed: false },
  'dropped.person_wading': {
    text: 'Hindi ginamit, dahil maaaring hindi nakatigil ang taong ito.',
    reviewed: false,
  },
  'dropped.person_no_reading': {
    text: 'Hindi ginamit, dahil walang reading ng lalim mula sa taong ito.',
    reviewed: false,
  },
  'dropped.no_water_contact': {
    text: 'Hindi ginamit, dahil hindi malinaw na dumadampi ang tubig sa reference na ito.',
    reviewed: false,
  },
  'dropped.ragged_waterline': {
    text: 'Hindi ginamit, dahil hindi malinaw ang waterline sa reference na ito.',
    reviewed: false,
  },
  'dropped.other': { text: 'Hindi ginamit sa reading na ito.', reviewed: false },
  'badge.sample': { text: 'Sample', reviewed: false },
  'badge.demo': { text: 'Demo', reviewed: false },
  'sample.photoAlt': { text: 'Ang photo, na may blur ang mga mukha at plaka.', reviewed: false },
  'sample.photoFrom': { text: 'Photo mula sa {parts}', reviewed: false },
  'sample.edited': {
    text: 'Binlur ng Lusot ang mga mukha at plaka sa photo na ito at iginuhit ang mga outline nito.',
    reviewed: false,
  },
  'sample.liveReading': {
    text: 'Ito ay live na reading ng photo na may credit, hindi test result.',
    reviewed: false,
  },
  'sample.savedReading': {
    text: 'Ito ay naka-save na reading ng photo na may credit, hindi test result.',
    reviewed: false,
  },
  'sample.savedFrom': { text: 'Naka-save na result noong {date}', reviewed: false },
  'gauge.outside': { text: 'Labas sa gauge ng MMDA', reviewed: false },
  'gauge.orDeeper': { text: 'o mas malalim', reviewed: false },
}
