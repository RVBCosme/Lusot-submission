# Lusot build design: how we deliver the plan

- **Date:** Oct 26, 2026 (Manila); **v2 on Oct 27** for the plan update and Rene's answers
- **Status:** **Approved by Rene on Oct 28, 2026 (12:08 AM), with six fixes** (§20). Builder-checked Oct 27 (§19).
- **Covers:** the whole hackathon build, milestones MS0 to MS10

## 1. What this document is

The plan (`Lusot Hackathon Build Plan.pdf`, last updated Oct 27, 2026 at 10:31 PM, 79 pages) already designs the product: the pipeline, output rules, data model, evaluation and schedule. This document doesn't redesign any of that. It decides **how we deliver it**:

- the milestones and what each one must produce
- the working process and tools
- how progress is tracked
- the code foundation
- how data is gathered within platform rules
- fixes for the gaps found when the plan was double-checked (Oct 26 and Oct 27)

Where this document says nothing, the plan rules. The hackathon's own rules override both. Those are the Official Rules and Event Waiver on the event page (dated Oct 25), the participant guide, and the Discord #rules (plan §2).

## 2. Intent

- Build Lusot as planned and on time, to a standard that can reach the top 5 of up to 20,000 accepted participants. Every judging criterion needs evidence that a judge can see or check.
- Rene should be able to see at any moment what is done and what is next. Each milestone has its own spec and its own implementation plan, and tasks are ticked only after they pass verification.
- Work runs through the Superpowers process. UI work also uses ui-ux-pro-max and frontend-design, library docs come from Context7, and coding follows the Karpathy guidelines.
- **Backend first** (Rene, Oct 27). The working core and the backend come before UI polish.

## 3. Goals, non-goals, anti-goals

**Goals**
1. A working core in the cloud by Oct 29: upload in, landmark-only result out (plan §8, §20 Phase 3).
2. Everything built by Nov 3. Submitted by Nov 4, 10:00 PM Manila time, with a live URL, an APK, a video, a README and the evaluation report (§18).
3. A traceable record: specs, plans, ticks with evidence, a decision log and a dated work log.
4. Every number or claim in the video, README and report traces to a checked source (see the Oct 27 check, `docs/research/2026-10-27-plan-update-check.md`).

**Non-goals**
- Everything in the plan's "Out of scope" list (§4) and its "Exclude" column (Table 20). That includes a native iOS app.
- Redesigning the product.
- Any nice-to-have before the must-haves are done. Should-haves come after the must-haves they depend on, and each is dropped without harm if it isn't solid by its date (§4).

**Anti-goals** (failures even if the app works)
- Breaking a hackathon or platform rule:
  - code before kickoff
  - reuse against a licence
  - scraping social platforms
  - a submission whose new work judges can't tell apart
- A leaked key, a stored unblurred photo, an account ID in the repo, or a pin that says "safe" or advises crossing.
- Tuning on the sealed set, or a headline number without its sample size.
- Process that costs more time than it saves: bloated specs, or re-planning settled questions.

## 4. Constraints

**Dates** (Manila time)

| Event | When |
|---|---|
| Kickoff | Oct 27, 12:00 AM (the event portal stores 1:00 AM; either way it has passed) |
| Office hours (Discord) | Weekdays 10:00 to 11:00 PM until Oct 30; 11:00 PM to midnight from Nov 2 |
| Our submission target | Nov 4, 10:00 PM |
| Hard cutoff | Nov 5, 10:00 AM (Nov 4, 9:00 PM ET) |
| Judging | Nov 5 to 9 (the public rules say Nov 4 to 8 ET) |
| Closing ceremony and finals | Nov 10, 1:00 AM (Nov 9, 12:00 PM ET) |
| Bonus and community-vote results | "On or about November 10" (public rules); Nov 16 or 17 (plan, from the guide and Discord) |

The rules say "Dates may be subject to change"; recheck the event page before each milestone.

**Rules.** Plan §2 summarizes the participant guide, the Discord #rules and, since the 10:31 PM update, the Official Rules and Event Waiver. That includes ownership: Rene must own all rights to what he submits, nothing shared is confidential, and the organizers get a perpetual, irrevocable licence. Rene read them on Oct 27 (M4, done). The public rules also say:
- **Credits:** the $150 of Meta credits are "valid for a 10-day development window". The plan doesn't mention this yet.
- **Open source:** allowed if its licences are followed and the project "enhances or builds upon" it.
- **Payout:** needs the signed waiver and a W-8BEN.

**Budget**
- **Meta:** $150 of credits, enough for about 5,000 photos as planned. **Every call runs on the credits** (D10). If the 10-day window ends before judging does, judging traffic bills the card instead. The stop switch, the $100 spend alert and a daily billing check stay on.
- **AWS:** the free plan, with the full $200 of credits (all five activities done Oct 27, valid until Oct 27, 2027) and a $5 budget alert. Use Singapore prices: HTTP API is $1.25 per million requests.

**People.** Rene and Claude, as a solo entry. Rene tests on an Android phone and an iPhone; on iOS that means the web app in Safari.

**Accounts** (plan §24 as of 10:31 PM, Oct 27, plus Claude's checks)
- **AWS:**
  - The account exists with root MFA.
  - The IAM user `rene-dev` signs in with a passkey (M31, done). Claude checked it at 11:17 PM: `aws sts get-caller-identity --profile lusot` returns `user/rene-dev`, region ap-southeast-1.
  - **Lambda concurrency in Singapore stays at 10:** AWS declined 1,000 on Oct 27 for lack of usage history (M2, done). Plan Table 18 has the fallback.
  - The credit activities left a tutorial Lambda (`explore-awswebapp`, N. Virginia) and a security group, which cost nothing.
- **Meta:** the credits are active and one API key exists. Claude read the Billing page at 9:35 PM: $150 of free credits in use, a card on file, and an email alert at $100 monthly spend, so M3 is done. The page states "While using free credits your content may be used for product improvement" and offers a team-wide "Stop using free credits" switch (M32).
- **Region check:** done at 9:30 PM. AWS Settings lists no projects, so this is a standard account (not a Sydney-pinned "new experience" project), and ap-southeast-1 works (C9).

**Machine** (checked Oct 26, re-checked Oct 27 at about 9 PM)

| | |
|---|---|
| OS | Windows 11 |
| Installed | git 2.48, GitHub CLI 2.100 (signed in as RVBCosme), Node 22.22, npm 10.9, Python 3.10.11 |
| Installed Oct 27 (verified 11:17 PM) | AWS CLI 2.38.6; AWS SAM CLI 1.170.0; Android Studio 2026.2 with Android SDK 36, build-tools 36.0.0 and platform-tools 37.0.1; WSL 2.7.14; Docker Desktop 4.97 (engine 29.9.2; `hello-world` runs; WSL capped at 6 GB). `JAVA_HOME` is JDK 17. |
| Disk | C: is the only drive, with 105 GB free |
| Memory | 15.7 GB RAM. Claude Code stopped a background job for low memory on Oct 26, so keep heavy builds apart. |
| GitHub | The connector in Claude Code fails with a 401 error; the GitHub CLI works |
| Availability | The laptop stays on throughout the hackathon (Rene, Oct 27), so work can run overnight |

## 5. Decisions Rene made

| # | Date | Topic | Decision |
|---|---|---|---|
| D1 | Oct 26 | Workflow | Superpowers is the main process. UI work uses ui-ux-pro-max and frontend-design, library docs come from Context7, and code follows the Karpathy guidelines. The work is split into milestones, each with its own spec and implementation plan. |
| D2 | Oct 26 | Social-media data | Rene collects MMDA and Quezon City posts by hand, as plan M7 says. Claude prepares the log and handles matching, event splits and checks. Claude automates only public news articles, open datasets and spec pages. |
| D3 | Oct 26 | Code foundation | Open-source starters: the official generators (Vite React-TS, Capacitor, AWS SAM) plus wiring adapted from `aws-samples/serverless-patterns`, credited. They go into a new repo, created after kickoff. |
| D4 | Oct 26 | Tracking | Repo documents only: a spec and a checkbox plan for each milestone, plus `docs/PROGRESS.md` as the board. Nothing is mirrored into GitHub Issues. |
| D5 | Oct 26 | Team | Solo entry: Rene is the only contributor. |
| D6 | Oct 27 | Obsidian | The project folder itself is the Obsidian vault: `Lusot-Staging` now, the repo once it exists. Docs, decisions, ticks and a dated work log live once, in git. `.obsidian/` stays out of git. |
| D7 | Oct 27 | Autonomy (answers R4 and R5) | While a milestone spec waits for approval, Claude goes ahead on its stated defaults and logs each one. After M31, and once `MODEL_API_KEY` is a Windows user variable, Claude's shell runs the Meta probes, tuning and deploys with the `lusot` profile. It never displays the key, and Rene re-runs `aws login` when its 12-hour session ends. **Always wait for Rene:** making any code public (D11), spending beyond the budget alerts, the sealed run and the submission. |
| D8 | Oct 27 | Priorities (answers R1) | Backend first. UI shells on mock data may start Oct 29, but only alongside the backend work, never delaying MS1, MS3 or MS4. Rene tests on Android and on iOS (the web app in Safari). |
| D9 | Oct 27 | Repos | The development repo stays private. Rene will provide a separate repository for the submitted version, so it is clean. How its history is carried over is open (R7). |
| D10 | Oct 27 (plan §13) | Credits and privacy | Every Meta call runs on the $150 credits. The consent notice and privacy policy say plainly that Meta receives each photo before Lusot blurs it and may use it to improve its products. Rene still asks the organizers whether credit-paid calls may carry people's photos (M32, open in #office-hours). If they say no, faces are blurred before every Meta call (D12, which replaces the phone-only blur). This replaces the plan's earlier fallback of card-paid calls. With the face blur on (C20), the disclosure says Meta receives each photo with faces already blurred. |
| D11 | Oct 27 | Pushes (clarifies D7) | Claude creates the private `RVBCosme/lusot` and pushes branches routinely, so CI and Amplify run on every push. Anything that makes code public (the submission repo, a visibility change) still waits for Rene. |
| D12 | Oct 27 | Faces and Meta (M32 fallback) | If the organizers say credit-paid calls must not carry people's photos, a non-Meta detector blurs faces before every Meta call. That includes live uploads, samples, demo pins, tuning and the sealed run. **Claude's reading (C20):** the blur is built in MS1, before the first Meta call (fix F1, §20), and is on from the start, so the probe and tuning data stay valid whichever way M32 goes. |
| D15 | Oct 28 | Overnight work | While Rene sleeps, Claude keeps going on any work that doesn't need him, across milestones ("Anything that you can continue working on, so even if you can finish all tonight you can do it"). The D7 gates still hold. |
| D16 | Oct 28 | Pushes and CI (Claude's reading, confirmed by Rene on Oct 28 at about 10:05 AM) | Rene's answer: "Run every only after milestones for now to maximize time." **Claude's reading:** for now, push and run the full checks at the end of each milestone, not after every task. The GitHub CLI lacks the `workflow` scope, so the CI workflow stays parked outside `.github/workflows/` until Rene runs `gh auth refresh -h github.com -s workflow`. Then it moves into place and runs on every push, as plan §19 asks. |
| D17 | Oct 28 | Alarm email | AWS alarms (the dead-letter queue and others) email the address on Rene's Claude account. It is passed at deploy time from a git-ignored config and never written into the repo. |
| D18 | Oct 28 | Model routing (this project only) | Subagents get Sonnet 5.5 at xhigh effort for easy tasks and Opus 5.5 at max effort for medium and harder ones. Fable 5.1 at max effort is used only when Opus can't do the task. Workflows are used only when needed, with at most 50 agents. Rene's global settings stay unchanged. |
| D19 | Oct 28 | Refusal copy | Plan §9's refusal line drops the word "safe", which `CLAUDE.md` bans: "I can't tell from this photo. Retake it from a dry spot with a parked car's wheel or a person standing still in view. Don't step into the water or the road." Rene confirmed the English line. The Taglish draft in the Oct 28 log waits for his copy review (M20). |
| D20 | Oct 28 | Three parallel windows | From about 10:30 AM on Oct 28, three Claude windows run at once, each in its own git worktree and branch. Window 1 finishes MS1 (Tasks 10 to 12) in the main folder and owns the log, the board and the deploys until MS1 closes. Window 2 runs MS1 Tasks 4 and 5. Window 3 reviews the MS3a plan, builds the MS3a tasks that need nothing from Tasks 4 and 5, and builds the rest after MS1 closes. Each window runs one implementer at a time (R1), and the windows pass notes through git-ignored handoff files. |
| D13 | Oct 27 | People as references | People count fully. A standing adult can set the level alone. With wheels in the photo too, the deepest believable reading wins, and a gap of more than one level means refusal. Wading adults count only when no adult is standing still. |
| D14 | Oct 27 | Dry streets and photos outside Metro Manila | An empty water mask still goes to Muse Spark, so a dry street can read "no flood seen" instead of a refusal. This changes plan §7 step 2 and costs about $0.004 more per such photo. Photos taken outside Metro Manila are analysed and shown to the person, but never pinned. |

## 6. Claude's calls (defaults that Rene can override)

| # | Call | Why |
|---|---|---|
| C1 | TypeScript for the app and the Node Lambda (built with AWS SAM's esbuild support), Tailwind CSS, and Playwright for end-to-end tests next to pytest and Vitest. The analysis container uses a current AWS Lambda Python base image (3.12 or newer), confirmed at MS1. | Types catch mistakes across the app–API boundary. Tailwind fits the output of ui-ux-pro-max. End-to-end tests prove the "whether it works" criterion. |
| C2 | Milestones are the plan's runbook phases, named MS0 to MS10. | They match §20 and Figure 5. The "MS" prefix avoids a clash with the plan's manual actions (M1 to M32) and weaknesses (W1 to W28). |
| C3 | `Lusot-Staging` holds the planning documents. After Rene approves this design, the private development repo is created at `C:\Systems\Lusot\lusot` (GitHub `RVBCosme/lusot`, private, per D9). Its first commit brings these documents in, but not the plan. | The git history starts cleanly after approval. |
| C4 | **The plan never enters any repo.** The PDF and its UTF-8 text copy stay in `C:\Systems\Lusot\Lusot-Staging\` (outside git), and `CLAUDE.md` points to them by absolute path. No account ID, Team ID or console link is ever written into repo files. Proposed Oct 27; Rene didn't object. | Plan §24 lists the AWS account ID and the Meta Team ID and says the plan stays out of the public repo. This answers R2. |
| C5 | Fixes G1 to G5 (§9 of this document). | These are gaps found in the double-checks. |
| C6 | At MS1, add deny rules to `.claude/settings.json` on top of the encrypted archive (M19). They cover:<ul><li>`eval/sealed/**`</li><li>every `sealed` folder under `C:\Systems\Lusot\lusot-data\` (Set A, A-neg and Set B final, plus Set D)</li><li>the archive file itself</li></ul> | A second layer of protection for everything that is sealed, wherever it lives (see B4). |
| C7 | After scaffolding at MS1, run `claude-code-setup:claude-automation-recommender` once, and add a local pre-commit secret scan. The tool is confirmed with Context7 at MS1. | The repo is private, so GitHub's free push protection doesn't apply, and a scan before each commit is the guard. |
| C8 | Private data lives outside the repo, in `C:\Systems\Lusot\lusot-data\`: Set A, A-neg, Set B and Set D photos, consented photos and Set C downloads. Evaluation code finds it through `LUSOT_DATA_DIR`. | Set A photos must never reach a repo. |
| C9 | **AWS details from the Oct 27 fact check:**<ul><li>Region check passed on Oct 27: AWS Settings lists no projects, so the account isn't pinned to Sydney.</li><li>No `ReservedConcurrentExecutions`: the account limit stays at 10 (AWS declined 1,000). The SQS event source's `MaximumConcurrency` (5) caps analysis, the API keeps the other 5, and the app retries a throttled call once (plan Table 18). Ask AWS again after a week of real use.</li><li>Automation passes `--no-cli-pager`: the AWS CLI's Windows pager hangs captured output (seen Oct 27).</li><li>AWS SAM CLI 1.148 or newer, so it reads `aws login` credentials.</li><li>`sam deploy --resolve-image-repos`.</li><li>Docker Desktop builds the image locally; GitHub Actions is the fallback if WSL or Docker misbehave.</li></ul> | AWS docs, read Oct 27. |
| C10 | **Meta API details from the Oct 27 fact check:**<ul><li>structured output sets `strict: true` inside `text.format` (it is off by default)</li><li>SAM requests stream, with background mode plus polling as the fallback for 504 timeouts</li><li>clips are MP4, uploaded with `expires_after` of 3,600 s and deleted after analysis</li><li>voice is recorded as WAV (mono, 16-bit, 16 kHz) in the app, because file transcription accepts only WAV</li></ul> | dev.meta.ai, read Oct 27. |
| C11 | **Other details from the Oct 27 fact check:**<ul><li>Nominatim is called only from the API Lambda, with a cache, a server-side off switch and visible attribution, because its limits apply per application.</li><li>The app uses Capacitor 8.1's `takePhoto` (`getPhoto` is deprecated).</li></ul> | OSMF policy; Capacitor docs. |
| C12 | Day-1 Meta probe photos come only from **STURM-FloodDepth** (CC BY 4.0 for the whole record) and consented photos. No Set A candidates and no news photos. **FloodDET's images keep the terms of their source datasets** (verification notes §5), so none goes to Meta until each source's licence has been checked (fix F2, §20). | Set A candidates could end up sealed, and news photos aren't ours to use. |
| C13 | **Plan points that need a decision:**<ul><li>The Mirage G4 uses 185/55R15 (Mitsubishi PH's own page, G5). A sidewall photo is still welcome.</li><li>The stakeholder quote (M28) is not required for MS5 to count as done.</li></ul>(An earlier bullet kept M4 in progress; M4 has been done since the 10:31 PM plan, fix F3.) | Plan Table 7 and §23 still say "to measure". §4 makes the stakeholder quote a should-have. |
| C14 | **Public wording carries the Oct 27 corrections:**<ul><li>"More than 500 flood incidents within 24 hours" (not "the July 2025 monsoon").</li><li>"MMDA's 7 gauge levels plus 2 off-scale levels".</li><li>No MDPI figure is quoted until it is read in a browser.</li></ul>Rene may also update the PDF. | A judge can check each of these. |
| C15 | **Labels printed on Set A images:** Rene crops them off at collection, recorded in a new `label_in_image` log column. A photo with the label still visible is excluded, under a reason written into `eval/rules.md` §9 before any result. | Muse Spark reads text in images. W15's prompt protects the product, not the evaluation. |
| C16 | **The Meta key is the one resource outside the template.** CloudFormation can't create `SecureString` parameters.<ul><li>At MS1, Claude stores the key once with a short boto3 script that reads `MODEL_API_KEY` and never prints it. A CLI argument would show in process lists.</li><li>The template references the parameter by name and grants `ssm:GetParameter` with decryption.</li><li>The stop-switch flags stay in the template as plain strings.</li></ul> | AWS CloudFormation docs (via Context7, Oct 27). |
| C17 | **Scoring and display of edge cases:**<ul><li>"No flood seen" on a flooded Set A photo counts as an underestimate.</li><li>"At least tire deep" scores as tire.</li><li>Pins carry a `levelIsFloor` flag, so the app says "at least tire deep".</li></ul> | Keeps the most dangerous misses in the headline rate. |
| C18 | **Consent for donated photos (M9)** covers all four uses: Meta on the credits, a lasting demo pin, the video and X post, and the organizers' licence. The draft message is in the Set A guide for Rene to approve. | The rules require rights to everything submitted. |
| C19 | **Guards on the geometry outcome rule:** coverage may fall by at most 10 points, and passability agreement by at most 5 points. Proposed in `eval/rules.md` §8, for Rene to fix with M18 by Nov 2. | Underestimation alone can't catch what geometry gets wrong. |
| C20 | **The face blur is the pipeline's first step,** in Python:<ul><li>It uses OpenCV's YuNet face detector. **It is built and tested in MS1, before the first Meta call**, and the model and its licence are confirmed then (fix F1, §20).</li><li>The analysis Lambda and the laptop tools share it. One implementation covers live uploads, samples, demo pins, tuning and the sealed run, so the phone needs no detector.</li><li>It is on from the start.</li><li>SAM's `face` request stays as a second pass before storage.</li><li>Plates still reach Meta, and the consent and privacy text say so.</li></ul> | The simplest way to meet D12 before tuning starts. |
| C21 | **A `private` mode for photos taken outside Metro Manila,** next to live, sample, eval and demo. The analysis runs and the result shows on the phone, but never reaches the map or the feed. The usual device limits apply. The Metro Manila test uses an NCR boundary polygon; its source and licence are confirmed at MS4. | D14. |

## 7. Questions only Rene can answer

Listed most important first. R1, R2, R4 and R5 are answered (D7, D8, C4).

| # | Question | Needed by | Default if unanswered |
|---|---|---|---|
| R6 | How many consented flood photos, with **where and when** each was taken, are secured or promised (M9)? If they run short, which fallbacks are acceptable? **Recommended:** (a) clearly labelled synthetic samples from Set B composites for the sample button; (b) a clearly labelled real puddle beside a parked car (Set D style) for the video's capture scene. Never pass staged footage off as a real flood. | MS4 (Oct 31) | Fallbacks (a) and (b), labelled |
| R7 | How does the submitted repository (D9) get its history? **Recommended:** push the private repo's full history into it, optionally dropping development-only files with `git filter-repo` while keeping commit dates. A single fresh commit would hide when the work was done, and the rules disqualify a project if judges can't tell what is new. | MS8 (Nov 3) | Full history, nothing dropped |
| R3 | UI language (English, Filipino or Taglish) and the visual direction. | When UI shells start (Oct 29 at the earliest, D8) | Asked in the MS5 brainstorm, with mockups |

Reminders from the plan's own list:
- fix the release-gate numbers before the sealed run (M18)
- follow the credits question in #office-hours by Oct 30 (M32)
- enter the Best agentic use case prize in the submission form (M33)

## 8. Milestone map

Every milestone has two files:
- a spec: `docs/superpowers/specs/YYYY-MM-DD-msN-<name>-design.md`
- an implementation plan: `docs/superpowers/plans/YYYY-MM-DD-msN-<name>.md`

Specs are short. Each says which plan sections the milestone implements, what decisions are new, and how acceptance is checked. The milestones with no code (MS0, MS9 and MS10) get the same two files as short checklists.

| MS | Plan phase | Dates (Manila) | What it builds | Done when (the plan's own finish line) | Plan refs | Manual actions |
|---|---|---|---|---|---|---|
| MS0 Prepare | 0 | Oct 26 to 27 | <ul><li>CLAUDE.md; this design; PROGRESS.md; the plan's text copy</li><li>the Set A collection kit; research notes (Meta API, tire sizes, datasets, the Oct 27 plan check); the `eval/rules.md` draft</li><li>the Obsidian vault (D6); the toolchain checklist</li></ul> | Rules read; accounts ready; about 20 candidate photos; evaluation rules written | §2, §20, §24 | M1 to M7, M9, M32, T1 to T6 |
| MS1 Set up | 1 | Oct 27 to 28 | <ul><li>The private repo from the starters (D3, D9), with CI in GitHub Actions running the tests on every push, the pre-commit secret scan (C7) and the deny rules (C6).</li><li>The Region check and the IAM profile (C9, M31).</li><li>The AWS SAM skeleton: HTTP API, S3 (`raw/`, `blurred/`, `overlay/`), SQS with a dead-letter queue, DynamoDB, the $5 budget alert, SSM parameters including the stop switch.</li><li>**The face blur (C20), built and tested before the first Meta call** (fix F1).</li><li>Meta probes on face-blurred STURM-FloodDepth photos (C12): SAM 3.1 and Muse Spark on 5 photos, and the SAM water test on 10 flood photos. Also 10 Taglish voice questions once M12's recordings exist; until then, a check that the WAV format is accepted (C10).</li><li>A bare Capacitor APK that uploads one photo.</li></ul> | The probe returns masks and schema-valid JSON; the stack deploys with one command; a bare APK uploads one photo from a real phone | §5, §16, §17, §19 | M1 to M3, M6, M12, M14, M31, T1 to T4 |
| MS2 Data | 2 | Oct 27 to 30 | <ul><li>Set A: about 50 government-posted photos, split by flood event into about 30 for development and about 20 sealed.</li><li>A-neg (about 15).</li><li>The Set B generator (about 10 cars, about 40 crops).</li><li>Set C downloads; the split audit script; the sealed archive.</li></ul> | All sets frozen; sealed files untouched | §11, Tables 12 and 25 | M7 to M11, M19 |
| MS3 Measurement | 3 | Oct 28 to Nov 1 | <ul><li>**3a, by Oct 29:** the landmark reading and the Table 8 rules, end to end in the cloud.</li><li>**3b, by Nov 1:** pipeline steps 1 to 7 with rim geometry, the reflection cut, the person cross-check and the combining rules.</li><li>**Oct 31:** decide the gated self-check. If yes, build it by Nov 1 with its development ablation.</li><li>**Before tuning starts (Oct 29):** the face blur (built in MS1) runs as the pipeline's first step (D12, C20), and an empty water mask still goes to Muse Spark (D14).</li><li>Cutoffs tuned on development data only. Unit tests.</li></ul> | The core works end to end in the cloud by Oct 29 with a landmark-only result; Set B median error known; tests pass; self-check decided | §4, §7, §8, §9, Tables 5 to 10 | none |
| MS4 Backend | 4 | Oct 31 to Nov 1 | <ul><li>The full pipeline in the container Lambda.</li><li>The reports API with its report-id index; flags; the samples endpoint; the expiry filter; the overlay image.</li><li>The public `GET /pins.geojson` feed (should-have).</li><li>G1 (demo mode); G2 (claim step); the stop switch.</li><li>Analysis-path recovery tests (B2).</li><li>The `private` mode and the Metro Manila check (D14, C21); the `levelIsFloor` flag (C17). The Meta key goes into SSM at MS1 (C16).</li></ul> | Upload to pin works end to end in the cloud, with the full pipeline and its overlay | §5, §12, §13, Tables 14 and 15 | none |
| MS5 App | 5 | Nov 1 to 3 (shells on mock data may start Oct 29, per D8) | <ul><li>Screens: consent with the 18+ check, capture with the quality check, the pin map, pin detail with an overlay that draws itself, refusal, the accuracy page with its sample button, the privacy policy.</li><li>Labelled demo pins (G1); photo to pin under 10 s.</li><li>Clip mode with SAM 3.1 tracking (Nov 1 to 2, should-have, before the freeze).</li><li>The Capacitor Android build. Rene's tests on Android and on iOS Safari.</li><li>The five-person user test; the stakeholder quote if it comes (C13).</li><li>The consent notice and privacy policy carry D10's disclosure, worded for the face blur (C20).</li><li>A private result screen for photos taken outside Metro Manila (D14).</li></ul> | Web URL live; APK installs on a real phone; five people outside the team have tried it; one change came from their feedback | §4, §6, §13, Tables 19 and 21 | M14 to M17, M21, M28 |
| MS6 Ask Lusot and evaluation | 6 | Nov 2 to 3 | <ul><li>**Nov 2:** typed Ask Lusot (spots list, the `get_reports` tool, 300 m and 3 hours, Nominatim through the Lambda), then voice with WAV capture.</li><li>**Nov 3:** the one sealed run, the evaluation report, the per-photo results committed, and `python eval/run_eval.py --from-saved`.</li></ul> | Report includes sample sizes and is rebuilt by one command from the saved results; Ask Lusot answers 10 typed and 10 spoken test questions | §9, §11, §12 | M18, M20 |
| MS7 Harden | 7 | Nov 3 | <ul><li>Load test (50 uploads in a minute). Expired-upload-link test. Stop-switch test.</li><li>Secret scan of the repo and the APK. Dependency audit. Privacy check. Copy review.</li><li>The analysis-path recovery tests have already moved before the freeze (B2).</li></ul> | Every Table 11 check is done or explained | §10, §13, §19 | M20 to M22 |
| MS8 Submit | 8 | Nov 4 | <ul><li>The demo video (Table 19) with English captions; its first cut shown to three people.</li><li>A README that opens with a 60-second judge path, including the one command.</li><li>The write-up in judging-criteria order.</li><li>The submission repository (D9, R7); the submission, entered for the Best agentic use case prize too (M33); the X post.</li></ul> | Submitted by 10:00 PM Manila time | §18, Table 19 | M23, M24, M26, M30, M33 |
| MS9 Judging | 9 | Nov 5 to 10 | Keep the demo live through the closing ceremony (Nov 10, 1:00 AM); watch the alarms, Meta billing (the credits will have run out) and the AWS budget; share the gallery link for the community vote | No downtime and no surprise bills | §19 | M25, M27 |
| MS10 After | 10 | From Nov 10 | Keep it running (upgrade the AWS plan before the 6 months end) or tear it down | Decision recorded | §20, §22 | none |

Rain work (M13 and M29) isn't a milestone. It happens whenever it rains, Oct 27 to Nov 3, from a dry curb only.

**Order of work**
- **Backend first (D8).** MS1's probes and skeleton come before 3a. MS2's development data feeds MS3's tuning.
- MS3's pipeline moves into MS4's Lambda.
- MS4 has to exist before the MS5 screens are wired up. The screen shells may start earlier on mock data, only alongside the backend work.
- MS3, MS4 and MS5 feed MS6.
- MS6's sealed run needs the pipeline frozen. After that, nothing may change how depth is measured (§11, §19).
- MS7 follows MS6, and MS8 follows MS7.

**Pipeline freeze.** Before the sealed run, freeze the model IDs, prompts, schemas, level rules, dataset versions and splits (§11). Clip mode and the self-check ship only if they are finished before the freeze. Three rules come from the builder check:
- **Recovery tests on the analysis path come before the freeze.** Duplicate events, interrupted SAM streams, Lambda timeouts and failed deletions are tested at the end of MS4 or the start of MS6, on development photos. MS7 keeps the load test, the stop switch, the secret scan, the privacy check and the copy review. (B2)
- **The outcome of the sealed run is decided by a rule written down in advance** in `eval/rules.md` §8, not chosen after seeing results. Both configurations (landmark alone, and with geometry) are scored in the one run as the ablation. The self-check is decided on development data before the run. The shipped configuration follows that rule. (B2)
- **After the freeze**, only fixes that can't change any depth output may land, such as error handling and retries. Any fix that could change an output needs one rerun, disclosed in the report with both sets of numbers. (B2)

**When we slip.** If any milestone runs more than half a day late, stop all nice-to-haves (plan §17). Should-haves are dropped next if they aren't solid by their dates. Say what was dropped in the README and the video.

*In the milestone table and in this section, "§N" means a section of the plan. Sections of this document are named explicitly, as in "this document's §17".*

## 9. Gap fixes (Claude's calls; details go into the milestone specs)

All five were rechecked against the Oct 27 plan; G1 to G4 are still needed.

**G1. Demo pins** (MS4, MS5, MS6)
- Add a `demo` mode next to `live`, `sample` and `eval`.
- Demo pins come from consented photos run through the real pipeline, so they are genuine outputs. Each sits at the photo's real spot.
- They appear on the map and in pin detail with a visible "Demo" badge.
- They are exempt from the 3-hour hide and the 7-day delete, which is allowed because the photos are consented. They are never counted in any metric.
- Ask Lusot may cite them, but must label each one "(demo)".
- A script seeds and removes them; nobody edits them by hand in the console.
- *Why:* §19 and Table 21 want labelled demo pins so judges never see an empty map. But Table 14 still lets only `live` pins reach the map and hides them after 3 hours, and the video's España question needs a pin nearby.

**G2. Pay once per photo** (MS4)
- When the SQS message arrives, conditionally move the report from `pending` to `processing` and give it a lease (`claimedAt` plus a claim token).
- If the report is already `done`, `refused` or `failed`, or another live lease holds it, delete the message and stop without calling Meta.
- The final write requires status `processing` and the same claim token. A retry may re-claim a lease that has expired, for example after a Lambda timeout.
- *Why:* the conditional write in §7 step 8 stops a result from being overwritten. The Oct 27 text says it also stops "a second paid analysis", but it can't: two workers can both pay Meta before either writes.

**G3. Set B ground truth** (MS2, MS3)
- In each dry Set B photo, measure the true scale from the whole tire: ground contact to tread top, with the diameter known from the tire code. Don't measure it from the rim.
- Compute each synthetic waterline's true depth in inches with that scale.
- Measure the ratio between the visible rim edge and the nominal rim size on development cars. Report geometry error with and without that calibration, and fix the factor on development cars only.
- *Why:* the rim size in a tire code is the diameter where the tire sits on the rim, slightly inside the visible metal edge. If the ground truth used the same rim assumption as the method, that bias would cancel out of the error and stay hidden.

**G4. Edge cases in the level rule** (`eval/rules.md`, MS2)
- On Raize and Innova tires the hub sits at 13.2 to 13.3 in, which is knee under the level rule, yet Table 8 maps the hub to half-tire (MMDA's own definition).
- "Tire only" can reach about 5.3 in, which is gutter under the level rule, yet Table 8 says below gutter.
- In both cases the passability class stays the same.
- Rule: landmark readings follow Table 8 as written, geometry inches follow the level rule, and when one wheel has both, the deeper reading wins (§7 step 5). `eval/rules.md` records this so scoring stays consistent.

**G5. Gaps in Table 7** (MS0, MS2)
- Look up the Hilux, Mirage G4 and Tamaraw tire codes on public spec pages and record the sources.
- **Result (Oct 26):** see `docs/research/2026-10-26-verification-notes.md` §4.
  - **Mirage G4:** confirmed on Mitsubishi PH's own page. 185/55R15 on every variant, 23.0 in, so it fits `sedan_hatch` (C13). The Oct 27 check confirmed its sales rank (8).
  - **Tamaraw:** 195R14C or 215/65R16 (26.3 to 27.0 in), from one secondary source.
  - **Hilux:** only the new generation's 265/60R18 (30.5 in) was found, from Thai data. The Hilux models already on Manila streets weren't verified.
- **So M11 still photographs the jeepney, tricycle and bus, and adds a Hilux and a Tamaraw.**
- Pickups get wheel measurement only after the Hilux sizes are verified; that is the plan's existing rule. A 30.5 in Hilux tire read as an SUV would come out one level too shallow, so W14's confusion matrix must check pickups.

## 10. Working process

- **Each milestone** follows the loop in `CLAUDE.md`: brainstorm a spec, Rene approves it (or Claude proceeds on stated defaults per D7), write the plan, then build on a branch with test-driven development, review, verification and merge.
- **Execution** defaults to `superpowers:subagent-driven-development`: one fresh subagent per task, with a review between tasks.
- **Skill routing** follows the table in `CLAUDE.md`. All UI work loads both ui-ux-pro-max and frontend-design. All library and cloud API use goes through Context7, or `dev.meta.ai` for Meta's API.
- **A task counts as done** only when its verification command has run and its output is recorded next to the tick.

## 11. Tracking

`docs/PROGRESS.md` has four parts:
1. **Milestones:** MS, dates, status, spec link, plan link, evidence.
2. **Manual actions:** M1 to M32 from the plan plus T1 to T6 (this document's §14), each with its date and status.
3. **Weakness register:** W1 to W28, each with "verified by" and status (Table 11).
4. **Decision log:** date, decision, who decided.

**Work log (D6):** `docs/log/YYYY-MM-DD.md`, one note per working day. Each note records what was done, the evidence, what was decided and what comes next, with links to the files. Obsidian's daily notes point at this folder.

The status words are Not started, In progress, Done, Blocked and Dropped (with a reason). Ticks land in the same commit as the work.

## 12. Data gathering

**Set A**
- Rene collects by hand (D2), using the kit: `docs/data/set-a-collection-guide.md` and `eval/templates/set_a_log.csv`.
- **Only photos that MMDA or a city government posted itself** (plan §11, Oct 27). News lists only help find the official posts.
- Photos are saved privately to `lusot-data/set_a/`, never to a repo.

**Matching and splits**
- Claude works on the log's metadata through scripts: same spot, within 30 minutes, an event ID per place and day, and a split by event (W18).
- **Before the split, Claude opens no Set A or A-neg photo**, because any of them could end up sealed.
- The split script assigns events to development or sealed with a seeded random draw. It writes the sealed rows and photos straight into the encrypted archive (M19).
- **After the split, development photos, their masks and their overlays are open** for tuning and debugging, which is what the plan intends ("tuned on development photos only"). Sealed photos never are.

**Independent labels (M8).** For every reference in Set A, the labeller records two things without seeing Lusot's output (the plan's M8 now says the same):
- the landmark
- the **vehicle type**, using the schema's nine values

The vehicle type feeds the vehicle-type confusion matrix that W14 and Table 18 call for.

**Set B final cars are sealed like Set A** (B4).
- Rene keeps the final cars' photos apart (M10). Claude builds and debugs the generator on development cars only.
- The generator and the G3 ground truth then run on the final cars as one unattended script. The SAM wheel mask in the dry photo gives the whole-tire height, so no hand measuring is needed.
- The script writes straight into the encrypted archive.

**Set D** (only if it rains, M13 and M29) is final only and sealed the same way.

**Claude's own research**
- public news lists of MMDA alerts (as a finder aid only)
- MMDA's list of flood-prone spots
- tire spec pages
- Set C datasets

Sources are cited in `docs/research/`.

**Consented photos** (M9). Each needs:
- a written OK
- a note of who appears in it
- a source note
- **where and when it was taken**

G1 places each demo pin at the photo's real spot, so the location matters. The photos are stored in `lusot-data/consented/`.

## 13. Code foundation (D3 in detail)

- **`app/`:** `npm create vite` (react-ts template), then Tailwind, then Capacitor (core, CLI, Android, camera, geolocation), then `vite-plugin-pwa`, then Leaflet. Versions are confirmed with Context7 at MS1.
- **`backend/`:**
  - `sam init` provides a Node.js TypeScript function for `api/` and a Python container-image function for `analysis/`.
  - The wiring comes from `aws-samples/serverless-patterns`: S3 filtered on `raw/`, then SQS with a dead-letter queue, then Lambda with an event-source maximum concurrency of 5.
  - `amazon-s3-presigned-urls-aws-sam` is archived, so it is a reference only.
- **CI:** `.github/workflows/` runs pytest and Vitest on every push (plan §19).
- **Ignored by git:**
  - `.obsidian/`, `.env*`, `node_modules/`, build output
  - any local data path
- **Credits:** the README lists every starter and library with its link and licence, including `meta-sam-parser` (SAM License).
- **Layout:** as in §20 of the plan, plus `docs/superpowers/`, `docs/research/`, `docs/data/`, `docs/log/`, `docs/PROGRESS.md` and `eval/templates/`.

## 14. Manual actions added to the plan's list

Statuses live in `docs/PROGRESS.md`.

| ID | Action | When |
|---|---|---|
| T1 | Install AWS CLI v2, version 2.32 or newer (M31's `aws login` needs it) | Oct 27, before MS1 |
| T2 | Install AWS SAM CLI 1.148 or newer | Oct 27 |
| T3 | Install WSL first: run `wsl --install` in an admin terminal, then restart. Then install Docker Desktop with the WSL 2 backend, which is needed to build the analysis container image. With 16 GB of RAM:<ul><li>cap WSL 2's memory with a `%UserProfile%\.wslconfig` file (for example `memory=6GB`)</li><li>don't run container builds and Android Studio at the same time; build the APK with Gradle from the command line when possible</li><li>close unused browser tabs during builds</li></ul> | Oct 27 |
| T4 | Install **Android Studio Otter (2025.2.1) or newer**. That is Capacitor 8's minimum (Capacitor docs via Context7, Oct 26), and it bundles the JDK, so no separate JDK is needed. For command-line Gradle builds, point `JAVA_HOME` at its `jbr` folder. Also install the Android SDK 36 platform (Capacitor 8 targets SDK 36, with a minimum of 24). Node 22.21.1 or newer is required, and 22.22 is already installed. | Oct 27 to 28 |
| T5 | Optional: fix the GitHub connector token in Claude Code. The GitHub CLI already works. | Any time |
| T6 | Free disk space until C: has about 60 GB free. It had 41.4 GB on Oct 27, and the toolchain, data and video add an estimated 30 to 40 GB. | Oct 27, before T3 |

## 15. Left to the builder

These are settled in each milestone's spec or plan:
- exact library versions
- prompt wording and the schema files
- cutoff values, tuned on development data only
- UI details within the MS5 visual direction
- test cases beyond the plan's lists
- file names inside each folder

## 16. Self-check

- Every Figure 5 bar and every runbook phase maps to exactly one milestone. The new clip-mode bar (Nov 1 to 2) sits in MS5.
- Every must-have in §4 has a home:
  - capture: MS1 (bare), MS5 (full)
  - pipeline: MS3, MS4
  - level output and the inches gate: MS3, MS6
  - pins and map: MS4, MS5
  - Ask Lusot, typed and voice: MS6
  - accuracy page and sample button: MS4, MS5
  - privacy: MS4 (blur and deletion), MS5 (consent and policy)
  - queue, dead-letter queue and stop switch: MS1, MS4
  - evaluation report: MS6
  - live URL, APK, video and README: MS5, MS8
- Every should-have and gated item has a home:
  - clip mode, the overlay that draws itself, photo to pin under 10 s, the stakeholder quote: MS5
  - the pin feed: MS4
  - the self-check decision: MS3 (Oct 31)
- Every new practice has a home:
  - CI: MS1
  - the one-command rebuild: MS6
  - captions and the X post: MS8
- Every rule in `CLAUDE.md` traces back to the plan, to the Official Rules or to a decision in §5.

## 17. Builder check (Oct 26)

A fresh reviewer read this design, `CLAUDE.md` and the plan as if they had to plan the build alone. It returned six questions, settled as follows.

| # | Question (short) | Pile | Settled as |
|---|---|---|---|
| B1 | Can Meta be called from outside a deployed Lambda (probes, tuning, evaluation)? May Claude hold AWS credentials? | Split | **Answered by the plan:** the day-1 probe (§16) runs before AWS exists, so local development calls are expected. `CLAUDE.md` limits "Lambda only" to the deployed system; local runs read Rene's `MODEL_API_KEY` environment variable, which is never printed or written. **Rene's call:** answered Oct 27 (D7). |
| B2 | What does the sealed run decide, and what may change after it? | Claude's call | The outcome rule is written into `eval/rules.md` §8 before the run. Analysis-path recovery tests move before the freeze. After the freeze, only fixes that can't change outputs; anything else gets one disclosed rerun. See §8 (Pipeline freeze). |
| B3 | What does "Claude never opens Set A photos" cover? | Answered by the plan | Only sealed data is off-limits (M19); development data is for tuning. Before the split, nothing is opened; after it, development photos, masks and overlays are open. M8 also records vehicle type for the W14 confusion matrix. See §12. |
| B4 | Is Set B's final split sealed like Set A's? | Claude's call | Yes. The final cars are kept apart, the generator and ground truth run unattended, and the output goes into the encrypted archive. The C6 deny rules cover every sealed path. See §12 and C6. |
| B5 | How much time does Rene have, and what happens while an approval waits? | Rene's call | Answered Oct 27: D7 and D8. |
| B6 | What do we demo if there's no flood and few consented photos? | Split | **Claude's call:** M9 records also note where and when each photo was taken (§12). **Rene's call:** how many photos are secured, and which labelled fallbacks are acceptable (R6). |

## 18. The Oct 27 plan update

Rene updated the plan on Oct 27. What changed, how it was checked and what the fact check found are in `docs/research/2026-10-27-plan-update-check.md`. This design absorbs it as follows:

- **New in §1, §4 and §5:**
  - the rules and dates
  - the accounts and the machine
  - D6 to D9
- **New or revised in §6:** C3, C4 and C6 to C14.
- **Milestone contents in §8:**
  - should-haves, the gated self-check and the pin feed
  - CI, the one-command rebuild, captions and the X post
  - M26 to M32
- **Data:** Set A is government-posted photos only (§12).
- **Gap fixes:** G1 to G4 are still needed after the update (§9).

**Second update (10:31 PM, 79 pages).** The changed lines were diffed against the 8:35 PM version. New:
- §2 now covers the Official Rules and Event Waiver, including the licence.
- §13 and §23: every call runs on the credits, with disclosure and an on-phone blur fallback (D10).
- Table 18: a new risk, "Lambda limit stays at 10".
- **Table 27:**
  - M2, M3, M4 and M31 are done, and M6 is in progress.
  - M32 is reworded.
  - New M33: enter the Best agentic use case prize ($5,000), from the kickoff stream.
- §24: account notes; the AWS credits are now the full $200.
- §26: the kickoff stream and the Official Rules are now sources.

The opening statistic of the video (Table 19, §3: "over 500 flooding incidents in the July 2025 monsoon") is still uncorrected. The source says 24 hours (see the Oct 27 check).

## 19. Builder check (Oct 27)

A fresh reviewer read design v2, the whole plan text, `CLAUDE.md`, `eval/rules.md` v0.4, PROGRESS.md, the research notes and the Set A guide. It opened nothing under `lusot-data`. It returned eight questions, settled the same night.

| # | Question (short) | Pile | Settled as |
|---|---|---|---|
| K1 | Set A photos with the depth printed on the image | Claude's call | C15 |
| K2a | Do routine pushes to the private repo wait for Rene? | Rene's call | D11: no; only making code public waits |
| K2b | CloudFormation can't create the key's `SecureString` parameter | Claude's call | C16 |
| K3 | Can a person set the level alone? | Rene's call | D13: yes |
| K4 | Scoring "no flood seen" and "at least tire deep" | Claude's call | C17 |
| K5 | What dry streets and photos from outside Metro Manila get | Rene's call | D14 |
| K6 | If M32 is a no, does it cover our own calls too? | Rene's call | D12; C20 for how |
| K7 | The outcome rule watches only underestimation | Claude's call; the numbers are Rene's (M18) | C19 |
| K8 | Consent for donated photos must cover every use | Claude's call | C18 |

## 20. Approval (Oct 28)

Before approving, Rene asked Claude to double-check the previous session's summary against the documents. The check, run from 11:50 PM on Oct 27 to 12:08 AM on Oct 28, confirmed the following:
- D11 to D14, C15 to C21, §19, `eval/rules.md` v0.5 and the Set A kit are as the summary said.
- The PDF on disk is the 10:31 PM version (internal timestamp 14:31 UTC). The text copy has exactly the same words, compared with PyMuPDF.
- No account ID or console link appears in any document bound for the repo.
- AWS (`rene-dev`, ap-southeast-1) and the GitHub CLI are signed in.

It found six problems. **Rene approved the design with these fixes** at 12:08 AM:

| # | Problem | Fix |
|---|---|---|
| F1 | The face blur was scheduled for MS3, but MS1 already calls Meta, and `CLAUDE.md` says no photo reaches Meta unblurred | The blur is built and tested in MS1, before the first Meta call (D12, C20, §8) |
| F2 | C12 called Set C "CC BY 4.0"; only STURM-FloodDepth is | Probes use STURM-FloodDepth only; FloodDET waits for a per-source licence check (C12) |
| F3 | C13 still kept M4 in progress | Bullet removed; M4 is done (plan Table 27) |
| F4 | Stale lines in PROGRESS.md and the Oct 27 log (header time, text-copy size, an unticked finished box, the D7, D10 and M32 rows, "waiting for the PDF", "five" calls for C15 to C21) | Corrected in place, with the old wording struck through where it is history |
| F5 | Claude Code still held the old one-character `MODEL_API_KEY` (`/clear` doesn't restart it); the Windows user variable has the right 48-character key | Until Claude Code restarts, scripts read the key from the user variable and never print it |
| F6 | The GitHub CLI login lacks the `workflow` scope, and there is no SSH key, so a push that adds CI would be refused | D16: CI stays parked until Rene grants the scope |

Rene's other answers are recorded as D15 to D18 (§5).
