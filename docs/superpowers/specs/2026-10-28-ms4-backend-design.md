# MS4 Backend: spec

- **Date:** Oct 28 to 29, 2026 (Manila)
- **Status:** Draft 3. Window 4 wrote it overnight under Rene's delegation, through the tracker, without a live conversation (D7, D15).
  - It was revised after an accuracy review (Opus 5.5 max): 3 Critical, 15 Important and 18 Minor findings, all addressed.
  - It was then revised after a builder check (Opus 5.5 max). Its seven questions became C518 to C521, a change to C515, and MS4-Q13.
  - Claude proceeds on the calls in §5 and the defaults in §8 until Rene approves.
- **Implements:**
  - design §8's MS4 row, with G1 (demo pins), G2 (pay once, built in MS3a's C46, re-tested here), D14 and C21 (`private` mode), and C17 (`levelIsFloor`)
  - plan §4's must-haves for pins and samples, §5, §6 (Table 4's checks and the pin's text), §7 step 8, §12 (Tables 14 and 15), §13, and Table 21's "show your work" overlay
  - the binding items in the tracker's update to Window 2, section D ("When you reach MS4")
  - MS3a's hand-offs (its §5, "Not in 3a"): the overlay, `readings` and photo links; `private` mode and the Metro Manila check; demo pins, flags, the samples endpoint and the publish switch; recovery tests before the freeze
- **Needs first:** MS3a merged into `main` (its handler, template and smoke changes are on its branch until then). MS3b merged before S1, the finish line, which needs the full pipeline. The overlay, its layers and `readings` also wait for MS3b's evidence record (C518).
- **Not here:** Ask Lusot (`POST /ask`, `POST /ask/voice`) gets its own spec after this one. It reads pins, so it must honour the publish switch (§4.6).

## 1. Intent

MS4 turns the pipeline from MS3a and MS3b into the service people use: a photo goes up, the analysis runs in the cloud, and the result comes back with its blurred photo and its overlay, and becomes a pin when its mode says so. Each pin can show its work, so anyone can check the reading. The finish line is the design's: upload to pin works end to end in the cloud, with the full pipeline and its overlay.

What makes it worth judging is that every path has one rule: who sees a result and for how long, how each kind of report is made, how a report is paid for once, and what the three stop switches do without a redeploy. The failure paths are tested before the pipeline freezes.

## 2. Goals, non-goals and anti-goals

**Goals**
- The analysis Lambda finishes each report by its mode (§4.1, §4.2): the blurred photo, the overlay and its layers, `readings`, and publishing for `live` and `demo` only.
- The reports API is complete for MS5's screens: a report's result and pin detail, nearby pins, the feed, flags and samples (§4.3).
- Every mode has one creation path, with its checks (§4.1).
- Demo pins (G1) and samples are seeded and removed by scripts, never by hand.
- `private` mode keeps results from outside Metro Manila off the map and the feed (D14, C21).
- The analysis path's recovery is tested before the freeze (B2), with G2 re-tested on MS4's handler.

**Non-goals**
- Changing how depth is measured. That is MS3a's and MS3b's, and it freezes before the sealed run (design §8). MS4 may change code that runs before the result only where no depth output changes.
- Ask Lusot, its tool and voice (their own spec).
- Real screens and their final wording (MS5), and the overlay's animation (MS5 uses the layers MS4 saves).
- Clip mode. MP4 uploads ship only if clip mode is finished before the freeze (design §8). Until then the upload policy takes JPEG only.

**Anti-goals** (it fails even if it works)
- A `private`, `sample` or `eval` result, or a refused or failed one, reaches the map or the feed.
- A photo or overlay is stored with faces or plates unblurred, or kept past its rule.
- Two workers pay for one report at once (G2). (A run that times out may be paid again by its re-claim, at most 5 receives: §4.8.)
- A demo pin counts in any metric, or is mistaken for a current report.
- A stop switch needs a redeploy.
- Text on the overlay or in a response says "safe", gives crossing advice, or describes more than one spot.

## 3. Constraints

- CLAUDE.md's rules hold throughout. The ones that bite here:
  - one SAM template in `ap-southeast-1`; no manual console change
  - no reserved concurrency; analysis stays capped at `MaximumConcurrency` 5 (C9)
  - pay once per report, with the claim before any Meta call (G2, MS3a's C46)
  - the Meta key is read only by Lambda, from SSM
  - never log photos, exact locations or IP addresses
  - faces are blurred before any photo goes to Meta, and faces and plates again before anything is stored
  - every Meta call runs on the credits
  - visual work (the overlay) uses the `ui-ux-pro-max` and `frontend-design` skills
- **Free plan:** DynamoDB stays inside the always-free 25 read and 25 write units. MS1 uses 15 and 10. MS4 adds the `feed-index` (2 and 2) and the `limits` table (2 and 2), for 19 and 14 in all.
- **Costs:** about $0.032 per analysed photo, or $0.034 at full size, from billed usage (section D, item 7). MS4's cloud runs (demo seeding, samples, recovery and smoke runs) stay under about $2 in all.
- **The pipeline is frozen code by the time MS6's sealed run starts.** MS4 changes what happens after the result (publishing, photos, the overlay and its layers, modes) and the API around it.
- **The lease rule stays:** a delivery that meets a live lease returns its message rather than finishing it (MS3a's §3.1 step 4). A change to the visibility timeout (1,080 s), the lease (15 minutes) or `maxReceiveCount` (5) must keep the lease longer than the 180 s Lambda timeout and shorter than the visibility timeout.

## 4. What gets built

### 4.1 Modes: how each report is made, and who sees it

| Mode | Made by | Checks at creation | Table key | On the map | In the feed | Hidden after | Deleted after |
|---|---|---|---|---|---|---|---|
| `live` | `POST /uploads`, inside Metro Manila | §4.3's upload checks | `GEO#` cell, capture time | yes, when published | yes, when published | 3 h (`visibleUntil`) | 7 days (`expiresAt`) |
| `private` | `POST /uploads`, outside Metro Manila (C21) | the same | `GEO#` cell, capture time | never | never | n/a | 7 days |
| `sample` | `POST /samples/{sampleId}` | the stop switch and the sample caps | `SAMPLE`, receive time | never | never | n/a | 7 days |
| `eval` | test and recovery scripts, writing the item directly (C513) | none, beyond the scripts' own guards (§4.7) | `EVAL`, receive time | never | never | n/a | 7 days |
| `demo` | `demo_pins.py`, writing the item directly (G1, C510) | the Metro Manila test on the photo's real spot | `GEO#` cell, the photo's real capture time | yes, with `mode: demo` | never (C517) | the script's `--until` date | `--until` plus 7 days, as a backstop |

- **Published** means a `live` or `demo` result that is `done` with a level, written while the publish switch was off (C516). It gets `published: true`, and `feedPart` set to its mode (`live` or `demo`) for the feed index.
- **"No flood seen"** isn't published by default (C506, MS4-Q2): it carries no photo or basis to show its work.
- **Smoke runs** post a point outside Metro Manila, so they exercise the whole upload path as `private` and never make a pin (C513).

### 4.2 The analysis Lambda: from result to publish

MS3a's handler claims the report, runs the pipeline under its deadline (C84, with C88's 30 s margin), saves `blurred/{id}.jpg` for a level result (its C61), and writes the result under the claim token. MS4 adds, for a level result, before the final write:
- **The overlay** (C505): `overlay/{id}.jpg`, the blurred photo with these drawn on it:
  - the masks: wheel, person, water, and a rim once MS3b links it
  - the waterline wherever MS3b's geometry computed one, with its fitted rim
  - the numbered boxes, each with its reading in plain words: the landmark category for a landmark reading, and its level

  Dropped references are dimmed and carry no level, and a wheel the self-check re-checked is marked.
- **The layers** (C505): `overlay/{id}.json`, the same marks as simplified vector outlines, in the order they're drawn, so MS5's overlay can draw itself (plan §4, should-have). Face and plate outlines are never in it.
- **`readings`** (C507), stored on the item, and `overlayKey` (plan Table 14), which names the overlay.
- **Mode-aware storage:** `live`, `private`, `sample` and `eval` write under `blurred/` and `overlay/`, which keep their 7-day lifecycle. `demo` writes under `demo/blurred/` and `demo/overlay/` (C510).
- **Publishing** sets `published` and `feedPart` (§4.1), after reading the publish switch (C516).

MS3a's C72 extends to every key a mode writes. Right after a successful claim, before any Meta call, the handler deletes that report's photo, overlay and layers keys, so only the attempt that writes a level leaves them.

Every write after the claim still requires `status = processing` and the worker's claim token (MS3a's C46, C82). The raw photo goes only once the final write has succeeded. If deleting it fails, only the deletion is tried again, never the analysis (plan §7 step 8).

**What the pipeline hands over** (C518): MS3a's result type today holds only the outcome, the log and the publish photo. The masks, the boxes and each reference's reading stay inside the run, and drops are kept as counts. So MS3b, which edits those modules now, adds an evidence record to the result. It holds, for each numbered reference:
- `id`, `kind` (`wheel`, `body` or `person`), `box`, and a simplified mask outline
- `landmark` (the category) and `level`, each or `None`
- with geometry: `inches` (min and max), the fitted rim, and the waterline as two points
- `used` (its reading entered the combine) and `deciding` (it set the level)
- `dropped` (the cause, or `None`) and `rechecked` (the self-check re-ran it)

The record also holds the water mask's outline. It adds no computation: it keeps what the steps already know. MS4 reads it and changes nothing in how it is made.

### 4.3 The API

| Method and path | What it does | Limits and switches |
|---|---|---|
| `POST /uploads` | As in MS1, plus the checks below, the Metro Manila test (C502) that sets `live` or `private`, and the device limit (C508) | uploads switch; 10 reports per device per hour, and 300 in all per hour (MS4-Q13); JPEG up to 10 MB |
| `GET /reports/{id}` | The report's result, which is also the pin detail. It returns MS3a's C67 fields plus `mode`, `levelFrom` (MS3b) and, for a level result, `readings`, `gpsAccuracyM`, and short-lived `photoUrl`, `overlayUrl` and `layersUrl` (C503) | none |
| `GET /reports?lat=&lng=&radius=` | Published pins near a point (C509), as public pins (§4.4) | publish switch; `radius` up to 300 m |
| `GET /map/pins` | Every visible published pin, `live` and `demo`, for the app's map across Metro Manila, read from `feed-index`'s two partitions (C519) | publish switch |
| `GET /pins.geojson` | Published `live` pins as a GeoJSON FeatureCollection, read from `feed-index` (C517); `Cache-Control: public, max-age=60` (should-have). It is served by a second, read-only API that any site may load (C521). | publish switch |
| `POST /reports/{id}/flag` | Records a flag on a published `live` pin (C511) | one flag per device per pin; demo pins can't be flagged |
| `POST /samples/{sampleId}` | Runs a stored sample in `sample` mode and returns its report id (C512) | uploads switch; 5 runs per device per hour and 30 in all per hour |
| `GET /samples` | Each sample's id, credit line, licence, place and capture date, and nothing else (C512). MS8's README, video and Tested page credit them. | none |

**The upload checks** (plan Table 4):
- GPS accuracy of 50 m or better, and a nudge of at most 100 m, both stored (`gpsAccuracyM`, `nudgeM`).
- The capture time within 15 minutes, as in MS1.

The Metro Manila test uses the final point, after the nudge.

### 4.4 Public pins

- **Fields:** `id` (the report id, as plan Table 15's routes use it), `lat` and `lng` rounded to 4 decimal places (C514), `gpsAccuracyM`, `capturedAt`, `mode`, `level`, `landmark`, `passability`, `levelIsFloor`, `basis` as counts, and `flags`. `depthInMin` and `depthInMax` appear only once the release gate shows inches (C515).
- **Never:** the device id, `readings`, `nudgeM`, the claim, or any link. Links come only from `GET /reports/{id}`.
- **Nearby** (plan §12): the point's 6-character geohash cell and the 8 cells around it, then a distance filter of at most 300 m. The pin must have `published` set and `visibleUntil > now`. Newest first.
- **The feed:** `feed-index` (partition `feedPart`, sort `visibleUntil`), queried for `feedPart = live` and `visibleUntil > now`. It is cached 60 s in the Lambda and by the header.

### 4.5 Demo pins and samples

- **Demo pins** (G1, C510): `backend/scripts/demo_pins.py seed|remove`.
  - **Sources:** photos from the consented log (M9), and from Rene's open-licensed set, only those marked `demo_use ok`, never CC BY-SA, each with its credit line (Rene's decision, 8:26 PM, Oct 28).
  - **What `seed` writes:** each photo goes through the real pipeline in `demo` mode, at the photo's real spot and with its real capture time, so a demo pin never passes as current. A spot outside Metro Manila is refused. The item gets `visibleUntil` from `--until` and `expiresAt` from `--until` plus 7 days, and the `demo/` prefix has a 60-day lifecycle rule as a backstop.
  - **What `remove` deletes:** the items and their `demo/` photos, or a single pin with `remove <id>` (the tracker's N9).
  - **The `--until` date:** if MS5-Q2 keeps any demo pins, they're seeded with `--until 2026-12-20` (the tracker's N7, from MS10).
- **Samples** (C512): `backend/scripts/samples.py seed|remove`.
  - **How a sample is made:** each candidate runs once in the cloud in `eval` mode, and only its blurred copy, with faces and plates blurred by the pipeline before storage, is kept as `samples/{sampleId}.jpg`. The original is never stored.
  - **The manifest:** its id, credit line, licence, place (a short public place name, such as a street and city) and capture date, and a private source note kept apart.
  - **Sources:** as for demo pins, plus R6's fallback, clearly labelled synthetic Set B composites.
  - **Retention:** samples are kept while the sample button exists (MS4-Q11).
  - **`GET /samples`** serves the id, credit line, licence, place and capture date only, never the source note.
  - **`POST /samples/{sampleId}`** writes a `sample` report and copies the stored sample to `raw/{reportId}.jpg`, so the usual event runs the real pipeline (MS4-Q8).

### 4.6 Limits, flags and the stop switches

- **Device limits** (plan §12, C508):
  - The app sends a random device id in `X-Lusot-Device`, which CORS allows. MS5 makes the id. MS1's test screen and the scripts send one too.
  - A request without a well-formed id counts in one shared `none` bucket under the same limits, so older clients keep working.
  - A small `limits` table counts uploads and samples per device per clock hour, in UTC, with a conditional increment and a 2-hour TTL.
  - Global counters in the same table cap sample runs at 30 an hour and uploads at 300 an hour, against credit drain (MS4-Q13).
  - The table stores only a SHA-256 hash of each device id, never the id itself. The report item never stores a device id at all (C520).
- **Flags** (C511):
  - Each flag adds 1 to the pin's `flags`, once per device per pin.
  - Flags never hide a pin on their own (MS4-Q3). The app shows the count, and Rene can hide a pin with `hide_pin.py`. The script hides `live` and `demo` pins alike, without deleting them (the tracker's N9).
  - A flag record holds its device id until the pin's `expiresAt`, at most 7 days (PRIV-Q7).
  - Demo pins can't be flagged.
- **The stop switches** (plan §13, MS1):
  - **`uploads`:** stops `POST /uploads` and `POST /samples/{id}`.
  - **`model-calls`:** stops every Meta call (MS1, MS3a).
  - **`publish`** acts twice (C516). A result written while it is set is never published. While it is set, nearby and the feed return no `live` pins, though demo pins stay. Each Lambda caches the switch for 30 s, and the feed adds its 60 s cache, so a change takes effect within about 90 s. The uploader's own `GET /reports/{id}` still works.
  - As in MS1, only an explicit `off` lets traffic through, and an unreadable switch fails closed.

### 4.7 Operations and guards (section D)

- **Spend alarms** (the tracker's N6, from the MS9 draft): the Meta credits probably lapse during judging, about Nov 5, 10:00 AM Manila, and later calls are billed to the card. Two CloudWatch alarms email Rene through MS1's alarm topic, inside the free 10 alarms. MS7 verifies them.
  - one on the analysis function's invocations in an hour, above 100
  - one on the API function's invocations in an hour, above a threshold sized for Ask Lusot, which that spec sets (5,000 until then)
- **The dead-letter queue:**
  - The alarm gains `OKActions`, so Rene also hears when it clears (section D, item 2).
  - `backend/scripts/redrive_dlq.py` moves only messages less than a day old, and moves each one once. An older message has lost its raw photo to the 1-day rule, so it is deleted and counted. A message that fails again after its redrive is deleted, never redriven twice. Each message is an S3 event record holding the uploader's IP, so moving it once keeps its life at about 8 days at most (MS4-Q5, which MS3a's Task 17 also queues).
  - The script prints counts only, never a message body.
- **`sqs:ChangeMessageVisibility`** stays, since MS3a uses it for `ReportNotFound` (its R92). Its template comment is corrected (section D, item 3).
- **The roles** (least privilege, MS1's R19):
  - **The analysis role:** put and delete on `blurred/*`, `overlay/*` and `demo/*`.
  - **The API role:** get, for presigning, on `blurred/*`, `overlay/*` and `demo/*`, and get on `samples/*` with put on `raw/*` to copy a sample.
  - **The API role's database access:** `Query` on the table, `reportId-index` and `feed-index`; `UpdateItem` for flags; and read and write on `limits`.
- **API tests** (section D, item 4): the handler's lazy setup, missing environment variables, the presigned URLs' host and region, and a sentinel test. The sentinel test shows that a sentinel IP (`requestContext.http.sourceIp`), a sentinel location (a `GET /reports` point, which is the viewer's own location) and a sentinel device id reach no log on any endpoint.
- **Script guards:** every script that reads `lusot-data` refuses any path with a part named `sealed`, as C66 does, and prints counts and ids only. That covers `demo_pins.py`, `samples.py`, `redrive_dlq.py`, `hide_pin.py` and the recovery runs.
- **Logs stay off** (section D, item 4): HTTP API access logs, S3 server access logs and CloudTrail data events, unless the privacy policy covers them and Rene agrees (MS4-Q6).
- **Blur geometry:** a single-copy refactor, only if MS3a hasn't done it, with no change in behaviour, pinned by R94's test (section D, item 1). The JPEG quality sent to Meta belongs to Window 3.
- **The Files API route is conditional** (section D, item 5). It is built only if MS3a's Task 16 or MS3b's logs show SAM 504s or 413s, and then with:
  - one live check that SAM accepts `input_image` by `file_id`
  - an `expires_after` of 3600 and an explicit DELETE
  - a line in the privacy policy

  If `judge` 504s appear, stream the judge call or lower its effort.
- **C74 is retired.** MS3a's C84 builds the deadline, and the `FACE_BLUR_VERSION` tie is MS3a's (section D, item 6).

### 4.8 Recovery tests before the freeze (B2)

The fault cases are unit tests on fakes. No fault injection goes into the code that freezes. The cloud runs only the cases that need no injected fault, in `eval` mode, on a clean development photo (C87's Commons set, or development Set A after the split).

| Case | Expected | Where |
|---|---|---|
| A duplicate S3 event for a report already `done` | no Meta call, and the leftover raw object deleted (MS3a's B5, re-run on MS4's handler) | unit and cloud |
| Two deliveries racing for one report; a lease that expired; a lease lost at the final write | one set of Meta calls; a re-claim after expiry; a lost lease drops its result and leaves `raw/` (G2, MS3a's B5) | unit and cloud |
| A duplicate that meets a live lease whose holder died (out of memory, or a crash past the deadline) | The duplicate returns its message (`batchItemFailures`, MS3a's §3.1 step 4, from its Task 13 review) instead of finishing it. After the visibility timeout (about 18 minutes), the lease has expired, so the returned message re-claims, and the report ends final, with at most one extra set of Meta calls. | unit; and cloud, where the script writes a live lease with no worker behind it to stand in for the crashed holder, then posts the duplicate |
| A SAM stream that stalls | ends `failed/model_error` at the 20 s idle cap (C88), without a retry; paid for the calls made | unit |
| A SAM stream that Meta shuts down | retried as a 503 (C88), and billed again for that call | unit |
| A run that hits its deadline or a Lambda timeout | `failed/model_error` at the deadline. After a timeout, the report stays `processing`, and the message returns after the visibility timeout. The lease has expired, so the next worker re-claims and pays again, for at most 5 receives, then the dead-letter alarm | unit |
| A failed raw deletion after the final write | the result stands, and the deletion retries on its own with no second analysis | unit |

## 5. Calls (Claude's, C500 onward)

| # | Call | Why |
|---|---|---|
| C500 | **MS4's boundary.** MS4 owns the API (except Ask Lusot), publishing, photo storage by mode, the overlay and its layers, `readings`, demo pins, samples, limits, flags, the publish switch and the recovery tests. It doesn't touch the pipeline's measuring code. | Design §8 freezes measurement before the sealed run, and MS3a's §5 lists exactly these hand-offs. |
| C501 | **Five modes, each with one creation path** (§4.1). | Table 14 lists `live`, `sample` and `eval`. G1 adds `demo` and C21 adds `private`. One table keeps every path accounted for, including how test reports avoid the map. |
| C502 | **The Metro Manila test runs in the API at upload,** on the final point after the nudge. It's a point-in-polygon test on a bundled NCR boundary file, which sets the mode once. The demo script runs the same test on each demo spot. The polygon is simplified to keep the file small, and its source and licence sit beside it (MS4-Q1). | The API already has the coordinates and checks them (MS1). Deciding at creation keeps the analysis Lambda mode-blind until publish. C21 leaves the polygon's source to MS4. |
| C503 | **Photo links** are presigned GETs that last 5 minutes, issued only by `GET /reports/{id}` and only for level results. For a `live` or `demo` report they're issued while the pin is visible. For other modes, they're issued for the report's 7 days (MS4-Q10, which carries PRIV-Q2). | Plan §13 asks for short-lived links. The pin detail must show its work (plan §4, Table 21), and how long anyone holding a pin's id can open its photo is a privacy choice for Rene. |
| C504 | **Pins carry the report id,** as plan Table 15's routes do (`GET /reports/{id}`, `POST /reports/{id}/flag`). The unguessable id keeps a result private only until it is published: for `private`, `sample`, `eval`, refused and failed reports, only the uploader or the script knows it. | Draft 1 hid report ids behind a separate pin id. That left pins unable to show their work, which plan Table 21 makes a must. The plan's own flag route already shares pins' ids. |
| C505 | **The overlay** draws, on the blurred photo, the masks, each waterline that geometry computed, the fitted rim, and the numbered boxes with each reference's reading in words (the landmark category for a landmark reading). It draws no line where nothing computed one. This is drawn in fixed colours that stay legible on any photo (a JPEG has no app theme). **The layers file** keeps the same marks as vectors, so MS5 can draw them one after another. No face or plate outline goes into either. The overlay's words follow MS3a's C81 wording and R3's language, and Rene reviews them (M20). | Plan §4 and Table 21: each pin shows the masks, the fitted rim and the waterline it used. The should-have overlay that draws itself needs its layers apart. |
| C506 | **"No flood seen" isn't published** (MS4-Q2's default). The uploader still sees it. | MS3a stores no photo or basis for it (its C61), so such a pin couldn't show its work (plan §13). C17 calls a false "no flood seen" the most dangerous miss. |
| C507 | **`readings`** is stored on the item for level results and returned by `GET /reports/{id}`. It is a list of `{id, kind, landmark, level, inches, used, dropped}`, where `inches` is present only once the gate shows inches. | Table 14 keeps per-reference readings, and the pin detail lists its evidence. |
| C508 | **Device limits** live in a separate `limits` table, provisioned at 2 read and 2 write units, with a TTL. The device id comes from `X-Lusot-Device`. A missing or malformed id counts in a shared `none` bucket. It's a soft limit, and the stage throttling stays the hard one. | Plan §12's per-device limits. A separate table keeps the reports table clean. The shared bucket keeps MS1's test screen, the APK under M14, and the smoke script working until MS5 sends ids. |
| C509 | **Nearby reads 9 geohash cells,** with no sort-key range, filtered on `published` and `visibleUntil > now`. `radius` is capped at 300 m. | Plan §12's nine-cell rule covers any 300 m circle. Demo pins keep their old capture times, which a sort-key range would cut. |
| C510 | **Demo pins use a `demo/` prefix** with only a 60-day backstop lifecycle rule. They carry `visibleUntil` from the script's `--until` date and `expiresAt` 7 days later, and they keep the photo's real capture time. Only `demo_pins.py` makes or removes them. | G1 exempts demo pins from the 3-hour hide and the 7-day delete. MS1's rules on `blurred/` and `overlay/` would delete them after 7 days. The backstops catch a missed `remove`. |
| C511 | **Flags are counted, never acted on automatically** (MS4-Q3). One per device per pin is kept in `limits` until the pin's `expiresAt`. Demo pins can't be flagged. | The client makes its own device id, so "3 devices" can be one person. That could hide a real deep-water pin, or every demo pin. A count lets people judge, and the script lets Rene act. |
| C512 | **Samples are stored only as blurred copies,** each made by one cloud run in `eval` mode. `POST /samples/{id}` runs the real pipeline on the stored copy. `GET /samples` serves the id, credit line, licence, place and capture date only. Sample runs are capped at 5 per device per hour and 30 in all per hour. | CLAUDE.md: blur faces and plates before anything is stored. The plan's sample button runs the live pipeline (§4). Source notes can name a donor. The place and date are what MS8's credits need (the tracker, Oct 29), and a demo pin already shows the same. Device ids are free to make, so the global cap bounds credit drain at about $1 an hour. |
| C513 | **`eval` is for scripts only.** The recovery runs and the D-row checks write `eval` items directly, under the `EVAL` key, and smoke runs post a point outside Metro Manila. | No test may put a pin on the public map, and the smoke run should still exercise the real upload path. |
| C514 | **Public coordinates are rounded to 4 decimal places,** about 11 m (MS4-Q4). | A pin marks a spot, not a phone. Rounding blunts device-precise tracking at no cost to the map. |
| C515 | **Inches appear only after the gate.** A literal `INCHES_SHOWN: "false"` in the API function's environment in the template controls `depthInMin`, `depthInMax` and `readings[].inches` in responses. It is not a template parameter. MS6's post-gate step changes it to `"true"` in the commit that records the gate's decision, and the next deploy applies it. | MS3b's C308 makes the API change a step after the gate. SAM CLI reuses a parameter's previous value on an existing stack when the overrides don't name it (the builder check read SAM CLI 1.170.0's source), so a committed parameter default would never reach the stack. A literal always deploys, and stays in git. |
| C516 | **The publish switch acts at write time and at read time** (§4.6). Demo pins stay visible (MS4-Q7). | At read time alone, results written while it was set would reappear when it's cleared. Demo pins are seeded by us from consented photos, and judges should never see an empty map. |
| C517 | **The feed carries `live` pins only,** from a sparse `feed-index` (2 read and 2 write units). | Plan Table 15 and §4: the feed is for other flood maps, which might show a demo pin as a current flood. A Scan would read every mode against 10 read units. |
| C518 | **MS3b adds the evidence record** (§4.2) to the pipeline's result type, as part of its own edits to those modules. The overlay, its layers and `readings` read the record, and MS4's tasks for them wait for MS3b's merge. `levelFrom` is returned as MS3b names it. Window 3 receives the field list through the tracker. | Only the steps know which reference was used or dropped and why, and MS3b is editing them now. A second window changing the same frozen code would risk the depth output. |
| C519 | **The app's map reads `GET /map/pins`:** every visible published pin, `live` and `demo`, from `feed-index`'s `live` and `demo` partitions. | Nearby covers 300 m, and the public feed carries `live` pins only, so without this the map would show demo pins only near the point asked about. That would defeat their purpose, an empty map for judges (C516). |
| C520 | **No device id is stored with a report,** and `limits` keeps only a SHA-256 hash of each id. | Storing it would link one device's reports and exact locations for 7 days. A random id's hash can't be reversed, and the counters need only equality. The stop switches and `hide_pin.py` are the tools against abuse. |
| C521 | **The public feed has its own read-only HTTP API,** with `AllowOrigins: *`, `GET` only and no credentials. The app's API keeps its own origins. | HTTP API CORS applies to a whole API, and API Gateway ignores the Lambda's CORS headers when CORS is set. Other flood maps, or a judge's web GeoJSON viewer, load the feed in a browser on another site. |

## 6. Left to the builder

- The module split inside `backend/api/src/` and `backend/analysis/src/lusot_analysis/`, and the scripts' flags beyond those named here.
- The overlay's line widths, font and colours, within the `ui-ux-pro-max` and `frontend-design` skills' legibility rules. The colours must stay legible on light and dark photos.
- The layers file's exact schema, as long as it carries kind, id, outline and draw order and no face or plate outline.
- The polygon's simplification tolerance. Every test point in S2 must keep its side.
- The exact shapes of the error responses, following MS1's existing ones.

## 7. Done when

| # | Check | Proved |
|---|---|---|
| S1 | **Upload to pin in the cloud,** with the full pipeline (MS3a and MS3b merged). An upload outside Metro Manila goes through `POST /uploads` and gives a `private` report with its blurred photo, overlay, layers and `readings`, and no pin. A `demo` seed of one consented Manila photo then appears in nearby, with its links in `GET /reports/{id}`, and is removed. The `live` publish path is the same code, proved by unit tests. | cloud runs and unit tests |
| S2 | **The Metro Manila test.** Points about 200 m inside and outside the NCR border land on their side: near Caloocan and Meycauayan, Valenzuela and Obando, Marikina and San Mateo, Pasig and Cainta, Taguig and Taytay, Muntinlupa and San Pedro, Las Piñas and Bacoor, and a point in Manila Bay. Their coordinates and sources are recorded in the test. | unit tests |
| S3 | **The upload checks:** accuracy above 50 m and a nudge above 100 m are refused, and `gpsAccuracyM` reaches public pins | unit tests |
| S4 | **Demo pins:** `mode: demo`, `visibleUntil` later than capture plus 3 hours, the real capture time, no flag accepted, and a clean `remove` | script run |
| S5 | **Samples:** stored only blurred; `GET /samples` serves no source note; a run is `sample` and never pins; both caps hold | unit tests and a cloud run |
| S6 | **The stop switches** work without a redeploy, and an unreadable switch fails closed. A result written while `publish` is set is never published. The 90 s delay is stated. | unit tests and a cloud check |
| S7 | **Limits and flags:** the 11th upload and the 6th sample from one device in a clock hour are refused, and so are the 31st sample and the 301st upload of the hour in all. A flag is counted once per device, flags never hide a pin, and no stored item holds a raw device id. | unit tests |
| S8 | **G2 on MS4's handler:** MS3a's B5 cases pass (a race, an expired lease, a lease lost at the final write) | unit tests, plus B5's cloud evidence re-run |
| S9 | **The recovery cases in §4.8** behave as stated | unit tests, and cloud runs for the first two rows |
| S10 | **Section D's API tests:** lazy setup, missing environment variables, the presigned URLs' host and region, and the sentinel IP, location and device id reaching no log | unit tests |
| S11 | **The feed:** a GeoJSON FeatureCollection of `live` pins only, carrying the `Cache-Control` header, with rounded coordinates, served by the read-only API with `Access-Control-Allow-Origin: *` | unit tests and a template test |
| S15 | **The map endpoint:** `GET /map/pins` returns every visible published `live` and `demo` pin, and none while the publish switch hides `live` ones, apart from the demo pins | unit tests |
| S16 | **The evidence record:** the overlay, the layers and `readings` are built from MS3b's record alone, and S13's copy rules hold on every word they draw | unit tests, after MS3b's merge |
| S12 | **`InchesShown`** in both states: false hides every inches field, and true shows them | unit tests |
| S13 | **Copy:** no "safe" in any form, no crossing advice and no whole-road wording, in the overlay's words and in every response string | unit tests and Rene's review (M20) |
| S14 | **Operations:** the two spend alarms exist on the alarm topic. The dead-letter alarm has `OKActions`. A redrive dry run lists the counts it would move and delete. `npm run check` and CI pass, and the free-plan units stay at or under 25 and 25. | template tests, a dry run, CI |

## 8. Questions for Rene

Each has a default that the draft plan follows (D7).

| # | Question | Options | Default |
|---|---|---|---|
| MS4-Q1 | **Where the Metro Manila boundary comes from** (C21, C502). | (a) OpenStreetMap's Metro Manila boundary, from a downloaded open extract, under ODbL with the "© OpenStreetMap contributors" credit. The polygon file is shared under ODbL. (b) geoBoundaries' Philippine ADM1 file for the National Capital Region, if its page shows a licence that allows redistribution with credit. (c) PSA or NAMRIA boundaries, if licensed for redistribution. In every case it is a downloaded file, never a Nominatim call from a laptop, since CLAUDE.md allows Nominatim only from the API Lambda. | (a), with its licence confirmed on the source page before the file is committed |
| MS4-Q2 | Does a "no flood seen" result become a public pin? It stores no photo or basis, so its pin couldn't show its work. | (a) yes, shown as "no flood seen at this spot", hidden after 3 hours; (b) no, and the uploader alone sees it | (b) |
| MS4-Q3 | **What flags do.** Device ids are made by the app, so several "devices" can be one person. | (a) a pin hides at 3 different devices; (b) flags are counted and shown, and Rene hides a pin by script; (c) a pin hides at 1 flag until Rene reviews it | (b) |
| MS4-Q4 | Rounding of public pin coordinates | (a) 4 decimal places, about 11 m; (b) as reported; (c) 3 decimal places, about 110 m | (a) |
| MS4-Q5 | Add "redrive only dead-letter messages under a day old, each once" to CLAUDE.md? This is section D, item 2, and MS3a's Task 17 also queues it. | (a) yes; (b) no, and the script only warns | (a) |
| MS4-Q6 | Access logs (HTTP API, S3 server access, CloudTrail data events) | (a) stay off, as now; (b) on, with a privacy-policy line for each | (a) |
| MS4-Q7 | What the publish switch hides | (a) `live` pins only, while demo pins stay; (b) every pin | (a) |
| MS4-Q8 | **Samples: run the real pipeline each time, or once?** | (a) each time, about $0.03 a run, capped at 5 per device and 30 in all per hour; (b) once per sample, serving the stored result. That saves credits, but plan §4's sample button runs the live pipeline. | (a). If MS9-Q1 ends on a pause in analysis, (b) becomes the fallback during the pause: a sample shows its seeding run's result, marked as saved and dated (the tracker's N2, conditional). |
| MS4-Q9 | An open-licensed demo photo whose source gives no spot | (a) samples only, never a demo pin; (b) a pin at the described place's centre | (a) |
| MS4-Q10 | **Who can open a pin's photo, and for how long** (this carries PRIV-Q2). The pin detail must show the photo and overlay. | (a) For a pin, links are issued while it is visible (3 hours), to anyone holding its id. For an unpublished result, they are issued for its 7 days to the holder of the id. (b) For every report, for its 7 days, to anyone holding the id. The privacy policy then states the chosen rule. | (a) |
| MS4-Q11 | Samples are kept while the sample button exists, as blurred copies with credit lines. That exempts them from the 7-day rule, as G1 does for demo pins. | (a) yes, until the button is removed after the hackathon; (b) no, and the samples are re-seeded every 7 days | (a) |
| MS4-Q12 | Public-domain-marked photos (such as 9 of C87's Commons set), which aren't CC0, as samples or demo pins | (a) yes, credited like CC0; (b) no, only CC0 and CC BY, as Rene's 8:26 PM decision names | (b), until Rene says otherwise |
| MS4-Q13 | **A global hourly cap on uploads.** Device ids are free to make, so only `MaximumConcurrency` 5 bounds spending. That still allows a few hundred runs an hour, which could use up the $150 of credits in a day or two of sustained abuse. | (a) 300 uploads an hour in all, so abuse costs at most about $10 an hour, while a real rush beyond it is refused with a retry message; (b) no cap, with the model-calls switch as the only brake | (a) |

The design's open questions bear on this too:
- **R6:** how many consented photos M9 secures sets how many demo pins there are. Its fallback (a), labelled synthetic Set B composites, can serve as samples (§4.5).
- **R3:** sets the overlay's language.
- **R7** doesn't change MS4.

## 9. Not in MS4

- **Ask Lusot:** `POST /ask` and `POST /ask/voice`, the question limit and Nominatim. They get their own spec, which must honour the publish switch.
- **The screens, the consent flow, the privacy page and the overlay's animation** (MS5). MS5 also makes the device id. It polls a report for at least C84's run deadline (about 150 s, since C88's margin), not the plan's 120 s.
- **Clip mode,** unless it is finished before the freeze.
- **CORS for Amplify Hosting's domain** arrives with M6 (Oct 31), as a template parameter.
