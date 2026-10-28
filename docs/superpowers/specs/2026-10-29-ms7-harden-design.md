# MS7 Harden: spec

- **Date:** Oct 29, 2026 (Manila), written from 11:36 PM on Oct 28
- **Status:** Claude's draft; Rene approves. Written overnight without a live conversation, under Rene's instruction (D7, D15). Claude proceeds on the calls in §6 and the defaults in §8 until he answers. The builder check (Opus 5.5 at max, Oct 29) is folded in: its five questions became C801 and C818 revised, C827 to C829, and MS7-Q5, Q7 and Q8 (§11). The independent review of the plan (Opus 5.5 at max, from 12:32 AM) then changed S1 to S3, C801, C810, C812 to C814, C822 and C824, the privacy rows and §5, which now follows MS4's Draft 2. The plan's notes list each fix. MS8's spec (`547cc36`, its C903, C922, N3 and N7) then extended the history scan, made `banned-safe` fail in the README, and moved MS7-Q8's decision under MS8-Q1 (1:38 AM). MS9's spec (`394b5b8`, its N5 and N6) then added C830's readings for its runbook (4:40 AM). MS4's Draft 3 (`6c345b0`, tip `1867afe`; rows 13, 15 and 16 of the cross-spec audit) then moved the app's map to `GET /map/pins` and the public feed to its own API, set `feedPart` to each pin's mode, and named the inches switch `INCHES_SHOWN`; the throttle probe, L8, S3, P5, P7, P9, P11, C801, C806, C810 and §5 follow it (5:29 AM).
- **Implements:**
  - design §8's MS7 row and its pipeline-freeze rules (B2): the load test, the expired-upload-link test and the stop-switch test; the secret scan of the repo and the APK, the dependency audit, the privacy check and the copy review. Done when every Table 11 check is done or explained.
  - plan §10 (Table 11, all 28 rows), §13 (privacy, security and safety), §19 (engineering practices), §20 (Table 22, Phase 7), §18's checklist line on Table 11, and the two rows of plan Table 18 that this milestone tests: the Lambda limit of 10 and runaway costs
  - plan §24's M20, M21 and M22
  - the MS1 review items routed to MS7: the deferred table in the Oct 28 log, R44, R51 and R52
- **Builds on**, by name, because most of these are still drafts (§5 lists what each provides):
  - MS1 on `main` (98e8266): the stack, the stop switches, the upload link, `npm run check` and the smoke script
  - MS3a's spec and plan on `ms3a-landmark-core`: the handler, its log fields, C84 to C88, and the smoke helpers of its Task 15
  - MS3b's spec on the same branch: what freezes
  - Window 4's MS4 draft (`lusot-wt\ms4`, uncommitted, C500 to C517): the API, the modes, demo pins, the publish switch and the recovery tests
  - the MS5 draft (`lusot-wt\ms5`, uncommitted; read as it stood at 11:48 PM, Oct 28, C600 to C636): the app's polling and retries, its string tables and copy tests, the APK
  - MS6's spec on `w4-independent` (C400 to C426): the freeze, the report and the latency rows
  - Window 4's consent notice and privacy policy drafts (`docs/drafts/` on `w4-independent`)
  - the Ask Lusot spec, not yet written (calls from C700)

## 1. Intent

By Nov 3 the pipeline is frozen and the sealed run is done. MS7 checks everything around the measurement before Lusot goes public: that a rush of uploads is buffered instead of lost, that an upload link really dies after 5 minutes, that each stop switch acts without a redeploy, that no key, account ID, photo or location leaks, that every promise in the consent notice is true of the running system, and that every word Lusot shows says only what it can stand behind.

It matters for three reasons:
- **Judges check claims.** Table 11 promises a check for each of 28 weaknesses, and plan §18 asks for each to be done or explained in the README.
- **The anti-goals are severe.** A leaked key, an unblurred stored photo, an account ID in the repo or a pin that says "safe" would each undo the work, whatever else works.
- **Two of plan Table 18's risks are tested only here:** the account's Lambda limit of 10 during a rush, and runaway costs, whose remedy is the model-calls switch.

## 2. Goals, non-goals, anti-goals

**Goals**
1. The three cloud checks (§4.1), run on the frozen, deployed stack, after one rehearsal before the freeze.
2. The scans (§4.2): secrets in the repo, its history, the APK and the web bundle; the full `claude-security` scan (W26); the npm and Python audits; and a licence check of what ships.
3. The privacy check (§4.3): every promise in the consent notice and the privacy policy, as Rene approves them (M21), matched to a check that proves it.
4. The copy review (§4.4): an extended copy check, MS5's copy suites on the release build, a live pass over the deployed site, and Rene's M20.
5. The weakness ledger (§4.5): each of W1 to W28 marked Done with its evidence, or explained in the README.
6. MS1's deferred hardening items (§4.6), each landed or dropped with its reason.

**Non-goals**
- The analysis-path recovery tests: duplicate events, interrupted SAM streams, Lambda timeouts and failed deletions. B2 moved them before the freeze, and MS4 §4.8 runs them. MS7 only reads their evidence into the ledger.
- Anything that could change a depth output (C801). That needs rules §10's one disclosed rerun, which waits for Rene.
- New features. The README's judge path, the video, captions, the submission repo and the X post are MS8's.
- Meta's own rate limits. Fifty uploads make about 400 Meta requests over several minutes, far below 3,000 a minute, so the client's backoff on a 429 stays proven by MS1's unit tests.

**Anti-goals** (failures even if every check passes)
- A test that puts a pin on the public map, leaves a switch on or leaves a raw photo behind.
- Spending past either budget alert, or more Meta credits than §3 states.
- A scan, a script or a note that prints, logs or writes the Meta key, the account ID or a report id.
- Opening any folder named `sealed`, or any Set A, A-neg, Set B or Set D photo. MS7 needs none of them.
- A weakness marked Done without evidence, or a README line that claims more than the evidence shows.
- A fix that could change a depth output landing quietly after the freeze.

## 3. Constraints

- **CLAUDE.md's rules hold throughout.** The ones that bite here:
  - B2: after the freeze, only changes that can't change any depth output (C801)
  - never print, log or write the key; no account ID, console link or email address in a repo file; never log photos or exact locations
  - setting a switch with `put-parameter` is drift from the template, and a deploy can reset it
  - no manual console changes: tests act through the API, scripts and the template only
  - never run a cloud test during a phone test (M14), and the same holds for M16 and M17 (C825)
  - the `aws login` session lasts 12 hours; IPv6 doesn't connect on the home Wi-Fi, so scripts force IPv4; a Docker build and a Gradle build never run at once
  - deploys and APK builds run in the main worktree, on `main` after the merge: they need its git-ignored `backend/samconfig.toml` and `app/.env.local`, and a deploy must hold everything already deployed
  - every `capturedAt` a script sends is built from the server's clock (the `Date` header), since the laptop's ran 101 s fast on Oct 28
- **When:**
  - **Build:** the tools are built and tested on fakes as soon as the specs they read are committed: MS4's for the API names, MS5's for the string tables. That can be before Nov 3 (D15). Template, Android and test changes land before the freeze where they can, so the frozen commit carries them.
  - **Rehearsal:** once MS4 and MS5 are deployed, before the freeze, around Nov 2 (C802).
  - **Final run:** Nov 3, after the sealed run and its commit, on the system that ships (C827). If it can't finish that day, it finishes on the morning of Nov 4, before MS8's repo steps.
- **Budget** (C824):
  - **Meta:** at most $2.00 of credits for all of MS7, rehearsal and retries included. A load-test run is about $0.45: about $0.34 for the photos and about $0.10 for Ask Lusot's questions (§4.1, C828). The misleading-sign probe is at most $0.30 (C822), and everything else uses no Meta call. The rehearsal, the record run and the probe come to about $1.20, which leaves room for one paid re-run; a running total in the results note gates each one.
  - **AWS:** cents, inside the $5 budget alert.
  - A step that would pass either alert waits for Rene (D7).
- **Photos sent to Meta** come only from C87's credited Wikimedia Commons set in `lusot-data\set_c\commons-ph-floods\`, sent as the app sends them (1,600 px, JPEG quality 85). Every other test image is synthetic. STURM-FloodDepth stays offline (C87).
- **Who runs what:** Claude runs every check, except these, which are Rene's:
  - the start of the full `claude-security` scan (MS7-Q1)
  - M20, M21 and M22
  - any spend past an alert, and the one disclosed rerun if a fix needs it
  - any rewrite of the history that goes public (MS7-Q8)

## 4. What gets built and run

### 4.1 The cloud checks

**Shared rules**
- **Where the code lives:** one script per check in `backend/scripts/`, as a locked PEP 723 script like `smoke_upload.py`. The scripts share one helper module, and reuse the smoke script's helpers from MS3a's Task 15:
  - the masking `say()` and the IPv4 client
  - `dark_jpeg()` and `as_app_jpeg()`
  - `seeded_photo_order()` and `credited()`
  - `log_lines()` and `refuse_sealed()`
- **Private by construction** (C803):
  - Every test upload sits at one fixed point well outside Metro Manila, so MS4 makes it `private` (C502) and it never pins.
  - A run starts by creating one report and checking that its `mode` is `private`. If it isn't, the run stops before any photo is sent.
- **Like real phones:** each simulated phone has its own random device id, sent as `X-Lusot-Device` (MS4's C508). Each follows MS5's upload retries (C635) and poll (C601).
- **What it prints** (C812):
  - Counts and timings only, through the masking `say()`.
  - Reports are named by ordinal, with the script's letter in front (`L#1` to `L#50` for the load test), never by report id. Each run writes its own private file under `LUSOT_DATA_DIR`, mapping ordinals to report ids and listing its device ids, for the privacy check and for debugging only.
- **When it runs** (C825): never during a phone or user test, and each run is announced in the handoff note as `MS7 CLOUD TESTS RUNNING <time>` and `DONE <time>`.
- **Budget first** (C824): before any paid run, Claude records the Meta spend (the Billing page, read-only) and AWS's month-to-date spend (the Budgets API). The script prints its own maximum spend before it uploads anything.

**The load test, W16** (`backend/scripts/load_test.py`; C804 to C808)

1. **The throttle probe** (C806), first.
   - 30 requests to one route within a second (`GET /reports/<a random id>`, which answers 404), then 3 to a second route of the same app API (`GET /samples`) right after them, in the same second. The second group goes last, so a shared limit is already spent when it arrives.
   - Both routes sit on the app's API. The public feed, `GET /pins.geojson`, sits on its own API with its own stage (MS4's C521), and two APIs never share a stage limit, so it can't answer the question.
   - The 429s are counted per route. This answers MS5's N10: whether MS1's stage throttle (10 a second, burst 20) is counted per route or shared.
   - The run then waits 10 s for the throttle to refill.
2. **The rush.** 50 phones start an upload over 60 s, one every 1.2 s. Phones 1, 6, 11 and so on to 46 send a credited Commons photo: the first 10 credited photos in C87's seeded order. The other 40 send `dark_jpeg()`, which the server refuses as `too_dark` before any Meta call.
3. **Each phone** posts `POST /uploads`, then the S3 form, then polls until a final status or 10 minutes, all by MS5's rules.
4. **Ask Lusot in the rush** (C828): phones 3, 8, 13 and so on to 48 also ask one typed question each, about a Metro Manila place, right after their upload, once Ask Lusot is deployed. These ten paid questions are the traffic most likely to take the account to its Lambda limit of 10.
5. **Afterwards,** the script reads, read-only:
   - CloudWatch: Lambda's `ConcurrentExecutions` per function and for the whole account, `Throttles`, the queues' depth and oldest-message age, and DynamoDB's throttle events
   - the analysis log lines: `meta_calls`, `outcome` and `meta_status` per report
   - S3: whether `raw/` objects remain, and what `blurred/` holds
   - the app's map read (`GET /map/pins`), the nearby read and the public feed

**Passes when (L1 to L9)**

| # | Check |
|---|---|
| L1 | Every `POST /uploads` succeeds within the app's rule: at most one retry, and never one on a device-limit 429 |
| L2 | Every S3 form post returns 204 |
| L3 | Every report reaches `done`, `refused` or `failed` inside the app's 10-minute poll window, and none stays `pending` or `processing`. Each dark JPEG ends `refused/too_dark`. |
| L4 | The analysis function's `ConcurrentExecutions` (Max, per minute) never passes 5 |
| L5 | The dead-letter queue stays empty, and its alarm stays OK |
| L6 | Each dark JPEG's log line shows `meta_calls` 0. Each real photo has exactly one log line with `meta_calls` above 0, so each was paid once. |
| L7 | No `raw/` object remains for any test report, and `blurred/` holds a photo only for level results (W25) |
| L8 | No test report is published: none reaches the app's map read (`GET /map/pins`), the public feed, or a nearby read at either test point, and none carries the fields that publish a pin (MS4's committed spec; Draft 3's `published`, and `feedPart` set to the mode) |
| L9 | Each of the ten questions is answered, by Muse Spark or by its plain-list fallback, within Ask Lusot's own time limit (plan §12: 10 s) |

**Recorded, not pass or fail:**
- the 429s per route and in total
- the account's peak `ConcurrentExecutions` against its limit of 10, and `Throttles` for both functions. The README says whether the rush reached the limit.
- DynamoDB throttle events on the table and the report-id index
- the queue's peak depth and its oldest message's age
- seconds from upload to final status: median, nearest-rank 95th percentile, slowest and n, for real photos and dark JPEGs apart
- Meta's 429s and 5xx from `meta_status`
- the Meta calls made, and their cost from the log lines' billed usage

**When a check fails:**
- A failure of L1 or L3 is a finding about capacity: route throttles, DynamoDB units or the app's intervals. Those fixes can't change a depth output, so they land after review and a re-run.
- A failure of L4 to L9 is a defect and goes to `superpowers:systematic-debugging`.

**The expired upload link, and the upload path's guards** (`backend/scripts/upload_checks.py`; C809, C822)

| # | Check | Expected |
|---|---|---|
| K1 | Control: a link used at once with a dark JPEG | 204. The report ends `refused/too_dark`, with `meta_calls` 0. |
| K2 | The form's policy, decoded from base64 | Its expiration is at most 300 s after the response's `Date` header. It names only that report's key `raw/<id>.jpg`, `image/jpeg` and 1 byte to 10 MB. |
| K3 | A second link, held until 330 s after its `Date` header, then posted with a valid dark JPEG | 403 from S3. No raw object appears, no analysis runs, and the report stays `pending` until its 7-day expiry, like the smoke test's unused link. |
| K4 | A third link's form, posted with its `key` field changed to another report's key | 403. No object appears at either key. |
| A1 | An 11th `POST /uploads` from one device id within an hour, with no photo sent | 429 with MS4's device-limit code (N7) |
| A2 | `capturedAt` 16 minutes old | 422 `capture_too_old` (W20) |
| A3 | Random bytes posted as `image/jpeg` | `failed/bad_file` (MS3a's C83), with `meta_calls` 0 |
| A4 | A PNG form post | 403 from S3, as the smoke test already checks |

None of these makes a Meta call. A1 to A4 are W21's manual abuse test (C822).

**The stop switches** (`backend/scripts/switch_test.py`; C810, C811)

For each switch, the script:
1. sets the switch with `put-parameter`
2. polls until the switch takes effect, and records the seconds
3. checks the effect
4. sets the switch back to `off`
5. polls until service returns, and records the seconds

A `finally` block always sets the switch back to `off`. If that fails, the script prints the exact command to do it by hand, as the smoke script does. At the end, all three switches must read `off`.

| # | Switch | With it on | With it off again |
|---|---|---|---|
| S1 | `uploads` | `POST /uploads` gives 503 `uploads_paused`. It is probed with no photo and a fresh device id each time, so the device limit never interferes. One `POST /samples/{id}` is sent only after the first 503, and must give 503 too. A mistyped value (`paused`) also stops uploads, since only `off` lets work through. | `POST /uploads` gives 201 |
| S2 | `model-calls` | A dark JPEG ends `failed/model_calls_paused` with `meta_calls` 0, and its raw photo is gone. Once the switch cache has passed, one `POST /ask` answers with its plain list and no Meta call (assumed, §5). | A dark JPEG ends `refused/too_dark`, with `meta_calls` 0: the analysis runs again, at no cost. The load test's real photos then show that model calls resume. |
| S3 | `publish` | In this order: set the switch and read it back as on; wait for the switch cache (30 s, plus a margin); write one synthetic `live` pin item at MS1's smoke spot, with the fields that publish a pin (C810); wait for the feed cache (60 s); check that the pin is absent from the nearby read, the app's map read (`GET /map/pins`) and the public feed, that any demo pins remain in the nearby read and the map read (C516), and that `GET /reports/{id}` still answers; delete the item in an inner `finally`, and confirm it is gone. Only then does the switch go off. | The feed answers as before |

None of these makes a Meta call: S2 uses dark JPEGs, and its one question is answered by the plain list. No sample run or question is sent before the switch cache has passed, so a check can't pay for work the switch should have stopped.

**Readings for MS9's runbook** (C830; MS9's hand-offs N5 and N6)
- **The switch times.** The switch test prints, and the results note keeps, one table that MS9 quotes as it stands: for each switch, the seconds from `put-parameter` until its effect shows, and from `off` until service is back. Each row carries the date and the run it came from (the rehearsal or the record run).

  | Switch | On: effect after | Off: back after | Measured |
  |---|---|---|---|
  | `uploads` | `__` s | `__` s | date, run |
  | `model-calls` | `__` s | `__` s | date, run |
  | `publish` | `__` s, the feed's 60 s cache included | `__` s | date, run |

- **The budget reading, on its own:** `uv run backend/scripts/load_test.py --budget`. It needs only Rene's AWS login, uploads nothing, and prints amounts only, taking the account ID from `sts` inside the call and never printing it. It prints two groups, each with a line saying what it means:
  - **The $5 budget:** its limit, its month-to-date actual and forecast spend, and whether it counts credits (`CostTypes.IncludeCredit`). AWS Budgets counts credits by default, netting them against usage. So while the credits pay, the actual spend reads near $0, and it says little about burn.
  - **The free plan's credits,** the real burn signal: the plan's type, status, remaining credits and end date, from the Free Tier API (`get-account-plan-state`, which answers only in `us-east-1`). Expected: `FREE` and `ACTIVE`, a little under $200, falling by cents a day, and an end date about Apr 27, 2027. `PAID`, `EXPIRED`, or credits falling faster than cents a day go to Rene at once.
- **The alarms:** `uv run backend/scripts/load_test.py --alarms` checks that three alarms exist and email Rene:
  - the dead-letter alarm (MS1, with MS4's `OKActions`)
  - MS4's two invocation alarms: the analysis function's invocations in an hour, and the API function's, sized for Ask Lusot
  - each must have the alarm topic among its actions, and the topic at least one confirmed email subscription, which is counted and never printed

  Task 12's template test checks the same alarms in the template. If MS4 hasn't added the two by the rehearsal, that is a finding for MS4, and MS9's twice-a-day check stands in for them (its N6 fallback).

### 4.2 The scans

**Secrets (W26; C813, C814)**
- **The repo:** `npm run check:secrets` on `main` at the freeze and at MS7's close. That runs gitleaks over the whole history of every local branch, the plan-leak check and the account-ID scan, with D-h's fixes (§4.6).
- **Clones without the plan** (MS8's N3): once MS3a's fail-closed plan-leak fix merges, `npm run check` exits 2 on any clone without the private plan, unless `CI=true`.
  - MS7's runs all happen on this laptop, where the check finds the plan at its fixed staging path, so they pass, in the fresh scan worktree too (C814).
  - GitHub Actions sets `CI=true` and skips only that step.
  - Judges never need `npm run check`: their path is MS6's one command, which reads no plan. The README's development section, drafted by MS8, says what each check needs.
- **The history that R7 will make public** (C829): `scripts/check_history.mjs` reads every blob and commit message reachable from the branches that will go public: `main` by R7's default, or every branch if Rene pushes them all. MS8 runs the same tool on its export (its C903, C922), so the rules here follow C903's list:
  - **Account details:** 12-digit runs, with the account-ID scan's exclusions, and plan §24's numbers, read from the plan at run time as the plan-leak check does.
  - **Plan text:** the plan-leak check's line rule, over every blob in history, not only the working tree.
  - **Email addresses,** in blobs and in commit messages, other than no-reply ones.
  - **Links:** AWS's and Meta's console and sign-in links.
  - **Files that must never be committed:** env files other than `.env.example`, `samconfig.toml`, keystores, APKs and archives.
  - **Sealed paths:** any path with a part named `sealed` is found by its path alone. Its blob is never read, and it is reported by commit and count only, since a file name could say what it holds.
  - **Images:** any image outside an allow-list of path globs: the credited test fixtures, the Android template's icons, the app's own icons (`app/public/`) and the README's media (`docs/media/`).
  - **Identities:** author, committer and tagger addresses, counted by domain. Today all 176 commits carry a `gmail.com` address, which a push of the history would publish (MS7-Q8, decided under MS8-Q1).
  - **`Claude-Session` trailers,** counted, for MS8-Q1's check of whether those links open only for Rene.
  - It prints commits, paths and counts, never the matched text, with any 12-digit run in a path masked.
  - **Exceptions** are allowed only by exact blob, each with a written reason, in a committed allow-list (`scripts/history-allow.json`), which Rene reads before any push. The first is YuNet's `LICENSE`, whose copyright line a licence requires word for word (R11). Allow-listed hits are reported as a count.
  - **Without the plan,** the plan rules follow the plan-leak check: skipped with a notice under `CI=true`, and exit 2 anywhere else. An export run (`--export`) fails on a missing plan even in CI, so it can never pass by skipping a rule.
  - Real hits are expected: older versions of an MS3a test hold a literal 12-digit run, fixed going forward in `baa69a0`. Each goes to Rene under MS7-Q8 and MS8-Q1.
  - It runs by the morning of Nov 3, so any fix can finish before MS8 makes the submission repo.
- **The builds:** `backend/scripts/scan_build.py <apk or folder>` scans the APK that MS8 will ship and the web bundle as deployed. The web bundle is downloaded from the live site, `index.html` and the assets it names, into a fresh folder, because `npm run check` rebuilds `app/dist`. The script lives beside the other laptop scripts, so `check:py` runs its tests.
  - It unpacks the APK into a fresh, empty folder outside the repo, which it deletes afterwards.
  - It runs `gitleaks dir --redact --no-banner` on the folder.
  - It checks every file's raw bytes, binaries included, for the Meta key and the account ID's digits. It reads both at run time: the key from the user-scope variable, and the ID from `sts get-caller-identity`. It compares them in memory and prints only "absent", or the names of the files that hold them.
  - It looks for MS5's markers in every file, not only JavaScript: `api.meta.ai`, `MODEL_API_KEY` and `LUSOT_MOCK_API`.
  - It reports any 12-digit run in a text file as file and line.
  - For the APK, it also reads the privacy flags that §4.3 checks (P13).
- **The full `claude-security` scan** (C814):
  - It scans the whole repository at `medium` effort, on the freeze commit, as soon as the freeze is tagged. `security-review` covers every diff that lands after it (C827).
  - It runs in a fresh worktree made at the freeze tag, which holds tracked files only. The main worktree also holds git-ignored private files, such as `backend/samconfig.toml`, `app/.env.local` and the handoff notes, which the scan's agents could otherwise open.
  - Its report folder `CLAUDE-SECURITY-<time>/` stays out of git through its own `.gitignore`.
  - MS7's results note gives the findings by severity, each one triaged: fixed (with the commit), accepted (with the reason), or a disclosed-rerun question for Rene. It never quotes a secret.
  - Its start needs Rene's own acknowledgement of its time and token cost (MS7-Q1).
- **MS7's own diffs** that touch uploads, keys or IAM get `security-review` before they merge (CLAUDE.md).
- **The submission repo** (D9, R7) doesn't exist yet. MS8 runs the same scans on it, the history scan included, before Rene makes it public.

**Dependencies (C815)**
- **npm:**
  - `npm audit --omit=dev --audit-level=high` covers what ships (the app's and the API's production trees) and must exit 0.
  - `npm audit --json` over everything is recorded. The 3 moderate warnings MS1 found in development tools are triaged there.
- **Python:**
  - `uvx pip-audit@2.10.1 -r backend/analysis/requirements.lock.txt --require-hashes --disable-pip` covers the analysis image's runtime packages, with no environment needed.
  - The laptop scripts' locks are audited too, through `uv export --script` where uv supports it. They are recorded, not gating.
- **The rule for findings:**
  - A high or critical advisory in a shipped npm package, or in an API Lambda package, is fixed: those can't change a depth output.
  - In the analysis image, a package change could change outputs. So such an advisory is first checked for reach: can an uploaded file or the network trigger it? An unreachable one is accepted with its reason. A reachable one goes to Rene (MS7-Q5).

**Licences (C816)**
- `scripts/licences.mjs` reads `package-lock.json` alone (lockfile v3 records each package's licence and `dev` flag) and walks the app's and the API's production trees.
- `backend/scripts/licences_py.py` reads the analysis image's packages from `requirements.lock.txt`. It takes their licences from the locked environment's package metadata.
- Both print a table of package, version, licence and where it ships, and flag:
  - strong copyleft (GPL, AGPL)
  - weak copyleft (LGPL, MPL), for review
  - non-commercial licences
  - custom licences, such as the SAM License, for review
  - a missing or unknown licence

  A strong-copyleft, non-commercial or unknown licence in shipped code fails the check.
- **Vendored and data files** get a table in the results note, with each file's licence and where its credit appears: the YuNet model, the Metro Manila boundary (MS4-Q1), Ask Lusot's spot list, the fonts and icons, and OpenStreetMap's tiles.
- **Two cross-checks:**
  - every direct dependency appears in the README's credits
  - the app's licences page (MS5's C636) lists every shipped npm package
- **The output feeds M22,** Rene's licence choice (MS7-Q4).

### 4.3 The privacy check (C817, C818)

`backend/scripts/privacy_check.py` runs the automated rows. It makes read-only AWS calls and public API calls, and prints counts only. The other rows are recorded from tests and runs.

| # | Promise (consent notice and policy) | Check |
|---|---|---|
| P1 | Adults only, and consent comes first (C605) | MS5's end-to-end gates on the release build: a sample stops at the 18+ check, and an upload at the notice, with no request reaching the API before. On the live site, the same two stops. |
| P2 | Faces are blurred before any photo goes to Meta (C20, C37) | The frozen client's type-gate tests pass. Every MS7 report with `meta_calls` above 0 logs the blur version and its face-box count. The deployed analysis image was built from the frozen commit's analysis code: at the deploy, the freeze guard (C801) finds no change on the measuring path, and the image digest is recorded. Plates reach Meta by design, and the notice says so. |
| P3 | Faces and plates are blurred before storage (C48) | MS3a's B4 unit test passes. Claude also opens what each prefix stores: the `blurred/` and `overlay/` photos of MS7's credited uploads, at the rehearsal and the final run; the `demo/` photos; and `samples/`, which MS4's Draft 3 still stores only as blurred copies (C512). Samples made from Set B composites (R6's fallback) are skipped, since MS7 opens no Set B photo. A readable face or plate is counted and disclosed. An unblurred original outside `raw/`, or an unblurred box the pipeline found, fails P3 (C818). |
| P4 | Lusot asks Meta not to store requests (C85, C88) | The frozen client's tests assert `store: false` on every streamed SAM request and on `judge`. The 504 background fallback sends none and deletes the job, as the policy's one exception says. Background fallbacks during MS7's runs are counted from `meta_status`. |
| P5 | A pin leaves the map after 3 hours; an expired report can't be read (W27) | A synthetic published `live` item whose `visibleUntil` has already passed, so it is never visible, is absent from the nearby read, the app's map read (`GET /map/pins`) and the public feed. A synthetic item past its `expiresAt` gets 404 from `GET /reports/{id}`, if MS4's committed spec filters that read as W27's note in PROGRESS expects; if it doesn't, that half is a finding for MS4. Both items are deleted afterwards (C810). |
| P6 | Lusot keeps its copies 7 days | TTL is on `expiresAt` for the reports table, and on MS4's `limits` table. S3 lifecycle: `raw/` 1 day, `blurred/` and `overlay/` 7 days, and `demo/` only its 60-day backstop (MS4's C510). `samples/` holds blurred, licensed copies with no rule, by design (C512). Log groups keep 14 days, as the policy says. |
| P7 | A photo taken outside Metro Manila is never a pin (D14) | All of MS7's reports are `private`. Each answers its own `GET /reports/{id}`, none is published, and none appears in the app's map read (`GET /map/pins`), the public feed, or a nearby read at the outside test point. MS5's private result screen passes its end-to-end test. |
| P8 | A failed upload's queue record keeps the IP address up to 7 days (R49) | The dead-letter queue's retention is 604,800 s, and the main queue's is no longer. The dead-letter queue is empty after MS7's runs. |
| P9 | Service logs hold no photo, location or IP address | The API's and the analysis function's log events from MS7's run windows are scanned for IP addresses, the test points' coordinates as a pair, the runs' own device ids (from their private files), base64 JPEG data and the key's bytes, compared in memory. Expected: 0 of each. Lambda's own START, REPORT and INIT lines must count 0 too, so timestamps, request ids and logged scores can't pass for addresses or coordinates. Access logging stays off on both HTTP APIs, the app's and the feed's (C521), and on the bucket, with no CloudTrail data events (MS4-Q6). The policy discloses Amplify's own access logs (C622), which the claims table checks. |
| P10 | The original is deleted after analysis (W25) | No `raw/` object remains for any MS7 report, refused and failed ones included (L7) |
| P11 | The feed carries only what the map shows (C514) | The public feed, `GET /pins.geojson` on its own read-only API (MS4's C521), and the app's map read, `GET /map/pins` (C519), carry exactly MS4's committed public pin fields, and nothing else: no device id, photo link, `readings` or claim. (Pins carry the report id as `id`, by design, C504; the privacy texts must then say what holding it allows, MS4-Q10.) Coordinates have at most 4 decimals. The feed's API allows any origin (`AllowOrigins: *`) for `GET` only, with no credentials, while the app's API keeps its own origins. |
| P12 | No accounts, no names, a random device id | No route in MS4's committed API takes a name, and the device ids are never logged (P9) |
| P13 | The APK keeps nothing private | In the APK's merged manifest, `allowBackup` is false, and the permissions are exactly the allowed list: network, location, camera, the microphone if the APK takes spoken questions, and AndroidX's own `DYNAMIC_RECEIVER_NOT_EXPORTED_PERMISSION`, which it adds to every app. Capacitor's `loggingBehavior` is `none` (`scan_build.py`). |
| P14 | Spoken questions are never stored by Lusot | The bucket holds only the known prefixes (`raw/`, `blurred/`, `overlay/`, `demo/`, `samples/`), counted by prefix only. No table in the committed template holds audio (assumed for Ask Lusot, §5). |

The rows follow the texts Rene approves (M21). A promise added or changed there adds or changes its row before MS7 closes.

**NPC registration** (M21's second half) gets a facts sheet for Rene. It lists the plan's four triggers (250 or more employees, sensitive personal information on 1,000 or more people, high-risk processing, automated decisions about people), each beside Lusot's facts (MS7-Q6).

### 4.4 The copy review (C819, C820)

**The copy check**
- `scripts/check_copy.mjs` reads its rules from `scripts/copy-rules.json`, and `scripts/check_copy.test.mjs` tests it.
- **What it scans:**
  - the app's string tables and content (`app/src/i18n/`, `app/src/content/`)
  - the overlay's words, from MS4's label source
  - Ask Lusot's prompt and fallback templates
  - the saved answers to MS6's 20 test questions, passed with `--answers <file>` from outside the repo
  - the evaluation report
  - the README, and later MS8's captions
- **Fail:**
  - MS5's banned words (C608), extended:
    - `unsafe`
    - any word that contains `ligtas`, such as `kaligtasan`, `ligtasan` or `makaligtas`
    - "MMDA's 9 levels" in any form
  - a level line without "at this spot" or "sa spot na ito"
  - MS5's crossing phrases, plus a few more
  - These fail everywhere, the README included, since it is product copy (MS8's C922). Only the evaluation files (`eval/`, whose rules and report name levels in tables) and Ask Lusot's prompt files (which quote banned words as prohibitions) report them for review instead.
- **Required:**
  - the exact safety line in the English table
  - "Not affiliated with MMDA." in the app and the README
- **Review** (printed for Rene's M20, not failing):
  - crossing words outside the allowed sentences: `cross`, `pass`, `drive through`, `wade`, `tawid`, `dumaan`, and `lusot` used as a verb
  - whole-road words: `road`, `street`, `route`, `kalsada`, `ruta`
  - level words outside the 9 levels, such as `ankle deep`
  - verdicts about one vehicle type, such as "for SUVs"
  - "first", "photo analyzer", "accuracy" and "danger"
- **Allowed sentences:** the safety line, D19's refusal (it mentions "the road"), MMDA's three class names, C81's class lines, and "Not affiliated with MMDA."

**MS5's suites on the release build**
- the string-table tests
- the end-to-end `safety` and `copy` specs, both languages, at 360 × 640
- `LUSOT_RELEASE=1 npm run copy:review -w app`, for C609's count of unreviewed lines

**The live pass** (C820): `app/e2e/live-safety.spec.ts`, skipped unless `LUSOT_LIVE_URL` is set. It opens every read-only route on the deployed site at 360 × 640, in both languages, and checks that the exact safety line is visible. It makes no upload.

**Rene's M20**
- `check_copy.mjs --sheet` gives him one table, ordered by screen: every Taglish line, refusal, reason line, retake tip and the safety line, with the review hits marked. The sheet goes to him beside his manual-tasks PDF, not into the repo.
- His review sets C609's marks. MS8's release needs the count at zero.

### 4.5 The weakness ledger (C821)

A row is **Done** only with evidence beside it: a command and its one-line result, or a named section of a report. Otherwise it is **Explained**: one line in the README's "Known limits" section says what wasn't proven and why. MS7 drafts that section, and MS8 keeps it.

| W | Table 11's check | Proved by | Evidence |
|---|---|---|---|
| W1 | Set A, parked against moving | MS6: the `moving` subset (C414) | the sealed report |
| W2 | Set B error by vehicle type | MS3b's C314, through MS6's harness | the sealed report, Set B |
| W3 | Set B error; landmark against geometry | MS6: the ablation | the sealed report |
| W4 | Unit test; Set A photos with reflections | MS3b's D3; MS6's `reflection` subset | MS3b's tests; the sealed report |
| W5 | Passability and within-one agreement | MS6 | the sealed report |
| W6 | Set A photos at tire depth or deeper | MS6's W6 subset | the sealed report |
| W7 | Set B by angle and size | MS6: Set B's bins | the sealed report |
| W8 | Coverage on the splash subset | MS6's `splash` subset | the sealed report |
| W9 | A-neg reads "no flood seen" or refuses | MS6: the false flood rate | the sealed report |
| W10 | Copy review | MS7 (§4.4) | the results note |
| W11 | No vehicle verdict in the output | MS7: a test reads the frozen schema and finds no vehicle verdict, and the copy check reads Ask Lusot's 20 answers | the results note |
| W12 | Ask Lusot's test questions | the Ask Lusot spec (MS6's 10 typed and 10 spoken) | its results |
| W13 | Correct refusals of dark and blurry photos | MS6: the quality subset | the sealed report |
| W14 | Vehicle-type confusion matrix | MS3b and MS6, on development data only | the development report (private); the counts in PROGRESS |
| W15 | Test photos with misleading signs | **No milestone owns it.** MS7 runs a small probe (C822). | the results note |
| W16 | Load test, 50 uploads in a minute | MS7 (§4.1), with the account's peak concurrency for plan Table 18's limit of 10 (C828) | the results note |
| W17 | Evaluation report | MS6 | the sealed report |
| W18 | Split audit script | MS2, run at the sealed run (MS6 S1) | MS2's audit output |
| W19 | Evaluation report | MS6 | the sealed report |
| W20 | A gallery photo and an old photo | MS5's U14, plus MS7's A2 | MS5's close; the results note |
| W21 | Manual abuse test | MS7's A1 to A4, plus MS4's unit tests for flags and the sample caps | the results note |
| W22 | Field test on two streets | MS5's U13 (Rene, M16) | MS5's close |
| W23 | Copy review | MS7 (§4.4) | the results note |
| W24 | Throttled-network test | MS5's slow-network test (C629) and C635 | MS5's close |
| W25 | No raw photo left in S3, refused ones included | MS7's L7 and P10, after MS3a's B4 | the results note |
| W26 | Secret scan of the repo and the APK | MS7 (§4.2) | the results note |
| W27 | Query test with an expired item | MS7's P5, after MS4's unit tests | the results note |
| W28 | Calendar reminder | Rene (§8, actions) | PROGRESS |

### 4.6 MS1's deferred hardening (C823)

From the Oct 28 deferred table, R44 and R51. Each can't change a depth output. They are listed in priority order.

| # | Item | Decision |
|---|---|---|
| D-a | Deny rules (R44's R6, first): `Read` on `backend/samconfig.toml` (it holds the alarm email) and on `.env`, `.env.local` and `.env.*.local` files; `Edit` and `Write` on lockfiles | Land, with a test that reads `.claude/settings.json` |
| D-e | A TLS-only bucket policy (R51) | Land, in the template |
| D-h | The account-ID scan reads non-UTF-8 text (such as UTF-16) and file paths too, and `check:py`'s test packages get exact versions | Land |
| D-l | A lock-drift guard (R51): `uv lock --check`, `requirements.lock.txt` equal to a fresh `uv export`, and each script lock checked | Land, in `npm run check` and CI |
| D-m | Both bundles built in `check:node` (R51) | Land |
| D-d | Template: a region assertion, and a comment that a deploy resets a flipped switch. The source map's cold-start cost is measured, and the setting is kept or dropped by the number. The dead-letter alarm's recovery path is MS4's `OKActions`, which MS7 only checks. | Land |
| D-f | Scripts: a traceback on an unexpected AWS reply, the one terse failure message, and no report id in any printed line (C812) | Land |
| D-g | The smoke test's fake-AWS harness, committed as a test (from the git-ignored `preserved/smoke_dryrun.py`) | Land |
| D-k | Narrow `file_paths.xml` to one cache subfolder, and keep the FileProvider, which Capacitor's own WebView client names for file inputs | Land, then rebuild the APK |
| D-i | Face-blur tests: assert the box coverage, lighten the 1.9 GB test, and make the seal tests stricter | Land (tests only) |
| D-b | A lint-on-edit hook | Dropped (C823) |
| D-c | A security-review agent | Not added: `security-review` and the `claude-security` scan cover it, as R44 itself said |
| D-n | The deny rules re-checked against the PowerShell tool | A static check of the rules' patterns, plus the live test MS1 and MS2 recorded. MS7 makes no new attempt on a sealed path (C823). |

Items not done by noon on Nov 3 are dropped, with the reason in the log (design §8, "When we slip").

## 5. Interfaces MS7 assumes

Each comes from a draft that may change. The MS4 rows follow its Draft 3 (`6c345b0`, tip `1867afe` on `ms4-backend-specs`), which changed after this spec's first version. The plan's first task re-reads each committed spec and records any change here before a script is built against it.

| Interface | As assumed | From | If it changes |
|---|---|---|---|
| The stop switches | `/lusot/stop/uploads`, `/lusot/stop/publish` and `/lusot/stop/model-calls`, as plain strings. Only `off` lets work through, and an unreadable switch fails closed. The API caches each for 30 s. The analysis handler reads `model-calls` for each message. `uploads` stops `POST /uploads` and `POST /samples/{id}`. `publish` acts when a result is written and when pins are read: it hides `live` pins from the nearby read, the app's map read and the feed, and demo pins stay. A change takes effect within about 90 s. | MS1 code; MS3a §3.1; MS4 §4.6, C516, C519, MS4-Q7 | S1 to S3's expectations follow the committed spec |
| The upload link | A presigned POST, 300 s, for one key `raw/<id>.jpg`, `image/jpeg`, 1 byte to 10 MB. The response is `{reportId, upload: {url, fields}, expiresInS}`. | MS1's C27; `uploads.ts` | K2 reads the policy, so a change shows at once |
| The endpoints | `POST /uploads` (with `X-Lusot-Device`; a missing id falls into a shared bucket; 10 a device and 300 in all per clock hour, MS4-Q13, which MS7's runs, the load test's 50 plus a few dozen from the other scripts, stay well under), `GET /reports/{id}` (with `mode`), `GET /reports?lat=&lng=&radius=` (at most 300 m), `GET /map/pins` (every visible published pin, `live` and `demo`, for the app's map, C519), `POST /reports/{id}/flag`, `POST /samples/{sampleId}` (5 a device and 30 in all an hour) and `GET /samples`, all on the app's API. The public feed, `GET /pins.geojson` (`live` pins only, cached 60 s), is on a second, read-only API with its own stage and `AllowOrigins: *` (C521). A published pin carries the report id as `id`. Publishing sets `published`, and `feedPart` to the pin's mode (`live` or `demo`), which `feed-index` reads. "No flood seen" isn't published. Error codes: 503 `uploads_paused`, 422 `capture_too_old` and `capture_in_future`, and a 429 with a device-limit code. | MS1 code; MS4 §4.1 to §4.4, C504, C506, C508, C517; MS5's N7 | the scripts take names from one constants block, filled in by Task 0 |
| The modes | `live`, `private`, `sample`, `eval` and `demo`. `private` is set at upload outside Metro Manila. `eval` items are written directly by scripts, but MS7 uses `private`, since it must go through the public API, as MS4's smoke runs do. | MS4's C501, C502, C513 | none, unless `private` changes |
| Demo mode (G1) | Demo pins come only from `demo_pins.py`. The publish switch never hides them, they are never in the public feed though the app's map read shows them (C519), and the 3-hour hide and the 7-day delete don't apply to them; `demo/` has a 60-day backstop rule. MS5-Q2 may leave none. S3's check works either way. | MS4's C510, C516, C517; MS5-Q2 | none |
| The poll and the retries | Every 2 s for the first minute, every 5 s to 4 minutes, every 15 s to 10 minutes. A 429 waits for `Retry-After`, or for the next interval with up to 1 s of jitter. The upload and the S3 post each retry once, and a device-limit 429 is never retried. | MS5's C601, C635 | the load test's phone follows the committed rules |
| The log fields | One JSON line per report, with `outcome`, `meta_calls`, `meta_status`, the blur version and the face-box count. The smoke helpers read them. | MS3a §3.6, C80, its Task 15 | the parsers follow the committed fields |
| The photos | C87's folder, its seeded order and `credited()` | MS3a's C87; its Task 15 | none |
| The copy | `app/src/i18n/en.ts` and `fil.ts` (`{text, reviewed}`), `npm run copy:review -w app`, the end-to-end `safety` and `copy` specs, `app/scripts/check-bundle.mjs`, and "sa spot na ito" | MS5's plan, Tasks 1, 6 and 18 | the copy check's file list follows them |
| The privacy texts | Window 4's drafts, which become `app/src/content/` | MS5's Task 7 | P1 to P14 follow the approved text |
| The evaluation | MS6's C416 latency rows, which MS7 doesn't feed (C808), and `eval/results/report/report.md` | MS6 | none |
| The APK | MS5's debug APK in `lusot-data\builds\` with its SHA-256, or MS8's release build if Rene wants one | MS5's C627 | the scan runs on whichever APK ships |
| Ask Lusot | `POST /ask` takes a typed question with a place in Metro Manila and answers within 10 s, or with its plain list from `get_reports`. With `model-calls` on, it gives the plain list with no Meta call, and voice returns an error the app words. The 20 test answers are saved outside the repo. No audio is stored. | not yet written (C700 onward); plan §12 | S2, L9, P14 and the copy check follow its spec |

## 6. Calls (Claude's, C800 onward)

| # | Call | Why |
|---|---|---|
| C800 | **MS7's boundary and timing.** MS7 owns the harden checks, their scripts, the weakness ledger and the deferred items in §4.6. It changes no pipeline code. Its tools are built and tested on fakes as soon as the specs they read are committed, rehearsed once before the freeze (C802), and run for the record on Nov 3. | Nov 3 also holds the sealed run and its report. Building early leaves the day for running, reading and fixing. |
| C801 *(revised by the builder check, BC1)* | **What "can't change a depth output" means after the freeze.**<ul><li>**The measuring path is frozen.** It is the pipeline from decoding the photo to its result (steps 0 to 7), with everything that feeds it: the face blur before Meta, the numbered boxes Muse Spark sees, the Meta client's requests, the prompts and schemas, the rules and tuning, the vendored model, the handler's run deadline and its margin (MS3a's C84, C88), the pixel cap set when the package loads (R26), the analysis image's locked dependencies and base-image digest, and the analysis function's environment, timeout and memory.</li><li>**Anything else can land.** That means the API, the app, the template outside the analysis function's resource, scripts, tests, and analysis code that runs after the result: the overlay and its words, the storage blur, the writes, the raw delete and the logs. Three proofs go with it: the diff names no file on the measuring path; the analysis function's resource in the template is unchanged since the freeze tag; and a replay of saved development outputs gives identical results before and after (MS3a's B3). The handler mixes both kinds of code, so a reviewer reads any change to it against the deadline's code.</li><li>**Error handling and retries** in the Meta client may land too, as B2 says, with the same replay proof.</li><li>**Any change on the measuring path,** the face blur included, goes to Rene as rules §10's one disclosed rerun (MS7-Q5).</li><li>**One exception is designed in:** applying the sealed run's decision, which sets `geometry_in_level` (MS6 §4.5 step 9, MS3b's C309) and flips `INCHES_SHOWN`, the literal in the API function's environment in the template, in the commit that records the gate (MS4's C515).</li></ul> | B2 allows fixes that can't change a reading, such as error handling and retries, and needs a test that anyone can apply. The sealed run never runs the publish step (MS6's C412 skips the face and plate phrases and publishes nothing), so code after the result can't change a scored reading, and the replay shows that the reading logic didn't move. This lets M20's overlay wording and late defects in the handler land, which a freeze of the whole package would have sent to the rerun. A timeout can turn a slow photo's failure into a result, so it stays frozen. The decision's settings were scored in the sealed run's ablation. |
| C802 *(revised by C827)* | **One rehearsal before the freeze.** The cloud checks, the privacy check with P3, and the build scan run once on the deployed stack before the freeze, at the same bounded cost. The rehearsal is written up to the record's standard, in its own section of the results note. The run after the sealed run is the record. | A load fault or a blur defect found after the freeze could need the disclosed rerun; found before it, the fix is free. If the final run can't happen, a rehearsal kept to the same standard can stand in, with the difference disclosed (C827). It costs about $0.45 and an hour. |
| C803 | **Test reports are private.** Every MS7 upload sits at one point well outside Metro Manila. Each run first checks that a new report is `private` and stops before any photo if it isn't. | A test pin on the public map would be a fake report (MS5's C630). `private` needs nothing new from the API. MS4's `eval` mode is reached only by scripts that bypass the API, which the load test must not do. |
| C804 | **The load test's mix:** 10 credited Commons photos and 40 synthetic dark JPEGs. The real photos go every fifth slot, so long analyses run through the whole minute. At about $0.034 a photo, a run costs about $0.34. | The rush tests the queue, the cap of 5, the shared Lambda limit and the API throttle. Ten real analyses of 35 to 45 s keep 5 slots busy for over a minute, while 40 cheap reports fill the queue and the polls. All 50 real would cost about $1.70 a run and test nothing more about buffering (MS7-Q2). |
| C805 | **The load test acts like the app:** one device id per phone, MS5's retries (C635) and its poll (C601), each request with its own timeout. | W16 asks whether real phones are served. MS5's §10 risks name exactly this rush against the index's read units and the stage throttle. |
| C806 | **A throttle probe** opens the load test: a burst on one route of the app's API, then a few requests on a second route of that same API (`GET /samples`) right after it, in the same second. | The API Gateway documentation read through Context7 doesn't say whether the stage's default throttle is counted per route or shared. MS5's N10 needs the answer, and the probe gives it in a minute. |
| C807 | **L1 to L8 decide the load test.** 429s, throttles, queue depth and latency are recorded, not judged. | A user is harmed only by a lost upload, a lost result or a wait past the app's window. A 429 on a poll is the throttle doing its job. |
| C808 | **The load test's latency stays out of `eval/results/latency.jsonl`.** | It measures a rush, not one photo. MS5's live checks feed MS6's latency rows (C416, C631). Mixing them would blur both. |
| C809 | **Link expiry runs on server time.** K3 waits until 330 s after the API response's `Date` header, not the laptop's clock. | The laptop's clock was found 101 s fast on Oct 28. A 30 s margin covers the header's one-second resolution and the network. |
| C810 | **Synthetic items, only while hidden.** The publish check (S3) and W27's check (P5) write report items straight to DynamoDB: a `done` item with a level, the fields that publish a pin in MS4's committed spec, built for the item's mode (Draft 3: `published`, and `feedPart` set to `live` or `demo`), and no photo. The publish item is written only after every API container has seen the switch on, and is deleted before the switch goes off. The W27 items are expired from the start. Each is deleted in a `finally` block. If a delete fails, `publish` stays on, and the script writes the hand fix to its private file and prints that file's path. | A real pin would be public for a minute or more (MS7-Q3). These items cost nothing and are never visible. An item without the publishing fields would be hidden anyway, and the check would prove nothing, so the field list is pinned to MS4's committed item shape by a test. The order matters: an item written before the switch has reached every container could be served for up to 30 s, and then cached for 60 more. |
| C811 | **The switch times go into the MS9 runbook,** as the results note's "Switch times" table (§4.1), and all three switches read `off` at the end of every run. | MS9 depends on flipping `model-calls` when the credits run out (plan Table 18), and Rene needs to know how long it takes to act. MS9's plan copies the table into its lever table and constants. A deploy can reset a flipped switch, so the read-back catches drift. |
| C812 | **No report id in any output.** Scripts name reports by ordinal, and each run's map from ordinal to id stays in its own private file under `LUSOT_DATA_DIR`. Photos fetched for P3 are named by ordinal too, so no S3 key reaches a command line. The smoke script's own `say()` gains the same mask (D-f). | An unpublished report's id is the only key to its result and photo links for 7 days (MS4's C503, C504), and every MS7 report is unpublished. Terminal output gets pasted into notes and logs, which reach the public repo (R7). |
| C813 | **The build scan** checks every file of the APK and of the web bundle as deployed, downloaded from the live site: gitleaks, the exact key and account-ID bytes compared in memory, MS5's markers and 12-digit runs. The APK is unpacked into a fresh folder outside the repo and deleted afterwards. A flagged file name is printed with any 12-digit run masked. | gitleaks finds patterns, not our own key. Comparing the exact bytes proves it isn't there without ever printing it. The repo scan can't see build output, MS5's bundle check reads JavaScript only, and a local `app/dist` may be a later build than the one judges get. |
| C814 *(timing revised by C827)* | **The full `claude-security` scan:** the whole repository at `medium` effort, on the freeze commit, as soon as the freeze is tagged, in a fresh worktree made at the tag, which holds tracked files only. It doesn't wait for the sealed run, and `security-review` covers every diff that lands after it. Its report stays git-ignored, and a summary of the findings with each triage goes into the results note. If Rene hasn't started it by noon on Nov 3, Claude runs a fresh-agent security review of the attack surface instead (the API handlers, the upload policy, IAM and the analysis handler), and W26 is recorded as partly met. | W26 and the deferred table require it before the code goes public. The frozen code is most of what ships, and an early scan leaves time to fix what it finds. The plugin requires the user's own words accepting its cost, so it can't start unattended (MS7-Q1). |
| C815 | **The audit rule.** What ships must have no unresolved high or critical advisory. Fixes in npm and the API land. In the analysis image, a finding is checked for reach first: an unreachable one is accepted and disclosed, and a reachable one goes to Rene. Laptop tools are recorded, not gating. | Plan §13 audits before submission. An analysis-image package change is a rerun-class change under C801. |
| C816 | **The licence check reads lockfiles and package metadata,** with no new dependency. It fails on a strong-copyleft, non-commercial or unknown licence in shipped code, and flags custom licences for review. | npm's lockfile v3 already records each package's licence and `dev` flag (checked on `main`: 373 of 377 entries carry one). M22 needs the list, and C636 and the README need to agree with it. |
| C817 | **The privacy check is a table of promises.** Every promise in the approved consent notice and policy gets one row and one check (§4.3). | M21 asks Rene to approve text. A table lets him approve text that has been shown to be true of the running system. |
| C818 *(revised by the builder check, BC2)* | **The blur before storage is checked by eye,** beside MS3a's unit test.<ul><li>**Scope:** every prefix that stores a photo: `blurred/`, `overlay/` and `demo/` on what MS7's runs and the demo seed stored, and `samples/` as MS7-Q7 settles it.</li><li>**Pass and fail:** a readable face or plate is a counted miss. It is disclosed, since the notice says blurring can miss some, and it doesn't fail P3. P3 fails when a stored photo outside `raw/` is an unblurred original, or shows a face or plate inside a box the pipeline found but didn't blur.</li><li>**When:** at the rehearsal too, where a fix is still free.</li></ul> | A unit test proves the code blurs the boxes SAM returns. Only looking shows whether a face or plate it missed stayed readable. A miss is the detector's known limit (W25), while an unblurred original or an unblurred box is a defect. These are credited public photos, so Claude may open them. |
| C819 | **One copy rule set.** `scripts/copy-rules.json` holds the fail, required, review and allowed lists, and the checker scans more than the string tables. Its banned list extends MS5's with `unsafe` and every word that contains `ligtas`. | MS5's test misses affixed Tagalog forms such as `kaligtasan`, and text outside the string tables: the overlay, Ask Lusot's answers, the report and the README. One file keeps MS5's and MS7's checks from drifting. |
| C820 | **A live pass of the deployed site** checks the safety line on every read-only route, both languages, at 360 × 640. | MS5's suites test a local build. Judges use the deployed one, and a stale deploy would slip through. |
| C821 | **The ledger's rule:** Done needs evidence, and Explained needs a README line. MS7 drafts the README's "Known limits" section. | Plan §18 asks for every row done or explained in the README. |
| C822 | **Two checks with no other owner.** W21's manual abuse test runs as A1 to A4, at no Meta cost. W15's misleading signs get a probe: 4 credited Commons photos go through MS3a's offline runner three times each, twice as the app would send them and once with a large printed depth (such as "TIRE DEEP") drawn on a blank area of that same app-format copy, so the sign is the only difference. A photo counts only when its two plain runs agree; it passes when the signed run gives the same status and level. The result is reported as k of n counted photos, with the noisy ones named, and called indicative. 12 runs cost at most $0.30, and the files stay under `LUSOT_DATA_DIR`. | Table 11 names a check for each row, and no spec names one for W15 or W21. The probe tests the frozen pipeline without changing it. Muse Spark can answer differently on two runs of one photo, so the second plain run tells noise from the sign's effect. It is the cheapest honest evidence; without it, W15 would only be explained. |
| C823 | **The deferred items** are landed in §4.6's order, and the lint-on-edit hook is dropped. The deny-rule re-check is static. | By Nov 3 little code is left to edit, and a hook reaches every window at once (R44's own worry). A live attempt on a sealed path, even a missing one, is the kind of access CLAUDE.md forbids, and MS1 and MS2 already recorded the live test. |
| C824 *(ceiling raised by the plan review)* | **Cost ceilings:** at most $2.00 of Meta credits and a few cents of AWS for all of MS7. Before each paid run, the spend so far is recorded, and a running total in the results note must leave room for the run's stated maximum. A run that would bring Meta past its $100 alert, or AWS past $5, waits for Rene. | D7 gates spending past the alerts. Recording the spend first makes the gate a check, not a hope. The rehearsal, the record run and the W15 probe come to about $1.20, and the spec expects at least one paid re-run, which $1.50 wouldn't cover. |
| C825 | **Runs never overlap a person's test** (M14, M16, M17), and each is announced in the handoff note. | The upload switch refuses real uploads for up to a minute, and the rush slows everyone's results. |
| C826 | **One results note,** `docs/research/2026-11-03-ms7-harden-results.md`, holds every check's command and one-line result, counts and timings only. PROGRESS's ticks point to it. | One place for judges and Rene to check. CLAUDE.md's "evidence with every tick". |
| C827 *(from the builder check, BC3)* | **What the record run waits for, and what stands if it can't run.**<ul><li>**The cloud and privacy checks** wait for the backend that ships: the sealed run's commit, then the decision's deploy (MS6 §4.5 step 9).</li><li>**The build scans and the live pass** wait for MS5's rebuild of the web app and the APK after the sealed run (C616).</li><li>**MS7's own changes** after the freeze merge into `main` only after the sealed run is committed, since the run accepts no commit but the freeze (MS6's C412).</li><li>**The `claude-security` scan** runs on the freeze commit as soon as it is tagged (C814).</li><li>**If the record run can't finish on Nov 3,** it finishes on the morning of Nov 4, before MS8's repo steps. A check that still can't run keeps its rehearsal result (C802), and the README says what changed between the two stacks.</li></ul> | The system that ships exists only after the decision's deploy and the rebuild, so a record taken earlier would check the wrong builds. The frozen code doesn't wait for either. Scanning it early, then reviewing each later diff, resolves "scan after the last fix" against "scan early enough to fix". Design §8 allows half a day of slip before nice-to-haves stop. |
| C828 *(from the builder check, BC4)* | **Ask Lusot joins the rush.** Ten phones each ask one typed question about a Metro Manila place, right after their upload. The run records the account's peak `ConcurrentExecutions` beside the analysis function's, and L9 checks every answer. It costs about $0.10 a run. If Ask Lusot isn't deployed by the rehearsal, the rush runs without it, and the README says that the account's limit wasn't tested. | Plan Table 18's risk is the shared limit of 10. Uploads and polls alone may never reach it, since analysis stops at 5 and API calls are short. An Ask Lusot answer holds an API slot for seconds, and its place lookups run in the API Lambda too (C11), so it is the traffic most likely to reach the limit. Without it, MS7 couldn't claim that risk as tested. |
| C829 *(from the builder check, BC5; extended by MS8's C903 and C922, its N7)* | **A scan of the history that R7 will make public** (§4.2): every blob and commit message, for account IDs, plan §24's numbers, plan text, email addresses, console and sign-in links, never-commit files, sealed paths (found by path, never read) and images outside an allow-list, plus author, committer and tagger domains and the `Claude-Session` count. Exceptions go only by exact blob, with a reason. An export run fails on a missing plan. A hit stops MS8's repo steps until it is fixed or allow-listed (MS7-Q8, MS8-Q1). | The working-tree scans miss history, and gitleaks finds keys, not bare account IDs. The deferred table puts a full-history account-ID scan before going public. R7's default publishes the full history, author addresses included. MS8 runs this one tool on its export, so its rules live here, once. |
| C830 *(from MS9's hand-offs N5 and N6)* | **Readings for MS9's runbook** (§4.1): the switch times in one quotable table; a budget reading that stands on its own (`load_test.py --budget`) and says what its numbers mean; and an alarm check (`load_test.py --alarms`) that the dead-letter alarm and MS4's two invocation alarms exist and email Rene. | MS9 runs daily checks through judging and quotes these as they stand. The $5 budget counts credits by default, so it stays near $0 while they pay, and only the free plan's remaining credits show the burn. Without the invocation alarms, abuse would show only at a check. MS9 already names `load_test.py --budget`, so the readings stay in that one script. |

## 7. Done when

| # | Check | Evidence |
|---|---|---|
| H1 | The load test passes L1 to L9 on the system that ships, with the recorded measures, the account's peak concurrency included (W16) | `load_test.py`'s summary in the results note |
| H2 | An expired link is refused, its policy is right, and a link writes one key only (K1 to K4) | `upload_checks.py link` |
| H3 | Each switch stops its part and releases it without a redeploy, with times recorded in the "Switch times" table, and all three read `off` at the end (S1 to S3) | `switch_test.py`; the results note |
| H4 | The secret scans are clean; the history that will go public is clean, or each hit is allow-listed by its exact blob with a reason Rene has read (MS8's S7); and the `claude-security` findings are triaged (W26) | `npm run check:secrets`; `check_history.mjs`; `scan_build.py` on the shipped APK and web bundle; the scan summary |
| H5 | No unresolved high or critical advisory in shipped packages, and every other finding triaged | the npm audit and pip-audit outputs |
| H6 | No strong-copyleft, non-commercial or unknown licence in shipped code; every vendored and data file credited; the choices laid out for M22 | the two licence scripts; the README and C636 cross-checks |
| H7 | Every privacy row is verified, and Rene approves the texts (M21) | `privacy_check.py`; the claims table; his approval |
| H8 | The copy check and MS5's suites pass on the release build; the live pass finds the safety line on every route; M20 is done, or its open count is recorded as MS8's release gate | `check_copy.mjs`, `npm run e2e -w app`, `live-safety.spec.ts`, `copy:review` |
| H9 | Every Table 11 row is Done with evidence or explained in the README (the design's finish line) | PROGRESS §3; the README's "Known limits" |
| H10 | Every deferred item is landed with its check, or dropped with a reason | §4.6, ticked |
| H11 | `npm run check` and CI pass; PROGRESS, the log and the spend are recorded | CI; the results note |
| H12 | MS9's readings are ready: the switch times in its quotable table, the budget reading with what its numbers mean, and the three alarms present and emailing Rene, or MS4's missing alarms recorded as a finding (C830) | `load_test.py --budget` and `--alarms`; the results note |

## 8. Questions for Rene

Each has a default that the plan follows until he answers (D7). Most important first.

| # | Question | Options | Default |
|---|---|---|---|
| MS7-Q1 | **Starting the full `claude-security` scan.** The plugin starts only on your own words accepting its time and token cost; a request passed on by an agent doesn't count. | (a) You start it once the freeze is tagged, from a Claude Code session in the fresh worktree Claude makes at the freeze tag (C814): `/claude-security`, Scan codebase, Whole repository at `medium`, then Yes. (b) A message from you includes "Run the full claude-security scan; I understand it may take a while and use a significant number of tokens," and Claude starts it on the freeze commit. | (b), so the scan starts as soon as the freeze is tagged (Nov 2 or 3) and its findings can still be fixed. Without either by noon on Nov 3, C814's fallback review runs, and W26 is recorded as partly met. |
| MS7-Q8 *(decided under MS8-Q1)* | **The history R7 would publish.** Every commit so far carries a `gmail.com` author and committer address, which a full-history push makes public. The history scan (C829) may also find an account ID or a console link in an old version of a file. MS8-Q1 owns this decision; this row only states the scan's side of it, and one answer settles both. | (a) In the export only, rewrite with `git filter-repo`: a `--mailmap` to your GitHub no-reply address for author, committer and tagger lines, and `--replace-text` for any hit you choose to remove. Dates, messages, files and every commit stay; the hashes change. (b) Publish the history as it is. (c) Rewrite the hits only, and keep the author address. | (a), which is MS8-Q1's default (b). It keeps R7's point, the dated history, while publishing no address and no account detail. The private repository stays as it is. Needed by Nov 3, before MS8 makes the submission repo. |
| MS7-Q7 *(settled by MS4's Draft 2 and kept in Draft 3, unless its committed spec changes it)* | **Sample originals in `samples/`.** MS4's Draft 1 stored each sample photo unblurred. CLAUDE.md says faces and plates are blurred before anything is stored, and the policy draft says they are blurred in every sample and demo pin. MS4's Draft 2 (C512) now stores only the pipeline's blurred copy, and never the original. Asked only if MS4's committed spec stores originals again. | (a) Keep the open-licensed originals, which their authors already publish unblurred under CC0 or CC BY, and store a consented M9 photo only after the face and plate blurs. (b) Store every sample only as its blurred copy, as Drafts 2 and 3 do. (c) Keep every original, and the policy says samples are stored as published. | (b), as Drafts 2 and 3 do. It meets CLAUDE.md's rule with no exception, and P3 checks it. |
| MS7-Q2 | **How real the rush is.** Each option adds about $0.10 a run for C828's ten questions. | (a) 10 credited photos and 40 dark JPEGs: about $0.34 a run, $0.68 with the rehearsal. (b) All 50 credited photos: about $1.70 a run, $3.40 with the rehearsal, which needs C824's ceiling raised to about $6 to leave room for one re-run. (c) All dark: $0, but no real analysis holds the 5 slots. | (a). The README says exactly what ran. (b) is still far inside the credits and the alert, if you want "50 real uploads" to be literally true. |
| MS7-Q3 | **The publish switch's cloud check.** | (a) A synthetic pin that exists only while the switch hides it. There is no public control in the cloud; MS4's unit tests show that such a pin appears when the switch is off. (b) One real test pin, visible for about 2 minutes as the control, then removed. | (a). (b) shows a fake report to anyone who opens the map in those minutes. |
| MS7-Q4 | **The repo licence (M22), and R52's two readings.** | Licence: (a) MIT; (b) Apache-2.0, with its patent grant and NOTICE file; (c) no licence, so judges can read the code but not reuse it. R52: meta-sam-parser stays a PyPI dependency named in the lockfiles and credited, never copied into the repo; and transitive packages are credited through the lockfiles, the base-image note and the app's licences page, not one by one. | MIT, and both R52 readings as stated. The Metro Manila boundary keeps its own ODbL notice beside the file, whatever the code's licence. |
| MS7-Q5 *(broadened by the builder check, BC1)* | **A fix that C801 sends to the rerun after the freeze:** a reachable advisory in the analysis image, or a defect on the measuring path, the face blur included. Only asked if one turns up. | (a) Fix it, and take rules §10's one disclosed rerun. (b) Leave it, disclose it with the reason, and fix it after judging. | While you decide, uploads stay on, unless the defect can expose a person's data or the key. If it can, the uploads switch goes on, which pauses samples too, while the map and Ask Lusot stay up. Then (a) if the defect can expose data or be reached through an upload or the API, and (b) otherwise. |
| MS7-Q6 | **NPC registration (M21's second half).** | (a) Not required, on the facts sheet (§4.3): a solo project, no employees, blurred photos of bystanders kept 7 days, no sensitive personal information as the Data Privacy Act defines it, and no decisions about people. (b) Ask the NPC first. | (a), if you agree with the facts. This is a reading of the plan's triggers, not legal advice; the call is yours. |

**Rene's actions** (not questions): M20 (the copy sheet), M21 (approving the texts against §4.3's table), M22 (the licence, with MS7-Q4), and W28's calendar reminder. The free plan ends 6 months after the Oct 27 sign-up, so the reminder goes about two weeks before Apr 27, 2027. Claude can't reach his calendar.

## 9. Not in MS7

- **The analysis-path recovery tests** (MS4 §4.8, before the freeze, B2), and **the sealed run** (MS6, Rene's).
- **MS8:** the README's judge path, the video and captions, the submission repo (which reruns MS7's scans, the history scan included, and the copy check before Rene makes it public), and the X post.
- **A scan of the container base image's operating-system packages.** Plan §13 audits dependencies; the base image is AWS's maintained image, pinned by digest, and changing it is a rerun-class change (C801). The results note records it as a known gap.
- **Load beyond 50 uploads a minute,** and Meta-side rate limits (§2).

## 10. Risks

- **Nov 3 is crowded,** and the record run sits at the end of a chain: the sealed run, its commit, the decision's deploy, then MS5's rebuild (C827). The tools are built and rehearsed before it (C800, C802), and the final run takes about two hours of wall clock. What can't finish on Nov 3 finishes on the morning of Nov 4; whatever is still left is dropped with its reason.
- **The `aws login` session lapses.** The cloud checks wait for Rene's login, while the scans and the copy review carry on.
- **A load finding late on Nov 3.** Capacity fixes, such as route throttles, DynamoDB units or poll intervals, land with a re-run. Anything bigger is explained in the README.
- **A switch left on after a crash.** The `finally` reset, the printed command and the read-back at the end of every run (C811).
- **A deploy during the switch test resets a switch.** Nothing deploys while MS7's cloud checks run.
- **Draft names change** (MS4, MS5, Ask Lusot). §5 is the checklist, and the plan's first task re-reads each committed spec.
- **Rene's time on Nov 2 and 3:** M20, M21, M22 and the scan's start all land then. The copy sheet and the claims table are built to be read in one sitting each.

## 11. Builder check (Oct 29)

A fresh reviewer (Opus 5.5 at max) read this spec as if it had to plan MS7 alone, with CLAUDE.md, the build design, PROGRESS, the code on `main`, the drafts §5 names and the Oct 28 deferred table. It opened nothing under `lusot-data` and made no network call. It returned five questions, settled as follows. Claude also found, while settling BC5, that every commit's author address is a `gmail.com` one.

| # | Question (short) | Pile | Settled as |
|---|---|---|---|
| BC1 | Does C801 send every change inside the analysis package to the rerun, such as M20's overlay wording, the geometry decision, or a late defect in code the sealed run never runs? And do uploads stop while a rerun question is open? | Claude's call; the rerun and the pause are Rene's | C801 now freezes the measuring path only, with two proofs, and the decision's settings are excepted. MS7-Q5 covers the rerun and the pause. |
| BC2 | What does P3 cover, and does one readable face fail it? `samples/` holds unblurred originals as MS4 drafts it. | Claude's call; the conflict is Rene's | C818: every stored prefix; a miss is counted and disclosed; an unblurred original or an unblurred found box fails. P3 also runs at the rehearsal. `samples/` is MS7-Q7. |
| BC3 | What must the record run wait for, and what stands if it can't run on Nov 3? C814 said "after the last fix" while MS7-Q1 said "early". | Claude's call | C827: the decision's deploy and MS5's rebuild come first; the scan runs on the freeze commit, and `security-review` covers later diffs; Nov 4 morning, then the rehearsal's result with the difference disclosed (C802). |
| BC4 | Should the rush include Ask Lusot traffic, without which the account's limit of 10 may never be reached? | Claude's call | C828: ten typed questions in the rush, L9, and the account's peak concurrency recorded, for about $0.10 a run |
| BC5 | Who scans the history that R7 will publish, and what if it finds something? | Claude's call for the scan; Rene's for any rewrite | C829 and §4.2's history scan; MS7-Q8 for a hit and for the author addresses |
