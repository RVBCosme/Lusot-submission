import { afterEach, expect, it, vi } from 'vitest'

// apiFetch is chosen when its module loads, so each test sets the environment first and imports afterwards.
afterEach(() => {
  vi.unstubAllEnvs()
  vi.restoreAllMocks()
  vi.resetModules()
})

async function loadApiFetch() {
  vi.resetModules()
  return (await import('./apiFetch')).apiFetch
}

it('is the browser fetch when DEV is false, even with the mock switched on', async () => {
  vi.stubEnv('DEV', false)
  vi.stubEnv('VITE_API_MOCK', '1')
  expect(await loadApiFetch()).toBe(fetch)
})

it('is the browser fetch in development without the switch', async () => {
  vi.stubEnv('DEV', true)
  vi.stubEnv('VITE_API_MOCK', undefined)
  expect(await loadApiFetch()).toBe(fetch)
})

it('takes only "1" as the switch', async () => {
  vi.stubEnv('DEV', true)
  for (const value of ['', '0', 'true', 'yes', ' 1']) {
    vi.stubEnv('VITE_API_MOCK', value)
    expect(await loadApiFetch(), `VITE_API_MOCK=${JSON.stringify(value)}`).toBe(fetch)
  }
})

it('is the mock in development with VITE_API_MOCK=1', async () => {
  vi.stubEnv('DEV', true)
  vi.stubEnv('VITE_API_MOCK', '1')
  const apiFetch = await loadApiFetch()
  const { mockFetch } = await import('../mock/mockFetch')
  expect(apiFetch).toBe(mockFetch)
  expect(apiFetch).not.toBe(fetch)
})

it('is where every client function, the poll and the S3 upload go when no fetch is passed', async () => {
  vi.stubEnv('DEV', true)
  vi.stubEnv('VITE_API_MOCK', '1')
  vi.stubEnv('VITE_API_MOCK_SCENARIO', 'level_knee')
  vi.resetModules()
  const network = vi.spyOn(globalThis, 'fetch').mockRejectedValue(new Error('no network request is allowed here'))
  const api = await import('./api')
  const { pollReport } = await import('./poll')
  const base = 'https://mock.invalid'
  const device = '0f8e4a52-3c1d-4b7a-9e26-5d0c8b1f7a43'

  const request = {
    lat: 14.6095,
    lng: 120.9894,
    gpsAccuracyM: 12,
    capturedAt: new Date(Date.now() - 60_000).toISOString(),
    nudgeM: 0,
    consentVersion: '3f9a1c07',
  }
  const { reportId, upload } = await api.requestUpload(base, request, device)
  await api.postToS3(upload, new Blob(['jpeg'], { type: 'image/jpeg' }))
  // The poll's real clock would wait 2 s a time; an instant sleep keeps this test quick.
  const result = await pollReport(base, reportId, { sleep: async () => {} })
  expect(result).toMatchObject({ status: 'done', level: 'knee' })
  expect(await api.getLayers(result.layersUrl ?? '')).toMatchObject({ version: 1 })
  expect((await api.getPins(base)).length).toBeGreaterThan(0)
  const samples = await api.getSamples(base)
  expect(samples.length).toBeGreaterThan(0)
  expect(await api.runSample(base, samples[0].sampleId, device)).toHaveProperty('reportId')
  const [pin] = (await api.getPins(base)).filter((p) => p.mode === 'live')
  expect(await api.flagPin(base, pin.id, device)).toHaveProperty('flags')
  expect(await api.getReport(base, reportId)).toMatchObject({ reportId })
  expect(network).not.toHaveBeenCalled()
})
