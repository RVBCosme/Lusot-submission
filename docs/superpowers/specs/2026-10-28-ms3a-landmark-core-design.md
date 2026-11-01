# MS3a Landmark core: spec

- **Date:** Oct 28, 2026 (Manila)
- **Status:** Approved by Rene on Oct 28, 2026 (3:24 PM), relayed by the tracker session. The approval covers C42 to C86, with Rene's Q1 to Q4 answers and the delegated C51, C76 and C81. Calls added after it, from C87, are Claude's under D7 until Rene looks at them.
- **Before the approval:** final and builder-checked on Oct 28.
  - **The builder check:** its three questions are settled. C57 follows `eval/rules.md` as written, and calls C69 to C71 are added.
  - **Rene's answers to §7** (Oct 28, 7:58 AM):
    - Q1 to Q3 keep the defaults.
    - Q4 changes C54: a floor means "this level or deeper". `eval/rules.md` §6 was updated with his OK (v0.6).

  Claude proceeds on the calls in §4 (D7, D15). Rene approves the whole spec.
  - **The plan review** (Window 3, Oct 28, D20) settled the plan's five spec gaps and its provisional calls as C72 to C81, and aligned C43 and C71 with them.
- **Needs first:** MS1 Task 4 (the Meta client, with R27) and Task 5 (the probes, prompt v1, schema v1 and `annotate`). Task 5's probe note settles §6. Under D20, the plan's Tasks 1, 6, 10, 11 and 12 need neither, so they are built before MS1 closes.
- **Implements:**
  - plan §7 steps 1, 2 and 4 to 8 (step 3 and geometry are MS3b), §8 Table 8, §9 (classes and the three messages), Tables 5, 6 and 14, and §13 (stop switches, blur before storage, deletion)
  - plan Table 11's W1, W6, W9, W13 and W25, and §19's logging and idempotency practices
  - design §8 MS3 row (3a, due Oct 29), D12 and C20 (blur first), D13 (people count fully), D14 (dry streets), C17 (`levelIsFloor`), G2 (claim before paying, pulled forward from MS4) and G4 (Table 8 as written)
  - `eval/rules.md` §1 (levels and classes) and §6 (reading rules)
  - MS1's spec (C22 to C41), its plan's interfaces (Tasks 3 to 8) and the MS1 review rulings R22, R26 and R27

## 1. Goal

The working core. A photo uploaded from the app comes back from the cloud with a landmark-only result:
- an MMDA level and its passability class, with the landmark and the references behind it, or
- one of plan §9's three other messages, kept separate: no flood seen, can't tell (a refusal with its reason), or processing failed (with its reason)

## 2. Done when

| # | Check | Evidence | Result (Oct 29) |
|---|---|---|---|
| B1 | Core works end to end in the cloud (plan Table 22, Phase 3) | The smoke script uploads two kinds of photo through the API: 5 Wikimedia Commons flood photos chosen by C87 (CC BY or public domain, Metro Manila), and one synthetic dark JPEG. STURM-FloodDepth stays offline (Rene, 5:53 PM): its licence is unverified.<ul><li>Every report reaches `done`, `refused` or `failed` within 120 s (C68, P3). None stays `pending` or `processing`.</li><li>At least one of the 5 photos gives a level. If none does, C71 applies.</li><li>The dark JPEG ends `refused/too_dark`, and its log shows no Meta call.</li><li>`GET /reports/{id}` returns the fields in C67.</li></ul> | ✅ `SMOKE OK` (exit 0, 353.6 s). 2 of 5 photos gave a level (below gutter, PATV), 1 no flood seen, 2 refused, 0 failed. Upload to final: p50 41.8 s, max 63.2 s. The dark JPEG: `refused/too_dark` with 0 Meta calls. C67's fields were checked on every body. C71 wasn't needed ([results note](../../research/2026-10-29-ms3a-results.md) §2). |
| B2 | Rules are tested | Unit tests cover:<ul><li>every Table 8 row, `not_visible`, and the body rule (C53)</li><li>linking (C55), the drops and caps before numbering (C69, C70), and every drop rule in §3.3</li><li>combining: floors, ties and the gutter gap (C54); the people rules (C57)</li><li>the gate on Muse Spark's answer (C51, C52) and every reason code in §3.4</li><li>the claim: fresh, finished, live lease, expired lease, and a lease lost at the final write</li><li>the stop switch, both set and unreadable; the missing-photo codes; the quality gate</li><li>a rejected key (C73), a stale `blurred/` photo (C72), unanswered boxes (C76), a repeated claim or write (C82) and non-JPEG bytes (C83)</li><li>the SAM blur (C48), the API fields (C67), and polling through `processing`</li></ul> | ✅ 535 analysis tests pass, with 1 skipped only when no real run is given, plus 65 scripts tests (`npm run check:py`). They include C90's 17 and R93's cases. |
| B3 | The same code runs on the laptop and in the cloud | One set of saved model outputs, replayed through the offline runner and through the handler's pipeline call, gives identical results | ✅ The synthetic replay test passes. On C87's first photo, the real run's replay gives 2 passed, 0 skipped (Task 16 Step 5; [results note](../../research/2026-10-29-ms3a-results.md) §3). |
| B4 | Nothing unblurred is stored (W25) | <ul><li>Unit test: the SAM face and plate boxes are blurred, and nothing else changes.</li><li>After the smoke run, `blurred/` holds a photo for each level result and nothing else.</li><li>No `raw/` object remains for any report, refused and failed included.</li></ul> | ✅ The unit test passes. After the smoke run, no `raw/` object was left for its 6 photo reports, and `blurred/` held a photo only for the 2 levels ([results note](../../research/2026-10-29-ms3a-results.md) §4). |
| B5 | Pay once (G2) | <ul><li>Unit tests:<ul><li>Two deliveries racing for one report make one set of Meta calls.</li><li>A delivery after the result makes none and deletes a leftover raw object.</li><li>A delivery after an expired lease re-claims.</li></ul></li><li>Cloud: the smoke script re-posts the same upload form after the result (a reused upload link, plan §7 step 8). This makes no Meta call, and the new raw object is deleted.</li></ul> | ✅ The unit tests pass. In the cloud, the reused form was taken (204), the raw photo was gone in 2.4 s, and `already_finished` made no Meta call ([results note](../../research/2026-10-29-ms3a-results.md) §5). |

## 3. What gets built

### 3.1 Handler (replaces the MS1 stub, C28)

For each message (batch size 1), in order:
1. Skip S3 test events. Delete any object whose key isn't `raw/r_<32 hex>.jpg` (MS1).
2. Find the report through `reportId-index`. If it isn't there yet, return the message for retry, because the index can lag (MS1).
3. Load the Meta key, once per process; a failed load isn't cached. Load the prompt and schema (C79). Then read `/lusot/stop/model-calls`. If any step fails, return the message and leave the report untouched (C60). An unreadable switch is a tested fail-closed path: the report stays `pending`.
4. **Claim (G2, C46).** A conditional update moves the report to `processing` and sets `claimToken` and `claimedAt`. It succeeds from `pending`, or from `processing` with a lease older than 15 minutes. If the claim fails:
   - **The report is `done`, `refused` or `failed`:** delete `raw/{id}.jpg` if it is there (a retried delete or a reused upload link), then finish the message.
   - **Another worker holds a live lease:** return the message and leave `raw/` alone (C89). Its copy comes back after the visibility timeout, when the report is final or the lease has expired.

   Neither path calls Meta. After a successful claim, delete `blurred/{id}.jpg`, before any Meta call (C72).
5. If the switch reads anything but `off`, end with `failed/model_calls_paused` (C60).
6. Get `raw/{id}.jpg`. The S3 error code `NoSuchKey` ends with `failed/photo_missing` (R22, narrowed; `AccessDenied` left the rule after Task 16 recorded `NoSuchKey` in the cloud, R93). Any other S3 error returns the message, so an `AccessDenied`, or a 403 from clock skew or a bad signature, retries, and a lasting one reaches the dead-letter queue and its alarm. A photo whose bytes don't start with JPEG's `FF D8 FF` ends with `failed/bad_file`, before anything decodes it (C83).
7. Run the pipeline (§3.2).
8. Publish (§3.2 step 8).

Every write after the claim requires `status = processing` and this worker's `claimToken`. If that check fails, the lease was lost: the worker drops its result, leaves `raw/` alone and finishes the message. A failed check that finds this worker's own token already applied is the worker's own earlier attempt, repeated by the AWS SDK's retry, and counts as success (C82).

**Errors (C59)**

| Error | Result |
|---|---|
| A Meta 401, 402 or 403: the key or the account was rejected | The handler drops its cached client and returns the message. The report stays `processing` until a redelivery re-claims it (C73). |
| Any other Meta error that outlasts the client's own retries, or a Meta call that would pass the run's deadline (C84) | `failed/model_error` |
| A Muse Spark answer that isn't valid JSON or fails the schema | `failed/model_error` (C47) |
| Any other exception inside the pipeline | `failed/pipeline_error` |
| An AWS error (S3, DynamoDB, SSM) other than `NoSuchKey` on the raw photo | The message returns for an SQS retry. The lease expires before the queue redelivers it (C46). |

### 3.2 Pipeline (`lusot_analysis/pipeline/`, one module per step)

The Lambda and the offline runner call the same pipeline function. Table 8's rows and the level scale live in one rules module inside the package (the plan's `rules/`). That way the image copies them with the code.

0. **Face blur (C20).** `blur_for_meta` runs first. A file it rejects ends with `failed/bad_file`. It rejects a file that is undecodable, over 50 MP (R25, R26), or has a short side of 32 px or less (R27). A face box that lands on a wheel would blur that wheel's landmark (P5).
1. **Quality (step 1).**
   - Brightness is the mean grey value. Sharpness is the Laplacian's variance.
   - Both scores use the decoded upload before the face blur, shrunk to at most 1,600 px the way `blur_for_meta` shrinks it (C58).
   - Below either cutoff (C44), the report ends `refused/too_dark` or `refused/too_blurry`, with no Meta call.
2. **Segment (step 2).**
   - The 7 `SAM_PHRASES` run in parallel through `MetaClient.segment` on the `BlurredImage`.
   - Each wheel links to a vehicle (C55). Rims are linked in 3b.
   - An empty `floodwater` result still goes to Muse Spark (D14, C51).
3. *(Cutting reflections is step 3, in MS3b.)*
4. **References (step 4).**
   1. **Before numbering (C69, C70).**
      - SAM's results lose every wheel that fails the 40 px rule (C56) or links to no single vehicle (C55). These wheels get no number, and Muse Spark never sees them.
      - The cap keeps at most 6 vehicles and 6 people, largest boxes first. Wheels follow their kept vehicles.
      - Every drop and cut is logged by count and cause.
   2. `number_boxes`, then `draw_numbered_boxes`, then `MetaClient.judge` in strict mode. The prompt and schema are the version the probe note settles (P1).
   3. `jsonschema` checks the answer (C47).
   4. A per-item form of `check_ids` drops the items with bad ids (C47). The probe's version only lists the problems.
   5. The gate decides, in this order:

      | Answer | Result |
      |---|---|
      | `photo_usable = no` | `refused/photo_unusable` |
      | `standing_water = unsure` | `refused/water_unsure` |
      | `standing_water = no`, and no answered waterline sits above its lowest mark (C52) | `done`, no flood seen |
      | `standing_water = no` otherwise | `refused/water_unsure` (C52) |
      | `standing_water = yes`, with an empty water mask | `refused/no_water_found` (C51, P4) |
      | `standing_water = yes`, with water in the mask | on to the drops in §3.3 |

   6. The drops in §3.3 that need Muse Spark's answer follow. If no reference is left, the report ends `refused/no_usable_reference`.
5. **Measure (step 5, landmarks only).** See §3.3.
6. **Combine (step 6).** See §3.3.
7. **Map (step 7).** The level takes its class from `eval/rules.md` §1. `landmark` is the deciding reference's (C49, C54), and `basis` counts the references kept.
8. **Publish (step 8).**
   1. For a level result only (C61): blur the SAM `face` and `license plate` boxes (C48) on the face-blurred image, and save `blurred/{id}.jpg`. The claim already removed any older copy (§3.1 step 4, C72).
   2. Write the result under the claim (§3.1).
   3. Delete `raw/{id}.jpg`. If the delete fails, the message returns. The redelivery finds the report finished and only deletes (§3.1 step 4).

### 3.3 Reading rules

**Wheel rows.** These are Table 8's rows, as written (G4). They apply to `sedan_hatch` and `suv_mpv` only (C45).

| `waterline` | Level |
|---|---|
| `tire_only` | below_gutter |
| `rim_quarter` | half_knee |
| `hub` | half_tire |
| `rim_three_quarters` | knee |
| `rim_top` | tire |
| `wheel_covered` | tire, as a floor |
| `not_visible` | no reading |

**People rows.** These are Table 8's rows, for adults (D13, C57), except `ankle`, which gives no reading since C91.

| `waterline` | Level |
|---|---|
| `ankle` | no reading (C91; Table 8 says below_gutter) |
| `mid_shin` | half_knee |
| `knee` | knee |
| `mid_thigh` | tire |
| `waist` | waist |
| `chest` | chest |
| `above_chest` | above_chest |
| `not_visible` | no reading |

**Body waterline (C53).** It counts only for a `sedan_hatch` or `suv_mpv` whose wheels are hidden: every linked wheel is `wheel_covered` or `not_visible`, or none is linked. A linked wheel that failed the 40 px rule, or that Muse Spark left unanswered, still counts as visible, so that vehicle gets no body reading (C69, C76).

| `body_waterline` | Reading |
|---|---|
| `mid_door`, `window` | tire, as a floor |
| `below_bumper`, `bumper`, `door_sill` | none. If one of the vehicle's wheels is `wheel_covered`, the vehicle is dropped. |
| `not_visible` | none |

**Drops.** Each drop is logged by count and cause.

| What | Dropped when | Source |
|---|---|---|
| Any answered item | Its id isn't among the boxes, sits in the wrong list, or is answered twice | C47 |
| Vehicle | `moving` is `yes` or `unsure` | plan §7 step 4, W1 |
| Vehicle | Its type isn't `sedan_hatch` or `suv_mpv`, so its wheels and body give no reading | C45, C53 |
| Vehicle | Its wheels fail C54's test: an exact wheel reading sits more than one level below its deepest wheel | C43 |
| Vehicle | It has a `wheel_covered` wheel, and its body waterline is at `door_sill` or lower | C53 |
| Wheel, before numbering | The longer side of its SAM box is under 40 px | plan §7 step 4, C56, C69, P2 |
| Wheel, before numbering | No vehicle box holds its centre, or more than one does | C55, C69 |
| Vehicle or person, before numbering | Beyond the cap of 6 per kind, smallest boxes first. A cut vehicle takes its wheels with it. | C70, P6 |
| Wheel | Its vehicle was dropped | C55 |
| Person | `adult` is `no` or `unsure` | plan §7 step 4 |
| Person | Wading (`standing_still` is `no` or `unsure`) while any adult in the photo is standing still, even one whose waterline is hidden. Only a person answered as an adult standing still blocks: one left unanswered, cut by the cap or answered `adult: unsure` doesn't (C76). | D13, `eval/rules.md` §6, C57 (Rene Q3), C76 |
| Any numbered box | Muse Spark left it unanswered, or C47 dropped every entry it had. A vehicle takes its wheels with it, a linked wheel still counts as visible (C53), and a person neither counts nor blocks wading adults. | C47, C76 |

People get no size floor, because the plan sets none.

**Combining (C43, C54, C57)**
- **References.** Each kept vehicle is one reference. It is read from its deepest reading among its wheels and, when its wheels are hidden, its body, with ties settled as in C78. Each counted adult is one reference.
- **Disagreement.** A floor means "this level or deeper", so a floor is never too shallow (Rene's Q4 answer, `eval/rules.md` §6 v0.6). Let D be the deepest level among all readings, with a floor counted at its own level. The photo is refused (`references_disagree`) when any exact reading sits more than one level below D (C54).
  - **Examples:**
    - a tire floor beside an exact chest reading gives chest
    - a tire floor beside an exact knee reading gives tire, as a floor
    - a tire floor beside an exact half_tire reading refuses
    - exact knee beside exact chest refuses
- **The gutter gap.** Landmarks never give `gutter`. So `tire_only` and `rim_quarter` are two levels apart and refuse together (Rene Q2). `ankle` and `mid_shin` did too, until C91 gave `ankle` no reading.
- **The result** is the deepest level. `levelIsFloor` is true when a floor reading sits at that level.
- **Ties.** On a tie, the deciding reference is:
  - a floor before an exact reading
  - then a wheel before a body, and a body before a person
  - then the lowest box id
- **Wake.** `wake_visible` doesn't change the result (C63).

### 3.4 Outcomes and reasons (C42, C50)

One field, `refusalReason`, carries the reason on both `refused` and `failed` reports (C50).

| Status | `refusalReason` | When |
|---|---|---|
| `done` | none | A level, or `noFloodSeen: true` |
| `refused` | `too_dark`, `too_blurry` | Step 1 |
| `refused` | `photo_unusable` | `photo_usable = no` |
| `refused` | `water_unsure` | `standing_water = unsure`, or a no that its own waterlines contradict (C52) |
| `refused` | `no_water_found` | Muse Spark sees water, but SAM's water mask is empty (C51) |
| `refused` | `no_usable_reference` | Nothing is left after the drops |
| `refused` | `references_disagree` | C54 |
| `refused` | `model_declined` | Muse Spark refused to answer: its answer held a refusal content part (C86) |
| `failed` | `model_calls_paused` | The model-calls switch isn't `off` |
| `failed` | `photo_missing` | `NoSuchKey` on the raw photo (R22, R93) |
| `failed` | `bad_file` | The bytes aren't JPEG (C83), or `blur_for_meta` rejects the file |
| `failed` | `model_error` | C47, C59 |
| `failed` | `pipeline_error` | C59 |

MS1's `pipeline_not_built` stays readable on old reports until their 7-day expiry.

**Effects of C50**
- **API:** no field is renamed. `refusalReason` stays a string, with the values above.
- **App:** the test screen picks its message from `status`, never from the reason. The reason shows only as a small test line. MS5 may add a retake tip for each reason.
- **Evaluation:** coverage counts refusals and failures apart, by `status` (`eval/rules.md` §7), so one field is enough.

### 3.5 What is stored and returned

- **Report item** (Table 14):
  - **Every final status:** `status`, plus `refusalReason` when refused or failed.
  - **`done`:** `noFloodSeen`. With a level, also `level`, `landmark`, `passability`, `levelIsFloor`, `photoKey` (C61), and `basis` as counts `{vehicles, people}`.
  - **The claim:** `claimToken` and `claimedAt`.
  - **Not yet:** `depthInMin` and `depthInMax` (3b); `readings` and `overlayKey` (MS4).
- **S3:**
  - `blurred/{id}.jpg` is saved for level results only (C61).
  - No `raw/` object outlives its report's result, whatever the status (W25).
- **API, `GET /reports/{id}` (C67):**
  - It adds `noFloodSeen` on `done`. With a level, it also adds `level`, `landmark`, `passability`, `basis` and `levelIsFloor`.
  - Other statuses carry only `refusalReason`, as now.
  - It never returns the location, `readings`, `photoKey` or the claim. Photo links come in MS4.
- **Polling.** `processing` is not final. MS1's `pollReport` and smoke script stop when the status leaves `pending`. Both now wait for `done`, `refused` or `failed`.

### 3.6 Meta client, container, role and logs (from MS1's reviews)

- **Meta client** (MS1 Task 4):
  - It checks `type(img) is BlurredImage`, so no subclass passes (C37).
  - It refuses a key shorter than 20 characters.
  - There is one client per process. The 7 SAM calls and the Muse Spark call reuse its connections.
  - Every call runs under the run's deadline (C84). SAM calls send `store: false` if Meta accepts it (C85).
- **OpenCV cap.** `OPENCV_IO_MAX_IMAGE_PIXELS` is set in `lusot_analysis/__init__.py` (R26). The 50 MP cap then holds whichever module imports `cv2` first.
- **Container:**
  - Add `COPY prompts` to the Dockerfile and `!prompts` to `.dockerignore`.
  - Prompts and schemas load through a path that doesn't walk up from `__file__`, because the image's layout differs from the repo's. A check in the built image loads them.
  - pip checks the hash of every locked package, including those the base image already has. Installing into the task root with `--target` is one way to do this.
  - `jsonschema` becomes a runtime dependency, locked with its hash.
- **Analysis role:**
  - `s3:PutObject` and `s3:DeleteObject` on `blurred/*` (C72).
  - `s3:ListBucket` on the bucket, limited to the `raw/` prefix.
  - AWS documents that a missing object reads as 404 with `s3:ListBucket` and as 403 without. It doesn't say whether a prefix-limited grant counts. The cloud check (Task 16, Oct 29) recorded `NoSuchKey` (404) for a missing key under this grant, so `AccessDenied` left the missing-photo rule and now retries (R93).
- **Logs.** One JSON line per report, as in MS1.
  - **Fields:**
    - the report id and the outcome
    - timings for each SAM phrase and for Muse Spark
    - instance counts, and the token counts the answer returns
    - model ids, the prompt and schema version, and the blur version
    - the face-box count, drops by cause, and the deciding reference's kind
  - **AWS errors** log their code and `http_status` (renamed from `status`).
  - **Never logged:** a location, image data, masks, the key, an AWS error message, or Muse Spark's `reason` text (C62).
  - The Lambda doesn't call `count_input_tokens`.
- **Laptop scripts** that use `aws login` credentials depend on `boto3[crt]`. The Lambda uses its role, so it doesn't.

### 3.7 Offline runner

`backend/analysis/probes/run_pipeline.py` runs the pipeline function on a local photo, for debugging and later tuning.
- **Live mode:**
  - It reads `MODEL_API_KEY` from the environment and face-blurs the photo first.
  - It sends the 5 phrases the reading uses, skipping `face` and `license plate` (C66).
  - It saves the raw SAM outputs, the Muse Spark answer (with its `reason`), the versions and the result under `LUSOT_DATA_DIR` (C8, C30), never in the repo.
- **Replay mode:** it reruns the pipeline from saved outputs, with no key and no Meta call (B3).
- **Guards:** it refuses any path inside a folder named `sealed` (C66), and it prints counts and timings only.

### 3.8 Test screen

The MS1 screen gains the result. There is no visual design yet (R3).
- **A level** follows plan §9's pin wording, without inches:
  - the level in words, followed by "at this spot (MMDA level)". Below gutter and above chest aren't MMDA's levels, so they drop "(MMDA level)" (CLAUDE.md, C81).
  - "at least" in front of the level when `levelIsFloor` is set
  - then the class, as "MMDA lists this level as …", and the reference count. The two added levels name the MMDA level they lie beyond instead (C81).
- **The other outcomes:** no flood seen, a refusal and processing failed appear as plan §9's three separate messages. A poll timeout reads as processing failed.
- **For testing:** the reason code shows as a small line. MS1's footer line stays.

Final wording waits for MS5 and Rene's review (M20).

## 4. New calls (Claude's)

C42 to C49 come from the draft. C44 to C48 are revised where marked. C50 onward are new. C72 to C81 come from the plan review (Oct 28, D20), and C82 to C86 from Task 12's review and MS1's security and final reviews.

**Accepted risks, restated for Rene (Oct 28):**
- **Time:** C84 replaces C74, and `judge`'s own request timeout is part of the deadline, so no Meta call can outlast the Lambda.
- **A rejected key or account (C73):** each report costs at most about $0.0875 over about 90 minutes (5 receives, 18 minutes apart) before the dead-letter alarm.
- **Deep water:** Level 3 photos give no wheel mask, so they rely on body and people readings.

| # | Call | Why |
|---|---|---|
| C42 | **Encoding the results.** `done` carries either a level or `noFloodSeen: true` with no level. `refused` and `failed` carry a `refusalReason` from §3.4. | CLAUDE.md keeps processing failed, no flood seen and can't tell apart. Plan §9 gives each its own message. |
| C43 *(aligned with C54 by the plan review)* | The deepest wheel speaks for its vehicle. The vehicle is dropped when its wheels fail C54's test: an exact wheel reading sits more than one level below its deepest wheel, with a floor counted at its own level. So `wheel_covered` beside `rim_three_quarters` reads tire, as a floor, while `wheel_covered` beside `hub` drops the vehicle. | Plan §7 step 5 treats a vehicle's wheels as a single reference, because one tire size applies to all of them. One test inside a vehicle and across references keeps the rules consistent. |
| C44 *(revised)* | Provisional quality cutoffs, marked untuned: brightness under 40 and sharpness under 25, on the pre-blur photo at up to 1,600 px (C58). MS3b tunes them on development photos only. No size cutoff applies beyond R27's 32 px floor. | Plan §7 step 1 tunes them on development photos, and low cutoffs refuse only the extremes until then. The app always sends 1,600 px photos, and the 40 px wheel rule already refuses photos too small to read. |
| C45 *(reason revised)* | In 3a, only `sedan_hatch` and `suv_mpv` wheels give landmark readings. | Table 8's wheel rows are for those two body types. Plan §8 gives vans and the other types no wheel rows until real photos confirm where their marks sit; meanwhile vans rely on geometry, which is 3b. G5 keeps pickups out until their tire sizes are verified. |
| C46 *(reason added)* | G2's claim moves from MS4 into 3a, with a 15-minute lease. | 3a is the first time the queue pays Meta, and CLAUDE.md says to claim before paying. The lease outlasts the 180 s Lambda timeout, so a live worker never loses it. It expires before the 1,080 s visibility timeout, so a message redelivered after a crash can re-claim. |
| C47 *(extended)* | An answer that isn't valid JSON or fails the schema ends `failed/model_error`, with no second paid call. An id that isn't among the boxes, or sits in the wrong list, drops only its item. An id answered twice drops every entry with that id. | Pay once. Each item is tied to its own box, so one bad id says nothing certain about the others. Two answers for one id would mean picking one, which is a guess. (P1) |
| C48 *(revised)* | SAM's `face` and `license plate` results are blurred with MS1's `blur_faces`. The blur covers each mask's bounding box, grown by 25% on every side. | The box holds the whole mask, and the margin covers its ragged edge, so no dilation size needs tuning. One tested blur serves YuNet and SAM alike. The draft's 10% dilation had no source. |
| C49 | `landmark` is the deciding reference's (C54 breaks ties), and `basis` counts the references kept. | Table 6 shows one landmark and a reference count. |
| C50 | **One reason field.** `refusalReason` holds the reason on both `refused` and `failed` reports. There is no `failureReason`. | Table 14 defines the field for both, and `status` already tells them apart. MS1's handler, API and app already use it. Effects in §3.4. |
| C51 | An empty water mask still goes to Muse Spark (D14). A clear no then gives no flood seen, and a yes gives `refused/no_water_found`. | D14 changes plan §7 step 2 only so that a dry street can read no flood seen. W9 asks for water touching a reference, and an empty mask has none. (Rene Q1, P4) |
| C52 | The gate checks `photo_usable` first. A no on standing water counts only when no answered item puts water above its lowest mark: no wheel above `tire_only`, no person above `ankle`, and no body above `below_bumper`. Otherwise the photo is refused as `water_unsure`. | Plan §7 step 4 gives no flood seen only for a clear no. A false no flood seen on a flooded photo scores as an underestimate (`eval/rules.md` §7). (P1) |
| C53 | The body waterline gives tire as a floor at `mid_door` or `window`. This applies only to a `sedan_hatch` or `suv_mpv` whose wheels are all hidden. A `wheel_covered` wheel with a body waterline at `door_sill` or lower drops the vehicle. | On these cars the door sill sits below the top of the wheel, so water at the sill can't hide the wheels. Table 8's whole-wheel row says to check the body. C17 sets how a floor is scored and shown, not where it starts. |
| C54 *(set by Rene's Q4 answer)* | A floor is never too shallow. With D as the deepest level among all readings (a floor counted at its own level), a photo is refused only when an exact reading sits more than one level below D. `levelIsFloor` is true when a floor sits at the result level. Ties go to a floor, then to a wheel, a body and a person, in that order, then to the lowest box id. | A floor means "this level or deeper", so it can't disagree with a deeper reading. Rene chose this on Oct 28 (Q4), and `eval/rules.md` §6 v0.6 records his OK. The tie order keeps results repeatable (B3) and prefers the cautious wording. |
| C55 | A wheel joins the vehicle whose box holds the centre of the wheel's box. A wheel inside no vehicle box, or inside more than one, is dropped. Rims are linked in 3b. | A wheel's reading needs its vehicle's type and motion, and choosing between two cars would be a guess. No 3a step reads a rim. |
| C56 | The 40 px rule measures the longer side of the wheel's SAM box, on the image sent to Meta. | Water hides the bottom of a wheel, so its visible height shrinks as the water rises. Measuring height alone would drop the deepest readings first and push results shallow. (P2) |
| C57 *(revised after the builder check)* | `standing_still = unsure` counts as wading. Wading adults count only when no adult in the photo is standing still, even one whose waterline is hidden. Each counted adult is one reference. | Plan §7 step 4 counts unsure as moving. D13 and `eval/rules.md` §6 use exactly this wording, and both are Rene's. Letting wading adults count when the standing adult gives no reading is Rene's Q3. |
| C58 | The quality scores use the photo before the face blur. The face blur still runs before any Meta call. | Plan §7 step 1 runs the same check on the phone, which has no face detector (C20). Only pre-blur scores can match it. The check sends nothing to Meta. |
| C59 *(narrowed by C73)* | A Meta error that outlasts the client's retries ends `failed/model_error`, except a rejected key or account (C73). Any other pipeline exception ends `failed/pipeline_error`. Otherwise only AWS errors, and the loads before the claim (C60, C79), return the message for an SQS retry. | CLAUDE.md caps Meta calls at 3 to 5 attempts, and an SQS retry would pay again for the calls that worked. The person sees "processing failed" in seconds, not after the 18-minute visibility timeout. |
| C60 | The handler loads the Meta key and reads the model-calls switch before the claim. It acts on a set switch after the claim. A failed key load isn't cached. | The ruling wants an unreadable switch to leave the report `pending`, which holds only before the claim. Failing a report under the claim also covers one whose lease expired. A key fault ends in the dead-letter queue and its alarm, not in failed reports. |
| C61 | Only a level result stores a photo (`blurred/{id}.jpg` and `photoKey`). `basis` is stored as counts. `readings` wait for MS4. | Plan §7 places step 4's exits before step 8. Nothing in 3a reads other photos or per-reference readings. MS4's overlay can add them. |
| C62 | The Lambda never logs or stores Muse Spark's `reason` text. Only the offline runner saves it. | Table 5 makes it an evaluation log. Free text can describe people or plates, and CloudWatch keeps logs for 14 days, past the 7-day limit. |
| C63 | `wake_visible` is read, but it doesn't change the result in 3a. | Table 5 uses it to lower confidence, and 3a has no confidence output. |
| C64 | 3a doesn't read `/lusot/stop/publish`. MS4 applies it where pins reach the map and the feed. | Plan §13 ties publishing to the public map. In 3a, a result can be read only through the uploader's unguessable report id. |
| C65 | 3a takes in Table 8's people rows, a landmark-only combine and `levelIsFloor`. The inches level rule moves to 3b. | The design's MS3 row puts the person cross-check and combining in 3b, and its MS4 row holds `levelIsFloor`. But Table 8 includes the standing-adult rows, and D13 counts people fully. A photo with two references needs step 6 to give any result, and `wheel_covered` already yields floors. No 3a step produces inches. |
| C66 | The offline runner sends the 5 phrases the reading uses, skipping `face` and `license plate`. It refuses any path inside a folder named `sealed`. | Plan §14 skips those two requests offline, since nothing offline is published. CLAUDE.md and C39 keep sealed data untouched. |
| C67 | `GET /reports/{id}` returns `noFloodSeen` on every `done` report, and the level fields only with a level. It never returns the location, `readings`, `photoKey` or the claim. | This gives the app one rule to rely on. Links wait for MS4. |
| C68 *(revised by the probe, P3)* | B1's bound is 120 s from upload to a final status, the app's own poll timeout, and applies to the smoke run only. | Plan Table 22 sets no time for 3a. The probe's Muse Spark answers took a median of 24.7 s and at most 54.5 s, so the draft's 60 s left no room for a cold start or one retry. The 10 s photo-to-pin target is MS5's. |
| C69 | Before numbering, SAM's results lose every wheel that fails the 40 px rule (C56) or links to no single vehicle (C55). Such a wheel gets no number. A linked wheel dropped for size still counts as visible, so its vehicle gets no body reading (C53). | SAM's boxes alone decide both rules, so Muse Spark needn't answer about wheels that can't count. Fewer labels mean fewer id mistakes and a shorter paid answer. A small visible wheel means water isn't hiding it, so the body rule's premise fails. |
| C70 | At most 6 vehicles and 6 people get numbers, largest boxes first. Wheels follow their kept vehicles. Cut boxes are logged by count. | A crowded street can return dozens of instances. Every label adds to the strict answer, its cost and its id mistakes. The largest boxes are the nearest and the most readable. The caps are provisional (P6). |
| C71 *(step 1 changed by C75; photos changed by C87)* | If no photo gives a level in B1:<ul><li>First, the B1 photos' own log lines are read for their outcomes and drop causes, with no Meta call (C75).</li><li>Then up to 15 more photos go through the cloud: positions 5 to 19 of C87's order.</li><li>If none of those gives a level, B1 is recorded as partly met, with the reason. 3a then closes on B2 to B5 and the other cloud checks, and the cloud proof of a level moves to the first Manila photos.</li></ul> | A street photo can rightly make Muse Spark answer `moving: unsure` or a type outside the two allowed, and those refuse. More photos cost a few cents. Holding 3a open for a data gap would stall MS3b. |
| C72 | **A stale photo.** Right after a successful claim, before any Meta call, the handler deletes `blurred/{id}.jpg`. A level result saves it again just before its write. A delete of a missing key succeeds, and a failed delete returns the message like any other AWS error, before anything is paid. The analysis role gains `s3:DeleteObject` on `blurred/*`. | A level result's photo is saved before its write. If that write fails, a later attempt can end without a level, or return the message on a rejected key (C73) or a timeout (C74), and a photo that B4 forbids would stay. Every attempt starts from a clean `blurred/`, so only the attempt that writes a level leaves a photo. S3 doesn't charge for deletes. A photo outlives its item only if the last attempt before the dead-letter queue saved it and then failed its write; the 7-day `blurred/` lifecycle rule then removes it. |
| C73 | **A rejected key or account.** A Meta 401 (a missing or revoked key), 402 (a billing fault, such as no credit left) or 403 (a key without access to a model) is an account fault, not a photo fault. Meta's error-handling page defines the three this way. The pipeline raises it instead of ending `failed/model_error`. The handler drops its cached client, logs `model_key_rejected` with `meta_status`, and returns the message. The report stays `processing` until a redelivery re-claims it, 18 minutes later, and reloads the key from SSM. After 5 receives the message goes to the dead-letter queue and its alarm. The report then stays `processing` until its 7-day expiry, and the raw photo goes with the 1-day `raw/` lifecycle rule. | C60 sends key faults to the dead-letter queue and its alarm, not into failed reports. Otherwise a warm container keeps the rejected client and fails every report until it recycles, even after Rene stores a new key, and no alarm fires when the credits run out. The cost: a key that may call SAM but not Muse Spark pays for 7 SAM calls on each of 5 receives, about 35 calls per report, until the alarm. |
| C74 *(replaced by C84)* | **No total time bound in 3a.** MS1's client allows 4 attempts of up to 90 s per call, so a photo can outlast the 180 s Lambda timeout. 3a adds no deadline. A timed-out report stays `processing`, is re-claimed at the next redelivery 18 minutes later, and goes to the dead-letter queue after 5 receives. The smoke run records each photo's seconds (C68). MS4 adds the deadline with its timeout recovery tests (§5). | Plan Table 22 sets no 3a time, and P3 measures real latency first, so a deadline chosen now would be a guess. In the worst case a stuck photo pays 5 times for 8 calls, a few cents. No user sees 3a before MS5. |
| C75 | **C71's first step is a diagnosis.** It reads the outcome and drop causes from the B1 photos' own log lines. It replays nothing. | The probe saved Muse Spark answers only for the same 5 photos, and positions 15 to 29 were never sent to Meta. A replay could only re-run photos that just failed, so it can't find candidates. The log lines already hold each photo's drops, at no cost. |
| C76 *(accepted: Rene, Oct 28, 1:30 PM, delegated to the recommended option)* | **Unanswered boxes give no reading.** A numbered box counts as unanswered when Muse Spark gave it no entry, or when C47 dropped every entry it had. An unanswered vehicle is dropped with its wheels. An unanswered linked wheel counts as visible, so its vehicle gets no body reading. An unanswered person neither counts nor blocks wading adults. Only a person answered as an adult standing still blocks them, so people cut by C70's cap and people answered `adult: unsure` don't block either. | A skipped box is a gap in the answer, and filling it would be a guess. D13 and Rene's Q3 answer are about adults Muse Spark says are standing still, whatever their waterline. Treating every unknown person alike keeps one rule: an unanswered person, a capped one and an unsure one are all unknown. Making them all block would drop the wading adults of every busy street with more than 6 people. |
| C77 | **An id answered twice** drops every entry with that id across all three lists. So an id under both `wheels` and `people` drops both entries. | Box ids are unique across kinds, so an id in a second list is a second answer about the same box (C47). |
| C78 | **Ties inside one vehicle** follow C54's order: a floor first, then a wheel before the body, then the lowest box id. So `rim_top` beside `wheel_covered` reads tire, as a floor, from the covered wheel. | One order everywhere keeps results repeatable (B3) and prefers the cautious "at least" wording. |
| C79 | **The prompt loads before the claim,** with the key (§3.1 step 3). A missing or broken prompt returns the message, like a key fault. | A missing prompt is a deploy fault. It belongs in the dead-letter queue and its alarm, not in failed reports (C60). |
| C80 | **Log fields beyond §3.6's list:** `meta_calls`, `brightness`, `sharpness`, `numbered` and `meta_status`. | The smoke run reads `meta_calls` for B1's "no Meta call" check. The others help tune C44 and C70 later. None is private (C62). |
| C81 *(accepted: Rene, Oct 28, 1:30 PM, delegated to the recommended option)* | **Test-screen wording** (§3.8):<ul><li>MMDA's 7 levels read like "Knee deep at this spot (MMDA level)." The two added levels read "Below gutter deep at this spot." and "Above chest deep at this spot.", without "(MMDA level)".</li><li>The class line follows plan §9: "MMDA lists this level as not passable to light vehicles (NPLV)." The added levels read "Shallower than MMDA's gutter level, which MMDA lists as passable to all vehicles (PATV)." and "Deeper than MMDA's chest level, which MMDA lists as not passable to any vehicle (NPATV)."</li><li>A refusal shows D19's English line.</li></ul> | CLAUDE.md forbids calling the 9 levels MMDA's, and plan §9 frames the class as what MMDA lists the level as, not a verdict on the spot. D19 is Rene's confirmed refusal line. The rest is test-build wording until MS5 and M20. |
| C82 *(from Task 12's review)* | **A repeated claim or write is the worker's own.** When a claim's condition fails and the old item is `processing` with this worker's token, the claim succeeded on an earlier try, so it counts as claimed. When a result write's condition fails and the old item holds this worker's token and the status being written, the write succeeded on an earlier try, so it counts as written. | The AWS SDK retries a DynamoDB call whose answer was lost (a timeout, a 5xx), and the repeat then fails against the first try's own result. Read as a lease held or lost, that would leave the report `processing` until its 7-day expiry and keep the raw photo, against W25. Tokens are a new random value for every delivery, so a match can't be another worker's. |
| C83 *(from MS1's security review)* | **JPEG bytes only.** The handler ends a photo whose bytes don't start with `FF D8 FF` as `failed/bad_file`, before any decoder sees it. The check lives in the handler, not in `face_blur.decode_image` or the pipeline, which the laptop tools also use on other formats. | The upload policy sets `Content-Type: image/jpeg` but can't check the bytes. OpenCV's decoder reads many formats, and it runs in a role that can read the Meta key, so only the one format the app sends should reach it. The app always sends JPEG, so nothing real is refused. |
| C84 *(replaces C74; from MS1's final review; margin raised by C88)* | **A total deadline.** The handler gives each run a deadline: the Lambda's remaining time less 30 s (C88; 20 s before), enough for the publish blur and the writes. Every Meta call honours it: a retry wait (`Retry-After` included), a 504 poll or a stream read that would pass it stops instead, and the run ends `failed/model_error`. The offline runner sets no deadline. | MS1's final review found that Meta's overload replies ask for a 60 s wait, which the client honours uncapped, so 4 attempts can sleep the whole 180 s. Its polling bound counts only its own sleeps, and a SAM stream kept open by keepalive events has no total bound. A Lambda killed by its timeout leaves the report `processing`, re-claims it 18 minutes later and pays again, up to 5 times. Stopping before the deadline gives "processing failed" in time and pays once. `Retry-After` is still honoured: the client never retries early, it just stops. |
| C85 *(from MS1's final review; reworked by the tracker's verified update, 3:30 PM; result in C88)* | **One SAM check at the app's size, before Task 16 and before any Set A development photo goes to Meta** (at most about $0.0075):<ul><li>**The frame check:** the first photo in C87's order that has a credit line (a clearly licensed Commons photo; STURM stays offline), enlarged or padded to 1,600 × 1,200 and passed through `blur_for_meta`, goes to SAM with the phrase `vehicle`. It passes only if a box's frame is 1,600 × 1,200. Zero matches is inconclusive, so it retries once with `wheel`.</li><li>**`store: false`:** judged by the value the stream echoes, not by the HTTP status. A 400 resends without it. One `background: true` call with `store: false` is polled to the end; if that fails, the background path keeps Meta's default and deletes the response after reading it. Muse Spark's echoed `store` is recorded once. If `store: false` is accepted, it becomes the default on every path, the offline runner included.</li><li>The result goes into `ms3a.md`, for Window 4's privacy drafts.</li></ul>Meta's retention, with no fixed period, is disclosed whatever `store` does (plan §13). C85 decides only the extra line that Meta stores a copy of each request. | SAM's live stream echoes `store: true`, Meta's default, so Meta keeps each photo once per phrase. Storing less is the privacy rule. A frame mismatch would fail every real photo, so it must be found before the cloud run. A real street photo gives SAM something to match; a blank synthetic image can return no box and prove nothing. |
| C86 *(made firm by the tracker's verified update, 3:30 PM)* | **A Muse Spark refusal** ends `refused/model_declined`, which the app shows as "can't tell". The client tells it apart: `judge` raises a distinct refusal error when the answer holds a refusal content part, before it parses any JSON. An answer whose status is anything but missing or `completed` (`incomplete`, `failed`, `cancelled` and the like) stays `failed/model_error`, even if it holds a refusal part (R104). | Meta's Responses schema has a refusal content part, so the client can see a refusal rather than guess from empty text. "Can't tell" with a retake tip fits a refusal better than "processing failed, try again". |
| C87 *(Rene's decision, 5:53 PM, relayed by the tracker session; the selection is Claude's under D7)* | **Clean photos for every new Meta call in MS3a.** STURM-FloodDepth stays on disk for offline development only: no new Meta call, no repo, no demo; MS1's probe results stay as recorded. B1, C71 and C85 use the Wikimedia Commons flood photos in `lusot-data\set_c\commons-ph-floods\`. The eligible photos are the tracker's verified list `metro_manila_41.txt` (the 41 files flagged `metro_manila_or_ondoy_2009`: 9 public domain, 32 CC BY 2.0). Their file names, sorted, give the full order `random.Random(20261028).sample(names, n)`, fixed in advance. Positions 0 to 4 are B1's, and 5 to 19 are C71's fallback; the rest are spare. (For these 41, Python's draw makes any shorter sample a prefix of the full one.) At send time, a photo without a credit line in the folder's `attribution.csv` is skipped and counted, so every photo sent to Meta has its credit line kept (R102). C85 uses the first credited photo in the full order. Attribution stays beside the photos, and no photo enters the repo or the demo. The offline runner refuses a live run on any path inside `sturm_flooddepth`. | Zenodo's own description says STURM's crops come from another lab's photos, whose repository is withdrawn and whose licence was never filled in, so its CC BY 4.0 label can't be relied on. Commons photos carry checked licences and attributions. A seeded order keeps the choice fixed in advance, as R7 did for STURM. CC BY-SA stays offline too. |
| C88 *(Claude's under D7, from Task 7a's review and C85's result, 8:40 PM)* | **The deadline's margin and the SAM stream's idle cap.**<ul><li>The handler's deadline is the Lambda's remaining time **less 30 s**, not 20 s.</li><li>While a deadline is set, a SAM stream read waits at most **20 s** for its next event (R103). A stream that stalls longer ends `failed/model_error`, or `DeadlineExceeded` at the deadline.</li><li>No try starts with less than 5 s left, the first included, and polling stops there too (R104, R106).</li></ul>**C85's result, Oct 28, 8:37 to 8:40 PM** (three SAM calls on two C87 photos sent at 1,600 × 1,200, plus one text-only Muse Spark call, about $0.008):<ul><li>**The frame check passed.** The first photo, a flooded river, has no vehicle or wheel, and SAM rightly found none. The second, a flooded street, gave 8 `person` matches, each box inside 1,600 × 1,200 and each mask the image's size.</li><li>**`store: false` is accepted on SAM's stream** (it echoes `false`), so it becomes the default on every streamed SAM request, the offline runner's included. Muse Spark echoes `store: false` too.</li><li>**Meta's background mode refuses `store: false` with a 400.** So the 504 fallback sends no `store`, keeping Meta's default, and tries once to delete the job however its polling ends, as far as Meta allows (R106).</li><li>A SAM call at 1,600 px took 8.4 s (5.3 s for no match), against MS1's 1.46 s median and 4.67 s maximum on small crops.</li></ul> | A stalled SAM stream could otherwise wait out a 90 s read timeout past the deadline, so the Lambda would be killed and the report would pay again (Task 7a's review). A 20 s cap is 2.4 times the slowest call seen at the app's size, and the 30 s margin covers it plus publishing. A try with under 5 s left can't finish but may still be billed. Storing less at Meta is the privacy rule, and background jobs must be stored to be polled. |
| C89 *(Claude's call under Rene's delegation, relayed by the tracker, Oct 29, 1:03 AM; from Task 13's review; R113)* | **A live lease returns the message.** A delivery that meets another worker's live lease lists its message in `batchItemFailures` and leaves `raw/` alone. It doesn't finish it. A message is finished only once its report is final or its own work has ended. | An SQS duplicate of the same message, finished while the lease holder runs, deletes the only copy. A holder that then crashes past its deadline (out of memory, a runtime crash) would leave the report `processing` for 7 days. The template has batch size 1, `ReportBatchItemFailures`, a 1,080 s visibility timeout and 5 receives before the dead-letter queue. So the returned copy comes back after the 900 s lease: it re-claims after a crash, or finishes with no Meta call after a result, in at most about 3 receives. MS4's recovery tests add the cloud crash test (B2). |
| C90 *(Claude's under D7, Oct 29, 9:07 PM; from Task 16's B3 live run; R122)* | **A SAM mask scaled to a 1024 px side is placed in its box.** When a mask's box has a side over 1024 px, SAM may send the raster scaled so that the box's longer side is exactly 1024, with the other side in the same ratio. The client accepts that shape only, with the other side within 1 px of the rounded ratio, and scales the raster up to the box with center-aligned nearest-neighbour. A raster of any other size still raises `MetaApiError` (R63). | The live run's water mask, a 700 × 1600 box, came as a 448 × 1024 raster, the box × 0.64. Upscaled, it matches the water exactly. C85's 1,600 px `person` masks came unscaled, so the scaling is per mask, not per frame. Meta's SAM pages and the SAM 3 protocol don't state the rule, so any other shape fails closed, as a visible `model_error`. Before this, every photo whose water spans more than 1024 px ended `failed/model_error`, and MS1's probe photos, all under 1000 px, never showed it. |
| C91 *(Claude, Nov 1, 2026, about 3:20 AM, on the tracker's request; approved by Rene, Nov 1, 2026, in writing, delegated to the tracker's double-check, about 9:58 PM)* | **An adult's `ankle` waterline gives no reading.** `PEOPLE_ROWS["ankle"]` is None, so an ankle-deep adult never sets a level alone: the photo's other references decide, or it is refused (`person_no_reading`). Every other people row, the wheel and body rows, the gate's lowest-mark rule (C52, which already left ankle out) and the wading rule (C57) are unchanged. The gutter gap's people pair (`ankle` beside `mid_shin`) no longer arises, and an ankle adult no longer counts toward a disagreement: beside a knee-deep adult the photo reads knee, where it used to refuse. A "no" on standing water with an ankle adult still gives no flood seen (C52). **It departs from plan Table 8 and from D13 ("a standing adult can set the level alone") for `ankle` only.** This spec's people table, its gutter gap and Q2, `eval/rules.md` §6 (v0.8) and CLAUDE.md's D13 line (Rene's own edit) carry the same exception. The app keeps `ankle`'s landmark line for results stored before C91. | The Nov 1 development check (`docs/research/2026-11-01-overnight-accuracy.md`; Set C, weak labels): 3 of 15 levels were below the gutter from an adult answered `ankle` on half-knee or knee labels. In OL127, checked by eye, adults stood in water to about mid-shin or knee. A prompt wording fix changed nothing (12 judge-only reruns). Replayed at $0 on the 120: levels 15 to 11, within one level 64% to 80%, the 3 under-reads become refusals, and 1 right below-gutter level (OL086) is lost. Reading shallower than the water is the dangerous direction, and a refusal beats a guess. |
| C92 *(the tracker's ruling under Rene's delegation, Nov 2, 2026, about 4:3x AM, from Window 4's accuracy pass; Rene's words: "Make sure it is accurate by then" (Nov 2, about 3:4x AM) and "double check it … proceed to approve" (Nov 1, about 9:55 PM))* | **A person too small to read never sets the level and blocks no one.** In `apply_drops`, an adult whose numbered box's longer side is under `TUNING.min_person_side_px` (60 px in tuning-v2; 0, off, at START) is kept as `small`, and a small adult standing still blocks no one, so it never leaves the near adults out as wading (C57). Step 5 gives a small adult's reading as one that doesn't decide, counted as `person_small`, as it does for a reading step 3 dropped (C317): so the reading refuses the photo when it is deeper than an exact result (a floor result stands), and never decides it. A small box can be an adult deep in the water, since SAM's box covers only what shows above it, so dropping the reading outright would lean shallow (the review of c8d4541). A shallower small reading changes nothing. The box is in px of the image SAM sees, at most 1,600 px on its longer side. A run saved before tuning-v2 replays with the cutoff off. | Rene's sample screenshot (Nov 2, about 3:1x AM): a distant figure set "Tire" while two near adults pushing a cart were not used. On the 120 Set C development runs, scored on the 55 photos the blind double relabel of Nov 2 agreed on: the smallest person that set a level was 46 px, and it read knee on a below-gutter photo (OL018, 3 levels over). Of 380 numbered people, the median longer side is 115 px (10th percentile 37, 25th 54), and 7 of 68 still adults are under 60 px. With C93, the combination gives 9 scored levels, 8 exact, 1 over and 0 under (v0.8: 10, 8, 2 and 0); OL018 is now refused. A-neg's 10 development photos and the 42 samples: no change. Development evidence only: no Set A photo or result informed this. |
| C93 *(the same ruling)* | **A "no" over wide water is refused as `water_unsure`.** In the gate, a "no" on standing water with no item above its lowest mark (C52) gives no flood seen only while SAM's water covers at most `TUNING.no_flood_share_max` of the image's lower half (0.25 in tuning-v2; 1.0, off, at START). Over it, the photo is refused as `water_unsure`, the reason C52 already uses, so the app needs no new line. The lower half is the rows from height // 2 down. This narrows C51: below that share, SAM's water still never overrides a clear no. | Rene's screenshot of a Manila sample that read "No flood seen" over a flooded street (Nov 2, about 3:35 AM). On the 120 Set C development runs, 6 gave no flood seen: 4 with an empty mask, and 2 with water over 0.60 of the lower half (OL047, with no agreed label, and OL064, below the gutter on the agreed relabel). Over the 162 development and sample runs with any water mask, the lower-half share's 10th percentile is 0.26 (5th 0.12, median 0.73), so 0.25 sits below nearly every real flood. A-neg's 9 development "no flood seen" results have empty masks, so none changes. Not yet measured: wet roads with reflections, and river or bay views, which may now be refused. Development evidence only: no Set A photo or result informed this. |

## 5. Not in 3a

- **MS3b:**
  - step 3 (the reflection cut) and W9's check that water touches each reference
  - rim linking, rim geometry, inches, and the level rule for inches
- **Oct 31:** the gated self-check decision.
- **MS4:**
  - the overlay image, `readings` and photo links
  - `private` mode and the Metro Manila check
  - demo pins, flags, the samples endpoint and the publish switch
- **MS4, before the freeze:** recovery tests beyond B5 (interrupted SAM streams, Lambda timeouts and failed deletions).
- **MS5:** real screens and final wording.
- **After the MS2 split:** tuning on development data.

## 6. Open until the MS1 probes report

The markers P1 to P5 above show each spot where a probe result may change a number or a rule.

| # | Open item | What it may change |
|---|---|---|
| P1 | Prompt v1, or a v2 that the probe teaches. This includes how Muse Spark answers waterlines on a dry street, and how often its ids go wrong. **Settled for MS3a: v1** (`muse_spark_photo_v1`). Rene's MS3b-Q5 answer (Oct 28, 11:09 PM) keeps v1's two extra rules. Any v2 or new drawing is MS3b's (its C325). | the prompt version (§3.2 step 4), C47, C52 |
| P2 | Whether SAM's wheel boxes on partly submerged wheels are good enough for the 40 px rule | C56's measure and the 40 px number |
| P3 | Typical and worst latency per photo | B1's 60 s (C68), which must stay under the 180 s Lambda timeout |
| P4 | How often SAM returns an empty water mask on a flooded photo. The water test measures it first, then the Manila check (C34, C40). | how many photos C51 refuses |
| P5 | Face boxes that overlap wheel boxes (the probe counts them) | If any appear, a rule to drop a blurred wheel. `blur_for_meta` would then have to return its boxes. |
| P6 | Busy scenes: how many SAM instances a Manila street returns, and whether 6 vehicles and 6 people cover the readable references. STURM crops can't show this. The first Manila photos measure it. | C70's caps |

## 7. Questions for Rene

Rene answered all four on Oct 28 at 7:58 AM, in chat. Q1 to Q3 keep the defaults. Q4 takes the alternative: a floor means "this level or deeper" (C54).

| # | Question | Default if unanswered |
|---|---|---|
| Q1 | **Scope of D14.** SAM can find no water while Muse Spark says there is standing water. Should the plan §7 step 2 refusal stand, since D14 only added no flood seen for dry streets? Or may the landmarks give a level anyway? | Refuse, as `no_water_found` (C51). P4 shows how often this happens. |
| Q2 | **The gutter gap.** Landmarks never give `gutter`, so `tire_only` beside `rim_quarter` (or `ankle` beside `mid_shin`) is two levels apart. Under `eval/rules.md` §6, that refuses. (Since C91, `ankle` gives no reading, so only the wheel pair remains.) Should the gap count landmark steps instead? Both readings are PATV, so only coverage on shallow scenes changes. A change needs Rene's written OK in that file's change log. | Keep the rule as written (refuse) |
| Q3 | **A standing adult with a hidden waterline.** D13 and `eval/rules.md` §6 count wading adults only when no adult in the photo is standing still. Should a standing adult whose legs are hidden (behind a car, say), and who gives no reading, still block the wading adults? This happens often on busy streets. | Yes, as written (C57). More photos refuse. |
| Q4 | **Floors in the one-level rule.** "At least tire" (wheels covered) beside a chest-deep adult agree physically, but §6 as written refuses them, because tire and chest are two levels apart. Should a floor count as "this level or deeper" when references are compared? A change needs Rene's written OK in that file's change log. | Refuse, as written. **Rene's answer:** this level or deeper. C54 and `eval/rules.md` §6 v0.6 are updated. |

**After the plan review (Oct 28, 1:30 PM).** Rene delegated the open items to the recommended option; the tracker session relayed it.
- **Q1, checked again after MS1's probe:** SAM found no water mask on 5 of 10 flooded STURM photos, so C51 would refuse about half of such photos. C51 stays as written, and Q1 is revisited at the Manila check (C34), on development photos after the MS2 split. STURM crops aren't street scenes (C40), a refusal beats a guess, and W9 needs the water to touch the reference.
- **C76 and C81** are accepted as written.
- Rene's approval of the whole spec still waits until he reads it (D7). Nothing waits on it.
