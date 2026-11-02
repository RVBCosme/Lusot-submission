import { EN, type Entry, type StringKey } from './en'

// The Taglish string table: every key of en.ts, each with its own review mark (C609). The drafts are Claude's
// and wait for Rene's copy review (M20). A screen-line key shows its English line until its Taglish is
// reviewed (C619).
// The M20 copy review of Oct 30 (by the tracker, under Rene's delegation) reviewed every key present at a4d066d.
// A key whose text changed after that commit stays unreviewed.
export const FIL: Record<StringKey, Entry> = {
  'nav.map': { text: 'Mapa', reviewed: true },
  'nav.report': { text: 'Mag-report', reviewed: true },
  'nav.tested': { text: 'Tested', reviewed: true },
  'nav.about': { text: 'Tungkol', reviewed: true },
  'nav.ask': { text: 'Magtanong', reviewed: true },
  // The two locked lines are the English entries themselves, so the tables can't drift apart (C619).
  'layout.screenLine': EN['layout.screenLine'],
  'about.notAffiliated': EN['about.notAffiliated'],
  'lang.en': { text: 'English', reviewed: true },
  'lang.fil': { text: 'Taglish', reviewed: true },
  'lang.switch': { text: 'Wika', reviewed: true },
  'layout.noApi': { text: 'Walang API address ang build na ito, kaya hindi ito makakapag-upload.', reviewed: true },
  'layout.offline': { text: 'Offline ka. Kailangan ng internet para magamit ang mapa, mga report, mga sample at Ask Lusot.', reviewed: true },
  'layout.noApiDetail': {
    text: 'Hindi naka-set ang VITE_API_URL. Ilagay ito sa app/.env.local, saka i-build ulit.',
    reviewed: true,
  },
  'layout.errorFallback': { text: 'Hindi maipakita ang screen na ito. Pumili ng ibang screen sa bar sa ibaba.', reviewed: true },
  // A privacy key: it shows its English line until its Taglish is reviewed (C619). Window 4's draft keeps the
  // policy's title in English.
  'privacy.title': { text: 'Lusot privacy policy', reviewed: true },
  'licences.title': { text: 'Mga open-source na lisensya', reviewed: true },
  'pin.title': { text: 'Detalye ng pin', reviewed: true },
  'privacy.contactPending': { text: 'idadagdag bago maging public ang Lusot', reviewed: true },
  // The gates' controls, from Window 4's draft of the notice (M20). Consent keys show their English line until
  // their Taglish is reviewed (C619).
  'consent.adultTitle': { text: 'Kumpirmahin ang edad mo', reviewed: true },
  'consent.adultBody': { text: 'Para lang sa mga adult ang Lusot, 18 taong gulang pataas.', reviewed: true },
  'consent.adult': { text: 'Ako ay 18 taong gulang pataas.', reviewed: true },
  'consent.required': { text: '(kailangan)', reviewed: true },
  'consent.continue': { text: 'Magpatuloy', reviewed: true },
  'consent.notNow': { text: 'Mamaya na lang', reviewed: true },
  'consent.readPolicy': { text: 'Basahin ang privacy policy', reviewed: true },
  'camera.title': { text: 'Kumuha ng photo', reviewed: true },
  'camera.hint': {
    text: 'Mula sa tuyong lugar, itutok ang camera sa tubig, at isama sa kuha ang gulong ng nakaparadang kotse o taong nakatayo lang.',
    reviewed: true,
  },
  'camera.starting': { text: 'Binubuksan ang camera. Kung magtanong ang phone mo, payagan ito.', reviewed: true },
  'camera.preview': { text: 'Live na kuha mula sa camera', reviewed: true },
  'camera.shutter': { text: 'Kumuha ng photo', reviewed: true },
  'camera.taking': { text: 'Inihahanda ang photo', reviewed: true },
  'camera.samples': { text: 'Tingnan na lang ang mga sample', reviewed: true },
  'camera.denied': {
    text: 'Hindi magamit ng Lusot ang camera. Payagan ang camera para sa page na ito sa settings ng browser o phone mo, saka subukan ulit.',
    reviewed: true,
  },
  'camera.noCamera': {
    text: 'Hindi nakapagbukas ng camera ang Lusot sa device na ito. Isara ang ibang app na gumagamit ng camera, saka subukan ulit.',
    reviewed: true,
  },
  'camera.unsupported': {
    text: 'Hindi mabuksan ng browser na ito ang camera para sa Lusot. Subukan ang Chrome o Safari.',
    reviewed: true,
  },
  'camera.timeout': {
    text: 'Hindi nagsimula ang camera. Isara ang ibang app na gumagamit nito, saka subukan ulit.',
    reviewed: true,
  },
  'camera.capture': { text: 'Hindi nakuha ng Lusot ang photo. Subukan ulit.', reviewed: true },
  'camera.inApp': { text: 'Buksan ang page na ito sa Chrome o Safari para makakuha ng photo.', reviewed: true },
  'place.title': { text: 'Tingnan ang pin', reviewed: true },
  'place.hint': {
    text: 'Nasa lugar mo ang pin, ayon sa phone mo. I-drag ito, o i-tap ang mapa, para ilagay sa spot na nasa photo mo. Hanggang 100 m lang ito maililipat.',
    reviewed: true,
  },
  'place.legend': {
    text: 'Ipinapakita ng bilog kung gaano katumpak ang pagtukoy ng phone mo sa lugar mo.',
    reviewed: true,
  },
  'place.map': { text: 'Mapa na may pin', reviewed: true },
  'place.pin': { text: 'Pin. Gamitin ang mga arrow key para igalaw ito nang 10 m bawat pindot.', reviewed: true },
  'place.moved': { text: 'Inilipat mo ang pin nang {metres} m.', reviewed: true },
  'place.atLimit': { text: 'Hanggang 100 m lang ang layo ng pin.', reviewed: true },
  'place.reset': { text: 'Ibalik ang pin', reviewed: true },
  'place.send': { text: 'Ipadala', reviewed: true },
  'location.retry': { text: 'Subukan ulit ang location', reviewed: true },
  'location.poor': {
    text: 'Hindi nakakuha ang Lusot ng sapat na tumpak na location mo. Mas madaling mahanap ng phone ang lokasyon mo kapag kita ang langit. Subukan ulit ang location. Sa Android 12 o mas bago, payagan din ang precise location, hindi lang approximate, sa settings ng page o app na ito.',
    reviewed: true,
  },
  'location.denied': {
    text: 'Hindi magamit ng Lusot ang location mo. Payagan ang location para sa page o app na ito sa settings ng browser o phone mo, saka subukan ulit.',
    reviewed: true,
  },
  'location.servicesOff': {
    text: 'Naka-off ang location sa phone na ito. I-on ito sa settings ng phone, saka subukan ulit.',
    reviewed: true,
  },
  'location.enableDenied': {
    text: 'Kailangan ng Lusot na naka-on ang location para mailagay ang pin. I-on ito kapag nagtanong ang phone mo, saka subukan ulit.',
    reviewed: true,
  },
  'location.allOff': {
    text: 'Hindi mahanap ng Lusot ang location mo dahil naka-off ang location at ang network. I-on ang location, saka subukan ulit.',
    reviewed: true,
  },
  'location.unavailable': { text: 'Hindi nakuha ng Lusot ang location mo. Subukan ulit.', reviewed: true },
  // The report flow (MS5 Task 12). Drafts for Rene's copy review (M20).
  'report.noApi': { text: 'Hindi makakapagpadala ng photo ang build na ito.', reviewed: true },
  'report.locationTitle': { text: 'Ang location mo', reviewed: true },
  'report.locating': { text: 'Hinahanap kung nasaan ka.', reviewed: true },
  'report.smallStill': {
    text: 'Mas maliit ang photo na binigay ng camera mo kaysa sa hinihingi ng Lusot, kaya baka mas mahirap itong basahin. Puwede mo itong ipadala, o kumuha ng bagong photo.',
    reviewed: true,
  },
  'report.checkTitle': { text: 'Tingnan ang photo', reviewed: true },
  'retake.too_dark': {
    text: 'Mukhang masyadong madilim ang photo na ito para mabasa ng Lusot. Kunan ulit kapag mas maliwanag na, mula sa tuyong lugar. Huwag lumusong sa baha o pumunta sa kalsada.',
    reviewed: true,
  },
  'retake.too_blurry': {
    text: 'Mukhang malabo ang photo na ito. Hawakan nang steady ang phone at kunan ulit, mula sa tuyong lugar. Huwag lumusong sa baha o pumunta sa kalsada.',
    reviewed: true,
  },
  'report.checkNote': { text: 'Puwede mo pa ring ipadala ang photo na ito. Titingnan ulit ito ng Lusot kapag natanggap na.', reviewed: true },
  'report.retake': { text: 'Kunan ulit', reviewed: true },
  'report.sendAnyway': { text: 'Ipadala pa rin', reviewed: true },
  'report.newPhoto': { text: 'Kumuha ng bagong photo', reviewed: true },
  'report.tooOld': { text: 'Lampas na sa 15 minuto ang photo na ito.', reviewed: true },
  'report.sendingTitle': { text: 'Pinapadala ang photo mo', reviewed: true },
  'report.sendingHint': { text: 'Huwag munang isara ang Lusot hanggang maipadala ang photo.', reviewed: true },
  'report.waitingTitle': { text: 'Binabasa ang photo mo', reviewed: true },
  'report.waitingHint': {
    text: 'Naipadala na ang photo mo. Puwede kang umalis sa screen na ito, at nandito ang resulta pagbalik mo.',
    reviewed: true,
  },
  'report.elapsed': { text: '{seconds} s na', reviewed: true },
  'report.queue': { text: 'Baka may ibang photo na nauna sa iyo.', reviewed: true },
  'report.resultTitle': { text: 'Ang resulta mo', reviewed: true },
  'report.notSent': { text: 'Hindi naipadala ang photo', reviewed: true },
  'report.nothingUploaded': { text: 'Walang na-upload.', reviewed: true },
  'report.uploadFailed': { text: 'Tingnan ang connection mo, saka subukan ulit.', reviewed: true },
  'report.sendFailed': { text: 'Hindi naipadala ng Lusot ang photo. Subukan ulit.', reviewed: true },
  'report.limit.device_limit': {
    text: 'Naabot na ng phone na ito ang dami ng photo na tinatanggap ng Lusot sa isang oras. Subukan ulit mamaya.',
    reviewed: true,
  },
  'report.limit.global_cap': {
    text: 'Naabot na ng Lusot ang dami ng photo na kaya nito sa ngayon. Subukan ulit mamaya.',
    reviewed: true,
  },
  'report.refused.capture_in_future': {
    text: 'Nauuna ang oras ng photo sa orasan ng Lusot. Tingnan ang date at time ng phone na ito, saka kumuha ng bagong photo.',
    reviewed: true,
  },
  'report.refused.gps_too_coarse': {
    text: 'Hindi sapat na tumpak ang location ng phone mo para mailagay ang pin.',
    reviewed: true,
  },
  'report.refused.nudge_too_far': {
    text: 'Lampas sa 100 m ang pin mula sa kung saan ka inilagay ng phone mo.',
    reviewed: true,
  },
  'about.what': {
    text: 'Tinatantya ng Lusot ang lalim ng baha sa isang spot mula sa photo na kinunan mo. Binabasa nito ang lalim ayon sa flood gauge ng MMDA at ipinapakita ang ebidensya, o sinasabi nitong hindi nito masabi.',
    reviewed: true,
  },
  'about.theme': { text: 'Tema', reviewed: true },
  'about.theme.system': { text: 'Gaya ng device na ito', reviewed: true },
  'about.theme.light': { text: 'Light', reviewed: true },
  'about.theme.dark': { text: 'Dark', reviewed: true },
  'about.officialTitle': { text: 'Mga opisyal na abiso', reviewed: true },
  'about.mmda': { text: 'Opisyal na site ng MMDA', reviewed: true },
  'about.pagasa': { text: 'Opisyal na site ng PAGASA', reviewed: true },
  'about.creditsTitle': { text: 'Credits', reviewed: true },
  'about.credits.maker': {
    text: 'Ginawa ni Rene Vincent Cosme, bilang solo entry sa Meta Global AI Developer Hackathon.',
    reviewed: true,
  },
  'about.credits.models': { text: 'Binabasa ng Lusot ang mga photo gamit ang SAM 3.1 at Muse Spark ng Meta.', reviewed: true },
  'about.credits.levels': {
    text: 'Ang 9 na level ng Lusot ay ang 7 gauge level ng MMDA, dagdag ang dalawang sariling level ng Lusot: below gutter at above chest. Sa MMDA ang mga passability class na PATV, NPLV at NPATV.',
    reviewed: true,
  },
  'about.legalTitle': { text: 'Privacy at mga lisensya', reviewed: true },
  'licences.intro': {
    text: 'Ang code at mga font na pinagmulan ng Lusot, kasama ang buong teksto ng lisensya ng bawat isa.',
    reviewed: true,
  },
  'licences.loading': { text: 'Kinukuha ang mga teksto ng lisensya.', reviewed: true },
  'licences.unavailable': { text: 'Hindi makuha ang mga teksto ng lisensya.', reviewed: true },
  'licences.textLabel': { text: 'Mga teksto ng lisensya', reviewed: true },
  'licences.otherTitle': { text: 'Iba pang pinagmulan', reviewed: true },
  'licences.osm': {
    text: 'Ang map data ay © OpenStreetMap contributors, sa ilalim ng Open Database License (ODbL). Ang mga map tile ay mula sa OpenStreetMap, ayon sa Tile Usage Policy nito.',
    reviewed: true,
  },
  'licences.osmLink': { text: 'Copyright at lisensya ng OpenStreetMap', reviewed: true },
  'licences.samples': { text: 'May sariling credit ang bawat sample na photo, na makikita kasama ng sample.', reviewed: true },
  'licences.packagesTitle': { text: 'Mga package na pinagmulan ng app', reviewed: true },
  'licences.packagesNote': {
    text: 'Ang mga production package ng app, ayon sa listahan ng npm. Kasama sa listahan ang package na pinagbabatayan ng Android app, at mga package na naglalarawan lang ng mga type at hindi kasama sa page.',
    reviewed: true,
  },
  // The draft of D19's line from the Oct 28 log.
  'refusal.d19': {
    text: 'Hindi ko masabi mula sa photo na ito. Kunan ulit mula sa tuyong lugar, kita ang gulong ng nakaparadang sasakyan o isang taong nakatayo. Huwag lumusong sa baha o pumunta sa kalsada.',
    reviewed: true,
  },
  // The wording of results (MS5 Task 4). Claude's drafts, passed in the M20 review. MMDA's own level
  // names stay in English, as people say them. The reason lines show their English text until reviewed (C619).
  // C637's two lines, drafted for Rene. Refusal keys show English on a Taglish screen until reviewed (C619).
  'refusal.sample.cantTell': { text: 'Hindi masabi ng Lusot mula sa photo na ito.', reviewed: true },
  'refusal.sample.someoneWouldSee': {
    text: 'Ito ang makikita ng sinumang magre-report sa spot na ito:',
    reviewed: true,
  },
  'result.levelName.below_gutter': { text: 'mas mababa sa gutter', reviewed: true },
  'result.levelName.gutter': { text: 'gutter', reviewed: true },
  'result.levelName.half_knee': { text: 'half-knee', reviewed: true },
  'result.levelName.half_tire': { text: 'half-tire', reviewed: true },
  'result.levelName.knee': { text: 'knee', reviewed: true },
  'result.levelName.tire': { text: 'tire', reviewed: true },
  'result.levelName.waist': { text: 'waist', reviewed: true },
  'result.levelName.chest': { text: 'chest', reviewed: true },
  'result.levelName.above_chest': { text: 'lampas chest', reviewed: true },
  'result.level.exact': { text: '{level} ang lalim sa spot na ito (MMDA level).', reviewed: true },
  'result.level.floor': { text: 'Hindi bababa sa {level} ang lalim sa spot na ito (MMDA level).', reviewed: true },
  'result.level.off': { text: '{level} ang lalim sa spot na ito.', reviewed: true },
  'result.level.offFloor': { text: 'Hindi bababa sa {level} ang lalim sa spot na ito.', reviewed: true },
  'result.class.patv': {
    text: 'Inililista ng MMDA ang level na ito bilang passable sa lahat ng sasakyan (PATV).',
    reviewed: true,
  },
  'result.class.nplv': {
    text: 'Inililista ng MMDA ang level na ito bilang hindi passable sa light vehicles (NPLV).',
    reviewed: true,
  },
  'result.class.npatv': {
    text: 'Inililista ng MMDA ang level na ito bilang hindi passable sa anumang sasakyan (NPATV).',
    reviewed: true,
  },
  'result.class.belowGutter': {
    text: 'Mas mababa sa gutter level ng MMDA, na inililista ng MMDA bilang passable sa lahat ng sasakyan (PATV).',
    reviewed: true,
  },
  'result.class.aboveChest': {
    text: 'Mas malalim sa chest level ng MMDA, na inililista ng MMDA bilang hindi passable sa anumang sasakyan (NPATV).',
    reviewed: true,
  },
  'result.landmark.tire_only': {
    text: 'Umaabot ang tubig sa gulong ng nakaparadang sasakyan, sa ibaba ng rim.',
    reviewed: true,
  },
  'result.landmark.rim_quarter': {
    text: 'Umaabot ang tubig sa isang kapat ng taas ng rim ng gulong ng nakaparadang sasakyan.',
    reviewed: true,
  },
  'result.landmark.hub': {
    text: 'Umaabot ang tubig sa hub, mga kalahati ng taas ng gulong ng nakaparadang sasakyan.',
    reviewed: true,
  },
  'result.landmark.rim_three_quarters': {
    text: 'Umaabot ang tubig sa tatlong kapat ng taas ng rim ng gulong ng nakaparadang sasakyan.',
    reviewed: true,
  },
  'result.landmark.rim_top': {
    text: 'Umaabot ang tubig sa tuktok ng rim ng gulong ng nakaparadang sasakyan.',
    reviewed: true,
  },
  'result.landmark.wheel_covered': {
    text: 'Natatakpan ng tubig ang buong gulong ng nakaparadang sasakyan.',
    reviewed: true,
  },
  'result.landmark.mid_door': {
    text: 'Umaabot ang tubig sa gitna ng pinto ng nakaparadang sasakyan.',
    reviewed: true,
  },
  'result.landmark.window': {
    text: 'Umaabot ang tubig sa mga bintana ng nakaparadang sasakyan.',
    reviewed: true,
  },
  'result.landmark.ankle': { text: 'Umaabot ang tubig sa bukong-bukong ng isang adult sa photo.', reviewed: true },
  'result.landmark.mid_shin': {
    text: 'Umaabot ang tubig sa gitna ng ibabang binti ng isang adult sa photo.',
    reviewed: true,
  },
  'result.landmark.knee': { text: 'Umaabot ang tubig sa tuhod ng isang adult sa photo.', reviewed: true },
  'result.landmark.mid_thigh': { text: 'Umaabot ang tubig sa gitna ng hita ng isang adult sa photo.', reviewed: true },
  'result.landmark.waist': { text: 'Umaabot ang tubig sa baywang ng isang adult sa photo.', reviewed: true },
  'result.landmark.chest': { text: 'Umaabot ang tubig sa dibdib ng isang adult sa photo.', reviewed: true },
  'result.landmark.above_chest': {
    text: 'Umaabot ang tubig sa itaas ng dibdib ng isang adult sa photo.',
    reviewed: true,
  },
  'result.basis.one': { text: 'Mula sa {count} reference object.', reviewed: true },
  'result.basis.other': { text: 'Mula sa {count} reference object.', reviewed: true },
  'result.inches.range': { text: 'Tinatayang {min} hanggang {max} in.', reviewed: true },
  'result.inches.same': { text: 'Tinatayang {min} in.', reviewed: true },
  'result.levelFrom.geometry': { text: 'Sinukat mula sa laki ng rim ng gulong.', reviewed: true },
  'result.noFlood': { text: 'Walang bahang nakita sa spot na ito.', reviewed: true },
  'result.failed': { text: 'Nabigo ang pagproseso, subukan ulit.', reviewed: true },
  'result.private': {
    text: 'Kinunan sa labas ng Metro Manila, kaya ikaw lang ang makakakita ng result na ito. Wala ito sa mapa.',
    reviewed: true,
  },
  'result.noResult': { text: 'Wala pang result. Mas matagal kaysa karaniwan ang analysis.', reviewed: true },
  'result.checkAgain': { text: 'Tingnan ulit', reviewed: true },
  'result.tryAgain': { text: 'Subukan ulit', reviewed: true },
  // Spec C638's own draft.
  'result.paused': {
    text: 'Naka-pause ngayon ang mga bagong analysis. Gumagana pa rin ang mapa at ang Tested page.',
    reviewed: true,
  },
  'result.photoTaken': { text: 'Kinunan ang photo {age}.', reviewed: true },
  'result.accuracy': { text: 'Nasa loob ng {m} m ang lokasyon.', reviewed: true },
  'result.age.justNow': { text: 'ngayon lang', reviewed: true },
  'result.age.minutes': { text: '{min} min na ang nakalipas', reviewed: true },
  'result.age.hours': { text: '{h} h na ang nakalipas', reviewed: true },
  'result.age.hoursMinutes': { text: '{h} h {min} min na ang nakalipas', reviewed: true },
  'result.details': { text: 'Mga detalye', reviewed: true },
  'result.details.reason': { text: 'Reason code: {code}', reviewed: true },
  'result.details.photoTime': { text: 'Oras ng photo: {time}', reviewed: true },
  'result.details.references': { text: 'Mga reference object', reviewed: true },
  'result.reference': { text: 'Reference {id}:', reviewed: true },
  'reason.too_dark': { text: 'Masyadong madilim ang photo para mabasa.', reviewed: true },
  'reason.too_blurry': { text: 'Masyadong malabo ang photo para mabasa.', reviewed: true },
  'reason.photo_unusable': { text: 'Hindi mababasa ng Lusot ang spot sa photo na ito.', reviewed: true },
  'reason.water_unsure': { text: 'Hindi masabi ng Lusot kung may nakatigil na tubig sa photo.', reviewed: true },
  'reason.no_water_found': {
    text: 'Hindi matukoy ng Lusot ang hugis ng tubig sa photo, kaya hindi nito mabasa ang lalim.',
    reviewed: true,
  },
  'reason.no_usable_reference': {
    text: 'Walang kotse o tao sa photo na magagamit para basahin ang lalim.',
    reviewed: true,
  },
  'reason.references_disagree': {
    text: 'Higit sa isang level ang pagitan ng lalim na ibinibigay ng mga kotse at tao sa photo.',
    reviewed: true,
  },
  'reason.model_declined': { text: 'Tumanggi ang reading model na sumagot para sa photo na ito.', reviewed: true },
  'reason.model_calls_paused': { text: 'Naka-pause ngayon ang mga bagong analysis.', reviewed: true },
  'reason.photo_missing': { text: 'Hindi makita ng Lusot ang na-upload na photo.', reviewed: true },
  'reason.bad_file': { text: 'Hindi mabasa ang file ng photo.', reviewed: true },
  'reason.model_error': { text: 'May error ang reading model.', reviewed: true },
  'reason.pipeline_error': { text: 'May error ang Lusot habang sinusuri ang photo.', reviewed: true },
  'reason.pipeline_not_built': {
    text: 'Galing ang report na ito sa isang maagang test build na hindi pa nagsusuri ng photo.',
    reviewed: true,
  },
  'reason.other': { text: 'Wala nang ibang dahilan na maibibigay.', reviewed: true },
  // The refusal tips, approved as written at M20 (en.ts says where and when).
  'tip.no_usable_reference': {
    text:
      'Kunan ang mismong spot, hindi ang larawan sa screen. Mababasa ng Lusot ang lalim mula sa gulong ng ' +
      'nakaparadang kotse, SUV o van na inaabot na ng tubig, hindi mula sa jeepney, bus, malaking truck, tricycle o ' +
      'motorsiklo. Mula sa tuyong bangketa, nang hindi lumalapit sa tubig, kunan ulit nang malaki at malinaw sa photo ' +
      'ang isang ganoong gulong.',
    reviewed: true,
  },
  'tip.photo_unusable': {
    text:
      'Kunan ang mismong spot, hindi ang larawan sa screen. Kailangan ng Lusot ng malinaw na kita ng spot na ito: ' +
      'punasan ang lens, hawakan nang steady ang phone, at kunan ulit mula sa tuyong bangketa nang walang nakaharang ' +
      'sa camera.',
    reviewed: true,
  },
  'tip.water_unsure': {
    text:
      'Hindi masabi ng Lusot kung baha ito o basa lang ang lupa. Mula sa tuyong bangketa, kunan ulit nang malinaw na ' +
      'kita ang tubig kung saan ito dumidikit sa gulong ng isang nakaparadang kotse.',
    reviewed: true,
  },
  'tip.no_water_found': {
    text:
      'Mula sa tuyong bangketa, nang hindi lumalapit sa tubig, kunan ulit nang mas malaki ang kita ng ibabaw ng ' +
      'tubig sa photo, para malinaw ang gilid nito sa paligid ng gulong ng isang nakaparadang kotse.',
    reviewed: true,
  },
  'tip.references_disagree': {
    text:
      'Kapag magkakaiba ang lalim sa mga kotse o tao, puwedeng hindi pantay ang tubig dito. Hindi pipili ang Lusot ' +
      'ng isang lalim kaysa sa iba, kaya walang level para sa photo na ito.',
    reviewed: true,
  },
  'dropped.vehicle_unanswered': {
    text: 'Hindi ginamit, dahil walang sagot ang reading model para sa sasakyang ito.',
    reviewed: true,
  },
  'dropped.vehicle_moving': { text: 'Hindi ginamit, dahil maaaring gumagalaw ang sasakyan.', reviewed: true },
  'dropped.vehicle_type': {
    text: 'Hindi ginamit, dahil hindi makapagbibigay ng reading ang ganitong uri ng sasakyan.',
    reviewed: true,
  },
  'dropped.vehicle_body_below_covered_wheel': {
    text: 'Hindi ginamit, dahil hindi magkatugma ang reading sa katawan at sa mga gulong ng sasakyang ito.',
    reviewed: true,
  },
  'dropped.vehicle_wheels_disagree': {
    text: 'Hindi ginamit, dahil magkaiba ang reading ng mga gulong ng sasakyang ito.',
    reviewed: true,
  },
  'dropped.vehicle_no_reading': {
    text: 'Hindi ginamit, dahil walang reading ng lalim mula sa sasakyang ito.',
    reviewed: true,
  },
  'dropped.wheel_vehicle_dropped': {
    text: 'Hindi ginamit, dahil hindi ginamit ang sasakyan ng gulong na ito.',
    reviewed: true,
  },
  'dropped.wheel_unanswered': {
    text: 'Hindi ginamit, dahil walang sagot ang reading model para sa gulong na ito.',
    reviewed: true,
  },
  'dropped.wheel_methods_disagree': {
    text: 'Hindi ginamit, dahil magkaiba ang lalim na nabasa sa dalawang paraan para sa gulong na ito.',
    reviewed: true,
  },
  'dropped.person_unanswered': {
    text: 'Hindi ginamit, dahil walang sagot ang reading model para sa taong ito.',
    reviewed: true,
  },
  // C92's line, approved as written at M20 by the tracker under Rene's written delegation (Nov 2, about 4:4x AM),
  // for Rene's morning sign-off.
  'dropped.person_small': {
    text: 'Hindi ginamit, dahil masyadong maliit ang taong ito sa photo para mabasa.',
    reviewed: true,
  },
  'dropped.person_not_adult': { text: 'Hindi ginamit, dahil maaaring hindi adult ang taong ito.', reviewed: true },
  'dropped.person_wading': {
    text: 'Hindi ginamit, dahil maaaring hindi nakatigil ang taong ito.',
    reviewed: true,
  },
  'dropped.person_no_reading': {
    text: 'Hindi ginamit, dahil walang reading ng lalim mula sa taong ito.',
    reviewed: true,
  },
  'dropped.no_water_contact': {
    text: 'Hindi ginamit, dahil hindi malinaw na dumadampi ang tubig sa reference na ito.',
    reviewed: true,
  },
  'dropped.ragged_waterline': {
    text: 'Hindi ginamit, dahil hindi malinaw ang waterline sa reference na ito.',
    reviewed: true,
  },
  'dropped.other': { text: 'Hindi ginamit sa reading na ito.', reviewed: true },
  'badge.sample': { text: 'Sample', reviewed: true },
  'badge.demo': { text: 'Demo', reviewed: true },
  'sample.photoAlt': { text: 'Ang photo, na may blur ang mga mukha at plaka.', reviewed: true },
  'sample.photoFrom': { text: 'Photo mula sa {parts}', reviewed: true },
  'sample.edited': { text: 'Binlur ng Lusot ang mga mukha at plaka sa photo na ito.', reviewed: true },
  'sample.outlines': { text: 'Iginuhit ng Lusot ang mga outline nito sa photo.', reviewed: true },
  'sample.liveReading': {
    text: 'Ito ay live na reading ng photo na may credit, hindi test result.',
    reviewed: true,
  },
  'sample.savedReading': {
    text: 'Ito ay naka-save na reading ng photo na may credit, hindi test result.',
    reviewed: true,
  },
  'sample.savedFrom': { text: 'Naka-save na result noong {date}', reviewed: true },
  'gauge.outside': { text: 'Labas sa gauge ng MMDA', reviewed: true },
  'gauge.orDeeper': { text: 'o mas malalim', reviewed: true },
  'overlay.title': { text: 'Mga outline ng Lusot sa photo', reviewed: true },
  'overlay.ref.wheel': { text: 'Gulong {id}', reviewed: true },
  'overlay.ref.body': { text: 'Katawan ng sasakyan {id}', reviewed: true },
  'overlay.ref.person': { text: 'Tao {id}', reviewed: true },
  'overlay.floor': { text: 'Hindi bababa sa {level}', reviewed: true },
  // Approved by the tracker under Rene's written delegation, Nov 2, about 3:4x AM (en.ts has the reason).
  'overlay.fromWheel': { text: 'Ang gulong nito ang nagbigay ng reading.', reviewed: true },
  'overlay.noLevel': { text: 'Walang nabasang level dito.', reviewed: true },
  'map.noApi': { text: 'Hindi maipapakita ng build na ito ang mga report.', reviewed: true },
  'map.loading': { text: 'Kinukuha ang mga report.', reviewed: true },
  'map.loadFailed': { text: 'Hindi makuha ng Lusot ang mga report ngayon. Susubukan ulit ng Lusot.', reviewed: true },
  'map.viewGroup': { text: 'Ipakita ang mga report bilang', reviewed: true },
  'map.list': { text: 'Listahan', reviewed: true },
  'map.listLabel': { text: 'Mga report, pinakabago muna', reviewed: true },
  'map.mapLabel': { text: 'Mapa ng mga report', reviewed: true },
  'map.locate': { text: 'Hanapin ako', reviewed: true },
  'map.zoomIn': { text: 'I-zoom in', reviewed: true },
  'map.zoomOut': { text: 'I-zoom out', reviewed: true },
  'map.report': { text: 'Mag-report ng spot', reviewed: true },
  'map.own': { text: 'Report mo', reviewed: true },
  'map.back': { text: 'Bumalik sa mapa', reviewed: true },
  'map.empty.title': { text: 'Walang report sa nakalipas na 3 oras', reviewed: true },
  'map.empty.note': { text: 'Maaaring baha pa rin ang spot na walang report.', reviewed: true },
  'map.trySample': { text: 'Subukan ang sample', reviewed: true },
  'badge.example': { text: 'Halimbawa', reviewed: true },
  'map.example.note': { text: 'Halimbawa lang ng reading, hindi report mula sa kahit saan.', reviewed: true },
  'pin.gone': { text: 'Wala na ang pin na ito sa mapa.', reviewed: true },
  'pin.loading': { text: 'Kinukuha ang pin na ito.', reviewed: true },
  'pin.loadFailed': { text: 'Hindi makuha ng Lusot ang pin na ito ngayon.', reviewed: true },
  'pin.photoFailed': { text: 'Hindi makuha ng Lusot ang photo ngayon.', reviewed: true },
  'pin.nearby': { text: 'Ibang report sa loob ng 300 m, nakalipas na 3 oras: {count}', reviewed: true },
  'pin.flags.one': { text: 'May 1 phone na nag-flag sa report na ito bilang mali o peke.', reviewed: true },
  'pin.flags.other': { text: 'May {count} phone na nag-flag sa report na ito bilang mali o peke.', reviewed: true },
  'pin.flag': { text: 'I-flag bilang mali o peke', reviewed: true },
  'pin.flagged': { text: 'Na-flag na', reviewed: true },
  'pin.flagFailed': { text: 'Hindi naipadala ng Lusot ang flag. Subukan ulit.', reviewed: true },
  'flag.title': { text: 'I-flag ang report na ito?', reviewed: true },
  'flag.body': {
    text: 'I-flag ito kung mukhang mali ang reading o peke ang photo. Madaragdagan ng flag ang bilang na nakikita sa pin na ito. Hindi nito aalisin ang pin.',
    reviewed: true,
  },
  'flag.confirm': { text: 'I-flag', reviewed: true },
  'flag.cancel': { text: 'Kanselahin', reviewed: true },
  'tested.how.title': { text: 'Paano tine-test ang Lusot', reviewed: true },
  'tested.how.labels': {
    text: 'Ikinukumpara ang mga reading ng Lusot sa mga flood level na ipinost ng MMDA at ng mga lungsod kasama ng sarili nilang mga photo.',
    reviewed: true,
  },
  'tested.how.sealed': {
    text: 'Itinabi at sinelyuhan ang bahagi ng mga photo na iyon bago ang anumang tuning. Isang beses lang sila sinu-score, naka-freeze ang settings ng Lusot, at ipinapaalam ang anumang rerun kasama ang dahilan nito.',
    reviewed: true,
  },
  'tested.how.rules': {
    text: 'Itinakda at inaprubahan ang mga patakaran sa pag-score bago makita ang anumang resulta.',
    reviewed: true,
  },
  'tested.how.cars': {
    text: 'Tine-test din ang pagsukat sa rim ng gulong sa mga photo ng nakaparadang kotse, na may tubig na iginuhit sa alam na lalim.',
    reviewed: true,
  },
  'tested.results.title': { text: 'Mga resulta', reviewed: true },
  'tested.pending': { text: 'Lalabas dito ang mga resulta pagkatapos ng sealed run sa Nov 3.', reviewed: true },
  'tested.results.from': { text: 'Mula sa sealed run noong {date}.', reviewed: true },
  'tested.results.rerunFrom': {
    text: 'Mula sa rerun noong {date}, ang nag-iisang rerun na pinapayagan ng mga patakaran sa pag-score.',
    reviewed: true,
  },
  'tested.results.intro': {
    text: 'Ipinapakita ng bawat figure kung gaano kadalas tumugma ang Lusot sa mga label na ipinost ng MMDA at ng mga lungsod, at kung ilang photo ang binibilang nito. Dahil kaunti ang mga photo, indicative ang bawat figure.',
    reviewed: true,
  },
  'tested.shipped.landmark': {
    text: 'Ang mga figure na ito ay para sa Lusot na ilalabas: binabasa ang lalim mula sa mga gulong at tao.',
    reviewed: true,
  },
  'tested.shipped.geometry': {
    text: 'Ang mga figure na ito ay para sa Lusot na ilalabas: binabasa ang lalim mula sa mga gulong at tao, at sinusukat ang rim ng gulong.',
    reviewed: true,
  },
  'tested.figure.underestimation': { text: 'Mas mababaw ang basa kaysa sa label (mas mababa, mas mabuti)', reviewed: true },
  'tested.figure.passability': { text: 'Parehong passability class sa label', reviewed: true },
  'tested.figure.coverage': { text: 'Mga photo na sinagot, hindi tinanggihan', reviewed: true },
  'tested.figure.exact': { text: 'Parehong level sa label', reviewed: true },
  'tested.figure.withinOne': { text: 'Hanggang isang level ang layo sa label', reviewed: true },
  'tested.rate': { text: '{k} sa {n} ({percent}%)', reviewed: true },
  'tested.rateNoShare': { text: '{k} sa {n}', reviewed: true },
  'tested.indicative': { text: 'indicative', reviewed: true },
  'tested.inches.shown': {
    text: 'Ipinapakita ang inches: pumasa ang pagsukat sa rim ng gulong sa release check nito.',
    reviewed: true,
  },
  'tested.inches.notShown': {
    text: 'Hindi ipinapakita ang inches: hindi pumasa ang pagsukat sa rim ng gulong sa release check nito.',
    reviewed: true,
  },
  'tested.setB.title': { text: 'Pagsukat sa rim ng gulong, sa mga nakaparadang kotse', reviewed: true },
  'tested.setB.median': { text: 'Median na error', reviewed: true },
  'tested.setB.medianValue': { text: '{inches} in, sa {n} gulong', reviewed: true },
  'tested.setB.measured': { text: 'Mga gulong na nasukat', reviewed: true },
  'tested.reportLink': { text: 'Basahin ang buong test report', reviewed: true },
  'tested.limits.title': { text: 'Mga alam na limitasyon', reviewed: true },
  'tested.limits.night': {
    text: 'Sa gabi, tinatanggihan ang photo na masyadong madilim, at mas mahirap basahin ang malamlam.',
    reviewed: true,
  },
  'tested.limits.rain': {
    text: 'Ang ulan sa lens, o malakas na ulan, ay puwedeng magtago kung hanggang saan ang tubig.',
    reviewed: true,
  },
  'tested.limits.blur': { text: 'Tinatanggihan ang photo na masyadong malabo.', reviewed: true },
  'tested.limits.faceBlur': {
    text: 'Puwedeng hindi ma-blur ng awtomatikong face blur ang ilang mukha: napakaliit, nakatagilid, may takip o nasa dilim. Ang mukhang hindi na-blur ay makakarating sa Meta nang walang blur.',
    reviewed: true,
  },
  'tested.samples.title': { text: 'Mga sample', reviewed: true },
  'tested.samples.intro': {
    text: 'Mga credited na photo ng baha na puwede mong patakbuhin sa Lusot. Ang run ay nagbibigay ng live na reading ng credited na photo, o naka-save na reading habang naka-pause ang mga bagong analysis. Hindi kailanman napupunta sa mapa ang result ng sample.',
    reviewed: true,
  },
  'tested.samples.loading': { text: 'Kinukuha ang mga sample.', reviewed: true },
  'tested.samples.more': { text: 'May darating pang mga sample.', reviewed: true },
  'tested.samples.noApi': { text: 'Hindi makapagpatakbo ng sample ang build na ito.', reviewed: true },
  'sample.run': { text: 'Patakbuhin ang sample na ito', reviewed: true },
  'sample.reading': { text: 'Binabasa ng Lusot ang sample na ito.', reviewed: true },
  'sample.unanswered': {
    text: 'Walang magagamit na sagot na natanggap ang Lusot. Baka nagsimula na ang run at baka matapos pa ito, pero hindi maipapakita ng page na ito ang resulta.',
    reviewed: true,
  },
  'sample.gone': { text: 'Wala na ang sample na ito.', reviewed: true },
  'sample.failed': { text: 'Hindi mapatakbo ng Lusot ang sample na ito ngayon.', reviewed: true },
  'sample.limit.device_limit': {
    text: 'Naabot na ng phone na ito ang dami ng sample na pinapayagan ng Lusot sa isang oras. Subukan ulit mamaya.',
    reviewed: true,
  },
  'sample.limit.global_cap': {
    text: 'Naabot na ng Lusot ang dami ng sample na kaya nito sa ngayon. Subukan ulit mamaya.',
    reviewed: true,
  },
  // Ask Lusot's lines (plan Task 14): Claude's Taglish drafts, each waiting for Rene's review (M20). The ask.answer.
  // keys show their English line until their Taglish is reviewed (C724). The first two example questions are Taglish
  // already and stay as written, the third is translated, and the attribution is OpenStreetMap's own wording.
  'ask.ui.placeholder': { text: 'Magtanong tungkol sa lalim ng baha sa isang lugar', reviewed: true },
  'ask.ui.send': { text: 'Itanong', reviewed: true },
  'ask.ui.mic': { text: 'Magtanong gamit ang boses', reviewed: true },
  'ask.ui.micStop': { text: 'Ihinto', reviewed: true },
  'ask.ui.micLeft': { text: '{s} s na lang', reviewed: true },
  'ask.ui.location': { text: 'Gamitin ang location ko', reviewed: true },
  'ask.ui.locationWaiting': { text: 'Hinahanap ang location mo…', reviewed: true },
  'ask.ui.locationPoor': {
    text: 'Hindi pa pasok sa 100 m ang location mo. Subukan sa lugar na kita ang langit, o magbanggit ng lugar.',
    reviewed: true,
  },
  'ask.ui.locationTurnOn': {
    text: 'Kailangang naka-on ang location para magamit ito sa tanong. I-on ito kapag nagtanong ang phone mo, saka subukan ulit, o magbanggit ng lugar.',
    reviewed: true,
  },
  'ask.ui.youAsked': { text: 'Tanong mo:', reviewed: true },
  'ask.ui.notice': {
    text: 'Napupunta sa AI service ng Meta ang tanong mo. Hindi ito sine-save ng Lusot.',
    reviewed: true,
  },
  'ask.ui.attribution': { text: 'Place search © OpenStreetMap contributors', reviewed: true },
  'ask.ui.used': { text: 'Ginamit', reviewed: true },
  'ask.ui.openPin': { text: 'Buksan ang pin na ito', reviewed: true },
  'ask.ui.example1': { text: 'Gaano kalalim ang baha sa España cor. Maceda?', reviewed: true },
  'ask.ui.example2': { text: 'May baha ba dito?', reviewed: true },
  'ask.ui.example3': { text: 'Gaano kalalim sa G. Araneta Ave cor. E. Rodriguez Sr. Ave?', reviewed: true },
  'ask.ui.questionLabel': { text: 'Ang tanong mo', reviewed: true },
  'ask.ui.asking': { text: 'Hinahanap ang mga recent report…', reviewed: true },
  'ask.ui.examples': { text: 'Subukang itanong:', reviewed: true },
  'ask.ui.noApi': { text: 'Hindi makapagtanong ang build na ito.', reviewed: true },
  'ask.ui.answer': { text: 'Sagot', reviewed: true },
  'ask.ui.suggestionQuestion': { text: 'Gaano kalalim sa {spot}?', reviewed: true },
  'ask.error.questionLimit': {
    text: '20 tanong na ang naitanong mo ngayong oras. Subukan ulit pagkalipas ng {min} min.',
    reviewed: true,
  },
  'ask.error.questionCap': {
    text: 'Naabot na ng Ask Lusot ang limit nito ngayong oras. Subukan ulit pagkalipas ng {min} min.',
    reviewed: true,
  },
  'ask.error.voicePaused': {
    text: 'Naka-pause ngayon ang mga tanong gamit ang boses. I-type na lang ang tanong mo.',
    reviewed: true,
  },
  'ask.error.voiceFailed': { text: 'Hindi narinig ng Lusot ang tanong. Subukan ulit, o i-type ito.', reviewed: true },
  'ask.error.unavailable': {
    text: 'Hindi makasagot ang Ask Lusot ngayon. Subukan ulit pagkalipas ng isang minuto.',
    reviewed: true,
  },
  'ask.error.micDenied': {
    text: 'Hindi magamit ng Lusot ang mikropono. Payagan ito para sa page o app na ito sa settings ng browser o phone mo para makapagtanong gamit ang boses, o i-type ang tanong mo.',
    reviewed: true,
  },
  'ask.error.micUnavailable': {
    text: 'Hindi makapag-record ng tanong ang phone o browser na ito. I-type na lang ang tanong mo.',
    reviewed: true,
  },
  'ask.answer.crossing': { text: 'Hindi ko masasabi kung dapat kang tumawid o dumaan.', reviewed: true },
  'ask.answer.summaryOne': {
    text: '1 report sa loob ng 300 m mula sa {place} sa nakaraang {window}.',
    reviewed: true,
  },
  'ask.answer.summaryMany': {
    text: '{n} report sa loob ng 300 m mula sa {place} sa nakaraang {window}.',
    reviewed: true,
  },
  'ask.answer.summaryHereOne': {
    text: '1 report sa loob ng 300 m mula sa iyo sa nakaraang {window}.',
    reviewed: true,
  },
  'ask.answer.summaryHereMany': {
    text: '{n} report sa loob ng 300 m mula sa iyo sa nakaraang {window}.',
    reviewed: true,
  },
  'ask.answer.where': { text: 'Kinunan ang photo {age}, {distance} m mula sa {place}.', reviewed: true },
  'ask.answer.whereHere': { text: 'Kinunan ang photo {age}, {distance} m mula sa iyo.', reviewed: true },
  'ask.answer.vehicleLight': {
    text: 'Para sa mga class ng MMDA, light vehicle ang turing ng Lusot sa sasakyan mo.',
    reviewed: true,
  },
  'ask.answer.vehicleHeavy': {
    text: 'Para sa mga class ng MMDA, heavy vehicle ang turing ng Lusot sa sasakyan mo.',
    reviewed: true,
  },
  'ask.answer.onFoot': {
    text: 'Para sa mga sasakyan ang mga class ng MMDA, kaya level lang ang ibinibigay ng sagot na ito.',
    reviewed: true,
  },
  'ask.answer.demo': { text: '(demo)', reviewed: true },
  'ask.answer.noReports': {
    text: 'Walang recent report sa loob ng 300 m mula sa {place} sa nakaraang {window}.',
    reviewed: true,
  },
  'ask.answer.noReportsHere': {
    text: 'Walang recent report sa loob ng 300 m mula sa iyo sa nakaraang {window}.',
    reviewed: true,
  },
  'ask.answer.noReportNote': { text: 'Ang walang report ay hindi nangangahulugang walang baha.', reviewed: true },
  'ask.answer.tooBroad': {
    text: 'Buong kalye o lugar iyan. Magtanong tungkol sa isang kanto o landmark doon, o i-on ang location mo at magtanong tungkol sa "dito".',
    reviewed: true,
  },
  'ask.answer.noPlace': {
    text: 'Hindi ko mahanap ang lugar na iyan sa Metro Manila. Magbanggit ng kanto o landmark, o i-on ang location mo at magtanong tungkol sa "dito".',
    reviewed: true,
  },
  'ask.answer.lookupUnavailable': {
    text: 'Hindi ko ma-check ang lugar na iyan ngayon. Subukan ulit pagkalipas ng isang minuto, o magbanggit ng malapit na landmark.',
    reviewed: true,
  },
  'ask.answer.outside': { text: 'Sumasagot lang ang Lusot tungkol sa mga spot sa Metro Manila.', reviewed: true },
  'ask.answer.noLocation': {
    text: 'I-on ang location mo para makapagtanong tungkol sa "dito", o magbanggit ng lugar.',
    reviewed: true,
  },
  'ask.answer.offTopic': {
    text: 'Lalim lang ng baha malapit sa isang lugar sa Metro Manila ang kaya kong sagutin, mula sa mga recent report.',
    reviewed: true,
  },
  'ask.answer.noSpeech': { text: 'Wala akong narinig na tanong. Subukan ulit, o i-type ito.', reviewed: true },
  'ask.answer.plainList': { text: 'Narito ang listahan ng mga report.', reviewed: true },
  'ask.window.hours': { text: '{n} oras', reviewed: true },
  'ask.window.hour': { text: '1 oras', reviewed: true },
  'ask.window.minutes': { text: '{n} minuto', reviewed: true },
  'ask.window.minute': { text: '1 minuto', reviewed: true },
}
