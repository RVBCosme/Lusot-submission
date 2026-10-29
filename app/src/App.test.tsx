import { cleanup, fireEvent, render, screen, within } from '@testing-library/react'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import App from './App'
import { HttpError, pollReport, PollTimeoutError, postToS3, requestUpload, type ReportResult } from './lib/api'
import { capturePhoto, getFix } from './lib/capture'

vi.mock('./lib/capture', () => ({ capturePhoto: vi.fn(), getFix: vi.fn() }))
vi.mock('./lib/api', async (importOriginal) => ({
  ...(await importOriginal<typeof import('./lib/api')>()),
  requestUpload: vi.fn(),
  postToS3: vi.fn(),
  pollReport: vi.fn(),
}))

const API = 'https://api.example.test'
const ID = 'r_0123456789abcdef0123456789abcdef'
const PHOTO = { blob: new Blob(['jpeg bytes'], { type: 'image/jpeg' }), capturedAt: '2026-10-30T10:05:12.000Z' }
const UPLOAD = { url: 'https://lusot-test01-uploads.s3.ap-southeast-1.amazonaws.com/', fields: { key: `raw/${ID}.jpg` } }
// Level results as pollReport returns them (C67). This one is a knee reading from a wheel and a person.
const KNEE: ReportResult = {
  status: 'done',
  noFloodSeen: false,
  level: 'knee',
  landmark: 'rim_three_quarters',
  passability: 'NPLV',
  basis: { vehicles: 1, people: 1 },
  levelIsFloor: false,
}
// A covered wheel reads tire deep or deeper.
const TIRE_FLOOR: ReportResult = {
  ...KNEE,
  level: 'tire',
  landmark: 'wheel_covered',
  passability: 'NPATV',
  basis: { vehicles: 1, people: 0 },
  levelIsFloor: true,
}
const BELOW_GUTTER: ReportResult = { ...KNEE, level: 'below_gutter', landmark: 'tire_only', passability: 'PATV' }
const ABOVE_CHEST: ReportResult = {
  ...KNEE,
  level: 'above_chest',
  landmark: 'above_chest',
  passability: 'NPATV',
  basis: { vehicles: 0, people: 1 },
}

beforeEach(() => {
  vi.mocked(capturePhoto).mockResolvedValue(PHOTO)
  vi.mocked(getFix).mockResolvedValue({ lat: 14.6095, lng: 120.9894, accuracyM: 12 })
})

afterEach(() => {
  cleanup()
  vi.resetAllMocks()
})

function takeAndUpload() {
  render(<App apiUrl={API} />)
  fireEvent.click(screen.getByRole('button', { name: 'Take photo and upload' }))
}

// Takes and uploads a photo whose poll ends in `outcome`, or times out, and returns the status region.
function takeAndUploadWith(outcome: ReportResult | 'timeout') {
  vi.mocked(requestUpload).mockResolvedValue({ reportId: ID, upload: UPLOAD })
  vi.mocked(postToS3).mockResolvedValue()
  if (outcome === 'timeout') vi.mocked(pollReport).mockRejectedValue(new PollTimeoutError(ID, 120_000))
  else vi.mocked(pollReport).mockResolvedValue(outcome)
  takeAndUpload()
  return screen.getByRole('status')
}

it('App shows the safety line', () => {
  render(<App apiUrl={API} />)

  expect(
    screen.getByText('Lusot estimates depth at one spot. It is not advice to cross. Follow MMDA and local advisories.'),
  ).toBeTruthy()
})

it('App uploads the photo and shows the result', async () => {
  vi.mocked(getFix).mockResolvedValue({ lat: 14.6095, lng: 120.9894, accuracyM: 80 })
  vi.mocked(requestUpload).mockResolvedValue({ reportId: ID, upload: UPLOAD })
  vi.mocked(postToS3).mockResolvedValue()
  vi.mocked(pollReport).mockResolvedValue({ status: 'failed', refusalReason: 'pipeline_not_built' })

  takeAndUpload()

  // The status lines sit in a live region, so a screen reader announces the result.
  const status = screen.getByRole('status')
  // The message comes from the status, never from the reason (C50).
  expect(await within(status).findByText('Processing failed, try again.')).toBeTruthy()
  expect(within(status).getByText('Reason: pipeline_not_built')).toBeTruthy()
  expect(requestUpload).toHaveBeenCalledWith(API, {
    lat: 14.6095,
    lng: 120.9894,
    gpsAccuracyM: 80,
    capturedAt: PHOTO.capturedAt,
  })
  expect(postToS3).toHaveBeenCalledWith(UPLOAD, PHOTO.blob)
  expect(pollReport).toHaveBeenCalledWith(API, ID)
  expect(within(status).getByText(ID, { exact: false })).toBeTruthy()
  // A poor fix is uploaded anyway, with a warning.
  expect(within(status).getByText(/GPS accuracy: 80 m/)).toBeTruthy()
  expect(within(status).getByText(/worse than 50 m/)).toBeTruthy()
})

it('App names VITE_API_URL when the build has no API address', () => {
  render(<App apiUrl="" />)

  expect(screen.getByText(/VITE_API_URL/)).toBeTruthy()
  const button = screen.getByRole<HTMLButtonElement>('button', { name: 'Take photo and upload' })
  expect(button.disabled).toBe(true)
  fireEvent.click(button)
  expect(capturePhoto).not.toHaveBeenCalled()
})

it('App reports a denied location without uploading', async () => {
  vi.mocked(getFix).mockRejectedValue(new Error('User denied Geolocation'))

  takeAndUpload()

  expect(await screen.findByText(/Could not read the location/)).toBeTruthy()
  expect(requestUpload).not.toHaveBeenCalled()
  expect(postToS3).not.toHaveBeenCalled()
})

it("App shows the API's refusal", async () => {
  vi.mocked(requestUpload).mockRejectedValue(new HttpError(422, 'capture_too_old'))

  takeAndUpload()

  expect(await screen.findByText(/clock or the photo time is off by more than 15 minutes/)).toBeTruthy()
  expect(postToS3).not.toHaveBeenCalled()
})

it('App explains a phone clock that runs ahead', async () => {
  vi.mocked(requestUpload).mockRejectedValue(new HttpError(422, 'capture_in_future'))

  takeAndUpload()

  expect(await screen.findByText(/clock is ahead of the real time/)).toBeTruthy()
  expect(screen.queryByText(/15 minutes/)).toBeNull()
  expect(postToS3).not.toHaveBeenCalled()
})

it('App says when uploads are paused', async () => {
  vi.mocked(requestUpload).mockRejectedValue(new HttpError(503, 'uploads_paused'))

  takeAndUpload()

  expect(await screen.findByText(/Uploads are paused for now/)).toBeTruthy()
  expect(postToS3).not.toHaveBeenCalled()
})

it('App shows a level result', async () => {
  const status = takeAndUploadWith(KNEE)

  expect(await within(status).findByText('Knee deep at this spot (MMDA level).')).toBeTruthy()
  expect(within(status).getByText('MMDA lists this level as not passable to light vehicles (NPLV).')).toBeTruthy()
  expect(within(status).getByText('From 2 reference objects.')).toBeTruthy()
})

it('App says at least for a floor', async () => {
  const status = takeAndUploadWith(TIRE_FLOOR)

  expect(await within(status).findByText('At least tire deep at this spot (MMDA level).')).toBeTruthy()
  expect(within(status).getByText('MMDA lists this level as not passable to any vehicle (NPATV).')).toBeTruthy()
  expect(within(status).getByText('From 1 reference object.')).toBeTruthy()
})

// CLAUDE.md never calls the 9 levels MMDA's, so the two added levels name the MMDA level they lie beyond (C81).
it.each([
  {
    report: BELOW_GUTTER,
    levelLine: 'Below gutter deep at this spot.',
    classLine: "Shallower than MMDA's gutter level, which MMDA lists as passable to all vehicles (PATV).",
  },
  {
    report: ABOVE_CHEST,
    levelLine: 'Above chest deep at this spot.',
    classLine: "Deeper than MMDA's chest level, which MMDA lists as not passable to any vehicle (NPATV).",
  },
])("App never calls the two added levels MMDA's: $report.level", async ({ report, levelLine, classLine }) => {
  const status = takeAndUploadWith(report)

  expect(await within(status).findByText(levelLine)).toBeTruthy()
  expect(within(status).getByText(classLine)).toBeTruthy()
  expect(document.body.textContent).not.toContain('(MMDA level)')
})

it('App shows no flood seen', async () => {
  const status = takeAndUploadWith({ status: 'done', noFloodSeen: true })

  expect(await within(status).findByText('No flood seen.')).toBeTruthy()
})

it('App shows a refusal and its reason', async () => {
  const status = takeAndUploadWith({ status: 'refused', refusalReason: 'too_dark' })

  // D19's line, which Rene confirmed.
  expect(
    await within(status).findByText(
      "I can't tell from this photo. Retake it from a dry spot with a parked car's wheel or a person standing still in view. Don't step into the water or the road.",
    ),
  ).toBeTruthy()
  expect(within(status).getByText('Reason: too_dark')).toBeTruthy()
})

it('App shows processing failed and its reason', async () => {
  const status = takeAndUploadWith({ status: 'failed', refusalReason: 'model_error' })

  expect(await within(status).findByText('Processing failed, try again.')).toBeTruthy()
  expect(within(status).getByText('Reason: model_error')).toBeTruthy()
})

it('A poll timeout reads as processing failed', async () => {
  const status = takeAndUploadWith('timeout')

  expect(await within(status).findByText('Processing failed, try again.')).toBeTruthy()
  // Not a step that "did not work".
  expect(screen.queryByRole('alert')).toBeNull()
})

it.each<[string, ReportResult | 'timeout']>([
  ['failed/pipeline_not_built', { status: 'failed', refusalReason: 'pipeline_not_built' }],
  ['a level', KNEE],
  ['a floor', TIRE_FLOOR],
  ['below_gutter', BELOW_GUTTER],
  ['above_chest', ABOVE_CHEST],
  ['no flood seen', { status: 'done', noFloodSeen: true }],
  ['refused/too_dark', { status: 'refused', refusalReason: 'too_dark' }],
  ['failed/model_error', { status: 'failed', refusalReason: 'model_error' }],
  ['a poll timeout', 'timeout'],
])('no screen uses the banned word: %s', async (_state, outcome) => {
  const status = takeAndUploadWith(outcome)

  // The run has ended, so the screen is final.
  await within(status).findByText('Step: Done')
  expect(document.body.textContent).not.toMatch(/\bsafe\b/i)
})
