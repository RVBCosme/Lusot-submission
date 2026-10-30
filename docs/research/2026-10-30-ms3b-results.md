# MS3b results: rim geometry built, its cloud proof and its tuning still waiting (Oct 30, 2026)

MS3b's build ran from 11:38 PM on Oct 29 to 5:43 AM on Oct 30, Manila time (UTC+8), on `ms3b-geometry`, branched from `main` at `96c2f11`, where MS3a is merged. This note records counts and figures only: no photo, photo name or path, key or account ID. The photos are C87's Wikimedia Commons flood photos and the Commons car photos in the private Set C folder, and a photo is named here only by its place in C87's seeded order. Their credits are kept in `attribution.csv` beside them. The [MS3a results note](2026-10-29-ms3a-results.md) covers the landmark core that this builds on. The plan is [here](../superpowers/plans/2026-10-28-ms3b-geometry.md), the spec [here](../superpowers/specs/2026-10-28-ms3b-geometry-design.md), and the day's work is in the [Oct 30 log](../log/2026-10-30.md).

Markers: ✅ as expected · ⚠️ needs action or a decision · ➕ new fact.

**In short.** The geometry code is built, reviewed and deployed. No credited Commons photo measured a wheel or gave a level in the cloud, so geometry has not yet produced a reading on a real photo. Set B, the split and `eval/rules.md` v0.7 don't exist yet, so nothing is tuned, calibrated or scored. Every figure below is indicative, never a headline number.

## 1. Where each done-check stands

| Check | State | In one line |
|---|---|---|
| D1 | partly met | The deploy and every cloud check passed, and the synthetic replays pass. No credited Commons photo measured a wheel offline (positions 4 to 9) or gave a level in the cloud (positions 0 to 19). The cloud half moves to the integrated deploy (R155). |
| D2 | waits | No Set B development cars yet. The Set B rows script is built. |
| D3 | ✅ | Tasks 1 to 10a added the rule tests. Analysis: 852 passed, 3 skipped. API: 42 passed. |
| D4 | waits | Not run (Task 16, Should). The defaults stand: effort default, drawing `boxes-v1`, self-check off. |
| D5 | waits | `tuning-v1`, every value untuned. No split and no v0.7, so no sweep, no event replay, no guard 3. |
| D6 | waits | C313's Manila check needs labelled development photos (the split and v0.7). Geometry stays on. |
| D7 | waits | The ablation needs Set B and the harness's report. The export that feeds it is built. |
| D8 | waits | W2 to W9 and W14 have no development results. Early signs from real photos are in §7. |
| D9 | waits | C319's trigger needs D2's figures. |
| D10 | ✅ | Built and tested. The field list was sent to Window 4 at 2:18 AM, and MS4 took it as built. |
| D11 | Task 19 | The sealed-run entry point isn't built yet. |

## 2. What was built

- **Tasks 1 to 12, 10a and 15** are built, each with its own review (Opus 5.5 at `xhigh`). Every task's tests were written first and seen to fail. The mutant checks killed every mutant they ran, for example 17 in Task 3, 15 in Task 5, 13 in Task 6, 11 in Task 7 and 22 in Task 8.
- **The suite grew from 535 passed (1 skipped) before MS3b to 852 passed, 3 skipped** at Task 15's commit. With MS2's merge it was 920, and after the final review's fixes it is 928 passed, 3 skipped. The 3 skips are MS3a's real-run B3 test, which needs a saved run, and two harness-gated tests that skip because `eval/scoring/` isn't in this tree. Those two passed against Window 4's copy, read-only, in the Task 12 review. `backend/scripts` has 82 passed and the API 42.
- **Not built:** Task 13 (the tuning sweep and event replay, Could, skipped), Task 12b (the runner's `record_spend` calls, which wait for MS4's deployed limits table, R154), and Tasks 14, 16 and 17 (they wait, see §14). Task 19 (the sealed-run entry point) comes after the close.

## 3. D1: the offline search, the deploy and the cloud checks

**The offline search** (Task 11 Step 2, 3:32 to 3:35 AM, geometry on): it started at position 4 of C87's order (R150), because MS3a's smoke run found 0 SAM wheels at positions 0, 1 and 2 and no floodwater at 3. It went through positions 4 to 9, six credited photos.

| Result | Count | Notes |
|---|---|---|
| Photos run | 6 | |
| A wheel measured | **0** | |
| `no_usable_reference` | 3 | Position 4: 8 SAM wheels, 2 rims, `rim_missing` 1 and `waterline_dropped` 2, and `no_water_contact` 6. Position 6: 7 wheels, 4 rims, `vehicle_type` 4 and `wheel_vehicle_dropped` 4. Position 7: `no_water_contact` 2. |
| `photo_unusable` | 3 | Positions 5, 8 and 9. |

**The deploy** (`DEPLOY RUNNING` at 3:40 AM, `DONE` at 3:51 AM):
- `sam build` exited 0 in 27 s. The image SAM built, not a manual `docker build`, was run with `--network none`: its imports worked, it held `tire-codes-v1` with 12 codes and `tuning-v1`, and `/var/task/prompts` held the `.md` and `.schema.json` files.
- `npm run deploy` exited 0 in 107 s. `AnalysisFunction` was updated, and the image repository kept 3.
- `sam validate --lint` had passed earlier (Task 10), with one `GEOMETRY_IN_LEVEL` line and no parameter.

**The smoke run** (`smoke_upload.py --bound 180`, 3:44 to 3:50 AM): it exited 3 with `SMOKE NO LEVEL` after 369.8 s. Every other check passed.
- B1's 5 photos: `photo_unusable` 1, `no_usable_reference` 3, `no_flood_seen` 1, each final in 25.0 to 66.3 s.
- The dark photo was refused with 0 Meta calls. The reused upload link got 204, and the raw photo was gone in 2.3 s (B5). No raw photo was left for any of the 6 reports (B4).
- The missing photo gave `NoSuchKey`, the PNG got 403, the key loaded, and the stop switch worked.

**The C71 fallback** (`--fallback --bound 180`, 3:51 to 4:04 AM): 15 of 15 photos sent (positions 5 to 19), and none gave a level.
- `photo_unusable` 7, `no_flood_seen` 3, `no_usable_reference` 5.
- Each was final in 12.5 to 74.5 s, all inside the 180 s bound. No raw photo was left for any of the 15.
- Step 3 dropped `no_water_contact` 2 in each of 2 photos. The other drops were `person_cap`, `person_not_adult`, `person_wading`, `vehicle_type` and the wheel caps.

**Over positions 0 to 19** (B1's 5 photos plus the 15 of the fallback): 20 photos, **0 levels**. `photo_unusable` 8, `no_usable_reference` 8, `no_flood_seen` 4.

**Why:** Muse Spark's request is unchanged from MS3a (prompt v1, `boxes-v1`, default effort), so the result reflects these Commons photos and the model's answers. Position 2 gave a people level on Oct 29 and now drops `person_not_adult` 6 times instead of 3, with no step 3 cause, so Muse Spark's answer varied, not MS3b's code.

**B3:** the synthetic replay tests pass (`test_b3_geometry_replay_matches` and MS3a's `test_b3_replay_through_runner_and_handler_match`). The real-run test (Step 7) doesn't apply, since no photo measured a wheel and so there is no run to replay. It stays skipped.

**Result: partly met.** The deploy and every cloud check passed, and step 3 and geometry run in the cloud with `GEOMETRY_IN_LEVEL` on. But no credited Commons photo measured a wheel offline or gave a level in the cloud. Per the plan, the first Manila development or consented photo proves it, and so does Rene's QA on Nov 3. Because MS3b makes no further deploy after MS4's Task 9 (R155), the cloud half moves to the integrated deploy, after MS3b merges and MS4's Phase B rebases (MS4 Task 15).

## 4. Step 3 on a real photo ➕

The first cloud runs changed the deployed core's answers, because step 3 runs with geometry off too (C309: "MS3a plus step 3").

- **What changed:** position 4 gave `below_gutter` from people in MS3a's Oct 29 cloud run. It now refuses with `no_usable_reference`, because step 3 drops 6 references as `no_water_contact`. Position 7 drops 2 the same way.
- **The check** (3:36 AM, an offline replay of position 4's run, no Meta call, overlay checked by eye): the 6 dropped references are 3 people and 3 cart or bicycle wheels on a dry debris pile at the left of the frame. SAM's water mask covers only the flooded street, and none of them stands in it.
- **The reading:** MS3a's `below_gutter` for that photo came from people on dry ground, so step 3's refusal is correct. It is what C317 is for. The people walking in the water were dropped earlier (`person_wading`, `person_not_adult`, `person_cap`).
- **What stays open:** this is not a code fault. Whether T = 5 px and the touch share of 0.25 are right is C310's and C313's question, on labelled photos.

## 5. The early rim check (C323) ➕

Run by the controller at 5:41 AM through `set_b.py rims`, with 8 SAM calls and about $0.02. It is diagnostic only: nothing was tuned on it (C310), and dry cars give no depth.

| What | Result |
|---|---|
| Cars in the Commons car set | 6, of which 4 carry tire-code candidates and were sent |
| SAM wheels found | 10 |
| Wheels with one linked rim (C300) | 6 |
| Rims fitted | **6 of 6**, with 307 to 466 contour points and an axis ratio of 0.880 to 0.994 |
| Check 9 (rim size) | **passes 2, fails 4** at START's factors; the 4 failing rim sizes are 0.655 to 0.710, against upper bounds of 0.630 to 0.684 |
| Rim-edge ratio | **1.17 to 1.26** (1.167 to 1.261) on every fitted rim |

- ⚠️ **The reading:** SAM's `wheel rim` mask is about 20% larger than the nominal rim. START's `rim_edge_k` of 1.0 is therefore low, and `rim_size_high` of 1.15 is too tight for real rims.
- **What it means at start values:** check 9 refuses most real rims, so their wheels keep the landmark reading. A rim that does pass would read slightly deep.
- **What fixes it:** C310 calibrates k from Set B's known-waterline rims, cross-checked against MS2's rim-edge ratio, and sets check 9's factors on Set B development rims. Without Set B (MS3b-Q1's fallback), geometry stays uncalibrated. The results note and Rene's QA must say so.

## 6. D2 and D7: Set B and the ablation

**Result: waits** for both.
- **Why:** no Set B development cars exist yet (MS3b-Q1's fallback applies), so there is no median error and no coverage by type, angle or size. The ablation needs MS6's harness, which is on `w4-independent` only, and Set A rows wait for the split.
- **What is built:**
  - Task 15's `set_b.py` writes MS6's Set B rows. It has 14 tests, and MS6's own loader read a synthetic export of it in a scratch folder.
  - Task 12's export writes the development rows (the `landmark` and `geometry` configurations, with the replay columns). It has 53 tests with 2 harness-gated skips, and its labels match the harness's rules (37 labels, 0 mismatches).
  - Under R133, Set A rows exit 2 without the harness (they need `--label-words`), and A-neg rows still write.
- **The figures to fill in later:** Set B's median and worst error, coverage and share measured, by vehicle type, angle and size, each with its n, up to half tire (MS2's C211). Then the ablation tables with their replay columns.

## 7. D8: W2 to W9 and W14

Every row is indicative. Nothing below is scored, and the headline numbers wait for the sealed run (MS6).

| Weakness | Built in MS3b | Real-photo signs so far | Waits for |
|---|---|---|---|
| W2, tire sizes by type | `tire-codes-v1`: 12 codes (`sedan_hatch` 4, `suv_mpv` 7, `van` 1), with `unknown` trying all 12 | The 4 coded Commons cars: check 9 passes 2 of 6 rims at start values (§5) | Set B error by type |
| W3, eyeballed waterline | G4 keeps the deeper of a wheel's two readings, and drops the wheel as `wheel_methods_disagree` when they are more than one level apart | None | The ablation and Set B |
| W4, reflections | Step 3's cut at the waterline, with synthetic reflection tests | None | Development photos with reflections |
| W5, the width of the error | Inch levels, with the range rounded outward and never landing shallower | None | Passability and within-one-level agreement |
| W6, deep water | C53's floor stays with sedans and SUVs (MS3b-Q7 a); vans and `unknown` read from geometry only; R143 gives a van's covered wheel a tire floor that refuses a shallower exact reading, even when step 3 drops the wheel (R158, the final review's I1) | 20 Commons photos in the cloud, 0 levels (§3). This is not the deep subset. | Development Set A photos whose alert gave tire or deeper, with their refusals by cause |
| W7, angles and small wheels | The 40 px rule and the 0.5 axis-ratio limit | Axis ratios of 0.880 to 0.994 on 6 side-on rims | Set B by angle and size |
| W8, splash and waves | The median water edge, and a refusal when the edge is ragged | None | The splash subset's coverage |
| W9, wet road as flood | Step 3's touch check (T = 5 px, touch share 0.25) | Step 3 dropped 6 dry references on one real photo and 2 on another, verified on an overlay (§4); `no_water_contact` 2 in each of 2 more photos | Development A-neg, with C326's false water |
| W14, vehicle type | Vans and `unknown` kept for geometry (C318) | None | Task 16 Step 5: the 19 Commons PUV photos |

**The Set C checks:** the flood photos (20 in the cloud, §3), the early rim check on the car photos (§5) and the PUV type check (not run, W14) are the three. Only the first two ran.

## 8. D4: effort, drawing and self-check

**Result: waits.** C312's run is Task 16, a Should task that waits for Rene's usage reading. The defaults stand:
- **Reasoning effort:** the default. No effort is sent, and the model picks its own level.
- **Drawing:** `boxes-v1`. The `boxes-v2` candidate is built (R145) but not adopted. Adopting it is a decision for labelled development photos after v0.7 (MS3b-Q8 a).
- **Self-check:** off and not built. C311's gate needs D1 green and photo to pin near 10 s, and D1 isn't green.
- **What Task 7 settled:** Meta's reasoning page, read at about 1:42 AM, lists `minimal`, `low`, `medium`, `high`, `xhigh` and `max` for Muse Spark. It refuses `none` with HTTP 400.

## 9. D5 and D6: tuning and the Manila check

**D5, waits.**
- The tuning change log has one entry, `tuning-v1`, with every value untuned.
- No Set A or A-neg photo or result was used, because the split hasn't happened. The ledger records no read of any `sealed` folder.
- The sweep, the event replay and guard 3 were not run (Task 13 is skipped, and Task 17 waits for the split, v0.7 and Set B). So there is no replay figure to put beside an in-sample one.
- ⚠️ **If T is ever tuned,** `rim_size_low` follows the synthetic hubcap's threshold at that T (R140). The 0.50 floor was derived at T = 5.

**D6, waits.**
- C313's counts, the no-water-mask share beside the probe's small samples, and C326's phrase comparison all need labelled development photos after the split and v0.7 (Task 14).
- Geometry stays on until C313 runs (MS3b-Q2's fallback).

## 10. D9: the backup method

**Result: waits.** C319's trigger is a Set B development result with under 70% of wheels measured, or a median error above 3 in. There are no Set B figures, so the trigger is neither fired nor cleared, and the visible-height backup isn't built. The early rim check (§5) is not a Set B result and doesn't count toward it.

## 11. D10: the evidence record sent to Window 4

Commit `cdfa11b` (2:16 AM). The tracker post went at 2:18 AM, with the field names, five wording differences from MS4's C518 and the dropped reference's level (M8). MS4's Task 14 took the record as built at 2:21 AM.

**`Evidence`:** `references` (the entries, in box-id order) and `water_outline`.

**`EvidenceEntry`**, in order: `id`, `kind` (`wheel`, `body` or `person`), `box`, `outline`, `landmark`, `level`, `level_from`, `inches`, `rim`, `rim_outline`, `waterline`, `used`, `deciding`, `dropped`, `rechecked`.

**`rim`** holds `centre`, `axes` and `angle_deg`.

- **No field is renamed.** The five wording differences:
  - C518 never names the entry list. It is `Evidence.references`.
  - `outline` is a tuple of polygons, since a mask can have several outer contours.
  - `rim`'s angle is `angle_deg`, in degrees as `cv2.fitEllipse` gives it.
  - `inches` is one unrounded `(min, max)` tuple.
  - `waterline` is `((x_first, y_w), (x_last, y_w))`, as floats.
- **M8:** a reference that step 3 dropped keeps its `level` in the record, with `used` false and `dropped` set. MS4 nulls that level (its C524).
- **What it never holds:** a face or plate outline, or Muse Spark's `reason`. It never reaches a log line, and MS3b stores none of it. It is `None` until Muse Spark's answer passes the schema and the id check.
- **One entry per numbered box** (R147): when a box holds two readings, the deciding one speaks for it. `used` means the reading entered the combine as one that could decide, so a `references_disagree` refusal can show `used` true with no level.
- **From Window 4's side:** dropped entries null `level`, `level_from` and `inches`, inches stay only on the deciding entry, and an empty `rim_outline` becomes null.

## 12. Spend

| Run | Meta calls | Tokens (billed) | Estimated cost |
|---|---|---|---|
| Offline search, positions 4 to 9 | 36 (SAM 30, Muse Spark 6) | 13,065 in, 15,148 out | about $0.156 |
| Smoke run, `--bound 180` | 40 (SAM 35, Muse Spark 5) | 12,747 in, 14,263 out | about $0.164 |
| C71 fallback, 15 photos | 120 (SAM 105, Muse Spark 15) | 35,640 in, 48,195 out | about $0.512 |
| Early rim check | 8 (SAM) | SAM is billed per image | about $0.02 |
| **MS3b total** | **204** | | **about $0.85** ($0.156 + $0.164 + $0.512 + $0.02) |

- **Window 3's total is about $1.05:** the C85 check (about $0.008) and MS3a Task 16 (about $0.194) came to about $0.20, and MS3b adds about $0.85.
- Task 11 cost about $0.83, over D1's estimate of about $0.50 and within the $30 development allocation.
- Until MS4's limits table is deployed (R154), each paid run's cost goes in the ledger and to the tracker, who folds it into the counter by hand.

## 13. The frozen values

These are the values as they stand today. They freeze with the prompt for the sealed run under `eval/rules.md` v0.7, item 10.1, which isn't applied (§14).

| What | Value |
|---|---|
| Tuning | `tuning-v1`, **untuned**: every value is at its start value. The list is in `tuning.py`. |
| Tire codes | `tire-codes-v1`, 12 codes |
| Reasoning effort | default (none sent) |
| Drawing | `boxes-v1` |
| SAM phrases (7) | `floodwater`, `wheel`, `wheel rim`, `person`, `vehicle`, `face`, `license plate` |
| Geometry default | `on`, the quoted literal `GEOMETRY_IN_LEVEL: "on"` in the template, applied by the Oct 30 deploy |

C309 sets the live default from the final ablation, after Set B's k and the tuning. That ablation hasn't run, so `on` is the starting default, kept until C313 runs.

## 14. What stays open

- ⚠️ **v0.7 isn't applied** (checked at 5:43 AM): `eval/rules.md` still says `DRAFT v0.6`, on `ms3b-geometry` and on `w4-independent`. So these wait for Rene and are recorded as pending on the progress board:
  - **MS3b-Q4** and v0.7 item 10.1's freeze items: the reasoning effort, the drawing version, the SAM phrases and MS3b's tuning values.
  - **MS3b-Q3**, the self-check's 10 s condition.
  - Until v0.7, no Set A or A-neg development result may be scored or shown (C322).
- ⚠️ **D1's cloud half** moves to the integrated deploy (R155). Until a real photo measures a wheel, geometry is on in the cloud but unproven there. At start values, check 9 refused 4 of 6 real rims (§5), so geometry will often leave the landmark reading in place until Set B calibrates it.
- ⚠️ **No deploy from `ms3b-geometry` or from `main` between MS4's Task 10a and its integrated Task 15** (R155, which the tracker extended at 6:11 AM, Oct 30). Neither template has MS4's limits table, routes or alarms until MS4 merges, so CloudFormation would delete them. Only MS4 deploys in that window.
- **Tasks 14, 16 and 17** wait for the split, v0.7, Set B and Rene's usage reading. Task 13 is skipped. Task 12b waits for MS4's deployed limits table, and its copy of the spend files waits for the sha of MS4 Task 8a's fix round (R151).
- **The final review** (Opus 5.5 at `xhigh`, after the security review found nothing at confidence 7 or above): one Important, I1, fixed before the merge (R158).
  - **What I1 was:** when step 3 dropped a van's or `unknown` vehicle's covered wheel, R143's floor was lost, so a shallower geometry level could publish where a sedan refuses.
  - **Still live in the cloud:** the bug stays in the deployed stack until MS4's integrated deploy (Task 15), under R155 as extended. It's rare there, since at start values check 9 refuses most real rims. Nobody uses the stack before Rene's QA on Nov 3, which runs on that deploy.
  - **M4 and M6 were fixed too** (R160): dev_eval's export refuses another export's leftover rows, and manifests need bare names.
- **For Rene (M5):** should each answered wheel of a van or `unknown` vehicle hold its sedan Table 8 row as a floor that never decides, as R143 does for a covered wheel? It would only ever add refusals. Claude recommends yes. Until he answers: no change (C318).
- **Carried into Task 13 or 17, whichever runs first (R159):** range checks on `Tuning` (C310's 0.50 and 1.55, k > 0), and a count of replays that end `pipeline_error`, with any such export refused.
- **Carried into Task 19's brief:** catch `InputError` on sealed crops and print a fixed message or the row number, never a cell. Wherever Task 19 reads a manifest through `parse_manifest`, it gets that function's bare-name check (M6). Any other ids or file names it reads need the same check.
- **Carried into Task 17:** the other tests in `test_prepare_boxes.py` still read the live 40 px and cap-of-6 constants, and the live-TUNING hubcap test runs at brightness 128 and score 0.9, so it should pass 255.0 and 1.0 before daylight or the rim score is tuned.

## 15. After the merge: Task 19 and Task 20 (Oct 30)

- **Task 19, the sealed-run entry point (D11).** `probes/run_sealed.py` is built and tested on synthetic data only, and it was never run on real sealed data. It:
  - reads only inside a `sealed` folder (MS2's guard, on the path as written and resolved)
  - starts only from Rene's console, after his confirmation, at the freeze tag
  - checks every label, and the harness's rules version against `--baseline`'s, before paying
  - pays once per photo and resumes as the same run, with a lock against a second window
  - retries a photo or item once on a Meta service failure (MS6E-Q6 (a)), and writes `service_retries`
  - exports only MS6's row fields
- **Its reviews:** one Opus 5.5 `xhigh` review (code and security) found 2 Important and 7 Minor issues, and none at confidence 7 or above. All were fixed. The combined review marked every one addressed. Ubuntu CI passed.
- **Task 20, M5 and M11** (Rene approved them under his delegation):
  - Every answered wheel of a van, `unknown` or pickup now holds its sedan row as a floor that never decides.
  - `tire-codes-v2` adds four Hilux codes and the Tamaraw AT's.
  - **Effects:**
    - `unknown`'s largest tire radius grows from 13.93 to 15.28 in, so its readings can land up to about 1.35 in deeper.
    - Check 9's lower bound for `unknown` loosens from 0.4883 to 0.4728.
    - Geometry-only wheels answered `rim_top` or `wheel_covered` can now only refuse, so van and `unknown` refusals may rise in development.
  - **Jeepney stays without codes (R170).** M11's one Fuso code, at 28.11 in, would read traditional, Hino and Isuzu jeepneys (29.6 to 32.2 in) too shallow.
- **For the freeze:** `tire-codes-v2` is a frozen value. Once v0.7 makes `RULES_VERSION` 0.7, `run_sealed` refuses a `--baseline` from a 0.6 development report, so the development report must be rerun on the freeze first.
- **Meta spend for these tasks:** $0.
- **Task 12b (laptop spend):** every laptop tool that calls Meta itself now reads MS4's counter before paying, and adds its cost after.
  - **Where:** `run_pipeline live`, `dev_eval run`, `set_b`, `set_b_masks`, `run_probe` and `run_sealed`.
  - **Before paying:** it refuses with exit 2 when the counter is unseeded, unreadable or at the stop.
  - **After paying:** a failed record prints `spend_error` and exits nonzero.
  - **To run it:** paid laptop runs need `--with "botocore[crt]==1.43.120"` under `aws login`.
  - **A limit to know:** the stop is checked once per run in each window. Concurrent runs can overshoot it by their combined cost.
- **Update to §14 (v0.7):** `eval/rules.md` v0.7 is approved and on `main` (`1138caf`, Oct 30), so MS3b-Q4 and item 10.1's freeze items are settled by its freeze list. MS3b-Q3 is moot, since the self-check is off and unbuilt. `run_eval.py --rules-version` prints 0.7, so the development report must be rerun under v0.7 before `run_sealed`.

