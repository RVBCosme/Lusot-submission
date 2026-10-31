# Overnight accuracy check, Nov 1, 2026

Window 4, on Rene's instruction to the tracker at about 1:30 AM: "make sure the core functionality (take picture, assess, give correct feedback) is accurate; continue to improve it." This note records what was measured, what it showed and what waits for Rene. Nothing here changed the deployed stack or `main`'s measuring path.

> **Caveat on every number below.** The development set is Set C's `open-licensed-ph`: 133 Philippine flood photos from Wikimedia Commons and Flickr (CC0, CC BY 2.0, CC BY-SA 4.0). Its depth labels are **Claude's visual estimates, never checked by Rene** (`label_status`). They are weak labels. Set C is development only and never counts toward headline numbers (`eval/rules.md`). One case (OL127) was checked by eye. The CC BY-SA 4.0 rows are analysis only and are never shown anywhere. No Set A, A-neg or sealed data was opened, listed or used.

## 1. Rene's 40 neighbourhood photos (check set, not for tuning)

Rene's own photos of wet and dry streets near home, taken Oct 31. They were sent through the deployed upload path, resized as the app sends them (1,600 px, JPEG 85), one at a time, from the smoke test's point outside Metro Manila, so every report was private.

| Outcome | Count |
|---|---|
| done / no flood seen | 36 |
| refused / photo unusable | 3 |
| refused / no water found | 1 |
| **level (a false positive here)** | **0** |

SAM found floodwater in none of the 40. The map had 0 pins before and after, and each batch's no-pin check passed. Not-used causes: wheel_small 68, vehicle_cap 43, wheel_unlinked 18, wrong_list 8, wheel_cap 1. Cost $1.5036.

## 2. The phone test's outcomes, about 12:50 to 1:06 AM

Six photos were analysed. Rene's own 4 uploads (screen photos of floods, `mode=live`) ended photo_unusable 1, no_usable_reference 2 and too_dark 1. The 2 levels came from the app's sample photos (`mode=sample`). The map showed 0 pins, which is correct: samples never pin (`handler.py`'s `_PUBLISHED_MODES`, C516), and only a level pins. A live level reaching the map was not exercised.

## 3. Snapshot of the deployed pipeline on 120 labelled development photos

`probes/dev_eval.py run` over the 120 photos with a level label (13 "unclear" left out), using the laptop pipeline, whose analysis code and prompt match the deployed image. Saved runs: `lusot-data\runs\dev\C\default_boxes-v1\`. Cost $3.7173.

| Outcome | Count |
|---|---|
| refused / no usable reference | 93 |
| done / level | 15 |
| done / no flood seen | 6 |
| refused / references disagree | 3 |
| refused / photo unusable | 2 |
| refused / no water found | 1 |

Levels against the labels, 14 scorable (the 6 "above knee" rows apart, which aren't an MMDA level): **exact 3 (21%), within one level 9 (64%)**. One level of half tire or more on a gutter-or-below label (OL018, gutter deep read as knee).

What decided each level:

| Deciding reference | Levels | Against the labels |
|---|---|---|
| A wheel, waterline `tire_only` | 7, all below gutter | 5 labelled gutter deep, 1 below gutter, 1 half knee. Within one, except OL083. Water only on the tire sits under a sedan's rim, about 5 inches, so this is consistent. |
| A person, waterline `ankle` | 4, all below gutter | OL086 right; **OL114 (half knee), OL127 (knee), OL130 (knee): under-reads** |
| A person, `mid_thigh` | 2 | tire, on above knee and knee deep labels |
| A person, `knee` | 1 | OL018, knee on a gutter deep label |
| A person, `waist` | 1 | right |

**The under-read is the main finding.** In OL127, checked by eye, adults stand in water to about mid-shin or knee, but Muse Spark answered `ankle` for both the deciding adult (box 2) and the one in the centre. So Lusot read the water as below the gutter in about knee-deep water. That's the dangerous direction: shallower than the water is.

## 4. Why most photos are refused

Of the 93 refusals, by what Muse Spark answered:

| What the photo had | Photos |
|---|---|
| No sedan or SUV, and no adult standing still | 43 |
| An adult standing still, but no sedan or SUV | 26 |
| Both | 12 |
| A sedan or SUV, but no adult standing still | 12 |

Muse Spark typed the vehicles as tricycle 122, unknown 86, motorcycle 71, SUV or MPV 33, bus or truck 28, sedan 18, van 13, pickup 9 and jeepney 9. Only `sedan_hatch` and `suv_mpv` give readings (C45). The still adults' waterlines were not_visible 29, ankle 27, mid_shin 4, knee 1 and mid_thigh 1.

All not-used causes: wheel_vehicle_dropped 181, wheel_small 175, vehicle_moving 173, person_cap 143, vehicle_type 128, person_not_adult 117, person_no_reading 93, no_water_contact 81, vehicle_cap 76, wheel_unlinked 58, person_wading 53, vehicle_no_reading 37, person_unanswered 36, vehicle_unanswered 32, wrong_list 31.

**vehicle_moving.** 96 photos have water and numbered vehicles. Every vehicle was dropped as moving in 24, and some were in 50. Muse Spark answered moving yes 55, unsure 141 and no 193, and "unsure" drops too (W1). Reading "unsure" as "no" in a $0 replay changes **none** of the 120 outcomes: those vehicles then fall to vehicle_type or give no reading. So vehicle_moving isn't the binding rule here, and slow wading trucks aren't a reading type anyway.

## 5. What was tried

All replays use the saved runs and make no Meta call. The base replay matched all 120 saved outcomes.

| Variant | Levels | Exact | Within one | Off by 2 or more | Over-reads on gutter-or-below labels |
|---|---|---|---|---|---|
| Deployed (base) | 15 | 3 of 14 | 9 of 14 (64%) | 5 | 1 (OL018) |
| A: moving "unsure" read as "no" | 15 | 3 | 9 | 5 | 1 |
| B: adult "unsure" read as "yes" | 16 | 4 of 14 | 10 (71%) | 4 | 0 |
| **D: an `ankle` answer gives no reading** | **11** | 2 of 10 | **8 of 10 (80%)** | **2** | 1 (OL018) |

Under D, the three under-reads become refusals and the one right `ankle` level (OL086) is lost.

**A prompt fix was tried and failed.** On a branch, `muse_spark_photo_v2` added one sentence after v1's waterline line:

> For a person, picture their whole body, including the part under the water. ankle means the water reaches only their feet and ankles. When their shins or knees disappear into the water, the waterline is where the surface crosses their legs, such as mid_shin or knee, even though their feet can't be seen: judge it by how much of their legs still shows above the water.

Judge-only reruns on the saved SAM outputs, on the first 12 of the 56 photos with an adult answered `ankle` or `mid_shin`. These included OL086, OL114, OL127 and OL130. Cost $0.2578. The adults' answers moved ankle → ankle 15, ankle → not_visible 3, mid_shin → mid_shin 2 and **mid_shin → ankle 1**. All 4 levels were unchanged. The wording didn't fix the under-read, so the test stopped and the v2 files were not kept.

## 6. Options for Rene

Each changes the measuring path, so each needs Rene's OK and, for the level rules, a line in `eval/rules.md`'s change log. No freeze tag exists yet (freeze-1 waits for his approval on the evening of Nov 3), so a change made before then is what the freeze pins. After the freeze, only fixes that can't change a depth output may land (`eval/rules.md` §10).

- **A. A prompt change (v2):** not supported. The one wording tried changed nothing. A stronger change, such as asking for the visible leg length, would need its own test, and it changes the pinned prompt version.
- **B. A conservative code rule: an adult's `ankle` alone can't set a level.** Variant D is its upper bound: levels 15 → 11 on this set, within one 64% → 80%, the 3 known under-reads removed, 1 right level lost. A softer form (`ankle` counts only when another reference agrees) loses less coverage but needs code to measure. It changes the level rules, so it needs a spec C-call and `eval/rules.md`'s change log.
- **C. Both:** no evidence that A adds anything to B.
- **D. Leave as is:** the deployed pipeline can read knee-deep water as below the gutter when an adult's waterline is answered `ankle`. On this set that happened in 3 of 15 levels.

Rene's 40 dry and wet street photos are unaffected by any of these: SAM found no water in them, so no reference was ever read.

## 7. Coverage, as context only

78% of these labelled flood photos were refused, mostly because the photo has no sedan, no SUV and no adult standing still. Tricycles and motorcycles are the most common vehicles in Philippine flood photos, and they aren't reading types (C45). That's the design's choice of a refusal over a guess. Adding vehicle types isn't proposed before the freeze.

## Spend

Tonight's Meta spend from 11:41 PM: $5.9208 on MS4's counter ($3.714364 → $9.635116), plus $0.0010 off it (the voice diagnostic). That's under the night's $6.50.
