import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import App from './App'
import { HttpError, pollReport, postToS3, requestUpload } from './lib/api'
import { capturePhoto, getFix } from './lib/capture'

vi.mock('./lib/capture', () => ({ capturePhoto: vi.fn(), getFix: vi.fn() }))
vi.mock('./lib/api', async (importOriginal) => ({
  ...(await importOriginal<typeof import('./lib/api')>()),
  requestUpload: vi.fn(),
  postToS3: vi.fn(),
  pollReport: vi.fn(),
}))

const ID = 'r_0123456789abcdef0123456789abcdef'
const PHOTO = { blob: new Blob(['jpeg bytes'], { type: 'image/jpeg' }), capturedAt: '2026-10-30T10:05:12.000Z' }
const UPLOAD = { url: 'https://lusot-test01-uploads.s3.ap-southeast-1.amazonaws.com/', fields: { key: `raw/${ID}.jpg` } }

beforeEach(() => {
  vi.mocked(capturePhoto).mockResolvedValue(PHOTO)
  vi.mocked(getFix).mockResolvedValue({ lat: 14.6095, lng: 120.9894, accuracyM: 12 })
})

afterEach(() => {
  cleanup()
  vi.resetAllMocks()
})

function takeAndUpload() {
  render(<App />)
  fireEvent.click(screen.getByRole('button', { name: 'Take photo and upload' }))
}

it('App shows the safety line', () => {
  render(<App />)

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

  expect(await screen.findByText(/Upload worked\. Analysis comes in a later build\./)).toBeTruthy()
  const apiUrl = import.meta.env.VITE_API_URL
  expect(requestUpload).toHaveBeenCalledWith(apiUrl, {
    lat: 14.6095,
    lng: 120.9894,
    gpsAccuracyM: 80,
    capturedAt: PHOTO.capturedAt,
  })
  expect(postToS3).toHaveBeenCalledWith(UPLOAD, PHOTO.blob)
  expect(pollReport).toHaveBeenCalledWith(apiUrl, ID)
  expect(screen.getByText(ID, { exact: false })).toBeTruthy()
  // A poor fix is uploaded anyway, with a warning.
  expect(screen.getByText(/GPS accuracy: 80 m/)).toBeTruthy()
  expect(screen.getByText(/worse than 50 m/)).toBeTruthy()
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
