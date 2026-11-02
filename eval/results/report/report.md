# Lusot evaluation report

The frozen pipeline ran once on the sealed sets, on 2026-11-03. Its figures are agreement with the labels MMDA and the cities posted, mapped by eval/rules.md §2 (v0.11) before any result was seen. With samples this small, every figure is indicative and carries its n.

## Reported first

Rules §7's three headline figures, for the configuration that ships and then for the other.

| Configuration | Underestimation | Passability agreement | Coverage |
|---|---|---|---|
| Landmark alone (ships) | 0 of 1 (0.0%) | 0 of 0 (undefined) | 1 of 6 (16.7%) |
| Landmark plus geometry | 0 of 1 (0.0%) | 0 of 0 (undefined) | 1 of 6 (16.7%) |

## Release gate

Rules §8's targets and guards, each with the value found. Geometry stays only if Set A underestimation doesn't rise and both guards hold, and inches show only if geometry stays and Set B meets its three targets.

Self-check: off (decided 2026-10-30, MS3). It is off in this evaluation: MS3b's ablation was dropped, so no development ablation exists to turn it on (eval/rules.md §8).

| Check | Found | Target | Passed |
|---|---|---|---|
| Set A underestimation | 0 of 1 (0.0%) with geometry, 0 of 1 (0.0%) without | no rise in the rate or the count | yes |
| Set A coverage (guard) | no change: 1 of 6 (16.7%) with geometry, 1 of 6 (16.7%) without | a fall of at most 10 points | yes |
| Set A passability agreement (guard) | 0 of 0 (undefined) with geometry, 0 of 0 (undefined) without | a fall of at most 5 points | no (undefined) |
| Set B median depth error | Set B wasn't run (n = 0) | at most 3 in | no (undefined) |
| Set B wheels measured | Set B wasn't run (n = 0) | at least 70% | no (undefined) |
| Set B envelope coverage | Set B wasn't run (n = 0) | at least 80% | no (undefined) |

**Decision:** Geometry doesn't stay, so landmark alone ships. Inches aren't shown, because geometry doesn't ship.

Reasons:

- Set A passability agreement can't be compared: 0 of 0 (undefined) with geometry, 0 of 0 (undefined) without.
- Set B wasn't run, so its three targets can't be checked and inches aren't shown.

## Set A: every metric

Each configuration's Set A figures over the photos that rules §9 keeps (rules §7). The level figures and kappa are over answered photos whose alert gave a level, and passability agreement over answered photos whose alert stated a class.

| Metric | Landmark alone | Landmark plus geometry |
|---|---|---|
| Photos scored | n = 6 | n = 6 |
| Coverage | 1 of 6 (16.7%) | 1 of 6 (16.7%) |
| Refused (can't tell) | 5 of 6 (83.3%) | 5 of 6 (83.3%) |
| Refused: no_usable_reference | 4 of 6 (66.7%) | 4 of 6 (66.7%) |
| Refused: no_water_found | 1 of 6 (16.7%) | 1 of 6 (16.7%) |
| Processing failed | 0 of 6 (0.0%) | 0 of 6 (0.0%) |
| Underestimation | 0 of 1 (0.0%) | 0 of 1 (0.0%) |
| Overestimation | 1 of 1 (100.0%) | 1 of 1 (100.0%) |
| Level agreement, exact | 0 of 1 (0.0%) | 0 of 1 (0.0%) |
| Level agreement, within one level | 0 of 1 (0.0%) | 0 of 1 (0.0%) |
| Passability agreement | 0 of 0 (undefined) | 0 of 0 (undefined) |
| Weighted kappa (quadratic) | 0.00 (n = 1) | 0.00 (n = 1) |
| "No flood seen" readings | 0 of 6 (0.0%) | 0 of 6 (0.0%) |
| Floor readings ("at least" a level) | 1 of 6 (16.7%) | 1 of 6 (16.7%) |

## Baseline

The baseline can't be set: these development rows give no class to take (C424).

## By the alert's level

Each configuration's Set A photos by the level the alert gave: the photos kept, those answered, and how many of those Lusot read exactly, within one level and below the alert's level. A level with 5 or more photos also shows the three as shares of its answered photos.

**Landmark alone**

| The alert's level | Photos | Answered | Exact | Within one level | Underestimated |
|---|---|---|---|---|---|
| gutter | n = 6 | 1 | 0 of 1 (0.0%) | 0 of 1 (0.0%) | 0 of 1 (0.0%) |

**Landmark plus geometry**

| The alert's level | Photos | Answered | Exact | Within one level | Underestimated |
|---|---|---|---|---|---|
| gutter | n = 6 | 1 | 0 of 1 (0.0%) | 0 of 1 (0.0%) | 0 of 1 (0.0%) |

## Set A: level matrices

One matrix for each configuration, over the answered photos whose alert gave a level: the alert's level down the side, Lusot's across. Each chart's table lists its non-empty cells, since GitHub shows a chart without its tooltips.

![Landmark alone: the alert's level against Lusot's](level-matrix-landmark.svg)

| The alert's level | Lusot's level | Photos |
|---|---|---|
| gutter | tire | 1 |

![Landmark plus geometry: the alert's level against Lusot's](level-matrix-geometry.svg)

| The alert's level | Lusot's level | Photos |
|---|---|---|
| gutter | tire | 1 |

## Landmark agreement

Muse Spark's landmark against our M8 label for the same box (C415), over the Set A photos kept that Muse Spark answered, Lusot's refusals included. Every configuration shares Muse Spark's answer, so this is counted once.

| Reference | Agreement with M8 |
|---|---|
| Wheel | 2 of 2 (100.0%) |
| Vehicle body | 5 of 11 (45.5%) |
| Person | 2 of 3 (66.7%) |
| All | 9 of 16 (56.3%) |

Boxes that Muse Spark's answer skipped, which count as disagreements: 0 of 16 (0.0%). M8 labels that matched no box, which are left out: n = 6.

## A-neg: flood-free photos

The A-neg photos are openly licensed Wikimedia Commons photos (CC0, public domain or CC BY). Flood-free photos that got a level instead of "no flood seen" or a refusal, over the A-neg photos kept. A processing failure counts in the n, never as a false flood.

| Metric | Landmark alone | Landmark plus geometry |
|---|---|---|
| False flood rate | 0 of 5 (0.0%) | 0 of 5 (0.0%) |
| False flood rate, wet surface | 0 of 0 (undefined) | 0 of 0 (undefined) |
| False flood rate, dry surface | 0 of 5 (0.0%) | 0 of 5 (0.0%) |
| "No flood seen" | 5 of 5 (100.0%) | 5 of 5 (100.0%) |
| Refused (can't tell) | 0 of 5 (0.0%) | 0 of 5 (0.0%) |
| Processing failed | 0 of 5 (0.0%) | 0 of 5 (0.0%) |

## Correct refusals

The quality subset: the Set A and A-neg photos kept that were marked dark or blurry before the run (C414). A refusal is correct here, and a processing failure is not a refusal.

| Metric | Landmark alone | Landmark plus geometry |
|---|---|---|
| Correct refusals | 3 of 3 (100.0%) | 3 of 3 (100.0%) |
| Refused: no_usable_reference | 2 of 3 (66.7%) | 2 of 3 (66.7%) |
| Refused: no_water_found | 1 of 3 (33.3%) | 1 of 3 (33.3%) |
| Answered | 0 of 3 (0.0%) | 0 of 3 (0.0%) |
| Processing failed | 0 of 3 (0.0%) | 0 of 3 (0.0%) |

## Subsets

Each subset marked before the run (C414), then the photos whose alert gave tire or deeper (W6).

**Landmark alone**

| Subset | Photos | Coverage | Underestimation | Passability agreement |
|---|---|---|---|---|
| moving | n = 6 | 1 of 6 (16.7%) | 0 of 1 (0.0%) | 0 of 0 (undefined) |
| reflection | n = 6 | 1 of 6 (16.7%) | 0 of 1 (0.0%) | 0 of 0 (undefined) |
| splash | n = 2 | 0 of 2 (0.0%) | 0 of 0 (undefined) | 0 of 0 (undefined) |
| tire or deeper, by the alert | n = 0 | 0 of 0 (undefined) | 0 of 0 (undefined) | 0 of 0 (undefined) |

**Landmark plus geometry**

| Subset | Photos | Coverage | Underestimation | Passability agreement |
|---|---|---|---|---|
| moving | n = 6 | 1 of 6 (16.7%) | 0 of 1 (0.0%) | 0 of 0 (undefined) |
| reflection | n = 6 | 1 of 6 (16.7%) | 0 of 1 (0.0%) | 0 of 0 (undefined) |
| splash | n = 2 | 0 of 2 (0.0%) | 0 of 0 (undefined) | 0 of 0 (undefined) |
| tire or deeper, by the alert | n = 0 | 0 of 0 (undefined) | 0 of 0 (undefined) | 0 of 0 (undefined) |

## Set B

Not run in this results folder.

## Set D

Not run in this results folder.

## Latency

Live tests' seconds from upload, or a sample's start, to the final result (C416).

| Measure | Upload, or a sample's start, to the final result |
|---|---|
| Median | 34.5 s (n = 5) |
| 95th percentile, nearest rank | 43.1 s (n = 5) |

## Exclusions

Rules §9's reasons, read from each photo's facts and labels before scoring, never from Lusot's output.

**Set A:** 1 of 7 (14.3%) photos excluded.

| Reason | Photos | Ids |
|---|---|---|
| not posted by MMDA or a city government | 0 | none |
| depth or passability label visible in the image | 0 | none |
| no matching alert | 0 | none |
| unmapped label | 1 | A097 |
| conflicting alerts | 0 | none |
| duplicate or repost | 0 | none |
| outside Metro Manila | 0 | none |
| the file can't be decoded | 0 | none |

**A-neg:** 0 of 5 (0.0%) photos excluded.

| Reason | Photos | Ids |
|---|---|---|
| duplicate or repost | 0 | none |
| the file can't be decoded | 0 | none |

Left out of passability agreement only, because the passability label didn't map: none (n = 0).

## Frozen versions and data

Scored by eval/rules.md v0.11.

Freeze commit: `cf9191f3145c0571d99dadf00ee177554a5afa35`.

Geometry's live default before the run (C309): on.

| Frozen | Version |
|---|---|
| blur | yunet-2023mar/multiscale-1-0.5-0.25/pixelate-gauss-v2 |
| brightness_min | 40.0 |
| daylight_brightness_min | 80.0 |
| drawing | boxes-v1 |
| max_people | 6 |
| max_side | 1600 |
| max_vehicles | 6 |
| min_person_side_px | 60 |
| min_wheel_side_px | 40 |
| no_flood_share_max | 0.25 |
| prompt | muse_spark_photo_v1 |
| ragged_iqr_share | 0.1 |
| reasoning_effort | default |
| rim_edge_k | 1.0 |
| rim_score_min | 0.5 |
| rim_size_high | 1.15 |
| rim_size_low | 0.85 |
| sam_model | sam-3.1 |
| sam_phrases | floodwater,wheel,wheel rim,person,vehicle |
| schema | muse_spark_photo_v1 |
| sharpness_min | 25.0 |
| spark_model | muse-spark-1.3 |
| store | false |
| tire_codes | tire-codes-v2 |
| touch_share_min | 0.25 |
| touch_tolerance_px | 5.0 |
| tuning | tuning-v2 |
| untuned | no |

The cutoffs were tuned on development data and validated by event replay (rules 4.3).

| Dataset | Version | Split seed | In this results folder |
|---|---|---|---|
| Set A | 2026-11-02-split | 20261030 | 7 photos from 5 events |
| A-neg | 2026-11-02-split | 20261030 | 5 photos from 5 events |
| Set B | not recorded | not recorded | not run |
| Set D | not recorded | not recorded | not run |

The run recorded no stops.

Photos and crops retried once after a Meta service failure in this run (MS6E-Q6): 0.

The face blur runs before Meta receives a photo. It can miss faces that are very small, side-on, partly covered or in the dark.

## Rebuild this report

With no API key, this command rebuilds the report from the saved rows:

```sh
python eval/run_eval.py --from-saved
```

Where `python` isn't installed, as on macOS and many Linux systems:

```sh
python3 eval/run_eval.py --from-saved
```

---

Lusot estimates depth at one spot. It is not advice to cross. Follow MMDA and local advisories.

Not affiliated with MMDA.
