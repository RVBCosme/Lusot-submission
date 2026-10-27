# MS3a Landmark core: spec

- **Date:** Oct 28, 2026 (Manila)
- **Status:** Final, builder-checked on Oct 28. The check's three questions are settled:
  - C54 and C57 follow `eval/rules.md` as written, and their alternatives become Rene's Q3 and Q4.
  - Calls C69 to C71 are added.

  Claude proceeds on the calls in §4 (D7, D15), and Rene approves in the morning.
- **Needs first:** MS1 Task 4 (the Meta client, with R27) and Task 5 (the probes, prompt v1, schema v1 and `annotate`). Neither is in the repo yet. Task 5's probe note settles §6.
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

| # | Check | Evidence |
|---|---|---|
| B1 | Core works end to end in the cloud (plan Table 22, Phase 3) | The smoke script uploads two kinds of photo through the API: the 5 STURM photos from MS1's probe, and one synthetic dark JPEG. MS1's probe sends all 15 of its STURM photos to Meta (C12), so the smoke run adds no new photo.<ul><li>Every report reaches `done`, `refused` or `failed` within 60 s (C68, P3). None stays `pending` or `processing`.</li><li>At least one STURM photo gives a level. If none does, C71 applies.</li><li>The dark JPEG ends `refused/too_dark`, and its log shows no Meta call.</li><li>`GET /reports/{id}` returns the fields in C67.</li></ul> |
| B2 | Rules are tested | Unit tests cover:<ul><li>every Table 8 row, `not_visible`, and the body rule (C53)</li><li>linking (C55), the drops and caps before numbering (C69, C70), and every drop rule in §3.3</li><li>combining: floors, ties and the gutter gap (C54); the people rules (C57)</li><li>the gate on Muse Spark's answer (C51, C52) and every reason code in §3.4</li><li>the claim: fresh, finished, live lease, expired lease, and a lease lost at the final write</li><li>the stop switch, both set and unreadable; the missing-photo codes; the quality gate</li><li>the SAM blur (C48), the API fields (C67), and polling through `processing`</li></ul> |
| B3 | The same code runs on the laptop and in the cloud | One set of saved model outputs, replayed through the offline runner and through the handler's pipeline call, gives identical results |
| B4 | Nothing unblurred is stored (W25) | <ul><li>Unit test: the SAM face and plate boxes are blurred, and nothing else changes.</li><li>After the smoke run, `blurred/` holds a photo for each level result and nothing else.</li><li>No `raw/` object remains for any report, refused and failed included.</li></ul> |
| B5 | Pay once (G2) | <ul><li>Unit tests:<ul><li>Two deliveries racing for one report make one set of Meta calls.</li><li>A delivery after the result makes none and deletes a leftover raw object.</li><li>A delivery after an expired lease re-claims.</li></ul></li><li>Cloud: the smoke script re-posts the same upload form after the result (a reused upload link, plan §7 step 8). This makes no Meta call, and the new raw object is deleted.</li></ul> |

## 3. What gets built

### 3.1 Handler (replaces the MS1 stub, C28)

For each message (batch size 1), in order:
1. Skip S3 test events. Delete any object whose key isn't `raw/r_<32 hex>.jpg` (MS1).
2. Find the report through `reportId-index`. If it isn't there yet, return the message for retry, because the index can lag (MS1).
3. Load the Meta key, once per process; a failed load isn't cached. Then read `/lusot/stop/model-calls`. If either step fails, return the message and leave the report untouched (C60). An unreadable switch is a tested fail-closed path: the report stays `pending`.
4. **Claim (G2, C46).** A conditional update moves the report to `processing` and sets `claimToken` and `claimedAt`. It succeeds from `pending`, or from `processing` with a lease older than 15 minutes. If the claim fails:
   - **The report is `done`, `refused` or `failed`:** delete `raw/{id}.jpg` if it is there (a retried delete or a reused upload link), then finish the message.
   - **Another worker holds a live lease:** finish the message and leave `raw/` alone.

   Neither path calls Meta.
5. If the switch reads anything but `off`, end with `failed/model_calls_paused` (C60).
6. Get `raw/{id}.jpg`. The S3 error codes `NoSuchKey` and `AccessDenied` end with `failed/photo_missing` (R22, narrowed). Any other S3 error returns the message, so a 403 from clock skew or a bad signature retries.
7. Run the pipeline (§3.2).
8. Publish (§3.2 step 8).

Every write after the claim requires `status = processing` and this worker's `claimToken`. If that check fails, the lease was lost: the worker drops its result, leaves `raw/` alone and finishes the message.

**Errors (C59)**

| Error | Result |
|---|---|
| A Meta error that outlasts the client's own retries | `failed/model_error` |
| A Muse Spark answer that isn't valid JSON or fails the schema | `failed/model_error` (C47) |
| Any other exception inside the pipeline | `failed/pipeline_error` |
| An AWS error (S3, DynamoDB, SSM) other than the missing-photo codes | The message returns for an SQS retry. The lease expires before the queue redelivers it (C46). |

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
   1. For a level result only (C61): blur the SAM `face` and `license plate` boxes (C48) on the face-blurred image, and save `blurred/{id}.jpg`.
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

**People rows.** These are Table 8's rows, for adults (D13, C57).

| `waterline` | Level |
|---|---|
| `ankle` | below_gutter |
| `mid_shin` | half_knee |
| `knee` | knee |
| `mid_thigh` | tire |
| `waist` | waist |
| `chest` | chest |
| `above_chest` | above_chest |
| `not_visible` | no reading |

**Body waterline (C53).** It counts only for a `sedan_hatch` or `suv_mpv` whose wheels are hidden: every linked wheel is `wheel_covered` or `not_visible`, or none is linked. A linked wheel that failed the 40 px rule still counts as visible, so that vehicle gets no body reading (C69).

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
| Vehicle | Its wheels disagree by more than one level | C43 |
| Vehicle | It has a `wheel_covered` wheel, and its body waterline is at `door_sill` or lower | C53 |
| Wheel, before numbering | The longer side of its SAM box is under 40 px | plan §7 step 4, C56, C69, P2 |
| Wheel, before numbering | No vehicle box holds its centre, or more than one does | C55, C69 |
| Vehicle or person, before numbering | Beyond the cap of 6 per kind, smallest boxes first. A cut vehicle takes its wheels with it. | C70, P6 |
| Wheel | Its vehicle was dropped | C55 |
| Person | `adult` is `no` or `unsure` | plan §7 step 4 |
| Person | Wading (`standing_still` is `no` or `unsure`) while any adult in the photo is standing still, even one whose waterline is hidden | D13, `eval/rules.md` §6, C57 (Rene Q3) |

People get no size floor, because the plan sets none.

**Combining (C43, C54, C57)**
- **References.** Each kept vehicle is one reference. It is read from its deepest wheel or, when its wheels are hidden, from its body. Each counted adult is one reference.
- **Disagreement.** `eval/rules.md` §6, as written, counts a floor at its own level, like an exact reading. The photo is refused (`references_disagree`) when any two readings differ by more than one level (C54, Rene Q4).
- **The gutter gap.** Landmarks never give `gutter`. So `tire_only` and `rim_quarter` are two levels apart and refuse together, and so do `ankle` and `mid_shin` (Rene Q2).
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
| `failed` | `model_calls_paused` | The model-calls switch isn't `off` |
| `failed` | `photo_missing` | `NoSuchKey` or `AccessDenied` on the raw photo (R22) |
| `failed` | `bad_file` | `blur_for_meta` rejects the file |
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
- **OpenCV cap.** `OPENCV_IO_MAX_IMAGE_PIXELS` is set in `lusot_analysis/__init__.py` (R26). The 50 MP cap then holds whichever module imports `cv2` first.
- **Container:**
  - Add `COPY prompts` to the Dockerfile and `!prompts` to `.dockerignore`.
  - Prompts and schemas load through a path that doesn't walk up from `__file__`, because the image's layout differs from the repo's. A check in the built image loads them.
  - pip checks the hash of every locked package, including those the base image already has. Installing into the task root with `--target` is one way to do this.
  - `jsonschema` becomes a runtime dependency, locked with its hash.
- **Analysis role:**
  - `s3:PutObject` on `blurred/*`.
  - `s3:ListBucket` on the bucket, limited to the `raw/` prefix.
  - AWS documents that a missing object reads as 404 with `s3:ListBucket` and as 403 without. It doesn't say whether a prefix-limited grant counts. So `AccessDenied` stays in the missing-photo rule, and the cloud check records which code a missing key returns.
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
  - the level in words, followed by "at this spot (MMDA level)"
  - "at least" in front of the level when `levelIsFloor` is set
  - then the class and the reference count
- **The other outcomes:** no flood seen, a refusal and processing failed appear as plan §9's three separate messages. A poll timeout reads as processing failed.
- **For testing:** the reason code shows as a small line. MS1's footer line stays.

Final wording waits for MS5 and Rene's review (M20).

## 4. New calls (Claude's)

C42 to C49 come from the draft. C44 to C48 are revised where marked. C50 onward are new.

| # | Call | Why |
|---|---|---|
| C42 | **Encoding the results.** `done` carries either a level or `noFloodSeen: true` with no level. `refused` and `failed` carry a `refusalReason` from §3.4. | CLAUDE.md keeps processing failed, no flood seen and can't tell apart. Plan §9 gives each its own message. |
| C43 | The deepest wheel speaks for its vehicle. A vehicle whose wheels disagree by more than one level (C54's test) is dropped. | Plan §7 step 5 treats a vehicle's wheels as a single reference, because one tire size applies to all of them. |
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
| C54 *(revised after the builder check)* | In the disagreement check, a floor counts at its own level, as `eval/rules.md` §6 is written. A photo is refused when any two readings differ by more than one level. `levelIsFloor` is true when a floor sits at the result level. Ties go to a floor, then to a wheel, a body and a person, in that order, then to the lowest box id. | §6 sets the one-level rule without exempting floors, and it changes only with Rene's written OK. Reading a floor as "this level or deeper" would answer more photos (such as "at least tire" beside a chest-deep adult), and that is Rene's Q4. The tie order keeps results repeatable (B3) and prefers the cautious wording. |
| C55 | A wheel joins the vehicle whose box holds the centre of the wheel's box. A wheel inside no vehicle box, or inside more than one, is dropped. Rims are linked in 3b. | A wheel's reading needs its vehicle's type and motion, and choosing between two cars would be a guess. No 3a step reads a rim. |
| C56 | The 40 px rule measures the longer side of the wheel's SAM box, on the image sent to Meta. | Water hides the bottom of a wheel, so its visible height shrinks as the water rises. Measuring height alone would drop the deepest readings first and push results shallow. (P2) |
| C57 *(revised after the builder check)* | `standing_still = unsure` counts as wading. Wading adults count only when no adult in the photo is standing still, even one whose waterline is hidden. Each counted adult is one reference. | Plan §7 step 4 counts unsure as moving. D13 and `eval/rules.md` §6 use exactly this wording, and both are Rene's. Letting wading adults count when the standing adult gives no reading is Rene's Q3. |
| C58 | The quality scores use the photo before the face blur. The face blur still runs before any Meta call. | Plan §7 step 1 runs the same check on the phone, which has no face detector (C20). Only pre-blur scores can match it. The check sends nothing to Meta. |
| C59 | A Meta error that outlasts the client's retries ends `failed/model_error`. Any other pipeline exception ends `failed/pipeline_error`. Only AWS errors return the message for an SQS retry. | CLAUDE.md caps Meta calls at 3 to 5 attempts, and an SQS retry would pay again for the calls that worked. The person sees "processing failed" in seconds, not after the 18-minute visibility timeout. |
| C60 | The handler loads the Meta key and reads the model-calls switch before the claim. It acts on a set switch after the claim. A failed key load isn't cached. | The ruling wants an unreadable switch to leave the report `pending`, which holds only before the claim. Failing a report under the claim also covers one whose lease expired. A key fault ends in the dead-letter queue and its alarm, not in failed reports. |
| C61 | Only a level result stores a photo (`blurred/{id}.jpg` and `photoKey`). `basis` is stored as counts. `readings` wait for MS4. | Plan §7 places step 4's exits before step 8. Nothing in 3a reads other photos or per-reference readings. MS4's overlay can add them. |
| C62 | The Lambda never logs or stores Muse Spark's `reason` text. Only the offline runner saves it. | Table 5 makes it an evaluation log. Free text can describe people or plates, and CloudWatch keeps logs for 14 days, past the 7-day limit. |
| C63 | `wake_visible` is read, but it doesn't change the result in 3a. | Table 5 uses it to lower confidence, and 3a has no confidence output. |
| C64 | 3a doesn't read `/lusot/stop/publish`. MS4 applies it where pins reach the map and the feed. | Plan §13 ties publishing to the public map. In 3a, a result can be read only through the uploader's unguessable report id. |
| C65 | 3a takes in Table 8's people rows, a landmark-only combine and `levelIsFloor`. The inches level rule moves to 3b. | The design's MS3 row puts the person cross-check and combining in 3b, and its MS4 row holds `levelIsFloor`. But Table 8 includes the standing-adult rows, and D13 counts people fully. A photo with two references needs step 6 to give any result, and `wheel_covered` already yields floors. No 3a step produces inches. |
| C66 | The offline runner sends the 5 phrases the reading uses, skipping `face` and `license plate`. It refuses any path inside a folder named `sealed`. | Plan §14 skips those two requests offline, since nothing offline is published. CLAUDE.md and C39 keep sealed data untouched. |
| C67 | `GET /reports/{id}` returns `noFloodSeen` on every `done` report, and the level fields only with a level. It never returns the location, `readings`, `photoKey` or the claim. | This gives the app one rule to rely on. Links wait for MS4. |
| C68 | B1's 60 s bound is provisional and applies to the smoke run only. | Plan Table 22 sets no time for 3a. The 10 s photo-to-pin target is MS5's, and the probe's latency sets the real bound. (P3) |
| C69 | Before numbering, SAM's results lose every wheel that fails the 40 px rule (C56) or links to no single vehicle (C55). Such a wheel gets no number. A linked wheel dropped for size still counts as visible, so its vehicle gets no body reading (C53). | SAM's boxes alone decide both rules, so Muse Spark needn't answer about wheels that can't count. Fewer labels mean fewer id mistakes and a shorter paid answer. A small visible wheel means water isn't hiding it, so the body rule's premise fails. |
| C70 | At most 6 vehicles and 6 people get numbers, largest boxes first. Wheels follow their kept vehicles. Cut boxes are logged by count. | A crowded street can return dozens of instances. Every label adds to the strict answer, its cost and its id mistakes. The largest boxes are the nearest and the most readable. The caps are provisional (P6). |
| C71 | If no STURM photo gives a level in B1:<ul><li>First, the probe's saved outputs are replayed offline, with no Meta call, to find likely candidates.</li><li>Then up to 15 more STURM photos from Level1 to Level3, the next in the seeded order, go through the cloud.</li><li>If none of those gives a level, B1 is recorded as partly met, with the reason. 3a then closes on B2 to B5 and the other cloud checks, and the cloud proof of a level moves to the first Manila photos.</li></ul> | STURM's crops can rightly make Muse Spark answer `moving: unsure` or a type outside the two allowed, and those refuse. More STURM photos stay within C12 and cost a few cents. Holding 3a open for a data gap would stall MS3b. |

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
| P1 | Prompt v1, or a v2 that the probe teaches. This includes how Muse Spark answers waterlines on a dry street, and how often its ids go wrong. | the prompt version (§3.2 step 4), C47, C52 |
| P2 | Whether SAM's wheel boxes on partly submerged wheels are good enough for the 40 px rule | C56's measure and the 40 px number |
| P3 | Typical and worst latency per photo | B1's 60 s (C68), which must stay under the 180 s Lambda timeout |
| P4 | How often SAM returns an empty water mask on a flooded photo. The water test measures it first, then the Manila check (C34, C40). | how many photos C51 refuses |
| P5 | Face boxes that overlap wheel boxes (the probe counts them) | If any appear, a rule to drop a blurred wheel. `blur_for_meta` would then have to return its boxes. |
| P6 | Busy scenes: how many SAM instances a Manila street returns, and whether 6 vehicles and 6 people cover the readable references. STURM crops can't show this. The first Manila photos measure it. | C70's caps |

## 7. Questions for Rene

Most important first. 3a builds on the defaults until Rene answers.

| # | Question | Default if unanswered |
|---|---|---|
| Q1 | **Scope of D14.** SAM can find no water while Muse Spark says there is standing water. Should the plan §7 step 2 refusal stand, since D14 only added no flood seen for dry streets? Or may the landmarks give a level anyway? | Refuse, as `no_water_found` (C51). P4 shows how often this happens. |
| Q2 | **The gutter gap.** Landmarks never give `gutter`, so `tire_only` beside `rim_quarter` (or `ankle` beside `mid_shin`) is two levels apart. Under `eval/rules.md` §6, that refuses. Should the gap count landmark steps instead? Both readings are PATV, so only coverage on shallow scenes changes. A change needs Rene's written OK in that file's change log. | Keep the rule as written (refuse) |
| Q3 | **A standing adult with a hidden waterline.** D13 and `eval/rules.md` §6 count wading adults only when no adult in the photo is standing still. Should a standing adult whose legs are hidden (behind a car, say), and who gives no reading, still block the wading adults? This happens often on busy streets. | Yes, as written (C57). More photos refuse. |
| Q4 | **Floors in the one-level rule.** "At least tire" (wheels covered) beside a chest-deep adult agree physically, but §6 as written refuses them, because tire and chest are two levels apart. Should a floor count as "this level or deeper" when references are compared? A change needs Rene's written OK in that file's change log. | Refuse, as written (C54) |
