import { useState } from 'react'
import { apiBaseUrl, HttpError, pollReport, postToS3, requestUpload, type ReportResult } from './lib/api'
import { capturePhoto, getFix } from './lib/capture'

// Read once at load (R31). Tests pass their own apiUrl.
const API_URL = apiBaseUrl(import.meta.env.VITE_API_URL)
const POOR_ACCURACY_M = 50

const STEPS = {
  photo: 'Taking the photo',
  location: 'Reading the location',
  link: 'Asking for an upload link',
  upload: 'Uploading the photo',
  analysis: 'Waiting for the analysis',
  done: 'Done',
}
type Step = keyof typeof STEPS

interface Problem {
  message: string
  detail: string
}

const NO_API_URL: Problem = {
  message: 'This build has no API address, so it cannot upload.',
  detail: 'VITE_API_URL is not set. Put it in app/.env.local, then build again.',
}

function App({ apiUrl = API_URL }: { apiUrl?: string }) {
  const [busy, setBusy] = useState(false)
  const [step, setStep] = useState<Step>()
  const [accuracyM, setAccuracyM] = useState<number>()
  const [reportId, setReportId] = useState<string>()
  const [result, setResult] = useState<string>()
  const [problem, setProblem] = useState<Problem>()
  const shownProblem = problem ?? (apiUrl === '' ? NO_API_URL : undefined)

  async function takeAndUpload() {
    // The `step` state is stale inside this closure, so the run keeps its own copy for the error message.
    let current: Step = 'photo'
    const advance = (next: Step) => {
      current = next
      setStep(next)
    }
    setBusy(true)
    setAccuracyM(undefined)
    setReportId(undefined)
    setResult(undefined)
    setProblem(undefined)
    try {
      advance('photo')
      const { blob, capturedAt } = await capturePhoto()
      advance('location')
      const fix = await getFix()
      setAccuracyM(fix.accuracyM)
      advance('link')
      const { reportId: id, upload } = await requestUpload(apiUrl, {
        lat: fix.lat,
        lng: fix.lng,
        gpsAccuracyM: fix.accuracyM,
        capturedAt,
      })
      setReportId(id)
      advance('upload')
      await postToS3(upload, blob)
      advance('analysis')
      setResult(describeResult(await pollReport(apiUrl, id)))
      advance('done')
    } catch (err) {
      setProblem(describeProblem(current, err))
    } finally {
      setBusy(false)
    }
  }

  return (
    <main className="safe-area mx-auto flex min-h-dvh max-w-md flex-col gap-4">
      <h1 className="text-xl font-bold">Lusot: MS1 test build</h1>
      <button
        type="button"
        onClick={takeAndUpload}
        disabled={busy || apiUrl === ''}
        className="rounded border px-4 py-2 disabled:opacity-50"
      >
        Take photo and upload
      </button>
      <div role="status" className="flex flex-col gap-1">
        {step && <p>Step: {STEPS[step]}</p>}
        {accuracyM !== undefined && (
          <p>
            GPS accuracy: {Math.round(accuracyM)} m
            {accuracyM > POOR_ACCURACY_M && `. Warning: worse than ${POOR_ACCURACY_M} m.`}
          </p>
        )}
        {reportId && <p>Report: {reportId}</p>}
        {result && <p>Final status: {result}</p>}
      </div>
      {shownProblem && (
        <div role="alert" className="flex flex-col gap-1">
          <p>{shownProblem.message}</p>
          <p>Details: {shownProblem.detail}</p>
        </div>
      )}
      <footer className="mt-auto text-sm">
        Lusot estimates depth at one spot. It is not advice to cross. Follow MMDA and local advisories.
      </footer>
    </main>
  )
}

function describeResult({ status, refusalReason }: ReportResult): string {
  if (refusalReason === 'pipeline_not_built') return 'Upload worked. Analysis comes in a later build.'
  return refusalReason === undefined ? status : `${status} (${refusalReason})`
}

function describeProblem(step: Step, err: unknown): Problem {
  const detail = err instanceof Error ? err.message : String(err)
  if (step === 'location') {
    return {
      message: 'Could not read the location. Turn on location and allow it for Lusot, then try again. Nothing was uploaded.',
      detail,
    }
  }
  if (err instanceof HttpError && err.code === 'capture_too_old') {
    return {
      message:
        "The phone's clock or the photo time is off by more than 15 minutes. Check the phone's date and time, then take a new photo. Nothing was uploaded.",
      detail,
    }
  }
  if (err instanceof HttpError && err.code === 'capture_in_future') {
    return {
      message: "The phone's clock is ahead of the real time. Check the clock, then try again. Nothing was uploaded.",
      detail,
    }
  }
  if (err instanceof HttpError && err.code === 'uploads_paused') {
    return { message: 'Uploads are paused for now. Try again later. Nothing was uploaded.', detail }
  }
  return { message: `${STEPS[step]} did not work.`, detail }
}

export default App
