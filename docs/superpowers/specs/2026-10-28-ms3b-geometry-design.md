# MS3b Geometry: spec

- **Date:** Oct 28, 2026 (Manila)
- **Status:** Draft. Window 3 wrote it while waiting for MS1 to close, following the MS3b add-on prompt (git-ignored, in the handoff folder) and without a live conversation (D7, D15). An accuracy review and a builder check (both Opus 5.5 max) were folded in on Oct 28. Claude proceeds on the calls in §5, and on the defaults in §8, until Rene approves the whole spec.
- **Due:** Nov 1. The gated self-check is decided on Oct 31 (design §8, MS3 row).
- **Starts after MS3a merges into `main`.** It extends MS3a's pipeline modules, so it can't run beside them.
- **Implements:**
  - plan §4 (the must-have pipeline: reflection cut, rim-scale wheel geometry, person cross-check, conservative combining), §7 steps 2 to 6, §8 (rim scale and Tables 7 and 8), §9's level rule for inches, and §11's release gate and ablation
  - plan Table 11's W2 to W9 and Table 18's geometry rows
  - design §8's MS3 row (3b), G3, G4 and G5; `eval/rules.md` §1, §5, §6, §7 and §8
  - what the MS3a spec defers in its §5, and MS1's C34, C40 and C44
- **Needs from MS2:** the Set B generator and its G3 ground truth (design §8, MS2 row), and the Set A and A-neg development split. §8 says what happens if they are late.
- **Needs from MS6:** its scoring harness, `eval/scoring/` and `eval/run_eval.py --from-saved` (C321). MS6 holds the only implementation of `eval/rules.md` §7's metrics and §8's gate, outcome rule and guards.
- **Inputs from MS1's probe** (`docs/research/2026-10-28-ms1-probe-results.md`, on `ms1-meta` and in `main` once MS1 merges):
  - SAM never put water on a wheel (0.0 overlap on all 20 wheels), but a seam separates the two masks: a median of 2 to 3 px, reaching 4 to 5 px under splash.
  - SAM's water recall is weak: no water mask on 5 of 10 flooded STURM photos (night, rain, shallow water, a colour cast).
  - Level 3 photos give no wheel mask, so deep water leaves only the body and people.
  - Muse Spark took a median of 24.7 s per answer, and about 95% of its output was reasoning.

## 1. Intent

MS3a reads depth from landmarks: Muse Spark names where the water meets a wheel or a person, and Table 8 turns that into a level. MS3b adds the plan's precision method. Each tire code names its rim diameter, so measuring the rim in pixels gives pixels per inch, and the tire's known radius locates the road surface below the water. Code measures the depth in inches; no model outputs a number.

Geometry is a second, independent reading of a wheel. Where a wheel has both readings, the deeper one wins (G4). Geometry also lets vans and unknown light vehicles count, and it can drop a wheel whose two readings disagree, so it can change results either way. That is why the development ablation (C315) and the sealed run's outcome rule (`eval/rules.md` §8) watch underestimation, coverage and passability. Inches reach people only after the release gate (plan §11). MS3b also adds the reflection cut and W9's touch check, so every reading must come from a reference standing in water that SAM sees.

**Why it matters:** geometry with a release gate is a large part of the technical-depth story (plan §1, §19), and "Set B median error known" is MS3's finish line (design §8).

## 2. Goals, non-goals, anti-goals

**Goals**
- Steps 2 to 6 gain: rim linking, the reflection cut with the touch check, the geometry checks, rim-scale measurement over the type's tire codes, and combining with the level rule for inches.
- Set B's error on development cars, with and without the rim-edge calibration (G3).
- A development ablation, landmark alone against landmark plus geometry, by replaying saved model outputs.
- Every tuned cutoff set on development data, in one versioned place.
- The Oct 31 self-check decision, and Table 18's decision on dropping the geometry layer.

**Non-goals**
- Showing inches. The release gate decides after the sealed run (MS6).
- The overlay drawing (MS4) and clip mode (plan §4, a should-have).
- The visible-height backup method (plan §8), unless C319's trigger fires.
- The mirror check (plan §4, a nice-to-have).
- Geometry for pickups, jeepneys, tricycles, motorcycles and buses, until M11's sidewall photos confirm their sizes (plan §8, G5).
- Building the Set B generator or the G3 ground truth, which are MS2's.

**Anti-goals** (failures even if the code works)
- A reading lowered because SAM missed water. A reading dropped by step 3 can still refuse a photo, but it never lets a shallower reading win (C317).
- A cutoff tuned on sealed data, or chosen after seeing the sealed run.
- Inches shown before the release gate passes.
- A level that counts a reference with no water touching it.

## 3. Constraints

- Everything in the MS3a spec and `CLAUDE.md` still holds: the 9 levels and 3 classes, no "safe", "at this spot", the three outcomes kept apart, blur first, and pay once.
- **No new Meta call per photo.** Geometry uses masks the pipeline already requests (`wheel rim`, `wheel`, `floodwater`). The ablation replays saved outputs through MS3a's offline runner (B3). Set B scoring uses a development script that calls the same geometry code.
- **One scoring implementation (C321).** MS3b computes readings; MS6's harness computes every metric. MS3b never imports `eval/`, and `eval/` never imports `lusot_analysis`.
- **Development data only for tuning:** Set A and A-neg development photos after MS2's split, Set B development cars, and Set C. Never sealed data, and never Set B's final cars (`eval/rules.md` §4, C39, `CLAUDE.md`).
- **Cost:** Set B's roughly 20 development crops go through SAM's 3 phrases only, about $0.15. C312's effort test stays under $2.
- **Freeze:** every cutoff, the tire codes, the reasoning effort and `geometry_in_level`'s default are frozen before the sealed run (design §8, pipeline freeze).

## 4. What gets built, by pipeline step

### Step 2: rim linking (C300)
A rim joins the wheel whose box holds the centre of the rim's box. A rim inside no wheel box, or inside more than one, is dropped. A wheel with two linked rims gets no geometry, since choosing one would be a guess.

### Step 3: the reflection cut and the touch check (W4, W8, W9; C301 to C303, C317)
These run for every numbered wheel and person, and for every vehicle whose body gives its reading. They run **after Muse Spark's answer and the gate**, alongside MS3a's §3.3 drops, so numbering and C52's contradiction check are unchanged (C317).
- **The water edge (plan §7 step 3):** in each of the object's columns, the edge is the top row of the water component that touches the object's lower outline. Where SAM's object mask holds a reflection, water around the reflection reaches above the mask's lowest pixel, so the edge sits at the real waterline.
- **Touch (C301, C302):** water touches the object in a column when that water component comes within T px of the object's lowest pixel there. T starts at 5 px. A reference whose water touches fewer than a quarter of its lower-outline columns is dropped as `no_water_contact`. The lower-outline columns are those whose lowest object pixel lies in the bottom third of the object's box.
- **Waterline:** `y_w` is the median edge row across the touching columns. Object pixels below `y_w` are cut, so a reflection can't make a wheel look whole.
- **Ragged edge (C303):** a reference is dropped as `ragged_waterline` when the interquartile range of its edge rows exceeds 10% of the object's box height.
- **What a drop keeps (C317):** it removes the reading only.
  - A standing adult dropped here still blocks wading adults (C57).
  - A dropped wheel still counts as visible for C53.
  - If its reading is deeper than an exact level the kept readings give, the photo is refused as `references_disagree`, so a reading whose water SAM missed can never let a shallower one win. A floor result already means "this level or deeper" (C54, Rene's Q4), so a deeper dropped reading doesn't refuse it.

### Step 4: the geometry checks (C304, C305, C318)
A wheel gets a geometry reading only when all of these hold. Otherwise it keeps its landmark reading alone, and the cause is logged.
1. Muse Spark answered the wheel with a waterline other than `not_visible` (C318).
2. Its vehicle was kept, and its type has tire codes (C304).
3. It has exactly one linked rim (C300).
4. The photo's brightness meets the daylight cutoff, which is tuned under C310 and starts at 80 (C305; plan §8 trusts geometry only in daylight).
5. The rim's SAM score is at least the tuned cutoff, which starts at 0.5.
6. The rim fit (step 5) uses at least 5 contour points above the waterline, and its centre lies inside the wheel's box.
7. The fit's axis ratio, minor over major, is at least 0.5 (plan §8).
8. The water is at or below the hub: `y_w` is at or below the fit's centre row, so at least half the rim arc shows (plan §8).
9. The rim's size fits the wheel (C305). The fit's horizontal extent over the wheel box's width must lie between 0.85 times the smallest and 1.15 times the largest ratio the type's codes give at the fit's viewing angle: `rim × cos φ ÷ (D × cos φ + W × sin φ)`, where D is the tire's diameter, W its section width in inches, and `cos φ` the fit's axis ratio. Seen at an angle, a wheel's box also takes in the visible tread, which this ratio allows for. A hubcap or a whole-wheel mask fails it.

The plan's first check, a wheel at least 40 px tall, is MS3a's C56 rule, applied before numbering.

### Step 5: rim-scale measurement (plan §8; G3, G4)
- **The fit:** `cv2.fitEllipse` runs on the rim mask's outer contour points above `y_w − T`, so the straight cut edge isn't fitted. `r` is half the longer axis, and `c` is the centre's row.
- **The formula, for each tire code of the type:** with k the rim-edge factor (G3; 1.0 until calibrated),
  - `s = r ÷ (k × rim ÷ 2)` pixels per inch
  - `R = rim ÷ 2 + width × aspect ÷ 100 ÷ 25.4`, the tire radius in inches
  - `depth = (c + R × s − y_w) ÷ s`, in inches
- **The result:** `depthInMin` and `depthInMax` over the type's codes, an envelope over tire sizes, not a confidence interval. The level comes from `eval/rules.md` §1's level rule applied to `depthInMax`, so it rounds deeper.
- **A failed fit (C306):** a depth of 0 or less on any code drops the geometry reading for that wheel. Check 8 already keeps every depth at or below the tire's radius.
- **One wheel with both readings (G4, plan §7 step 5):** the deeper level is kept. Readings more than one level apart drop the wheel as `wheel_methods_disagree`.
- **Vans and `unknown`** are kept for geometry, which narrows MS3a's type drop (C45, C318). Their wheels give geometry readings only, since Table 8's wheel rows don't cover them. Sedans and SUVs get both readings.

**Tire codes (C304)**, from plan Table 7 and G5. They live in one versioned data file inside the package, with their sources.

| Type | Codes | Diameters (in) |
|---|---|---|
| `sedan_hatch` | 175/65R14 (Wigo), 185/55R15 (Mirage G4), 185/60R15 and 195/55R16 (Vios) | 23.0 to 24.4 |
| `suv_mpv` | 205/55R16 and 205/55R17 (Xpander), 185/65R15 and 195/60R16 (Avanza), 205/65R16 (Raize and Innova), 205/60R17 (Raize), 215/55R17 (Innova) | 24.5 to 26.7 |
| `van` | 215/70R16C (Hiace) | 27.9 |
| `unknown` | every code above | 23.0 to 27.9 |
| `pickup`, `jeepney`, `tricycle`, `motorcycle`, `bus_truck` | none until M11's sidewall photos | none |

The Tamaraw stays out of `van` until a sidewall photo confirms its size, because G5 found it in one secondary source only. A Hilux (30.5 in) that Muse Spark calls `unknown` would read too shallow, so W14's development confusion matrix checks pickups (G5).

### Step 6: combining (extends MS3a's combine)
- A wheel's reading is its kept reading from G4. Geometry readings are exact, never floors. A vehicle still reads from its deepest wheel (C43), or from its body's floor when the wheels are hidden (C53).
- C54's disagreement test and tie order are unchanged. A reading dropped by step 3 that is deeper than an exact result refuses the photo (C317).
- **Inches with the result (C307):** `depthInMin` and `depthInMax` go with a result only when the deciding reference's level came from geometry. When a wheel's landmark and geometry readings give the same level, the level counts as coming from geometry. A level set by a landmark alone or by a person carries no inches.

### Storage, API and settings
- **The item (C308, C320):**
  - `depthInMin` and `depthInMax` are stored when C307 publishes them, rounded outward to 0.1 in (min down, max up). The level always comes from the unrounded value, so a rebuild from the stored values never lands shallower.
  - `levelFrom` (`landmark` or `geometry`) is stored on every level result. `landmark` keeps Muse Spark's category, so a wheel read at `hub` whose geometry gives knee stores `landmark: hub`, `level: knee` and `levelFrom: geometry`.
  - `GET /reports/{id}` returns none of the three in MS3b. MS6 adds the inches if the release gate passes, and MS5 words `levelFrom` (M20).
- **Geometry in the level path (C309):** one setting, `geometry_in_level`, chooses between the two configurations `eval/rules.md` §8 names in advance. It is an environment variable on the analysis Lambda, and a flag on the offline runner.
  - **Off** means MS3a's landmark rules plus step 3: vans and `unknown` are dropped as in 3a, and no geometry is computed. "Landmark alone" is then the same configuration in the development and sealed runs.
  - **Its live default** comes from the development ablation (C315): the outcome rule that MS6's harness computes on the development rows, labelled as development data. It is on unless development underestimation rises, coverage falls by more than 10 points, or passability agreement falls by more than 5 points.
  - After the sealed run, §8's outcome rule sets it.
- **Logs (C316):** per report, the geometry check failures by cause, the number of wheels measured, the tuning version, k and the reasoning effort. Inches are numbers, not private data, so they may be logged. Masks are never logged.

## 5. Decisions (Claude's calls)

| # | Call | Why |
|---|---|---|
| C300 | A rim joins the wheel whose box holds its centre. None or several → the rim is dropped. A wheel with two rims gets no geometry. | Plan §7 step 2 links rims to wheels. Choosing between two would be a guess (as in C55). |
| C301 | T, the touch tolerance, starts at 5 px and is tuned on development photos. | The probe's seam has a median of 2 to 3 px and reaches 4 to 5 px under splash. Without a tolerance, no water ever touches. |
| C302 | A reference needs water touching at least a quarter of its lower-outline columns, or it is dropped as `no_water_contact`. Lower-outline columns are those whose lowest object pixel sits in the bottom third of the box. | W9 asks for water touching each reference, and plan §7 step 3 counts water at the lower outline. Counting all columns would penalise a raised arm or an umbrella. The share is tuned on development photos. |
| C303 *(start value lowered by the plan review)* | A waterline is ragged when its IQR exceeds 10% of the object's box height, and that reference is dropped. | Plan §7 step 3 drops ragged edges with a tuned cutoff. A share of the object's height works at every photo size. The plan writer's synthetic cases put flat waterlines at 0 to 1.5%, and a reflection over a hole in SAM's water mask at 12.3 to 13.8%, which 15% let through to a reading 2 or 3 levels shallow on a van. |
| C304 | Tire codes per type as in the §4 table. `unknown` runs every code. Vans get geometry only. The other types get none until M11. | Plan §8 and Table 7 give the ranges (sedan_hatch 23 to 24.5 in, suv_mpv 24.5 to 27, van 27 to 28, unknown 23 to 28), and G5 keeps pickups out. One data file keeps the codes checkable and frozen. |
| C305 | The geometry checks in §4 step 4: the plan's four, plus a daylight brightness cutoff (starting at 80, tuned), at least 5 points for the fit, a fit centre inside the wheel box, and a rim size that fits the wheel (check 9). The rim score cutoff starts at 0.5. | Plan §8 trusts geometry only where Set B tested it: daylight, roughly side-on, wheels at least 40 px. C44's quality cutoff refuses only the darkest photos. `fitEllipse` needs at least 5 points, and a centre outside the wheel means the rim isn't this wheel's. A hubcap or a whole-wheel mask gives the wrong scale and a shallow reading, and the tire codes fix how much of the wheel a rim can fill. |
| C306 | A depth of 0 or less on any code is a failed fit and drops the geometry reading. | The touch check already proves water at the wheel, so such a result can only come from a bad fit. |
| C307 | Inches go with a result only when its deciding reference's level came from geometry. Equal landmark and geometry levels on one wheel count as geometry. C54's tie order is unchanged. | Otherwise a shallower range would sit beside a deeper level, and the pin would contradict itself. |
| C308 | The item stores `depthInMin` and `depthInMax`, rounded outward to 0.1 in. The level comes from the unrounded value. The API returns neither until the release gate passes. | Plan Table 14 defines the fields, and §11 gates their display. Rounding outward keeps `--from-saved` rebuilds from landing shallower (`eval/rules.md` §10). |
| C309 | One setting, `geometry_in_level`. Off means MS3a's rules plus step 3. Its live default comes from the development ablation, under all three of `eval/rules.md` §8's guards. | §8 names both configurations in advance. A setting switches them without a code change after the freeze. G4 drops and geometry-only vans can move results either way, so all three guards apply. |
| C310 | **Tuning:** every cutoff lives in one versioned tuning module with a change log. Each is chosen on development data by a rule written down before its results are seen:<ul><li>**Quality (C44) and daylight (C305):** the highest cutoffs that refuse no development photo which otherwise reads within one level of its label.</li><li>**T, the touch share, the IQR share and the rim score:** the values with the best within-one-level agreement on development Set A, with no rise in development underestimation and no more than 10 points' cost in coverage. Ties go to the stricter value.</li><li>**k:** the median ratio of the visible rim edge to the nominal rim diameter on Set B development cars (G3).</li><li>**Check 9's 0.85 and 1.15 factors:** lowered or raised only as far as needed to pass every Set B development rim, since a rim recessed behind the sidewall shows less of its width at steep angles.</li><li>**C70's caps and C56's 40 px:** checked on the first Manila development photos (P2, P6).</li><li>**Without labelled development photos (MS3b-Q2's fallback):** the start values stay, marked untuned, until a tuning window before the freeze.</li></ul> | Plan §7 and design §8 tune on development data only, and plan §11 leads with underestimation. Rules fixed in advance keep the tuning honest. |
| C311 | **The self-check, in two steps** (plan §4, Table 18, `eval/rules.md` §8):<ul><li>**Oct 31, the build gate:** it is built only if the core and the rim geometry are solid: MS3a merged, and D1 and D3 green. If yes, it is built by Nov 1 with its own development ablation.</li><li>**By Nov 1, the turn-off check:** it is turned off if its own ablation shows no gain, or if photo to pin, with the self-check on, takes over 10 s.</li></ul> | Plan §4 gates the build, and Table 18 gives the later turn-off signs. At the probe's median of 24.7 s for Muse Spark, the core alone is over 10 s, so §8's rule as written would turn it off. MS3b-Q3 puts that to Rene. |
| C312 | **Reasoning effort, if time allows before Oct 31:** compare Muse Spark's default, `low` and `minimal` effort on about 10 development photos, for landmark agreement and latency, under $2. A lower effort is kept only if its landmark agreement is no worse. Without labelled photos, it is compared with the default effort's own answers instead. The effort is logged with the prompt version and frozen (MS3b-Q4). | The probe found 95% of the output was reasoning, and Meta documents `reasoning.effort`. It decides C311's latency and MS5's speed. It changes model outputs, so it must be set before the freeze. |
| C313 | **Dropping the geometry layer (Table 18, C40), on the Manila check (C34):** development Set A photos after MS2's split, or consented photos.<ul><li>**This changes C40's count.** C40 passes a photo when water reaches each submerged wheel, and R72 fails a photo with no water mask. C313 counts wheels instead, and leaves out wheels with no water mask within 30 px.</li><li>A wheel passes when water lies within 5 px along at least a quarter of its lower edge (as C302) and covers under 10% of it.</li><li>Geometry is dropped when fewer than half the counted wheels pass.</li><li>The same check reports the share of flooded photos with no water mask at all. That is the figure Rene asked to revisit Q1 (C51) with.</li></ul> | Table 18's trigger is SAM failing to separate water from wheels. The probe shows separation holds (0.0 overlap) while recall is weak. On the STURM photos, C40 passes 3 of 10 photos while 5 of 5 counted wheels pass, so C40's count would drop geometry for recall, which C51 and C302 already handle. Rene can overrule. |
| C314 | **Set B scoring:** a development-only script measures Set B's development crops twice (plan Table 12): with SAM's masks, and with the known waterline fed straight to the geometry. Per crop it writes MS6's row (C321): the variants `geometry` and `geometry_uncalibrated` (SAM's waterline, with and without k), and `known_waterline` and `known_waterline_uncalibrated`, each with the point estimate from the true tire code (`depthInPoint`, Table 13), the envelope, or the failed check's cause, plus the angle and size bins (W7). MS6's harness reports the median and worst error, the envelope coverage and the share measured, by vehicle type (W2) and by bin. MS2 builds the generator and the G3 truth. If SAM finds no composited water, the known-waterline runs still measure the geometry alone, and the report gives SAM's share. | This is MS3's finish line, "Set B median error known". Two runs separate SAM's waterline error from the geometry's own. |
| C315 | **The development ablation:** landmark alone against landmark plus geometry, by replaying the same saved outputs with no extra Meta call. MS3b's export writes MS6's rows per photo, with the outcomes `landmark` and `geometry` (C321), and MS6's harness reports `eval/rules.md` §7's metrics, with the subsets for W4, W6 and W8, on development Set A, and the false flood rate (W9) on development A-neg, each with its n. | Geometry is pure code on saved masks, so both configurations come from one paid run, the same ablation the sealed run reports. |
| C316 | Logs add the geometry check failures by cause, the wheels measured, the tuning version, k and the reasoning effort. No masks. | Plan §19's logging, and the record that C310's tuning needs. |
| C317 *(made strict by the plan review)* | **Step 3 runs after the gate, with MS3a's other drops,** and removes only the reading. A standing adult dropped there still blocks wading adults. A dropped wheel still counts as visible. A dropped reading deeper than an exact level the kept readings give refuses the photo as `references_disagree`. A floor result stands, since it already means "this level or deeper". Readings of a vehicle that C43 or C53 drops play no part. | Running before numbering would hide waterlines from C52's check and turn some `water_unsure` refusals into "no flood seen" when SAM misses water. And a deep reading whose water SAM missed must not let a shallower one win. A refusal beats a guess. |
| C318 | Geometry reads only wheels Muse Spark answered with a waterline other than `not_visible`. Vans and `unknown` are kept for geometry, which narrows MS3a's C45 type drop for those two types. | C76 gives unanswered boxes no reading. A visible waterline confirms the water at that wheel, and gives every sedan or SUV wheel G4's cross-check. |
| C319 | **The visible-height backup (Table 18's "rim fit unstable"):** its trigger is a Set B development result below the release gate's targets: under 70% of wheels measured, or a median error above 3 in. If it fires, the backup is built only if it fits before the freeze. Otherwise the results note records it. | Table 18 names the sign but no threshold. The gate's own targets are the ones geometry must meet anyway. |
| C320 | `landmark` keeps Muse Spark's category, even when geometry sets the level. `levelFrom` records which one did. MS3b's API returns neither new field. | C49 ties `landmark` to the deciding reference's answer, which stays true. MS5's wording and Rene's copy review (M20) decide how a geometry level is shown. |
| C321 *(agreed with Window 4, MS6's spec)* | **One scoring implementation.** MS6's harness (`eval/scoring/`, `eval/run_eval.py`, standard library only) computes every metric, the gate, the outcome rule and the report. MS3b's export function in `backend/analysis` turns a saved run into MS6's rows and writes them to a private folder under `LUSOT_DATA_DIR`, then runs `python eval/run_eval.py --from-saved --results <dir> --write`. MS6's later sealed-run entry point reuses the export. If the harness isn't on `main` when D2 and D7 run, MS3b writes the rows and records both as waiting for it. | Two implementations of the metrics could drift, and the sealed run must score exactly as the development runs did. No imports either way keeps the two packages apart. |

## 6. Done when

| # | Check | Evidence |
|---|---|---|
| D1 | Steps 2 to 6 run with geometry, on the laptop and in the cloud | Unit tests, plus one cloud smoke photo with a geometry reading (STURM, or a consented photo). The offline runner and the handler agree on a replayed run (B3). |
| D2 | Set B median error known (design §8) | MS6's harness report on C314's rows, with each n |
| D3 | Rules tested | Unit tests for: rim linking (C300); the touch check, cut and raggedness on synthetic masks, including a wheel whose mask holds its mirrored reflection (`y_w` within 2 px of the true line) and the seam; C317's effects; the formula on hand-computed Table 7 examples; each geometry check; the envelope; G4's deeper reading and its drop; C306, C307 and C308's rounding; `geometry_in_level` off matching 3a's results plus step 3; and an API that never returns inches |
| D4 | Self-check decided | Oct 31's build-gate entry and, if built, the Nov 1 turn-off check (C311), with the figures |
| D5 | Tuned on development data only | The tuning module's change log, with each value's development evidence or an "untuned" mark. Nothing under a `sealed` folder was opened. |
| D6 | Geometry layer kept or dropped | C313's counts from the Manila check, with the decision and the no-water-mask share for Q1 |
| D7 | Ablation reported | MS6's harness report on C315's rows, with coverage beside every rate |
| D8 | Weaknesses checked as Table 11 asks | Development results, called indicative, for: W2 (Set B by type), W3 (the ablation and G4 drops), W4 (the reflection test, and development photos with reflections), W5 (passability and within-one-level agreement), W6 (development photos at tire depth or deeper), W7 (Set B by angle and size), W8 (the splash subset's coverage), W9 (development A-neg). Headline numbers wait for the sealed run (MS6). |
| D9 | Backup method decided | C319's trigger checked on D2's figures and recorded |

## 7. Left to the builder

- The contour extraction and point filtering for `fitEllipse`.
- File names inside `pipeline/`, and the tuning module's format.
- How the Set B script reads MS2's generator output.
- Which development photos form the splash and reflection subsets, marked before the ablation runs.
- Test cases beyond D3's list.

## 8. Questions for Rene

Each has a default that the draft plan follows (D7).

| # | Question | Options | Default (recommended) |
|---|---|---|---|
| MS3b-Q1 | **Set B photos (M10).** "Set B median error known" needs development cars with known tire codes, and M10 hasn't started. Can you photograph at least 3 parked cars side-on in daylight, with their sidewall codes, by Oct 30? Set B's final cars stay apart, in `set_b\sealed\` (C39). | (a) Yes, by Oct 30. (b) Later: D2 slips past Nov 1, and the release gate can't pass until it's done. | (a). If no photos arrive by Oct 31, (b) applies and the results note says so. |
| MS3b-Q2 | **Labelled development photos.** C310's tuning and C313's check need Set A development photos after MS2's split (M7: 0 rows so far), or consented photos (M9). | (a) The split happens by Oct 30. (b) The cutoffs keep their start values, marked untuned, until a tuning window before the freeze, and C313 waits for the first Manila development photos. | (a). Otherwise (b), with geometry kept until C313 runs. |
| MS3b-Q3 | **The self-check's 10 s condition** (`eval/rules.md` §8). The core alone takes about 25 s at Muse Spark's default effort, so the rule as written turns the self-check off. | (a) Keep the rule: the self-check is built only if C312's lower effort brings photo to pin near 10 s. (b) Change the condition to "adds no more than 5 s to photo to pin", which needs your written OK in `eval/rules.md`'s change log. It keeps plan §25's Meta-tooling item in play. | (a). It protects the Nov 1 date, and the core's speed is MS5's real problem. |
| MS3b-Q4 | **Freezing the reasoning effort.** If C312 changes the effort, it changes model outputs, so the sealed run should freeze it with the prompt version. `eval/rules.md` §10's frozen list doesn't name it, and a change there needs your written OK. | (a) Add "Muse Spark's reasoning effort" to §10's list. (b) Leave §10 as it is, and record the effort in the run's log only. | (a). |
