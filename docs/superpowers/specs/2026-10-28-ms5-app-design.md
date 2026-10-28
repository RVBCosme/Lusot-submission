# MS5 App: spec

- **Date:** Oct 28, 2026 (Manila), written from 11:05 PM
- **Status:** Draft. Written overnight without a live conversation, under Rene's instruction (D7, D15). Claude proceeds on the calls in §6 and the defaults in §8 until Rene approves. Building follows those defaults (D7).
- **Checked before commit:** a fresh accuracy review (Opus 5.5 at max, 11:43 PM: 12 Important and 10 Minor findings, all fixed) and a builder check (Oct 29, 12:08 AM: 3 questions, all settled in §12).
- **Implements:**
  - design §8's MS5 row, with G1 (demo pins), D8 (shells on mock data may start early), D10 and C20 (the disclosure, worded for the face blur), D14 and C21 (the private result screen) and C17 (`levelIsFloor`)
  - plan §4 (the app's must-haves and should-haves), §6 (Tables 4 and 6), §9 (output rules), §12 (Table 15, as the app uses it), §13 (consent, privacy page, safety), §18 (the checklist and Table 19's app scenes), §19 (Tables 20 and 21), §20 (Table 22, Phase 5) and §24 (M14 to M17, M20, M21, M28)
  - Rene's Oct 28 decisions: keep React and Capacitor; English with a Taglish switch (R3's language half); samples and demo pins may use CC0 and CC BY photos marked `demo_use ok`, credited and blurred, never CC BY-SA (8:26 PM); R3's visual half is his, asked here as MS5-Q1
  - the deferred items routed to MS5 in the Oct 28 log ("Deferred, with target"), W20's picker note, and R44's copy check
- **Builds on:**
  - MS1's app (§3.6, C27, C33) and MS3a's test screen (§3.8, C50, C67, C81), which this milestone replaces. MS3a's code, `quality.py` included, reaches `main` when MS3a closes.
  - MS3a's run deadline (C84, C88), MS3b's inches and `levelFrom` (C307, C308, C320), MS6's summary file (C409) and latency rows (C416), and Window 4's privacy and consent drafts (`docs/drafts/` on `w4-independent`)
  - Window 4's MS4 draft (`docs/superpowers/specs/2026-10-28-ms4-backend-design.md` in `lusot-wt\ms4`, uncommitted at 10:51 PM, calls C500 to C517). Where it defines the API, MS5 follows it. §5 lists what MS5 still needs from it, and from MS6.

## 1. Intent

MS5 turns the test screen into the app people and judges use. A person in a flood takes a photo in the app, sees MMDA's level at that spot with the evidence behind it, or an honest "can't tell", and sees it join a live map of other spots. A judge far from any flood opens the web URL, presses a sample, and watches the real pipeline read a real flood photo.

Three things make it worth judging, and every choice below serves one of them:
- **It speaks only in MMDA's terms, at one spot.** The words, the gauge and the map never say more than the reading supports (CLAUDE.md's product rules, plan §9).
- **It shows its work.** Each reading shows the landmark it came from and, where allowed, the outlines drawn on the blurred photo (plan Table 21).
- **It works for real people outdoors.** Big readable type in daylight and at night, a camera that only takes fresh photos, a GPS check, Taglish, and a waiting screen that never claims a failure it hasn't seen.

## 2. Goals, non-goals, anti-goals

**Goals**
- The screens in design §8's MS5 row: consent with the 18+ check, capture with the phone's quality check, the pin map, pin detail with an overlay that draws itself, the result and refusal screens, the Tested page (the plan's accuracy page) with its sample button, the privacy policy page, and the private result screen.
- The web URL live as an installable PWA, and the Capacitor APK installed on a real phone.
- The five-person user test (M17) run on this build, with one change made from it.

**Non-goals**
- Anything that changes how depth is measured (design §8's freeze). MS5 reads results; it computes none.
- Ask Lusot's screen, tool and voice (MS6). MS5 leaves a slot in the navigation, and the consent gate covers it.
- The plan's nice-to-haves: the share card, the offline queue, the MMDA alert layer, the Messenger bot (plan §4).
- A native iOS app (design §3).

**Anti-goals** (failures even if the app works)
- Any screen without the exact safety line, any use of the word "safe", any crossing advice, or any wording about a whole road (CLAUDE.md).
- A level word outside the 9 levels, a class outside MMDA's 3, or a word or picture that presents the 9 levels as MMDA's.
- Showing "processing failed" when the server hasn't said so, or offering a retry that pays Meta again for the same photo.
- A gallery photo or an old file becoming a live pin (W20), or a sample's old photo shown as if it were taken now.
- A report id in an app route, an app log or any public response (MS4's C504).
- A demo or sample photo shown without its credit line, or any CC BY-SA photo shown at all.
- A fake pin on the map: a test upload, a staged photo or a demo pin passed off as current.

## 3. Constraints

- CLAUDE.md's rules hold throughout. The ones that bite here: the product rules, every screen's safety line, no photo or exact location in any log, nothing that calls Meta from the app, and Rene's review of the Taglish lines, refusals and safety line (M20).
- **The safety line,** exactly as CLAUDE.md gives it: "Lusot estimates depth at one spot. It is not advice to cross. Follow MMDA and local advisories."
- **Stack:** React 19, Vite 8, TypeScript 7, Tailwind CSS 4 and Capacitor 8.5, as MS1 pinned them in `app/package.json`. Leaflet with OpenStreetMap tiles for the map (CLAUDE.md "Stack"). Every new library is checked with Context7 for the version installed, pinned in the lockfile and credited in the README.
- **Dates:** MS5 runs Nov 1 to 3 (design §8). Shells on mock data may start from Oct 29, only beside backend work (D8). MS4's API lands Oct 31 to Nov 1, so the screens are built against a mock API first (C628).
- **Budget:** the app never calls Meta. MS5's own live checks spend at most about $3 of credits in all (C630).
- **Time to a result:** one analysis takes about 35 to 45 s at Muse Spark's default effort: about 8 s for SAM's phrases at 1,600 px (MS3a's C88) and a median of about 25 s for Muse Spark (C68, MS3b-Q3), plus the queue and a cold start. A run stops at about 150 s (C84, C88), and the Lambda's timeout is 180 s. Under a rush, the queue adds minutes (C601). The plan's "photo to pin under 10 s" is a should-have that MS5 measures but can't change (C631).

## 4. What gets built

### 4.1 The screens and the flow

| Screen | What it shows | Notes |
|---|---|---|
| **Map** (home) | Live pins from the last 3 hours and labelled demo pins (G1), on OpenStreetMap; a list view of the same pins; a "Report" action | C612, C618 |
| **Consent** | The 18+ check before any action that calls Meta, and Window 4's consent notice before the first upload or question | C605 |
| **Report: camera** | A live camera view inside the app, on the web and in the APK alike; the GPS fix starts at the same time | C602, C603 |
| **Report: check** | The phone's quality check; a retake tip when the photo is too dark or blurry | C604 |
| **Report: place** | The pin on a small map with its accuracy circle; drag to move it up to 100 m; "Send" | C603 |
| **Report: waiting** | What is happening, with elapsed time; never a failure the server hasn't reported | C601, C635 |
| **Result** | The result card (§4.2) with the overlay for a level result; links to the map and to MMDA's and PAGASA's advisories | C610, C613, C615 |
| **Pin detail** | The same result card for a pin on the map, with its age, how many other reports lie nearby, a Demo badge where it applies, and a flag button on live pins | C613, C614 |
| **Tested** | The evaluation's headline figures with their sample sizes, how Lusot was tested, its known limits, and the samples, each with its blurred photo | C616, C617 |
| **Sample result** | The result card with a Sample badge, the blurred photo, its own place and date, and its credit line; never pinned | C617, C637 |
| **About** | What Lusot is, the language and theme choices, the privacy policy link, credits, the open-source licences, "Not affiliated with MMDA." | C619, C633, C636 |
| **Privacy policy** | Window 4's policy as Rene approves it (M21) | C605 |

The bottom navigation has Map, Report, Tested and About. MS6 adds Ask as the fifth (C620). Every screen, dialog and camera view carries the safety line, visible without scrolling (C608).

### 4.2 The result card

One component serves the result screen, pin detail and sample results, so every reading is worded the same way. It follows plan Table 6's parts, kept separate as plan §6 says: what the photo shows, Lusot's estimate, and MMDA's terms.

| Part | English draft | Source |
|---|---|---|
| Level line | "Knee deep at this spot (MMDA level)." The two added levels drop "(MMDA level)". A floor reads "At least tire deep at this spot (MMDA level)." | MS3a's C81, C17, C54 |
| Landmark line | Where the water meets the deciding reference, such as "Water reaches three quarters of the way up a parked car's wheel rim." (§4.3) | `landmark`, C609 |
| How it was read | "Measured from the size of the wheel rim." when `levelFrom` is `geometry` | MS3b's C320, once MS4 returns it (N8) |
| Inches | "Estimated 15 to 18 in.", only when the API sends `depthInMin` and `depthInMax`, which happens only after the release gate passes | MS3b's C308, MS4's C515 |
| Class line | "MMDA lists this level as not passable to light vehicles (NPLV)." The two added levels name the MMDA level they lie beyond, as C81 words them. | MS3a's C81 |
| Time and place | Your own report and a live pin: "Photo taken 25 min ago. Location within 12 m." A demo pin or a sample: the photo's own date, place and event, such as "Photo from Sep 26, 2009, Manila, Typhoon Ondoy", and no accuracy line. | Table 6, C617, C618 |
| Basis | "From 2 reference objects." | `basis` |
| The gauge | MMDA's 7 gauge levels drawn as a vertical scale, with the 2 off-scale levels (below gutter and above chest) drawn apart and marked as outside MMDA's gauge (design C14). It fills to the result's level; a floor is drawn open at the top; "no flood seen" leaves it empty. It repeats the level line, so screen readers skip it. | MS5-Q1, C624 |

The other outcomes use the same card, so they stay apart by `status` (C50, C610):

| Outcome | What it says |
|---|---|
| `done`, no flood seen | "No flood seen at this spot." |
| `refused` | D19's line: "I can't tell from this photo. Retake it from a dry spot with a parked car's wheel or a person standing still in view. Don't step into the water or the road." Then a plain reason line (§4.3). |
| `failed` | "Processing failed, try again." Then a plain reason line. "Try again" starts a new photo; it never resends this one. |
| `mode: private` | The result as above, plus "Taken outside Metro Manila, so only you see this result. It isn't on the map." (D14, C611) |
| No result yet (the app's own state) | "No result yet. The analysis is taking longer than usual." with "Check again" (C601) |

A "Details" disclosure shows the reason code and the photo's time. No report id, raw error text or URL ever shows (C610).

### 4.3 Wording to write

MS5 drafts every line below in English and in Taglish, and Rene reviews them (M20). The test screen's lines (C81) and D19's refusal are the starting point. They live in one string table per language (C609).

- **Landmark lines,** one per category the pipeline can return as the deciding landmark: the wheel rows (`tire_only`, `rim_quarter`, `hub`, `rim_three_quarters`, `rim_top`, `wheel_covered`), the people rows (`ankle` to `above_chest`) and the body floors (`mid_door`, `window`). People lines say "an adult in the photo", because the API doesn't say whether that adult was standing or wading. Vehicle lines say "a parked car", because moving vehicles never give a reading (plan §7 step 4).
- **Reason lines** for every `refusalReason` in MS3a §3.4, such as "The photo is too dark to read." for `too_dark` and "The cars and people in the photo give depths more than one level apart." for `references_disagree`. None tells anyone to approach water or traffic (plan §13).
- **Every other line** in the app: buttons, the waiting states, location and camera problems, the limits MS4 returns, the Tested page, samples, demo pins, the flag dialog and the empty map.

The Taglish refusal starts from the draft under the Oct 28 log's "Waiting on Rene".

### 4.4 What the app keeps

- **On the phone,** in `localStorage`, each read inside a guard so the app works without them (C607): the 18+ confirmation and the consent version accepted, the random device id (C606), and the language and theme choices. Android's `allowBackup` is set to `false` with this first on-device storage, as the Oct 28 deferred list asks.
- **In memory only:** the photo, until its upload succeeds or its 15 minutes pass (C635), and the report id, until the result screen closes. The in-app camera writes no file (C602, C626).
- **Never:** a photo on disk, a location or a report id after its screen.

## 5. What MS5 needs from MS4 and MS6

Window 4's MS4 draft already gives most of the API. These are the gaps MS5 depends on. Each goes to Window 4 through the tracker, and MS5's plan follows whatever MS4's and MS6's committed specs decide.

| # | Need | Why | Default if not added |
|---|---|---|---|
| N1 | `GET /reports/{id}` adds `pinId` and `gpsAccuracyM`, with `pinId` only while the pin is on the map (not while the publish switch hides live pins, MS4's C516) | The person's own new pin shows at once and gives way to the feed's copy. Table 6's "location within 12 m" needs the accuracy. | The own pin is matched by time and position; the accuracy comes from the app's own fix. |
| N2 | Public pins (`GET /pins.geojson`, `GET /reports?lat=&lng=`) add `gpsAccuracyM`; demo pins add their credit line and their event | Table 6's line; Rene's rule that every demo photo shows its credit; C618's date line | Pins show no accuracy line; a demo pin without a credit line isn't shown. |
| N3 | `GET /pins.geojson` is built, not dropped | The map needs every visible pin. The nearby read covers only 300 m, which can't fill a city map. The plan makes the feed a should-have; MS5's map makes it required. | The map reads the nearby route at its centre once zoomed to about 16 or closer, says "Zoom in to see reports near a spot" when wider, and the list shows what it has read (C612) |
| N4 | `POST /uploads` accepts `nudgeM` (0 to 100) and `consentVersion`, and the API's CORS allows the `X-Lusot-Device` header | Plan Tables 4 and 14 (`nudgeM`; consent is an input); MS4's C508. The web origin is MS5's to add (C600, C622). | The app sends both fields; MS4 ignores what it doesn't store. |
| N5 | **Overlay layers as data,** beside the overlay JPEG: the blurred photo's size, the water mask as simplified polygons, and per reference its box, kind, reading and whether it was used or dropped; later the fitted rim and the waterline from MS3b | The overlay "draws itself" one layer after another (plan §4, Table 21). A flat JPEG can only fade in. | C615's fallback: the JPEG fades in over the photo, and the should-have is reported as partly met. |
| N6 | Demo pins' photo and overlay links by `pinId`, and live pins' too if Rene picks MS5-Q3's (b) | Pin detail shows its work where MS5-Q3 allows | Demo pins show text only. |
| N7 | Error codes for the device limits (uploads, samples, flags) in the response body, so the app tells them apart from API Gateway's own throttling 429 | Each limit gets its own line; a throttle is retried, a limit isn't (C601, C635) | Any 429 without a known code is treated as a throttle. |
| N8 | `GET /reports/{id}` returns `levelFrom` on level results | §4.2's "how it was read" line. MS3b stores it, but no milestone's API returns it yet (MS3b's C320). | The line doesn't show. |
| N9 | **Samples:** `GET /samples` gives each photo's place, date and event, beside the credit line and licence. The seed script keeps only C617's picks, and filters on `demo_use = ok`, `share_alike = no` and a CC0 or CC BY licence. The same filter applies to demo pins. | §4.2's line for samples. 19 of the 61 photos marked `demo_use ok` are CC BY-SA 4.0, and MS4 §4.5 filters on `demo_use` alone. | Samples show their credit line only, with no date. |
| N10 | **A route throttle for `GET /reports/{id}`** sized for W16's rush (50 uploads in a minute, each polling), and a check of whether HTTP API's default route throttle (MS1's 10 a second, burst 20) is per route or shared | 50 phones polling every 2 s make 25 requests a second, so the stage default refuses most polls; if it is shared, uploads and the feed are refused too | The app backs off on 429s (C601), and MS7's load test shows the effect. |
| N11 | **Samples and demo pins keep a blurred copy of their photo whatever the outcome:** faces and plates blurred at seeding, as the privacy draft promises, with a short-lived link from `GET /samples` (each sample's photo) and from a demo pin's detail (N6) | A judge should see the photo that was read, refused or found dry, and the Tested list needs something to show before a run. MS3a's C61 stores a photo only for level results, which is right for people's reports; these photos are open-licensed or consented, and Rene allowed them to be shown, credited and blurred. | Samples and demo pins show text only, and refusal samples aren't seeded. |
| N12 | **Flags never hide demo pins:** MS4's C511 counts their flags but doesn't hide them, and the demo script removes a wrong one | Three flags, perhaps from one person clearing storage, would hide a demo pin for everyone until a paid re-seed. MS4's C516 keeps demo pins up under the publish switch for the same reason. | The app shows no flag button on demo pins. |
| M1 | **From MS6:** `summary.json` adds exact and within-one level agreement (`{k, n}`) for each configuration | Plan §18 puts level agreement on the accuracy page; MS6's summary (its plan, Task 8) has no such fields | The Tested page shows the other figures and links to the report for level agreement. |

MS4's draft also says MS5 polls for about 180 s, and that the Amplify domain arrives as a template parameter with M6; C601 and C622 settle both differently and say why.

## 6. Calls (Claude's, C600 onward)

| # | Call | Why |
|---|---|---|
| C600 | **MS5's boundary.** MS5 owns the app: its screens, copy, languages, capture, PWA, APK and web hosting. It changes no pipeline code and no API handler. Its only backend edits are the hosting resources and the web origin in the API's and the bucket's CORS lists (C622). MS4 owns the `X-Lusot-Device` header in the API's allowed headers (C508). Everything else MS5 needs from the API goes to MS4 as §5's requests. | Design §8 freezes measurement before the sealed run, and MS4's C500 owns the API. Line-by-line owners in `backend/template.yaml` avoid clashing edits. |
| C601 | **The poll, settled.** After the photo reaches S3, the app polls `GET /reports/{id}` every 2 s for the first 60 s, every 5 s until 4 minutes, then every 15 s until 10 minutes after the upload. A 404, a network error or a 5xx keeps it polling. A 429 waits for its `Retry-After`, or for the next interval with up to 1 s of random jitter. At 10 minutes the app shows "No result yet" with "Check again", which polls the same report for another 10 minutes and never uploads again. From 60 s the waiting screen says that many photos may be waiting ahead, without promising a time. This replaces MS3a §3.8's rule that a poll timeout reads as processing failed, and it departs from plan Table 15's "every 2 s until done" (§9). MS3a's B1 bound of 120 s (C68) is a smoke-run bound and stays. | MS1's 120 s was shorter than one analysis can take: a run stops at about 150 s and must publish before the 180 s timeout (C84, C88). Under W16's rush of 50 uploads in a minute, 5 analyses at a time of about 35 to 45 s each take about 6 to 7 minutes to clear, so the last results come long after 240 s. Saying "processing failed" before the server does would be a guess, and "Try again" would pay Meta twice for one photo. The slower intervals and the 429 handling keep a rush of waiting phones inside the API's throttle (N10). |
| C602 | **One camera for every platform:** a live camera view inside the app, from the browser's camera stream (`getUserMedia`), on the web and in the APK alike. It asks for about 1,920 × 1,080 from the rear camera, takes the still with `ImageCapture` where the browser has it, and otherwise from the video frame. A still under 1,600 px on its longer side gets a quiet warning. No file picker and no gallery exist anywhere in the app, and Capacitor's camera plugin is removed. The APK declares Android's `CAMERA` permission, and Capacitor's WebView client asks for it when the stream starts. `capturedAt` is the moment the shutter is pressed. Without a camera or its permission, the app says what to do and points to the samples. | Plan Table 4 wants in-app photos, never gallery picks. MS1's review found that the web's file picker stamps a fresh time on an old photo (W20), and an EXIF check can't catch a photo whose metadata was stripped. Capacitor's `takePhoto` opens the phone's own camera app, where Lusot can't show the safety line; it writes the unblurred original, perhaps with the camera's EXIF location, to a file on the phone; and its new Android flow keeps its state in memory, so `appRestoredResult` can't bring the photo back when Android closes the app (the accuracy review, from `IonCameraFlow.kt` in `@capacitor/camera` 8.2.6). One in-app camera avoids all three, and Capacitor's `BridgeWebChromeClient` grants the stream once `CAMERA` is allowed. This departs from plan Table 3's file-input fallback on the web (§9). |
| C603 | **Location.** The GPS fix starts when the camera opens. The app waits up to 20 s for a fix of 50 m or better, and without one it uploads nothing and says why: move to open sky, or, on Android 12 and later, allow precise location. The place screen shows the pin and the accuracy circle; the person may drag the pin up to 100 m from the fix, and the app sends the moved position with `nudgeM`. | Plan Table 4 sets 50 m and the 100 m nudge, and W22 relies on both. Refusing a poor fix costs nothing, while a pin on the wrong street misleads everyone. Desktop browsers rarely reach 50 m, which steers judges to the samples, as the plan intends. |
| C604 | **The phone's quality check** computes MS3a's two scores (C44, C58) on the 1,600 px image before it is encoded: the mean grey value with OpenCV's weights, and the variance of the 3 × 3 Laplacian with OpenCV's border rule. It uses the cutoffs in `backend/analysis/src/lusot_analysis/pipeline/quality.py`, which reaches `main` with MS3a, and a test reads that file so the two never drift. Under a cutoff, the screen shows the retake tip with "Retake" first and "Send anyway" second. The server checks again for free. | Plan §7 step 1 runs the same check on the phone and on the server. The phone's copy saves an upload and gives the tip in a second. The cutoffs are provisional until MS3b tunes them, so one source of truth matters. "Send anyway" covers the small gap between the phone's pixels and the server's decoded JPEG. |
| C605 | **Two gates, both before Meta is called.** The 18+ check comes before the first action that calls Meta: a sample, an upload or, in MS6, a question. Window 4's consent notice, with the same check, comes before the first upload and the first question. The accepted notice version and the 18+ confirmation are kept on the phone, and a new version of the notice asks again. The map, the Tested page, About and the privacy policy need neither. The notice and the policy show Window 4's English text as Rene approves it (M21); their Taglish shows only after he approves it too. | Plan §13 and Table 4 require the notice and the age check before the first upload, and Meta's terms require adult users. A sample also goes to Meta, but the notice speaks of "your photo" becoming a pin, which isn't true of a sample, so a sample needs only the age check. A question sends the person's own words and location to Meta, so it gets the notice: the default for Window 4's PRIV-Q3. A person must understand what they agree to, so unreviewed Taglish never stands in for it. |
| C606 | **The device id** is a random UUID made at first launch with `crypto.randomUUID()`, kept on the phone and sent as `X-Lusot-Device` (MS4's C508) with uploads, samples and flags. It is never shown or logged. | Plan Table 4's device id, for the hourly limits. |
| C607 | **On-device storage** is `localStorage` only, for §4.4's items, read inside guards. No Capacitor storage plugin. | Losing it costs only a repeated consent and a new device id. One mechanism works on the web and in the APK. |
| C608 | **The copy rules are tested, and then reviewed.** One test scans both string tables, and the end-to-end suite scans the visible text of every screen in both languages (not CSS names, R51):<ul><li>no "safe", "safer", "safest", "safely", "safety" or "ligtas", in any case</li><li>none of a short list of crossing phrases, such as "you can cross", "go ahead" and "pwedeng dumaan"</li><li>CLAUDE.md's exact safety line on every route and dialog, visible without scrolling on a 360 × 640 screen</li><li>every level line says "at this spot" (or its Taglish line), and level and class words come only from the 9 levels and the 3 classes</li><li>no "MMDA's 9 levels" in any form</li></ul>A word test can't catch every piece of crossing advice or whole-road wording, so the string tables also go to a reviewer pass in each UI task's code review, and to Rene (M20). No UI-review agent is added: R44 judged that a deterministic test may beat a skill here. | CLAUDE.md's product rules, as a check that fails the build, backed by people who can read meaning. |
| C609 | **The words.** MS3a's C81 lines are the base for levels and classes, and D19's line for refusals. Claude drafts every other line (§4.3) in English and Taglish. Each line, in both tables, carries a "reviewed" mark: lines Rene has already fixed (the safety line, D19's refusal, C81's lines) start reviewed, and every new line starts unreviewed until his M20 review. A check prints the count of unreviewed lines; design §8 puts the copy review in MS7, and MS8's release needs the count at zero. | CLAUDE.md: Rene reviews every Taglish line, refusal and safety line before release (M20), English reason lines included. A per-line mark lets him approve in batches, and the count makes "done" checkable. |
| C610 | **Outcomes are shown by `status`, never by reason** (MS3a's C50). Each reason gets a plain line (§4.3). "Details" shows only the reason code and the photo's time. No report id appears on any screen; a privacy request names the time and place of the photo, as the policy draft's main text says. MS1's raw "Details:" error line goes. | Keeps the three outcomes apart (CLAUDE.md). The raw error line was deferred to MS5 by MS1's Task 9 review. The report id is the only key to a report's photo links for 7 days (MS4's C503), so a screenshot must never show it. Window 4's bracketed "[and the report id, if the app showed you one]" can go. |
| C611 | **The private result screen** (D14, C21): a `private` report shows its result with one extra line saying it isn't on the map because the photo was taken outside Metro Manila. | Design §8's MS5 row. MS4's `mode` field says which mode a report is in. |
| C612 | **The map.** Leaflet is used directly through a small React wrapper, with no `react-leaflet`. Pins come from `GET /pins.geojson` when the map opens, every 60 s while it is visible, and when the app returns to the front; if MS4 drops the feed, the map falls back to N3's nearby reads. The person's own new pin shows at once and gives way to the feed's copy (N1). A live pin shows at full strength for its first hour and faded until it leaves the map at 3 hours (plan §9). Demo pins carry a Demo mark and never fade. A list view shows the same pins newest first, as the keyboard and screen-reader route. OpenStreetMap's tile policy is followed: its attribution stays visible above the safety bar, the site never sends a `no-referrer` policy, and the APK adds "Lusot" and its version to its user agent (`appendUserAgent`). | One read keeps the map simple, and the feed's 60 s cache matches the refresh. A thin wrapper avoids a second library whose version must follow React's. A map alone isn't accessible, so the list is the equivalent. |
| C613 | **One result card** for the result screen, pin detail and samples (§4.2). Pin detail adds the age, the number of other pins within 300 m in the last 3 hours (from the feed the app already has), and, on live pins only, a "Flag as wrong or fake" action (MS4's `POST /pins/{pinId}/flag`), with a confirmation, one per phone. Demo pins have no flag button (N12). | Plan Table 6 is one wording; three copies of it would drift. W21's fixes include a flag button and report counts. A demo pin is ours to remove, not the crowd's to hide. |
| C614 | **Photos on pins follow MS5-Q3.** Until Rene answers: the person's own result and demo pins show the blurred photo and the overlay; other people's live pins show the result card without a photo. | Plan §4 says each pin shows its work, while MS4's C504 keeps photo links off public pins and Window 4's PRIV-Q2 asks Rene. The default is the one that is easy to widen later. |
| C615 | **The overlay that draws itself.** From MS4's layer data (N5), the app draws over the blurred photo in SVG: the water first, then each reference's outline with its reading, then the fitted rim and the waterline once MS3b provides them, about 2 s in all. Dropped references are drawn dimmed with no level, as MS4's C505 does. With reduced motion, the final frame shows at once. Without layer data, the overlay JPEG fades in over the photo, and the should-have is reported as partly met. | Plan §4 and Table 21: the masks, the rim and the waterline appear one after another. SVG keeps the lines sharp and lets each layer carry a text label for screen readers. |
| C616 | **The Tested page** (the plan's accuracy page). It reads `eval/results/report/summary.json` at build time, and the rerun's summary if `eval/results/rerun/` exists (MS6's C421), through Vite's `import.meta.glob`, which leaves an empty result when the file is missing. It shows figures only from a summary whose `kind` is `sealed` and that isn't `synthetic` (MS6's C422). For the configuration that ships, it shows underestimation, passability agreement and coverage, and exact and within-one level agreement once MS6 adds them (M1), each as "k of n"; whether inches are shown; and Set B's median error whenever Set B ran. Every figure carries its n and the word "indicative", and the page calls them agreement with the labels MMDA and the cities posted. Until the sealed run (Nov 3), it shows how Lusot is tested and says the results appear after that run. The full report is linked in the submitted repo once it exists (D9, R7). The page never uses the word "accuracy". After the sealed run, the web app and the APK are rebuilt and redeployed so the page shows the results. | Plan Table 21's must-have and plan §18's list for the page, with MS6's rules (W17, W19, C409): no number copied by hand, and the same claims as the report. `eval/results/` exists only from the sealed run (MS6 §4.3), and development results stay private. |
| C617 | **Samples.** The Tested page lists `GET /samples`, each with its blurred photo (N11, C637), place, date, event and credit line (N9). "Run this sample" goes through the 18+ check, then `POST /samples/{sampleId}`, then the same poll and result card, with a Sample badge, the photo's own date and place, and no accuracy line. Sample results never reach the map. The photos are the 42 CC0 and CC BY photos marked `demo_use ok` and not share-alike (39 from Wikimedia Commons, 3 from Flickr), later joined by consented M9 photos; CC BY-SA photos are never used. Claude runs each of the 42 once, face-blurred first, through MS3a's offline runner or the sample endpoint (about $1.35), and MS4's seeding keeps about 8 that between them show a level, no flood seen and a refusal. Each credit line adds that Lusot blurred faces and plates and drew its outlines. The sample result says it is a live reading of a credited photo, not a test result. | Rene's 8:26 PM decision. By the manifest's `subject` column, only 11 of the 42 have a car, an SUV or people as their main subject, and the landmark rules read only parked cars' wheels and adults (MS3a's C45, C57), so an unscreened list would mostly refuse. Choosing samples by outcome is fine for a demo and never touches the evaluation. Each run is fresh (MS4-Q8), so a sample can come out differently, and the screen doesn't promise an outcome. CC BY 2.0 asks that a credit for an adapted photo say how it was changed. |
| C618 | **Demo pins** show a Demo mark, the photo's date, place and event, its credit line (with C617's note on the blur and outlines), and, with N11, the blurred photo whatever the outcome (C637). Where MS5-Q2 leaves no demo pin, the map shows an honest empty state: "No reports in the last 3 hours", a "Try a sample" action, and one example result card labelled as an example. It never shows a pin that isn't a real reading at a real spot. | G1 says demo pins sit at the photo's real spot and are labelled. An empty map with a clear way in is better than a pin that misleads. |
| C619 | **Languages.** English is the default. A Taglish switch sits in the header and on About, and the choice is kept on the phone. Taglish sets the page's `lang` to `fil`. The safety line and "Not affiliated with MMDA." stay in English in both languages until Rene decides otherwise (M20), as Window 4's drafts do. Lines that bear on safety (the refusal, every retake tip and reason line, consent and the privacy policy) also stay in English until Rene reviews their Taglish. Other draft Taglish lines show in development and user-test builds, so M17's testers can react to them; the release needs C609's count at zero. | Rene's decision (English with a Taglish switch). An unreviewed retake tip could tell someone the wrong thing near water, while a draft button label can't. |
| C620 | **Navigation.** Hash routes: `#/map` (the default), `#/report`, `#/tested`, `#/about`, `#/privacy` and `#/pin/<pinId>`, through a small hook with no router library. No URL ever holds a report id; the result screen keeps it in memory. | Hash routes work the same in the APK, on Amplify without rewrite rules, and offline. The report id is the only key to a report's photo links (plan §13). |
| C621 | **The PWA.** `vite-plugin-pwa` (version 2 supports Vite 8), with automatic updates. The service worker precaches the app's own files only. API calls go to the network, and map tiles are never cached by the service worker. It registers on the web only, not in the APK. Offline, the app says so; the map and reports need the network. | Plan Table 3 wants an installable PWA. OpenStreetMap's tile policy forbids bulk downloads and asks clients to follow its caching headers, which the browser already does. A cached report would show a stale result. |
| C622 | **Web hosting follows MS5-Q4.** Until Rene answers: the Amplify app and its branch are defined in the SAM template with no Git connection, and `npm run deploy:web` builds the app with `VITE_API_URL` from the stack's output, then uploads it as a zip through Amplify's manual deployment. The same template adds the app's origin (`https://main.` plus its default domain) to the API's and the bucket's CORS, so no parameter is needed. Amplify keeps access logs, with visitors' IP addresses, until the app is deleted, so the privacy policy says so (Window 4's PRIV-Q9) and the app is deleted at the MS10 teardown. | CLAUDE.md: one template and no manual console changes. A Git connection needs a GitHub approval in the console (M6), and pushes happen only at milestone ends (D16). Amplify's user guide documents no way to turn its access logs off, which is why MS5-Q4 offers a host without them. |
| C623 | **Fonts and icons are bundled.** Fonts come from `@fontsource` packages (SIL Open Font License), never from Google Fonts at run time. Icons are inline SVG, from Lucide (ISC) for generic ones. OpenStreetMap's tiles are the app's one third-party request: their servers see each visitor's IP address, and the place screen and "Locate me" load tiles around the person's position, so the policy says both (Window 4's PRIV-Q5). | No font or icon request carries a person's IP address to another company, the PWA works offline, and the APK needs no network for its look. |
| C624 | **Visual tokens.** Colours are CSS variables per theme, light and dark, following the system setting unless the person picks one on About, and Tailwind's theme reads them. A script checks every text pair at 4.5:1 or more and every meaningful non-text pair at 3:1 or more, in both themes. Depth is shown on one hue that grows stronger with depth, never in traffic-light colours, and classes are shown as words and codes. Level names sit beside the gauge, not on its fill. | A green "passable" or a red "danger" reads as advice, which CLAUDE.md forbids. Some mid-ramp fills can't hold 4.5:1 text in either colour, so text stays on the page's surface. |
| C625 | **Accessibility target: WCAG 2.2 AA.** Touch targets of 48 px or more, visible focus, the result announced in a live region, layouts that hold at 200% text size, and reduced motion respected. The end-to-end suite runs axe on every route in both themes and fails on any serious or critical finding. | Outdoor use in rain, with wet hands, older phones and large system text. ui-ux-pro-max's first two priorities. |
| C626 | **The Android items from MS1's deferred list.** C602's in-app camera settles two of them: no external camera activity, so nothing for `appRestoredResult` to restore, and no photo file written to the phone. The photo-read timeout becomes a 10 s timeout on opening the camera stream. The rest: the template's broken example tests are deleted, a test pins `loggingBehavior: 'none'`, and `allowBackup` is off (§4.4). | Each was deferred to MS5 on Oct 28. A stream that never opens must not leave the screen waiting, as the read timeout guarded before. |
| C627 | **The APK is a debug build,** as MS1's was, made with the commands in CLAUDE.md. Release signing, with a keystore kept outside the repo, waits for MS8 if Rene wants it. | The web URL is the main judge path (M15). A debug APK installs the same way, holds no key and keeps its logging off. A release keystore is a new secret to guard. |
| C628 | **A mock API for development.** With `VITE_API_MOCK=1`, a development build answers from fixtures for every outcome, mode and limit. A production build can't include it, and a check on the built bundle proves it. | D8 lets shells start before MS4's API exists, and every outcome needs to be seen on screen before the backend can produce it. |
| C629 | **Tests.** Vitest covers the logic and the components. Playwright runs the end-to-end suite in Chromium with the API mocked per test, a fake camera from Chromium's fake media flags and a fake position: the gates, each outcome, the map and list, pin detail, samples, the language switch, the safety line on every route, the copy rules, a slow network, and axe. The suite runs as a fourth CI job; `npm run check` keeps its three parts, and CLAUDE.md's CI line is updated at the close with Rene's OK. | CLAUDE.md names Playwright for end-to-end tests. Keeping it out of `npm run check` keeps the local loop fast. |
| C630 | **Live checks pay little and pin nothing.** Runs against the deployed stack use samples, and uploads placed outside Metro Manila, which MS4 makes `private`, so no test pin reaches the public map. They spend at most about $1.50, plus C617's screening of the 42 samples, about $3 in all. Rene's own phone tests (M14, M16) are real reports at real spots; the instructions suggest public streets, not his home, because a live pin is public for 3 hours. | A test pin on the public map would be a fake report (W21). Design §4's budget note makes each photo about $0.032. |
| C631 | **Photo to pin is measured, not promised.** The live checks record the seconds from the upload to the result for each run, outside the repo, with ids of their own (never report ids). MS6's export copies them into `eval/results/latency.jsonl` (C416). The log gives the median, the nearest-rank 95th percentile and n, as plan Table 13 does. Nothing, including MS8's video, claims under 10 s unless a measurement shows it. | Plan §4's should-have. One analysis takes about 35 to 45 s at the default effort (§3), and only MS3b's effort test (C312) can lower it. |
| C632 | **Clip mode follows MS5-Q5.** Until Rene answers, it is dropped, and the storyboard's 15 s go to the map with demo pins, as plan §18 allows, which depends on MS5-Q2. | It needs video segmentation, the Files API and a motion check in the pipeline before the freeze, which no milestone has room for. |
| C633 | **"Not affiliated with MMDA."** appears on consent, the Tested page and About. No MMDA logo, and nothing that copies MMDA's own marks or the layout of its advisories. The result card and About link to MMDA's and PAGASA's official sites, with each URL checked when it is added. | CLAUDE.md and M22. W23's fix links MMDA's advisories. A look-alike of an official advisory would mislead. |
| C634 | **The five-person test (M17).** MS5 prepares a short protocol and an observation sheet for Rene (`docs/research/`): five adults, at least two of them drivers or commuters who deal with floods, each giving a spoken OK to being watched and noted, on top of the in-app consent. His notes stay outside the repo, with no names. The one change from it goes through the normal task loop and is logged with its reason. | Plan Table 22's finish line and M17. CLAUDE.md: no names. |
| C635 | **Uploads on a weak signal** (W24). The photo targets about 300 KB (plan Table 4): JPEG quality 0.85 first, and 0.75 if the result is over 450 KB. `POST /uploads` and the S3 upload each retry once after about 2 s on a network error, a 503 or a throttling 429. A retry of the S3 upload reuses the same link while it is valid (5 minutes, MS1's C27), so the photo is analysed once; a new link is asked for only after it expires. The photo stays in memory, with "Try again", until it uploads or its 15 minutes pass. A device limit's 429 (N7) is never retried. | Plan Table 18: the app retries a throttled call once. Re-posting the same form is paid once (MS3a's B5), while a second report for the same photo would be paid twice. |
| C636 | **Licences ship with the app.** The web build and the APK carry a licences page, reached from About, with the full licence text of every bundled library and font (Leaflet's BSD-2-Clause, the fonts' OFL, Lucide's ISC and the rest), generated from the installed packages at build time. | BSD-2-Clause and the OFL require their texts with binary or bundled copies; a README credit isn't enough. |
| C637 | **Samples and demo pins always show their photo** (from N11): blurred, with its credit line, before a sample runs and whatever it gives. A sample's refusal doesn't ask the judge to retake a photo they didn't take: it reads "Lusot can't tell from this photo." with the reason line, then "Someone reporting this spot would see:" and D19's line. Both new lines go to Rene with the rest (M20). Without N11, these cards are text only and no refusal sample is seeded. | The builder check found that C61's level-only rule would leave refused and dry samples, and dry-street demo pins, with nothing to show. D19's line is written for the person holding the phone, so a sample needs a frame around it. |

## 7. Done when

| # | Check | Evidence |
|---|---|---|
| U1 | The web URL is live | `npm run deploy:web` ends in a successful deployment; the Amplify URL loads over HTTPS on a phone, and the PWA installs on Android Chrome and through Safari's "Add to Home Screen" |
| U2 | The MS5 APK installs on a real phone, and the full flow works on mobile data | Rene, on his Android phone (M14 passed on the MS1 APK; this repeats it on MS5's): the 18+ check, consent, the in-app camera, a fix of 50 m or better, the nudge, upload, result, map and a sample. The stored photo is upright, which closes M14's open item. |
| U3 | The web app works in iOS Safari | Rene, on his iPhone (D8): the same flow |
| U4 | Every screen carries the safety line, and the copy rules hold | The end-to-end suite visits every route and dialog in both languages at 360 × 640 (C608); the string-table test passes |
| U5 | The outcomes stay apart | Component and end-to-end tests for every status, reason and mode, plus "No result yet"; one live sample run that reads a level or no flood seen, and one that refuses |
| U6 | The map shows live and demo pins, and each shows its work where MS5-Q3 allows | End-to-end tests on fixtures; one live check of the deployed feed after MS4 seeds demo pins (or C618's empty state, under MS5-Q2) |
| U7 | The Tested page and samples work | End-to-end tests with no summary, a sealed fixture, a rerun fixture and a synthetic one; a live sample run, with the feed unchanged afterwards; after the sealed run, both builds rebuilt and the page showing its figures |
| U8 | The gates come before Meta is called, and the privacy policy is live | End-to-end: a sample stops at the 18+ check, and an upload at the consent notice, until accepted; the policy page shows the text Rene approved (M21, dated Nov 1 to 2 in plan Table 27) |
| U9 | Accessibility | axe finds nothing serious or critical on any route in either theme; the token contrast script passes; a 200% text check on the main screens |
| U10 | Five people outside the team tried it, and one change came from their feedback | Rene's M17 notes (outside the repo): five adults, at least two drivers or commuters; the change's commit and its log entry |
| U11 | Photo to pin is measured | The log gives the median, the 95th percentile and n from the live checks (C631) |
| U12 | Repo hygiene | `npm run check` and CI pass, the end-to-end job included; the plan-leak check, the account-ID scan and gitleaks are clean; the APK's bundle and the web bundle hold no key, no Meta host and no mock API |
| U13 | Pins land on the right street (W22, M16) | Rene, on two public streets: each pin within its accuracy circle of where he stood |
| U14 | No old photo can become a pin (W20) | A source scan finds no file input and no gallery call in `app/src`; Rene tries to send a gallery photo or an old photo, and finds no way to |

The stakeholder quote (M28) is welcome but not required (C13). M15 stays as the plan has it: the web URL is the main judge path, and Google's optional registration is Rene's choice. W27's app side needs nothing: the app holds a report id only while its screen is open.

## 8. Questions for Rene

Each has a default that the build follows until he answers (D7). Most important first.

### MS5-Q1: the visual direction (R3's visual half)

Rene said he would research this himself. Three distinct directions follow, made with ui-ux-pro-max (its accessible, high-contrast civic profile, palettes, type pairings and UX rules) and frontend-design (a direction grounded in the subject, with one memorable element). Phone mockups of all three, showing the same knee-deep result, are on a private page made for this question (link in the overnight report). Every direction keeps the same screens, the same rules in C624 and C625, and light and dark themes. Contrast figures are WCAG ratios, computed for this spec.

**A. Panukat (the gauge).** Lusot as a field instrument. The memorable element is a vertical gauge beside every result and in each pin's marker: MMDA's 7 gauge levels, with below gutter and above chest drawn apart, dashed, and marked as outside MMDA's gauge. It fills with floodwater colour up to the reading; a floor is drawn open at the top, and "no flood seen" leaves it empty.

| | Light | Dark |
|---|---|---|
| Surface | pole white `#FBFBF8` | night `#111315` |
| Text | gauge ink `#16181A` (17.2:1) | `#F1F1EC` (16.4:1) |
| Secondary text | wet concrete `#50565C` (7.2:1) | `#A9AFB5` (8.4:1) |
| Action | signal blue `#0050B3`, with white text (7.5:1) | `#6EA8FF`, with night text (7.7:1) |
| Depth | silt, 9 steps from `#EDE8D0` to `#312B18`: the brown of Manila floodwater, not a clean blue | the same silt, growing brighter with depth, from `#3A3626` to `#ECE4BE` |

- **Type:** Atkinson Hyperlegible Next for everything, ui-ux-pro-max's pick for accessibility-critical public apps. It was made for the Braille Institute for readers with low vision, and it draws look-alike characters (1, l and I) differently. Level names are set large and heavy.
- **Tone:** plain and measured. "Knee deep at this spot (MMDA level)." No exclamation marks.
- **Map:** OpenStreetMap greyed a little under the pins, so the silt gauges stand out.
- **Motion:** one moment: the gauge fills to the level as the result arrives, then the overlay draws.
- **Accessibility:** every text pair is 7:1 or more. The gauge cells carry an ink outline, because the shallowest fill is only 1.2:1 against the page. Level names never sit on the fill, since the middle steps can't hold 4.5:1 text in either colour.

**B. Kalye (the street sign).** Lusot as roadside signage. The memorable element is the result set as an information sign plate: white on sign blue, in letters drawn after the Highway Gothic road-sign alphabet.

| | Light | Dark |
|---|---|---|
| Surface | concrete `#ECECE8` | asphalt `#191C20` |
| Text | asphalt `#1F2226` (13.5:1) | `#F2F4F6` (15.5:1) |
| Sign plate | sign blue `#0A4D9B`, with white text (8.2:1) | `#2C5FA3`, with white text (6.4:1) |
| Accent | lane yellow `#F6B800`, for the pin's "at this spot" mark only | the same yellow (9.6:1 on asphalt) |
| Depth | sign blue, 9 tints from `#DCE8F6` to `#08305F` | the same tints, brighter with depth |

- **Type:** Overpass, an open font based on the Highway Gothic signs, heavy for the plate and regular for the rest, in sentence case.
- **Tone:** direct and neighbourly, Taglish first in spirit. "Hanggang tuhod ang baha sa spot na ito." (a draft for M20)
- **Map:** pins as small sign plates with the level's short name.
- **Motion:** the plate turns over to show the result, then the overlay draws.
- **Accessibility:** big type reads well in sunlight. Lane yellow fails as text on concrete (1.5:1), so it is used only on asphalt or with an outline.
- **Risk:** the more it looks like official signage, the more it can read as an advisory. It uses information blue, never warning colours, to keep it an observation, and C633 keeps it to generic road-sign letters and colours, never MMDA's own marks.

**C. Ebidensya (the evidence).** Lusot as a case file. The memorable element is the overlay photo as the hero of every result, with thin leader lines from each wheel and person to its reading, and the app's colours taken from the overlay's own key.

| | Dark (default) | Light |
|---|---|---|
| Surface | night slate `#10161B` | `#F3F5F7` |
| Text | `#E8EDF1` (15.5:1) | `#0E141A` (17.0:1) |
| Secondary text | `#9AA7B2` (7.4:1) | `#56636F` (5.6:1) |
| Overlay key | water `#38C6D9`, wheel `#FF6BAA`, person `#FFC44D`, rim `#A6E05C` (6.9:1 to 11.7:1 on night slate) | water `#0B7285`, wheel `#C2255C`, person `#B35C00`, rim `#5C940D` (3.4:1 to 5.2:1) |
| Depth | a cool slate ramp, brighter with depth | the same ramp, darker with depth |

- **Type:** Instrument Sans, using its narrow widths for the callouts and its normal width for the text.
- **Tone:** precise and evidential. "Read from 2 references: a wheel at the rim's three-quarter mark, and an adult at the knee."
- **Map:** dark tiles at night, normal by day, with pins as small rings in the water colour.
- **Motion:** the overlay draws itself, layer by layer, as the result's opening.
- **Accessibility:** dark-first suits storms at night and saves battery on OLED phones, but it reads less well in bright sun, so the light theme matters as much. The key colours are never the only cue: each outline also carries a label and its own dash pattern, since wheel pink and person amber can merge for colour-blind people.

**Recommended default: A, Panukat.** It shows the pitch at a glance: MMDA's gauge, read from a wheel or a knee. Its light theme reads best outdoors in daylight, where most reports happen. Its one memorable element, the gauge, also works as the map pin, the result and the Tested page's explainer. C's leader lines can still be used on its overlay screen. Only the plan's tokens, the gauge and the map markers depend on this choice, so a change after the shells costs little.

### MS5-Q2: what fills the map for judges?

Plan Table 21 makes the live map a must-have so that judges never see an empty map, and plan §18's fallback for a dropped clip scene is a map full of labelled demo pins. Under today's defaults there would be none: G1 and MS4-Q9 (a) place demo pins only at a photo's real spot; the only 3 Metro Manila photos among the 42 (Ondoy, Sep 26, 2009, CC BY 2.0) give only "Manila" as their place; and M9 has 0 consented photos (R6). Without demo pins, judges see C618's empty state, the video's map scene has nothing to show, and under MS5-Q3 (a) no pin on the map shows its work.

| Option | What happens |
|---|---|
| (a) | Demo pins only from photos with a real spot: consented M9 photos (R6), and photos you take yourself at real places, a dry street giving "no flood seen". The map stays empty until they exist. |
| (b) | As (a), plus the 3 Manila photos at the described place's centre, labelled "Demo, approximate spot" (MS4-Q9 (b)). |
| (c) | As (a), and if it rains, real pins (M29). Nothing else. |

**Default: (a).** It keeps G1's rule that a demo pin is a real reading at a real spot. Your own photos of a few named streets, even dry ones, are the quickest way to fill the map honestly. A dry street's pin shows its photo only if MS4 keeps demo photos whatever the outcome (N11, C637). (b) puts a pin where no photo was taken, so it is yours to allow.

### MS5-Q3: which pins show their photo and overlay?

Plan §4 says every pin shows its work on the blurred photo. MS4's C504 keeps photo links off public pins, and Window 4's PRIV-Q2 asks the same question for the privacy text.

| Option | What happens |
|---|---|
| (a) | Your own result and demo pins show the blurred photo and the overlay. Other people's live pins show the result card without a photo. |
| (b) | Every pin shows its blurred photo and overlay to anyone for its 3 hours, and the consent notice says so. MS4 adds the links by `pinId`. |
| (c) | No pin shows a photo. Only your own result does. |

**Default: (a).** It is easy to widen to (b) later, while (b) exposes bystanders' blurred photos at once, and the blur can miss faces (W25). (b) is the plan's own wording, so it is yours to choose.

### MS5-Q4: how the website is hosted, and its access logs

Plan Table 3 hosts the site on Amplify, deployed from GitHub on every push, and D11 expected CI and Amplify to run on every push. Amplify keeps access logs, with visitors' IP addresses, until the app is deleted, and documents no way to turn them off (Window 4's PRIV-Q9). CLAUDE.md keeps data 7 days.

| Option | What happens |
|---|---|
| (a) | Amplify connected to GitHub, as the plan says. You approve the connection (M6), and each push to the connected branch deploys. The logs are disclosed, and the app is deleted at MS10. |
| (b) | Amplify defined in the SAM template with no Git connection; `npm run deploy:web` uploads each build. M6's approval isn't needed. The logs are disclosed, and the app is deleted at MS10. |
| (c) | S3 and CloudFront defined in the template, with access logging off, deployed by the same script. A new service and a plan change. |

**Default: (b).** It keeps one template and no console steps, deploys when Claude deploys the backend, and follows the plan's choice of Amplify, with Window 4's recommendation for the logs. (a) deploys only when pushes happen, which is at milestone ends (D16), and the submitted repo is a separate one (D9). (c) is the only option that keeps no visitor IP address past 7 days.

### MS5-Q5: clip mode

| Option | What happens |
|---|---|
| (a) | Drop it. The video's 15 s show the map with demo pins, as plan §18 allows, which needs MS5-Q2's pins. |
| (b) | Build it only if the pipeline's video path, the Files API and the motion check are done and tested before the freeze. MS5 then adds the 5-second recording screen. |

**Default: (a).** Plan §25 counts clip mode toward Meta tooling, but it changes the pipeline right before the freeze, and nothing has room for it.

## 9. Departures from the plan

CLAUDE.md asks that a difference between the plan and the build go to Rene, not be chosen quietly. Each one here is a default he can overturn.

| Plan | MS5 | Call |
|---|---|---|
| Table 15: the app polls every 2 s until the report is done | 2 s for a minute, then slower, for up to 10 minutes, then "No result yet" | C601 |
| Table 3: on the web, the camera falls back to a file input; the APK uses the Camera plugin | One in-app live camera on every platform, with no file input | C602 |
| §18's accuracy page holds every metric listed there | Level agreement waits for MS6's summary fields (M1) | C616 |
| Table 3: Amplify deploys from GitHub on every push (with M6 and D11) | Under MS5-Q4's default, Amplify takes uploaded builds | C622 |
| §4: each pin shows its work | Under MS5-Q3's default, other people's live pins show no photo | C614 |

## 10. Not in MS5

- **MS4:** every API handler, the demo-pin and sample scripts, the overlay JPEG and its layer data, limits, flags and the route throttles (§5 lists what MS5 needs).
- **MS6:** Ask Lusot's screen, typed and spoken, and its tool. MS5 leaves the fifth navigation slot and the consent gate for it.
- **MS3b and the sealed run:** inches, `levelFrom`, and the release gate's decision. MS5 words them when the API sends them.
- **MS7:** the load test, the secret scan of the repo and the APK, and the copy review.
- **MS8:** the video, captions, the README's judge path and the release build.
- The plan's nice-to-haves (plan §4).

## 11. Risks

- **No demo pins** (MS5-Q2). The map can start empty for judges until consented photos with real spots exist, and the video's map scene depends on them.
- **Photo to pin takes about 35 to 45 s, not 10 s** (C631). The waiting screen must make that bearable, and the video must not claim otherwise.
- **The in-app camera** depends on each browser's camera stream: on iOS Safari it needs a tap, `playsinline` and HTTPS, and installed web apps on iOS have had camera quirks; in the APK it rests on Capacitor's WebView permission path. Rene's phone tests (U2, U3) are the proof, and the samples are the fallback.
- **API Gateway's throttle.** MS1's stage default of 10 requests a second, burst 20, can refuse a rush of polls (N10). C601's backoff softens it; MS4 owns the route limits, and MS7's load test measures them.
- **MS4's API arrives late or differs** (§5). The mock API (C628) keeps the screens moving, and each difference is reconciled when MS4's spec is committed.
- **OpenStreetMap's tile servers** limit heavy use. A judging spike stays small, but if tiles are refused, the list view still works.
- **The reports index's read units.** Each poll costs about half a read unit on the index, which has 5 (MS1 §3.2). C601's intervals and N10's throttle keep a rush near that; MS4 owns the capacity.
- **Taglish review time.** M20 is Nov 2 to 3. Every line goes to Rene in one table, ordered by where it appears, so he can review it in one sitting.

## 12. Builder check (Oct 29, 12:08 AM)

A fresh builder (Opus 5.5 at max) read this spec with CLAUDE.md, the MS1 and MS3a code and specs, the design, the MS4 draft, the MS6 spec and the privacy drafts, without the plan draft. It opened nothing under `lusot-data`. It raised three questions. Each one could be settled from Rene's decisions and the existing calls, so none goes to him as a new question.

| # | Question (short) | Pile | Settled as |
|---|---|---|---|
| Q1 | Does a sample show its photo when it doesn't read a level, or before it runs? MS3a's C61 stores photos only for level results, so refused and dry samples, and dry-street demo pins, would show nothing, and D19's line would ask a judge to retake a photo they didn't take. | Claude's call, with a request to MS4 | N11 (samples and demo pins keep a blurred photo whatever the outcome) and C637 (they always show it, and a sample's refusal frames D19's line). People's own reports keep C61's rule. |
| Q2 | If MS4 drops `GET /pins.geojson`, what fills the map? The bounding-box fallback would be another MS4 handler. | Answered from the project | N3's default now uses the existing nearby read at street zoom (C612), and Task 0 of the plan checks MS4's committed spec for the feed. |
| Q3 | Can three flags hide a demo pin? | Claude's call, with a request to MS4 | N12 (flags never hide demo pins) and C613 (no flag button on demo pins). |
