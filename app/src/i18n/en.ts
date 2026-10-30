// The English string table (C609). Every line carries Rene's review mark (M20): the lines he has already fixed
// start reviewed, and every new line starts unreviewed until his copy review. `npm run copy:review -w app`
// prints the lines still waiting.
// The M20 copy review of Oct 30 (by the tracker, under Rene's delegation) reviewed every key present at a4d066d.
// A key whose text changed after that commit stays unreviewed.
export type Entry = { text: string; reviewed: boolean }

export const EN = {
  'nav.map': { text: 'Map', reviewed: true },
  'nav.report': { text: 'Report', reviewed: true },
  'nav.tested': { text: 'Tested', reviewed: true },
  'nav.about': { text: 'About', reviewed: true },
  // CLAUDE.md's exact line, on every screen. It stays in English in both languages (C619).
  'layout.screenLine': {
    text: 'Lusot estimates depth at one spot. It is not advice to cross. Follow MMDA and local advisories.',
    reviewed: true,
  },
  // CLAUDE.md's line. It stays in English in both languages (C619).
  'about.notAffiliated': { text: 'Not affiliated with MMDA.', reviewed: true },
  'lang.en': { text: 'English', reviewed: true },
  'lang.fil': { text: 'Taglish', reviewed: true },
  // The header's language switch, as a group of two buttons.
  'lang.switch': { text: 'Language', reviewed: true },
  // MS1's banner for a build made without VITE_API_URL (R31).
  'layout.noApi': { text: 'This build has no API address, so it cannot upload.', reviewed: true },
  'layout.noApiDetail': { text: 'VITE_API_URL is not set. Put it in app/.env.local, then build again.', reviewed: true },
  // The fallback where a screen that crashed would have been (S5-R5). The nav and the screen line stay.
  'layout.errorFallback': { text: 'This screen could not be shown. Choose another screen from the bar below.', reviewed: true },
  // Screen headings without a nav label. The policy's is the title of Window 4's draft.
  'privacy.title': { text: 'Lusot privacy policy', reviewed: true },
  'licences.title': { text: 'Open-source licences', reviewed: true },
  'pin.title': { text: 'Pin detail', reviewed: true },
  // The policy's contact until VITE_PRIVACY_CONTACT is set at build time (PRIV-Q4). The policy is English until
  // Rene approves its Taglish, so the page uses this English line in both languages.
  'privacy.contactPending': { text: 'to be added before Lusot goes public', reviewed: true },
  // The gates (C605). The notice's prose is app/src/content/consent.en.md; its controls are these lines, from
  // Window 4's draft. The 18+ check alone, before a sample, has its own heading and line.
  'consent.adultTitle': { text: 'Confirm your age', reviewed: true },
  'consent.adultBody': { text: 'Lusot is only for adults, 18 or older.', reviewed: true },
  'consent.adult': { text: 'I am 18 or older.', reviewed: true },
  'consent.required': { text: '(required)', reviewed: true },
  'consent.continue': { text: 'Continue', reviewed: true },
  'consent.notNow': { text: 'Not now', reviewed: true },
  'consent.readPolicy': { text: 'Read the privacy policy', reviewed: true },
  // The in-app camera (C602). Its problem lines say what to do and point to the samples. They aren't screen-line
  // keys, so their Taglish drafts show. 'camera.inApp' is the plan's own line for Messenger's and Facebook's browsers.
  'camera.title': { text: 'Take a photo', reviewed: true },
  'camera.hint': {
    text: "From a dry spot, point the camera at the water, with a parked car's wheel or a person standing still in view.",
    reviewed: true,
  },
  'camera.starting': { text: 'Starting the camera. If your phone asks, allow it.', reviewed: true },
  'camera.preview': { text: 'Live view from the camera', reviewed: true },
  'camera.shutter': { text: 'Take photo', reviewed: true },
  'camera.taking': { text: 'Preparing the photo', reviewed: true },
  'camera.samples': { text: 'Look at the samples instead', reviewed: true },
  'camera.denied': {
    text: "Lusot can't use the camera. Allow the camera for this page in your browser or phone settings, then try again.",
    reviewed: true,
  },
  'camera.noCamera': {
    text: "Lusot couldn't open a camera on this device. Close any other app that is using the camera, then try again.",
    reviewed: true,
  },
  'camera.unsupported': { text: "This browser can't open a camera for Lusot. Try Chrome or Safari.", reviewed: true },
  'camera.timeout': {
    text: "The camera didn't start. Close any other app that is using it, then try again.",
    reviewed: true,
  },
  'camera.capture': { text: "Lusot couldn't take the photo. Try again.", reviewed: true },
  'camera.inApp': { text: 'Open this page in Chrome or Safari to take a photo.', reviewed: true },
  // The place step (C603): the pin on a small map, with the circle of the fix's accuracy. The pin may move up to
  // 100 m from the fix. A position is never written out as numbers, only the distance moved.
  'place.title': { text: 'Check the pin', reviewed: true },
  'place.hint': {
    text: 'The pin is where your phone says you are. Drag it, or tap the map, to put it on the spot in your photo. It can move up to 100 m.',
    reviewed: true,
  },
  'place.legend': { text: 'The circle shows how closely your phone placed you.', reviewed: true },
  'place.map': { text: 'Map with the pin', reviewed: true },
  'place.pin': { text: 'Pin. Use the arrow keys to move it 10 m at a time.', reviewed: true },
  // The two status lines stay short enough for one line at 360 px, so the feedback shows above Send without scrolling.
  'place.moved': { text: 'You moved the pin {metres} m.', reviewed: true },
  'place.atLimit': { text: "The pin can't go further than 100 m.", reviewed: true },
  'place.reset': { text: 'Put the pin back', reviewed: true },
  'place.send': { text: 'Send', reviewed: true },
  // The location's own problem lines (locationLine in lib/geo.ts picks one). The flow shows them with
  // 'location.retry' and keeps the photo for a new try. Not screen-line keys, so their Taglish drafts show.
  'location.retry': { text: 'Try the location again', reviewed: true },
  'location.poor': {
    text: "Lusot couldn't get a good enough fix on your spot. A clear view of the sky helps the phone find you. Try the location again. On Android 12 or later, also allow precise location, not only approximate, in the settings for this page or app.",
    reviewed: true,
  },
  'location.denied': {
    text: "Lusot can't use your location. Allow location for this page or app in your browser or phone settings, then try again.",
    reviewed: true,
  },
  'location.servicesOff': {
    text: 'Location is turned off on this phone. Turn it on in your phone settings, then try again.',
    reviewed: true,
  },
  'location.enableDenied': {
    text: 'Lusot needs location turned on to place the pin. Turn it on when your phone asks, then try again.',
    reviewed: true,
  },
  'location.allOff': {
    text: "Lusot couldn't find your location because location and the network are both turned off. Turn location on, then try again.",
    reviewed: true,
  },
  'location.unavailable': { text: "Lusot couldn't get your location. Try again.", reviewed: true },
  // The report flow (MS5 Task 12): finding the location, sending, waiting, the result's heading, and why a photo
  // wasn't sent. Not screen-line keys, so their Taglish drafts show. "Nothing was uploaded." follows each line that
  // the API's refusal or pause gives (C638). A limit's line names no time, since the API's reset may differ.
  'report.noApi': { text: "This build can't send photos.", reviewed: true },
  'report.locationTitle': { text: 'Your location', reviewed: true },
  'report.locating': { text: 'Finding where you are.', reviewed: true },
  'report.smallStill': {
    text: 'Your camera gave a smaller photo than Lusot asks for, so it may be harder to read. You can send it, or take a new photo.',
    reviewed: true,
  },
  'report.newPhoto': { text: 'Take a new photo', reviewed: true },
  'report.tooOld': { text: 'This photo is more than 15 minutes old.', reviewed: true },
  'report.sendingTitle': { text: 'Sending your photo', reviewed: true },
  'report.sendingHint': { text: 'Keep Lusot open until the photo is sent.', reviewed: true },
  'report.waitingTitle': { text: 'Reading your photo', reviewed: true },
  'report.waitingHint': {
    text: 'Your photo was sent. You can leave this screen, and the result will be here when you come back.',
    reviewed: true,
  },
  'report.elapsed': { text: '{seconds} s so far', reviewed: true },
  // From 60 s. It promises no time (C601).
  'report.queue': { text: 'Other photos may be ahead of yours.', reviewed: true },
  'report.resultTitle': { text: 'Your result', reviewed: true },
  'report.notSent': { text: 'Photo not sent', reviewed: true },
  'report.nothingUploaded': { text: 'Nothing was uploaded.', reviewed: true },
  // Only when the browser said it was offline as the upload failed. Any other failure gets 'report.sendFailed'.
  'report.uploadFailed': { text: 'Check your connection, then try again.', reviewed: true },
  'report.sendFailed': { text: "Lusot couldn't send the photo. Try again.", reviewed: false },
  'report.limit.device_limit': {
    text: 'This phone has sent as many photos as Lusot takes in an hour. Try again later.',
    reviewed: true,
  },
  'report.limit.global_cap': {
    text: 'Lusot has taken as many photos as it can for now. Try again later.',
    reviewed: true,
  },
  // MS4's 422s (its §4.3). The app's own checks should keep the last two from happening.
  'report.refused.capture_in_future': {
    text: "The photo's time is ahead of Lusot's clock. Check the date and time on this phone, then take a new photo.",
    reviewed: true,
  },
  'report.refused.gps_too_coarse': {
    text: "Your phone's location wasn't precise enough to place the pin.",
    reviewed: false,
  },
  'report.refused.nudge_too_far': {
    text: 'The pin was more than 100 m from where your phone placed you.',
    reviewed: true,
  },
  // About (C619, C633, C636). Its links to the policy and the licences use those screens' titles.
  'about.what': {
    text: "Lusot estimates the depth of a flood at one spot from a photo you take. It reads the depth against MMDA's flood gauge and shows the evidence, or it says it can't tell.",
    reviewed: true,
  },
  'about.theme': { text: 'Theme', reviewed: true },
  'about.theme.system': { text: 'Same as this device', reviewed: true },
  'about.theme.light': { text: 'Light', reviewed: true },
  'about.theme.dark': { text: 'Dark', reviewed: true },
  'about.officialTitle': { text: 'Official advisories', reviewed: true },
  'about.mmda': { text: "MMDA's official site", reviewed: true },
  'about.pagasa': { text: "PAGASA's official site", reviewed: true },
  'about.creditsTitle': { text: 'Credits', reviewed: true },
  'about.credits.maker': {
    text: 'Made by Rene Vincent Cosme, as a solo entry to the Meta Global AI Developer Hackathon.',
    reviewed: true,
  },
  'about.credits.models': { text: "Lusot reads photos with Meta's SAM 3.1 and Muse Spark models.", reviewed: true },
  'about.credits.levels': {
    text: "Lusot's 9 levels are MMDA's 7 gauge levels plus two of Lusot's own, below gutter and above chest. The passability classes PATV, NPLV and NPATV are MMDA's.",
    reviewed: true,
  },
  'about.legalTitle': { text: 'Privacy and licences', reviewed: true },
  // D19's refusal, which Rene confirmed in English.
  'refusal.d19': {
    text: "I can't tell from this photo. Retake it from a dry spot with a parked car's wheel or a person standing still in view. Don't step into the water or the road.",
    reviewed: true,
  },
  // The wording of results (MS5 Task 4; copy/wording.ts builds each line). A level's line is its name in one of
  // four templates. MS3a's C81 fixed the pattern and these four names (knee, tire, below gutter, above chest);
  // the M20 review passed the other names, the lines for a floor on an added level and every other line below.
  // C637: a sample's refusal doesn't ask a judge to retake a photo they didn't take, so D19's line sits inside a frame.
  'refusal.sample.cantTell': { text: "Lusot can't tell from this photo.", reviewed: true },
  'refusal.sample.someoneWouldSee': { text: 'Someone reporting this spot would see:', reviewed: true },
  'result.levelName.below_gutter': { text: 'below gutter', reviewed: true },
  'result.levelName.gutter': { text: 'gutter', reviewed: true },
  'result.levelName.half_knee': { text: 'half-knee', reviewed: true },
  'result.levelName.half_tire': { text: 'half-tire', reviewed: true },
  'result.levelName.knee': { text: 'knee', reviewed: true },
  'result.levelName.tire': { text: 'tire', reviewed: true },
  'result.levelName.waist': { text: 'waist', reviewed: true },
  'result.levelName.chest': { text: 'chest', reviewed: true },
  'result.levelName.above_chest': { text: 'above chest', reviewed: true },
  'result.level.exact': { text: '{level} deep at this spot (MMDA level).', reviewed: true },
  'result.level.floor': { text: 'At least {level} deep at this spot (MMDA level).', reviewed: true },
  // The two levels that aren't MMDA's drop "(MMDA level)" (CLAUDE.md, C81).
  'result.level.off': { text: '{level} deep at this spot.', reviewed: true },
  'result.level.offFloor': { text: 'At least {level} deep at this spot.', reviewed: true },
  // The class line is what MMDA lists, never a verdict on the spot (plan §9, C81). C81 spells out the NPLV line
  // and the two added levels' lines; the PATV and NPATV lines follow plan §9, Table 10.
  'result.class.patv': { text: 'MMDA lists this level as passable to all vehicles (PATV).', reviewed: true },
  'result.class.nplv': { text: 'MMDA lists this level as not passable to light vehicles (NPLV).', reviewed: true },
  'result.class.npatv': { text: 'MMDA lists this level as not passable to any vehicle (NPATV).', reviewed: true },
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
    text: "Water reaches the tire of a parked car's wheel, below its rim.",
    reviewed: true,
  },
  'result.landmark.rim_quarter': {
    text: "Water reaches a quarter of the way up a parked car's wheel rim.",
    reviewed: true,
  },
  'result.landmark.hub': { text: "Water reaches the hub, about halfway up a parked car's wheel.", reviewed: true },
  'result.landmark.rim_three_quarters': {
    text: "Water reaches three quarters of the way up a parked car's wheel rim.",
    reviewed: true,
  },
  'result.landmark.rim_top': { text: "Water reaches the top of a parked car's wheel rim.", reviewed: true },
  'result.landmark.wheel_covered': { text: "Water covers a parked car's wheel completely.", reviewed: true },
  'result.landmark.mid_door': { text: "Water reaches the middle of a parked car's doors.", reviewed: true },
  'result.landmark.window': { text: 'Water reaches the windows of a parked car.', reviewed: true },
  'result.landmark.ankle': { text: 'Water reaches the ankles of an adult in the photo.', reviewed: true },
  'result.landmark.mid_shin': {
    text: 'Water reaches the middle of the shins of an adult in the photo.',
    reviewed: true,
  },
  'result.landmark.knee': { text: 'Water reaches the knees of an adult in the photo.', reviewed: true },
  'result.landmark.mid_thigh': {
    text: 'Water reaches the middle of the thighs of an adult in the photo.',
    reviewed: true,
  },
  'result.landmark.waist': { text: 'Water reaches the waist of an adult in the photo.', reviewed: true },
  'result.landmark.chest': { text: 'Water reaches the chest of an adult in the photo.', reviewed: true },
  'result.landmark.above_chest': {
    text: 'Water reaches above the chest of an adult in the photo.',
    reviewed: true,
  },
  'result.basis.one': { text: 'From {count} reference object.', reviewed: true },
  'result.basis.other': { text: 'From {count} reference objects.', reviewed: true },
  // Only when the API sends both ends, which happens only after the release gate passes (C515).
  'result.inches.range': { text: 'Estimated {min} to {max} in.', reviewed: true },
  'result.inches.same': { text: 'Estimated {min} in.', reviewed: true },
  // Shown only when geometry set the level (MS3b's C320, C328).
  'result.levelFrom.geometry': { text: 'Measured from the size of the wheel rim.', reviewed: true },
  // The three outcomes keep their own lines (CLAUDE.md): no flood seen, processing failed, and can't tell
  // ('refusal.d19', then a reason line).
  'result.noFlood': { text: 'No flood seen at this spot.', reviewed: true },
  'result.failed': { text: 'Processing failed, try again.', reviewed: true },
  'result.private': {
    text: "Taken outside Metro Manila, so only you see this result. It isn't on the map.",
    reviewed: true,
  },
  'result.noResult': { text: 'No result yet. The analysis is taking longer than usual.', reviewed: true },
  'result.checkAgain': { text: 'Check again', reviewed: true },
  'result.tryAgain': { text: 'Try again', reviewed: true },
  // A pause reads as a pause, never as "Processing failed" (C638, amendment 7). It is shown whatever set the switch,
  // so it names no cause. Its Taglish is spec C638's draft, and it isn't a screen-line key, so it shows in Taglish.
  'result.paused': {
    text: 'New analyses are paused right now. The map and the Tested page still work.',
    reviewed: true,
  },
  // "Photo taken 25 min ago. Location within 12 m." (plan Table 6): the age is one of the four lines below.
  'result.photoTaken': { text: 'Photo taken {age}.', reviewed: true },
  'result.accuracy': { text: 'Location within {m} m.', reviewed: true },
  'result.age.justNow': { text: 'just now', reviewed: true },
  'result.age.minutes': { text: '{min} min ago', reviewed: true },
  'result.age.hours': { text: '{h} h ago', reviewed: true },
  'result.age.hoursMinutes': { text: '{h} h {min} min ago', reviewed: true },
  // The "Details" disclosure: the reason code and the photo's time, never a report id or an error message (C610).
  'result.details': { text: 'Details', reviewed: true },
  'result.details.reason': { text: 'Reason code: {code}', reviewed: true },
  'result.details.photoTime': { text: 'Photo time: {time}', reviewed: true },
  'result.details.references': { text: 'Reference objects', reviewed: true },
  'result.reference': { text: 'Reference {id}:', reviewed: true },
  // One plain line for each refusalReason of MS3a's §3.4, and MS1's pipeline_not_built. None tells anyone to go
  // near water or traffic (plan §13). 'reason.other' stands in for any code the app doesn't know, so no raw code
  // is ever shown.
  'reason.too_dark': { text: 'The photo is too dark to read.', reviewed: true },
  'reason.too_blurry': { text: 'The photo is too blurry to read.', reviewed: true },
  'reason.photo_unusable': { text: "The photo doesn't show a spot that Lusot can read.", reviewed: true },
  'reason.water_unsure': {
    text: "Lusot couldn't tell whether there is standing water in the photo.",
    reviewed: true,
  },
  'reason.no_water_found': {
    text: "Lusot couldn't outline the water in the photo, so it can't read the depth.",
    reviewed: true,
  },
  'reason.no_usable_reference': {
    text: 'No car or person in the photo could be used to read the depth.',
    reviewed: true,
  },
  'reason.references_disagree': {
    text: 'The cars and people in the photo give depths more than one level apart.',
    reviewed: true,
  },
  'reason.model_declined': { text: 'The reading model declined to answer for this photo.', reviewed: true },
  'reason.model_calls_paused': { text: 'New analyses are paused right now.', reviewed: true },
  'reason.photo_missing': { text: "Lusot couldn't find the uploaded photo.", reviewed: true },
  'reason.bad_file': { text: "The photo's file couldn't be read.", reviewed: true },
  'reason.model_error': { text: 'The reading model had an error.', reviewed: true },
  'reason.pipeline_error': { text: 'Lusot had an error while analyzing the photo.', reviewed: true },
  'reason.pipeline_not_built': {
    text: "This report came from an early test build that didn't analyze photos.",
    reviewed: true,
  },
  'reason.other': { text: 'No further reason is available.', reviewed: true },
  // Why a numbered reference wasn't used (amendment 2): one line per cause the pipeline writes (copy/levels.ts), each
  // starting "Not used". 'dropped.other' stands in for any cause the app doesn't know, so no code is ever shown.
  'dropped.vehicle_unanswered': {
    text: 'Not used, since the reading model gave no answer for this vehicle.',
    reviewed: true,
  },
  'dropped.vehicle_moving': { text: 'Not used, since the vehicle may be moving.', reviewed: true },
  'dropped.vehicle_type': { text: "Not used, since this type of vehicle can't give a reading.", reviewed: true },
  'dropped.vehicle_body_below_covered_wheel': {
    text: "Not used, since the readings from this vehicle's body and wheels don't match.",
    reviewed: true,
  },
  'dropped.vehicle_wheels_disagree': {
    text: "Not used, since this vehicle's wheels gave different readings.",
    reviewed: true,
  },
  'dropped.vehicle_no_reading': { text: 'Not used, since this vehicle gave no depth reading.', reviewed: true },
  'dropped.wheel_vehicle_dropped': { text: "Not used, since this wheel's vehicle wasn't used.", reviewed: true },
  'dropped.wheel_unanswered': {
    text: 'Not used, since the reading model gave no answer for this wheel.',
    reviewed: true,
  },
  'dropped.wheel_methods_disagree': {
    text: 'Not used, since the two ways of reading this wheel gave different depths.',
    reviewed: true,
  },
  'dropped.person_unanswered': {
    text: 'Not used, since the reading model gave no answer for this person.',
    reviewed: true,
  },
  'dropped.person_not_adult': { text: 'Not used, since this person may not be an adult.', reviewed: true },
  'dropped.person_wading': { text: 'Not used, since this person may not be standing still.', reviewed: true },
  'dropped.person_no_reading': { text: 'Not used, since this person gave no depth reading.', reviewed: true },
  'dropped.no_water_contact': {
    text: "Not used, since the water doesn't clearly touch this reference.",
    reviewed: true,
  },
  'dropped.ragged_waterline': {
    text: "Not used, since the waterline against this reference isn't clear.",
    reviewed: true,
  },
  'dropped.other': { text: 'Not used for this reading.', reviewed: true },
  // A sample or a demo pin (C617, C618, C637): a credited photo that Lusot blurred and drew on, read live or saved.
  'badge.sample': { text: 'Sample', reviewed: true },
  'badge.demo': { text: 'Demo', reviewed: true },
  'sample.photoAlt': { text: 'The photo, with faces and plates blurred.', reviewed: true },
  'sample.photoFrom': { text: 'Photo from {parts}', reviewed: true },
  'sample.edited': { text: 'Lusot blurred the faces and plates in this photo.', reviewed: true },
  // Said after 'sample.edited' only when the result has outlines to show (the card checks).
  'sample.outlines': { text: 'Lusot drew its outlines on it.', reviewed: true },
  'sample.liveReading': {
    text: 'This is a live reading of a credited photo, not a test result.',
    reviewed: true,
  },
  'sample.savedReading': {
    text: 'This is a saved reading of a credited photo, not a test result.',
    reviewed: true,
  },
  'sample.savedFrom': { text: 'Saved result from {date}', reviewed: true },
  // The gauge's captions, beside its cells (the gauge is hidden from screen readers; the level line says it all).
  'gauge.outside': { text: "Outside MMDA's gauge", reviewed: true },
  'gauge.orDeeper': { text: 'or deeper', reviewed: true },
  // The live map, its list and pin detail (MS5 Task 13). Every line that says what a pin shows keeps "at this spot"
  // through the level line, and none says anything about a place with no report, since no report is not a dry spot.
  'map.noApi': { text: "This build can't show reports.", reviewed: false },
  'map.loading': { text: 'Loading reports.', reviewed: false },
  'map.loadFailed': { text: "Lusot couldn't load the reports just now. It will try again.", reviewed: false },
  'map.viewGroup': { text: 'Show reports as', reviewed: false },
  'map.list': { text: 'List', reviewed: false },
  'map.listLabel': { text: 'Reports, newest first', reviewed: false },
  'map.mapLabel': { text: 'Map of reports', reviewed: false },
  'map.locate': { text: 'Locate me', reviewed: false },
  'map.zoomIn': { text: 'Zoom in', reviewed: false },
  'map.zoomOut': { text: 'Zoom out', reviewed: false },
  // The map's own way in to the report flow. It is not named 'Report', as the bar's link is, so the two don't read alike.
  'map.report': { text: 'Report a spot', reviewed: false },
  'map.own': { text: 'Your report', reviewed: false },
  'map.back': { text: 'Back to the map', reviewed: false },
  // The empty map (C618): an invitation, with one card that says it is an example and is never pinned.
  'map.empty.title': { text: 'No reports in the last 3 hours', reviewed: false },
  'map.empty.note': { text: 'A spot with no report may still be flooded.', reviewed: false },
  'map.trySample': { text: 'Try a sample', reviewed: false },
  'badge.example': { text: 'Example', reviewed: false },
  'map.example.note': { text: 'An example of a reading, not a report from anywhere.', reviewed: false },
  'pin.gone': { text: 'This pin is no longer on the map.', reviewed: false },
  'pin.loading': { text: 'Loading this pin.', reviewed: false },
  'pin.loadFailed': { text: "Lusot couldn't load this pin just now.", reviewed: false },
  'pin.photoFailed': { text: "Lusot couldn't load the photo just now.", reviewed: false },
  'pin.nearby': { text: 'Other reports within 300 m, last 3 hours: {count}', reviewed: false },
  'pin.flags.one': { text: '1 phone has flagged this report as wrong or fake.', reviewed: false },
  'pin.flags.other': { text: '{count} phones have flagged this report as wrong or fake.', reviewed: false },
  'pin.flag': { text: 'Flag as wrong or fake', reviewed: false },
  'pin.flagged': { text: 'Flagged', reviewed: false },
  'pin.flagFailed': { text: "Lusot couldn't send the flag. Try again.", reviewed: false },
  // The flag's confirmation, in a dialog of the app's own (C613).
  'flag.title': { text: 'Flag this report?', reviewed: false },
  'flag.body': {
    text: "Flag it if the reading looks wrong or the photo looks fake. A flag adds to the count shown on this pin. It doesn't remove the pin.",
    reviewed: false,
  },
  'flag.confirm': { text: 'Flag it', reviewed: false },
  'flag.cancel': { text: 'Cancel', reviewed: false },
} satisfies Record<string, Entry>

export type StringKey = keyof typeof EN
