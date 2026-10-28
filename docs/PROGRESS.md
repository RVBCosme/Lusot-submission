# Lusot progress board

- **Last updated:** Oct 28, 2026, 3:01 PM Manila, by Claude (Window 3: took over the board after MS1 closed; `main` merged into `ms3a-landmark-core`)
- **Rule:** tick a box only after its check passes, and write the evidence next to it.
- **Status words:** Not started, In progress, Done, Blocked, Dropped (with a reason).
- **Key dates (Manila time):** kickoff Oct 27, 12:00 AM. Core working by Oct 29. Build ends Nov 3. **Submit Nov 4, 10:00 PM.** Hard cutoff Nov 5, 10:00 AM. Closing ceremony and finals Nov 10, 1:00 AM.

## 1. Milestones

| MS | Name | Dates (Manila) | Status | Spec | Plan | Evidence |
|---|---|---|---|---|---|---|
| MS0 | Prepare | Oct 26 to kickoff (+ Oct 27) | In progress: all done except M7's 20 candidates (moved to MS2) and R3, R6, R7 (needed later) | [build design](superpowers/specs/2026-10-26-lusot-build-design.md) (approved Oct 28) | checklist below | see the MS0 checklist |
| MS1 | Set up | Oct 27 to 28 | **Done, Oct 28.** All 12 tasks are reviewed, and the stack was re-deployed (2:44 PM) and smoke-tested (2:45 PM). It is merged into `main` at the close and pushed to the private `RVBCosme/lusot`, where CI passed. A6 passed with Rene's phone test (M14, 3:40 PM). | [MS1 spec](superpowers/specs/2026-10-28-ms1-setup-design.md) (approved by Rene, Oct 28, 3:24 PM; closing notes in §8) | [MS1 plan](superpowers/plans/2026-10-28-ms1-setup.md) (12 tasks, all ticked) | the acceptance checks below; ticked steps in the plan; [Oct 28 log](log/2026-10-28.md) |
| MS2 | Data | Oct 27 to 30 | In progress, by Window 2 on `ms2-data`: the data-tooling spec (`586296c`, amended in `fc0cd13` for Rene's 80-10-10 rule) and plan (`85ce8ff`, 21 tasks) await Rene's review. Tasks 1 and 2 are done (`1d85421`, 9:19 PM), and Task 3 was in its fix round at 9:55 PM. | on `ms2-data` (Window 2's branch) | on `ms2-data` | Window 2's note and the Oct 28 log |
| MS3 | Measurement (3a core by Oct 29, 3b by Nov 1) | Oct 28 to Nov 1 | In progress, by Window 3 on `ms3a-landmark-core` (D20):
<ul><li>The MS3a plan review is done (8ec1769, 11:23 AM). The spec gained calls C72 to C88, and Rene's answers are in (7:58 AM and 1:30 PM).</li><li>MS1 closed (98e8266), and `main` is merged in (f953b2f, 2:57 PM; `npm run check` passes).</li><li>Tasks 1 to 9, 7a, 10, 11 and 12 are built and reviewed, plus the plan-leak fix R97 (663c146, 11:24 PM; analysis 483 tests). C85's paid SAM check passed (8:40 PM, about $0.008, on Commons photos).</li><li>Next: Tasks 13 to 17 (the handler, the image, the smoke script, the deploy with its live checks, and the close).</li><li>The MS3b spec and plan draft are committed (e4f1c33, 860a294, 22ab3d2; calls C300 to C321, rulings R86 to R91). The plan's review found 10 items, fixed in the MS3b amendment pass after MS3a.</li></ul> | [MS3a spec](superpowers/specs/2026-10-28-ms3a-landmark-core-design.md) (approved by Rene, Oct 28, 3:24 PM, C42 to C86; C87 and C88 are Claude's under D7) | [MS3a plan](superpowers/plans/2026-10-28-ms3a-landmark-core.md) (17 tasks; the reviewed version is on Window 3's branch) | Window 3's task reviews, in its note and the Oct 28 log |
| MS4 | Backend | Oct 31 to Nov 1 | Not started | none | none | none |
| MS5 | App | Nov 1 to 3 | Not started | none | none | none |
| MS6 | Ask Lusot and evaluation | Nov 2 to 3 | The evaluation half is in progress, by Window 4 on `w4-independent`: the MS6 evaluation spec (`a69b7d9`, calls C400 to C426) and plan are committed there. Harness Tasks 1 to 5 are done (`68a9329`, 9:32 PM), and Task 6 (the release gate) started at 9:33 PM. Ask Lusot hasn't started. | on `w4-independent` (Window 4's branch) | on `w4-independent` | Window 4's note and the Oct 28 log |
| MS7 | Harden | Nov 3 | Not started | none | none | none |
| MS8 | Submit | Nov 4 | Not started | none | none | none |
| MS9 | Judging | Nov 5 to 10 | Not started | none | none | none |
| MS10 | After | From Nov 10 | Not started | none | none | none |

### MS0 checklist (before kickoff; documents only, no project code)

- [x] Read the whole plan (64 pages, including the figures) and double-check it. Evidence: [verification notes](research/2026-10-26-verification-notes.md) §1.
- [x] Write `CLAUDE.md` with Superpowers as the main workflow and the skill routing. Evidence: `CLAUDE.md` at the staging root.
- [x] Make a searchable text copy of the plan. Evidence: `docs/plan/lusot-build-plan.txt`, extracted with pdftotext in layout mode. It was 158 KB for the Oct 26 version. It is now 198 KB for the 79-page 10:31 PM version, and on Oct 28 PyMuPDF confirmed it has exactly the same words as the PDF.
- [x] Draft the build design (milestones, decisions, gap fixes). Evidence: [build design](superpowers/specs/2026-10-26-lusot-build-design.md).
- [x] Builder check of the design, with the answers folded in. Evidence: build design §17 (B1 to B6). `CLAUDE.md` and `eval/rules.md` v0.3 updated.
- [x] Rene answers R1, R4 and R5. Evidence: Oct 27 answers, recorded as D6 to D9 in build design §5. R2 is answered by plan §24 (build design C4).
- [ ] Rene answers R3, R6 and R7 (UI direction; consented photos and fallbacks; how the submission repo gets its history). See build design §7.
- [x] Builder check of design v2. Evidence: build design §19 (K1 to K8). Rene answered K2a, K3, K5 and K6 (D11 to D14); Claude settled the rest (C15 to C21). `eval/rules.md` is now v0.5, and the Set A log and template gained `label_in_image`.
- [x] **Rene approves the build design.** This gates MS1. Evidence: Rene chose "Approve with the fixes" at 12:08 AM, Oct 28, after Claude double-checked the summary (build design §20, fixes F1 to F6). His other answers are D15 to D18.
- [x] Obsidian vault config for `Lusot-Staging` (D6). Evidence: `.obsidian/app.json` (Markdown links, relative paths, attachments in `_attachments/`) and `.obsidian/daily-notes.json` (`docs/log`, YYYY-MM-DD).
- [x] Rene opens `C:\Systems\Lusot\Lusot-Staging` in Obsidian with "Open folder as vault". Evidence: `%APPDATA%\obsidian\obsidian.json` lists it as open, and `.obsidian\workspace.json` now exists (checked about 11:35 PM, Oct 27).
- [x] AWS Region check (C9). Evidence: AWS Settings lists no projects (Claude in Chrome, read-only, Oct 27, 9:30 PM), so the account isn't pinned to Sydney.
- [x] Toolchain installs T1 to T4 and T6. Evidence: the T rows in §2 below (all verified by 11:20 PM, Oct 27).
- [x] `MODEL_API_KEY` holds the real key. Evidence: the user variable is 48 characters with no whitespace or control characters, and `POST /v1/responses/input_tokens` (muse-spark-1.3, free, no inference) returns HTTP 200 (Claude, about 11:35 PM, Oct 27; the key was never printed). The first attempt had stored a Ctrl+V character. Claude Code still holds the old value until it restarts.
- [x] Re-read the second plan update (10:31 PM, 79 pages). Evidence: build design §18; `CLAUDE.md` rewritten to match.
- [x] Verify the Meta API facts, the hackathon page, the Set C datasets and the foundation repos. Evidence: verification notes §2 to §6.
- [x] G5 tire lookups. Evidence: verification notes §4. Mirage G4 confirmed; Tamaraw and Hilux need confirmation.
- [x] Set A collection kit: guide plus log template. Evidence: [collection guide](data/set-a-collection-guide.md), `eval/templates/set_a_log.csv`, and the private folders under `C:\Systems\Lusot\lusot-data\` (set_a, a_neg, consented).
- [x] Alert index from public news lists (Jul 10, Aug 9, Aug 10) as a search aid. Evidence: [alert index](research/2026-10-26-alert-index.md).
- [x] `eval/rules.md` draft v0.2, for Rene to approve; the release-gate numbers are Rene's call (M18). Evidence: `eval/rules.md`.
- [x] Disk space estimate for the toolchain (Rene asked). Evidence: T6 below; about 30 to 40 GB is needed against 42.9 GB free.
- [x] Re-check whether the Official Rules have been posted (M4). Evidence: the Official Rules and Event Waiver (dated Oct 25) are in the event page's HTML, found by the Oct 27 fact check ([plan update check](research/2026-10-27-plan-update-check.md) §5). Plan §2 summarizes the participant guide and the Discord #rules. Reading and accepting them is still Rene's (M4).
- [x] Re-read the updated plan (Oct 27, 78 pages), compare it with the Oct 26 version, and check its new facts against their sources. Evidence: [plan update check](research/2026-10-27-plan-update-check.md).
- [x] Bring the Set A collection guide, the alert index and `eval/rules.md` (draft v0.4) in line with the Oct 27 plan: government-posted Set A photos only, the self-check ablation row, Set D apart from Set B, the one-command check. Evidence: those files and the `eval/rules.md` change log.
- [x] Update `CLAUDE.md`, the build design and this board's milestone contents to the Oct 27 plan, after Rene answers the Oct 27 questions. Evidence: build design §5, §6, §8, §18 and §19 and the rewritten `CLAUDE.md` (Oct 27, 11 PM to midnight); the stale lines left over were fixed on Oct 28 (design §20, F4).

### MS1 acceptance checks (spec §2)

- [x] **A1, the probe returns masks and schema-valid JSON.** Evidence: Window 2's probe (12:47 PM, Oct 28) ran 5 STURM photos through SAM 3.1's 7 phrases, decoded with `meta-sam-parser`. Muse Spark's answers were valid against schema v1 in strict mode 5 of 5, and every returned id exists. `check_ids` caught one id in the wrong list. See the [MS1 probe results](research/2026-10-28-ms1-probe-results.md).
- [x] **A2, the water test ran on 10 photos.** Evidence: overlays reviewed by Window 2 and its task reviewer. The probe note says SAM never put water on a wheel (overlap 0.0), but found no water in 5 of 10 photos. 3 of 10 pass C40, an early signal only.
- [x] **A3, every photo sent to Meta was face-blurred first.** Evidence: the client accepts only the exact `BlurredImage` type, and `test_rejects_unblurred_input` and `test_rejects_blurred_image_subclass` prove it. The probe log records the blur version.
- [x] **A4, one-command deploy.** Evidence: `npm run deploy` exited 0 (2:40 to 2:44 PM). `sam deploy` succeeded, then "lifecycle: keep 3" (C38). A no-change rerun passes through `--no-fail-on-empty-changeset` (855147f).
- [x] **A5, upload end to end in the cloud.** Evidence:
  - the script: SMOKE OK at 2:45 PM, covering the link, the JPEG, `failed/pipeline_not_built` and the raw photo gone (404)
  - the web build: Task 9b showed "Upload worked…" with Playwright
  - the bucket held 0 objects afterwards (2:46 PM)
- [ ] **A6, a bare APK uploads one photo from a real phone.** Waits for Rene (M14). The emulator run passed (Task 10).
- [x] **A7, repo hygiene.** Evidence:
  - `npm run check` exited 0 after the merge (2:00 PM) and after the fix wave.
  - The pre-commit scan blocked a planted fake key, and the deny rules blocked a sealed read at the harness level (Task 2).
  - gitleaks, the plan-leak check and the account-ID scan are clean.
  - CI runs the same checks, and its first run passed (2:52 PM).
- [x] **A8, the Meta key is in SSM.** Evidence: a `SecureString`, "length 48, read-back matches: True" (Task 8). The cloud function logs `model_key_loaded=true` (smoke, 2:45 PM).

## 2. Manual actions (Rene)

From Table 27 of the plan (M1 to M33, as of the 10:31 PM update on Oct 27), plus T1 to T6 from the build design (§14). Statuses for M1 to M3 and M31 are as Rene recorded them in plan §24 on the evening of Oct 27. T statuses and data counts were checked on this PC at about 9 PM, Oct 27.

| ID | Type | Action | When | Status |
|---|---|---|---|---|
| T1 | Setup | Install AWS CLI v2, version 2.32 or newer (M31's `aws login` needs it) | Oct 27 | Done. Evidence: `aws --version` gives `aws-cli/2.38.6` (Oct 27, 9:47 PM; installed by Claude with winget) |
| T2 | Setup | Install AWS SAM CLI | Oct 27 | Done. Evidence: `sam --version` gives `SAM CLI, version 1.170.0` (Oct 27, 9:57 PM; the first attempt was cancelled at its admin prompt, and the retry worked). |
| T3 | Setup | WSL isn't installed: run `wsl --install` as admin and restart, then install Docker Desktop with the WSL 2 backend (builds the analysis container image) | Oct 27 | Done. Evidence: `wsl --version` gives 2.7.14 with the `docker-desktop` distro running on WSL 2. Docker engine 29.9.2 reports about 6.2 GB of memory (the `.wslconfig` cap works). `docker run --rm hello-world` prints "Hello from Docker!" (Claude, 11:20 PM, Oct 27). |
| T6 | Setup | Free disk space so C: has about 60 GB free (the build adds about 30 to 40 GB) | Oct 27, before T3 | Done. Evidence: C: had 105.6 GB free at 9:57 PM, Oct 27 (it was 41.4 GB at 9 PM; Claude deleted nothing). |
| T4 | Setup | Install Android Studio Otter (2025.2.1) or newer, which bundles the JDK, plus the Android SDK 36 platform (Capacitor 8 minimum) | Oct 27 to 28 | Done. Evidence: Android Studio 2026.2 in `C:\Program Files\Android\Android Studio` (`studio64.exe`, bundled JBR 25). `sdkmanager --list_installed` shows `platforms;android-36` (rev 2), `build-tools;36.0.0` and `platform-tools` 37.0.1. Command-line tools 22.0 match Google's SHA-256. `ANDROID_HOME` and `JAVA_HOME` (JDK 17.0.20.1) were already set and left unchanged; Capacitor 8's JDK need is confirmed at MS1. |
| T5 | Setup | Optional: fix the GitHub connector token in Claude Code (the GitHub CLI already works) | Any time | Not started |
| T7 | Setup | Give the GitHub CLI the `workflow` scope so CI can be pushed: `gh auth refresh -h github.com -s workflow`, then approve in the browser (D16) | When convenient; CI stays parked until then | Done. Evidence: `gh auth status` lists the token scopes `'gist', 'read:org', 'repo', 'workflow'` (Rene granted it at 10:32 AM; Claude checked at 10:55 AM, Oct 28). |
| T8 | Setup | Restart Claude Code from a new terminal so it picks up the fixed `MODEL_API_KEY` (F5) | Next time Claude Code is restarted | Done. Evidence: in the new session, `MODEL_API_KEY` is 48 characters and equals the user variable (Claude, 9:55 AM, Oct 28; never printed). |
| M1 | Accounts | Create the AWS account with a card that allows online and international charges, a billing address and a phone code; turn on MFA for the root user | Oct 27 | Done (plan §24) |
| M2 | Accounts | Check the Lambda concurrency quota in Service Quotas and request an increase if it is too low | Oct 27 | Done (plan §24, 10:31 PM): AWS declined 1,000 on Oct 27 for lack of usage history. Lusot works within 10 and asks again after some real use (plan Table 18). |
| M3 | Accounts | Claim the $150 credits with Meta's claim form (application email and Team ID); add a card that passes Meta's check; set a Spend Limit alert; then create the API key | Oct 27; claim by Nov 4, 9:00 PM ET | Done. Evidence: Billing page read by Claude in Chrome, Oct 27, about 9:35 PM: $150 free credits in use, a card on file, an email alert at $100 monthly spend. One API key exists (plan §24). |
| M4 | Rules | Read the participant guide, the Discord #rules and #faqs posts, and the Official Rules and Event Waiver, which bind everyone who takes part | Oct 27 | Done Oct 27 (plan Table 27). Winners are paid only after the organizers confirm both were signed. |
| M5 | Team | Solo entry confirmed: no one else builds, labels or submits | Oct 27 | Done |
| M6 | Accounts | Link Discord to the Cerebral Valley account and claim the Builders role; approve the Amplify connection to GitHub | Oct 27; Amplify at the first web deploy (Oct 31) | In progress: Discord linked and Builders role claimed on Oct 27 (plan Table 27). Still to do: the Amplify approval. |
| M7 | Set A | Search MMDA's and Quezon City's own posts **by hand** for flood photos with alerts; log the link, time and label; use no news-outlet photos; keep everything private | Oct 26 to 30 | Not started (Set A log: 0 rows) |
| M8 | Set A | Label each photo's landmark and vehicle type before Lusot runs on it, with the MMDA label columns hidden; only Rene labels, as the one approved participant | Oct 28 to 30 | Not started |
| M9 | Samples | Collect July and August 2026 flood photos and clips from friends, family or community groups; get a written OK; note who appears in each, and where and when it was taken (design §12) | From Oct 26 | Not started (0 consented files) |
| M10 | Set B | Photograph parked cars side-on in daylight (our own or family cars) and read each tire code from the sidewall | Oct 27 to 28 | Not started |
| M11 | Table 7 | Photograph the tire sidewalls of a jeepney, a tricycle and a bus (and, per G5, a Hilux and a Tamaraw if possible) | Oct 27 to 28 | Not started |
| M12 | Voice | Record at least 10 Taglish questions from different people, with street noise | Oct 27 | Not started |
| M13 | Set D | Only if it rains: measure a puddle beside a parked car from the dry curb, aiming for at least 5 ruler-checked photos | If it rains | Not started |
| M14 | Android | Install the APK on a real phone; test the camera, GPS and upload on mobile data | Oct 28 | **Done, 3:40 PM, Oct 28.** Evidence (Rene's screenshot, checked by the tracker session): the MS1 debug APK on his Android phone, over mobile data (5G), reached Step: Done with a 22 m GPS fix and the server's "Upload worked. Analysis comes in a later build.", which the app shows only for `refusalReason = pipeline_not_built`, so the whole round trip worked. The safety line shows, and the layout clears the system bars. Still open: whether the stored photo is upright (EXIF), checked at the first analysed photo (MS3a Task 16 or MS5). |
| M15 | Android | Keep the web URL as the main judge path; optionally register Google's free limited-distribution account (up to 20 devices, no government ID) | Nov 1 | Not started |
| M16 | GPS | Test pin accuracy on two real streets | Nov 1 to 2 | Not started |
| M17 | Users | Five-person user test with adults (18+), with consent, at least two of them drivers or commuters who deal with floods; watch without helping, take notes, make one change | Nov 1 to 3 | Not started |
| M18 | Evaluation | Fix the release-gate numbers in `eval/rules.md` | Before Nov 3 | Not started |
| M19 | Evaluation | Keep the sealed files in an encrypted archive only Rene can open | Oct 30 | Not started |
| M20 | Copy | Read every Taglish line, refusal and safety line as a native speaker | Nov 2 to 3 | Not started |
| M21 | Privacy | Approve the privacy policy and consent text; confirm NPC registration isn't required | Nov 1 to 2 | Not started |
| M22 | Repo | Choose the repo licence; credit third-party code and data; add "Not affiliated with MMDA"; use no MMDA logo | Nov 3 | Not started |
| M23 | Video | Record screen and phone footage with our own voice-over; open with a line that everything shown was built during the event; use only consented footage and royalty-free music; show the first cut to three people who haven't seen Lusot and cut whatever they can't recall | Nov 3 to 4 | Not started |
| M24 | Submit | Submit on the Cerebral Valley platform: public repo and 3-minute video link, as a solo entry | Nov 4, 10:00 PM | Not started |
| M25 | Judging | Keep the demo up through the closing ceremony (Nov 10, 1:00 AM Manila); watch the Meta credits and AWS budget emails; be ready for the live final round | Nov 5 to 10 | Not started |
| M26 | Bonus | Post the demo video on X and add the post link on the platform, for the Most Viral award | Nov 4 to 5 | Not started |
| M27 | Bonus | Share the public gallery link for the Community Vote | From Nov 10 | Not started |
| M28 | Stakeholder | Get one real stakeholder (a barangay official, a drivers' or riders' group, or a community flood page admin) to try Lusot and give a one-line quote, with written consent to use it in the video; ask whether their group will use Lusot in the next rain and, if yes, get that in writing | Nov 1 to 3 | Not started |
| M29 | Rain | Keep a rain kit ready (a phone with Lusot, a tape measure, printed consent forms, boots) and follow PAGASA's thunderstorm advisories for Metro Manila; when a nearby street floods and the lightning has passed, take the Set D ruler checks (M13), ask people there to post real pins, and film the one-person story with a consenting adult. Dry curb only. | Whenever it rains, Oct 27 to Nov 3 | Not started |
| M30 | Video | Write English captions for the whole video, including every Taglish line and the voice-over, and check their timing | Nov 4 | Not started |
| M31 | Accounts | Create the IAM user `rene-dev` (console access, AdministratorAccess, its own MFA); connect the terminal with `aws login --profile lusot` (AWS CLI 2.32 or newer, region ap-southeast-1); check it with `aws sts get-caller-identity --profile lusot`; never deploy as root | Oct 27 to 28, before the first deploy | Done. Evidence: `aws sts get-caller-identity --profile lusot` returns `user/rene-dev`, and the profile region is ap-southeast-1 (Claude, 11:17 PM, Oct 27). MFA is a passkey (plan §24). |
| M32 | Rules | Decided Oct 27: every call runs on the $150 credits (D10). Ask in office hours whether credit-paid calls may carry people's photos; if Meta says no, blur faces on the phone before upload | Oct 27 to 30 | In progress. The question is open in #office-hours with no answer from Meta as of 10:30 PM, Oct 27 (plan Table 27). The Billing page confirms "may be used for product improvement". **The phone blur in this row is superseded:** D12 and C20 blur faces on the server before every Meta call, on from the start, whatever the answer. **New fact (MS1 probe, Oct 28):** SAM keeps each photo at Meta by default (`store: true`), once per phrase. MS3a tries `store: false` (C85). Meta's retention, with no fixed period, is disclosed whatever `store` does (plan §13); C85 decides only the extra line that Meta stores a copy of each request. |
| M33 | Bonus | In the submission form, also enter Lusot for the Best agentic use case prize ($5,000), pointing to Ask Lusot's tool calls and the self-check if it is built | Nov 4 | Not started |

## 3. Weakness register

From Table 11 of the plan. Update each row as its check passes.

| ID | Area | Weakness | Fix | Verified by | Status |
|---|---|---|---|---|---|
| W1 | Measurement | Bow wave around moving vehicles | Leave moving vehicles out; in clips, SAM tracks show motion | Set A: parked versus moving photos | Not started |
| W2 | Measurement | Tire sizes differ by vehicle | Classify the type; tire-code ranges; "unknown" gets 23 to 28 in | Set B error per vehicle type | Not started |
| W3 | Measurement | A model eyeballing the waterline | Muse Spark names landmarks only; geometry measures; drop wheels whose readings differ by more than one level | Set B error; landmark versus geometry ablation | Not started |
| W4 | Measurement | Reflections make wheels look whole | Cut masks at the waterline; optional mirror check | Unit test; Set A photos with reflections | Not started |
| W5 | Measurement | 3 to 5 in error is wider than the 2 to 3 in gaps between low levels | Lead with passability; round deeper; publish a range | Passability and within-one-level agreement | Not started |
| W6 | Measurement | Water above the wheel hides the main reference | Use people and the body waterline; "at least tire deep" | Set A photos at tire depth or deeper | Not started |
| W7 | Measurement | Steep angles, low resolution, small wheels | Drop wheels under about 40 px; skip geometry when the axis ratio is under 0.5 | Set B by angle and size | Not started |
| W8 | Measurement | Waves, splashes and other cars hide the waterline | Median water edge; refuse when ragged | Coverage on the splash subset | Not started |
| W9 | Measurement | Wet road mistaken for floodwater | `standing_water` must be yes and the water must touch the reference | A-neg: "no flood seen" or a refusal | Not started |
| W10 | Measurement | Curb depth differs from mid-road depth | "At this spot"; prefer references near the road centre | Copy review | Not started |
| W11 | Claims | Vehicle-specific passability overclaims | Only MMDA's three classes | Output schema has no vehicle verdict | Not started |
| W12 | Claims | One photo is one spot, not a route | "At this spot"; deepest report within 300 m | Ask Lusot test questions | Not started |
| W13 | Claims | Night, rain and blur | Quality check on the phone and the server, then refuse | Correct refusals on the dark and blurry subset | Not started |
| W14 | AI | Muse Spark's visual judgment is unproven on these photos | Test on Set A development photos and Set C; fall back to "unknown" | Vehicle-type confusion matrix | In progress: MS1's probe got schema-valid answers on 5 STURM photos of 5. The confusion matrix waits for Set A development photos. |
| W15 | AI | Text in a photo could steer the model | Schema-only output; prompt says to ignore text; geometry decides | Test photos with misleading signs | Not started |
| W16 | AI | Rate limits and outages | SQS buffer, concurrency 5, backoff with jitter | Load test: 50 uploads in a minute | Not started |
| W17 | Evaluation | MMDA labels are eyeballed and use off-scale words | Call it agreement; fix the label mapping in advance | Evaluation report | Not started |
| W18 | Evaluation | Leakage: one flood event in both sets | Split by event (same place and day) | Split audit script | Not started |
| W19 | Evaluation | About 20 sealed photos is a small sample | Report sample sizes; call results indicative | Evaluation report | Not started |
| W20 | Product | Old or reposted photos | In-app capture only; captured within 15 minutes | Try a gallery photo and an old photo | Not started. MS1's final review found that on desktop the browser's file picker stamps a fresh capture time on an old photo. MS5 reads the EXIF time before the canvas strips it, or refuses picker sources. |
| W21 | Product | Fake or prank reports | Photo required, device rate limit, flag button, report counts | Manual abuse test | Not started |
| W22 | Product | GPS error puts a pin on the wrong street | 50 m accuracy or better; 100 m nudge | Field test on two streets | Not started |
| W23 | Safety | A pin treated as a safety guarantee | Never "safe"; show time and basis; link MMDA advisories | Copy review | Not started |
| W24 | Product | Weak signal during storms | Compress to about 300 KB; retry uploads | Throttled-network test | Not started |
| W25 | Privacy | Faces and plates in photos | Blur, delete originals, 7-day retention, consent | No raw photo left in S3 after analysis | In progress:<ul><li>MS1 blurs faces before any Meta call (C37) and stores no photo.</li><li>The bucket held 0 objects at 2:46 PM, Oct 28, after the web, emulator and smoke runs.</li><li>The dead-letter queue keeps 7 days (R49).</li><li>Plates wait for MS3.</li><li>The face blur's known misses: faces under about 10 px, strong profiles, partly covered faces and night shots.</li></ul> |
| W26 | Security | API key exposure | SSM, server-only calls, CORS, 5-minute links | Secret scan of the repo and the APK | In progress:<ul><li>gitleaks and the account-ID scan run in `npm run check` and in CI, clean on Oct 28.</li><li>The MS1 APK's bundle holds no key and no Meta host.</li><li>A full `claude-security` scan comes before the submission.</li></ul> |
| W27 | Operations | DynamoDB TTL deletes in the background | Filter on `visibleUntil` for every map read | Query test with an expired item | Not started. MS1's final review found that `GET /reports/{id}` doesn't filter expired items either. MS4 and MS5 extend the filter to that read and to the privacy wording. |
| W28 | Operations | Free plan suspends after 6 months or when credits run out | Upgrade if needed; $5 budget alert | Calendar reminder | Not started |

## 4. Decision log

| Date | ID | Decision | By |
|---|---|---|---|
| Oct 26 | D1 | Superpowers is the main workflow, with ui-ux-pro-max, frontend-design, Context7 and the Karpathy guidelines; milestones, each with its own spec and plan | Rene |
| Oct 26 | D2 | Social-media data is collected by hand by Rene; Claude processes it and automates only news, datasets and spec pages | Rene |
| Oct 26 | D3 | Foundation: official generators plus `aws-samples/serverless-patterns`, credited, in a new repo after kickoff | Rene |
| Oct 26 | D4 | Tracking lives in repo docs only (this board plus per-milestone spec and plan) | Rene |
| Oct 26 | D5 | Build and submit as a solo entry | Rene |
| Oct 26 | C1 to C8, G1 to G5 | Claude's defaults and gap fixes, listed in the build design §6 and §9 | Claude (pending Rene's approval) |
| Oct 26 | B1 to B6 | Builder-check answers: local development calls allowed; outcome rule fixed in advance; sealed scope covers Set B final; M8 records vehicle type; M9 records place and time (design §17) | Claude (pending Rene's approval) |
| Oct 27 | D6 | Obsidian: the project folder is the vault; `.obsidian/` stays out of git; a dated work log in `docs/log/` | Rene |
| Oct 27 | D7 | Autonomy: Claude proceeds on stated defaults and logs them. With Rene's `lusot` profile and `MODEL_API_KEY`, Claude runs probes, tuning and deploys. Making any code public, spending beyond the budget alerts, the sealed run and the submission wait for Rene (routine private pushes don't, per D11). | Rene |
| Oct 27 | D8 | Backend first. UI shells may start Oct 29, but only alongside backend work. Rene tests on Android and iOS (the web app in Safari). | Rene |
| Oct 27 | D9 | The development repo is private; Rene provides a separate, clean repository for the submitted version | Rene |
| Oct 27 | D10 | Every Meta call runs on the $150 credits, disclosed in the consent notice and privacy policy. ~~Faces are blurred on the phone if the organizers rule out people's photos (plan §13).~~ Superseded by D12 and C20: faces are blurred on the server before every Meta call, on from the start. | Rene |
| Oct 27 | D11 | Routine pushes to the private repo don't wait for Rene; making any code public does | Rene |
| Oct 27 | D12 | If M32 is a no, faces are blurred before every Meta call (all uses). Claude's reading, C20: built before tuning and on from the start. | Rene |
| Oct 27 | D13 | People count fully: a standing adult can set the level alone | Rene |
| Oct 27 | D14 | Dry streets can read "no flood seen"; photos outside Metro Manila are analysed but never pinned | Rene |
| Oct 27 | C3, C4, C6 to C21 | Claude's calls from the Oct 27 plan updates, the fact check and the second builder check (build design §6, §19) | Claude (pending Rene's approval) |
| Oct 28 | Approval | Build design approved with fixes F1 to F6 (design §20): the face blur moves into MS1, probes use STURM-FloodDepth only, and stale lines are corrected | Rene |
| Oct 28 | D15 | Overnight, Claude keeps going on any work that doesn't need Rene, across milestones; the D7 gates still hold | Rene |
| Oct 28 | D16 | Pushes and full checks at the end of each milestone; CI parked until the `workflow` scope is granted (T7). This was Claude's reading of "Run every only after milestones for now to maximize time", and Rene confirmed it at about 10:05 AM. | Rene |
| Oct 28 | D17 | AWS alarms email the address on Rene's Claude account, passed at deploy time and kept out of the repo | Rene |
| Oct 28 | D18 | Model routing for this project only: Sonnet 5.5 at xhigh for easy tasks, Opus 5.5 at max for medium and up, Fable 5.1 at max only when Opus can't do it; workflows only when needed, at most 50 agents | Rene |
| Oct 28 | D19 | Refusal copy: plan §9's line drops "safe" and reads "Retake it from a dry spot…". The English line is confirmed; the Taglish draft waits for M20 | Rene |
| Oct 28 | D20 | Three Claude windows work at once, each in its own git worktree: Window 1 runs MS1 Tasks 10 to 12 and owns the log and this board until MS1 closes, Window 2 runs Tasks 4 and 5, and Window 3 reviews the MS3a plan and builds MS3a. Each window runs one implementer at a time | Rene |
| Oct 28 | MS3a answers | At 1:30 PM Rene took the recommended option on the open MS3a questions (relayed by the tracker): C51 stays as written, and C76 and C81 are accepted | Rene |
| Oct 28 | D20, extended | A fourth window (about 1:40 PM). Window 4, on `w4-independent`, writes the MS6 evaluation spec, plan and harness, plus the privacy and consent drafts. Window 2's second job, on `next-specs`, writes the MS2 and MS4 specs and plans. Both branches add new files only and merge into `main` after MS1 closes. | Rene |
| Oct 28 | R44, R47, R49 | Claude's MS1-close rulings, confirmed under Rene's delegation to the recommended option (relayed by the tracker session, about 2:30 PM). He can overturn any of them:<ul><li>R44: the automation suggestions wait for MS5 and MS7.</li><li>R47: no `sam init` or serverless-patterns starter was used, which amends D3 and design §13.</li><li>R49: the dead-letter queue keeps 7 days, not 14.</li></ul> | Rene (delegated) |
| Pending | R3, R6, R7 | UI language and visual direction; consented demo photos and fallbacks; how the submission repo gets its history | Rene |
