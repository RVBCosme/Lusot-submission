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
  'nav.ask': { text: 'Ask', reviewed: true },
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
  'report.sendFailed': { text: "Lusot couldn't send the photo. Try again.", reviewed: true },
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
    reviewed: true,
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
  // The licences page (C636): the build writes the packages' texts to licences.txt; these lines frame them and name the
  // sources that aren't packages.
  'licences.intro': { text: 'The code and fonts Lusot is built from, each with the full text of its licence.', reviewed: true },
  'licences.loading': { text: 'Loading the licence texts.', reviewed: true },
  'licences.unavailable': { text: 'The licence texts could not be loaded.', reviewed: true },
  'licences.textLabel': { text: 'Licence texts', reviewed: true },
  'licences.otherTitle': { text: 'Other sources', reviewed: true },
  'licences.osm': {
    text: 'Map data © OpenStreetMap contributors, under the Open Database License (ODbL). The map tiles come from OpenStreetMap, under its Tile Usage Policy.',
    reviewed: true,
  },
  'licences.osmLink': { text: 'OpenStreetMap copyright and licence', reviewed: true },
  'licences.samples': { text: 'Each sample photo carries its own credit, shown with that sample.', reviewed: true },
  'licences.packagesTitle': { text: 'Packages the app is built from', reviewed: true },
  'licences.packagesNote': {
    text: "The app's production packages, as npm lists them. The list includes the package the Android app is built on, and packages that only describe types and don't ship in the page.",
    reviewed: true,
  },
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
  // The overlay drawn over the photo (MS5 Task 14, C615). A reference's label is built from these, the landmark lines and
  // the drop-cause lines above. A floor reads as the result card does ("At least {level}"), and none of these names a
  // road or tells anyone to go anywhere. All wait for Rene's copy review.
  'overlay.title': { text: "Lusot's outlines on the photo", reviewed: true },
  'overlay.ref.wheel': { text: 'Wheel {id}', reviewed: true },
  'overlay.ref.body': { text: 'Car body {id}', reviewed: true },
  'overlay.ref.person': { text: 'Person {id}', reviewed: true },
  'overlay.floor': { text: 'At least {level}', reviewed: true },
  'overlay.notUsed': { text: 'Not used', reviewed: true },
  // The live map, its list and pin detail (MS5 Task 13). Every line that says what a pin shows keeps "at this spot"
  // through the level line, and none says anything about a place with no report, since no report is not a dry spot.
  'map.noApi': { text: "This build can't show reports.", reviewed: true },
  'map.loading': { text: 'Loading reports.', reviewed: true },
  'map.loadFailed': { text: "Lusot couldn't load the reports just now. It will try again.", reviewed: true },
  'map.viewGroup': { text: 'Show reports as', reviewed: true },
  'map.list': { text: 'List', reviewed: true },
  'map.listLabel': { text: 'Reports, newest first', reviewed: true },
  'map.mapLabel': { text: 'Map of reports', reviewed: true },
  'map.locate': { text: 'Locate me', reviewed: true },
  'map.zoomIn': { text: 'Zoom in', reviewed: true },
  'map.zoomOut': { text: 'Zoom out', reviewed: true },
  // The map's own way in to the report flow. It is not named 'Report', as the bar's link is, so the two don't read alike.
  'map.report': { text: 'Report a spot', reviewed: true },
  'map.own': { text: 'Your report', reviewed: true },
  'map.back': { text: 'Back to the map', reviewed: true },
  // The empty map (C618): an invitation, with one card that says it is an example and is never pinned.
  'map.empty.title': { text: 'No reports in the last 3 hours', reviewed: true },
  'map.empty.note': { text: 'A spot with no report may still be flooded.', reviewed: true },
  'map.trySample': { text: 'Try a sample', reviewed: true },
  'badge.example': { text: 'Example', reviewed: true },
  'map.example.note': { text: 'An example of a reading, not a report from anywhere.', reviewed: true },
  'pin.gone': { text: 'This pin is no longer on the map.', reviewed: true },
  'pin.loading': { text: 'Loading this pin.', reviewed: true },
  'pin.loadFailed': { text: "Lusot couldn't load this pin just now.", reviewed: true },
  'pin.photoFailed': { text: "Lusot couldn't load the photo just now.", reviewed: true },
  'pin.nearby': { text: 'Other reports within 300 m, last 3 hours: {count}', reviewed: true },
  'pin.flags.one': { text: '1 phone has flagged this report as wrong or fake.', reviewed: true },
  'pin.flags.other': { text: '{count} phones have flagged this report as wrong or fake.', reviewed: true },
  'pin.flag': { text: 'Flag as wrong or fake', reviewed: true },
  'pin.flagged': { text: 'Flagged', reviewed: true },
  'pin.flagFailed': { text: "Lusot couldn't send the flag. Try again.", reviewed: true },
  // The flag's confirmation, in a dialog of the app's own (C613).
  'flag.title': { text: 'Flag this report?', reviewed: true },
  'flag.body': {
    text: "Flag it if the reading looks wrong or the photo looks fake. A flag adds to the count shown on this pin. It doesn't remove the pin.",
    reviewed: true,
  },
  'flag.confirm': { text: 'Flag it', reviewed: true },
  'flag.cancel': { text: 'Cancel', reviewed: true },
  // The Tested page (MS5 Task 15, C616): how Lusot is tested, its figures once the sealed run is done, its known limits
  // and the samples. Its figures are "agreement with the labels MMDA and the cities posted", each "indicative" and with
  // its n; the page never says "accuracy". The known limits match the privacy policy's words on the face blur.
  'tested.how.title': { text: 'How Lusot is tested', reviewed: true },
  'tested.how.labels': {
    text: "Lusot's readings are compared with the flood levels that MMDA and the cities posted with their own photos.",
    reviewed: true,
  },
  'tested.how.sealed': {
    text: "Some of those photos were set aside and sealed before any tuning. They are scored once, with Lusot's settings frozen, and any rerun is disclosed with its reason.",
    reviewed: true,
  },
  'tested.how.rules': { text: 'The scoring rules were fixed and approved before any result was seen.', reviewed: true },
  'tested.how.cars': {
    text: 'The wheel-rim measurement is also tested on photos of parked cars, with water drawn in at known depths.',
    reviewed: true,
  },
  'tested.results.title': { text: 'Results', reviewed: true },
  'tested.pending': { text: 'The results appear here after the sealed run on Nov 3.', reviewed: true },
  'tested.results.from': { text: 'From the sealed run on {date}.', reviewed: true },
  'tested.results.rerunFrom': {
    text: 'From the rerun on {date}, the one rerun the scoring rules allow.',
    reviewed: true,
  },
  'tested.results.intro': {
    text: 'Each figure shows how often Lusot agreed with the labels MMDA and the cities posted, and how many photos it counts. With this few photos, every figure is indicative.',
    reviewed: true,
  },
  'tested.shipped.landmark': {
    text: 'These figures are for Lusot as it ships: reading the depth from wheels and people.',
    reviewed: true,
  },
  'tested.shipped.geometry': {
    text: 'These figures are for Lusot as it ships: reading the depth from wheels and people, and measuring the wheel rim.',
    reviewed: true,
  },
  'tested.figure.underestimation': { text: 'Read shallower than the label (lower is better)', reviewed: true },
  'tested.figure.passability': { text: 'Same passability class as the label', reviewed: true },
  'tested.figure.coverage': { text: 'Photos answered, not refused', reviewed: true },
  'tested.figure.exact': { text: 'Same level as the label', reviewed: true },
  'tested.figure.withinOne': { text: 'Within one level of the label', reviewed: true },
  // A rate: "12 of 20 (60%)", and "0 of 0" with no share.
  'tested.rate': { text: '{k} of {n} ({percent}%)', reviewed: true },
  'tested.rateNoShare': { text: '{k} of {n}', reviewed: true },
  'tested.indicative': { text: 'indicative', reviewed: true },
  'tested.inches.shown': {
    text: 'Inches are shown: the wheel-rim measurement passed its release check.',
    reviewed: true,
  },
  'tested.inches.notShown': {
    text: "Inches aren't shown: the wheel-rim measurement didn't pass its release check.",
    reviewed: true,
  },
  'tested.setB.title': { text: 'Wheel-rim measurement on parked cars', reviewed: true },
  'tested.setB.median': { text: 'Median error', reviewed: true },
  'tested.setB.medianValue': { text: '{inches} in, over {n} wheels', reviewed: true },
  'tested.setB.measured': { text: 'Wheels measured', reviewed: true },
  'tested.reportLink': { text: 'Read the full test report', reviewed: true },
  'tested.limits.title': { text: 'Known limits', reviewed: true },
  'tested.limits.night': {
    text: 'At night, a photo that is too dark is refused, and a dim one is harder to read.',
    reviewed: true,
  },
  'tested.limits.rain': { text: 'Rain on the lens, or heavy rain, can hide where the water reaches.', reviewed: true },
  'tested.limits.blur': { text: 'A photo that is too blurry is refused.', reviewed: true },
  'tested.limits.faceBlur': {
    text: 'The automatic face blur can miss some faces: very small, side-on, partly covered or in the dark. A face it misses reaches Meta unblurred.',
    reviewed: true,
  },
  'tested.samples.title': { text: 'Samples', reviewed: true },
  'tested.samples.intro': {
    text: "Credited flood photos you can run through Lusot. A run gives a live reading of the credited photo, or a saved one while new analyses are paused. A sample's result never goes on the map.",
    reviewed: true,
  },
  'tested.samples.loading': { text: 'Loading samples.', reviewed: true },
  // Only when the list is short (fewer than 3) or empty, and in place of any error (amendment 11).
  'tested.samples.more': { text: 'More samples coming.', reviewed: true },
  'tested.samples.noApi': { text: "This build can't run samples.", reviewed: true },
  // A sample's run (C617). Each run spends Meta credits, so a run that may have started is never offered again on the
  // spot, and a limit names no time, since the API's reset may differ.
  'sample.run': { text: 'Run this sample', reviewed: true },
  'sample.reading': { text: 'Lusot is reading this sample.', reviewed: true },
  'sample.unanswered': {
    text: "Lusot didn't get a usable answer. The run may have started and may still finish, but this page can't show its result.",
    reviewed: true,
  },
  'sample.gone': { text: 'This sample is no longer available.', reviewed: true },
  'sample.failed': { text: "Lusot couldn't run this sample just now.", reviewed: true },
  'sample.limit.device_limit': {
    text: 'This phone has run as many samples as Lusot allows in an hour. Try again later.',
    reviewed: true,
  },
  'sample.limit.global_cap': {
    text: 'Lusot has run as many samples as it can for now. Try again later.',
    reviewed: true,
  },
  // Ask Lusot (its spec §4.4, §4.10, plan Task 14): the screen's controls and errors (ask.ui., ask.error.), and the
  // answer's lines (ask.answer.), which are screen-line keys, so their Taglish shows only once reviewed (C724). The
  // answer's level and class lines are MS5's own (copy/wording.ts). Every one waits for Rene's review (M20).
  'ask.ui.placeholder': { text: 'Ask about flood depth at a place', reviewed: true },
  'ask.ui.send': { text: 'Ask', reviewed: true },
  'ask.ui.mic': { text: 'Ask by voice', reviewed: true },
  'ask.ui.micStop': { text: 'Stop', reviewed: true },
  'ask.ui.micLeft': { text: '{s} s left', reviewed: true },
  'ask.ui.location': { text: 'Use my location', reviewed: true },
  'ask.ui.locationWaiting': { text: 'Finding your location…', reviewed: true },
  'ask.ui.locationPoor': {
    text: "Your location isn't within 100 m yet. Try under open sky, or name a place.",
    reviewed: true,
  },
  'ask.ui.locationTurnOn': {
    text: 'Lusot needs location turned on to use it in a question. Turn it on when your phone asks, then try again, or name a place.',
    reviewed: true,
  },
  'ask.ui.youAsked': { text: 'You asked:', reviewed: true },
  'ask.ui.notice': { text: "Your question goes to Meta's AI service. Lusot doesn't keep it.", reviewed: true },
  'ask.ui.attribution': { text: 'Place search © OpenStreetMap contributors', reviewed: true },
  'ask.ui.used': { text: 'Used', reviewed: true },
  'ask.ui.openPin': { text: 'Open this pin', reviewed: true },
  'ask.ui.example1': { text: 'Gaano kalalim ang baha sa España cor. Maceda?', reviewed: true },
  'ask.ui.example2': { text: 'May baha ba dito?', reviewed: true },
  'ask.ui.example3': { text: 'How deep is it at G. Araneta Ave cor. E. Rodriguez Sr. Ave?', reviewed: true },
  'ask.ui.questionLabel': { text: 'Your question', reviewed: true },
  'ask.ui.asking': { text: 'Looking up recent reports…', reviewed: true },
  'ask.ui.examples': { text: 'Try asking:', reviewed: true },
  'ask.ui.noApi': { text: "This build can't ask questions.", reviewed: true },
  'ask.ui.answer': { text: 'Answer', reviewed: true },
  'ask.ui.suggestionQuestion': { text: 'How deep is it at {spot}?', reviewed: true },
  'ask.error.questionLimit': { text: "You've asked 20 questions this hour. Try again in {min} min.", reviewed: true },
  'ask.error.questionCap': {
    text: 'Ask Lusot has reached its limit for this hour. Try again in {min} min.',
    reviewed: true,
  },
  'ask.error.voicePaused': {
    text: 'Voice questions are paused right now. Type your question instead.',
    reviewed: true,
  },
  'ask.error.voiceFailed': { text: "Lusot couldn't hear the question. Try again, or type it.", reviewed: true },
  'ask.error.unavailable': { text: "Ask Lusot can't answer right now. Try again in a minute.", reviewed: true },
  'ask.error.micDenied': {
    text: "Lusot can't use the microphone. Allow it for this page or app in your browser or phone settings to ask by voice, or type your question.",
    reviewed: true,
  },
  'ask.error.micUnavailable': {
    text: "This phone or browser can't record a question here. Type your question instead.",
    reviewed: true,
  },
  'ask.answer.crossing': { text: "I can't tell you whether to cross or go through.", reviewed: true },
  'ask.answer.summaryOne': { text: '1 report within 300 m of {place} in the last {window}.', reviewed: true },
  'ask.answer.summaryMany': { text: '{n} reports within 300 m of {place} in the last {window}.', reviewed: true },
  'ask.answer.summaryHereOne': { text: '1 report within 300 m of you in the last {window}.', reviewed: true },
  'ask.answer.summaryHereMany': { text: '{n} reports within 300 m of you in the last {window}.', reviewed: true },
  'ask.answer.where': { text: 'Photo taken {age}, {distance} m from {place}.', reviewed: true },
  'ask.answer.whereHere': { text: 'Photo taken {age}, {distance} m from you.', reviewed: true },
  'ask.answer.vehicleLight': {
    text: "For MMDA's classes, Lusot counts your vehicle as a light vehicle.",
    reviewed: true,
  },
  'ask.answer.vehicleHeavy': {
    text: "For MMDA's classes, Lusot counts your vehicle as a heavy vehicle.",
    reviewed: true,
  },
  'ask.answer.onFoot': {
    text: "MMDA's classes are for vehicles, so this answer gives the level only.",
    reviewed: true,
  },
  'ask.answer.demo': { text: '(demo)', reviewed: true },
  'ask.answer.noReports': { text: 'No recent reports within 300 m of {place} in the last {window}.', reviewed: true },
  'ask.answer.noReportsHere': { text: 'No recent reports within 300 m of you in the last {window}.', reviewed: true },
  'ask.answer.noReportNote': { text: "No report doesn't mean no flood.", reviewed: true },
  'ask.answer.tooBroad': {
    text: "That's a whole street or area. Ask about a corner or a landmark on it, or turn on your location and ask about \"dito\".",
    reviewed: true,
  },
  'ask.answer.noPlace': {
    text: "I couldn't find that place in Metro Manila. Name a corner or a landmark, or turn on your location and ask about \"dito\".",
    reviewed: true,
  },
  'ask.answer.lookupUnavailable': {
    text: "I couldn't look up that place just now. Try again in a minute, or name a nearby landmark.",
    reviewed: true,
  },
  'ask.answer.outside': { text: 'Lusot answers only about spots in Metro Manila.', reviewed: true },
  'ask.answer.noLocation': { text: 'Turn on your location to ask about "dito", or name a place.', reviewed: true },
  'ask.answer.offTopic': {
    text: 'I can only answer about flood depth near a place in Metro Manila, from recent reports.',
    reviewed: true,
  },
  'ask.answer.noSpeech': { text: "I didn't catch a question. Try again, or type it.", reviewed: true },
  'ask.answer.plainList': { text: 'Here is the plain list of reports.', reviewed: true },
  'ask.window.hours': { text: '{n} hours', reviewed: true },
  'ask.window.hour': { text: '1 hour', reviewed: true },
  'ask.window.minutes': { text: '{n} minutes', reviewed: true },
  'ask.window.minute': { text: '1 minute', reviewed: true },
} satisfies Record<string, Entry>

export type StringKey = keyof typeof EN
