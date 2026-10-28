# Evaluation rules

- **Status:** DRAFT v0.6 (Oct 28, 2026), written from plan §9 and §11 (as updated Oct 27), real alert wording and two builder checks. v0.6 adds Rene's answers to the MS3a questions. Rene approves the whole file before any Set A result is seen.
- **Freeze rule:** every rule here is set **before** testing (plan §9, §11). Once Rene approves this file, any change needs his written OK in the change log at the bottom. After the sealed run, the scoring rules don't change at all; §10 covers fixes and the one disclosed rerun.

Items marked **[Rene]** are judgment calls that only Rene can make. Every other rule is copied from the plan.

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

- Spelling and case variants of the same words map the same way, for example "half knee", "half-knee", "Half Gutter", "gutter-deep" and "above gutter deep".
- **Labels given in inches** (real MMDA alerts do this; see `docs/research/2026-10-26-alert-index.md`):
  - **Words win.** When an alert gives both words and inches ("Gutter deep, 8""), the words decide the level.
  - **A single number** ("10"", "12"", "37 inches") takes its level from the level rule in §1.
  - **[Rene] Proposed:** a **range** ("13-18 inches") takes the level of its **upper** value. That matches Lusot's round-deeper rule and keeps the underestimation measure strict.
  - Centimetres are converted at 2.54 cm per inch first.
- **Statuses that are not depths**, such as "subsided", can't match a photo.
- **Any other label is excluded and logged with the reason "unmapped label".** It is never guessed. A new mapping may be added only before the sealed run, with Rene's OK.

**Passability ground truth** is the class stated in the alert. It is scored separately from the level, because MMDA's field passability sometimes differs from the gauge table (plan §9). For example, "Waist Deep, 37"" has been marked *not passable to light vehicles*.

| Passability as written | Class |
|---|---|
| PATV, passable to all (types of) vehicles, passable to light vehicles | PATV |
| NPLV, not passable to light vehicles, not passable to motorcycles and cars (sedan) | NPLV |
| NPATV, not passable to all (types of) vehicles, not passable to any vehicle | NPATV |

**[Rene] Proposed:** if an alert states no class, the photo is left out of the passability metric only, not out of the level metrics. Likewise, a passability-only alert counts for passability only. The report gives every count.

## 3. Matching a photo to an alert (Set A)

- **Source:** Set A uses only photos that MMDA or a city government posted itself. News-outlet photos are never used; news lists only help find the official posts (plan §11, Table 25, M7).
- **Labels printed on the image** (alert cards, banners, burned-in captions) would let the model read the answer. Rene crops them off at collection when the reference stays in frame (`label_in_image` = `cropped`). A photo whose depth or passability words are still visible is excluded (§9).
- **Same post:** a photo inside the same MMDA or city post as the alert is matched by construction.
- **Separate posts:** a government-posted photo must show the **same named spot** as the alert, meaning the same street plus cross street or landmark, and its time must be within **30 minutes** of the alert time.
- If a photo matches several alerts, use the one nearest in time. If two of them differ by more than one level, exclude the photo ("conflicting alerts").
- Only Metro Manila photos count.

## 4. Flood events and splits

- **Flood event:** the same place on the same calendar day (Manila time). **[Rene] Proposed:** "same place" means the same named spot, or spots within 300 m of each other.
- **Set A** is split **by event, not by photo**: about 30 photos for development and about 20 sealed, so no event appears in both (W18).
  - The split script assigns whole events with a seeded random draw. The seed is recorded below.
  - It writes the sealed rows straight into the encrypted archive (M19), and agents only ever see development rows.
- **A-neg:** about 10 for development and 5 sealed, split the same way.
- **Set B:** split by car photo, so development and final never share a car. **The final cars are sealed like Set A.**
  - Their photos are kept apart.
  - The generator and the G3 ground truth run on them as one unattended script, writing straight into the encrypted archive.
  - The generator is built and debugged on development cars only.
- **Set C** is development only and never counts toward headline numbers.
- **Set D** (only if it rains) is final only, never tuned on, and reported apart from Set B (plan Table 12).
- Split seed: `TBD at split time`. Split date: `TBD`.

## 5. Ground truth for Set B (gap fix G3)

- Scale comes from the **whole tire** in each dry photo: ground contact to tread top, with the overall diameter taken from the tire code (formula from Table 7). It is **not** taken from the rim.
- Each synthetic waterline's true depth (in inches) uses that scale.
- The ratio between the visible rim edge and the nominal rim size is measured on **development cars only**. Geometry error is reported both without and with that calibration.

## 6. Reading rules that scoring must respect (plan §7 to §9, gap fix G4)

- Landmark readings follow Table 8 exactly as written.
  - Hub = half_tire, MMDA's own definition, even where a large tire's hub sits slightly above 13 in.
  - Tire only = below_gutter.
- Geometry inches follow the level rule in §1.
- When one wheel has both a landmark and a geometry reading, the deeper one is kept. A wheel whose two readings are more than one level apart is dropped.
- Across references, Lusot keeps the deepest believable reading and refuses when references disagree by more than one level.
  - **Floors (Rene, Oct 28):**
    - A floor ("at least" a level, such as covered wheels) means that level or deeper, so it never disagrees with a deeper reading.
    - The photo is refused when an exact reading sits more than one level below the deepest reading, with a floor counted at its own level there.
    - So "at least tire" beside a chest-deep adult gives chest, while "at least tire" beside an exact half_tire refuses.
  - **The gutter gap (Rene, Oct 28: kept):** landmarks never read `gutter`, so `tire_only` beside `rim_quarter` (and `ankle` beside `mid_shin`) is two levels apart, and the photo is refused.
- **People count fully (Rene, Oct 27, D13):**
  - A standing adult can set the level alone, through Table 8's body rows.
  - With wheels in the photo too, the rules above apply: deepest believable reading, and refusal when readings differ by more than one level.
  - Wading adults count only when no adult in the photo is standing still. That includes a standing adult whose waterline is hidden (Rene, Oct 28).
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
| Landmark agreement | Muse Spark's landmark against our own labels, made without seeing Lusot's output (M8) | A | |
| Vehicle-type agreement | Confusion matrix of Muse Spark's vehicle type against our labels (M8 records the type as well). A development diagnostic for W14, not a headline number. | A (development), C | |
| False flood rate | Flood-free photos that got a level instead of "no flood seen" or a refusal | A-neg | |
| Correct refusals | Dark or blurry photos that were refused | Quality subset | |
| Depth error | Median and worst error in inches, one point estimate per wheel from its true tire code | B, D | |
| Envelope coverage | Wheels whose true depth falls inside `depthInMin` to `depthInMax` | B, D | |
| Ablation | All of the above with the landmark reading alone, then with geometry added, then with the self-check when it is built (plan §4, gated) | A, B | |
| Latency | Upload to pin, median and 95th percentile | Live tests | |

- Every metric is reported with its sample size `n`.
- With about 20 sealed photos, results are called **indicative** (W19).
- There is no human baseline. Rene is the only approved person and logs MMDA's labels while collecting Set A, so his level labels wouldn't be independent (plan §11).
- **"No flood seen" on a Set A photo** counts as an answered photo whose level is below every level, so it is an **underestimate**. It is never counted as a refusal. For passability it counts as PATV. The report also gives the number of these readings. **[Claude's call]**
- Coverage always sits next to every rate, so a run that refuses almost everything can't look good.

## 8. Release gate for inches (M18)

**[Rene]** These are the plan's proposed targets. Rene fixes the final numbers here **before the sealed run**:

- Set B median depth error ≤ **3 in**
- At least **70%** of Set B wheels measured
- Envelope coverage ≥ **80%**
- **No rise** in Set A underestimation when geometry is added

If the sealed run misses any target, pins show the level and landmark without inches, and the report says why.

**[Rene] Proposed outcome rule, fixed before the run.** The one sealed run scores both configurations as the ablation: landmark alone, and landmark plus geometry. Then:
1. If Set A underestimation **does not rise** when geometry is added, geometry stays in the level path (the deeper reading wins). Inches are shown only if the other three targets also pass.
2. If Set A underestimation **rises** with geometry, the shipped pipeline uses landmark-only levels and shows no inches. The landmark-only row becomes the headline.
3. Both rows are always reported. This rule chooses between two configurations named in advance, so nothing is tuned on the sealed set.

**[Rene, with M18 by Nov 2] Proposed guards.** "Deeper reading wins" means geometry can only raise a level or drop a wheel, so underestimation will almost never rise. Rule 1 alone would keep geometry even if it adds refusals or overestimates. Compared with landmark alone on the sealed Set A, geometry stays only if all three hold:
- underestimation doesn't rise
- coverage falls by no more than **10 percentage points**
- passability agreement falls by no more than **5 percentage points**

Otherwise rule 2 applies.

**[Rene] Proposed: the self-check (plan §4, gated).** Whether it is on is decided on **development data only**, by Nov 1, and frozen before the sealed run. It is turned off if the development ablation shows no gain or photo to pin takes over 10 s (plan Table 18). If it is on, "landmark plus geometry" in the rule above means the frozen configuration with the self-check. The sealed run also reports geometry without the self-check as an extra ablation row. That row can never be chosen after the run.

## 9. Exclusions

A photo is excluded before scoring **only** for one of these reasons, and each exclusion is logged with its reason:
- not posted by MMDA or a city government
- depth or passability label visible in the image (`label_in_image` = `yes`)
- no matching alert
- unmapped label
- conflicting alerts
- duplicate or repost
- outside Metro Manila
- the file can't be decoded

A photo is **never** excluded because of Lusot's output.

## 10. Reproducibility (the sealed run)

- Freeze and record: model IDs, prompt and schema versions, this file's version, the level rules, dataset versions and split seeds, and the face-blur setting with its detector version (D12). Every evaluation run sends Meta the same face-blurred photos the live system would.
- Save the raw SAM masks and Muse Spark outputs. SAM results can vary slightly between runs (plan §19).
- Run the sealed set **once**.
- Recovery tests on the analysis path happen **before** the freeze: duplicate events, interrupted SAM streams, Lambda timeouts and failed deletions.
- **After the freeze**, only fixes that can't change any depth output may land, such as error handling and retries. A fix that could change an output needs **one** rerun of the sealed set, disclosed in the report with both sets of numbers and the reason.
- **One-command check (plan §11).** The sealed run's per-photo results are committed to the repo: readings, levels and labels, but no photos. `python eval/run_eval.py --from-saved` rebuilds every table in the report from them without an API key, so judges can check the numbers themselves. **[Claude's call]** The committed rows also leave out post links and spot names. Judges need only the IDs, the labels and Lusot's outputs to check the numbers.

## Change log

| Date | Version | Change | Approved by |
|---|---|---|---|
| Oct 26, 2026 | 0.1 | First draft from plan §9 and §11, with gap fixes G3 and G4 | Pending (Rene) |
| Oct 26, 2026 | 0.2 | Label rules for inches, ranges, statuses and passability phrases, taken from real alert wording in public news lists (before any result exists) | Pending (Rene) |
| Oct 26, 2026 | 0.3 | From the builder check: Set B final sealed; vehicle-type diagnostic; outcome rule fixed in advance; recovery tests before the freeze; post-freeze fix rule | Pending (Rene) |
| Oct 27, 2026 | 0.4 | From the Oct 27 plan update: government-posted Set A photos only (and a matching exclusion reason); Set D reported apart from Set B; the self-check ablation row and when it is decided; no human baseline; the one-command check | Pending (Rene) |
| Oct 27, 2026 | 0.5 | From the second builder check:<ul><li>labels printed on images are cropped or excluded</li><li>people count fully (D13, Rene)</li><li>"no flood seen" scores as an underestimate</li><li>"at least tire deep" scores as tire</li><li>proposed guards on the outcome rule (M18)</li><li>the face-blur setting is frozen (D12)</li></ul> | Pending (Rene) |
| Oct 28, 2026 | 0.6 | Rene's answers to the MS3a spec's questions, before any result exists (§6):<ul><li>a floor means "this level or deeper" in the one-level rule (Q4, changed)</li><li>the gutter gap still refuses (Q2, kept)</li><li>a standing adult with a hidden waterline still blocks wading adults (Q3, kept)</li></ul>A photo where SAM finds no water but Muse Spark sees some is refused (Q1, an MS3a pipeline rule). | These items: Rene, Oct 28, 7:58 AM, in chat. The whole file is still pending. |
