// The report flow's state, from photo to result, as a reducer with no side effects (ReportFlowProvider runs the
// camera's location watch, the upload and the poll, and dispatches what happens). The order: the camera (C602),
// whose first frame starts the location watch (C603); the place step; sending; waiting; then the result or a
// problem. Task 10's on-phone quality check is dropped, so there is no check step: the server's own check refuses a
// dark or blurry photo (C604).
//
// What it keeps (spec §4.4): the photo only until its upload succeeds or 15 minutes pass; a position only until the
// upload succeeds, then the sent one for the own pin until the result comes; the report id only until the result
// screen closes. A step that can't use one of them doesn't carry it.
import type { StringKey } from '../i18n/en'
import { HttpError, RequestTimeoutError, type Pin, type PresignedPost, type ReportResult } from '../lib/api'
import type { Fix } from '../lib/geo'
import { POLL } from '../lib/poll'
import type { Photo } from '../screens/report/CameraStep'
import type { Place } from '../screens/report/PlaceStep'

// The photo stays in memory, and is sent, while it is under 15 minutes old (C635; MS4's capture_too_old).
export const PHOTO_LIFE_MS = 15 * 60_000
// An upload link lasts 5 minutes (MS1's C27), counted from when POST /uploads answered.
export const LINK_LIFE_MS = 5 * 60_000
// The person's own pin stays at most 2 minutes, or until GET /map/pins shows it (spec §4.4).
export const OWN_PIN_LIFE_MS = 2 * 60_000
// The waiting step says that other photos may be ahead from 60 s after the upload, the poll's first step (C601).
export const QUEUE_NOTE_AFTER_MS = POLL.fastForMs

// The location watch. `gen` numbers each watch, so the answer of one that was replaced is dropped. A failure keeps
// only the line that says why, never the error.
export type FixState =
  | { status: 'idle' }
  | { status: 'finding'; gen: number }
  | { status: 'found'; gen: number; fix: Fix }
  | { status: 'failed'; gen: number; line: StringKey }

export type UploadLink = { reportId: string; upload: PresignedPost; at: number }

// MS4's refusals of POST /uploads that the app words one by one: its 422s and the limits' 429s (C522).
export type RefusedCode =
  | 'capture_too_old'
  | 'capture_in_future'
  | 'gps_too_coarse'
  | 'nudge_too_far'
  | 'device_limit'
  | 'global_cap'

// Why a photo wasn't sent. `upload`: a failure on the way that outlasted its one retry. `paused`: MS1's 503
// uploads_paused (C638). `refused`: MS4 said no. `other`: anything else, such as an answer in the wrong shape.
export type Problem = { kind: 'upload' } | { kind: 'paused' } | { kind: 'refused'; code: RefusedCode } | { kind: 'other' }

// What was sent, kept for the own pin until the result comes.
export type Sent = { lat: number; lng: number; accuracyM: number; capturedAt: string }

// One poll's schedule: where it started on the clock and in the C601 schedule, and its absolute deadline.
export type PollWindow = { startedAt: number; startElapsedMs: number; deadlineAt: number }

// `shot` keys the camera, so each new photo gets a fresh camera view (Task 9).
export type FlowState =
  | { step: 'camera'; shot: number; fix: FixState }
  | { step: 'place'; shot: number; fix: FixState; photo?: Photo }
  | { step: 'sending'; shot: number; photo: Photo; fix: Fix; place: Place; link?: UploadLink }
  | {
      step: 'waiting'
      shot: number
      reportId: string
      sent: Sent
      uploadedAt: number
      window: PollWindow
      timedOut: boolean
    }
  | { step: 'result'; shot: number; result: ReportResult; fixAccuracyM: number }
  // `photo` while a retry can reuse it; `again` with what a resend of the same photo needs.
  | {
      step: 'problem'
      shot: number
      problem: Problem
      photo?: Photo
      again?: { fix: Fix; place: Place; link?: UploadLink }
    }

export type FlowAction =
  | { type: 'start' }
  | { type: 'leave' }
  | { type: 'fixStarted'; gen: number }
  | { type: 'fixFound'; gen: number; fix: Fix }
  | { type: 'fixFailed'; gen: number; line: StringKey }
  | { type: 'photo'; photo: Photo }
  | { type: 'photoExpired' }
  | { type: 'send'; place: Place }
  | { type: 'resend'; link?: UploadLink }
  | { type: 'linked'; link: UploadLink }
  | { type: 'uploaded'; at: number }
  | { type: 'failed'; problem: Problem }
  | { type: 'result'; result: ReportResult }
  | { type: 'timedOut' }
  | { type: 'checkAgain'; at: number }

export const initialFlow: FlowState = { step: 'camera', shot: 0, fix: { status: 'idle' } }

const freshCamera = (state: FlowState): FlowState => ({ step: 'camera', shot: state.shot + 1, fix: { status: 'idle' } })

export function flowReducer(state: FlowState, action: FlowAction): FlowState {
  switch (action.type) {
    case 'start':
      return freshCamera(state)

    // The upload and the wait go on while the person looks at the map; anything else closes with the screen.
    case 'leave':
      return survivesLeaving(state) ? state : freshCamera(state)

    case 'fixStarted': {
      const fix: FixState = { status: 'finding', gen: action.gen }
      if (state.step === 'camera') return { ...state, fix }
      // "Try the location again" keeps the photo and drops any older position.
      if ((state.step === 'place' || state.step === 'problem') && state.photo !== undefined) {
        return { step: 'place', shot: state.shot, fix, photo: state.photo }
      }
      return state
    }

    case 'fixFound':
    case 'fixFailed': {
      if (state.step !== 'camera' && state.step !== 'place') return state
      if (state.fix.status !== 'finding' || state.fix.gen !== action.gen) return state
      const fix: FixState =
        action.type === 'fixFound'
          ? { status: 'found', gen: action.gen, fix: action.fix }
          : { status: 'failed', gen: action.gen, line: action.line }
      return { ...state, fix }
    }

    case 'photo':
      if (state.step !== 'camera') return state
      return { step: 'place', shot: state.shot, fix: state.fix, photo: action.photo }

    // The 15 minutes passed: the photo goes, and the position with it, since only a new photo can be sent now.
    case 'photoExpired':
      if (state.step === 'place' && state.photo !== undefined) {
        return { step: 'place', shot: state.shot, fix: { status: 'idle' } }
      }
      if (state.step === 'problem' && state.photo !== undefined) {
        return { step: 'problem', shot: state.shot, problem: state.problem }
      }
      return state

    case 'send':
      if (state.step !== 'place' || state.photo === undefined || state.fix.status !== 'found') return state
      return { step: 'sending', shot: state.shot, photo: state.photo, fix: state.fix.fix, place: action.place }

    case 'resend': {
      if (state.step !== 'problem' || state.photo === undefined || state.again === undefined) return state
      const { fix, place } = state.again
      const sending: FlowState = { step: 'sending', shot: state.shot, photo: state.photo, fix, place }
      return action.link === undefined ? sending : { ...sending, link: action.link }
    }

    case 'linked':
      if (state.step !== 'sending') return state
      return { ...state, link: action.link }

    // The photo, the fix and the link go; what the own pin needs stays until the result.
    case 'uploaded': {
      if (state.step !== 'sending' || state.link === undefined) return state
      const { photo, fix, place, link } = state
      return {
        step: 'waiting',
        shot: state.shot,
        reportId: link.reportId,
        sent: { lat: place.lat, lng: place.lng, accuracyM: fix.accuracyM, capturedAt: photo.capturedAt },
        uploadedAt: action.at,
        window: firstWindow(action.at),
        timedOut: false,
      }
    }

    case 'failed': {
      if (state.step !== 'sending') return state
      const { problem } = action
      const failed: FlowState = { step: 'problem', shot: state.shot, problem }
      if (!keepsPhoto(problem)) return failed
      if (problem.kind === 'refused') return { ...failed, photo: state.photo }
      const { fix, place, link } = state
      return { ...failed, photo: state.photo, again: link === undefined ? { fix, place } : { fix, place, link } }
    }

    case 'result':
      if (state.step !== 'waiting') return state
      return { step: 'result', shot: state.shot, result: action.result, fixAccuracyM: state.sent.accuracyM }

    case 'timedOut':
      if (state.step !== 'waiting') return state
      return { ...state, timedOut: true }

    // A new 600 s window on the same report, at the 15 s interval (C601). It never uploads.
    case 'checkAgain':
      if (state.step !== 'waiting' || !state.timedOut) return state
      return {
        ...state,
        timedOut: false,
        window: { startedAt: action.at, startElapsedMs: POLL.midForMs, deadlineAt: action.at + POLL.windowMs },
      }
  }
}

// The first poll after an upload: from the start of the schedule, and 600 s at most (C601).
export function firstWindow(at: number): PollWindow {
  return { startedAt: at, startElapsedMs: 0, deadlineAt: at + POLL.windowMs }
}

// An upload under way, or a wait still polling, goes on when the person leaves the screen.
export function survivesLeaving(state: FlowState): boolean {
  return state.step === 'sending' || (state.step === 'waiting' && !state.timedOut)
}

export function photoUsable(photo: Photo, now: number): boolean {
  return now - Date.parse(photo.capturedAt) < PHOTO_LIFE_MS
}

export function linkReusable(link: UploadLink, now: number): boolean {
  return now - link.at <= LINK_LIFE_MS
}

// A retry with the same photo: after an upload problem or a pause (a resend), or after MS4 found the location too
// coarse or the pin too far (a new fix). Every other problem asks for a new photo, or has no retry.
export function keepsPhoto(problem: Problem): boolean {
  if (problem.kind === 'upload' || problem.kind === 'paused') return true
  return problem.kind === 'refused' && (problem.code === 'gps_too_coarse' || problem.code === 'nudge_too_far')
}

const REFUSED_422 = new Set(['capture_too_old', 'capture_in_future', 'gps_too_coarse', 'nudge_too_far'])

// Why POST /uploads failed, after retryOnce had its say. Only failures on the way (a network error, a timeout, a
// 5xx, a throttle) are `upload`, which the person may retry with the same photo.
export function uploadProblem(err: unknown): Problem {
  if (err instanceof HttpError) {
    const { status, code } = err
    if (status === 503 && code === 'uploads_paused') return { kind: 'paused' }
    if (status === 429 && (code === 'device_limit' || code === 'global_cap')) return { kind: 'refused', code }
    if (status === 422 && code !== undefined && REFUSED_422.has(code)) return { kind: 'refused', code: code as RefusedCode }
    if ((status === 429 && code === undefined) || status >= 500) return { kind: 'upload' }
    return { kind: 'other' }
  }
  if (err instanceof TypeError || err instanceof RequestTimeoutError) return { kind: 'upload' }
  return { kind: 'other' }
}

// The person's own new pin on the map (C612), held until GET /map/pins shows it or 2 minutes pass. Its id is the
// report id, which GET /map/pins gives the same pin (MS4's C504).
export type OwnPin = Pin & { own: true }

// Only a done level result in live mode that the API published makes one (N1); its position is the one sent, and
// its accuracy the API's or else the fix's.
export function ownPinOf(result: ReportResult, sent: Sent): OwnPin | undefined {
  const { level, landmark, passability, basis, gpsAccuracyM, depthInMin, depthInMax } = result
  if (result.status !== 'done' || result.mode !== 'live' || result.published !== true) return undefined
  if (result.noFloodSeen === true) return undefined
  if (level === undefined || landmark === undefined || passability === undefined || basis === undefined) return undefined
  const pin: OwnPin = {
    id: result.reportId,
    lat: sent.lat,
    lng: sent.lng,
    capturedAt: sent.capturedAt,
    mode: 'live',
    flags: 0,
    gpsAccuracyM: typeof gpsAccuracyM === 'number' && Number.isFinite(gpsAccuracyM) ? gpsAccuracyM : sent.accuracyM,
    level,
    landmark,
    passability,
    levelIsFloor: result.levelIsFloor === true,
    basis,
    own: true,
  }
  return Number.isFinite(depthInMin) && Number.isFinite(depthInMax) ? { ...pin, depthInMin, depthInMax } : pin
}
