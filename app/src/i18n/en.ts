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
  // Screen headings without a nav label. The policy's is the title of Window 4's draft.
  'privacy.title': { text: 'Lusot privacy policy', reviewed: false },
  'licences.title': { text: 'Open-source licences', reviewed: false },
  'pin.title': { text: 'Pin detail', reviewed: false },
  // The policy's contact until VITE_PRIVACY_CONTACT is set at build time (PRIV-Q4). The policy is English until
  // Rene approves its Taglish, so the page uses this English line in both languages.
  'privacy.contactPending': { text: 'added when the page is published', reviewed: false },
  // The gates (C605). The notice's prose is app/src/content/consent.en.md; its controls are these lines, from
  // Window 4's draft. The 18+ check alone, before a sample, has its own heading and line.
  'consent.adultTitle': { text: 'Confirm your age', reviewed: false },
  'consent.adultBody': { text: 'Lusot is only for adults, 18 or older.', reviewed: false },
  'consent.adult': { text: 'I am 18 or older.', reviewed: false },
  'consent.required': { text: '(required)', reviewed: false },
  'consent.continue': { text: 'Continue', reviewed: false },
  'consent.notNow': { text: 'Not now', reviewed: false },
  'consent.readPolicy': { text: 'Read the privacy policy', reviewed: false },
  // The in-app camera (C602). Its problem lines say what to do and point to the samples. They aren't screen-line
  // keys, so their Taglish drafts show. 'camera.inApp' is the plan's own line for Messenger's and Facebook's browsers.
  'camera.title': { text: 'Take a photo', reviewed: false },
  'camera.hint': {
    text: "From a dry spot, point the camera at the water, with a parked car's wheel or a person standing still in view.",
    reviewed: false,
  },
  'camera.starting': { text: 'Starting the camera. If your phone asks, allow it.', reviewed: false },
  'camera.preview': { text: 'Live view from the camera', reviewed: false },
  'camera.shutter': { text: 'Take photo', reviewed: false },
  'camera.taking': { text: 'Preparing the photo', reviewed: false },
  'camera.samples': { text: 'Look at the samples instead', reviewed: false },
  'camera.denied': {
    text: "Lusot can't use the camera. Allow the camera for this page in your browser or phone settings, then try again.",
    reviewed: false,
  },
  'camera.noCamera': {
    text: "Lusot couldn't open a camera on this device. Close any other app that is using the camera, then try again.",
    reviewed: false,
  },
  'camera.unsupported': { text: "This browser can't open a camera for Lusot. Try Chrome or Safari.", reviewed: false },
  'camera.timeout': {
    text: "The camera didn't start. Close any other app that is using it, then try again.",
    reviewed: false,
  },
  'camera.capture': { text: "Lusot couldn't take the photo. Try again.", reviewed: false },
  'camera.inApp': { text: 'Open this page in Chrome or Safari to take a photo.', reviewed: false },
  // The place step (C603): the pin on a small map, with the circle of the fix's accuracy. The pin may move up to
  // 100 m from the fix. A position is never written out as numbers, only the distance moved.
  'place.title': { text: 'Check the pin', reviewed: false },
  'place.hint': {
    text: 'The pin is where your phone says you are. Drag it, or tap the map, to put it on the spot in your photo. It can move up to 100 m.',
    reviewed: false,
  },
  'place.legend': { text: 'The circle shows how closely your phone placed you.', reviewed: false },
  'place.map': { text: 'Map with the pin', reviewed: false },
  'place.pin': { text: 'Pin. Use the arrow keys to move it 10 m at a time.', reviewed: false },
  // The two status lines stay short enough for one line at 360 px, so the feedback shows above Send without scrolling.
  'place.moved': { text: 'You moved the pin {metres} m.', reviewed: false },
  'place.atLimit': { text: "The pin can't go further than 100 m.", reviewed: false },
  'place.reset': { text: 'Put the pin back', reviewed: false },
  'place.send': { text: 'Send', reviewed: false },
  // The location's own problem lines (locationLine in lib/geo.ts picks one). The flow shows them with
  // 'location.retry' and keeps the photo for a new try. Not screen-line keys, so their Taglish drafts show.
  'location.retry': { text: 'Try the location again', reviewed: false },
  'location.poor': {
    text: "Lusot couldn't get a good enough fix on your spot. A clear view of the sky helps the phone find you. Try the location again. On Android 12 or later, also allow precise location, not only approximate, in the settings for this page or app.",
    reviewed: false,
  },
  'location.denied': {
    text: "Lusot can't use your location. Allow location for this page or app in your browser or phone settings, then try again.",
    reviewed: false,
  },
  'location.servicesOff': {
    text: 'Location is turned off on this phone. Turn it on in your phone settings, then try again.',
    reviewed: false,
  },
  'location.enableDenied': {
    text: 'Lusot needs location turned on to place the pin. Turn it on when your phone asks, then try again.',
    reviewed: false,
  },
  'location.allOff': {
    text: "Lusot couldn't find your location because location and the network are both turned off. Turn location on, then try again.",
    reviewed: false,
  },
  'location.unavailable': { text: "Lusot couldn't get your location. Try again.", reviewed: false },
  // The report flow (MS5 Task 12): finding the location, sending, waiting, the result's heading, and why a photo
  // wasn't sent. Not screen-line keys, so their Taglish drafts show. "Nothing was uploaded." follows each line that
  // the API's refusal or pause gives (C638). A limit's line names no time, since the API's reset may differ.
  'report.noApi': { text: "This build can't send photos.", reviewed: false },
  'report.locationTitle': { text: 'Your location', reviewed: false },
  'report.locating': { text: 'Finding where you are.', reviewed: false },
  'report.smallStill': {
    text: 'Your camera gave a smaller photo than Lusot asks for, so it may be harder to read. You can send it, or take a new photo.',
    reviewed: false,
  },
  'report.newPhoto': { text: 'Take a new photo', reviewed: false },
  'report.tooOld': { text: 'This photo is more than 15 minutes old.', reviewed: false },
  'report.sendingTitle': { text: 'Sending your photo', reviewed: false },
  'report.sendingHint': { text: 'Keep Lusot open until the photo is sent.', reviewed: false },
  'report.waitingTitle': { text: 'Reading your photo', reviewed: false },
  'report.waitingHint': {
    text: 'Your photo was sent. You can leave this screen, and the result will be here when you come back.',
    reviewed: false,
  },
  'report.elapsed': { text: '{seconds} s so far', reviewed: false },
  // From 60 s. It promises no time (C601).
  'report.queue': { text: 'Other photos may be ahead of yours.', reviewed: false },
  'report.resultTitle': { text: 'Your result', reviewed: false },
  'report.notSent': { text: 'Photo not sent', reviewed: false },
  'report.nothingUploaded': { text: 'Nothing was uploaded.', reviewed: false },
  // Only when the browser said it was offline as the upload failed. Any other failure gets 'report.sendFailed'.
  'report.uploadFailed': { text: 'Check your connection, then try again.', reviewed: false },
  'report.sendFailed': { text: "Lusot couldn't send the photo. Try again.", reviewed: false },
  'report.limit.device_limit': {
    text: 'This phone has sent as many photos as Lusot takes in an hour. Try again later.',
    reviewed: false,
  },
  'report.limit.global_cap': {
    text: 'Lusot has taken as many photos as it can for now. Try again later.',
    reviewed: false,
  },
  // MS4's 422s (its §4.3). The app's own checks should keep the last two from happening.
  'report.refused.capture_in_future': {
    text: "The photo's time is ahead of Lusot's clock. Check the date and time on this phone, then take a new photo.",
    reviewed: false,
  },
  'report.refused.gps_too_coarse': {
    text: "Your phone's location wasn't precise enough to place the pin.",
    reviewed: false,
  },
  'report.refused.nudge_too_far': {
    text: 'The pin was more than 100 m from where your phone placed you.',
    reviewed: false,
  },
  // About (C619, C633, C636). Its links to the policy and the licences use those screens' titles.
  'about.what': {
    text: "Lusot estimates the depth of a flood at one spot from a photo you take. It reads the depth against MMDA's flood gauge and shows the evidence, or it says it can't tell.",
    reviewed: false,
  },
  'about.theme': { text: 'Theme', reviewed: false },
  'about.theme.system': { text: 'Same as this device', reviewed: false },
  'about.theme.light': { text: 'Light', reviewed: false },
  'about.theme.dark': { text: 'Dark', reviewed: false },
  'about.officialTitle': { text: 'Official advisories', reviewed: false },
  'about.mmda': { text: "MMDA's official site", reviewed: false },
  'about.pagasa': { text: "PAGASA's official site", reviewed: false },
  'about.creditsTitle': { text: 'Credits', reviewed: false },
  'about.credits.maker': {
    text: 'Made by Rene Vincent Cosme, as a solo entry to the Meta Global AI Developer Hackathon.',
    reviewed: false,
  },
  'about.credits.models': { text: "Lusot reads photos with Meta's SAM 3.1 and Muse Spark models.", reviewed: false },
  'about.credits.levels': {
    text: "Lusot's 9 levels are MMDA's 7 gauge levels plus two of Lusot's own, below gutter and above chest. The passability classes PATV, NPLV and NPATV are MMDA's.",
    reviewed: false,
  },
  'about.legalTitle': { text: 'Privacy and licences', reviewed: false },
  // D19's refusal, which Rene confirmed in English.
  'refusal.d19': {
    text: "I can't tell from this photo. Retake it from a dry spot with a parked car's wheel or a person standing still in view. Don't step into the water or the road.",
    reviewed: true,
  },
  // The wording of results (MS5 Task 4; copy/wording.ts builds each line). A level's line is its name in one of
  // four templates. MS3a's C81 fixed the pattern and these four names (knee, tire, below gutter, above chest);
  // the other names, the lines for a floor on an added level and every other line below wait for Rene's review.
  // C637: a sample's refusal doesn't ask a judge to retake a photo they didn't take, so D19's line sits inside a frame.
  'refusal.sample.cantTell': { text: "Lusot can't tell from this photo.", reviewed: false },
  'refusal.sample.someoneWouldSee': { text: 'Someone reporting this spot would see:', reviewed: false },
  'result.levelName.below_gutter': { text: 'below gutter', reviewed: true },
  'result.levelName.gutter': { text: 'gutter', reviewed: false },
  'result.levelName.half_knee': { text: 'half-knee', reviewed: false },
  'result.levelName.half_tire': { text: 'half-tire', reviewed: false },
  'result.levelName.knee': { text: 'knee', reviewed: true },
  'result.levelName.tire': { text: 'tire', reviewed: true },
  'result.levelName.waist': { text: 'waist', reviewed: false },
  'result.levelName.chest': { text: 'chest', reviewed: false },
  'result.levelName.above_chest': { text: 'above chest', reviewed: true },
  'result.level.exact': { text: '{level} deep at this spot (MMDA level).', reviewed: true },
  'result.level.floor': { text: 'At least {level} deep at this spot (MMDA level).', reviewed: true },
  // The two levels that aren't MMDA's drop "(MMDA level)" (CLAUDE.md, C81).
  'result.level.off': { text: '{level} deep at this spot.', reviewed: true },
  'result.level.offFloor': { text: 'At least {level} deep at this spot.', reviewed: false },
  // The class line is what MMDA lists, never a verdict on the spot (plan §9, C81). C81 spells out the NPLV line
  // and the two added levels' lines; the PATV and NPATV lines follow plan §9, Table 10, so they wait for review.
  'result.class.patv': { text: 'MMDA lists this level as passable to all vehicles (PATV).', reviewed: false },
  'result.class.nplv': { text: 'MMDA lists this level as not passable to light vehicles (NPLV).', reviewed: true },
  'result.class.npatv': { text: 'MMDA lists this level as not passable to any vehicle (NPATV).', reviewed: false },
  'result.class.belowGutter': {
    text: "Shallower than MMDA's gutter level, which MMDA lists as passable to all vehicles (PATV).",
    reviewed: true,
  },
  'result.class.aboveChest': {
    text: "Deeper than MMDA's chest level, which MMDA lists as not passable to any vehicle (NPATV).",
    reviewed: true,
  },
  // Where the water meets the deciding reference (spec §4.3). A wheel or body line says "a parked car", because
  // moving vehicles never give a reading; a person's line says "an adult in the photo", because the API doesn't
  // say whether that adult was standing or wading.
  'result.landmark.tire_only': {
    text: "Water reaches only the tire of a parked car's wheel, not its rim.",
    reviewed: false,
  },
  'result.landmark.rim_quarter': {
    text: "Water reaches a quarter of the way up a parked car's wheel rim.",
    reviewed: false,
  },
  'result.landmark.hub': { text: "Water reaches the hub, about halfway up a parked car's wheel.", reviewed: false },
  'result.landmark.rim_three_quarters': {
    text: "Water reaches three quarters of the way up a parked car's wheel rim.",
    reviewed: false,
  },
  'result.landmark.rim_top': { text: "Water reaches the top of a parked car's wheel rim.", reviewed: false },
  'result.landmark.wheel_covered': { text: "Water covers a parked car's wheel completely.", reviewed: false },
  'result.landmark.mid_door': { text: "Water reaches the middle of a parked car's doors.", reviewed: false },
  'result.landmark.window': { text: 'Water reaches the windows of a parked car.', reviewed: false },
  'result.landmark.ankle': { text: 'Water reaches the ankles of an adult in the photo.', reviewed: false },
  'result.landmark.mid_shin': {
    text: 'Water reaches the middle of the shins of an adult in the photo.',
    reviewed: false,
  },
  'result.landmark.knee': { text: 'Water reaches the knees of an adult in the photo.', reviewed: false },
  'result.landmark.mid_thigh': {
    text: 'Water reaches the middle of the thighs of an adult in the photo.',
    reviewed: false,
  },
  'result.landmark.waist': { text: 'Water reaches the waist of an adult in the photo.', reviewed: false },
  'result.landmark.chest': { text: 'Water reaches the chest of an adult in the photo.', reviewed: false },
  'result.landmark.above_chest': {
    text: 'Water reaches above the chest of an adult in the photo.',
    reviewed: false,
  },
  'result.basis.one': { text: 'From {count} reference object.', reviewed: false },
  'result.basis.other': { text: 'From {count} reference objects.', reviewed: false },
  // Only when the API sends both ends, which happens only after the release gate passes (C515).
  'result.inches.range': { text: 'Estimated {min} to {max} in.', reviewed: false },
  'result.inches.same': { text: 'Estimated {min} in.', reviewed: false },
  // Shown only when geometry set the level (MS3b's C320, C328).
  'result.levelFrom.geometry': { text: 'Measured from the size of the wheel rim.', reviewed: false },
  // The three outcomes keep their own lines (CLAUDE.md): no flood seen, processing failed, and can't tell
  // ('refusal.d19', then a reason line).
  'result.noFlood': { text: 'No flood seen at this spot.', reviewed: false },
  'result.failed': { text: 'Processing failed, try again.', reviewed: false },
  'result.private': {
    text: "Taken outside Metro Manila, so only you see this result. It isn't on the map.",
    reviewed: false,
  },
  'result.noResult': { text: 'No result yet. The analysis is taking longer than usual.', reviewed: false },
  'result.checkAgain': { text: 'Check again', reviewed: false },
  'result.tryAgain': { text: 'Try again', reviewed: false },
  // A pause reads as a pause, never as "Processing failed" (C638, amendment 7). It is shown whatever set the switch,
  // so it names no cause. Its Taglish is spec C638's draft, and it isn't a screen-line key, so it shows in Taglish.
  'result.paused': {
    text: 'New analyses are paused right now. The map and the Tested page still work.',
    reviewed: false,
  },
  // "Photo taken 25 min ago. Location within 12 m." (plan Table 6): the age is one of the four lines below.
  'result.photoTaken': { text: 'Photo taken {age}.', reviewed: false },
  'result.accuracy': { text: 'Location within {m} m.', reviewed: false },
  'result.age.justNow': { text: 'just now', reviewed: false },
  'result.age.minutes': { text: '{min} min ago', reviewed: false },
  'result.age.hours': { text: '{h} h ago', reviewed: false },
  'result.age.hoursMinutes': { text: '{h} h {min} min ago', reviewed: false },
  // The "Details" disclosure: the reason code and the photo's time, never a report id or an error message (C610).
  'result.details': { text: 'Details', reviewed: false },
  'result.details.reason': { text: 'Reason code: {code}', reviewed: false },
  'result.details.photoTime': { text: 'Photo time: {time}', reviewed: false },
  'result.details.references': { text: 'Reference objects', reviewed: false },
  'result.reference': { text: 'Reference {id}:', reviewed: false },
  // One plain line for each refusalReason of MS3a's §3.4, and MS1's pipeline_not_built. None tells anyone to go
  // near water or traffic (plan §13). 'reason.other' stands in for any code the app doesn't know, so no raw code
  // is ever shown.
  'reason.too_dark': { text: 'The photo is too dark to read.', reviewed: false },
  'reason.too_blurry': { text: 'The photo is too blurry to read.', reviewed: false },
  'reason.photo_unusable': { text: "The photo doesn't show a spot that Lusot can read.", reviewed: false },
  'reason.water_unsure': {
    text: "Lusot couldn't tell whether there is standing water in the photo.",
    reviewed: false,
  },
  'reason.no_water_found': { text: "Lusot couldn't outline any water in the photo.", reviewed: false },
  'reason.no_usable_reference': {
    text: 'No car or person in the photo could be used to read the depth.',
    reviewed: false,
  },
  'reason.references_disagree': {
    text: 'The cars and people in the photo give depths more than one level apart.',
    reviewed: false,
  },
  'reason.model_declined': { text: 'The reading model declined to answer for this photo.', reviewed: false },
  'reason.model_calls_paused': { text: 'New analyses are paused right now.', reviewed: false },
  'reason.photo_missing': { text: "Lusot couldn't find the uploaded photo.", reviewed: false },
  'reason.bad_file': { text: "The photo's file couldn't be read.", reviewed: false },
  'reason.model_error': { text: 'The reading model had an error.', reviewed: false },
  'reason.pipeline_error': { text: 'Lusot had an error while analyzing the photo.', reviewed: false },
  'reason.pipeline_not_built': {
    text: "This report came from an early test build that didn't analyze photos.",
    reviewed: false,
  },
  'reason.other': { text: 'No further reason is available.', reviewed: false },
  // Why a numbered reference wasn't used (amendment 2): one line per cause the pipeline writes (copy/levels.ts), each
  // starting "Not used". 'dropped.other' stands in for any cause the app doesn't know, so no code is ever shown.
  'dropped.vehicle_unanswered': {
    text: 'Not used, since the reading model gave no answer for this vehicle.',
    reviewed: false,
  },
  'dropped.vehicle_moving': { text: 'Not used, since the vehicle may be moving.', reviewed: false },
  'dropped.vehicle_type': { text: "Not used, since this type of vehicle can't give a reading.", reviewed: false },
  'dropped.vehicle_body_below_covered_wheel': {
    text: "Not used, since the readings from this vehicle's body and wheels don't match.",
    reviewed: false,
  },
  'dropped.vehicle_wheels_disagree': {
    text: "Not used, since this vehicle's wheels gave different readings.",
    reviewed: false,
  },
  'dropped.vehicle_no_reading': { text: 'Not used, since this vehicle gave no depth reading.', reviewed: false },
  'dropped.wheel_vehicle_dropped': { text: "Not used, since this wheel's vehicle wasn't used.", reviewed: false },
  'dropped.wheel_unanswered': {
    text: 'Not used, since the reading model gave no answer for this wheel.',
    reviewed: false,
  },
  'dropped.wheel_methods_disagree': {
    text: 'Not used, since the two ways of reading this wheel gave different depths.',
    reviewed: false,
  },
  'dropped.person_unanswered': {
    text: 'Not used, since the reading model gave no answer for this person.',
    reviewed: false,
  },
  'dropped.person_not_adult': { text: 'Not used, since this person may not be an adult.', reviewed: false },
  'dropped.person_wading': { text: 'Not used, since this person may not be standing still.', reviewed: false },
  'dropped.person_no_reading': { text: 'Not used, since this person gave no depth reading.', reviewed: false },
  'dropped.no_water_contact': {
    text: "Not used, since the water doesn't clearly touch this reference.",
    reviewed: false,
  },
  'dropped.ragged_waterline': {
    text: "Not used, since the waterline against this reference isn't clear.",
    reviewed: false,
  },
  'dropped.other': { text: 'Not used for this reading.', reviewed: false },
  // A sample or a demo pin (C617, C618, C637): a credited photo that Lusot blurred and drew on, read live or saved.
  'badge.sample': { text: 'Sample', reviewed: false },
  'badge.demo': { text: 'Demo', reviewed: false },
  'sample.photoAlt': { text: 'The photo, with faces and plates blurred.', reviewed: false },
  'sample.photoFrom': { text: 'Photo from {parts}', reviewed: false },
  'sample.edited': {
    text: 'Lusot blurred the faces and plates in this photo and drew its outlines.',
    reviewed: false,
  },
  'sample.liveReading': {
    text: 'This is a live reading of a credited photo, not a test result.',
    reviewed: false,
  },
  'sample.savedReading': {
    text: 'This is a saved reading of a credited photo, not a test result.',
    reviewed: false,
  },
  'sample.savedFrom': { text: 'Saved result from {date}', reviewed: false },
  // The gauge's captions, beside its cells (the gauge is hidden from screen readers; the level line says it all).
  'gauge.outside': { text: "Outside MMDA's gauge", reviewed: false },
  'gauge.orDeeper': { text: 'or deeper', reviewed: false },
} satisfies Record<string, Entry>

export type StringKey = keyof typeof EN
