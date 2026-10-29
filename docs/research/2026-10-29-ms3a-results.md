# MS3a results: the landmark core in the cloud (Oct 29, 2026)

MS3a's Task 16 deployed the landmark core and ran its cloud checks on Oct 29, between 9:00 and 10:16 PM Manila time (UTC+8). This note records counts and timings only: no photo, photo name or path, key or account ID. The photos are C87's Wikimedia Commons flood photos from Metro Manila. Their credits are kept in `attribution.csv` beside them in the private Set C folder. The [MS1 probe note](2026-10-28-ms1-probe-results.md) covers the earlier STURM probe and its dataset.

Markers: ✅ as expected · ⚠️ needs action or a decision · ➕ new fact.

## 1. A bug the real-data run caught first (C90) ➕

- **What happened:** B3's local live run (Task 16 Step 5, run first under R121) ended `failed/model_error` on C87's first photo, with no HTTP status.
- **The cause:** SAM sends the mask of a box with a side over 1024 px scaled so the box's longer side is 1024. The photo's water was a 700 × 1600 box, and SAM sent it as a 448 × 1024 raster. The client required a raster the size of its box, so it refused a valid answer.
- **Why nothing caught it:** MS1's probe photos were all under 1000 px. C85's 1600 px `person` masks came unscaled, so the scaling is per mask.
- **The fix:** C90 accepts a raster scaled so the box's longer side is exactly 1024 px, with the other side within 1 px of the same ratio, and only when the box has a side over 1024 px. It scales the raster up to its box with center-aligned nearest-neighbour. Any other size still raises. It came with 17 tests and two review rounds (`044fdad`, `14ad29b`).
- **Why it mattered:** without it, every photo whose water spans more than 1024 px would have ended `failed/model_error`. Floodwater usually spans the frame, and the app sends up to 1600 px.

## 2. B1: the core end to end in the cloud ✅

`uv run backend/scripts/smoke_upload.py` printed `SMOKE OK in 353.6 s` (exit 0), so C71's fallback wasn't needed.

| What | Result |
|---|---|
| B1's 5 Commons photos | 4 CC BY 2.0, 1 public domain |
| A level | **2 of 5:** `done/level` below gutter, PATV |
| No flood seen | 1: `done/no_flood_seen` |
| Refused | 2: `photo_unusable` 1, `no_usable_reference` 1 |
| Failed | 0 |
| Seconds from upload to a final status | 27.0, 35.6, 41.8, 43.5, 63.2: **p50 41.8 s, max 63.2 s**, under B1's 120 s bound (C68) |
| The synthetic dark JPEG | `refused/too_dark` in 2.1 s, with **0 Meta calls** |
| C67 fields | The smoke script checked every report body: `noFloodSeen` on `done`, the level fields only with a level, and no location, `readings`, `photoKey` or claim |

**Drop causes, as counts over the 5 photos:**
- people over the cap of 6: 25
- people not adult: 11
- people wading: 3
- wheels not linked to a vehicle: 5
- wheels under 40 px: 2
- wheels of a dropped vehicle: 4
- vehicles of another type: 2
- moving vehicles: 2
- a vehicle with no reading: 1

## 3. B3: the same code on the laptop and in the cloud ✅

- **Synthetic replay test:** it passes in the suite (`test_b3_replay_through_runner_and_handler_match`).
- **Real-data replay:** `probes/run_pipeline.py live` on C87's first photo exited 0 with `refused/photo_unusable` (a river with no street, Rene's Q5 rule), 6 Meta calls and 18 s. `pytest -q tests/test_handler.py -k b3` on that run gave **2 passed, 0 skipped**.

## 4. B4: nothing unblurred is stored ✅

After the smoke run:
- no `raw/` object was left for any of its 6 photo reports, refused and failed ones included
- `blurred/` held a photo only for the 2 level results

## 5. B5: pay once ✅

- **Unit tests:** they pass in the suite (racing deliveries, a delivery after the result, a delivery after an expired lease, and C89's live lease).
- **Cloud:** the script posted photo 1's upload form again. S3 took it (204), the raw photo was gone in 2.4 s, and the log shows `already_finished` with no Meta call. Still only one line for that report carries Meta calls.

## 6. The missing-photo code (spec §3.6, R93) ✅

- A report whose photo never came ended `failed/photo_missing` 2.1 s after its notification. S3 said **`NoSuchKey` (HTTP 404)** under the role's `raw/`-limited `s3:ListBucket`.
- So `AccessDenied` left the missing-photo rule (`d32ddf6`, after a delta review, with its notes in `5262f5d`). A real 403 now retries into the dead-letter queue and its alarm.
- **After the redeploy** (10:15 PM), the smoke script's own missing-photo check, which makes no Meta call, gave `failed/photo_missing` with `NoSuchKey` (404). It took 23.1 s in all, and the handler's own work was 1.7 s. The rest was the cold start: its init timed out at Lambda's 10 s limit and ran again inside the invocation (§8, P3).

## 7. Meta calls, tokens and cost

| Run | Meta calls | Tokens (billed) | Estimated cost |
|---|---|---|---|
| Smoke run, 5 photos (7 SAM phrases and 1 Muse Spark answer each) | 40 (SAM 35, Muse Spark 5) | 12,747 in, 12,621 out | about $0.157 |
| B3 live runs (two) and one diagnostic SAM call | 12 (SAM 11, Muse Spark 1) | 2,373 in, 1,442 out | about $0.037 |
| **Total** | **52** | | **about $0.194** ($0.1571 + $0.0366), within the plan's worst case of about $0.67 |

- SAM is billed per image ($2.50 per 1,000), and Muse Spark by billed tokens. No call ended on a 504 or a 413.
- Muse Spark's reasoning took 1,467 to 2,984 tokens per answer.

## 8. What the run shows for P2, P3, P4 and P6

- **P2 (wheel boxes and the 40 px rule):** the one photo with cars had 8 SAM wheels. 2 were under 40 px, 2 weren't linked to a vehicle, and 4 belonged to a vehicle dropped for its type or for moving. A wheel never decided a level here; people did. ⚠️ C56's 40 px number still waits for Set B and the Manila check.
- **P3 (latency):**
  - The Lambda ran 26 to 62 s per photo, against the 180 s timeout.
  - SAM's 7 phrases ran in parallel, each taking 1.9 to 4.9 s. Muse Spark took 11.7 to 19.5 s.
  - ⚠️ **Cold starts sit at Lambda's 10 s init limit.**
    - The first cold start after the 9:51 PM deploy took 9.19 s of init.
    - The one after the 10:15 PM redeploy hit `INIT_REPORT … Status: timeout` at 10.00 s. Lambda then runs init again inside the first invocation, under the function's 180 s timeout, so that cold start lost about 10 s.
    - Found by the tracker's read-only log check (10:23 PM), and confirmed in CloudWatch by Window 3.
    - **No MS3a done-check is broken.** B1's 120 s bound (C68) includes the first cold start, and that photo was final in 41.8 s.
    - **But every cold start now costs 9 to 20 s.** That matters for the app's 120 s poll (MS5) and for the self-check's time rule (MS3b-Q3).
    - **Fix:** load the heavy imports and models lazily, out of static init, and re-measure. Deferred to MS4, which owns the handler's next changes.
  - ⚠️ **The slowest photo** (62.1 s in the handler) spent only about 19 s on the models, so about 43 s is unexplained. It had 28 SAM masks: 16 people, 9 faces and 3 wheels.
    - **The leading candidate is SAM's mask decoding** (the final review, 10:40 PM). Each mask is decoded twice in pure Python, once by meta-sam-parser to check it and once by `_instances`. Both run outside `sam_ms` and hold the GIL across the 7 SAM threads. On the laptop, one 448 × 1024 mask takes about 3.3 s in `_instances`, and 16 person masks of 80 × 220 take about 1.8 s.
    - **The face blur is unlikely.** `blur_for_meta` takes about 0.13 s on a 1600 px photo, and its cost doesn't grow with the face count. The second blur, before storage, runs only for a level, and this photo had none.
    - MS4 logs a per-phrase parse time and measures it on Lambda.
- **P4 (empty water masks):** SAM found water on 4 of the 5 B1 photos, and on the B3 photo. The fifth ended `no_flood_seen`. Without labels this can't say whether that is right, so the Manila check measures it on labelled photos (C34, C40).
- **P6 (busy scenes):**
  - SAM returned up to 16 people on one photo. The busiest photo, at 504 MB, had 13 people, 8 wheels and 5 vehicles.
  - The people cap of 6 dropped people on 4 of 5 photos (25 in all).
  - Max Memory Used was 411 to 504 MB of 1,024.
  - ⚠️ Whether 6 people cover the readable references stays open for the first Manila photos.

## 9. What stays open

- C90's rule rests on one scaled record and C85's unscaled ones. A mask SAM sends in any other shape ends as a visible `model_error`, never as a wrong reading. MS4's alarms and the Manila check would show it.
- The unexplained time on crowded photos (P3 above): SAM's double mask decoding is the leading candidate. MS4 measures it.
- Cold-start init at Lambda's 10 s limit (P3 above): MS4.
- P2, P4 and P6 need labelled Manila photos (after the Oct 30 split) and Set B.
