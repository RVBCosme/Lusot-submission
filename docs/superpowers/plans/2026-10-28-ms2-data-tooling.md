> Approved Oct 29, 2026, by Claude under Rene's delegation (PDF item 17), except MS2-Q2, which rides on eval/rules.md v0.7 (Rene's). Written before the spec's approval (D7); the executing controller reviewed it before Task 1.

# MS2 Data Tooling Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task by task, one implementer at a time, with a task review after each task and a final whole-branch review (CLAUDE.md, Workflow step 4). Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Tools that check Rene's hand-collected logs, give him the M8 labelling sheet, split Set A and A-neg by flood event into a development side and a write-once encrypted archive, audit that split, generate Set B's crops with G3's truth and seal its final cars, seal Set D, and record every dataset version. Everything is tested on synthetic data only.

**Architecture:**
- **`eval/data/` and `eval/set_b/`** hold PEP 723 uv scripts with their own locks (C200), over small single-purpose modules. Neither imports `lusot_analysis`, and files are the interface.
- **Claude's tools** (`intake`, `m8_sheet`, `audit --dev`, `generate`, `water_check`, `freeze_record`, `setc`) refuse any path inside a folder named `sealed`.
- **Rene's commands** (`split`, `generate --final`, `seal_set_d`, `audit --sealed`, `set_b_masks --final`) run only from an interactive console, after a typed confirmation, and write sealed data only into write-once 7z archives.
- **`backend/analysis/probes/set_b_masks.py`** is the one Meta caller. It sends only cars whose owner's OK is on record. It blurs faces, asks SAM for `vehicle`, `wheel` and `wheel rim` on Set B's car photos (and `floodwater` on development crops), and saves files for `generate`.

**Tech Stack:** Python 3.13 through uv 0.13.6 (`uv lock --script`, `uv run --locked --script`). The standard library for the intake, sheet, audit, Set C and records; numpy 2.5.4, opencv-python-headless 4.14.0.94 and py7zr 1.1.4 for photos, crops and archives; pytest 9.1.1; Node 22 (`node --test`) for the M8 page's script.

**Spec:** `docs/superpowers/specs/2026-10-28-ms2-data-tooling-design.md` at `fc0cd13` (calls C200 to C224, questions MS2-Q1 to MS2-Q4; C204 and MS2-Q4 as amended at 4:13 PM). It is binding. Executors read both documents. Cite the project plan as "plan §N" and never copy its text.

**Branch and start** (the tracker's build rules, Oct 28, about 3:30 PM, under Rene's delegation). Window 2 executes this plan in its worktree, `C:\Systems\Lusot\lusot-wt\meta`. The controller first commits this reviewed plan on `next-specs`, then runs `git switch -c ms2-data main` and `git merge next-specs`, which adds new files only (Task 1). Commit only on `ms2-data`. Never merge into `main` and never push. The line for the merge owner: "`ms2-data` merges into `main` after review".

**C204's deep group** is settled: the tracker confirmed reading (a) at 5:15 PM. A row is deep only when its stated `passability_raw` maps to NPLV or NPATV by `eval/rules.md` §2's passability table, which matches Window 4's v0.7 item 4.2 (`e07663c`). The stratifier only balances the split and never scores, so a deep-looking row with no stated class walks with the rest. MS2 maps no level label (C207).

**Defaults followed (D7).** Each question below follows its recommended default until Rene answers. The last column names the steps a different answer changes.

| Question | Default followed | Changes if answered otherwise |
|---|---|---|
| MS2-Q1, the password | (a), approved on Oct 29 by Claude under Rene's delegation: typed twice into Rene's own console with `getpass`; the tools write the archives | (b) or (c) replace `ask_password` (Task 2) and the archive writes in Tasks 9, 13, 16 and 18 |
| MS2-Q2, departures from `eval/rules.md` and C39 | (a): the tools follow C203, C204 (stratified), C209, C211, C212, C214, C224 and §9's duplicate rule, with one archive per sealing step | (b) changes only the items left out: C203 (Task 6), C204 (Tasks 8 and 10), C209 (Tasks 3 and 7), C211 and C212 (Tasks 14 and 15), C214 (Task 16 and R6), C224 (Tasks 6 and 7), the duplicate rule (Task 13), and the archives (Tasks 13, 16 and 18). (c) moves Tasks 13, 16 and 18 to one archive written after the last sealing input. |
| MS2-Q3, `set_b_masks` before MS3a merges | (a), approved on Oct 29 by Claude under Rene's delegation: build it now (Task 5), after telling Window 3 (Task 1, Step 4) | (b) holds Task 5 until MS3a merges |
| MS2-Q4, city offices | (a), approved on Oct 29 by Claude under Rene's delegation: official city-office pages are `poster_kind = city` | (b) narrows `places.poster_kind` (Task 6) and the guide's poster forms (Task 3) |
| MS3b-Q5, in-between waterlines (open elsewhere) | the higher mark for wheels, people and car bodies | `m8_sheet.IN_BETWEEN_RULE` (Task 4b), set before Rene labels |

## Files

**Dependency approach (C200):** every tool is a PEP 723 script with exact pins and its own `.py.lock`, run with `uv run --locked --script`. The spec leaves the test path open, so the tests run through one locked PEP 723 runner, `eval/data/tests/run_tests.py`, as MS6's C417 does for its harness. That touches no conflict file: nothing in `backend/analysis/`'s project, `package.json` or CI changes on this branch.

**New, MS2's own (no conflict):**

| File | Responsibility | Task |
|---|---|---|
| `eval/data/tests/run_tests.py`, `run_tests.py.lock` | the locked test runner, for `eval/data/tests` and `eval/set_b/tests` | 2 |
| `eval/data/tests/conftest.py`, `eval/set_b/tests/conftest.py` | put the tool folders on `sys.path` | 2 |
| `eval/data/tests/synth.py` | synthetic builders, and the audit-hook helper that records what a tool opens | 2, grows later |
| `eval/data/guards.py` | sealed-path refusal (C222), console check (C202), password and confirmation (C206), quiet errors | 2 |
| `eval/data/table.py` | CSV reading and writing, hashing, the id pattern (C221), findings | 2 |
| `eval/data/formats.py` | every file's columns and value lists, Metro Manila, consent versions (C218) | 3 |
| `eval/templates/a_neg_log.csv`, `m8_labels.csv`, `set_b_cars.csv`, `set_d_log.csv`, `consented_log.csv`, `sidewalls.csv` | header-only templates (§8) | 3 |
| `eval/data/m8_sheet.js`, `eval/data/tests/m8_sheet.test.mjs` | the M8 page's script (C208) | 4a |
| `eval/data/m8_sheet.py` | the M8 page and its command (C208) | 4b |
| `eval/data/places.py`, `eval/data/events.py` | spot, city and poster normalisation (C224, MS2-Q4); flood events (C203) | 6 |
| `eval/data/setlogs.py` | Set A and A-neg checks, matching and facts (C209, C223) | 7 |
| `eval/data/strata.py`, `eval/data/otherlogs.py`, `eval/data/intake.py` | the stated passability class and the deep row (C204); M8, M9 and sidewall checks (C208, C218); the intake command (§5.3) | 8 |
| `eval/data/photos.py`, `eval/data/archive.py` | SHA-256, dHash and `decodes`; the write-once archive (C205) | 9 |
| `eval/data/draw.py` | the stratified walk (C204) | 10 |
| `eval/data/manifest.py`, `eval/data/record_io.py` | manifest and M8 rows (C207, §5.9); the three record kinds, their builders and their writing (C216), in a module named apart from the `records/` folder | 11 |
| `eval/data/audit.py` | the audit (W18, C220) | 12 |
| `eval/data/split.py` | the split (M19, C219) | 13 |
| `eval/set_b/tires.py`, `wheels.py`, `truth.py` | tire codes, the wheel choice, G3's truth (C212) | 14 |
| `eval/set_b/water.py`, `crops.py` | the water's look and the crops (C211) | 15 |
| `eval/set_b/cars.py`, `generate.py` | the generator, development and final (C214) | 16 |
| `eval/set_b/water_check.py`, `eval/data/freeze_record.py` | the freeze check (C213); the freeze record (C216, V8) | 17 |
| `eval/data/seal_set_d.py` | Set D's seal (C217) | 18 |
| `eval/data/setc.py`, `docs/research/<date>-set-c-licences.md` | Set C manifests and FloodDET's licence check (C215) | 19 |
| each entry script's `.py.lock` | its locked dependencies (C200) | with its script |
| `eval/data/tests/test_*.py`, `eval/set_b/tests/test_setb_*.py` | one test file per module; basenames unique across both folders (pytest's default prepend import mode needs that) | each task |

**New, in MS3a's area (a conflict by the brief's rule, so it went to Rene as MS2-Q3; default (a) builds it now):** `backend/analysis/probes/set_b_masks.py` and `backend/analysis/tests/test_set_b_masks.py` (Task 5). Neither exists on MS3a's branch, and MS3b's own Set B script is a different file (`probes/set_b.py`).

**Existing, modified here** (checked against MS3a's plan and branch and Window 4's branch: neither touches them):
- `eval/templates/set_a_log.csv`: C209's three optional last columns (Task 3)
- `docs/data/set-a-collection-guide.md`: spec §8's guide items (Task 3)
- `README.md`: py7zr's credit, MS2's lock files, and any Set C data used (Task 20). Window 4's merge may add its own credit, so the merge owner may reconcile one table.

**Conflict files, unchanged on this branch:**

| File | Who changes it, and when |
|---|---|
| `backend/analysis/pyproject.toml`, `uv.lock`, `requirements.lock.txt`, `src/lusot_analysis/` | nobody here: `set_b_masks` uses what `main` has |
| `backend/template.yaml` | nobody here |
| `.claude/settings.json` | no change: the tracker's user-level deny rules (about 4:08 PM) cover MS2's paths. Task 1 checks them, and Task 20 shows the file unchanged. |
| `eval/rules.md` | Window 4's single v0.7 proposal, applied by the log owner after Rene's written OK (B.8). This plan only confirms it (Tasks 1 and 20). |
| `docs/PROGRESS.md`, `docs/log/` | Window 3, the owner since MS1 closed (D20), from the log-ready lines in Task 20 |
| `package.json` (`check:py`) | the merge owner, with the line Task 20 gives |
| `CLAUDE.md` | the window that closes MS2 (`revise-claude-md`), with the lines Task 20 gives |

## Global Constraints

- **Data:** tests use synthetic data only, made under pytest's `tmp_path`. Never read, list or search anything under `C:\Systems\Lusot\lusot-data\set_a\` or `a_neg\`, or any folder named `sealed`. Task 1's deny probes are the one sanctioned exception: names that don't exist, approved by the tracker's B.3 and its data-roles note (§5, item 4). No photo, log, manifest, mask or crop enters the repo.
- **Not in the build:** Docker builds, Gradle, AWS calls, Meta calls. `set_b_masks` is built and tested with a fake client; its live runs are later steps with their own budget lines.
- **Boundaries (C200, MS3b's C321, MS6's C400):** nothing in `eval/` imports `lusot_analysis` or MS6's `scoring`, and nothing in `backend/analysis/` imports `eval/`.
- **Sealed paths (C222):** every tool calls `guards.refuse_sealed` on every path it is given, before opening anything.
  - A path is refused when any part of it as given, or of its absolute normalised form (`os.path.normpath(os.path.abspath(p))`), names `sealed` in any case.
  - Each part is compared by its name before any `:`, with trailing dots and spaces stripped, so an NTFS stream name such as `sealed::$INDEX_ALLOCATION` is refused too.
  - It prints `refused: path inside a folder named sealed` and exits 2.
- **Rene's commands (C202):** `split`, `generate --final`, `seal_set_d`, `audit --sealed` and `set_b_masks --final`.
  - Their sealed paths must lie inside a folder named `sealed` (`guards.require_sealed`). Every other path they take is refused if it does.
  - They run in this order: the path checks on the strings alone, then `require_console()`, then any check that stats a path (an output that already exists). A run from Claude's shell therefore stops before it touches a sealed path. The typed confirmation comes before anything is written; `generate --final` runs C214's overlap check just before its password, as §5.6 orders.
  - `guards.console_ok()` holds only when, on Windows, `GetConsoleMode` succeeds on both the stdin and the stdout handle; elsewhere, when both are terminals.
  - The confirmation is the password typed twice for the three archive writers, `yes` for the other two. No agent runs these commands, ever.
  - Any exception other than `SystemExit` prints its class only (`guards.quiet`) and exits 1, so no traceback names a photo.
- **Passwords (C206):** read only with `getpass`, typed twice, never empty, held in memory only. No option, environment variable or file ever carries one. Tests use `synth.TEST_PHRASE = "test phrase for synthetic archives"`; its spaces keep gitleaks' generic rule from matching.
- **Archives (C205):** py7zr 1.1.4's `SevenZipFile(path, "x", password=..., header_encryption=True)`. That is an exclusive create, LZMA2 plus AES-256 contents, and an AES-256 header, so the names are hidden too.
  - Each archive is written in one pass, from memory (`writestr`) and from files named in the inputs (`write`).
  - No tool opens, lists, decrypts or adds to an archive. Only tests open one, with the test phrase.
- **No listing:** no tool lists, walks or searches a folder (`os.listdir`, `os.scandir`, `os.walk`, `Path.iterdir`, `Path.glob`, `Path.rglob`, `Path.walk`, the `glob` module, `shutil.copytree`, `shutil.rmtree`, py7zr's `writeall`).
  - The one exception is `setc`'s walk (§5.2), which prunes folders named `sealed`.
  - Every other file is opened by a name from a log, a file list or the command line.
  - Task 2's source test enforces this.
- **Before the split (C201):** Claude's tools read only the logs' text fields, and check that a named photo exists with a stat, never by reading its bytes. Tests prove it with `synth.opened_paths`, an audit hook that sees every `open`.
- **Output:** ids, column names, fact values, counts, sizes, hashes and timings, in ASCII.
  - Never a cell's text, a photo, a location, a link, a key or a password.
  - A problem prints as `<id> <column>: <kind>` (`row <n>` when the id itself is bad), a warning as `<id> <fact>=<value>`.
  - Rene's commands print development ids only. They name a final or sealed item by its row number.
- **Ids (C221):** every id MS2 writes matches `^[A-Z]{1,3}[0-9]{1,4}(-[0-9]{1,3}){0,2}$` (`table.is_id`).
- **Post links:** `post_url` is never fetched, opened, resolved, parsed or validated. The intake checks only that it isn't empty.
- **Environment:** no tool reads an environment variable (`os.getenv`, `os.environ.get`, `os.environ[...]` as a read) or defaults to `LUSOT_DATA_DIR`. The one write is `photos.py`'s `os.environ["OPENCV_IO_MAX_IMAGE_PIXELS"] = "50000000"`, before it imports cv2 (as MS1's R25 does). `set_b_masks` reads `MODEL_API_KEY` only through `MetaClient`.
- **Files:**
  - CSV: UTF-8 with a header row, written without a BOM and with `\n` endings. Read with or without a BOM and with either ending. A blank cell means none, and all-blank rows are skipped.
  - Records: JSON with sorted keys, a two-space indent, ASCII only and a final newline. Each is created exclusively, and none is ever rewritten. Each of C213's looks is its own record, `set-b-look-<n>.json`.
  - `files.txt`: lines of `<sha256>  <path relative to its folder, with />`, sorted by path.
- **Exact values (spec):**
  - matching (C223, C224): within 30 minutes, inclusive; the same spot means two shared names, or one name each and the same one
  - duplicates (§5.5): identical SHA-256, or 64-bit dHashes within 6 bits
  - decode cap: 50 MP
  - **The split (C204):**
    - The seed is `20261030`. Set A's target is 40% and its cap 45%; A-neg's are a third and 40%.
    - Both shares apply per group: `deep` (an event with a row whose stated `passability_raw` maps to NPLV or NPATV) and `other`.
    - A group of 2 or more events ends with an event on each side: when the walk seals none, the group's smallest event moves to sealed.
    - A set with fewer than 2 events stops the split.
  - **Set B:**
    - Cars: odd numbers are development cars, even ones final (C210). Photos are 1,600 px at most (`blur_for_meta`'s `max_side`).
    - Wheels (C212): at least 40 px on the longer side, and a height over width of 0.9 to 2.0. At most the two largest are used, with centres inside the largest vehicle box and clear of the frame.
    - Crops (C211): the bands are 1 to 5, 5 to 8, 8 to 10, and 10 to the lower of 13 and the hub less 0.5 in. Two of the four crops are shrunk so the smaller wheel is 50 to 80 px tall.
    - `true_depth_in` has at most 4 decimals.
  - the freeze (C213): a crop passes when SAM's water covers at least a quarter of the drawn water, and a look passes at three quarters of its crops; at most 3 looks
- **Toolchain:**
  - Python `>=3.13,<3.14` through uv 0.13.6. Each entry script carries PEP 723 metadata with exact pins and its `.py.lock` (`uv lock --script <file>`), and runs as `uv run --locked --script <file>`.
  - The pins, and how each was checked on Oct 28:
    - **py7zr 1.1.4** (LGPL-2.1-or-later, released Oct 12): with Context7 (`/miurahr/py7zr`), and in its v1.1.4 source. Mode `"x"` raises `FileExistsError`. `header_encryption=True` encrypts the header with AES-256, and a password with no `filters` gives LZMA2 plus AES-256. `writestr(data, arcname)` and `write(file, arcname)` exist, and reading back uses `getnames()` and `extractall(path=...)`; there is no `readall` in 1.x. Opening without a password raises `py7zr.exceptions.PasswordRequired`.
    - **pytest 9.1.1:** with Context7 at 9.1.1. The default prepend import mode needs unique test file names, and the rootdir comes from the arguments' common ancestor.
    - **uv 0.13.6:** with Context7's 0.13.5 docs (`uv lock --script` writes `<script>.lock`; `--locked` fails instead of updating it), and the installed 0.13.6's help for `uv run --locked --script`.
    - **numpy 2.5.4 and opencv-python-headless 4.14.0.94:** the versions `backend/analysis/uv.lock` already locks. Context7 has no docs at those exact versions, only NumPy 2.4 and OpenCV 4.13, and the calls used here (`np.load`, `np.savez_compressed`, `cv2.imdecode`, `cv2.resize`, `cv2.imencode`, `OPENCV_IO_MAX_IMAGE_PIXELS`) match those docs. MS1's R25 test shows the 50 MP cap holds at 4.14.0.94 on this PC.
  - Node 22 (22.22.2 installed) runs `node --test`.
- **Model ids:** where one appears, exactly `sam-3.1`, through `meta_client.SAM_MODEL`.
- **Face blur first (C20, C37):** every image `set_b_masks` sends comes from `blur_for_meta`, crops included.
- **Copy:** the M8 page and the guide follow CLAUDE.md's product copy rules.
- **What never enters the repo:** account IDs, the Meta Team ID, console links, email addresses and plan text.
- **Shells:** start each PowerShell command with CLAUDE.md's PATH refresh. Run from the worktree root, `C:\Systems\Lusot\lusot-wt\meta`, unless a step says otherwise. One test process at a time.
- **Commits:**
  - Conventional Commits. Write the message to a file and run `git commit -F <file>` from PowerShell after the PATH refresh: the gitleaks hook fails closed in Git Bash. Never `--no-verify`.
  - Before each commit, run `uv run --python 3.13 scripts/check_no_plan_leak.py` (expect `clean`) and `node scripts/check_account_ids.mjs` (expect `clean`).
  - end each commit with the attribution lines Claude Code gives the session.

## Review Focus

Most likely first. Each line names its test.

1. **Logs saved from Excel or Google Sheets:** a BOM, CRLF endings, `Yes` and `CROPPED` in capitals, stray spaces, `A001.JPG` and blank rows at the end. They read cleanly, values are normalised, and nothing is flagged. Test: Task 7 `test_spreadsheet_saved_log_reads_cleanly`.
2. **A photo OpenCV can't decode:** a phone's HEIC saved as `.jpg`, a cut-off download, or a header that declares over 50 MP. It gets `decodes = no` and a blank dHash, stays in its event and is split like any other, and nothing crashes. Tests: Task 9 `test_photo_facts_for_files_that_do_not_decode`, Task 13 `test_split_keeps_an_undecodable_photo`.
3. **A split stopped partway** (a power cut or Ctrl+C after the archive or some copies were written). The rerun writes nothing and names each partial output to delete. Test: Task 13 `test_rerun_names_the_partial_outputs`.
4. **Spot text that names a city** ("…, Manila", "…, Quezon City"). City names never join events, so one day's Manila spots don't merge into one event. Test: Task 6 `test_city_names_never_join_events`.
5. **A Set B car on a slope, or shot at an angle,** so its two wheels meet the ground on different rows. The line still gives both wheels the same true depth, within a pixel. Test: Task 14 `test_sloped_line_gives_both_wheels_one_depth`.

## Execution notes

- **Routing (D18):** implementers and every task review (spec compliance and code quality) run on Opus 5.5 at xhigh, scoped re-reviews and easy edits on Sonnet 5.5 at xhigh, and the final whole-branch review on Opus 5.5 at xhigh (Rene's change at 8:48 PM on Oct 29: Opus at xhigh, never max). This follows the tracker's later build rule, as the SDD ledger records it, in place of this plan's first routing, which put spec-compliance reviews on Sonnet. Task 19's licence reading is a lookup and may run on Sonnet 5.5 at xhigh. Task 1, Task 4b's browser check and Task 20's handoff are the controller's own steps.
- **One subagent at a time** (the tracker's section A). None starts while Window 3's `DOCKER/DEPLOY RUNNING` line stands, until its `DONE` (the tracker relays both).
- **Each implementer** gets this plan's task, the Global Constraints, the spec, and the controller's attribution lines.
- **Order:** Tasks 1 to 20 in order, with 4a before 4b. Rene needs the guide and the M8 sheet first, `set_b_masks` lets the development-car masks run early, and the split (Task 13) is due Oct 30. No task uses a name a later task defines: the three record kinds live in Task 11, before the audit (Task 12) and the tools that write them (Tasks 13, 16 and 18).
- **Commands** run from the worktree root. A test run is `uv run --locked --script eval/data/tests/run_tests.py`, with any pytest arguments after it, such as `-k "guards or table"`.
- **Tracking:** the controller ticks this plan's boxes with their evidence, in the same commit as the work. The board and the day's log belong to Window 3 (D20), so the controller writes log-ready lines into its handoff note, `C:\Systems\Lusot\lusot\.superpowers\handoff\specs.md`.
- **MS1 interfaces used (Task 5 only),** as on `main`:
  - `face_blur`: `blur_for_meta(data, *, max_side=1600) -> BlurredImage` (`jpeg`, `width`, `height`, `faces`, `blur_version`), `UndecodableImage`
  - `meta_client`: `MetaClient(api_key=None)` with `.segment(image, phrase) -> SamResult(phrase, instances, elapsed_s, raw)`, `SamInstance(id, box, mask, score)` with a half-open box and a full-size bool mask, `MissingApiKey`, `MetaApiError(message, *, status)`
  - MS1's probe layout (`run_probe.save_sam`): `sam_<stem>.txt` and `sam_<stem>_masks.npz`, where the stem is the phrase with spaces as `_`, with `ids`, `boxes`, `scores` and `masks`

---

### Task 1: Start the branch and re-check the guards (controller)

**Files:** none. The evidence goes into this task's boxes and into `specs.md`.

- [x] **Step 1:**
  - Commit this reviewed plan on `next-specs`.
  - Then, in `C:\Systems\Lusot\lusot-wt\meta` with a clean tree, run `git switch -c ms2-data main` and `git merge next-specs -F <file>`. The message file holds `Merge next-specs into ms2-data: the MS2 spec and plan`, then the attribution lines.
  - Then run `git diff --name-status main ms2-data`. Expected: only `A` lines, under `docs/superpowers/`. Anything else: stop and ask the tracker.
- [x] **Step 2 (B.3, the deny re-check):** probe with names that don't exist, and create nothing.
  - **The Read tool, expected denied:** `C:\Systems\Lusot\lusot-data\set_b\sealed\ms2-probe-none.txt`, `...\set_a\raw\ms2-probe-none.jpg`, `...\a_neg\raw\ms2-probe-none.jpg`, `...\set_a\ms2-probe-none.csv`, `...\a_neg\ms2-probe-none.csv`, `C:\Systems\Lusot\lusot-wt\meta\eval\sealed\ms2-probe-none.txt` and `C:\Systems\Lusot\lusot\eval\sealed\ms2-probe-none.txt`. The two `eval\sealed` probes rest on the project settings, which `main`'s copy carries.
  - **The Read tool, expected not denied** (a missing-file error): `C:\Systems\Lusot\lusot-data\set_a\dev\ms2-probe-none.csv`, since `set_a/*.csv` doesn't reach into `dev\`.
  - **Shell reads** of the seven denied paths, expected to be blocked by the auto-mode check:
    - in PowerShell: `Get-Content -LiteralPath C:\Systems\Lusot\lusot-data\set_b\sealed\ms2-probe-none.txt`, and the same for the others
    - in Bash, with POSIX paths: `cat "/c/Systems/Lusot/lusot-data/set_b/sealed/ms2-probe-none.txt"`, and the same for the others
  - Record each result (denied, blocked, or "file not found"). If a path expected denied isn't, stop: restart Claude Code in this worktree, run the check again, and report to the tracker before Task 2.
- [x] **Step 3 (B.8):** read the status line of `git show main:eval/rules.md` and record its version. Expected today: `DRAFT v0.6`. This build edits nothing in it, and Task 20 confirms v0.7 is applied.
- [x] **Step 4 (MS2-Q3 (a)):** add this line to `specs.md`, for the tracker to relay to Window 3: "MS2 builds `backend/analysis/probes/set_b_masks.py` and `tests/test_set_b_masks.py` on `ms2-data`, as new files only (MS2-Q3's default). They use `blur_for_meta` and `MetaClient.segment` unchanged." Task 5 starts only after this line is written.
- [x] **Step 5:** Commit the ticks: `docs: start MS2's build with the guard re-check`.

*Evidence (Task 1, Oct 28): `ms2-data` made from `main` (`98e8266`), with `next-specs` merged (`ed8e38f`); `git diff --name-status main ms2-data` shows only two `A` lines under `docs/superpowers/`. Deny re-check, on non-existent names: the Read tool was denied on all seven guarded paths (`set_bsealed`, `set_aaw`, `a_negaw`, `set_a*.csv`, `a_neg*.csv`, and both worktrees' `evalsealed`). It returned "File does not exist" under `set_adev`. Shell reads of the seven were blocked in PowerShell and in Bash. `eval/rules.md` on `main` is `DRAFT v0.6`. The relay line for Window 3 (MS2-Q3 (a)) is in `specs.md`.*

### Task 2: Test runner and the guards (C222, C202, C206, C221)

**Files:**
- Create: `eval/data/tests/run_tests.py`, `eval/data/tests/run_tests.py.lock`, `eval/data/tests/conftest.py`, `eval/data/tests/synth.py`, `eval/set_b/tests/conftest.py`, `eval/data/guards.py`, `eval/data/table.py`
- Test: `eval/data/tests/test_guards.py`, `eval/data/tests/test_table.py`, `eval/data/tests/test_sources.py`

**Interfaces:**
- Produces, in `run_tests.py`: PEP 723 `requires-python = ">=3.13,<3.14"` and `dependencies = ["pytest==9.1.1", "numpy==2.5.4", "opencv-python-headless==4.14.0.94", "py7zr==1.1.4"]`. It runs `pytest.main([<eval/data/tests>, <eval/set_b/tests>, "-q", "-p", "no:cacheprovider", *sys.argv[1:]])` and exits with its code.
- Produces, in the conftests: `eval/data/tests/conftest.py` puts `eval/data` and `eval/data/tests` at the front of `sys.path`. `eval/set_b/tests/conftest.py` puts `eval/set_b`, `eval/data` and `eval/data/tests` there.
- Produces, in `synth.py`:
  - `TEST_PHRASE = "test phrase for synthetic archives"`
  - `jpeg(seed: int, size: tuple[int, int] = (240, 320)) -> bytes`: seeded random blocks, so different seeds give dHashes far apart
  - `write_csv(path: Path, columns: Sequence[str], rows: Sequence[Mapping[str, str]]) -> Path`
  - `console(monkeypatch) -> None`: patches `guards.console_ok` to return True
  - `typed(monkeypatch, *answers: str) -> None`: patches `getpass.getpass` and `builtins.input` to return the answers in order
  - `opened_paths(script: Path, argv: Sequence[str]) -> tuple[int, list[tuple[str, str]]]`. It runs the script as `__main__` in a fresh interpreter, with the script's folder first on `sys.path`, as `python <script>` sets it, and stdin on NUL; the interpreter's first act is `sys.addaudithook`. It returns the exit code and each `(event, path)` for the `open`, `os.scandir` and `os.listdir` audit events. `open` covers `builtins.open`, `io.open`, `os.open` and pathlib's reads (checked on Oct 28 with Python 3.13).
- Produces, in `guards.py`:
  - `is_sealed_name(name: str) -> bool`: the per-part rule in the Global Constraints. The name before any `:`, with trailing dots and spaces stripped, is `sealed` in any case. `refuse_sealed` and `require_sealed` apply it to each part, and `setc` prunes with it (Task 19).
  - `refuse_sealed(*paths: str | os.PathLike) -> None`, by the rule in the Global Constraints
  - `require_sealed(path: str | os.PathLike, *, flag: str) -> None`: prints `refused: <flag> must be inside a folder named sealed` and exits 2
  - `console_ok(*, is_console: Callable[[int], bool] | None = None) -> bool`: True when fd 0 and fd 1 are both consoles. The default check is `GetConsoleMode` on `msvcrt.get_osfhandle(fd)` on Windows, `os.isatty(fd)` elsewhere.
  - `require_console() -> None`: prints `refused: run this yourself, in a Windows PowerShell window` and exits 2
  - `ask_password(*, ask: Callable[[str], str] | None = None) -> str`: `None` means `getpass.getpass`, looked up at call time so `synth.typed` can patch it. It prompts `Archive password: ` and `Type it again: `. Empty: `refused: empty password`, exit 2. Different: `refused: the two entries differ; nothing was written`, exit 2.
  - `confirm(summary: str, *, ask: Callable[[str], str] | None = None) -> None`: `None` means `builtins.input`, looked up at call time. It prints the summary and asks `Type yes to continue: `. Anything but `yes` (after stripping) prints `stopped: nothing was done` and exits 2.
  - `quiet(run: Callable[[], int]) -> int`: returns `run()`. On any `Exception`, and on `KeyboardInterrupt` (Ctrl+C), it prints `stopped: <class name>` to stderr and returns 1. `SystemExit` passes through.
- Produces, in `table.py`:
  - `ID_PATTERN = r"[A-Z]{1,3}[0-9]{1,4}(-[0-9]{1,3}){0,2}"` and `is_id(text: str) -> bool` (a full match)
  - `@dataclass class Table: columns: tuple[str, ...]; rows: list[dict[str, str]]`: cells stripped, plus `"#"`, the row's 1-based number among the data rows; all-blank rows dropped
  - `read_table(path: Path) -> Table`, with `encoding="utf-8-sig"` and `newline=""`
  - `csv_bytes(columns: Sequence[str], rows: Iterable[Mapping[str, str]]) -> bytes`
  - `write_new(path: Path, data: bytes) -> str`: creates parent folders, opens with `"xb"`, returns the SHA-256
  - `sha256_bytes(data: bytes) -> str` and `sha256_file(path: Path) -> str`
  - `@dataclass(frozen=True) class Finding: ref: str; column: str; kind: str`, whose `str()` is `"<ref> <column>: <kind>"`
  - `@dataclass(frozen=True) class Fact: ref: str; fact: str; value: str`, whose `str()` is `"<ref> <fact>=<value>"`

- [x] **Step 1:** Write `run_tests.py`, both conftests and `synth.TEST_PHRASE`, then run `uv lock --script eval/data/tests/run_tests.py`. Expected: `Resolved` and the new `run_tests.py.lock`.
- [x] **Step 2: Write the failing tests.**
  - `test_refuse_sealed_paths`, parametrized over `tmp_path/"sealed"/"x.csv"`, `tmp_path/"a"/"Sealed"/"x.csv"`, `tmp_path/"SEALED"`, `tmp_path/"sealed"/"sub"/".."/"x.csv"`, `tmp_path/"x"/"sealed"/".."/"y.csv"` (refused as given), `tmp_path/"sealed."/"x.csv"` and, on Windows, `tmp_path/"sealed::$INDEX_ALLOCATION"/"x.csv"`. Each gives `SystemExit` 2 and the message. None of these exists, and the test creates none.
  - `test_refuse_sealed_lets_other_names_pass`: `tmp_path/"unsealed"/"x.csv"`, `tmp_path/"sealed.csv"` and `tmp_path/"sealed_notes"/"x"` pass.
  - `test_is_sealed_name`: `sealed`, `Sealed`, `SEALED`, `sealed.`, `"sealed "` (a trailing space) and `sealed::$INDEX_ALLOCATION` are sealed names; `unsealed`, `sealed.csv`, `sealed_notes` and `""` aren't.
  - `test_require_sealed`: `tmp_path/"sealed"/"a.7z"` passes; `tmp_path/"a.7z"` exits 2, and the message names the flag.
  - `test_console_needs_both_handles`: with a fake `is_console`, consoles on (0, 1) give True; a console on 0 only (stdout piped) gives False; on 1 only, False.
  - `test_nul_stdin_and_piped_stdout_fail_the_console_check`: a subprocess, `[sys.executable, "-c", "import guards, sys; sys.exit(0 if guards.console_ok() else 3)"]` with `PYTHONPATH` set to `eval/data`, `stdin=subprocess.DEVNULL` and `stdout=subprocess.PIPE`, returns 3. On Windows a second subprocess shows `os.isatty(0)` is True on NUL, the trap C412 names.
  - `test_require_console_message`: with `console_ok` patched to False, `SystemExit` 2, and stderr names Windows PowerShell.
  - `test_password_typed_twice`: answers `"p q r"` twice give `"p q r"`; `"a"` then `"b"` exits 2 with "differ"; two empty answers exit 2.
  - `test_confirm_needs_yes`: `"yes"` and `" yes "` pass; `"y"` and `""` exit 2.
  - `test_quiet_prints_the_class_only`: a function raising `ValueError("A007.jpg")` gives 1, and stderr is `stopped: ValueError` without `A007`; a `KeyboardInterrupt` gives 1 and `stopped: KeyboardInterrupt`; a `SystemExit(2)` passes through.
  - `test_opened_paths_sees_every_open`: a tiny script that imports a sibling module from its own folder, reads one file with `open`, one with `os.open` and one with `Path.read_bytes`, and lists one folder, exits 0 and reports all four paths. The exit 0 shows the script's folder is on `sys.path`.
  - `test_ids`: `A001`, `N015`, `E01`, `E100`, `B01`, `B01-1`, `B01-1-2`, `D01`, `S001`, `P1` and `R12` pass; `a001`, `A001-`, `A00001`, `2026-10-30`, `Espana`, `B01-1-2-3` and `""` fail.
  - `test_read_table_tolerates_bom_crlf_and_blank_rows`: the bytes `b"\xef\xbb\xbfa , b\r\n 1 , x \r\n,\r\n\r\n"` give columns `("a", "b")` and the one row `{"a": "1", "b": "x", "#": "1"}`.
  - `test_csv_bytes_are_plain`: no BOM, `\n` endings, the header first, and a value holding a comma is quoted.
  - `test_write_new_never_overwrites`: the first write returns the SHA-256; a second raises `FileExistsError` and leaves the bytes.
  - `test_findings_print_as_specified`: `str(Finding("A001", "city", "missing")) == "A001 city: missing"` and `str(Fact("A001", "match", "none")) == "A001 match=none"`.
  - In `test_sources.py`, each scanning every `*.py` under `eval/data` and `eval/set_b` outside the `tests` folders:
    - `test_sources_list_no_folder`: outside `setc.py`, none contains `listdir(`, `scandir(`, `os.walk(`, `.iterdir(`, `.glob(`, `.rglob(`, `.walk(`, `import glob`, `copytree(`, `rmtree(` or `writeall(`
    - `test_sources_read_no_environment`: none contains `getenv`, `environ.get(` or `LUSOT_DATA_DIR`, and the only `environ[` is `photos.py`'s cap line
    - `test_sources_never_import_lusot_analysis_or_scoring`
    - `test_no_password_option`: none contains `--password` or `--pass`
- [x] **Step 3:** Run `uv run --locked --script eval/data/tests/run_tests.py`. Expected: FAIL, with `ModuleNotFoundError: No module named 'guards'`.
- [x] **Step 4:** Implement `guards.py` and `table.py` with the names above, and the rest of `synth.py`. `refuse_sealed` and `require_sealed` touch no disk.
- [x] **Step 5:** Run it again. Expected: all pass.
- [x] **Step 6:** Commit `feat(data): add the guards, CSV helpers and the locked test runner`.

*Evidence (Task 2, Oct 28): commits f754182 and 2f3ab17. `uv run --locked --script eval/data/tests/run_tests.py`: 44 passed, also with `-W error`; ruff, the plan-leak check, the account-ID scan and gitleaks clean. The task review held the guards against every string-level route probed (case, `..`, trailing dots and spaces, `:` streams, UNC, extended-length, relative and drive-relative paths) and confirmed `console_ok()` False in both of Claude's shells; one fix round added the 60 s subprocess timeout (S-R2), a drive-relative test pinning the absolute half of C222, and `MalformedCsv` for over-long or short rows and bad header names; the re-review was clean.*

### Task 3: Formats, templates and the collection guide (C209, C218, §5.9, §8)

**Files:**
- Create: `eval/data/formats.py`; `eval/templates/a_neg_log.csv`, `m8_labels.csv`, `set_b_cars.csv`, `set_d_log.csv`, `consented_log.csv` and `sidewalls.csv`
- Modify: `eval/templates/set_a_log.csv`, `docs/data/set-a-collection-guide.md`
- Test: `eval/data/tests/test_formats.py`

**Interfaces:**
- Consumes: `table.is_id`, `table.read_table` (Task 2).
- Produces, in `formats.py`, each list in the order spec §5.9 gives:
  - columns:
    - `SET_A_COLUMNS`: today's 17 template columns, required in Set A's log
    - `SET_A_OPTIONAL = ("same_spot_as", "alert_poster", "alert_spot_text")`: optional columns in both logs (C209); A-neg ignores the two alert columns
    - `A_NEG_COLUMNS = SET_A_COLUMNS + ("surface",)`: the columns required in A-neg's log. That is Rene's log as the tracker's checklist v2 has him make it: the Set A template plus `surface`.
    - `M8_COLUMNS = ("photo_id", "ref_id", "kind", "x", "y", "vehicle_type", "body_waterline", "waterline", "quality", "subsets")`
    - `MANIFEST_COLUMNS`, the 27 of §5.9's manifest table: `photo_id`, `set`, `split`, `event_id`, `event_date`, `city`, `metro_manila`, `spot_key`, `same_spot_as`, `poster_kind`, `match`, `level_label_raw`, `passability_raw`, `other_alerts_raw`, `label_in_image`, `reference_visible`, `faces_or_plates`, `surface`, `duplicate`, `duplicate_of`, `decodes`, `photo_file`, `photo_sha256`, `photo_dhash`, `width`, `height`, `notes`
    - `CARS_COLUMNS`, `TRUTH_COLUMNS` (27), `SET_D_COLUMNS`, `CONSENTED_COLUMNS` and `SIDEWALLS_COLUMNS`, as §5.9 lists them
  - `TEMPLATES: dict[str, tuple[str, ...]]`, from template file name to header: `set_a_log.csv` (`SET_A_COLUMNS + SET_A_OPTIONAL`), `a_neg_log.csv` (`A_NEG_COLUMNS + ("same_spot_as",)`), `m8_labels.csv`, `set_b_cars.csv`, `set_d_log.csv`, `consented_log.csv` and `sidewalls.csv`
  - value lists:
    - from the guide and the spec: `PLATFORMS = ("facebook", "x", "other")`, `YES_NO = ("yes", "no")`, `REFERENCE_VISIBLE = ("wheel", "person", "both", "none")`, `LABEL_IN_IMAGE = ("no", "cropped", "yes")`, `A_NEG_POSTERS = ("own", "friend")` (Task 13c adds `"commons"`, with `COMMONS_LICENCES` and the optional `licence` and `credit` columns, S-R20), `SURFACES = ("wet", "dry")`
    - Table 5's `VEHICLE_TYPES` (9), `BODY_WATERLINES` (6), `WHEEL_WATERLINES` (7) and `PERSON_WATERLINES` (8): schema v1's enums, in its order
    - M8: `M8_KINDS = ("photo", "vehicle", "wheel", "person")`, `QUALITIES = ("ok", "dark", "blurry")`, `SUBSET_TAGS = ("reflection", "splash", "moving")`
    - Set B and the other logs: `SET_B_TYPES = ("sedan_hatch", "suv_mpv", "van")`, `VIEWS = ("side", "angled")`, `WHEEL_SIDES = ("left", "right")`, `ITEM_KINDS = ("photo", "clip")`, `SIDEWALL_VEHICLES = ("jeepney", "tricycle", "bus", "hilux", "tamaraw", "other")`
  - `METRO_MANILA: tuple[str, ...]`: the 16 cities and Pateros, as display names (`Las Piñas`, `Parañaque`, `Quezon City`…)
  - `APPROVED_CONSENT: dict[str, frozenset[str]] = {"m9": frozenset(), "set_b": frozenset(), "m11": frozenset()}` (C218: set when Rene approves each text; Window 4's M9 text is `M9-v4`, approved on Oct 29 by Claude under Rene's delegation, and only a v4 reply counts)
  - id and file patterns: `SET_A_ID = r"A[0-9]{3}"`, `A_NEG_ID = r"N[0-9]{3}"`, `ITEM_ID = r"S[0-9]{3}"`, `CAR_ID = r"B[0-9]{2}"`, `SET_D_ID = r"D[0-9]{2}"`, `PHOTO_EXTENSIONS = ("jpg", "jpeg", "png")`
  - `is_date(text: str) -> bool` (`YYYY-MM-DD`, a real date), `is_time(text: str) -> bool` (`YYYY-MM-DD HH:MM`, 24-hour, real) and `parse_time(text: str) -> datetime`

- [x] **Step 1: Write the failing tests.**
  - `test_templates_match_the_constants`: each file in `TEMPLATES` exists in `eval/templates/`, holds exactly its header line, and that header equals the constant.
  - `test_set_a_template_keeps_the_17_columns_first`: the first 17 names equal today's template, written out in the test, and the last three are `SET_A_OPTIONAL`.
  - `test_table5_lists_match_schema_v1`: reads `backend/analysis/prompts/muse_spark_photo_v1.schema.json` as JSON (no import) and compares the four enums, in order.
  - `test_patterns_fit_c221`: an example of each id pattern `re.fullmatch`es its own pattern and passes `table.is_id`.
  - `test_dates_and_times`: `2026-08-09` passes; `2026-8-9`, `09/08/2026` and `2026-02-30` fail. `2026-08-09 08:20` passes; `2026-08-09 8:20`, `2026-08-09 08:20 AM` and `2026-08-09T08:20` fail.
  - `test_no_consent_version_is_approved_yet`: all three sets are empty. Its docstring says the test changes with C218's constant, when Rene approves a text. Task 13b replaces it with `test_approved_consent_versions`: `M9-v4`, `SETB-v1` and `M11-v1`, approved on Oct 29 by Claude under Rene's delegation.
  - `test_guide_names_every_column`: every column of every template appears in backticks in `docs/data/set-a-collection-guide.md`.
- [x] **Step 2:** Run `uv run --locked --script eval/data/tests/run_tests.py -k formats`. Expected: FAIL, with `ModuleNotFoundError: No module named 'formats'`.
- [x] **Step 3:** Write `formats.py` and the templates: headers only, a `\n` ending, no BOM.
- [x] **Step 4: Update the guide.** Fold in the tracker's search checklist v2 (`C:\Systems\Lusot\lusot\.superpowers\handoff\rene\set-a-search-checklist.md`, which follows C209, C223 and C224). Make sure the guide covers:
  - **Set A (C209):**
    - one row per alert a photo may fit, with the photo's columns repeated
    - separate-post rows fill `alert_poster`, `alert_spot_text` and `alert_time_pht`: the time the alert's text gives, or else its post's time
    - every time in `YYYY-MM-DD HH:MM`
    - `level_label_raw` holds the alert's depth words only, `passability_raw` its class words or code exactly as posted, and `other_alerts_raw` is never filled by hand
    - `same_spot_as` takes ids separated by `;`, on the same date, for nearby spots with different names and for corners on a city boundary
  - **`poster` (MS2-Q4 (a)):** `MMDA`, a city's name, or a city office such as `Quezon City DRRMO` or `Manila Public Information Office`. Barangay, personal, police and fire pages count as `other`. **`city`:** one of the 17 names, as listed.
  - **A-neg:** its template, or the checklist's copy of the Set A template plus `surface`; `same_spot_as` is optional. Ids `N001`…; `poster` `own`, `friend` or `commons` (from Oct 29, Wikimedia Commons photos with `licence` and `credit`, downloaded by the tracker's script into `lusot-data\a_neg_commons_staging\`; Rene fills `reference_visible`, `label_in_image`, `faces_or_plates` and, where the page doesn't say, `surface`; Task 13c, S-R20); the capture time in `post_time_pht`; the level `none`; 5 or more places over 2 or more days; a friend's OK.
  - **Set B (M10):**
    - cars numbered `B01`… in the order photographed; odd numbers go in `set_b\dev\`, even ones in `set_b\sealed\` (C210)
    - `cars.csv` from `set_b_cars.csv`, one row per photo `B01-1.jpg`…, with the photos in `photos\` beside it; types `sedan_hatch`, `suv_mpv` or `van`, with one tire code on both axles
    - parked, side-on, in daylight; as many cars as possible by Oct 30 (fewer than 6 accepted, Rene's decision, Oct 29)
    - each owner's OK as `consent_file`, beside `cars.csv`, with the version of the text it answered. A car without its OK is never sent to Meta. The final cars' OKs go into the Set B archive, so keep a copy outside `set_b\sealed\` if you want them at hand after the archive test.
  - **M8 (C208):**
    - Claude makes `set_a\m8_sheet.html`. Rene opens it in his browser, clicks each readable vehicle, wheel and person, sets each photo's marks, and exports `m8_labels.csv` into `set_a\`.
    - the in-between convention
    - the page never shows alert labels
    - its Clear button, after the split
  - **Set D (M13):** `set_d_log.csv` in `set_d\sealed\`, with the photos in `set_d\sealed\photos\`.
  - **M9:** `consented_log.csv`, whose `consent_version` is the donor message's version, such as `M9-v4` once approved. The old draft message is replaced by a pointer to the message Rene approves (Window 4's draft `M9-v4`).
  - **M11:** `sidewalls.csv`.
- [x] **Step 5:** Run the tests again. Expected: all pass.
- [x] **Step 6:** Commit `feat(data): add MS2's formats, the log templates and the updated collection guide`.

*Evidence (Task 3, Oct 28): commits 9d10803, e9d58ad and e756694. `uv run --locked --script eval/data/tests/run_tests.py`: 57 passed, also with `-W error`; ruff, the plan-leak check, the account-ID scan and gitleaks clean. All seven column lists match spec §5.9 in order. The task review found plan text copied into the guide's Set D paragraph (the leak check misses text split across the plan's table lines), fixed with the guide's own wording (no shared run longer than 4 words); two fix rounds also added Excel's date handling (keep an .xlsx working copy with Text columns, save CSV UTF-8 for the tools), the office words the tools recognise, and the rule that `raw\` is deleted only after 7-Zip opens the archive, with Excel closed. Both re-reviews were clean.*

### Task 4a: The M8 page's script (C208)

**Files:**
- Create: `eval/data/m8_sheet.js`, `eval/data/tests/m8_sheet.test.mjs`
- Test: `eval/data/tests/test_m8_script.py` (the pytest wrapper)

**Interfaces:**
- Consumes: `eval/templates/m8_labels.csv` (Task 3).
- Produces, in `m8_sheet.js`: a classic script (no modules) defining one global, `M8`.
  - **Pure functions:**
    - `fractionOf(clientX, clientY, rect)`: returns `{x, y}` as fractions of the shown image, rounded to 4 decimals, or `null` outside it
    - `newState(photoIds)`
    - `addRef(state, photoId, kind, x, y)`: returns `R1`, `R2`… per photo; a number is never reused
    - `setValue(state, photoId, refId, column, value)`, `removeRef(state, photoId, refId)`
    - `setMarks(state, photoId, quality, subsets)`: the photo row, `P1`
    - `toCsv(state)`: the header is `M8.COLUMNS`, the M8 columns the script holds itself. Rows run by photo id, `P1` first, then the `R` numbers ascending, with `\n` endings and `subsets` joined by `;`.
    - `fromCsv(text, photoIds)`: tolerates a BOM and CRLF; rows of unknown photos are dropped and counted
    - `problems(state)`: a photo without marks, and a reference missing a value
  - **The page:** `start(doc, win, data)` wires the photos, clicks, values, marks, `localStorage` autosave, export, import and "Clear saved work". It runs only when `document` exists. `data` has exactly these keys: `photos` (a list of `{id, file}`), `vehicleTypes`, `bodyWaterlines`, `wheelWaterlines` and `personWaterlines` (Table 5's lists), and `storageKey`. The M8 columns aren't in it.
  - **No `</`:** the script's text contains no `</`, so Task 4b embeds it verbatim.

- [x] **Step 1: Write the failing tests.**
  - In `m8_sheet.test.mjs` (`node:test`, `node:assert/strict`, and `node:vm` loading `m8_sheet.js` into a context without `document`):
    - `fractionOf maps a click to fractions of the shown image`: rect `{left: 10, top: 20, width: 200, height: 100}`; `(110, 70)` gives `{x: 0.5, y: 0.5}`, `(10 + 200/3, 20)` gives `x` 0.3333, and `(5, 70)` gives `null`
    - `references are numbered per photo and never reused`
    - `export then import gives the same state`, with subsets `reflection;splash`
    - `the export header equals eval/templates/m8_labels.csv`
    - `import tolerates a BOM and CRLF and drops unknown photos`
    - `problems name a photo without marks and a wheel without its waterline`
  - In `test_m8_script.py`: `test_m8_script_passes_its_node_tests`: `node --test` on the test file, by its path from `__file__`, exits 0.
- [x] **Step 2:** Run `uv run --locked --script eval/data/tests/run_tests.py -k m8_script`. Expected: FAIL; node reports `ENOENT` for `m8_sheet.js`.
- [x] **Step 3:** Implement `m8_sheet.js`.
- [x] **Step 4:** Run the tests again. Expected: all pass.
- [x] **Step 5:** Commit `feat(data): add the M8 page's script`.

*Evidence (Task 4a, Oct 28): commits 07ad13d, 58ce186 and 49d4c1f. `uv run --locked --script eval/data/tests/run_tests.py`: 59 passed, also with `-W error`; 12 node tests pass; ruff, the plan-leak check, the account-ID scan and gitleaks clean. The script holds no `</` or `<!--`, one global, no network call and no HTML built from data. The task review approved it; one fix round (S-R5) made an import show its kept and left-out counts and refuse a file with no row for the page's photos, tied the quality and subset lists to `formats.py`, and pinned the photo's border and padding to 0. The re-review was clean.*

### Task 4b: The M8 sheet command (C208)

**Files:**
- Create: `eval/data/m8_sheet.py`, `eval/data/m8_sheet.py.lock`
- Test: `eval/data/tests/test_m8_sheet.py`

**Interfaces:**
- Consumes: `m8_sheet.js` (Task 4a); `guards.refuse_sealed`, `table.read_table`, `table.Finding`, `formats` (Tasks 2 and 3).
- Produces, in `m8_sheet.py` (PEP 723, `dependencies = []`):
  - `IN_BETWEEN_RULE = "When the water sits between two marks, pick the higher mark. This holds for wheels, people and car bodies alike."` (MS3b-Q5's default; prompt v1 says the same)
  - `STORAGE_KEY = "lusot-m8-v1"`
  - `build_page(photos: Sequence[tuple[str, str]]) -> str`
  - `main(argv: Sequence[str] | None = None) -> int`, with `--set-a-log` and `--out`
- **The page itself:**
  - one self-contained HTML file, with an inline `<style>` and one classic inline `<script>`. The script holds `m8_sheet.js`, verbatim, and a JSON block of `start`'s `data`, under Task 4a's keys: the ids, file names, Table 5's lists and `STORAGE_KEY`. The JSON has `</` escaped, and the M8 columns stay in the script.
  - images by the relative path `raw/<photo_file>`, beside the page; no network
  - `IN_BETWEEN_RULE` above the photos, and nothing else from the log
- **The command:** it reads only `candidate_id` and `photo_file`, and stats each `<out folder>/raw/<photo_file>`. Problems print as `row <n> candidate_id: bad_id` or `<id> photo_file: file_missing` (a file not in `raw/`; `missing` means a blank cell, S-R10), exit 1 and write nothing. Otherwise it writes the page (a rerun overwrites it, as rows are added) and prints `photos=<n>`.

- [x] **Step 1: Write the failing tests.**
  - `test_page_lists_each_photo_once`: a log with two rows for `A002` and one for `A001` gives a data block listing `A001`, then `A002`.
  - `test_page_holds_no_log_text`: every other column holds a sentinel (`SENTINEL-SPOT`, `SENTINEL-LINK`, `SENTINEL knee deep`, `SENTINEL-NOTE`…), and none reaches the page.
  - `test_page_needs_no_network`: no `http:`, `https:`, `<link` or `@import`, and every `src=` starts with `raw/`.
  - `test_page_states_the_convention`: `IN_BETWEEN_RULE` is in the page.
  - `test_page_embeds_the_script`: `m8_sheet.js`'s text contains no `</`, and the page holds that text verbatim.
  - `test_sheet_reads_no_photo_bytes`: `synth.opened_paths` on `m8_sheet.py` shows no `open` under `raw/`.
  - `test_missing_photo_and_bad_ids`: a missing `raw/A003.jpg` gives exit 1 and `A003 photo_file: file_missing`; a bad id gives `row 2 candidate_id: bad_id`; no page is written.
  - `test_refuses_sealed_paths`: `--set-a-log` or `--out` under a `sealed` folder exits 2.
- [x] **Step 2:** Run `uv run --locked --script eval/data/tests/run_tests.py -k test_m8_sheet`. Expected: FAIL, with `ModuleNotFoundError: No module named 'm8_sheet'`.
- [x] **Step 3:** Implement, then run `uv lock --script eval/data/m8_sheet.py`.
- [x] **Step 4:** Run the tests again. Expected: all pass. `uv run --locked --script eval/data/m8_sheet.py --help` exits 0.
- [x] **Step 5 (controller, a browser check on a synthetic page):**
  - Build a page from a synthetic log and two `synth.jpeg` images in the scratchpad, never in `lusot-data`.
  - Open it with the Playwright plugin. If the plugin refuses `file://` pages, serve the scratch folder with `uv run --python 3.13 python -m http.server --bind 127.0.0.1 --directory <scratch folder> 8770`, and open the page on port 8770 of `127.0.0.1`.
  - Click a point on each photo, set the values and marks, export, reload, and import.
  - Expected: the re-imported state matches, and the export equals the first export.

  Agents never open the real page: it shows Set A photos.
- [x] **Step 6:** Commit `feat(data): add the M8 labelling sheet`.

*Evidence (Task 4b, Oct 28): commits 35f6287, 647fbfe, bf6b547, 932e329 and b1983eb. `uv run --locked --script eval/data/tests/run_tests.py`: 75 passed, also with `-W error`; 13 of 13 mutations caught; ruff, the plan-leak check, the account-ID scan and gitleaks clean. A browser check on a synthetic page showed every request was the page or a `raw/` photo, Clear dismissed then accepted, and no sideways scroll from 320 to 1280 px. The page states Rene's final in-between rule (MS3b-Q5, 11:09 PM). The task review found that `--out` could overwrite any file, Rene's log included; one fix round made a non-`.html` `--out` a usage error, required each photo file to be `<id>.<jpg|jpeg|png>`, and named a missing column. The re-review was clean.*

### Task 5: `set_b_masks` (C200; MS2-Q3 (a))

Starts only after Task 1, Step 4. MS2-Q3 (b) would hold this task until MS3a merges.

**Files:**
- Create: `backend/analysis/probes/set_b_masks.py`
- Test: `backend/analysis/tests/test_set_b_masks.py`; on the eval side, `eval/data/tests/test_guard_copies.py` (the parity test)

**Interfaces:**
- Consumes: MS1's `blur_for_meta`, `UndecodableImage`, `MetaClient`, `MissingApiKey`, `MetaApiError`, `SamResult` and `SamInstance` (Execution notes).
- Produces, in `set_b_masks.py`:
  - `PHRASES = ("vehicle", "wheel", "wheel rim")` and `WATER_PHRASE = "floodwater"`
  - **The copied guards:** `refuse_sealed`, `require_sealed`, `console_ok(*, is_console=None)`, `require_console`, `confirm(summary, *, ask=None)` and `quiet(run)`, plus `is_sealed_name`, which the first two call, with `eval/data/guards.py`'s rules, signatures and messages (Task 2). They are copied verbatim and call no helper outside these seven. This package can't import `eval/`, and MS3a's runner, whose `refuse_sealed` C222 names, isn't on `main` yet, so they are copied here. This departs from C222, which has `set_b_masks` use the runner's `refuse_sealed`: the departure is a D7 default, forced by the import boundary, and the copies give way to MS3a's helper when MS3a merges (Waiting on others).
  - `check_cars(cars: Path, *, final: bool) -> tuple[list[str], dict[str, str]]` (§5.6, C210, C218): reads only `car_id`, `photo_file` and `consent_file`. It returns the photo files to send, in order, and each skipped car with its cause, keyed by car id, or under `final` by `row <n>` for each of the car's rows, so no final car id is kept. The causes:
    - `no_consent`: a blank `consent_file`, or no such file beside `cars.csv`, by a stat
    - `wrong_side`: an even car number without `--final`, or an odd one with it

    A photo name must match `B[0-9]{2}-[0-9]{1,2}\.(jpg|jpeg|png)` in any case, else exit 1 naming the row. The consent version isn't checked here: `generate` warns on an unapproved one (C218).
  - `save_result(folder: Path, result: SamResult, shape: tuple[int, int]) -> list[Path]`: writes `sam_<stem>.txt` (the raw text, R11) and `sam_<stem>_masks.npz` (`ids`; `boxes`, N×4 floats; `scores`, NaN for None; `masks`, N×H×W bool), where the stem is the phrase with spaces as `_` (`sam_wheel_rim_masks.npz`), as `run_probe.save_sam` does. *Note for reviewers:* `save_result` re-implements `run_probe.save_sam`, because importing `run_probe` would read `LUSOT_DATA_DIR` at import (`run_probe.py` line 68).
  - `mask_photo(client, data: bytes, folder: Path) -> int`: runs `blur_for_meta(data)` (1,600 px at most) and writes `blurred.jpg` (the BlurredImage's JPEG bytes). Then one `segment` call per phrase, each saved with `save_result`. `meta.json` comes last: `width`, `height`, `faces`, `blur_version`, the instances per phrase, the seconds and the files written. Returns the calls made.
  - `water_crop(client, data: bytes, folder: Path, *, generator_version: str) -> int`: `blur_for_meta` on the crop, then one `floodwater` call, saved the same way. Its `meta.json`, written last, holds the crop's SHA-256 under the key `crop_sha256`, and `generator_version`.
  - `write_files_txt(out: Path, written: Iterable[Path]) -> None`: merges the entries already in `out/files.txt` (a file named on purpose, not a listing) with the newly written files, hashed, and rewrites it in the `files.txt` format. A `--water` run thereby keeps the photo entries an earlier run wrote.
  - `main(argv: Sequence[str] | None = None, *, make_client: Callable[[], MetaClient] = MetaClient) -> int`, its body run through `quiet`. Every mode runs, in order:
    1. the path checks on the strings
    2. under `--final`, `require_console()`
    3. `check_cars`, or the truth file's crops
    4. a summary with the planned calls and their cost at $0.0025 a call
    5. under `--final`, `confirm`
    6. the client is made, then the calls run

    The modes:
    - `--cars CARS --photos DIR --out DIR`: sends each photo `check_cars` returns. A photo whose `<out>/<stem>/meta.json` exists is skipped. A skipped car prints as `<car> skipped: <cause>`, or `row <n> skipped: <cause>` under `--final`, so no final car id prints. A photo that `blur_for_meta` refuses with `UndecodableImage` (it doesn't decode, or a side is 32 px or less) is skipped as `undecodable`, counted and printed like any other skip: `<photo stem> skipped: undecodable`, or `row <n> skipped: undecodable` under `--final`.
    - `--water TRUTH --out DIR`: one call per distinct `crop_file` in `truth.csv`, read from `<TRUTH folder>/crops/`, saved in `<out>/water/<crop_id>/`. A crop is skipped only when its `meta.json` holds the crop file's current SHA-256 and the truth file's `generator_version`, so a new look is always segmented again (C213). `--water` with `--final` is refused.
    - `--final`: `require_sealed` on `--cars`, `--photos` and `--out`. Without `--final`, `refuse_sealed` covers every path.

    It prints `photos=<n> skipped=<k> sam_calls=<c> seconds=<s>`. It exits 0; 1 on a `MetaApiError`, printing its class and status only, with finished photos kept; 2 on a refusal or `MissingApiKey`.

- [x] **Step 1: Write the failing tests.** A `FakeClient` in the test file records each image and phrase and returns synthetic instances; it never touches the network. The probe is loaded with `importlib.util.spec_from_file_location`, as MS3a's runner tests load theirs.
  - **The copied guards,** tested as Task 2 tests `guards`:
    - `test_copied_refuse_sealed`: Task 2's cases, with the stream-name case on Windows
    - `test_copied_console_needs_both_handles`: with a fake `is_console`, each handle alone fails
    - `test_copied_console_check_on_nul`: a subprocess with stdin on NUL and stdout piped gives False, while on Windows `os.isatty(0)` is True there
    - `test_copied_confirm_needs_yes`; `test_copied_quiet_prints_the_class_only`
  - **The parity test,** on the eval side, which already reads backend files as data (Task 3): `test_set_b_masks_guards_match_eval_guards` in `eval/data/tests/test_guard_copies.py`. It reads `backend/analysis/probes/set_b_masks.py` and `eval/data/guards.py` as text and parses both with `ast`, never importing either. For each of the seven copied functions, the `ast.dump` of its definition is the same in both files, so the copies can't drift.
  - `test_masks_every_photo_with_three_phrases`: 2 photos make 6 calls. Each folder holds `blurred.jpg`, the three `.txt` and `_masks.npz` files and `meta.json`, and the masks round-trip with `np.load` (ids, boxes, scores and mask shapes).
  - `test_every_image_sent_is_blurred_first`: each image the fake receives satisfies `type(img) is BlurredImage` and is at most 1,600 px on its longer side (from a 2,400 px photo).
  - `test_cars_without_consent_are_never_sent`: a car with a blank `consent_file` and a car whose file is missing. The fake receives no image of either, and each prints `<car> skipped: no_consent`.
  - `test_wrong_side_cars_are_never_sent`: an even car in development mode, and an odd one under `--final`. No image of either is sent.
  - `test_rerun_pays_nothing`: a second run makes 0 calls and changes no file.
  - `test_files_txt_lists_every_file_with_its_hash`
  - `test_water_mode_segments_each_crop_once`: a `truth.csv` with 2 crops of 2 wheels each makes 2 `floodwater` calls.
  - `test_water_mode_redoes_a_changed_crop`: after a first `--water` run, one crop's bytes change. The second run sends only that crop, and its `meta.json` holds the new SHA-256.
  - `test_dev_mode_refuses_sealed_paths`, for each flag
  - `test_final_needs_sealed_paths_and_a_console`: a subprocess with stdin on NUL and stdout piped exits 2; `--final` with paths outside `sealed` exits 2.
  - `test_final_needs_yes_before_any_call`: with the console patched and sealed paths under `tmp_path`, the summary shows the planned calls and cost. Answering `no` exits 2 with zero fake calls, and `yes` writes the masks.
  - `test_meta_error_keeps_finished_photos`: the fake raises `MetaApiError("x", status=503)` on the fourth call. Exit 1, the first photo's folder is complete, and the output holds only the class name and 503.
  - `test_missing_key_exits_2`: `make_client` raises `MissingApiKey`.
  - `test_source_lists_no_folder_and_reads_no_environment`: the probe's source has no listing call, `environ` or `getenv`.
- [x] **Step 2:** From the root, run `uv run --locked --directory backend/analysis pytest -q tests/test_set_b_masks.py`, then `uv run --locked --script eval/data/tests/run_tests.py -k guard_copies`. Expected: both FAIL, with `FileNotFoundError` for `probes/set_b_masks.py`.
- [x] **Step 3:** Implement. Calls run one at a time on one client.
- [x] **Step 4:** Run the test file and the parity test, then `uv run --locked --directory backend/analysis pytest -q` and `uv run --locked --directory backend/analysis ruff check .`. Expected: all pass, MS1's tests unchanged, and ruff clean.
- [x] **Step 5:** Commit `feat(analysis): add set_b_masks, the face-blurred SAM masks for Set B`.

*Evidence (Task 5, Oct 29): commits ffa46da and 76b1d03 (new files only; no existing `backend/analysis` file changed). `uv run --directory backend/analysis pytest -q`: 180 passed; `uv run --locked --script eval/data/tests/run_tests.py`: 76 passed, the guard parity test included; ruff, the plan-leak check, the account-ID scan and gitleaks clean; 24 of 24 mutations caught. Every photo reaches SAM only as a `BlurredImage`, and consent and the car's odd/even side are checked before any client exists; tests use a fake client only (no live Meta call). The task review found that a photo listed twice was paid twice and that stems could collide; one fix round refused duplicate stems, named missing photos before any call, repaired `files.txt` after an interrupt, held consent files beside `cars.csv`, refused final-car crops under `--water`, and required an absolute `--out`. The re-review was clean.*

### Task 6: Places and events (C203, C224, MS2-Q4)

**Files:**
- Create: `eval/data/places.py`, `eval/data/events.py`
- Test: `eval/data/tests/test_places.py`, `eval/data/tests/test_events.py`

**Interfaces:**
- Consumes: `formats.METRO_MANILA`.
- Produces, in `places.py` (standard library):
  - `fold(text: str) -> str`: NFKD, combining marks dropped (`ñ` becomes `n`), casefolded, every character outside `a-z0-9` made a space, spaces collapsed
  - `spot_names(text: str) -> frozenset[str]`, in four steps:
    1. Split the raw text on `, ; / & + ( ) [ ]` and on a hyphen or dash with a space on each side. Fold each piece, then split it again on the connector words `cor`, `corner`, `near`, `along`, `at`, `and`, `in front of`, `infront of`, `fronting`, `beside`, `between` and `intersection`. An unspaced hyphen (`EDSA-Kamuning`) doesn't split.
    2. Drop a segment that is a Metro Manila city (`city_name` isn't None). This is checked before step 3, so `Quezon City` is dropped whole and never leaves `quezon`.
    3. In the rest, drop:
       - street words: `street`, `st`, `avenue`, `ave`, `av`, `boulevard`, `blvd`, `road`, `rd`, `highway`, `hwy`, `drive`, `dr`, `extension`, `ext`, `lane`, `ln`
       - direction words: `nb`, `sb`, `eb`, `wb`, `northbound`, `southbound`, `eastbound`, `westbound`, `bound`
       - area words: `area`, `vicinity`, `portion`, `brgy`, `barangay`, `city`, `the`
       - one-letter tokens

       Map `sto` to `santo`, `sta` to `santa`, and `epifanio de los santos` or `epifanio delos santos` to `edsa`.
    4. Each non-empty remainder is one name.

    The builder may extend these word lists, as long as the tests below hold (§10: fixed and tested before the split).
  - `spot_key(names: frozenset[str]) -> str` (sorted, joined by `|`) and `names_of(key: str) -> frozenset[str]`
  - `same_spot(a: frozenset[str], b: frozenset[str]) -> bool` (C224): at least two shared names, or one name each and the same one
  - `city_name(text: str) -> str | None`: the display name for a folded text equal to the base name, `<base> city` or `city of <base>`. Quezon City only as `quezon city`, `qc` or `q c`, since plain `quezon` is the province. Pateros also as `municipality of pateros`.
  - `poster_kind(text: str) -> str` (MS2-Q4 (a)):
    - `mmda` for `mmda`, `metropolitan manila development authority` or `metro manila development authority`
    - `other` when any word is `barangay`, `brgy`, `police`, `pnp`, `fire` or `bfp`
    - `city` when the folded text is `<x>` or `<x> <office>` with `city_name(x)` set, where `<office>` is one of `government`, `city government`, `city hall`, `lgu`, `drrmo`, `cdrrmo`, `pio`, `public information office` or `information office`
    - `other` otherwise
- Produces, in `events.py` (standard library):
  - `NEAR_BITS = 6`; `near(a: str, b: str) -> bool`: two 16-hex dHashes within 6 bits; False when either is blank
  - `@dataclass(frozen=True) class EventInput: photo_id: str; date: str; key: str; links: frozenset[str]`
  - `group_events(rows: Sequence[EventInput], joined: Iterable[tuple[str, str]] = ()) -> dict[str, str]`: a union-find. Two rows of one set join:
    - on the same date with the same key, or with a shared name (`names_of`). Empty keys (spot text that names only a city) count as the same key, so such rows of one date join one another, the conservative choice for W18.
    - when either links the other in `same_spot_as`
    - as a `joined` pair

    Event ids are `E01`, `E02`… (at least two digits), numbered by each event's lowest photo id.
  - `event_number(event_id: str) -> int`

- [x] **Step 1: Write the failing tests.**
  - `test_fold_strips_marks_and_case`: `"España Blvd."` folds to `"espana blvd"`.
  - `test_spot_names`, parametrized:
    - `"España Blvd. cor. Lacson Ave."` and `"Lacson Avenue corner Espana Boulevard"` both give `{espana, lacson}`
    - `"EDSA Kamuning (SB)"` gives `{"edsa kamuning"}`
    - `"A. Maceda St., Sampaloc, Manila"` gives `{maceda, sampaloc}`
    - `"Quezon Ave., Quezon City"` gives `{quezon}`
    - `"Sto. Domingo St."` gives `{"santo domingo"}`
    - `"Araneta Ave. - Ma. Clara St."` gives `{araneta, "ma clara"}`
    - `"Manila"` gives the empty set
  - `test_same_spot`: `{espana, lacson}` against itself, reordered, is True. `{araneta, quezon}` against `{quezon}` is False. One equal name each is True. `{a}` against `{a, b}` is False, and two empty sets are False.
  - `test_city_name`: `Las Piñas`, `QC`, `City of Manila` and `Pateros` are found; `quezon` and `Calamba` give None.
  - `test_poster_kind`, parametrized:
    - `mmda`: `MMDA`, `Metropolitan Manila Development Authority`
    - `city`: `Quezon City`, `Quezon City DRRMO`, `Quezon City Government`, `Manila Public Information Office`, `City of Manila`, `Pasig City Information Office`
    - `other`: `Brgy. Damayang Lagi`, `Barangay Tumana`, `QC Police District`, `BFP Manila`, `Manila Bulletin`, `Mayor Juan dela Cruz`, `Quezon`
  - `test_same_date_and_key_join`; `test_shared_name_joins_across_cities`; `test_other_dates_never_join` (the same spot on the next day gives two events); `test_links_join_both_ways`; `test_joined_pairs_join`
  - `test_empty_keys_join_on_one_date`: two rows whose spot text is `"Manila"`, on one date, share an event; on two dates they don't.
  - `test_city_names_never_join_events` (Review Focus 4): `"A. Maceda St., Manila"` and `"Dimasalang St., Manila"` on one date give two events, and so do `"Quezon Ave., Quezon City"` and `"Kamuning Rd., Quezon City"`.
  - `test_event_ids_follow_the_lowest_photo_id`: `E01` holds `A001`, and every id passes `is_id`.
  - `test_event_numbers_sort_past_99`: `E100` sorts after `E99` by `event_number`.
  - `test_near`: hashes 6 bits apart are near, 7 bits apart aren't, and a blank is never near.
- [x] **Step 2:** Run `uv run --locked --script eval/data/tests/run_tests.py -k "places or events"`. Expected: FAIL, with `ModuleNotFoundError: No module named 'places'`.
- [x] **Step 3:** Implement.
- [x] **Step 4:** Run the tests again. Expected: all pass.
- [x] **Step 5:** Commit `feat(data): add spot normalisation, the same-spot test and flood events`.

*Evidence (Task 6, Oct 29): commits 00b42d3, 51a9a80 and 514d1da. `uv run --locked --script eval/data/tests/run_tests.py`: 150 passed, also with `-W error`; ruff, the plan-leak check, the account-ID scan and gitleaks clean. The office words are tied to the guide's list by a test. The task review found that the plan's normalisation let C224 match two different corners through a barangay, district or lane name (a real QC pair) and let run-together corners split one flood into two events; ruling S-R9 (one fix round) marks barangay, zone and Manila district names so `same_spot` never counts them, requires at least two unmarked shared names (one plan-pinned case reversed), joins events whose names sit inside each other, normalises `C-5`/`C5`, and adds the guide's linking sentence. The re-review was clean.*

### Task 7: Set A and A-neg log checks, matching and facts (C209, C223)

**Files:**
- Create: `eval/data/setlogs.py`
- Modify: `eval/data/tests/synth.py`: add `set_a_row(**cells) -> dict` and `a_neg_row(**cells) -> dict`, rows that pass every check by default
- Test: `eval/data/tests/test_setlogs.py`

**Interfaces:**
- Consumes: `table.read_table`, `table.Finding`, `table.Fact`; `formats`; `places.spot_names`, `spot_key`, `same_spot`, `city_name`, `poster_kind`.
- Produces, in `setlogs.py`:
  - `PHOTO_COLUMNS = ("platform", "post_url", "poster", "post_time_pht", "spot_text", "city", "photo_file", "reference_visible", "label_in_image", "faces_or_plates", "same_spot_as")`, plus `surface` for A-neg: the columns a repeated id must repeat. `logged_on`, `alert_time_pht`, `level_label_raw`, `passability_raw`, `photo_in_alert_post`, `alert_poster`, `alert_spot_text` and `notes` belong to each row.
  - `@dataclass class Photo`, with these fields: `photo_id`, `set` (`A` or `A-neg`), `photo_file`, `event_date`, `post_time` (datetime), `city`, `metro_manila`, `spot_key`, `same_spot_as` (frozenset), `poster_kind`, `match`, `level_label_raw`, `passability_raw`, `other_alerts_raw`, `label_in_image`, `reference_visible`, `faces_or_plates`, `surface`, `notes`, `rows` (int)
  - `@dataclass class SetCheck: photos: list[Photo]; problems: list[Finding]; warnings: list[Fact]; rows: int`
  - `check_set_log(log: Path, photos_dir: Path, *, set_name: str) -> SetCheck`, where `set_name` is `A` or `A-neg`
  - `match_alerts(rows: Sequence[Mapping[str, str]]) -> tuple[str, str, str, str]`: `(match, level_label_raw, passability_raw, other_alerts_raw)` for one photo's rows
- **Columns (C209):** Set A requires `SET_A_COLUMNS`; A-neg requires `A_NEG_COLUMNS` (the 17 plus `surface`). `same_spot_as`, `alert_poster` and `alert_spot_text` are optional columns in both, and A-neg ignores the two alert columns.
- **Required values:**
  - **Set A, every row:** `candidate_id`, `logged_on`, `platform`, `post_url`, `poster`, `post_time_pht`, `spot_text`, `city`, `photo_in_alert_post`, `photo_file`, `reference_visible`, `label_in_image` and `faces_or_plates`
  - **Set A, separate-post rows also:** `alert_poster`, `alert_spot_text` and `alert_time_pht`
  - **A-neg, every row:** `candidate_id`, `logged_on`, `poster`, `post_time_pht`, `spot_text`, `city`, `photo_file`, `reference_visible`, `label_in_image`, `faces_or_plates`, `level_label_raw` (exactly `none`) and `surface`; on a `commons` row also `licence` (in `COMMONS_LICENCES`) and `credit` (Task 13c)
  - **May be blank:** `level_label_raw` and `passability_raw` in Set A (C207: MS2 checks no label, and the harness reports a blank as unmapped), `alert_time_pht` on same-post rows, `same_spot_as` and `notes`
- **Problems** (the `kind`; the ref is the id, or `row <n>` for a bad id):
  - `missing_column` (ref `log`)
  - `bad_id`
  - `id_file_mismatch`: `photo_file` isn't `<id>.<jpg|jpeg|png>` in any case
  - `differs`: a repeated id whose `PHOTO_COLUMNS` differ after stripping, and, for list columns, lowercasing
  - `file_missing` (a stat only)
  - `bad_date`, `bad_time`, `not_in_list`
  - `missing`: a required value is blank
  - `bad_link`: a `same_spot_as` id naming no photo of the same set on the same date
- **Facts:**
  - `city`: `city_name`, or the text as logged, with `metro_manila`
  - `poster_kind`: Set A by `places.poster_kind`; every A-neg row is `other`
  - `event_date`: the date of `post_time_pht`
  - `notes`: the photo's rows' distinct non-blank notes, in log order, joined by ` | `
  - `match` (C223), Set A only (A-neg's is blank):
    - A row fits when `photo_in_alert_post = yes`, or when all three hold: its `alert_poster` is `mmda` or `city`; `same_spot` holds between the names of `spot_text` and `alert_spot_text`; and the alert's time is within 30 minutes of `post_time_pht`.
    - The nearest fitting row gives `match` (`same_post` or `separate_post`), `level_label_raw` and `passability_raw`. Nearest means the time distance. A same-post row without `alert_time_pht` counts as 0, and ties go to same-post rows, then log order.
    - The other fitting rows' `level_label_raw` go to `other_alerts_raw`, joined by `;` in log order.
    - With no fitting row: `match = none` and blank labels.
- **Warnings:** `metro_manila=no`, `poster_kind=other` (Set A) and `match=none`.
- No `Finding` or `Fact` ever holds a cell's text.

- [x] **Step 1: Write the failing tests.**
  - `test_each_problem_kind`, parametrized over the kinds above; each case gives exactly its finding.
  - `test_each_required_value`, parametrized over each set's required values: a blank one gives `<id> <column>: missing`.
  - `test_bad_id_names_the_row_not_the_cell`: `candidate_id = "Espana"` gives `row 1 candidate_id: bad_id`, and `Espana` appears in no finding.
  - `test_todays_17_column_template_works`: same-post rows without the three optional columns give no problem and `match = same_post`.
  - `test_separate_post_row_needs_its_alert_columns`: on the 17-column template, a `photo_in_alert_post = no` row gives `A001 alert_poster: missing`.
  - Matching (V1):
    - `test_same_post_alert_fits`
    - `test_separate_alert_fits_within_30_minutes_at_the_same_spot`
    - `test_thirty_minutes_is_inclusive`
    - `test_separate_alert_misses`, parametrized over 31 minutes, a spot sharing one name, and the poster `Manila Bulletin`. Each gives `match = none` and the warning `A001 match=none`.
    - `test_nearest_of_several_alerts`: three fitting rows at 25, 5 and 15 minutes. The labels come from the 5-minute row, and `other_alerts_raw` holds the other two in log order.
  - `test_outside_metro_manila_is_a_warning`: `Calamba` gives `metro_manila = no`, the city kept as logged, and `A001 metro_manila=no`, with no problem.
  - `test_poster_other_is_a_warning`
  - `test_notes_join_in_log_order`: two rows of one photo with notes `a` and `b` give `a | b`.
  - `test_a_neg_rows` (Task 13c adds `test_a_neg_accepts_commons_rows` and `test_commons_row_needs_licence_and_credit`): a row with `poster` `own`, level `none` and `surface` `dry` gives `poster_kind = other`, a blank `match`, and no problem or warning. `poster` `stranger` gives `not_in_list`, a level other than `none` gives `not_in_list`, and a blank `surface` gives `missing`.
  - `test_a_neg_log_made_from_the_checklist_reads_cleanly` (C209): a log with the 17 columns plus `surface`, and no optional column, gives no problem.
  - `test_a_neg_log_from_the_template_reads_cleanly`: a log with the template's columns, plus blank alert columns, gives no problem.
  - `test_spreadsheet_saved_log_reads_cleanly` (Review Focus 1)
  - `test_findings_hold_no_cell_text`: a sentinel in every column of rows with problems, and no sentinel in any `str()` of a finding or fact
- [x] **Step 2:** Run `uv run --locked --script eval/data/tests/run_tests.py -k setlogs`. Expected: FAIL, with `ModuleNotFoundError: No module named 'setlogs'`.
- [x] **Step 3:** Implement.
- [x] **Step 4:** Run the tests again. Expected: all pass.
- [x] **Step 5:** Commit `feat(data): check the Set A and A-neg logs and match photos to alerts`.

*Evidence (Task 7, Oct 29): commits b0839e6 and 76409e5. `uv run --locked --script eval/data/tests/run_tests.py`: 234 passed, also with `-W error`; ruff, the plan-leak check, the account-ID scan and gitleaks clean; mutation checks caught 25 of 25 and then 14 of 14. Matching follows C223 and S-R9 (two-name spots; ties deterministic), output holds only ids, fixed kinds and counts (C201), and S-R4's `alert_poster=other` warning is in. The task review found that same-post rows skip the spot test, so a multi-spot post could attach another corner's label; one fix round (S-R10) added the warnings `same_post=several` and `nearest=tied` and the guide sentence, refused a `;` in a label and an unknown header column, and made `missing` mean a blank cell and `file_missing` a photo not on disk in both this task's checks and `m8_sheet` (Task 4b's text above is updated to match). The re-review was clean.*

### Task 8: Passability classes, M8, consent and the intake command (§5.3, C204, C208, C218)

**Files:**
- Create: `eval/data/strata.py`, `eval/data/otherlogs.py`, `eval/data/intake.py`, `eval/data/intake.py.lock`
- Test: `eval/data/tests/test_strata.py`, `eval/data/tests/test_otherlogs.py`, `eval/data/tests/test_intake.py`

**Interfaces:**
- Consumes: `setlogs.check_set_log`, `SetCheck`; `events.group_events`, `EventInput`; `places.spot_key`; `table.*`; `formats.*`; `guards.refuse_sealed`.
- Produces, in `strata.py` (standard library). It reads the stated passability only, to pick a C204 group; MS2 maps no level label, and the harness maps every label for scoring (C207). The tracker confirmed this reading at 5:15 PM (Window 4's v0.7 item 4.2, `e07663c`).
  - `class_of(passability: str) -> str | None`: `eval/rules.md` §2's passability table. The text is folded: lowercase, punctuation as spaces, spaces collapsed. It must then equal a listed variant exactly, with `(types of)` and `(sedan)` optional. The result is `PATV`, `NPLV`, `NPATV`, or None.
  - `deep_row(passability_raw: str) -> bool`: `class_of(passability_raw)` is `NPLV` or `NPATV`
- Produces, in `otherlogs.py`:
  - `@dataclass class M8Check: rows: list[dict[str, str]]; problems: list[Finding]; missing_photo_rows: list[str]`
  - `check_m8(path: Path, set_a_ids: Collection[str], *, allow_missing: bool = False) -> M8Check`. Refs read `<photo_id> <ref_id>.<column>`, for example `A001 R2.x: out_of_range`. The kinds:
    - `missing_column`, `unknown_photo`
    - `bad_ref`: `P1` only for `photo` rows, `R<n>` for the rest
    - `duplicate_ref`
    - `not_in_list`: the kind; `vehicle_type` and `body_waterline` on vehicles; `waterline` on wheels and on people (each against its own list); `quality`; each subset tag
    - `out_of_range`: `x` and `y` on references must be numbers from 0 to 1
    - `missing`: a required value
    - `no_photo_row` (`<id> m8: no_photo_row`), unless `allow_missing`
  - `check_consented(path: Path) -> tuple[list[Finding], list[Fact]]`: ids `S…`; `file` beside the log (a stat); `kind`; `taken_pht`; `lat` from −90 to 90 and `lon` from −180 to 180, as decimals; `consent_file` named and present. A `consent_version` outside `APPROVED_CONSENT["m9"]` is the problem `not_approved`.
  - `check_sidewalls(path: Path) -> tuple[list[Finding], list[Fact]]` (only for a sidewall photo Rene still takes; from Oct 29 M11's codes come from public specs): refs `sidewalls row <n>`; `photo_file` beside the log; `vehicle`; `taken_on`; `consent_file` present. Two warnings: `consent_version=unapproved`, and `code=mismatch` when `checked_code` is filled and differs from `tire_code` (compared in capitals, without spaces).
- Produces, in `intake.py` (PEP 723, `dependencies = []`):
  - `@dataclass class IntakeResult: set_a: SetCheck; a_neg: SetCheck; m8: M8Check | None; problems: list[Finding]; warnings: list[Fact]`
  - `run_intake(*, set_a_log: Path, set_a_photos: Path, a_neg_log: Path, a_neg_photos: Path, m8: Path | None = None, consented: Path | None = None, sidewalls: Path | None = None, allow_missing_m8: bool = False) -> IntakeResult`, which `split` reuses
  - `main(argv=None) -> int`, with `--set-a-log --set-a-photos --a-neg-log --a-neg-photos [--m8] [--consented] [--sidewalls]`. It prints, in order:
    - `set_a rows=<r> photos=<p> no_class=<k>`, where `no_class` counts Set A photos whose stated `passability_raw` maps to no class (blank or unlisted). Some official lists give inches with no class, so the count shows before the split how many photos C204 can't stratify as deep.
    - `a_neg rows=<r> photos=<p>`
    - `m8 rows=<n> photo_rows=<k>`, when given
    - each problem, then each warning
    - `events set_a=<n> largest=<k> single=<m>`, the same for `a_neg`; these events come from the logs' text alone, so no duplicates are joined
    - `problems=<n> warnings=<m>`

    It exits 1 on any problem, 0 otherwise, and 2 when refused. It writes no file.

- [x] **Step 1: Write the failing tests.**
  - `test_rules_md_passability_table`: parse `eval/rules.md` §2's passability table, found by its header row, `Passability as written` (the level table comes first under the `## 2.` heading). Expand each row's comma-separated variants, with and without `(types of)` and `(sedan)`; `class_of` gives each row's class.
  - `test_deep_rows`, parametrized:
    - True: `"NPLV"`, `"NPATV"`, `"Not passable to light vehicles"`, `"not passable to all types of vehicles"`
    - False: `"PATV"`, `"passable to light vehicles"`, `""`, `"closed to traffic"`, and `"knee deep"`, since a level label in the class column states no class
  - One test per M8 problem kind; `test_m8_photo_row_only_is_fine`; `test_allow_missing_turns_off_no_photo_row`
  - `test_m9_version_must_be_approved`: with `APPROVED_CONSENT["m9"]` patched to `{"M9-v2"}`, `M9-v2` passes and `M9-v1` is a problem.
  - `test_m11_version_only_warns`; `test_sidewall_code_mismatch_warns`
  - `test_intake_prints_counts_problems_warnings_and_events`: the exact lines for a small synthetic data set
  - `test_intake_counts_photos_without_a_class`: 3 photos whose nearest alerts give `NPLV`, blank and `12"` print `no_class=2`.
  - `test_intake_exit_codes`: 0, 1 and 2
  - `test_intake_reads_no_photo_bytes`: `synth.opened_paths` on `intake.py` shows no `open` under either photos folder.
  - `test_intake_writes_nothing`: the files under `tmp_path` are the same before and after.
  - `test_intake_output_holds_no_log_text`: sentinels in every text column (links, spots, labels, notes, posters, cities and alert columns), and none in stdout or stderr
  - `test_intake_refuses_sealed_paths`, for each flag
  - `test_intake_imports_only_the_standard_library`: a fresh interpreter imports `intake`, and `numpy`, `cv2` and `py7zr` aren't in `sys.modules`.
- [x] **Step 2:** Run `uv run --locked --script eval/data/tests/run_tests.py -k "strata or otherlogs or intake"`. Expected: FAIL, with `ModuleNotFoundError: No module named 'strata'`.
- [x] **Step 3:** Implement, then run `uv lock --script eval/data/intake.py`.
- [x] **Step 4:** Run the tests again. Expected: all pass. `uv run --locked --script eval/data/intake.py --help` exits 0.
- [x] **Step 5:** Commit `feat(data): add the intake command with the class count and the M8, consent and sidewall checks`.

*Evidence (Task 8, Oct 29):*
- **Commits:** 8922515, a4d9d7a and 2d6a15e.
- **Tests:** `uv run --locked --script eval/data/tests/run_tests.py` gives 357 passed, also with `-W error`. `uv run --locked --script eval/data/intake.py --help` exits 0.
- **Checks:** ruff, the plan-leak check, the account-ID scan and gitleaks are clean. Mutation checks caught 53 of 53, then 9 of 9.
- **The task review approved it,** with no Critical or Important findings:
  - the deep rule matches `eval/rules.md` §2's passability table
  - an unapproved consent version can't pass (C218)
  - output holds only ids, fixed kinds and counts (C201)
  - a malformed log is named
- **One fix round (S-R11):**
  - A log that is missing or not UTF-8 is named (`<log> log: file_missing` or `not_utf8`).
  - M8 isn't read after a Set A `missing_column`, so no noise lines follow it.
  - The column checks have explicit branches.
  - A repeated consented `item_id` is a problem.
  - The guide explains the new kinds.

  The re-review was clean.

### Task 9: Photo facts and the write-once archive (§5.5 step 2, C205)

**Files:**
- Create: `eval/data/photos.py`, `eval/data/archive.py`
- Test: `eval/data/tests/test_photos.py`, `eval/data/tests/test_archive.py`

**Interfaces:**
- Produces, in `photos.py`, which sets `os.environ["OPENCV_IO_MAX_IMAGE_PIXELS"] = "50000000"` before `import cv2`:
  - `@dataclass(frozen=True) class PhotoFacts: sha256: str; dhash: str; decodes: bool; width: int | None; height: int | None`
  - `photo_facts(data: bytes) -> PhotoFacts`: decodes with `cv2.imdecode(..., cv2.IMREAD_COLOR)`. A `cv2.error` or `None` gives `decodes=False`, with a blank dHash and sizes. The dHash: grayscale, `cv2.resize` to 9 × 8 with `INTER_AREA`, a bit where the left pixel is brighter than its right neighbour, row by row, as 16 lowercase hex digits.
- Produces, in `archive.py`:
  - `@dataclass(frozen=True) class ArchiveFacts: file: str; size: int; sha256: str`, where `file` is the name only
  - `write_sealed_archive(path: Path, password: str, members: Sequence[tuple[str, bytes | Path]]) -> ArchiveFacts`:
    - Before creating anything, it raises `ValueError` for an arcname that is empty, absolute, holds `\` or a `..` part, or repeats.
    - It opens `py7zr.SevenZipFile(path, "x", password=password, header_encryption=True)`, writes bytes with `writestr(data, arcname)` and files with `write(path, arcname)`, and closes.
    - Then it hashes the written file's bytes.

- [x] **Step 1: Write the failing tests.**
  - `test_photo_facts_of_a_jpeg`: the SHA-256 equals hashlib's, the sizes are right, and the dHash has 16 hex digits.
  - `test_reencoded_copy_is_near`: quality 95 and 70 copies are near (`events.near`).
  - `test_different_photos_are_far`: seeds 1 and 2 aren't near.
  - `test_photo_facts_for_files_that_do_not_decode` (Review Focus 2): random bytes, a cut-off JPEG header and `b""` each give `decodes=False` and a blank dHash, with the SHA-256 still set.
  - `test_decodes_is_no_over_50_megapixels`: in a fresh interpreter with `OPENCV_IO_MAX_IMAGE_PIXELS` removed from its environment, a 16 × 16 JPEG whose SOF0 header declares 10,000 × 6,000 gives `decodes=False`, and the unchanged JPEG gives True. This is MS1's R25 test method; OpenCV's docs warn that setting the variable from Python may not reach its Windows build, and MS1's test shows it does here.
  - `test_archive_round_trip_with_the_test_phrase`: members from bytes and from a file. Opened in the test with `py7zr.SevenZipFile(path, "r", password=TEST_PHRASE)`, `getnames()` lists exactly the arcnames, and `extractall(path=...)` gives equal bytes.
  - `test_names_are_encrypted`: opening without a password raises `py7zr.exceptions.PasswordRequired`, and the file's bytes hold no member name in UTF-8 or UTF-16-LE.
  - `test_never_overwrites`: an existing path raises `FileExistsError`, and its bytes are unchanged.
  - `test_bad_arcnames_are_refused_before_writing`: `../x`, `/x`, `a\b` and a repeat each raise `ValueError`, and no file is created.
  - `test_facts_are_the_file_bytes`: the size and SHA-256 equal the file's.
  - `test_archive_module_never_reads_an_archive`: its source has exactly one `SevenZipFile(` call, with mode `"x"`, and none of py7zr's reading methods (`.extract`, `.getnames(`, `.namelist(`, `.list(`, `.test(`, `.testzip(`).
- [x] **Step 2:** Run `uv run --locked --script eval/data/tests/run_tests.py -k "photos or archive"`. Expected: FAIL, with `ModuleNotFoundError: No module named 'photos'`.
- [x] **Step 3:** Implement.
- [x] **Step 4:** Run the tests again. Expected: all pass.
- [x] **Step 5:** Commit `feat(data): add photo facts and the write-once encrypted archive`.

*Evidence (Task 9, Oct 29):*
- **Commits:** a369ffa, d04de77 and bed8e3d.
- **Tests:** `uv run --locked --script eval/data/tests/run_tests.py` gives 398 passed, also with `-W error`.
- **Checks:** ruff, the plan-leak check, the account-ID scan and gitleaks are clean.
- **What the review confirmed:**
  - No member name or content reaches the file in plaintext: header encryption plus AES on the contents, each pinned by a test.
  - An existing file is never overwritten.
  - The 50-megapixel cap is real in a fresh interpreter.
  - The dHash is MSB-first, row by row.
  - 14 of 16 mutants were caught.
- **One fix round (S-R12)** moved every foreseeable failure before the archive exists:
  - each member must be `bytes` or a regular, unlinked file
  - members are read once
  - arcnames must be printable, with repeats compared by casefold
  - a password must encode as UTF-16, refused with no chained exception
- **A golden dHash pins `INTER_AREA` and BGR-to-gray:** `9ca95593565bb5b7`, worked out first and recomputed independently by the re-review.
- **Extras the review accepted:** an empty password and `.`, `..` or empty arcname parts are refused. The re-review was clean.

### Task 10: The stratified draw (C204, as amended)

**Files:**
- Create: `eval/data/draw.py`
- Test: `eval/data/tests/test_draw.py`

**Interfaces:**
- Consumes: `events.event_number` (Task 6). An event's `deep` flag comes from `strata.deep_row` (Task 8), applied by the caller.
- Produces, in `draw.py`:
  - `SPLIT_SEED = 20261030`
  - `SHARES = {"A": (Fraction(2, 5), Fraction(9, 20)), "A-neg": (Fraction(1, 3), Fraction(2, 5))}`, each a target and a cap
  - `class TooFewEvents(ValueError)`, which holds the set's name
  - `@dataclass(frozen=True) class GroupDraw: group: str; sealed: frozenset[str]; dev: frozenset[str]; rows: int; sealed_rows: int; moved: str | None`, where `moved` is `smallest_to_sealed` or None. The cap keeps the sealed side under half a group's rows, so the dev side is never empty.
  - `draw_group(sizes: Mapping[str, int], *, group: str, target: Fraction, cap: Fraction, seed: int = SPLIT_SEED) -> GroupDraw`:
    - The order: `sorted(sizes, key=event_number)`, shuffled with a fresh `random.Random(seed)`.
    - The walk: an event goes to sealed only when the sealed rows plus its size stay at or under `cap × rows`, and the walk stops once the sealed rows reach `target × rows`.
    - Both sides: with 2 or more events and nothing sealed, the group's smallest event (fewest rows, then lowest number) moves to sealed, and `moved` says so.
  - `draw_set(set_name: str, events: Mapping[str, tuple[int, bool]], *, seed: int = SPLIT_SEED) -> dict[str, GroupDraw]`: takes each event's `(rows, deep)`, draws groups `deep` and `other` separately, each with `seed` and the set's shares, and leaves out empty groups. A-neg has `other` only, since it states no class. Raises `TooFewEvents` when the set has fewer than 2 events. The tests pass other seeds; the split passes none, so it always draws with `SPLIT_SEED`.

- [x] **Step 1: Write the failing tests.**
  - `test_deep_events_land_on_both_sides`: a Set A of 5 deep events (1 or 2 rows) and 15 others (1 to 3 rows). Each group has an event on each side, under `SPLIT_SEED` and seven other seeds.
  - `test_same_seed_same_split`: `draw_set` twice, and once more with the events given in reverse order, gives identical results.
  - `test_group_of_two_or_more_has_both_sides`: group sizes 2 to 8, with event sizes all 1, then `[3, 1, 1, …]`, then one event of 60% of the rows. Both sides are always non-empty, and `moved` is set whenever the walk alone sealed nothing.
  - `test_two_single_row_events_move_the_smallest`: `{E01: 1, E02: 1}` seals nothing by the walk (1 is over 0.9 rows). `E01` moves to sealed, and `moved == "smallest_to_sealed"`.
  - `test_shares_and_cap`: 20 one-row events seal exactly 8. A group of 20 rows holding a 10-row event never seals that event by the walk.
  - `test_a_neg_shares`: 15 one-row events seal 5.
  - `test_single_event_group_stays_dev`: a deep group of one event stays dev, with no move.
  - `test_fewer_than_two_events_stops`: a set with one event raises `TooFewEvents("A-neg")`.
  - `test_golden_draw`: a fixed 12-event input seals exactly the events written in the test. This pins `random.Random(20261030)` on Python 3.13. The expected set is worked out before `draw.py` exists: in a REPL, shuffle each group's events, sorted by number, with a fresh `random.Random(20261030)`, as `draw_group` will, then walk that order by hand against the cap and target. The test therefore fails first (RED), and its value never comes from a green run.
- [x] **Step 2:** Run `uv run --locked --script eval/data/tests/run_tests.py -k draw`. Expected: FAIL, with `ModuleNotFoundError: No module named 'draw'`.
- [x] **Step 3:** Implement.
- [x] **Step 4:** Run the tests again. Expected: all pass.
- [x] **Step 5:** Commit `feat(data): add the stratified split draw`.

*Evidence (Task 10, Oct 29):*
- **Commits:** d50159d and 4f20f3a.
- **Tests:** `uv run --locked --script eval/data/tests/run_tests.py` gives 429 passed, also with `-W error`.
- **Checks:** ruff, the plan-leak check, the account-ID scan and gitleaks are clean.
- **`test_golden_draw`:** its values were worked out by hand before `draw.py` existed. They are Task 13's synthetic Set A: under `SPLIT_SEED` it seals E01, E02, E07 and E09, 8 of 20 rows, exactly 2/5.
- **The review approved it:**
  - The golden draw was re-derived independently.
  - 29,383 random groups match a walk written from C204's words.
  - The draw is independent of input order.
  - Every comparison is exact.
- **One test-only round (S-R15)** pinned each group's own fresh shuffle and the 2-event draw. The controller confirmed that a reseeded-deep-group mutant and a `< 3` mutant each fail exactly their new test.
- **A Set A of exactly 2 events, one deep and one other, seals nothing.** It is the only such case. Task 12's audit stops the split on it (`set_one_sided`, S-R14).

### Task 11: Manifests and the three record kinds (C207, C216, §5.9)

**Files:**
- Create: `eval/data/manifest.py`, `eval/data/record_io.py`
- Test: `eval/data/tests/test_manifest.py`, `eval/data/tests/test_record_io.py`

**Interfaces:**
- Consumes: `setlogs.Photo`, `photos.PhotoFacts`, `archive.ArchiveFacts`, `draw.GroupDraw`, `formats.MANIFEST_COLUMNS`, `M8_COLUMNS`, `table.*`.
- **Standard library only:** `record_io.py` and `manifest.py` load only the standard library. They import `photos`, `archive` and `setlogs` names only under `typing.TYPE_CHECKING`, because the audit, `seal_set_d`, `water_check` and `freeze_record` import `record_io`, and a load-time import would bring in cv2 or py7zr, which those tools' tests and `--help` runs can't load.
- Produces, in `manifest.py`:
  - `manifest_row(photo: Photo, facts: PhotoFacts, *, event_id: str, split: str, duplicate_of: str) -> dict[str, str]`:
    - the cells in `MANIFEST_COLUMNS`
    - `duplicate` is `yes` when `duplicate_of` is set and isn't the photo's own id
    - `decodes` is `yes` or `no`, with blank sizes when it doesn't decode
    - `same_spot_as` is sorted and joined by `;`, and `surface` is set for A-neg
  - `m8_rows(rows: Sequence[Mapping[str, str]], photo_ids: Collection[str]) -> list[dict[str, str]]`: those photos' rows, in input order, in `M8_COLUMNS`
  - `counts(rows: Sequence[Mapping[str, str]]) -> dict`: `{"rows", "events", "facts": {fact: {value: count}}}`, over `poster_kind`, `match`, `metro_manila`, `label_in_image`, `reference_visible`, `duplicate`, `decodes` and, for A-neg, `surface`
- Produces, in `record_io.py`, the one source for every record's format:
  - `RECORD_KINDS = {"eval/data/split.py": "split", "eval/set_b/generate.py": "set_b_final", "eval/data/seal_set_d.py": "set_d"}`, and `record_kind(record: Mapping) -> str`, from its `tool`. Any other tool raises `ValueError`.
  - `git_state(repo: Path) -> dict`: `{"commit": <40 hex or "unknown">, "dirty": bool}`, from `git rev-parse HEAD` and `git status --porcelain`
  - `manila_now() -> str`: ISO 8601 with `+08:00`, to the second
  - `base_record(tool: str, repo: Path) -> dict`: `tool`, `git`, `date` and `python` (`platform.python_version()`)
  - `archive_block(facts: ArchiveFacts) -> dict`: `{"file", "size", "sha256"}`
  - `record_bytes(record: Mapping) -> bytes` and `write_record(path: Path, record: Mapping) -> str`, which returns `table.write_new(path, record_bytes(record))`: the parent folder is created, the file is created exclusively, and its SHA-256 is returned
  - `split_record(*, repo: Path, inputs: Mapping[str, str], draws: Mapping[str, Mapping[str, GroupDraw]], sides: Mapping[str, Mapping[str, Sequence[Mapping[str, str]]]], missing_m8: int, dev_files: Mapping[str, str]) -> dict`. This is the core, also written into the archive:
    - `base_record("eval/data/split.py", repo)`, and `seed`
    - `inputs`: the SHA-256 of `set_a_log`, `a_neg_log` and `m8`
    - `sets`: for each set, `dev` and `sealed` as `counts(...)`; `share` (sealed rows as `"k/n"`) and `share_in_range` (A: 40% to 45%; A-neg: a third to 40%); and `groups`, each with `{"events", "rows", "dev": {"events", "rows"}, "sealed": {"events", "rows"}, "moved"}`
    - `missing_m8_photo_rows`, `audit` (`"PASS"`), and `dev_files`: the SHA-256 of each development file, under the keys `set_a_manifest`, `set_a_m8` and `a_neg_manifest`

    The committed record adds `archive` (`archive_block`) and `copy_check` (`rehash_ok`: the copies whose re-hash matched, of all copies; `matched_sealed`: 0).
  - `set_b_final_record(*, repo: Path, counts: Mapping, generator_version: str, generator_seed: int, inputs: Mapping[str, str]) -> dict`: `base_record("eval/set_b/generate.py", repo)`, plus:
    - `generator_version` and `generator_seed`
    - `inputs`: the SHA-256 of the final `cars.csv`, the final masks' `files.txt` and the development `cars.csv`
    - `counts`: `cars`, `photos`, `crops`, `wheels`, `wheels_without_rim`, `drops` by cause, `warnings`, and crops by `band`, `size_bin`, `vehicle_type` and `view`. `cars` and `crops` count only what reaches `truth.csv`, and a dropped car counts under `drops` only.
    - `overlap_check: "PASS"`

    No car, crop or photo id.
  - `set_d_record(*, repo: Path, counts: Mapping, inputs: Mapping[str, str], extends: Mapping | None) -> dict`: `base_record("eval/data/seal_set_d.py", repo)`, plus `inputs` (the SHA-256 of `set_d_log.csv`), `counts` (`photos`, by `vehicle_type`, by `wheel`), and `extends` (`file`, `sha256`) when given. No id.

- [x] **Step 1: Write the failing tests.**
  - `test_manifest_columns_and_values`: a synthetic photo gives an exact row.
  - `test_duplicate_fields`: in a group, the lowest id gets `duplicate = no` and `duplicate_of = A003`, its own id; the others get `yes` and `A003`; an ungrouped photo gets `no` and a blank.
  - `test_undecodable_row`: a blank dHash, width and height, and `decodes = no`.
  - `test_counts_by_fact_value`
  - `test_split_record_per_group_counts`: the counts of two groups' draws reach the record exactly.
  - `test_record_kinds`: each builder's `tool` gives its kind through `record_kind`, and an unknown tool raises `ValueError`.
  - `test_set_b_and_set_d_records_hold_their_input_hashes`
  - `test_record_holds_no_ids_labels_links_or_spots`: each builder, given rows full of sentinels, writes bytes with no sentinel, no match for `\b[AN][0-9]{3}\b`, and none for `\bE[0-9]{2,}\b`, `\bB[0-9]{2}\b` or `\bD[0-9]{2}\b`.
  - `test_record_bytes_are_stable`: the same dict in another key order gives the same bytes, ASCII with a final newline.
  - `test_write_record_never_overwrites`
  - `test_record_io_imports_only_the_standard_library`: a fresh interpreter imports `record_io`, and `numpy`, `cv2` and `py7zr` aren't in `sys.modules`.
- [x] **Step 2:** Run `uv run --locked --script eval/data/tests/run_tests.py -k "manifest or record_io"`. Expected: FAIL, with `ModuleNotFoundError: No module named 'manifest'`.
- [x] **Step 3:** Implement.
- [x] **Step 4:** Run the tests again. Expected: all pass.
- [x] **Step 5:** Commit `feat(data): build the manifests and the three record kinds`.

*Evidence (Task 11, Oct 29):*
- **Commits:** 6faff57 and 6c4ac30.
- **Tests:** `uv run --locked --script eval/data/tests/run_tests.py -W error` gives 476 passed.
- **Checks:** ruff format and check, the plan-leak check (210 files), the account-ID scan (172 files) and gitleaks are clean.
- **RED:** the two expected `ModuleNotFoundError`s, for `manifest` and `record_io`.
- **The review approved it:** spec compliant, with no Critical or Important findings.
- **One fix round (S-R16)** added one guard for every record writer: `record_bytes` refuses any record whose keys or text values hold an id-shaped token, so a caller's counts can't carry a final or sealed id into a committed record. The same round made `record_kind` refuse a record that isn't a mapping, and isolated every git-running test. The scoped re-review found every finding addressed.

### Task 12: The audit (W18, C220)

**Files:**
- Create: `eval/data/audit.py`, `eval/data/audit.py.lock`
- Test: `eval/data/tests/test_audit.py`

**Interfaces** (standard library only):
- Consumes: `events.group_events`, `EventInput`, `near`; `strata.deep_row`; `places.names_of`; `record_io.record_kind`, `record_io` builders (for the tests); `table.*`; `guards.*`.
- Produces, in `audit.py`:
  - `rebuild_events(rows: Sequence[Mapping[str, str]]) -> dict[str, str]`: `group_events` over each row's `event_date`, `spot_key` and `same_spot_as`, with joined pairs from `duplicate_of`, equal `photo_sha256` and near `photo_dhash`, within one set
  - `copy_check(dev: Sequence[Mapping[str, str]], sealed: Sequence[Mapping[str, str]]) -> list[tuple[str, str]]` (C219): the one cross-side photo check, which `check_split` and the split's copy check (Task 13) both call. Across both sets, a dev row whose `photo_sha256` equals any sealed row's gives `(<dev id>, "sha256")`; otherwise, one whose `photo_dhash` is near any sealed row's (`near`) gives `(<dev id>, "near_identical")`.
  - `check_split(sides: Mapping[str, Sequence[Mapping[str, str]]], groups: Mapping[str, Mapping] | None) -> list[str]`: the violations, naming dev ids only. `sides` is `{"dev": rows, "sealed": rows}`, each side holding both sets' manifest rows, which the `set` column tells apart. `groups` is `{set: record["sets"][set]["groups"]}`, or None before the record exists. Events and event ids are compared within each set, since ids are numbered per set (§5.9). SHA-256 and near-identical pairs are compared across both sets, by `copy_check`.
    - `event_on_both_sides <dev id>`, `event_id_on_both_sides <dev id>`, `sha256_on_both_sides <dev id>` and `near_identical_on_both_sides <dev id>`
    - `group_one_sided <set> <group>`: a group of 2 or more rebuilt events, `deep` when `deep_row` holds on any row's `passability_raw`, with no event on one side
    - `count_mismatch <set> <group> <side>`, against the record's `groups`
  - `audit_dev(manifest: Path, record: Path) -> list[str]`. Its checks:
    - the manifest's SHA-256 equals the record's `dev_files` entry: `set_a_manifest` when its rows' `set` is `A`, `a_neg_manifest` when it is `A-neg`
    - every `split` is `dev`
    - the dev counts per group equal the record's
    - each copy (`<manifest folder>/photos/<photo_file>`) hashes to its `photo_sha256` (C219)

    Its violations: `manifest_hash`, `split_value <id>`, `count_mismatch …`, `copy_hash <id>` and `copy_missing <id>`.
  - `audit_sealed(run_dir: Path, dev_root: Path, records: Sequence[Path]) -> list[str]`, Rene's mode. For each record, first `archive_hash <file>` when `run_dir.parent / <archive file>` doesn't hash to the record's `archive.sha256`. Then, by `record_kind`:
    - **`split`:** `check_split` on Set A and A-neg, from `<dev_root>/set_a/dev/manifest.csv` and `<dev_root>/a_neg/dev/manifest.csv` against `<run_dir>/set_a/manifest.csv` and `<run_dir>/a_neg/manifest.csv`, with the record's groups
    - **`set_b_final`:** `car_on_both_sides <dev car id>` across `<run_dir>/set_b/truth.csv` and `<dev_root>/set_b/dev/generated/truth.csv`, and `count_mismatch set_b` against the record's `counts.cars` and `counts.crops`
    - **`set_d`:** the hash only
  - `main(argv=None) -> int`: `--dev MANIFEST --record RECORD`, or `--sealed RUN_DIR --dev-root DATA --record R [--record R …]`.
    - `--dev` refuses sealed paths in `--dev` and `--record`.
    - `--sealed` runs Rene's order: on the strings, `RUN_DIR` must be inside `sealed`, and `--dev-root` and every `--record` must not be; then `require_console()`; then the existence checks; then `confirm(...)`. Its body runs through `quiet`.
    - It prints `PASS` or `FAIL`, the counts per set, group and side, and each violation. It exits 0 on PASS, 1 on FAIL and 2 when refused.

- [x] **Step 1: Write the failing tests** (V1: every violation, in both modes). Records are built with `record_io`'s builders, and archives are synthetic files written with `write_sealed_archive`.
  - On both sides (the split's check and `--sealed`):
    - `test_clean_split_passes`
    - `test_event_split_across_sides`: the same date and spot on both sides, under different event ids
    - `test_event_id_on_both_sides`; `test_identical_photo_on_both_sides`
    - `test_same_event_id_in_two_sets_is_not_a_violation`: Set A's `E01` on the dev side and A-neg's `E01` on the sealed side
    - `test_near_identical_photo_on_both_sides`: hashes 6 bits apart are found; 7 bits apart aren't
    - `test_copy_check_catches_identical_and_near_photos`: a dev row whose SHA-256 equals a sealed row's in the other set gives `sha256`, and one whose dHash is 6 bits from a sealed row's gives `near_identical`; a dHash 7 bits away gives nothing.
    - `test_group_one_sided`: a deep group of 2 events, both dev
    - `test_group_counts_must_match_the_record`
    - `test_only_dev_ids_print`: every violation names a dev id, and no sealed id reaches stdout
  - In `--dev`:
    - `test_dev_audit_passes_on_a_true_copy`
    - `test_dev_manifest_hash_mismatch`
    - `test_dev_copy_changed` (one byte gives `copy_hash`) and `test_dev_copy_missing`
    - `test_dev_split_value`; `test_dev_counts_mismatch`
    - `test_dev_refuses_sealed_paths`: `--dev` or `--record` under a `sealed` folder exits 2, and `synth.opened_paths` shows nothing opened there
  - In `--sealed`:
    - `test_sealed_audit_hashes_each_archive`: a changed byte gives `archive_hash`
    - `test_sealed_set_b_cars_on_both_sides`; `test_sealed_set_d_record_checks_the_hash_only`
    - `test_sealed_path_rules`, parametrized: `RUN_DIR` outside `sealed`, or `--dev-root` or a `--record` inside it, exits 2 before anything is read
    - `test_sealed_refuses_without_a_console`: a subprocess with stdin on NUL and stdout piped exits 2 before any given path, none of which exists, is read
    - `test_sealed_needs_yes`
  - `test_audit_imports_only_the_standard_library`: in a fresh interpreter.
- [x] **Step 2:** Run `uv run --locked --script eval/data/tests/run_tests.py -k audit`. Expected: FAIL, with `ModuleNotFoundError: No module named 'audit'`.
- [x] **Step 3:** Implement, then run `uv lock --script eval/data/audit.py`.
- [x] **Step 4:** Run the tests again. Expected: all pass. `uv run --locked --script eval/data/audit.py --help` exits 0.
- [x] **Step 5:** Commit `feat(data): add the split audit for the development side and the sealed run`.

*Evidence (Task 12, Oct 29):*
- **Commits:** ca3dffc and fe85b3a.
- **Tests:** `uv run --locked --script eval/data/tests/run_tests.py -W error` gives 592 passed. `uv run --locked --script eval/data/audit.py --help` exits 0.
- **Checks:** ruff format and check, the plan-leak check (213 files), the account-ID scan (174 files) and gitleaks are clean.
- **RED:** the expected `ModuleNotFoundError: No module named 'audit'`.
- **Every "both sides" test runs twice,** through `check_split` in memory and through `audit_sealed` on a disk layout, and both must give the same violations.
- **The review held all five named risks:** only development ids print; no manifest or record cell steers a read outside its folder; `--sealed` runs Rene's order; the event rebuild matches the split's; a `photo_file` named `sealed` is refused.
- **One fix round (S-R18):** a set the record names but whose manifests are both empty now fails `--sealed` instead of passing. The sealed rows' dates join the leak test, an event split across sides names every development row, and `archive.file` must be a plain ASCII `.7z` name before it is opened or printed. A record naming a set other than A or A-neg stops the audit, so its text never prints. The scoped re-review found every finding addressed.

### Task 13: The split command (M19, C204, C205, C219)

**Files:**
- Create: `eval/data/split.py`, `eval/data/split.py.lock`
- Modify: `eval/data/tests/synth.py`: add `split_inputs(root: Path) -> dict[str, Path]`, which lays out a synthetic data folder like `lusot-data` under `root`. It returns each flag's path: the logs, the photo folders and the M8 export; `root/set_a/dev` and `root/a_neg/dev`; `root/sealed/lusot-sealed.7z`; and a record path outside `root/sealed`.
  - **Set A:** 20 photos, `A001` to `A020`, in 12 events of 3, 2, 2, 2, 2, 2, 2, 1, 1, 1, 1 and 1 rows over two dates. The 2nd, 4th, 6th, 9th and 11th events are deep: their alerts give `NPLV`.
  - **A-neg:** 8 photos, `N001` to `N008`, in 6 events of 2, 2, 1, 1, 1 and 1 rows.
  - **M8:** rows for every Set A photo.
- Test: `eval/data/tests/test_split.py`

**Interfaces:**
- Consumes: `intake.run_intake`; `photos.photo_facts`; `events.group_events`, `near`; `strata.deep_row`; `draw.draw_set`, `TooFewEvents`; `manifest.*`; `record_io.*`; `audit.copy_check`, `audit.check_split`, `audit.audit_sealed`; `archive.write_sealed_archive`; `guards.*`; `table.*`.
- Produces, in `split.py` (PEP 723 `dependencies = ["numpy==2.5.4", "opencv-python-headless==4.14.0.94", "py7zr==1.1.4"]`):
  - `main(argv=None) -> int`, with `--set-a-log --set-a-photos --a-neg-log --a-neg-photos --m8 --set-a-dev --a-neg-dev --archive --record [--allow-missing-m8]`, its body run through `guards.quiet`. Its copy check (C219) calls `audit.copy_check`, the helper `check_split` uses, so the two never drift apart.

  The run, in order. Each failure exits before the next step, and nothing is written before step 10:
  1. On the strings alone: `require_sealed(--archive)`, then `refuse_sealed` on every other path.
  2. `require_console()`.
  3. When the archive, the record or either dev folder exists, name each by its flag (`--archive exists: delete it before rerunning`) and exit 2.
  4. `ask_password()`, which is C202's confirmation.
  5. `run_intake(...)`. Any problem is printed, and the split exits 1.
  6. Read each photo once, by name, keep its bytes, and take `photo_facts`.
  7. Within each set, group duplicates: identical SHA-256, or near dHashes. `duplicate_of` is the group's lowest id.
  8. Events: `group_events`, with the duplicate pairs joined. An event is deep when `deep_row` holds for the `passability_raw` of any of its photos. Then `draw_set` per set. `TooFewEvents` prints `split stopped: set <name> has fewer than 2 events` and exits 1.
  9. Build the manifest and M8 rows per side. First the copy check, before copying (C219): `audit.copy_check(<dev rows>, <sealed rows>)`, over both sets. Each dev id it returns prints as `copy check: <dev id> matches a sealed photo`, and the split exits 1. Then `check_split({"dev": <dev rows>, "sealed": <sealed rows>}, None)`; the record doesn't exist yet, and it is built from the same draw. Any violation prints `FAIL` and the violations, and exits 1.
  10. `write_sealed_archive(--archive, password, members)`. Every photo is written from the bytes kept in step 6 (`writestr`), so the archived bytes are the hashed ones. The members, in order:
      - `records/split.json`: the core record
      - Set A: `set_a/manifest.csv`, `set_a/m8.csv`, `set_a/photos/<file>` (each sealed photo), `set_a/source/set_a_log.csv` and `set_a/source/m8_labels.csv`
      - A-neg: `a_neg/manifest.csv`, `a_neg/photos/<file>` and `a_neg/source/a_neg_log.csv`
  11. The dev side:
      - Create `--set-a-dev` and `--a-neg-dev` (failing if either exists).
      - Write `manifest.csv` and, for Set A, `m8.csv`, and write each dev photo from its kept bytes into `photos/`.
      - Re-hash each copy from disk against its manifest row (C219). A mismatch prints `copy check: <dev id> changed on disk` and exits 1.
  12. Write the committed record: the core plus `archive` (`record_io.archive_block`) and `copy_check`. Its `rehash_ok` comes from step 11, and its `matched_sealed` is the number of dev ids step 9's `audit.copy_check` returned, which is 0 on any run that gets this far.
  13. Print:
      - the rows and events per set, side and group
      - the counts per fact value
      - `audit PASS` and `copy check <n> of <n>`
      - `archive <size> bytes sha256 <hex>`

      No id is printed.

- [x] **Step 1: Write the failing tests.** All use `synth.split_inputs(tmp_path / "data")`, `synth.console` and `synth.typed(monkeypatch, TEST_PHRASE, TEST_PHRASE)`.
  - `test_split_end_to_end`, on that layout. It checks:
    - exit 0, and the archive opens with the test phrase and holds exactly the members above
    - the archive's manifests hold only sealed rows, and the dev manifests only dev rows
    - each dev copy's bytes equal its raw file, and no sealed photo's bytes are in a dev folder
    - the record's archive hash equals the file's; its `copy_check` shows every copy's re-hash matching, and `matched_sealed` is 0
    - every `photo_id`, `event_id` and `duplicate_of` in every manifest passes `is_id` (C221)
  - `test_split_is_deterministic`: two runs on copies of the same inputs give identical dev manifests, identical archive manifests (extracted in the test) and identical records, apart from `archive`, `date` and `git`.
  - `test_deep_events_reach_both_sides`: the layout's deep group has rows on both sides.
  - `test_every_group_of_two_or_more_has_both_sides`: in every set, each C204 group of 2 or more events has rows on both sides of the written manifests.
  - `test_record_group_counts_are_right`: the record's per-group counts equal those the test recomputes from the manifests.
  - `test_audit_sealed_passes_on_the_split_it_wrote` (C220): the test extracts the archive with the test phrase into `tmp_path/"data"/"sealed"/"run-1"`. Then `audit.audit_sealed(run_dir, tmp_path/"data", [record])` gives no violation. After one archive byte changes, it gives `archive_hash`.
  - `test_duplicates_join_one_event`: `A001` and `A007` are identical bytes, and `A009` is a re-encoded `A001`. All three share one event and `duplicate_of = A001`, and `A007` and `A009` have `duplicate = yes`.
  - `test_split_path_rules`, parametrized over each flag: an input, `--record` or a dev folder inside a `sealed` folder exits 2, and so does `--archive` outside one. `synth.opened_paths` shows nothing read, and nothing is created.
  - `test_split_refuses_without_a_console`: a subprocess with stdin on NUL and stdout piped exits 2, and no output exists afterwards.
  - `test_rerun_names_the_partial_outputs` (Review Focus 3): an existing archive file and dev folder give exit 2. Stdout names `--archive` and `--set-a-dev`, and nothing changes.
  - `test_password_mismatch_writes_nothing`
  - `test_intake_problem_stops_the_split`: exit 1, with nothing written.
  - `test_one_event_set_stops`: all A-neg photos at one spot on one date give exit 1, and the message names `A-neg`.
  - `test_missing_m8_photo_row`: the split stops; with `--allow-missing-m8` it runs, and the record counts 1.
  - `test_split_keeps_an_undecodable_photo` (Review Focus 2): one Set A photo is random bytes. It gets `decodes = no`, sits in a manifest, and the split succeeds.
  - `test_changed_copy_stops_the_split`: a patched writer alters one dev copy's bytes. The split exits 1, naming that dev id.
  - `test_unexpected_error_names_no_photo`: `photos.photo_facts`, patched to raise `OSError` with a photo's name in its message, gives exit 1 and output naming the class only.
  - `test_split_output_and_record_hold_no_log_text`: sentinels in every text column of both logs, and none in stdout, stderr or the record.
  - `test_record_holds_no_photo_or_event_id`
- [x] **Step 2:** Run `uv run --locked --script eval/data/tests/run_tests.py -k split`. Expected: FAIL, with `ModuleNotFoundError: No module named 'split'`.
- [x] **Step 3:** Implement, then run `uv lock --script eval/data/split.py`.
- [x] **Step 4:** Run the tests again. Expected: all pass. `uv run --locked --script eval/data/split.py --help` exits 0.
- [x] **Step 5:** Commit `feat(data): add the split, writing the sealed archive and the development side`.

*Evidence (Task 13, Oct 29):*
- **Commits:** add21f0, 5fea0db and 6a23b21.
- **Tests:** `uv run --locked --script eval/data/tests/run_tests.py -W error` gives 660 passed. `uv run --locked --script eval/data/split.py --help` exits 0.
- **Checks:** ruff format and check, the plan-leak check (216 files), the account-ID scan (176 files), gitleaks and the banned-forms check are clean.
- **RED:** the expected `ModuleNotFoundError` for `split`.
- **The golden split** is asserted from the manifest extracted from the written archive: Set A seals E01, E02, E07 and E09 (8 of 20 rows, exactly 2/5), and A-neg seals 3 of 8.
- **Ruling S-R19:** every check (the intake, photo facts, draw, manifests, copy check, audit and the record's id pre-check) runs before the password, as spec §5.5 orders, so a stop leaves nothing written and the password is never asked. An `--archive` name outside S-R18's pattern, or holding an id, is refused on the string.
- **The review approved it,** with all seven named risks held: order and fail-closed writes; no sealed id, spot or label in any output line; the golden split; each log and photo read once and archived as the same bytes; the archive and dev layout of spec §5.5 and §5.9; private names; an undecodable photo split like any other.
- **One fix round (S-R21),** checked by the controller under the usage plan (the code diff read; 660 passed with `-W error`; three mutants, each caught): overlapping dev folders, a `--record` inside a dev folder, and a dev folder inside a photo folder (R5 would delete it) are refused on the strings; the rerun after a real failure past the password is pinned; a relative `--record` is tested; refusals print to stderr.

### Task 14: Tire codes, wheels and G3's truth (C212, G3)

**Files:**
- Create: `eval/set_b/tires.py`, `eval/set_b/wheels.py`, `eval/set_b/truth.py`
- Modify: `eval/data/tests/synth.py`: add `ellipse_mask(shape, centre, half_h, half_w) -> np.ndarray` and `masks_folder(root, stem, photo, vehicles, wheels, rims) -> Path`. It takes the masks root, writes `<root>/<stem>/blurred.jpg` and the three `_masks.npz` files as `set_b_masks.save_result` does, merges those files into `<root>/files.txt` in the Global Constraints' `files.txt` format, and returns `<root>/<stem>`.
- Test: `eval/set_b/tests/test_setb_tires.py`, `test_setb_wheels.py`, `test_setb_truth.py`

**Interfaces:**
- Produces, in `tires.py`:
  - `@dataclass(frozen=True) class TireSize: width_mm: int; aspect: int; rim_in: int`
  - `parse_tire_code(code: str) -> TireSize | str`: a size, or the cause `no_aspect_ratio` (such as `195R14C`) or `bad_tire_code`. It accepts any case, an optional `P` or `LT` prefix, `Z`, a `C` suffix, and anything after the rim (load index and speed rating).
  - `diameter_in(size: TireSize) -> float`: `rim + 2 × width × aspect ÷ 100 ÷ 25.4` (plan Table 7)
- Produces, in `wheels.py`:
  - `@dataclass(frozen=True) class Instance: box: tuple[int, int, int, int]; mask: np.ndarray; score: float | None`, with a half-open box taken from the mask's own extent
  - `load_instances(npz: Path) -> list[Instance]`: `np.load` inside `with`, keeping its default `allow_pickle=False`. An instance with an empty mask has no extent and is skipped, and a NaN score loads as None.
  - `pick_wheels(vehicles: Sequence[Instance], wheels: Sequence[Instance], shape: tuple[int, int]) -> list[Instance] | str` (C212): at most the two largest wheel masks by area that meet every rule below. Returned left to right. The causes are `no_vehicle` and `no_wheel`.
    - the box centre lies inside the largest vehicle box (by box area)
    - the mask touches no edge row or column
    - the box's longer side is at least 40 px
    - its height over width is 0.9 to 2.0
  - `link_rim(wheel: Instance, rims: Sequence[Instance]) -> Instance | None`: the rim mask that overlaps the wheel mask most; None when none overlaps
- Produces, in `truth.py`:
  - `@dataclass(frozen=True) class WheelGeom: x0: int; y0: int; x1: int; y1: int; top_row: int; ground_row: int; px_per_in: float; cx: int`
    - `top_row` is the first mask row, and `ground_row` is one past the last (half-open, like SAM's boxes)
    - `px_per_in = (ground_row − top_row) ÷ diameter`, and `cx = (x0 + x1 − 1) // 2`
  - `wheel_geom(mask: np.ndarray, diameter: float) -> WheelGeom`
  - `rim_edge_ratio(rim_mask: np.ndarray | None, px_per_in: float, rim_in: int) -> float | None`: the rim mask's row extent, in inches, over `rim_in`; None without a rim, written as a blank `rim_edge_ratio` and counted in `wheels_without_rim`
  - `line_rows(wheels: Sequence[WheelGeom], depth_in: float, width: int) -> np.ndarray`: one int row per column. The straight line runs through each wheel's `(cx, ground_row − depth × px_per_in)`, and is level for one wheel. Each column's row is rounded half up; water fills the column from that row down.
  - `wheel_truth(geom: WheelGeom, rows: np.ndarray) -> tuple[int, int, int, float]`: `waterline_left_row` (`rows[x0]`), `waterline_right_row` (`rows[x1 − 1]`), `waterline_row` (`rows[cx]`), and `true_depth_in = (ground_row − waterline_row) ÷ px_per_in`, rounded to 4 decimals

- [x] **Step 1: Write the failing tests.**
  - `test_parse_tire_codes`, parametrized:
    - `175/65R14` gives (175, 65, 14) and diameter 22.9567; `185/55R15` gives 23.0118; `215/70R16C` gives 27.8504
    - `P205/55ZR16 91V` gives (205, 55, 16); `LT235/75R15` gives (235, 75, 15)
    - `195R14C` gives `no_aspect_ratio`; `14 inch` and `""` give `bad_tire_code`
  - `test_two_largest_wheels_inside_the_vehicle`: 3 wheels inside the vehicle and 1 outside give the two largest inside, left to right.
  - `test_wheel_rules`, parametrized: excluded when touching the left edge, 38 px tall, or at a height over width of 0.85 or 2.1. Kept at 0.9 and 2.0, since the bounds are inclusive.
  - `test_no_vehicle_and_no_wheel_causes`; `test_link_rim_by_overlap`; `test_load_instances_round_trip`
  - `test_empty_masks_are_skipped`: an npz with one empty mask among two gives one instance.
  - `test_truth_on_a_drawn_wheel` (V1): a 400 × 300 frame and a wheel ellipse centred at (200, 200) with a vertical half-height of 50, so `top_row` 150 and `ground_row` 251. With `175/65R14` the scale is 101 ÷ 22.9567 = 4.3996 px/in. Depth 6.0 puts the line at 224.60, drawn at row 225, so `waterline_row == 225` and `true_depth_in == 5.9096`.
  - `test_sloped_line_gives_both_wheels_one_depth` (Review Focus 5): ground rows 251 and 263, at 4.4 and 4.0 px/in. The line's rows at the two centres differ, and each wheel's `true_depth_in` lies within one pixel (1 ÷ `px_per_in`) of the drawn depth.
  - `test_rim_edge_ratio`: a rim 70 px tall at 4.3996 px/in on a 14 in rim gives 1.1365, and no rim gives None.
- [x] **Step 2:** Run `uv run --locked --script eval/data/tests/run_tests.py -k setb`. Expected: FAIL, with `ModuleNotFoundError: No module named 'tires'`.
- [x] **Step 3:** Implement.
- [x] **Step 4:** Run the tests again. Expected: all pass.
- [x] **Step 5:** Commit `feat(set_b): add tire codes, the wheel choice and G3's truth`.

*Evidence (Task 14, Oct 30):*
- **Commits:** 677e971, 1e4319f and 11c2f57.
- **Tests:** `uv run --locked --script eval/data/tests/run_tests.py -W error` gives 713 passed.
- **Checks:** ruff format and check, the plan-leak check (257 files), the account-ID scan (217 files), gitleaks and the banned-forms check are clean.
- **RED:** the expected `ModuleNotFoundError` for `tires` and `wheels`.
- **The review approved it** and re-checked the geometry beyond the golden numbers: `line_rows` against exact fractions over 3,000 random two-wheel slopes in both wheel orders (2,746,370 columns, no mismatch, 19 exact half-pixel ties), and `wheel_truth` on an off-brief slope within half a pixel. Rim suffixes glued to the rim (`22.5`, `16V`, `14XL`) give `bad_tire_code`.
- **Ruling S-R24:** the two chosen wheels must be different wheels, so two SAM masks of one wheel (a tire and its hub) count once and never draw a vertical line.
- **One fix round (S-R25),** checked by the controller: a test for each direction of the overlap rule (two mutants, each deleting one direction, each caught), a shape check in `synth.masks_folder`, and `Instance` compared by identity.

### Task 15: The water and the crops (C211)

**Files:**
- Create: `eval/set_b/water.py`, `eval/set_b/crops.py`
- Test: `eval/set_b/tests/test_setb_water.py`, `test_setb_crops.py`

**Interfaces:**
- Consumes: `truth.WheelGeom`, `wheel_geom`, `line_rows`, `wheel_truth`.
- Produces, in `water.py`:
  - `GENERATOR_VERSION = "set-b-gen-v1"`
  - `composite(image: np.ndarray, rows: np.ndarray, rng: np.random.Generator) -> tuple[np.ndarray, np.ndarray]`: the composited BGR image and the water mask.
    - Every pixel at or below `rows[x]` in column x is water: an opaque muddy base colour, ripples (low-frequency brightness bands, inside the water only), and the scene above the line mirrored about it, darkened and blended in.
    - Pixels above the line are unchanged. The texture is the builder's, within C211 (§10).
- Produces, in `crops.py`:
  - `GENERATOR_SEED = 20261029`, fixed before any Set B photo exists
  - `BANDS = (("below_gutter", 1.0, 5.0), ("gutter", 5.0, 8.0), ("half_knee", 8.0, 10.0), ("half_tire", 10.0, 13.0))`
  - `band_limits(band: str, diameter: float) -> tuple[float, float] | None`: as `BANDS`, except that `half_tire`'s top is `min(13, diameter ÷ 2 − 0.5)`. None when that top isn't above 10.
  - `photo_rngs(photo_file: str) -> tuple[random.Random, np.random.Generator]`: both seeded from the SHA-256 of `f"{GENERATOR_SEED}:{photo_file}"`
  - `@dataclass(frozen=True) class CropPlan: crop_id: str; band: str; depth_in: float; shrink: bool; target_px: float | None`
  - `plan_crops(car_id: str, photo_no: int, diameter: float, rng: random.Random) -> list[CropPlan]`:
    - the four bands, in a seeded order, give crop numbers 1 to 4 (`B01-1-3`)
    - each depth is drawn evenly within its band
    - two of the four, drawn at random, shrink, each to a target height drawn evenly from 50 to 80 px
    - a band without limits is left out
  - `@dataclass class Crop: plan: CropPlan; image: np.ndarray; water: np.ndarray; scale: float; wheels: list[tuple[WheelGeom, tuple[int, int, int, float]]]`
  - `make_crop(blurred: np.ndarray, wheel_masks: Sequence[np.ndarray], diameter: float, plan: CropPlan, rng: np.random.Generator) -> Crop`:
    - When `plan.shrink`, it shrinks first. The scale is the target over the smaller wheel's height, at most 1; the image shrinks with `INTER_AREA` and the masks with `INTER_NEAREST`.
    - It then recomputes each `WheelGeom` in the crop's own pixels, and runs `line_rows`, `composite` and `wheel_truth`.

- [ ] **Step 1: Write the failing tests.**
  - `test_water_hides_everything_below_the_line`: two images equal above the line and different below it give identical composites.
  - `test_pixels_above_the_line_are_unchanged`; `test_water_mask_is_exactly_below_the_rows`; `test_same_seed_same_water`
  - `test_band_limits`: diameter 22.9567 gives `half_tire` a top of 10.9783; diameter 20.0 gives None.
  - `test_plan_crops`: four plans with ids `B01-1-1` to `B01-1-4` in a seeded band order. Each depth lies within its band, and exactly two plans shrink, with targets from 50 to 80. The same rng seed gives the same plans, and every id passes `is_id`.
  - `test_small_crop_wheel_height`: a shrunk crop's smaller wheel is 50 to 80 px tall, so C56's 40 px holds.
  - `test_rows_are_the_crops_own`: a shrunk crop's `ground_row`, `px_per_in` and waterline rows belong to the shrunk image. Water starts at `waterline_row` in column `cx`, with the original pixel above it.
  - `test_generator_is_reproducible`: the same photo name gives the same crops, byte for byte after JPEG encoding.
- [ ] **Step 2:** Run `uv run --locked --script eval/data/tests/run_tests.py -k "setb_water or setb_crops"`. Expected: FAIL, with `ModuleNotFoundError: No module named 'water'`.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** Run the tests again. Expected: all pass.
- [ ] **Step 5:** Commit `feat(set_b): composite the muddy water and plan the four crops`.

### Task 16: The generator, development and final (C214)

**Files:**
- Create: `eval/set_b/cars.py`, `eval/set_b/generate.py`, `eval/set_b/generate.py.lock`
- Test: `eval/set_b/tests/test_setb_cars.py`, `test_setb_generate.py`

**Interfaces:**
- Consumes: `tires.*`, `wheels.*`, `truth.*`, `water.*`, `crops.*` (Tasks 14 and 15). From `eval/data`: `guards`, `table`, `formats`, `photos.photo_facts`, `events.near`, `archive.write_sealed_archive`, `record_io.set_b_final_record`, `archive_block` and `write_record`, and `audit.audit_sealed` (in the tests).
- Produces, in `cars.py`:
  - `@dataclass class CarsCheck: rows: list[dict[str, str]]; problems: list[Finding]; warnings: list[Fact]; drops: dict[str, str]`, where `drops` maps a car to its cause
  - `check_cars(path: Path, *, side: str) -> CarsCheck`, where `side` is `dev` or `final`:
    - **Problems:** the columns; the `car_id` pattern and C210's parity (`<car> car_id: wrong_side`: odd numbers are `dev`, even ones `final`); `photo_file` as `<car>-<n>.<ext>`, matching Task 5's pattern `B[0-9]{2}-[0-9]{1,2}\.(jpg|jpeg|png)` in any case; a car's rows must agree on `model`, `vehicle_type` and `tire_code`; `vehicle_type` in `SET_B_TYPES`; `view` in `VIEWS`; `taken_on` a date.
    - **Drops,** per car: `no_aspect_ratio`, `bad_tire_code`, and `no_consent` (a blank `consent_file`, or no such file beside `cars.csv`).
    - **Warnings:** `consent_version=unapproved` (C218).
    - **Refs:** under `final`, findings and facts name `row <n>`, never a final car id.
- Produces, in `generate.py`: it puts `eval/data` on `sys.path` before importing from it, and its PEP 723 dependencies are `["numpy==2.5.4", "opencv-python-headless==4.14.0.94", "py7zr==1.1.4"]`.
  - `@dataclass class Generated: crops: list[Crop]; rows: list[dict[str, str]]; drops: Counter[str]; wheels_without_rim: int; seconds: float`
  - `generate(cars: CarsCheck, masks: Path, *, split: str) -> Generated`. For each kept photo, in `cars.csv` order:
    - It reads `<masks>/<stem>/blurred.jpg` and `sam_vehicle_masks.npz`, `sam_wheel_masks.npz` and `sam_wheel_rim_masks.npz`. A missing file drops the photo as `no_masks`.
    - Then `pick_wheels`, `link_rim`, `plan_crops` and `make_crop`.
    - The truth rows are in `TRUTH_COLUMNS`, one per wheel per crop: `split` is `dev` or `sealed`, `crop_file` is `<crop_id>.jpg`, and `size_bin` is `small` or `full`; `rim_edge_ratio` is blank without a rim; `generator_version` is filled.
  - `main(argv=None) -> int`:
    - **Development:** `--cars --masks --out`. It refuses sealed paths and an existing `--out`. It writes `crops/<crop_id>.jpg` (JPEG quality 95), `water/<crop_id>.png` (the drawn water mask), `overlays/<crop_id>.jpg` (the drawn line in red and each chosen wheel's box in yellow), `truth.csv` and `files.txt`.
    - **`--final`,** in Rene's order, its body run through `quiet`:
      1. On the strings: `--cars`, `--masks` and `--archive` must be inside `sealed`; `--dev-cars`, `--dev-masks` and `--record` must not.
      2. `require_console()`.
      3. An existing archive or record is refused.
      4. `check_cars(<--cars>, side="final")`, beside the overlap check (C214). Any problem it finds exits 1, before the password. The overlap check stops on any of these: a final car id in the dev `cars.csv`; an odd final car number; or a final blurred photo whose SHA-256 equals, or whose dHash is near, a development blurred photo's. Both blurred photos are read by name, as `<masks>/<stem>/blurred.jpg`. A stop prints `overlap: <dev car id>` and exits 1.
      5. `ask_password()`, then generation in memory.
      6. The archive, in one pass, holds:
         - `records/set_b_final.json`, `set_b/truth.csv` and `set_b/crops/<crop_file>`
         - `set_b/source/cars.csv`
         - `set_b/source/photos/<photo_file>`, the raw photos read by name from `<--cars folder>/photos/` (inside `sealed`)
         - each distinct consent file, once, under `set_b/source/`, at its path relative to `cars.csv`
         - `set_b/source/masks/<path>` for each file in the final masks' `files.txt`
      7. The committed record: `record_io.set_b_final_record`, plus `archive`.

      No crop, truth row or overlay is ever written in plaintext. Problems, drops and warnings print as `row <n> …` with counts, never a final car id.
    - It prints the counts by cause, the crops and wheels, and the seconds.

- [ ] **Step 1: Write the failing tests.** The masks folders come from `synth.masks_folder`, under `tmp_path/"data"` laid out like `lusot-data`.
  - In `test_setb_cars.py`: one test per problem, drop and warning; `test_final_side_needs_even_numbers`; `test_final_refs_are_row_numbers`.
  - `test_dev_generation_writes_crops_truth_overlays`: cars `B01` and `B03`, with one photo and 2 wheels each, give 8 crops and 16 truth rows. Every `crop_id` and `car_id` passes `is_id`, `true_depth_in` has at most 4 decimals, `files.txt` lists every file with its hash, and each crop has an overlay.
  - `test_drops_are_counted_by_cause`: a `195R14C` car gives `no_aspect_ratio`, a car without its consent file gives `no_consent`, and a masks folder without a vehicle gives `no_vehicle`.
  - `test_wheel_without_a_rim`: a wheel with no linked rim gets a blank `rim_edge_ratio` and counts in `wheels_without_rim`.
  - `test_unapproved_consent_only_warns`
  - `test_dev_refuses_sealed_paths_and_existing_out`
  - `test_final_path_rules`, parametrized: `--cars`, `--masks` or `--archive` outside `sealed`, or `--dev-cars`, `--dev-masks` or `--record` inside it, exits 2 before anything is read.
  - `test_final_writes_no_plaintext`: one final car has two photos, so its consent file is named twice. With the console patched and the test phrase, `--final` adds exactly two files, the archive and the record, to the tree under `tmp_path`. The archive holds the members above, with that consent file once. Its `set_b/truth.csv` equals, apart from `split`, the rows of `generate.generate(check, masks, split="dev")`, called directly on the same `check_cars(..., side="final")` result and masks.
  - `test_audit_sealed_passes_on_the_final_cars_it_wrote` (C220): one final car is dropped (its tire code is `195R14C`), so `counts.cars` must leave it out. The test extracts the archive with the test phrase into `tmp_path/"data"/"sealed"/"run-1"`, beside a development run in `tmp_path/"data"/"set_b"/"dev"/"generated"`. Then `audit.audit_sealed` gives no violation. After one archive byte changes, it gives `archive_hash`.
  - `test_final_overlap_stops_before_the_password`: each case exits 1 without `getpass` being called. The cases: a final photo with a dev photo's blurred bytes; a near-identical re-encode; the final car id `B03`, which is odd.
  - `test_final_refuses_without_a_console`: a subprocess with stdin on NUL and stdout piped exits 2.
  - `test_final_prints_no_final_car_id`: stdout and stderr of a `--final` run with a drop and a warning hold no `B02` or `B04`.
  - `test_final_record_holds_no_ids`
- [ ] **Step 2:** Run `uv run --locked --script eval/data/tests/run_tests.py -k "setb_cars or setb_generate"`. Expected: FAIL, with `ModuleNotFoundError: No module named 'cars'`.
- [ ] **Step 3:** Implement, then run `uv lock --script eval/set_b/generate.py`.
- [ ] **Step 4:** Run the tests again. Expected: all pass. `uv run --locked --script eval/set_b/generate.py --help` exits 0.
- [ ] **Step 5:** Commit `feat(set_b): add the generator, with the sealed final-car run`.

### Task 17: The freeze check and the freeze record (C213, C216, V8)

**Files:**
- Create: `eval/set_b/water_check.py`, `eval/set_b/water_check.py.lock`, `eval/data/freeze_record.py`, `eval/data/freeze_record.py.lock`
- Test: `eval/set_b/tests/test_setb_water_check.py`, `eval/data/tests/test_freeze_record.py`

**Interfaces:**
- Consumes: `record_io.base_record` and `write_record` (Task 11); `guards.refuse_sealed` and `table` (Task 2).
- Produces, in `water_check.py`, which puts `eval/data` on `sys.path` before importing from it, with the dependencies numpy and opencv-python-headless at the pins:
  - `CROP_PASS = Fraction(1, 4)`, `LOOK_PASS = Fraction(3, 4)` and `MAX_LOOKS = 3`
  - `coverage(sam: np.ndarray, drawn: np.ndarray) -> Fraction`: the shared pixels over the drawn pixels
  - `main(argv=None) -> int`, with `--truth <generated/truth.csv> --sam <masks/water> --looks-dir <eval/data/records>`. It runs `refuse_sealed` on all three before reading anything. Then, for each crop in `truth.csv`:
    - `<sam>/<crop_id>/meta.json` missing: the crop fails as `no_result`.
    - Its `crop_sha256` differs from the SHA-256 of `<truth folder>/crops/<crop_file>`, or its `generator_version` from the rows': the crop fails as `stale_result`, so a new look is never scored against old masks (C213).
    - Otherwise SAM's mask is the union of the masks in `sam_floodwater_masks.npz` beside it, the drawn mask is `<truth folder>/water/<crop_id>.png`, and the crop passes at `coverage ≥ CROP_PASS`.

    The rows must share one `generator_version`, else exit 1. It writes the look as its own record, exclusively, with `write_record`: `<looks-dir>/set-b-look-<n>.json`, where n is the first of 1 to 3 whose file doesn't exist (checked by name). The record starts from `base_record(...)` for the tool `eval/set_b/water_check.py` (`tool`, `git`, `date` and `python`) and adds `{"look", "generator_version", "crops", "passed", "failed_by_cause", "share": "k/n", "result": "pass" | "fail"}`. When all three exist it exits 2: "three looks are used: the generator freezes as it is (C213)". It prints the counts and the result.
- Produces, in `freeze_record.py` (standard library): `main(argv=None) -> int`, with `--data DIR`, `--file REL` (repeatable, relative to `--data`), `--record PATH` (repeatable: the split, Set B final and Set D records), `--look PATH` (repeatable) and `--out PATH`.
  - It refuses sealed paths, checking each `--file` joined to `--data`.
  - It writes, exclusively, with `write_record`: a record that starts from `base_record(...)` for the tool `eval/data/freeze_record.py` (`tool`, `git`, `date` and `python`) and adds `{"files": {rel: sha256}, "records": {name: {"sha256", "archive"}}, "generator_version", "looks"}`. `generator_version` is read from `set_b/dev/generated/truth.csv` when that file is listed, and `looks` holds each look record's content.
  - It prints the file count and the record's SHA-256.

- [ ] **Step 1: Write the failing tests.**
  - `test_coverage`, with exact fractions; `test_crop_pass_is_inclusive` (exactly a quarter passes)
  - `test_look_passes_at_three_quarters`: 3 of 4 passes, 2 of 4 fails.
  - `test_missing_sam_result_fails_the_crop`
  - `test_stale_sam_result_fails_the_crop`: a crop whose bytes changed after its SAM run fails as `stale_result`, and so does one whose `meta.json` names an older generator version.
  - `test_looks_are_numbered_and_capped`: three runs write `set-b-look-1.json` to `-3.json`. A fourth exits 2, and no file is rewritten.
  - `test_mixed_generator_versions_stop`
  - `test_water_check_refuses_sealed_paths`, for each flag
  - `test_freeze_record_holds_the_hashes`: each file's SHA-256 equals hashlib's, the records' archive blocks are copied, and the looks are included.
  - `test_freeze_record_refuses_sealed_paths`; `test_freeze_record_never_overwrites`
  - `test_freeze_record_holds_no_ids`: the synthetic files' ids appear nowhere in the record.
- [ ] **Step 2:** Run `uv run --locked --script eval/data/tests/run_tests.py -k "water_check or freeze_record"`. Expected: FAIL, with `ModuleNotFoundError: No module named 'water_check'`.
- [ ] **Step 3:** Implement, then lock both scripts.
- [ ] **Step 4:** Run the tests again. Expected: all pass. Both scripts' `--help` exit 0.
- [ ] **Step 5:** Commit `feat(data): add Set B's freeze check and the freeze record`.

### Task 18: Set D's seal (C217)

**Files:**
- Create: `eval/data/seal_set_d.py`, `eval/data/seal_set_d.py.lock`
- Test: `eval/data/tests/test_seal_set_d.py`

**Interfaces:**
- Consumes: `guards`, `table`, `formats`, `archive.write_sealed_archive`, `record_io.set_d_record`, `archive_block` and `write_record`, and `audit.audit_sealed` (in the tests).
- Produces, in `seal_set_d.py`, with the dependency `py7zr==1.1.4`:
  - `check_set_d(path: Path) -> tuple[list[dict[str, str]], list[Finding]]`: `SET_D_COLUMNS`; `photo_id` as `D[0-9]{2}`; `photo_file` as `<id>.<ext>` in `photos/` beside the log (a stat); `taken_pht` a time; `vehicle_type` in Table 5's nine; `wheel` in `WHEEL_SIDES`; `ruler_depth_in` a decimal above 0 with at most 4 decimals. Findings name `row <n>` only, because every Set D id is final.
  - `main(argv=None) -> int`, with `--log` (inside `sealed`), `--archive` (inside `sealed`), `--record` and `[--extends <freeze record>]`, its body run through `quiet`. It runs, in Rene's order:
    1. The path rules on the strings: `--log` and `--archive` inside `sealed`; `--record` and `--extends` outside it.
    2. `require_console()`.
    3. An existing archive or record is refused.
    4. `ask_password()`.
    5. The checks. Problems print and exit 1.
    6. The archive, in one pass: `records/set_d.json`, `set_d/set_d_log.csv` and `set_d/photos/<file>`.
    7. The record: `record_io.set_d_record`, plus `archive`. It prints the counts and the archive's size and SHA-256.

- [ ] **Step 1: Write the failing tests.**
  - `test_seal_set_d_end_to_end`: with the console patched and the test phrase, the archive's members and bytes and the record's counts are right, and no id appears in the record or stdout.
  - `test_audit_sealed_checks_the_set_d_hash` (C220): `audit.audit_sealed` on this record gives no violation, and after one archive byte changes, `archive_hash`.
  - `test_problems_print_row_numbers_only`
  - `test_path_rules`, parametrized over every flag: `--log` or `--archive` outside `sealed`, or `--record` or `--extends` inside it, exits 2.
  - `test_refuses_without_a_console` (subprocess); `test_refuses_existing_outputs`
  - `test_extends_names_the_freeze_record`
- [ ] **Step 2:** Run `uv run --locked --script eval/data/tests/run_tests.py -k seal_set_d`. Expected: FAIL, with `ModuleNotFoundError: No module named 'seal_set_d'`.
- [ ] **Step 3:** Implement, then lock the script.
- [ ] **Step 4:** Run the tests again. Expected: all pass. `--help` exits 0.
- [ ] **Step 5:** Commit `feat(data): add Set D's seal`.

### Task 19: Set C (C215)

**Files:**
- Create: `eval/data/setc.py`, `eval/data/setc.py.lock`, `docs/research/<date>-set-c-licences.md` (the date it is written)
- Test: `eval/data/tests/test_setc.py`

**Interfaces:**
- Consumes: `guards.refuse_sealed`, `guards.is_sealed_name` and `table.write_new` (Task 2).
- Produces, in `setc.py` (standard library): `main(argv=None) -> int`, with the subcommand `sturm --root DIR --out FILE`.
  - It walks `--root` with `os.walk`, the one walk §5.2 allows, pruning before descending any folder whose name `guards.is_sealed_name` matches, so the walk and the guard share one rule.
  - An image (`.jpg`, `.jpeg` or `.png`, any case) whose nearest folder named `Level0` to `Level4` (any case) is an ancestor gets one row: `path` (relative to the root, with `/`), `level` (0 to 4) and `sha256`. Other files count as skipped.
  - Rows are sorted by path. It prints `files=<n>`, the count per level and `skipped=<k>`. Neither `--root` nor `--out` may be inside a `sealed` folder.
  - `--out` is created exclusively, with `table.write_new`, and never overwritten: an existing `--out` is refused (exit 2) before the walk, so a rerun needs a new path.
- Only if Step 5's note finds a source that qualifies: `flooddet --root DIR --sources FILE --out FILE`, where `--sources` is a CSV (`prefix`, `source`, `meta_ok`) that Claude writes from the note. Each image takes the `source` and `meta_ok` of its longest matching prefix, and `meta_ok = no` when none matches.

- [ ] **Step 1: Write the failing tests.**
  - `test_sturm_manifest`: a synthetic tree with `extracted/upscaled_images/Level1/x.jpg`, `Level3/y.png` and `readme.txt` gives two rows, at levels 1 and 3, and `skipped=1`.
  - `test_walk_skips_sealed_folders`: `Level2/Sealed/z.jpg` isn't listed, and `synth.opened_paths` shows no `open` or `os.scandir` event under `Sealed`.
  - `test_paths_use_slashes_and_sort`; `test_refuses_sealed_root_or_out`
  - `test_existing_out_is_never_overwritten`: an existing `--out` exits 2, and its bytes are unchanged.
- [ ] **Step 2:** Run `uv run --locked --script eval/data/tests/run_tests.py -k setc`. Expected: FAIL, with `ModuleNotFoundError: No module named 'setc'`.
- [ ] **Step 3:** Implement, then lock the script.
- [ ] **Step 4:** Run the tests again. Expected: all pass.
- [ ] **Step 5 (the licence note; Claude reads each page as a person would):** for each source of FloodDET's images (DEEPFLOOD, FloodIMG, Mapillary Vistas and MS COCO), on that source's own page, record:
  - its licence
  - whether private development use is allowed
  - whether sending its images to Meta on the credits is allowed, given that Meta may use them to improve its products

  The decision: download FloodDET only if some source qualifies, and mark `meta_ok` per source. If none qualifies, FloodDET is out of scope, and Muse Spark's person categories are checked on development Set A and consented photos instead (C215).
- [ ] **Step 6:** Only if a source qualifies: add `flooddet` with `test_flooddet_marks_meta_ok_by_source` (the longest prefix wins, and no match means `no`).
- [ ] **Step 7:** Commit `feat(data): add Set C's manifests and the FloodDET licence check`.

### Task 20: README, the full check and the handoff

**Files:**
- Modify: `README.md`
- Outside git: the handoff note `C:\Systems\Lusot\lusot\.superpowers\handoff\specs.md`

- [ ] **Step 1: README.**
  - Add a row: py7zr | the write-once encrypted archives of MS2's sealing steps | LGPL-2.1-or-later. Confirm that licence from the installed metadata: `uv run --with py7zr==1.1.4 --python 3.13 python -c "import importlib.metadata as m; print(m.metadata('py7zr')['License-Expression'])"` prints `LGPL-2.1-or-later`.
  - The NumPy and OpenCV rows' use also names MS2's data tools.
  - If Task 19's note let FloodDET be downloaded, add a row for each source used, with its licence (spec §8: any Set C data used).
  - The lock-file note gains `eval/data/*.py.lock`, `eval/data/tests/run_tests.py.lock` and `eval/set_b/*.py.lock`, and one sentence: py7zr's compression and crypto libraries are pinned there, several under LGPL-2.1-or-later.
- [ ] **Step 2: The full check.** Each must pass:
  - `uv run --locked --script eval/data/tests/run_tests.py`: all pass, the M8 script's node tests included
  - `npm run check:py`: the analysis package's ruff and pytest, including `test_set_b_masks.py`, and the `backend/scripts` tests, all pass
  - `uv run --locked --script <file> --help`, for each entry script: exits 0
  - `npm run check:secrets` (V10): gitleaks finds no leak, the plan-leak check prints `clean`, and the account-ID scan prints `clean`
  - `git diff --name-status main...ms2-data`: only `A` lines for the new files in this plan's file table, the spec and the plan, and `M` lines for `eval/templates/set_a_log.csv`, `docs/data/set-a-collection-guide.md` and `README.md`. That shows V9's "`.claude/settings.json` is unchanged", and that no conflict file changed.

  **A departure from V10, stated:** `check:node` isn't run. The branch's only JavaScript, `m8_sheet.js` and its node test, runs inside the first check, not under `check:node`, and `check:node` would need an `npm ci`.
- [ ] **Step 3 (B.8, confirm v0.7 is applied):** read `git show main:eval/rules.md`'s status line.
  - If v0.7 is applied, check that it carries MS2-Q2's items: C203; C204 with its stratified walk (item 4.2); C209; C211; C212; C214; C224; §9's duplicate rule; one archive per sealing step.
  - If not, record that MS2's calls run as D7 defaults.

  Either way, `eval/rules.md` isn't edited.
- [ ] **Step 4: The handoff, in `specs.md`:**
  - **For Window 3:** log-ready lines: what was built, with the evidence; T9 (7-Zip) as a new setup action; the open points.
  - **For the merge owner:** "`ms2-data` merges into `main` after review". Then append ` && uv run --locked --script eval/data/tests/run_tests.py` to `check:py` in `package.json`. CI runs it through `npm run check:py`, whose job already sets up Node 22 for the M8 script test.
  - **For MS2's close (`revise-claude-md`):** CLAUDE.md's Commands gain MS2's commands (spec §5.10, with `--locked --script`), and the archive names once MS2-Q2 is answered.
- [ ] **Step 5: The reviews.**
  - `security-review` (CLAUDE.md: before a merge that touches keys). `set_b_masks` is a new Meta caller that reads `MODEL_API_KEY`, and the branch handles the archive password. The skill diffs against `origin/HEAD`.
  - Then the final whole-branch review, on Opus 5.5 at xhigh, with `superpowers:requesting-code-review` against `main`.
  - Fixes get their own commits, after `superpowers:receiving-code-review`.
- [ ] **Step 6:** Commit `docs: credit py7zr and close MS2's build`.

---

## Rene runs (never an agent step)

Rene runs each command in his own Windows PowerShell window. He starts at the repo root of the checkout that holds the tools: `C:\Systems\Lusot\lusot` once `ms2-data` has merged, or `C:\Systems\Lusot\lusot-wt\meta` before that. He first refreshes the PATH:

```powershell
$env:Path = [Environment]::GetEnvironmentVariable('Path','Machine') + ';' + [Environment]::GetEnvironmentVariable('Path','User')
```

**`<date>` in a command** stands for the run's date, such as `2026-10-30`. Replace it before running: PowerShell reads `<` as an error, so a command with the placeholder left in stops before it runs.

**R0. If Claude's intake or M8 sheet run is blocked** by the auto-mode check (the logs sit under the user-level deny rules), Rene runs it with `!` in Claude's prompt, so Claude sees only its printed ids and counts:

```text
! uv run --locked --script eval/data/intake.py --set-a-log "C:/Systems/Lusot/lusot-data/set_a/set_a_log.csv" --set-a-photos "C:/Systems/Lusot/lusot-data/set_a/raw" --a-neg-log "C:/Systems/Lusot/lusot-data/a_neg/a_neg_log.csv" --a-neg-photos "C:/Systems/Lusot/lusot-data/a_neg/raw" --m8 "C:/Systems/Lusot/lusot-data/set_a/m8_labels.csv"
! uv run --locked --script eval/data/m8_sheet.py --set-a-log "C:/Systems/Lusot/lusot-data/set_a/set_a_log.csv" --out "C:/Systems/Lusot/lusot-data/set_a/m8_sheet.html"
```

Leave out `--m8` until the export exists. On Oct 28, `uv` resolved in Claude's shell. If it isn't found there, run the same command in your PowerShell window and paste its output to Claude.

**R1 (T9).** Install 7-Zip: `winget install --id 7zip.7zip --exact`.

**R2. Before the split,** all five must hold:
- `C:\Systems\Lusot\lusot-data\sealed\` exists (the split refuses a missing archive folder)
- the intake prints `problems=0` on the final logs and M8 export
- MS3b-Q5 is answered, and the page states that answer
- every Set A photo is labelled
- Task 20's v0.7 status is noted

**R3. The split** (M19), typing the password twice from the password manager. Close other windows first: the split holds the photos in memory until the dev copies are written. It reads every photo, draws and audits first, and asks for the password only after every check passes (S-R19):

```powershell
uv run --locked --script eval/data/split.py --set-a-log C:\Systems\Lusot\lusot-data\set_a\set_a_log.csv --set-a-photos C:\Systems\Lusot\lusot-data\set_a\raw --a-neg-log C:\Systems\Lusot\lusot-data\a_neg\a_neg_log.csv --a-neg-photos C:\Systems\Lusot\lusot-data\a_neg\raw --m8 C:\Systems\Lusot\lusot-data\set_a\m8_labels.csv --set-a-dev C:\Systems\Lusot\lusot-data\set_a\dev --a-neg-dev C:\Systems\Lusot\lusot-data\a_neg\dev --archive C:\Systems\Lusot\lusot-data\sealed\lusot-sealed.7z --record eval\data\records\<date>-split.json
```

Expect `warnings=<n>` first, then `audit PASS`, `copy check <n> of <n>`, and the archive's size and SHA-256. A stop before writing names what to fix; fix it and run the command again. If the run was interrupted after writing, delete what the rerun names, then run it again.

**R4.** Test the archive: `& "C:\Program Files\7-Zip\7z.exe" t C:\Systems\Lusot\lusot-data\sealed\lusot-sealed.7z`. 7-Zip asks for the password. Expect `Everything is Ok`.

**R5. Only after R4,** delete the plaintext inputs (C219). Close Excel first: a working copy open in `raw\` would stop the delete partway. Then click the M8 page's "Clear saved work", and delete any other copy of `m8_labels.csv`, such as one in Downloads. Then:

```powershell
Remove-Item -Recurse -Force C:\Systems\Lusot\lusot-data\set_a\raw, C:\Systems\Lusot\lusot-data\a_neg\raw
Remove-Item -Force C:\Systems\Lusot\lusot-data\set_a\set_a_log.csv, C:\Systems\Lusot\lusot-data\set_a\m8_labels.csv, C:\Systems\Lusot\lusot-data\set_a\m8_sheet.html, C:\Systems\Lusot\lusot-data\a_neg\a_neg_log.csv
```

Then tell Claude: "split done, 7-Zip test passed, inputs deleted".

**R6. Set B's final cars** (C214), after C213's generator freeze and by Nov 1. The summary shows the planned calls and their cost before you type `yes`: 3 SAM calls per photo at $0.0025 a call, about $0.04 for 5 photos. A car without its owner's OK is skipped and never sent. Close the window afterwards, because the key stays set in it.

```powershell
$env:MODEL_API_KEY = [Environment]::GetEnvironmentVariable('MODEL_API_KEY','User'); uv run --locked --directory backend/analysis python probes/set_b_masks.py --final --cars C:\Systems\Lusot\lusot-data\set_b\sealed\cars.csv --photos C:\Systems\Lusot\lusot-data\set_b\sealed\photos --out C:\Systems\Lusot\lusot-data\set_b\sealed\masks
```

Then, in a new window, with the same password typed twice:

```powershell
uv run --locked --script eval/set_b/generate.py --final --cars C:\Systems\Lusot\lusot-data\set_b\sealed\cars.csv --masks C:\Systems\Lusot\lusot-data\set_b\sealed\masks --dev-cars C:\Systems\Lusot\lusot-data\set_b\dev\cars.csv --dev-masks C:\Systems\Lusot\lusot-data\set_b\dev\masks --archive C:\Systems\Lusot\lusot-data\sealed\lusot-sealed-set-b.7z --record eval\data\records\<date>-set-b-final.json
```

Test it as in R4, then empty the folder: `Remove-Item -Recurse -Force C:\Systems\Lusot\lusot-data\set_b\sealed\*`. The archive keeps the owners' OKs.

**R7. Set D** (C217), only if it rains:

```powershell
uv run --locked --script eval/data/seal_set_d.py --log C:\Systems\Lusot\lusot-data\set_d\sealed\set_d_log.csv --archive C:\Systems\Lusot\lusot-data\sealed\lusot-sealed-set-d.7z --record eval\data\records\<date>-set-d.json
```

Add `--extends eval\data\records\<date>-freeze.json` once the freeze record exists. Test it, then run `Remove-Item -Recurse -Force C:\Systems\Lusot\lusot-data\set_d\sealed\*`.

**R8. At the sealed run** (Nov 3, as MS6's procedure orders):
- Extract each archive into `sealed\run-1\`, MS6E-Q3's default: `& "C:\Program Files\7-Zip\7z.exe" x C:\Systems\Lusot\lusot-data\sealed\lusot-sealed.7z -oC:\Systems\Lusot\lusot-data\sealed\run-1`, and the same for the Set B and Set D archives.
- Then run the audit, type `yes`, and expect `PASS`. Add `--record eval\data\records\<date>-set-d.json` when Set D was sealed. Leave out the Set B final record's `--record` if no final-car run happened (fewer cars, Rene's decision, Oct 29).

```powershell
uv run --locked --script eval/data/audit.py --sealed C:\Systems\Lusot\lusot-data\sealed\run-1 --dev-root C:\Systems\Lusot\lusot-data --record eval\data\records\<date>-split.json --record eval\data\records\<date>-set-b-final.json
```

## Later steps, outside the build (Claude)

Live spend stays under $0.25 in all (spec §3). Commands are spec §5.10's, run as `uv run --locked --script`.
- **L1.** `intake` on Rene's logs whenever he asks; if it's blocked, R0. Its `no_class` count shows how many Set A photos C204 can't stratify as deep.
- **L2.** `m8_sheet` once Set A is in, rerun as rows are added. Before Rene labels, set `IN_BETWEEN_RULE` to his MS3b-Q5 answer, in a commit on the branch that holds the tools. Claude never opens the page in a browser.
- **L3.** After R5: `audit --dev` for Set A and for A-neg (expect `PASS`), then commit the record (`chore(data): add the split record`).
- **L4. Set B's development cars:**
  - `set_b_masks` on the development photos. **Budget:** 3 SAM calls per photo, $0.0075 a photo, about $0.04 for 5 photos.
  - `generate`, then Claude reviews every overlay: the line sits on the truth row, and the masks hold the wheels (C213, step 1).
  - `set_b_masks --water` on the development crops. **Budget:** 1 call per crop, about $0.05 for 20 crops.
  - `water_check`, then commit its look record.
  - If the look fails: change the water's look, bump `GENERATOR_VERSION`, delete `generated\`, and run `generate`, `set_b_masks --water` and `water_check` again, for at most 3 looks. `set_b_masks --water` re-segments every changed crop by its hash, so old masks are never reused. The version is frozen before MS3b's first Set B score.
- **L5.** `setc sturm`, and FloodDET as Task 19's note decides.
- **L6. M11** (Rene's decision, Oct 29): the tracker compiles public-spec tire sizes for the five vehicles, each with its citation; Rene reviews them; they go to Window 3 for MS3b's tire-code file (its C304). Only a sidewall photo Rene still takes goes through `sidewalls.csv`: read it, fill `checked_code`, and rerun the intake with `--sidewalls`.
- **L7. MS2's close:** run `freeze_record` (V8) with the look records, and commit its output. The CLAUDE.md lines go through `revise-claude-md`, and the board and log lines go to Window 3.

## Waiting on others

- **`eval/rules.md` (B.8):** Window 4's v0.7 proposal, applied by Window 3 after Rene's written OK. Its item 4.2 carries the stratified walk. This plan only confirms it (Tasks 1 and 20).
- **`.claude/settings.json`:** no change. The tracker's user-level denies (about 4:08 PM) cover `lusot-data/**/sealed/**`, `set_a/raw/**`, `a_neg/raw/**`, `set_a/*.csv` and `a_neg/*.csv`.
- **`package.json` and CI:** the merge owner adds MS2's test line (Task 20).
- **`docs/PROGRESS.md` and `docs/log/`:** Window 3 (D20). **`CLAUDE.md`:** at MS2's close.
- **Rene:** MS2-Q2, which rides on `eval/rules.md` v0.7. MS2-Q1, MS2-Q3 and MS2-Q4 were approved as (a) on Oct 29 by Claude under Rene's delegation, and MS3b-Q5 was answered on Oct 28.
- **Window 4:** version labels for the Set B owner and M11 driver texts, so C218's constant can hold them. Done on Oct 29: `M9-v4`, `SETB-v1` and `M11-v1`, approved by Claude under Rene's delegation, which Task 13b puts in the constant.
- **Window 3:** once MS3a's runner, with its `refuse_sealed`, is on `main`, `set_b_masks` may import that instead of its copy.
