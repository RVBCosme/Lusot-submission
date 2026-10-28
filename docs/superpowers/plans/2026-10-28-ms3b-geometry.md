# MS3b Geometry Implementation Plan

> **Draft:** written before Rene approved the spec (D7). The executing controller reviews it before Task 1. It follows the spec at `860a294`, whose C321 hands all scoring to MS6's harness (MS3b only writes rows for it), plus the plan review's rulings R86 to R88: C303 starts at 10%, C317 is strict, and C305 gains check 9.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Steps 2 to 6 gain rim geometry. Each reference must stand in water that SAM sees, a wheel's rim gives a depth in inches, and the deeper of a wheel's two readings decides. The development rows, the Set B rows and the tuned cutoffs follow, and the API still returns no inches.

**Architecture:**
- **Pure modules on masks:** `pipeline/waterline.py` (step 3) and `pipeline/geometry.py` (rim linking, the fit, the checks, the formula and G4). `rules.py` gains the inch level rule and the tire codes (`tire_codes.json`). `tuning.py` holds every cutoff.
- **The pipeline:** `run_pipeline` runs step 3 after the gate, and geometry when `geometry_in_level` is on. `Outcome` carries `levelFrom` and the inches. The handler reads the setting from the template, and the API's allow-list stays as it is.
- **Development tools** in `backend/analysis/probes/` write MS6's §4.3 rows through `lusot_analysis/export.py`, and `python eval/run_eval.py` scores them (C400). MS3b computes no metric.

**Tech Stack:** Python 3.13 through uv: OpenCV 4.14.0 (`findContours`, `fitEllipse`) and NumPy; pytest, moto and ruff. Node 22 and Vitest for one API test. AWS SAM CLI and Docker Desktop for the deploy.

**Spec:** `docs/superpowers/specs/2026-10-28-ms3b-geometry-design.md` at `860a294` (C300 to C321), with the plan review's amendments to C303, C305 and C317 (R86 to R88), binding. The row contract is MS6's draft spec §4.3 (`C:\Systems\Lusot\lusot-wt\w4\docs\superpowers\specs\2026-10-28-ms6-evaluation-design.md`, read-only). Once MS6 merges, its copy in `main` wins. Executors read all three.

**Start condition:** after MS3a merges into `main`. Branch `ms3b-geometry` from `main` then. Every task changes files that MS3a's Tasks 1 to 13 create, so nothing starts earlier.

## Global Constraints

- **AWS:** as MS3a: region `ap-southeast-1`, profile `lusot`, `--no-cli-pager`, and `MSYS_NO_PATHCONV=1` in Git Bash for arguments that start with `/`.
- **Model IDs:** exactly `sam-3.1` and `muse-spark-1.3`. Never `muse-spark-1.3-contributor`.
- **The face blur comes first.** Every image sent to Meta comes from `blur_for_meta` or `BlurredImage.derive`: live runs, Set B crops and the effort test alike.
- **No new Meta call per photo.** Geometry uses masks the pipeline already requests (`wheel`, `wheel rim`, `floodwater`). The Lambda still makes 7 + 1 calls, the offline runner 5 + 1, and a replay none. Pay once (G2) is unchanged.
- **The Meta key:** as MS3a. It is never printed or written. A command that needs it sets it in the same PowerShell line: `$env:MODEL_API_KEY = [Environment]::GetEnvironmentVariable('MODEL_API_KEY','User'); <command>`.
- **Logs:** one JSON line per report, with C316's fields. Never masks, image data, a location, the key, an AWS error message or Muse Spark's `reason`. Inches may be logged.
- **Printed output:** counts and timings only, with runs of 12 digits masked. No photo names or paths.
- **What never enters the repo:** account IDs, the Meta Team ID, console links, emails, plan text (cite "plan §N"), photos of any set, manifests, run folders and results rows. Tests build synthetic images and masks only.
- **Sealed data:** nothing under a folder named `sealed` is opened, listed or searched. Every new script calls the runner's `refuse_sealed` on every path it is given before opening anything. Set B's final cars and Set D are never touched. No Set A or A-neg photo is opened before MS2's split.
- **Scoring belongs to MS6 (C321; MS6's C400).**
  - MS3b computes no `eval/rules.md` §7 metric, §8 gate, outcome rule or guard.
  - It writes MS6's §4.3 rows to a folder under `LUSOT_DATA_DIR`: never in the repo, and never a path with a part named `sealed`.
  - Then it runs `python eval/run_eval.py --from-saved --results <dir> --write` from the repo root.
  - `backend/analysis` never imports `eval/`, and nothing under `eval/` or the `w4` worktree is edited.
- **Exact values (spec §4, C301 to C308):**
  - **Step 3:** T = 5 px. In each lower-outline column, the edge is the top row of the water run that comes within T px of the object's lowest pixel (the run reaches into rows `y_low − T` to `y_low + T`). Lower-outline columns have their lowest object pixel in the bottom third of the object's mask box (`y_low − top ≥ 2 × height ÷ 3`). Fewer than a quarter of them touching → `no_water_contact`. `y_w` is the median edge row of the touching columns. Their interquartile range above 10% of the box height → `ragged_waterline` (C303 as amended, R86). The cut clears rows ≥ `y_w`.
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
      - The result must lie between 0.85 × the smallest and 1.15 × the largest of each code's `rim × cos φ ÷ (D × cos φ + W × sin φ)`, over the type's codes. Otherwise `rim_size`.
      - D is the tire's diameter and W its section width, both in inches. `cos φ` is the fit's axis ratio, and `sin φ = √(1 − cos² φ)`.
      - The ratio allows for the tread a box takes in when the wheel is seen at an angle.
    - any code's depth of 0 or less → `depth_not_positive` (C306)
  - **Formula:** `s = r ÷ (k × rim ÷ 2)`, `R = rim ÷ 2 + width × aspect ÷ 100 ÷ 25.4`, `depth = (c + R × s − y_w) ÷ s`. k = 1.0 until calibrated (G3).
  - **Inches:** the level is the level rule (`eval/rules.md` §1: upper limits 5, 8, 10, 13, 19, 26, 37 and 45 in) applied to the deepest code's depth. Inches are stored rounded outward to 0.1 in: min down, max up (C308).
  - **Tire codes (C304):**

    | Type | Codes |
    |---|---|
    | `sedan_hatch` | 175/65R14, 185/55R15, 185/60R15, 195/55R16 |
    | `suv_mpv` | 205/55R16, 205/55R17, 185/65R15, 195/60R16, 205/65R16, 205/60R17, 215/55R17 |
    | `van` | 215/70R16C |
    | `unknown` | every code above |
    | others | none |

  - **Figures read from the harness's report:** the release-gate targets (`eval/rules.md` §8: median error at most 3 in, at least 70% measured, envelope coverage at least 80%, no rise in underestimation), C309's guards (coverage falls by no more than 10 points, passability by no more than 5), and C319's trigger (under 70% measured, or a median error above 3 in).
- **Tuning uses development data only:** Set A and A-neg development photos after MS2's split, Set B development cars, and Set C.
- **Cost:**
  - Set B: about $0.15 (about 20 crops × 3 SAM phrases)
  - C312: under $2 (about $0.60 planned)
  - development runs: about $0.03 a photo, so about $1.10 for 40 photos
  - D1: at most $0.50 (up to 10 offline runs, MS3a's smoke run and one geometry photo)

  Every paid command prints its call count and estimated cost, and stops there unless given `--yes`.
- **Freeze:** the tuning version, the tire codes, the reasoning effort and `geometry_in_level`'s default are frozen before the sealed run, and each is recorded in the results folder's `run.json`.
- **Screen copy:** MS3b changes no screen. The word "safe" appears in nothing it writes.
- **Toolchain, commits, builds and shells:** as MS3a.
  - Python `>=3.13,<3.14` through uv. No dependency changes.
  - Conventional Commits ending with the session's attribution lines, written with `git commit -F <file>`. Never `--no-verify`.
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
5. **Set B's composited water that SAM can't see.** The SAM variants record the crop as unmeasured, the known-waterline variants still measure it, and `sam_water_found` is false. Task 12 `test_sam_missing_water_still_measures_the_known_waterline`.

## Execution notes

- **Routing (D18):**
  - Opus 5.5 at max: Tasks 1 to 12 and the code-quality reviews
  - Sonnet 5.5 at xhigh: the spec-compliance reviews
  - Claude itself: Task 9's paid steps, and Tasks 13 to 15
- **Order:** one task at a time, in number order. Task 9 deploys the core before the development tools, because C311's Oct 31 gate needs D1. Tasks 13 and 14 run when their data exists (MS3b-Q1 and Q2).
- **MS3a interfaces used** (names as the MS3a plan gives them):
  - `rules`: `LEVELS`, `PASSABILITY`, `level_index`, `Reading`, `WHEEL_ROWS`, `PEOPLE_ROWS`, `BODY_ROWS`, `HIDDEN_WHEEL`, `READING_TYPES`, `disagree`
  - `pipeline.types`: `Outcome` (its builders, `item_fields()`, `log_name`), `Reference`, `ModelClient`
  - `pipeline.segment`: `box_xyxy`, `segment_all`, `link_wheels`
  - `pipeline.references`: `Prepared`, `prepare_boxes`, `Layout`, `layout`, `water_found`, `KeptVehicle`, `KeptPerson`, `Kept`, `apply_drops`
  - `pipeline.measure.measure`, `pipeline.combine.combine`, and `pipeline.quality` (`QualityScores`, `quality_scores`, `quality_refusal`)
  - `pipeline`: `READING_PHRASES`, `PipelineRun`, `run_pipeline`
  - `pipeline.saved`: `RecordingClient`, `SavedOutputsClient`, and the run-folder layout of MS3a Task 9
  - `probes/run_pipeline.py`: `refuse_sealed`, `make_client`, `live`, `replay`, `main`
  - `prompts.load_prompt`, `handler.analyse`, `report_store.write_result`
  - `tests/fakes.py`: `SIZE`, `noise_jpeg`, `instance`, `sam_results`, `FakeClient`, `vehicle`, `wheel`, `person`, `answer`, `REPO_PROMPTS`, `level_case`
  - MS1's `SamInstance(id, box, mask, score)`: `box` is half-open `(x0, y0, x1, y1)` floats in sent-image pixels, `mask` is an H×W bool array, and `score` is `float | None`
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
    - `rim_edge_k: float = 1.0` (G3)
    - `brightness_min: float = 40.0` and `sharpness_min: float = 25.0` (C44)
    - `min_wheel_side_px: int = 40` (C56), `max_vehicles: int = 6`, `max_people: int = 6` (C70)
    - `reasoning_effort: str | None = None` (C312). `None` sends no effort, so Muse Spark picks its own.
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
    - `test_start_values_are_the_specs`: every start value above, and `version == "tuning-v1"`
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
  - `@dataclass(frozen=True) class Waterline: y_w: float | None; touch_share: float; iqr_px: float | None; box_height: int; cause: str | None`. The cause is `None`, `"no_water_contact"` or `"ragged_waterline"`.
  - `water_mask(result: SamResult, shape: tuple[int, int]) -> np.ndarray`: the union of the instances' masks; all False when there are none
  - `find_waterline(obj: np.ndarray, water: np.ndarray, tuning: Tuning) -> Waterline`, by this algorithm (the tests don't fix it alone):

    ```python
    ys, xs = np.nonzero(obj)
    if ys.size == 0:
        return Waterline(None, 0.0, None, 0, "no_water_contact")
    top = ys.min(); height = ys.max() - top + 1
    T = tuning.touch_tolerance_px
    lower, edges = 0, []
    for x in np.unique(xs):                    # each object column
        y_low = ys[xs == x].max()
        if y_low - top < 2 * height / 3:       # not a lower-outline column
            continue
        lower += 1
        for start, end in runs(water[:, x]):   # maximal runs of water, top down
            if start <= y_low + T and end >= y_low - T:
                edges.append(start)            # this run touches: its top is the edge
                break
    share = len(edges) / lower
    y_w = float(np.median(edges)) if edges else None
    iqr = float(np.percentile(edges, 75) - np.percentile(edges, 25)) if edges else None
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
  - `test_no_water_and_empty_masks`: no water → `no_water_contact` with `y_w is None`; an empty object mask → `no_water_contact` with `box_height == 0`.
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
  - `MIN_FIT_POINTS = 5`, `MIN_AXIS_RATIO = 0.5`, `RIM_SIZE_LOW = 0.85`, `RIM_SIZE_HIGH = 1.15` (R88; spec values, not tuned)
  - `GEOMETRY_CAUSES`, in check order: `("waterline_not_visible", "no_tire_codes", "rim_missing", "rim_several", "waterline_dropped", "not_daylight", "rim_score_low", "rim_fit_points", "rim_fit_off_wheel", "rim_axis_ratio", "water_above_hub", "rim_size", "depth_not_positive")`
  - `rim_size_bounds(codes: Sequence[TireCode], axis_ratio: float) -> tuple[float, float]` (check 9, R91): `RIM_SIZE_LOW × min` and `RIM_SIZE_HIGH × max`, over the codes, of `rim_in × c ÷ (D × c + W × s)`. Here `c = axis_ratio`, `s = √(1 − c²)`, `D = 2 × radius_in` and `W = width_mm ÷ 25.4`.
  - `link_rims(wheels: Sequence[SamInstance], rims: Sequence[SamInstance]) -> list[tuple[SamInstance, ...]]` (C300): for each wheel, the rims that `link_wheels(wheels, rims)` assigns to it. That reuses C55's rule: the one wheel whose box holds the rim box's centre, edges included.
  - `@dataclass(frozen=True) class RimFit: centre_x: float; centre_y: float; r: float; axis_ratio: float; width_x: float; points: int`. `width_x` is the fit's horizontal extent, by the formula above (R89).
  - `rim_points(rim_mask: np.ndarray, y_w: float, tolerance_px: float) -> np.ndarray`: the outer contour points (N × 2 int32, `(x, y)`) of `cut_at_waterline(rim_mask, y_w)`, over every contour, keeping `y < y_w − tolerance_px`
  - `fit_rim(points: np.ndarray) -> RimFit | None`: `None` with fewer than 5 points, or when the centre or an axis isn't finite or an axis isn't positive
  - `check_fit(fit: RimFit, *, wheel_box: tuple[float, float, float, float], y_w: float, codes: Sequence[TireCode]) -> str | None`: `rim_fit_off_wheel`, then `rim_axis_ratio`, then `water_above_hub`, then `rim_size` when `fit.width_x ÷ (x1 − x0)` lies outside `rim_size_bounds(codes, fit.axis_ratio)` (bounds included; R89, R91)
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
  - `test_fit_needs_five_points` (check 6): 4 points on a circle give `None` without raising; 5 points on a circle of radius 30 give `r == approx(30, abs=0.01)`.
  - `test_rim_points_skip_the_cut_edge` (spec §4 step 5): `wheel_scene(y_true=257)`'s rim with `y_w = 257` gives points all with y < 252, and a fit with its centre at (320.0, 239.6) ± 0.5 and `r == approx(34.5, abs=0.5)`.
  - `test_formula_hand_computed` (Table 7; exact to 1e-4):
    - 175/65R14, `r=35, k=1.0, centre_y=200, y_w=220`: s = 5.0, R = 11.4783, depth 7.4783 (7.5 in) → `gutter`
    - 215/70R16C, `r=40, k=1.0, centre_y=300, y_w=300`: depth 13.9252 (13.9 in) → `knee`. At the hub, the Hiace reads knee, where Table 8's hub row says half-tire (G4).
    - 195/55R16, `r=42, k=1.05, centre_y=100, y_w=110`: s = 5.0, depth 10.2224 (10.2 in) → `half_tire`
  - `test_envelope_over_the_sedan_codes`: `r=35, k=1.0, centre_y=200, y_w=215` over `tire_codes("sedan_hatch")` gives 8.4783, 8.2916, 8.6558 and 8.7939. `geometry_reading` gives min 8.2916, max 8.7939 and `half_knee`, which `round_out` stores as 8.2 and 8.8.
  - `test_depth_not_positive_boundary` (C306): `geometry_reading([0.0, 3.0]) == "depth_not_positive"`; `[0.01, 3.0]` gives `GeometryReading(0.01, 3.0, "below_gutter")`.
  - `test_rim_size_bounds_from_the_codes` (R88, R91), hand-computed as `rim × c ÷ (D × c + W × s)`. All values to 1e-4.
    - **`sedan_hatch` at axis ratio 1.0** (s = 0, so the ratio is rim ÷ D): 175/65R14 gives 14 ÷ 22.9567 = 0.6098; 185/55R15, 15 ÷ 23.0118 = 0.6518; 185/60R15, 15 ÷ 23.7402 = 0.6318; 195/55R16, 16 ÷ 24.4449 = 0.6545. Bounds: 0.85 × 0.6098 = 0.5184 and 1.15 × 0.6545 = 0.7527.
    - **`sedan_hatch` at axis ratio 0.6** (s = 0.8; W = 6.8898, 7.2835, 7.2835 and 7.6772 in):
      - 175/65R14: 8.4 ÷ (13.7740 + 5.5118) = 0.4356
      - 185/55R15: 9.0 ÷ (13.8071 + 5.8268) = 0.4584
      - 185/60R15: 9.0 ÷ (14.2441 + 5.8268) = 0.4484
      - 195/55R16: 9.6 ÷ (14.6669 + 6.1417) = 0.4613
      - Bounds: 0.85 × 0.4356 = 0.3702 and 1.15 × 0.4613 = 0.5306.
    - **The other types at 1.0:** `suv_mpv` (0.5134, 0.7555), `van` (0.4883, 0.6607), `unknown` (0.4883, 0.7555).
  - `test_check_fit_boundaries`: the base is `RimFit(centre_x=320.0, centre_y=240.0, r=35.0, axis_ratio=0.9, width_x=70.0, points=50)` with wheel box `(263, 183, 378, 257)`, `y_w = 257` and the sedan codes → `None`. Its rim size, 70 ÷ 115 = 0.6087, lies inside the bounds at 0.9, which are 0.4526 to 0.6533. Then:
    - `axis_ratio` 0.5 → `None`; 0.4999 → `rim_axis_ratio`
    - `y_w` 240.0 → `None` (at the hub); 239.99 → `water_above_hub`
    - `centre_x` 263.0 → `None` (on the edge); 262.99 → `rim_fit_off_wheel`
    - check 9 (R88, R89, R91), with `axis_ratio=1.0` (bounds 0.51837 and 0.75271) and wheel box `(300, 183, 400, 257)` (width 100, so the rim size is `width_x ÷ 100`): `width_x` 51.86 → `None`; 51.82 → `rim_size`; 75.26 → `None`; 75.28 → `rim_size`
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
    - each within 0.002
    - `keep_reading(WHEEL_ROWS["rim_quarter"], None)` keeps the landmark, so a failed rim leaves the wheel its landmark reading
- [ ] **Step 3:** Run `uv run pytest -q tests/test_geometry.py`. Expected: FAIL, except the Step 1 test.
- [ ] **Step 4:** Implement `geometry.py`.
- [ ] **Step 5:** Run `uv run pytest -q`, then `uv run ruff check .`. Expected: PASS; clean.
- [ ] **Step 6:** Commit `feat(analysis): add rim geometry with its checks, the formula and G4`.

### Task 4: Results that carry their source and inches

**Files:**
- Modify: `backend/analysis/src/lusot_analysis/pipeline/types.py`, `backend/analysis/src/lusot_analysis/pipeline/combine.py`
- Test: `backend/analysis/tests/test_pipeline_types.py`, `backend/analysis/tests/test_combine.py`

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
- [ ] **Step 2:** Run `uv run pytest -q tests/test_pipeline_types.py tests/test_combine.py`. Expected: the new tests FAIL.
- [ ] **Step 3:** Implement as specified.
- [ ] **Step 4:** Run `uv run pytest -q`, then `uv run ruff check .`. Expected: PASS; clean. Every MS3a test other than `test_outcome_item_fields` passes unchanged.
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
      3. C43 runs over the kept wheel readings.
      4. The body is read only for `READING_TYPES` (C53). A body in `step3_drops` gives a non-deciding reference and counts under its cause.
      5. The deepest deciding candidate speaks, with C54's tie order. A vehicle dropped by C53 or C43 gives no references, deciding or not.
    - **Each person:** in `step3_drops`, a non-deciding reference counted under its cause; otherwise as in MS3a.
    - `landmark` is always Muse Spark's category (C320). For a van, it is the answered waterline.

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
  - `test_a_dropped_vehicle_gives_nothing`: a C53-dropped vehicle whose wheel step 3 also dropped → no references at all.
- [ ] **Step 2:** Run `uv run pytest -q tests/test_apply_drops.py tests/test_measure.py`. Expected: the new tests FAIL.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** Run `uv run pytest -q`, then `uv run ruff check .`. Expected: PASS; MS3a's tests unchanged; clean.
- [ ] **Step 5:** Commit `feat(analysis): read wheels by G4, keep vans for geometry and keep step 3's drops for C317`.

### Task 6: The pipeline: step 3 after the gate, `geometry_in_level`, reasoning effort and logs

**Files:**
- Modify:
  - `backend/analysis/src/lusot_analysis/pipeline/__init__.py`
  - `backend/analysis/src/lusot_analysis/pipeline/references.py` (add `instances_by_id`)
  - `backend/analysis/src/lusot_analysis/pipeline/types.py` (`ModelClient.judge`)
  - `backend/analysis/src/lusot_analysis/pipeline/saved.py` (the two clients' `judge` signatures only)
  - `backend/analysis/src/lusot_analysis/meta_client.py`
  - `backend/analysis/tests/fakes.py`
- Test: `backend/analysis/tests/test_pipeline.py`, `backend/analysis/tests/test_meta_client.py`, and any MS3a test Step 4 lists

**Interfaces:**
- Consumes: Tasks 1 to 5
- Produces:
  - `meta_client.REASONING_EFFORTS = ("minimal", "low", "medium", "high", "xhigh", "max")`, from Meta's reasoning page (read Oct 28; `none` returns HTTP 400 for Muse Spark). `MetaClient.judge(..., reasoning_effort: str | None = None)` sends `"reasoning": {"effort": value}` only when it is set. Any value outside the tuple raises `ValueError` before a request is sent.
  - `ModelClient.judge`, `RecordingClient.judge` (passes it through) and `SavedOutputsClient.judge` (ignores it) accept `reasoning_effort`. `FakeClient` records it the way it records `deadline` (MS3a Task 7a).
  - `references.instances_by_id(prepared: Prepared, layout: Layout) -> dict[int, SamInstance]`: the k-th numbered box of a kind is the k-th kept instance of its phrase
  - `PipelineRun` gains `wheel_inches: Mapping[int, tuple[float, float]] = field(default_factory=dict)`: the unrounded inches of every wheel geometry measured, before G4
  - `run_pipeline(data, client, prompt, *, phrases=SAM_PHRASES, deadline=None, geometry_in_level: bool = False, tuning: Tuning = TUNING) -> PipelineRun`:
    - **Steps 0 to 4.5** are unchanged, except that step 1 uses `quality_refusal(scores, tuning)` and `judge` gets `reasoning_effort=tuning.reasoning_effort`.
    - **Step 4.6:** `apply_drops(..., geometry_types=GEOMETRY_ONLY_TYPES if geometry_in_level else frozenset())`.
    - **Step 3 (C317, after the gate):** `water = water_mask(sam["floodwater"], (image.height, image.width))`. Then `find_waterline(instance.mask, water, tuning)` runs for:
      - each kept vehicle's wheels answered other than `not_visible`
      - each kept person whose `PEOPLE_ROWS` reading isn't `None`
      - each kept `READING_TYPES` vehicle whose body gives a reading (`wheels_hidden`, and `BODY_ROWS[body]` isn't `None`)

      Every Waterline with a cause enters `step3_drops`.
    - **Steps 4 and 5, only with geometry on:**
      - `link_rims(kept wheel instances, sam["wheel rim"].instances)`
      - for every wheel of a kept vehicle: `wheel_geometry(answer_waterline=..., codes=tire_codes(vehicle_type), rims=..., waterline=..., wheel_box=box_xyxy(instance), brightness=scores.brightness, tuning=tuning)`
    - **Then** `measure(kept, step3_drops=..., geometry=...)` and `combine`, as before.
  - **New log keys (C316):**
    - always: `geometry_in_level` (`"on"` or `"off"`), `tuning_version`, `rim_edge_k`, and `reasoning_effort` (its value, or `"default"`)
    - with geometry on: `wheels_measured` and `geometry_checks` (`{cause: count}`)
    - on level results: `level_from`, plus `depth_in` (`[min, max]`, rounded out) when it is `"geometry"`
    - step 3's causes and `wheel_methods_disagree` join `drops`
- Produces, in `tests/fakes.py`: `geometry_case(vehicle_type="sedan_hatch", waterline="rim_quarter") -> tuple[bytes, dict[str, SamResult], dict]`, the photo, SAM results and answer below. Tasks 7 to 10 reuse it.
  - the photo is `noise_jpeg()`
  - from `wheel_scene(y_true=257)`, built with `instance(..., mask=...)`: `wheel` box `(263, 183, 378, 257)`, `wheel rim` box `(285, 205, 356, 257)` and `floodwater` box `(0, 257, 640, 480)`. `vehicle` is `(150, 100, 500, 300)`. Other phrases are empty.
  - the answer: vehicle 1 of the given type, not moving, body `not_visible`; wheel 2 at the given waterline

- [ ] **Step 1: Write the failing tests:**
  - `test_judge_sends_reasoning_effort_only_when_set` (`test_meta_client.py`): `"low"` puts `"reasoning": {"effort": "low"}` in the request JSON. `None` sends no `reasoning` key. `"none"` and `"turbo"` raise `ValueError` with no request made.
  - `test_geometry_result_end_to_end`, with `geometry_case()` and `geometry_in_level=True`:
    - the outcome is `half_knee`, landmark `rim_quarter`, `level_from == "geometry"`, with `depth_in_min` and `depth_in_max` within 0.02 of 7.720 and 8.184
    - `item_fields()` has `depthInMin` 7.7 and `depthInMax` 8.2
    - the log has `wheels_measured == 1`, `geometry_checks == {}`, `tuning_version == "tuning-v1"`, `rim_edge_k == 1.0`, `reasoning_effort == "default"` and `depth_in == [7.7, 8.2]`
    - still 7 `segment` calls and 1 `judge`, so geometry made no new Meta call
    - `run.wheel_inches` has the key 2
  - `test_geometry_off_is_ms3a_plus_step3` (C309), with `geometry_case("van")`:
    - off: `no_usable_reference`, with `drops["vehicle_type"] == 1` and no `wheels_measured` key
    - on: `half_knee` from geometry, with depths within 0.02 of 9.887
  - `test_step3_runs_after_the_gate` (C317): `geometry_case()` with an empty `floodwater` and the answer's water `no` → `water_unsure` from the gate, and step 3 adds no drop.
  - `test_a_dry_reference_refuses_rather_than_reads_shallow` (C317): `level_case()` plus person 3, box `(450, 50, 480, 200)`, answered at `waist`. No water reaches the person, so the result is `references_disagree`, with `drops["no_water_contact"] == 1`.
  - Review Focus 3, `test_not_visible_wheel_gets_no_geometry`: `geometry_case(waterline="not_visible")` with geometry on → `geometry_checks == {"waterline_not_visible": 1}`, `wheels_measured == 0`, `no_usable_reference`, and no step 3 cause in `drops`.
  - `test_reasoning_effort_reaches_judge`: `tuning=replace(TUNING, reasoning_effort="low")` → the fake recorded `"low"`.
  - `test_log_keys_are_the_known_set` (C316): `set(run.log)` sits inside MS3a's keys plus the new ones above, so a mask can't reach the log.
- [ ] **Step 2:** Run `uv run pytest -q tests/test_pipeline.py tests/test_meta_client.py`. Expected: FAIL.
- [ ] **Step 3:** Implement. Read `meta_client.py` first to put `reasoning` where its `judge` builds the request.
- [ ] **Step 4:** Run `uv run pytest -q`. An MS3a test can now change outcome because its fake water doesn't touch a reference. Move that test's `floodwater` box so the water touches the reference, and never loosen step 3. List each such test in the task report. Then run `uv run ruff check .`. Expected: PASS; clean.
- [ ] **Step 5:** Commit `feat(analysis): run step 3 after the gate and geometry behind geometry_in_level`.

### Task 7: The offline runner and saved runs

**Files:**
- Modify: `backend/analysis/probes/run_pipeline.py`, `backend/analysis/src/lusot_analysis/pipeline/saved.py`
- Test: `backend/analysis/tests/test_run_pipeline.py`, `backend/analysis/tests/test_saved.py`

**Interfaces:**
- Consumes: `run_pipeline`'s new keywords (Task 6); `Tuning`, `TUNING`, `START`, `TIRE_CODES_VERSION`
- Produces, in `pipeline.saved`:
  - `save_sam_results(run_dir: Path, sam: Mapping[str, SamResult]) -> None` and `load_sam_results(run_dir: Path) -> dict[str, SamResult]`: MS3a's `sam/` layout, taken out of `RecordingClient.save` and `SavedOutputsClient`, with no change in behaviour
  - `SavedSamLiveJudge(saved: SavedOutputsClient, live: ModelClient)`: `segment` from the saved run, `judge` live
  - `run.json` gains `geometry_in_level` (bool), `tuning` (`asdict`, with `untuned` as a sorted list), `tire_codes_version`, `reasoning_effort` and `sam_from` (bool)
- Produces, in `probes/run_pipeline.py`:
  - `live(photo, data_dir, *, run_dir: Path | None = None, geometry_in_level: bool = True, tuning: Tuning = TUNING, sam_from: Path | None = None) -> tuple[Path, PipelineRun]`
  - the commands:
    - `live <photo> [--data-dir DIR] [--run-dir DIR] [--geometry on|off] [--effort E] [--sam-from RUN_DIR]`. `--effort` is a `REASONING_EFFORTS` value or `default`. `--sam-from` reuses that run's SAM outputs and pays for `judge` only.
    - `replay` uses the saved `geometry_in_level` and `tuning`. A run without them, from MS3a, replays with geometry off and `START`.
  - The printout adds `level_from`, `wheels_measured` and `geometry_checks` (Task 9 reads them).
  - `refuse_sealed` also covers `--run-dir` and `--sam-from`

- [ ] **Step 1: Write the failing tests:**
  - `test_live_records_the_geometry_config`: `geometry_case()` live gives a `run.json` with `geometry_in_level` true, tuning version `"tuning-v1"`, `tire_codes_version == "tire-codes-v1"` and `reasoning_effort` null.
  - `test_replay_uses_the_saved_config`: a `geometry_case("van")` run recorded with `--geometry off` replays to `no_usable_reference` and `same as saved: True`.
  - `test_effort_flag_reaches_judge`: `--effort low` → the fake recorded `"low"`, and `run.json` says `"low"`.
  - `test_sam_from_pays_only_for_judge`: a recorded run, then `live --sam-from <dir>` with a fake whose `segment` raises `AssertionError` → 0 `segment` calls and 1 `judge`. The new run replays to its own saved outcome.
  - `test_run_dir_flag_writes_there`, and `test_sealed_run_dirs_are_refused` (`--run-dir` or `--sam-from` under `sealed` → exit 2).
  - `test_old_runs_replay_with_geometry_off`: a `run.json` without the new keys → geometry off and `START`.
  - `test_sam_results_round_trip`: `save_sam_results`, then `load_sam_results`, gives equal boxes and scores, and `np.array_equal` masks. MS3a's saved-layout tests pass unchanged.
- [ ] **Step 2:** Run `uv run pytest -q tests/test_run_pipeline.py tests/test_saved.py`. Expected: FAIL.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** Run `uv run pytest -q`, then `uv run ruff check .`. Expected: PASS; clean.
- [ ] **Step 5:** Commit `feat(analysis): record the geometry setting, tuning and effort in saved runs`.

### Task 8: Storage, the handler, the API test and the template

**Files:**
- Modify: `backend/analysis/src/lusot_analysis/report_store.py`, `backend/analysis/src/lusot_analysis/handler.py`, `backend/template.yaml`
- Test: `backend/analysis/tests/test_report_store.py`, `backend/analysis/tests/test_handler.py`, `backend/api/test/reports.test.ts`

**Interfaces:**
- Consumes: `item_fields()` (Task 4); `run_pipeline(..., geometry_in_level=...)` (Task 6); the runner (Task 7)
- Produces:
  - `write_result` accepts `float` values as `{"N": str(value)}`. The order of checks is `str`, `bool`, `int`, `float`, then a mapping.
  - `handler._geometry_in_level() -> bool`, cached: `GEOMETRY_IN_LEVEL` `"on"` → True and `"off"` → False. Anything else, or no value, raises `ValueError`. It loads before the claim, with the key and the prompt, so a bad value returns the message and leaves the report `pending` (C60, C79).
  - `handler.analyse(data, client, *, deadline=None)` passes `geometry_in_level=_geometry_in_level()` (B3).
  - The template gains a Parameter `GeometryInLevel` (AllowedValues `on` and `off`, Default `on`), and the analysis function gets `GEOMETRY_IN_LEVEL: !Ref GeometryInLevel` (C309).
  - `GET /reports/{id}` doesn't change: its allow-list (MS3a Task 10) already leaves out `levelFrom`, `depthInMin` and `depthInMax` (C320).

- [ ] **Step 1: Write the failing tests:**
  - `test_writes_inches_as_numbers` (C308): `depthInMin` 8.2, `depthInMax` 8.8 and `levelFrom` `"geometry"` are stored as `{"N": "8.2"}`, `{"N": "8.8"}` and `{"S": "geometry"}`.
  - `test_geometry_setting_is_read_before_the_claim`, parametrized over unset and `"maybe"` → `RETRY`, the report stays `pending`, and the fake made no call.
  - `test_geometry_result_is_stored_with_its_source_and_inches` (C308): `geometry_case()` gives an item with `level` `half_knee`, `levelFrom` `geometry`, `depthInMin` 7.7 and `depthInMax` 8.2, stored as numbers.
  - `test_landmark_result_stores_level_from_only` (C320): `level_case()` gives `levelFrom` `landmark` and no `depthIn*`.
  - `test_b3_geometry_replay_matches` (D1, B3): the runner's `live()` records `geometry_case()` with geometry on. `replay(...).outcome == analyse(data, SavedOutputsClient(run_dir, data)).outcome`, and both carry the inches.
  - `test_log_line_carries_the_geometry_fields` (C316): the line has `geometry_in_level`, `tuning_version`, `rim_edge_k`, `reasoning_effort`, `wheels_measured`, `geometry_checks`, `level_from` and `depth_in`.
  - In `reports.test.ts`, `never returns levelFrom or the inches before the release gate` (C320): a stored level item with those three fields gives exactly MS3a's level body, and the body text contains none of the three names.
  - MS3a's handler and report-store tests that compare a level result's exact fields gain `levelFrom: "landmark"`. The handler fixture sets `GEOMETRY_IN_LEVEL=on`.
- [ ] **Step 2:** Run `uv run pytest -q tests/test_report_store.py tests/test_handler.py` and `npm test -w backend/api` (from the repo root). Expected: the Python tests FAIL. The API test PASSES with no code change. If it fails, the allow-list leaks: fix it in `reports.ts`.
- [ ] **Step 3:** Implement the store, the handler and the template.
- [ ] **Step 4:** Run `uv run pytest -q` and `uv run ruff check .`. From `backend`, run `sam validate --lint --profile lusot --region ap-southeast-1` and `grep -n "GEOMETRY_IN_LEVEL" template.yaml`. Expected: PASS; clean; valid; one match.
- [ ] **Step 5:** Commit `feat(analysis): store levelFrom and the inches, and read geometry_in_level from the template`.

### Task 9: Deploy and the cloud geometry check (D1; spends Meta credits)

**Files:**
- Modify: `backend/scripts/smoke_upload.py`
- Test: `backend/scripts/test_smoke_upload.py`

**Interfaces:**
- Consumes: MS3a Task 15's `as_app_jpeg`, `wait_final`, `log_lines`, `seeded_sturm_order`, `refuse_sealed` and `say()`
- Produces:
  - `check_geometry_line(line: dict) -> None` raises `CheckFailed("no wheel measured")` unless `wheels_measured >= 1`
  - `check_no_inches(body: dict) -> None` raises `CheckFailed` when the body has `levelFrom`, `depthInMin` or `depthInMax` (C320)
  - `smoke_upload.py --geometry-photo PATH` uploads that one photo as the app sends it, waits for a final status (120 s), runs both checks, and prints the outcome, `level_from`, `wheels_measured` and `geometry_checks`

- [ ] **Step 1:** Write the failing tests:
  - `test_geometry_check_needs_a_measured_wheel`: `wheels_measured` 1 passes; 0 or missing → `CheckFailed`.
  - `test_api_body_hides_the_inches`: a body with any of the three fields → `CheckFailed`.

  Run them with MS3a's command (Task 15, Step 2). Expected: FAIL. Implement them, re-run, expect PASS, and commit `test(backend): add the smoke run's geometry check`.
- [ ] **Step 2 (Claude; about $0.03 a photo):** find a photo with a geometry reading, offline. Go through the STURM photos in `seeded_sturm_order` positions 0 to 9, one at a time: `uv run probes/run_pipeline.py live <photo> --geometry on`, with the key line. Stop at the first run whose output shows `wheels_measured` of at least 1, and record its position, never its name. If none of the 10 measures a wheel, D1's cloud half is partly met. Record that, continue, and let the first Manila or consented photo prove it.
- [ ] **Step 3:** With no Gradle build running, run `docker build -t lusot-analysis:ms3b backend/analysis` from the repo root. Then `docker run --rm --entrypoint python lusot-analysis:ms3b -c "from lusot_analysis.rules import tire_codes, TIRE_CODES_VERSION; print(TIRE_CODES_VERSION, len(tire_codes('unknown')))"` → `tire-codes-v1 12`.
- [ ] **Step 4:** Run `npm run deploy` from PowerShell. Expected: the stack updates, then `lifecycle: keep 3`.
- [ ] **Step 5:** Run `uv run backend/scripts/smoke_upload.py`, then `uv run backend/scripts/smoke_upload.py --geometry-photo <Step 2's photo>`. Expected: `SMOKE OK` both times. Record the outcome, `level_from`, `wheels_measured` and the seconds to a final status.
- [ ] **Step 6:** Check B3 on the real run: `$env:LUSOT_B3_RUN_DIR = '<Step 2's run dir>'; $env:LUSOT_B3_PHOTO = '<photo>'; uv run --directory backend/analysis pytest -q tests/test_handler.py -k b3`. Expected: all passed, 0 skipped.
- [ ] **Step 7:** Record the spend: the photos sent, 6 calls for each offline run, 8 for the cloud photo, and the estimate from the logged tokens.

### Task 10: The export: development rows for MS6's harness (C315)

**Files:**
- Create: `backend/analysis/src/lusot_analysis/export.py`, `backend/analysis/probes/dev_eval.py`
- Test: `backend/analysis/tests/test_export.py`, `backend/analysis/tests/test_dev_eval.py`

**Interfaces:**
- Consumes: `SavedOutputsClient`, `load_prompt`, `run_pipeline`, `PipelineRun.wheel_inches`, `round_out`, `Tuning`; the runner's `live` and `refuse_sealed`, loaded from the sibling file with `importlib.util.spec_from_file_location` as its tests load it
- **The input:** MS2's development manifests, one JSON Lines file per set. Each line is a §4.3 Set A or A-neg row without `outcomes`, `answer` and `wheel_inches`, plus `photo`: the photo's path under `LUSOT_DATA_DIR`. The tools need only `photo_id` (`^[A-Za-z0-9_-]{1,64}$`, unique) and `photo`. Every other field passes through unread, and `photo` never reaches a row. If MS2's format differs, MS2's wins (MS6 §4.3): adapt the reader in Step 1 and record how.
- Produces, in `lusot_analysis.export` (MS6's sealed-run entry point reuses it, C412; MS3b doesn't build that entry point):
  - `CONFIGURATIONS = {"landmark": False, "geometry": True}`: each outcome key and its `geometry_in_level`
  - `rebuild_outcome(saved: Mapping[str, object]) -> Outcome`: `Outcome(**saved)` from a saved `asdict`
  - `answer_without_reason(data: Mapping | None) -> dict | None`
  - `replay_configurations(photo_data: bytes, run_dir: Path, prompt: PromptSpec, *, tuning: Tuning = TUNING) -> dict[str, PipelineRun]`: one replay per configuration, with no Meta call
  - `photo_row(base: Mapping[str, object], runs: Mapping[str, PipelineRun], answer: Mapping | None) -> dict[str, object]`: `base` without `photo`, plus:
    - `outcomes`: `{key: run.outcome.item_fields()}`
    - `answer`
    - `wheel_inches`: `{"<box id>": {"depthInMin", "depthInMax"}}`, rounded out, from the `geometry` run
  - `results_manifest(*, date: str, rules_version: str, tuning: Tuning, saved_run: Mapping, geometry_default: str, datasets: Mapping) -> dict`: `kind` `"development"`, `date`, `rules_version`, and `versions` (models, prompt, blur, tuning, `rim_edge_k`, tire codes, reasoning effort). Also `datasets`, `self_check` (`{"state": "off", "decided": null}` until C311 says otherwise) and `geometry_default`.
- Produces, in `probes/dev_eval.py`:
  - `read_manifest(path: Path, data_dir: Path) -> list[dict]`
  - `run_dir_for(data_dir: Path, photo_id: str, subdir: str = "dev") -> Path`: `<data_dir>/runs/<subdir>/<photo_id>`
  - `run --manifest F [--limit N] [--effort E --sam-from-dev] [--yes]`: a live run for each row without a saved run. Effort runs go under `runs/effort-<E>/`, reusing `runs/dev/`'s SAM. It prints the photo count and the estimated cost first: $0.03 a photo, or $0.015 for an effort run.
  - `export --set-a F --a-neg F --out DIR --rules-version V [--set NAME=VALUE ...] [--runs-subdir dev] [--datasets JSON] [--geometry-default on|off]`:
    - It writes `run.json`, `set_a.jsonl` and `a_neg.jsonl`.
    - `--out` must lie under `LUSOT_DATA_DIR` and outside the repo, and no part of it may be named `sealed`.
    - A row without a saved run → exit 2 ("run `dev_eval.py run` first").
    - `--set` overrides a `Tuning` field for the replays.
    - It prints counts only: the photos, the G4 drops, `wheels_measured`, the geometry checks by cause, and the drops before numbering (`wheel_small`, `wheel_unlinked`, `vehicle_cap`, `wheel_cap`, `person_cap`; P2, P6). Then it prints the harness command to run next.

- [ ] **Step 1:** Check MS6's harness. If `eval/run_eval.py` and `eval/scoring/` exist on `main`, read its loader's contract (read-only) and match every row and `run.json` key it names, including `geometry_default`, `datasets` and `self_check`. Where its names differ from this task's, MS6's win; record each difference in the task report. If it doesn't exist yet, build to this task's names and record that.
- [ ] **Step 2: Write the failing tests** (runs recorded with the runner's `live()` and a `FakeClient`; manifests in `tmp_path`):
  - `test_rebuild_outcome_round_trips`: a landmark level, a geometry level with inches, no flood seen and a refusal each satisfy `rebuild_outcome(asdict(o)) == o`.
  - `test_answer_without_reason`: `reason` is gone and every other key stays; `None` gives `None`.
  - `test_photo_row_has_both_configurations`, on a `geometry_case("van")` run:
    - `outcomes.landmark` equals `Outcome.refused("no_usable_reference").item_fields()`
    - `outcomes.geometry` has `level` `half_knee`, `levelFrom` `geometry`, `depthInMin` 9.8 and `depthInMax` 9.9
    - `wheel_inches == {"2": {"depthInMin": 9.8, "depthInMax": 9.9}}`
    - `answer` has no `reason`, the base fields pass through, and `photo` is gone
  - `test_export_writes_the_results_folder`: two Set A rows and one A-neg row give 2 and 1 lines. `run.json` has `kind` `development`, the given `rules_version`, tuning `tuning-v1`, `rim_edge_k` 1.0, the tire codes version, `reasoning_effort` null and `geometry_default` `on`. The fake makes no call during the export.
  - `test_export_refuses_bad_paths`: `--out` under a `sealed` folder, `--out` inside the repo, or a manifest photo under `sealed` → exit 2, with nothing created.
  - `test_export_needs_every_run`: a row with no saved run → exit 2.
  - `test_rows_hold_no_free_text`: the written text has no `REASON-MARKER-31` and no photo path.
  - `test_run_prints_cost_first_and_needs_yes`: without `--yes` → exit 2, after printing the count and the cost. With it → a run folder for each row that lacked one; existing runs are kept.
  - `test_no_import_crosses_into_eval` (C400): an `ast` walk of `export.py`, `dev_eval.py` and `set_b.py` (once it exists) finds no import of `eval` or `eval.*`.
- [ ] **Step 3:** Run `uv run pytest -q tests/test_export.py tests/test_dev_eval.py`. Expected: FAIL.
- [ ] **Step 4:** Implement.
- [ ] **Step 5:** Run `uv run pytest -q`, then `uv run ruff check .`. Expected: PASS; clean.
- [ ] **Step 6:** Commit `feat(analysis): export development rows for MS6's harness`.

### Task 11: The tuning sweep, the Manila check and the effort comparison (C310, C313, C312)

**Files:**
- Modify: `backend/analysis/probes/dev_eval.py`
- Test: `backend/analysis/tests/test_dev_eval.py`

**Interfaces:**
- Consumes: Task 10's export; `load_sam_results` (Task 7); `prepare_boxes`, `water_found` (MS3a); `water_mask`, `find_waterline` (Task 2)
- Produces, in `probes/dev_eval.py`:
  - `SWEEP_GRID`: one field at a time, the others at `TUNING`. Quality cutoffs never go below `TUNING`'s, because a photo refused before Meta has no saved outputs.
    - `brightness_min` 40, 50, 60, 70; `sharpness_min` 25, 50, 100, 200
    - `daylight_brightness_min` 40, 60, 80, 100
    - `touch_tolerance_px` 3, 4, 5, 6, 8; `touch_share_min` 0.15, 0.25, 0.35, 0.5
    - `ragged_iqr_share` 0.06, 0.08, 0.10, 0.12. It stays under the 12.3% where R86's reflection case begins, so tuning can't reopen it.
    - `rim_score_min` 0.3, 0.5, 0.7
  - `sweep --set-a F --a-neg F --out DIR --rules-version V`:
    - For each candidate, it runs the export into `DIR/<field>-<value>/`, then `[sys.executable, <repo>/eval/run_eval.py, "--from-saved", "--results", <dir>, "--write"]`.
    - It prints one line per candidate with the figures `SUMMARY_FIGURES` names from that folder's `report/summary.json`, or `n/a`.
    - It chooses nothing: the controller applies C310's rules (Task 14).
  - `SUMMARY_FIGURES: dict[str, tuple[str, ...]]`: JSON paths, set in Step 1, to the `geometry` configuration's Set A within-one agreement, underestimation and coverage, as "k of n"
  - `manila --set-a F` (C313), from saved SAM outputs only:
    - The counted wheels are each photo's numbered wheels (`prepare_boxes`).
    - A wheel is left out when no water pixel lies in its mask box grown by 30 px.
    - It passes when `find_waterline(..., replace(TUNING, touch_tolerance_px=5.0, touch_share_min=0.25)).touch_share >= 0.25` and `|wheel ∩ water| / |wheel| < 0.10`.
    - It prints the photos, the photos with no water mask (k of n), and the wheels counted, passed and left out. The decision is `geometry kept` when passed ≥ counted ÷ 2, `geometry dropped` when fewer, and `untested` when nothing is counted.
  - `effort --manifest F --efforts low,minimal` (C312): for rows with both `runs/dev/<id>` and `runs/effort-<E>/<id>`, it prints for each effort:
    - n
    - answer items equal to the default's (by id, every field), as k of n
    - saved outcomes identical to the default's, as k of n
    - Muse Spark seconds (median and max) and output tokens (median)
    - the median of the default run's slowest SAM phrase plus this run's Muse Spark seconds

    These are diagnostics, not rules §7 metrics.

- [ ] **Step 1:** If MS6's harness is on `main`, read its `summary.json` writer and set `SUMMARY_FIGURES`. If any of the three figures is missing, record it. The sweep then prints `n/a`, and the controller reads each candidate's `report.md` instead. Otherwise leave `SUMMARY_FIGURES` empty.
- [ ] **Step 2: Write the failing tests:**
  - `test_sweep_grid_is_one_field_at_a_time`: 28 candidates, each differing from `TUNING` in exactly one field, with none below `TUNING`'s quality cutoffs and no `ragged_iqr_share` above 0.12.
  - `test_sweep_runs_the_harness_per_candidate`: with `subprocess.run` patched, it is called once per candidate with exactly the command above. A fake `summary.json` holding one figure prints it, and a missing one prints `n/a`.
  - `test_manila_check_counts_wheels` (C313), on saved runs built from `wheel_scene`:
    - a wheel whose water touches with no overlap → passed
    - the `overlap` scene, where water covers 50% of the wheel → counted, failed
    - a wheel with no water within 30 px → left out
    - a photo with an empty `floodwater` → the no-water count
    - the decision is kept at 1 of 2, dropped at 0 of 1, and untested at 0 of 0
  - `test_effort_comparison` (C312): a default run and a `low` run that changes one item's waterline but not the outcome → items 1 of 2, outcomes 1 of 1, and the medians from the saved `elapsed_s` values.
- [ ] **Step 3:** Run `uv run pytest -q tests/test_dev_eval.py`. Expected: the new tests FAIL.
- [ ] **Step 4:** Implement.
- [ ] **Step 5:** Run `uv run pytest -q`, then `uv run ruff check .`. Expected: PASS; clean.
- [ ] **Step 6:** Commit `feat(analysis): add the tuning sweep, the Manila check and the effort comparison`.

### Task 12: Set B rows (C314)

**Files:**
- Create: `backend/analysis/probes/set_b.py`
- Test: `backend/analysis/tests/test_set_b.py`

**Interfaces:**
- Consumes: `blur_for_meta`, `segment_all`, `save_sam_results`, `load_sam_results`, `water_mask`, `find_waterline`, `water_found`, `measure_rim` and `GeometryReading.fit`, `depth_inches`, `round_out`, `tire_codes`, `TireCode`, `quality_scores`, `results_manifest`, the runner's `refuse_sealed`
- **The input:** MS2's Set B development manifest, a JSON Lines file with one crop per line:
  - `crop_id`, `car_id`, `vehicle_type`, `tire_code` and `true_depth_in` (G3)
  - `image` (a path under `LUSOT_DATA_DIR`), `wheel_box` (`[x0, y0, x1, y1]`, the crop's own pixels, half-open)
  - `true_waterline_row`, `px_per_in` (G3's scale from the whole tire) and `angle` (a lowercase token)

  If MS2's generator writes another format, MS2's wins: adapt the reader and record it.
- Produces, in `probes/set_b.py`:
  - `SET_B_PHRASES = ("floodwater", "wheel", "wheel rim")`
  - `read_crops(path: Path, data_dir: Path) -> list[Crop]`, with every field checked. Pixel values are scaled by the factor `blur_for_meta` applies, sent width over the crop's width.
  - `segment --manifest F [--yes]` (paid): `blur_for_meta`, then `segment_all` with the 3 phrases, saved with `save_sam_results` under `<data_dir>/set_b_runs/<crop_id>/`. It skips crops already saved, and prints "N SAM calls, about $X" first, at $0.0025 a call.
  - `crop_estimates(crop: Crop, sam: Mapping[str, SamResult], brightness: float, *, tuning: Tuning) -> dict[str, dict]`, keyed by the four variants of the amended C314:
    - `geometry`: `y_w` from step 3 on the one SAM wheel whose box holds the true box's centre, with the frozen k (`tuning.rim_edge_k`). None or several such wheels → `wheel_not_found`.
    - `known_waterline`: `y_w = true_waterline_row`, with the frozen k
    - `geometry_uncalibrated` and `known_waterline_uncalibrated`: the same with k = 1, always written
    - The rim is the one whose box centre lies in the true wheel box, edges included, as C300 counts them (none → `rim_missing`, several → `rim_several`). So the variants differ only in `y_w` and k.
    - Each variant runs `measure_rim` with `tire_codes(vehicle_type)`, so checks 4 to 9 match the pipeline's. A measured variant is `{"measured": true, "depthInPoint", "depthInMin", "depthInMax"}`:
      - `depthInPoint` is `depth_inches(true code, ...)` from that reading's `fit`, to 0.01. A point depth of 0 or less makes the variant unmeasured, as `depth_not_positive` (C306).
      - the min and max are `round_out` of the reading's envelope
    - An unmeasured variant is `{"measured": false, "cause": <token>}`: a step 3 cause, `wheel_not_found`, or a `GEOMETRY_CAUSES` value, `rim_size` included.
  - `k_estimate(ratios_by_car: Mapping[str, Sequence[float]]) -> float | None`: the median of each car's median of `(2 r ÷ px_per_in) ÷ rim_in`, taken from the `fit` of each `known_waterline_uncalibrated` variant that measured. Check 9 thereby keeps hubcap and whole-wheel masks out of k (G3, C310).
  - `export --manifest F --out DIR --rules-version V` (free): it writes `run.json` and `set_b.jsonl`. Each row is `crop_id`, `car_id`, `vehicle_type`, `tire_code`, `true_depth_in`, `sam_water_found`, `bins` (`angle`, and `size`: `small` under 80 px, `medium` 80 to 159, `large` 160 and over, from the true box's longer side) and `estimates`. It prints the crops, the measured count per variant and `k_estimate` with its number of cars.

- [ ] **Step 1:** As Task 10's Step 1, for `set_b.jsonl`: if MS6's loader is on `main`, match its field names and its rule for the uncalibrated variants (its draft gives them only when k isn't 1), and record any difference from the amended C314.
- [ ] **Step 2: Write the failing tests** (crop images are `noise_jpeg()` files in `tmp_path`, and SAM results come from `wheel_scene(y_true=257)`; the crop is a `sedan_hatch` on 175/65R14 with `px_per_in` 5.0, true row 257, `true_depth_in` 8.08 and wheel box `(263, 183, 378, 257)`):
  - `test_read_crops_validates`: a missing field, an unknown type or an unparseable code → `ValueError` naming the `crop_id`. A 2000 × 1500 crop scales its pixel values by 0.8.
  - `test_crop_estimates_at_k_1`: all four variants give `depthInPoint` 7.94, with `depthInMin` 7.7 and `depthInMax` 8.2.
  - `test_crop_estimates_with_a_calibrated_k`: `rim_edge_k=1.05` → `geometry` and `known_waterline` give 7.77, 7.5 and 8.0; the two uncalibrated variants give 7.94, 7.7 and 8.2.
  - Review Focus 5, `test_sam_missing_water_still_measures_the_known_waterline`: an empty `floodwater` → `sam_water_found` false, `geometry` is `{"measured": false, "cause": "no_water_contact"}`, and `known_waterline` still measures 7.94.
  - `test_k_is_the_median_of_car_medians`: `{"car01": [0.98, 1.00], "car02": [1.04], "car03": [1.10, 1.12, 1.08]}` → 1.04; `{}` → `None`.
  - `test_segment_prints_cost_and_needs_yes`: 20 crops print "60 SAM calls, about $0.15" and exit 2 without `--yes`.
  - `test_set_b_paths_are_refused`: a manifest or image under `set_b\sealed\`, or `--out` under `sealed` → exit 2.
  - `test_rows_are_the_contracts`: one written row has exactly the fields above, and `bins.size == "medium"`.
- [ ] **Step 3:** Run `uv run pytest -q tests/test_set_b.py`. Expected: FAIL.
- [ ] **Step 4:** Implement.
- [ ] **Step 5:** Run `uv run pytest -q`, then `uv run ruff check .`. Expected: PASS; clean.
- [ ] **Step 6:** Commit `feat(analysis): write Set B rows for MS6's harness`.

### Task 13: The effort test and the Oct 31 decision (C312, C311; Claude)

**Files:** possibly `backend/analysis/src/lusot_analysis/tuning.py` and `tests/test_tuning.py`; `docs/log/<date>.md`

- [ ] **Step 1: The photos.** If MS2's Set A development manifest exists, use its first 10 rows by `photo_id`. Otherwise write a manifest under `LUSOT_DATA_DIR`: `photo_id` `c-01` to `c-10` for STURM's seeded positions 0 to 9, which MS1's probe already sent to Meta (C12).
- [ ] **Step 2 (about $0.27):** `dev_eval.py run --manifest <m> --limit 10 --yes`, with the key line.
- [ ] **Step 3 (about $0.15 each):** the same with `--effort low --sam-from-dev`, then with `--effort minimal --sam-from-dev`.
- [ ] **Step 4:** Run `dev_eval.py effort --manifest <m> --efforts low,minimal`, and keep the lowest effort that passes the rule:
  - With M8 landmark labels in the rows: export each effort's rows (`--runs-subdir effort-<E>`), run the harness, and keep an effort only if its landmark agreement is no worse than the default's.
  - Without them: keep an effort only if every outcome equals the default's. That is this plan's reading of "no worse" when the default is the reference.

  If one is kept, set `reasoning_effort` in a new tuning version. Add the change-log entry with its figures, update `test_start_values_are_the_specs`, run the tests, and commit `feat(analysis): set Muse Spark's reasoning effort from the C312 test`.
- [ ] **Step 5 (Oct 31, C311's build gate):** the self-check is built only if all four hold:
  - MS3a is merged
  - D1 is green (Task 9)
  - D3 is green (Tasks 1 to 8, `uv run pytest -q`)
  - the chosen effort's median SAM plus Muse Spark time is at most 10 s (MS3b-Q3's default (a))

  Record the decision and its figures in the day's log and `docs/PROGRESS.md`.
  - **Yes:** start the self-check's own spec addendum and plan (the Superpowers loop, outside this plan). It is built by Nov 1 with its own development ablation, and C311's Nov 1 turn-off check follows.
  - **No:** record "not built" and why.

### Task 14: Development data through the harness (C315, C309, C310, C313, C314, C319; Claude)

**Files:** possibly `tuning.py`, the tests that pin start values, and `backend/template.yaml` (`GeometryInLevel`'s default); results only under `LUSOT_DATA_DIR`

- [ ] **Step 1: The harness.** Merge `main`, then run `python eval/run_eval.py --help` from the repo root. Expected: the usage text, exit 0. If it doesn't exist, every step below still writes its rows. Record that D2 and D7 wait for the harness, and run the harness steps once it merges.
- [ ] **Step 2: The data.**
  - Record which of MS2's manifests exist: Set A and A-neg development (MS3b-Q2), and Set B development with the G3 truth (MS3b-Q1).
  - No Set A or A-neg photo is opened before the split.
  - **No development Set A by Oct 31:** Q2's (b) applies. The cutoffs stay untuned, C315 and C313 wait, and geometry stays on.
  - **No Set B by Oct 31:** Q1's (b) applies. D2 slips, and the release gate can't pass until it is done.
- [ ] **Step 3 (about $0.03 a photo):** run `dev_eval.py run --manifest <set_a_dev> --yes` and `dev_eval.py run --manifest <a_neg_dev> --yes`.
- [ ] **Step 4: The ablation (C315).**
  - Run `dev_eval.py export --set-a ... --a-neg ... --out <data>\dev_results\<date>-ablation --rules-version <eval/rules.md's version> --geometry-default on`.
  - Then run `python eval/run_eval.py --from-saved --results <dir> --write`.
  - From the development report, record the ablation tables with coverage beside every rate (D7), the subsets (W4, W6, W8), A-neg (W9) and passability with within-one agreement (W5). The `reflection` and `splash` tags come from the manifests, marked before the run (MS6's C414).
  - From the export's printout, record the G4 drops (W3). Check C70's caps and C56's 40 px against the drops before numbering (C310, P2, P6), and record whether either cut readable references.
- [ ] **Step 5: The live default (C309).** Read the report's "outcome rule on development data". If geometry doesn't stay, set `GeometryInLevel`'s Default to `off`, and commit `chore(backend): set geometry's live default from the development ablation`.
- [ ] **Step 6: Tuning (C310).** Run `dev_eval.py sweep ...` and apply the spec's rules to its figures, or to the candidates' reports:
  - **Quality and daylight cutoffs:** the highest candidate whose within-one count equals the lowest candidate's, so no photo that read within one level is refused.
  - **T, the touch share, the IQR share and the rim score:** the best within-one agreement, with underestimation no higher than at the start values and coverage no more than 10 points below. Ties go to the stricter value: smaller T, a larger share, a smaller IQR share, a larger score.
  - **When values change:** write a new tuning version with each value's evidence (n and figures) in the change log, and update the tests that pin start values. Re-run Step 4's export and the harness on it, and commit `feat(analysis): tune the step 3 and geometry cutoffs on development data`.
- [ ] **Step 7: The Manila check (C313).** Run `dev_eval.py manila --set-a <set_a_dev>`. Record the counts, the decision, and the share of photos with no water mask for Q1 (D6). If geometry is dropped, set `GeometryInLevel`'s Default to `off` (Table 18) and commit.
- [ ] **Step 8: Set B (C314, about $0.15).**
  - Run `set_b.py segment --manifest <set_b_dev> --yes`, then `set_b.py export --manifest ... --out <data>\dev_results\<date>-set-b --rules-version <v>`, then the harness on that folder.
  - If `k_estimate` gives a value, set `rim_edge_k` in a new tuning version with its n of cars, then re-export and re-run the harness.
  - **Check 9's bounds (C305, C310; notes item E):** a rim partly hidden behind the near sidewall can fall under the 0.85 factor at steep angles, which synthetic masks can't show. From the Set B development crops, record how many fail check 9 and at what axis ratio. If real rims fail it, lower the 0.85 factor to the largest value that passes every Set B development rim, in a new tuning version with its n, then re-export.
  - Record the Set B figures from the report: each variant, by type (W2) and by angle and size (W7) (D2).
- [ ] **Step 9: The backup method (C319, D9).** If the `geometry` variant is under 70% measured or above a 3 in median error, the visible-height backup is built only if it fits before the freeze; otherwise record it. If neither holds, record that the trigger didn't fire.
- [ ] **Step 10:** If `tuning.py` or the template changed, re-run `uv run pytest -q`, `npm run deploy`, and `smoke_upload.py --geometry-photo <photo>`. Expected: `SMOKE OK`.

### Task 15: Results note and milestone close (D2 to D9; Claude)

**Files:**
- Create: `docs/research/<date>-ms3b-results.md`
- Modify: the spec's §6 table, this plan's boxes, `docs/PROGRESS.md` (the MS3 row; W2 to W9), the day's `docs/log/` note, and the design doc's decision log if anything new was decided

- [ ] **Step 1:** Write the results note, with counts and figures copied from the harness's reports and n beside each:
  - D1: the cloud photo's outcome, and the B3 replay
  - D2 and D7: Set B's figures and the ablation tables, or "waits for the harness"
  - D4: the self-check decision
  - D5: the tuning change log, or "untuned"
  - D6: C313's counts and the no-water share
  - D8: W2 to W9, each called indicative
  - D9: C319
  - the spend
  - the frozen values: the tuning version, the tire codes version, the reasoning effort and geometry's default

  It holds no photo names, paths, images, key or account ID.
- [ ] **Step 2:** Add a "Result" column to the spec's §6, with ✅ or "partly met" and the evidence line for each of D1 to D9.
- [ ] **Step 3: MS3b-Q4.** With Rene's written OK, add "Muse Spark's reasoning effort" to `eval/rules.md` §10, with a change-log row. Without it, record the default as pending in `docs/PROGRESS.md`.
- [ ] **Step 4:** Run the checks. Expected: all clean.
  - `uv run pytest -q` and `uv run ruff check .`
  - `npm run check`
  - the 12-digit grep (R15)
  - `python scripts/check_no_plan_leak.py`
  - `git diff --name-only main | xargs grep -n -i -w "safe"`: nothing about flood conditions
- [ ] **Step 5:** Run `security-review` (the dev tools build Meta clients from the key), then `superpowers:requesting-code-review` on the whole branch. Fix anything confirmed, and re-run Step 4.
- [ ] **Step 6:** Commit `docs: record MS3b results and tick its done-checks`. Then use `superpowers:finishing-a-development-branch`: merge `ms3b-geometry` into `main`, and push to the private repo (D16).
