# MS3b Geometry Implementation Plan

> **Draft:** written before Rene approved the spec (D7). The executing controller reviews it before Task 1. It follows the spec as amended on Oct 29 (calls C300 to C328), whose C321 hands all scoring to MS6's harness (MS3b only writes rows for it). The plan review's rulings R86 to R88 hold: C303 starts at 10%, C317 is strict, and C305 gains check 9.
>
> **Amended on Oct 29, 4:33 AM,** with the spec: the plan review's findings 1 to 10 and its items 11 and 12, the tracker's §D1 to §D9, Rene's event replay (data roles §5), MS3b-Q5's answer, the Commons photo sets, MS4's evidence record (its C518), and fits to MS3a's code as built. The tasks are renumbered:
> - Tasks 1 to 6 keep their numbers. Task 6 loses the reasoning effort to a new Task 7 (finding 10).
> - Task 8 is new: the evidence record (C328).
> - The old Tasks 7 to 10 are now 9 to 12.
> - The old Task 11 is now Task 13 (the sweep and event replay) and Task 14 (the other development tools).
> - The old Tasks 12 to 15 are now 15 to 18.
>
> **Fix round 1, Oct 29, 5:26 AM:** the fresh review's P1 to P18 (and the spec's S1 to S10), and the rulings R117 and R119. Task 19, the sealed-run entry point, is new and comes last (C329). Task 7 gains a first step, so its steps are renumbered. Task 17 gains a step for the drawing on labelled photos (MS3b-Q8), so its later steps move down one.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Steps 2 to 6 gain rim geometry. Each reference must stand in water that SAM sees, a wheel's rim gives a depth in inches, and the deeper of a wheel's two readings decides. The development rows, the Set B rows and the tuned cutoffs follow, and the API still returns no inches. The pipeline's result also carries the evidence record that MS4 draws its overlay from.

**Architecture:**
- **Pure modules on masks:** `pipeline/waterline.py` (step 3) and `pipeline/geometry.py` (rim linking, the fit, the checks, the formula and G4). `rules.py` gains the inch level rule and the tire codes (`tire_codes.json`). `tuning.py` holds every cutoff, with Muse Spark's reasoning effort and the drawing.
- **The pipeline:** `run_pipeline` runs step 3 after the gate, and geometry when `geometry_in_level` is on. `Outcome` carries `levelFrom` and the inches, and `PipelineRun` carries the evidence record (`pipeline/evidence.py`, C328). The handler reads the setting from the template, and the API's allow-list stays as it is.
- **Development tools** in `backend/analysis/probes/` write MS6's §4.3 rows through `lusot_analysis/export.py`, and `python eval/run_eval.py` scores them (C400). MS3b computes no metric.

**Tech Stack:** Python 3.13 through uv: OpenCV 4.14.0 (`findContours`, `fitEllipse`, `approxPolyDP`) and NumPy; pytest, moto and ruff. Node 22 and Vitest for one API test. AWS SAM CLI and Docker Desktop for the deploy.

**Spec:** `docs/superpowers/specs/2026-10-28-ms3b-geometry-design.md` as amended on Oct 29 (C300 to C328, MS3b-Q1 to Q7), binding. These are read-only:
- The row contract is MS6's draft spec §4.3, with its C415, C418, C420, C423 and C425 (`C:\Systems\Lusot\lusot-wt\w4\docs\superpowers\specs\2026-10-28-ms6-evaluation-design.md`).
- MS2's formats are its spec's §5.9 (`C:\Systems\Lusot\lusot-wt\meta\docs\superpowers\specs\2026-10-28-ms2-data-tooling-design.md`), and MS2's win where the two differ, as MS6 says.
- The evidence record answers MS4's C518 (MS4's spec on `ms4-backend-specs`, at `6c345b0`).

Once MS2, MS4 and MS6 merge, their copies in `main` win. Executors read all four.

**Start condition:** after MS3a merges into `main`. Branch `ms3b-geometry` from `main` then. Every task changes files that MS3a's Tasks 1 to 13 create, so nothing starts earlier. Rene's overnight plan sets what runs first:
- Tasks 1 to 10 and 12 to 15 build on synthetic data.
- Task 11 sends C87's Commons photos, and Task 16 runs the Set C checks (C323).
- Steps that need Set A, A-neg or Set B development data wait, marked waiting. So does every step that scores or shows a Set A or A-neg development result, until Rene approves v0.7 (C322).
- Task 19 starts after Task 18 merges MS3b into `main`, on its own branch, and is due by Nov 2 (C329).

## Global Constraints

- **AWS:** as MS3a: region `ap-southeast-1`, profile `lusot`, `--no-cli-pager`, and `MSYS_NO_PATHCONV=1` in Git Bash for arguments that start with `/`.
- **Cloud waits (R119):** MS3b's smoke runs wait at least 180 s for each report's final status. MS3a's runs stop as late as about 150 s (C84, C88), and geometry adds time. B1's recorded bound stays 120 s (C68).
- **Model IDs:** exactly `sam-3.1` and `muse-spark-1.3`. Never `muse-spark-1.3-contributor`.
- **The face blur comes first.** Every image sent to Meta comes from `blur_for_meta` or `BlurredImage.derive`: live runs, Set B crops, the effort test and the Set C checks alike.
- **No new Meta call per photo.** Geometry uses masks the pipeline already requests (`wheel`, `wheel rim`, `floodwater`). The Lambda still makes 7 + 1 calls, the offline runner 5 + 1, and a replay none. Pay once (G2) is unchanged.
- **The Meta key:** as MS3a. It is never printed or written. A command that needs it sets it in the same PowerShell line: `$env:MODEL_API_KEY = [Environment]::GetEnvironmentVariable('MODEL_API_KEY','User'); <command>`.
- **Logs:** one JSON line per report, with C316's fields. Never masks, image data, a location, the key, an AWS error message, Muse Spark's `reason` or the evidence record (C328). Inches may be logged.
- **Printed output:** counts and timings only, with runs of 12 digits masked. No photo names or paths.
- **What never enters the repo:** account IDs, the Meta Team ID, console links, emails, plan text (cite "plan §N"), photos of any set, manifests, run folders and results rows. Tests build synthetic images and masks only.
- **Sealed data:** nothing under a folder named `sealed` is opened, listed or searched. Every new script calls the runner's `refuse_sealed` on every path it is given before opening anything. Set B's final cars and Set D are never touched. No Set A or A-neg photo is opened before MS2's split.
  - Task 19's entry point is the one tool that reads inside a folder named `sealed`, and only when Rene runs it (C329).
  - Its tests make their own `tmp_path` folder named `sealed`. That folder is synthetic, not sealed data. No test reads `lusot-data` or any real sealed folder, and no one opens the test folders by hand.
- **STURM stays offline** (MS3a's C87): the runner's `refuse_sturm_live` refuses a live run on it, and no MS3b command sends it to Meta. New Meta calls use only C323's sources, each with its credit line kept (R102).
- **v0.7 first (C322):** before any step that scores or shows a Set A or A-neg development result (C310's tuning and replay, C312 on labelled photos, C313, C315), the controller checks that `eval/rules.md`'s status line says v0.7, approved by Rene. If it doesn't, the step waits, marked waiting, and MS3b-Q2's fallback (b) applies. Set B's figures show no Set A result, so Set B doesn't wait for it.
- **Scoring belongs to MS6 (C321; MS6's C400).**
  - MS3b computes no `eval/rules.md` §7 metric, §8 gate, outcome rule or guard.
  - It writes MS6's §4.3 rows to a folder under `LUSOT_DATA_DIR`: never in the repo, and never a path with a part named `sealed`.
  - Then it runs `python eval/run_eval.py --from-saved --results <dir> --write` from the repo root.
  - `backend/analysis` never imports `eval/`. It runs the harness's commands, `--label-words` among them (C420), and reads their output.
  - **Nothing under `eval/` is edited** (the plan review's finding 9, §D9). MS6's code is Window 4's, and `eval/rules.md` changes only through Window 4's single v0.7 proposal, which Rene approves. Nothing in the `w4` or `meta` worktrees is edited either.
- **Exact values (spec §4, C301 to C308):**
  - **Step 3:** T = 5 px. In each lower-outline column, the edge is the top row of the water run that comes within T px of the object's lowest pixel (the run reaches into rows `y_low − T` to `y_low + T`). Lower-outline columns have their lowest object pixel in the bottom third of the object's mask box (`y_low − top ≥ 2 × height ÷ 3`). Fewer than a quarter of them touching → `no_water_contact`, and so does a mask with no lower-outline column, 1 or 2 px tall (finding 7). `y_w` is the median edge row of the touching columns. Their interquartile range above 10% of the box height → `ragged_waterline` (C303 as amended, R86). The cut clears rows ≥ `y_w`.
  - **C317 (strict, R87 and R90):**
    - A reading step 3 drops never decides.
    - If it is deeper than an exact result (`level_is_floor` false), the photo is refused as `references_disagree`.
    - A floor result stands, since it already means "this level or deeper". So does a result the dropped reading doesn't exceed.
    - Readings of a vehicle that C43 or C53 drops play no part.
  - **Checks (C305):**
    - daylight brightness at least 80 (MS3a's quality score)
    - rim score at least 0.5; a missing score fails
    - at least 5 contour points above `y_w − T`, and the fit's centre inside the wheel's SAM box, edges included
    - axis ratio (minor over major) at least 0.5
    - `y_w` at or below the fit's centre row
    - **check 9 (R88, R89, R91), the rim's size:**
      - The fit's horizontal extent (its full width along x, from its axes and angle) is divided by the wheel box's width.
      - The result must lie between `rim_size_low` × the smallest and `rim_size_high` × the largest of each code's `rim × cos φ ÷ (D × cos φ + W × sin φ)`, over the type's codes. Otherwise `rim_size`.
      - `rim_size_low` (0.85) and `rim_size_high` (1.15) are tuning fields, so C310 can tune them (finding 1). `rim_size_low` never goes below 0.50, and `rim_size_high` never above 1.55: past them, Task 3's side-on hubcap (0.2985) or whole wheel (0.9805) would pass (S3).
      - D is the tire's diameter and W its section width, both in inches. `cos φ` is the fit's axis ratio, and `sin φ = √(1 − cos² φ)`.
      - The ratio allows for the tread a box takes in when the wheel is seen at an angle.
    - any code's depth of 0 or less → `depth_not_positive` (C306)
  - **Formula:** `s = r ÷ (k × rim ÷ 2)`, `R = rim ÷ 2 + width × aspect ÷ 100 ÷ 25.4`, `depth = (c + R × s − y_w) ÷ s`. k = 1.0 until calibrated (G3).
  - **Inches:** the level is the level rule (`eval/rules.md` §1: upper limits 5, 8, 10, 13, 19, 26, 37 and 45 in) applied to the deepest code's depth. Inches are stored rounded outward to 0.1 in: min down, max up (C308). Rows for MS6 carry them unrounded, to 4 decimal places (C327).
  - **Tire codes (C304):**

    | Type | Codes |
    |---|---|
    | `sedan_hatch` | 175/65R14, 185/55R15, 185/60R15, 195/55R16 |
    | `suv_mpv` | 205/55R16, 205/55R17, 185/65R15, 195/60R16, 205/65R16, 205/60R17, 215/55R17 |
    | `van` | 215/70R16C |
    | `unknown` | every code above |
    | others | none |

  - **Figures read from the harness's report:**
    - the release-gate targets (`eval/rules.md` §8: median error at most 3 in, at least 70% measured, envelope coverage at least 80%, no rise in underestimation)
    - C309's guards (coverage falls by no more than 10 points, passability by no more than 5)
    - C319's trigger (under 70% measured, or a median error above 3 in)
    - the replay's difference in within-one photos (MS6's C425), which guard 3 reads (C324)
    - development A-neg's false floods (W9), which C310's rule for T, the touch share, the IQR share and the rim score reads (S6)
- **Tuning uses development data only:** Set A and A-neg development photos after MS2's split and v0.7 (C322), Set B development cars, and Set C.
- **Cost:**
  - Set B: about $0.15 (about 20 crops × 3 SAM phrases)
  - C312, its own line (§D2): about $0.90, under $2 (10 photos: one full run, then 4 runs of Muse Spark alone), plus about $0.15 to run a lower effort and the drawing together if both pass (P16)
  - the drawing on labelled photos (MS3b-Q8, Task 17): about $0.30, plus about $0.60 to re-judge the development photos if it is adopted
  - development runs: about $0.03 a photo, so about $1.10 for 40 photos
  - the water phrases (C326): about $0.20 on 40 development photos, plus an optional $0.05 on 10 Commons photos
  - the Set C checks (C323): about $0.57 for the 19 PUV photos, and $0.02 for the 4 coded cars
  - D1: at most $0.50 (up to 10 offline runs, MS3a's smoke run and one geometry photo)
  - Task 19: nothing, since its tests use synthetic data and fakes

  Every paid command prints its call count and estimated cost, and stops there unless given `--yes`.
- **Freeze:** the tuning version (with the reasoning effort and the drawing), the tire codes, the SAM phrases and `geometry_in_level`'s default are frozen before the sealed run, and each is recorded in the results folder's `run.json` (v0.7 item 10.1).
- **Screen copy:** MS3b changes no screen. The word "safe" appears in nothing it writes.
- **Toolchain, commits, builds and shells:** as MS3a.
  - Python `>=3.13,<3.14` through uv. No dependency changes.
  - Conventional Commits ending with the session's attribution lines, written with `git commit -F <file>`. Never `--no-verify`.
  - Run `node scripts/check_account_ids.mjs` from the repo root before every commit: the pre-commit hook doesn't run it (MS3a's `baa69a0`).
  - No Docker build while a Gradle build runs. Refresh PATH first, and commit from PowerShell.
  - Run the analysis package's commands from `backend/analysis` with `uv run`.

## Review Focus

Most likely first. Each line names its tests.

1. **SAM's wheel mask holds the wheel's reflection.**
   - When the water mask covers the reflection too, the edge sits at the real waterline (within 2 px) and the cut removes the reflection: Task 2 `test_reflection_in_the_wheel_mask_is_cut`.
   - When the water mask leaves a hole where the reflection is, the edge follows the reflection's round bottom. Its spread is 12.3 to 13.8% of the box, over C303's 10% (R86), so step 3 drops the reference as `ragged_waterline` and no type gets a geometry reading. Flat waterlines measure 0 to 1.5% and pass. Tests: Task 2 `test_reflection_hole_edge_is_ragged` and `test_flat_waterlines_pass`; Task 3 `test_reflection_hole_gets_no_geometry_reading`.
2. **The rim mask is a hubcap or the whole wheel.** Check 9 (R88) catches both, and the wheel keeps its landmark reading.
   - A hubcap scores 0.2985, against `sedan_hatch`'s bounds of 0.5108 to 0.7412 at its fit's axis ratio.
   - A whole wheel scores 0.9805, against 0.4966 to 0.7197.
   - A true rim seen at an angle, in a box that takes in the tread, still passes (R89, R91).

   Tests: Task 3 `test_hubcap_and_whole_wheel_rims_fail_rim_size` and `test_an_angled_rim_passes_checks_7_and_9`.
3. **A wheel answered `not_visible`.** It gets no geometry and no step 3, and the vehicle gives no reading from it. Task 6 `test_not_visible_wheel_gets_no_geometry`.
4. **Geometry decides while a person reads deeper.** Two levels apart refuses. One level deeper gives the person's level, without inches. A tie goes to the wheel, with its inches. Task 4 `test_a_person_reading_deeper_decides_without_inches`.
5. **Set B's composited water that SAM can't see.** The SAM variants record the wheel as unmeasured, the known-waterline variants still measure it, and `sam_water_found` is false. Task 15 `test_sam_missing_water_still_measures_the_known_waterline`.
6. **The evidence record leaks nothing.** No face or plate outline, no `reason`, and never a log line. Task 8 `test_evidence_holds_no_face_plate_or_reason` and `test_evidence_never_reaches_the_log`; Task 10 `test_log_line_holds_no_evidence`.
7. **Efforts never mix in the ablation (finding 5).** Development runs live in folders named by their effort and drawing, and the export refuses a run whose settings aren't the tuning's. Task 12 `test_export_refuses_mixed_settings`.
8. **A label the harness can map stays mappable (P1).** The export's label check mirrors the harness's `scoring.labels` exactly, or labels such as "Knee deep." and "9in" would become `(other words)` and their photos would be excluded, in the sealed run too. Task 12 `test_labels_match_the_harness`.

## Execution notes

- **Routing (D18, R81):**
  - Opus 5.5 at max: the implementers of Tasks 1 to 15 and 19, and each task's review, one seat with both verdicts (R81)
  - Sonnet 5.5 at xhigh: scoped re-reviews after a fix round
  - Claude itself: Task 11's paid steps, and Tasks 16 to 18
- **Order:** one task at a time, in number order. Task 11 deploys the core before the development tools, because C311's Oct 31 gate needs D1. Task 16 runs on Set C before the split. Task 17 runs when its data exists and Rene has approved v0.7 (C322, MS3b-Q1 and Q2). Task 19 runs after Task 18's merge, by Nov 2 (C329).
- **MS3a interfaces used,** as built (checked against the code on Oct 29):
  - `rules`: `LEVELS`, `PASSABILITY`, `level_index`, `Reading`, `WHEEL_ROWS`, `PEOPLE_ROWS`, `BODY_ROWS`, `HIDDEN_WHEEL`, `READING_TYPES`, `disagree`
  - `pipeline.types`: `Outcome` (its builders, `item_fields()`, `log_name`), `Reference`, `ModelClient` (whose `judge` already takes `deadline` and `reasoning_effort`), `ModelAnswerError`
  - `pipeline.segment`: `box_xyxy`, `segment_all`, `link_wheels`
  - `pipeline.references`: `Prepared`, `prepare_boxes`, `Layout`, `layout`, `water_found`, `gate`, `KeptVehicle`, `KeptPerson`, `Kept`, `apply_drops`
  - `pipeline.measure.measure`; `pipeline.combine`'s `combine` and `tie_order` (R82); and `pipeline.quality` (`QualityScores`, `quality_scores`, `quality_refusal`, `BRIGHTNESS_MIN`, `SHARPNESS_MIN`)
  - `pipeline`: `READING_PHRASES`, `PipelineRun(outcome, log, publish_jpeg)`, and `run_pipeline(data, client, prompt, *, phrases=SAM_PHRASES, deadline=None)`
  - `pipeline.saved`: `RecordingClient` (its `save(run_dir, *, photo, prompt, run)`), `SavedOutputsClient(run_dir, photo_data)`, `PhotoMismatch`, and the run-folder layout of MS3a Task 9: `run.json`; `sam/<phrase>.json`, `.npz` and `.raw`; `spark.json` with `reasoning_tokens`; and `spark.raw`. Each call's keywords pass through (R108), and a replay ends as its live run did (R109).
  - `annotate`: `NumberedBox`, `number_boxes`, `draw_numbered_boxes`, `check_ids_per_item`
  - `meta_client`: `MetaClient.judge(..., deadline=None, reasoning_effort=None)`, which sends `reasoning.effort` only when it is set (MS3a Task 7a); `SparkResult.reasoning_tokens`; `SAM_PHRASES`, `ModelRefused`, `MetaApiError`
  - `face_blur`: `blur_for_meta`, `MAX_SIDE` (1,600)
  - `probes/run_pipeline.py`: `refuse_sealed`, `refuse_sturm_live` (C87), `refuse_data_in_repo` (R111), `make_client`, `live(photo, data_dir)`, `replay(photo, run_dir)`, `main` (exit codes 0 to 3, R110) and `say`
  - `prompts.load_prompt`; `handler.analyse(data, client, *, deadline=None)`, and the handler's loads before the claim (C60, C79); `report_store.write_result`
  - `tests/fakes.py`: `SIZE`, `noise_jpeg`, `flat_jpeg`, `instance(..., mask_xyxy=None, score=0.9)`, `sam_results`, `FakeClient` (its `keywords` record `deadline` and `reasoning_effort`, R101), `vehicle`, `wheel`, `person`, `answer`, `meta_error`, `REPO_PROMPTS`, `level_case`
  - `backend/scripts/smoke_upload.py` (MS3a Task 15; R102, R115, R116): `photo_folder`, `seeded_photo_order(folder)` (C87's order, as `images/<name>` paths), `credited(folder, photos)`, `as_app_jpeg`, `upload_photo` (which runs `wait_final` and `log_lines`), `wait_final(..., clock=None, sleep=None)`, `check_report_body`, `log_lines(stack, report_id, *, until=None, clock=None, sleep=None)`, `Stack` (with `log_group`), `say_spend`, `CheckFailed`, `refuse_sealed`, `say`
  - MS1's `SamInstance(id, box, mask, score)`: `box` is half-open `(x0, y0, x1, y1)` floats in sent-image pixels, `mask` is an H×W bool array, and `score` is `float | None`
- **MS2's interfaces used by Task 19,** on `ms2-data` until MS2 merges: `backend/analysis/probes/set_b_masks.py` holds verbatim copies of `eval/data/guards.py`'s `is_sealed_name`, `refuse_sealed`, `require_sealed`, `console_ok` (`GetConsoleMode` on stdin and stdout, MS2's C202), `require_console`, `confirm` and `quiet`, with a parity test. `backend/analysis` can't import `eval/`, so these copies are the ones to reuse.
- **Commands** run from `backend/analysis` unless a step says otherwise.

---

### Task 1: Inch levels, tire codes and the tuning module

**Files:**
- Create: `backend/analysis/src/lusot_analysis/tuning.py`, `backend/analysis/src/lusot_analysis/tire_codes.json`
- Modify: `backend/analysis/src/lusot_analysis/rules.py`, `backend/analysis/src/lusot_analysis/pipeline/quality.py`, `backend/analysis/src/lusot_analysis/pipeline/references.py` (constants only)
- Test: `backend/analysis/tests/test_rules.py` (add), `backend/analysis/tests/test_tuning.py`

**Interfaces:**
- Produces, in `lusot_analysis.rules`:
  - `level_for_inches(depth_in: float) -> str`: the shallowest level whose upper limit is at or above the depth; above 45 in is `above_chest`. It raises `ValueError` for a depth of 0 or less, or one that isn't finite.
  - `round_out(depth_min: float, depth_max: float) -> tuple[float, float]` (C308): `math.floor(round(x * 10, 6)) / 10` for the min, and `math.ceil` the same way for the max
  - `@dataclass(frozen=True) class TireCode: code: str; width_mm: int; aspect: int; rim_in: int`, with `TireCode.parse(code: str) -> TireCode` (pattern `^(\d{3})/(\d{2})R(\d{2})C?$`, otherwise `ValueError`) and the property `radius_in: float`
  - `TIRE_CODES_VERSION: str` and `tire_codes(vehicle_type: str) -> tuple[TireCode, ...]`. The file is read once through `importlib.resources.files("lusot_analysis")`, never through a path built from `__file__`. `unknown` gets every listed code in file order, without repeats. A type the file doesn't list gets `()`.
  - `GEOMETRY_ONLY_TYPES: frozenset[str]`: the types with codes, minus `READING_TYPES` (C318)
- `tire_codes.json`: `{"version": "tire-codes-v1", "types": {<type>: [{"code", "vehicle", "source"}]}}` for `sedan_hatch`, `suv_mpv` and `van`, in the spec table's order. Each source is "plan Table 7", except the Mirage G4's: "verification notes §4 (Mitsubishi PH model page)". The Tamaraw isn't listed (G5).
- Produces, in `lusot_analysis.tuning`:
  - `@dataclass(frozen=True) class Tuning`, with these fields and start values:
    - `version: str`
    - `touch_tolerance_px: float = 5.0` (C301), `touch_share_min: float = 0.25` (C302), `ragged_iqr_share: float = 0.10` (C303, R86)
    - `daylight_brightness_min: float = 80.0` and `rim_score_min: float = 0.5` (C305)
    - `rim_size_low: float = 0.85` and `rim_size_high: float = 1.15`: check 9's factors (C305), tuned only on Set B development rims (C310; finding 1)
    - `rim_edge_k: float = 1.0` (G3)
    - `brightness_min: float = 40.0` and `sharpness_min: float = 25.0` (C44)
    - `min_wheel_side_px: int = 40` (C56), `max_vehicles: int = 6`, `max_people: int = 6` (C70)
    - `reasoning_effort: str | None = None` (C312). `None` sends no effort, so Muse Spark picks its own.
    - `drawing: str = "boxes-v1"` (C325): MS3a's drawing of the numbered boxes. C312's run may change it to `"boxes-v2"` (Task 7).
    - `untuned: frozenset[str] = frozenset()`: the names still at their start values
  - `START = Tuning(version="tuning-v1", untuned=<every field except version and untuned>)` and `TUNING = START`
  - The module docstring is the change log. Each version names its date, every value it changed with that value's development evidence (n and the harness figures used), or "untuned".
- Changes to MS3a:
  - `quality.BRIGHTNESS_MIN` and `SHARPNESS_MIN` become `TUNING.brightness_min` and `TUNING.sharpness_min`.
  - `quality_refusal(scores, tuning: Tuning = TUNING)` reads the tuning's two cutoffs, so a replay can raise them.
  - `references.MIN_WHEEL_SIDE_PX`, `MAX_VEHICLES` and `MAX_PEOPLE` alias `TUNING`'s values. They are checked on Manila photos, never swept (C310).

- [ ] **Step 1: Write the failing tests:**
  - `test_level_for_inches_follows_the_level_rule`, parametrized:
    - 0.1 and 5.0 → `below_gutter`
    - 5.01 and 8.0 → `gutter`
    - 8.01 and 10.0 → `half_knee`
    - 13.0 → `half_tire`; 13.01 and 19.0 → `knee`
    - 26.0 → `tire`, 37.0 → `waist`, 45.0 → `chest`, 45.01 → `above_chest`
  - `test_level_for_inches_rejects_impossible_depths`: 0.0, −1.0, `nan` and `inf` raise `ValueError`.
  - `test_round_out`: (8.291619, 8.793869) → (8.2, 8.8); (8.3, 8.3) → (8.3, 8.3); (7.0, 7.96) → (7.0, 8.0); (0.05, 0.05) → (0.0, 0.1).
  - `test_a_rebuild_never_lands_shallower` (C308): for 4.96, 5.0, 7.96, 8.0, 12.95, 13.0, 18.99 and 44.99, the level of `round_out(d, d)[1]` equals the level of `d`.
  - `test_tire_codes_match_the_spec`: the three lists exactly, in the spec's order. `unknown` has the 12 codes in the order sedan, SUV, van. `pickup`, `jeepney`, `tricycle`, `motorcycle` and `bus_truck` give `()`.
  - `test_tire_sizes_match_table_7`:
    - `TireCode.parse("175/65R14").radius_in == approx(11.4783, abs=1e-4)`, and `215/70R16C` gives 13.9252
    - per type, the min and max of `2 × radius_in`, rounded to 0.1: `sedan_hatch` (23.0, 24.4), `suv_mpv` (24.5, 26.7), `van` (27.9, 27.9), `unknown` (23.0, 27.9)
    - `TireCode.parse("265/60R18X")` raises `ValueError`
  - `test_every_code_names_its_source`: each entry has a non-empty `source`, and `TIRE_CODES_VERSION == "tire-codes-v1"`.
  - `test_geometry_only_types`: `GEOMETRY_ONLY_TYPES == {"van", "unknown"}`.
  - In `test_tuning.py`:
    - `test_start_values_are_the_specs`: every start value above, check 9's 0.85 and 1.15 and the drawing `boxes-v1` included, and `version == "tuning-v1"`
    - `test_untuned_values_are_still_their_start_values`: each name in `TUNING.untuned` is a field and equals `START`'s value
    - `test_ms3a_cutoffs_read_the_tuning_module`: the five MS3a constants equal `TUNING`'s values, and `quality_refusal(QualityScores(45.0, 100.0), replace(TUNING, brightness_min=50.0)) == "too_dark"`
    - `test_change_log_names_the_version`: `TUNING.version` appears in `tuning.__doc__`
- [ ] **Step 2:** Run `uv run pytest -q tests/test_rules.py tests/test_tuning.py`. Expected: the new tests FAIL.
- [ ] **Step 3:** Implement as specified. Write the JSON entries as plain lines, so a reviewer can check each against the spec table.
- [ ] **Step 4:** Run `uv run pytest -q`, then `uv run ruff check .`. Expected: PASS, with MS3a's tests unchanged; ruff clean.
- [ ] **Step 5:** Commit `feat(analysis): add the inch level rule, the tire codes and the tuning module`.

### Task 2: Step 3: the water edge, touch, the cut and raggedness

**Files:**
- Create: `backend/analysis/src/lusot_analysis/pipeline/waterline.py`
- Modify: `backend/analysis/tests/fakes.py` (add `wheel_scene`, and `instance(..., mask=None)`)
- Test: `backend/analysis/tests/test_waterline.py`

**Interfaces:**
- Consumes: `Tuning` (Task 1); `SamResult`
- Produces, in `lusot_analysis.pipeline.waterline` (spec §4 step 3; C301 to C303):
  - `@dataclass(frozen=True) class Waterline: y_w: float | None; touch_share: float; iqr_px: float | None; box_height: int; x_span: tuple[int, int] | None; cause: str | None`. The cause is `None`, `"no_water_contact"` or `"ragged_waterline"`. `x_span` is the first and last touching column, which the evidence record draws the waterline between (C328), or `None` when no column touches.
  - `water_mask(result: SamResult, shape: tuple[int, int]) -> np.ndarray`: the union of the instances' masks; all False when there are none
  - `find_waterline(obj: np.ndarray, water: np.ndarray, tuning: Tuning) -> Waterline`, by this algorithm (the tests don't fix it alone):

    ```python
    ys, xs = np.nonzero(obj)
    if ys.size == 0:
        return Waterline(None, 0.0, None, 0, None, "no_water_contact")
    top = ys.min(); height = ys.max() - top + 1
    T = tuning.touch_tolerance_px
    lower, edges, touching = 0, [], []
    for x in np.unique(xs):                    # each object column
        y_low = ys[xs == x].max()
        if y_low - top < 2 * height / 3:       # not a lower-outline column
            continue
        lower += 1
        for start, end in runs(water[:, x]):   # maximal runs of water, top down
            if start <= y_low + T and end >= y_low - T:
                edges.append(start)            # this run touches: its top is the edge
                touching.append(x)
                break
    if lower == 0:                             # a mask 1 or 2 px tall (finding 7)
        return Waterline(None, 0.0, None, height, None, "no_water_contact")
    share = len(edges) / lower
    y_w = float(np.median(edges)) if edges else None
    iqr = float(np.percentile(edges, 75) - np.percentile(edges, 25)) if edges else None
    x_span = (int(min(touching)), int(max(touching))) if touching else None
    cause = ("no_water_contact" if share < tuning.touch_share_min
             else "ragged_waterline" if iqr > tuning.ragged_iqr_share * height
             else None)
    ```

    The run that touches the lowest pixel gives the edge, not the water's top row anywhere in the column: flood water often wraps around a person or a car and shows above them.
  - `cut_at_waterline(mask: np.ndarray, y_w: float) -> np.ndarray`: a copy with every row at or below the edge (rows ≥ `y_w`) cleared
- Produces, in `tests/fakes.py`:
  - `wheel_scene(*, centre=(320, 240), tire_r=57, rim_r=35, y_true=257, seam=0, reflection="none", ripple=0, squash=1.0, size=SIZE) -> tuple[np.ndarray, np.ndarray, np.ndarray]`, returning the `(wheel, rim, water)` bool masks of a wheel:
    - The wheel and the rim are filled ellipses, with vertical semi-axis r and horizontal semi-axis `squash × r` (pixel centres inside). `squash` below 1 is a wheel seen at an angle. The masks hold the wheel's face only, so a test that needs the tread in the box sets the box itself. Both are kept on rows < `y_true`.
    - With `reflection` `"overlap"` or `"hole"`, both also hold their mirror image: row y maps to `2 × y_true − 1 − y`.
    - In column x, the water starts at row `y_true + seam + round(ripple × sin(x ÷ 7))`. For `"none"` and `"hole"`, the wheel's pixels are removed from it. For `"overlap"`, it keeps them.
  - `instance(...)` gains `mask: np.ndarray | None = None`, which overrides `mask_xyxy` when given.

- [ ] **Step 1: Write the failing tests.** The values come from a scratch run of the algorithm above on these scenes.
  - `test_seam_within_tolerance_touches` (C301, D3's seam), with `wheel_scene(y_true=250, seam=s)`:
    - s = 0 → `y_w == 250.0`, cause `None`
    - s = 3 → `253.0`; s = 4 → `254.0` (the distance is 5)
    - s = 5 → `no_water_contact`, `touch_share == 0.0`
  - `test_reflection_in_the_wheel_mask_is_cut` (W4, D3): `reflection="overlap"`, `y_true=250` gives cause `None`, `abs(y_w - 250) <= 2` (it is 250.0) and `box_height == 134`. `cut_at_waterline(wheel, y_w)` equals the wheel of `wheel_scene(y_true=250)` exactly.
  - Review Focus 1, `test_reflection_hole_edge_is_ragged` (R86): with `reflection="hole"`, the edge follows the reflection's round bottom. Each case is `ragged_waterline`, with `touch_share == 1.0`:
    - `y_true=240` (the hub): `y_w == 290.0`, `iqr_px == 15.0`, `box_height == 114` (13.2%)
    - `y_true=250`: `y_w == 309.0`, `iqr_px == 16.5`, `box_height == 134` (12.3%)
    - `y_true=230`: `y_w == 271.0`, `iqr_px == 13.0`, `box_height == 94` (13.8%)
  - Review Focus 1, `test_flat_waterlines_pass` (R86):
    - `wheel_scene(y_true=250)` → `iqr_px == 0.0`, cause `None`
    - `reflection="overlap"`, `y_true=250`, `ripple=1` → `iqr_px == 2.0` with `box_height == 134` (1.5%), cause `None`, `y_w == 250.0`
  - `test_touch_share_boundary` (C302): an object on rows 200 to 239 and columns 300 to 359. The water is rows ≥ 240 under its first n columns and rows ≥ 260 under the rest.
    - n = 15 → `touch_share == 0.25`, cause `None`
    - n = 14 → 0.2333…, `no_water_contact`
  - `test_umbrella_columns_are_not_lower_outline` (C302): legs on rows 200 to 299 and columns 300 to 319, an umbrella on rows 200 to 214 and columns 260 to 359, and water on rows ≥ 296 outside the object. The result is cause `None`, `touch_share == 1.0` and `y_w == 300.0`. Counting every column would give 0.2 and drop the person.
  - `test_ragged_boundary` (C303, R86): the object on rows 200 to 239 and columns 300 to 359, with water tops alternating 236 and 236 + D by column.
    - D = 4 → `iqr_px == 4.0` (10% of 40), cause `None`, `y_w == 238.0`
    - D = 5 → `ragged_waterline`
  - `test_far_water_above_the_object_is_ignored` (plan §7 step 3): the legs as above, water on rows ≥ 300, plus a band on rows 100 to 180 over the same columns → `y_w == 300.0`.
  - `test_no_water_and_empty_masks`: no water → `no_water_contact` with `y_w is None` and `x_span is None`; an empty object mask → `no_water_contact` with `box_height == 0`.
  - `test_thin_masks_have_no_water_contact` (finding 7): objects 1 px and 2 px tall, with water right below them, give `no_water_contact` with `touch_share == 0.0`, and no error.
  - `test_waterline_span` (C328): the object on rows 200 to 239 and columns 300 to 359, with water on rows ≥ 240 under columns 310 to 349 only → cause `None`, `touch_share == 40 / 60`, `y_w == 240.0` and `x_span == (310, 349)`.
  - `test_water_mask_is_the_union`: two `floodwater` instances give their union; no instances give all False in the given shape.
- [ ] **Step 2:** Run `uv run pytest -q tests/test_waterline.py`. Expected: FAIL.
- [ ] **Step 3:** Implement `waterline.py` and the two fakes.
- [ ] **Step 4:** Run `uv run pytest -q`, then `uv run ruff check .`. Expected: PASS; clean.
- [ ] **Step 5:** Commit `feat(analysis): add step 3, the water edge with the touch check and the cut`.

### Task 3: Rim linking, the rim fit, the checks and the formula

**Files:**
- Create: `backend/analysis/src/lusot_analysis/pipeline/geometry.py`
- Test: `backend/analysis/tests/test_geometry.py`

**Interfaces:**
- Consumes: `Tuning`, `TireCode`, `tire_codes`, `level_for_inches` (Task 1); `Waterline`, `cut_at_waterline`, `find_waterline` (Task 2); `link_wheels`, `box_xyxy` (MS3a); `Reading`, `WHEEL_ROWS`, `disagree`
- **OpenCV facts** (Context7's OpenCV 4.13 docs, checked on the locked 4.14.0):
  - `cv2.fitEllipse(points)` returns `((cx, cy), (w, h), angle)`: the rotated rectangle the ellipse is inscribed in.
    - `w` and `h` are full axis lengths in no fixed order, so `r = max(w, h) / 2`, and the ratio is min over max.
    - `w` lies along `angle` (in degrees) and `h` across it: an ellipse with semi-axes 40 (along x) and 20 gave `(40.1, 80.1)` at 90°.
    - So the horizontal extent is `width_x = sqrt((w × cos θ)² + (h × sin θ)²)`, with θ = `angle` in radians. It gave 80.1 for that ellipse, and 72.2 for the same ellipse turned 30°, whose mask is 73 px wide.
  - Points are int32 or float32. Fewer than 5 raise `cv2.error`, so `fit_rim` checks the count first. Five collinear points return a sliver (minor axis 0.02), not an error.
  - `cv2.findContours(mask_u8, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)` returns `(contours, hierarchy)`. Each contour is an (N, 1, 2) int32 array of every outer boundary pixel `(x, y)`. Points are pixel centres, so a filled disk of radius 35 fits r ≈ 34.6.
- Produces, in `lusot_analysis.pipeline.geometry`:
  - `MIN_FIT_POINTS = 5` and `MIN_AXIS_RATIO = 0.5` (spec values, not tuned). Check 9's factors are `Tuning.rim_size_low` and `rim_size_high` (finding 1).
  - `GEOMETRY_CAUSES`, in check order: `("waterline_not_visible", "no_tire_codes", "rim_missing", "rim_several", "waterline_dropped", "not_daylight", "rim_score_low", "rim_fit_points", "rim_fit_off_wheel", "rim_axis_ratio", "water_above_hub", "rim_size", "depth_not_positive")`
  - `rim_size_bounds(codes: Sequence[TireCode], axis_ratio: float, tuning: Tuning) -> tuple[float, float]` (check 9, R91): `tuning.rim_size_low × min` and `tuning.rim_size_high × max`, over the codes, of `rim_in × c ÷ (D × c + W × s)`. Here `c = axis_ratio`, `s = √(1 − c²)`, `D = 2 × radius_in` and `W = width_mm ÷ 25.4`.
  - `link_rims(wheels: Sequence[SamInstance], rims: Sequence[SamInstance]) -> list[tuple[SamInstance, ...]]` (C300): for each wheel, the rims that `link_wheels(wheels, rims)` assigns to it. That reuses C55's rule: the one wheel whose box holds the rim box's centre, edges included.
  - `@dataclass(frozen=True) class RimFit: centre_x: float; centre_y: float; r: float; axis_ratio: float; width_x: float; axes: tuple[float, float]; angle_deg: float; points: int`. `width_x` is the fit's horizontal extent, by the formula above (R89). `axes` and `angle_deg` are `cv2.fitEllipse`'s own full axes, in its order, and its angle, kept so the evidence record can draw the fit (C328).
  - `rim_points(rim_mask: np.ndarray, y_w: float, tolerance_px: float) -> np.ndarray`: the outer contour points (N × 2 int32, `(x, y)`) of `cut_at_waterline(rim_mask, y_w)`, over every contour, keeping `y < y_w − tolerance_px`
  - `fit_rim(points: np.ndarray) -> RimFit | None`: `None` with fewer than 5 points, or when the centre or an axis isn't finite or an axis isn't positive
  - `check_fit(fit: RimFit, *, wheel_box: tuple[float, float, float, float], y_w: float, codes: Sequence[TireCode], tuning: Tuning) -> str | None`: `rim_fit_off_wheel`, then `rim_axis_ratio`, then `water_above_hub`, then `rim_size` when `fit.width_x ÷ (x1 − x0)` lies outside `rim_size_bounds(codes, fit.axis_ratio, tuning)` (bounds included; R89, R91)
  - `depth_inches(code: TireCode, *, centre_y: float, r: float, y_w: float, k: float) -> float`: the spec's formula
  - `@dataclass(frozen=True) class GeometryReading: depth_in_min: float; depth_in_max: float; level: str; fit: RimFit | None = None`. `measure_rim` sets `fit`, so Set B takes its point estimate from the same fit.
  - `geometry_reading(depths: Sequence[float]) -> GeometryReading | str`: `depth_not_positive` when any depth is 0 or less (C306); otherwise the min, the max, and `level_for_inches(max)`
  - `measure_rim(rim: SamInstance, *, y_w: float, wheel_box: tuple[float, float, float, float], brightness: float, codes: Sequence[TireCode], tuning: Tuning) -> GeometryReading | str`: checks 4 to 9 and C306, with `k = tuning.rim_edge_k`. A fit of `None` is `rim_fit_points`.
  - `wheel_geometry(*, answer_waterline: str, codes: Sequence[TireCode], rims: Sequence[SamInstance], waterline: Waterline | None, wheel_box: tuple[float, float, float, float], brightness: float, tuning: Tuning) -> GeometryReading | str`: checks 1 to 3, then the waterline (`None` or with a cause gives `waterline_dropped`), then `measure_rim`
  - `@dataclass(frozen=True) class KeptReading: reading: Reading; level_from: Literal["landmark", "geometry"]; depth_in: tuple[float, float] | None`
  - `keep_reading(landmark: Reading | None, geometry: GeometryReading | None) -> KeptReading | Literal["wheel_methods_disagree"] | None` (G4, C307). Geometry's reading is exact. With both readings:
    - `disagree([landmark, geometry's])` → `"wheel_methods_disagree"`
    - otherwise the deeper, and an equal level counts as geometry

- [ ] **Step 1:** Write `test_fit_ellipse_facts_on_this_opencv`, then run it before writing any code: a disk mask of radius 35 at (320, 240) fits a centre within 0.5 px and r within 1.0 of 35; a filled ellipse with semi-axes 40 and 20 gives `max(w, h) / 2` within 1 of 40, a ratio within 0.02 of 0.5, and `width_x` within 1 of 80; turned 30°, `width_x` is within 1 of 72.1; 4 points raise `cv2.error`. Expected: PASS. If it fails, stop: the OpenCV facts above are wrong for this version, and the controller rules on them before anything else.
- [ ] **Step 2: Write the failing tests:**
  - `test_link_rims_by_centre` (C300): wheels A `(100, 100, 200, 200)` and B `(180, 100, 280, 200)`. Rims centred at:
    - (140, 150) → A, and (240, 150) → B
    - (190, 150) → neither (it is inside both); (400, 150) → neither
    - a second rim at (120, 150) → A then holds two rims
  - `test_fit_needs_five_points` (check 6): 4 points on a circle give `None` without raising; 5 points on a circle of radius 30 give `r == approx(30, abs=0.01)`, with both `axes` within 0.02 of 60.
  - `test_rim_points_skip_the_cut_edge` (spec §4 step 5): `wheel_scene(y_true=257)`'s rim with `y_w = 257` gives points all with y < 252, and a fit with its centre at (320.0, 239.6) ± 0.5 and `r == approx(34.5, abs=0.5)`.
  - `test_formula_hand_computed` (Table 7; exact to 1e-4):
    - 175/65R14, `r=35, k=1.0, centre_y=200, y_w=220`: s = 5.0, R = 11.4783, depth 7.4783 (7.5 in) → `gutter`
    - 215/70R16C, `r=40, k=1.0, centre_y=300, y_w=300`: depth 13.9252 (13.9 in) → `knee`. At the hub, the Hiace reads knee, where Table 8's hub row says half-tire (G4).
    - 195/55R16, `r=42, k=1.05, centre_y=100, y_w=110`: s = 5.0, depth 10.2224 (10.2 in) → `half_tire`
  - `test_envelope_over_the_sedan_codes`: `r=35, k=1.0, centre_y=200, y_w=215` over `tire_codes("sedan_hatch")` gives 8.4783, 8.2916, 8.6558 and 8.7939. `geometry_reading` gives min 8.2916, max 8.7939 and `half_knee`, which `round_out` stores as 8.2 and 8.8.
  - `test_depth_not_positive_boundary` (C306): `geometry_reading([0.0, 3.0]) == "depth_not_positive"`; `[0.01, 3.0]` gives `GeometryReading(0.01, 3.0, "below_gutter")`.
  - `test_rim_size_bounds_from_the_codes` (R88, R91), hand-computed as `rim × c ÷ (D × c + W × s)`, with `TUNING`. All values to 1e-4.
    - **`sedan_hatch` at axis ratio 1.0** (s = 0, so the ratio is rim ÷ D): 175/65R14 gives 14 ÷ 22.9567 = 0.6098; 185/55R15, 15 ÷ 23.0118 = 0.6518; 185/60R15, 15 ÷ 23.7402 = 0.6318; 195/55R16, 16 ÷ 24.4449 = 0.6545. Bounds: 0.85 × 0.6098 = 0.5184 and 1.15 × 0.6545 = 0.7527.
    - **`sedan_hatch` at axis ratio 0.6** (s = 0.8; W = 6.8898, 7.2835, 7.2835 and 7.6772 in):
      - 175/65R14: 8.4 ÷ (13.7740 + 5.5118) = 0.4356
      - 185/55R15: 9.0 ÷ (13.8071 + 5.8268) = 0.4584
      - 185/60R15: 9.0 ÷ (14.2441 + 5.8268) = 0.4484
      - 195/55R16: 9.6 ÷ (14.6669 + 6.1417) = 0.4613
      - Bounds: 0.85 × 0.4356 = 0.3702 and 1.15 × 0.4613 = 0.5306.
    - **The other types at 1.0:** `suv_mpv` (0.5134, 0.7555), `van` (0.4883, 0.6607), `unknown` (0.4883, 0.7555).
  - `test_check_fit_boundaries`: the base is `RimFit(centre_x=320.0, centre_y=240.0, r=35.0, axis_ratio=0.9, width_x=70.0, axes=(70.0, 63.0), angle_deg=0.0, points=50)` with wheel box `(263, 183, 378, 257)`, `y_w = 257`, the sedan codes and `TUNING` → `None`. Its rim size, 70 ÷ 115 = 0.6087, lies inside the bounds at 0.9, which are 0.4526 to 0.6533. Then:
    - `axis_ratio` 0.5, with `width_x` 48.0 → `None`: 48 ÷ 115 = 0.4174 lies inside that ratio's bounds of 0.3411 to 0.4875 (finding 3; 70.0 would fail check 9 there). `axis_ratio` 0.4999 → `rim_axis_ratio`.
    - `y_w` 240.0 → `None` (at the hub); 239.99 → `water_above_hub`
    - `centre_x` 263.0 → `None` (on the edge); 262.99 → `rim_fit_off_wheel`
    - check 9 (R88, R89, R91), with `axis_ratio=1.0` (bounds 0.51837 and 0.75271) and wheel box `(300, 183, 400, 257)` (width 100, so the rim size is `width_x ÷ 100`): `width_x` 51.86 → `None`; 51.82 → `rim_size`; 75.26 → `None`; 75.28 → `rim_size`
  - `test_check_9_factors_come_from_the_tuning` (finding 1): with axis ratio 1.0, wheel box `(300, 183, 400, 257)` and `width_x` 50.0 (a rim size of 0.50), `check_fit` gives `rim_size` under `TUNING` (lower bound 0.51837), and `None` under `replace(TUNING, rim_size_low=0.80)` (lower bound 0.80 × 0.60984 = 0.48787).
  - `test_an_angled_rim_passes_checks_7_and_9` (R89, R91): a 175/65R14 wheel at 5 px per inch, seen at axis ratio 0.6.
    - **The box.** It takes in the tread: the face is D × cos φ = 114.78 × 0.6 = 68.87 px, plus W × sin φ = 34.45 × 0.8 = 27.56 px of tread on one side. So the box is `(258.01, 183, 354.44, 257)`, 96.43 px wide.
    - **The fit.** The rim of `wheel_scene(y_true=257, squash=0.6)` with `y_w = 257` fits `w` 40.77 and `h` 68.15 at angle 0. So `axis_ratio` is 0.598 (check 7 passes), and `width_x` 40.77 gives a rim size of 0.4228.
    - **The checks.** At the fit's axis ratio, the sedan bounds are 0.3697 to 0.5298, so check 9 passes. `measure_rim` measures, with min and max within 0.02 of 7.676 and 8.137.
    - Against the side-on bounds (0.5184 to 0.7527), the same rim would fail. That is why the bounds follow the viewing angle.
  - `test_measure_rim_checks` (C305), on `wheel_scene(y_true=257)`'s rim (score 0.9), `y_w = 257`, wheel box `(263, 183, 378, 257)`, the sedan codes and brightness 128.0:
    - it passes, with min and max within 0.02 of 7.720 and 8.184, and `half_knee`
    - brightness 79.99 → `not_daylight`; 80.0 passes
    - score 0.49 → `rim_score_low`; 0.5 passes; `None` → `rim_score_low`
    - `y_w = 209`, which leaves no point above `y_w − T` → `rim_fit_points`
  - `test_wheel_geometry_checks_in_order`:
    - a `not_visible` wheel with no codes and no rims → `waterline_not_visible`
    - no codes → `no_tire_codes`; no rim → `rim_missing`; two rims → `rim_several`
    - waterline `None`, or one whose cause is `no_water_contact` → `waterline_dropped`
  - `test_keep_reading_follows_g4` (G4, C307, C320), parametrized. "geo L" is `GeometryReading(d, d, L)`, with d = 4.0 for below_gutter, 9.0 for half_knee, 12.0 for half_tire and 15.0 for knee.
    - `hub` (half_tire) and `None` → the landmark
    - `None` and geo half_knee → geometry, `depth_in == (9.0, 9.0)`
    - `rim_quarter` (half_knee) and geo half_knee → geometry (equal counts as geometry)
    - `hub` and geo knee → geometry; `rim_quarter` and geo half_tire → geometry
    - `hub` and geo half_knee → the landmark
    - `hub` and geo below_gutter → `"wheel_methods_disagree"`
    - `wheel_covered` (tire, a floor) and geo knee → the landmark floor; with geo half_tire → `"wheel_methods_disagree"`
    - `None` and `None` → `None`
  - Review Focus 1, `test_reflection_hole_gets_no_geometry_reading` (R86; this was a strict xfail before C303's change). For each of Task 2's three hole scenes (`y_true` 240, 250 and 230), `find_waterline` gives `ragged_waterline` with Task 2's exact values. `wheel_geometry` with that waterline, the scene's rim, the wheel mask's box and brightness 128 then gives `waterline_dropped`, for the `sedan_hatch` and the `van` codes alike. Without step 3, `measure_rim` at the hub with `y_w = 290` would read `below_gutter` (0.494 to 1.216 in) and pass check 9 (0.610). G4 would still drop a sedan's wheel: `keep_reading(WHEEL_ROWS["hub"], that) == "wheel_methods_disagree"`.
  - Review Focus 2, `test_hubcap_and_whole_wheel_rims_fail_rim_size` (R88), on `wheel_scene(y_true=257)` with `y_w = 257`, wheel box `(263, 183, 378, 257)` (width 115) and the sedan codes:
    - `rim_r=17.5` (a hubcap): axis ratio 0.9988, `width_x` 34.33, a rim size of 0.2985, against bounds 0.5108 to 0.7412 → `rim_size`
    - `rim_r=57` (the whole wheel): 0.9895, `width_x` 112.76, 0.9805, against 0.4966 to 0.7197 → `rim_size`
    - `rim_r=35` (the true rim): 0.9894, `width_x` 68.99, 0.5999, against 0.4965 to 0.7196 → passes
    - each within 0.002, with `START`'s factors
    - under `TUNING` too, the hubcap and the whole wheel still give `rim_size`, so a tuned factor can't let them through (S3, P4). They would pass only with `rim_size_low` at 0.4967 or below, or `rim_size_high` at 1.5667 or above, hence the limits of 0.50 and 1.55.
    - `keep_reading(WHEEL_ROWS["rim_quarter"], None)` keeps the landmark, so a failed rim leaves the wheel its landmark reading
- [ ] **Step 3:** Run `uv run pytest -q tests/test_geometry.py`. Expected: FAIL, except the Step 1 test.
- [ ] **Step 4:** Implement `geometry.py`.
- [ ] **Step 5:** Run `uv run pytest -q`, then `uv run ruff check .`. Expected: PASS; clean.
- [ ] **Step 6:** Commit `feat(analysis): add rim geometry with its checks, the formula and G4`.

### Task 4: Results that carry their source and inches

**Files:**
- Modify: `backend/analysis/src/lusot_analysis/pipeline/types.py`, `backend/analysis/src/lusot_analysis/pipeline/combine.py`
- Test: `backend/analysis/tests/test_pipeline_types.py`, `backend/analysis/tests/test_combine.py`, `backend/analysis/tests/test_report_store.py`, `backend/analysis/tests/test_handler.py`

**Interfaces:**
- Consumes: `level_for_inches`, `round_out` (Task 1)
- Produces:
  - `Reference` gains `level_from: Literal["landmark", "geometry"] = "landmark"`, `depth_in: tuple[float, float] | None = None` (unrounded min and max) and `decides: bool = True`. False means step 3 dropped it: it can refuse the photo but never decide it (C317).
  - `Outcome` gains `level_from: Literal["landmark", "geometry"] | None = None`, `depth_in_min: float | None = None` and `depth_in_max: float | None = None`. `__post_init__` checks:
    - On a level result, `None` becomes `"landmark"` through `object.__setattr__`, so MS3a's direct constructions keep working. Any other value than the two raises.
    - The inches come both or neither. They come exactly when `level_from == "geometry"`, with `0 < min <= max`, both finite, and `level == level_for_inches(depth_in_max)`.
    - Outcomes that aren't level results carry none of the three.
  - `Outcome.level_result(level, landmark, level_is_floor, basis, *, level_from="landmark", depth_in=None)`
  - `item_fields()` on a level result adds `"levelFrom"`, and with geometry `"depthInMin"` and `"depthInMax"` from `round_out` (C308, C320)
  - `combine(references)` keeps its signature. In this order:
    1. Only references with `decides` can decide. With none → `no_usable_reference`, whatever was dropped.
    2. C54's test runs over the deciding readings only, as in MS3a → `references_disagree`.
    3. The level is the deepest deciding reading, and `level_is_floor` is set as in MS3a. If the result is exact and any non-deciding reading's level is deeper, by level index → `references_disagree` (C317 as amended, R87). A floor result stands (R90), and so does a result no dropped reading exceeds.
    4. The tie order, `level_is_floor` and `basis` come from the deciding references only. `level_from`, and the inches when it is `"geometry"`, come from the deciding reference (C307).

- [ ] **Step 1: Write the failing tests:**
  - `test_landmark_results_record_their_source` (C320): `Outcome.level_result("knee", ...)` and MS3a's direct `Outcome("done", level=...)` both have `level_from == "landmark"`. Update `test_outcome_item_fields`: the knee dict gains `"levelFrom": "landmark"`.
  - Update MS3a's other tests that compare a stored level result field by field, since the item gains `levelFrom` (finding 3; moved here from the handler task): `test_writes_a_level_result_under_the_claim` (`test_report_store.py`) and the `KNEE` item in `test_handler.py` each gain `"levelFrom": {"S": "landmark"}`. `write_result` already stores a `str` as `{"S": ...}`, so no code changes for it.
  - `test_geometry_result_stores_rounded_inches` (C308): `level_result("half_knee", "rim_quarter", False, {"vehicles": 1, "people": 0}, level_from="geometry", depth_in=(8.291619, 8.793869))`. Its `item_fields()` equals MS3a's level dict for these values, plus `"levelFrom": "geometry"`, `"depthInMin": 8.2` and `"depthInMax": 8.8`.
  - `test_outcome_rejects_bad_inch_shapes`, parametrized; each raises `ValueError`:
    - inches with `level_from="landmark"`; geometry without inches; only one of the two
    - min above max; min of 0; `level="knee"` with max 8.8
    - inches on a refusal; `level_from` on no flood seen
  - `test_geometry_deciding_reference_brings_its_inches` (C307): a lone geometry wheel reference at `half_knee` with `depth_in` (8.29, 8.79) gives `level_from == "geometry"` and those inches.
  - Review Focus 4, `test_a_person_reading_deeper_decides_without_inches`:
    - a geometry wheel at `half_knee` (8.29, 8.79) and a person at `knee` → `references_disagree`
    - a geometry wheel at `half_tire` (11.08, 11.77) and a person at `knee` → `knee`, landmark `knee`, `level_from == "landmark"`, no inches
    - a geometry wheel (box 3) at `knee` (13.47, 13.47) and a person (box 9) at `knee` → the wheel decides (C54), with `level_from == "geometry"` and its inches
  - `test_geometry_ties_follow_c54`: a geometry wheel 3 and a landmark wheel 5 (`hub`), both at `half_tire` → box 3 decides, with inches. Swap the boxes → box 3 (landmark) decides, without inches.
  - `test_dropped_readings_refuse_only_when_deeper` (C317 as amended, R87 and R90):
    - a kept wheel at `hub` (half_tire, exact) and a dropped person at `knee`, one level deeper → `references_disagree`
    - a kept person at `knee` (exact) and a dropped person at `waist` → `references_disagree`
    - a kept `wheel_covered` floor (tire) and a dropped person at `waist` → `tire`, with `level_is_floor` true. A floor already means "this level or deeper" (R90).
    - a kept person at `knee` and a dropped wheel at `rim_three_quarters` (knee, the same level) → `knee`, with basis 0 vehicles and 1 person
    - a kept person at `chest` and a dropped `window` body (a tire floor, below) → `chest`
    - a kept wheel at `hub` and a dropped wheel at `tire_only`, three levels below → `half_tire`. MS3a's C54 would refuse that gap between two kept readings, but a dropped reading never refuses from below.
    - only dropped readings → `no_usable_reference`
  - MS3a's `test_result_ignores_input_order` gains a mixed list with non-deciding references.
- [ ] **Step 2:** Run `uv run pytest -q tests/test_pipeline_types.py tests/test_combine.py tests/test_report_store.py tests/test_handler.py`. Expected: the new and updated tests FAIL.
- [ ] **Step 3:** Implement as specified.
- [ ] **Step 4:** Run `uv run pytest -q`, then `uv run ruff check .`. Expected: PASS; clean. Every other MS3a test passes unchanged.
- [ ] **Step 5:** Commit `feat(analysis): carry each result's source and its inches, and let dropped readings refuse`.

### Task 5: Readings per wheel: G4, geometry-only types and step 3's drops

**Files:**
- Modify: `backend/analysis/src/lusot_analysis/pipeline/references.py` (`KeptVehicle`, `apply_drops`), `backend/analysis/src/lusot_analysis/pipeline/measure.py`
- Test: `backend/analysis/tests/test_apply_drops.py`, `backend/analysis/tests/test_measure.py`

**Interfaces:**
- Consumes: `GEOMETRY_ONLY_TYPES` (Task 1); `GeometryReading`, `keep_reading` (Task 3); the new `Reference` fields (Task 4)
- Produces:
  - `KeptVehicle` gains `vehicle_type: str = "sedan_hatch"` as its last field. `apply_drops` always sets it, and the default keeps MS3a's constructions working.
  - `apply_drops(answer, layout, *, geometry_types: frozenset[str] = frozenset())`: a vehicle is kept when its type is in `READING_TYPES | geometry_types`. The pipeline passes `GEOMETRY_ONLY_TYPES` when geometry is on (C318, which narrows C45).
  - `measure(kept, *, step3_drops: Mapping[int, str] | None = None, geometry: Mapping[int, GeometryReading] | None = None) -> tuple[list[Reference], Counter[str]]`. `step3_drops` maps a box id (a wheel's, a person's, or a vehicle's for its body) to its step 3 cause. `geometry` maps a wheel id to its reading. Both default to none, which is MS3a's behaviour.
    - **Each vehicle, in order:**
      1. C53's drop is unchanged.
      2. Each wheel: the landmark is `WHEEL_ROWS[w]` for `READING_TYPES`, and `None` for geometry-only types.
         - A wheel in `step3_drops` gives a non-deciding `Reference` with its landmark reading, if it has one. It counts under its cause.
         - Otherwise `keep_reading(landmark, geometry.get(id))` gives a reading with `level_from` and `depth_in`, or `wheel_methods_disagree` (counted; the wheel gives nothing), or nothing.
      3. C43 runs over the deciding wheel readings.
      4. The body is read only for `READING_TYPES` (C53). A body in `step3_drops` gives a non-deciding reference and counts under its cause.
      5. The deepest deciding candidate speaks, with C54's tie order. A vehicle dropped by C53 or C43 gives no references, deciding or not.
    - **Counting:** each box counts once, after its vehicle's fate is known. A vehicle that C53 or C43 drops counts each of its answered wheels as `wheel_vehicle_dropped`, as in MS3a, whatever step 3 or G4 found for them.
    - **Each person:** in `step3_drops`, a non-deciding reference counted under its cause; otherwise as in MS3a.
    - `landmark` is always Muse Spark's category (C320). For a van, it is the answered waterline.
- On real photos, the type rules here are checked by Task 16's type check on the Commons PUV photos (C323, W14).

- [ ] **Step 1: Write the failing tests:**
  - `test_vans_and_unknown_are_kept_only_for_geometry` (C318): with `geometry_types=GEOMETRY_ONLY_TYPES`, `van` and `unknown` are kept with their `vehicle_type`, while `pickup`, `jeepney`, `tricycle`, `motorcycle` and `bus_truck` drop as `vehicle_type`. Without it, `van` and `unknown` drop as in MS3a.
  - `test_kept_vehicles_carry_their_type`: `sedan_hatch` and `suv_mpv` keep theirs.
  - `test_geometry_only_types_read_from_geometry`:
    - a van with wheel 5 at `hub` and `{5: GeometryReading(13.47, 13.47, "knee")}` → `Reference("wheel", 5, "hub", Reading("knee", False), level_from="geometry", depth_in=(13.47, 13.47))`
    - the same van without geometry → `vehicle_no_reading`
    - a van whose wheels are hidden, with a `window` body → `vehicle_no_reading`, because C53 is for sedans and SUVs only
  - `test_g4_through_measure` (G4, C320):
    - a sedan wheel at `hub` with geometry `knee` → a geometry reference whose landmark is `hub`
    - with geometry `below_gutter` → `wheel_methods_disagree` 1 and `vehicle_no_reading` 1, and no reference
  - `test_step3_drops_keep_the_reading_for_c317` (C317):
    - sedan wheel 4 at `rim_top` dropped as `no_water_contact` → `Reference("wheel", 4, "rim_top", Reading("tire", False), decides=False)`, with `no_water_contact` 1 and `vehicle_no_reading` 1
    - a person dropped as `ragged_waterline` → a non-deciding person reference
    - a hidden-wheel sedan whose `window` body is dropped → a non-deciding body reference
  - `test_a_dropped_wheel_still_counts_as_visible` (C317, C53): a sedan with a `window` body and its only wheel at `hub`, dropped by step 3 → no body reading; only the non-deciding wheel reference.
  - `test_a_dropped_vehicle_gives_nothing`: a C53-dropped vehicle whose wheel step 3 also dropped → no references at all, with `vehicle_body_below_covered_wheel` 1, `wheel_vehicle_dropped` 1, and no step 3 cause counted.
  - `test_a_c43_dropped_vehicle_gives_nothing` (finding 8): a sedan with wheels 4 at `hub` and 5 at `tire_only` (three levels apart, so C43 drops it) and wheel 6 at `rim_top`, dropped by step 3 → no references at all, not even wheel 6's non-deciding one, with `vehicle_wheels_disagree` 1, `wheel_vehicle_dropped` 3, and no step 3 cause counted.
- [ ] **Step 2:** Run `uv run pytest -q tests/test_apply_drops.py tests/test_measure.py`. Expected: the new tests FAIL.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** Run `uv run pytest -q`, then `uv run ruff check .`. Expected: PASS; MS3a's tests unchanged; clean.
- [ ] **Step 5:** Commit `feat(analysis): read wheels by G4, keep vans for geometry and keep step 3's drops for C317`.

### Task 6: The pipeline: step 3 after the gate, `geometry_in_level` and logs

**Files:**
- Modify:
  - `backend/analysis/src/lusot_analysis/pipeline/__init__.py`
  - `backend/analysis/src/lusot_analysis/pipeline/references.py` (add `instances_by_id`)
  - `backend/analysis/tests/fakes.py`
- Test: `backend/analysis/tests/test_pipeline.py`, and any MS3a test Step 4 lists

The reasoning effort is Task 7's (finding 10), and the evidence record is Task 8's.

**Interfaces:**
- Consumes: Tasks 1 to 5
- Produces:
  - `references.instances_by_id(prepared: Prepared, layout: Layout) -> dict[int, SamInstance]`: the k-th numbered box of a kind is the k-th kept instance of its phrase, since `number_boxes` keeps SAM's order
  - `run_pipeline(data, client, prompt, *, phrases=SAM_PHRASES, deadline=None, geometry_in_level: bool = False, tuning: Tuning = TUNING) -> PipelineRun`:
    - **Steps 0 to 4.5** are unchanged, except that step 1 uses `quality_refusal(scores, tuning)`.
    - **Step 4.6:** `apply_drops(..., geometry_types=GEOMETRY_ONLY_TYPES if geometry_in_level else frozenset())`.
    - **Step 3 (C317, after the gate):** `water = water_mask(sam["floodwater"], (image.height, image.width))`. Then `find_waterline(instance.mask, water, tuning)` runs for:
      - each kept vehicle's wheels answered other than `not_visible`
      - each kept person whose `PEOPLE_ROWS` reading isn't `None`
      - each kept `READING_TYPES` vehicle whose body gives a reading (`wheels_hidden`, and `BODY_ROWS[body]` isn't `None`)

      Every Waterline with a cause enters `step3_drops`.
    - **Steps 4 and 5, only with geometry on:**
      - `link_rims(sam["wheel"].instances, sam["wheel rim"].instances)`, over all of SAM's wheels before the cuts, as C55 links wheels among all of SAM's vehicles (P14). So a rim inside a cut wheel's box never joins a kept wheel. Each kept wheel then takes its own rims.
      - for every wheel of a kept vehicle: `wheel_geometry(answer_waterline=..., codes=tire_codes(vehicle_type), rims=..., waterline=..., wheel_box=box_xyxy(instance), brightness=scores.brightness, tuning=tuning)`
    - **Then** `measure(kept, step3_drops=..., geometry=...)` and `combine`, as before.
  - **New log keys (C316):**
    - always: `geometry_in_level` (`"on"` or `"off"`), `tuning_version` and `rim_edge_k`
    - with geometry on: `wheels_measured` and `geometry_checks` (`{cause: count}`)
    - on level results: `level_from`, plus `depth_in` (`[min, max]`, rounded out) when it is `"geometry"`
    - step 3's causes and `wheel_methods_disagree` join `drops`
- Produces, in `tests/fakes.py`: `geometry_case(vehicle_type="sedan_hatch", waterline="rim_quarter") -> tuple[bytes, dict[str, SamResult], dict]`, the photo, SAM results and answer below. Tasks 7 to 10 and 12 reuse it.
  - the photo is `noise_jpeg()`
  - from `wheel_scene(y_true=257)`, built with `instance(..., mask=...)`: `wheel` box `(263, 183, 378, 257)`, `wheel rim` box `(285, 205, 356, 257)` and `floodwater` box `(0, 257, 640, 480)`. `vehicle` is `(150, 100, 500, 300)`. Other phrases are empty.
  - the answer: vehicle 1 of the given type, not moving, body `not_visible`; wheel 2 at the given waterline

- [ ] **Step 1: Write the failing tests:**
  - `test_geometry_result_end_to_end`, with `geometry_case()` and `geometry_in_level=True`:
    - the outcome is `half_knee`, landmark `rim_quarter`, `level_from == "geometry"`, with `depth_in_min` and `depth_in_max` within 0.02 of 7.720 and 8.184
    - `item_fields()` has `depthInMin` 7.7 and `depthInMax` 8.2
    - the log has `wheels_measured == 1`, `geometry_checks == {}`, `tuning_version == "tuning-v1"`, `rim_edge_k == 1.0` and `depth_in == [7.7, 8.2]`
    - still 7 `segment` calls and 1 `judge`, so geometry made no new Meta call
  - `test_geometry_off_is_ms3a_plus_step3` (C309), with `geometry_case("van")`:
    - off: `no_usable_reference`, with `drops["vehicle_type"] == 1` and no `wheels_measured` key
    - on: `half_knee` from geometry, with depths within 0.02 of 9.887
  - `test_step3_runs_after_the_gate` (C317): `geometry_case()` with an empty `floodwater` and the answer's water `no` → `water_unsure` from the gate, and step 3 adds no drop.
  - `test_a_dry_reference_refuses_rather_than_reads_shallow` (C317): `level_case()` plus person 3, box `(450, 50, 480, 200)`, answered at `waist`. No water reaches the person, so the result is `references_disagree`, with `drops["no_water_contact"] == 1`.
  - `test_a_dry_standing_adult_still_blocks_wading_adults` (C317, C57; finding 8): `level_case()` plus person 3 (box `(450, 50, 480, 200)`, an adult standing still, at `knee`, with no water near) and person 4 (box `(520, 150, 560, 280)`, an adult not standing still, at `knee`). Person 4 drops as `person_wading`, before step 3 runs, and step 3 then drops person 3 as `no_water_contact`. The result is `knee` from wheel 2, with `drops["person_wading"] == 1` and `drops["no_water_contact"] == 1`.
  - Review Focus 3, `test_not_visible_wheel_gets_no_geometry`: `geometry_case(waterline="not_visible")` with geometry on → `geometry_checks == {"waterline_not_visible": 1}`, `wheels_measured == 0`, `no_usable_reference`, and no step 3 cause in `drops`.
  - `test_a_rim_in_a_cut_wheel_never_joins_a_kept_one` (P14): `geometry_case()` plus a 30 px `wheel` at `(300, 228, 330, 257)`, which the 40 px rule cuts, and a second `wheel rim` centred at (315, 245), inside both wheel boxes. That rim links to no single wheel, so wheel 2 keeps its own rim and still measures: `wheels_measured == 1` and `geometry_checks == {}`. Linking among the kept wheels only would give wheel 2 two rims (`rim_several`).
  - `test_log_keys_are_the_known_set` (C316): `set(run.log)` sits inside MS3a's keys plus the new ones above, so a mask can't reach the log.
- [ ] **Step 2:** Run `uv run pytest -q tests/test_pipeline.py`. Expected: FAIL.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** Run `uv run pytest -q`. An MS3a test can now change outcome because its fake water doesn't touch a reference. Move that test's `floodwater` box so the water touches the reference, and never loosen step 3. List each such test in the task report. Then run `uv run ruff check .`. Expected: PASS; clean.
- [ ] **Step 5:** Commit `feat(analysis): run step 3 after the gate and geometry behind geometry_in_level`.

### Task 7: Muse Spark's request: the reasoning effort and the drawing candidate (C312, C325)

**Files:**
- Modify: `backend/analysis/src/lusot_analysis/meta_client.py`, `backend/analysis/src/lusot_analysis/annotate.py`, `backend/analysis/src/lusot_analysis/pipeline/__init__.py`, `backend/analysis/tests/fakes.py`
- Test: `backend/analysis/tests/test_meta_client.py`, `backend/analysis/tests/test_annotate.py`, `backend/analysis/tests/test_pipeline.py`, `backend/analysis/tests/test_tuning.py`

The plan review split this out of Task 6 (finding 10). MS3a's Task 7a already built the plumbing:
- `MetaClient.judge(..., reasoning_effort=None)` sends `"reasoning": {"effort": value}` only when it is set, and `SparkResult.reasoning_tokens` holds the count.
- `ModelClient.judge`, `RecordingClient.judge` (which passes it on) and `SavedOutputsClient.judge` (which ignores it) take the keyword (R108).
- `FakeClient.keywords` records it (R101), and MS3a's `test_judge_sends_reasoning_effort_and_records_reasoning_tokens` covers `low` and `None`.

This task checks the value, passes the tuning's effort and drawing, and logs them.

**Interfaces:**
- Consumes: `Tuning` (Task 1); `run_pipeline(..., tuning=...)` (Task 6)
- Produces:
  - `meta_client.REASONING_EFFORTS = ("minimal", "low", "medium", "high", "xhigh", "max")`, as the plan writer read Meta's reasoning page on Oct 28. MS1's probe note records only "minimal to max", and that `none` returns HTTP 400 for Muse Spark, so Step 1 re-reads the page first (P15). `MetaClient.judge` raises `ValueError` for any other `reasoning_effort` before a request is sent. `None` still sends no `reasoning` key.
  - `annotate.DRAWINGS = ("boxes-v1", "boxes-v2")`, and `outline_corners(box: tuple[int, int, int, int], drawing: str) -> tuple[tuple[int, int], tuple[int, int]]`, the two corners `draw_numbered_boxes` passes to `cv2.rectangle` at thickness 2 (C325, §D6):
    - `boxes-v1`, MS3a's drawing, unchanged: `((x0, y0), (x1 − 1, y1 − 1))`. Its 3 px outline is centred on the box's edge, so it covers a wheel box's rows y1 − 2 to y1.
    - `boxes-v2`: `((x0 − 4, y0 − 4), (x1 + 3, y1 + 3))`. The same 3 px outline lies outside the box with a 2 px gap: its bottom covers rows y1 + 2 to y1 + 4.
    - Any other drawing raises `ValueError`.
  - `draw_numbered_boxes(img, boxes, *, drawing: str = "boxes-v1")`. Labels are placed as in MS3a.
  - `run_pipeline` calls `judge(..., reasoning_effort=tuning.reasoning_effort)` and draws with `drawing=tuning.drawing`.
  - **Log keys (C316, §D2):** always `reasoning_effort` (its value, or `"default"`) and `drawing_version`; once Muse Spark has answered, `reasoning_tokens` (the answer's count, or null when Meta doesn't report it). Muse Spark's latency is MS3a's `spark_ms`.
  - The handler and the offline runner both use `TUNING` by default, so the Lambda and the laptop send the same effort and draw the same way (§D2). Only a development run's explicit flag changes them (Task 9).
  - `FakeClient(..., reasoning_tokens: int | None = None)` puts that count in its answer.

- [ ] **Step 1:** Re-read Meta's reasoning page (`https://dev.meta.ai/docs/reasoning`), and record the values it lists for `reasoning.effort`, with the date, in the task report. If they differ from the tuple above, the page's list wins (P15).
- [ ] **Step 2: Write the failing tests:**
  - `test_judge_refuses_an_unknown_effort` (`test_meta_client.py`): `"none"` and `"turbo"` raise `ValueError`, and no request is made.
  - `test_tuning_effort_and_drawing_are_known_values` (`test_tuning.py`): `TUNING.reasoning_effort` is `None` or in `REASONING_EFFORTS`, and `TUNING.drawing` is in `DRAWINGS`.
  - `test_drawing_v2_leaves_the_wheels_edge_clear` (`test_annotate.py`), for the box `(100, 100, 160, 160)`:
    - `outline_corners` gives `((100, 100), (159, 159))` for `boxes-v1` and `((96, 96), (163, 163))` for `boxes-v2`. `"boxes-v3"` raises `ValueError`.
    - Drawn with `cv2.rectangle` at thickness 2 on a blank 480 × 640 array, before any JPEG encoding: `boxes-v1` sets rows 158 to 160 across columns 100 to 159. `boxes-v2` sets none of rows 157 to 161 there, and all of rows 162 to 164.
    - `draw_numbered_boxes(..., drawing="boxes-v2")` returns a `BlurredImage` with the base's faces, blur version and size, as MS3a's `test_draw_numbered_boxes_keeps_blur_provenance` checks for v1.
  - `test_reasoning_effort_and_drawing_reach_judge` (`test_pipeline.py`):
    - `tuning=replace(TUNING, reasoning_effort="low", drawing="boxes-v2")` → the fake recorded `"low"`, and the log has `reasoning_effort == "low"` and `drawing_version == "boxes-v2"`.
    - With `TUNING`, the fake recorded `None`, and the log has `"default"` and `"boxes-v1"`.
  - `test_reasoning_tokens_are_logged`: `FakeClient(..., reasoning_tokens=180)` → `run.log["reasoning_tokens"] == 180`; without it → `None`.
  - `test_log_keys_are_the_known_set` (Task 6) gains the three keys.
- [ ] **Step 3:** Run `uv run pytest -q tests/test_meta_client.py tests/test_annotate.py tests/test_pipeline.py tests/test_tuning.py`. Expected: the new tests FAIL.
- [ ] **Step 4:** Implement. Read `meta_client.py` first: the check goes in `judge` before `options` is built.
- [ ] **Step 5:** Run `uv run pytest -q`, then `uv run ruff check .`. Expected: PASS; clean.
- [ ] **Step 6:** Commit `feat(analysis): send the tuning's reasoning effort and box drawing to Muse Spark`.

### Task 8: The evidence record (C328; MS4's C518)

**Files:**
- Create: `backend/analysis/src/lusot_analysis/pipeline/evidence.py`
- Modify: `backend/analysis/src/lusot_analysis/pipeline/__init__.py` (`PipelineRun.evidence`), `backend/analysis/src/lusot_analysis/pipeline/references.py` (`Kept.causes`), `backend/analysis/src/lusot_analysis/pipeline/measure.py` (`measure_boxes`)
- Test: `backend/analysis/tests/test_evidence.py`, `backend/analysis/tests/test_pipeline.py`, `backend/analysis/tests/test_apply_drops.py`, `backend/analysis/tests/test_measure.py`

**Interfaces:**
- Consumes: `Waterline` with `x_span`, `water_mask` (Task 2); `RimFit` with `axes` and `angle_deg`, `GeometryReading`, `KeptReading` (Task 3); `Reference.decides` (Task 4); `instances_by_id` (Task 6); MS3a's `NumberedBox` and `Layout`
- Produces, in `lusot_analysis.pipeline.evidence` (C328):
  - `Polygon = tuple[tuple[int, int], ...]`
  - `outline(mask: np.ndarray) -> tuple[Polygon, ...]`: the mask's outer contours (`cv2.findContours` with `RETR_EXTERNAL` and `CHAIN_APPROX_SIMPLE`), each simplified with `cv2.approxPolyDP(contour, 1.0, True)`, as `(x, y)` pixel points. A contour of under 3 points is left out, and an empty mask gives `()`.
  - `@dataclass(frozen=True) class RimDrawing: centre: tuple[float, float]; axes: tuple[float, float]; angle_deg: float`: the fit as `cv2.fitEllipse` returned it, which `cv2.ellipse` draws
  - `@dataclass(frozen=True) class EvidenceEntry`:
    - `id: int`; `kind: Literal["wheel", "body", "person"]`, where a vehicle's numbered box is `body`; `box: tuple[int, int, int, int]`, the numbered box, half-open; `outline: tuple[Polygon, ...]`
    - `landmark: str | None`: Muse Spark's category for the box (a wheel's or a person's `waterline`, a vehicle's `body_waterline`), or `None` when unanswered
    - `level: str | None` and `level_from: Literal["landmark", "geometry"] | None`: the box's own reading, or `None` when it gives none
    - `inches: tuple[float, float] | None`: geometry's unrounded min and max, whenever geometry measured the wheel, G4's drop included
    - `rim: RimDrawing | None`: with a geometry reading only
    - `waterline: tuple[tuple[float, float], tuple[float, float]] | None`: `((x_first, y_w), (x_last, y_w))` from step 3's `x_span`, wherever step 3 found a `y_w`
    - `used: bool`: its reading entered the combine as one that can decide, so it counts in `basis`
    - `deciding: bool`; `dropped: str | None`, its cause; `rechecked: bool = False`, which only the self-check's addendum sets (C311)
  - `@dataclass(frozen=True) class Evidence: references: tuple[EvidenceEntry, ...]; water_outline: tuple[Polygon, ...]`, the entries in box-id order
  - `build_evidence(boxes: Sequence[NumberedBox], instances: Mapping[int, SamInstance], answer: dict, water: np.ndarray, *, causes: Mapping[int, str], readings: Mapping[int, KeptReading], waterlines: Mapping[int, Waterline], geometry: Mapping[int, GeometryReading], used: frozenset[int], deciding: int | None) -> Evidence`. It reads only the numbered boxes and the water mask, never `face` or `license plate` (C518), and never the answer's `reason` (C62).
- Changes:
  - `Kept` gains `causes: Mapping[int, str] = field(default_factory=dict)`: each dropped box's first cause. `apply_drops` sets it, and the `Counter` it returns is `Counter(kept.causes.values())`, the same counts as before.
  - `measure_boxes(kept, *, step3_drops=None, geometry=None) -> Measured`, with `references`, `drops` (`Counter`), `causes` (box id → cause, counted as Task 5 says) and `readings` (box id → `KeptReading`, for every box that gives a reading, non-deciding ones included). `measure` returns `(m.references, m.drops)`, so MS3a's tests and Task 5's stand.
  - `PipelineRun` gains `evidence: Evidence | None = None`, so MS3a's constructions keep working. It is set once Muse Spark's answer has passed the schema and the id check (step 4.4), on a gate result too, where no box has a reading. It is `None` before that, and on every error path. A replay rebuilds it, so the runner saves nothing new, and nothing in MS3b stores it (MS4 does, its C505 and C507).
  - After the commit, post the record's field names to the tracker for Window 4 (MS4's C518), naming any that differ from C518's list.

- [ ] **Step 1: Write the failing tests:**
  - `test_outline_of_simple_masks`: a filled rectangle on rows 10 to 29 and columns 20 to 59 gives one polygon, whose points are exactly the corners {(20, 10), (59, 10), (59, 29), (20, 29)}; a disk of radius 35 at (320, 240) gives one polygon of at least 8 points, each 33.5 to 35.5 px from the centre; an empty mask gives `()`.
  - `test_apply_drops_names_each_box_cause`: a moving vehicle → its own and each wheel's cause (`vehicle_moving`, `wheel_vehicle_dropped`); an unanswered wheel of a kept vehicle → `wheel_unanswered`; a wading person → `person_wading`; and the returned `Counter` equals `Counter(kept.causes.values())`.
  - `test_measure_boxes_keeps_each_box`: a sedan 1 with wheels 2 at `hub` and 3 at `tire_only` → causes `{1: "vehicle_wheels_disagree", 2: "wheel_vehicle_dropped", 3: "wheel_vehicle_dropped"}`; a lone sedan wheel at `hub` → `readings[id].reading.level == "half_tire"`; `measure(kept)` still returns MS3a's pair.
  - `test_evidence_for_a_geometry_result` (`geometry_case()`, geometry on):
    - entry 1: `body`, landmark `not_visible`, level `None`, not used or deciding, dropped `None`
    - entry 2: `wheel`, landmark `rim_quarter`, level `half_knee`, `level_from` `geometry`, inches within 0.02 of (7.720, 8.184), `rim.centre` within 0.5 of (320.0, 239.6), used and deciding, dropped `None`, `rechecked` false
    - entry 2's waterline is `((x0, 257.0), (x1, 257.0))`, where `(x0, x1)` is `find_waterline(wheel mask, water, TUNING).x_span`
    - each entry's `box` is its numbered box, and the water outline is the one rectangle {(0, 257), (639, 257), (639, 479), (0, 479)}
  - `test_evidence_marks_drops_and_kept_readings`: `level_case()` plus Task 6's persons 3 and 4 (a dry standing adult at `knee`, and a wading adult at `knee`):
    - wheel 2: level `knee`, `level_from` `landmark`, used and deciding, and a waterline at row 280.0 from column 150 to 199
    - person 3: level `knee`, not used, dropped `no_water_contact`, waterline `None`
    - person 4: level `None`, not used, dropped `person_wading`
  - `test_a_g4_drop_keeps_its_geometry`: `geometry_case(waterline="rim_three_quarters")` with geometry on → `no_usable_reference`, and wheel 2 is dropped `wheel_methods_disagree`, with level `None`, not used, its inches within 0.02 of (7.720, 8.184) and its `rim` set.
  - `test_evidence_with_geometry_off`: `geometry_case("van")` with geometry off → vehicle 1 dropped `vehicle_type`, wheel 2 dropped `wheel_vehicle_dropped`, and no inches or rim anywhere.
  - Review Focus 6, `test_evidence_holds_no_face_plate_or_reason` (C62, C518): with `level_case()`, which has a face and a plate, the entries are exactly boxes 1 and 2; no entry's box is the face's `(300, 120, 330, 150)` or the plate's `(220, 270, 280, 290)`; no polygon lies wholly inside either box; and `REASON-MARKER-31` isn't in `repr(run.evidence)`.
  - Review Focus 6, `test_evidence_never_reaches_the_log`: no key of `run.log` is `evidence`, `outline`, `water_outline` or `rechecked`, and `json.dumps(run.log)` doesn't contain `"outline"`.
  - `test_no_evidence_before_the_answer`: a `flat_jpeg(10)` photo (`too_dark`) and a `judge` that raises `meta_error(500)` (`model_error`) both give `evidence is None`. `level_case()` answered with `standing_water: "no"` and its wheel at `tire_only` gives no flood seen, with a record of boxes 1 and 2: landmarks `not_visible` and `tire_only`, every `level` `None`, nothing used, deciding or dropped, and the water outline present.
- [ ] **Step 2:** Run `uv run pytest -q tests/test_evidence.py tests/test_pipeline.py tests/test_apply_drops.py tests/test_measure.py`. Expected: the new tests FAIL.
- [ ] **Step 3:** Implement. The record is assembled from what steps 3 to 6 already hold; no step measures anything new for it.
- [ ] **Step 4:** Run `uv run pytest -q`, then `uv run ruff check .`. Expected: PASS; MS3a's tests unchanged; clean.
- [ ] **Step 5:** Commit `feat(analysis): hand MS4 an evidence record of every numbered box`, then post the field names to the tracker (above).

### Task 9: The offline runner and saved runs

**Files:**
- Modify: `backend/analysis/probes/run_pipeline.py`, `backend/analysis/src/lusot_analysis/pipeline/saved.py`
- Test: `backend/analysis/tests/test_run_pipeline.py`, `backend/analysis/tests/test_saved.py`

**Interfaces:**
- Consumes: `run_pipeline`'s new keywords (Tasks 6 and 7); `Tuning`, `TUNING`, `START`, `TIRE_CODES_VERSION`; `REASONING_EFFORTS`, `DRAWINGS` (Task 7)
- Produces, in `pipeline.saved`:
  - `save_sam_results(run_dir: Path, sam: Mapping[str, SamResult]) -> None` and `load_sam_results(run_dir: Path) -> dict[str, SamResult]`: MS3a's `sam/` layout, taken out of `RecordingClient.save` and `SavedOutputsClient`, with no change in behaviour
  - `SavedSamLiveJudge(saved: SavedOutputsClient, live: ModelClient)`: `segment` from the saved run, `judge` live
  - `rebuild_outcome(saved: Mapping[str, object]) -> Outcome`: `Outcome(**saved)` from a saved `asdict`. An MS3a run's saved outcome has none of Task 4's three fields, and rebuilds with their defaults.
  - `run.json` gains `geometry_in_level` (bool), `tuning` (`asdict`, with `untuned` as a sorted list), `tire_codes_version`, `reasoning_effort`, `drawing_version` and `sam_from` (bool)
- Produces, in `probes/run_pipeline.py`:
  - `live(photo, data_dir, *, run_dir: Path | None = None, geometry_in_level: bool = True, tuning: Tuning = TUNING, sam_from: Path | None = None) -> tuple[Path, PipelineRun]`. MS3a's guards still run first: `refuse_sealed`, `refuse_data_in_repo` and `refuse_sturm_live` (C87).
  - the commands:
    - `live <photo> [--data-dir DIR] [--run-dir DIR] [--geometry on|off] [--effort E] [--drawing D] [--sam-from RUN_DIR]`. `--effort` is a `REASONING_EFFORTS` value or `default`, and `--drawing` a `DRAWINGS` value. `--sam-from` reuses that run's SAM outputs and pays for `judge` only.
    - `replay` uses the saved `geometry_in_level` and `tuning`. A run without them, from MS3a, replays with geometry off and `START`.
    - `same as saved` compares `rebuild_outcome(saved["outcome"])` with the replay's outcome, so an MS3a run folder isn't judged by the keys it lacks. Its outcome can still really change, since step 3 now runs even with geometry off, and the printout then says `same as saved: False` (P12).
  - The printout adds `level_from`, `wheels_measured`, `geometry_checks`, `reasoning_effort`, `drawing_version` and `reasoning_tokens` (Task 11 reads them).
  - `refuse_sealed` also covers `--run-dir` and `--sam-from`

- [ ] **Step 1: Write the failing tests:**
  - `test_live_records_the_geometry_config`: `geometry_case()` live gives a `run.json` with `geometry_in_level` true, tuning version `"tuning-v1"`, `tire_codes_version == "tire-codes-v1"`, `reasoning_effort` null and `drawing_version == "boxes-v1"`.
  - `test_replay_uses_the_saved_config`: a `geometry_case("van")` run recorded with `--geometry off` replays to `no_usable_reference` and `same as saved: True`.
  - `test_effort_and_drawing_flags_reach_judge`: `--effort low --drawing boxes-v2` → the fake recorded `"low"`, and `run.json` says `"low"` and `"boxes-v2"`.
  - `test_handler_and_runner_send_the_same_effort` (§D2): with default settings, the runner's `live()` and `handler.analyse` record the same `reasoning_effort` (`TUNING`'s) and log the same `drawing_version`.
  - `test_sam_from_pays_only_for_judge`: a recorded run, then `live --sam-from <dir>` with a fake whose `segment` raises `AssertionError` → 0 `segment` calls and 1 `judge`. The new run replays to its own saved outcome.
  - `test_run_dir_flag_writes_there`, and `test_sealed_run_dirs_are_refused` (`--run-dir` or `--sam-from` under `sealed` → exit 2).
  - `test_rebuild_outcome_round_trips`: a landmark level, a geometry level with inches, no flood seen and a refusal each satisfy `rebuild_outcome(asdict(o)) == o`. An MS3a-shaped `asdict`, without the three new keys, rebuilds to the same level with `level_from == "landmark"`.
  - `test_old_runs_replay_with_geometry_off`: a `run.json` without the new keys, whose saved outcome lacks the three new fields, from `level_case()`, whose water touches its wheel so step 3 changes nothing → geometry off, `START`, and `same as saved: True`.
  - `test_sam_results_round_trip`: `save_sam_results`, then `load_sam_results`, gives equal boxes and scores, and `np.array_equal` masks. MS3a's saved-layout tests pass unchanged.
- [ ] **Step 2:** Run `uv run pytest -q tests/test_run_pipeline.py tests/test_saved.py`. Expected: FAIL.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** Run `uv run pytest -q`, then `uv run ruff check .`. Expected: PASS; clean.
- [ ] **Step 5:** Commit `feat(analysis): record the geometry setting, tuning, effort and drawing in saved runs`.

### Task 10: Storage, the handler, the API test and the template

**Files:**
- Modify: `backend/analysis/src/lusot_analysis/report_store.py`, `backend/analysis/src/lusot_analysis/handler.py`, `backend/template.yaml`
- Test: `backend/analysis/tests/test_report_store.py`, `backend/analysis/tests/test_handler.py`, `backend/api/test/reports.test.ts`

**Interfaces:**
- Consumes: `item_fields()` (Task 4); `run_pipeline(..., geometry_in_level=...)` (Task 6); `PipelineRun.evidence` (Task 8); the runner and `rebuild_outcome` (Task 9)
- Produces:
  - `write_result` accepts `float` values as `{"N": str(value)}`. The order of checks is `str`, `bool`, `int`, `float`, then a mapping.
  - `handler._geometry_in_level() -> bool`, cached: `GEOMETRY_IN_LEVEL` `"on"` → True and `"off"` → False. Anything else, or no value, raises `ValueError`. It loads before the claim, with the key and the prompt, so a bad value returns the message and leaves the report `pending` (C60, C79).
  - `handler.analyse(data, client, *, deadline=None)` passes `geometry_in_level=_geometry_in_level()` (B3).
  - The handler writes `item_fields()` only, as in MS3a, so the evidence record is never stored, and its log line takes `run.log` only, so the record never reaches CloudWatch (C328).
  - **The template** gives the analysis function `GEOMETRY_IN_LEVEL: "on"`, a literal beside its other variables, not a template parameter (C309). SAM CLI keeps a parameter's previous value on an existing stack when `parameter_overrides` doesn't name it, and `samconfig.toml` names only `AlarmEmail` and `BucketSuffix`, so a changed parameter default would never reach the stack (MS4's C515 found this in SAM CLI 1.170.0's source). Task 17 changes the literal in the commit that records C309's decision.
  - `GET /reports/{id}` doesn't change: its allow-list (MS3a Task 10) already leaves out `levelFrom`, `depthInMin` and `depthInMax` (C320).

- [ ] **Step 1: Write the failing tests:**
  - `test_writes_inches_as_numbers` (C308): `depthInMin` 8.2, `depthInMax` 8.8 and `levelFrom` `"geometry"` are stored as `{"N": "8.2"}`, `{"N": "8.8"}` and `{"S": "geometry"}`.
  - `test_geometry_setting_is_read_before_the_claim`, parametrized over unset and `"maybe"` → `RETRY`, the report stays `pending`, and the fake made no call.
  - `test_geometry_result_is_stored_with_its_source_and_inches` (C308): `geometry_case()` gives an item with `level` `half_knee`, `levelFrom` `geometry`, `depthInMin` 7.7 and `depthInMax` 8.2, stored as numbers.
  - `test_landmark_result_stores_level_from_only` (C320): `level_case()` gives `levelFrom` `landmark` and no `depthIn*`.
  - `test_b3_geometry_replay_matches` (D1, B3): the runner's `live()` records `geometry_case()` with geometry on. `replay(...).outcome == analyse(data, SavedOutputsClient(run_dir, data)).outcome`, both carry the inches, and their evidence records are equal (C328).
  - MS3a's `test_b3_on_a_real_saved_run` compares `rebuild_outcome(saved["outcome"])` with the handler's outcome, so a folder isn't failed by the keys it lacks. It is meant for a folder MS3b's runner saved (Task 11 Step 7). An MS3a folder can still fail it on a real change, since the handler now runs step 3, and geometry by `GEOMETRY_IN_LEVEL` (P12).
  - `test_log_line_carries_the_geometry_fields` (C316): the line has `geometry_in_level`, `tuning_version`, `rim_edge_k`, `reasoning_effort`, `drawing_version`, `reasoning_tokens`, `wheels_measured`, `geometry_checks`, `level_from` and `depth_in`.
  - Review Focus 6, `test_log_line_holds_no_evidence` (C328): for `geometry_case()`, no key at any depth of the handler's log line is `evidence`, `outline`, `water_outline` or `rechecked`, and the stored item holds none either.
  - In `reports.test.ts`, `never returns levelFrom or the inches before the release gate` (C320): a stored level item with those three fields gives exactly MS3a's level body, and the body text contains none of the three names.
  - The `prompts` fixture in `test_handler.py` sets `GEOMETRY_IN_LEVEL=on` and clears `_geometry_in_level`'s cache, as it does for the prompt (P12). Both B3 tests use `prompts` alone, and the `aws` fixture builds on it, so every handler test gets the setting. (MS3a's exact-field tests gained `levelFrom` in Task 4.)
- [ ] **Step 2:** Run `uv run pytest -q tests/test_report_store.py tests/test_handler.py` and `npm test -w backend/api` (from the repo root). Expected: the Python tests FAIL. The API test PASSES with no code change. If it fails, the allow-list leaks: fix it in `reports.ts`.
- [ ] **Step 3:** Implement the store, the handler and the template.
- [ ] **Step 4:** Run `uv run pytest -q` and `uv run ruff check .`. From `backend`, run `sam validate --lint --profile lusot --region ap-southeast-1` and `grep -n "GEOMETRY_IN_LEVEL" template.yaml`. Expected: PASS; clean; valid; one match, and no `GeometryInLevel` parameter.
- [ ] **Step 5:** Commit `feat(analysis): store levelFrom and the inches, and read geometry_in_level from the template`.

### Task 11: Deploy and the cloud geometry check (D1; spends Meta credits)

**Files:**
- Modify: `backend/scripts/smoke_upload.py`
- Test: `backend/scripts/test_smoke_upload.py`

**Interfaces:**
- Consumes: MS3a Task 15's smoke script as built (R102, R115, R116): `photo_folder`, `seeded_photo_order(folder)` (C87's order, as `images/<name>` paths), `credited(folder, photos)`, `as_app_jpeg`, `upload_photo` (which runs `wait_final` and `log_lines`), `check_report_body`, `log_lines(stack, report_id, *, until=None, clock=None, sleep=None)`, `Stack` (with `log_group`), `say_spend`, `CheckFailed`, `refuse_sealed` and `say`. STURM stays offline (C87, C323).
- Produces:
  - `check_geometry_line(line: dict) -> None` raises `CheckFailed("no wheel measured")` unless `wheels_measured >= 1`
  - No new body check: `check_report_body` already fails a body with any key beyond C67's, so `levelFrom`, `depthInMin` and `depthInMax` fail it (C320). A test pins that.
  - `smoke_upload.py --bound S` (R119): the wait for each report's final status, passed through `upload_photo` to `await_report`'s `bound_s`. It defaults to 120 s, B1's bound (C68). MS3b's runs pass `--bound 180`, since MS3a's runs stop as late as about 150 s (C84, C88) and geometry adds time.
  - `smoke_upload.py --geometry N`: sends the photo at position N of C87's order (`seeded_photo_order(folder)[N]`), as the app sends it, and only that photo. It stops with `CheckFailed`, before any upload, if `credited` skips that photo. Through `upload_photo` it waits for the final status within `--bound` and checks the body. It then runs `check_geometry_line` on the report's final log line, and prints the outcome, `level_from`, `wheels_measured`, `geometry_checks` and the spend. It exits 0 when every check passes and 1 otherwise. No path or name is typed or printed.

- [ ] **Step 1:** Write the failing tests:
  - `test_geometry_check_needs_a_measured_wheel`: `wheels_measured` 1 passes; 0 or missing → `CheckFailed`.
  - `test_report_body_refuses_levelfrom_and_the_inches` (C320): a level body plus any one of the three keys → `CheckFailed` naming that key.
  - `test_geometry_mode_sends_one_credited_photo` (on fakes): position N's credited photo is the one sent; an uncredited one stops with `CheckFailed` before any upload.
  - `test_bound_reaches_every_wait` (R119): with `--bound 180`, every report's wait gets 180 s; without it, 120 s.

  Run them with MS3a's command (its Task 15, Step 2): `uv run --with pytest --with "boto3[crt]" --with httpx --with numpy --with "opencv-python-headless<5" pytest -q backend/scripts/test_smoke_upload.py` from the repo root. Expected: FAIL. Implement them, re-run, expect PASS, and commit `test(backend): add the smoke run's geometry check`.
- [ ] **Step 2 (Claude; about $0.03 a photo):** find a photo with a geometry reading, offline, on the photo the cloud will get (P7).
  - Go through C87's credited photos in its order, positions 0 to 9, one at a time. The smoke script's `seeded_photo_order` and `credited` give their paths; print none.
  - For each, write `as_app_jpeg(that photo)`, the app's 1,600 px at quality 85, to `<LUSOT_DATA_DIR>\d1_search\<position>.jpg`. Then run `uv run python probes/run_pipeline.py live "<that file>" --geometry on`, with the key line.
  - Stop at the first run whose output shows `wheels_measured` of at least 1, and record its position, never its name.
  - The Commons car photos can't serve: they are dry, so Muse Spark sees no flood and geometry never runs (C323).
  - If none of the 10 measures a wheel, D1's cloud half is partly met. Record that, go on, and let the first Manila development or consented photo prove it.
- [ ] **Step 3: Preconditions**, as MS3a's Task 16 Step 1:
  - Rene's AWS login holds: the `ends_with(Arn, 'user/rene-dev')` query prints `true`.
  - Docker is running, and no Gradle build is. `git status` is clean.
  - **A heads-up** in the handoff note: after this deploy, the cloud runs step 3 and geometry, so a photo's result can change, and the smoke run turns uploads off for about a minute (P6).
  - **No phone test is running (M14).** CLAUDE.md says never to run the smoke during one. If Rene is testing the phone, wait (P6).
  - Post `DOCKER/DEPLOY RUNNING <time>` in the handoff note and to the tracker before Step 4, and `DOCKER/DEPLOY DONE <time>` after the last smoke run (the tracker's update A.2).
- [ ] **Step 4:** Build and check the image as `CLAUDE.md`'s deploy line says. From PowerShell, with PATH refreshed, run `npm run build -w backend/api`, then `sam build --parallel` from `backend`. Check the image SAM built, `analysisfunction:<the template's DockerTag>` (`ms1` today), never a manual `docker build`:
  - `docker run --rm --network none --entrypoint python <image> -c "import lusot_analysis.meta_client, lusot_analysis.handler"`, and list `/var/task/prompts`
  - `docker run --rm --network none --entrypoint python <image> -c "from lusot_analysis.rules import tire_codes, TIRE_CODES_VERSION; print(TIRE_CODES_VERSION, len(tire_codes('unknown')))"` → `tire-codes-v1 12`
- [ ] **Step 5:** Run `npm run deploy` from PowerShell. Expected: the stack updates, then `lifecycle: keep 3`.
- [ ] **Step 6:** Run `uv run backend/scripts/smoke_upload.py --bound 180` from the repo root. Expected: `SMOKE OK`; an exit 3 follows MS3a's C71 path (its Task 16, Step 4). Then, if Step 2 found a photo, run `uv run backend/scripts/smoke_upload.py --bound 180 --geometry <Step 2's position>`. Expected: exit 0. Record the outcome, `level_from`, `wheels_measured` and the seconds to a final status.
  - Muse Spark's answers vary between runs, so the cloud can miss a wheel the offline run measured. If `--geometry` exits 1, go back to Step 2's search from the next position, and try the next photo found (P7).
  - Once positions 0 to 9 are used up, record D1's cloud half as partly met.
- [ ] **Step 7:** If a photo passed, check B3 on its real run: `$env:LUSOT_B3_RUN_DIR = '<its run dir from Step 2>'; $env:LUSOT_B3_PHOTO = '<its file in d1_search>'; uv run --directory backend/analysis pytest -q tests/test_handler.py -k b3`. Expected: all passed, 0 skipped.
- [ ] **Step 8:** Record the spend: the photos sent, 6 calls for each offline run, 8 for each cloud photo, and the estimate from billed usage in the log lines.

### Task 12: The export: development rows for MS6's harness (C315, C327)

**Files:**
- Create: `backend/analysis/src/lusot_analysis/export.py`, `backend/analysis/probes/dev_eval.py`
- Test: `backend/analysis/tests/test_export.py`, `backend/analysis/tests/test_dev_eval.py`

**Interfaces:**
- Consumes: `SavedOutputsClient`, `rebuild_outcome`, `SavedSamLiveJudge` (Task 9); `load_prompt`, `run_pipeline`, `PipelineRun.evidence` (Task 8); `Tuning`; the runner's `live` and `refuse_sealed`, loaded from the sibling file with `importlib.util.spec_from_file_location` as its tests load it
- **The input, in MS2's formats** (its §5.9; MS6's spec header lists the bridging):
  - `set_a\dev\manifest.csv` and `a_neg\dev\manifest.csv`, UTF-8 CSV with a header row; each photo is `photos\<photo_file>` beside its manifest
  - Set A's `m8.csv`: one row per labelled item, with `photo_id`, `ref_id` (`P1` is the photo row), `kind` (`photo`, `vehicle`, `wheel` or `person`), `x` and `y` (fractions of the photo's width and height, from the top left), `vehicle_type`, `body_waterline`, `waterline`, `quality` and `subsets`
  - The tools need `photo_id` (unique), `set` and `photo_file`. Set A rows also need `event_id`, which the replay groups by; other manifests, such as Task 16's for Set C, may leave it out (P10). The export bridges the rest into §4.3's fields: `yes` and `no` into booleans, `;`-separated lists into lists, `quality` and `subsets` from M8's photo row, M8's points into box ids, and `duplicate_of` into `duplicate`. Only §4.3's fields reach a row: cities, spots, notes, file names, hashes, sizes and times stay out.
  - If MS2's format changes, MS2's wins: adapt the reader in Step 1 and record how.
- Produces, in `lusot_analysis.export` (MS6's sealed-run entry point reuses it, C412; MS3b doesn't build that entry point):
  - `CONFIGURATIONS = {"landmark": False, "geometry": True}`: each outcome key and its `geometry_in_level`
  - `answer_without_reason(data: Mapping | None, schema: dict) -> dict | None`: the answer without its `reason`. It is `None` when there was no answer, or when the answer fails the schema (`validate_answer`), since MS6's allow-list would refuse such a row (P13).
  - `replay_configurations(photo_data: bytes, run_dir: Path, prompt: PromptSpec, *, tuning: Tuning = TUNING, configurations=CONFIGURATIONS) -> dict[str, PipelineRun]`: one replay per configuration, with no Meta call
  - `m8_boxes(labels: Sequence[Mapping], evidence: Evidence, size: tuple[int, int]) -> list[dict]` (C327, MS6's C415, MS2's C208): each labelled reference's point, scaled to the sent image's width and height, goes to the numbered box of its kind that holds it, edges included (M8's `vehicle` is the record's `body`). Where two hold it, the one whose centre is nearest wins; where none does, the box id is `null`. Each entry has `box_id`, `kind`, `landmark` (a wheel's or a person's `waterline`, a vehicle's `body_waterline`) and, for a vehicle, `vehicle_type`.
  - `label_or_marker(label: str, words: frozenset[str]) -> str` (C327, MS6's C420): a mirror of the harness's `scoring.labels.label_words_ok`, as committed on Window 4's branch (P1). Step 1 reads `eval/scoring/labels.py` there, read-only, and copies its three patterns exactly:

    ```python
    _MARKS = "-–,()\"'”“″/+"
    _LABEL_CHARS = re.compile(f"[A-Za-z0-9 .{re.escape(_MARKS)}]*")
    _SEPARATOR = re.compile(f"[ {re.escape(_MARKS)}]+|(?<![0-9])[.]|[.](?![0-9])")
    _NUMBER_TOKEN = re.compile("[0-9]{1,3}(?:[.][0-9]{1,2})?(?:in|cm)?")
    ```

    - A blank label, and the marker itself, stay as they are.
    - Any other label stays as written when it fullmatches `_LABEL_CHARS`, and every non-empty token of `_SEPARATOR.split(label.lower())` is in `words` or fullmatches `_NUMBER_TOKEN`. So a `.` outside a number separates words, and a number may be glued to `in` or `cm`.
    - Any other label becomes `(other words)`.
    - `words` comes from `python eval/run_eval.py --label-words`, run once as a subprocess and never imported (C321). Its list includes "ankle" and "head", and "+" is among the marks (MS6E-Q1, items 15 and 16).
    - If `labels.py` no longer has these patterns, its own win; record the change in the task report.
  - `photo_row(base: Mapping[str, object], runs: Mapping[str, PipelineRun], answer: Mapping | None, *, m8: Sequence[dict] = (), replay: Mapping[str, Mapping] | None = None) -> dict[str, object]`: `base`'s §4.3 fields, plus:
    - `outcomes`: `{key: run.outcome.item_fields()}`, and `<key>_replay` for each replayed configuration (C324, MS6's C425)
    - `answer`
    - `wheel_inches`: `{"<box id>": {"depthInMin", "depthInMax"}}` from the `geometry` run's evidence record, unrounded, to 4 decimal places (C327; finding 2)
    - `m8`, on Set A rows
  - `results_manifest(*, date: str, rules_version: str, tuning: Tuning, saved_run: Mapping, geometry_default: str, dropped_reason: str | None, datasets: Mapping) -> dict`:
    - `kind` `"development"`, `date` and `rules_version`
    - `versions`: the models, the prompt, the drawing, the blur, `store` (false), `max_side` (1,600), the SAM phrases sent, the tuning, `rim_edge_k`, the tire codes and the reasoning effort (v0.7 item 10.1)
    - `datasets`, and `self_check` (`{"state": "off", "decided": null}` until C311 says otherwise)
    - `geometry_default`: `on`, `off` or `dropped`, with its reason when dropped (MS6's C418)
- Produces, in `probes/dev_eval.py`:
  - `read_manifest(path: Path, data_dir: Path, *, photos: str = "photos") -> list[dict]`. `photos` is the photo folder, relative to the manifest's folder: MS2's `photos\` by default, and `commons-ph-floods\images` for Task 16's Set C manifest. `refuse_sealed` runs on every path before it is opened.
  - `settings_name(tuning: Tuning) -> str`: `"<effort or default>_<drawing>"`, such as `default_boxes-v1`
  - `run_dir_for(data_dir: Path, row: Mapping, settings: str, *, repeat: int = 1) -> Path`: `<data_dir>/runs/dev/<row's set>/<settings>[_r<repeat>]/<photo_id>`. Runs at different efforts or drawings never share a folder (finding 5).
  - `run --manifest F [--photos DIR] [--limit N] [--effort E] [--drawing D] [--repeat 2] [--sam-from SETTINGS] [--yes]`: a live run for each row without a saved run in its folder. The settings are the tuning's, changed by the flags. `--sam-from` reuses SAM's saved outputs from that sibling folder and pays for `judge` only; a row without them runs in full. It prints the photo count and the estimated cost first: $0.03 a full photo, $0.015 for Muse Spark alone. After the runs it prints counts only, never an outcome, so no Set A result shows before v0.7 (C322).
  - `export --set-a F --m8 F --a-neg F --out DIR --rules-version V [--set NAME=VALUE ...] [--runs SETTINGS] [--datasets JSON] [--geometry-default on|off|dropped] [--dropped-reason TOKEN] [--replay FILE]`:
    - It writes `run.json`, `set_a.jsonl` and `a_neg.jsonl`.
    - `--runs` defaults to the tuning's own settings. A row whose saved run used another effort or drawing than the tuning's → exit 2, so efforts never mix (finding 5).
    - `--out` must lie under `LUSOT_DATA_DIR` and outside the repo, and no part of it may be named `sealed`.
    - A row without a saved run → exit 2 ("run `dev_eval.py run` first").
    - `--set` overrides a `Tuning` field for the replays.
    - `--geometry-default dropped` writes only `landmark` outcomes and an empty `wheel_inches`, and needs `--dropped-reason` (MS6's C418).
    - `--replay` takes Task 13's `replay.jsonl` and adds each Set A row's `<key>_replay` outcomes. Every Set A row must have them, or it exits 2 (MS6's C425).
    - It prints counts only: the photos, the G4 drops, `wheels_measured`, the geometry checks by cause, the labels written as `(other words)`, and the drops before numbering (`wheel_small`, `wheel_unlinked`, `vehicle_cap`, `wheel_cap`, `person_cap`; P2, P6). Then it prints the harness command to run next.

- [ ] **Step 1:** Check MS6's harness. If `eval/run_eval.py` and `eval/scoring/` exist on `main`, read its loader's contract (read-only) and match every row and `run.json` key it names, including `m8`, `geometry_default`, `datasets`, `self_check` and the replay keys. Where its names differ from this task's, MS6's win; record each difference in the task report. Run `python eval/run_eval.py --label-words` once to see the list. Read `eval/scoring/labels.py` from `main`, or else read-only with `git show w4-independent:eval/scoring/labels.py`, and check `label_or_marker`'s three patterns against it (P1). If the harness doesn't exist yet, build to this task's names and record that.
- [ ] **Step 2: Write the failing tests** (runs recorded with the runner's `live()` and a `FakeClient`; manifests and M8 sheets as CSV in `tmp_path`):
  - `test_answer_without_reason`: `reason` is gone and every other key stays; `None` gives `None`; an answer that fails the schema gives `None` (P13).
  - `test_photo_row_has_both_configurations`, on a `geometry_case("van")` run:
    - `outcomes.landmark` equals `Outcome.refused("no_usable_reference").item_fields()`
    - `outcomes.geometry` has `level` `half_knee`, `levelFrom` `geometry`, `depthInMin` 9.8 and `depthInMax` 9.9, as the item stores them (C308)
    - `wheel_inches["2"]` has `depthInMin` equal to `depthInMax`, within 0.02 of 9.887, with at most 4 decimal places (finding 2)
    - `answer` has no `reason`, the base fields pass through, and `photo_file` is gone
  - `test_m8_points_join_boxes` (C327): a wheel point inside wheel 2's box → box 2; a person point inside two person boxes → the one whose centre is nearer; a point in no box → `null`; a vehicle point → the vehicle's box, with its `vehicle_type`.
  - Review Focus 8, `test_labels_match_the_harness` (C327; P1), over one shared table:
    - **Stay as written:** "Knee deep.", "9in", "8.25 cm", "Head+ (60+ inches)", "10/28", "ANKLE DEEP (9 inches)", "Not passable to light vehicles (NPLV)", a blank label, and `(other words)` itself.
    - **Become `(other words)`:** "knee deep near the market", "8:00 AM", "1234 in" and "8.255 cm".
    - The same table runs through the harness's own `label_words_ok`, in a subprocess that loads `scoring.labels` from `eval/`, so `backend/analysis` never imports it (C321). The test checks that both give the same verdict on every row, so the export can't drift from the harness.
    - It is skipped, with its reason, only while `eval/scoring/labels.py` isn't in the tree. A second check, with a patched `--label-words` list, needs no harness: it runs the table through `label_or_marker` alone, and an `other_alerts_raw` entry is handled the same way.
  - `test_export_writes_the_results_folder`: two Set A rows and one A-neg row give 2 and 1 lines. `run.json` has `kind` `development`, the given `rules_version`, tuning `tuning-v1`, `rim_edge_k` 1.0, the tire codes version, `reasoning_effort` null, the drawing `boxes-v1`, `store` false, `max_side` 1600, the SAM phrases sent, and `geometry_default` `on`. The fake makes no call during the export.
  - `test_dropped_geometry_writes_only_landmark` (MS6's C418): `--geometry-default dropped --dropped-reason manila_check` → `run.json` records both, every row's `outcomes` has only `landmark`, and `wheel_inches` is empty.
  - `test_replay_outcomes_join_every_set_a_row` (MS6's C425): with a `replay.jsonl`, each Set A row gains `landmark_replay` and `geometry_replay`; a Set A row missing from it → exit 2.
  - Review Focus 7, `test_export_refuses_mixed_settings` (finding 5): a row whose saved run used `low` while the tuning's effort is the default → exit 2, with nothing written.
  - `test_export_refuses_bad_paths`: `--out` under a `sealed` folder, `--out` inside the repo, or a manifest photo under `sealed` → exit 2, with nothing created.
  - `test_export_needs_every_run`: a row with no saved run → exit 2.
  - `test_rows_hold_no_free_text`: the written text has no `REASON-MARKER-31`, no photo path, and none of the manifest's `notes`, `city` or `spot_key` values.
  - `test_run_prints_cost_first_and_needs_yes`: without `--yes` → exit 2, after printing the count and the cost. With it → a run folder for each row that lacked one; existing runs are kept.
  - `test_runs_at_other_settings_go_to_their_own_folder`: `--effort low --sam-from default_boxes-v1` writes under `low_boxes-v1`, reusing the default runs' SAM outputs with no `segment` call.
  - `test_no_import_crosses_into_eval` (C400; finding 8): an `ast` walk of every `.py` file under `src/lusot_analysis` and `probes/` finds no import of `eval` or `eval.*`.
- [ ] **Step 3:** Run `uv run pytest -q tests/test_export.py tests/test_dev_eval.py`. Expected: FAIL.
- [ ] **Step 4:** Implement.
- [ ] **Step 5:** Run `uv run pytest -q`, then `uv run ruff check .`. Expected: PASS; clean.
- [ ] **Step 6:** Commit `feat(analysis): export development rows for MS6's harness`.

### Task 13: The tuning sweep and event replay (C310, C324)

**Files:**
- Modify: `backend/analysis/probes/dev_eval.py`
- Test: `backend/analysis/tests/test_dev_eval.py`

**Interfaces:**
- Consumes: Task 12's export; `Tuning`, `START`, `TUNING`
- Produces, in `probes/dev_eval.py`:
  - `SWEEP_VALUES`: each swept field's fixed list of values. The start values are among them:
    - `brightness_min` 40, 50, 60, 70; `sharpness_min` 25, 50, 100, 200
    - `daylight_brightness_min` 40, 60, 80, 100
    - `touch_tolerance_px` 3, 4, 5, 6, 8; `touch_share_min` 0.15, 0.25, 0.35, 0.5
    - `ragged_iqr_share` 0.06, 0.08, 0.10, 0.12. It stays under the 12.3% where R86's reflection case begins, so tuning can't reopen it.
    - `rim_score_min` 0.3, 0.5, 0.7
    - Check 9's factors, k, the effort and the drawing aren't swept: Set B and C312 set them.
  - `SWEPT_FIELDS`: the 7 fields above, which C310 tunes on Set A, and the ones guard 3 resets (C324)
  - `sweep_grid(tuning: Tuning) -> list[Tuning]`: one field at a time, the others at `tuning`. Each field takes its listed values except its current one, and the quality cutoffs take none below their current value, because a photo refused before Meta has no saved outputs.
    - With `START`, that gives 21 candidates (finding 3), plus the baseline, `tuning` itself, so 22 exports in all.
    - Built from fixed lists, the grid stays right after the tuning moves a value onto one of them (P9).
  - `SUMMARY_FIGURES: dict[str, tuple[str, ...]]`: JSON paths, set in Step 1, to the configuration geometry's default names (`landmark` when geometry is dropped). Each is "k of n": Set A's within-one agreement, underestimation and coverage, and development A-neg's false floods (W9; S6).
  - `sweep --set-a F --m8 F --a-neg F --out DIR --rules-version V`:
    - For each candidate in `sweep_grid(TUNING)` and the baseline, it runs the export into `DIR/<field>-<value>/` (the baseline into `DIR/baseline/`), then `[sys.executable, <repo>/eval/run_eval.py, "--from-saved", "--results", <dir>, "--write"]`.
    - It prints one line per candidate with the figures `SUMMARY_FIGURES` names from that folder's `report/summary.json`, or `n/a`.
  - `choose_tuning(figures: Mapping[str, Mapping[str, tuple[int, int]]], *, start: Tuning) -> Tuning`: C310's rules as code (C324), so the in-sample choice and every held-out choice follow the same rules. Each field is chosen alone, from its candidates and the baseline:
    - **Quality and daylight cutoffs:** the highest value whose within-one count is no lower than that field's lowest value's.
    - **T, the touch share, the IQR share and the rim score:** the most photos within one level, a count (S6). A value qualifies only if:
      - its underestimation is no higher than the baseline's, as a count and as a rate (MS6E-Q5's default (d))
      - its false floods on development A-neg are no more than the baseline's (W9; S6)
      - its coverage is no more than 10 points below the baseline's

      Ties go to the stricter value: smaller T, a larger share, a smaller IQR share, a larger score.
    - The result keeps `start`'s other fields. Both the in-sample choice and `replay-events` pass `start=TUNING`, so k, check 9's factors, the effort, the drawing and the caps stay as tuned (P3).
  - `reset_swept(tuning: Tuning) -> Tuning` (guard 3; C324, P3): `SWEPT_FIELDS` back to `START`'s values, and added to `untuned`. Everything else stays as `tuning` has it, so the development runs still match the tuning's effort and drawing, and the export still takes them.
  - `replay-events --set-a F --m8 F --a-neg F --sweep DIR --out DIR --rules-version V` (C324, MS6's C425): for each development Set A event, by `event_id`:
    1. Each sweep folder is copied without that event's Set A rows, and the harness rescores the copy.
    2. `choose_tuning(..., start=TUNING)` picks that event's tuning from those figures.
    3. That event's photos are replayed with it, in both configurations, with no Meta call.

    It writes `DIR/replay.jsonl`, one line per Set A photo with its `landmark_replay` and `geometry_replay` outcomes (only `landmark_replay` when geometry is dropped), for Task 12's `export --replay`. A-neg rows get none. It prints counts only: the events, the photos, and for each event how many values its tuning changed. It never prints a figure: the harness's report shows them.

- [ ] **Step 1:** If MS6's harness is on `main`, read its `summary.json` writer and set `SUMMARY_FIGURES`. If any of the four figures is missing, record it and ask Window 4, through the tracker, to add it. Until then the sweep prints `n/a`, the controller reads each candidate's `report.md` for the in-sample choice, and `replay-events` waits. Otherwise leave `SUMMARY_FIGURES` empty.
- [ ] **Step 2: Write the failing tests:**
  - `test_sweep_grid_is_one_field_at_a_time` (finding 3; P9), pinned to `START`, not `TUNING`: `sweep_grid(START)` has 21 candidates, each differing from `START` in exactly one field and none equal to it; none below the quality cutoffs; no `ragged_iqr_share` above 0.12; no check 9 factor, k, effort or drawing. For a tuning whose `touch_tolerance_px` is 4, every candidate still differs from it in one field, and 5 is among the candidates.
  - `test_sweep_runs_the_harness_per_candidate`: with `subprocess.run` patched and `TUNING` at `START`, it is called 22 times, each with exactly the command above. A fake `summary.json` holding one figure prints it, and a missing one prints `n/a`.
  - `test_choose_tuning_follows_c310`, on synthetic figures:
    - quality picks the highest value that loses no within-one photo
    - T picks the most within-one photos within the limits, and a tie goes to the smaller T
    - a value is never chosen with one more underestimated photo, with an underestimation rate that rises while its count holds, with one more false flood on A-neg, or with 10.1 points less coverage
    - k, check 9's factors, the effort and the drawing stay as `start` has them
  - `test_reset_swept_keeps_set_b_and_c312_values` (P3): from a tuning with k 1.05, `rim_size_low` 0.80, effort `low`, drawing `boxes-v2`, and moved swept fields, `reset_swept` returns the 7 swept fields to `START`'s values and marks them untuned, and keeps the rest.
  - `test_replay_events_holds_each_event_out`, with 3 events: the harness rescored folders without E01's rows for E01's choice; `choose_tuning` got `start=TUNING`; each event's photos were replayed with its own chosen tuning; `replay.jsonl` has both replay outcomes for every Set A row and none for A-neg.
- [ ] **Step 3:** Run `uv run pytest -q tests/test_dev_eval.py`. Expected: the new tests FAIL.
- [ ] **Step 4:** Implement.
- [ ] **Step 5:** Run `uv run pytest -q`, then `uv run ruff check .`. Expected: PASS; clean.
- [ ] **Step 6:** Commit `feat(analysis): add the tuning sweep and event replay`.

### Task 14: The Manila check, the water phrases, the effort comparison and the type check (C313, C326, C312, C325, C323)

**Files:**
- Modify: `backend/analysis/probes/dev_eval.py`
- Test: `backend/analysis/tests/test_dev_eval.py`

**Interfaces:**
- Consumes: Task 12's `read_manifest`, `run_dir_for` and the runner's `live`; `save_sam_results`, `load_sam_results` (Task 9); `prepare_boxes`, `number_boxes`, `layout`, `check_ids_per_item`, `apply_drops`, `water_found`, `blur_for_meta`, `segment_all` (MS3a); `water_mask`, `find_waterline` (Task 2); `GEOMETRY_ONLY_TYPES` (Task 1)
- Produces, in `probes/dev_eval.py`:
  - `manila --set-a F [--phrase P]` (C313), from saved SAM outputs only:
    - The counted wheels are each photo's numbered wheels (`prepare_boxes`).
    - A wheel is left out when no water pixel lies in its mask box grown by 30 px.
    - It passes when `find_waterline(..., replace(TUNING, touch_tolerance_px=5.0, touch_share_min=0.25)).touch_share >= 0.25` and `|wheel ∩ water| / |wheel| < 0.10`.
    - It prints the photos, the photos with no water mask (k of n), and the wheels counted, passed and left out. The decision is `geometry kept` when passed ≥ counted ÷ 2, `geometry dropped` when fewer, and `untested` when nothing is counted.
    - `--phrase` reads one of C326's saved phrases as the water mask instead of `floodwater`. The thresholds stay exactly as written.
  - `water-phrases --manifest F [--photos DIR] [--yes]` (C326; paid, about $0.005 a photo): for each row, `blur_for_meta`, then `segment_all` with `"flood water"` and `"water"`, saved with `save_sam_results` under `<data_dir>/water_phrases/<set>/<photo_id>/`. It skips saved rows, and prints "N SAM calls, about $X" first, at $0.0025 a call.
  - `water-share --manifest F` (free): for `floodwater` (from the development runs) and each saved phrase, the photos with any water in the mask, as k of n. On development Set A that is recall; on development A-neg it is false water (W9).
  - `effort --manifest F --runs A,B,...` (C312, C325): for rows saved under every listed settings folder, it compares each with the first, the reference run. It prints for each:
    - n, and the answer items equal to the reference's (by id, every field) as k of n, with the wheels' items apart for the drawing (C325)
    - the saved outcomes identical to the reference's, as k of n
    - Muse Spark's seconds (median and max), and its output and reasoning tokens (median)
    - the median of the reference's slowest SAM phrase plus this run's Muse Spark seconds
    - the `photo_unusable` answers, and the photos whose people and wheels read more than one level apart by `disagree` (§D5)

    These are diagnostics, not rules §7 metrics.
  - `types --folder DIR [--yes]` (C323, W14; paid, about $0.03 a photo): for each photo in `DIR\images\` named in `DIR\puv_meta.csv` with a credit line in `DIR\attribution.csv` (R102; any without one is skipped and counted), a live run saved under `runs/set_c_puv/<settings>/<sha1>/`. The runs have geometry off (P11): the PUV photos' `ATTRIBUTION.md` says no geometry, and a wet road could reach step 4.6. Then, from the saved runs:
    - the subject is each photo's largest numbered vehicle, the one `puv_meta.csv` describes
    - the confusion matrix of the subject's answered `type` against `puv_meta.csv`'s `vehicle_type`, as counts, with photos that have no answered vehicle counted apart
    - replaying `apply_drops` on each saved answer, with and without `GEOMETRY_ONLY_TYPES`, the vehicles kept for a reading by answered type, and the subjects that `puv_meta.csv` expects as non-cars but that are kept, with geometry off (a typing error that lets them give wheel readings, against C45) and with it on (C318)
    - The gate isn't replayed: these are dry streets, which end "no flood seen" before step 4.6.

- [ ] **Step 1:** Read Tasks 12 and 13's `dev_eval.py`, so the new commands reuse `read_manifest`, `settings_name`, `run_dir_for` and the runner's `live`, never copies of them.
- [ ] **Step 2: Write the failing tests:**
  - `test_manila_check_counts_wheels` (C313), on saved runs built from `wheel_scene`:
    - a wheel whose water touches with no overlap → passed
    - the `overlap` scene, where water covers 50% of the wheel → counted, failed
    - a wheel with no water within 30 px → left out
    - a photo with an empty `floodwater` → the no-water count
    - the decision is kept at 1 of 2, dropped at 0 of 1, and untested at 0 of 0
    - with `--phrase "flood water"`, the saved alternative is the water mask
  - `test_water_phrases_print_cost_first_and_need_yes` (C326): 10 rows print "20 SAM calls, about $0.05" and exit 2 without `--yes`; with it, the fake records `flood water` and `water` for each photo, each on a `blur_for_meta` image.
  - `test_water_share_counts_photos_with_water`: 3 photos, 2 with water → 2 of 3, per phrase.
  - `test_effort_comparison` (C312): a reference run, a second default run that changes one wheel's waterline, and a `low` run that changes nothing → items 1 of 2 and 2 of 2, outcomes 1 of 1 each, the medians from the saved `elapsed_s` and `reasoning_tokens`, and the `photo_unusable` and person-against-wheel counts.
  - `test_type_check` (C323), on saved runs in `tmp_path` with a small `puv_meta.csv` and `attribution.csv`: a jeepney answered `jeepney` fills its cell and is kept neither way; a pedicab answered `unknown` is counted as a non-car kept with geometry on only; a jeepney answered `sedan_hatch` is counted as a non-car kept both ways; every live run is made with geometry off (P11); a photo without a credit line is skipped before any call; a folder under `sealed` → exit 2.
- [ ] **Step 3:** Run `uv run pytest -q tests/test_dev_eval.py`. Expected: the new tests FAIL.
- [ ] **Step 4:** Implement.
- [ ] **Step 5:** Run `uv run pytest -q`, then `uv run ruff check .`. Expected: PASS; clean.
- [ ] **Step 6:** Commit `feat(analysis): add the Manila check, the water phrases, the effort comparison and the type check`.

### Task 15: Set B rows (C314) and the early rim check (C323)

**Files:**
- Create: `backend/analysis/probes/set_b.py`
- Test: `backend/analysis/tests/test_set_b.py`

**Interfaces:**
- Consumes: `blur_for_meta`, `segment_all`, `save_sam_results`, `load_sam_results`, `water_mask`, `find_waterline`, `water_found`, `link_rims`, `rim_points`, `fit_rim`, `check_fit`, `rim_size_bounds`, `measure_rim` and `GeometryReading.fit`, `depth_inches`, `tire_codes`, `TireCode`, `quality_scores`, `results_manifest`, the runner's `refuse_sealed`
- **The input, in MS2's format:** `set_b\dev\generated\truth.csv`, one row per wheel per crop, keyed by `crop_id` and `wheel` (MS2's §5.9), with the crops in `crops\<crop_file>`. Rows and pixels are the crop's own. The fields used:
  - `crop_id`, `wheel`, `car_id`, `crop_file`, `vehicle_type`, `tire_code`
  - the wheel's box `x0`, `y0`, `x1`, `y1`, its `px_per_in` (G3's scale from the dry wheel) and `waterline_row` (at the wheel's centre)
  - `true_depth_in`, `view`, `size_bin` and `rim_edge_ratio`

  If MS2's format changes, MS2's wins: adapt the reader and record it.
- Produces, in `probes/set_b.py`:
  - `SET_B_PHRASES = ("floodwater", "wheel", "wheel rim")`
  - `read_wheels(path: Path, data_dir: Path) -> list[WheelRow]`, with every field checked. Pixel values are scaled by the factor `blur_for_meta` applies, sent width over the crop's width.
  - `segment --truth F [--yes]` (paid): for each crop, once whatever its wheels, `blur_for_meta`, then `segment_all` with the 3 phrases, saved with `save_sam_results` under `<data_dir>/set_b_runs/<crop_id>/`. It skips crops already saved, and prints "N SAM calls, about $X" first, at $0.0025 a call.
  - `wheel_estimates(row: WheelRow, sam: Mapping[str, SamResult], brightness: float, *, tuning: Tuning) -> dict[str, dict]`, keyed by the four variants of C314:
    - **MS2's true box only picks the SAM wheel** (finding 6): the one SAM wheel whose box holds the true box's centre. None or several such wheels → every variant `wheel_not_found`.
    - Rims link to the crop's SAM wheels by C300 (`link_rims`), and the fit and checks 6 and 9 use the SAM wheel's box, as the pipeline does. None or several linked rims → `rim_missing` or `rim_several`. So the variants differ only in `y_w` and k.
    - `geometry`: `y_w` from step 3 on the SAM wheel, with the frozen k (`tuning.rim_edge_k`)
    - `known_waterline`: `y_w = waterline_row`, with the frozen k
    - `geometry_uncalibrated` and `known_waterline_uncalibrated`: the same with k = 1, always written
    - Each variant runs `measure_rim` with `tire_codes(vehicle_type)`, so checks 4 to 9 match the pipeline's. A measured variant is `{"measured": true, "depthInPoint", "depthInMin", "depthInMax"}`, each unrounded, to 4 decimal places (C327; finding 2):
      - `depthInPoint` is `depth_inches(true code, ...)` from that reading's `fit`. A point depth of 0 or less makes the variant unmeasured, as `depth_not_positive` (C306).
      - the min and max are the reading's envelope
    - An unmeasured variant is `{"measured": false, "cause": <token>}`: a step 3 cause, `wheel_not_found`, or a `GEOMETRY_CAUSES` value, `rim_size` included.
  - `k_estimate(ratios_by_car: Mapping[str, Sequence[float]]) -> float | None`: the median of each car's median of `(2 r ÷ px_per_in) ÷ rim_in`, taken from the `fit` of each `known_waterline_uncalibrated` variant that measured. Check 9 thereby keeps hubcap and whole-wheel masks out of k (G3, C310).
  - `export --truth F --out DIR --rules-version V` (free): it writes `run.json` and `set_b.jsonl`, one row per wheel: `crop_id`, `wheel`, `car_id`, `vehicle_type`, `tire_code`, `true_depth_in`, `sam_water_found`, `bins` (MS2's `view` and `size_bin`, passed under those names, MS6's C423) and `estimates`. It prints the wheels, the measured count per variant, the wheels that fail check 9 by axis ratio, and `k_estimate` with its number of cars, beside the median of MS2's `rim_edge_ratio`, a cross-check from the dry rim mask (MS2's C212; C310).
  - `overlay --truth F --crop ID --wheel N` (free; P4): the crop with that wheel's SAM wheel and rim masks and its rim fit drawn, written under `<data_dir>/set_b_overlays/`, never in the repo. Task 17 uses it to check by eye whether a rim that fails check 9 is the true rim. It prints only the count of files written, never a path.
  - `rims --folder DIR [--yes]` (C323; paid, about $0.005 a photo): the early rim check on the Commons car photos, before Set B exists.
    - **The join (P2):** each `cars_meta.csv` row joins `attribution.csv` by `title`, and that row's `file_name` names the photo in `DIR\images\`. All 6 titles match. `cars_meta.csv` has no `file_name`, and its `sha1` is the Commons original's, while the files are 1920 px thumbnails. So `sha1` is only a key for the saved folder, never compared with a file's hash.
    - For each photo whose row gives `tire_code_candidates` (4 of the 6) and whose credit line is present, it runs `blur_for_meta`, then `segment_all` with `wheel` and `wheel rim`, saved under `<data_dir>/set_c_rims/<sha1>/`. It prints how many photos it matched before any call. For each wheel, it prints counts only:
      - one linked rim or not
      - the fit's points and axis ratio, fitting the whole rim (no waterline: `y_w` lies below the image)
      - whether check 9 passes at the candidates' bounds, with the SAM wheel's box
      - the rim-edge ratio `2 r ÷ (box height ÷ D) ÷ rim`, over the candidates
    - It is diagnostic only: nothing is tuned on it (C310 tunes k and check 9 on Set B development rims), and dry cars give no geometry depth.

- [ ] **Step 1:** As Task 12's Step 1, for `set_b.jsonl`: if MS6's loader is on `main`, match its field names and its rule for the uncalibrated variants (its draft gives them only when k isn't 1), and record any difference from C314.
- [ ] **Step 2: Write the failing tests** (crop images are `noise_jpeg()` files in `tmp_path`, and SAM results come from `wheel_scene(y_true=257)`; the wheel is a `sedan_hatch` on 175/65R14 with `px_per_in` 5.0, `waterline_row` 257, `true_depth_in` 8.08 and the box `(263, 183, 378, 257)`):
  - `test_read_wheels_validates`: a missing field, an unknown type or an unparseable code → `ValueError` naming the `crop_id` and `wheel`. A 2000 × 1500 crop scales its pixel values by 0.8.
  - `test_wheel_estimates_at_k_1`: all four variants give `depthInPoint` within 0.02 of 7.94, and `depthInMin` and `depthInMax` within 0.02 of 7.720 and 8.184, each with at most 4 decimal places.
  - `test_wheel_estimates_with_a_calibrated_k`: `rim_edge_k=1.05` → `geometry` and `known_waterline` give `depthInPoint` within 0.02 of 7.77, with min and max within 0.02 of 7.53 and 7.98; the two uncalibrated variants give 7.94, 7.720 and 8.184.
  - `test_the_true_box_only_picks_the_sam_wheel` (finding 6): a SAM wheel box 6 px off the true box still holds its centre, links its rim, and runs checks 6 and 9 on SAM's box. Two SAM wheels holding the true centre → `wheel_not_found` for every variant.
  - Review Focus 5, `test_sam_missing_water_still_measures_the_known_waterline`: an empty `floodwater` → `sam_water_found` false, `geometry` is `{"measured": false, "cause": "no_water_contact"}`, and `known_waterline` still measures, with its point within 0.02 of 7.94.
  - `test_k_is_the_median_of_car_medians`: `{"car01": [0.98, 1.00], "car02": [1.04], "car03": [1.10, 1.12, 1.08]}` → 1.04; `{}` → `None`.
  - `test_segment_prints_cost_and_needs_yes`: 20 crops print "60 SAM calls, about $0.15" and exit 2 without `--yes`; a crop with two wheel rows is sent once.
  - `test_set_b_paths_are_refused`: a truth file or crop under `set_b\sealed\`, or `--out` under `sealed` → exit 2.
  - `test_rows_are_the_contracts`: one written row has exactly the fields above, keyed by `crop_id` and `wheel`, with `bins == {"view": ..., "size_bin": ...}` from the truth row, and no number with more than 4 decimal places.
  - `test_rims_check_prints_counts_only` (C323), with a folder in `tmp_path`: only photos with codes and a credit line are sent, each through `blur_for_meta` with exactly the 2 phrases; the cost prints first and `--yes` is needed; the printout holds no name or path; a folder under `sealed` → exit 2.
  - `test_rims_check_joins_by_title` (P2): a `cars_meta.csv` row whose `sha1` isn't its file's hash, and matches no file name, still finds its photo through `attribution.csv`'s `title` and `file_name`. A title with no `attribution.csv` row is counted as unmatched and sent nothing.
  - `test_overlay_writes_under_the_data_dir` (P4): `overlay` writes one image for the named wheel under `LUSOT_DATA_DIR`, never in the repo; a path under `sealed` → exit 2.
- [ ] **Step 3:** Run `uv run pytest -q tests/test_set_b.py`. Expected: FAIL.
- [ ] **Step 4:** Implement.
- [ ] **Step 5:** Run `uv run pytest -q`, then `uv run ruff check .`. Expected: PASS; clean.
- [ ] **Step 6:** Commit `feat(analysis): write Set B rows for MS6's harness, and add the early rim check`.

### Task 16: The Set C checks and the Oct 31 decision (C312, C325, C323, C311; Claude)

**Files:** possibly `backend/analysis/src/lusot_analysis/tuning.py` and `tests/test_tuning.py`; `docs/log/<date>.md`

This task runs on Set C, before the split and before v0.7 (C322, C323), and opens no Set A or A-neg photo. The one exception is Step 1's: if development Set A and v0.7 both exist by then, C312 runs on Set A instead.

- [ ] **Step 1: The photos for C312.** If MS2's Set A development manifest exists and Rene has approved v0.7, use its first 10 rows by `photo_id`. Otherwise use C87's credited Commons photos at positions 0 to 9 of its order (STURM stays offline):
  - Write their manifest as `<LUSOT_DATA_DIR>\set_c\c312_manifest.csv`, with `photo_id` `C01` to `C10`, `set` `C`, and each `photo_file` from the paths that the smoke script's `seeded_photo_order` and `credited` give. Print only the count.
  - The photos sit in `commons-ph-floods\images\` beside it, so each command below passes `--photos commons-ph-floods\images` with a Set C manifest.
- [ ] **Step 2 (about $0.30):** the reference run: `dev_eval.py run --manifest <m> --limit 10 --yes`, with the key line.
- [ ] **Step 3 (about $0.15 each; Muse Spark alone, on the reference run's SAM outputs):** with `--sam-from default_boxes-v1`, run these 4:
  - `--repeat 2`: the default effort again, the baseline
  - `--effort low`
  - `--effort minimal`
  - `--drawing boxes-v2`, at the default effort
- [ ] **Step 4: Apply C312's rule, written before any result.** Run `dev_eval.py effort --manifest <m> --runs default_boxes-v1,default_boxes-v1_r2,low_boxes-v1,minimal_boxes-v1,default_boxes-v2`.
  - **Without labels (Set C):** a run is no worse when its answer items and its outcomes that match the reference are each at least the baseline run's counts.
  - **With M8 labels** (Set A, after v0.7): export each run's rows with `--runs <settings>`, and `--set` for that run's effort and drawing so the export's settings check passes, then run the harness. A run is no worse when its landmark agreement is at least the lower of the two default runs'.
  - Keep the lowest effort that is no worse: `minimal`, then `low`, else the default.
  - **The drawing follows MS3b-Q8's default (C325).**
    - On Set C, without labels, record the drawing run's figures and keep `boxes-v1` (P5). Task 17 decides the drawing on labelled photos.
    - With M8 labels, adopt `boxes-v2` only if its wheels' landmark agreement is no worse.
    - If a lower effort and `boxes-v2` both pass, run that pair once more (`--effort <E> --drawing boxes-v2`, about $0.15), and adopt the drawing only if the pair is no worse too (P16).
    - An adopted drawing counts as one of guard 4's 2 changes.
  - Record each run's figures, latency and reasoning tokens, and the `photo_unusable` and person-against-wheel counts (§D5). If those counts show a cost, put it to Rene as a new question, with the evidence. Prompt v1 stays until he answers.
  - If the effort or the drawing changes, set them in a new tuning version, with the change-log entry and its figures. Update `test_start_values_are_the_specs`, run the tests, and commit `feat(analysis): set Muse Spark's reasoning effort and drawing from the C312 test`.
- [ ] **Step 5 (about $0.57): the type check (C323, W14).** Run `dev_eval.py types --folder <LUSOT_DATA_DIR>\set_c\commons-puv-side --yes`, with the key line. Record the confusion matrix and the kept counts for D8. A non-car vehicle kept for geometry, such as a pedicab answered `unknown`, goes to Rene as a question with the evidence. Geometry keeps `unknown` as C318 says until he answers.
- [ ] **Step 6 (about $0.02): the early rim check (C323).** Run `set_b.py rims --folder <LUSOT_DATA_DIR>\set_c\commons-cars-side --yes`, with the key line. Record the counts. A real rim that fails check 9 is noted for Set B's check in Task 17, never tuned on.
- [ ] **Step 7 (optional, about $0.05): exploratory water phrases (C326).** Run `dev_eval.py water-phrases --manifest <m> --yes`, then `dev_eval.py water-share --manifest <m>`. Record the counts as exploratory: they never decide adoption.
- [ ] **Step 8 (Oct 31, C311's build gate):** the self-check is built only if all four hold:
  - MS3a is merged
  - D1 is green (Task 11)
  - D3 is green (Tasks 1 to 10, `uv run pytest -q`)
  - over C312's photos, the median of the slowest SAM phrase plus Muse Spark's time, at the chosen effort, is at most 10 s (C311; MS3b-Q3's default (a), v0.7 item 8.4). That median is only a lower bound on photo to pin, which also counts the upload, the queue, the blur and the publish (S4).

  Record the decision and its figures in the day's log and `docs/PROGRESS.md`.
  - **Yes:** start the self-check's own spec addendum and plan (the Superpowers loop, outside this plan). It is built by Nov 1 with its own development ablation, and C311's Nov 1 turn-off check follows. Its addendum sets the evidence record's `rechecked` (C328).
  - **No:** record "not built" and why.

### Task 17: Development data through the harness (C325, C313, C326, C314, C319, C310, C324, C315, C309; Claude)

**Files:** possibly `tuning.py`, the tests that pin start values, and `backend/template.yaml` (`GEOMETRY_IN_LEVEL`'s literal); results only under `LUSOT_DATA_DIR`

The steps run in this order: the drawing first, if it is still open, then Set B before the tuning, and the live default last, after the final ablation (finding 4).

- [ ] **Step 1: The harness.** Merge `main`, then run `python eval/run_eval.py --help` from the repo root. Expected: the usage text, exit 0. If it doesn't exist, every step below still writes its rows. Record that D2 and D7 wait for the harness, and run the harness steps once it merges.
- [ ] **Step 2: The data and the preconditions.**
  - Record which of MS2's files exist: Set A and A-neg development (MS3b-Q2), and Set B's development `truth.csv` (MS3b-Q1).
  - Check that `eval/rules.md`'s status line says v0.7, approved by Rene (C322). Until it does, Steps 3 to 5 and 8 to 10 wait, marked waiting. Steps 6 and 7 don't, since Set B shows no Set A result.
  - No Set A or A-neg photo is opened before the split.
  - **No development Set A by Oct 31:** Q2's (b) applies. The cutoffs stay untuned, C315 and C313 wait, and geometry stays on.
  - **Consented photos instead (P18):** if consented photos (M9) exist but development Set A doesn't, C313 can run on them. Write a manifest from `consented_log.csv`'s photo rows (`photo_id` from `item_id`, `set` `consented`, `photo_file` from `file`, and `--photos` naming their folder), run `dev_eval.py run` on it, then `manila` on it. They never join Set A (MS2's C218).
  - **No Set B by Oct 31:** Q1's (b) applies. D2 slips, and the release gate can't pass until it is done.
- [ ] **Step 3 (about $0.03 a photo): the development runs,** at the frozen effort and drawing: `dev_eval.py run --manifest <set_a_dev> --yes` and `dev_eval.py run --manifest <a_neg_dev> --yes`. They land in the tuning's settings folder, so they never mix with other efforts (finding 5). When C312 ran on Set A, its 10 rows at the chosen settings are already there, and the rest run in full.
- [ ] **Step 4: The drawing on labelled photos (MS3b-Q8's default; S1, P5).** Only when Task 16 ran C312 on Set C, which left the drawing open, and only if time allows before the freeze. Otherwise `boxes-v1` stays.
  - On the first 10 development Set A rows, Step 3's runs are the reference. Run `--repeat 2` and `--drawing boxes-v2`, both with `--sam-from <the tuning's settings>` (about $0.30). The drawing run uses the frozen effort, so the effort and the drawing are tested together (P16).
  - Export each run's rows with `--runs` and `--set` for its settings, and run the harness. Apply C312's rule to the wheels' landmark agreement.
  - If `boxes-v2` is no worse, set it in a new tuning version, as one of guard 4's 2 changes. Then re-run Muse Spark on every development row at the new settings (`dev_eval.py run --sam-from <the old settings> --yes`, about $0.60), so no run mixes drawings, and continue on those runs.
- [ ] **Step 5: The Manila check and the water phrases (C313, C326; about $0.20).**
  - Run `dev_eval.py manila --set-a <set_a_dev>`. Record the counts, the decision, and the share of photos with no water mask for Q1, beside the probe's small samples: 5 of 15 probe photos and 5 of 10 A2 photos (§D4) (D6).
  - Run `dev_eval.py water-phrases --manifest <set_a_dev> --yes` and the same for `<a_neg_dev>`. Then run `water-share` on both, and `manila --phrase` for each phrase. A phrase that finds water on more development Set A photos, with no more false water on development A-neg, goes to Rene as MS3b-Q6 with the figures. `floodwater` stays until he answers, and the phrases are frozen.
  - **If geometry is dropped** (Table 18): change `GEOMETRY_IN_LEVEL` to `"off"` in the template, and pass `--geometry-default dropped --dropped-reason manila_check` to every export from here on (MS6's C418). Commit `chore(backend): drop geometry from the level path after the Manila check`.
- [ ] **Step 6: Set B (C314, about $0.15).**
  - Run `set_b.py segment --truth <truth.csv> --yes`, then `set_b.py export --truth <truth.csv> --out <data>\dev_results\<date>-set-b --rules-version <v>`, then the harness on that folder.
  - **Check 9's factors first (C305, C310; finding 1, S3, P4).** A rim partly hidden behind the near sidewall can fall under the 0.85 factor at steep angles, which synthetic masks can't show.
    - From the export's printout, record how many development wheels fail check 9, and at what axis ratio, beside Task 16's rim check.
    - Look at each failing rim with `set_b.py overlay`. A mask that isn't the true rim (a hubcap, the whole wheel, or one cut by the frame) is left out. Record each one left out, with its cause, as counts in the results note.
    - If true rims still fail, move `rim_size_low` (or `rim_size_high`) only as far as needed to pass every true rim, and never below 0.50 nor above 1.55. Write a new tuning version with its n.
    - Then run Task 3's `test_hubcap_and_whole_wheel_rims_fail_rim_size`: under the new `TUNING`, the hubcap and the whole wheel must still fail. Re-export.
  - **Then k.** If `k_estimate` gives a value, set `rim_edge_k` in a new tuning version with its n of cars and MS2's `rim_edge_ratio` median beside it, then re-export and re-run the harness.
  - Record the Set B figures from the report: each variant, by type (W2) and by view and size (W7) (D2). Set B's crops stop at half tire (MS2's C211), so these figures cover readings up to half tire, and knee depth and deeper rest on Set A.
- [ ] **Step 7: The backup method (C319, D9).** If the `geometry` variant is under 70% measured or above a 3 in median error, the visible-height backup is built only if it fits before the freeze; otherwise record it. If neither holds, record that the trigger didn't fire.
- [ ] **Step 8: Tuning, then event replay (C310, C324).**
  - Run `dev_eval.py sweep ...`, then apply `choose_tuning(..., start=TUNING)` to the in-sample figures. When values change, write a new tuning version with each value's evidence (n and figures) in the change log, update the tests that pin start values, and commit `feat(analysis): tune the step 3 and geometry cutoffs on development data`.
  - Run `dev_eval.py replay-events ... --sweep <the sweep folder>`.
  - **§D7:** if C47's id drops (`wrong_list` and the like) recur on Manila development photos, record them. Only then is a minimum box size for numbering tuned, by the same rules (C310).
- [ ] **Step 9: The final ablation and guard 3 (C315, C324).**
  - Run `dev_eval.py export --set-a ... --m8 ... --a-neg ... --out <data>\dev_results\<date>-ablation --rules-version <eval/rules.md's version> --replay <replay.jsonl>` (with Step 5's geometry default), then `python eval/run_eval.py --from-saved --results <dir> --write`.
  - From the development report, record the ablation tables with coverage beside every rate and the replay columns (D7), the subsets (W4, W6, W8), A-neg (W9) and passability with within-one agreement (W5). Rene's `reflection` and `splash` marks come from the M8 sheet, made before the run (MS6's C414).
  - Count the refusals in W6's deep subset, photos whose alert gave tire or deeper, by cause (§D8; S7). The body floor for taller types stays MS3b-Q7's.
  - From the export's printout, record the G4 drops (W3). Check C70's caps and C56's 40 px against the drops before numbering (C310, P2, P6), and record whether either cut readable references.
  - **Guard 3 (P3):** if either configuration's replay is 3 or more photos below its in-sample within-one count, apply `reset_swept`. The 7 swept fields go back to `START`'s values, marked untuned, in a new tuning version whose change-log entry says why. Set B's k and check 9's factors, the effort, the drawing and the caps stay, so the development runs still match the tuning. Then re-export without `--replay`, re-run the harness, and commit.
- [ ] **Step 10: The live default (C309).** Read the final report's "outcome rule on development data". If geometry doesn't stay, change `GEOMETRY_IN_LEVEL` to `"off"` in the template, and commit `chore(backend): set geometry's live default from the development ablation`. Repeat this step after any later change to the tuning.
- [ ] **Step 11:** If `tuning.py` or the template changed, re-run `uv run pytest -q`, then deploy as Task 11's Steps 3 to 5 do (P8, R119):
  - Run `uv run backend/scripts/smoke_upload.py --bound 180`. Expected: `SMOKE OK`.
  - Only if geometry is still on and Task 11 recorded a position, also run `uv run backend/scripts/smoke_upload.py --bound 180 --geometry <that position>`. Expected: exit 0.

### Task 18: Results note and milestone close (D2 to D10; Claude)

**Files:**
- Create: `docs/research/<date>-ms3b-results.md`
- Modify: the spec's §6 table, this plan's boxes, `docs/PROGRESS.md` (the MS3 row; W2 to W9 and W14), the day's `docs/log/` note, and the design doc's decision log if anything new was decided

- [ ] **Step 1:** Write the results note, with counts and figures copied from the harness's reports and n beside each:
  - D1: the cloud photo's outcome, and the B3 replay
  - D2 and D7: Set B's figures (up to half tire) and the ablation tables with their replay columns, or "waits for the harness"
  - D4: C312's effort and C325's drawing, with each run's figures, and the self-check decision
  - D5: the tuning change log, or "untuned"; the replay against the in-sample figures, and guard 3's result
  - D6: C313's counts, the no-water share beside the probe's small samples, and C326's phrase comparison
  - D8: W2 to W9 and W14, each called indicative, with the refusals in W6's deep subset by cause, and the Set C checks
  - D9: C319
  - D10: the evidence record's field list as sent to Window 4
  - the spend
  - the frozen values: the tuning version, the tire codes version, the reasoning effort, the drawing, the SAM phrases and geometry's default

  It holds no photo names, paths, images, key or account ID.
- [ ] **Step 2:** Add a "Result" column to the spec's §6, with ✅ or "partly met" and the evidence line for each of D1 to D10.
- [ ] **Step 3: Confirm v0.7 is applied (§D9).** Check that `eval/rules.md`'s status line says v0.7, approved by Rene, and that its §10 freeze list names the reasoning effort, the drawing version, the SAM phrases and MS3b's tuning values (v0.7 item 10.1, which carries MS3b-Q4). If it doesn't, record MS3b-Q4 and those freeze items as pending in `docs/PROGRESS.md`. MS3b edits nothing under `eval/`.
- [ ] **Step 4:** Run the checks. Expected: all clean.
  - `uv run pytest -q` and `uv run ruff check .`
  - `npm run check`
  - `node scripts/check_account_ids.mjs` and `uv run --python 3.13 scripts/check_no_plan_leak.py`, from the repo root
  - `git diff --name-only main | xargs grep -n -i -w "safe"`: nothing about flood conditions. Run it once more without `-w`, as MS3a's Task 17 did.
- [ ] **Step 5:** Run `security-review` (the dev tools build Meta clients from the key), then `superpowers:requesting-code-review` on the whole branch. Fix anything confirmed, and re-run Step 4.
- [ ] **Step 6 (P17):** Run `claude-md-management:revise-claude-md` for what MS3b adds: the commands `probes/dev_eval.py` and `probes/set_b.py`, the smoke script's `--bound` and `--geometry`, and the `GEOMETRY_IN_LEVEL` literal in the template, which a deploy applies. Rene approves the CLAUDE.md change before it is committed.
- [ ] **Step 7:** Commit `docs: record MS3b results and tick its done-checks`. Then use `superpowers:finishing-a-development-branch`: merge `ms3b-geometry` into `main`, and push to the private repo (D16).

### Task 19: The sealed-run entry point, `run_sealed.py` (MS6's C412; R117, C329)

*Added on Oct 29 by Window 3, from the tracker's cross-spec audit, row 5: a ruling under Rene's delegation. It starts after Task 18 merges MS3b into `main`, on a new branch from `main`, and is due by Nov 2. Building the entry point isn't the sealed run: the run stays Rene's gate (CLAUDE.md), and Claude never runs it.*

**Files:**
- Create: `backend/analysis/probes/run_sealed.py`
- Test: `backend/analysis/tests/test_run_sealed.py`

**Interfaces:**
- **Consumes:**
  - MS3a's pipeline: `run_pipeline` with `READING_PHRASES` (C66)
  - Task 9's saved runs: `RecordingClient`, `SavedOutputsClient`, `rebuild_outcome`, `save_sam_results` and `load_sam_results` (R108, R109); and the runner's conventions, R110's exit codes and `say()`'s masking
  - Task 12's export: `replay_configurations`, `photo_row`, `m8_boxes`, `label_or_marker` and `results_manifest` (C315, C327)
  - Task 15's Set B tools: `read_wheels`, `wheel_estimates` and its export, for Set B's final crops and, only if it rained, Set D's photos
  - the label words, from `python eval/run_eval.py --label-words`, run as a subprocess (MS6's C420)
  - MS2's guard copies in `probes/set_b_masks.py`: `require_sealed`, `console_ok`, `require_console`, `confirm` and `quiet` (MS2's C202). If MS2 hasn't merged by then, copy the seven guards verbatim from `eval/data/guards.py`, and extend MS2's parity test to the new copy.
  - MS6's row contract (its §4.3) and freeze (its §4.6)
- **Produces:** `python probes/run_sealed.py <sealed folder> [--resume RUN]`, as MS6's §4.5 step 6 and C412 describe:
  - **The folder.** It reads only inside a folder named `sealed`, by MS2's `require_sealed`: in any case, with a trailing dot or space, or as an NTFS stream name. Both the path as written and its resolved form must name it. This mirrors C66's runner, which refuses sealed paths, so each tool refuses the other's inputs.
  - **The console.** It starts only from an interactive console (`console_ok`: `GetConsoleMode` on stdin and stdout, MS2's C202), after Rene types a confirmation (`confirm`). `isatty()` isn't enough, because it passes on NUL, where an agent's shell sends stdin.
  - **The freeze.** It refuses a tree with changes, and any commit but the tagged freeze, or the second freeze for the one disclosed rerun (MS6's C413, C421). It records the freeze commit. It writes the last development report's `baseline_level` and `baseline_class`, from that report's `summary.json`, into `run.json` (MS6's C424).
  - **The labels (C420, C329).** Before any paid call, it checks every label with Task 12's `label_or_marker`. If any would become `(other words)`, it prints how many and stops with exit 2, unless Rene confirms that too. On his go-ahead, the export writes the marker, and those photos are excluded as unmapped. A label it can't read stops it.
  - **The run:**
    - It runs the frozen pipeline once per photo, with the self-check if it is on. It sends the same face-blurred photo the live system would (rules §10), with the 5 phrases the reading uses, skipping the face and plate phrases.
    - It saves the raw SAM masks and Muse Spark answers under the `sealed` folder (rules §10).
    - It replays the saved outputs for every configuration (C309, C315).
    - Set B's final crops, and any Set D photos, go through SAM's phrases and the geometry. Set D's `set_d_log.csv` rows (`photo_id`, `wheel` left or right, `ruler_depth_in`, `vehicle_type`, `tire_code`) are bridged to MS6's Set D rows.
  - **Paying once.** It pays for each photo once.
    - **Resume (MS6's C419):** a stop for a rejected key, a crash or a lost connection resumes as the same run. Photos with saved outputs are never sent again. `run.json` records each stop and its cause, and only a completed run is exported. A resume isn't the disclosed rerun.
    - **MS6E-Q6,** a photo that failed because Meta's service failed: under default (a), it is retried once before the export, and the count of retries is disclosed. A photo whose answer was invalid is never retried. Follow Rene's answer if it differs.
  - **The export.** Through MS3b's export, it writes only §4.3's fields to the repo's `eval/results/`. That is the one place any MS3b tool writes into the repo, and only in Rene's run (MS6 §4.5 step 6). Its `run.json` has `kind` `sealed`, the freeze commit, the frozen versions and each stop. The raw outputs stay under `sealed`.
  - **Output:** counts and timings only. It never prints a photo's name, a path, a label, an answer, a reason or a key, and every line masks 12-digit runs.

- [ ] **Step 1: Write the failing tests.** They use synthetic data only: `tmp_path` trees, flat test images and `FakeClient`.
  - A `tmp_path/"sealed"` folder made by a test is synthetic, not sealed data.
  - No test reads `lusot-data` or any real sealed folder, and none writes into the repo's `eval/results/`. No test makes a Meta call.
  - No one opens these test folders by hand: the deny rules on `**/sealed/**` block that anyway.

  The tests:
  - `test_refuses_a_folder_not_named_sealed`: a folder not named `sealed` exits 2 before anything is read. So does a path that reaches a `sealed` folder only through a link.
  - `test_refuses_a_non_console_stdin`: NUL, a pipe and a file all exit 2 before anything is read.
  - `test_refuses_a_dirty_tree_or_another_commit`, using a fake git reader.
  - `test_checks_every_label_before_paying`: a label with another word is counted before any client call. Declining the second confirmation exits 2, with no client call. Confirming goes on, and the export writes `(other words)` for it.
  - `test_pays_once_and_resumes`: a stop after photo 2 of 4, then a resume. That gives 4 sets of calls in all, and the stop is recorded in `run.json`.
  - `test_service_failure_is_retried_once`: under default (a), a 503 after the client's retries is retried once and counted. An invalid answer is never retried.
  - `test_export_holds_only_the_row_contract`: the rows hold only §4.3's fields, the raw outputs stay under the synthetic `sealed` folder, and `run.json` has `kind` `sealed`, the freeze commit and the baseline pair from a synthetic `summary.json`.
  - `test_prints_counts_only`: no name, path, label, reason or 12-digit run.
- [ ] **Step 2:** Run `uv run pytest -q tests/test_run_sealed.py`. Expected: FAIL.
- [ ] **Step 3:** Implement `run_sealed.py`, reusing the runner's helpers, Task 12's export and Task 15's Set B tools. It never imports `eval/` code (C321).
- [ ] **Step 4:** Run `uv run pytest -q`, then `uv run ruff check .`, then `node scripts/check_account_ids.mjs` from the repo root. Expected: PASS, clean and clean.
- [ ] **Step 5:** Commit `feat(analysis): add the sealed-run entry point (MS6 C412)`.
- [ ] **Step 6:** Run `security-review`, since the entry point reads sealed paths and builds a Meta client from the key, then `superpowers:requesting-code-review`. Fix anything confirmed, and re-run Step 4.
- [ ] **Step 7:** Tick D11 in the spec's §6 with its evidence. Then use `superpowers:finishing-a-development-branch` to merge into `main`, and push to the private repo (D16).
- [ ] **Step 8:** Tell the tracker that the entry point is built and tested on synthetic data only, for Window 4's freeze checklist (MS6's §4.5 step 4). Never run it on the real `sealed` folder.
