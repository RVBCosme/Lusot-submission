# Evaluation rules

- **Status:** v0.9 (Nov 2, 2026), approved under Rene's written delegation. v0.9 adds two rules to §6, a person too small in the photo (C92) and a "no" over wide water (C93), with tuning-v2's two values beside them, for Rene's confirmation on Nov 2, all in the change log. v0.8 (Nov 1, 2026) added one exception to §6, an adult's ankle (C91), with his written OK in the change log. v0.7 (Oct 30, 2026) was written from plan §9 and §11 (as updated Oct 27), real alert wording and two builder checks. v0.7 applies the proposal in `docs/drafts/eval-rules-v0.7-proposal.md`. Rene approved the whole file on Oct 30, 2026, before any Set A result was seen, except §8's numbers and the guards marked **[Rene, with M18 by Nov 2]**, which stay his.
- **Freeze rule:** every rule here is set **before** testing (plan §9, §11). Once Rene approves this file, any change needs his written OK in the change log at the bottom. After the sealed run, the scoring rules don't change at all; §10 covers fixes and the one disclosed rerun.

Items marked **[Rene]** are judgment calls that only Rene can make. Every other rule is copied from the plan, or from the source it cites. Every item that v0.1 to v0.6 marked Proposed was approved with v0.7, except §8's numbers and guards, which stay with Rene and M18 by Nov 2.

## 1. The level scale (9 ordered levels)

A depth `d` in inches takes the shallowest level whose upper limit is at or above it, so every in-between reading rounds deeper (plan §9). That rounding is Lusot's rule, not MMDA's.

| Index | Level | Upper limit (in) | Passability class |
|---|---|---|---|
| 0 | below_gutter | d ≤ 5 | PATV |
| 1 | gutter | d ≤ 8 | PATV |
| 2 | half_knee | d ≤ 10 | PATV |
| 3 | half_tire | d ≤ 13 | NPLV |
| 4 | knee | d ≤ 19 | NPLV |
| 5 | tire | d ≤ 26 | NPATV |
| 6 | waist | d ≤ 37 | NPATV |
| 7 | chest | d ≤ 45 | NPATV |
| 8 | above_chest | d > 45 | NPATV |

Classes: PATV is passable to all vehicles, NPLV is not passable to light vehicles, NPATV is not passable to any vehicle. People on foot get the level only, never a class (plan §9).

## 2. Mapping MMDA and city labels to the scale (ground truth)

| Label as written in the alert | Level |
|---|---|
| gutter deep | gutter |
| half-knee deep | half_knee |
| half-tire deep | half_tire |
| knee deep | knee |
| tire deep | tire |
| waist deep | waist |
| chest deep | chest |
| half gutter deep (off-scale) | below_gutter |
| above gutter level (off-scale) | half_knee |
| above knee level (off-scale) | tire |
| "lagpas tao" (over a person's head) | above_chest |
| "head" (as in Quezon City's "Head+") | above_chest |

- Spelling and case variants of the same words map the same way, for example "half knee", "half-knee", "Half Gutter", "gutter-deep" and "above gutter deep".
- Any phrase may end with `deep` or `level`, or with neither: the two words are interchangeable, as "above gutter deep" beside "above gutter level" shows. Real alerts write "half tire level".
- **Labels given in inches** (real MMDA alerts do this; see `docs/research/2026-10-26-alert-index.md`):
  - **Words win.** When an alert gives both words and inches ("Gutter deep, 8""), the words decide the level.
  - When a label's words aren't one of these phrases but it gives a depth in inches or centimetres, the depth decides by the level rule. Quezon City's "ANKLE DEEP (9 inches)" reads half-knee. Words alone that aren't a phrase, such as "Ankle Deep", stay unmapped, and so does a label whose words also hold a number without a unit or a status such as "subsided".
  - **A single number** ("10"", "12"", "37 inches") takes its level from the level rule in §1.
  - A number written without a unit (such as "25") is unmapped.
  - A + after a number, or after its unit, means at least that depth, and maps only when that is deeper than 45 in (above chest). A + anywhere else, as in "Waist+", also means at least, so the label is excluded as unmapped unless it reads above chest.
  - A **range** ("13-18 inches") takes the level of its **upper** value. That matches Lusot's round-deeper rule and keeps the underestimation measure strict.
  - A range may carry a unit on each number (13"-18"). Two measures not joined by a range word, such as "24 in (61 cm)", give one depth in two units: the label takes that level when both units give the same level, and is unmapped when they don't.
  - Centimetres are converted at 2.54 cm per inch first.
- **Statuses that are not depths**, such as "subsided", can't match a photo. As a photo's own label, a status gives "no matching alert". Among a photo's other matching alerts, it is ignored.
- **Any other label is excluded and logged with the reason "unmapped label".** It is never guessed. A new mapping may be added only before the sealed run, with Rene's OK.
- A passability phrase that maps to no class leaves the photo out of the passability metric only, and is logged. A photo whose alert gives neither a depth nor a class is excluded as "unmapped label".

**Passability ground truth** is the class stated in the alert. It is scored separately from the level, because MMDA's field passability sometimes differs from the gauge table (plan §9). For example, "Waist Deep, 37"" has been marked *not passable to light vehicles*.

| Passability as written | Class |
|---|---|
| PATV, passable to all (types of) vehicles, passable to light vehicles | PATV |
| NPLV, not passable to light vehicles, not passable to motorcycles and cars (sedan) | NPLV |
| NPATV, not passable to all (types of) vehicles, not passable to any vehicle | NPATV |

If an alert states no class, the photo is left out of the passability metric only, not out of the level metrics. Likewise, a passability-only alert counts for passability only. The report gives every count.

## 3. Matching a photo to an alert (Set A)

- **Source:** Set A uses only photos that MMDA or a city government posted itself. A city government's own official office pages count as the city, such as its disaster risk reduction and management office or its public information office. News-outlet photos are never used; news lists only help find the official posts (plan §11, Table 25, M7).
- **Labels printed on the image** (alert cards, banners, burned-in captions) would let the model read the answer. Rene crops them off at collection when the reference stays in frame (`label_in_image` = `cropped`). A photo whose depth or passability words are still visible is excluded (§9).
- **Same post:** a photo inside the same MMDA or city post as the alert is matched by construction.
- **Separate posts:** a government-posted photo must show the **same named spot** as the alert, meaning the same street plus cross street or landmark, and its time must be within **30 minutes** of the alert time. The alert's time is the time its text gives, or else its post's time (MS2's C209).
- "Same spot" compares normalised spot text (C203's normalisation), which gives each spot its names, such as a street, its cross street or a landmark. The photo's and the alert's spots match when they share at least two names that aren't marked. A barangay's, a zone's or a Manila district's name is marked, and never counts toward the same spot. One shared name is never enough, even when it is each spot's only name (MS2's C224, as S-R9 ruled).
- If a photo matches several alerts, the log gives the nearest one's labels, and the others' level labels as written (MS2's C209). If any two of them differ by more than one level, the photo is excluded ("conflicting alerts"). An unmapped label among the others makes a conflict impossible to rule out, so it excludes the photo as "unmapped label". An empty one, from an alert that gave only a class, is ignored.
- Only Metro Manila photos count.

## 4. Flood events and splits

- **Flood event:** the same place on the same calendar day (Manila time). "Same place" means the same named spot, or spots within 300 m of each other. The log has no coordinates, so the split stands in for distance with the text rule below and Rene's `same_spot_as` links (MS2's C203).
  - Two rows of one set join one event when they share a date and a name of one is the same as a name of the other, or sits whole inside it as a run of words: edsa joins edsa kamuning, but edsa kamuning doesn't join edsa ortigas. That holds whatever their city, and marked names count here. Two rows with no names join. Rows also join, whatever their dates, when Rene links them in `same_spot_as`, or when the split finds their photos identical or near-identical (MS2's C203, as S-R9 ruled).
- **Set A** is split **by event, not by photo**: about 30 photos for development and about 20 sealed, so no event appears in both (W18).
  - The split script assigns whole events with a seeded random draw. The seed is recorded below.
  - It writes the sealed rows into a write-once encrypted archive (M19), one per sealing step: Set A and A-neg, Set B's final cars, and Set D if it rains (MS2's C205). Agents only ever see development rows.
  - The seed is fixed in the code. The split runs once, and rows logged after it are never used (MS2's C204).
  - **The split is stratified by passability.** The walk runs separately for two groups of events, with the same seed and the same shares: events with any NPLV or NPATV row (by §2's passability table), and the rest. In a group with 2 or more events, each side gets at least one.
  - The shares are by whole events, with a cap. Within a group, events sorted by id are shuffled with `random.Random(seed)`. Walking that order, an event goes to sealed only if the group's sealed side would then hold at most 45% of the group's rows (A-neg: 40%), and the walk ends once it holds 40% (A-neg: a third). If the cap would leave a side empty, the group's smallest event goes there, and the record says so (MS2's C204).
- **A-neg:** about 10 for development and 5 sealed, split the same way.
  - A-neg comes from Wikimedia Commons: openly licensed photos (CC0, public domain or CC BY, never CC BY-SA) of non-flooded wet or dry Metro Manila streets, from at least 5 places over at least 2 days, about 15 photos in all.
  - A script downloads the photos unopened, and no Claude opens one before the split. Rene fills the look-only columns (`reference_visible`, `label_in_image` and `faces_or_plates`, and `surface` when the file page doesn't say; MS2's C209) and reviews the list of files and licences before the split.
  - The report states this source in its A-neg section, and each photo's credit stays in the private manifest.
- **Set B:** split by car photo, so development and final never share a car. **The final cars are sealed like Set A.**
  - Their photos are kept apart.
  - Cars are numbered in the order Rene photographs them: odd numbers are development cars, even numbers final (MS2's C210).
  - The final-car run is two Rene-only commands: `set_b_masks --final`, then `generate --final`. Before writing anything, `generate --final` stops if a final car shares an id, an identical photo or a near-identical photo with the development side. Crops and truth never exist in plaintext: the generator and the G3 ground truth write straight into the encrypted archive. Only Rene's photos and the masks sit in `set_b\sealed\` until the archive is tested (MS2's C214).
  - The generator is built and debugged on development cars only.
- **Set C** is development only and never counts toward headline numbers.
- **Set D** (only if it rains) is final only, never tuned on, and reported apart from Set B (plan Table 12).
- **Validation is event replay, when tuning runs.** Development data has two uses when tuning runs (MS3b's C310). All of it tunes. Then, as validation, each development flood event is scored with C310's settings chosen on the other events, by replaying the saved model outputs, with no new Meta call. Reports show the replay figures beside the in-sample ones. If the replay's within-one agreement falls 3 or more photos below the in-sample figure, the cutoffs go back to their start values, marked untuned, and the tuning change log says why. If tuning doesn't run, the cutoffs keep their start values, marked untuned, and the report says so.
- Split seed: `20261030`. Split date: `TBD`.

## 5. Ground truth for Set B (gap fix G3)

- Scale comes from the **whole tire** in each dry photo: ground contact to tread top, with the overall diameter taken from the tire code (formula from Table 7). It is **not** taken from the rim.
- Each synthetic waterline's true depth (in inches) uses that scale.
- The ratio between the visible rim edge and the nominal rim size is measured on **development cars only**. Geometry error is reported both without and with that calibration.
- **Crops (MS2's C211).** Four per car photo, one in each depth band below the hub: 1 to 5 in (below_gutter), 5 to 8 (gutter), 8 to 10 (half_knee), and 10 in to the lower of 13 in and 0.5 in below the hub (half_tire). Each depth is drawn evenly within its band. Two of the four, drawn at random, are shrunk so the smaller chosen wheel (at most the two largest wheels in the largest vehicle box; MS2's C212) is 50 to 80 px tall. The others stay at the app's 1,600 px.
- **Truth (MS2's C212).** The scale is the dry `wheel` mask's height over the tire code's overall diameter (Table 7's formula). The waterline row is the ground row minus depth times scale, and the truth comes from the row actually drawn.

## 6. Reading rules that scoring must respect (plan §7 to §9, gap fix G4)

- Landmark readings follow Table 8 exactly as written.
  - **Except an adult's ankle (C91, v0.8):** it gives no reading, so it never sets a level. The photo's other references decide, or the photo is refused. It also no longer counts toward a disagreement: an ankle adult beside a knee-deep adult reads knee, where it used to refuse. A "no" on standing water with an ankle adult still gives no flood seen (C52 is unchanged), unless C93's water share applies.
  - Hub = half_tire, MMDA's own definition, even where a large tire's hub sits slightly above 13 in.
  - Tire only = below_gutter.
- **In-between waterlines.** When the water sits between two marks, the reading takes the higher mark, for wheels, people and car bodies alike. Table 5 says so for wheels; prompt v1 and our own M8 labels follow the same convention. A photo that shows no street is unusable.
- Geometry inches follow the level rule in §1.
- When one wheel has both a landmark and a geometry reading, the deeper one is kept. A wheel whose two readings are more than one level apart is dropped.
- Across references, Lusot keeps the deepest believable reading and refuses when references disagree by more than one level.
  - **Floors (Rene, Oct 28):**
    - A floor ("at least" a level, such as covered wheels) means that level or deeper, so it never disagrees with a deeper reading.
    - The photo is refused when an exact reading sits more than one level below the deepest reading, with a floor counted at its own level there.
    - So "at least tire" beside a chest-deep adult gives chest, while "at least tire" beside an exact half_tire refuses.
  - **The gutter gap (Rene, Oct 28: kept):** landmarks never read `gutter`, so `tire_only` beside `rim_quarter` (and `ankle` beside `mid_shin`) is two levels apart, and the photo is refused.
    - **Since C91 (v0.8):** an adult's `ankle` gives no reading, so the people pair no longer arises.
- **People count fully (Rene, Oct 27, D13):**
  - A standing adult can set the level alone, through Table 8's body rows, except at ankle depth (C91, v0.8).
  - **Except a person too small to read (C92, v0.9):** a person whose box's longer side is under tuning-v2's 60 px, in the image SAM sees (at most 1,600 px on its longer side), never sets the level and blocks no one (`person_small`). Its reading still refuses the photo when it is deeper than the result, as a reading step 3 dropped does (C317): a small box can be an adult deep in the water. A shallower one changes nothing.
  - With wheels in the photo too, the rules above apply: deepest believable reading, and refusal when readings differ by more than one level.
  - Wading adults count only when no adult in the photo is standing still. That includes a standing adult whose waterline is hidden (Rene, Oct 28).
- **A "no" over wide water (C93, v0.9):** when Muse Spark answers no standing water but SAM's water covers more than tuning-v2's 0.25 of the image's lower half, the photo is refused as `water_unsure` instead of "no flood seen". Below that share, SAM's water still never overrides a clear no (C51).
- **"At least tire deep"** (wheels covered, with the body waterline as a floor) is scored as `tire`. When MMDA's label is deeper, it counts as an underestimate. Passability isn't affected, because tire and deeper are all NPATV. The report gives the number of these readings. **[Claude's call]**

## 7. Metrics (plan Table 13)

| Metric | Definition | Set | Reported first |
|---|---|---|---|
| Underestimation rate | Answered photos where Lusot's level is below MMDA's, over all answered photos | A | **Yes** |
| Passability agreement | Same class as MMDA, over answered photos with a stated class | A | **Yes** |
| Coverage | Answered photos over all photos; refusals and processing failures counted separately | A | **Yes** |
| Overestimation rate | Answered photos where Lusot's level is above MMDA's, over answered photos | A | |
| Level agreement | Exact match, and within one level, over answered photos | A | |
| Weighted kappa | Quadratic-weighted Cohen's kappa over the 9 ordered levels (`sklearn.metrics.cohen_kappa_score(..., weights="quadratic", labels=range(9))`) | A | |
| Landmark agreement | Muse Spark's landmark against our own labels, made without seeing Lusot's output (M8). Over the references our labels give a landmark, in photos Muse Spark answered. A labelled box that Muse Spark skipped counts as a disagreement. A label that matched no box is counted apart and left out. | A | |
| Vehicle-type agreement | Confusion matrix of Muse Spark's vehicle type against our labels (M8 records the type as well). A development diagnostic for W14, not a headline number. | A (development), C | |
| False flood rate | Flood-free photos that got a level instead of "no flood seen" or a refusal. Over every scored A-neg photo. A processing failure counts in n, never as a false flood, and is shown beside it. | A-neg | |
| Correct refusals | Dark or blurry photos that were refused. A processing failure is not a refusal. | Quality subset | |
| Depth error | Median and worst error in inches, one point estimate per wheel from its true tire code | B, D | |
| Envelope coverage | Wheels whose true depth falls inside `depthInMin` to `depthInMax`, over the wheels measured | B, D | |
| Ablation | All of the above with the landmark reading alone, then with geometry added, then with the self-check when it is built (plan §4, gated) | A, B | |
| Latency | Upload, or a sample's start, to the final result, median and 95th percentile | Live tests | |

- Every metric is reported with its sample size `n`.
- With about 20 sealed photos, results are called **indicative** (W19).
- There is no human baseline. Rene is the only approved person and logs MMDA's labels while collecting Set A, so his level labels wouldn't be independent (plan §11).
- **"No flood seen" on a Set A photo** counts as an answered photo whose level is below every level, so it is an **underestimate**. It is never counted as a refusal. For passability it counts as PATV. The report also gives the number of these readings. **[Claude's call]**
- For exact and within-one agreement, "no flood seen" counts as one step below `below_gutter`: never exact, and within one level only of `below_gutter`. In the weighted kappa, which knows only the 9 levels, it counts as `below_gutter`.
- Coverage always sits next to every rate, so a run that refuses almost everything can't look good.
- Every report shows two baselines, "always the most common level" and "always the most common passability class". Both come from the development rows, and are scored on Lusot's answered rows. Lusot should beat them on within-one agreement and on underestimation, and falling short on either is underfitting. Exact agreement is shown but not judged, because landmarks never read `gutter` (§6). The report also counts the NPLV and NPATV photos caught. Reports print numbers, not verdicts.
- In results by level, a level with fewer than 5 photos shows counts, not percentages.

## 8. Release gate for inches (M18)

**[Rene]** These are the plan's proposed targets. Rene fixes the final numbers here **before the sealed run**:

- Set B median depth error ≤ **3 in**
- At least **70%** of Set B wheels measured
- Envelope coverage ≥ **80%**
- **No rise** in Set A underestimation when geometry is added

**What "rise" means here.** Wherever this section says Set A underestimation rises, or doesn't rise, when geometry is added, a rise means that geometry raises either the underestimation rate or the number of underestimated photos.

Set B's figures are the shipped configuration's: SAM's waterline with the frozen rim-edge factor k. The figures without k, and with the known waterline, are reported but never gate. Without Set B, no inches show.

If the sealed run misses any target, pins show the level and landmark without inches, and the report says why.

**Outcome rule, fixed before the run.** The one sealed run scores both configurations as the ablation: landmark alone, and landmark plus geometry. Then:
1. If Set A underestimation **does not rise** when geometry is added, geometry stays in the level path (the deeper reading wins). Inches are shown only if the other three targets also pass.
2. If Set A underestimation **rises** with geometry, the shipped pipeline uses landmark-only levels and shows no inches. The landmark-only row becomes the headline.
3. Both rows are always reported. This rule chooses between two configurations named in advance, so nothing is tuned on the sealed set.

**[Rene, with M18 by Nov 2] Proposed guards.** "Deeper reading wins" means geometry can only raise a level or drop a wheel, so underestimation will almost never rise. Rule 1 alone would keep geometry even if it adds refusals or overestimates. Compared with landmark alone on the sealed Set A, geometry stays only if all three hold:
- underestimation doesn't rise
- coverage falls by no more than **10 percentage points**
- passability agreement falls by no more than **5 percentage points**

Otherwise rule 2 applies.

A rate with nothing to count can't show that a guard or a target is met, so it fails, and rule 2 applies when it is a guard.

**The self-check (plan §4, gated).** It is off in this evaluation: MS3b's Task 16 ablation was dropped (Oct 30, 7:28 AM), so no development ablation exists to turn it on. Whether it is on is decided on **development data only**, by Nov 1, and frozen before the sealed run. It is turned off if the development ablation shows no gain or photo to pin takes over 10 s (plan Table 18). If it is on, "landmark plus geometry" in the rule above means the frozen configuration with the self-check. The sealed run also reports geometry without the self-check as an extra ablation row. That row can never be chosen after the run.

## 9. Exclusions

A photo is excluded before scoring **only** for one of these reasons, and each exclusion is logged with its reason:
- not posted by MMDA or a city government
- depth or passability label visible in the image (`label_in_image` = `yes`)
- no matching alert
- unmapped label
- conflicting alerts
- duplicate or repost (identical files, or difference hashes within 6 bits of each other, found by MS2's split)
- outside Metro Manila
- the file can't be decoded (checked by MS2's split, before any run; a file that decoded but fails in the pipeline is a processing failure, not an exclusion)

A-neg photos are excluded only as duplicates or files that can't be decoded.

A label whose depth words don't map to the scale is excluded as `unmapped label`, even when its passability class maps.

A photo is **never** excluded because of Lusot's output. **Notes never change the ground truth.** No photo is relabeled after its prediction is seen. A new exclusion must be a written rule that tests facts recorded before the run, applies to every row, and is made before the sealed run with Rene's OK.

## 10. Reproducibility (the sealed run)

- Freeze and record: model IDs, prompt and schema versions, this file's version, the level rules, dataset versions and split seeds, and the face-blur setting with its detector version (D12); Muse Spark's reasoning effort; the SAM phrases sent, any backup phrase included; `store` and `max_side`; the annotation (drawing) version of the numbered image; the self-check setting; and MS3b's tuning version, tire codes, rim-edge factor k and geometry's default. Every evaluation run sends Meta the same face-blurred photos the live system would.
- Save the raw SAM masks and Muse Spark outputs. SAM results can vary slightly between runs (plan §19).
- Run the sealed set **once**.
- A run that stops partway, from a rejected key, a crash or a lost connection, resumes as the same run: photos with saved outputs are never sent again. A resume isn't the disclosed rerun.
- A photo whose analysis failed because Meta's service failed (an HTTP error after the client's retries, or a timeout) is retried once before the export, and the report says how many were. A photo whose answer was invalid is never retried.
- Recovery tests on the analysis path happen **before** the freeze: duplicate events, interrupted SAM streams, Lambda timeouts and failed deletions.
- **After the freeze**, only fixes that can't change any depth output may land, such as error handling and retries. A fix that could change an output needs **one** rerun of the sealed set, disclosed in the report with both sets of numbers and the reason. The one disclosed rerun runs at a second, recorded freeze, and its results sit beside the first run's, so both sets of numbers stay in the repo.
- **One-command check (plan §11).** The sealed run's per-photo results are committed to the repo: readings, levels and labels, but no photos. `python eval/run_eval.py --from-saved` rebuilds every table in the report from them without an API key, so judges can check the numbers themselves. **[Claude's call]** The committed rows also leave out post links and spot names. Judges need only the IDs, the labels and Lusot's outputs to check the numbers.

## Change log

| Date | Version | Change | Approved by |
|---|---|---|---|
| Oct 26, 2026 | 0.1 | First draft from plan §9 and §11, with gap fixes G3 and G4 | Covered by the 0.7 approval |
| Oct 26, 2026 | 0.2 | Label rules for inches, ranges, statuses and passability phrases, taken from real alert wording in public news lists (before any result exists) | Covered by the 0.7 approval |
| Oct 26, 2026 | 0.3 | From the builder check: Set B final sealed; vehicle-type diagnostic; outcome rule fixed in advance; recovery tests before the freeze; post-freeze fix rule | Covered by the 0.7 approval |
| Oct 27, 2026 | 0.4 | From the Oct 27 plan update: government-posted Set A photos only (and a matching exclusion reason); Set D reported apart from Set B; the self-check ablation row and when it is decided; no human baseline; the one-command check | Covered by the 0.7 approval |
| Oct 27, 2026 | 0.5 | From the second builder check:<ul><li>labels printed on images are cropped or excluded</li><li>people count fully (D13, Rene)</li><li>"no flood seen" scores as an underestimate</li><li>"at least tire deep" scores as tire</li><li>proposed guards on the outcome rule (M18)</li><li>the face-blur setting is frozen (D12)</li></ul> | Covered by the 0.7 approval |
| Oct 28, 2026 | 0.6 | Rene's answers to the MS3a spec's questions, before any result exists (§6):<ul><li>a floor means "this level or deeper" in the one-level rule (Q4, changed)</li><li>the gutter gap still refuses (Q2, kept)</li><li>a standing adult with a hidden waterline still blocks wading adults (Q3, kept)</li></ul>A photo where SAM finds no water but Muse Spark sees some is refused (Q1, an MS3a pipeline rule). | These items: Rene, Oct 28, 7:58 AM, in chat. The rest of the file is covered by the 0.7 approval. |
| Oct 30, 2026 | 0.7 | <ul><li>Scope (the tracker's ruling under Rene's delegation, Oct 30, 10:42 AM): the whole file is approved at 0.7, rows 0.1 to 0.6 included, except §8's numbers and the guards marked [Rene, with M18 by Nov 2], which stay with Rene</li><li>§2 and §3: label and matching readings, the alert time for separate posts and the same-spot test. Item 3.3 took C224 from MS2's spec (the fix relayed Oct 30, 8:06 AM), which S-R9's ruling had since changed in the code but not in the spec; §3 and §4 now state the rule the code applies: two unmarked shared names for the same spot, and any shared name for an event</li><li>§4: the split, its seed, cap and stratification by passability, Set B's split by car, the final-car run, one archive per sealing step (MS2-Q2), A-neg's source (Wikimedia Commons), and validation by event replay when tuning runs</li><li>§4: the cap's rule for an empty side (C204)</li><li>§4 and §8: the sealed run.json records whether the cutoffs kept their start values (4.3), and the self-check is stated as off in this evaluation</li><li>§5: Set B's crops and truth (MS2-Q2)</li><li>§6: in-between waterlines (MS3b-Q5)</li><li>§7: metric denominators, the baseline row, the per-level counts rule and what latency measures</li><li>§8: what "rise" means, Set B's gate figures, and undefined guards and targets</li><li>§9: duplicates, files checked before the run, A-neg's exclusions, notes that never change the ground truth, who counts as a city, and an unmapped depth beside a mapped class</li><li>§10: the freeze list, resume, retry and the rerun</li></ul> | Rene, Oct 30, 2026, in writing (delegated to the tracker's double-check) |
| Nov 1, 2026 | 0.8 | §6: an adult's `ankle` gives no reading (MS3a's C91), and the gutter gap's people pair goes with it. From the Nov 1 development check (`docs/research/2026-11-01-overnight-accuracy.md`): `ankle` answers read about knee-deep water as below the gutter. | Rene, Nov 1, 2026, in writing (delegated to the tracker's double-check, about 9:58 PM) |
| Nov 2, 2026 | 0.9 | <ul><li>§6: a person whose box's longer side is under 60 px never sets the level and blocks no one; its reading still refuses the photo when deeper than the result (MS3a's C92, with C317)</li><li>§6: a "no" on standing water is refused as `water_unsure` when SAM's water covers more than 0.25 of the image's lower half (MS3a's C93)</li><li>tuning-v2 (C310's change log in `tuning.py`): `min_person_side_px` 60 (C92) and `no_flood_share_max` 0.25 (C93). `touch_share_min` stays 0.25: 0.10 passed on the agreed labels, but was held for OL131, whose label is unsure, and which would read knee where one relabel read tire (MS3b's C331)</li><li>Evidence: $0 replays of the 120 Set C development runs, scored on the 55 photos the blind double relabel of Nov 2 agreed on. At v0.8: 10 scored levels, 8 exact, 2 over, 0 under, and 6 "no flood seen". At v0.9: 9 scored levels, 8 exact, 1 over, 0 under, no passability class read lower, and 4 "no flood seen" (OL064's, below the gutter on the relabel, is now a refusal). A-neg's 10 development photos and the 42 samples: no change.</li><li>Not yet measured: C93 on wet roads with reflections and on river or bay views, which may now be refused.</li><li>Integrity: decided on development evidence only (Set C with the blind double relabel of Nov 2, and A-neg's development photos). The tracker had seen Set A's text labels while filling the log, and no Set A photo or result informed this.</li></ul> | The tracker's ruling under Rene's standing delegation (Oct 31: "choose the best recommended action"; Nov 1, about 9:55 PM; Nov 2, about 3:4x AM), for Rene's confirmation on Nov 2. If he declines, the change is reverted before the freeze. |
