import { useState } from 'react'
import { apiBaseUrl, HttpError, pollReport, PollTimeoutError, postToS3, requestUpload, type ReportResult } from './lib/api'
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

interface ResultLines {
  lines: string[] // one <p> each, so each line can be matched exactly
  reason?: string // refused and failed only, a small line for testing (spec §3.8)
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
  const [result, setResult] = useState<ResultLines>()
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
      // A poll timeout reads as processing failed, not as a step that didn't work (spec §3.8).
      const report = await pollReport(apiUrl, id).catch((err: unknown): ReportResult => {
        if (err instanceof PollTimeoutError) return { status: 'failed' }
        throw err
      })
      setResult(describeResult(report))
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
        {result?.lines.map((line) => <p key={line}>{line}</p>)}
        {result?.reason !== undefined && <p className="text-xs">Reason: {result.reason}</p>}
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

// Test-build wording until MS5 and Rene's review (spec §3.8, C81, M20). The 9 levels, shallowest first:
const LEVEL_WORDS: Record<string, string> = {
  below_gutter: 'Below gutter deep',
  gutter: 'Gutter deep',
  half_knee: 'Half-knee deep',
  half_tire: 'Half-tire deep',
  knee: 'Knee deep',
  tire: 'Tire deep',
  waist: 'Waist deep',
  chest: 'Chest deep',
  above_chest: 'Above chest deep',
}

// Below gutter and above chest aren't MMDA's levels (CLAUDE.md). So their lines never say "MMDA level", and they
// name the MMDA level they lie beyond in place of a class (C81).
const BEYOND_MMDA: Partial<Record<string, string>> = {
  below_gutter: "Shallower than MMDA's gutter level, which MMDA lists as passable to all vehicles (PATV).",
  above_chest: "Deeper than MMDA's chest level, which MMDA lists as not passable to any vehicle (NPATV).",
}

const CLASS_WORDS: Record<string, string> = {
  PATV: 'passable to all vehicles',
  NPLV: 'not passable to light vehicles',
  NPATV: 'not passable to any vehicle',
}

// D19's line, which Rene confirmed. Plan §9's own line uses a word CLAUDE.md bans.
const CANT_TELL =
  "I can't tell from this photo. Retake it from a dry spot with a parked car's wheel or a person standing still in view. Don't step into the water or the road."

// The message comes from the status, never from the reason, which shows only as a small test line (C50).
function describeResult(result: ReportResult): ResultLines {
  const { status, refusalReason, noFloodSeen, level, passability, basis, levelIsFloor } = result
  if (status === 'refused') return { lines: [CANT_TELL], reason: refusalReason }
  if (status === 'done' && noFloodSeen) return { lines: ['No flood seen.'] }
  if (status === 'done' && level !== undefined && passability !== undefined && basis !== undefined) {
    // A floor means this level or deeper (C54).
    const words = levelIsFloor ? `At least ${LEVEL_WORDS[level].toLowerCase()}` : LEVEL_WORDS[level]
    const beyond = BEYOND_MMDA[level]
    const references = basis.vehicles + basis.people
    return {
      lines: [
        beyond === undefined ? `${words} at this spot (MMDA level).` : `${words} at this spot.`,
        beyond ?? `MMDA lists this level as ${CLASS_WORDS[passability]} (${passability}).`,
        `From ${references} reference object${references === 1 ? '' : 's'}.`,
      ],
    }
  }
  // failed, or a poll timeout
  return { lines: ['Processing failed, try again.'], reason: refusalReason }
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
