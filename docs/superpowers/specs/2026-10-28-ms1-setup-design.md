# MS1 Set up: spec

- **Date:** Oct 28, 2026 (Manila)
- **Status:** Written while Rene sleeps. Claude proceeds on the calls in §4 (D7, D15), and Rene approves in the morning.
- **Implements:**
  - plan §20 Phase 1 (Table 22) and §16 "First steps"
  - the parts of §5 (Table 3), §12 (Tables 14 and 15), §13 and §19 that the skeleton needs
  - build design §8 (MS1 row, as fixed by F1) and the calls behind it: C1, C3, C4, C6, C7, C9, C10, C12, C16, C20, D11, D16, D17

## 1. Goal

MS1 lays the base every later milestone builds on. It also proves early that Meta's three models do what the pipeline assumes. It delivers:
- a private repo with tests and guards
- a deployed backend skeleton that takes one photo upload end to end
- the face blur, working before any photo reaches Meta (F1)
- probe results for SAM 3.1, Muse Spark 1.3 and Muse Voice Transcribe
- a bare APK that captures a photo with its GPS fix and uploads it

## 2. Done when

| # | Check | Evidence |
|---|---|---|
| A1 | The probe returns masks and schema-valid JSON (plan Table 22) | The probe note shows, for 5 photos: <ul><li>SAM 3.1 results for each of the 7 noun phrases (plan §7 step 2), decoded with `meta-sam-parser`</li><li>Muse Spark output that validates against the Table 5 schema in strict mode</li><li>every id it returns exists</li></ul> |
| A2 | The SAM water test ran on 10 flood photos | Overlays reviewed. The probe note says whether the floodwater mask stays apart from submerged wheels. |
| A3 | Every photo sent to Meta was face-blurred first | The Meta client accepts only face-blurred images (C37), and a unit test proves it refuses anything else. The probe log records the blur version. |
| A4 | The stack deploys with one command | `npm run deploy` ends in a successful `sam deploy` and then applies the image lifecycle rule (C38). It needs the one-time local `backend/samconfig.toml`, copied from the example (C31). |
| A5 | Upload works end to end in the cloud | A script and the web build each: <ul><li>get an upload link</li><li>send a JPEG</li><li>see the report reach its MS1 end state (C28)</li><li>find the raw object gone</li></ul> |
| A6 | A bare APK uploads one photo from a real phone | Rene (M14): camera, GPS and upload on mobile data |
| A7 | Repo hygiene | <ul><li>`npm run check` passes.</li><li>The pre-commit scan blocks a planted fake key.</li><li>The deny rules block a read of a sealed path.</li><li>A scan finds no plan text, key or account ID in the repo.</li></ul> |
| A8 | The Meta key is in SSM | A `SecureString`, read back by length only (48) and never printed |

## 3. What gets built

### 3.1 Repo (C3, C4, C6, C7, D11, D16)
- Local path `C:\Systems\Lusot\lusot`; GitHub `RVBCosme/lusot`, **private**. Layout as plan §20 plus design §13.
- **First commit** brings in the staging documents but never the plan or its text copy. Staging then keeps only the plan, the text copy and a pointer `CLAUDE.md` (C29).
- **`.gitignore`** covers:
  - `.obsidian/`, `_attachments/`, `.env*` (except `.env.example`)
  - `node_modules/`, build output, `.aws-sam/`
  - `backend/samconfig.toml` (C31)
  - Python caches and virtual environments
- **Guards:**
  - deny rules in `.claude/settings.json` for every sealed path (C6)
  - a gitleaks pre-commit hook (C24)
  - the CI workflow, parked (C26)
- `CLAUDE.md` is updated for the repo:
  - its "Where things are" table points at repo paths
  - the plan stays at its staging path
  - its "Commands" section is filled in, as `CLAUDE.md` promised for MS1

### 3.2 Backend skeleton (one AWS SAM template, ap-southeast-1)

| Resource | Settings |
|---|---|
| S3 bucket | <ul><li>Private, with all public access blocked; SSE-S3.</li><li>CORS allows POST from `https://localhost` (Capacitor) and the local dev origin.</li><li>Lifecycle: `raw/` expires after 1 day; `blurred/` and `overlay/` after 7 days.</li><li>Object-created events on `raw/` only go to SQS.</li></ul> |
| SQS queue and DLQ | <ul><li>Redrive after 5 receives.</li><li>Visibility timeout at least 6× the analysis Lambda's timeout (180 s, so at least 1,080 s).</li><li>The queue policy lets only this bucket send.</li></ul> |
| DynamoDB `reports` | <ul><li>`pk` and `sk` (Table 14), with the `reportId-index` index.</li><li>TTL on `expiresAt`.</li><li>Provisioned 10 read and 5 write units for the table, and 5 and 5 for the index: 15 and 10 in all, inside the free 25 (plan Table 3).</li></ul> |
| HTTP API and API Lambda (Node.js 22, TypeScript, esbuild) | `POST /uploads` and `GET /reports/{id}` (Table 15), with CORS and stage throttling. **`POST /uploads`:** <ul><li>checks the uploads stop switch</li><li>validates the coordinates and the 15-minute capture window (W20)</li><li>writes a `pending` report (geohash `pk`, Table 14 times, `expiresAt`, `visibleUntil`)</li><li>returns a 5-minute presigned POST (C27)</li></ul> **`GET /reports/{id}`** returns the status through the index. |
| Analysis Lambda (container, Python 3.13, C22) | <ul><li>SQS event source with batch size 1 and `MaximumConcurrency` 5. No reserved concurrency (C9).</li><li>Reports partial batch failures.</li><li>The MS1 stub behaviour is C28.</li></ul> |
| SSM | <ul><li>Stop switches `/lusot/stop/uploads`, `/lusot/stop/publish` and `/lusot/stop/model-calls`, as plain strings in the template.</li><li>The Meta key `/lusot/meta/model-api-key` is created by script (C16) and only referenced by name.</li></ul> |
| Alarms | <ul><li>Dead-letter queue depth of 1 or more triggers an SNS topic, which emails Rene (D17, C31).</li><li>Log groups keep 14 days.</li></ul> |

The $5 budget stays on the account and is checked read-only (C25). The analysis image's repository comes from SAM's companion stack (C9), so its keep-the-last-3 rule (plan §14, Table 16) is applied by the deploy script (C38).

### 3.3 Face blur (C20, F1)
- **What it is:** one Python module, shared by the analysis Lambda and the laptop tools.
- **Detector:** OpenCV's YuNet (`FaceDetectorYN`), with the model vendored (C36).
- **How it blurs:** each detected face, plus a margin, gets a heavy blur. Recall matters more than precision, so the score cutoff leans low.
- **Version:** the module exposes a version string that every run records (`eval/rules.md` §10).
- **Tests:**
  - a photo with no face comes out unchanged
  - a detected box is blurred and nothing outside it changes
  - a public-domain portrait has its face found and blurred

### 3.4 Meta client and probes (C10, C12, C34, C35, C37)
- **The Python client:**
  - uses the OpenAI SDK at `https://api.meta.ai/v1` for Muse Spark and SAM 3.1 (plan Table 17), and plain HTTPS for transcription. If `meta-sam-parser`'s documented example needs SAM's raw stream, SAM goes through httpx instead, and that change is recorded.
  - retries only on 429, 500 and 503, with backoff, jitter and `Retry-After`, for 3 to 5 attempts
  - when a streamed SAM request ends in a 504, switches to background mode and polls (C10)
  - logs model ids, prompt versions and timings, never keys or image bytes
  - reads the key from `MODEL_API_KEY`
- **Request formats** are confirmed against `dev.meta.ai/docs` before coding.
- **Probes** (laptop only, on the credits, D10):
  1. **SAM and Muse Spark:** 5 face-blurred STURM-FloodDepth photos, 7 SAM phrases each, plus Muse Spark with the Table 5 schema in strict mode, the photo drawn with thin numbered boxes, and the token count from `/v1/responses/input_tokens`.
  2. **Water test:** 10 more STURM photos, floodwater and wheel masks drawn as overlays.
  3. **Voice:** a WAV check (C35). The probe also takes a folder of WAVs, so M12's 10 Taglish questions run the day they arrive (C41).
- **Outputs** stay in `lusot-data/probes/` (C30). The findings go in `docs/research/2026-10-28-ms1-probe-results.md`.

### 3.5 The Meta key in SSM (C16)
- `backend/scripts/put_model_key.py`, using boto3, reads `MODEL_API_KEY` and writes a `SecureString` that uses the AWS-managed key.
- It prints only the parameter's name, its type and the value's length.
- F5 still applies: in this session, the caller fills `MODEL_API_KEY` from the Windows user variable.

### 3.6 Bare app and APK (C33)
- **Build:** Vite (react-ts), then Tailwind, then Capacitor 8 (core, CLI, Android, camera, geolocation).
- **One test screen:**
  - **Take photo:** uses `takePhoto` (C11) and resizes the photo to 1,600 px on its longest side.
  - **Upload:** reads the GPS fix and its accuracy, calls `POST /uploads`, posts the file to S3, and polls `GET /reports/{id}` every 2 s.
  - **Shows:** the report's status.
  - **Footer:** carries the line every screen needs.
- The API address comes from `VITE_API_URL`, set in a git-ignored `.env.local`; `.env.example` is committed.
- **APK:** a debug build from the command line with Gradle; its path is recorded for Rene.
- **Visual work** waits for MS5 (R3). This screen is a test harness.

## 4. New calls (Claude's, for Rene to check)

| # | Call | Why |
|---|---|---|
| C22 | Python 3.13 everywhere: the Lambda base image `public.ecr.aws/lambda/python:3.13` (pinned by digest) and the laptop tools, managed with uv (`uv.lock`, a per-user install with no admin prompt). | C1 asked for 3.12 or newer. One Python means probes, tuning and the Lambda run the same code. |
| C23 | npm workspaces (`app`, `backend/api`) under one root `package.json`; TypeScript strict; Vitest; ESLint from the Vite template. | One install and one `npm run check`. |
| C24 | gitleaks (MIT) as the pre-commit secret scan, from a tracked hooks folder (`core.hooksPath`), installed per user. | C7. A private repo gets no GitHub push protection. |
| C25 | The $5 budget stays on the account, where plan §16 puts it at sign-up. MS1 checks it read-only and doesn't duplicate it in the template. | The design's MS1 row listed it in the skeleton, but the plan sets it on the account. |
| C26 | CI is parked at `ci/github-actions.yml`, and `npm run check` runs the same steps locally. It moves to `.github/workflows/` after T7. | D16. |
| C27 | Upload links are presigned S3 **POSTs**, which allow only the one key, `image/jpeg`, 1 byte to 10 MB, and 5 minutes. | A presigned PUT can't cap the size, and plan §12 sets 10 MB. |
| C28 | **The MS1 analysis Lambda is a stub.** <ul><li>It checks the model-calls stop switch.</li><li>It decodes the file and runs the face blur, which proves OpenCV and YuNet work in the container.</li><li>It stores no photo and deletes the raw one.</li><li>It marks the report `failed` with `pipeline_not_built`.</li><li>It reads the Meta key at cold start and checks only its length, which proves the SSM and KMS wiring. It calls no model.</li></ul> | Plates can't be blurred until SAM runs (MS3), so storing any photo would break "blur faces and plates before anything is stored". |
| C29 | Staging keeps only the plan, its text copy and a pointer `CLAUDE.md`; every other document moves into the repo. Rene reopens the Obsidian vault on the repo folder. | D6 and C3: one copy of each document. |
| C30 | Probe outputs (masks, overlays, raw JSON) stay under `lusot-data/probes/`; the repo gets a summary note with counts, timings and cost. | Keeps third-party images out of git. |
| C31 | Deploy settings live in a git-ignored `backend/samconfig.toml`, including the alarm email (D17); `samconfig.example.toml` is committed. | Keeps the email out of the repo. |
| C32 | Report ids are `r_` plus 32 hex characters from `crypto.randomUUID()` (122 random bits). | Plan §13: results are fetched only by an unguessable id. |
| C33 | The bare APK also reads GPS and the capture time. The API already enforces the 15-minute window (W20) and writes the geohash key (Table 14). | M14 tests the camera, GPS and upload together. |
| C34 | The water test runs on STURM photos (C12). The plan's Manila check repeats on development photos after the split, or on consented photos. | No Manila photo can go to Meta yet. |
| C35 | Voice gets a WAV format check with a synthetic English clip (mono, 16-bit, 16 kHz) until M12's recordings exist. | M12 is Rene's, but the endpoint and format can be proven now. |
| C36 | The YuNet model file (about 230 KB) is vendored with its licence and SHA-256, and credited in the README. | Reproducible builds. Its licence is confirmed before vendoring (F1). |
| C37 | The Meta client accepts only images that come out of the face blur, as a separate type, so an unblurred photo can't be sent by mistake. | Enforces F1 in code. |
| C38 | **The image repository's lifecycle rule** (keep the last 3 images) is applied by `npm run deploy` after `sam deploy`, with an idempotent `put-lifecycle-policy` on the repository that SAM's companion stack made. `CLAUDE.md` now says what sits outside the one template:<ul><li>account setup from sign-up (the IAM user and the $5 budget)</li><li>the Meta key (C16)</li><li>this rule</li></ul> | `--resolve-image-repos` (C9) creates the repository outside our template. Defining it ourselves would need a second, bootstrap template. |
| C39 | **Sealed paths are named now**, before they exist:<ul><li>all sealed material lives in folders named `sealed`</li><li>the M19 archive is `C:\Systems\Lusot\lusot-data\sealed\lusot-sealed.7z`</li><li>Set B's final cars go in `lusot-data\set_b\sealed\` (Rene, M10)</li><li>Set D goes in `lusot-data\set_d\sealed\`</li></ul>The deny rules match `**/sealed/**`. They go in the repo's `.claude/settings.json` and also in the staging folder's, because this overnight session started there. | A rule written for a folder name that doesn't match would silently stop guarding. |
| C40 | **What the water test can decide.** <ul><li>Claude reviews the A2 overlays.</li><li>A photo passes when the floodwater mask reaches each submerged wheel's lower edge and covers less than 10% of the wheel mask.</li><li>STURM results are an early signal for Rene, recorded in the probe note.</li><li>The plan Table 18 fallback ("drop the geometry layer") is decided on the Manila check (C34) at MS3, or by Rene sooner.</li></ul> | STURM photos aren't Manila photos, and the fallback is too costly to trigger on a stand-in. |
| C41 | **The Taglish voice test stays in MS1** as a follow-up: the probe runs on M12's recordings the day they arrive, even if MS1 has otherwise closed. | Plan §16 and Table 18 make it the early warning for voice, and it shouldn't slip to MS6. |

## 5. Not in MS1
- the pipeline (MS3)
- the full reports API, device limits, the claim step (G2) and the samples endpoint (MS4)
- real screens, consent and privacy pages (MS5)
- Amplify Hosting (M6, Oct 31)

## 6. Risks
- **AWS CLI calls are slow** on this machine: about 2 minutes for one `sts` call on Oct 28. Allow time for deploys and use long timeouts.
- **Capacitor 8 may need JDK 21,** and `JAVA_HOME` is JDK 17. If so, use a portable JDK 21 per user, with no admin prompt.
- **Memory:** Docker image builds and Gradle builds never run at the same time.
- **The `aws login` session** ends 12 hours after Rene's last login. If it lapses overnight, the deploy waits for him, and the rest continues.
- **Probe surprises,** such as SAM failing to separate water from wheels, are recorded and handled under the double-check loop (`CLAUDE.md`, "Workflow"): record it, fix it, continue. They don't stop MS1, and C40 says what they can decide.
- **CI is parked (D16, C26).** Until T7, GitHub Actions can't serve as C9's fallback for building the container. If Docker fails, the fix is local, or it waits for T7.

## 7. Builder check (Oct 28)

A fresh reviewer read this spec with the design, `CLAUDE.md`, the plan and the research notes. It opened nothing under `lusot-data`. Every point was settled by Claude, and none needed Rene.

| # | Point | Settled as |
|---|---|---|
| Q1 | The double-check loop isn't defined, and nobody owns the water test's verdict | The loop is in `CLAUDE.md` ("Workflow"). C40 covers the verdict. |
| Q2 | Sealed folders and the archive have no names, and the repo's deny rules don't cover a session started in staging | C39 |
| X1 | C25 conflicted with `CLAUDE.md`'s "the one resource outside the template" | `CLAUDE.md` reworded (C38) |
| X2 | The spec's client had no path for a 504 | Added (§3.4, C10) |
| X3 | The SAM transport differed from plan Table 17 | Plan Table 17 is followed, with a recorded exception (§3.4) |
| X4 | Parking CI loses C9's container-build fallback | Added to the risks |
| X5 | Nobody owned the Taglish voice test | C41 |
| X6 | The plan's ECR lifecycle rule was missing | C38 |

## 8. Closing notes (Oct 28, at the MS1 close)

What changed from this spec while MS1 was built. The rulings (R numbers) are in the [Oct 28 log](../../log/2026-10-28.md), under "Decided".

| Spec | What changed | Why |
|---|---|---|
| C23 | The app lints with **Oxlint**, not ESLint (R33). | The current Vite react-ts template ships Oxlint, and ESLint's TypeScript plugin doesn't support the template's TypeScript 7. |
| C26 | **CI is live** in `.github/workflows/ci.yml`, not parked in `ci/` (R38). It runs the same three checks as `npm run check`. | T7 (the `workflow` scope) was granted on Oct 28, 10:32 AM. Pushes still happen at the end of each milestone (D16). |
| §3.1 Guards | `npm run check` adds a **scan for 12-digit numbers** (the shape of an AWS account ID). It skips lockfiles and hex hashes of 32 or more characters (R39, R45). Claude's deny rules also cover the raw Set A and A-neg photos until the MS2 split (R8). | A7's "no account ID in the repo" becomes a repeatable check that CI also runs, unlike the plan-leak check, which needs the plan. |
| §3.2 Backend skeleton | Each function has its own least-privilege role (R19). The stack outputs queue names, not queue URLs, which contain the account ID (R20). The API is bundled from the lockfile before `sam build` (R21). | Review findings in Task 6. |
| C28 stub | The stub downscales before face detection (R16), caps decoding at 50 MP (R25), and marks a report whose raw photo is missing `failed/photo_missing` (R22). | Memory limits, and a missing photo can't be retried. |
| C38, design §13 | **No `sam init` or `aws-samples/serverless-patterns` starter was used.** Task 6 wrote the template and both functions for Lusot, so the README credits the SAM CLI only (R47). | D3 limits where starting code may come from; it doesn't require any. |
| §3.6 APK | Gradle needs **JDK 21**: a portable Microsoft Build of OpenJDK 21 runs the build, and the user `JAVA_HOME` stays JDK 17 (the risk in §6 came true). Capacitor's logging is off (`loggingBehavior: 'none'`), because debug builds wrote the exact GPS fix to the phone's log (R43). | "Never log exact locations." |
| A6 | Still open: it waits for Rene's phone test (M14). The emulator run passed. | A6 needs a real phone on mobile data. |
