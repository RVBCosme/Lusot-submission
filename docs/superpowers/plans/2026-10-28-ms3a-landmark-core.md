# MS3a Landmark Core Implementation Plan

> **Status (Oct 28):** reviewed by Window 3 (D20). The review settled the five spec gaps and the provisional calls as spec C72 to C81, and amended the tasks to match.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A photo uploaded from the app comes back from the cloud with a landmark-only result. That is either an MMDA level with its class, landmark and reference count, or one of the three other outcomes, kept apart: no flood seen, a refusal with its reason, or processing failed with its reason.

**Architecture:**
- **Pipeline:** pure step modules in `lusot_analysis/pipeline/` around one `run_pipeline` function. Table 8 and the level scale live in `lusot_analysis/rules.py`. SAM and Muse Spark are reached only through a client object, so tests and replays pass in fakes.
- **Lambda:** `handler.py` wraps `run_pipeline` with the claim and lease (`report_store.py`), the stop switch, the missing-photo rule and publishing.
- **Laptop:** `probes/run_pipeline.py` wraps the same function with a recording client (live mode) and a saved-outputs client (replay mode).
- **Edges:** the API and the test screen gain the result fields. The template, the image and the smoke script gain what the cloud check needs.

**Tech Stack:**
- Python 3.13 through uv: OpenCV, NumPy, boto3, and `jsonschema` (new runtime dependency); MS1's Meta client (OpenAI SDK, httpx, `meta-sam-parser`); pytest with moto 5.2.4, and ruff
- Node 22, TypeScript strict: AWS SDK v3; Vitest with `aws-sdk-client-mock`
- the app: React, Vite and Capacitor 8; Vitest with Testing Library
- AWS SAM CLI 1.170 and Docker Desktop

**Spec:** `docs/superpowers/specs/2026-10-28-ms3a-landmark-core-design.md`. It is binding, including Rene's §7 answers of Oct 28 (commit f632cde, which sets C54 by Q4). Executors read both.

**Order (D20).** The branch `ms3a-landmark-core` starts from `ms1-setup` at `461c398`.
- **Before MS1 closes:** Tasks 1, 6, 10, 11 and 12, in that order. They need nothing from MS1 Tasks 4 and 5.
- **After MS1 closes:** merge `main` and re-run every test. Then Tasks 2, 3, 4, 5, 7, 7a, 8, 9, 13, 14, 15, 16 and 17, in that order. These need MS1 Task 4 (`lusot_analysis/meta_client.py`) and Task 5: `annotate.py`, `prompts/muse_spark_photo_v1.md`, `prompts/muse_spark_photo_v1.schema.json`, `probes/run_probe.py` and the probe note.

MS1's Interfaces are used exactly as the MS1 plan states them. MS3a changes an MS1 interface only where a task says so.

## Global Constraints

- **AWS:** region `ap-southeast-1`, profile `lusot`, and every AWS CLI call passes `--no-cli-pager`. A `CreateOAuth2Token ... INVALID_REQUEST` error is transient: retry once. In Git Bash, prefix calls whose arguments start with `/` with `MSYS_NO_PATHCONV=1`.
- **Model IDs:** exactly `sam-3.1` and `muse-spark-1.3`. `muse-spark-1.3-contributor` is never used.
- **The face blur comes first (C20, C37).** Every image sent to Meta comes from `blur_for_meta` or `BlurredImage.derive`, and the client accepts only `type(img) is BlurredImage`.
- **Pay once (G2).** No Meta call happens before a successful claim. Tests prove it by counting the fake client's calls.
- **The Meta key:**
  - It is never printed, logged or written to a file: not its value, and not a prefix of it. Printing its length is fine.
  - Laptop code reads `MODEL_API_KEY`. The Lambda reads `/lusot/meta/model-api-key` from SSM.
  - A command that needs the key sets it in the same PowerShell command: `$env:MODEL_API_KEY = [Environment]::GetEnvironmentVariable('MODEL_API_KEY','User'); <command>` (F5).
- **Logs (§3.6, C62):**
  - one JSON line per report
  - never a location, image data, masks, the key, an AWS error message, or Muse Spark's `reason` text
  - AWS errors log their code and `http_status`
- **Printed output:** scripts print counts and timings only. Every printed line masks runs of 12 digits as `<account>`. Nothing prints an ARN, a queue URL or an image URI.
- **What never enters the repo:**
  - account IDs, the Meta Team ID, console links or email addresses
  - plan text: cite "plan §N" and paraphrase
  - photos other than public-domain or synthetic test fixtures. Tests make their own images. Data-set photos (STURM, Commons) and saved runs stay under `LUSOT_DATA_DIR`.
- **Sealed data:** nothing under a folder named `sealed` is opened, listed or searched. No Set A or A-neg photo is used. **Meta sees only the Commons photos C87 selects (CC BY or public domain, attribution kept beside them) and synthetic images** (Rene, 5:53 PM). STURM-FloodDepth stays offline: no new Meta call on any STURM photo.
- **Data directory:** `LUSOT_DATA_DIR`, defaulting to `C:\Systems\Lusot\lusot-data` when unset.
- **Queue and concurrency (unchanged from MS1):**
  - no reserved concurrency
  - SQS event source `MaximumConcurrency: 5`
  - visibility timeout 1,080 s, which is 6× the 180 s Lambda timeout
  - DLQ after 5 receives, with its alarm
  - S3 events on `raw/` only
- **Meta calls:**
  - The client keeps MS1's retry rule: retry only on 429, 500 and 503, 0.5 s doubling plus up to 1 s of jitter, at most 4 attempts, honouring `Retry-After`. SAM is streamed with the 504 background fallback; `strict: true`; `max_retries=0`.
  - Every call runs under the run's deadline (C84, Task 7a): a wait, poll or read that would pass it stops instead of retrying early.
  - The pipeline itself never retries a Meta call (C47, C59).
  - The Lambda never calls `count_input_tokens`.
- **Credits:** Meta credits are spent only in Task 7a's one SAM check (C85, about $0.0025) and in Task 16. It sends the photos the spec names (B1's 5 photos, positions 0 to 4 of C87's order) and runs one offline-runner live run on one of them. C71's fallback adds up to 15 more, positions 5 to 19.
- **Exact values (spec):**
  - quality: brightness under 40 → `too_dark`, sharpness under 25 → `too_blurry`, on the pre-blur upload shrunk to at most 1,600 px
  - before numbering: a wheel whose SAM box has a longer side under 40 px is dropped; at most 6 vehicles and 6 people, largest boxes first
  - the lease: 900 s (15 minutes)
  - the smoke run's bound: 120 s from upload to a final status (C68)
  - the run's deadline: the Lambda's remaining time less 30 s (C84, C88); a SAM stream read waits at most 20 s for its next event while a deadline is set; no try starts with under 5 s left, the first included (R104, R106)
  - the publish blur grows each mask's box by 25% on every side
- **Screen copy:**
  - Every screen shows exactly: `Lusot estimates depth at one spot. It is not advice to cross. Follow MMDA and local advisories.`
  - The word "safe" never appears in screen copy.
- **Toolchain:** Python `>=3.13,<3.14` through uv; Node 22; TypeScript `strict: true`. Library versions are pinned in lockfiles. Check each library's API with Context7 before calling it.
- **Commits:**
  - Conventional Commits, ending with the attribution lines Claude Code gives the session. The controller copies its own lines into each brief.
  - Write the message to a file and use `git commit -F <file>`. Never pipe it from Windows PowerShell 5.1.
  - Never `--no-verify`.
- **Builds:** a Docker build and a Gradle build never run at the same time.
- **Shells:** start each PowerShell command with the PATH refresh in `CLAUDE.md` ("Commands"). Commit from PowerShell after it, or the gitleaks hook fails closed. Run the analysis package's commands from `backend/analysis` with `uv run`. The PEP 723 scripts in `backend/scripts` run from the repo root.

## Review Focus

Most likely first. Each line names its tests.

1. **Muse Spark leaves a numbered box unanswered** (it skips a car, a wheel or a person). The box should give no reading and invent no floor (C76):
   - an unanswered vehicle is dropped with its wheels
   - an unanswered linked wheel counts as visible, so its car gets no body reading
   - an unanswered person neither counts nor blocks wading adults; only a person answered as an adult standing still blocks them

   Tests: Task 4 `test_unanswered_boxes_give_no_reading`, Task 5 `test_unanswered_wheel_blocks_the_body_reading`.
2. **A finished report gets another delivery after its lease time has passed.** This happens when the raw delete failed and SQS redelivers 18 minutes later. The redelivery should not re-claim the report or call Meta. It should only delete. Tests: Task 12 `test_finished_report_with_old_claim_is_never_reclaimed`, Task 13 `test_failed_delete_redelivered_after_lease_time_only_deletes`.
3. **SAM finds nothing at all** (a wall, a selfie or a dry lane). Muse Spark should still be asked once, with no boxes, and the gate decides. Nothing should crash on empty lists. Test: Task 8 `test_empty_scene_still_asks_muse_spark_once`.
4. **The upload link is reused while the first worker is still analysing.** The second delivery should find a live lease and pay nothing. The first worker's result stands, and no raw object is left. Test: Task 13 `test_reused_link_during_analysis_pays_once_and_leaves_no_raw`.
5. **SAM returns floodwater instances whose masks are all empty.** That should count as an empty water mask: `no_water_found` on a yes, while a clear no still gives no flood seen. Test: Task 3 `test_water_found_ignores_empty_masks`.

## Execution notes

- **Routing (D18):**
  - Opus 5.5 at max: Tasks 1 to 16 and the code-quality reviews, until Oct 29, 8:48 PM. From then on it is Opus 5.5 at `xhigh` (D18, amended by Rene), never `max`.
  - Sonnet 5.5 at xhigh: the spec-compliance reviews
  - Claude itself: Task 17, and the key step in Task 16 (Step 5)
- **Branch:** `ms3a-landmark-core`, from `ms1-setup` at `461c398`, with `main` merged in once MS1 closes (D20; see "Order" above). Tasks run one at a time (R1). Only Tasks 3 and 14 touch `pyproject.toml`, `uv.lock` or `requirements.lock.txt`.
- **MS1 interfaces this plan uses** (names as the MS1 plan gives them):
  - `face_blur`: `BlurredImage` (`jpeg`, `width`, `height`, `faces`, `blur_version`, `.bgr()`, `.derive(bgr, base)`), `blur_for_meta(data, *, max_side=1600)`, `decode_image`, `blur_faces(bgr, faces, *, margin=0.25)`, `FaceBox(x, y, w, h, score)`, `UndecodableImage`, `FACE_BLUR_VERSION`
  - `meta_client`: `SAM_PHRASES`, `SAM_MODEL`, `SPARK_MODEL`, `MissingApiKey`, `MetaApiError` (`.status`), `SamInstance(id, box, mask, score)`, `SamResult(phrase, instances, elapsed_s, raw)`, `SparkResult(data, input_tokens, output_tokens, elapsed_s, raw)`, `MetaClient(api_key=None, ...)` with `.segment(image, phrase)` and `.judge(image, *, prompt, schema, schema_name)`
  - `annotate`: `NumberedBox(id, kind, box)`, `number_boxes(sam)`, `draw_numbered_boxes(img, boxes)`, `check_ids(answer, boxes)`
  - the answer's fields (plan Table 5, schema v1):
    - top level: `photo_usable`, `standing_water`, `reason`
    - `vehicles[]`: `id`, `type`, `moving`, `wake_visible`, `body_waterline`
    - `wheels[]`: `id`, `waterline`
    - `people[]`: `id`, `adult`, `standing_still`, `waterline`
- **Commands** run from `backend/analysis` unless a step says otherwise.

---

### Task 1: Rules module and shared pipeline types

**Files:**
- Create: `backend/analysis/src/lusot_analysis/rules.py`, `backend/analysis/src/lusot_analysis/pipeline/__init__.py` (a docstring only; Task 8 fills it), `backend/analysis/src/lusot_analysis/pipeline/types.py`
- Test: `backend/analysis/tests/test_rules.py`, `backend/analysis/tests/test_pipeline_types.py`

**Interfaces:**
- Produces, in `lusot_analysis.rules` (`eval/rules.md` §1 and §6, spec §3.3):
  - `LEVELS: tuple[str, ...] = ("below_gutter", "gutter", "half_knee", "half_tire", "knee", "tire", "waist", "chest", "above_chest")`
  - `PASSABILITY: Mapping[str, str]`: `PATV` for the first three levels, `NPLV` for `half_tire` and `knee`, `NPATV` for `tire` and every deeper level (`eval/rules.md` §1)
  - `level_index(level: str) -> int`, which raises `ValueError` for an unknown level
  - `@dataclass(frozen=True) class Reading: level: str; floor: bool`
  - `WHEEL_ROWS`, `PEOPLE_ROWS`, `BODY_ROWS: Mapping[str, Reading | None]`, holding the spec's three tables. `not_visible` maps to `None`. The body table maps `mid_door` and `window` to `Reading("tire", True)`, and every other value to `None`.
  - `BODY_AT_OR_BELOW_SILL = frozenset({"below_bumper", "bumper", "door_sill"})` (C53's drop)
  - `HIDDEN_WHEEL = frozenset({"wheel_covered", "not_visible"})` (C53)
  - `READING_TYPES = frozenset({"sedan_hatch", "suv_mpv"})` (C45)
  - `ABOVE_LOWEST_MARK: Mapping[str, frozenset[str]]` (C52), with keys:
    - `"wheel"`: every wheel waterline above `tire_only`, except `not_visible`
    - `"person"`: everything above `ankle`, except `not_visible`
    - `"body"`: `bumper`, `door_sill`, `mid_door`, `window`
  - `disagree(readings: Iterable[Reading]) -> bool` (C54 as set by Rene's Q4): let D be the deepest level, with a floor counted at its own level. It returns True when any **exact** reading sits more than one level below D. A floor is never too shallow.
- Produces, in `lusot_analysis.pipeline.types`:
  - `REFUSED_REASONS = ("too_dark", "too_blurry", "photo_unusable", "water_unsure", "no_water_found", "no_usable_reference", "references_disagree")`
  - `FAILED_REASONS = ("model_calls_paused", "photo_missing", "bad_file", "model_error", "pipeline_error")`
  - `@dataclass(frozen=True) class Outcome`:
    - fields: `status: Literal["done", "refused", "failed"]`, `reason: str | None = None`, `no_flood_seen: bool = False`, `level: str | None = None`, `landmark: str | None = None`, `passability: str | None = None`, `level_is_floor: bool = False`, `basis: Mapping[str, int] | None = None`
    - builders: `Outcome.refused(reason)`, `Outcome.failed(reason)`, `Outcome.no_flood()`, `Outcome.level_result(level, landmark, level_is_floor, basis)`. The last takes `passability` from `rules.PASSABILITY`; that lookup is step 7 (map).
    - `__post_init__` raises `ValueError` on any other shape (C42, C50):
      - a reason from the wrong list, a `refused` or `failed` outcome without a reason, or `done` with a reason
      - `done` with neither a level nor `no_flood_seen`, or with both
      - an unknown level
      - a level result without `landmark` or `basis`, or whose `passability` isn't `PASSABILITY[level]`
      - a no-flood result carrying `landmark`, `passability`, `basis` or `level_is_floor`
      - `basis` keys other than exactly `vehicles` and `people`, or counts summing to 0
      - result fields on `refused` or `failed`
    - `.item_fields() -> dict[str, object]`: the report item's attributes (§3.5):
      - `{"status", "refusalReason"}` when refused or failed
      - `{"status": "done", "noFloodSeen": True}` for no flood seen
      - for a level: `{"status": "done", "noFloodSeen": False, "level", "landmark", "passability", "levelIsFloor", "basis": {"vehicles", "people"}}`
    - `.log_name: str`: `"done/level"`, `"done/no_flood_seen"`, `"refused/<reason>"` or `"failed/<reason>"`
  - `@dataclass(frozen=True) class Reference: kind: Literal["wheel", "body", "person"]; box_id: int; landmark: str; reading: Reading`. For a body reading, `box_id` is the vehicle's id. For a wheel, it is the wheel's id.
  - `class ModelClient(Protocol)` with `segment(image: BlurredImage, phrase: str) -> SamResult` and `judge(image: BlurredImage, *, prompt: str, schema: dict, schema_name: str) -> SparkResult`
    - **Before MS1 closes (R80):** `meta_client` isn't on the branch yet. The module starts with `from __future__ import annotations` and imports `SamResult`, `SparkResult` and `BlurredImage` only under `if TYPE_CHECKING:`. The import stays that way after the merge, so loading the rules never loads the OpenAI SDK.
  - `class ModelAnswerError(Exception)`: Muse Spark's answer isn't valid JSON or fails the schema (C47)
  - `class ModelKeyRejected(Exception)`: Meta answered 401, 402 or 403, so the key or the account was rejected (C73). It holds `status: int`. Task 8 raises it, and Tasks 9 and 13 handle it.

The rule tables use the value names in spec §3.3. Task 3's `test_rules_cover_every_schema_enum` checks them against MS1's schema after the merge.

- [x] **Step 1: Write the failing tests.** Every expected value is the spec's. Evidence: tests/test_rules.py (15) and tests/test_pipeline_types.py (39) written first, 54 in all (Task 1's report); commit 222ae4e.
  - `test_levels_are_the_nine_in_order`: `LEVELS` equals the tuple above; `level_index("gutter") == 1`; `level_index("knee") == 4`; `level_index("deep")` raises `ValueError`.
  - `test_passability_for_every_level`: equality with the 9-entry mapping.
  - `test_wheel_rows_match_table_8`: equality with:
    - `tire_only` → `Reading("below_gutter", False)`
    - `rim_quarter` → `half_knee`, `hub` → `half_tire`, `rim_three_quarters` → `knee`, `rim_top` → `tire`, all exact
    - `wheel_covered` → `Reading("tire", True)`
    - `not_visible` → `None`
  - `test_people_rows_match_table_8`: `ankle` → `below_gutter`, `mid_shin` → `half_knee`, `knee` → `knee`, `mid_thigh` → `tire`, `waist` → `waist`, `chest` → `chest`, `above_chest` → `above_chest`, all exact; `not_visible` → `None`.
  - `test_body_rows_and_sets`: the body table as above; `BODY_AT_OR_BELOW_SILL`, `HIDDEN_WHEEL`, `READING_TYPES` and the three `ABOVE_LOWEST_MARK` sets equal the values above.
  - `test_disagree_follows_c54`, parametrized. `R` is `Reading`, `True` marks a floor:
    - `[R(tire, True), R(chest, False)]` → False
    - `[R(tire, True), R(half_tire, False)]` → True
    - `[R(tire, True), R(knee, False)]` → False
    - `[R(knee, False), R(chest, False)]` → True
    - `[R(below_gutter, False), R(half_knee, False)]` → True (the gutter gap, Rene Q2)
    - `[R(knee, False), R(tire, False)]` → False
    - `[R(tire, True), R(above_chest, False)]` → False
    - `[R(waist, False)]` → False
    - `[]` → False
  - `test_outcome_item_fields`: the exact dicts for a knee level result (`basis` 1 and 1), for no flood seen, for `refused/too_dark` and for `failed/model_error`.
  - `test_outcome_rejects_bad_shapes`, parametrized over each `__post_init__` case above. Each raises `ValueError`.
  - `test_every_reason_has_a_log_name`: `Outcome.refused(r).log_name == f"refused/{r}"` for every refused reason, the same for failed, and the two `done` names.
  - `test_pipeline_not_built_is_not_a_new_reason`: `"pipeline_not_built" not in FAILED_REASONS`. MS1's reason stays readable only on old reports.
  - `test_types_import_the_meta_client_only_for_type_checking` (R80): an `ast` walk of `pipeline/types.py` finds every import of `lusot_analysis.meta_client` and `lusot_analysis.face_blur` inside an `if TYPE_CHECKING:` block, and none outside one. It reads the file, so it holds after Task 8 fills `pipeline/__init__.py`.
  - `test_rules_load_without_the_meta_client` (R80): in a fresh interpreter, `import lusot_analysis.rules, sys; print("lusot_analysis.meta_client" in sys.modules, "openai" in sys.modules)` prints `False False`.
  - `test_key_rejected_keeps_its_status`: `ModelKeyRejected(401).status == 401`.
- [x] **Step 2:** Run `uv run pytest -q tests/test_rules.py tests/test_pipeline_types.py`. Expected: FAIL (modules missing). Evidence: `uv run pytest -q tests/test_rules.py tests/test_pipeline_types.py` → RED: ModuleNotFoundError for lusot_analysis.rules and lusot_analysis.pipeline, 2 collection errors, exit 2 (Task 1's report).
- [x] **Step 3:** Implement the two modules with the names and values above. The tables are plain dict literals, so a reviewer can check them against spec §3.3 line by line. Evidence: rules.py, pipeline/__init__.py and pipeline/types.py as specified; same command → 54 passed; 6 hand-made mutants each killed (Task 1's report).
- [x] **Step 4:** Run `uv run pytest -q`, then `uv run ruff check .`. Expected: all PASS; ruff clean. Evidence: `uv run pytest -q` → 90 passed (36 before); `uv run ruff check .` → All checks passed (Task 1's report).
- [x] **Step 5:** Commit `feat(analysis): add the level scale, Table 8 rows and the outcome type`. Evidence: commit 222ae4e (11:37 AM); review clean, 0 Critical/Important (SDD ledger).

### Task 2: Segment step and the boxes before numbering

**Files:**
- Create: `backend/analysis/src/lusot_analysis/pipeline/segment.py`, `backend/analysis/src/lusot_analysis/pipeline/references.py`
- Modify: `backend/analysis/tests/fakes.py` (shared test builders; not collected by pytest). Task 12 created it before MS1 closed, holding `create_reports_table`; this task adds the builders below.
- Test: `backend/analysis/tests/test_segment.py`, `backend/analysis/tests/test_prepare_boxes.py`

**Interfaces:**
- Consumes: `SamInstance`, `SamResult`, `MetaApiError`, `SAM_PHRASES` (MS1 Task 4); `BlurredImage`; `ModelClient` (Task 1)
- Produces, in `lusot_analysis.pipeline.segment` (step 2):
  - `box_xyxy(inst: SamInstance) -> tuple[float, float, float, float]` returns `(x0, y0, x1, y1)` in pixels of the image sent to SAM. It is the only place that reads `SamInstance.box`.
  - `segment_all(client: ModelClient, image: BlurredImage, phrases: Sequence[str]) -> dict[str, SamResult]`: one thread per phrase (`ThreadPoolExecutor(max_workers=len(phrases))`), keyed by phrase. A `MetaApiError` from any phrase propagates.
  - `link_wheels(vehicles: Sequence[SamInstance], wheels: Sequence[SamInstance]) -> list[int | None]` (C55): for each wheel, the index of the one vehicle whose box holds the wheel box's centre, with edges included. It is `None` when no vehicle holds the centre, or more than one does.
- Produces, in `lusot_analysis.pipeline.references` (step 4.1; C56, C69, C70):
  - `MIN_WHEEL_SIDE_PX = 40`, `MAX_VEHICLES = 6`, `MAX_PEOPLE = 6`
  - `@dataclass(frozen=True) class Prepared`:
    - `sam: dict[str, SamResult]`: `vehicle`, `wheel` and `person` cut to the kept instances, in SAM order; other phrases unchanged
    - `wheel_vehicle: tuple[int, ...]`: for each kept wheel, its vehicle's position among the kept vehicles
    - `small_wheel_vehicles: frozenset[int]`: positions of kept vehicles that had a linked wheel cut by the 40 px rule
    - `drops: Counter[str]`
  - `prepare_boxes(sam: Mapping[str, SamResult]) -> Prepared`. A phrase missing from `sam` counts as no instances. The order is fixed, because it decides each drop's cause:
    1. Link every SAM wheel against every SAM vehicle. An unlinked wheel is dropped as `wheel_unlinked`.
    2. A linked wheel whose box's longer side is under 40 px is dropped as `wheel_small`, and its vehicle is marked.
    3. Keep the 6 vehicles with the largest box areas; on equal areas, the earlier in SAM order. Cut vehicles are dropped as `vehicle_cap`, and their wheels as `wheel_cap`.
    4. Keep the 6 largest people the same way. The rest are dropped as `person_cap`.
- Produces, in `tests/fakes.py`:
  - `SIZE = (640, 480)` (width, height)
  - `noise_jpeg(width=640, height=480, seed=0) -> bytes`
  - `flat_jpeg(value: int, width=640, height=480) -> bytes`
  - `instance(i: int, xyxy: tuple[float, float, float, float], *, size=SIZE, mask_xyxy=None, score=0.9) -> SamInstance`: stores the box in the client's convention (the inverse of `box_xyxy`). The bool mask fills `mask_xyxy`, which defaults to the box.
  - `sam_results(boxes: Mapping[str, Sequence[tuple]], *, size=SIZE) -> dict[str, SamResult]`: every one of the 7 phrases, empty unless listed
  - `meta_error(status: int) -> MetaApiError`, built the way `tests/test_meta_client.py` builds one
  - `class FakeClient(sam: Mapping[str, SamResult], answer: dict | Exception | None = None, *, on_segment=None, on_judge=None)`:
    - `.segment()` and `.judge()` record `(method, phrase or schema_name, type(image))` in `.calls`, behind a lock
    - each runs its hook first, if set, as `on_segment(phrase)` or `on_judge()`
    - `.judge()` returns `SparkResult(data=answer, input_tokens=1000, output_tokens=200, elapsed_s=1.5, raw=json.dumps(answer))`, or raises `answer` when it is an exception
    - `.count_input_tokens()` raises `AssertionError`

- [x] **Step 1:** MS1's Interfaces give `SamInstance.box` as four floats without naming their order. Read `meta_client.py` and `tests/test_meta_client.py`, and write what you find into `test_box_xyxy_reads_the_client_convention`: one instance and its expected `(x0, y0, x1, y1)`. Evidence: test_box_xyxy_reads_the_client_convention pins SAM's record x1=211;y1=228;x2=270;y2=254 as the half-open (211.0, 228.0, 271.0, 255.0), read from meta_client.py:98-100 and test_meta_client.py::test_segment_box_is_half_open_in_sent_pixels (Task 2's report); commit 00a63e9.
- [x] **Step 2: Write the failing tests:** Evidence: 24 new tests in tests/test_segment.py (13) and tests/test_prepare_boxes.py (11), with the builders in tests/fakes.py (Task 2's report); commit 00a63e9.
  - `test_segment_all_runs_every_phrase_at_once`: a `FakeClient` whose segment hook waits on a `threading.Barrier(7, timeout=5)`. All 7 calls must be in flight together. The result is keyed by all 7 phrases, and every call saw a `BlurredImage`.
  - `test_segment_all_propagates_a_meta_error`: one phrase raises `meta_error(503)`, so `segment_all` raises `MetaApiError`.
  - `test_link_wheels_by_centre`: vehicle A `(0, 0, 200, 100)`, B `(150, 0, 400, 100)`, C `(0, 200, 100, 300)`. Wheel centres and their links:
    - `(50, 50)` → A
    - `(300, 50)` → B
    - `(175, 50)` → None (inside both A and B)
    - `(500, 50)` → None (inside neither)
    - `(100, 250)` → C (on C's edge, which counts)
  - `test_small_and_unlinked_wheels_are_dropped_before_numbering`:
    - longer sides of 39.9 px → `wheel_small`; 40.0 → kept
    - a 45 × 20 box is kept: the longer side counts, not the height (C56)
    - an unlinked wheel → `wheel_unlinked`
    - a 10 × 10 person box is kept: people get no size floor (spec §3.3)
    - `drops` equals the exact `Counter`
  - `test_small_linked_wheel_marks_its_vehicle` (C69): vehicle 0 with one small and one large wheel. `small_wheel_vehicles == {0}`, and the large wheel is kept.
  - `test_caps_keep_the_six_largest` (C70):
    - 8 vehicles with areas 1 to 8, plus a wheel inside the smallest: the 6 largest are kept in SAM order; `vehicle_cap` 2, `wheel_cap` 1
    - 7 people: `person_cap` 1, the smallest cut
  - `test_cap_ties_keep_sam_order`: 7 vehicles of equal area. The first 6 in SAM order are kept.
  - `test_kept_wheels_point_at_their_kept_vehicle`: after a cut shifts the positions, `wheel_vehicle` still names each wheel's own vehicle.
  - `test_a_crowded_street_stays_within_the_caps`: 40 vehicles, 60 wheels and 30 people. At most 6 vehicles and 6 people are kept, and every cut is in `drops`.
  - `test_other_phrases_pass_through`: `floodwater`, `wheel rim`, `face` and `license plate` are the same objects.
- [x] **Step 3:** Run `uv run pytest -q tests/test_segment.py tests/test_prepare_boxes.py`. Expected: FAIL. Evidence: `uv run pytest -q tests/test_segment.py tests/test_prepare_boxes.py` → RED 1: ImportError (cannot import name 'around' from 'fakes'), then RED 2: ModuleNotFoundError for pipeline.segment and pipeline.references; 2 collection errors, exit 2 (Task 2's report).
- [x] **Step 4:** Implement `segment.py`, `prepare_boxes` and `fakes.py` as specified. Evidence: segment.py, references.py (prepare_boxes) and fakes.py implemented; same command → 24 passed; 28 of 28 mutants killed (Task 2's report).
- [x] **Step 5:** Run `uv run pytest -q`, then `uv run ruff check .`. Expected: PASS; clean. Evidence: `uv run pytest -q` → 228 passed (204 before); `uv run ruff check .` → All checks passed (Task 2's report).
- [x] **Step 6:** Commit `feat(analysis): add the SAM step and the box rules before numbering`. Evidence: commit 00a63e9 (3:24 PM); review clean, 0 Critical/Important (SDD ledger).

### Task 3: Muse Spark's answer: schema, ids and the gate

**Files:**
- Create: `backend/analysis/src/lusot_analysis/prompts.py`
- Modify:
  - `backend/analysis/src/lusot_analysis/annotate.py` (add `check_ids_per_item`)
  - `backend/analysis/src/lusot_analysis/pipeline/references.py` (add `validate_answer`, `Layout`, `layout`, `water_found`, `gate`)
  - `backend/analysis/pyproject.toml`, `backend/analysis/uv.lock` (`jsonschema` becomes a runtime dependency)
  - `backend/analysis/tests/fakes.py` (answer builders)
- Test: `backend/analysis/tests/test_prompts.py`, `backend/analysis/tests/test_annotate.py`, `backend/analysis/tests/test_gate.py`

**Interfaces:**
- Consumes: `NumberedBox`, `number_boxes`, `check_ids` (MS1 Task 5); `Prepared` (Task 2); `rules`, `Outcome`, `ModelAnswerError` (Task 1)
- Produces, in `lusot_analysis.prompts` (§3.6):
  - `PROMPT_VERSION: str`, the version the MS1 probe note settles (P1): `"muse_spark_photo_v1"`, unless the note names a v2
  - `@dataclass(frozen=True) class PromptSpec: version: str; text: str; schema: dict; schema_name: str`, where `schema_name` is `version`
  - `load_prompt(prompts_dir: Path, version: str = PROMPT_VERSION) -> PromptSpec` reads `<version>.md` and `<version>.schema.json` from the directory it is given. It checks the schema with the validator class its `$schema` names (`jsonschema.validators.validator_for`, defaulting to Draft 2020-12). It never builds a path from `__file__`, because the image's layout differs from the repo's.
- Produces, in `lusot_analysis.annotate`:
  - `check_ids_per_item(answer: dict, boxes: Sequence[NumberedBox]) -> tuple[dict, Counter[str]]` (C47) returns a copy of the answer without the bad entries, plus drop counts. An entry counts under the first cause that applies, in this order:
    1. `unknown_id`: its id isn't among the boxes
    2. `duplicate_id`: a known id appears in more than one entry anywhere across `vehicles`, `wheels` and `people`, so every such entry goes
    3. `wrong_list`: the box's kind doesn't match the list

    Other keys are copied unchanged. `check_ids` stays as it is, because the probe uses it.
- Produces, in `lusot_analysis.pipeline.references`:
  - `validate_answer(data: object, schema: dict) -> None` raises `ModelAnswerError` unless `data` is a dict that passes the schema, using the same validator class as `load_prompt`
  - `@dataclass(frozen=True) class Layout: boxes: tuple[NumberedBox, ...]; wheel_vehicle: Mapping[int, int]; small_wheel_vehicles: frozenset[int]`, using numbered ids, not positions
  - `layout(prepared: Prepared, boxes: Sequence[NumberedBox]) -> Layout`: the k-th `vehicle` box is the k-th kept vehicle, and likewise for wheels and people
  - `water_found(result: SamResult) -> bool`: True when any instance's mask has a pixel
  - `gate(answer: dict, *, has_water: bool) -> Outcome | None` (C51, C52, spec §3.2 step 4.5), in this order:
    1. `photo_usable = no` → `refused/photo_unusable`
    2. `standing_water = unsure` → `refused/water_unsure`
    3. `standing_water = no` → `Outcome.no_flood()` when no answered item's value is in `ABOVE_LOWEST_MARK` (wheel waterline, person waterline, vehicle `body_waterline`), and `refused/water_unsure` otherwise
    4. `standing_water = yes` without water → `refused/no_water_found` (Rene Q1)
    5. otherwise `None`, and the pipeline goes on
- Produces, in `tests/fakes.py`:
  - `vehicle(id, type="sedan_hatch", moving="no", body="not_visible", wake=False) -> dict`
  - `wheel(id, waterline) -> dict`
  - `person(id, waterline, adult="yes", standing_still="yes") -> dict`
  - `answer(*, photo_usable="yes", standing_water="yes", vehicles=(), wheels=(), people=(), reason="REASON-MARKER-31") -> dict`
  - `REPO_PROMPTS = Path(__file__).parents[1] / "prompts"`

- [x] **Step 1:** Make `jsonschema` a runtime dependency in `[project] dependencies`. Evidence: jsonschema was already a runtime dependency from MS1 (pyproject.toml `jsonschema>=4.26.0`, locked in uv.lock and requirements.lock.txt), so no `uv add` ran and pyproject.toml and uv.lock are untouched; `uv run python -c "import jsonschema"` → exit 0, version 4.26.0 (Task 3's report).
  - If MS1 Task 5 already did, record that and go on.
  - If it sits in a dependency group, remove it there first (`uv remove --group <group> jsonschema`), so it is listed once.
  - Then run `uv add jsonschema`.

  Expected: `uv.lock` updated, and `uv run python -c "import jsonschema"` exits 0.
- [x] **Step 2: Write the failing tests:** Evidence: 40 new tests in tests/test_prompts.py (15), tests/test_annotate.py (+7) and tests/test_gate.py (18), with the builders in tests/fakes.py (Task 3's report); commit 339cfc7.
  - `test_load_prompt_reads_the_versioned_files`: `load_prompt(REPO_PROMPTS)` has `version == PROMPT_VERSION == schema_name`, non-empty text, and `schema["additionalProperties"] is False`.
  - `test_missing_prompt_raises`: `load_prompt(tmp_path)` raises `FileNotFoundError`.
  - `test_prompts_module_never_walks_up_from_its_file`: `"__file__" not in inspect.getsource(prompts)`.
  - `test_jsonschema_is_a_runtime_dependency`: `pyproject.toml`'s `project.dependencies` has a `jsonschema` entry.
  - `test_rules_cover_every_schema_enum`: the schema's enums for wheel and person `waterline` and vehicle `body_waterline` equal the keys of `WHEEL_ROWS`, `PEOPLE_ROWS` and `BODY_ROWS`. `READING_TYPES` sits inside the vehicle `type` enum.
  - `test_answer_builder_matches_the_schema`: `validate_answer(answer(vehicles=[vehicle(1)], wheels=[wheel(2, "hub")], people=[person(3, "knee")]), schema)` passes. The builders therefore use the schema's real field names and nesting.
  - `test_validate_answer_rejects_bad_answers`: each of these raises `ModelAnswerError`:
    - a string instead of a dict
    - an extra top-level key
    - `"id": "2"` instead of `2`
    - a waterline outside its enum
  - `test_number_boxes_keeps_input_order`: 2 vehicles, 2 wheels and 1 person come back in input order with ids 1 to 5. If this fails, change `number_boxes` so each kind keeps its input order. That is an MS1 interface change; record it in the task report.
  - `test_per_item_check_drops_only_bad_items`, on boxes vehicle 1, wheels 2 and 3, person 4:
    - an unknown id 99 → `unknown_id` 1, and wheel 2 stays
    - wheel id 3 under `vehicles` → `wrong_list` 1
    - wheel 2 answered twice → both dropped, `duplicate_id` 2
    - id 3 under both `wheels` and `people` → both dropped, `duplicate_id` 2
    - id 99 twice → `unknown_id` 2
    - a clean answer comes back equal, with an empty `Counter`
    - the input dict is never changed
  - `test_layout_maps_positions_to_ids`: 2 kept vehicles, 3 wheels with `wheel_vehicle (1, 0, 1)`, 1 person, and `small_wheel_vehicles {1}`. After `number_boxes`: `wheel_vehicle == {3: 2, 4: 1, 5: 2}` and `small_wheel_vehicles == {2}`.
  - `test_gate_order`, parametrized with exact outcomes:
    - usable no + water yes → `photo_unusable`
    - usable no + water no → `photo_unusable`
    - water unsure → `water_unsure`
    - water no with only lowest marks or `not_visible` (wheel `tire_only`, person `ankle`, body `below_bumper`) → no flood seen
    - water no plus a wheel at `rim_quarter` → `water_unsure`
    - water no plus a wheel at `wheel_covered` → `water_unsure`
    - water no plus a person at `mid_shin` → `water_unsure`
    - water no plus a body at `bumper` → `water_unsure`
    - water no, everything `not_visible`, `has_water=True` → no flood seen (the mask doesn't override a clear no, C51)
    - water yes, `has_water=False` → `no_water_found`
    - water yes, `has_water=True` → `None`
  - `test_contradiction_counts_every_answered_item` (C52): water no, plus a moving `bus_truck` whose body is at `window` → `water_unsure`.
  - Review Focus 5, `test_water_found_ignores_empty_masks`:
    - two instances whose masks are all False → False
    - one instance with one True pixel → True
    - no instances → False
- [x] **Step 3:** Run `uv run pytest -q tests/test_prompts.py tests/test_annotate.py tests/test_gate.py`. Expected: FAIL. Evidence: `uv run pytest -q tests/test_prompts.py tests/test_annotate.py tests/test_gate.py` → RED 1: ImportError for REPO_PROMPTS and answer from fakes, then RED 2: prompts, check_ids_per_item and Layout missing; 3 collection errors, exit 2 (Task 3's report).
- [x] **Step 4:** Implement `prompts.py`, `check_ids_per_item`, `validate_answer`, `Layout`, `layout`, `water_found`, `gate` and the builders. Evidence: prompts.py, check_ids_per_item, validate_answer, Layout, layout, water_found, gate and the builders implemented; same command → 47 passed; 34 of 34 mutants killed (Task 3's report).
- [x] **Step 5:** Run `uv run pytest -q`, then `uv run ruff check .`. Expected: PASS; clean. Evidence: `uv run pytest -q` → 268 passed (228 before); `uv run ruff check .` → All checks passed (Task 3's report).
- [x] **Step 6:** Commit `feat(analysis): add the answer schema check, per-item ids and the gate`. Evidence: commit 339cfc7 (3:55 PM); review clean, 0 Critical/Important (SDD ledger).

### Task 4: Answer drops for vehicles, wheels and people

**Files:**
- Modify: `backend/analysis/src/lusot_analysis/pipeline/references.py` (add the `Kept` types and `apply_drops`)
- Test: `backend/analysis/tests/test_apply_drops.py`

**Interfaces:**
- Consumes: `Layout` (Task 3); `rules.READING_TYPES`, `rules.HIDDEN_WHEEL`; the answer builders
- Produces:
  - `@dataclass(frozen=True) class KeptVehicle: id: int; body_waterline: str; wheels: tuple[tuple[int, str], ...]; wheels_hidden: bool`. `wheels` holds `(wheel id, waterline)` for each answered wheel linked to the vehicle, in id order.
  - `@dataclass(frozen=True) class KeptPerson: id: int; waterline: str`
  - `@dataclass(frozen=True) class Kept: vehicles: tuple[KeptVehicle, ...]; people: tuple[KeptPerson, ...]`, each in id order
  - `apply_drops(answer: dict, layout: Layout) -> tuple[Kept, Counter[str]]` (spec §3.3 drops, step 4.6). It takes the answer after `check_ids_per_item`.
    - **Vehicles**, each numbered vehicle in id order:
      - no entry → `vehicle_unanswered`
      - `moving` is `yes` or `unsure` → `vehicle_moving` (W1)
      - a type outside `READING_TYPES` → `vehicle_type` (C45)
      - each numbered wheel of a dropped vehicle → `wheel_vehicle_dropped`
    - **Wheels:** a numbered wheel of a kept vehicle with no entry → `wheel_unanswered`.
    - **`wheels_hidden`** (C53, C69) is true when both hold:
      - the vehicle isn't in `small_wheel_vehicles`
      - every numbered wheel linked to it has an entry whose waterline is in `HIDDEN_WHEEL`. This holds trivially when none is linked. An unanswered wheel makes it false.
    - **People** (C57, C76; Rene Q3):
      - no entry → `person_unanswered`
      - `adult` is `no` or `unsure` → `person_not_adult`
      - an adult whose `standing_still` is `no` or `unsure` is wading. If any person answered `adult = yes` has `standing_still = yes`, whatever its waterline, every wading adult → `person_wading`. Otherwise wading adults are kept. An unanswered person, or one answered `adult: unsure`, never blocks (C76).
    - `wake_visible` is read and changes nothing (C63).

- [x] **Step 1: Write the failing tests:** Evidence: tests/test_apply_drops.py, 26 cases covering the brief's 10 tests plus extras (Task 4's report); commit c0a50d8.
  - `test_moving_vehicles_are_dropped_with_their_wheels`: `moving` `yes` and `unsure` each → `vehicle_moving`. Their wheels are counted as `wheel_vehicle_dropped`.
  - `test_only_sedans_and_suvs_are_read`: parametrized over `pickup`, `van`, `jeepney`, `tricycle`, `motorcycle`, `bus_truck`, `unknown` → `vehicle_type`. `sedan_hatch` and `suv_mpv` are kept.
  - `test_children_and_unsure_adults_are_dropped`: `adult` `no` and `unsure` → `person_not_adult`.
  - `test_wading_adults_yield_to_a_standing_adult`: one standing adult, and wading adults with `standing_still` `no` and `unsure` → only the standing adult is kept; `person_wading` 2.
  - `test_a_hidden_standing_adult_still_blocks_wading` (Rene Q3): a standing adult at `not_visible`, plus a wading adult at `waist` → the wading adult is dropped; the kept person is the `not_visible` one.
  - `test_wading_adults_count_when_nobody_stands`: two wading adults → both kept.
  - `test_a_standing_child_does_not_block_wading_adults`, parametrized over `adult` `no` and `unsure` (C76): that person, standing, plus a wading adult → the adult is kept and the other person dropped.
  - `test_wheels_hidden`, parametrized:
    - `wheel_covered` plus `not_visible` → True
    - one wheel at `rim_top` → False
    - no linked wheel → True
    - a vehicle in `small_wheel_vehicles` whose answered wheels are all `not_visible` → False (C69)
  - `test_wake_visible_changes_nothing` (C63): the same answer with `wake_visible` True and False gives equal results.
  - Review Focus 1, `test_unanswered_boxes_give_no_reading`:
    - vehicle 1 has no entry, and its wheel 3 → `vehicle_unanswered` 1 and `wheel_vehicle_dropped` 1
    - kept vehicle 2: wheel 4 unanswered, wheel 5 `not_visible` → `KeptVehicle(2, "not_visible", ((5, "not_visible"),), wheels_hidden=False)` and `wheel_unanswered` 1
    - person 6 has no entry → `person_unanswered` 1, and it doesn't block wading adult 7, who is kept (C76)
- [x] **Step 2:** Run `uv run pytest -q tests/test_apply_drops.py`. Expected: FAIL. Evidence: `uv run pytest -q tests/test_apply_drops.py` → RED: ImportError (cannot import name 'Kept'), 1 error, exit 2 (Task 4's report).
- [x] **Step 3:** Implement the types and `apply_drops`. Evidence: Kept, KeptVehicle, KeptPerson and apply_drops added to pipeline/references.py; same command → 26 passed; 31 of 31 mutants killed (Task 4's report).
- [x] **Step 4:** Run `uv run pytest -q`, then `uv run ruff check .`. Expected: PASS; clean. Evidence: `uv run pytest -q` → 294 passed (268 before); `uv run ruff check .` → All checks passed (Task 4's report).
- [x] **Step 5:** Commit `feat(analysis): add the answer drops for vehicles, wheels and people`. Evidence: commit c0a50d8 (4:20 PM); review clean, 0 Critical/Important (SDD ledger).

### Task 5: Landmark readings (step 5)

**Files:**
- Create: `backend/analysis/src/lusot_analysis/pipeline/measure.py`
- Test: `backend/analysis/tests/test_measure.py`

**Interfaces:**
- Consumes: `Kept` (Task 4); the `rules` tables, `BODY_AT_OR_BELOW_SILL` and `disagree` (Task 1); `Reference`
- Produces: `measure(kept: Kept) -> tuple[list[Reference], Counter[str]]`. It returns one reference per kept vehicle with a reading, then one per kept adult with a reading, each in id order.
  - **Each vehicle, in this order:**
    1. a wheel at `wheel_covered` and a body in `BODY_AT_OR_BELOW_SILL` → drop as `vehicle_body_below_covered_wheel` (C53)
    2. the readings of its wheels (`WHEEL_ROWS`, skipping `None`). If `disagree` is true → drop as `vehicle_wheels_disagree`. That is C43, which uses C54's test: an exact wheel more than one level below the vehicle's deepest wheel.
    3. the candidates: each wheel reading as `Reference("wheel", wheel id, waterline, reading)`. When `wheels_hidden` holds and `BODY_ROWS[body]` isn't `None`, also `Reference("body", vehicle id, body, reading)`.
    4. no candidate → `vehicle_no_reading`. Otherwise the deepest candidate speaks for the vehicle. Ties use C54's order: a floor first, then a wheel before the body, then the lowest box id.
    5. a vehicle dropped in item 1 or 2 also counts each of its wheels as `wheel_vehicle_dropped`. A `vehicle_no_reading` doesn't, because its wheels gave nothing to drop.
  - **Each person:** `PEOPLE_ROWS[waterline]` gives `Reference("person", id, waterline, reading)`, or `person_no_reading`.

- [x] **Step 1: Write the failing tests:** Evidence: tests/test_measure.py, 39 cases in 10 functions (the brief's 9 tests plus additions); the R82 refactor (47fc5bb) and the R96 case (d259d21) came first (Task 5's report).
  - `test_each_wheel_row_reads_through`, parametrized over the 6 marks: a sedan with one wheel gives `Reference("wheel", 2, mark, WHEEL_ROWS[mark])`. A lone `not_visible` wheel with body `not_visible` → `vehicle_no_reading`.
  - `test_deepest_wheel_speaks` (C43): `hub` plus `rim_three_quarters` → `knee`, landmark `rim_three_quarters`.
  - `test_wheels_too_far_apart_drop_the_vehicle` (C43 with C54's test), parametrized:
    - `tire_only` plus `rim_quarter` → dropped (the gutter gap)
    - `rim_quarter` plus `rim_top` → dropped
    - `wheel_covered` plus `hub` → dropped (an exact `half_tire` sits 2 below the tire floor)
    - `wheel_covered` plus `rim_three_quarters` → kept, as `tire` and a floor, landmark `wheel_covered`
  - `test_rim_top_and_wheel_covered_read_as_a_floor`: → `tire` as a floor, from the `wheel_covered` wheel's id.
  - `test_body_reads_only_when_wheels_are_hidden` (C53):
    - `wheels_hidden=True` with `window` → `Reference("body", vehicle id, "window", Reading("tire", True))`; `mid_door` the same
    - `wheels_hidden=False` with a `rim_top` wheel and `window` → the wheel's exact `tire`
    - `wheels_hidden=False` with only `not_visible` wheels and `window` (the small-wheel case, C69) → `vehicle_no_reading`
  - `test_covered_wheel_with_low_body_drops_the_vehicle` (C53):
    - bodies `below_bumper`, `bumper` and `door_sill` → `vehicle_body_below_covered_wheel`
    - body `not_visible` → a `tire` floor from the wheel
    - body `mid_door` → the `wheel_covered` wheel wins the tie over the body
  - `test_no_linked_wheel_reads_from_the_body`: no wheels and `window` → a `tire` floor, kind `body`. No wheels and `bumper` → `vehicle_no_reading`.
  - `test_each_people_row_reads_through`: parametrized over the 7 marks; `not_visible` → `person_no_reading`.
  - Review Focus 1, `test_unanswered_wheel_blocks_the_body_reading`: `KeptVehicle(2, "window", ((5, "not_visible"),), wheels_hidden=False)` → no reference, and the drops equal exactly `Counter({"vehicle_no_reading": 1})`.
- [x] **Step 2:** Run `uv run pytest -q tests/test_measure.py`. Expected: FAIL. Evidence: `uv run pytest -q tests/test_measure.py` → RED 1: ModuleNotFoundError for pipeline.measure, 1 error, exit 2; RED 2 with a stub: 39 failed (Task 5's report).
- [x] **Step 3:** Implement `measure` as specified. Evidence: pipeline/measure.py implemented; same command → 39 passed; 31 of 31 mutants killed (Task 5's report).
- [x] **Step 4:** Run `uv run pytest -q`, then `uv run ruff check .`. Expected: PASS; clean. Evidence: `uv run pytest -q` → 334 passed (294 before); `uv run ruff check .` → All checks passed (Task 5's report).
- [x] **Step 5:** Commit `feat(analysis): add the landmark readings for vehicles and people`. Evidence: commit 65c407e (4:50 PM), after 47fc5bb (R82) and d259d21 (R96); review clean, 0 Critical/Important (SDD ledger).

### Task 6: Combine (steps 6 and 7)

**Files:**
- Create: `backend/analysis/src/lusot_analysis/pipeline/combine.py`
- Test: `backend/analysis/tests/test_combine.py`

**Interfaces:**
- Consumes: `Reference`, `Outcome` (Task 1); `rules.disagree`, `rules.level_index`
- Produces: `combine(references: Sequence[Reference]) -> tuple[Outcome, Reference | None]`, which returns the outcome and the deciding reference (`None` on a refusal). Step 7 (map) is the `rules.PASSABILITY` lookup inside `Outcome.level_result`, so it needs no module of its own.
  - no reference → `refused/no_usable_reference`
  - `disagree(...)` → `refused/references_disagree` (C54)
  - otherwise:
    - the level is the deepest
    - the deciding reference is chosen among those at that level: a floor first, then `wheel` < `body` < `person`, then the lowest `box_id` (C54)
    - `level_is_floor` is true when any floor sits at that level
    - `landmark` is the deciding reference's (C49)
    - `basis` is `{"vehicles": <wheel and body references>, "people": <person references>}`

- [x] **Step 1: Write the failing tests.** The first four are the spec's own examples, on references from different vehicles or people: Evidence: tests/test_combine.py, 16 cases in 11 functions (the spec's examples and C54's ties, each tie in both input orders) (Task 6's report); commit d7fa873.
  - `test_floor_beside_exact_chest_gives_chest`: a `wheel_covered` floor (wheel 4) and an exact `chest` (person 9) → `done`, `chest`, landmark `chest`, `NPATV`, `level_is_floor` False, basis 1 and 1; deciding kind `person`.
  - `test_floor_beside_exact_knee_gives_tire_as_a_floor`: a `wheel_covered` floor (wheel 4) and `rim_three_quarters` (wheel 6) → `tire`, landmark `wheel_covered`, `level_is_floor` True, basis 2 and 0.
  - `test_floor_beside_exact_half_tire_refuses`: a `wheel_covered` floor and `hub` → `references_disagree`.
  - `test_exact_knee_beside_exact_chest_refuses`: people at `knee` and `chest` → `references_disagree`.
  - `test_gutter_gap_refuses` (Rene Q2): `tire_only` beside `rim_quarter`, and `ankle` beside `mid_shin` → each `references_disagree`.
  - `test_one_level_apart_takes_the_deeper`: `hub` (wheel 3) and a person at `knee` (person 8) → `knee`, landmark `knee`, deciding kind `person`.
  - `test_a_standing_adult_alone_sets_the_level` (D13): one person at `knee` → `knee`, `NPLV`, basis 0 and 1.
  - `test_no_reference_refuses`: `[]` → `no_usable_reference`.
  - `test_ties`, parametrized:
    - `rim_top` (wheel 6) and `mid_thigh` (person 9) → landmark `rim_top`, not a floor
    - `rim_top` (wheel 6) and a `window` body (vehicle 2) → landmark `window`, `level_is_floor` True
    - a `wheel_covered` floor (wheel 7) and a `mid_door` body (vehicle 1) → landmark `wheel_covered`
    - `rim_top` on wheels 8 and 5 → deciding `box_id` 5
    - people at `chest` with ids 10 and 9 → deciding `box_id` 9
  - `test_level_is_floor_only_at_the_result_level`: a `wheel_covered` floor and an exact person at `waist` → `waist`, `level_is_floor` False.
  - `test_result_ignores_input_order` (B3): `combine(refs) == combine(list(reversed(refs)))` for a mixed list.
- [x] **Step 2:** Run `uv run pytest -q tests/test_combine.py`. Expected: FAIL. Evidence: `uv run --frozen pytest -q tests/test_combine.py` → RED 1: ModuleNotFoundError for pipeline.combine, 1 error, exit 2; RED 2 with a placeholder: 16 failed (Task 6's report).
- [x] **Step 3:** Implement `combine`. Evidence: pipeline/combine.py implemented; same command → 16 passed; 17 mutants killed after one added assertion (M11) (Task 6's report).
- [x] **Step 4:** Run `uv run pytest -q`, then `uv run ruff check .`. Expected: PASS; clean. Evidence: `uv run --frozen pytest -q` → 106 passed (90 before); `uv run --frozen ruff check .` → All checks passed (Task 6's report).
- [x] **Step 5:** Commit `feat(analysis): combine references into one level, with floors as Rene set them`. Evidence: commit d7fa873 (11:55 AM); review clean, 0 Critical/Important (SDD ledger).

### Task 7: Quality gate and the blur before storage

**Files:**
- Modify:
  - `backend/analysis/src/lusot_analysis/face_blur.py`: move `blur_for_meta`'s shrink into `shrink_to_max_side`, with no behaviour change
  - `backend/analysis/src/lusot_analysis/__init__.py`: the OpenCV cap (R26), if MS1 Task 5 hasn't already moved it there
- Create: `backend/analysis/src/lusot_analysis/pipeline/quality.py`, `backend/analysis/src/lusot_analysis/pipeline/publish.py`
- Test: `backend/analysis/tests/test_quality.py`, `backend/analysis/tests/test_publish.py`, `backend/analysis/tests/test_face_blur.py` (add up to 3 tests)

**Interfaces:**
- Consumes: `decode_image`, `blur_faces`, `FaceBox`, `BlurredImage`, `blur_for_meta` (MS1 Task 3); `box_xyxy` (Task 2)
- Produces:
  - `face_blur.shrink_to_max_side(bgr: np.ndarray, max_side: int = 1600) -> np.ndarray`: `INTER_AREA`, with the rounding `blur_for_meta` uses today. Input that already fits comes back unchanged.
  - in `pipeline.quality` (step 1; C44, C58):
    - `BRIGHTNESS_MIN = 40.0`, `SHARPNESS_MIN = 25.0`, `MAX_SIDE = 1600`
    - `@dataclass(frozen=True) class QualityScores: brightness: float; sharpness: float`
    - `quality_scores(data: bytes) -> QualityScores`: decode, `shrink_to_max_side`, convert to grey, then take the mean, and the variance of `cv2.Laplacian(grey, cv2.CV_64F)`
    - `quality_refusal(scores: QualityScores) -> str | None`: `"too_dark"` when brightness is under 40, else `"too_blurry"` when sharpness is under 25, else `None`
  - in `pipeline.publish` (step 8.1; C48):
    - `PUBLISH_PHRASES = ("face", "license plate")`, `PUBLISH_MARGIN = 0.25`
    - `publish_boxes(sam: Mapping[str, SamResult]) -> list[FaceBox]`: each face and plate instance's mask bounding box, or its SAM box when the mask is empty. A mask box from pixel `x0` to `x1` becomes `FaceBox(x0, y0, x1 - x0 + 1, y1 - y0 + 1, score)`. A SAM box is rounded outward first: floor the start, ceil the end.
    - `publish_pixels(bgr: np.ndarray, sam: Mapping[str, SamResult]) -> np.ndarray`: `blur_faces(bgr, publish_boxes(sam), margin=PUBLISH_MARGIN)`
    - `publish_jpeg(image: BlurredImage, sam: Mapping[str, SamResult]) -> bytes`: `publish_pixels(image.bgr(), sam)`, encoded as JPEG at quality 90

- [x] **Step 1: Write the failing tests:** Evidence: 19 new tests: tests/test_quality.py (10), tests/test_publish.py (6) and 3 in tests/test_face_blur.py (the R94 pin, the shrink, R26's second case); R27 and R26's first case were already MS1's tests (Task 7's report).
  - `test_shrink_to_max_side_matches_blur_for_meta`: a 4000 × 3000 array → shape `(1200, 1600, 3)`; 640 × 480 comes back unchanged; `blur_for_meta` of the same 4000 × 3000 JPEG has the same size. MS1's downscale test keeps passing.
  - `test_package_init_sets_the_opencv_cap` (R26):
    - in a fresh interpreter, with the variable removed from its environment, `import lusot_analysis, os; print(os.environ["OPENCV_IO_MAX_IMAGE_PIXELS"])` prints `50000000`
    - a fresh interpreter that imports `lusot_analysis.pipeline.quality` first refuses MS1's 60 MP header (reuse `declare_size`)

    If it passes before Step 3, MS1 Task 5 already carried R26. Record that in the report.
  - `test_blur_for_meta_rejects_a_short_side_of_32_px` (R27, carried into MS1 Task 4): a 32 × 100 JPEG raises `UndecodableImage`, and 33 × 100 doesn't. If MS1's tests already hold this, record it. If `blur_for_meta` lacks the check, add it to `face_blur.py` in Step 3.
  - `test_cutoffs_are_exact` (C44):
    - `(39.99, 100)` → `too_dark`; `(40.0, 100)` → `None`
    - `(100, 24.99)` → `too_blurry`; `(100, 25.0)` → `None`
    - `(10, 1)` → `too_dark` (dark is checked first)
  - `test_dark_and_flat_photos_are_refused`: `flat_jpeg(10)` → `too_dark`; `flat_jpeg(128)` → `too_blurry`; `noise_jpeg()` → `None`.
  - `test_scores_use_the_photo_before_the_face_blur` (C58): for MS1's portrait fixture, `quality_scores(data)` equals the scores of `shrink_to_max_side(decode_image(data))` to within 1e-9, and its sharpness is above that of `blur_for_meta(data).bgr()`.
  - `test_scores_use_the_shrunk_photo`: a 4000 × 3000 noise JPEG's scores equal those of its 1600 × 1200 shrink.
  - `test_face_and_plate_boxes_are_blurred_and_nothing_else_changes` (C48, B4):
    - setup: 400 × 300 noise; a `face` mask over x 100 to 159, y 80 to 139; a `license plate` mask over x 200 to 259, y 150 to 169; plus `wheel`, `vehicle` and `person` instances
    - pixels outside the two boxes, each grown by 25% on every side, are identical
    - inside each grown box, the Laplacian variance falls by at least 90%
  - `test_blur_covers_the_mask_box_not_the_sam_box`: a face whose SAM box is `(50, 50, 250, 250)` but whose mask covers only x and y 100 to 139. The pixels outside 90 to 149 on both axes are unchanged.
  - `test_empty_mask_falls_back_to_the_sam_box`: an all-False mask with box `(100, 100, 140, 140)` → that region is blurred.
  - `test_publish_jpeg_keeps_the_image_size`: the output starts with `b"\xff\xd8"` and decodes to the image's size.
  - `test_face_blur_settings_are_pinned_to_their_version` (R94, from MS1's final review): `face_blur`'s settings become named module constants (the score threshold 0.6, the margin 0.25, the 10-cell pixelate grid, the `//3` blur kernel, JPEG quality 90 and the 1,600 px side). The test pins each value next to `FACE_BLUR_VERSION`, and its failure message says to bump the version. `eval/rules.md` §10 freezes the blur setting, so a silent change must fail a test. No value changes.
- [x] **Step 2:** Run `uv run pytest -q tests/test_quality.py tests/test_publish.py tests/test_face_blur.py`. Expected: the new tests FAIL. Evidence: `uv run pytest -q tests/test_quality.py tests/test_publish.py tests/test_face_blur.py` → RED 1: 3 collection errors (pipeline.quality, pipeline.publish, shrink_to_max_side missing), exit 2; RED 2 with stubs: 15 failed, 27 passed (Task 7's report).
- [x] **Step 3:** Implement as specified. In `__init__.py`, call `os.environ.setdefault("OPENCV_IO_MAX_IMAGE_PIXELS", "50000000")` before anything imports `cv2`. Keep `face_blur.py`'s own line, which covers a direct import. Evidence: quality.py, publish.py and face_blur.shrink_to_max_side implemented; the R26 cap line was already in __init__.py from MS1, so it is unchanged; 41 of 42 mutants killed, the survivor equivalent (Task 7's report); commits 232005c (R94 constants) and 457baf9.
- [x] **Step 4:** Run `uv run pytest -q`, then `uv run ruff check .`. Expected: PASS; clean. Evidence: `uv run pytest -q` → 353 passed (334 before); `uv run ruff check .` → All checks passed; after the review's fix round 355 passed, ruff clean (Task 7's report and SDD ledger).
- [x] **Step 5:** Commit `feat(analysis): add the quality gate and the face-and-plate blur before storage`. Evidence: commit 457baf9 (5:27 PM), with 232005c (R94) before it; review fix commits 0f56b37 (fail closed on a missing face or plate result) and 648691e (R98, the downscale pin); review clean after 1 fix round (SDD ledger).

### Task 7a: A total deadline, and the SAM check (C84, C85)

**Files:**
- Modify: `backend/analysis/src/lusot_analysis/meta_client.py`, `backend/analysis/src/lusot_analysis/pipeline/types.py` (`ModelClient`), `backend/analysis/tests/fakes.py` (`FakeClient`)
- Test: `backend/analysis/tests/test_meta_client.py`

**Interfaces:**
- Consumes: MS1's `MetaClient` and `MetaApiError`. Read `meta_client.py` first: its retry loop, its 504 background poll and its SAM stream reader, and how its tests fake the transport and the clock.
- Produces:
  - `segment(image, phrase, *, deadline: float | None = None)` and `judge(image, *, prompt, schema, schema_name, deadline: float | None = None)` on `MetaClient`, the `ModelClient` protocol and `FakeClient` (which records it). `deadline` is an absolute `time.monotonic()` value; `None` keeps MS1's behaviour exactly.
  - `class DeadlineExceeded(MetaApiError)`, with `status=None`. The client raises it instead of starting anything that would end after the deadline:
    - a retry wait, `Retry-After` included. The client still never retries early; when the wait it must honour would pass the deadline, it stops.
    - the next sleep of a 504 background poll
    - a SAM stream read: its read timeout becomes the smaller of `timeout_s` and the time left, and a read that times out at the deadline raises `DeadlineExceeded`
  - It subclasses `MetaApiError`, so Task 8 maps it to `failed/model_error` with no new branch.
  - `MetaClient(..., sam_store: bool | None = None)`: `False` sends `store: false` on every SAM request; `None` sends nothing, as MS1 does. Step 4 sets the default.
  - `judge`'s request timeout is the smaller of `timeout_s` and the time left, and a timeout at the deadline raises `DeadlineExceeded`. Two 60 s waits could otherwise push `judge` past the Lambda's limit, and the report would pay again.
  - `judge(..., reasoning_effort: str | None = None)` sends `reasoning: {"effort": ...}` when set (for MS3b's C312). `SparkResult` gains `reasoning_tokens: int | None`, from `usage.output_tokens_details.reasoning_tokens`, and the client's log line carries it.
  - `class ModelRefused(Exception)` (C86): `judge` raises it, before any JSON parsing, when the answer's message content holds a refusal part (`{"type": "refusal", "refusal": ...}`, Meta's Responses `RefusalContent`). It never carries the refusal text into a log. A response whose status is `incomplete` still raises `MetaApiError`.
  - **Cleanups from MS1's final review:** retitle or drop the dead test about a box past the 320 px photo, and correct R75's comment to about 768 KiB of JPEG.

- [x] **Step 1: Write the failing tests**, using the client's existing fakes for the transport and the clock: Evidence: the brief's 8 tests (some parametrized) plus 3 extras in tests/test_meta_client.py, written with the client's fakes and a FakeClock (Task 7a's report); commit cf3d3d5.
  - `test_retry_after_past_the_deadline_stops`: a 503 with `Retry-After: 60` and a deadline 5 s away → `DeadlineExceeded` after 1 call, with no sleep.
  - `test_retry_after_within_the_deadline_is_honoured`: a 503 with `Retry-After: 2`, then 200, with a deadline 30 s away → one sleep of at least 2 s, then the result.
  - `test_background_poll_stops_at_the_deadline`: a 504, then a background job that never finishes → `DeadlineExceeded`, with the fake clock never past the deadline.
  - `test_stream_read_timeout_shrinks_to_the_time_left`: with 6 s left (above the 5 s floor, R106), the stream's read timeout is at most 6 s.
  - `test_sam_store_false_is_sent_only_when_set`: `sam_store=False` puts `"store": false` in the SAM request body; the default sends no `store` key.
  - `test_judge_timeout_shrinks_to_the_time_left`: with 6 s left (above the 5 s floor, R106), `judge`'s request timeout is at most 6 s, and a timeout raises `DeadlineExceeded`.
  - `test_judge_sends_reasoning_effort_and_records_reasoning_tokens`: `reasoning_effort="low"` puts `reasoning: {"effort": "low"}` in the body; a fixture whose `usage.output_tokens_details.reasoning_tokens` is 1,234 gives `SparkResult.reasoning_tokens == 1234`; the default sends no `reasoning` key.
  - `test_judge_raises_model_refused_on_a_refusal_part` (C86): a fixture shaped from Meta's Responses schema, with a `refusal` content part → `ModelRefused`, and the refusal text isn't in `caplog`. An `incomplete` response still raises `MetaApiError`.
  - MS1's tests pass unchanged, which shows `deadline=None` keeps its behaviour.
- [x] **Step 2:** Run `uv run pytest -q tests/test_meta_client.py`. Expected: the new tests FAIL. Evidence: `uv run pytest -q tests/test_meta_client.py` → RED 1: ImportError (cannot import name 'DeadlineExceeded'); RED 2: 15 failed, 66 passed; RED 3 with the keywords accepted but ignored: 14 failed, 67 passed (Task 7a's report).
- [x] **Step 3:** Implement the deadline and `sam_store`. Then run `uv run pytest -q` and `uv run ruff check .`. Expected: PASS; clean. Commit `feat(analysis): give every Meta call a total deadline`. Evidence: commits cf3d3d5 (deadline, judge timeout, reasoning effort and tokens, ModelRefused, sam_store) and 0d89128 (320 px case, R75 note) → test_meta_client.py 81 passed, `uv run pytest -q` 370 passed, ruff clean; review fixes d6bddbd (R103, R104), 749a635 (C88) and f334ffe (R106) → 101 meta tests, 390 passed, ruff clean; review clean after 1 fix round (Task 7a's report and SDD ledger).
- [x] **Step 4 (Claude, at most about $0.0075; C85), before Task 16 and before any Set A development photo goes to Meta.** In one PowerShell command that sets the key from the user variable. Record counts, booleans and statuses only, then put the result in `ms3a.md` for Window 4's privacy drafts. Evidence: done by Claude, 8:37 to 8:40 PM, about $0.008 (SDD ledger, C85 Step 4): the first C87 photo (position 0) showed no vehicle or person, so R105 walked to position 1 and sent it with "person" → 8 instances, boxes inside 1600x1200, frame check PASSED; stream `store: false` accepted (echo False); Muse Spark echo False; background `store: false` → 400. `store: false` became the default in 749a635 (subject "ask Meta not to store SAM streams", not the plan's "SAM requests"); the result is recorded in docs commit 7bcbb5a.
  - **The frame check:** the first photo in C87's full order that has a credit line in `attribution.csv` (a Commons photo; STURM stays offline), enlarged or padded to 1,600 × 1,200 in the session scratchpad and passed through `blur_for_meta`, goes to `segment(image, "vehicle")`. It passes only if a returned box's frame is 1,600 × 1,200. Zero matches is inconclusive: retry once with `"wheel"`. A failure stops everything: `superpowers:systematic-debugging` before any other task, because every real 1,600 px photo would fail.
  - **`store: false` on the stream:** with `MetaClient(sam_store=False)`, judge it by the echoed `store` value, not by the HTTP status. A 400 → resend without it and record the refusal.
  - **The background path:** one `background: true` call with `store: false`, polled to the end. If it fails, the background path keeps Meta's default and deletes the response after reading it.
  - **Muse Spark:** record `judge`'s echoed `store` value once (it already sends `false`).
  - **If `store: false` is accepted:** make it the default on every path, the offline runner included; flip `test_meta_client.py`'s default-store test; commit `fix(analysis): ask Meta not to store SAM requests`. **If refused:** keep `None`, and record that the privacy line about stored copies stays (C85).
  - **Not here:** the request-body size of a real 1,600 px photo. Measure it with no Meta call on the first Set B development phone photo or the first Set A development photo after the split, before MS3b decides the JPEG quality sent to Meta (90 or 85).
- [ ] **Step 5 (optional, only if MS3a is on schedule; Claude, about $0.10 to $0.15):** a `judge`-only latency pre-test on the 5 A1 photos' saved numbered images at default, `low` and `minimal` effort (15 calls), recorded as an estimate. MS3b's C312 decides the effort.

### Task 8: The pipeline function

**Files:**
- Modify: `backend/analysis/src/lusot_analysis/pipeline/__init__.py`, `backend/analysis/tests/fakes.py` (add `level_case`)
- Modify, as built: `pipeline/segment.py` (`segment_all` takes the keyword `deadline`, C84, and raises a key rejection ahead of other failures, R107) and `pipeline/types.py` (`KEY_REJECTED_STATUSES`, R107)
- Test: `backend/analysis/tests/test_pipeline.py` and `test_segment.py`, plus `backend/analysis/tests/test_meta_client.py` if Step 1 finds a gap

**Interfaces:**
- Consumes: Tasks 1 to 7; `blur_for_meta`, `UndecodableImage`; `number_boxes`, `draw_numbered_boxes`, `check_ids_per_item`; `MetaApiError`, `SAM_PHRASES`, `SAM_MODEL`, `SPARK_MODEL`
- Produces, in `lusot_analysis.pipeline`:
  - `READING_PHRASES`: `SAM_PHRASES` without `"face"` and `"license plate"`, so 5 phrases (C66)
  - `@dataclass(frozen=True) class PipelineRun: outcome: Outcome; log: dict[str, object]; publish_jpeg: bytes | None`. It carries no answer: Muse Spark's `reason` never reaches the handler (C62).
  - `run_pipeline(data: bytes, client: ModelClient, prompt: PromptSpec, *, phrases: Sequence[str] = SAM_PHRASES, deadline: float | None = None) -> PipelineRun`, passing `deadline` to every `segment` and `judge` call (C84), in spec §3.2's order:
    - **step 0:** `blur_for_meta(data)`. An `UndecodableImage` here → `failed/bad_file` (undecodable, over 50 MP, or a short side of 32 px or less, R27).
    - **step 1:** `quality_refusal(quality_scores(data))` → `refused/too_dark` or `refused/too_blurry`, with no Meta call
    - **step 2:** `segment_all(client, image, phrases)`
    - **step 4:**
      1. `prepare_boxes`, then `number_boxes(prepared.sam)` and `layout`
      2. `draw_numbered_boxes(image, boxes)`, then **one** `client.judge(drawn, prompt=prompt.text, schema=prompt.schema, schema_name=prompt.schema_name)`
      3. `validate_answer`
      4. `check_ids_per_item`
      5. `gate(answer, has_water=water_found(sam["floodwater"]))`
      6. `apply_drops`
    - **step 5:** `measure`
    - **steps 6 and 7:** `combine`
    - **step 8.1:** a level result, with both `PUBLISH_PHRASES` among `phrases` → `publish_jpeg(image, sam)`. Otherwise `None`.
    - **Errors (C59, C73):**
      - A `MetaApiError` whose `.status` is 401, 402 or 403 raises `ModelKeyRejected(status)` out of `run_pipeline`. It is not an outcome (C73).
      - Any other `MetaApiError`, or a `ModelAnswerError` → `failed/model_error`. Check `MetaApiError` before anything broader: it subclasses `RuntimeError`.
      - The error `judge` raises on an answer that isn't JSON (read `meta_client.py` to learn which class) is turned into `ModelAnswerError`.
      - Any other exception → `failed/pipeline_error`.
      - The log keeps the error's class name (`error`) and, for `MetaApiError`, `meta_status`. It never keeps the message.
  - **The log's keys (exact)**, each present once its step has run:
    - `blur_version`, `face_boxes`, and `brightness` and `sharpness` (1 decimal)
    - `meta_calls`: the `segment` and `judge` calls made
    - `sam_ms` (`{phrase: ms}`), `instances` (`{phrase: count}`)
    - `spark_ms`, `input_tokens`, `output_tokens`
    - `models` (`{"sam": SAM_MODEL, "spark": SPARK_MODEL}`), `prompt_version`
    - `numbered` (`{"vehicles", "wheels", "people"}`)
    - `drops`: `{cause: count}`, merged from every step
    - `deciding`: the kind, on level results only
    - `error`, `meta_status`: on failures only
- Produces, in `tests/fakes.py`: `level_case() -> tuple[bytes, dict[str, SamResult], dict]`, the photo, SAM results and answer of `test_level_result_end_to_end` below. Tasks 9 and 13 reuse it as "the level case".

- [x] **Step 1:** Check MS1's work and record each finding in the task report: Evidence: Task 8's report, "Step 1: MS1's work, checked": the BlurredImage-subclass and short-key tests exist, every timeout or lost connection is a MetaApiError, judge's non-JSON answer raises JSONDecodeError (mapped to ModelAnswerError), ModelRefused maps to refused/model_declined, and P5 = 0 face boxes over wheel boxes (probe note §5).
  - `tests/test_meta_client.py` covers both §3.6 items: a `BlurredImage` subclass is refused (`type(img) is BlurredImage`), and a key under 20 characters is refused. If either test is missing, add it there (`test_rejects_blurred_image_subclass`, `test_short_key_refused`).
  - Read `meta_client.py` for the classes it raises on a timeout or a connection error that outlasts its retries. They are Meta errors, so they end `failed/model_error` (C59), never `pipeline_error`. Add each to the Errors mapping and to `test_model_errors_pay_once`.
  - Read the probe note's count of face boxes that overlap wheel boxes (P5). If it is above 0, stop and report it: the controller rules on P5 before this task goes on.
  - C86: map Task 7a's `ModelRefused` to `refused/model_declined`. Add `"model_declined"` to `REFUSED_REASONS` in `pipeline/types.py` (and update Task 1's reason-list test), and add a case to `test_gate_outcomes_through_the_pipeline`. Check `ModelRefused` before the broader exceptions.
- [x] **Step 2: Write the failing tests** (`FakeClient`, `noise_jpeg()`, `prompt = load_prompt(REPO_PROMPTS)`): Evidence: 37 new tests in tests/test_pipeline.py using FakeClient, noise_jpeg() and level_case() (Task 8's report); commit 61502cf.
  - `test_level_result_end_to_end`, built from `level_case()`:
    - SAM: `vehicle (100, 100, 400, 300)`, `wheel (150, 250, 200, 300)`, `floodwater (0, 280, 640, 480)`, `face (300, 120, 330, 150)`, `license plate (220, 270, 280, 290)`
    - answer: vehicle 1, `sedan_hatch`, not moving, body `not_visible`; wheel 2 at `rim_three_quarters`
    - outcome: `Outcome.level_result("knee", "rim_three_quarters", False, {"vehicles": 1, "people": 0})`
    - `publish_jpeg` decodes to 640 × 480
    - the fake's calls: 7 `segment` (one per phrase) and 1 `judge`; every image it saw has `type(...) is BlurredImage`
    - the log: `meta_calls == 8`, `deciding == "wheel"`, `set(sam_ms) == set(SAM_PHRASES)`, the two model ids, `prompt_version == PROMPT_VERSION`
  - `test_quality_refusals_make_no_meta_call`: `flat_jpeg(10)` → `too_dark`; `flat_jpeg(128)` → `too_blurry`. Each makes no calls and has `meta_calls == 0`.
  - `test_bad_files`: `b"not a jpeg"` and a 32 × 32 JPEG (R27) → `failed/bad_file`, with no calls.
  - `test_gate_outcomes_through_the_pipeline`, parametrized: `photo_unusable`, `water_unsure`, no flood seen, and `no_water_found` (empty floodwater). Each gives the exact outcome and `publish_jpeg is None`.
  - `test_refusals_after_the_drops`:
    - only a moving vehicle → `no_usable_reference`
    - a `tire_only` wheel on car A plus a person at `chest` → `references_disagree`
  - `test_model_errors_pay_once`, parametrized; each case → `failed/model_error`, with at most 1 `judge` call and `error` set to the class name:
    - `segment` raises `meta_error(500)`
    - `judge` raises `meta_error(400)`
    - the answer has an extra key
    - the answer has an id as a string
    - `judge` raises the class it raises on a non-JSON answer (see **Errors** above)
  - `test_rejected_key_raises` (C73), parametrized: `segment` raises `meta_error(401)`, `segment` raises `meta_error(402)`, and `judge` raises `meta_error(403)` → each raises `ModelKeyRejected` with that status. In the `judge` case, the fake recorded exactly 1 `judge` call.
  - `test_deadline_reaches_every_call` (C84): `run_pipeline(..., deadline=123.0)` → every `segment` and `judge` call the fake recorded carries `deadline=123.0`.
  - `test_deadline_exceeded_is_a_model_error` (C84): `segment` raises `DeadlineExceeded` → `failed/model_error`, `error == "DeadlineExceeded"`, and no `judge` call.
  - `test_other_exceptions_are_pipeline_errors`: `segment` raises `KeyError("boom-marker")` → `failed/pipeline_error`, and `"boom-marker"` isn't in `json.dumps(run.log)`.
  - `test_reason_text_never_reaches_the_log` (C62): `"REASON-MARKER-31"` isn't in `json.dumps(run.log)`, and `PipelineRun` has no field holding the answer.
  - `test_reading_phrases_skip_face_and_plate` (C66): with `phrases=READING_PHRASES`, `segment` is called 5 times, never for `face` or `license plate`, and a level result has `publish_jpeg is None`.
  - `test_bad_ids_are_dropped_before_the_gate`: water no, plus a wheel with id 99 at `rim_top` → no flood seen.
  - Review Focus 3, `test_empty_scene_still_asks_muse_spark_once`: every SAM result is empty, and nothing raises. Each answer below causes exactly one `judge` call:
    - water no → no flood seen
    - water yes → `no_water_found`
    - usable no → `photo_unusable`
- [x] **Step 3:** Run `uv run pytest -q tests/test_pipeline.py`. Expected: FAIL. Evidence: `uv run pytest -q tests/test_pipeline.py tests/test_pipeline_types.py` → RED: ImportError (cannot import name 'READING_PHRASES'), 1 error; test_pipeline_types.py 1 failed, 38 passed (the missing model_declined reason) (Task 8's report).
- [x] **Step 4:** Implement `run_pipeline`, `PipelineRun` and `READING_PHRASES`. Count `meta_calls` around the client calls. Take the timings from `SamResult.elapsed_s` and `SparkResult.elapsed_s`. Evidence: run_pipeline, PipelineRun and READING_PHRASES implemented; segment_all gained a deadline keyword and REFUSED_REASONS gained model_declined (C86); `uv run pytest -q tests/test_pipeline.py tests/test_pipeline_types.py tests/test_segment.py` → 88 passed; 23 of 23 mutants killed, then 27 of 27 after the R107 fix df3c7db (Task 8's report).
- [x] **Step 5:** Run `uv run pytest -q`, then `uv run ruff check .`. Expected: PASS; clean. Evidence: `uv run pytest -q` → 427 passed (390 before), 434 passed after the R107 fix; `uv run ruff check .` → All checks passed (Task 8's report).
- [x] **Step 6:** Commit `feat(analysis): add the pipeline function shared by the Lambda and the laptop`. Evidence: commit 61502cf (9:38 PM), then fix df3c7db (10:07 PM, R107); review clean after 1 fix round (SDD ledger).

### Task 9: Saved outputs and the offline runner

**Files:**
- Create: `backend/analysis/src/lusot_analysis/pipeline/saved.py`, `backend/analysis/probes/run_pipeline.py`
- Test: `backend/analysis/tests/test_saved.py`, `backend/analysis/tests/test_run_pipeline.py`

**Interfaces:**
- Consumes: `run_pipeline`, `PipelineRun`, `READING_PHRASES` (Task 8); `load_prompt`, `PromptSpec` (Task 3); `MetaClient`, `MissingApiKey`, `SamInstance`, `SamResult`, `SparkResult`; `ModelAnswerError`
- Produces, in `lusot_analysis.pipeline.saved`:
  - `RecordingClient(client: ModelClient)` passes each call through and keeps each `SamResult` and `SparkResult`, behind a `threading.Lock`, because the phrases run in parallel. `.save(run_dir: Path, *, photo: Path, prompt: PromptSpec, run: PipelineRun) -> None`.
  - Both clients take the protocol's keyword arguments, `deadline` on both calls and `reasoning_effort` on `judge` (Task 7a). `RecordingClient` passes them through unchanged, and `SavedOutputsClient` accepts and ignores them (R108).
  - `SavedOutputsClient(run_dir: Path, photo_data: bytes)`:
    - it raises `PhotoMismatch`, a `ValueError` with the message "saved outputs belong to another photo", when the photo's SHA-256 differs from `run.json`'s
    - `.segment` returns the saved result and checks the image size against the saved size. A phrase the live run asked for, with no saved result, raises `MetaApiError(status=log["meta_status"])` when the saved log has `meta_status`, and `KeyError` otherwise, so the replay ends as the live run did (R109). `face` and `license plate` come back empty when they weren't asked for (C66). Any other missing phrase raises `KeyError`.
    - `.judge` returns the saved answer after checking `schema_name`. It raises `ModelRefused` for a saved refusal (R109), and `ModelAnswerError` when the live run saved no answer.
  - **The saved layout (exact):**
    - `run.json`: `photo` (the file name only), `photo_sha256`, `phrases`, `prompt_version`, `schema_name`, `models`, `blur_version`, `image` (`{width, height}`), `outcome` (`dataclasses.asdict`), `log`
    - `sam/<phrase>.json`, with spaces in the phrase as `_`: `phrase`, `elapsed_s`, `instances` (`[{id, box, score}]`)
    - `sam/<phrase>.npz`: `masks`, an N×H×W bool array, written only when N > 0
    - `sam/<phrase>.raw`: SAM's raw output text (§3.7)
    - `spark.json`: `data` (with its `reason`, which only the offline runner keeps, C62), `input_tokens`, `output_tokens`, `reasoning_tokens` (None when Meta didn't report it; restored on replay, R108), `elapsed_s`
    - `spark.raw`: the raw answer text
    - after a live refusal, `spark.json` is exactly `{"refused": true}`, with no `spark.raw`, since `ModelRefused` carries no text (C86, R109)
- Produces, in `probes/run_pipeline.py` (§3.7):
  - `refuse_sealed(*paths: Path) -> None` raises `SystemExit(2)` when any part of a resolved path equals `sealed`, ignoring case. It runs before any file is opened or listed (C66).
  - `refuse_sturm_live(photo: Path) -> None` (C87): in `live` mode only, raises `SystemExit(2)` with `refused: STURM photos stay offline` when any part of the resolved path equals `sturm_flooddepth`, ignoring case. `replay` is allowed, since it makes no Meta call.
  - `refuse_data_in_repo(data_dir: Path) -> None` (R111): in `live` mode, after `refuse_sealed` and before any client or folder, raises `SystemExit(2)` with `refused: the data folder is inside the repo` when the resolved data folder lies inside the repo. Run folders hold masks and Muse Spark's reasons (C62).
  - `make_client() -> MetaClient` builds the client from `MODEL_API_KEY`. Tests replace it.
  - `live(photo: Path, data_dir: Path) -> tuple[Path, PipelineRun]` writes the run directory `<data_dir>/runs/<YYYY-MM-DD>/<photo stem>-<HHMMSS>`.
  - `replay(photo: Path, run_dir: Path) -> PipelineRun`
  - `main(argv: list[str] | None = None) -> int`:
    - commands: `live <photo> [--data-dir DIR]`, where the directory defaults to `LUSOT_DATA_DIR`, and `replay <photo> <run dir>`
    - exit 0; 1 when a replay's outcome differs from the saved one; 2 when refused (a sealed path, a STURM photo in live mode, a data folder inside the repo, a missing or short key, a key Meta rejects with `ModelKeyRejected`, another photo; argparse's usage errors also exit 2); 3 when the run can't read or write what it needs, printed as `failed: <class name>` with no path (R110)
    - prints only: the outcome's `log_name` and level, `meta_calls`, instances and ms per phrase, Muse Spark's ms, tokens, drops, and on replay `same as saved: True|False`
    - never prints the answer, its reason or the key. Every line masks 12-digit runs.

- [x] **Step 1: Write the failing tests.** The runner is loaded with `importlib.util.spec_from_file_location("run_pipeline_script", ...)`. Evidence: tests/test_saved.py (13) and tests/test_run_pipeline.py (15) (Task 9's report); the pre-review and fix rounds added the R109 replay cases, the early-exit saves, R110's exit-3 cases and R111's data-folder cases (49 task tests in all).
  - `test_record_then_replay_gives_the_same_outcome`: `level_case()` recorded with `phrases=READING_PHRASES`, saved to `tmp_path`, then run again through `SavedOutputsClient` → an equal `Outcome`, and equal `log["drops"]` and `log["instances"]`.
  - `test_saved_layout`: the files listed above exist; `spark.json` holds the reason marker; no file is named after `face` or `license_plate`.
  - `test_saved_masks_round_trip`: the masks are `np.array_equal` after saving and loading.
  - `test_replay_refuses_another_photo`: other bytes → `ValueError`.
  - `test_replay_of_a_model_error`: a live `judge` raised `meta_error(500)`, so no answer was saved. The replay → `failed/model_error`.
  - `test_refuses_paths_inside_sealed_folders`, parametrized over `tmp_path/"sealed"/"x.jpg"`, `tmp_path/"a"/"Sealed"/"x.jpg"` and `tmp_path/"sealed"/"sub"/".."/"x.jpg"`. None of these exists, and the test creates none. `main(["live", str(p)]) == 2`, and the output says `refused: path inside a folder named sealed`. `refuse_sealed(tmp_path/"unsealed"/"x.jpg")` doesn't raise.
  - `test_live_refuses_sturm_photos` (C87): `main(["live", str(tmp_path/"set_c"/"sturm_flooddepth"/"x.jpg")])` exits 2 with that message, and no client is built; `replay` on such a path isn't refused by this rule.
  - `test_live_sends_the_reading_phrases_and_saves_under_the_data_dir`: `make_client` is replaced by a `FakeClient`, with `--data-dir tmp_path`. The result: exit 0, a run directory under `tmp_path/"runs"`, 5 `segment` calls, `meta_calls` in the output, and no `REASON-MARKER-31` in it.
  - `test_missing_or_short_key_exits_2_without_echo`: `MODEL_API_KEY` is `"\x16"` and the real `make_client` is used → exit 2, and `"\x16"` isn't in the output.
  - `test_rejected_key_exits_2` (C73): a `FakeClient` whose `segment` raises `meta_error(401)` → exit 2, and no run directory is written.
  - `test_replay_needs_no_key`: with `MODEL_API_KEY` removed, `replay` of a recorded run → exit 0 and `same as saved: True`.
- [x] **Step 2:** Run `uv run pytest -q tests/test_saved.py tests/test_run_pipeline.py`. Expected: FAIL. Evidence: `uv run pytest -q tests/test_saved.py tests/test_run_pipeline.py` → RED: ModuleNotFoundError for pipeline.saved and FileNotFoundError for probes/run_pipeline.py, 2 errors (Task 9's report).
- [x] **Step 3:** Implement `saved.py` and the runner. The runner loads the prompt with `load_prompt(Path(__file__).resolve().parents[1] / "prompts")`. That is allowed: only package code must not walk up from `__file__`, and the runner runs only in the repo. Evidence: pipeline/saved.py and probes/run_pipeline.py implemented (44926cf), then changed by rulings: R108 (spark.json keeps reasoning_tokens), R109 (a refusal or a failed SAM call replays to its live outcome, 1c7cb20), R110 (other I/O and parse errors exit 3) and R111 (live refuses a data folder inside the repo), both in 663c146; 28 passed at first, 49 task tests at the end; 37 of 37 mutants killed, then 14 of 14 on the last round (Task 9's report).
- [x] **Step 4:** Run `uv run pytest -q`, then `uv run ruff check .`. Expected: PASS; clean. Evidence: `uv run pytest -q` → 462 passed (434 before), 472 after R109, 483 after R110 and R111; `uv run ruff check .` → All checks passed (Task 9's report). The controller's baa69a0 then built one test's 12-digit string at run time so `node scripts/check_account_ids.mjs` stays clean.
- [x] **Step 5:** Commit `feat(analysis): add the offline runner with live and replay modes`. Evidence: commit 44926cf (10:49 PM), then 1c7cb20 (R109), 663c146 (R110, R111) and baa69a0; review clean after a pre-review R109 round and 1 fix round (SDD ledger).

### Task 10: API result fields

**Files:**
- Modify: `backend/api/src/reports.ts`
- Test: `backend/api/test/reports.test.ts`

**Interfaces:**
- Consumes: the report item's attributes as `Outcome.item_fields()` names them (Task 1). Tasks 12 and 13 write them, plus `photoKey`, `claimToken` and `claimedAt`.
- Produces: the `GET /reports/{id}` 200 body (C67):
  - always `reportId`, `status` and `capturedAt`; `refusalReason` when the item has one
  - on `done`: `noFloodSeen` (a boolean). With a level, also `level`, `landmark`, `passability`, `basis: {vehicles, people}` and `levelIsFloor`.
  - never `lat`, `lng`, `gpsAccuracyM`, `readings`, `photoKey`, `overlayKey`, `claimToken`, `claimedAt`, `pk` or `sk`. Build the body from an allow-list, as now. `basis` is copied as exactly its two counts.

- [x] **Step 1: Write the failing Vitest tests** (keep the MS1 tests: old `failed/pipeline_not_built` reports read as before): Evidence: 5 tests (6 cases) added to backend/api/test/reports.test.ts, MS1's tests untouched (Task 10's report); commit c13be20.
  - `a done report with a level returns the level fields`: an exact `toEqual` on `{reportId, status: "done", capturedAt, noFloodSeen: false, level: "knee", landmark: "rim_three_quarters", passability: "NPLV", basis: {vehicles: 1, people: 1}, levelIsFloor: false}`.
  - `a done report with no flood seen returns noFloodSeen and nothing else new`.
  - `refused and failed reports carry only refusalReason`: `refused/too_dark` and `failed/model_error`.
  - `a processing report carries no result or claim fields`: exactly `{reportId, status: "processing", capturedAt}`.
  - `never returns the location, readings, photo key or the claim`: a stored item holds all of those plus the level fields. Every key of the body is in the allowed set, and the body text contains none of the forbidden names.
- [x] **Step 2:** Run `npm test -w backend/api`. Expected: FAIL. Evidence: `npm test -w backend/api` → RED, exit 1: 3 failed, 38 passed (Task 10's report).
- [x] **Step 3:** Implement the allow-list in `getReport`. Evidence: allow-list in getReport (backend/api/src/reports.ts, +16 -3); 3 planted mistakes each failed the tests, then the file was restored byte for byte (Task 10's report).
- [x] **Step 4:** Run `npm test -w backend/api`, then `npm run typecheck -w backend/api`. Expected: PASS; clean. Evidence: `npm test -w backend/api` → 41 passed (35 before); `npm run typecheck -w backend/api` → exit 0 (Task 10's report).
- [x] **Step 5:** Commit `feat(api): return the landmark result fields from GET /reports/{id}`. Evidence: commit c13be20 (12:10 PM); review clean, 0 Critical/Important (SDD ledger).

### Task 11: The result on the test screen

**Files:**
- Modify: `app/src/lib/api.ts`, `app/src/App.tsx`
- Test: `app/src/lib/api.test.ts`, `app/src/App.test.tsx`

**Interfaces:**
- Consumes: Task 10's body
- Produces:
  - `ReportResult` gains `noFloodSeen?: boolean`, `level?: string`, `landmark?: string`, `passability?: string`, `basis?: { vehicles: number; people: number }` and `levelIsFloor?: boolean`
  - `pollReport` keeps its signature and resolves with `status`, `refusalReason` and those fields only, as today it drops `reportId` and `capturedAt`. It still polls through `pending`, `processing` and 404 (R30, R32).
  - `export class PollTimeoutError extends Error`, built as `new PollTimeoutError(reportId, timeoutMs)`, is thrown on a timeout. It builds today's message: `` `No result for report ${reportId} after ${timeoutMs / 1000} s` ``.
  - The result shows as one `<p>` per line inside the status region, without MS1's `Final status:` prefix, so each line can be matched exactly.
  - the result lines (§3.8). This is test-build wording; final wording waits for MS5 and Rene's review (M20).
    - **A level**, three lines (C81):
      - For MMDA's 7 levels: `<words> at this spot (MMDA level).`, where the words are `Gutter deep`, `Half-knee deep`, `Half-tire deep`, `Knee deep`, `Tire deep`, `Waist deep` and `Chest deep`. The two added levels drop "(MMDA level)": `Below gutter deep at this spot.` and `Above chest deep at this spot.` With `levelIsFloor`, the line starts `At least` and the words go lower case, as in `At least tire deep at this spot (MMDA level).`
      - For MMDA's 7 levels: `MMDA lists this level as <class words> (<passability>).`, where the class words are `passable to all vehicles` (PATV), `not passable to light vehicles` (NPLV) and `not passable to any vehicle` (NPATV). For `below_gutter`: `Shallower than MMDA's gutter level, which MMDA lists as passable to all vehicles (PATV).` For `above_chest`: `Deeper than MMDA's chest level, which MMDA lists as not passable to any vehicle (NPATV).`
      - `From <n> reference object<s>.`, where n is the vehicles plus the people
    - **No flood seen:** `No flood seen.`
    - **A refusal:** `I can't tell from this photo. Retake it from a dry spot with a parked car's wheel or a person standing still in view. Don't step into the water or the road.` Rene confirmed this English line (D19, C81); plan §9's own line uses the banned word.
    - **Processing failed, and a poll timeout:** `Processing failed, try again.`
    - **Refused and failed** results add a small line, `Reason: <refusalReason>` (`text-xs`).
    - The message comes from `status`, never from the reason (C50). So MS1's `pipeline_not_built` now reads as processing failed. MS1's footer line stays.

- [x] **Step 1: Write the failing Vitest tests:** Evidence: 18 new cases: 1 in app/src/lib/api.test.ts and 17 in app/src/App.test.tsx, and 2 existing tests updated (Task 11's report); commit bbcaf03.
  - `pollReport returns the result fields`: a `done` body with every field → `toEqual` on those fields.
  - `pollReport times out with a clear error`: also `rejects.toBeInstanceOf(PollTimeoutError)`.
  - Update `App uploads the photo and shows the result` (`failed/pipeline_not_built`): it now shows `Processing failed, try again.` and `Reason: pipeline_not_built`.
  - `App shows a level result`: `knee`, `NPLV`, basis 1 and 1 → `Knee deep at this spot (MMDA level).`, `MMDA lists this level as not passable to light vehicles (NPLV).`, `From 2 reference objects.`
  - `App says at least for a floor`: `tire`, `levelIsFloor`, `NPATV`, basis 1 and 0 → `At least tire deep at this spot (MMDA level).`, `MMDA lists this level as not passable to any vehicle (NPATV).` and `From 1 reference object.`
  - `App never calls the two added levels MMDA's` (CLAUDE.md, C81), parametrized:
    - `below_gutter`, `PATV` → `Below gutter deep at this spot.` and `Shallower than MMDA's gutter level, which MMDA lists as passable to all vehicles (PATV).`
    - `above_chest`, `NPATV` → `Above chest deep at this spot.` and `Deeper than MMDA's chest level, which MMDA lists as not passable to any vehicle (NPATV).`
    - in both, the text `(MMDA level)` appears nowhere on the screen
  - `App shows no flood seen`.
  - `App shows a refusal and its reason`: `refused/too_dark` → the refusal line and `Reason: too_dark`.
  - `App shows processing failed and its reason`: `failed/model_error`.
  - `A poll timeout reads as processing failed`: `pollReport` rejects with `PollTimeoutError` → `Processing failed, try again.`, with no "did not work" alert.
  - `no screen uses the banned word`: for each state above, `document.body.textContent` doesn't match `/\bsafe\b/i`.
- [x] **Step 2:** Run `npm test -w app`. Expected: FAIL. Evidence: `npm test -w app -- --reporter=verbose` → RED, exit 1: 12 failed, 28 passed (Task 11's report).
- [x] **Step 3:** Implement it, keeping the change small: a `describeResult(result): { lines: string[]; reason?: string }` in `App.tsx`. Visual design waits for MS5 (R3). Evidence: describeResult in app/src/App.tsx, and PollTimeoutError plus the result fields in app/src/lib/api.ts; copy and markup only, per R83 (Task 11's report).
- [x] **Step 4:** Run `npm test -w app`, then `npm run typecheck -w app` and `npm run lint -w app`. Expected: PASS; clean. Evidence: `npm test -w app` → 40 passed (22 before); `npm run typecheck -w app` → exit 0; `npm run lint -w app` → exit 0 (Task 11's report).
- [x] **Step 5:** Commit `feat(app): show the landmark result on the test screen`. Evidence: commit bbcaf03 (12:31 PM); review clean, 0 Critical/Important (SDD ledger).

### Task 12: Report store: the claim and the result writes

**Files:**
- Create: `backend/analysis/src/lusot_analysis/report_store.py`, and `backend/analysis/tests/fakes.py` with `create_reports_table` only. This task runs before MS1 closes (D20), so `fakes.py` must not import `meta_client`; Task 2 adds the rest.
- Test: `backend/analysis/tests/test_report_store.py`

**Interfaces:**
- Consumes: `Outcome.item_fields()` (Task 1); the table's keys `pk`, `sk` and `reportId-index` (MS1)
- Produces, in `lusot_analysis.report_store` (G2, C46):
  - `LEASE_S = 900`
  - `FINAL_STATUSES = frozenset({"done", "refused", "failed"})`
  - `ClaimState = Literal["claimed", "finished", "leased"]`
  - `claim(ddb, table: str, key: Mapping[str, dict], token: str, now_s: int) -> ClaimState` is one `UpdateItem`:
    - it sets `#status = :processing`, `claimToken = :token` and `claimedAt = :now`, a Number in epoch seconds
    - condition: `#status = :pending OR (#status = :processing AND claimedAt < :expired)`, where `:expired = now_s - LEASE_S`
    - it passes `ReturnValuesOnConditionCheckFailure="ALL_OLD"`. On `ConditionalCheckFailedException`, it reads the item from `exc.response["Item"]`: a status in `FINAL_STATUSES` → `"finished"`; `processing` with this `token` → `"claimed"`, because the SDK retried a claim that had succeeded (C82); anything else → `"leased"`. moto 5.2.4 supports this.
    - other AWS errors propagate
  - `write_result(ddb, table: str, key: Mapping[str, dict], token: str, fields: Mapping[str, str | bool | int | Mapping[str, int]]) -> bool` is one `UpdateItem` that sets every field:
    - condition: `#status = :processing AND claimToken = :token`, with `ReturnValuesOnConditionCheckFailure="ALL_OLD"`. When that fails and the old item holds this `token` and the `status` being written, the SDK retried a write that had succeeded, so it returns True (C82). Otherwise it returns False: the lease was lost.
    - every attribute name goes through `ExpressionAttributeNames`. `status` and `level` are DynamoDB reserved words, and moto enforces them.
    - values: `str` → `S`, `bool` → `BOOL` (check it before `int`), `int` → `N`, a mapping of ints → `M`
- Produces, in `tests/fakes.py`: `create_reports_table(ddb, name: str) -> None`, the table and index as MS1's `test_handler.py` creates them

- [x] **Step 1: Write the failing tests** (moto `mock_aws`, `now_s = 1_800_000_000`): Evidence: tests/test_report_store.py, 14 cases on moto mock_aws with now_s = 1_800_000_000, and tests/fakes.py with create_reports_table (Task 12's report); the R84 fix round made it 16 cases (afe9394).
  - `test_claims_a_pending_report`: → `"claimed"`; the status is `processing`, with the token and `claimedAt == now_s`.
  - `test_finished_reports_are_not_claimed`, parametrized over `done`, `refused`, `failed` → `"finished"`; the item is unchanged.
  - `test_live_lease_is_respected`: `processing` with `claimedAt = now_s - 900` → `"leased"`, because exactly 15 minutes is still live. The item is unchanged.
  - `test_expired_lease_is_reclaimed`: `processing`, `claimedAt = now_s - 901`, token `"old"` → `"claimed"`, with the new token and `claimedAt == now_s`.
  - Review Focus 2, `test_finished_report_with_old_claim_is_never_reclaimed`: `done`, `claimedAt = now_s - 3600`, token `"old"` → `"finished"`; the item is unchanged.
  - `test_writes_a_level_result_under_the_claim`: claim, then `write_result` with `Outcome.level_result("knee", "rim_three_quarters", False, {"vehicles": 1, "people": 0}).item_fields() | {"photoKey": "blurred/r_<32 hex>.jpg"}` → True. The item has `status` `done`, `noFloodSeen` `{"BOOL": False}`, `level`, `landmark`, `passability`, `levelIsFloor`, `basis {"M": {"vehicles": {"N": "1"}, "people": {"N": "0"}}}` and `photoKey`; `claimToken` stays.
  - `test_writes_refusals_and_failures`, parametrized over `refused/too_dark` and `failed/model_error` → exactly `status` and `refusalReason` among the result fields.
  - `test_lost_lease_drops_the_write`: claim with `"a"`, then set `claimToken` to `"b"` directly → `write_result(..., "a", ...)` is False, and the item keeps `processing` and `"b"`.
  - `test_write_requires_processing`: a `done` item holding token `"a"` → False.
  - `test_other_aws_errors_propagate`: `update_item` patched to raise `ProvisionedThroughputExceededException` → both `claim` and `write_result` raise `ClientError`.
  - `test_a_repeated_claim_is_its_own` (C82): `claim` twice with the same token and `now_s` → `"claimed"` both times; the item is unchanged by the second.
  - `test_a_repeated_write_is_its_own` (C82): claim, then `write_result` twice with the same token and fields → True both times. A `write_result` with another token on that finished item → False.
- [x] **Step 2:** Run `uv run pytest -q tests/test_report_store.py`. Expected: FAIL. Evidence: `uv run --frozen pytest -q tests/test_report_store.py` → RED 1: ModuleNotFoundError for fakes; RED 2 (fakes added): ModuleNotFoundError for lusot_analysis.report_store; each 1 error, exit 2 (Task 12's report).
- [x] **Step 3:** Implement `report_store.py` and `create_reports_table`. Evidence: report_store.py (claim, write_result, LEASE_S, FINAL_STATUSES) and create_reports_table; 14 passed, 16 of 16 mutants killed; after R84 (a repeated claim or write counts as the worker's own, spec C82) 16 passed, 24 of 25 mutants killed, 1 equivalent (Task 12's report).
- [x] **Step 4:** Run `uv run pytest -q`, then `uv run ruff check .`. Expected: PASS; clean. Evidence: `uv run --frozen pytest -q` → 120 passed (106 before), 122 after the R84 fix; `uv run --frozen ruff check .` → All checks passed (Task 12's report).
- [x] **Step 5:** Commit `feat(analysis): claim reports before paying and write results under the claim`. Evidence: commit eb7e7a6 (12:54 PM), then fix afe9394 (1:13 PM); review clean after 1 fix round (SDD ledger).

### Task 13: The handler (replaces the MS1 stub)

**Files:**
- Modify: `backend/analysis/src/lusot_analysis/handler.py`
- Test: `backend/analysis/tests/test_handler.py` (rewritten; keep the MS1 tests that still hold)

**Interfaces:**
- Consumes:
  - `run_pipeline`, `PipelineRun` (Task 8); `load_prompt` (Task 3); `SAM_PHRASES`, `MetaClient`, `MissingApiKey`
  - `claim`, `write_result` (Task 12); `Outcome`; `SavedOutputsClient`, and the runner's `live` and `replay` (Task 9, in tests)
  - environment: `TABLE_NAME`, `BUCKET_NAME`, `STOP_PARAM_PREFIX`, `MODEL_KEY_PARAM`, and `PROMPTS_DIR`, which is new and set by the Dockerfile in Task 14
- Produces:
  - `handler.handler(event: dict, context) -> dict`, with the same shape as MS1's
  - `handler.analyse(data: bytes, client: ModelClient, *, deadline: float | None = None) -> PipelineRun`: the handler's pipeline call, `run_pipeline(data, client, _prompt(), phrases=SAM_PHRASES, deadline=deadline)` (B3)
  - `DEADLINE_MARGIN_S = 30` (C88) and `_deadline(context) -> float | None`: `time.monotonic() + context.get_remaining_time_in_millis() / 1000 - DEADLINE_MARGIN_S`, or `None` when the context has no such method, as in tests that pass `None` (C84)
  - the log `outcome` values (exact): each result's `Outcome.log_name`, plus `already_finished`, `lease_held`, `lease_lost`, `unknown_key`, `s3_test_event`, `error`, `model_key_loaded=true`, `model_key_missing` and `model_key_rejected`
- **The flow for each S3 record** (spec §3.1):
  1. Skip test events. A key that isn't `raw/r_<32 hex>.jpg` is deleted and logged as `unknown_key` (MS1).
  2. `_find_report` through `reportId-index`. If the report isn't there yet, set that message's visibility to 10 s with `ChangeMessageVisibility` (the record's `receiptHandle`, and the queue URL built from its `eventSourceARN`, never logged), then retry (R92, from MS1's final review). Otherwise the retry would wait the full 1,080 s, far past the app's 120 s poll. If that call fails, log its error fields and retry anyway.
  3. Three loads, in this order:
     - `_meta_client()`: the key from SSM (`WithDecryption`), then `MetaClient(api_key=value)`. It is kept in `_META_CLIENT` only once it succeeds. It logs `model_key_loaded=true` once, or `model_key_missing` with the error fields.
     - `_prompt()`, cached with `functools.cache`: `load_prompt(Path(os.environ["PROMPTS_DIR"]))`
     - `_model_calls_switch()`: the SSM value, not cached

     If any of these fails, the message returns for retry and the report stays untouched (C60). A missing prompt is a deploy fault, like a key fault: it goes to the DLQ and its alarm, never to failed reports.
  4. `claim(...)` with `uuid.uuid4().hex` and `_now_s()`:
     - `"finished"` → delete `raw/`, logged as `already_finished`
     - `"leased"` → logged as `lease_held`; `raw/` is left alone, and the message returns for retry (C89, R113, added after the build). Its copy comes back after the 1,080 s visibility timeout: by then the report is final, or the 900 s lease has expired.
     - `"claimed"` → delete `blurred/{id}.jpg` first, before any Meta call (C72). A delete of a missing key succeeds; a failed delete raises, and the message retries before anything is paid.
  5. A switch value other than `off` → finish `failed/model_calls_paused`.
  6. `get_object` on `raw/`:
     - the codes `NoSuchKey` and `AccessDenied` → finish `failed/photo_missing`, logging the error fields
     - any other S3 error raises, and the message retries
     - bytes that don't start with `b"\xff\xd8\xff"` → finish `failed/bad_file`, before `analyse` or any decoder runs (C83, R85). The check stays in the handler: `face_blur.decode_image` and `run_pipeline` keep accepting other formats for the laptop tools.
  7. `analyse(data, client, deadline=_deadline(context))`, with the Lambda `context` passed down from `handler` (C84). A `ModelKeyRejected` (C73) sets `_META_CLIENT` to `None`, logs `model_key_rejected` with `meta_status`, and returns the message. The report stays `processing`, and `raw/` is kept.
  8. Publish:
     - for a level result, first put `blurred/{id}.jpg` (`ContentType: image/jpeg`)
     - then `write_result` with `item_fields()`, plus `photoKey` on a level. False → `lease_lost`: no batch failure, and `raw/` is left alone.
     - then delete `raw/`. A failed delete returns the message.

  "Finish" in steps 5 and 6 means the last two parts of step 8: `write_result` under the claim, then the `raw/` delete. A delete of a missing key succeeds.
- `_error_fields(exc)` gives `{"error": code, "http_status": n}`, or `{"error": class name}` for errors that aren't from AWS.
- One JSON line per report holds `reportId`, `outcome`, `ms` and the pipeline's log fields.
- The handler never reads `/lusot/stop/publish` (C64), and never calls `count_input_tokens`.

- [x] **Step 1: Write the failing tests.** Evidence: tests/test_handler.py rewritten: 36 functions, 53 cases (5 MS1 functions kept, 7 MS1 stub tests deleted, 31 new) (Task 13's report); commit fd04cdb.
  - **Set-up:**
    - MS1's moto fixture, rebuilt on `create_reports_table`, with `PROMPTS_DIR = REPO_PROMPTS`
    - a `FakeClient` on `level_case()` patched in as `handler._meta_client`, except in the key tests
    - `handler._now_s` patched to a fixed clock
    - the fixture clears `_client`, `_prompt` and `_META_CLIENT`
    - "The level case" below means `level_case()`'s photo, SAM results and answer.
  - **Kept from MS1, adapted:**
    - `test_s3_test_event_is_ignored`
    - `test_unknown_key_is_deleted_and_skipped`, also asserting the `unknown_key` outcome
    - `test_report_not_found_is_retried`, now also asserting one `ChangeMessageVisibility` call with `VisibilityTimeout=10` for that message (R92), and that a failing `ChangeMessageVisibility` still returns `RETRY`
    - `test_undecodable_file_marks_bad_file`, now ending `failed/bad_file` through the pipeline, with no Meta call
    - `test_aws_error_is_logged_by_code_and_http_status_only`: the line's keys are `reportId`, `outcome`, `error`, `http_status` and `ms`. It has no `status` key and no `arn:`.
  - **Replaced:** the tests below supersede these MS1 stub tests, which are deleted:
    - `test_stub_marks_failed_pipeline_not_built_and_deletes_raw`
    - `test_duplicate_event_does_not_reprocess`
    - `test_model_calls_stop_switch_marks_paused`
    - `test_failed_delete_is_reported_for_retry`
    - `test_cold_start_checks_key_length_only`: a missing key now retries instead of proceeding (C60)
    - `test_missing_photo_marks_photo_missing`
    - `test_finished_report_is_not_overwritten`
  - **Results:**
    - `test_level_result_is_published`: `done` with the level fields and `photoKey`. The `blurred/` object decodes to 640 × 480, `raw/` is gone, and the fake recorded 7 + 1 calls.
    - `test_non_level_results_store_no_photo`, parametrized over no flood seen, `refused/too_dark` (with `flat_jpeg(10)`), `refused/photo_unusable` and `failed/model_error` (`judge` raises). Each gets exact item fields, no `blurred/` key, and no `raw/` left.
    - `test_deadline_comes_from_the_lambda_context` (C84): a fake context whose `get_remaining_time_in_millis()` returns 100,000 → the fake client records a deadline within 1 s of `time.monotonic() + 70`. With `context=None` it records `None`.
    - `test_publish_switch_is_not_read` (C64): with `/lusot/stop/publish` set to `on`, a level result is still published.
    - `test_stale_photo_is_removed_after_the_claim` (C72), parametrized over no flood seen and `failed/model_calls_paused`: the report is `processing` with `claimedAt = now - 901`, and `blurred/{id}.jpg` already exists. After the delivery, no `blurred/` object is left and the item has no `photoKey`.
    - `test_failed_photo_cleanup_retries_before_paying` (C72): `delete_object` on `blurred/` raises `InternalError` → `RETRY`, status `processing`, `raw/` kept, and no fake calls.
  - **A rejected key (C73):**
    - `test_rejected_key_drops_the_client_and_retries`: the real `_meta_client`, with `handler.MetaClient` replaced by a recorder that returns a `FakeClient` whose `judge` raises `meta_error(401)`. The first delivery → `RETRY`, the status stays `processing`, `raw/` is kept, and one line reads `model_key_rejected` with `meta_status` 401. A second delivery at `now + 1080` re-claims and reads the key from SSM again, so the recorder built two clients.
  - **Before the claim (C60):**
    - `test_ssm_read_failure_retries_before_any_work`: `get_parameter` raises for every SSM read → `RETRY`, no `blur_for_meta` call (patched to raise if called), no fake calls, and the report stays `pending`.
    - `test_unreadable_switch_leaves_the_report_pending`: `get_parameter` raises for the switch only → `RETRY`. The status stays `pending`, with no `claimToken`, `raw/` kept and no fake calls.
    - `test_key_load_failure_is_not_cached`: the real `_meta_client`, with `handler.MetaClient` replaced by a recorder that returns a `FakeClient` on the level case.
      - first delivery: the key read raises → `RETRY`, still `pending`
      - second: the key loads and the report is processed
      - third: no new key read, and the client was built once
      - one `model_key_loaded=true` line, and the fake key's text never appears in `caplog`
    - `test_short_key_is_a_key_fault`: key `"stale"` → `RETRY`, `pending`, and `"stale"` isn't in `caplog`.
    - `test_missing_prompt_is_retried`: `PROMPTS_DIR` is an empty `tmp_path` → `RETRY`, `pending`.
  - **The claim and the lease (G2, B5):**
    - `test_switch_set_ends_model_calls_paused`, parametrized over `on`, `ON` and `Off` → `failed/model_calls_paused`, with `raw/` gone and no Meta call.
    - `test_delivery_after_result_pays_nothing_and_deletes_raw`, parametrized over `done`, `refused`, `failed`: no failures, the item unchanged, `raw/` gone, no calls, `already_finished`.
    - `test_live_lease_is_left_alone`: `processing` with `claimedAt = now - 60` → the message is returned (C89), `raw/` kept, the item unchanged, `lease_held`. Then the holder "crashes": a redelivery at `now + 1080`, after the lease, re-claims and processes with one set of calls.
    - `test_expired_lease_is_reclaimed`: `claimedAt = now - 901` → processed with one set of calls and a new token.
    - `test_racing_deliveries_pay_once`: the fake's first `segment("floodwater")` hook runs `handler.handler(message(), None)` and asserts it returns the message (C89). In all, 7 + 1 calls; the nested delivery's line is `lease_held` (it logs first); the report ends `done` with `raw/` gone. The returned message's redelivery after the result finishes as `already_finished` with no Meta call.
    - `test_lease_lost_at_the_final_write`: the answer gives no flood seen, and the `judge` hook sets the item's `claimToken` to `"other"`. Result: no failures; the item stays `processing` with `"other"` and no result fields; `raw/` is kept; `lease_lost`.
    - `test_failed_raw_delete_retries_without_reanalysis`: `delete_object` fails once → `RETRY` with status `done`. The redelivery deletes and makes no new calls.
    - Review Focus 2, `test_failed_delete_redelivered_after_lease_time_only_deletes`: as above, but the redelivery runs at `now + 1080`. No new calls; the item is unchanged and `raw/` is gone.
    - Review Focus 4, `test_reused_link_during_analysis_pays_once_and_leaves_no_raw`: the `judge` hook puts a new `raw/` object and runs a second delivery, which logs `lease_held` and returns its message (C89). Afterwards there is one set of calls, the first worker's result, and no `raw/` object.
  - **S3 codes (R22, narrowed):**
    - `test_missing_photo_codes`: `NoSuchKey` (no object in moto) and `AccessDenied` (403, patched) → `failed/photo_missing`, with `error` and `http_status` logged and no Meta call.
    - `test_non_jpeg_bytes_end_bad_file_before_decoding` (C83), parametrized over PNG bytes (`cv2.imencode(".png", …)`) and `b"GIF89a…"`: → `failed/bad_file`, `raw/` gone, no fake calls, and `handler.analyse` (patched to raise if called) never runs. A JPEG starting `FF D8 FF` still reaches `analyse`, as the level-case tests show.
    - `test_other_s3_errors_retry`, parametrized over `SignatureDoesNotMatch` 403, `RequestTimeTooSkewed` 403 and `InternalError` 500 → `RETRY`, status `processing`, no Meta call.
    - `test_aws_error_after_meta_calls_retries`: the `blurred/` put raises `InternalError` → `RETRY`, status `processing`, no `blurred/` object, `raw/` kept.
  - **Logs (§3.6, C62):**
    - `test_sentinel_ip_never_reaches_a_log`: an S3 event carrying `sourceIPAddress: "203.0.113.7"` and a `principalId` goes through the level, refusal (`too_dark`), Meta-error and malformed-key paths. Neither value appears in `caplog.text`.
    - `test_one_log_line_per_report_with_its_fields`: the level case writes exactly one line with the `reportId`. Its keys include `outcome` (`done/level`), `ms`, `meta_calls`, `sam_ms`, `spark_ms`, `instances`, `models`, `prompt_version`, `blur_version`, `face_boxes`, `drops` and `deciding`.
    - `test_logs_never_carry_private_data`: in the level case, `caplog.text` contains none of `wdw515`, `14.6095`, `120.9894`, the fake key, `REASON-MARKER-31` or `arn:`.
    - `test_lambda_never_counts_tokens`: the level case passes, and the fake's `count_input_tokens` (which raises) was never called.
  - **B3:**
    - `test_b3_replay_through_runner_and_handler_match`: the runner's `live()` records a level run with a `FakeClient`. Then `replay(photo, run_dir).outcome == analyse(data, SavedOutputsClient(run_dir, data)).outcome`, and both equal the live outcome.
    - `test_b3_on_a_real_saved_run`: skipped unless `LUSOT_B3_RUN_DIR` and `LUSOT_B3_PHOTO` are set. It runs the same equality on that run (Task 16).
- [x] **Step 2:** Run `uv run pytest -q tests/test_handler.py`. Expected: FAIL. Evidence: `uv run --frozen pytest -q tests/test_handler.py` against MS1's stub → RED: 1 skipped, 52 errors (for example AttributeError: no attribute '_prompt') (Task 13's report).
- [x] **Step 3:** Rewrite `handler.py` in that order. Keep MS1's structure: module-level `_client` cache, `_log`, `_handle_object`, the batch-failure loop. Rename the error field `status` to `http_status`. Evidence: handler.py rewritten in the spec's order, with R85 (non-JPEG ends bad_file), R92 (visibility change) and R93 (AccessDenied kept in the missing-photo rule); `pytest -q tests/test_handler.py` → 52 passed, 1 skipped; 59 of 59 mutants killed; C89 (R113) then made a live lease return its message (334d012, 5fe9a52), 62 of 62 mutants (Task 13's report and SDD ledger).
- [x] **Step 4:** Run `uv run pytest -q`, then `uv run ruff check .`. Expected: PASS; clean. Evidence: `uv run pytest -q` → 518 passed, 1 skipped (the B3 real run waits for Task 16); `uv run ruff check .` → All checks passed; `ruff format --check` flagged only the controller's earlier baa69a0 line, fixed in 4c0e4b8 (Task 13's report and SDD ledger).
- [x] **Step 5:** Commit `feat(analysis): replace the MS1 stub with the landmark pipeline under a claim`. Evidence: commit fd04cdb (12:36 AM); review clean, no fix round (SDD ledger); follow-up commits 334d012 and 5fe9a52 (C89).

### Task 14: Container image and analysis role

**Files:**
- Modify: `backend/template.yaml` (`AnalysisRole`), `backend/analysis/Dockerfile`, `backend/analysis/.dockerignore`, `backend/analysis/requirements.lock.txt` (regenerated)
- Test: the commands in Steps 1, 4 and 5

**Interfaces:**
- Consumes: `PROMPTS_DIR` (Task 13), `prompts/` (MS1 Task 5), `jsonschema` (Task 3)
- Produces:
  - an image that holds the prompts at `${LAMBDA_TASK_ROOT}/prompts`, with `PROMPTS_DIR` set, and every locked package hash-checked in the task root
  - a role with `s3:PutObject` and `s3:DeleteObject` on `blurred/*` (C72), and `s3:ListBucket` limited to `raw/`

- [x] **Step 1:** Change the dead-letter queue's comment (R49's wording, comment only) to "7 days, not the MS1 plan's first 14 days". Then add two statements to `AnalysisRole`: Evidence: template.yaml (dead-letter comment and two AnalysisRole statements, commit 942c92e); `sam validate --lint --profile lusot --region ap-southeast-1` → valid, exit 0 (SAM CLI 1.170.0); the grep for ReservedConcurrentExecutions or a wildcard Resource found nothing; `grep -c "AnalysisRole" template.yaml` → 2 (Task 14's report).
  - `s3:PutObject` and `s3:DeleteObject` on `!Sub "${UploadBucket.Arn}/blurred/*"`
  - `s3:ListBucket` on `!GetAtt UploadBucket.Arn`, with `Condition: {StringLike: {"s3:prefix": "raw/*"}}`. Comment it: the grant makes a missing raw photo read as 404 `NoSuchKey`. AWS doesn't document whether a prefix-limited grant counts, so the handler keeps `AccessDenied` in the missing-photo rule, and Task 16 records which code comes back (§3.6).

  Run `sam validate --lint --profile lusot --region ap-southeast-1` from `backend`. Expected: valid. Also from `backend`, `grep -n "ReservedConcurrentExecutions\|Resource: \"\*\"" template.yaml` finds nothing, and `grep -c "AnalysisRole" template.yaml` prints a number above 0, which proves the grep read the file.
- [x] **Step 2:** Regenerate the lock: `uv export --no-dev --no-emit-project --format requirements-txt -o requirements.lock.txt`. Expected: `grep -c "^jsonschema==" requirements.lock.txt` prints 1, and every package line has a `--hash=sha256:`. Evidence: `uv export --no-dev --no-emit-project --format requirements-txt -o requirements.lock.txt` → byte-identical to the committed lock (Task 3 had already locked jsonschema); `grep -c "^jsonschema==" requirements.lock.txt` → 1; all 32 package entries carry a --hash=sha256: (Task 14's report).
- [x] **Step 3:** Change the Dockerfile: Evidence: Dockerfile now has `pip install --require-hashes --target` and ENV PROMPTS_DIR; COPY prompts and .dockerignore's !prompts were already there (Task 14's report); commit 942c92e.
  - `RUN pip install --no-cache-dir --require-hashes --target ${LAMBDA_TASK_ROOT} -r ${LAMBDA_TASK_ROOT}/requirements.lock.txt`. `--target` makes pip ignore the base image's copies, so it checks the hash of every locked package, `six`, `python-dateutil` and `urllib3` included. Lambda puts the task root first on `sys.path`. Comment it so.
  - `COPY prompts ${LAMBDA_TASK_ROOT}/prompts` and `ENV PROMPTS_DIR=${LAMBDA_TASK_ROOT}/prompts`
  - `.dockerignore` gains `!prompts`
- [x] **Step 4:** Make sure no Gradle build is running, and post `DOCKER/DEPLOY RUNNING <time>` in `ms3a.md` first (the tracker then pauses Windows 2 and 4; `DOCKER/DEPLOY DONE <time>` after Step 5). Then run `docker build -t lusot-analysis:ms3a backend/analysis` from the repo root. Expected: success. Evidence: controller (R112): `docker build -t lusot-analysis:ms3a backend/analysis` → exit 0 in 29 s; no Gradle build running; DOCKER RUNNING and DOCKER DONE posted at 1:42 AM (SDD ledger).
- [x] **Step 5:** Check the built image: Evidence: controller ran the three checks with `--network none`: prompts → `muse_spark_photo_v1 True False`; the /var/task check → `True`; handler import → `ok` (SDD ledger).
  - `docker run --rm --entrypoint python lusot-analysis:ms3a -c "import os, pathlib; from lusot_analysis.prompts import load_prompt; p = load_prompt(pathlib.Path(os.environ['PROMPTS_DIR'])); print(p.version, bool(p.text), p.schema['additionalProperties'])"` → `<PROMPT_VERSION> True False`
  - `docker run --rm --entrypoint python lusot-analysis:ms3a -c "import boto3, dateutil, six, urllib3, jsonschema, numpy, cv2; print(all(m.__file__.startswith('/var/task/') for m in (boto3, dateutil, six, urllib3, jsonschema, numpy, cv2)))"` → `True`
  - `docker run --rm --entrypoint python lusot-analysis:ms3a -c "import lusot_analysis.handler; print('ok')"` → `ok`
- [x] **Step 6:** Run `uv run pytest -q` from `backend/analysis`. Expected: PASS, since no code changed. Evidence: `uv run pytest -q` from backend/analysis → 518 passed, 1 skipped; `uv run ruff check .` → All checks passed (Task 14's report).
- [x] **Step 7:** Commit `build(analysis): ship the prompts, hash-check every package and widen the role for MS3a`. Evidence: commit 942c92e (1:10 AM); review clean, no fix round (SDD ledger).

### Task 15: Smoke script for the MS3a cloud checks

**Files:**
- Modify: `backend/scripts/smoke_upload.py`. Its `.lock` changes only if its dependencies change, and they shouldn't.
- Test: `backend/scripts/test_smoke_upload.py`

**Interfaces:**
- Consumes:
  - the stack outputs `ApiUrl`, `BucketName` and `QueueName`
  - Task 10's body
  - Task 13's log fields: `outcome`, `meta_calls`, `error`, `http_status`
  - C87's photo folder `%LUSOT_DATA_DIR%\set_c\commons-ph-floods\`: `metro_manila_41.txt` (lines of `full path<TAB>licence`, `#` lines are comments) for eligibility, and `attribution.csv` (columns `file_name`, `title`, `commons_page_url`, `author`, `licence`, `licence_url`, `credit_line`, `fetch_mode`, `flags`) for each photo's credit line (R102)
- Produces: `uv run backend/scripts/smoke_upload.py [--fallback]`. Exit 0 when every check passed, 1 when a check failed, and 3 when no B1 photo gave a level, so C71 applies.
  - `seeded_photo_order(folder: Path) -> list[Path]` follows C87 and R102: the base names listed in `folder/metro_manila_41.txt`, sorted, then the full order `random.Random(20261028).sample(names, n)`, fixed in advance whatever `attribution.csv` holds. Positions 0 to 4 are B1's photos, and 5 to 19 are C71's fallback. A listed file missing from disk raises `CheckFailed`. Nothing reads MS1's STURM `summary.json` any more.
    - As built (R116): the photos sit in `folder/images/`. Each is opened at `folder / "images" / <base name>`, and the listed full path gives only the name, so it returns `images/<name>` paths. A photo placed directly in the folder counts as missing.
  - `credited(folder: Path, photos: Sequence[Path]) -> tuple[list[Path], int]`: keeps, in order, the photos whose row in `attribution.csv` has a non-empty `credit_line`, and returns how many were skipped. Only kept photos are sent to Meta, and the run prints the skipped count (R102).
  - `refuse_sealed(path: Path) -> None`, with the runner's rule
  - `as_app_jpeg(path: Path) -> bytes`: decode, shrink to at most 1,600 px with `INTER_AREA`, then encode as JPEG at quality 85, as the app sends it
  - `dark_jpeg() -> bytes`: 1600 × 1200, a horizontal grey gradient from 0 to 30
  - `wait_final(http, api_url, report_id, *, since: float, bound_s: float = 120.0, clock=time.monotonic, sleep=time.sleep) -> dict` polls every 2 s through `pending`, `processing` and 404. It raises `CheckFailed` after `bound_s` (C68).
  - `check_report_body(body: dict) -> None` checks C67's shapes
  - `check_form_fresh(issued_s: float, now_s: float) -> None` raises `CheckFailed("reused link: form too old")` when more than 280 s have passed since `POST /uploads` returned the form (C27's 300 s, less a margin)
  - `log_lines(session, report_id: str, since_ms: int) -> list[dict]` returns the analysis log's JSON lines for one report: the text from the first `{` of each event. It waits up to 30 s and never prints them.
    - As built: `log_lines(stack, report_id, *, until=None, clock=None, sleep=None)`. The log group is looked up once and kept in `Stack.log_group`. `until` waits for a given outcome, such as B5's `already_finished`. `wait_final`'s `clock` and `sleep` also default to `None` and resolve to `time.monotonic` and `time.sleep` at each call.
  - As built, also: CI runs these tests, because `check:py`'s scripts part installs httpx, numpy and opencv (R115). The run's 18 failure branches each have a test.
  - the HTTP client is `httpx.Client(timeout=30, transport=httpx.HTTPTransport(local_address="0.0.0.0"))`. That forces IPv4, which matters because IPv6 doesn't connect on this Wi-Fi (Oct 28 log). httpx 0.28.1 documents `local_address`.
- **The B1 run's checks, in order** (keep MS1's preflight, PNG, key-loaded and stop-switch checks):
  1. the CORS preflight
  2. Upload B1's 5 photos and the dark JPEG. The dark one goes from the app origin, with MS1's allow-origin checks. Each report must be final within 120 s of its 204.
  3. **The reused link (B5), run as soon as the first B1 report is final** and its log line shows `meta_calls` above 0, before the next upload. The upload form expires 300 s after `POST /uploads` (C27), and the whole run takes longer. Re-post that report's form with the same bytes; if the form is older than 280 s, fail with `reused link: form too old`. S3 returns 204; `raw/` is gone within 60 s; the log has an `already_finished` line, and exactly one line with `meta_calls` above 0.
  4. The dark JPEG is `refused/too_dark`, and its log line has `meta_calls` 0.
  5. Every body passes `check_report_body`. If no B1 report has a level, print the outcomes and carry on. The run then ends with exit 3 instead of 0, so the B4 and B5 checks still run.
  6. No `raw/` object is left for any report (head gives 404). `blurred/{id}.jpg` exists for each level report, and for no other (B4).
  7. **The missing photo (§3.6):**
     - create a report with `POST /uploads`, and upload no photo
     - send the queue one S3-shaped notification for `raw/{id}.jpg`, through `get_queue_url` on `QueueName`. The URL is never printed.
     - expect `failed/photo_missing` within 60 s
     - print the line's `error` and `http_status`
  8. MS1's PNG refusal, key-loaded and stop-switch checks
- `--fallback` (C71) uploads positions 5 to 19 of C87's order one at a time and stops at the first level. It runs checks 2, 5 and 6 on them, and prints how many it sent.
- The output is counts and timings only: each report's outcome or level, and its seconds to a final status. Everything prints through the masking `say()`.

- [x] **Step 1: Write the failing tests.** They use only fakes: `httpx.MockTransport`, `tmp_path` trees and no AWS. Evidence: backend/scripts/test_smoke_upload.py, fakes only (httpx.MockTransport, tmp_path trees, in-memory AWS clients) (Task 15's report); the fix round (62e999a, R116) added the 18-case failure table and built the `images/<name>` layout.
  - `test_seeded_order_follows_c87`: a `tmp_path` folder with a `metro_manila_41.txt` of 30 lines (a comment line first) and one empty file per line:
    - the order equals `random.Random(20261028).sample(sorted(names), 30)` over the listed base names, and its first 20 equal `random.Random(20261028).sample(sorted(names), 20)` (the prefix property R102 relies on)
    - a listed file missing from the folder → `CheckFailed`
  - `test_only_credited_photos_are_sent` (R102): an `attribution.csv` with credit lines for some listed photos, an empty credit line for one and no row for another → `credited` keeps the credited ones in order and reports 2 skipped.
  - `test_photos_are_sent_as_the_app_sends_them`: a 4000 × 3000 PNG → bytes that start with `FF D8` and decode to 1600 × 1200.
  - `test_dark_jpeg_is_below_the_brightness_cutoff`: it decodes to 1600 × 1200 with a mean grey under 40.
  - `test_wait_final_polls_through_processing`: replies of `pending`, `processing`, 404 and then `done` → `done`. A fake clock that passes 121 s while `processing` → `CheckFailed`.
  - `test_report_body_shapes` (C67): a level body, a no-flood body and a refused body pass. A body with `photoKey`, `lat` or `claimToken` fails, and so does a level body without `levelIsFloor`.
  - `test_reused_link_needs_a_fresh_form`: 280 s after issue passes; 280.1 s raises `CheckFailed` with `reused link: form too old`.
  - `test_log_lines_parse_the_lambda_text_format`: the event `"[INFO]\t2026-10-29T01:02:03.000Z\treq-1\t{\"reportId\": \"r_...\", \"meta_calls\": 0}\n"` parses, and a line that isn't JSON is skipped.
  - `test_sealed_paths_are_refused`.
  - The run's summary counts `meta_status` 504 and 413 for SAM and `judge`, and takes cost from billed usage only (never from token counts).
- [x] **Step 2:** Run `uv run --with pytest --with "boto3[crt]" --with httpx --with numpy --with "opencv-python-headless<5" pytest -q backend/scripts/test_smoke_upload.py` from the repo root (R5's pattern). Expected: FAIL. Evidence: the Step 2 command on MS1's script → RED: 16 failed; in the fix round, the new tests on ac07fc1's script: 30 failed, 7 passed (Task 15's report).
- [x] **Step 3:** Implement the script changes as specified. Evidence: smoke_upload.py extended (B1 flow, B4's stored-photo check, B5, C71's --fallback, the spend line); R116: each photo is opened at folder/images/<base name>; R115: check:py's scripts part adds httpx, numpy and opencv-python-headless so CI runs these tests (package.json) (Task 15's report); commits ac07fc1 and 62e999a.
- [x] **Step 4:** Run the Step 2 command, and `uv run --with pytest --with boto3 pytest -q backend/scripts/test_put_model_key.py backend/scripts/test_apply_ecr_lifecycle.py`. Expected: PASS. Evidence: the Step 2 command → 37 passed; `uv run --with pytest --with boto3 pytest -q backend/scripts/test_put_model_key.py backend/scripts/test_apply_ecr_lifecycle.py` → 18 passed; `npm run check:py` → exit 0 (analysis 518 passed, 1 skipped; scripts 65 passed); 37 of 37 new mutants and the first round's 50 killed (Task 15's report).
- [x] **Step 5:** Commit `test(backend): extend the smoke run to the MS3a cloud checks`. Evidence: commit ac07fc1 (3:08 AM), then fix 62e999a (3:57 AM); review clean after 1 fix round (SDD ledger).

### Task 16: Deploy and the cloud check (spends Meta credits)

**Files:** none expected. A fix found here gets its own commit, after `superpowers:systematic-debugging`.

**Interfaces:**
- Consumes: Tasks 10 to 15
- Produces: the deployed MS3a stack, and the evidence for B1, B3 (real data), B4 and B5 in the task report, as counts and timings only

- [x] **Step 1:** Check the preconditions, then post two lines in `ms3a.md`:
  - Evidence (Oct 29, 9:47 PM): the heads-up and `DEPLOY RUNNING 9:47 PM` were posted in `ms3a.md` and sent to the tracker. A6 had passed (M14, Oct 28). There was no java or Gradle process, 4.3 GB was free, the tree was clean, and the `ends_with(Arn, 'user/rene-dev')` check printed `true`. Docker Desktop started with engine 29.9.2. `DEPLOY DONE` was posted at 9:58 PM. A second, short deploy for R93 (RUNNING 10:12 PM, DONE 10:16 PM) followed the same checks.
  - **A heads-up:** after this deploy, a photo from MS1's APK goes through SAM and Muse Spark, its final text changes, and the smoke run turns uploads off for about a minute. Check whether Rene has done the phone test (A6, M14); if not, note it under "Waiting on Rene".
  - `DOCKER/DEPLOY RUNNING <time>` before Step 2, and `DOCKER/DEPLOY DONE <time>` after the last smoke run.
  - Expect exit 3 and C71's fallback (C75). The worst case is about $0.67, plus about $0.16 per re-run of the 6 photos.
  - Docker is running, and no Gradle build is
  - `git status` is clean
  - `aws sts get-caller-identity --profile lusot --region ap-southeast-1 --no-cli-pager | sed -E 's/[0-9]{12}/<account>/g'` answers. Rene's `aws login` lasts 12 hours.
- [x] **Step 2:** From PowerShell, with PATH refreshed: `npm run deploy`. Expected: `Successfully created/updated stack - lusot`, then `lifecycle: keep 3`. If the first deploy fails on IAM propagation, re-run it once before changing anything.
  - Evidence:
    - **Image check first,** as CLAUDE.md asks: `sam build --parallel` exited 0. The image `analysisfunction:ms1`, run with `--network none`, imports the handler and the Meta client, holds C90's code, and has both prompt files in `/var/task/prompts`.
    - **First deploy (9:51 PM):** exit 0 in 131 s, `Successfully created/updated stack - lusot`, then `lifecycle: keep 3`.
    - **R93's redeploy (10:15 PM):** exit 0 in 93 s. Its image's missing-photo codes read `['NoSuchKey']`.
- [x] **Step 3:** Run `uv run backend/scripts/smoke_upload.py`. Expected: `SMOKE OK`. Record:
  - Evidence (9:57 PM): **`SMOKE OK in 353.6 s`**, exit 0.
    - **B1:** 2 levels (below gutter, PATV), 1 no flood seen, and 2 refused (`photo_unusable`, `no_usable_reference`). Upload to final took 27.0, 35.6, 41.8, 43.5 and 63.2 s.
    - **Dark JPEG:** `refused/too_dark` with 0 Meta calls.
    - **Reused link:** 204, the raw photo gone in 2.4 s, and `already_finished` with no Meta call.
    - **B4:** no raw photo left for 6 reports, and a blurred photo only for the 2 levels.
    - **Missing photo:** `failed/photo_missing` in 2.1 s, **`NoSuchKey` (404)**. So the R93 follow-up ran (`d32ddf6`, with its delta review's notes in `5262f5d`): `AccessDenied` retries now, `test_missing_photo_codes` became `test_missing_photo_code` plus an `AccessDenied` case in `test_other_s3_errors_retry`, and spec §3.1 step 6, its error and outcome tables, §3.6 and both comments cite MS3a Task 16. After the redeploy, the same check gave `NoSuchKey` again (10:15 PM, no Meta call).
    - **Spot and bound:** the test spot and the 120 s bound were unchanged (R118, R119).
  - each report's outcome and seconds to a final status
  - the dark JPEG's `meta_calls 0`
  - the reused-link result
  - the missing-photo code. If it is `NoSuchKey` (404) under the prefix-limited `s3:ListBucket` grant, remove `AccessDenied` from the missing-photo rule in a follow-up commit, so a real 403 retries into the dead-letter queue and its alarm instead of marking every report `photo_missing` (R93, from MS1's final review). Update `test_missing_photo_codes` and spec §3.1 step 6 to match.
    - If it is `AccessDenied` (403), the prefix-limited grant buys nothing. Delete the `s3:ListBucket` statement and keep `AccessDenied` in the rule (Task 14's review, Minor 2).
    - Either way, update the two comments that point to this run, the ListBucket statement's in `template.yaml` and the missing-photo rule's in `handler.py`. Cite the recorded result as "MS3a Task 16" (Task 14's review, Minor 3).
  - **The test spot stays where it is** (R118, from the tracker's cross-spec audit, row 4). MS3a publishes nothing, so the smoke script's `SPOT`, the plan §12 example in Manila, is left alone here. MS4 moves it outside Metro Manila in the same change that turns publishing on (its C513), so the spot moves once.
  - **The bound stays 120 s here** (R119, audit row 22). It is B1's recorded figure (C68). Runs after MS3b adds geometry use at least 180 s, since a run may stop as late as about 150 s (C84, C88).
    - The MS3a image builds as `analysisfunction:ms1`, because the template's `DockerTag` is `ms1`. CLAUDE.md's pre-deploy image check uses that tag.
  - the B4 checks

  Exit 1 → debug, fix, re-run. A re-run sends the same 6 photos again: it adds cost, not new photos. Exit 3 → Step 4.
- [x] **Step 4: C71's fallback** (only after exit 3):
  - Evidence: not needed. Step 3 exited 0 with 2 levels, so no fallback photo was sent.
  1. **The diagnosis, with no Meta call (C75):** read B1's 5 photos' log lines from Step 3, and record each photo's outcome and drop causes as counts. This shows why the 5 gave no level. Nothing is replayed.
  2. Run `uv run backend/scripts/smoke_upload.py --fallback`. It sends up to 15 more photos, positions 5 to 19 of C87's order, and stops at the first level.
  3. If there is still no level, B1 is partly met, with the drop causes as the reason. 3a then closes on B2 to B5 and the other cloud checks, and the cloud proof of a level moves to the first Manila photos. Record that for Task 17.
- [x] **Step 5 (Claude; one photo, about $0.01):** check B3 on real data.
  - Run `$env:MODEL_API_KEY = [Environment]::GetEnvironmentVariable('MODEL_API_KEY','User'); uv run --directory backend/analysis probes/run_pipeline.py live "<the first photo in C87's order>"`. Expected: exit 0, and a run directory under `%LUSOT_DATA_DIR%\runs\`.
  - Then run `$env:LUSOT_B3_RUN_DIR = '<run dir>'; $env:LUSOT_B3_PHOTO = '<the photo>'; uv run --directory backend/analysis pytest -q tests/test_handler.py -k b3`. Expected: 2 passed, 0 skipped.
  - Evidence (Oct 29, run before the deploy under R121, as it needs no AWS):
    - **First run (9:00 PM):** `failed/model_error`, with `meta_status` null. SAM sent a water mask over 1024 px wide scaled to a 1024 px side, and the client refused it. Fixed by C90 (`044fdad`, `14ad29b`, reviewed).
    - **Re-run on `044fdad` (9:19 PM):** exit 0, `refused/photo_unusable`, 6 Meta calls in 18 s. The `-k b3` command on that run gave **2 passed, 0 skipped**.
    - **Cost:** the two runs plus one diagnostic SAM call came to about $0.037, against the step's $0.01 estimate. The estimate predates C87's 1600 px photos and Muse Spark's measured cost.
- [x] **Step 6:** Add up the spend: the Meta calls made (8 per cloud photo that reached SAM, plus 6 for Step 5), and the estimated cost from the token counts in the log lines. Record it.
  - Evidence: **52 Meta calls, about $0.19 in all,** within the plan's worst case of about $0.67 ([results note](../../research/2026-10-29-ms3a-results.md) §7).
    - **Smoke run:** 40 calls (SAM 35, Muse Spark 5), billed 12,747 input and 12,621 output tokens, about $0.157.
    - **Step 5:** two runs plus one diagnostic SAM call, 12 calls (SAM 11, Muse Spark 1), about $0.037.
    - No call ended on a 504 or a 413.
  - A failed run's spend line is a lower bound. It counts only photos whose reports finished, so add up to 8 calls for each photo that timed out, or read that report's lines in CloudWatch (Task 15's re-review).

### Task 17: Results note and milestone close (Claude)

**Files:**
- Create: `docs/research/2026-10-29-ms3a-results.md`
- Modify: the spec's §2 table, this plan's boxes, `docs/PROGRESS.md`, and `docs/log/2026-10-29.md` (create it if it doesn't exist yet)

- [x] **Step 1:** Write the results note, with counts and timings only:
  - Evidence: [`docs/research/2026-10-29-ms3a-results.md`](../../research/2026-10-29-ms3a-results.md) covers C90's bug, B1 to B5, the missing-photo code, spend, P2 to P6 and what stays open. It holds counts and timings only, with no image, photo name, path, key or account ID (the plan-leak and account-ID scans are clean).
  - **B1:**
    - reports by outcome: how many of B1's 5 Commons photos gave a level, refusals by reason, and failures
    - the photos' licences as counts (CC BY, public domain), with a pointer to the attribution kept beside them; no photo name or path
    - seconds from upload to a final status, as p50 and max
    - the dark JPEG refused with 0 Meta calls
    - the C67 fields checked
    - C71, if it ran: photos sent and outcome counts
  - **B3:** the synthetic replay test and the real-run replay
  - **B4:** `blurred/` holds photos only for level results, and no `raw/` object is left, as counts
  - **B5:** the unit tests, and the reused link: no Meta call, and the raw object deleted
  - the missing-photo code, for §3.6
  - Meta calls, tokens and the estimated cost
  - what the run shows for P2, P3, P4 and P6, and what stays open

  It holds no images, photo names or paths, key, or account ID. It links to the MS1 probe note for the dataset and its attribution.
- [x] **Step 2:** Tick the spec's done-checks: add a column "Result (Oct 29)" to spec §2, with ✅ or "partly met" and the evidence line for each of B1 to B5.
  - Evidence: spec §2 has the column, with ✅ and an evidence line for each of B1 to B5. None is partly met: B1 got 2 levels without C71's fallback.
- [x] **Step 3:** Tick this plan's boxes with their evidence. Update `docs/PROGRESS.md` (the MS3a row) and the day's log, including every ruling made during execution.
  - Evidence:
    - Tasks 1 to 16 are ticked (f28be11 for Tasks 1 to 15 and 7a; this commit for Task 16). Task 7a Step 5, the optional latency pre-test, stays unticked: it was skipped, and MS3b's C312 measures the effort instead.
    - `docs/PROGRESS.md`'s MS3 row and W25 are updated.
    - The rulings are recorded:
      - R80 to R119 are listed by range in the [Oct 28 log](../../log/2026-10-28.md). Each one's reason and its cost if wrong are in Window 3's SDD ledger.
      - R120, R121, R122, C90 and R93's application are in the [Oct 29 log](../../log/2026-10-29.md).
- [x] **Step 4:** Run the checks. Expected: all clean.
  - Evidence (Oct 29, 10:18 to 10:21 PM, at 5262f5d plus this commit's docs):
    - `npm run check` exited 0 in 88 s: app 40, API 41, Node scripts 14, analysis 535 passed with 1 skipped (B3's real-run test, which runs only with a saved run), and `backend/scripts` 65.
    - gitleaks found no leaks. The plan-leak check was clean over 193 files, and the 12-digit account-ID scan, which skips lockfiles, was clean over 158.
    - **Whole-word "safe"** over the 61 files that differ from `main`, plus the results note: every hit is a rule banning the word, the CSS class `safe-area`, or Python's `quote_plus(safe="/")`. None is about flood conditions.
    - **Strict form:** the extra substring hits are all "safety line", the required disclaimer, or the banned-word test, and each was judged.
  - `npm run check`
  - the 12-digit grep, skipping lockfiles (R15)
  - `python scripts/check_no_plan_leak.py`
  - `git diff --name-only main | xargs grep -n -i -w "safe"`: nothing about flood conditions
  - once, the strict form: `git diff --name-only main | xargs grep -n -i "safe"` (any substring, such as "unsafe" or "safety"), with each hit judged and recorded
- [x] **Step 5:** Run the `security-review` skill on the branch, because it changes the role and the upload path. Then run `superpowers:requesting-code-review` on the whole branch, on Opus 5.5 at `xhigh` (D18, as amended Oct 29), and give the reviewer every held note: the ledger's deferred minors and parked findings. Fix anything confirmed, and re-run Step 4. Record what is left, each with its milestone, in the committed log.
  - Evidence:
    - **Security review:** the `security-review` skill ran on `origin/main...HEAD` at 5:57 AM, Oct 29, and found nothing at or above confidence 7. For the delta after it (C90 and R93), the final review carried the security lens instead (R123, in the Oct 29 log).
    - **Whole-branch reviews:** R120's (Opus 5.5 at max, 6:29 AM) found no Critical or Important issue, and its M1 to M11 are in the Oct 28 log. The final one (Opus 5.5 at `xhigh`, on `98e8266..bda9ff5`, 10:40 PM) found no Critical issue and no code defect.
    - **The final review's fixes, applied in the close commit:**
      - **Important:** the slow photo was misattributed to the face blur. SAM's double mask decoding is the leading candidate, and it went to MS4.
      - **Minor:** `_upscaled`'s docstring now says one index off either way.
      - **Minor:** R123 is in the log with its premise corrected, and the parser's claimed-size allocation went to MS7.
      - **Minor:** M10 and M11 moved to MS4.
      - **Minor:** the board's stamp.
    - **Left open, each with its milestone:** the Oct 29 log's deferred table.
    - **Step 4 re-run after the fixes:** `npm run check` exit 0.
- [x] **Step 5b:** Run `claude-md-management:revise-claude-md`, for Rene to approve. Propose, among this session's notes: (a) a deploy may set a stop switch that was flipped from the CLI back to `off`, so re-check every switch after a deploy during an incident; (b) in the dead-letter line, redrive only messages under a day old and purge older ones, since their photo is gone and a redrive restarts the IP address's 7-day clock.
  - Evidence: the skill ran (10:23 PM, Oct 29). Seven proposals are in the Oct 29 log under "Waiting on Rene":
    - (a) and (b) above
    - the sealed deny rules' real paths
    - the smoke test's cost, time and background run
    - the account-ID scan before each commit
    - `boto3[crt]` for Python AWS tools
    - C90's 1600 px testing note

    None is applied until Rene approves.
- [ ] **Step 6:** Commit `docs: record MS3a results and tick its done-checks`. Then use `superpowers:finishing-a-development-branch`: merge `ms3a-landmark-core` into `main` and push to the private repo (D16).
