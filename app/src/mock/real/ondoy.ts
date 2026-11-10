// The portfolio demo's one real result (Nov 10, 2026). The demo answers every call from the mock, since the live system
// is shut down, but this sample shows what the live pipeline really returned for it: the face-blurred photo, the
// outlines it drew and its reading, as the live API served them on Nov 4. The photo is open-licensed (Wikimedia
// Commons, CC BY 2.0), and the credit says what Lusot changed, as the licence asks.
import { ONDOY_LAYERS, ONDOY_RESULT } from './ondoy-data'

// The two pictures live in app/demo/, and a demo build writes them to dist/demo/ (vite.config.ts's demoFiles), so no
// other build carries them.
const photoUrl = '/demo/ondoy-photo.jpg'
const overlayUrl = '/demo/ondoy-overlay.jpg'

// The live system's id for this sample (lusot-data's sample_sources.csv: OL002).
export const REAL_SAMPLE_ID = 'sc3cb512491'

// GET /samples' entry for it. The stored sample photo is the same face-blurred photo, without the outlines.
export const REAL_SAMPLE = {
  sampleId: REAL_SAMPLE_ID,
  credit:
    'Photo: Department of Foreign Affairs and Trade via Wikimedia Commons, CC BY 2.0 (https://creativecommons.org/licenses/by/2.0). Faces and plates blurred, and outlines drawn, by Lusot. A real saved result from the live system.',
  license: 'CC BY 2.0',
  date: '2009-10-08',
  event: 'Typhoon Ondoy',
  photoUrl,
}

export const REAL_LAYERS = ONDOY_LAYERS

// GET /reports/{id}'s final answer for a demo run of this sample: the saved result under the run's own id, with links
// the demo serves (the two pictures from the bundle, the layers from the mock's files origin).
export function realResultBody(reportId: string, layersUrl: string): Record<string, unknown> {
  return { ...ONDOY_RESULT, reportId, photoUrl, overlayUrl, layersUrl }
}
