# MS6 Evaluation Harness Implementation Plan

> **Draft: written before Rene approved the spec (D7). The executing controller reviews it before Task 1.**

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A standard-library harness that scores saved evaluation results by `eval/rules.md`, decides the release gate, writes a deterministic report with its charts, and rebuilds that report with the one command `python eval/run_eval.py --from-saved`.

**Architecture:**
- **`eval/scoring/`** is a package of small standard-library modules: the level scale, the label mapping, the row loader with its allow-list, the exclusions, the metrics, the gate, the charts and the report. Each module is pure: it takes rows or scores and returns values.
- **`eval/run_eval.py`** is the only entry point. It refuses sealed paths, loads a results folder (and its `rerun/` folder if one exists), builds every report file in memory, and either compares them with the committed copies or writes them.
- **`eval/tests/`** holds pytest tests on synthetic rows, run through a locked PEP 723 runner, plus one synthetic results folder in `eval/tests/fixtures/` that the command tests rebuild byte for byte.
- No code imports `lusot_analysis`, and nothing in MS3 imports `eval/`. They meet through the spec's §4.3 files (C400).

**Tech Stack:** the Python 3.9+ standard library for the report path (`json`, `decimal`, `fractions`, `dataclasses`, `pathlib`, `argparse`, `xml.sax.saxutils`); pytest 9.1.1 (the version `backend/analysis` locks) and scikit-learn 1.9.1, for the tests only, through uv 0.13.6. Script locking (`uv lock --script`, `uv run --locked --script`) was checked with Context7 and a local run on Oct 28. The dataviz skill's palette validator runs once (Node 22) for the chart colours.

**Spec:** `docs/superpowers/specs/2026-10-28-ms6-evaluation-design.md`. It is binding. Executors read both documents.

**Branch and order.** Branch `w4-independent` in `C:\Systems\Lusot\lusot-wt\w4`, on top of `ms1-setup` at `a724abf`. Tasks run in order, one at a time (R1). Every file is new, and no existing file changes.

## Global Constraints

- **The report path is standard library only.** `eval/run_eval.py` and every module in `eval/scoring/` import only the standard library and `scoring` itself. They read no environment variable (no `os.environ`, no `os.getenv`), open no socket, call no model, and never import `lusot_analysis`.
- **Python 3.9 or newer** for the report path.
  - Each file starts with `from __future__ import annotations`, and every file must parse with `ast.parse(source, feature_version=(3, 9))`.
  - **Grammar to avoid:** `match`, parenthesised context managers.
  - **Library calls to avoid:** `zip(strict=...)`, `dataclass(slots=..., kw_only=...)`, `itertools.pairwise`, `int.bit_count`, `tomllib`, `datetime.UTC`, `typing.TypeAlias`.
  - **`X | Y` outside annotations,** such as `isinstance(x, int | str)`, parses as 3.9 grammar but fails on 3.9 at run time. Use a tuple.
  - **Formatting a `Fraction`** with a format spec (`f"{x:.1f}"`) works only from 3.12. Convert to `Decimal` first.
- **Small rules for every module:**
  - Patterns use `re.fullmatch`, and `[0-9]` instead of `\d`, which also matches non-ASCII digits.
  - Every text file is opened with `encoding="utf-8"`, because `eval/rules.md` holds `≤`, `≥` and `§`, and Windows defaults to cp1252.
  - A `RowError` message names the file, the line and the rule broken, and never repeats the offending value. Sealed rows pass through this loader, and printed output stays ASCII.
- **Tests** live only in `eval/tests/` and run from the repo root with `uv run --locked --script eval/tests/run_tests.py` (Python 3.13 through uv). One test process at a time. Tests write only under pytest's `tmp_path`.
- **Paths:** the harness reads only the folder it is given, or `eval/results/` beside `run_eval.py`. It refuses any path with a part named `sealed`, in any case, before anything is read or listed (C411). It never defaults to `LUSOT_DATA_DIR`.
- **Data:** synthetic fixtures only. Never read, list or search `C:\Systems\Lusot\lusot-data\`, anything under `set_a\` or `a_neg\`, or any folder named `sealed`. No Meta or AWS call, and no claude-in-chrome. No fixture contains a run of 12 digits.
- **Exact values (the spec, and `eval/rules.md` v0.6):**
  - **Levels,** in order: `below_gutter`, `gutter`, `half_knee`, `half_tire`, `knee`, `tire`, `waist`, `chest`, `above_chest`. Their upper limits are 5, 8, 10, 13, 19, 26, 37 and 45 in, and `above_chest` is anything deeper. The classes are PATV for the first three, NPLV for `half_tire` and `knee`, and NPATV for the rest.
  - **"No flood seen"** scores at index −1, and as `below_gutter` (index 0) in kappa (C405).
  - **Labels:** centimetres convert at 2.54 per inch, and a range takes its upper value. The marker for a label with other words is `(other words)` (C420).
  - **Gate:**
    - a median error of at most 3 in, at least 70% of wheels measured, and envelope coverage of at least 80%
    - no rise in Set A underestimation, meaning neither the rate nor the number of underestimated photos rises (MS6E-Q5's default)
    - coverage falls by at most 10 percentage points, and passability agreement by at most 5
    - every boundary passes (C406)
  - **Ids:** `^[A-Z]{1,3}[0-9]{1,4}(-[0-9]{1,3}){0,2}$`. Numbers carry at most 4 decimal places.
  - `RULES_VERSION = "0.6"`
  - **Shown values** round half up: rates to 0.1%, inches to 0.01 in.
- **Names:**
  - **Configurations:** `landmark`, `geometry`, `geometry_no_self_check`; on development runs, each may also come as `<configuration>_replay` (spec C425).
  - **Set B variants:** `geometry`, `geometry_uncalibrated`, `known_waterline`, `known_waterline_uncalibrated`, `geometry_no_self_check`.
  - **Result fields** keep Table 14's names (`status`, `refusalReason`, `noFloodSeen`, `level`, `landmark`, `passability`, `levelIsFloor`, `basis`, `depthInMin`, `depthInMax`), plus MS3b's `levelFrom`. The per-wheel point estimate is `depthInPoint`.
- **Report copy:**
  - The footer carries exactly two lines: `Lusot estimates depth at one spot. It is not advice to cross. Follow MMDA and local advisories.` and `Not affiliated with MMDA.`
  - The word "safe" never appears in any case. Neither do "MMDA's 9 levels", "accuracy", or the verdict words "overfit" and "underfit": comparisons are stated as numbers (spec §4.2).
  - Set A figures are called agreement. Every figure carries its n, and the report calls its results indicative.
  - Axis and row labels say "the alert's level", never "MMDA's level", since the 9 levels aren't all MMDA's and city alerts count too.
- **Printed output** is ASCII only: counts and file names. A path is printed with `backslashreplace`, so a non-ASCII folder name can't break a console. Every printed line masks runs of 12 digits as `<account>`.
- **What never enters the repo:** plan text (cite "plan §N" and paraphrase), account IDs, the Meta Team ID, console links, email addresses, photos, masks, Muse Spark's `reason` text, post links and spot names.
- **Commits:**
  - Conventional Commits, ending with the attribution lines Claude Code gives the session. The controller copies its own lines into each brief.
  - Write the message to a file and use `git commit -F <file>`. Never pipe it from Windows PowerShell 5.1, and never use `--no-verify`.
  - Before every commit, run `python scripts/check_no_plan_leak.py` (expect "clean") and `node scripts/check_account_ids.mjs` (expect no finding). The gitleaks pre-commit hook must pass.
- **Shells:** start each PowerShell command with the PATH refresh in `CLAUDE.md` ("Commands"), and run from the worktree root, `C:\Systems\Lusot\lusot-wt\w4`. Commit from PowerShell after the refresh, or the gitleaks hook fails closed.
- **Memory:** the laptop has about 2 to 3 GB free. No npm install, no `uv sync` of `backend/analysis`, and one test process at a time.

## Review Focus

Most likely first. Each line names its test.

1. **Rows arrive in another order, or with Windows line endings or a byte-order mark** (a judge's checkout, or a file saved by an editor). The rebuild should still be byte for byte identical, and nothing should crash. Tests: Task 2 `test_bom_and_crlf_are_tolerated`, Task 8 `test_report_ignores_row_order`.
2. **A set with nothing to count:** no A-neg rows, every Set A photo refused, or no Set D. Rates read "0 of 0 (undefined)", the guards fail, and nothing divides by zero. Tests: Task 3 `test_all_refused_gives_undefined_rates`, Task 6 `test_undefined_rate_drops_geometry`, Task 8 `test_report_with_empty_sets`.
3. **An M8 label whose box Muse Spark never answered, or a label that matched no box.** The first is a disagreement and the second is counted apart, never a `KeyError`. Test: Task 4 `test_landmark_agreement_counts_unanswered_and_unmatched`.
4. **A judge runs the command from another folder, as `python3`, under `-I`, in a cp1252 console.** It works, and the output is ASCII. Tests: Task 9 `test_runs_isolated_from_another_folder`, `test_output_is_ascii`.
5. **A raw label with odd spacing, capitals, curly quotes or a spelled-out unit** ("Knee  Deep", `10”`, "13 - 18 inches", "25 centimeters"). It maps as rules §2 says and passes the word check. Tests: Task 1 `test_label_spacing_case_and_units`, `test_label_words`.

## Files

All new.

| File | Responsibility | Task |
|---|---|---|
| `eval/tests/run_tests.py`, `eval/tests/run_tests.py.lock` | the locked PEP 723 test runner (C417) | 1 |
| `eval/tests/conftest.py` | puts `eval/` on `sys.path` | 1 |
| `eval/tests/rules_md.py` | reads `eval/rules.md`'s sections and tables for the drift tests (C408) | 1 |
| `eval/scoring/__init__.py` | `RULES_VERSION` and the package docstring | 1 |
| `eval/scoring/scale.py` | the 9 levels, their limits and classes (rules §1) | 1 |
| `eval/scoring/labels.py` | rules §2's mapping and its word list (C404, C420) | 1, 10 |
| `eval/scoring/rows.py` | the results contract: loading, the allow-list and the row types (C402, C403) | 2, 4 |
| `eval/scoring/paths.py` | the sealed-path guard (C411), shared by the loader and the one command | 2 |
| `eval/tests/builders.py` | synthetic row builders shared by the tests | 2 |
| `eval/scoring/exclusions.py` | rules §3 and §9, from the manifest's facts and labels (C404) | 3 |
| `eval/scoring/metrics.py` | rules §7's metrics (C405, C406) | 3, 4, 5 |
| `eval/scoring/gate.py` | rules §8's gate and outcome rule (C407) | 6 |
| `eval/scoring/svg.py` | the charts (C410) | 7 |
| `eval/scoring/report.py` | `report.md` and `summary.json` (C409, C418, C421) | 8 |
| `eval/run_eval.py` | the one command (C401, C411, C420) | 9 |
| `eval/tests/fixtures/small_run/` | a synthetic results folder and its committed report | 9 |
| `eval/tests/test_*.py` | one test file per module | 1 to 9 |

## Execution notes

- **Routing (D18):** implementers, task reviews and the final whole-branch review on Opus 5.5 at xhigh, never max (Rene's override, Oct 29, 8:48 PM; Tasks 1 to 10 and the final review ran at max, before it), and scoped re-reviews on Sonnet 5.5 at xhigh. Fable 5.1 at max only when Opus can't.
- **Each implementer** gets from the controller this plan's task, its Global Constraints, the spec, and the controller's attribution lines.
- **Commands** run from the worktree root unless a step says otherwise. A test run is `uv run --locked --script eval/tests/run_tests.py`, followed by any pytest arguments, for example `-k test_level_for_inches`.
- **Tracking:** the controller ticks this plan's boxes with their evidence, in the same commit as the work. This branch changes no existing file, so the controller doesn't touch `docs/PROGRESS.md` or the day's log. Its handoff note `w4.md` carries log-ready lines, which the log owner (Window 3, after MS1) folds in.

---

### Task 1: Test runner, level scale and label mapping

**Files:**
- Create: `eval/tests/run_tests.py`, `eval/tests/run_tests.py.lock`, `eval/tests/conftest.py`, `eval/tests/rules_md.py`, `eval/scoring/__init__.py`, `eval/scoring/scale.py`, `eval/scoring/labels.py`
- Test: `eval/tests/test_scale.py`, `eval/tests/test_labels.py`

**Interfaces:**
- Produces, in `scoring`: `RULES_VERSION: str = "0.6"`.
- Produces, in `scoring.scale`:
  - `LEVELS: tuple[str, ...]`, the 9 names in order (the same strings as MS3a's `rules.LEVELS`)
  - `UPPER_IN: tuple[Decimal | None, ...]`: 5, 8, 10, 13, 19, 26, 37, 45, None
  - `CLASSES: dict[str, str]`, from level to class; `CLASS_NAMES = ("PATV", "NPLV", "NPATV")`
  - `NO_FLOOD_INDEX: int = -1`
  - `level_index(level: str) -> int`, which raises `ValueError` for an unknown level
  - `level_for_inches(depth: Decimal) -> str`: the shallowest level whose upper limit is at or above `depth`, so in-between values round deeper. It raises `ValueError` below 0.
- Produces, in `scoring.labels`:
  - `LevelLabel(kind: str, level: str | None)`, a frozen dataclass, where `kind` is `level`, `blank`, `status` or `unmapped`
  - `ClassLabel(kind: str, cls: str | None)`, a frozen dataclass, where `kind` is `class`, `blank` or `unmapped`
  - `map_level_label(raw: str) -> LevelLabel` and `map_passability(raw: str) -> ClassLabel`
  - `CM_PER_INCH = Decimal("2.54")`, `STATUS_WORDS = frozenset({"subsided"})`, `OTHER_WORDS = "(other words)"`
  - `LABEL_WORDS: frozenset[str]`: every word in the first column of rules §2's two tables (with the annotations `(off-scale)` and `(over a person's head)` dropped, and the words of the other parentheticals kept, so `types`, `of` and `sedan` are in), plus the unit words (`in`, `inch`, `inches`, `cm`, `centimeter`, `centimeters`, `centimetre`, `centimetres`), `to` and `STATUS_WORDS`
  - `label_words_ok(raw: str) -> bool`: true when `raw` is empty or blank, when it is exactly `OTHER_WORDS`, or when every token is a `LABEL_WORDS` word or a number of up to 3 digits with up to 2 decimals (optionally glued to `in` or `cm`). Tokens are lowercase, and split on spaces and the punctuation `- – , . ( ) " ' ” “ ″ /`, where a `.` inside a number stays part of it. Any other character makes it false.
  - **The passability phrases,** from rules §2's second table: `passable to all vehicles`, `passable to all types of vehicles`, `passable to light vehicles` (PATV); `not passable to light vehicles`, `not passable to motorcycles and cars`, `not passable to motorcycles and cars sedan` (NPLV); `not passable to all vehicles`, `not passable to all types of vehicles`, `not passable to any vehicle` (NPATV); and the three codes. A parenthetical's brackets are dropped and its words kept, so `cars (sedan)` normalises to `cars sedan`.
- Produces, in `eval/tests/rules_md.py`:
  - `section(number: int) -> str`: the text of `eval/rules.md`'s `## N.` section
  - `tables(text: str) -> list[list[list[str]]]`: each Markdown table as rows of stripped cells, with the header and separator rows dropped
  - `version() -> str`: the `vX.Y` on the status line, without the `v`

- [x] **Step 1: Write the runner and the path hook.**
  - `run_tests.py` carries PEP 723 metadata: `requires-python = ">=3.13,<3.14"`, `dependencies = ["pytest==9.1.1", "scikit-learn==1.9.1"]`. Its body runs `pytest.main([<its own folder>, "-q", "-p", "no:cacheprovider", *sys.argv[1:]])` and exits with the result.
  - `conftest.py` inserts the `eval/` folder (`Path(__file__).resolve().parents[1]`) at the front of `sys.path`, so tests import `scoring` and `run_eval`.
- [x] **Step 2: Write the failing tests.**
  - `test_scale.py`:
    - `test_scale_matches_rules_md`: `rules_md.tables(rules_md.section(1))[0]` gives rows of index, level, limit and class. Each row's level equals `LEVELS[i]`, its limit text (`d ≤ 5` … `d > 45`) gives `UPPER_IN[i]`, and its class equals `CLASSES[level]`.
    - `test_level_for_inches`: `0 → below_gutter`, `5 → below_gutter`, `5.01 → gutter`, `8 → gutter`, `13 → half_tire`, `13.2 → knee`, `26 → tire`, `45 → chest`, `45.1 → above_chest` (each a `Decimal`). `Decimal("-0.1")` raises `ValueError`.
    - `test_level_index`: `level_index("knee") == 4`, and `level_index("ankle")` raises `ValueError`.
    - `test_rules_version_matches_rules_md`: `RULES_VERSION == rules_md.version()`.
  - `test_labels.py`:
    - `test_label_table_matches_rules_md`: every row of rules §2's first table maps to its level. The test drops a trailing parenthetical such as `(off-scale)` and surrounding quotes, so `"lagpas tao"` is tested as `lagpas tao`.
    - `test_listed_variants`: `half knee` and `half-knee` → `half_knee`; `Half Gutter` → `below_gutter`; `gutter-deep` → `gutter`; `above gutter deep` → `half_knee`.
    - `test_words_beat_numbers`: `Gutter deep, 8"` → `gutter`; `knee deep (10 inches)` → `knee`.
    - `test_single_number`: `10"` → `half_knee`; `12"` → `half_tire`; `37 inches` → `waist`; `19 in` → `knee`.
    - `test_range_takes_its_upper_value`: `13-18 inches` → `knee`; `8 to 10 inches` → `half_knee`.
    - `test_centimetres`: `25 cm` → `half_knee` (9.84 in); `33 cm` → `half_tire` (12.99 in).
    - `test_label_spacing_case_and_units` (Review Focus 5): `Knee  Deep` → `knee`; `10”` → `half_knee`; `13 - 18 inches` → `knee`; `13–18 inches` (an en dash) → `knee`; `25 centimeters` → `half_knee`.
    - `test_bare_number_and_suffixes` (MS6E-Q1, items 11 and 12; C404):
      - `25` → `unmapped`, because a number with no unit maps to nothing
      - `knee level` → `knee` and `waist level` → `waist`, because `level` and `deep` are interchangeable
      - `13-18 inches ("half tire level")`, a real Valenzuela alert form, → `half_tire`: the words map, and words beat the range
      - `above knee level` and `above knee deep` → `tire`; `knee` → `knee`, because the suffix may be left off
    - `test_ranges_and_two_units` (MS6E-Q1, item 13):
      - `13"-18"` and `13 in - 18 in` → `knee`, a range with a unit on each number
      - `24 in (61 cm)` and `61 cm / 24 in` → `tire`, one depth in two units, both of which give `tire`
      - `8 in (25 cm)` → `unmapped`: 8 in gives `gutter`, 25 cm gives `half_knee`
      - `knee deep, subsided` → `unmapped`, since a status counts only as the whole label
    - `test_status_blank_and_unmapped`:
      - `subsided` → kind `status`
      - `""` and `"  "` → kind `blank`
      - `neck deep`, `ankle deep`, `deep` and `OTHER_WORDS` → kind `unmapped`
      - `Ankle deep, 4"` → `unmapped`, because words that don't map can't decide, and the number never stands in for them
    - `test_passability_table_matches_rules_md`: every comma-separated phrase in rules §2's passability table maps to its class, with each parenthetical tried both kept and dropped. So `passable to all (types of) vehicles` checks both `passable to all vehicles` and `passable to all types of vehicles`.
    - `test_passability_forms`:
      - `NPLV` → NPLV
      - `not passable to light vehicles (NPLV)` → NPLV
      - `Passable to light vehicles` → PATV
      - `NPATV (passable to all vehicles)` → `unmapped`, because its two parts disagree
      - `""` → `blank`; `closed` → `unmapped`
    - `test_label_words`:
      - `label_words_ok` is true for every phrase in rules §2's two tables (with the two annotations dropped, since `off` and `scale` aren't label words), for `Gutter deep, 8"`, `13-18 inches`, `25cm`, `NPLV`, `""` and `OTHER_WORDS`
      - it is false for `Espana Maceda`, `8:00 AM`, `knee deep (Espana)`, `2026 knee`, and a label holding `http://x` or `@`
      - every word in the first column of `rules_md.section(2)`'s two tables, outside the two annotations, is in `LABEL_WORDS`
- [x] **Step 3:** Run `uv lock --script eval/tests/run_tests.py`. Expected: `eval/tests/run_tests.py.lock` appears (uv fetches the package index once). Check in the lock that scikit-learn resolved to 1.9.1; if that version doesn't exist, pin the newest 1.9.x, and check its `cohen_kappa_score` with Context7 at that version. Then run the tests. Expected: FAIL, since `scoring` doesn't exist.
- [x] **Step 4: Implement `scale.py`, `labels.py` and `scoring/__init__.py`.**
  - **Level labels.** The order matters, so that no mark is lost.
    1. Lowercase the raw text.
    2. Pull out every number with its unit (`"`, `”`, `″`, `in`, `inch`, `inches`, `cm` and the centimetre spellings), including a range: two numbers joined by `-`, `–` or `to`.
    3. Only then normalise the words that are left: hyphens, underscores and runs of whitespace become single spaces, and outer punctuation is stripped.
    - **Words that remain** must equal one of rules §2's phrases exactly: `gutter`, `half knee`, `half tire`, `knee`, `tire`, `waist`, `chest`, `half gutter`, `above gutter`, `above knee` and `lagpas tao`. Each may end with `deep` or `level`, or neither, since §2 treats the two words alike (spec C404; MS6E-Q1, item 12).
    - **A number with no unit** maps to nothing (MS6E-Q1, item 11).
    - **Two measures** joined by `-`, `–` or `to` form a range, whether or not each carries its own unit. Two measures not joined that way are one depth in two units: the label maps only when both give the same level (MS6E-Q1, item 13).
    - **Words win** when they map. Words that don't map give `unmapped`.
    - **With no words left,** the number decides through `level_for_inches`, after centimetres are converted and a range is taken at its upper value.
    - **Special cases:** a word in `STATUS_WORDS` gives `status`, and `OTHER_WORDS` gives `unmapped`.
  - **Passability:** the same normalising. A lone code (`patv`, `nplv` or `npatv`) or an exact phrase gives its class. A phrase with a code in parentheses, or a code with a phrase in parentheses, gives the class only when both agree. Anything else is `unmapped`.
- [x] **Step 5:** Run the tests. Expected: PASS.
- [x] **Step 6:** Run the two leak checks (Global Constraints), then commit `feat(eval): add the level scale, the label mapping and the test runner`.
  - **Evidence:** `1411538`, fix round `268dec3`. RED: `ModuleNotFoundError` for `scoring`; then 17 passed with no warnings, and the lock resolves scikit-learn 1.9.1. Ruff, the leak check, the account-ID scan and gitleaks clean. Review: Approved (w4.md, 4:41 PM Oct 28; `w4-ms6-ledger.md`).

### Task 2: Rows: the loader and its allow-list

**Files:**
- Create: `eval/scoring/rows.py`, `eval/scoring/paths.py`, `eval/tests/builders.py`
- Test: `eval/tests/test_rows.py`, `eval/tests/test_paths.py`

**Interfaces:**
- Consumes: `LEVELS`, `CLASSES`, `CLASS_NAMES` (Task 1); `label_words_ok` (Task 1).
- Produces, in `scoring.rows`:
  - `class RowError(ValueError)`, whose message reads `<file>:<line>: <what>` (line 0 for `run.json` as a whole)
  - `CONFIGS = ("landmark", "geometry", "geometry_no_self_check")`
  - `SET_B_VARIANTS = ("geometry", "geometry_uncalibrated", "known_waterline", "known_waterline_uncalibrated", "geometry_no_self_check")`
  - Schema v1's categories, as frozensets:
    - `VEHICLE_TYPES` (the 9 types)
    - `WHEEL_WATERLINES` (7 values), `BODY_WATERLINES` (6), `PERSON_WATERLINES` (8)
    - `YES_NO_UNSURE`, and `{"yes", "no"}` for `photo_usable`
  - frozen dataclasses:
    - `Result(status: str, reason: str | None, no_flood_seen: bool, level: str | None, level_is_floor: bool, passability: str | None, landmark: str | None)`, where `landmark` is a level result's landmark and `None` otherwise (Task 8's `review.csv`, C426)
    - `Facts(poster_kind: str | None, label_in_image: str | None, match: str | None, duplicate: bool, metro_manila: bool, decodes: bool)`
    - `Reference(box_id: int | None, kind: str, m8_landmark: str | None, m8_type: str | None, spark_landmark: str | None, spark_type: str | None)`, where `kind` is `wheel`, `body` or `person`
    - `PhotoRow(photo_id: str, event_id: str, level_label_raw: str, passability_raw: str, other_alerts_raw: tuple[str, ...], facts: Facts, quality: str | None, subsets: tuple[str, ...], surface: str | None, results: Mapping[str, Result], answered: bool, references: tuple[Reference, ...])`, where `answered` means `answer` wasn't null
    - `Estimate(measured: bool, point: Decimal | None, low: Decimal | None, high: Decimal | None, fail: str | None)`
    - `WheelRow(crop_id: str, wheel: int, car_id: str, vehicle_type: str, tire_code: str, true_depth_in: Decimal, sam_water_found: bool, bins: Mapping[str, str], estimates: Mapping[str, Estimate])`
    - `Run(meta: Mapping[str, object], kind: str, synthetic: bool, self_check: bool, geometry_dropped: bool, rerun_reason: str | None, baseline_level: str | None, baseline_class: str | None, set_a: tuple[PhotoRow, ...] | None, a_neg: tuple[PhotoRow, ...] | None, set_b: tuple[WheelRow, ...] | None, set_d: tuple[WheelRow, ...] | None, latency: tuple[tuple[str, Decimal], ...] | None)`, where `None` means the set's file is absent
  - `load_run(folder: Path) -> Run`. Its first step is `refuse_sealed(folder)`, before anything is read or listed.
- Produces, in `scoring.paths` (C411):
  - `class SealedPath(ValueError)`, whose message is `path inside a folder named sealed` and never names the path
  - `refuse_sealed(path: Path) -> None`. It raises `SealedPath` when any part of the path as given, or of its absolute, normalised form (`os.path.abspath`, then `normpath`), equals `sealed`, ignoring case. It never touches the disk.
- Produces, in `eval/tests/builders.py`:
  - `level(level: str, *, floor: bool = False, landmark: str = "hub", level_from: str | None = None, inches: tuple[str, str] | None = None) -> dict`, plus `nfs() -> dict`, `refused(reason: str) -> dict` and `failed(reason: str) -> dict`, each an `item_fields()` dict
  - `set_a_row(photo_id: str, *, label: str = "knee deep", passability: str = "", others: tuple[str, ...] = (), landmark: dict | None = None, geometry: dict | None = None, **fields) -> dict`. Both results default to `level("knee")`. The facts default to values that pass §9: `poster_kind: "mmda"`, `label_in_image: "no"`, `match: "same_post"`, `duplicate: false`, and `metro_manila` and `decodes` true. `quality` defaults to `"ok"`. Any other field is set through `fields`.
  - `a_neg_row(photo_id: str, **fields) -> dict`, with `surface: "wet"`, `poster_kind: "other"`, `label_in_image: "no"`, `match: None`, `metro_manila: true`, `duplicate: false`, `decodes: true`, `quality: None` and `subsets: []` by default (MS2 has no M8 for A-neg, spec C423); `set_b_row(crop_id: str, wheel: int = 1, **fields) -> dict`; `run_json(**overrides) -> dict`
  - `write_run(folder: Path, *, run: dict, set_a=None, a_neg=None, set_b=None, set_d=None, latency=None) -> Path`. It writes JSON Lines with `\n` endings, and leaves out any set given as `None`.

**The contract the loader enforces** (spec §4.3, C403, C420):
- **Files:** `run.json` is required. `set_a.jsonl`, `a_neg.jsonl`, `set_b.jsonl`, `set_d.jsonl` and `latency.jsonl` are each optional, except that a `sealed` run needs `set_a.jsonl` and `a_neg.jsonl`. Text is UTF-8 with an optional byte-order mark; `\r\n` and `\n` both end a line; blank lines are skipped.
- **Numbers:** JSON is parsed with `parse_float=Decimal`, and with a `parse_constant` that refuses `NaN` and `Infinity`.
  - A decimal field accepts a JSON integer, converted to `Decimal`, refuses a boolean, and carries at most 4 decimal places.
  - An integer field (ids, `wheel`, `basis` counts) refuses booleans and fractions.
  - A boolean field takes only `true` or `false`.
- **`run.json`:**
  - **Keys:**
    - `kind` (`sealed` or `development`) and `date` (`YYYY-MM-DD`)
    - `rules_version` and `freeze_commit` (40 lowercase hex characters)
    - `frozen` (names to short strings)
    - `datasets`: keys among `set_a`, `a_neg`, `set_b` and `set_d`, each with `version` and `split_seed` strings
    - `self_check` (`on` or `off`) and `self_check_decided` (a short string)
    - `geometry_default`: `on`, `off` or `dropped`, with `geometry_dropped_reason` when `dropped`
    - `stops`: a list of `{at, cause, resumed}`, all short strings
    - `rerun_reason` (a short string, only in a `rerun/` folder)
    - `synthetic: true`, only in test fixtures (C422)
    - `baseline_level` (one of `LEVELS`) and `baseline_class` (one of `CLASS_NAMES`), the frozen baseline (C424)
  - **Required:** a sealed run needs every key except `geometry_dropped_reason`, `rerun_reason`, `stops` and `synthetic`. A development run may leave out the baseline pair, and the harness then computes it from the run's own rows (Task 4). A development run may also leave out `rules_version`, `freeze_commit`, `self_check_decided` and `geometry_default`.
  - **Version:** `rules_version`, when present, must equal `RULES_VERSION`.
  - **Strings:** each is at most 80 characters from `[A-Za-z0-9 ._:/,+()=-]`, with no `://` and no `@`.
- **A Set A row** has exactly these keys: `photo_id`, `event_id`, `level_label_raw`, `passability_raw`, `other_alerts_raw`, `poster_kind`, `label_in_image`, `match`, `duplicate`, `metro_manila`, `decodes`, `quality`, `subsets`, `outcomes`, `answer`, `wheel_inches`, `m8`.
- **An A-neg row** has exactly Set A's keys without the three label fields and `m8`, plus `surface` (`wet` or `dry`): `photo_id`, `event_id`, `poster_kind`, `label_in_image`, `match` (null for A-neg), `duplicate`, `metro_manila`, `decodes`, `quality`, `subsets`, `surface`, `outcomes`, `answer` and `wheel_inches`. Scoring reads only `duplicate` and `decodes` (Task 3).
- **Values:**
  - ids match the Global Constraints' pattern; `photo_id` is unique within its file, and so is the pair `crop_id` + `wheel`
  - `level_label_raw`, `passability_raw` and each entry of `other_alerts_raw` pass `label_words_ok`
  - `poster_kind` is `mmda`, `city` or `other`; `label_in_image` is `no`, `cropped` or `yes`; `match` is `same_post`, `separate_post` or `none`
  - `quality` is `ok`, `dark`, `blurry`, or null when no mark was made (spec C423); `subsets` may be empty
  - tags, refusal reasons, bin names and values, and failed checks are tokens matching `^[a-z][a-z0-9_]{0,31}$`
- **`outcomes`:**
  - **Which configurations:** exactly `landmark` and `geometry`, plus `geometry_no_self_check` when, and only when, `self_check` is `on`. When `geometry_default` is `dropped`, only `landmark`.
  - **Replay results (C425):** in a development run only, any present configuration may also have `<configuration>_replay` (for example `landmark_replay`), a result of the same shape. A sealed run with any `_replay` key is refused. `PhotoRow.results` holds them under those keys, and `REPLAY_SUFFIX = "_replay"` names the suffix.
  - **Each result:**
    - `refused` or `failed`: exactly `status` and `refusalReason`
    - "no flood seen": exactly `status: "done"` and `noFloodSeen: true`
    - a level: `status`, `noFloodSeen: false`, `level`, `landmark`, `passability`, `levelIsFloor` and `basis`, with an optional `levelFrom` and an optional pair `depthInMin` ≤ `depthInMax`
  - **Values in a level result:**
    - `level` is one of `LEVELS`, and `passability` equals `CLASSES[level]`, in capitals
    - `landmark` is in the union of the three waterline sets, except `not_visible`
    - `basis` holds exactly `vehicles` and `people`, integers of 0 or more that sum to at least 1
    - `levelFrom` is `landmark` or `geometry`
    - the depths are decimals from 0 to under 100
- **`answer`:** `null`, or exactly `photo_usable`, `standing_water`, `vehicles`, `wheels` and `people`. Each value is checked against its schema v1 set. Ids are integers and `wake_visible` is a boolean. A `reason` key, at any depth, is refused.
- **`wheel_inches`:** a list of `{box_id, depthInMin, depthInMax}`.
- **`m8`:** a list of `{box_id, kind, landmark, vehicle_type}`.
  - `box_id` is an integer or null, and `kind` is `wheel`, `vehicle` or `person`.
  - `landmark` is null or a value from that kind's waterline set: wheel, body for a vehicle, or person.
  - `vehicle_type` is from `VEHICLE_TYPES` for a vehicle, and null otherwise.
- **The join into `references`:**
  - An M8 `wheel` reads Muse Spark's `wheels[].waterline` for its box.
  - A `vehicle` gives a `body` reference from `vehicles[].body_waterline`, and its type from `vehicles[].type`.
  - A `person` reads `people[].waterline`.
  - A box id the answer lacks gives `spark_landmark = None` (unanswered).
- **A Set B or Set D row** has exactly:
  - `crop_id`, `wheel` (1 or 2) and `car_id`
  - `vehicle_type` (from `VEHICLE_TYPES`) and `tire_code` (`^\d{3}/\d{2}R\d{2}C?$`)
  - `true_depth_in`, a decimal from 0 to under 100
  - `sam_water_found`, and an optional `bins` (tokens to tokens; a missing `bins` reads as `{}`)
  - `estimates`. It must include `geometry`, holds only names from `SET_B_VARIANTS`, and has the same names on every row of a file. `geometry_no_self_check` is allowed only when `self_check` is `on`. Each estimate is `{measured, depthInPoint, depthInMin, depthInMax, fail}`. A measured one has all three decimals and a null `fail`. An unmeasured one has three nulls and a token `fail`.
- **A latency row** has exactly `test_id` and `seconds`, a decimal above 0 and under 3,600.

- [x] **Step 1: Write the failing tests** in `test_rows.py`, building each folder with `builders.write_run(tmp_path, ...)`:
  - `test_loads_a_valid_run`: 3 Set A rows, 2 A-neg rows, 2 Set B rows and 2 latency rows load. The types are `Run`, `PhotoRow` and `WheelRow`; `true_depth_in` is `Decimal("11.25")`; and an absent `set_d.jsonl` gives `run.set_d is None`.
  - `test_refuses_fields_outside_the_contract`, parametrized over a top-level `reason`, `post_url`, `spot_text`, `city`, `alert_time_pht` and `conflicting_alerts`: a `RowError` naming the file and line 1.
  - `test_refuses_free_text`: `waterline: "Rim quarter"`, `waterline: "hubcap"`, a `reason` key inside `answer`, and a refusal reason with a space are each refused.
  - `test_accepts_real_values` (spec E8): a level result with `passability: "NPLV"`; a passability label of `not passable to motorcycles and cars (sedan)` (44 characters); and `other_alerts_raw: ["Knee deep", "(other words)"]` all load.
  - `test_refuses_private_text_in_labels` (spec E8): `level_label_raw` of `Espana Maceda`, `knee deep 8:00 AM` and `http://x`, and an `other_alerts_raw` entry of `Espana`, are each refused.
  - `test_refuses_ids_that_arent_opaque`: `photo_id` of `A 01`, `2026-10-30`, `Espana` and `A0001-1-2-3` are refused; `A001`, `N001`, `E01`, `B01-1-2` and `D01` load. A duplicate `photo_id`, and a duplicate `crop_id` with the same `wheel`, are refused.
  - `test_result_shapes`: a level with the wrong class, a lowercase class, a level result without `basis`, an NFS result carrying `level`, a refusal carrying `level`, a landmark of `not_visible`, and `basis: {"vehicles": 0, "people": 0}` are each refused. The four builder results load to the expected `Result` values, the level result's with `landmark="hub"` and the other three with `landmark=None`.
  - `test_numbers`:
    - `true_depth_in` of `11.12345` is refused, and `11.1234` loads
    - `true_depth_in: 10` loads as `Decimal("10")`, and `true_depth_in: true` is refused
    - `seconds: NaN` and `seconds: Infinity` are refused
    - `wheel: 1.0` and `wheel: true` are refused
  - `test_synthetic_flag`: `synthetic: true` loads and reaches `run.meta`, and `synthetic: "yes"` is refused.
  - `test_replay_and_baseline_fields` (C424, C425): a development row with `landmark_replay` loads; a sealed row with it is refused; `geometry_replay` without `geometry` is refused. A sealed `run.json` without `baseline_level` is refused, `baseline_level: "ankle"` is refused, and a development `run.json` without the pair loads.
  - `test_unmarked_quality` (spec C423): an A-neg row with `quality: null` and `subsets: []` loads, and so does a Set A row with `quality: null`; `quality: "unknown"` is refused.
  - `test_errors_never_echo_values`: a refused label `Espana Maceda` gives a message with the file, the line and the rule, without the word `Espana`.
  - `test_self_check_controls_the_third_configuration`: with `self_check: "on"`, a row without `geometry_no_self_check` is refused; with `"off"`, a row that has it is refused.
  - `test_geometry_dropped`: with `geometry_default: "dropped"` and a reason, rows with only `landmark` load and `run.geometry_dropped` is true; a row with `geometry` is refused; `dropped` without a reason is refused.
  - `test_rules_version`: a sealed run without `rules_version`, or with `"0.5"`, is refused; a development run without it loads.
  - `test_sealed_run_needs_set_a_and_a_neg`: a sealed run without `a_neg.jsonl` is refused; a development run without both loads.
  - `test_bom_and_crlf_are_tolerated` (Review Focus 1): the same rows written with a byte-order mark and `\r\n` endings load equal to the plain ones.
  - `test_m8_join`:
    - an M8 wheel on box 3, with the answer's wheel 3 at `rim_quarter`, gives `Reference(3, "wheel", "hub", None, "rim_quarter", None)`
    - a box missing from the answer gives `spark_landmark=None`
    - `box_id: null` survives as `None`
    - an M8 vehicle on box 1 gives a `body` reference with both types
    - a null `answer` gives `answered=False`
  - `test_set_b_estimates`: a measured estimate missing `depthInPoint`, an unmeasured one with numbers, a row without `geometry`, an unknown variant, and two rows with different variant sets are each refused. All five variants load together.
  - `test_load_run_refuses_sealed_first` (C411): `load_run(tmp_path / "sealed")`, which doesn't exist, raises `SealedPath`, not `RowError` or `OSError`, and nothing is created.
- [x] **Step 1b: Write the failing tests** in `test_paths.py`:
  - `test_refuses_sealed_paths`, parametrized over `tmp_path/"sealed"`, `tmp_path/"a"/"Sealed"/"x"`, `tmp_path/"sealed"/"sub"/".."` and `tmp_path/"sealed"/".."/"x"`: `refuse_sealed(p)` raises `SealedPath`, its message is `path inside a folder named sealed`, and nothing is created.
  - `test_allows_other_paths`: `refuse_sealed` doesn't raise for `tmp_path/"unsealed"/"x"`, `tmp_path/"sealed_notes"` or `tmp_path/"final"`.
- [x] **Step 2:** Run the tests. Expected: FAIL.
- [x] **Step 3:** Implement `paths.py`, then `rows.py`: one validator per kind of object, with the messages above, and `load_run` assembling a `Run` from them. Rows keep their file order; sorting is the report's job.
- [x] **Step 4:** Run the tests. Expected: PASS.
- [x] **Step 5:** Run the leak checks, then commit `feat(eval): load results through an allow-list`.
  - **Evidence:** `18eb891`, fix round `bbe1edf`. RED: `Result`'s arity `TypeError`, `ModuleNotFoundError` for `scoring.paths`, a `RowError` in place of `SealedPath`; then 143 passed, and 39 single-rule mutations of the loader plus 7 targeted ones were each caught. Checks clean (plan-leak 165 files, account-ID 129). Review: fixed, then re-reviewed clean (w4.md, 5:53 PM).

### Task 3: Exclusions, Set A's level metrics and kappa

**Files:**
- Create: `eval/scoring/exclusions.py`, `eval/scoring/metrics.py`
- Test: `eval/tests/test_exclusions.py`, `eval/tests/test_set_a.py`, `eval/tests/test_kappa.py`

**Interfaces:**
- Consumes: `LEVELS`, `CLASSES`, `level_index`, `NO_FLOOD_INDEX`, `map_level_label`, `map_passability`, `LevelLabel`, `ClassLabel` (Task 1); `PhotoRow`, `Facts`, `Result` (Task 2).
- Produces, in `scoring.exclusions`:
  - `REASONS: tuple[str, ...]`: rules §9's eight reasons in order, worded as there:
    1. `not posted by MMDA or a city government`
    2. `depth or passability label visible in the image`
    3. `no matching alert`
    4. `unmapped label`
    5. `conflicting alerts`
    6. `duplicate or repost`
    7. `outside Metro Manila`
    8. `the file can't be decoded`
  - `set_a_exclusion(facts: Facts, level: LevelLabel, cls: ClassLabel, others: Sequence[LevelLabel]) -> str | None`. It returns the first reason that applies, in order, and takes no result, so exclusion can't read one (C404).
    - reason 1: `poster_kind` is neither `mmda` nor `city`
    - reason 2: `label_in_image == "yes"`
    - reason 3: `match == "none"`, or the main level label has kind `status`
    - reason 4: the main level label is `unmapped`; or the main level label is `blank` and the class label is `blank` or `unmapped` (MS6E-Q1, item 14); or any label in `others` is `unmapped`
    - reason 5: the levels of the main label and of the `others` (statuses and blanks left out) span more than one level
    - reason 6: `duplicate`; reason 7: not `metro_manila`; reason 8: not `decodes`
    - An `unmapped` passability label beside a mapped level label excludes nothing (MS6E-Q1, item 2).
  - `a_neg_exclusion(facts: Facts) -> str | None`: `duplicate` → reason 6; not `decodes` → reason 8 (MS6E-Q1, item 6)
- Produces, in `scoring.metrics`:
  - `Rate(k: int, n: int)`, a frozen dataclass with `.value -> Fraction | None`, which is `None` when `n == 0`
  - `scored_index(result: Result) -> int | None`: the level's index (a floor at its own level), `NO_FLOOD_INDEX` for "no flood seen", and `None` for a refusal or a failure
  - `lusot_class(result: Result) -> str | None`: the level's class, `"PATV"` for "no flood seen", and `None` otherwise
  - `quadratic_kappa(pairs: Sequence[tuple[int, int]], levels: int = 9) -> Fraction | None`: `1 − Σ w·O / Σ w·E`, with `w = (i − j)²`, `O` the counts and `E = rowᵢ · colⱼ / N`. It returns `None` for no pairs, or when `Σ w·E = 0`.
  - `SetAScores`, a frozen dataclass with these fields:
    - `config: str`, `scored: int`, `answered: int`, `refused: int`, `failed: int`
    - `coverage`, `under`, `over`, `exact`, `within_one` and `passability`, each a `Rate`
    - `kappa: Fraction | None` and `kappa_n: int`
    - `no_flood_seen: int` and `floors: int`
    - `refusal_reasons` and `failure_reasons`, each `tuple[tuple[str, int], ...]`
    - `matrix: tuple[tuple[int, int, int], ...]`: the alert's index, Lusot's index (−1 for "no flood seen") and the count, sorted
  - `excluded_set_a(rows: Sequence[PhotoRow]) -> tuple[tuple[str, str], ...]`: (photo id, reason) pairs, sorted by id
  - `excluded_a_neg(rows: Sequence[PhotoRow]) -> tuple[tuple[str, str], ...]`, the same for A-neg
  - `left_out_of_passability(rows: Sequence[PhotoRow]) -> tuple[str, ...]`: the ids of scored photos whose passability phrase didn't map, which the report lists (MS6E-Q1, item 2)
  - `score_set_a(rows: Sequence[PhotoRow], config: str) -> SetAScores`, which skips excluded rows
  - `fmt_rate(rate: Rate) -> str`: `3 of 17 (17.6%)`, or `0 of 0 (undefined)`, with percentages rounded half up to 0.1% through `Decimal`
  - `fmt_inches(value: Decimal | None) -> str`: `2.10 in`, or `undefined`. Both formatters live here, so the gate and the report share one rounding path.

- [x] **Step 1: Write the failing tests.**
  - `test_exclusions.py`:
    - `test_reasons_match_rules_md`: each bullet of `rules_md.section(9)`, with its backticked parenthetical removed, equals `REASONS`, in order.
    - `test_each_reason`: one `Facts` per reason gives that reason, and a row that triggers 2 and 6 gives 2.
    - `test_status_and_blank_labels`:
      - `subsided` gives `no matching alert`
      - two blank labels give `unmapped label`
      - a blank level label with `closed`, a class phrase that maps to nothing, gives `unmapped label` (MS6E-Q1, item 14)
      - a blank level label with `NPLV` gives `None` (an alert with only a class)
      - an unmapped passability phrase with `knee deep` gives `None`
    - `test_other_alerts`:
      - `knee deep` with others `["half-tire deep"]` gives `None` (one level apart)
      - `knee deep` with `["waist deep"]` gives `conflicting alerts`
      - `knee deep` with `["subsided"]` gives `None` (a status is ignored)
      - `knee deep` with `["(other words)"]` gives `unmapped label`
      - `knee deep` with `[""]` gives `None`, because an empty entry is an alert that gave only a class
    - `test_a_neg_reasons`: `duplicate` gives reason 6, an undecodable file reason 8, and `poster_kind` is ignored.
  - `test_set_a.py`, with the hand-computed set below as a module-level fixture:
    - `test_hand_computed_set`:

      | id | label | class | result | why |
      |---|---|---|---|---|
      | A01 | knee deep | NPLV | `knee` | exact; class agrees |
      | A02 | knee deep | (none) | `half_tire` | under, within one; no class |
      | A03 | tire deep | NPATV | no flood seen | under (−1 against 5); PATV disagrees |
      | A04 | half-knee deep | PATV | `tire`, floor | over; NPATV disagrees; one floor |
      | A05 | gutter deep | PATV | refused `too_dark` | unanswered |
      | A06 | waist deep | NPATV | failed `model_error` | unanswered |
      | A07 | half gutter deep | PATV | no flood seen | under (−1 against 0), within one; PATV agrees |
      | A08 | (none) | NPLV | `knee` | an alert with only a class: agrees |
      | A09 | chest deep | NPATV | `chest` | exact; agrees |
      | A10 | knee deep | NPLV | `knee` | excluded: `label_in_image: yes` |

      Expected:
      - `scored == 9`, `answered == 7`, `coverage == Rate(7, 9)`, `refused == 1`, `failed == 1`
      - `under == Rate(3, 6)`, `over == Rate(1, 6)`, `exact == Rate(2, 6)`, `within_one == Rate(4, 6)`, `passability == Rate(4, 6)`
      - `no_flood_seen == 2`, `floors == 1`
      - `refusal_reasons == (("too_dark", 1),)`, `failure_reasons == (("model_error", 1),)`
      - `excluded_set_a(rows) == (("A10", "depth or passability label visible in the image"),)`
    - `test_matrix_counts`: for the set above, `matrix` holds `(4, 4, 1)`, `(4, 3, 1)`, `(5, -1, 1)`, `(2, 5, 1)`, `(0, -1, 1)` and `(7, 7, 1)`, and nothing for A05, A06, A08 or A10.
    - `test_configurations_are_scored_apart`: the same rows with a different `geometry` result give different `geometry` scores and unchanged `landmark` scores.
    - `test_all_refused_gives_undefined_rates` (Review Focus 2): with three rows, all refused, `coverage == Rate(0, 3)`, `under.value is None`, `passability.value is None` and `kappa is None`.
    - `test_exclusions_never_read_results` (spec E5): the hand-computed rows with every outcome replaced, by a refusal and then by a level, give the same `excluded_set_a` and the same `scored`.
    - `test_formatters`: `fmt_rate(Rate(3, 17)) == "3 of 17 (17.6%)"`; `fmt_rate(Rate(1, 16)) == "1 of 16 (6.3%)"` (half up); `fmt_rate(Rate(0, 0)) == "0 of 0 (undefined)"`; `fmt_inches(Decimal("2.1")) == "2.10 in"`; `fmt_inches(Decimal("2.125")) == "2.13 in"`; `fmt_inches(None) == "undefined"`.
    - `test_left_out_of_passability`: a scored row with `passability_raw` of `closed` is listed, and an excluded one isn't.
  - `test_kappa.py`:
    - `test_hand_computed`: `quadratic_kappa([(0, 0), (1, 1), (2, 1), (3, 3)]) == Fraction(9, 10)`.
    - `test_matches_scikit_learn`: 200 sets from `random.Random(20261028)`, each of 2 to 40 pairs of values 0 to 8. `float(ours)` equals `cohen_kappa_score(t, p, weights="quadratic", labels=list(range(9)))` within `1e-9`.
    - `test_undefined_matches_scikit_learn_nan`: `[(3, 3), (3, 3)]` gives `None`, and scikit-learn gives NaN for the same pairs.
    - `test_scikit_learn_drops_values_outside_labels`: this documents why C405 maps "no flood seen" to 0. scikit-learn's kappa on `[(4, -1), (4, 4), (2, 2), (6, 5)]` with `labels=range(9)` equals its kappa without the first pair.
    - `test_no_flood_seen_counts_as_below_gutter`: `score_set_a` on the hand-computed set gives `kappa == quadratic_kappa([(4, 4), (4, 3), (5, 0), (2, 5), (0, 0), (7, 7)])` and `kappa_n == 6`.
- [x] **Step 2:** Run the tests. Expected: FAIL.
- [x] **Step 3:** Implement `exclusions.py` and the Set A part of `metrics.py`. Use `Fraction` for every rate and for kappa. A level metric counts a photo only when its level label's kind is `level`, and passability only when its class label's kind is `class`.
- [x] **Step 4:** Run the tests. Expected: PASS.
- [x] **Step 5:** Run the leak checks, then commit `feat(eval): score Set A and apply the exclusions`.
  - **Evidence:** `15aff38`, fix round `a5ce561`. RED: item 14's case (`assert None == 'unmapped label'`); then 163 passed with `-W error`. Ruff, the 3.9 parse check, the leak checks and gitleaks clean. Review: fixed, then re-reviewed clean (w4.md, 8:29 PM).

### Task 4: Landmark agreement, A-neg, the quality subset, subsets, the baseline and replay

**Files:**
- Modify: `eval/scoring/metrics.py` (this branch's own file, from Task 3), and `eval/scoring/rows.py` for the loader's replay rule below (Task 2's file)
- Test: `eval/tests/test_other_sets.py`, plus one new test in `eval/tests/test_rows.py`

**Interfaces:**
- Consumes: `PhotoRow`, `Reference`, `Result` (Task 2); `Rate`, `excluded_set_a`, `a_neg_exclusion` (Task 3); `map_level_label` (Task 1).
- Produces, in `scoring.metrics`:
  - `LandmarkAgreement(by_kind: tuple[tuple[str, Rate], ...], unanswered: int, unmatched: int)`, with `by_kind` in the order `wheel`, `body`, `person`, `all`.
    - Only rows that aren't excluded and have `answered` true are counted.
    - Each rate counts references that have a box and an M8 landmark. A reference whose `spark_landmark` is `None` counts in `n` as a disagreement, and in `unanswered`.
    - `unmatched` counts M8 labels whose `box_id` is `None`.
  - `landmark_agreement(rows: Sequence[PhotoRow]) -> LandmarkAgreement`
  - `vehicle_type_matrix(rows) -> tuple[tuple[str, str, int], ...]`: M8's type, Muse Spark's type (or `unanswered`) and the count, over `body` references that have a box and an M8 type, in answered rows that aren't excluded; sorted. An M8 label with `box_id` null counts only in `LandmarkAgreement.unmatched`, since it is a gap in M8's labelling, not a box Muse Spark skipped (C415).
  - `ANegScores(scored: int, levels: int, no_flood_seen: int, refused: int, failed: int, false_flood: Rate)`, where `false_flood = Rate(levels, scored)`
  - `score_a_neg(rows, config: str, surface: str | None = None) -> ANegScores`. It skips rows that `a_neg_exclusion` excludes, and when `surface` is given, it keeps only rows with that surface.
  - `QualityScores(n: int, refused: int, answered: int, failed: int, correct: Rate, refusal_reasons: tuple[tuple[str, int], ...])`, where `correct = Rate(refused, n)`
  - `correct_refusals(set_a: Sequence[PhotoRow], a_neg: Sequence[PhotoRow], config: str) -> QualityScores`, over rows that aren't excluded and have `quality` `dark` or `blurry`
  - `SubsetScores(tag: str, n: int, coverage: Rate, under: Rate, passability: Rate)`
  - `score_subsets(rows, config: str) -> tuple[SubsetScores, ...]`: one per tag found in Set A rows, sorted, then `tire_or_deeper` (W6: rows whose level label maps to `tire` or deeper), which is always present
  - **The baseline (spec C424):**
    - `baseline_from_rows(rows: Sequence[PhotoRow]) -> tuple[str | None, str | None]`: the most common mapped level among scored rows with a mapped level, with ties going to the deeper level, and the most common mapped class among scored rows with a mapped class, with ties going to the stricter class (NPATV, then NPLV, then PATV). Each is `None` when there's nothing to count.
    - `BaselineScores(config: str, level: str, cls: str, exact: Rate, within_one: Rate, under: Rate, passability: Rate, caught_nplv: Rate, caught_npatv: Rate)`, and `score_baseline(rows, config: str, level: str, cls: str) -> BaselineScores`. The constant answer is scored on exactly the rows `score_set_a` uses for that configuration: answered rows with a mapped level for the level rates, and answered rows with a mapped class for passability and the caught counts.
    - `caught(rows, config: str) -> tuple[Rate, Rate]`: Lusot's NPLV and NPATV catches, over answered rows whose stated class is NPLV (then NPATV). A row counts as caught when Lusot's class is NPLV or NPATV.
  - **Per level:** `LevelRow(level: str, n: int, answered: int, exact: int, within_one: int, under: int)`, and `score_by_level(rows, config: str) -> tuple[LevelRow, ...]`, over scored rows with a mapped level, in level order. Only levels present get a row.
  - **Replay (spec C425):** `ReplayComparison(config: str, in_sample: SetAScores, replay: SetAScores, within_one_drop: int)`, and `replay_comparison(rows, config: str) -> ReplayComparison | None`. It returns `None` when no row carries `<config>_replay`. `within_one_drop` is `in_sample.within_one.k - replay.within_one.k`. `score_set_a` accepts a replay key as its `config`.
  - **The loader's replay rule (spec C425):** every row of a results file carries the same replay keys. `load_run` refuses a file where they differ, at the first row whose replay keys differ from the file's first row, with the message `replay results must be the same on every row (C425)`, as Set B's same-variants rule does. So a replay is always compared over the same photos, and `score_set_a(rows, "<config>_replay")` never meets a row without the key.
- [x] **Step 1: Write the failing tests:**
  - `test_landmark_agreement`: wheels at `hub`/`hub` and `hub`/`rim_top`, a body at `door_sill`/`door_sill`, and a person at `knee`/`knee` give `wheel Rate(1, 2)`, `body Rate(1, 1)`, `person Rate(1, 1)` and `all Rate(3, 4)`.
  - `test_landmark_agreement_counts_unanswered_and_unmatched` (Review Focus 3):
    - an M8 wheel on a box the answer lacks gives `wheel Rate(0, 1)` and `unanswered == 1`
    - an M8 label with `box_id: null` gives `unmatched == 1` and adds nothing to `n`
    - a row whose `answer` is null adds nothing at all
  - `test_landmark_agreement_skips_excluded_rows` and `test_m8_without_a_landmark_is_left_out`.
  - `test_vehicle_type_matrix`: `sedan_hatch`/`sedan_hatch` twice and `pickup`/`unknown` once give `(("pickup", "unknown", 1), ("sedan_hatch", "sedan_hatch", 2))`.
  - `test_false_flood_rate`:
    - five A-neg rows (a level, NFS, a refusal, a failure and a level) give `levels == 2`, `false_flood == Rate(2, 5)`, `no_flood_seen == 1`, `refused == 1` and `failed == 1`
    - a duplicate row is left out
    - `surface="dry"` keeps only the dry rows
  - `test_correct_refusals`: dark (refused), blurry (refused), dark (a level), dark (failed), `ok` (refused) and an unmarked `null` (refused) give `n == 4`, `correct == Rate(2, 4)` and `failed == 1`, with the reasons counted.
  - `test_subsets`: rows tagged `splash` and `reflection`, plus a `waist deep` row, give `reflection`, `splash` and `tire_or_deeper`, in that order, each with its own n, coverage, under and passability.
  - `test_baseline_ties`: labels knee ×3, gutter ×3 and tire ×1 give `knee` (a tie goes to the deeper level); classes NPLV ×3, PATV ×3 and NPATV ×1 give `NPLV` (a tie goes to the stricter class); no labelled rows give `(None, None)`.
  - `test_baseline_on_the_hand_computed_set`, on Task 3's ten-row set with its `landmark` results:
    - `baseline_from_rows` gives `("knee", "NPATV")`. Knee appears twice among the scored levels; PATV and NPATV tie at 3 among the stated classes, and NPATV is stricter.
    - `score_baseline(rows, "landmark", "knee", "NPATV")` gives `exact == Rate(2, 6)`, `within_one == Rate(3, 6)`, `under == Rate(2, 6)` (A03 and A09), `passability == Rate(2, 6)`, `caught_nplv == Rate(2, 2)` and `caught_npatv == Rate(2, 2)`.
    - `caught(rows, "landmark")` gives `(Rate(2, 2), Rate(1, 2))`: A03's "no flood seen" reads PATV.
  - `test_by_level`: on the same set, `knee` gives `LevelRow("knee", 2, 2, 1, 2, 1)`, and `waist` gives `LevelRow("waist", 1, 0, 0, 0, 0)` (A06 failed).
  - `test_replay_comparison`: rows whose `landmark` results put 5 of 6 within one level, and whose `landmark_replay` results put 2 of 6, give `within_one_drop == 3`; rows without replay results give `None`.
  - `test_replays_are_the_same_on_every_row`, in `test_rows.py` (C425): a development `set_a.jsonl` with `landmark_replay` on rows 1 and 3 of 3 is refused at line 2, with a message naming the rule; with it on all three rows, or on none, the file loads.
- [x] **Step 2:** Run the tests. Expected: FAIL.
- [x] **Step 3:** Implement the functions in `metrics.py`.
- [x] **Step 4:** Run the tests. Expected: PASS.
- [x] **Step 5:** Run the leak checks, then commit `feat(eval): add landmark agreement, A-neg, quality and subset scores`.
  - **Evidence:** `32a16ae`. RED: `ImportError` for the new names, and the loader accepting a partial replay file; then 177 passed with `-W error`, and 29 single-rule mutations were each caught. Checks clean. Review: Approved (w4.md, 9:04 PM).

### Task 5: Set B, Set D and latency

**Files:**
- Modify: `eval/scoring/metrics.py`
- Test: `eval/tests/test_wheels.py`

**Interfaces:**
- Consumes: `WheelRow`, `Estimate` (Task 2); `Rate` (Task 3).
- Produces, in `scoring.metrics`:
  - `WheelScores(variant: str, wheels: int, measured: Rate, median_error: Decimal | None, worst_error: Decimal | None, envelope: Rate, sam_water_found: Rate)`
    - The errors are `|depthInPoint − true_depth_in|`, over measured wheels.
    - `envelope` counts measured wheels with `depthInMin ≤ true_depth_in ≤ depthInMax`, over measured wheels (MS6E-Q1, item 4).
    - `sam_water_found` is over all wheels.
  - `score_wheels(rows: Sequence[WheelRow], variant: str) -> WheelScores`. The median of an even count is the mean of the middle two, exact in `Decimal`.
  - `wheel_groups(rows, by: str) -> tuple[tuple[str, tuple[WheelRow, ...]], ...]`, where `by` is `vehicle_type` or a bin name. Groups are sorted, and rows without that bin are left out.
  - `measured_errors(rows, variant: str) -> tuple[Decimal, ...]`, sorted, for the chart
  - `LatencyScores(n: int, median: Decimal | None, p95: Decimal | None)` and `score_latency(samples: Sequence[tuple[str, Decimal]]) -> LatencyScores`, where p95 is the nearest rank: the `ceil(0.95 × n)`-th smallest value
- [x] **Step 1: Write the failing tests:**
  - `test_hand_computed_wheels`, on five wheels:

    | crop | true depth | measured | point | envelope | error | inside? |
    |---|---|---|---|---|---|---|
    | C1 | 10 | yes | 11 | [9, 12] | 1 | yes |
    | C2 | 12 | yes | 11.5 | [12.5, 15] | 0.5 | no |
    | C3 | 14 | yes | 14 | [13, 15] | 0 | yes |
    | C4 | 18 | yes | 20 | [17, 19.5] | 2 | yes |
    | C5 | 16 | no (`fail: "axis_ratio"`) | | | | |

    Expected: `measured == Rate(4, 5)`, `median_error == Decimal("0.75")` (the mean of 0.5 and 1), `worst_error == Decimal("2")` and `envelope == Rate(3, 4)`.
  - `test_envelope_bounds_are_inclusive`: a true depth equal to `depthInMin`, and one equal to `depthInMax`, both count.
  - `test_variants_are_scored_apart`: rows carrying all five variants give five different `WheelScores`.
  - `test_groups_by_type_and_bins`: two `sedan_hatch` rows and one `suv_mpv` row, two of them with `bins` `{"view": "side"}`, give the type groups `sedan_hatch` and `suv_mpv`, and a view group `side` of 2 rows.
  - `test_nothing_measured`: `measured == Rate(0, 2)`, `median_error is None` and `envelope.value is None`.
  - `test_latency_nearest_rank`: `1` to `20` seconds give `median == Decimal("10.5")` and `p95 == Decimal("19")`. One sample gives that sample as both, and none gives `None`.
- [x] **Step 2:** Run the tests. Expected: FAIL.
- [x] **Step 3:** Implement the functions in `metrics.py`.
- [x] **Step 4:** Run the tests. Expected: PASS.
- [x] **Step 5:** Run the leak checks, then commit `feat(eval): score Set B, Set D and latency`.
  - **Evidence:** `68a9329`. RED: `ImportError`; then 183 passed with `-W error`, and 28 single-rule mutations were each caught. Checks clean. Review: Approved (w4.md, 9:32 PM).

### Task 6: The release gate and the outcome rule

**Files:**
- Create: `eval/scoring/gate.py`
- Test: `eval/tests/test_gate.py`

**Interfaces:**
- Consumes: `SetAScores`, `WheelScores`, `Rate`, `fmt_rate`, `fmt_inches` (Tasks 3 and 5).
- Produces, in `scoring.gate`:
  - the constants `MEDIAN_ERROR_MAX_IN = Decimal("3")`, `MEASURED_MIN = Fraction(70, 100)`, `ENVELOPE_MIN = Fraction(80, 100)`, `COVERAGE_DROP_MAX = Fraction(10, 100)` and `PASSABILITY_DROP_MAX = Fraction(5, 100)`
  - `Check(name: str, found: str, target: str, shown: bool, passed: bool)`. `name` is one of `no_rise`, `coverage_drop`, `passability_drop`, `median_error`, `measured` and `envelope`. When a value is undefined, `shown` is `False` and so is `passed` (C406).
  - `Decision(geometry_stays: bool, inches_shown: bool, shipped: str, checks: tuple[Check, ...], reasons: tuple[str, ...])`, where `shipped` is `geometry` or `landmark`, and `reasons` holds one plain sentence per failed check
  - `decide(landmark: SetAScores, geometry: SetAScores, set_b: WheelScores | None) -> Decision`:
    - `no_rise` (MS6E-Q5, default (d)): `geometry.under.value <= landmark.under.value` and `geometry.under.k <= landmark.under.k`
    - `coverage_drop`: `landmark.coverage.value - geometry.coverage.value <= COVERAGE_DROP_MAX`
    - `passability_drop`: `landmark.passability.value - geometry.passability.value <= PASSABILITY_DROP_MAX`
    - `geometry_stays` when all three pass
    - **with `set_b` given:** `median_error <= MEDIAN_ERROR_MAX_IN`, `measured.value >= MEASURED_MIN` and `envelope.value >= ENVELOPE_MIN`. **Without it,** those three checks are not shown, and fail.
    - `inches_shown` when `geometry_stays` and all three Set B checks pass
    - The self-check's extra row never reaches `decide`, so it can't be chosen. When geometry was dropped before the freeze (C418), `decide` isn't called (Task 8).
- [x] **Step 1: Write the failing tests.** Each builds `SetAScores` and `WheelScores` from small row sets with Tasks 3 and 5's functions.
  - `test_numbers_match_rules_md`: `rules_md.section(8)` contains `≤ **3 in**`, `**70%**`, `≥ **80%**`, `**10 percentage points**` and `**5 percentage points**`, matching the constants.
  - `test_geometry_stays_with_inches`: no rise, small drops, and a Set B of 25 wheels (20 measured, a 2 in median error, 18 of the 20 inside their envelope) give `geometry_stays`, `inches_shown` and `shipped == "geometry"`.
  - `test_geometry_stays_without_inches`, parametrized over each Set B target missed by one wheel: `geometry_stays`, but no `inches_shown`, and `reasons` names the target.
  - `test_a_higher_rate_drops_geometry`: `under` of 3/15 with geometry against 3/16 without (the same count, a higher rate) gives `shipped == "landmark"`.
  - `test_a_higher_count_drops_geometry`: `under` of 4/26 with geometry against 3/16 without (a lower rate, one more underestimated photo) gives `shipped == "landmark"`.
  - `test_each_boundary_passes`, with one scenario per boundary, everything else comfortably passing. Each uses a pair where float subtraction would get it wrong:
    - a coverage fall of exactly 10 points, 8/20 to 6/20 (in floats, `0.4 - 0.3` is `0.10000000000000003`)
    - a passability fall of exactly 5 points, 20/20 to 19/20 (in floats, `1.0 - 0.95` is `0.050000000000000044`)
    - a median of exactly `3.00`; exactly 70% measured (14/20, with 12 of the 14 inside their envelope); exactly 80% envelope (8 of 10 measured wheels inside)
  - `test_each_boundary_just_missed_fails`, again one scenario per boundary: coverage 8/20 to 5/20, passability 20/20 to 18/20, a median of `3.01`, 13/20 measured, and 7 of 10 inside. Each fails its own check. For the three Set A guards, `geometry_stays` is `False`.
  - `test_undefined_rate_drops_geometry` (Review Focus 2): geometry answering no Set A photo gives `no_rise` with `shown False`, and `shipped == "landmark"`.
  - `test_no_set_b_means_no_inches`: `set_b=None` gives `inches_shown False`, and the reasons say Set B wasn't run.
  - `test_rates_compare_exactly`: geometry's `under` of 2/6, against landmark's 1/3 with a count of 2 against 1, fails only on the count. `under` of 1/3 against 1/3 passes.
- [x] **Step 2:** Run the tests. Expected: FAIL.
- [x] **Step 3:** Implement `gate.py`. `found` and `target` are display strings, such as `2 of 17 (11.8%)` and `at most 10 points`.
- [x] **Step 4:** Run the tests. Expected: PASS.
- [x] **Step 5:** Run the leak checks, then commit `feat(eval): decide the release gate and the outcome rule`.
  - **Evidence:** `30c097f`. 206 passed with `-W error`, and 35 of 36 mutants were caught (the survivor is equivalent at any realistic n). Checks clean. Review: Approved (w4.md, 10:26 PM). RED, run Oct 29 at 9:06 PM because the ledger didn't record it: `test_gate.py` from `30c097f` on `68a9329`'s `eval/` fails collection with `ModuleNotFoundError: No module named 'scoring.gate'` (exit 2).

### Task 7: The charts

**Files:**
- Create: `eval/scoring/svg.py`
- Test: `eval/tests/test_svg.py`

**Interfaces:**
- Consumes: `LEVELS` (Task 1); `SetAScores.matrix` (Task 3); `measured_errors` (Task 5).
- Produces, in `scoring.svg`:
  - `level_matrix_svg(matrix: Sequence[tuple[int, int, int]], *, title: str, description: str) -> str`
  - `error_plot_svg(errors: Sequence[Decimal], *, target: Decimal, title: str, description: str) -> str`
- **Design (the dataviz skill; spec C410):**
  - **Every SVG** has `role="img"` and `aria-labelledby` pointing at its `<title>` and `<desc>`, and uses the system sans (`system-ui, -apple-system, "Segoe UI", sans-serif`). A `<style>` defines the colour roles as CSS variables, and a `@media (prefers-color-scheme: dark)` block redefines them:
    - **Light:** surface `#fcfcfb`, primary ink `#0b0b0b`, secondary ink `#52514e`, muted `#898781`, gridline `#e1e0d9`, axis `#c3c2b7`.
    - **Dark:** surface `#1a1a19`, ink `#f0efec`, secondary `#c3c2b7`, muted `#898781`, gridline `#2c2c2a`, axis `#383835`.
  - **The level matrix:**
    - **Layout:** rows are the alert's levels, deepest at the top, under the axis title "Alert's level (MMDA or city)". Columns are "no flood seen", then the levels from shallowest, under "Lusot's level".
    - **Shading:** a count shades its cell with a sequential blue ramp chosen for each mode and validated (C410).
      - **Light:** steps 250, 400, 550 and 700 (`#86b6ef`, `#3987e5`, `#1c5cab`, `#0d366b`).
      - **Dark:** steps 600, 450, 300 and 150 (`#184f95`, `#2a78d6`, `#6da7ec`, `#b7d3f6`), lighter as the count rises.

      The step for count `c` is `steps[ceil(4 * c / max_count) - 1]`, so the largest count always takes the last step. The fills are per-step CSS classes that the dark block redefines, with no fill written inline on a cell. A zero cell stays the surface colour, with no number. (The first ramp, steps 100 to 700 in both modes, failed the validator's light-end contrast in both modes, so Task 7 changed the steps.)
    - **Labels:** each non-empty cell shows its count. The ink is chosen by APCA: in light mode `#0b0b0b` on step 250 and `#ffffff` on 400, 550 and 700; in dark mode `#ffffff` on 600 and 450 and `#0b0b0b` on 300 and 150. Each cell has a `<title>` such as `alert knee, Lusot half_tire: 2`.
    - **Marks:** the diagonal cells are outlined with a 1 px axis-coloured stroke. Because rows run deepest at the top and columns shallowest at the left, the diagonal rises from the bottom left to the top right. The underestimates, where Lusot reads shallower than the alert, sit above and to the left of it, and that area is labelled "shallower than the alert".
  - **The error plot:**
    - one 8 px dot per measured wheel, in blue (`#2a78d6` light, `#3987e5` dark), sorted, against inches on one y axis
    - a solid 1 px reference line at `target`, labelled from `target` itself (`release-gate target: 3 in` today), since M18 may change the number
    - the median as a short horizontal tick, labelled `median`
    - each dot with a `<title>` such as `wheel 3: 0.75 in`
    - gridlines as solid hairlines
  - **Determinism:** coordinates are written with at most 2 decimals, attributes always come in the same order, and there are no random ids, so the output is the same every time.
- [x] **Step 1: Write the failing tests:**
  - `test_level_matrix_parses`:
    - `xml.etree.ElementTree.fromstring` accepts it, and the root is `{http://www.w3.org/2000/svg}svg` with `role="img"`
    - it has one `title` and one `desc`
    - each non-zero count appears once as text, and no `0` cell text appears
    - there are 9 × 10 cells, and every non-empty cell has a `<title>`
    - "MMDA's level" doesn't appear
  - `test_shallower_label_sits_above_the_diagonal`: the "shallower than the alert" text's position lies above and left of the diagonal; for example, its x is left of the top row's diagonal cell and its y is above the bottom row
  - `test_error_plot_parses`: one `circle` per error, each with a `<title>`; a line labelled with the target, where `target=Decimal("2.5")` gives `2.5 in`; and the median tick.
  - `test_charts_are_deterministic`: two calls give equal strings, for both charts.
  - `test_dark_mode_and_no_dashes`: each chart contains `prefers-color-scheme: dark` and no `stroke-dasharray`.
  - `test_empty_inputs`: an empty matrix and an empty error list still give valid SVG, which says "no answered photos" or "no measured wheels".
- [x] **Step 2:** Run the tests. Expected: FAIL.
- [x] **Step 3:** Implement `svg.py`, escaping text with `xml.sax.saxutils.escape`.
- [x] **Step 4: Check the colours** with the dataviz skill's validator (Node 22). The skill's base directory is in the controller's brief.
  - `node <dataviz>/scripts/validate_palette.js "#86b6ef,#3987e5,#1c5cab,#0d366b" --ordinal --mode light`, and `"#184f95,#2a78d6,#6da7ec,#b7d3f6" --ordinal --mode dark --surface "#1a1a19"`
  - `node <dataviz>/scripts/validate_palette.js "#2a78d6" --mode light`, and `"#3987e5"` with `--mode dark`

  Record each result in the task report. A FAIL changes the colour step, never the check. A contrast WARN is met by the counts and the table twins, under the skill's relief rule.
- [x] **Step 5:** Run the tests. Then write one matrix and one error plot into the session's scratchpad, open each with the Playwright plugin at its `file://` URL (never claude-in-chrome), take a screenshot, and look for label collisions and overflow. Expected: PASS, with nothing clipped.
- [x] **Step 6:** Run the leak checks, then commit `feat(eval): draw the level matrix and the Set B error chart`.
  - **Evidence:** `c44ad0e`, fix round `001f0a1`. RED: `ModuleNotFoundError`; then 220, and after the fix 221, passed with `-W error`; 14 planted defects caught. The dataviz validator passed all 4 runs. The Playwright plugin blocks `file:` URLs, so each scratch SVG was opened through a `data:` URL with the same bytes; the screenshots showed no collision or overflow, and the plugin's `.playwright-mcp/` folder was deleted before the commit. Checks clean. Review: fixed, then re-reviewed clean (w4.md, 11:31 PM).

### Task 8: The report and the summary

**Files:**
- Create: `eval/scoring/report.py`
- Test: `eval/tests/test_report.py`

**Interfaces:**
- Consumes: everything from Tasks 1 to 7, including `fmt_rate`, `fmt_inches`, `excluded_set_a`, `excluded_a_neg` and `left_out_of_passability` (Task 3); `Run` (Task 2).
- Produces, in `scoring.report`:
  - `build_report(run: Run, *, first_run: Run | None = None) -> dict[str, bytes]`. The keys are file names: `report.md`, `summary.json`, `level-matrix-<config>.svg` for each configuration present, and `set-b-errors.svg` when Set B exists. The values are UTF-8, with `\n` line endings and a final newline. `first_run` is given only when building a rerun's report (C421).
  - `build_review(run: Run) -> bytes | None` (spec C426): `review.csv` for a development run, and `None` for a sealed one. It is written with `csv.writer`, UTF-8, `\r\n` line endings, and one row per development Set A then A-neg photo, sorted by id. Its columns, in order:
    - `set`, `photo_id`, `event_id`, `excluded` (the reason, or empty)
    - `alert_level`, `alert_class` (mapped, or empty)
    - for each configuration present, `<config>_result` (the level, `no_flood_seen`, `refused:<reason>` or `failed:<reason>`), `<config>_class` (as `lusot_class` gives it, so "no flood seen" shows `PATV`) and `<config>_landmark` (from `Result.landmark`)
    - `m8_agreement` (`k of n`, or empty), and `m8_detail`, such as `wheel 3: hub/rim_top; person 5: knee/knee`
    - `rene_verdict` and `rene_note`, both empty
- **`report.md`'s sections,** in spec §4.4's order, with these exact headings:
  - `# Lusot evaluation report`
  - `## Reported first`, `## Release gate`
  - `## Set A: every metric`, `## Baseline`, `## By the alert's level`, `## Set A: level matrices`, `## Landmark agreement`
  - `## A-neg: flood-free photos`, `## Correct refusals`, `## Subsets`
  - `## Set B`, `## Set D`, `## Latency`
  - `## Exclusions`, `## Frozen versions and data`, `## Rebuild this report`
  - then the footer
- **What the sections hold:**
  - **The opening paragraph** of a sealed run says the frozen pipeline ran once on the sealed sets, on the run's date. It says the figures are agreement with the labels MMDA and the cities posted, mapped by `eval/rules.md` §2 (the version loaded) before any result was seen. It adds that, with samples this small, every figure is indicative and carries its n.
  - **A development report** differs in three ways:
    - it opens with `# Lusot evaluation report (development data)` and says the data is development data, not the sealed run
    - its gate section is titled `## Outcome rule on development data`, and says it sets geometry's live default (C309) and isn't the release gate
    - it adds `## Vehicle types (development)` after landmark agreement
  - **A rerun's report** (C421) opens by saying it is `eval/rules.md` §10's one disclosed rerun, gives `rerun_reason`, and adds `## First run, for comparison`, with the first run's "Reported first" and gate rows, before the exclusions.
  - **With geometry dropped** (C418), "Reported first" has one configuration. The gate section says geometry was dropped before the freeze, gives the reason, and says no inches show.
  - **Without Set A** (a development run of Set B alone, MS3b's D2), "Reported first", the gate and the Set A sections each read `Not run in this results folder.`, `decide` isn't called, and `summary.json` holds nulls for Set A and the gate.
  - **A synthetic fixture** (C422) opens with `# Lusot evaluation report (synthetic test data)` and the line `Synthetic test data for the harness's own tests. These are not Lusot's results.`, in place of the opening paragraph.
  - **Configuration labels:** "Landmark alone", "Landmark plus geometry", and "Landmark plus geometry, without the self-check". The shipped one comes first in "Reported first" and is marked `(ships)`.
  - **The self-check line** reads `Self-check: off (decided <self_check_decided>, MS3).`, or `Self-check: on (decided …). Its extra row, geometry without the self-check, is reported but never chosen (eval/rules.md §8).` A development run without `self_check_decided` reads `decided: not recorded`.
  - **A-neg** gives the false flood rate overall, then for `wet` and `dry`.
  - **Replay (C425):** on a development run with replay results, "Set A: every metric" gets a column for each `<config>_replay`, labelled with its configuration's name plus `(replay)`. A line per configuration then gives the within-one counts both ways and the difference, such as `Within one level: 5 of 6 in-sample, 2 of 6 in replay (3 fewer photos).`
  - **"Baseline" (C424)** names the two constant answers, and says where they came from: `run.json`, or "computed from these development rows". A table gives, for each configuration and then for the baseline scored on that configuration's rows: exact (marked "shown, not compared"), within one level, underestimation, passability agreement, and the NPLV and NPATV photos caught. Then one plain sentence per comparison where Lusot is behind, such as `The baseline's within-one agreement is higher: 3 of 6 against 2 of 6.`
  - **"By the alert's level"** has a table with one row per level present: n, answered, exact, within one level and underestimated, as counts. A row with n of 5 or more also gives the three percentages.
  - **Verdict words:** the report never writes "overfit" or "underfit" in any form. It states numbers.
  - **A missing set** gets its heading and the line `Not run in this results folder.`. Missing latency instead reads `Latency wasn't measured in this run.` (C416).
  - **Every metric line or table row** shows k and n through `fmt_rate`, or `n = N` beside a count, a median or a kappa.
  - **The Set B table** has one row per variant present, then one per vehicle type and one per bin value for `geometry`, plus the `sam_water_found` line. Set D gets the same table and groups.
  - **"Exclusions"** lists Set A's exclusions and A-neg's, each with its reason and count. A line then lists the photos left out of passability because their passability phrase didn't map.
  - **Each chart** is linked as `![<title>](<file>)` and followed by its table twin: a Markdown table of counts for the matrix, and the sorted errors for the error plot.
  - **"Frozen versions and data"** lists `frozen`, `datasets`, the photo and event counts, and each entry of `stops`. It ends with the line `The face blur runs before Meta receives a photo. It can miss faces that are very small, side-on, partly covered or in the dark.`
  - **"Rebuild this report"** gives `python eval/run_eval.py --from-saved`, and `python3 eval/run_eval.py --from-saved` for systems without `python`.
  - **The footer,** exactly:

    ```text
    Lusot estimates depth at one spot. It is not advice to cross. Follow MMDA and local advisories.

    Not affiliated with MMDA.
    ```
- **The copy guard** (Window 4's ruling, from Task 8's build): `build_report` raises `ValueError` when any text file it builds would hold a banned word, matched case-insensitively. The banned words are "safe" in any form, "overfit", "underfit", "accuracy", "MMDA's 9 levels" and "MMDA's level". The message is ASCII, names the file and the word, and never repeats the surrounding text. The guard catches free text copied from `run.json`.
- **`summary.json`** is `json.dumps(..., indent=2, sort_keys=True)` plus a newline. It holds:
  - `kind`, `date`, `rules_version`, `shipped`, `geometry_stays`, `inches_shown`
  - per configuration: `underestimation`, `passability`, `coverage`, `exact` and `within_one`, each `{"k", "n"}`, plus `refused` and `failed`. `exact` and `within_one` were added on Oct 29, for MS5-M1 (the cross-spec audit's row 20).
  - for Set B's `geometry` variant: `wheels`, `measured` (`{"k", "n"}`), `median_error_in` and `worst_error_in` (strings, or null), and `envelope`
  - `baseline_level` and `baseline_class`, which the freeze copies into the sealed run's `run.json` (C424)
- [x] **Step 1: Write the failing tests,** on runs built with `builders.write_run` and `rows.load_run`:
  - `test_sections_in_order`: the headings above appear in order.
  - `test_every_metric_row_has_n`: every Markdown table row, apart from header and separator rows, under "Reported first", "Release gate", the Set A, A-neg, quality, subset, Set B and Set D sections and "Latency" matches ` of [0-9]+ ` or `n = [0-9]+`. The chart twins' count tables are exempt.
  - `test_each_chart_has_its_twin`: every `![…](….svg)` link is followed, before the next heading, by a Markdown table.
  - `test_set_b_only_report`: a development run with only `set_b.jsonl` builds without error; "Reported first" reads `Not run in this results folder.`; the Set B section has its rows; and `summary.json` holds nulls for Set A.
  - `test_synthetic_report`: `synthetic: true` gives the synthetic heading and line, and no "ran once on the sealed sets".
  - `test_baseline_section`: on Task 3's set, the section names `knee` and `NPATV`, gives "computed from these development rows" for a development run without the pair, and states the within-one comparison sentence only where the baseline is ahead. A sealed run with the pair says it came from `run.json`.
  - `test_by_level_hides_small_percentages`: a level with 4 photos shows counts and no `%`, and a level with 5 shows the percentages.
  - `test_replay_columns`: a development run with `landmark_replay` gets the `(replay)` column and the within-one line with `3 fewer photos`; a run without replay results gets neither.
  - `test_no_verdict_words`: `"overfit" not in report.lower()` and `"underfit" not in report.lower()`, for runs that put Lusot behind the baseline.
  - `test_review_sheet`: `build_review` on a development run gives one row per Set A and A-neg photo, with the header above in order, an excluded row's reason, and empty `rene_verdict` and `rene_note`; on a sealed run it gives `None`.
  - `test_required_words`: the report contains `indicative`, `agreement` and both footer lines exactly. It contains neither `accuracy` nor `MMDA's 9 levels`.
  - `test_never_says_safe`: `"safe" not in report.lower()`, for runs that exercise every section.
  - `test_both_configurations_and_the_self_check_line`: with `self_check: "off"`, two configuration columns and the "off" line; with `"on"`, three columns, the extra row's label and the "never chosen" sentence.
  - `test_shipped_configuration_comes_first`: in a run where geometry's count rises, "Landmark alone (ships)" comes first.
  - `test_development_report`: the development heading, `## Outcome rule on development data` and `## Vehicle types (development)`.
  - `test_rerun_report`: `build_report(rerun, first_run=first)` names the reason and has `## First run, for comparison` with the first run's three headline rates.
  - `test_geometry_dropped_report`: one configuration, and the gate section's dropped sentence with its reason.
  - `test_report_with_empty_sets` (Review Focus 2): `a_neg=[]`, every Set A photo refused, and no Set D give "0 of 0 (undefined)" lines and `Not run in this results folder.`, and nothing raises.
  - `test_report_ignores_row_order` (Review Focus 1): shuffled rows give byte-identical output for every file.
  - `test_summary_json`: it parses, its keys are sorted, and `shipped` and the Set A rates match the report's.
  - `test_exclusions_listed`: each excluded Set A and A-neg id appears with its reason, the counts add up to the number excluded, and a photo whose passability phrase didn't map is listed on the passability line.
- [x] **Step 2:** Run the tests. Expected: FAIL.
- [x] **Step 3:** Implement `report.py`. Rows are sorted by id before anything is written, and no value comes from the clock.
- [x] **Step 4:** Run the tests. Expected: PASS.
- [x] **Step 5:** Run the leak checks, then commit `feat(eval): write the evaluation report and its summary`.
  - **Evidence:** `c6bd75b`, pre-review fixes `ad82c29`. 249, then 250, passed with `-W error`; 22 planted defects caught; the same bytes on Python 3.10, 3.11 and 3.13. Checks clean. Review: Approved (w4.md, 2:55 AM Oct 29). RED, run Oct 29 at 9:06 PM because the ledger didn't record it: `test_report.py` from `c6bd75b` on `8234395`'s `eval/` fails collection with `ModuleNotFoundError: No module named 'scoring.report'` (exit 2).

### Task 9: The one command, and the fixture it rebuilds

**Files:**
- Create:
  - `eval/run_eval.py`
  - in `eval/tests/fixtures/small_run/`: `run.json`, `set_a.jsonl`, `a_neg.jsonl`, `set_b.jsonl`, `latency.jsonl`, and the report files that `--write` creates in its `report/`
- Test: `eval/tests/test_run_eval.py`

**Interfaces:**
- Consumes: `rows.load_run`, `RowError` (Task 2); `SealedPath`, `refuse_sealed` from `scoring.paths` (Task 2); `build_report` (Task 8), whose `summary.json` supplies the printed figures; `LABEL_WORDS` (Task 1).
- Produces, in `eval/run_eval.py`:
  - **Its own folder on the path:** before importing `scoring`, it puts `Path(__file__).resolve().parent` first on `sys.path` when it isn't there, so `python -I eval/run_eval.py` works
  - **Imports by module:** `from scoring import rows`, calling `rows.load_run`, so a test that patches `scoring.rows.load_run` patches what `run_eval` calls
  - `DEFAULT_RESULTS = Path(__file__).resolve().parent / "results"`
  - **The sealed guard is imported, not redefined:** `main` calls `scoring.paths.refuse_sealed` itself, first, so the loader's own call (Task 2) is a second guard for other callers
  - `main(argv: list[str] | None = None) -> int`:
    - **Arguments:** `--from-saved`, `--results DIR` (default `DEFAULT_RESULTS`), `--write`, and `--label-words`.
    - **`--label-words`** prints `sorted(LABEL_WORDS)`, one per line, and returns 0.
    - **Otherwise `--from-saved` is required.** The order is fixed: refuse a sealed path first, before any read; load; build; then write the files to `<results>/report/`, or compare them. If `<results>/rerun/run.json` exists, it does the same for the rerun, with `first_run` set to the main run (C421).
    - **Comparing** reads each committed file and turns `\r\n` into `\n` on both sides. It reports any built file that differs or is missing, and any extra `.md`, `.json` or `.svg` file in a `report/` folder. It never reads or reports `review.csv`.
    - **The review sheet (C426):** with `--write` on a development run, `build_review`'s bytes go to `<results>/report/review.csv` only when that file doesn't exist yet. Otherwise the run prints `review.csv kept (it may hold Rene's notes)` and leaves it alone.
    - **Exit codes:** 0 when identical or written; 1 when different; 2 for a sealed path, a `RowError`, a `ValueError` from `build_report` (Task 8's copy guard, or C421's `first_run` without `rerun_reason`), a missing results folder, or a run without `--from-saved` or `--label-words`. A `ValueError` prints `invalid: <its ASCII message>`.
    - **Printed lines,** ASCII only, with 12-digit runs masked: the results folder, then from the `summary.json` just built, the run's kind and date, each configuration's three headline rates and the gate's decision (or `Set A: not run`). They end with `report: N files identical`, `report: differs: <names>`, `refused: path inside a folder named sealed`, or `invalid: <file>:<line>: <what>`.
- **The fixture** is hand-written and synthetic:
  - a `sealed` run with `synthetic: true` (C422), `freeze_commit` `abcdef0123456789abcdef0123456789abcdef01`, `self_check: "off"`, `baseline_level: "knee"` and `baseline_class: "NPLV"`
  - 12 Set A rows, covering every kind of result and at least four exclusion reasons, one of them `conflicting alerts`
  - 4 A-neg rows, both wet and dry
  - 8 Set B rows over 4 crops (two wheels each), with the four variants `geometry`, `geometry_uncalibrated`, `known_waterline` and `known_waterline_uncalibrated`
  - 5 latency rows

  Its report is created once with `--write` and committed.
- [x] **Step 1: Write the fixture's rows, then the failing tests:**
  - `test_refuses_sealed_paths`, parametrized over `tmp_path/"sealed"`, `tmp_path/"a"/"Sealed"/"x"`, `tmp_path/"sealed"/"sub"/".."` and `tmp_path/"sealed"/".."/"x"`:
    - `main(["--from-saved", "--results", str(p)]) == 2`
    - the output says `refused: path inside a folder named sealed`
    - nothing is created
    - the loader is never called (`scoring.rows.load_run` is patched to fail if called)
  - `test_from_saved_is_required`: `main([]) == 2`.
  - `test_label_words`: `main(["--label-words"]) == 0`, and its output lines equal `sorted(LABEL_WORDS)`.
  - `test_rebuilds_the_fixture_identically`: `main(["--from-saved", "--results", <fixture>]) == 0`, and the output ends with `report: N files identical`.
  - `test_a_changed_row_gives_exit_1`: in a copy under `tmp_path`, a scored row's `geometry` result becomes `level: "waist", passability: "NPATV"`, which the loader accepts. That gives 1, and the output names `report.md`.
  - `test_set_b_only_folder`: a development folder with only `run.json` and `set_b.jsonl`, written with `--write` and then checked, gives 0, and the output says `Set A: not run`.
  - `test_review_sheet_is_written_once` (spec E11): a development folder written with `--write` gets `report/review.csv`. After a `rene_verdict` cell is filled in, a second `--write` leaves the file byte for byte the same and prints `review.csv kept`. The check without `--write` still gives 0. The sealed fixture has no `review.csv`.
  - `test_write_then_compare`: a copy without `report/` gives 0 with `--write`, then 0 without it.
  - `test_rerun_folder`: a copy with a `rerun/` folder (its `run.json` carrying `rerun_reason`), written with `--write`, rebuilds both reports with 0. Changing a rerun row then gives 1.
  - `test_invalid_input_gives_exit_2`: a broken JSON line gives 2 and `invalid: set_a.jsonl:<line>`.
  - `test_runs_isolated_from_another_folder` (Review Focus 4): `subprocess.run([sys.executable, "-I", <run_eval.py>, "--from-saved", "--results", <fixture>], cwd=tmp_path, env={"SYSTEMROOT": os.environ["SYSTEMROOT"]} if os.name == "nt" else {})` returns 0.
  - `test_no_network`: with `socket.socket.connect`, `socket.create_connection` and `socket.getaddrinfo` patched to raise, `main([... fixture])` returns 0.
  - `test_standard_library_only`: an AST walk over `run_eval.py` and `scoring/*.py` finds only imports in `sys.stdlib_module_names`, or `scoring` and its modules, and no `os.environ` or `getenv`. Each file parses with `ast.parse(source, feature_version=(3, 9))`.
  - `test_output_is_ascii` (Review Focus 4): every printed character of the runs above is below 128.
- [x] **Step 2:** Run the tests. Expected: FAIL.
- [x] **Step 3:** Implement `run_eval.py`.
- [x] **Step 4:** Create the fixture's report with `python eval/run_eval.py --from-saved --results eval/tests/fixtures/small_run --write`. Read `report.md` once in full against spec §4.4 and the Global Constraints' copy rules, and look at each SVG.
- [x] **Step 5:** Run the whole suite. Expected: PASS.
- [x] **Step 6: Run the literal command on plain Pythons** (spec E10), on the fixture. Each must exit 0:
  - `python eval/run_eval.py --from-saved --results eval/tests/fixtures/small_run`, on the laptop's own `python` (3.10.11)
  - the same with `python3` (3.11.9)
  - `uv run --no-project --python 3.9 python eval/run_eval.py --from-saved --results eval/tests/fixtures/small_run`. uv downloads CPython 3.9 once (spec §3). If that download fails, record the error; the after-merge CI step then covers 3.9.
- [x] **Step 7:** Run the leak checks, then commit `feat(eval): rebuild the report with one command`.
  - **Evidence:** `159cb7f`, pre-review fix `941743f`. RED: the module missing, then 22 failing on their own assertions; then 284, and 286, passed with `-W error`; 21 mutations caught. Step 6: `python eval/run_eval.py --from-saved --results eval/tests/fixtures/small_run` exits 0 with `report: 5 files identical` (the bare `--from-saved` reads `eval/results/`, which exists only once the sealed run's results are committed, so today it exits 2 with "no results folder"; corrected Oct 29 at the tracker's audit) on `python` 3.10.11, `python3` 3.11.9 and uv's CPython 3.9.25. Checks clean. Review: Approved (w4.md, 4:05 AM).

### Task 10: Two more label readings (MS6E-Q1, items 15 and 16)

Added on Oct 28 at 11:27 PM, after Quezon City's official road-status pages turned up labels that §2 doesn't map. The tracker found them while checking official alert text. This task runs before Task 8.

**Files:**
- Modify: `eval/scoring/labels.py` (Task 1's file)
- Test: `eval/tests/test_labels.py`

**Interfaces:**
- No signature changes.
- `LABEL_WORDS` gains `ankle` and `head`, and a committed label may hold `+` after a number (spec C420).
- `--label-words` therefore prints the two new words, and MS3b's export picks them up.

**The readings (spec C404):**
- **Item 15.** When a label's words aren't one of §2's phrases (and aren't a status), the label takes its level from its measures, as a label with no words does. Words that are a phrase still win. Words with no measure stay unmapped.
  - Two exceptions keep the label unmapped. Both are Window 4's rulings, from the implementer's edge cases.
    - **A bare number** with no unit among the words: `8 (25 cm)`. Item 11 treats an unmarked number as unmapped, and it could contradict the measure.
    - **A status word anywhere** among the words: `knee deep, subsided (19 in)`. The water may have gone down.
  - A label that is only a status still gives `status`.
- **Item 16.**
  - `head` maps to `above_chest`, as `lagpas tao` does, and takes `deep` or `level` like any phrase.
  - A `+` left in the label after its measures are removed also marks a floor: the label is unmapped unless it reads `above_chest`, so `Knee+` and `Waist+ (37+ inches)` are unmapped while `Head+` maps. A `+` on a passability label leaves the class unmapped. (This is Window 4's ruling, from Task 10's review.)
  - A number followed by `+` and a unit, or by its unit and then `+` (`13 in+`), means "at least that depth". It maps to `above_chest` when the number is over 45 in, and otherwise leaves the label unmapped. "At least 13 in" could be deeper than half tire, and a label never sets a floor.

- [x] **Step 1: Write the failing tests** in `test_labels.py`:
  - `test_measures_decide_unmapped_words` (item 15):
    - `ANKLE DEEP (9 inches)` gives `LevelLabel("level", "half_knee")`, and `Ankle Deep` gives `unmapped`
    - `knee deep (25 inches)` still gives `knee`, because words win
    - `ankle deep (61 cm)` gives `tire`, since 61 cm is 24.02 in
    - `8 (25 cm)` and `knee deep, subsided (19 in)` give `unmapped`
  - `test_head_plus` (item 16):
    - `Head+ (60+ inches)`, `Head+`, `head deep` and `head level` each give `above_chest`
    - `60+ inches`, `60 in+` and `120 cm+` give `above_chest`
    - `13+ in` and `13 in+` give `unmapped`
    - `Knee+`, `Gutter+`, `Waist+ (37+ inches)`, `knee deep +` and `+13 inches` give `unmapped`, and `map_passability("NPLV+")` gives an unmapped class
  - `test_label_words_take_ankle_head_and_plus`: `label_words_ok` passes `ANKLE DEEP (9 inches)` and `Head+ (60+ inches)`, and still refuses `Espana Maceda` and `knee deep 8:00 AM`. `head` and `ankle` are in `LABEL_WORDS`.
- [x] **Step 2:** Run the tests. Expected: FAIL.
- [x] **Step 3:** Implement the two readings in `labels.py`, and update its docstring, so it no longer says that only §2's phrases map.
- [x] **Step 4:** Run the whole suite. Expected: PASS. Task 1's drift tests still pass, because they read `eval/rules.md` toward the code only. The final review's bidirectional drift test, if it adds one, must allow `head` until v0.7 lands.
- [x] **Step 5:** Run the leak checks, then commit `feat(eval): read alert labels by their inches when the words don't map (MS6E-Q1 items 15, 16)`.
  - **Evidence:** `215c337`, `6683b6d`, fix round `ded7106`. The new cases red first; then 224 passed with `-W error`; 6 swapped-in wrong implementations caught. Checks clean. Review: fixed, then re-reviewed clean (w4.md, 12:11 AM).

**Whole branch (Oct 29, 9:05 PM, at `b0f8a5c`):** after the final review and its fix wave (`2e9a958`, re-reviewed clean) and `9ca7464`, `uv run --locked --script eval/tests/run_tests.py -W error` gives 320 passed, exit 0, and `python eval/run_eval.py --from-saved --results eval/tests/fixtures/small_run` (Python 3.10.11) exits 0 with `report: 5 files identical`.

---

## After the merge (the merging window, not this branch)

Done on `w4-independent` just before its merge, at the tracker's call (Oct 30, 7:15 AM), so CI checks them before they reach `main`. The branch first took `main` at `5c3b089` (`87fc903`, CI run 40970740214 passed). Window 4 merges it.

- [x] Add `uv run --locked --script eval/tests/run_tests.py` to `check:py` in the root `package.json`, so `npm run check` runs the eval tests.
  - **Evidence:** `npm run check` exit 0, its `check:py` ending `325 passed`.
- [x] Add the same command to `.github/workflows/ci.yml`, plus a step that runs `python eval/run_eval.py --from-saved --results eval/tests/fixtures/small_run` on Python 3.9 (for example with `actions/setup-python`, pinned to a commit SHA like the workflow's other actions).
  - **Evidence:** CI's python job runs `npm run check:py`, which now holds the command, and a new step runs `uv run --no-project --python 3.9 python eval/run_eval.py --from-saved --results eval/tests/fixtures/small_run`. uv downloads CPython 3.9, so no new action is needed. Locally: `report: 5 files identical`.
- [x] Credit the new test libraries in the README, in its existing credits style (CLAUDE.md: every third-party library is credited), each with its licence, checked in the installed wheels:
  - scikit-learn, and what its wheels bring: SciPy, joblib, threadpoolctl, NumPy, cloudpickle 3.1.2 and narwhals 2.28.0
  - pytest, if its row doesn't already cover this use, with what it brings: colorama, iniconfig, packaging, pluggy and Pygments
  - `actions/setup-python`, if CI adds it
  - **Evidence:** a scikit-learn row (BSD-3-Clause), naming SciPy, joblib, threadpoolctl and cloudpickle (BSD-3-Clause), NumPy and narwhals (MIT), read from the installed wheels' metadata. pytest's row already covers this use; its colorama (BSD), iniconfig (MIT), packaging (Apache-2.0 or BSD-2-Clause), pluggy (MIT) and Pygments (BSD-2-Clause) fall under the README's pinned-dependencies note, which now names `eval/tests/run_tests.py.lock`. No `setup-python` was added.
- [x] Add `eval/**/review.csv` and `.playwright-mcp/` to `.gitignore`. `review.csv` holds Rene's notes, and Task 7's chart check used the Playwright plugin.
- [x] `review.csv` gains the blank `claude_check` column before `rene_verdict` (spec C426, Rene's rule of Oct 29: Claude annotates first, then he reviews), with its test and the fixture's rebuild; until then the harness writes the old column set.
  - **Evidence:** `test_review_sheet` failed first, then passed; `uv run --locked --script eval/tests/run_tests.py -W error` gave 325 passed. No fixture holds a `review.csv`, since the rebuild check skips it, so nothing needed rebuilding.
- [ ] Record the changes on the board and in the day's log.

## Follow-up (Oct 30): `service_retries`

Asked by Window 3 through the tracker (Oct 30, 7:45 AM), from MS3b's Task 19 (`run_sealed.py`, `ea45ede`). MS6E-Q6 (a) retries once each photo whose analysis failed because Meta's service failed, and discloses how many were retried. The run.json contract had no field for that count, and the loader refuses any field outside the contract, so the entry point couldn't record it and the report couldn't show it. This lands on `w4-independent`, after MS6's merge (`a30bd07`), and merges into `main` after the tracker's OK. One commit: `feat(eval): record and report service_retries in run.json (MS6E-Q6)`.

- [x] **Step 1: Write the failing tests** (`test_rows.py`, `test_report.py`, `test_run_eval.py`): `service_retries` 0 and 3 load on a sealed and on a development run; `-1`, `"2"`, `True`, `2.5` (and `2.0`) are refused on both; a sealed run.json without it is refused; a development one without it reads as 0; report.md shows `Photos retried once after a Meta service failure in this run (MS6E-Q6): N.` for a sealed run with 0 and for a development run with 2, and not for a development run with 0; summary.json carries the value; and the committed fixture rebuilds byte for byte.
  - **Evidence:** the new cases failed first, each at its own assertion: the loader's accepting cases on `the manifest holds a field outside the contract`, its refusals on `assert 'run.json:0: ... the contract' == 'run.json:0: ... whole number'` (and `... be 0 or more`), and the sealed case on `Failed: the loader accepted final`. With the loader in place, the report's cases failed on `assert 0 == 1` (the line counted in the section), `KeyError: 'service_retries'` and `test_summary_json`'s extra item `'service_retries'`; the fixture's tests failed on `the manifest lacks service_retries` until its run.json gained the field.
- [x] **Step 2: The loader.** `service_retries` is checked by `_count` in `_RUN_FIELDS` (a whole number of 0 or more, so a boolean, a string, a fraction and a negative are refused), is left out of `_SEALED_OPTIONAL` and put in `_DEVELOPMENT_OPTIONAL`, and `Run.service_retries` carries it, 0 when absent. The tests' `run_json` builder gains `"service_retries": 0`, so it still holds every key a sealed run needs.
- [x] **Step 3: The report.** report.md's "Frozen versions and data" section, beside the stops table, states `Photos retried once after a Meta service failure in this run (MS6E-Q6): N.` for a sealed run, and for a development run only when N is above 0. The count covers every photo in the run (Set A, Set B and Set D), so it sits with the run's other events and not in a set's section (the review's Important 1, Step 8). It states the count and nothing else. summary.json gains `service_retries`, an integer, for every run.
- [x] **Step 4: The fixture.** `eval/tests/fixtures/small_run/run.json` gains `"service_retries": 0`, and its report was regenerated with the harness's own tool.
  - **Evidence:** `python eval/run_eval.py --from-saved --results eval/tests/fixtures/small_run` gave `report: differs: report.md, summary.json` before; `--write` gave `report: 5 files written`; then it gave `report: 5 files identical`, also under `uv run --no-project --python 3.9`. The fixture's report changed by the one line and the one summary key.
- [x] **Step 5: `--rules-version`**, added at the controller's request for Window 3. `python eval/run_eval.py --rules-version` prints `RULES_VERSION` (`eval/scoring/__init__.py`) and a newline and nothing else, then exits 0. It needs no `--results` and reads nothing from disk, as `--label-words` does. MS3b's `run_sealed.py` doesn't import `eval/`, so it will run this by subprocess before it pays for the sealed run, and compare the output with its own `rules_version`.
  - **Evidence:** the two new tests failed first on `assert 2 == 0` (`invalid: unrecognized arguments: --rules-version`), then passed. One checks the output in-process with the loader and the file-reading `Path` methods made to fail, the other under `python -I` from an empty folder.
- [x] **Step 6: Checks.**
  - **Evidence:** `uv run --locked --script eval/tests/run_tests.py -W error` gave 344 passed (325 before; 19 new). Eight swapped-in wrong implementations were each caught: the count checked as a plain integer, the count optional in a sealed run, an absent count read as nothing, the line shown for a development run with 0, the line hidden for a sealed run with 0, a summary without the count, a trailing space after the version, and the flag reading the results folder first. Ruff format is clean on the seven changed files, and ruff check is clean on them with `--target-version py39`. With the project's default target (3.13) it also reports two UP047 in `rows.py`'s `_read` and `_no_repeats`, which this change doesn't touch and which its fix would break: they need Python 3.12 syntax, and the rebuild must run on 3.9. `npm run check` exit 0 in 307 s, its `check:py` ending `344 passed` for this harness; `uv run --no-project --python 3.9 python eval/run_eval.py --from-saved --results eval/tests/fixtures/small_run` gave `report: 5 files identical`.
- [x] **Step 7: A wheel with no answer from Meta stays out of the water-found rate** (a second commit, at the controller's request for Window 3: MS3b's Task 19 exports a Set B crop or Set D photo whose Meta call failed twice with every variant `{measured: false, fail: model_error}`, which a strict boolean `sam_water_found` would have counted as "SAM found no water"). The loader accepts `sam_water_found: null` only on a row whose every variant is that estimate, and refuses it on any other row; `score_wheels` rates SAM's water over the wheels that have an answer and counts the rest as `no_answer`; report.md's Set B and Set D sections end the water line with `; left out: N with no usable answer from Meta (model_error).` (Step 8 words it so); summary.json's `set_b` gains `sam_water_found` (`{k, n}`) and `no_answer`. The wheel stays in `wheels` and counts as unmeasured.
  - **Evidence:** the new cases failed first, each at its own assertion (`sam_water_found must be true or false` where a null should load, `AssertionError: measured` where the null-rule message was expected, `TypeError: WheelScores.__init__() got an unexpected keyword argument 'no_answer'`, and the report and summary assertions); then `uv run --locked --script eval/tests/run_tests.py -W error` gave 348 passed (344 before). The fixture's numbers didn't change (7 of 8 wheels, as before), but its report gains the clause and its summary the two keys, so it was regenerated with `--write` (`report: 5 files identical` after, also on 3.9). Seven swapped-in wrong implementations were each caught: a null accepted on any row, a null accepted on a row with an answered variant, the denominator keeping the unanswered wheel, the unanswered wheel counted as water found, the count always 0, the report line without the count, and the summary without it. Ruff format is clean and ruff check is clean with `--target-version py39` (the two UP047 noted in Step 6 remain). `npm run check` exit 0 in 766 s.
- [x] **Step 8: Fix round for the review of Steps 1 to 7** (Oct 30; Important 1 and Minors 1, 2 and 4). The retries line moved from "Set A: every metric" to "Frozen versions and data", beside the stops table, worded `Photos retried once after a Meta service failure in this run (MS6E-Q6): N.` (still always in a sealed report, and in a development one only when N is above 0); the tests that claim an absent `service_retries` now build a run.json that lacks it; the water line says `with no usable answer from Meta (model_error)`, since `model_error` also covers an invalid answer; and `--rules-version` and `--label-words` are an argparse mutually exclusive group, with the refusal that asks for `--from-saved` naming both.
  - **Evidence:** the changed and new tests failed first on their own assertions (the line's section and wording, the water line's wording, `AssertionError: ('--rules-version', '--label-words')` where the pair should be refused); then `uv run --locked --script eval/tests/run_tests.py -W error` gave 349 passed (348 before). The fixture's report was regenerated with `--write` (the line moved, and the water clause changed; no figure changed) and gave `report: 5 files identical`, also on 3.9, where `--rules-version --label-words` gives `invalid: argument --label-words: not allowed with argument --rules-version`. Ruff format and `ruff check --target-version py39` are clean. `npm run check` exit 0.

### The freeze checklist: the sealed entry point's flags

The plan has no freeze checklist, so the entry point's flags are recorded here, in the section nearest the freeze (spec §4.5 item 5, §4.6). `run_sealed.py` (MS3b Task 19, `ea45ede`) takes:
- `--baseline SUMMARY`: the last development report's `summary.json`, which supplies `baseline_level`, `baseline_class` and `rules_version`
- `--self-check-decided`, which is required
- `--geometry-default`, `--dropped-reason` and `--datasets`, as `dev_eval` has them

It also has to write `service_retries` into the sealed run.json, since a sealed run without it is refused. MS3b's `export.results_manifest` doesn't carry it yet. Before it pays for the run, it can compare its `rules_version` with `python eval/run_eval.py --rules-version`, run by subprocess.

The freeze tags (`freeze-1`) only once those flags are in `main` with their tests.

## When `eval/rules.md` becomes v0.7 (the same commit as the rules change)

Done in this commit (Oct 30): Rene approved v0.7 ("Yes, include v0.7", delegated to the tracker's double-check, relayed Oct 30, 8:06 AM), including items 4.5 and 7.8, once four fixes were made to the proposal. The rules and the harness landed together in `feat(eval): apply eval/rules.md v0.7, with the harness`.

Rene approved v0.7, and the log owner applied it. The harness changed in the same commit, or CI would fail:
- [x] Set `RULES_VERSION = "0.7"` in `eval/scoring/__init__.py`, and `rules_version: "0.7"` in the fixture's `run.json`.
  - **Evidence:** with `eval/rules.md` at v0.7 and the code at 0.6, `test_rules_version_matches_rules_md` failed on `assert '0.6' == '0.7'`; after the change it passed. The fixture's `run.json` says "0.7" too, since the loader refuses any other version, and five fixture tests in `test_run_eval.py` (`test_rebuilds_the_fixture_identically` and four more) then failed on `report: differs: report.md, summary.json` until the report was regenerated (below).
- [x] Update the §2 drift tests for v0.7's table: its row count, and the `head` row (item 2.7). Make the phrase test two-way (C408), so a code phrase that §2 doesn't list fails.
  - **Evidence:** `test_label_table_matches_rules_md` failed first on `assert 12 == 11`, and `test_label_words` on `label_words_ok('"head" (as in Quezon City's "Head+")')`; the table test now expects 12 rows and the `head` row beside "lagpas tao", both `above_chest`. `test_phrases_are_the_same_both_ways` (new) compares `_PHRASE_LEVELS` with §2's rows (a closing `deep` or `level` dropped, hyphens as spaces), `_WORDS_LEVELS` with each phrase in its three forms, and the passability codes and phrases with each row's variants. §9's `test_reasons_match_rules_md` also failed first, on `At index 5 diff: "duplicate or repost (identical files, ...` from items 9.1 and 9.2, and now splits each bullet at its first ` (`. Four wrong implementations were each caught by the new test: a code phrase §2 doesn't list, a §2 phrase the code lacks, a passability phrase §2 doesn't list, and `rules.md` without the `head` row.
- [x] Remove `ankle` and `head` from the drift test's named extras once §2 lists them.
  - **Evidence:** `ALERT_WORDS` is gone from `test_labels.py`. `head` now comes from the table's first column. `ankle` is in no table, so `test_label_words` reads its words from §2's own example, `"ANKLE DEEP (9 inches)"` (item 2.6), after asserting the example is in §2. `LABEL_WORDS == rules_words | UNIT_WORDS | {"to"} | STATUS_WORDS` holds.
- [x] Item 7.8 (approved): `report.py`'s latency sentence, column and docstring say "upload to final result" in place of "upload to pin" (spec C416).
  - **Evidence:** `test_latency_says_upload_to_the_final_result` (new) failed first on its lead and header assertions, then passed. It pins the sentence `Live tests' seconds from upload, or a sample's start, to the final result (C416).`, the column `Upload, or a sample's start, to the final result`, and that no `eval/scoring/*.py` file says "upload to pin". `report.py`'s `_latency` docstring and `metrics.LatencyScores`' docstring changed with it. Three wrong implementations were each caught: the sentence, the column and a docstring back at "pin".
- [x] Item 4.5 (approved): the report's "A-neg: flood-free photos" lead names the source: openly licensed Wikimedia Commons photos (CC0, public domain or CC BY), with a test that pins the sentence and its copy rules.
  - **Evidence:** `test_a_neg_lead_names_its_source` (new) first failed on a mistake of its own (a results folder named `sealed`, which the loader refuses, so the test's folders are named `sealed-run` and `development-run`); then the old lead failed its `lead == A_NEG_LEAD` assertion (the first wrong implementation below), and the new lead passed. It pins the whole lead, `The A-neg photos are openly licensed Wikimedia Commons photos (CC0, public domain or CC BY). Flood-free photos that got ...`, in a sealed and in a development report. Its copy rules: no "credit" (each photo's credit stays in the private manifest), no "http", no ShareAlike or "BY-SA", and no "accuracy" (the report's banned-word guard covers the rest). With no A-neg rows the section still reads only `Not run in this results folder.`. Two wrong implementations were caught: the lead without its source, and a lead that adds CC BY-SA.
- [x] The retry line's wording, since `service_retries` counts every item retried (Set A's photos, and Set B's and Set D's items; Window 3's question): report.md says `Photos and crops retried once after a Meta service failure in this run (MS6E-Q6): N.`, and the MS6 spec's `run.json` row says the count covers photos and crops alike.
  - **Evidence:** `test_service_retries_line` failed first on the old wording, then passed; one wrong implementation (the old "Photos retried once") was caught.
- [x] Regenerate the fixture's report with `--write`. Its "v0.6" lines change.
  - **Evidence:** before `--write`, `uv run --no-project --python 3.9 python eval/run_eval.py --from-saved --results eval/tests/fixtures/small_run` gave `report: differs: report.md, summary.json`; `--write` gave `report: 5 files written`; then `report: 5 files identical`. The fixture's diff is five lines of `report.md` (the A-neg lead, the latency sentence and column, "Scored by eval/rules.md v0.7.", the retries line), one of `summary.json` and one of `run.json`.
- [x] Re-run the full suite and the literal command.
  - **Evidence:** `uv run --locked --script eval/tests/run_tests.py -W error` gave 352 passed (349 before; 3 new). Ruff format and `ruff check --target-version py39` are clean on the seven changed Python files. `uv run --no-project --python 3.9 python eval/run_eval.py --from-saved --results eval/tests/fixtures/small_run` gave `report: 5 files identical`. `npm run check` was run in its three parts: `check:node` exit 0, `check:py` exit 0 (its last step `352 passed`), `check:secrets` exit 0 (gitleaks: no leaks in 437 commits; the plan-leak and account-ID scans clean).

## Done-when map

| Spec row | Task |
|---|---|
| E1 metrics | 3, 4, 5 |
| E2 kappa against scikit-learn | 3 |
| E3 gate and outcome rule | 6, 8 (geometry dropped) |
| E4 label mapping and drift tests | 1, 3, 6 |
| E5 exclusions | 3 |
| E6 the one command | 9 |
| E7 sealed paths | 9 |
| E8 the allow-list | 1, 2 |
| E9 report wording and charts | 7, 8 |
| E10 plain Pythons | 9 |
| E11 Rene's review sheet | 8, 9 |
| S1 to S6 | the sealed run (spec §4.5), not this plan |
