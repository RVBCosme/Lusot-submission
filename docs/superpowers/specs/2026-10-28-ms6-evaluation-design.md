# MS6 Evaluation: spec

- **Date:** Oct 28, 2026 (Manila)
- **Status:** Draft. Window 4 wrote it without a live conversation (D7, D15), following its window prompt. A fresh accuracy review and a builder check (both Opus 5.5 at max) are folded in. Claude proceeds on the calls in §5 and the defaults in §8 until Rene approves the whole spec. On Oct 29 it took rows 16, 19, 20, 21 and 30 of the tracker's cross-spec audit: the inches switch's name, the freeze tags, level agreement in `summary.json`, what latency measures, and label prefixes.
  - **Approved, Oct 29 evening,** by Claude under Rene's delegation after the tracker's check, apart from the questions held for Rene as parts of v0.7 (MS6E-Q1's 17 items, Q4, Q5 and Q6). MS6E-Q2 is settled by MS2's C208, and Q3 takes (a): the extract into `run-1`, deleted afterwards.
- **Scope:** MS6's evaluation part (design §8's MS6 row). The harness is built now, on synthetic data, because MS3b's development ablation and Set B scoring run it from Oct 30 (MS3b's C321). The sealed run is Nov 3. Ask Lusot gets its own spec after MS4's.
- **Implements:**
  - plan §11: Tables 12 and 13, the release gate for inches, reproducibility and the one-command check
  - plan §19's evaluation practices: no flood event shared between the sealed and development sides, the underestimation rate before anything else, a sample size on every figure, and the raw model outputs kept
  - the evaluation part of plan Table 22's Phase 6 finish line
  - design §8 (the MS6 row, the pipeline freeze, B2), G3 and G4; `eval/rules.md` v0.6 §1 to §3 and §5 to §10
  - plan Table 11's W17 and W19, plus the development checks MS3b reports through this harness (W1 to W9, W13, W14)
- **Builds on** Window 3's branch `ms3a-landmark-core` (these refs are as of Oct 28; MS3a, with MS3b's spec, merged into `main` at `96c2f11` on Oct 29, and MS2 builds on `ms2-data`):
  - from MS3a: `Outcome` and its `item_fields()` (`pipeline/types.py`), the outcomes in spec §3.4, the offline runner and its saved-run layout (spec §3.7 and C66; plan Task 9)
  - the MS3b spec at `860a294`: C307 to C309, C311, C314, C315, C320, and C321, which records this spec's boundary from MS3b's side
- **Needs from MS2:** the manifests, the M8 labels, the archives and the audit. Window 2's MS2 spec is committed on `next-specs` at `586296c` (calls C200 to C224), and MS2's formats win:
  - its manifest keeps raw labels and rules §9's facts (its C207), M8 labels carry points (C208), and its standard-library audit runs at the sealed run
  - MS3b's export bridges MS2's files into §4.3's rows: CSV into JSON Lines, `yes`/`no` into booleans, `;`-separated lists into lists, the marks from M8's photo row, M8's points into box ids, `duplicate_of` into `duplicate`, and Set D's `photo_id`, `left`/`right` and `ruler_depth_in`
  - two differences are settled by C423

  If MS2's approved formats change again, MS2's win, and this spec records the change.

## 1. Intent

The sealed evaluation is one of the things Lusot's pitch leads with (CLAUDE.md; plan §1 and §19), and it counts only if a judge can check it. So MS6 runs the frozen pipeline once on the sealed sets, scores the result by rules written before any result was seen, and commits the per-photo results. One command then rebuilds every table, with no key, no installs and no network.

The scoring lives in one place. MS3b's development ablation and its Set B scoring run the same harness (C400). The figures that set geometry's live default on development data and the figures judges rebuild therefore come from one implementation.

The report claims what it can and no more. Its figures are agreement with the labels MMDA and the cities posted, not accuracy, with the label mapping fixed in advance (W17). Every figure carries its sample size and is called indicative (W19). Underestimation, passability and coverage come first, with coverage beside every rate. Both configurations are shown, whichever one ships.

## 2. Goals, non-goals, anti-goals

**Goals**
1. A standard-library harness, `eval/run_eval.py` with `eval/scoring/`. It holds the only implementation of `eval/rules.md` §7's metrics, §8's gate and outcome rule, and the report with its charts.
2. A results contract (§4.3) that MS2's manifests, MS3b's development export and the sealed-run export all write to.
3. The sealed-run procedure Rene runs (§4.5), the pipeline freeze before it (§4.6), and room for rules §10's one disclosed rerun beside the first run (C421).
4. Tests on synthetic fixtures for every metric, the gate's boundaries, the label mapping, the exclusions, the privacy allow-list and the one command.

**Non-goals**
- Ask Lusot.
- Running the sealed run, which always waits for Rene, or opening any sealed data.
- **The export and the entry point.** MS3b builds the export from saved runs in `backend/analysis/` (its C321). The sealed-run entry point is built by `backend/analysis/`'s owner after MS3a and MS3b merge, and reuses that export. This spec fixes their contract (C412).
- MS2's tools: the manifests, matching, the split and its audit, the archives, the M8 sheet, and the Set B generator with its G3 truth.
- MS3b's replay and geometry code.
- **Set C.** It has no MMDA labels and never counts toward a headline (rules §4), so MS3b checks it in development, outside this contract.
- The app's accuracy page (MS5). It can read the report's summary file (C409).
- Metrics beyond rules §7, such as confidence intervals.

**Anti-goals** (failures even if the code works)
- A number in the report, README, video or app that the one command doesn't rebuild.
- A scoring choice made after a sealed result is seen, or any tuning on sealed data.
- A figure without its n, a rate without coverage beside it, or Set A results called accuracy.
- Photos, masks, Muse Spark's `reason` text, post links, spot names or any other free text in the repo.
- A harness that reads a sealed path, defaults to `LUSOT_DATA_DIR`, needs a key or opens a network connection.
- "Safe" in any form, crossing advice or a claim about a whole road in the report.

## 3. Constraints

- **The report path** uses only the Python standard library and runs on Python 3.9 or newer, since macOS ships 3.9 as `python3` (C401). It reads no environment variable, opens no network connection, and writes the same bytes every time.
- **The tests** may use pytest and scikit-learn, pinned, locked and run through uv (C417). Proving the 3.9 promise takes one uv-managed CPython 3.9 (E10). That is the only download beyond uv's test environment.
- **No imports across the boundary.** `eval/` never imports `lusot_analysis`, and MS3's code never imports `eval/`. They meet through files (C400).
- **Data:** synthetic fixtures only on this branch, and no Meta or AWS call. Nothing under `set_a\`, `a_neg\` or any `sealed` folder is opened (CLAUDE.md, design §12, C39).
- **The rules freeze once Rene approves them.** The harness implements `eval/rules.md` v0.6, with the defaults of MS6E-Q1 and MS6E-Q5. Any change to `eval/rules.md` needs Rene's written OK.
- **Plan text** is cited by section and table, never copied.
- **The laptop:** one test process at a time, and no installs beyond those above.

## 4. What gets built

### 4.1 The harness and the one command (C401)

All new files: `eval/run_eval.py`, the standard-library package `eval/scoring/`, the tests in `eval/tests/`, and synthetic results in `eval/tests/fixtures/`.

| Command | What it does |
|---|---|
| `python eval/run_eval.py --from-saved` (or `python3 ...`) | Rebuilds every table, chart and the summary from `eval/results/`, and from `eval/results/rerun/` if rules §10's rerun happened. It finds the folder beside the script, so it works from any folder. It compares what it built with the committed copies in each `report/` folder, then prints the headline counts and either "identical" or the files that differ. |
| `... --results DIR` | Uses another results folder: a development run or a fixture. A path with any part named `sealed` is refused before anything is read (C411). |
| `... --write` | Writes the report files instead of comparing. Used once after the sealed run, and for development reports. |
| `python eval/run_eval.py --label-words` | Prints the words a committed label may hold, one per line, for the export (C420). |

`--from-saved` is required for a rebuild: it states that nothing calls a model. Exit codes: 0 when the report is rebuilt and identical (or written), 1 when it is rebuilt but differs, and 2 when the input is refused or invalid. Printed output is ASCII counts only, so any console can show it.

### 4.2 Scoring (rules §1 to §3 and §6 to §9)

**What each result scores as (C405).** Each Set A photo has one result per configuration (§4.3):

| Result (`item_fields()`) | Answered? | Scored level | Passability |
|---|---|---|---|
| `done` with a level | yes | its level; a floor (`levelIsFloor`) at its own level | the level's class |
| `done` with `noFloodSeen` | yes | one step below `below_gutter`, so always an underestimate (rules §7) | PATV (rules §7) |
| `refused` | no: a refusal | none | none |
| `failed` | no: a processing failure | none | none |

**The ground truth (C404).** The manifest's label is the alert nearest in time (MS2's C209), and the other matching alerts' labels come with it.
- The harness maps every label by rules §2.
- **Statuses:** a status that isn't a depth ("subsided") can't match a photo (rules §2). As the main label it gives "no matching alert"; among the others it is ignored.
- **Conflicts:** any two matching alerts more than one level apart exclude the photo as "conflicting alerts" (rules §3). An unmapped label among the others makes a conflict impossible to rule out, so it excludes the photo as "unmapped label".

The status and unmapped rules are MS6E-Q1's defaults.

**Who counts where (C405).**
- **Excluded photos** (rules §9, from the manifest's facts) are logged with their reason and scored nowhere.
- **Coverage** is over every scored photo, with refusals and failures counted apart.
- **The level metrics** (under- and overestimation, exact and within-one agreement, weighted kappa) are over answered photos whose alert gave a depth that maps to a level.
- **Passability agreement** is over answered photos whose alert states a class that maps. This is rules §2's proposal, which narrows Table 13's denominator from every answered photo.
- **The false flood rate** is over every scored A-neg photo. A processing failure counts in n, never as a false flood, and is shown beside it (MS6E-Q1).
- **Correct refusals** are over every scored photo marked `dark` or `blurry`. A processing failure is not a refusal, since CLAUDE.md keeps the two apart.

**The metrics** (rules §7). Each comes with its n, and each is per configuration unless marked.
- **Set A:** the underestimation rate, passability agreement and coverage (reported first); the overestimation rate; exact and within-one agreement; quadratic-weighted kappa over the 9 levels, computed by its formula; the counts of "no flood seen" and of floors; refusals and failures by reason.
- **Set A, once per run** (Muse Spark's answer is the same in every configuration): landmark agreement by kind (wheel, body, person) against M8's labels (C415).
  - Photos with no answer are left out, since their failure already counts in coverage.
  - In an answered photo, a labelled box that Muse Spark skipped counts as a disagreement and is also shown apart.
  - A label that matched no box is counted apart and left out.

  Development runs add the vehicle-type confusion matrix (W14).
- **A-neg:** the false flood rate, beside the counts of "no flood seen", refusals and failures, also split by `surface` (wet or dry; W9).
- **The quality subset:** correct refusals (C414).
- **Set B, then Set D apart:** the wheels measured; the median and worst absolute error of each wheel's point estimate from its true tire code; and envelope coverage, over measured wheels (MS6E-Q1). Each is given per variant (C407), by vehicle type, and by the producer's bins.
- **Latency,** when live-test timings are supplied: the median and the nearest-rank 95th percentile (C416).
- **Subsets** marked before the run (`reflection`, `splash`, `moving`), plus photos whose alert gave tire or deeper (W6): n, coverage, underestimation and passability agreement.

**The ablation** is the same tables with one column per configuration: landmark alone, landmark plus geometry, and, when the self-check is on, geometry without it (rules §7 and §8).

**Guards against over- and underfitting** (Rene's review-loop and data-roles instruction, Oct 28, about 3:35 PM; the tracker's verified v2):
- **The baseline row (C424).** Every report scores two baselines on the same answered rows as each configuration:
  - "always the most common level", the most common mapped level among the development Set A photos
  - "always the most common passability class", likewise
  - It scores them on within-one agreement and underestimation, which Lusot should beat. Exact agreement is shown but not compared, since landmarks never read `gutter` (rules §6).
  - It also counts the NPLV and NPATV photos each one catches.
- **Per-level results.** A table by the alert's level gives each level's n, answered, exact, within-one and underestimated counts. A level with fewer than 5 photos shows counts only, with no percentages.
- **Event replay (C425).** On development runs, each configuration may carry a replay result per photo, scored with settings chosen on the other flood events. It is shown beside the in-sample one, with the difference in within-one photos that MS3b's guard 3 reads.
- **Numbers, not verdicts.** The report states comparisons as numbers ("the baseline's within-one agreement is higher: 12 of 20 against 10 of 20"). It never calls a result over- or underfitting.
- **Rene's review sheet (C426).** A development run also writes `review.csv`, one row per development photo, for his verdict and note.

### 4.3 The results layout and the row contract (C402, C403, C420, C421)

`eval/results/` is created at the sealed run, not on this branch. Development runs use the same layout in a private folder under `LUSOT_DATA_DIR`, passed with `--results`.

| File | One line per | Holds |
|---|---|---|
| `run.json` | run (a single JSON object) | `kind` (`sealed` or `development`); `synthetic: true` for a test fixture only (C422); the Manila date; `rules_version`; the freeze commit (sealed runs); the frozen versions (rules §10's list, plus the SAM phrases sent, any backup phrase included, `store` and `max_side`, the annotation (drawing) version, and MS3b's tuning version, k, tire codes and reasoning effort); each dataset's version and split seed (MS2's records, its C216); `self_check` (`on` or `off`) and when MS3 decided it; geometry's live default before the run (C309), or `dropped` (C418); `baseline_level` and `baseline_class` (C424; required in a sealed run, and frozen from the last development report); `service_retries` (MS6E-Q6; an integer of 0 or more, counting the photos retried once after a Meta service failure; required in a sealed run, and read as 0 when a development run leaves it out); each stop and resume (C419); and, for a rerun, its reason (C421) |
| `set_a.jsonl` | Set A photo, excluded ones included | see below |
| `a_neg.jsonl` | A-neg photo | as for Set A without labels or M8, plus `surface`. It keeps MS2's facts, with `match` null, but scoring reads only `duplicate` and `decodes` (MS6E-Q1). MS2 has no M8 for A-neg, so `quality` is null and `subsets` empty (C423). |
| `set_b.jsonl` | Set B wheel in one crop (a crop shows up to two wheels) | see below |
| `set_d.jsonl` | Set D wheel, only if it rained | as for Set B, with the ruler depth as the truth |
| `latency.jsonl` | live test (optional) | its id (`L1`, `L2` and so on, never a report id), and its seconds from the upload, or a sample's start, to the final result (C416) |
| `report/` | | `report.md`, the SVG charts and `summary.json`, all rebuilt by the one command |
| `rerun/` | | only after rules §10's one disclosed rerun: the same files for the rerun (C421) |

**A Set A row:**

| Part | Fields | From |
|---|---|---|
| Ids | `photo_id`, `event_id` | MS2's manifest and split |
| Labels as written | `level_label_raw` and `passability_raw`: the nearest alert's (empty when it gave none). `other_alerts_raw`: a list of the other matching alerts' labels. | the Set A log (MS2's C209) |
| Facts for rules §9 | `poster_kind` (`mmda`, `city` or `other`), `label_in_image` (`no`, `cropped` or `yes`), `match` (`same_post`, `separate_post` or `none`), `duplicate`, `metro_manila`, `decodes` | the log, MS2's matching and its split |
| Marks made before the run | `quality` (`ok`, `dark` or `blurry`, or null when no mark was made) and `subsets` (tags, possibly none) | the M8 sheet's photo row (MS2's C208) |
| Results | `outcomes`: `landmark`, `geometry` and, with the self-check on, `geometry_no_self_check`. Each is an `item_fields()` object, plus MS3b's `levelFrom`, `depthInMin` and `depthInMax` where set, as the item stores them (C308). On development runs only, any configuration may also carry `<configuration>_replay`, its event-replay result (C425). | the export, by replay |
| Readings | `answer`: Muse Spark's saved answer without its `reason` (null when no answer was made). `wheel_inches`: `depthInMin` and `depthInMax` by box id, unrounded, for each wheel the geometry configuration measured. | the export |
| Our labels | `m8`: for each labelled reference, its box id (null when its point matched no box), kind and landmark, plus the type for a vehicle | the M8 sheet, joined by the export (C415) |

**A Set B row:**
- `crop_id` and `wheel`, which together are unique, and `car_id`
- the true `vehicle_type` and `tire_code`, and `true_depth_in` (G3)
- `sam_water_found`, and optional `bins`, such as view and size (W7)
- `estimates`, keyed by variant. A measured wheel gives `depthInPoint` (the estimate from its true tire code), `depthInMin` and `depthInMax`, unrounded, to 4 decimal places. An unmeasured one names the check that failed.

The variants:
- `geometry`: the frozen configuration, with SAM's waterline and the frozen k. Only this variant gates (C407).
- `geometry_uncalibrated`: SAM's waterline with k = 1 (rules §5)
- `known_waterline` and `known_waterline_uncalibrated`: plan Table 12's second run, which gives the geometry the known waterline directly, with the frozen k and with k = 1 (MS3b's C314)
- `geometry_no_self_check`: only when the self-check is on

**The allow-list (C403, C420).** The loader refuses any row that has:
- a field outside this contract
- an id that isn't opaque. An id is 1 to 3 capital letters, 1 to 4 digits, and at most two `-` suffixes of 1 to 3 digits, so no date or spot fits.
- a value outside its field's own list: the 9 levels, the 3 classes, schema v1's categories, or MS2's fact values. Reasons, tags and failed checks must be lowercase tokens.
- a raw label holding anything but rules §2's words, numbers of up to 3 digits, units and simple punctuation, unless it is exactly the marker `(other words)` that the export writes instead (C420)
- a number with more than 4 decimal places

So no committed field can hold free text, and Muse Spark's `reason`, post links, emails, spot names, cities and times have nowhere to go. Photos and masks never appear.

### 4.4 The report (C409, C410)

`report/report.md` runs in this order:
1. What was run and when, and what its figures are: agreement with the labels MMDA and the cities posted, mapped by rules §2 before any result was seen (W17). Every figure is indicative and carries its n (W19).
2. **Reported first:** underestimation, passability agreement and coverage, for the configuration that ships and then for the other, each as "k of n (p%)".
3. **The release gate:** each target with the value found and whether it passed; the two guards; the outcome rule's decision; and whether inches show, with the reasons when they don't. One line gives MS3's self-check decision. With the self-check on, its extra row is marked as reported but never chosen.
4. Set A's ablation tables (with replay columns on development runs, C425), the baseline rows (C424), the per-level table, the level matrices, landmark agreement, A-neg (also by surface), the quality subset and the subsets. Comparisons are stated as numbers, never as verdicts.
5. Set B and Set D, with the error chart.
6. Latency, if measured.
7. **Exclusions:** the count for each rules §9 reason, and each excluded id with its reason.
8. The frozen versions, the stops and resumes (C419), and the datasets with their photo and event counts. One line states the face blur's known limits: it runs before Meta receives a photo, and it can miss faces that are very small, side-on, partly covered or in the dark (W25).
9. **How to rebuild the report:** `python eval/run_eval.py --from-saved`, or `python3 eval/run_eval.py --from-saved` where `python` isn't installed, as on macOS and many Linux systems.
10. **The footer:** "Lusot estimates depth at one spot. It is not advice to cross. Follow MMDA and local advisories." and "Not affiliated with MMDA."

**Other kinds of report:**
- **A development report** has the same sections, with three differences:
  - its header says the data is development data
  - its gate section is titled as the outcome rule on development data, which is the figure C309 reads, not the release gate
  - it adds the vehicle-type confusion matrix
  - its tables show replay results beside the in-sample ones (C425), and `--write` also writes `review.csv` (C426)
- **A rerun's report** (C421) says it is rules §10's one disclosed rerun and why, and gives the first run's headline and gate rows beside its own.
- **When geometry was dropped** before the freeze (C418), the report shows one configuration and says why.
- **A results folder with only Set B** (MS3b's D2): "Reported first" and the gate read "Not run in this results folder.", and the summary holds nulls for Set A.
- **A synthetic test fixture** (C422) opens by saying it holds synthetic test data, not Lusot's results.

`report/summary.json` holds the headline figures, each configuration's exact and within-one agreement as `{k, n}` (MS5-M1), the gate's decision and Set B's figures for the app's accuracy page (MS5), so no number is copied by hand.

**Charts** (the dataviz skill, as plain SVG; C410):
- **One level matrix per configuration.** The alert's level (MMDA's or the city's) runs down the side and Lusot's across, with "no flood seen" first. Counts shade the cells on one sequential hue, and the agreement diagonal is outlined. Each non-empty cell shows its count. That is a deliberate exception to the skill's rule against a number on every point: with about 20 photos the counts stay readable, and they are the data.
- **Set B's error per measured wheel** in the `geometry` variant, sorted, with the gate's 3 in target as a solid reference line and the median marked.
- **The headline figures stay a table.** The skill puts a handful of headline numbers in tiles or a table, not a chart.
- **Every chart** has a table twin in the report, a title and a description, and colours from the skill's reference palette, checked with its validator. Light and dark styles come from a media query inside the SVG. Each mark has a `<title>` tooltip. GitHub shows an SVG as an image, where tooltips don't appear, so the twins carry the values there.

### 4.5 The sealed run (Rene runs it; Claude never does)

**Before it** (items 1 to 4 by Nov 2, as §7 and design C19 give M18's date; the freeze, item 5, on the evening of Nov 3, after Rene's QA of the real app that afternoon and once he approves it, just before the run; a measuring-path change on Nov 4 needs `freeze-2`, C421):
1. Rene approves `eval/rules.md`, with M18's gate numbers and his answers to MS6E-Q1 and MS6E-Q5 in its change log.
2. MS3 has decided the self-check on development data (C311). It has also set geometry's live default from the development ablation that this harness computed (C309, C315), or dropped geometry (C418).
3. MS4's recovery tests on the analysis path have passed (design §8, B2).
4. Any Set D photos, which exist only if it rained, are sealed by the end of Nov 2, so they are in `freeze-1`'s run.
5. The freeze (§4.6) is one commit on `main`, tagged `freeze-1`, with the harness's tests and the entry point's tests green. It records the last development report's `baseline_level` and `baseline_class` (its `summary.json`), which the entry point writes into the sealed run's `run.json` (C424).

**The run** (Nov 3):

5. **The archives.** Rene checks each archive's SHA-256 against its committed record (MS2's C205 and C216), then extracts them with 7-Zip into a folder named `sealed` under `lusot-data`. The password step follows MS2's C206. Claude never sees the password or a sealed photo.
6. **The audit, then the entry point.** In his own terminal, Rene runs MS2's audit on both sides (W18), then `backend/analysis/probes/run_sealed.py` (C412). The entry point checks the freeze, asks him to type a confirmation, and checks every label against rules §2's words before any paid call (C420). Then, for each sealed photo, it:
   - runs the frozen pipeline once, with the self-check if it is on. It sends the same face-blurred photo the live system would (rules §10), with the 5 phrases the reading uses (C66). Nothing is published, so the face and plate phrases are skipped.
   - replays the saved outputs for each configuration, so every configuration comes from that one pass (C309, C315)
   - saves the raw SAM masks and Muse Spark answers under the `sealed` folder (rules §10; plan §19)

   Set B's final crops go through SAM's phrases and the geometry, and so do Set D's photos if any exist. A run that stops partway resumes (C419). The entry point prints counts and timings only, and writes the export (§4.3) to the repo's `eval/results/`.
7. Rene runs `python eval/run_eval.py --from-saved --write`, then `python eval/run_eval.py --from-saved`, which must exit 0.

**After it:**

8. Rene reads the diff, and the export and the report are committed. Claude may commit them on his word.
9. **The decision is applied.**
   - `geometry_in_level` is set in the template and deployed (C309).
   - Only if inches pass is `INCHES_SHOWN` flipped to `"true"` in the template, in the commit that records the gate's decision (MS4's C515). The next deploy then shows `depthInMin` and `depthInMax` in `GET /reports/{id}` (C308), for MS5 to word (M20).
   - Otherwise pins keep the level and the landmark, and the report says why.
10. Rene deletes the decrypted photos (MS6E-Q3). The archives and the raw outputs stay.
11. If a later fix could change any depth output, rules §10's one disclosed rerun follows, only with Rene's go-ahead, at a second freeze (C421).

The "Done when" rows S1 to S6 (§6) are proved only here.

### 4.6 The pipeline freeze (C413)

- **What freezes:** the model IDs; the prompt and schema versions; Muse Spark's reasoning effort (MS3b-Q4); the SAM phrases, any backup phrase included; `store` and `max_side`; the annotation (drawing) version, since a change to the numbered boxes changes what Muse Spark sees; the self-check setting (rules §8); the level rules; the face-blur setting and its detector version; MS3b's tuning version, tire codes, k and geometry's default; the baseline's level and class (C424); the dataset versions and split seeds (rules §10; design §8). Also `eval/rules.md`'s version and this harness.
- **How:** one commit on `main`, tagged `freeze-1` and recorded in `run.json`. The entry point refuses any other commit, and a tree with changes. The one disclosed rerun runs at a second freeze, tagged `freeze-2` and recorded with its reason (C421).
- **After it:** only fixes that can't change a depth output (rules §10). The scoring code doesn't change after the sealed run. A change to the report's presentation regenerates the report with `--write` in the same commit, and the byte-for-byte check enforces that.

### 4.7 Who owns what

| Piece | Owner | Notes |
|---|---|---|
| The metrics, the gate, the outcome rule, the report, the results contract and this procedure | MS6 (this spec) | the only implementation (C400) |
| The export from saved runs, and the development rows from replays (C315) and from Set B's geometry runs (C314) | MS3b | its C321: it writes §4.3's rows to a private folder and runs the harness on them |
| The sealed-run entry point, `backend/analysis/probes/run_sealed.py` | `backend/analysis/`'s owner, after MS3a and MS3b merge | C412; it reuses MS3b's export |
| The manifests with the §9 facts, the M8 sheet and its marks, the split, the audit, the archives, and the Set B generator with its G3 truth | MS2 | its C200 to C219; §4.3 is the consumer contract |
| `INCHES_SHOWN`, which turns on the API's inches (MS4's C515; C308), and `geometry_in_level` in the template | the template's owner | steps after the gate (§4.5, step 9) |
| The latency rows (C416) | the window that runs MS5's live checks (its C631) or MS7's rehearsal | it commits them as `eval/results/latency.jsonl`, in §4.3's shape, before the freeze |
| Adding the eval tests to `npm run check` and CI | the window that merges this branch | after the merge |

**Design §7's open questions:**
- **Design R7** (how the submission repo gets its history; default: full history) carries `eval/results/`, with its dates, into the submitted repo.
- **Design R3** (UI language and visual direction; default: asked in MS5's brainstorm) doesn't reach the report, which is written in English for judges.
- **Design R6** (consented photos; default: labelled fallbacks) doesn't reach the evaluation, since consented photos never enter Set A.

## 5. Decisions (Claude's calls)

| # | Call | Why |
|---|---|---|
| C400 | **One implementation, through files.** `eval/scoring/` and `eval/run_eval.py` are the only code for rules §7's metrics, §8's gate and outcome rule, and the report. MS3b's Set B scoring (C314) and development ablation (C315) write §4.3's rows and run `python eval/run_eval.py --from-saved --results DIR --write` (MS3b's C321). Neither side imports the other. | Two copies of a metric drift apart, and the development figures that set geometry's default would then differ from the figures judges rebuild. Meeting through files keeps `eval/` standard-library only and free of `lusot_analysis`. |
| C401 | **The one command.** `python eval/run_eval.py --from-saved` uses only the standard library and Python 3.9 or newer. It needs no key, no network and no install, and works from any folder, as `python` or `python3`. It rebuilds every table, chart and the summary and checks them byte for byte against the committed report, with line endings normalised. It prints ASCII counts and exits 0 when identical, 1 when different, and 2 when refused or invalid. Kappa is computed by its formula, and a test checks it against scikit-learn's `cohen_kappa_score`, as rules §7 names it. Charts are plain SVG, and pytest and scikit-learn stay in the tests. | Rules §10 and design §8 give this exact command. The byte-for-byte check turns "rebuilds every table" into a yes or no that a judge can see. Python 3.9 is the oldest a judge is likely to have, as macOS's own `python3`, which is also why the report names both commands. The `uv run` alternative is MS6E-Q4. |
| C402 | **The results layout and rows** as in §4.3: one file per set, one JSON object per line, and a run manifest. Names keep their sources' style: the Set A log's and MS2's snake_case, Table 14's camelCase for results (`item_fields()`, `depthInMin`, `depthInMax`), MS3b's `levelFrom`, and the schema's names in `answer`. | JSON Lines holds nested results and answers with the standard library, and diffs line by line. Each source's names let a reader trace every field back to it. |
| C403 | **An allow-list loader** (§4.3). Each field is checked against its own list (levels, classes, schema v1's categories, MS2's fact values); ids must be opaque; numbers carry at most 4 decimals. | Rules §10 (a Claude's call there) keeps post links and spot names out, and MS3a's C62 keeps the `reason` text private. Per-field lists accept every real row, such as the classes in capitals, while a strict loader keeps free text out of the committed rows whatever the export does. |
| C404 | **Raw labels in; the mapping and the exclusions in the harness.** The manifest keeps every label as written. The harness applies rules §2: words before numbers, a single number with its unit by the level rule, a range by its upper value, and centimetres at 2.54 per inch. A number with no unit stays unmapped (MS6E-Q1). Every phrase may end with `deep` or `level`, or with neither. §2 lists "above gutter deep" as a variant of "above gutter level", and real alerts write "half tire level" (the alert index), so the two words are interchangeable (MS6E-Q1, item 12). A range may carry a unit on each number (`13"-18"`). Two measures not joined by a range word, such as `24 in (61 cm)`, are one depth in two units: they map when both give the same level, and stay unmapped when they don't (MS6E-Q1, item 13; Pasig gives depths in centimetres and inches). When a label's words aren't one of §2's phrases but its measures give one level, the measures decide (MS6E-Q1, item 15). Quezon City's "ANKLE DEEP (9 inches)" reads `half_knee`, while "Ankle Deep" alone stays unmapped. Two things among the words keep the label unmapped: a bare number with no unit ("8 (25 cm)") and a status ("knee deep, subsided (19 in)"). "Head", like "lagpas tao", maps to `above_chest`. A `+` after a number or after its unit reads "at least", which maps only above 45 in. A `+` anywhere else marks a floor too, as in "Waist+", so the label is unmapped unless it reads `above_chest` (MS6E-Q1, item 16). Two blank main labels give "unmapped label", and so does a blank level label beside a passability phrase that maps to no class, since neither alert gives any ground truth (MS6E-Q1, item 14). Each `other_alerts_raw` entry is a level label, where an empty one (an alert with only a class) is ignored. The harness handles statuses, conflicts and unmapped other alerts as §4.2 says, and applies §9 from the manifest's facts, logging the first reason that applies, in §9's order. Exclusion never reads a result. `decodes` is set before the run (MS2's split), so a pipeline `failed/bad_file` on a file that decoded is a processing failure, not an exclusion. | The mapping is fixed in rules §2, so it runs in one tested place, from the words judges can read, and a mapping Rene adds before the sealed run reaches the sealed rows too (MS2's C207). §9 forbids exclusion by Lusot's output, and a test can prove that only if exclusion never sees a result. |
| C405 | **What a result scores as, and who counts where** (§4.2). "No flood seen" sits one step below `below_gutter`: always an underestimate, never exact, within one level only of `below_gutter`, and counted as `below_gutter` in kappa, which knows only the 9 levels. | Rules §7 make "no flood seen" an underestimate and PATV, but say nothing about agreement or kappa. scikit-learn's `labels=range(9)` drops any value outside the labels without a word, which would hide the most dangerous misses. These readings go to Rene in MS6E-Q1. |
| C406 | **Exact arithmetic.** Rates are exact fractions, and inches exact decimals as written. Targets include their boundaries, so "no more than 10 points" passes at exactly 10. Shown values round half up: rates to 0.1% and inches to 0.01 in. A rate with nothing to count is undefined, and an undefined comparison counts as a guard not met. | A float can put a median of exactly 3.00 in above 3. The report's counts let a judge redo every rate by hand. A refusal beats a guess, so a guard that can't be shown isn't passed. |
| C407 | **The gate** (rules §8). Geometry stays only if Set A underestimation doesn't rise, by MS6E-Q5's test, and both guards hold. Inches show only if geometry stays and Set B's `geometry` variant meets the median-error, measured-share and envelope targets (MS6E-Q1). The shipped configuration's row is the headline, and both rows always show. The self-check row is reported, never chosen. The gate's numbers are constants that a test checks against rules §8. Without Set B, no inches show. | The gate tests what ships. The other Set B variants are reported (rules §5; plan Table 12) but never gate, so nothing is picked after the run. |
| C408 | **Rules drift tests.** Tests read `eval/rules.md` and check that the code's level scale (§1), label table (§2), exclusion reasons (§9), gate numbers (§8) and version match it. A `run.json` whose `rules_version` differs from the harness's is refused. | Rules §2 and §8 change only with Rene's OK. The tests make the code follow, so the report can't apply a rule the file doesn't state. |
| C409 | **The report** as in §4.4: deterministic, plus `summary.json` for the accuracy page. It never says "safe" (checked in any case), and it carries the footer's two lines. | W17, W19 and rules §7's coverage beside every rate, in a fixed order a judge can follow. One summary file keeps the app's figures from being copied by hand. |
| C410 | **The charts** as in §4.4. | The dataviz skill: a grid of magnitudes is a heatmap on one hue, a few headline numbers are a table, every chart has a table twin, and colours come from a validated palette. The count labels are a deliberate exception at this size. |
| C411 | **Paths.** The harness reads only the folder it is given, or `eval/results/` beside it. It refuses any path with a part named `sealed`, in any case, before anything is read or listed, as MS3a's C66 does. It reads no environment variable, so it never defaults to `LUSOT_DATA_DIR`. | CLAUDE.md and C39 keep sealed data untouched, and the deny rules don't guard code. The committed export never sits in a folder named `sealed`, so the rule costs the sealed run nothing. |
| C412 | **The sealed-run entry point,** `backend/analysis/probes/run_sealed.py`, built by `backend/analysis/`'s owner after MS3a and MS3b merge, not on this branch:<ul><li>It reads only inside a `sealed` folder, so it can't run on development data, just as C66's runner can't run on sealed data.</li><li>It starts only from an interactive console, after Rene types a confirmation, as MS2's sealing commands do (its C202). `isatty()` isn't enough: Window 2's MS2 review found that it passes on NUL, which is where an agent's shell sends stdin, so the check reads the console mode.</li><li>It refuses a tree with changes, or any commit but the freeze, or the second freeze for the rerun (C421).</li><li>It checks every label before any paid call (C420).</li><li>It pays for each photo once, resumes after a stop (C419), and gets the configurations from replays.</li><li>It reuses MS3b's export, which rebuilds `item_fields()` from the saved `asdict` outcome (MS3a plan, Task 9).</li><li>Raw outputs stay under `sealed`. The export goes outside it and holds only §4.3's fields.</li><li>It prints counts and timings only.</li></ul> | Each tool refuses the other's inputs, which squares C66 with a run that must read sealed data. The terminal check is a strong guard, not a proof: an agent could open a console. CLAUDE.md's rule that the sealed run waits for Rene stays the control. |
| C413 | **The freeze** as in §4.6: tag `freeze-1`, and `freeze-2` for the one disclosed rerun (C421). | Design §8 and rules §10. Freezing the harness too means the rules that scored the run are the rules judges rebuild with. |
| C414 | **Marks made before the run.** `quality` (`dark` or `blurry`) defines the quality subset for correct refusals, and `subsets` carries MS2's tags `reflection`, `splash` and `moving` (W4, W8, W1). Both are marked by eye on the M8 sheet before the run, never from Lusot's output. W6's subset is computed from the labels, and A-neg's `surface` splits W9. | Table 13 names a quality subset but not who marks it, and MS3b's C315 reports subsets for W4, W6 and W8. Marking before the run keeps a subset from following the results. |
| C415 | **M8 labels by box id.** The export matches each M8 point to the numbered box of its kind that holds it (MS2's C208). Landmark agreement is exact, counted as §4.2 says: answered photos only, a skipped box a disagreement, an unmatched label apart. | Rules §7 compare Muse Spark's landmark with ours per reference, so both must name the same box. A photo whose answer failed says nothing about how Muse Spark reads landmarks. |
| C416 | **Latency** is optional input from live tests (MS5, MS7): the median and the nearest-rank 95th percentile, with n. Without it, the report says latency wasn't measured in this run. A row runs from the upload, or a sample's start, to the final result, under an id of its own (MS5's C631). Nothing exports it: the window that ran the checks commits the rows before the freeze (§4.7), and rows measured later arrive with a `--write` in the same commit, since latency can't change a depth output (rules §10). The report's label follows rules §7, which says "upload to pin" until v0.7's item 7.8. | Table 13 takes latency from live tests, not from the sealed run. The live checks use samples and private uploads, which never pin (MS5's C630), so "upload to pin" can't be measured on them. |
| C417 | **The test path.** A PEP 723 runner, `eval/tests/run_tests.py`, pins pytest and scikit-learn and is locked with `uv lock --script`. It runs as `uv run --locked --script eval/tests/run_tests.py`, which uv 0.13.6 accepts (checked on Oct 28). After the merge, the merging window adds it to `npm run check` and CI. | It follows the locked scripts in `backend/scripts/` and CLAUDE.md's "pin versions in lockfiles", without a new project or any change to `backend/analysis/`. |
| C418 | **Geometry dropped before the freeze** (by MS3b's C313, or because it isn't ready). `run.json` records `dropped` with the reason, rows carry only `landmark`, and the report shows one configuration and says why. There is no ablation and no inches, and the sealed run can't bring geometry back. | Rules §8 chooses between two configurations named in advance. With one left, there is nothing to choose, and reviving geometry after seeing sealed results would be choosing after the run. |
| C419 | **A run that stops partway** (a rejected key, a crash or a lost connection) resumes as the same run. Photos with saved outputs are never sent again; the rest run when Rene restarts it. `run.json` records each stop and its cause, and only a completed run is exported. A resume isn't the disclosed rerun. | Pay once per photo. Spending §10's one rerun on an outage would leave none for a real fix. Whether a photo that failed because Meta's service failed may be retried is MS6E-Q6. |
| C420 | **Labels hold only rules §2's words.** `--label-words` lists the words §2's labels use (the phrases' words, `deep`, `level`, the units, `to`, the statuses and the passability words and codes), plus `ankle` and `head`, which real alerts write beside inches (MS6E-Q1, items 15 and 16). Between its words a label may hold spaces, the marks `- – , ( ) " ' ” “ ″ / + .`, and numbers of up to 3 digits with up to 2 decimals, optionally glued to `in` or `cm`. The final review found that the code allows a `.` anywhere, so `Knee deep.` passes and maps. Numbers can still take the shape of a date or a time (`10/28`, `8.00`). Those map to nothing, so the photo is excluded, and they can hold no place name. The export doesn't import the harness (C321), so it mirrors this mark set, which `scoring.labels` holds. The export writes the marker `(other words)` for any label with another word. The entry point checks every sealed label the same way before any paid call. | A label maps by its words or, when they aren't a phrase, by its inches (item 15). A label with a word outside the list loses its inches to the marker and stays unmapped, which is the cautious reading. It keeps spot names and times out of the committed labels, and the list stays in one place. |
| C421 | **The disclosed rerun's place.** Rules §10's one rerun writes to `eval/results/rerun/`, beside the first run, at a second freeze, tagged `freeze-2` and recorded with its reason. The one command rebuilds both reports. The rerun's report gives the first run's headline and gate rows beside its own, and the rerun's decision is the one applied. | Rules §10 requires both sets of numbers and the reason. Keeping the first run's folder untouched shows it as it was committed. |
| C422 | **Synthetic fixtures say so.** `run.json` may carry `synthetic: true`, used only by test fixtures. Their reports open by saying they hold synthetic test data, not Lusot's results, so a committed fixture can't pass for a run. | The harness's own fixture is committed with its report, where a judge browsing the repo could read made-up rates as results. |
| C423 | **Two of MS2's format differences** (Window 2, 3:50 PM). **Marks nobody made stay null:** `quality` may be null, which means unmarked, and an unmarked photo is never in the quality subset. A-neg rows always carry null (MS2 has no M8 for A-neg, its C208), and so does a Set A photo without an M8 photo row. **Set B's bins stay a free map of tokens:** the export passes MS2's `view` and `size_bin` under those names, and any bin MS3b derives under its own name. The report groups by each name it finds. | Filling `ok` would claim a mark that nobody made. The harness only groups by bins, so their names are the producers' to choose. |
| C424 | **The baseline row** (Rene's underfitting guard 1).<ul><li>**What it is:** "always the most common level" is the most common mapped level among the development Set A photos that are scored and labelled, and "always the most common passability class" is the most common stated class. A tie goes to the deeper level, or the stricter class.</li><li>**Where it comes from:** a sealed run reads both from `run.json`, where they are required, frozen from the last development report. A development run without them computes them from its own rows, and says so. The last development run before the freeze leaves the pair out of its `run.json`. Its report then computes the pair from its rows, and that computed pair is what the freeze copies. A stale pair can't be frozen.</li><li>**How it's scored:** on each configuration's own answered rows, for exact agreement (shown, not compared), within-one agreement and underestimation, passability agreement, and the NPLV and NPATV photos caught. A photo counts as caught when its stated class is NPLV or NPATV and the class given is either of those.</li><li>**The per-level table** shows percentages only for levels with 5 or more photos.</li></ul> | Rene asked for guards against underfitting. A rule that can't beat "always the commonest answer" on within-one agreement and underestimation reads depth no better than a constant. Freezing the baseline into `run.json` lets judges rebuild it without development rows. The tie rules make the baseline harder to beat on underestimation, not easier. |
| C425 | **Event replay results** (Rene's validation step). On development runs only, a row's `outcomes` may carry `<configuration>_replay`: that configuration's result with C310's settings chosen on the other flood events, written by MS3b's export (its C321). The report shows each replay beside its in-sample configuration, and gives the difference in photos within one level, which MS3b's guard 3 reads (a fall of 3 or more photos sends the cutoffs back to their start values). A sealed run carries no replay results. Every row of a results file carries the same replay results, or the file is refused, so a replay is always compared over the same photos. | Validation by replay uses every development photo, needs no extra Meta call and cancels a split's luck. The harness reports the numbers; MS3b applies its own guard. |
| C426 | **Rene's review sheet.** A development run's `--write` also writes `report/review.csv`, one row per development Set A and A-neg photo:<ul><li>the set, the id and the event, and any exclusion reason</li><li>the alert's mapped level and class</li><li>each configuration's result, class and landmark</li><li>the M8 agreement count, and a compact list of each reference's two landmarks</li><li>a blank `claude_check` column, which Claude fills first, then blank `rene_verdict` (`right`, `wrong` or `unsure`) and `rene_note` columns, in that order (Rene's rule, Oct 29: Claude annotates first, then he reviews)</li></ul>It is written only when no `review.csv` exists, so Rene's notes are never overwritten, and the rebuild check skips it. A sealed run writes none. | It is the last 10% of Rene's review loop: his verdict and insight on every development photo, which Claude then checks against the photo, its overlay and the saved outputs. A worksheet he fills in can't be part of the byte-for-byte check. |

## 6. Done when

| # | Check | Evidence | Proved |
|---|---|---|---|
| E1 | Every rules §7 metric is right | Unit tests on synthetic rows, against hand-computed values with each n, covering the four kinds of result, floors, "no flood seen", alerts with only a class or no class, other alerts that conflict or don't map, the false flood rate's and correct refusals' denominators, landmark agreement's counting, the baseline rows and their ties, the per-level table's under-5 rule, and the replay comparison | on synthetic data |
| E2 | Kappa matches scikit-learn | `cohen_kappa_score(..., weights="quadratic", labels=range(9))` agrees to 1e-9 on seeded random synthetic sets, with "no flood seen" as `below_gutter`. Where scikit-learn returns NaN, the harness says undefined. A test shows scikit-learn dropping a value outside `labels`. | on synthetic data |
| E3 | The gate and the outcome rule follow rules §8 | A fixture for each branch: geometry stays, with and without inches; geometry dropped by a rise or by either guard; each boundary (10 and 5 points, 3.00 in, 70%, 80%) on both sides; an undefined rate; Set B missing; geometry dropped before the freeze; the self-check row never chosen | on synthetic data |
| E4 | Labels map as rules §2 says | Every label and variant written in §2 maps as written; inches, ranges and centimetres; words beat numbers; statuses, unknown words and the marker are handled; the drift tests (C408) pass | on synthetic data |
| E5 | Exclusions follow rules §9 | Each reason is logged with its photo, and changing any result leaves every exclusion unchanged | on synthetic data |
| E6 | The one command keeps its promises | An AST check finds only standard-library imports and Python 3.9 grammar. Run with `-I`, with only `SYSTEMROOT` in its environment and from another folder, it rebuilds a fixture's report byte for byte (exit 0). With sockets blocked it still runs, and a changed row gives exit 1. Output is ASCII. | on synthetic data |
| E7 | Sealed paths are refused | Path variants (`sealed`, `Sealed`, `sealed\sub\..`) exit 2 before anything is read, and none is created | on synthetic data |
| E8 | Private fields can't load, and real ones do | A row with a `reason`, a post link, a spot name, a time such as `8:00 AM`, an unknown field or free text in `answer` is refused. A level result's class in capitals, and rules §2's longest phrase ("not passable to motorcycles and cars (sedan)"), load. | on synthetic data |
| E9 | The report says what it may | Every metric row has its n; the report says "indicative" and "agreement", shows both configurations and the self-check line, and has the exclusions log and the footer's two lines; "safe" appears in no case, and neither do the verdict words "overfit" and "underfit"; every SVG parses, with a title and a description | on synthetic data |
| E10 | The literal command runs on plain Pythons | `python` and `python3` on the laptop (3.10 and 3.11) and uv's CPython 3.9 with no packages each rebuild every fixture with exit 0 | on synthetic data |
| E11 | Rene's review sheet is right and never overwritten | A development run's `--write` writes `review.csv` with a row for every development Set A and A-neg photo, and blank verdict and note columns. A second `--write` leaves an existing sheet untouched, the rebuild check ignores it, and a sealed run writes none. | on synthetic data |
| S1 | The run's preconditions hold | §4.5 steps 1 to 4 are recorded, with the tag `freeze-1` | at the sealed run |
| S2 | One sealed run, by Rene | `run_sealed.py`'s printed counts and the stops in `run.json`; nothing under `sealed` opened by Claude | at the sealed run |
| S3 | The export is committed, and clean | `eval/results/` loads under the allow-list, and a scan finds no photo, mask, link or 12-digit run | at the sealed run |
| S4 | The one command rebuilds it | On a clean clone, `python eval/run_eval.py --from-saved` exits 0 | at the sealed run |
| S5 | The decision is applied | `geometry_in_level` matches the outcome rule; `INCHES_SHOWN` reads `"true"` only if inches pass; otherwise the report says why | at the sealed run |
| S6 | Design §8's finish line | The committed report gives every sample size and the self-check decision, and the one command rebuilds it | at the sealed run |

## 7. Left to the builder

- The module split inside `eval/scoring/`, and file names there.
- The fixture scenarios and their names.
- Chart geometry within C410, and the Markdown layout within §4.4's order.
- Test cases beyond §6.

## 8. Questions for Rene

Each has a default that the draft plan follows (D7). They are listed most important first. The numbers stay as first issued, because MS2's draft cites them.

| # | Question | Options | Default (recommended) | Needed by |
|---|---|---|---|---|
| MS6E-Q5 | **What "no rise in Set A underestimation" compares.** The two configurations answer different photos: geometry can refuse some and answer vans. So a rate, a count and a per-photo comparison can give different verdicts. This decides the gate and geometry's development default (C309). | (a) The rate, each configuration over its own answered photos, as rules §7 defines it. (b) The number of underestimated photos. (c) Photos answered in both: none moves below MMDA's level. (d) Neither the rate nor the number rises. | (d). It passes only when both readings agree, so it holds whichever reading a judge takes, and refusals stay with the coverage guard. | your approval of `eval/rules.md` |
| MS6E-Q1 | **Readings to add to `eval/rules.md` before you approve it.** The harness implements each first option now (C404 to C407, C415):<ol><li>"No flood seen" in agreement and kappa: (a) one step below `below_gutter`, so never exact, within one level only of `below_gutter`, and `below_gutter` in kappa; (b) left out of agreement and kappa, and counted only in under- and overestimation and passability.</li><li>A passability phrase that maps to no class, beside a depth that maps: (a) leaves the photo out of passability only, logged; (b) excludes the photo as "unmapped label".</li><li>The gate's Set B figures: (a) the shipped configuration's only, SAM's waterline with the frozen k; (b) both with and without k.</li><li>Envelope coverage: (a) over measured wheels; (b) over every wheel, an unmeasured one counting as outside.</li><li>A rate with nothing to count: (a) fails its guard; (b) is skipped.</li><li>A-neg exclusions: (a) duplicates and files that can't be decoded only; (b) none.</li><li>A status that isn't a depth ("subsided"): (a) "no matching alert" as the main label, and ignored among the others; (b) "unmapped label".</li><li>An unmapped label among the other alerts: (a) excludes the photo as "unmapped label"; (b) is ignored.</li><li>The false flood rate's n: (a) every scored A-neg photo, with failures counted in n but never as false floods; (b) failures left out of n.</li><li>Landmark agreement: (a) photos with no answer left out, and a skipped box in an answered photo a disagreement; (b) every labelled reference counted.</li><li>A label that is a bare number with no unit ("25"): (a) unmapped, since §2's examples all carry a unit; (b) read as inches.</li><li>`level` after a phrase that §2 writes with `deep` ("half tire level", a real Valenzuela alert): (a) a variant of `deep`, since §2 lists "above gutter deep" as a variant of "above gutter level"; (b) unmapped, as only the exact phrases §2 writes count.</li><li>One depth in two units (`24 in (61 cm)`, as Pasig writes them): (a) it maps when both units give the same level, and is unmapped otherwise; (b) always unmapped, since it is neither a single number nor a range.</li><li>A blank depth beside a passability phrase that maps to no class, so the alert gives no usable label: (a) excluded as "unmapped label", as two blank labels are; (b) kept, and counted toward coverage only.</li><li>Words that aren't one of §2's phrases, beside inches: Quezon City's road-status pages write "ANKLE DEEP (9 inches)", and Manila's DRRMO writes "Ankle Deep" with no inches. (a) The inches decide, so 9 in reads `half_knee`, and the words alone stay unmapped. A bare number or a status among the words still keeps the label unmapped. Under (a), level words that aren't a whole phrase also follow the inches: "above chest (45 in)" reads `chest`, and "knee deep (19 in) / waist deep (19 in)" reads `knee`. (b) Excluded as "unmapped label", because the words don't map. (c) As (a), and the export also keeps the measures of a label whose other words become the marker, which needs MS3b's export to change.</li><li>"Head+" (Quezon City's "Head+ (60+ inches)"): (a) `above_chest`, like "lagpas tao", with `60+` (or `60 in+`) read as "at least 60 in", which maps only above 45 in. A `+` anywhere else ("Waist+") also marks a floor, which leaves the label unmapped. (b) Unmapped.</li><li>An unmapped depth beside a class that maps, such as `(other words)` with `NPLV`. This is the commonest route to "unmapped label", because the export writes the marker. (a) The photo is excluded as "unmapped label", as rules §2 reads literally, though an unmapped class beside a mapped depth keeps the photo (item 2). (b) The photo is kept for passability only, and left out of the level metrics.</li></ol> | (a) for all seventeen, or change any item. | (a) throughout | your approval of `eval/rules.md`, before the first Set A result |
| MS6E-Q6 | **A photo whose analysis failed because Meta's service failed** during the sealed run (an HTTP error after the client's retries, or a timeout). | (a) Retry it once before the export, and disclose how many were retried: run.json's `service_retries` holds the count, and the report states it. A photo whose answer was invalid is never retried. (b) Never retry it: it stays a processing failure in coverage. | (a). An outage says nothing about how Lusot reads a photo, while an invalid answer does. | the entry point's build (by Nov 2) |
| MS6E-Q3 | **The decrypted sealed copy** (MS2's C205 and C206 cover the archives and the password). | (a) Extract into `lusot-data\sealed\run-1\`, and delete the decrypted photos once you've checked the export. The archives and the raw outputs stay under `sealed`. (b) Keep the decrypted photos until judging ends. | (a) | the sealed run (Nov 3) |
| MS6E-Q4 | **The one command's form.** | (a) `python eval/run_eval.py --from-saved`, standard library only, as rules §10 and design §8 say. (b) `uv run ...`, which needs uv and changes both documents. | (a) | the freeze |
| MS6E-Q2 | **How M8 labels name Lusot's boxes.** Settled by MS2's draft C208: a point per reference, matched to the numbered box of its kind. | You approve it with MS2's spec. | (none needed here) | |

Already open elsewhere, and needed before the sealed run: M18 (the gate's numbers, by Nov 2), M19 (the archive, Oct 30), M8 (the labels, Oct 28 to 30), MS3b-Q1 (answered: Set B accepts fewer cars, the fallback, Rene, Oct 29), MS3b-Q4 (freezing the reasoning effort), and MS2-Q1 and MS2-Q2 (the archive password, and MS2's additions to `eval/rules.md`).
