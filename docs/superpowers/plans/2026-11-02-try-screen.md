# "Try your own photo" (app) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** On the Tested page, a person can choose a flood photo from their device. Lusot reads it through `POST /try`, and the result shows in the same ResultCard as a sample, only to that person. It never goes on the map.

**Architecture:** The API part is on main (`POST /try`, C534). This plan adds four things: a client call, a re-encode helper, a `'try'` source for ResultCard, and a `TryPhoto` component in a new Tested-page section. The component's flow is: gate → file input → re-encode → `POST /try` → S3 POST → poll. The one file input in `app/src` lives in `TryPhoto.tsx`, and the no-picker test is narrowed to allow only that file (C640).

**Tech Stack:** React 19 + TypeScript, Tailwind (the app's tokens), Vitest + Testing Library, Playwright (all requests mocked).

**Spec:** MS4 spec C534 and MS5 spec C640 (`docs/superpowers/specs/2026-10-28-ms4-backend-design.md`, `docs/superpowers/specs/2026-10-28-ms5-app-design.md`); the tracker's build brief of Nov 2, 4:1x PM (below, under Global Constraints).

## Global Constraints

- Branch `try-screen` from main `5c3b292`. Work in `C:\Systems\Lusot\lusot-wt\w4`; commit only there. Commit messages use Conventional Commits, written to a file and committed with `git commit -F <file>` from PowerShell after the PATH refresh (CLAUDE.md "Commits").
- Before writing any UI code, load `ui-ux-pro-max:ui-ux-pro-max` and `frontend-design:frontend-design` (CLAUDE.md). Keep the layout **neutral**: single column, the existing classes and tokens, no `lg:` grid rules. Window 2's desktop branch styles the wide layout later.
- The entry sits on the Tested screen, after the samples. It must never appear in the camera Report flow (`screens/ReportScreen.tsx`, `screens/report/*`).
- One file input only, in `app/src/components/TryPhoto.tsx`, with `accept="image/jpeg,image/png,image/webp"`. Never a `capture` attribute, `showOpenFilePicker`, a gallery call or `@capacitor/camera`.
- Re-encode with the existing `encodeJpeg` (`app/src/lib/jpeg.ts`, C635): the longest side at most 1,600 px (within the brief's ≤ 1,920), quality 0.85, then 0.75 when the first result is over 450 KB. Decode with `createImageBitmap(file, { imageOrientation: 'from-image' })`, so the photo comes out upright and its EXIF (GPS included) is dropped.
- `POST /try` contract (main `backend/api/src/tryPhoto.ts`):
  - Body `{"consentVersion": NOTICE_VERSION}`, header `X-Lusot-Device`.
  - 201 `{reportId, upload, expiresInS}`.
  - 503 `uploads_paused` | `model_calls_paused`; 400 `bad_request`; 429 `device_limit` | `global_cap` | `daily_cap`; 500.
  - `GET /reports/{id}` gives `mode: "try"`, and `capturedAt` is the run's start, not a capture time.
  - `POST /samples/{id}` can now answer 429 `daily_cap` too.
- Copy rules (CLAUDE.md, `scripts/copy-rules.json`): never the word "safe", no crossing advice, only "at this spot", and never "MMDA's 9 levels". Every new EN and FIL entry starts `reviewed: false`; the tracker approves under Rene's delegation (M20). The FIL text is a Taglish draft. The screen line stays on every screen.
- A pause reads as a pause (C638): both 503 codes, and a poll that ends `failed/model_calls_paused`, show the existing `PausedNotice` with `links={['map']}`, never "Processing failed".
- Privacy text: one line in `app/src/content/consent.en.md` and one in `app/src/content/privacy.en.md`. `NOTICE_VERSION` is the notice text's hash, so editing the notice is the bump; update any test that pins the old hash.
- No AWS calls and no paid runs. Every e2e request is mocked.
- Checks before the final commit, from the repo root: `npm run check:node` exits 0, then `npm run e2e -w app` exits 0. Run both in the foreground, one at a time.

## Review Focus

1. A HEIC, GIF or other non-allowed file → the "JPEG, PNG or WebP" line, with no request at all. A file whose type lies and won't decode → the "couldn't open" line, with no request.
2. A sideways phone photo (EXIF orientation 6) → it is sent upright. The test asserts the `imageOrientation: 'from-image'` option.
3. A double change event or a second choice while a run is in flight → exactly one `POST /try`.
4. Leaving the Tested page mid-poll → the poll is aborted, with no state update after unmount.
5. Choosing the same file again after a result → it runs again (the input's value is cleared after each choice).

---

### Task 1: API client and the day caps in the app

**Files:**
- Modify: `app/src/lib/api.ts` (ReportResult's `mode`, `LIMIT_CODES`, the new `requestTry`)
- Modify: `app/src/components/SampleList.tsx` (`afterFailure`)
- Modify: `app/src/i18n/en.ts`, `app/src/i18n/fil.ts` (`sample.limit.daily_cap`)
- Test: `app/src/lib/api.test.ts`, `app/src/screens/TestedScreen.test.tsx` (where the sample-run tests live; put it wherever SampleList's limit tests are)

**Interfaces:**
- Produces: `requestTry(apiUrl: string, consentVersion: string, deviceId: string, fetchFn?: typeof fetch): Promise<{ reportId: string; upload: PresignedPost }>`. It POSTs to `${apiUrl}/try` with `content-type: application/json` and `X-Lusot-Device`, under `REQUEST_TIMEOUT_MS`. It throws `httpError(res)` on a non-2xx, and `MalformedAnswerError('POST /try')` when `reportId` isn't a string or `upload` isn't a presigned POST. It is never retried. `ReportResult['mode']` gains `'try'`. `LIMIT_CODES` gains `'daily_cap'`.

- [ ] **Step 1: Failing tests:**
  - `requestTry sends only consentVersion with the device header and returns the link`: assert the URL `…/try`, method POST, body exactly `{"consentVersion":"0a1b2c3d"}`, and the header `X-Lusot-Device`.
  - `requestTry throws HttpError with the API's code`: for 503 `model_calls_paused` and 429 `daily_cap`, assert `err.code`, and `isDeviceLimit === true` for `daily_cap`.
  - `requestTry throws MalformedAnswerError on a 201 without a presigned POST`.
  - `a sample refused by daily_cap shows sample.limit.daily_cap and keeps Run this sample hidden`, following the existing `global_cap` test.
- [ ] **Step 2:** Run `npx vitest run src/lib/api.test.ts src/screens/TestedScreen.test.tsx` from `app/`. Expected: the new tests FAIL.
- [ ] **Step 3:** Implement. In `afterFailure`, map `429 daily_cap` to `{ phase: 'refused', line: 'sample.limit.daily_cap' }`. EN: `"Lusot has run as many samples as it can today. Try again later."`. FIL draft: `"Naabot na ng Lusot ang dami ng sample na kaya nito ngayong araw. Subukan ulit mamaya."`. Both `reviewed: false`.
- [ ] **Step 4:** Re-run. Expected: PASS. Also run `npx tsc --noEmit -p .` (or the workspace `typecheck`). Expected: exit 0.
- [ ] **Step 5:** Commit `feat(app): requestTry and the daily_cap refusal for samples (C534)`.

### Task 2: The re-encode helper

**Files:**
- Create: `app/src/lib/tryPhoto.ts`
- Test: `app/src/lib/tryPhoto.test.ts` (fake `createImageBitmap` and the canvas as `camera.test.ts:312-342` does)

**Interfaces:**
- Produces:
  - `export const TRY_TYPES = ['image/jpeg', 'image/png', 'image/webp'] as const`
  - `export class TryPhotoError extends Error { readonly kind: 'unsupported' | 'unreadable' }`
  - `export async function photoToJpeg(file: Blob): Promise<Blob>`. It throws `TryPhotoError('unsupported')` when `file.type` isn't in `TRY_TYPES`, before any decode. It throws `TryPhotoError('unreadable')` when `createImageBitmap` rejects. Otherwise it returns `encodeJpeg(bitmap, bitmap.width, bitmap.height).blob` and closes the bitmap in a `finally`.

- [ ] **Step 1: Failing tests:**
  - `refuses a HEIC or GIF file as unsupported without decoding it`: `createImageBitmap` is never called.
  - `decodes with imageOrientation from-image`: assert the second argument is `{ imageOrientation: 'from-image' }`.
  - `a 4000×3000 photo comes out at 1600×1200 as image/jpeg`.
  - `a file that won't decode is unreadable`.
  - `the bitmap is closed after encoding, and after a failed encode`.
- [ ] **Step 2:** Run `npx vitest run src/lib/tryPhoto.test.ts`. Expected: FAIL (the module is missing).
- [ ] **Step 3:** Implement `photoToJpeg` as specified.
- [ ] **Step 4:** Re-run. Expected: PASS.
- [ ] **Step 5:** Commit `feat(app): photoToJpeg re-encodes a chosen photo upright, without EXIF (C640)`.

### Task 3: ResultCard's `'try'` source

**Files:**
- Modify: `app/src/components/ResultCard.tsx`
- Modify: `app/src/i18n/en.ts`, `app/src/i18n/fil.ts` (`result.try`)
- Test: `app/src/components/ResultCard.test.tsx`

**Interfaces:**
- Produces: `ResultCardProps['source']` is `'own' | 'pin' | 'sample' | 'try'`. A try card behaves like `'own'` except:
  - no "Photo taken … ago" or accuracy line, even when `capturedAt` is set
  - `Details` gets no `photoTime`
  - the paused links are `['map']`
  - it shows `result.try` under any reading (level, no flood, can't tell)
  - a can't-tell shows D19 bold, the reason, and the tip line (the person chose the photo, so the tips apply)

- [ ] **Step 1: Failing tests:**
  - `a try level shows its verdict and level line, with no photo-taken line though capturedAt is set`
  - `a try refusal shows D19, the reason and the tip`
  - `a try reading says only you see it and it isn't on the map`
  - `a paused try card links to the map only`
  - `a failed try card offers Try again when onNewPhoto is given`
- [ ] **Step 2:** Run `npx vitest run src/components/ResultCard.test.tsx`. Expected: the new tests FAIL.
- [ ] **Step 3:** Implement with the smallest branches on `source === 'try'`. EN `result.try`: `"Only you see this result. It isn't on the map."` FIL draft: `"Ikaw lang ang nakakakita ng resultang ito. Wala ito sa mapa."` Both `reviewed: false`.
- [ ] **Step 4:** Re-run the file plus `src/screens/PinScreen.card.test.tsx`. Expected: PASS, with no other card test changed.
- [ ] **Step 5:** Commit `feat(app): ResultCard's try source (C640)`.

### Task 4: The TryPhoto component on the Tested page, the narrowed no-picker test and the privacy lines

**Files:**
- Create: `app/src/components/TryPhoto.tsx`
- Test: `app/src/components/TryPhoto.test.tsx`
- Modify: `app/src/screens/TestedScreen.tsx` (a new `Section title="tested.try.title"` after the samples Section, holding `<TryPhoto apiUrl={apiUrl} />`)
- Modify: `app/src/no-picker.test.ts`
- Modify: `app/src/i18n/en.ts`, `app/src/i18n/fil.ts`
- Modify: `app/src/content/consent.en.md`, `app/src/content/privacy.en.md`, and any test that pins `NOTICE_VERSION` or the notice text

**Interfaces:**
- Consumes:
  - `requestTry` (Task 1), `photoToJpeg` and `TryPhotoError` (Task 2), and `ResultCard source="try"` (Task 3)
  - `postToS3`, `HttpError` and `MalformedAnswerError` from `lib/api`
  - `pollReport`, `POLL` from `lib/poll`
  - `useGate` and `NOTICE_VERSION` from `lib/consent`
  - `getDeviceId` from `lib/device`
  - `PausedNotice` from `ResultCard`
- Produces: `export function TryPhoto({ apiUrl }: { apiUrl: string })`.

Behaviour:
- **Starting a choice:** the "Choose a photo" button calls `useGate('notice')(() => input.click())`. The notice gate is used because the photo goes to Meta, as a report's does. The input is visually hidden and labelled.
- **On change:** take `files[0]`, then clear `input.value`. A `paying` ref makes a second choice in flight a no-op.
- **Phases:** `preparing` (photoToJpeg) → `sending` (requestTry, then postToS3) → `waiting` (pollReport, with the deadline as SampleList uses it and an AbortController aborted on unmount) → `result` | `noResult` (with "Check again", polling the same report as SampleList does) | `paused` | `refused` (a limit line) | `fileProblem` (`try.unsupported` / `try.unreadable`) | `sendFailed` (any other error before the S3 POST succeeded).
- **Mapping errors:**
  - 503 `uploads_paused` or `model_calls_paused` → `paused`
  - 429 `device_limit` / `global_cap` / `daily_cap` → `try.limit.<code>`
  - anything else → `sendFailed`
  - a poll result `failed` with `refusalReason: 'model_calls_paused'` → the card's own paused state (ResultCard handles it)
- **On screen:**
  - `result` renders `<ResultCard result={…} source="try" onNewPhoto={choose} />`
  - after any end state, the button reads `try.chooseAnother`
  - in-flight phases show `try.reading` with the spinner, as `RunStatus` does
  - while the card isn't there, the selected photo's preview is not shown, so no object URL is needed

Copy (EN; every key `reviewed: false`, with a FIL draft beside it):
- `tested.try.title`: "Try your own photo"
- `tested.try.intro`: "Choose a flood photo from your device. Lusot reads it the same way as a photo you take, and shows the result only to you. It never goes on the map, and Lusot keeps the report for 7 days."
- `try.choose`: "Choose a photo" / `try.chooseAnother`: "Choose another photo"
- `try.inputLabel`: "Flood photo from your device"
- `try.reading`: "Lusot is reading your photo."
- `try.unsupported`: "Lusot can read a JPEG, PNG or WebP photo. Choose another photo."
- `try.unreadable`: "Lusot couldn't open this photo. Choose another photo."
- `try.sendFailed`: "Lusot couldn't send your photo. Check your connection and try again."
- `try.limit.device_limit`: "This device has tried as many photos as Lusot allows in an hour. Try again later."
- `try.limit.global_cap`: "Lusot has read as many chosen photos as it can for now. Try again later."
- `try.limit.daily_cap`: "Lusot has read as many chosen photos as it can today. Try again later."

Consent bullet (`consent.en.md`, after the "Your photo goes to Meta" bullet):
`- **You can also choose a photo from your device** on the Tested page. It's handled the same way: faces blurred first, then sent to Meta, which may use it to improve its products. Its result is shown only to you, never put on the map, and the report is deleted after 7 days. Choose only photos you may share.`

Privacy bullet (`privacy.en.md`, after "Outside Metro Manila."):
`- **A photo you choose.** On the Tested page you can choose a photo from your device instead of taking one. Your device re-saves it first, which drops details stored in the file, such as where it was taken. It is analysed the same way and goes to Meta as described above. The result is shown only to you, never becomes a pin, and the report is kept for 7 days like any other.`

- [ ] **Step 1: Failing tests** (`TryPhoto.test.tsx`; mock `fetch` as `api.test.ts` does, and fake `photoToJpeg`):
  - `choosing a JPEG posts /try once, uploads it, polls, and shows the try card`
  - `the notice gate opens first, and a declined gate opens no picker and sends nothing`
  - `a HEIC file shows try.unsupported and sends nothing`
  - `503 model_calls_paused and 503 uploads_paused both show the paused notice with the map link`
  - `429 daily_cap shows try.limit.daily_cap`
  - `two change events in one tick start one run`
  - `unmounting mid-poll aborts the poll`
  - `the input's value is cleared after a choice`
  - In `no-picker.test.ts`: the file-input patterns (0 and 1) may match only `./components/TryPhoto.tsx`, and exactly once there. Every other pattern still matches no file, `TryPhoto.tsx` included. `TryPhoto.tsx` doesn't contain `requestUpload` or `/uploads`. No file under `./screens/report/` or `./screens/ReportScreen.tsx` imports `TryPhoto`. Keep the self-tests of the patterns.
  - In `TestedScreen.test.tsx`: `the Tested page shows the Try your own photo section after the samples`.
- [ ] **Step 2:** Run `npx vitest run src/components/TryPhoto.test.tsx src/no-picker.test.ts src/screens/TestedScreen.test.tsx`. Expected: FAIL.
- [ ] **Step 3:** Implement, then add the copy and the two privacy lines. Run `npx vitest run` for the whole app and fix any test that pinned the notice text or its hash.
- [ ] **Step 4:** Run from the repo root: `npm run check:node`. Expected: exit 0.
- [ ] **Step 5:** Commit `feat(app): Try your own photo on the Tested page (C534, C640)`.

### Task 5: End-to-end, all mocked

**Files:**
- Modify: `app/e2e/mocks.ts` (POST `/try` → 201 with an upload link to the files origin, or a configured 503 or 429; the S3 POST for the try id; GET `/reports/<try id>` → a done level with `mode: 'try'`)
- Create: `app/e2e/try.spec.ts`

- [ ] **Step 1: Write the specs:**
  - `choose a photo on Tested → the try card with its verdict and "Only you see this result", and no POST /uploads or map-pin call made by the try flow`: use `page.setInputFiles` on the labelled input, with a small PNG from `app/e2e/fixtures`, and pass the notice gate first (`steps.ts` has the helpers).
  - `paused: POST /try answers 503 model_calls_paused → the paused notice`.
  - `the screen line shows on the Tested page with the try card` (reuse `screenLine.ts`).
- [ ] **Step 2:** Run `npm run e2e -w app` from the repo root (run `npx playwright install chromium` once if needed). Expected: the new specs pass, and every other spec still passes.
- [ ] **Step 3:** Commit `test(app): e2e for Try your own photo, all mocked`.
