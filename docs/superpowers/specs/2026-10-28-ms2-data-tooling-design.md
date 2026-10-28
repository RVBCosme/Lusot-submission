# MS2 Data tooling: spec

- **Date:** Oct 28, 2026 (Manila)
- **Status:** Draft, written before Rene's approval and without a live conversation (D7, D15). Revised after an accuracy review, Window 4's alignment note, a builder check and the tracker's verified updates (section B, under Rene's delegation). Claude proceeds on the calls in §6 and the defaults in §11 until Rene approves. **One rule bends:** Rene-only commands may read inside `sealed` folders (C202), because C39 puts the final cars there. Amended at 4:13 PM for Rene's 80-10-10 instruction (about 3:35 PM), from the tracker's verified note. It adds C204's stratified walk and MS2-Q4. No validation part is drawn: validation is event replay in MS3b and MS6.
- **Implements:**
  - plan §11 (Table 12, and the inputs Table 13's metrics need), Table 25, §20 Phase 2 (Table 22) and §20's repo layout (`eval/set_b/`)
  - plan Table 11's W18, and Table 27's M7 to M11, M13 and M19
  - build design §8 (MS2 row), §12, G3 and G5
  - `eval/rules.md` v0.6 §2 to §5, §9 and §10
- **Read at:** `main` `98e8266` (MS1 closed), `ms3a-landmark-core` `66c2f77` (the MS3a and MS3b specs, the MS3b plan draft, and the log and board, which Window 3 now owns), `next-specs` `28b3530`, and `w4-independent` `b254a81` (the MS6 spec and plan, from `a69b7d9`, `e0a133c` and `51004e1`).
- **Feeds:** MS3b's tuning and Set B scoring (its C310, C313 to C315), and MS6's harness and sealed run. The MS6 calls cited here (C403, C404, C407, C412, C414, C415, C420) are in Window 4's draft spec, not yet approved.

## 1. Intent

Rene collects and labels the data by hand. MS2 builds the tools that check it, group it into flood events, split it, generate Set B and seal everything final, so that no agent ever sees what will be sealed. The sealed run is part of Lusot's pitch, and it counts only if a judge can trust three things: no flood event sits on both sides, nothing was tuned on sealed data, and Set B's truth doesn't share the method's own assumption (G3). Every dataset version ends up in a committed record.

## 2. Goals, non-goals, anti-goals

**Goals**
- Set A (about 50) and A-neg (about 15) checked and split by event, with the W18 audit passing.
- Rene's M8 labels for every Set A reference, made in a sheet that never shows the MMDA columns.
- The Set B generator with G3's truth: development crops for MS3b, then the final cars sealed by one unattended run.
- Set C within its licences.
- One documented format for every file that MS3b and MS6 read.

**Non-goals**
- Metrics, the gate, the report and the sealed run itself (MS6). Geometry and its tuning (MS3b).
- Searching a social platform, or opening a post link.
- Publishing any data set.

**Anti-goals** (failures even if the tools work)
- An agent sees a sealed row's labels, link or photo, or any row's labels or link before the split.
- One flood event, or one photo, ends up on both sides.
- Sealed crops, truth or rows written in plaintext; or plaintext sealed inputs kept once their archive has been tested.
- A password typed into Claude's shell, stored in a file or passed as an argument.
- Set B's truth taken from the rim (G3), or the generator changed after seeing geometry's errors.
- A FloodDET image sent to Meta before its source's licence is checked (F2).

## 3. Constraints

- CLAUDE.md's "Evaluation integrity" and "Data collection" rules hold as written. Before the split, no agent views a Set A or A-neg photo or log. Only the intake reads the logs, and it prints ids and counts (C201). After the split, development data is open.
- Everything sealed lives under a folder named `sealed` (C39), which the deny rules cover. Only Rene holds the archive password, so only Rene runs the commands that touch sealed storage (C202).
- **Boundaries set by MS3b and MS6:** `eval/` never imports `lusot_analysis` (MS3b's C321, MS6's C400), and MS6's harness holds the only label mapping and scoring code (its C404, C420). Files are the interface.
- **Meta:** only `set_b_masks` calls Meta. It makes 3 SAM calls per car photo, plus one `floodwater` call per development crop for the freeze check (C213). Every photo is face-blurred first (C20, C37), on the credits (D10). Under $0.25 in all.
- **Other windows:** nothing in `backend/`, `.claude/settings.json` or `eval/rules.md` changes until MS3a merges or Rene agrees (MS2-Q2, MS2-Q3). The log and the board change only through their owner, Window 3 since MS1 closed (D20).
- **Time:** MS2 closes in two parts: the split and the development data by Oct 30 (M19, MS3b-Q2), then Set B's final cars and the freeze record by Nov 1, past design §8's MS2 dates (Oct 27 to 30). Set B sits on MS3b's critical path: `set_b_masks` (MS2-Q3), `generate`, the freeze, MS3b's D2, then the final-car run.
- **Risks:**
  - Rene's manual work (M7 to M11, M19) all lands on Oct 29 and 30. If Set A is short, Table 18's fallback applies: add Quezon City's lists, then report the smaller sample. If the split slips, MS3b-Q2's default applies.
  - SAM may not see the composited water. MS3b's known-waterline variants then still measure the geometry (its C314).
  - A lost password loses the sealed sets, so each archive is tested before anything is deleted (MS2-Q1).
  - Grouping events from free-text spots can over-merge and make the split lumpy. C204 caps the sealed share, and the record gives each side's counts.
  - G3's scale divides the loaded tire's height by its nominal diameter. A loaded tire stands a little shorter, so the truth runs a few percent deep, which `eval/rules.md` §5 accepts. MS3b's results note should say so.

## 4. Decided already

| What | Decided in |
|---|---|
| Set sizes and uses: A about 50 (about 30 development, 20 sealed); A-neg about 15 (10 and 5); B about 40 crops from about 10 car photos, split by car; C for development only; D final only, reported apart from B | plan Table 12 |
| Set A splits by flood event (same place, same day), and a split audit script verifies it | plan §11, Table 11 (W18) |
| Set A takes government-posted photos only. News lists only help find posts. | plan §11, Table 25, M7; D2 |
| Rene collects by hand. Claude's scripts check the log, match each photo to its alert (same spot, within 30 minutes) and group events. **Changed:** Claude builds the split, but Rene runs it, because only he holds the password (the brief, M19). Design §12 implied Claude would. | D2, design §12 |
| No agent opens a Set A or A-neg photo before the split. After it, development photos, masks and overlays are open. | design §12 (B3), CLAUDE.md |
| The split draws events with a recorded seed and writes the sealed rows straight into the encrypted archive. Agents only ever see development rows. | design §12, `eval/rules.md` §4, M19 |
| M8: Rene labels each reference's landmark and vehicle type before Lusot runs, with the MMDA columns hidden | plan M8, design §12 (B3) |
| Set B's final cars are sealed like Set A. The generator is built on development cars, then runs once, unattended, on the final cars, writing into the archive. | design §12 (B4), `eval/rules.md` §4 |
| G3: truth scale from the whole tire, never the rim. The rim-edge ratio comes from development cars only, and errors are reported with and without it. | design §9, `eval/rules.md` §5 |
| Matching, label mapping and exclusions, including a label still visible in the photo | `eval/rules.md` §2, §3 and §9; C15 |
| Sealed folder names, the archive path and the deny rules; raw Set A and A-neg photos denied until the split; private data under `LUSOT_DATA_DIR` | C39, C6, R8, C8 |
| Set C: STURM-FloodDepth (CC BY 4.0) is in use. FloodDET waits for a check of each source's licence. | C12, F2 |
| A path with any part named `sealed`, in any case, is refused before anything opens | MS3a's C66 (`refuse_sealed`) |
| MS6 maps labels and applies §9 from MS2's facts. Its export keeps only its §4.3 fields, with opaque ids and labels of §2's words only. Marks are made before the run, and the sealed entry point checks every label before any paid call. | MS6's C403, C404, C414, C420 (Window 4's draft, uncommitted) |
| Settled by the tracker's verified updates (section B, Rene's delegation): M8's in-between convention (B.4, C208); C210's car numbering (B.7); `eval/rules.md` changes go into Window 4's single v0.7 proposal (B.8) | the tracker's update to Window 2, Oct 28, about 3:30 PM |
| Open elsewhere, not re-asked here: R6 (consented photos and fallbacks; default: labelled fallbacks), MS3b-Q1 (at least 3 parked cars by Oct 30), MS3b-Q2 (the split by Oct 30), MS3b-Q5 (prompt v1's two rules beyond Table 5; Rene answered on Oct 28 at 11:09 PM, keeping both: the higher mark for people and car bodies too, and the street clause), MS6E-Q3 (the decrypted copy; default `lusot-data\sealed\run-1\`) | design §7, MS3b's questions (Q5 in the Oct 28 log), MS6 spec §8 |

## 5. What gets built

### 5.1 Folders under `LUSOT_DATA_DIR`

| Path | Holds | Written by | Agents may read |
|---|---|---|---|
| `set_a\raw\` | Set A photos `A001.jpg`… | Rene (M7) | Never (R8). Deleted after the split. |
| `set_a\set_a_log.csv`, `set_a\m8_labels.csv` | Rene's log and his M8 export | Rene | Only through `intake`. Deleted after the split. |
| `set_a\m8_sheet.html` | the M8 page: ids and file names only | `m8_sheet` | As text only, never in a browser |
| `set_a\dev\` | `manifest.csv`, `m8.csv`, `photos\` | `split` | Yes |
| `a_neg\raw\`, `a_neg\a_neg_log.csv`, `a_neg\dev\` | the same for A-neg (`N001.jpg`…, no M8) | Rene; `split` | As for Set A |
| `set_b\dev\` | `cars.csv`, `photos\B01-1.jpg`…, `masks\`, `generated\` | Rene; `set_b_masks`; `generate` | Yes |
| `set_b\sealed\` | the final cars' `cars.csv`, `photos\` and `masks\`, until their archive is tested | Rene; `set_b_masks --final` | Never |
| `set_c\sturm_flooddepth\`, `set_c\flooddet\` | the downloads and their `manifest.csv` | MS1; `setc` | Yes |
| `set_d\sealed\` | Set D photos and `set_d_log.csv`, until their archive is tested | Rene (M13) | Never |
| `sidewalls\`, `consented\` | M11's photos and M9's items, each folder with its log | Rene | Yes |
| `sealed\` | the archives (C205), and at the sealed run the extracted copy, `run-1\` (MS6E-Q3) | `split`; `generate --final`; `seal_set_d`; Rene | Never |

### 5.2 Rules every tool follows

- **Explicit paths:** every path comes from the command line. No tool defaults to `LUSOT_DATA_DIR`.
- **Sealed paths:** every input path is refused when any segment is named `sealed`, in any case, before anything is opened (C222), except in Rene-only commands.
- **Rene-only commands** are `split`, `set_b_masks --final`, `generate --final`, `seal_set_d` and `audit --sealed` (C202).
  - **Console check:** each starts only from an interactive console. On Windows, `GetConsoleMode` must succeed on both the stdin and the stdout handle; elsewhere, both must be terminals. Claude's tools run commands with stdin on NUL and stdout piped, which fails both checks.
  - **Confirmation:** each then asks Rene to type a confirmation. A password prompt counts as one.
  - **Sealed paths:** these commands may take paths inside a `sealed` folder, but only names given on their command line or in a log they were given.
- **No listing:** no tool lists, walks or searches a folder, except `setc`'s walk of a Set C download, which skips any folder named `sealed`. Every other file is opened by a name from a log or a file list.
- **Before the split:** Claude's tools read only the logs' text fields, and check that each named photo exists without reading its bytes (C201).
- **Output:** ids, column names, fact values and counts. Never a cell's text, a photo, a location, a key or a password.
- **Ids** are opaque, in MS6's pattern (C221).
- **Post links:** `post_url` is never fetched, opened, resolved, parsed or validated. The intake checks only that it isn't empty.

### 5.3 Intake: `eval/data/intake.py` (Claude runs it, any time before the split)

- **Reads:** `set_a_log.csv` (the template's 17 columns, plus C209's optional ones when present), `a_neg_log.csv` and, when given, `m8_labels.csv`, `consented_log.csv` and `sidewalls.csv`. UTF-8, with or without a BOM.
- **Problems** (exit 1):
  - a missing required column
  - a bad id, an id that doesn't match `photo_file`, or a repeated id whose photo columns differ (a repeated id is an alert row, C223)
  - a consent record missing, or an M9 item whose `consent_version` Rene hasn't approved (C218)
  - a named file that doesn't exist
  - a date or time not in the guide's format, or a value outside its column's list (Table 5's lists, in M8)
  - a `same_spot_as` that names no row of the same set on the same date
  - in M8: a Set A photo without its photo row, or a point outside 0 to 1
- **Warnings** (listed by id; they never stop anything; C209):
  - **Facts:** a city outside Metro Manila becomes `metro_manila = no`, and a poster other than MMDA or a Metro Manila city becomes `poster_kind = other`. A separate-post photo that no logged alert fits becomes `match = none` (C223). Rules §9 then excludes each one, and its reason is logged.
  - **Typos:** Rene fixes his own transcription slips, never the post's words.
- **Labels:** MS2 checks none (C207).
- **Computes:** the match (C223, C224), the other text-only facts of §5.9, and the events (C203).
- **Prints:** counts; each problem as `<id> <column>: <kind>`; each warning as `<id> <fact>=<value>`; the number of events, the largest event's size and the number of one-photo events. It writes no file.

### 5.4 The M8 sheet: `eval/data/m8_sheet.py` (C208)

- **The page:** Claude runs the command, which writes `set_a\m8_sheet.html`. It is one self-contained page: inline CSS and a classic inline script, no network and no build step. It lists every Set A photo once, by id, with its photo from `raw\`.
- **What it reads:** only `candidate_id` and `photo_file`. The page holds no label, passability, link or spot text.
- **Labelling:** Rene opens it in his browser. For each photo he clicks each vehicle, wheel and person he can read and picks its values, then sets the photo's marks. A photo with nothing readable gets its photo row only. The page keeps his work in the browser, and can export and re-import it.
- **In-between waterlines:** the page states one convention for wheels, people and car bodies alike, the same one the prompt gives Muse Spark and `eval/rules.md` §6 follows (C208).
- **Export:** `m8_labels.csv` (§5.9), which Rene moves to `set_a\`. The split requires a photo row for every Set A photo (C204).
- **Agents never open the page in a browser,** because it shows the photos. Its script is tested on synthetic images (V1).

### 5.5 The split, the archive and the audit

**`eval/data/split.py`** runs once, a Rene-only command (M19), after `intake` reports no problems and M8 is complete:
1. Repeats the intake's checks and stops on any problem. Warnings don't stop it.
2. **Reads each photo by name,** and records:
   - its SHA-256 and a 64-bit difference hash
   - `decodes`: whether OpenCV decodes it, under the pipeline's 50 MP cap

   Identical files, or difference hashes within 6 bits, are one photo posted twice: a duplicate group. All of them join one event and carry the group's lowest id in `duplicate_of`, and every one but that lowest id gets `duplicate = yes`. A repost that was cropped or re-framed won't match, and the guide's skip-reposts rule covers those.
3. **Draws the split** (C204) and audits it. It stops if the audit fails, or if a set has fewer than 2 events, naming the set.
4. **Writes `lusot-sealed.7z` in one pass** (C205), after the password (C206). It writes from memory and from files named in the logs:
   - the sealed rows' `manifest.csv` and `m8.csv`, and their photos
   - Rene's whole logs and M8 export
   - the split record, without the archive's own hash
5. **Writes the development side:** `set_a\dev\` and `a_neg\dev\`, holding `manifest.csv`, `m8.csv` (Set A only) and copies of the development photos, with the copy check (C219).
6. Hashes the archive file's bytes, then writes the record to `eval/data/records/` (C216).
7. **Prints:** rows and events per side, counts per fact value, the audit result, and the archive's size and SHA-256.

It refuses to start if the archive or a `dev` folder already exists. A failed run is repeated after Rene deletes its partial outputs. The seed is a constant, so the same split comes out.

**After the split:**
1. Rene tests the archive in 7-Zip, then deletes the plaintext inputs (C219).
2. Claude runs `audit --dev` and commits the record.

**The audit (W18): `eval/data/audit.py`.** It uses the standard library only.
- **What it does:** it rebuilds the events from the manifests alone, by C203's rule. Then it checks that:
  - no rebuilt event, no `event_id`, no SHA-256 and no near-identical pair sits on both sides
  - each C204 group of 2 or more events has an event on each side (where it can see both sides: inside `split`, and in `--sealed`)
  - the counts, per group, match the record
- **Where it runs:**
  - inside `split`, before anything is written
  - `--dev` (Claude): the development manifest and the record, including the manifest's hash
  - `--sealed` (Rene-only, C220): at the sealed run, on the development manifests and the sealed copy extracted to `lusot-data\sealed\run-1\`. First it hashes each archive file against its record. MS6's procedure runs it before its entry point.
- **Output:** PASS or FAIL, with counts. Only development ids may print.

### 5.6 Set B

**Inputs (Rene, M10).**
- **Numbering:** cars are numbered `B01`, `B02`… in the order photographed. Odd numbers are development cars, in `set_b\dev\`; even numbers are final cars, in `set_b\sealed\` (C210).
- **How many:** at least 6 cars by Oct 30, which gives 3 development cars, and about 10 in all (Table 12).
- **Which cars:** types with Table 7 codes (sedan or hatchback, SUV or MPV, van), each with one tire code on both axles, and each with its owner's OK on record (C218).
- **Files:** each side has its `cars.csv` and `photos\B01-1.jpg`… (§5.9).

**Step 1. `set_b_masks`** is a new script in `backend/analysis/probes/` (C200; when it's built is MS2-Q3). For each photo named in `cars.csv`, it:
- runs `blur_for_meta`, which also shrinks the photo to the app's 1,600 px at most
- calls SAM for `vehicle`, `wheel` and `wheel rim`
- saves the blurred photo, the boxes, the scores and the masks under `masks\`, with a `files.txt` naming each file and its SHA-256

A photo already done is skipped, so a rerun pays nothing.

With `--water <truth.csv>`, it instead sends `floodwater` on each development crop named there, for the freeze check. It saves the results beside the masks, so MS3b's Set B script can reuse them. If MS3b can't, it pays about $0.05 again.

**Step 2. `eval/set_b/generate.py`** reads step 1's files and, for each car photo:
1. **Picks the wheels** (C212). A car is left out if its tire code has no aspect ratio (such as `195R14C`), or if it has no owner's OK on record (C218). Every drop is counted by cause.
2. **Truth** (G3, C212): the scale per wheel, the waterline rows and the rim-edge ratio.
3. **Crops** (C211): four per photo, one per depth band.
4. **Writes:** for development cars, `generated\crops\`, `truth.csv` (§5.9), `files.txt` and `overlays\` (the truth line and the chosen wheels drawn).

**With `--final`, it writes no plaintext at all.** It runs C214's overlap check first. Then it asks for the password and writes `lusot-sealed-set-b.7z` in one pass (C205): the crops and `truth.csv` from memory, plus `cars.csv`, the photos and the masks, read by name.

It prints counts and timings.

**The freeze (C213).**
1. Claude reviews the development overlays: the line sits on the truth row, and the masks hold the wheels.
2. `set_b_masks --water` runs on the development crops, and C213's criterion decides.
3. The generator's version is frozen before MS3b's first Set B score.

**The final-car run (C214):** after the freeze, by Nov 1, Rene runs `set_b_masks --final` (with `MODEL_API_KEY` set for that command), then `generate --final`. He then tests the archive in 7-Zip and empties `set_b\sealed\` (C219).

### 5.7 Set C (C215)

- **STURM-FloodDepth** (downloaded in MS1): `setc sturm` writes `manifest.csv`, with each file's path, its level (0 to 4, from its folder) and its SHA-256.
  - Users draw and record their own seeded subsets, as MS1's probe did.
  - It never backs a claim of agreement with MMDA (Table 25). Its photos are upscaled single-car crops, not street scenes (the Oct 28 log, C40).
- **FloodDET:**
  - **Licences first:** Claude checks the licence of each source its images come from (DEEPFLOOD, FloodIMG, Mapillary Vistas, MS COCO), on that source's own page, and records the result in `docs/research/`.
  - **Download:** only if some source's terms allow private development use and sending its images to Meta on the credits, where Meta may use them to improve its products.
  - **`meta_ok`:** its manifest marks this per image, by source. The default is `no`.
  - **If no source qualifies,** FloodDET is out of scope, and Muse Spark's person categories are checked on development Set A and consented photos instead.
- **Out of scope:** DeepFlood (only by asking its authors) and the FloodDepth-GPT photos (not released) (Table 25).

### 5.8 Set D, M9 and M11

- **Set D** (only if it rains, M13): Rene keeps the photos and `set_d_log.csv` in `set_d\sealed\` (C39). He then runs `seal_set_d`, which writes its archive and record in one pass (C217). He tests the archive in 7-Zip and empties the folder (C219). Its record extends the freeze record (C216).
- **Consented photos** (M9): `consented\consented_log.csv` (§5.9, C218) gives MS4's demo pins (G1) each item's place, time and source note, and records which version of the donor message each written OK answered. The intake accepts only the corrected version Rene approves (Window 4 is drafting it). They are never mixed into Set A (Table 18).
- **Sidewalls** (M11): Rene's photos go in `sidewalls\`, with `sidewalls.csv` (§5.9), which records each driver's permission. Claude reads each code from its photo and checks it against Rene's reading. MS3b's tire-code file (its C304) takes the confirmed codes with their source.

### 5.9 Formats

All files are UTF-8 CSV with a header row, and a blank cell means none. MS3b's plan draft reads JSON Lines; MS2's CSV stands, as that plan allows. The field names Window 4's contract uses match: `level_label_raw`, `passability_raw`, `other_alerts_raw`, `surface`, `quality`, `subsets` and the facts below.

**`manifest.csv`**, for Set A and A-neg. It is the ground-truth manifest, with the same columns on the development and sealed sides (C207).

| Column | Holds |
|---|---|
| `photo_id` | the log's `candidate_id` |
| `set`, `split` | `A` or `A-neg`; `dev` or `sealed` |
| `event_id`, `event_date` | `E01`… within the set, numbered by each event's lowest id; the Manila date of `post_time_pht` (A-neg: the capture time) |
| `city`, `metro_manila` | the normalised city, or the text as logged; `yes` only for the 16 cities and Pateros |
| `spot_key`, `same_spot_as` | the normalised spot text (C203); Rene's link |
| `poster_kind` | `mmda`, `city` (a Metro Manila city government, including its official offices, MS2-Q4) or `other` (anything else, and every A-neg row) |
| `match` | `same_post`, `separate_post` (within 30 minutes) or `none` (A-neg: blank) |
| `level_label_raw`, `passability_raw` | exactly as logged: the nearest fitting alert's (C223; A-neg: `none`, blank) |
| `other_alerts_raw` | the level labels of the other fitting alerts, separated by `;` (C223). MS6's export turns it into a list. |
| `label_in_image`, `reference_visible`, `faces_or_plates` | as logged |
| `surface` | A-neg: `wet` or `dry` |
| `duplicate`, `duplicate_of`, `decodes` | `yes` or `no`; the duplicate group's lowest id, or blank; `yes` or `no` (§5.5 step 2) |
| `photo_file`, `photo_sha256`, `photo_dhash`, `width`, `height` | the file in the side's `photos\`, and its facts |
| `notes` | Rene's notes |

MS6 maps the labels and applies §9 from these facts (its C404). Its committed export keeps only its §4.3 fields (its C403, C420), so cities, spots, notes, file names, hashes, sizes and times stay private.

**`m8.csv`** (Set A only; one row per labelled item; C208)

| Column | Holds |
|---|---|
| `photo_id`, `ref_id`, `kind` | the photo; `P1` for its photo row, `R1`, `R2`… for references; `photo`, `vehicle`, `wheel` or `person` |
| `x`, `y` | the clicked point as fractions of the photo's width and height, from the top left: a wheel's hub, a vehicle's body, a person's torso |
| `vehicle_type`, `body_waterline` | vehicles: Table 5's nine and six values |
| `waterline` | wheels: Table 5's seven values; people: its eight |
| `quality`, `subsets` | photo rows: `ok`, `dark` or `blurry`; zero or more of `reflection`, `splash` and `moving`, separated by `;` |

**Set B**
- **`cars.csv`** (Rene's): `car_id`, `photo_file`, `model`, `vehicle_type` (Table 5), `tire_code` (as on the sidewall), `view` (`side` or `angled`), `taken_on`, `consent_file`, `consent_version` (the owner's OK) and `notes`.
- **`truth.csv`:** one row per wheel per crop, keyed by `crop_id` and `wheel`.
  - **ids:** `crop_id` (`B01-1-2`: car, photo, then the crop's number in a seeded order, so the band doesn't show), `car_id`, `split`, `photo_file`, `crop_file`, and `wheel` (1 is the leftmost)
  - **the car and bins:** `view`, `vehicle_type`, `tire_code`, `rim_in`, `diameter_in`, `crop_scale` and `size_bin` (`full` or `small`)
  - **the wheel:** its box (`x0`, `y0`, `x1`, `y1`), `ground_row`, `top_row` and `px_per_in`
  - **the water:** `waterline_left_row`, `waterline_right_row` and `waterline_row` (at the wheel's centre)
  - **the truth:** `true_depth_in` (4 decimal places at most, as MS6's loader requires), `band`, `rim_edge_ratio` and `generator_version`

  Rows and pixels are the crop's own, after any shrink.

**The other logs**
- **Set D's `set_d_log.csv`:** `photo_id` (`D01`…), `photo_file`, `taken_pht`, `place_text`, `model`, `vehicle_type`, `tire_code`, `wheel` (`left` or `right` in the photo), `ruler_depth_in` and `notes`.
- **M9's `consented_log.csv`:** `item_id` (`S001`…), `file`, `kind` (`photo` or `clip`), `taken_pht`, `place_text`, `lat`, `lon`, `people`, `source_note`, `consent_file`, `consent_version` (the donor message the OK answered) and `notes`.
- **M11's `sidewalls.csv`:** `photo_file`, `vehicle` (`jeepney`, `tricycle`, `bus`, `hilux`, `tamaraw` or `other`), `model`, `tire_code` (Rene's reading), `checked_code` (Claude's reading), `taken_on`, `consent_file`, `consent_version` (the driver's permission) and `notes`.

**Archives** (7z with AES-256 and encrypted names; C205). They are laid out so that all of them extract into one folder without clashing:
- `lusot-sealed.7z`:
  - `records/split.json`
  - `set_a/`: `manifest.csv`, `m8.csv`, `photos/` and `source/` (Rene's whole log and M8 export)
  - `a_neg/`: `manifest.csv`, `photos/` and `source/`
- `lusot-sealed-set-b.7z`:
  - `records/set_b_final.json`
  - `set_b/`: `truth.csv`, `crops/` and `source/` (`cars.csv`, the photos and the masks)
- `lusot-sealed-set-d.7z`:
  - `records/set_d.json`
  - `set_d/`: `set_d_log.csv` and `photos/`

The development side uses the same names inside its folders (`set_a\dev\manifest.csv`; `set_b\dev\generated\truth.csv` and `crops\`), so one reader serves both sides.

**Records** (`eval/data/records/`, committed; C216). Each holds:
- the tool, its commit, the date and the seed
- the inputs' SHA-256
- counts per set and side, by fact value
- the audit result
- the archive's file name, size and SHA-256, and the development manifests' SHA-256

None holds a sealed row's id, a label, a link, a spot, a location or a photo.

### 5.10 Commands

Run from the repo root in PowerShell. `<data>` is the full data path, `C:\Systems\Lusot\lusot-data` (CLAUDE.md's default; `LUSOT_DATA_DIR` isn't set on this PC). No tool has a default path.

| Command | Run by | Prints |
|---|---|---|
| `uv run eval/data/intake.py --set-a-log <data>\set_a\set_a_log.csv --set-a-photos <data>\set_a\raw --a-neg-log <data>\a_neg\a_neg_log.csv --a-neg-photos <data>\a_neg\raw [--m8 <data>\set_a\m8_labels.csv]` | Claude | §5.3 |
| `uv run eval/data/m8_sheet.py --set-a-log <data>\set_a\set_a_log.csv --out <data>\set_a\m8_sheet.html` | Claude | the photo count |
| `uv run eval/data/split.py` with the intake's inputs plus `--set-a-dev <data>\set_a\dev --a-neg-dev <data>\a_neg\dev --archive <data>\sealed\lusot-sealed.7z --record eval\data\records\<date>-split.json` | Rene | §5.5 step 7 |
| `uv run eval/data/audit.py --dev <data>\set_a\dev\manifest.csv --record eval\data\records\<date>-split.json`, and the same for A-neg | Claude | PASS or FAIL, with counts |
| `uv run eval/data/audit.py --sealed <data>\sealed\run-1 --dev-root <data> --record eval\data\records\<date>-split.json --record eval\data\records\<date>-set-b-final.json` | Rene | the hash checks; PASS or FAIL, with counts |
| `uv run --locked --directory backend/analysis python probes/set_b_masks.py --cars <data>\set_b\dev\cars.csv --photos <data>\set_b\dev\photos --out <data>\set_b\dev\masks`, or `--water <data>\set_b\dev\generated\truth.csv`; `--final` with the `sealed` paths | Claude; Rene for `--final` | counts, SAM calls and seconds |
| `uv run eval/set_b/generate.py --cars <data>\set_b\dev\cars.csv --masks <data>\set_b\dev\masks --out <data>\set_b\dev\generated`; `--final` takes the `sealed` paths, `--dev-cars`, `--dev-masks`, `--archive <data>\sealed\lusot-sealed-set-b.7z` and `--record` | Claude; Rene for `--final` | counts by cause |
| `uv run eval/data/seal_set_d.py --log <data>\set_d\sealed\set_d_log.csv --archive <data>\sealed\lusot-sealed-set-d.7z --record eval\data\records\<date>-set-d.json` | Rene | counts, and the archive's size and SHA-256 |
| `uv run eval/data/setc.py sturm --root <data>\set_c\sturm_flooddepth --out <data>\set_c\sturm_flooddepth\manifest.csv` | Claude | files by level |

`set_b_masks` needs `MODEL_API_KEY`, set for that one command, as CLAUDE.md's probe command does. `audit --sealed` takes each archive's file name from its record, and the manifests' names are fixed, so it lists no folder.

## 6. New calls (Claude's)

Each call gives the decision and its reason; §5 holds the mechanics.

| # | Call | Why |
|---|---|---|
| C200 | **Where the tools live.** `eval/data/` and `eval/set_b/` hold uv scripts with inline dependencies and their own locks, like `backend/scripts/`, and neither imports `lusot_analysis`. The one step that needs the face blur and SAM, `set_b_masks`, is a new script in `backend/analysis/probes/` (MS2-Q3), which passes its results on as files. | Plan §20 puts the generator in `eval/set_b/`. MS3b's C321 and MS6's C400 keep `eval/` free of `lusot_analysis`, and the face blur must not be copied (C20, C37). |
| C201 | **Before the split, Claude's tools read only the logs' text fields** and print only ids, column names, fact values and counts. Photo bytes are read only inside Rene's split (§5.2, §5.3). | `eval/rules.md` §4 lets agents see development rows only, and until the split every row may end up sealed. A spot and a date, read beside Claude's own alert index, could give a label away. |
| C202 | **Rene-only commands** (§5.2's list) may read named paths inside a `sealed` folder. Each starts only from an interactive console (`GetConsoleMode` on stdin and stdout), after Rene types a confirmation, as MS6's sealed-run entry point does (its C412). | C39 puts the final cars in `set_b\sealed\`, and the sealed run's audit reads the extracted copy. Each tool refuses the other's inputs: Claude's tools refuse sealed paths, and these refuse a shell without a console. The console check is a strong guard, not a proof, since an agent could open a console. CLAUDE.md's rule that sealed data waits for Rene stays the control. |
| C203 | **Events.** Rows of one set join one event when they share a date and either the same normalised spot text or a street name, whatever their city. They also join when Rene links them in `same_spot_as`, or when the split finds their photos identical or near-identical. Event ids are opaque. In MS2-Q2. | Rules §4 counts one named spot, or spots within 300 m, as one place, but the log has no coordinates, and only the API Lambda may call Nominatim. Joining on a shared street across cities over-merges, and over-merging can't split an event across the two sides. Rene's link is a duty in the guide's update (§8): nearby spots with different names, and corners on a city boundary. |
| C204 | **The split.** It runs once, when M7 and M8 are complete (due Oct 30). Its seed, `20261030`, is a constant in the code.<ul><li>**Two groups:** the walk runs separately for deep events (any row whose passability is NPLV or NPATV by rules §2's table) and for the rest. Each group uses that seed and the same shares.</li><li>**The walk:** within a group, events sorted by id are shuffled with `random.Random(seed)`. Walking that order, an event goes to sealed only if the group's sealed side would then hold at most 45% of the group's rows (A-neg: 40%), and the walk ends once it holds 40% (A-neg: a third).</li><li>**Both sides:** a group of 2 or more events puts at least one on each side. If the cap would leave a side empty, the group's smallest event goes there, and the record says so.</li><li>**The record** gives each group's counts.</li></ul>Rows logged after the split are never used. A missing M8 photo row stops the split, unless Rene passes `--allow-missing-m8`, which the record counts. In MS2-Q2. | Table 12's 30 and 20, and 10 and 5, hold at any size, by whole events (W18), and the cap stops one big event from swinging the share. Set B stops at half tire (C211), so knee depth and deeper rest on Set A alone. Unstratified, with 5 deep events in 20, the sealed side gets at most one deep event about 31% of the time (Rene's 80-10-10 instruction, verified by the tracker). A seed fixed before any row exists can't be redrawn. A single split means a late row can't land on the other side of an event already sealed. |
| C205 | **No tool opens an archive once it's written.** Each sealing step writes its archive in one pass, straight from memory and from files named in its inputs, with encrypted names, then hashes the file's bytes. No tool decrypts, lists or adds to an archive; Rene tests each one in 7-Zip. How many archive files there are, one per sealing step or C39's single file, is MS2-Q2 (default: one per step). py7zr's exclusive-create mode and encrypted headers are to be confirmed at the locked version. | Adding to an archive means opening it, and so decrypting its index. The hash in the committed record lets the sealed run prove each archive is the one written at sealing. |
| C206 | **The password** (MS2-Q1's default) is typed twice into Rene's own console, read with `getpass`. It never comes from an argument, an environment variable or a file, and stays in memory only. One password serves every archive, kept in his password manager. | Claude never sees it, and an argument would show in process lists. |
| C207 | **The manifest keeps raw labels and §9's facts, in MS6's names.** MS2 computes only facts that need the log or the photo bytes. The harness maps the labels and decides every exclusion. Other alerts stay raw labels, not a conflict flag. **MS2 doesn't import MS6's `scoring.labels`, and checks no label.** | Only the harness holds the mapping, and a mapping Rene adds before the sealed run (rules §2) must still reach the archived rows. MS2's split is due Oct 30, and the harness reaches `main` only after its own build and merge, so an import could block the split, and a check that switches on later would be speculative. A mistyped label is excluded and logged, never guessed (rules §2). MS6's entry point checks every sealed label before any paid call (its C420), and MS2 commits no label at all. |
| C208 | **M8 per reference, with points.** For each vehicle, wheel and person Rene can read, the sheet records a clicked point and Table 5's values. Each photo also gets `quality` and `subsets`. A-neg gets no M8. MS6's export matches each point to the numbered box of its kind that holds it (MS6E-Q2's option (a), its C415). Where two boxes hold a point, the one whose centre is nearest is proposed. For a waterline between two marks, the page states one convention for wheels, people and car bodies: the higher mark, as prompt v1 says. Rene settled this in MS3b-Q5 (Oct 28, 11:09 PM): "between two marks, take the higher one" for all three, and a photo that shows no street is unusable. The page states it as the final rule (the tracker's B.4). | Design §12 asks for every reference, and only a position ties Rene's label to the box Muse Spark answered about. The marks give MS6's C414 its quality subset and the W1, W4 and W8 subsets, marked before any result. M8's labels are sealed at the split and can't be redone, so the page must ask what Muse Spark is asked, or landmark agreement is skewed. |
| C209 | **Log changes.**<ul><li>Set A's log gains three optional last columns: `same_spot_as`, and, on rows whose photo isn't in the alert's post, `alert_poster` and `alert_spot_text`. Same-post rows need nothing new, so rows logged on today's template still work.</li><li>On those rows, `alert_time_pht` holds the alert's time: the time its text gives, or else its post's time.</li><li>A photo that several alerts may fit gets one row per alert, with its photo columns repeated (C223).</li><li>Each row's `level_label_raw` holds only the alert's depth words, because the others reach MS6 as `other_alerts_raw`, read as level labels (its C404). The guide says so.</li><li>An unrecognised city or poster is a warning that becomes a fact (§5.3), never a stop.</li><li>A-neg uses Set A's columns, with ids `N001`…, `poster` `own` or `friend`, the capture time in `post_time_pht`, the level `none`, plus `surface`. A friend's OK covers sending the photo to Meta face-blurred (D10), for evaluation only, and never the repo or the demo (as C18).</li></ul> The alert-time rule is in MS2-Q2. | Rules §3's test needs each alert's time, poster and spot, and the template holds only the photo's. One row per alert keeps every alert checkable. Rules §9's "outside Metro Manila" and "not posted by MMDA or a city government" are logged only if such rows reach the manifest. |
| C210 | **Set B splits by car number:** odd numbers are development cars, even numbers final, in the order Rene photographs them. Settled (the tracker's B.7). | Table 12 splits by car. Settling it before any photo exists needs no tool, and Claude never sees a final car. |
| C211 | **Set B crops.**<ul><li>Four per car photo, one in each depth band below the hub: 1 to 5 in (below_gutter), 5 to 8 (gutter), 8 to 10 (half_knee), and 10 in to the lower of 13 in and 0.5 in below the hub (half_tire). Each depth is drawn evenly within its band.</li><li>Two of the four, drawn at random, are shrunk so the smaller chosen wheel is 50 to 80 px tall. The others stay at the app's 1,600 px.</li><li>Opaque muddy water fills everything below a straight waterline at the same true depth at both wheels, with ripples and a darkened mirror image of the scene above it.</li><li>Crops are made from the face-blurred photo, and one recorded seed drives every draw.</li></ul> In MS2-Q2. | Four crops from each of about 10 photos are Table 12's 40. Geometry measures only up to the hub (plan §8), so deeper water would only add designed refusals to the share measured. Plan §8 trusts geometry down to 40 px wheels, so Set B needs small ones (W7), sized on the smaller wheel so none drops under C56. The reflection tests W4. |
| C212 | **G3's truth, and the wheels used.**<ul><li>The scale is the dry `wheel` mask's height over the tire code's overall diameter (Table 7's formula).</li><li>The waterline row is the ground row minus depth times scale, and the truth comes from the row actually drawn.</li><li>`rim_edge_ratio` is the linked rim mask's height, in inches at that scale, over the code's rim size. MS3b's k comes from it (its C310).</li><li>Wheels used: at most the two largest whose centres lie in the largest vehicle box, clear of the frame's edges, at least 40 px on the longer side (C56), with height over width from 0.9 to 2.0.</li></ul> In MS2-Q2. | Design §9 and rules §5. A height doesn't shrink when a car is turned. 2.0 is plan §8's 0.5 axis ratio, and below 0.9 the mask has merged with something. A wheel cut by the frame hides its ground row. |
| C213 | **The freeze criterion, set before looking:**<ul><li>A development crop passes when SAM's `floodwater` mask covers at least a quarter of the drawn water's area.</li><li>The water's look passes when at least 3 in 4 crops pass.</li><li>At most 3 looks are allowed, each version and its share recorded. After the third, the generator freezes anyway, and MS3b's results note says so.</li></ul> The freeze comes before MS3b's first Set B score. Later changes get a new version and a reason, and none is ever made because of a geometry result. | Table 12 composites the water so SAM can segment it, and the gate's variant uses SAM's waterline (MS6's C407). A test fixed in advance, on mask presence only and never the edge's accuracy, with capped looks, keeps the truth from being tuned toward the method. |
| C214 | **The final-car run is two Rene-only commands:** `set_b_masks --final`, then `generate --final`. Before writing anything, `generate --final` stops if a final car shares an id, an identical photo or a near-identical photo with the development side. Crops and truth never exist in plaintext. Only Rene's photos and the masks sit in `set_b\sealed\` until the archive is tested (C219). In MS2-Q2. | Rules §4 and design §12 ask for one unattended script writing straight into the archive. The generator and the truth do (C205). The masks need a separate process, because `eval/` can't import `lusot_analysis` and `backend/analysis/` can't import `eval/`. A mask holds no depth or label, so it is no more sensitive than the photo beside it. |
| C215 | **Set C:** a STURM manifest; FloodDET only after each source's licence is checked, with `meta_ok` per image; DeepFlood and FloodDepth-GPT out of scope. | C12 and F2: only STURM is CC BY 4.0 throughout. Checking first avoids a download that couldn't be used. |
| C216 | **Committed records** in `eval/data/records/`: the split, Set B's final cars, Set D if it rains, and a freeze record at MS2's close. A later Set D record extends the freeze record. Records hold counts and hashes only. | "All sets frozen" becomes a file a judge can check, and MS6's `run.json` takes the dataset versions and seeds from it (rules §10). |
| C217 | **Set D** is sealed by `seal_set_d`, from `set_d\sealed\`, into its own archive. | Design §12 seals Set D like Set B's final cars. |
| C218 | **Consent records.**<ul><li>M9's log carries place, time, coordinates read off a map by hand, and design §12's source note. It also records which version of the donor message each written OK answered, and the intake accepts only the corrected version Rene approves.</li><li>Set B's `cars.csv` records each car owner's OK, and `sidewalls.csv` each driver's permission (M11), each with its text's version. A version Rene hasn't approved yet is a warning, so Set B isn't held up.</li><li>Window 4 is drafting all three texts. The approved versions are one constant in `eval/data/`, set when Rene approves them.</li></ul> | G1 places each demo pin at its photo's real spot, and only the API Lambda may call Nominatim. The rules require rights to everything submitted (C18), and the tracker's B.6 asks for these records. |
| C219 | **Rene deletes the plaintext inputs only after 7-Zip opens their archive:** the split's raw folders, logs, M8 export and sheet; `set_b\sealed\`'s contents; `set_d\sealed\`'s contents. No deny rule is loosened; the optional tightening for the pre-split logs stands (§8). **The copy check:** the split builds its copy list from development rows only. Before copying, it checks that no copy's SHA-256 or difference hash matches a sealed row's. After copying, it re-hashes each copy against the development manifest, and the record keeps the result. `audit --dev` repeats the re-hash. | An archive protects nothing while plaintext copies sit beside it, and deny rules don't bind scripts. The test first guards against a mistyped password. The copy check needs no sealed storage: the split hashes the raw photos before it seals anything (the tracker's B.2). |
| C220 | **The audit gets a Rene-only `--sealed` mode** for the sealed run (§5.5). | MS6's procedure runs it before its entry point (Window 4's point 6), and the entry point can't import `eval/` (MS3b's C321). |
| C221 | **Every id MS2 writes is opaque,** in MS6's pattern: 1 to 3 capitals, 1 to 4 digits, and at most two `-` suffixes of 1 to 3 digits. That covers `A001`, `N001`, `E01`, `B01`, `B01-1`, `B01-1-2`, `D01`, `S001`, and M8's `P1` and `R1`. | MS6's loader refuses any other id (its C403), and no date or spot fits the pattern. |
| C222 | **MS2's own sealed-path refusal.** One helper in `eval/data/` refuses any path with a segment named `sealed`, in any case and after `..` is resolved, before anything opens, and a test proves it. `set_b_masks`, in `backend/analysis/probes/`, uses the runner's `refuse_sealed` (MS3a's C66), as MS3b's scripts do. | `eval/` can't import `lusot_analysis` (MS3b's C321, MS6's C400), so it can't reuse C66's helper (the tracker's B.1). |
| C223 | **Tools match each photo to its alerts** (D2). An alert fits a photo when it is in the photo's own post, or when it was posted by MMDA or a Metro Manila city government, at the same spot (C224), within 30 minutes of the photo's post. The nearest fitting alert gives the labels and `match`. The other fitting alerts' level labels go to `other_alerts_raw`. With none, `match = none`. No tool opens a link. | D2 and design §12 give matching to Claude's scripts, and rules §3 sets the test. Rene's hand-picked match (the first draft's C209) departed from D2. |
| C224 | **"Same spot" compares normalised spot text** (C203's normalisation): the photo's and the alert's spots match when they share at least two names (a street and its cross street or landmark), or when each names one place and it is the same. | Rules §3 asks for the same street plus a cross street or landmark. A key Rene writes would hand the judgment back to him, against D2. A spot the text can't confirm is excluded as "no matching alert" and logged, never guessed, and the intake lists it so Rene can fix a transcription slip. |

## 7. Who does what

| Who | What | When |
|---|---|---|
| Rene (M7) | Collects Set A by hand into `set_a_log.csv` (C209): one row per alert a photo may match, with the alert's poster, spot and time on separate-post rows. Links nearby spots and city-boundary corners in `same_spot_as` (C203). Fixes what `intake` flags, and checks his own transcriptions against the posts before the split. | Oct 28 to 30 |
| Rene (A-neg) | About 15 wet and dry street photos, at 5 or more places over 2 or more days, so the split has events to draw from. A friend's photo needs C209's OK. | By Oct 30 |
| Rene (M8) | Labels every Set A photo in the sheet, under the in-between rule he settled in MS3b-Q5 (C208), and exports `m8_labels.csv`. | Before the split |
| Rene (T9, a new setup action) | Installs 7-Zip | Before the split |
| Rene (M19) | Chooses the password, runs `split`, tests the archive in 7-Zip, deletes the plaintext inputs (C219) and tells Claude | Oct 30, evening |
| Rene (M10) | Photographs the cars §5.6 asks for: parked, side-on, in daylight, plus an angled photo of some if there's time. Reads each tire code from the sidewall, and records each owner's OK (C218). | Oct 29 to 30. The plan's Oct 27 to 28 has passed. |
| Rene (final cars) | The final-car run (C214), the 7-Zip test, and emptying `set_b\sealed\` | After the freeze, by Nov 1 |
| Rene (M11) | Sidewall photos of a jeepney, a tricycle and a bus, plus a Hilux and a Tamaraw if possible (G5), logged in `sidewalls.csv` with each driver's permission (C218) | Oct 29 to 30. The plan's Oct 27 to 28 has passed. |
| Rene (M9, M13) | Consented items with their log (R6), each OK answering the donor message he approved (C218). Set D if it rains, then `seal_set_d`, the 7-Zip test and emptying `set_d\sealed\`. | Ongoing; if it rains |
| Rene (sealed run) | `audit --sealed`, as MS6's procedure orders | Nov 3 |
| Claude | <ul><li>builds and tests the tools</li><li>runs `intake`, `m8_sheet`, `set_b_masks` and `generate` on development cars, `audit --dev` and `setc`</li><li>reviews the development overlays, checks the sidewall codes and FloodDET's sources</li><li>commits the records, updates the guide, and passes log-ready lines to the board's owner</li></ul> | From MS2's plan to its close |
| Claude, never | Runs a Rene-only command; opens the M8 page in a browser, a sealed folder or an archive | Always |

## 8. Files the build would touch

**New (MS2's own; no conflict):**
- `eval/data/`: the tools, their `.py.lock` files, `tests/` and `records/`
- `eval/set_b/`: `generate.py`, its modules and `tests/`
- `eval/templates/`: `a_neg_log.csv`, `m8_labels.csv`, `set_b_cars.csv`, `set_d_log.csv`, `consented_log.csv` and `sidewalls.csv` (headers only)
- `docs/research/<date>-set-c-licences.md`

**Existing ones, which MS2's build updates:**
- `eval/templates/set_a_log.csv`: C209's three optional columns
- `docs/data/set-a-collection-guide.md`:
  - C209: one row per alert, and each `level_label_raw` holds depth words only
  - Rene's duty to link nearby spots
  - A-neg's ids, places and consent
  - Set B's numbering, car types, folders and owners' OKs
  - M8's steps and convention
  - Set D's and the sidewalls' logs
- `package.json`: MS2's tests join `check:py`. The window that merges MS2's build makes that edit, extending MS6's if the harness merged first.
- `README.md`: py7zr (its licence confirmed at install), and any Set C data used
- `CLAUDE.md`: MS2's commands, and the archive names once MS2-Q2 is answered, at the close (`revise-claude-md`)

**Waiting for MS3a's merge, for Rene, or for the owner:**
- `backend/analysis/probes/set_b_masks.py` and its test: a new file in MS3a's area (MS2-Q3). It uses `blur_for_meta` and `MetaClient.segment`, which are the same on `main` and on MS3a's branch.
- `eval/rules.md`: only through Window 4's v0.7 proposal, with Rene's written OK (MS2-Q2). The MS2 plan's rules steps read "confirm v0.7 is applied".
- `.claude/settings.json`: no change needed (C219). Optional, after MS3a merges: read-deny rules for the pre-split logs (`set_a/*.csv`, `a_neg/*.csv`). The MS2 plan's first task re-checks the deny rules, since this worktree runs older settings. The tracker's check at about 3:20 PM passed.
- `docs/PROGRESS.md` and `docs/log/`: ticks with evidence and a T9 row, written by their owner (Window 3, D20) from MS2's log-ready lines

## 9. Done when

| # | Check | Evidence |
|---|---|---|
| V1 | The tools are tested on synthetic data | pytest passes for `eval/data`, `eval/set_b` and `set_b_masks` (with a fake client). The tests cover:<ul><li>C222's refusal (case, `..`)</li><li>no listing outside `setc`</li><li>matching (C223, C224): a same-post alert; a separate alert that fits, or misses on spot, time or poster; the nearest of several, the rest in `other_alerts_raw`; rows on today's 17-column template</li><li>the copy check (C219), and the consent versions (C218)</li><li>each Rene-only command refusing with stdin on NUL, and with stdout piped</li><li>no password taken from an argument or the environment</li><li>a sentinel test: no label, link or spot text in any output, record or M8 page</li><li>the M8 page's script on a synthetic page: points as fractions, export, re-import</li><li>events, the split's shares, cap and determinism, and every audit violation in both modes</li><li>one-pass archives with encrypted names, opened only by the test, with the test password</li><li>the truth on a drawn wheel, with the waterline on its row</li><li>seeded reproducibility, and every written id in C221's pattern</li></ul> |
| V2 | Set A and A-neg are checked | `intake` reports no problems on Rene's final logs and M8 export. Its warnings are recorded. |
| V3 | The split is done (M19, W18) | The committed split record, with the seed, each C204 group's counts and the audit's PASS. Set A's sealed share is 40% to 45% (A-neg: a third to 40%), or the record says why not. Rene's note that 7-Zip opened the archive and that the plaintext inputs are deleted. |
| V4 | The development side is open and consistent | `audit --dev` passes, and the development manifest's hash equals the record's |
| V5 | Set B's development crops are ready for MS3b | `truth.csv` and crops for at least 3 development cars; Claude's overlay review; each look's water share and the frozen generator version (C213) |
| V6 | Set B's final cars are sealed | The committed Set B record: counts, no overlap with the development side, and the archive's hash. About 10 cars and about 40 crops across both sides, or the shortfall noted. Rene's 7-Zip test and deletion. |
| V7 | Set C stays within its licences | The STURM manifest, and the FloodDET licence note with its decision |
| V8 | All sets are frozen | The freeze record: the hashes of the development manifests and `m8.csv`, `truth.csv`, the STURM manifest (and FloodDET's, if downloaded) and each archive, plus the generator version. A later Set D record extends it. |
| V9 | Sealed files are untouched | V1's guard tests, and a source check that finds no listing call outside `setc`. `.claude/settings.json` is unchanged. At the sealed run, `audit --sealed` matches each archive's hash. |
| V10 | Nothing private is in the repo | `npm run check` passes (plan text, account IDs, gitleaks), and the records hold no sealed id, label, link, spot or photo |
| V11 | M11's codes are recorded | `sidewalls.csv` with each code checked against its photo, passed to MS3b's tire-code file (its C304) |

V6 and V8 close by Nov 1, after design §8's MS2 dates (§3).

## 10. Left to the builder

- The spot-text normalisation (abbreviations, connectors, generic words), fixed and tested before the split
- The water's texture, within C211
- The M8 page's layout and keyboard shortcuts
- File and function names inside `eval/data/` and `eval/set_b/`
- Library versions, pinned in the locks and checked with Context7, including py7zr's write-once mode and encrypted headers
- Test cases beyond V1's list

## 11. Questions for Rene

Each has a default that the draft plan follows (D7). MS6E-Q2 (how M8 names boxes) is settled by C208, for you to approve with this spec. C202 is the one place your sealed-path rule bends.

| # | Question | Options | Default (recommended) |
|---|---|---|---|
| MS2-Q1 | **The archive password.** The documents say only you can open the archive (M19), but not how the password is entered. | (a) C206 and C219: you type it twice into your own PowerShell window, and nothing stores it. You test each archive in 7-Zip (T9) before deleting the plaintext inputs. (b) As (a), but 7-Zip asks for the password itself, so no Lusot code ever holds it. Sealed files would then sit in plaintext inside a `sealed` folder first, which C205 avoids. (c) You build the archives by hand in 7-Zip from files the tools stage. | (a). It writes no plaintext beyond the inputs you already hold, and the test proves the password before anything is deleted. |
| MS2-Q2 | **Departures from `eval/rules.md` and from C39,** each needing your written OK. The `eval/rules.md` items are carried in Window 4's single v0.7 proposal (the tracker's B.8):<ul><li>**§3:** the alert time for a separate post (C209), and how tools test the same spot (C224)</li><li>**§4:** the seed `20261030`, fixed in the code; the shares, the cap and a single split; the walk stratified by deep (NPLV or NPATV) and other events, with at least one event of each group on each side (C204); the event rule (C203); and the final-car run as two commands, with the masks in plaintext in `set_b\sealed\` until the archive is tested (C214)</li><li>**§5:** Set B's crops and truth (C211, C212)</li><li>**§9:** "duplicate or repost" found as duplicate groups of identical files or difference hashes within 6 bits</li><li>**C39 and CLAUDE.md:** one write-once archive per sealing step (`lusot-sealed.7z`, `-set-b`, `-set-d`), not one file. The alternative is a single archive written once, after the last sealing input exists, with those inputs left in plaintext until then. Reopening an archive to add to it is ruled out (C205).</li></ul> | (a) Approve all, before the split. (b) Approve some. (c) None: the spec stands as Claude's calls, the report cites it, and the archives follow the single-file alternative. | (a). Until you answer, the tools follow these calls (D7), with one archive per sealing step. |
| MS2-Q3 | **Building `set_b_masks` before MS3a merges.** It is a new file in `backend/analysis/probes/`. It changes no existing file, and it uses two functions that are the same on `main` and on MS3a's branch. Your brief holds `backend/analysis/` until MS3a merges. | (a) Build it now that MS1 has closed, telling Window 3 first. (b) Wait for MS3a's merge, which puts Set B on MS3b's critical path. | (a). It keeps Set B's development crops on time for MS3b's Nov 1 finish line. |
| MS2-Q4 | **City offices as "a city government".** Set A takes only photos that MMDA or a city government posted itself (CLAUDE.md), and `eval/rules.md` §9 excludes other posters. Official city-office pages, such as a city's DRRMO or its information office, aren't named. | (a) Yes: official city-office pages map to `poster_kind = city`. Barangay pages, officials' personal pages, and police or fire pages map to `other`. (b) No: only the city government's own main page counts. | (a). City offices post many of the flood alerts, and the tracker's search checklist v2 already follows it. |
