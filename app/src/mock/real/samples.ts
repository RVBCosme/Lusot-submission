// The portfolio demo's real results (Nov 10, 2026). The demo answers every call from the mock, since the live system
// is shut down, but its nine credited samples show what the live pipeline really returned for them on Nov 4: the
// reading or the refusal, and for a level its face-blurred photo, the outlines it drew and their layers. The photos are
// open-licensed (Wikimedia Commons), each with its live credit line, which says what Lusot changed.
import { REAL_SAMPLE_DATA, type RealSampleData } from './samples-data'

// The pictures live in app/demo/, and a demo build writes them to dist/demo/ (vite.config.ts's demoFiles), so no other
// build carries them.
const photoUrl = (sampleId: string) => `/demo/${sampleId}.jpg`
const overlayUrl = (sampleId: string) => `/demo/${sampleId}-overlay.jpg`

export function realSample(sampleId: string): RealSampleData | undefined {
  return REAL_SAMPLE_DATA.find((sample) => sample.entry.sampleId === sampleId)
}

// GET /samples' entries for them, in the fixture's order (the flood readings first).
export function realSampleEntries(): Record<string, unknown>[] {
  return REAL_SAMPLE_DATA.map(({ entry }) => ({ ...entry, photoUrl: photoUrl(entry.sampleId) }))
}

// GET /reports/{id}'s final answer for a demo run of a real sample: its saved live result under the run's own id. A
// level gets links the demo serves (the two pictures from dist/demo/, the layers from the mock's files origin).
export function realResultBody(sample: RealSampleData, reportId: string, layersUrl: string): Record<string, unknown> {
  const body: Record<string, unknown> = { ...sample.result, reportId }
  if (sample.overlay) {
    const id = sample.entry.sampleId
    Object.assign(body, { photoUrl: photoUrl(id), overlayUrl: overlayUrl(id), layersUrl })
  }
  return body
}
