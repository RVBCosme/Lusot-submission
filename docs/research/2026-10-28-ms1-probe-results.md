# MS1 probe results (Oct 28, 2026)

The MS1 probes (spec §3.4) ran 15 STURM-FloodDepth photos through Meta's models: 5 through SAM 3.1 and Muse Spark 1.3 (A1), and 10 through SAM's water test (A2). A synthetic English clip went to Muse Voice Transcribe. This note records the counts, timings, cost and findings. STURM photos aren't Manila photos, so the water results are an early signal only (C34, C40).

Markers: ✅ as expected · ⚠️ needs action or a decision · ➕ new fact.

## 1. The run

- **When:** Oct 28, 2026. It started at 12:47:15 PM Manila time (UTC+8) and ran once.
  - 218.1 s inside the script, 220.4 s wall time
  - exit code 0
- **How:**
  - `probes/make_test_wav.ps1` first.
  - Then, from `backend/analysis` in PowerShell, with the key set from the Windows user variable in the same command: `uv run python probes/run_probe.py` (the defaults, `--photos 5 --water 10`).
  - The code was commit `1e08f1e`. The label fix in §4 (`5dfdb89`) came after the run.
- **Recorded in `summary.json`:**
  - blur `yunet-2023mar/multiscale-1-0.5-0.25/pixelate-gauss-v2`
  - prompt `muse_spark_photo_v1`
  - models `sam-3.1`, `muse-spark-1.3` and `muse-voice-transcribe-1.0`
- **Outputs** are in `%LUSOT_DATA_DIR%\probes\2026-10-28\`, outside the repo (C30):
  - `summary.json`
  - `a1\` and `a2\`: raw SAM streams, masks, the numbered images, Muse Spark's raw answers and the overlays
  - `voice\`
  - `meta_calls.jsonl`: one line per HTTP try, without content
  - the review crops used in §6
- **Selection (R7):** the 2,267 files in `Level1` to `Level3`, sorted by relative path, then `random.Random(20261028).sample(names, 15)`. The first 5 went to A1 and the next 10 to A2. `summary.json` lists them in sample order:
  - **`a1_photos`:** `Level1/car-1623-Level1_2.jpg`, `Level2/car-1335-Level2_1.jpg`, `Level1/car-1510-Level1_1.jpg`, `Level3/car-2069-Level3_4.jpg`, `Level3/car-752-Level3_3.jpg`
  - **`a2_photos`:** `Level1/car-763-Level1_1.jpg`, `Level2/car-1772-Level2_1.jpg`, `Level1/car-111-Level1_3.jpg`, `Level3/car-1385-Level3_1.jpg`, `Level2/car-1491-Level2_1.jpg`, `Level2/car-1350-Level2_2.jpg`, `Level1/car-1476-Level1_1.jpg`, `Level1/car-1015-Level1_1.jpg`, `Level2/car-1341-Level2_2.jpg`, `Level3/car-1383-Level3_1.jpg`
- The photos are 240 to 492 px on the short side and 260 to 999 px on the long side, so `blur_for_meta` sent them at their own size.

## 2. Calls, tokens and cost

- ✅ **Calls:**
  - SAM: 55 (35 in A1, 20 in A2)
  - Muse Spark: 5 answers and 5 token counts
  - voice: 1
  - All 66 HTTP tries returned 200 the first time: no retry, and no fallback to background mode.
- **Tokens:**
  - counted input: 3,637
  - billed input of the 5 answers: 2,769
  - output: 16,320
- ✅ **Estimated cost: $0.2105**, under the $0.50 budget, at the prices in the [Oct 26 verification notes](2026-10-26-verification-notes.md):
  - SAM: $0.1375
  - Muse Spark: $0.0728
  - voice: $0.0002
  - Meta doesn't say whether token counting is billed. If it is billed as input, add $0.0045.
- ⚠️ **Per photo, about $0.032:** SAM's 7 phrases $0.0175, plus Muse Spark's $0.0146. The verification notes assumed $0.0213, with Muse Spark at 2,000 tokens in and 300 out. Here the input was smaller (small photos), but the output was about 10 times larger (§4). At this rate, $150 covers about 4,700 photos rather than 7,050.

## 3. SAM 3.1

Instances per phrase in A1:

| Photo | floodwater | wheel | wheel rim | person | vehicle | face | license plate |
|---|---|---|---|---|---|---|---|
| car-1623-Level1_2 | 1 | 1 | 0 | 0 | 1 | 0 | 1 |
| car-1335-Level2_1 | 1 | 2 | 2 | 0 | 2 | 1 | 1 |
| car-1510-Level1_1 | 1 | 2 | 1 | 0 | 5 | 0 | 1 |
| car-2069-Level3_4 | 1 | 0 | 0 | 0 | 5 | 0 | 0 |
| car-752-Level3_3 | 1 | 0 | 0 | 0 | 0 | 0 | 0 |
| **Total** | 5 | 5 | 3 | 0 | 13 | 1 | 3 |

In A2, `floodwater` matched once in each of 5 photos and nothing in the other 5. `wheel` gave 20 instances over the 10 photos (§6).

- ✅ **Latency, all 55 requests:** p50 1.46 s, maximum 4.67 s. The first photo's 7 requests took 3.0 to 4.7 s while the connections opened; later ones took 0.4 to 2.3 s.
- ✅ **Empty phrases:** a phrase with no match completed with an empty result. For example, `person` matched nothing in all 5 A1 photos.
- ⚠️ **A missed vehicle:** `vehicle` found nothing in car-752, a wrecked car swept along under debris. Muse Spark therefore got no boxes, and correctly named no ids.
- ➕ **`face` matched a windshield:** its one match, in car-1335, is the car's windshield (score 0.62), and no one is in that photo. YuNet found no face there, which was right. In MS3, SAM's face masks would blur that windshield before storage, which costs nothing for depth.
- ➕ **Plates:** `license plate` matched in 3 of the 5 A1 photos. Plates still reach Meta unblurred, as the rules expect.
- ➕ **Small, far-off wheels:** some `wheel` matches are far from any submerged wheel: 13 × 17 px near the top of car-763, and two of about 15 px near the top of car-1341. MS3a's 40 px rule (C56) drops such wheels.
- ➕ **Mask alignment:** 49 of the 55 masks fill their half-open box exactly; the other 6 sit 1 px inside it on one edge.

## 4. Muse Spark 1.3 (prompt v1, schema v1, strict)

| Photo | Boxes | Counted / billed input | Output | Time | Valid | Id problems |
|---|---|---|---|---|---|---|
| car-1623-Level1_2 | 2 | 622 / 437 | 1,883 | 21.7 s | ✅ | none |
| car-1335-Level2_1 | 4 | 783 / 626 | 5,145 | 54.5 s | ✅ | `vehicle id 2 in people` |
| car-1510-Level1_1 | 7 | 682 / 509 | 5,279 | 50.6 s | ✅ | none (but id 1 was hidden, see below) |
| car-2069-Level3_4 | 5 | 778 / 582 | 2,565 | 24.7 s | ✅ | none |
| car-752-Level3_3 | 0 | 772 / 615 | 1,448 | 16.9 s | ✅ | none |

- ✅ **Schema validity, 5 of 5:**
  - Every answer parsed and passed schema v1 (Draft 2020-12): `schema_valid: true` and `schema_errors: []`.
  - Strict mode accepted `array`/`items`, `integer` and `boolean`, which Meta's structured-output page doesn't name. No request got an HTTP 400.
- ✅ **Categories only:**
  - No answer gave inches or any number except ids.
  - Every `reason` was 54 to 77 characters, within the 200 the prompt asks for.
  - The keys come back in alphabetical order, not the schema's, which doesn't matter for JSON.
- **The answers:**
  - **car-1623** (a dark night photo): `photo_usable: no` and `standing_water: unsure`, so a refusal.
  - **car-1335:** water yes; the sedan at `door_sill`; wheels 3 and 4 at `rim_quarter`.
  - **car-1510:** water yes; the van at `door_sill`, moving, with a wake; wheels 6 and 7 at `tire_only`.
  - **car-2069:** water yes; the van at `mid_door`; no wheel boxes, because the wheels are under water.
  - **car-752:** water yes, with empty lists.
- ✅ **One id problem, in car-1335:**
  - Box 2 is a 59 × 32 px sliver at the photo's top edge. SAM called it a vehicle (score 0.63); Muse Spark listed it as a person, with every field `unsure` or `not_visible`.
  - `check_ids` caught it as `vehicle id 2 in people`. MS3a's per-item check drops it as `wrong_list`.
- ⚠️ **A label covered another (car-1510), now fixed:**
  - Vehicle 1's box starts at (38, 11) and vehicle 4's at (45, 7). Both labels were moved down inside the photo's top edge and landed 7 px apart, so label 4 hid id 1. Muse Spark answered vehicles 2 to 5 and wheels 6 and 7, never 1.
  - `5dfdb89` fixes it: a label now also avoids the labels drawn before it, and faces still come first. Redrawn from the run's saved SAM boxes, car-1510 shows all seven ids (`numbered_after_label_fix.jpg`). The probe wasn't rerun.
- ⚠️ **Latency and reasoning:**
  - The answers took a median of 24.7 s and at most 54.5 s.
  - The output was 1,448 to 5,279 tokens, but the answers are only 170 to 636 bytes. So about 95% of the output is reasoning. That share is an estimate: the client keeps only the totals, not `reasoning_tokens`.
  - Meta's [reasoning page](https://dev.meta.ai/docs/reasoning) says:
    - `reasoning: {"effort": ...}` takes `minimal` to `max`
    - without it, the model picks its own level
    - `none` returns HTTP 400 for Muse Spark
    - reasoning tokens are billed as output
  - **For MS3a:**
    - Give the analysis Lambda about a minute for this call, and keep the queue's visibility timeout at 6 times the Lambda's.
    - Try `low` or `minimal` effort on development photos before settling.
    - At the default effort, a photo can't reach the map in under 10 s.
- ➕ **Counts aren't bills:**
  - `/responses/input_tokens` counted 25 to 42% more than the answer call billed as input, even though the answer call also carries the schema.
  - Meta's [token counting page](https://dev.meta.ai/docs/token-counting) says counts are for context-window fit, not billing. Cost should come from `usage`.
  - A count took 2.2 s at the median and 2.6 s at most.

**The prompt for MS3a is v1 (`muse_spark_photo_v1`); no v2 is needed.**
- All 5 answers were valid.
- The one id problem is an ambiguous sliver that SAM and Muse Spark classed differently, which the per-item check handles.
- The hidden id came from the drawing, which `5dfdb89` fixes.

## 5. Faces

- ✅ YuNet found no face in any of the 5 A1 photos: `faces` is 0 and `face_boxes` is empty for each. SAM's `person` found no one in them either.
- ✅ Face boxes over a SAM wheel box, after growing each by the blur margin of 0.25: none. No wheel lost detail to the face blur.

## 6. Water test (C40)

**The rule:**
- A photo passes when the floodwater mask reaches each submerged wheel's lower edge and covers less than 10% of the wheel mask.
- A photo with no water mask or no wheel mask fails (R72).
- **My reading of "reaches":** the water mask comes within 5 px of the wheel mask's lower edge along that edge. SAM leaves a seam of 2 to 3 px between any two of its masks (see the findings).

I opened every overlay, then zoomed crops of each wheel (the blurred photo beside the overlay).

| A2 photo | Water / wheels | Each wheel: overlap; share of the lower edge with water within 3 px / 5 px | Verdict | Why |
|---|---|---|---|---|
| car-763-Level1_1 | 0 / 1 | 0: 0.0 | ❌ | No water mask. It is a night photo with water all round the car; the one wheel match is a far-off car's (13 × 17 px). |
| car-1772-Level2_1 | 1 / 1 | 0: 0.0; 96% / 99% | ✅ | The water meets the wheel's lower edge. |
| car-111-Level1_3 | 0 / 2 | 0: 0.0; 1: 0.0 | ❌ | No water mask. Rear view on a wet road. |
| car-1385-Level3_1 | 1 / 1 | 0: 0.0; 84% / 99% | ✅ | Only the top arc of the rear wheel shows, and the water meets it with a seam of about 3 px. |
| car-1491-Level2_1 | 1 / 2 | 0: 0.0; 96% / 100%. 1: 0.0; 56% / 97% | ✅ | Both wheels are met. The front one's seam reaches 4 to 5 px under splash. |
| car-1350-Level2_2 | 1 / 2 | 0: 0.0; 78% / 89%. 1: 0.0; 0% / 0% | ❌ | Wheel 1 is a 7 × 23 px sliver of another car's wheel that runs into the frame's bottom edge, with no water mask within 30 px. Wheel 0 passes. Setting frame-cut wheels aside would pass the photo. |
| car-1476-Level1_1 | 0 / 5 | all 0.0 | ❌ | No water mask. Shallow water on the road behind two white cars. |
| car-1015-Level1_1 | 0 / 2 | 0: 0.0; 1: 0.0 | ❌ | No water mask, although muddy water surrounds the SUV's wheels in heavy rain. |
| car-1341-Level2_2 | 0 / 4 | all 0.0 | ❌ | No water mask. The photo has a strong yellow colour cast. |
| car-1383-Level3_1 | 1 / 0 | none | ❌ | No wheel mask: the wheels are under water. |

**Pass count: 3 of 10** (car-1772, car-1385 and car-1491). It is 4 of 10 if car-1350's frame-cut wheel is set aside.

- ✅ **Overlap:** the "less than 10%" half held everywhere. All 20 wheel masks in A2 overlap the water by 0.0, and SAM never put water on a wheel.
- ⚠️ **The seam:** SAM's water and wheel masks don't touch.
  - Under the 5 wheels whose lower edge meets water, the median gap is 2 to 3 px. 56 to 96% of each edge is within 3 px, and 89 to 100% within 5 px.
  - So MS3's step that keeps only water touching an object's lower outline needs about 5 px of tolerance, or it finds no water at all.
- ⚠️ **Floodwater recall is the weak part:**
  - 5 of the 10 A2 photos got no water mask. Four are Level 1 photos (one at night, one in heavy rain, two of shallow water on a road), and the fifth is a Level 2 photo with a strong colour cast.
  - All 5 A1 photos did get one, but car-2069's covered only a strip at the right edge (score 0.50).
- ⚠️ **Deep water hides wheels:** Level 3 photos (car-1383, car-2069) give no wheel mask, so only the body waterline and people can read depth there.
- **What it decides:** this is an early signal for Rene. As C40 says, the plan's Table 18 fallback (dropping the geometry layer) is decided on the Manila check (C34) at MS3, or by Rene sooner.

## 7. Voice

- ✅ **The clip:** `make_test_wav.ps1` wrote it with System.Speech and Windows' default English voice. It is mono, 16-bit PCM at 16 kHz, 3.67 s long (117,486 bytes). The format check passed, and Meta reported 3,680 ms of audio.
- ✅ **The transcript:** "Is the water knee deep at España Boulevard right now?" Every word is right, and the spoken "Espana" came back spelled "España". It took 1.99 s and cost $0.0002.
- ⚠️ **For Ask Lusot:** match spot names with accents folded, so "España" equals "Espana".
- **M12's Taglish recordings (C41)** run with `uv run python probes/run_probe.py --photos 0 --water 0 --voice-dir <folder>`. That sends only the voice clips, into that day's folder. On Oct 28 itself, move this run's `summary.json` aside first: the script refuses to overwrite it.

## 8. Data and attribution

- **STURM-FloodDepth Flooded Cars**, by Nicla Notarangelo (WEO), on Zenodo:
  - version v1, published Feb 7, 2025
  - **CC BY 4.0**
  - DOI [10.5281/zenodo.14833532](https://doi.org/10.5281/zenodo.14833532)
- **How it was used:**
  - Images only: `flooded_cars.zip`, folders `upscaled_images\Level1` to `Level3`. None of the dataset's code.
  - Development probes only. No STURM image is in the repo, this note or the demo.
- The 15 files are the `a1_photos` and `a2_photos` in §1.

Sources: [Zenodo 14833532](https://zenodo.org/records/14833532) · [structured output](https://dev.meta.ai/docs/structured-output) · [Responses schemas](https://dev.meta.ai/docs/api-reference/responses/schemas) · [reasoning](https://dev.meta.ai/docs/reasoning) · [token counting](https://dev.meta.ai/docs/token-counting) · [models](https://dev.meta.ai/docs/models)
