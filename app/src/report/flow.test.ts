import { describe, expect, it } from 'vitest'
import { HttpError, MalformedAnswerError, RequestTimeoutError, type ReportResult } from '../lib/api'
import type { Fix } from '../lib/geo'
import { POLL } from '../lib/poll'
import type { Photo } from '../screens/report/CameraStep'
import type { Place } from '../screens/report/PlaceStep'
import {
  flowReducer,
  firstWindow,
  initialFlow,
  LINK_LIFE_MS,
  linkReusable,
  ownPinOf,
  PHOTO_LIFE_MS,
  photoUsable,
  retryKind,
  type FlowAction,
  type FlowState,
  type Problem,
  type Sent,
  type UploadLink,
  uploadProblem,
} from './flow'

const T0 = Date.parse('2026-10-30T09:15:30.000Z')
const PHOTO: Photo = {
  blob: new Blob([new Uint8Array(10)], { type: 'image/jpeg' }),
  pixels: new ImageData(2, 2),
  capturedAt: new Date(T0).toISOString(),
  smallStill: false,
}
const FIX: Fix = { lat: 14.6123456, lng: 121.0456789, accuracyM: 30 }
const PLACE: Place = { lat: 14.6124, lng: 121.0457, nudgeM: 7 }
const LINK: UploadLink = {
  reportId: 'r_0123456789abcdef0123456789abcdef',
  upload: { url: 'https://bucket.example.test/', fields: { key: 'raw/x.jpg' } },
  at: T0 + 5_000,
}

const run = (state: FlowState, ...actions: FlowAction[]) => actions.reduce(flowReducer, state)

// A place step with the photo in hand and a good fix.
const atPlace = (): FlowState =>
  run(
    initialFlow,
    { type: 'fixStarted', gen: 1 },
    { type: 'fixFound', gen: 1, fix: FIX },
    { type: 'photo', photo: PHOTO },
  )
const sending = () => run(atPlace(), { type: 'send', place: PLACE })
const failedWith = (problem: Problem, linked = false) =>
  run(sending(), ...(linked ? [{ type: 'linked', link: LINK } as const] : []), { type: 'failed', problem })
const waiting = () => run(sending(), { type: 'linked', link: LINK }, { type: 'uploaded', at: T0 + 9_000 })

const LEVEL: ReportResult = {
  reportId: LINK.reportId,
  status: 'done',
  mode: 'live',
  published: true,
  capturedAt: PHOTO.capturedAt,
  noFloodSeen: false,
  level: 'knee',
  landmark: 'rim_three_quarters',
  passability: 'NPLV',
  basis: { vehicles: 1, people: 0 },
  levelIsFloor: false,
}

// Every Blob, and every string equal to `text`, anywhere in a value.
function holds(value: unknown, test: (leaf: unknown) => boolean): boolean {
  if (test(value)) return true
  if (value === null || typeof value !== 'object' || value instanceof Blob) return false
  return Object.values(value).some((child) => holds(child, test))
}
const holdsPhoto = (state: FlowState) => holds(state, (leaf) => leaf instanceof Blob)
const holdsText = (state: FlowState, text: string) => holds(state, (leaf) => leaf === text)

describe('the flow reducer', () => {
  it('starts on the camera, with no location watch and nothing kept', () => {
    expect(initialFlow).toEqual({ step: 'camera', shot: 0, fix: { status: 'idle' } })
  })

  it('"start" opens a fresh camera from any step, keeping nothing, and gives the camera a new key', () => {
    for (const state of [atPlace(), sending(), waiting(), failedWith({ kind: 'upload' })]) {
      const next = flowReducer(state, { type: 'start' })
      expect(next).toEqual({ step: 'camera', shot: state.shot + 1, fix: { status: 'idle' } })
    }
  })

  it('keeps only the current location watch: a stale answer is dropped', () => {
    const finding = run(initialFlow, { type: 'fixStarted', gen: 1 }, { type: 'fixStarted', gen: 2 })
    expect(flowReducer(finding, { type: 'fixFound', gen: 1, fix: FIX })).toBe(finding)
    expect(run(finding, { type: 'fixFound', gen: 2, fix: FIX })).toMatchObject({ fix: { status: 'found', gen: 2, fix: FIX } })
    expect(run(finding, { type: 'fixFailed', gen: 2, line: 'location.poor' })).toMatchObject({
      fix: { status: 'failed', gen: 2, line: 'location.poor' },
    })
  })

  it('the photo moves the camera to the place step, with the fix as it stands', () => {
    const state = run(initialFlow, { type: 'fixStarted', gen: 1 }, { type: 'photo', photo: PHOTO })
    expect(state).toEqual({ step: 'place', shot: 0, fix: { status: 'finding', gen: 1 }, photo: PHOTO })
    expect(flowReducer(state, { type: 'photo', photo: PHOTO })).toBe(state)
  })

  it('a retried location keeps the photo and starts a new watch, from the place step or a location refusal', () => {
    const failed = run(atPlace(), { type: 'fixStarted', gen: 2 }, { type: 'fixFailed', gen: 2, line: 'location.poor' })
    expect(run(failed, { type: 'fixStarted', gen: 3 })).toEqual({
      step: 'place',
      shot: 0,
      photo: PHOTO,
      fix: { status: 'finding', gen: 3 },
    })
    const refused = failedWith({ kind: 'refused', code: 'gps_too_coarse' })
    expect(run(refused, { type: 'fixStarted', gen: 4 })).toEqual({
      step: 'place',
      shot: 0,
      photo: PHOTO,
      fix: { status: 'finding', gen: 4 },
    })
  })

  it('"send" needs the photo and a good fix', () => {
    expect(sending()).toEqual({ step: 'sending', shot: 0, photo: PHOTO, fix: FIX, place: PLACE })
    const finding = run(initialFlow, { type: 'fixStarted', gen: 1 }, { type: 'photo', photo: PHOTO })
    expect(flowReducer(finding, { type: 'send', place: PLACE })).toBe(finding)
    const expired = run(atPlace(), { type: 'photoExpired' })
    expect(flowReducer(expired, { type: 'send', place: PLACE })).toBe(expired)
  })

  it('an upload drops the photo, the fix and the link, and keeps only what the own pin needs', () => {
    const state = waiting()
    expect(state).toEqual({
      step: 'waiting',
      shot: 0,
      reportId: LINK.reportId,
      sent: { lat: PLACE.lat, lng: PLACE.lng, accuracyM: FIX.accuracyM, capturedAt: PHOTO.capturedAt },
      uploadedAt: T0 + 9_000,
      window: { startedAt: T0 + 9_000, startElapsedMs: 0, deadlineAt: T0 + 9_000 + POLL.windowMs },
      timedOut: false,
    })
    expect(holdsPhoto(state)).toBe(false)
    expect(Number.isFinite(state.step === 'waiting' && state.window.deadlineAt)).toBe(true)
  })

  it('"uploaded" without a link does nothing', () => {
    const state = sending()
    expect(flowReducer(state, { type: 'uploaded', at: T0 })).toBe(state)
  })

  it('a failure keeps the photo only where its retry reuses it', () => {
    const upload = failedWith({ kind: 'upload' }, true)
    expect(upload).toEqual({
      step: 'problem',
      shot: 0,
      problem: { kind: 'upload' },
      photo: PHOTO,
      again: { fix: FIX, place: PLACE, link: LINK },
    })
    expect(failedWith({ kind: 'paused' })).toEqual({
      step: 'problem',
      shot: 0,
      problem: { kind: 'paused' },
      photo: PHOTO,
      again: { fix: FIX, place: PLACE },
    })
    // A location refusal reuses the photo with a new fix, so the old position goes.
    expect(failedWith({ kind: 'refused', code: 'nudge_too_far' })).toEqual({
      step: 'problem',
      shot: 0,
      problem: { kind: 'refused', code: 'nudge_too_far' },
      photo: PHOTO,
    })
    for (const problem of [
      { kind: 'refused', code: 'device_limit' },
      { kind: 'refused', code: 'global_cap' },
      { kind: 'refused', code: 'capture_too_old' },
      { kind: 'refused', code: 'capture_in_future' },
      { kind: 'other' },
    ] as Problem[]) {
      expect(failedWith(problem), JSON.stringify(problem)).toEqual({ step: 'problem', shot: 0, problem })
    }
  })

  it('the 15 minutes passing drops the photo and the position at the place step and after a failure', () => {
    expect(run(atPlace(), { type: 'photoExpired' })).toEqual({ step: 'place', shot: 0, fix: { status: 'idle' } })
    expect(run(failedWith({ kind: 'upload' }, true), { type: 'photoExpired' })).toEqual({
      step: 'problem',
      shot: 0,
      problem: { kind: 'upload' },
    })
    // An upload under way finishes or fails first; the retry then checks the photo's age.
    const state = sending()
    expect(flowReducer(state, { type: 'photoExpired' })).toBe(state)
  })

  it('"resend" sends the same photo again, after an upload problem or a pause only, with the link it is given', () => {
    const upload = failedWith({ kind: 'upload' }, true)
    expect(run(upload, { type: 'resend', link: LINK })).toEqual({
      step: 'sending',
      shot: 0,
      photo: PHOTO,
      fix: FIX,
      place: PLACE,
      link: LINK,
    })
    expect(run(upload, { type: 'resend' })).toEqual({ step: 'sending', shot: 0, photo: PHOTO, fix: FIX, place: PLACE })
    const paused = failedWith({ kind: 'paused' })
    expect(run(paused, { type: 'resend' })).toMatchObject({ step: 'sending', photo: PHOTO })
    for (const state of [
      failedWith({ kind: 'refused', code: 'gps_too_coarse' }),
      failedWith({ kind: 'other' }),
      run(upload, { type: 'photoExpired' }),
    ]) {
      expect(flowReducer(state, { type: 'resend' })).toBe(state)
    }
  })

  it('an S3 failure that may have landed (a timeout or a network error) is marked so with its link', () => {
    const state = run(sending(), { type: 'linked', link: LINK }, { type: 'failed', problem: { kind: 'upload' }, mayHaveLanded: true })
    expect(state).toMatchObject({ step: 'problem', again: { link: LINK, mayHaveLanded: true } })
    // Without a link, nothing reached S3, so nothing can have landed.
    expect(run(sending(), { type: 'failed', problem: { kind: 'upload' }, mayHaveLanded: true })).toEqual({
      step: 'problem',
      shot: 0,
      problem: { kind: 'upload' },
      photo: PHOTO,
      again: { fix: FIX, place: PLACE },
    })
  })

  it('"landed" waits on the old report: the photo goes, the sent position stays, and the window is fresh', () => {
    const resending = run(
      sending(),
      { type: 'linked', link: LINK },
      { type: 'failed', problem: { kind: 'upload' }, mayHaveLanded: true },
      { type: 'resend' },
    )
    const state = flowReducer(resending, { type: 'landed', reportId: LINK.reportId, at: T0 + 400_000 })
    expect(state).toEqual({
      step: 'waiting',
      shot: 0,
      reportId: LINK.reportId,
      sent: { lat: PLACE.lat, lng: PLACE.lng, accuracyM: FIX.accuracyM, capturedAt: PHOTO.capturedAt },
      uploadedAt: T0 + 400_000,
      window: firstWindow(T0 + 400_000),
      timedOut: false,
    })
    expect(holdsPhoto(state)).toBe(false)
    for (const other of [atPlace(), waiting(), failedWith({ kind: 'upload' }, true)]) {
      expect(flowReducer(other, { type: 'landed', reportId: LINK.reportId, at: T0 })).toBe(other)
    }
  })

  it('the result keeps the answer and the accuracy of the fix, and no position', () => {
    const state = run(waiting(), { type: 'result', result: LEVEL })
    expect(state).toEqual({ step: 'result', shot: 0, result: LEVEL, fixAccuracyM: FIX.accuracyM })
  })

  it('"No result yet" stops the wait, and "Check again" opens a new 600 s window at the 15 s interval', () => {
    const timedOut = run(waiting(), { type: 'timedOut' })
    expect(timedOut).toMatchObject({ step: 'waiting', timedOut: true })
    const again = run(timedOut, { type: 'checkAgain', at: T0 + 700_000 })
    expect(again).toMatchObject({
      step: 'waiting',
      reportId: LINK.reportId,
      timedOut: false,
      uploadedAt: T0 + 9_000,
      window: { startedAt: T0 + 700_000, startElapsedMs: 240_000, deadlineAt: T0 + 700_000 + POLL.windowMs },
    })
    // Only after the wait ran out.
    const state = waiting()
    expect(flowReducer(state, { type: 'checkAgain', at: T0 })).toBe(state)
  })

  it('leaving the screen keeps an upload and a wait, and closes everything else', () => {
    for (const state of [sending(), waiting()]) expect(flowReducer(state, { type: 'leave' })).toBe(state)
    const result = run(waiting(), { type: 'result', result: LEVEL })
    for (const state of [atPlace(), failedWith({ kind: 'upload' }, true), result, run(waiting(), { type: 'timedOut' })]) {
      const next = flowReducer(state, { type: 'leave' })
      expect(next).toEqual({ step: 'camera', shot: state.shot + 1, fix: { status: 'idle' } })
      expect(holdsPhoto(next) || holdsText(next, LINK.reportId)).toBe(false)
    }
  })
})

describe('the time rules', () => {
  it('a photo can be sent while it is under 15 minutes old', () => {
    expect(PHOTO_LIFE_MS).toBe(900_000)
    expect(photoUsable(PHOTO, T0 + PHOTO_LIFE_MS - 1)).toBe(true)
    expect(photoUsable(PHOTO, T0 + PHOTO_LIFE_MS)).toBe(false)
    expect(photoUsable({ ...PHOTO, capturedAt: 'not a time' }, T0)).toBe(false)
  })

  it('an upload link is used again until it is over 5 minutes old, counted from the answer', () => {
    expect(LINK_LIFE_MS).toBe(300_000)
    expect(linkReusable(LINK, LINK.at + LINK_LIFE_MS)).toBe(true)
    expect(linkReusable(LINK, LINK.at + LINK_LIFE_MS + 1)).toBe(false)
  })
})

describe('uploadProblem, for a failed POST /uploads', () => {
  it.each([
    ['the pause', new HttpError(503, 'uploads_paused'), { kind: 'paused' }],
    ['device_limit', new HttpError(429, 'device_limit'), { kind: 'refused', code: 'device_limit' }],
    ['global_cap', new HttpError(429, 'global_cap'), { kind: 'refused', code: 'global_cap' }],
    ['capture_too_old', new HttpError(422, 'capture_too_old'), { kind: 'refused', code: 'capture_too_old' }],
    ['capture_in_future', new HttpError(422, 'capture_in_future'), { kind: 'refused', code: 'capture_in_future' }],
    ['gps_too_coarse', new HttpError(422, 'gps_too_coarse'), { kind: 'refused', code: 'gps_too_coarse' }],
    ['nudge_too_far', new HttpError(422, 'nudge_too_far'), { kind: 'refused', code: 'nudge_too_far' }],
    ['a throttle that outlasted its retry', new HttpError(429), { kind: 'upload' }],
    ['a 503 that outlasted its retry', new HttpError(503), { kind: 'upload' }],
    ['a 500', new HttpError(500, 'internal'), { kind: 'upload' }],
    ['a network error', new TypeError('Failed to fetch'), { kind: 'upload' }],
    ['a timeout', new RequestTimeoutError(15_000), { kind: 'upload' }],
    ['an answer in the wrong shape', new MalformedAnswerError('POST /uploads'), { kind: 'other' }],
    ['a 400', new HttpError(400, 'bad_request'), { kind: 'other' }],
    ['an unknown 422', new HttpError(422, 'something_new'), { kind: 'other' }],
    ["Ask Lusot's limit", new HttpError(429, 'question_limit'), { kind: 'other' }],
    ['anything else', new Error('odd'), { kind: 'other' }],
  ])('%s', (_name, err, problem) => {
    expect(uploadProblem(err)).toEqual(problem)
  })

  it('retryKind: a resend after an upload problem or a pause, a new fix after a location refusal, no retry after a limit', () => {
    expect(retryKind({ kind: 'upload' })).toBe('resend')
    expect(retryKind({ kind: 'paused' })).toBe('resend')
    expect(retryKind({ kind: 'refused', code: 'gps_too_coarse' })).toBe('refix')
    expect(retryKind({ kind: 'refused', code: 'nudge_too_far' })).toBe('refix')
    expect(retryKind({ kind: 'refused', code: 'capture_too_old' })).toBe('newPhoto')
    expect(retryKind({ kind: 'refused', code: 'capture_in_future' })).toBe('newPhoto')
    expect(retryKind({ kind: 'other' })).toBe('newPhoto')
    expect(retryKind({ kind: 'refused', code: 'device_limit' })).toBe('none')
    expect(retryKind({ kind: 'refused', code: 'global_cap' })).toBe('none')
  })
})

describe('ownPinOf', () => {
  const SENT: Sent = { lat: PLACE.lat, lng: PLACE.lng, accuracyM: 30, capturedAt: PHOTO.capturedAt }

  it('a done level result in live mode, published, gives the own pin from the sent position', () => {
    expect(ownPinOf({ ...LEVEL, gpsAccuracyM: 12, levelIsFloor: true, depthInMin: 15, depthInMax: 18 }, SENT)).toEqual({
      id: LINK.reportId,
      lat: PLACE.lat,
      lng: PLACE.lng,
      capturedAt: PHOTO.capturedAt,
      mode: 'live',
      flags: 0,
      gpsAccuracyM: 12,
      level: 'knee',
      landmark: 'rim_three_quarters',
      passability: 'NPLV',
      levelIsFloor: true,
      basis: { vehicles: 1, people: 0 },
      depthInMin: 15,
      depthInMax: 18,
      own: true,
    })
  })

  it("takes the fix's accuracy when the API sends none (N1)", () => {
    expect(ownPinOf(LEVEL, SENT)?.gpsAccuracyM).toBe(30)
  })

  it('gives none for no flood seen, a refusal, a failure, a private or sample result, or an unpublished one', () => {
    const none: ReportResult[] = [
      { ...LEVEL, noFloodSeen: true, level: undefined, landmark: undefined, passability: undefined },
      { ...LEVEL, status: 'refused', refusalReason: 'references_disagree' },
      { ...LEVEL, status: 'failed', refusalReason: 'model_error' },
      { ...LEVEL, mode: 'private', published: false },
      { ...LEVEL, mode: 'sample', published: false },
      { ...LEVEL, published: false },
    ]
    for (const result of none) expect(ownPinOf(result, SENT), JSON.stringify(result)).toBeUndefined()
  })
})
