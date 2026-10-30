import { Capacitor } from '@capacitor/core'
import { Geolocation, type Position, type PositionOptions, type WatchPositionCallback } from '@capacitor/geolocation'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { EN } from '../i18n/en'
import { FIL } from '../i18n/fil'
import { offsetM, offsetOf } from '../test/geo'
import geoSource from './geo.ts?raw'
import {
  clampToRadius,
  distanceM,
  LocationDenied,
  locationLine,
  moveM,
  nudgeM,
  PoorFix,
  waitForFix,
  type LatLng,
} from './geo'

// The plugin's own singleton. Only its permission call is used for real (and mocked here); the watch is always a fake.
vi.mock('@capacitor/geolocation', () => ({
  Geolocation: { requestPermissions: vi.fn(), watchPosition: vi.fn(), clearWatch: vi.fn() },
}))

const ORIGIN: LatLng = { lat: 14.6, lng: 121 }

describe('distanceM', () => {
  it('is about 111.2 m for a thousandth of a degree of latitude, and 0 for the same point', () => {
    expect(distanceM({ lat: 14.6, lng: 121 }, { lat: 14.601, lng: 121 })).toBeCloseTo(111.2, 1)
    expect(distanceM(ORIGIN, ORIGIN)).toBe(0)
  })

  it('is the same both ways, and follows a degree of longitude at this latitude', () => {
    const there = { lat: 14.61, lng: 121.02 }
    expect(distanceM(ORIGIN, there)).toBeCloseTo(distanceM(there, ORIGIN), 6)
    // 0.001 degree of longitude is 111.2 m times the cosine of 14.6 degrees.
    expect(distanceM(ORIGIN, { lat: 14.6, lng: 121.001 })).toBeCloseTo(111.195 * Math.cos((14.6 * Math.PI) / 180), 1)
  })
})

describe('clampToRadius', () => {
  it('brings a point 300 m away back to 100 m, along the same bearing', () => {
    const target = offsetM(ORIGIN, 300 * Math.cos(Math.PI / 6), 300 * Math.sin(Math.PI / 6))
    expect(distanceM(ORIGIN, target)).toBeCloseTo(300, 0)

    const clamped = clampToRadius(ORIGIN, target)
    expect(Math.abs(distanceM(ORIGIN, clamped) - 100)).toBeLessThan(0.5)
    const { northM, eastM } = offsetOf(ORIGIN, clamped)
    expect(Math.abs(northM - 100 * Math.cos(Math.PI / 6))).toBeLessThan(0.5)
    expect(Math.abs(eastM - 100 * Math.sin(Math.PI / 6))).toBeLessThan(0.5)
  })

  it('clamps in every direction, and to another radius when one is given', () => {
    for (const bearing of [0, 90, 180, 270, 225]) {
      const rad = (bearing * Math.PI) / 180
      const clamped = clampToRadius(ORIGIN, offsetM(ORIGIN, 400 * Math.cos(rad), 400 * Math.sin(rad)))
      expect(Math.abs(distanceM(ORIGIN, clamped) - 100)).toBeLessThan(0.5)
    }
    const near = clampToRadius(ORIGIN, offsetM(ORIGIN, 0, 300), 20)
    expect(Math.abs(distanceM(ORIGIN, near) - 20)).toBeLessThan(0.5)
  })

  it('leaves a point 40 m away, one exactly 100 m away and the origin itself alone', () => {
    const forty = offsetM(ORIGIN, 24, 32)
    expect(clampToRadius(ORIGIN, forty)).toEqual(forty)
    const hundred = clampToRadius(ORIGIN, offsetM(ORIGIN, 0, 250))
    expect(clampToRadius(ORIGIN, hundred)).toEqual(hundred)
    expect(clampToRadius(ORIGIN, ORIGIN)).toEqual(ORIGIN)
  })

  it('keeps a longitude inside -180 to 180 when the clamp crosses the date line', () => {
    const edge = { lat: 0, lng: 179.9995 }
    const clamped = clampToRadius(edge, { lat: 0, lng: -179.99 })
    expect(clamped.lng).toBeGreaterThanOrEqual(-180)
    expect(clamped.lng).toBeLessThanOrEqual(180)
    expect(Math.abs(distanceM(edge, clamped) - 100)).toBeLessThan(0.5)
  })
})

describe('moveM', () => {
  it('moves the point by the metres asked, north and east, to within a centimetre at 10 m', () => {
    expect(Math.abs(distanceM(ORIGIN, moveM(ORIGIN, 10, 0)) - 10)).toBeLessThan(0.01)
    expect(Math.abs(distanceM(ORIGIN, moveM(ORIGIN, 0, 10)) - 10)).toBeLessThan(0.01)
    expect(Math.abs(distanceM(ORIGIN, moveM(ORIGIN, 6, 8)) - 10)).toBeLessThan(0.01)
    expect(moveM(ORIGIN, 10, 0).lat).toBeGreaterThan(ORIGIN.lat)
    expect(moveM(ORIGIN, 0, -10).lng).toBeLessThan(ORIGIN.lng)
    expect(moveM(ORIGIN, 0, 0)).toEqual(ORIGIN)
  })
})

describe('nudgeM', () => {
  it('is 0 for no move, rounds the distance, and never exceeds 100', () => {
    expect(nudgeM(ORIGIN, ORIGIN)).toBe(0)
    expect(nudgeM(ORIGIN, offsetM(ORIGIN, 0, 40.4))).toBe(40)
    expect(nudgeM(ORIGIN, offsetM(ORIGIN, 0, 40.6))).toBe(41)
    expect(nudgeM(ORIGIN, offsetM(ORIGIN, 0, 100.4))).toBe(100)
    expect(nudgeM(ORIGIN, offsetM(ORIGIN, 0, 300))).toBe(100)
    expect(nudgeM(ORIGIN, offsetM(ORIGIN, 5000, 5000))).toBe(100)
  })

  it('is a whole number from 0 to 100 for a clamped point, whatever the target', () => {
    for (const metres of [0, 1, 49.5, 99.9, 100, 100.6, 250, 3000]) {
      const value = nudgeM(ORIGIN, clampToRadius(ORIGIN, offsetM(ORIGIN, metres, 0)))
      expect(Number.isInteger(value)).toBe(true)
      expect(value).toBeGreaterThanOrEqual(0)
      expect(value).toBeLessThanOrEqual(100)
    }
  })
})

// A position of this accuracy at this place, as the plugin hands it to a watch's callback.
function position(accuracy: number, at: LatLng = ORIGIN): Position {
  return {
    timestamp: 0,
    coords: { latitude: at.lat, longitude: at.lng, accuracy, altitude: null, altitudeAccuracy: null, speed: null, heading: null },
  } as Position
}

// A watch that records how it was started and stopped, and whose callback a test calls by hand.
function fakeWatch(id = 'w1') {
  let callback: WatchPositionCallback | undefined
  const options: PositionOptions[] = []
  const watch = {
    watchPosition: vi.fn(async (opts: PositionOptions, cb: WatchPositionCallback) => {
      options.push(opts)
      callback = cb
      return id
    }),
    clearWatch: vi.fn(async (_options: { id: string }) => {}),
  }
  return {
    watch,
    options,
    fix: (accuracy: number, at?: LatLng) => callback?.(position(accuracy, at)),
    fail: (err: unknown) => callback?.(null, err),
  }
}

function track<T>(promise: Promise<T>) {
  const outcome: { state: 'pending' | 'resolved' | 'rejected'; value?: unknown } = { state: 'pending' }
  promise.then(
    (value) => {
      outcome.state = 'resolved'
      outcome.value = value
    },
    (reason: unknown) => {
      outcome.state = 'rejected'
      outcome.value = reason
    },
  )
  return outcome
}

beforeEach(() => {
  vi.useFakeTimers()
  vi.mocked(Geolocation.requestPermissions).mockReset()
})

afterEach(() => {
  vi.useRealTimers()
  vi.restoreAllMocks()
})

describe('waitForFix on the web', () => {
  it('resolves on the first fix at 12 m, and clears the watch it started', async () => {
    const fake = fakeWatch('w7')
    const outcome = track(waitForFix({ watch: fake.watch }))
    fake.fix(12, { lat: 14.6123, lng: 121.0456 })
    await vi.advanceTimersByTimeAsync(0)

    expect(outcome).toEqual({ state: 'resolved', value: { lat: 14.6123, lng: 121.0456, accuracyM: 12 } })
    expect(fake.watch.clearWatch).toHaveBeenCalledExactlyOnceWith({ id: 'w7' })
  })

  it('asks the watch for high accuracy and a 20 s timeout, with no Android-only options on the web', async () => {
    const fake = fakeWatch()
    void waitForFix({ watch: fake.watch })
    expect(fake.options).toEqual([{ enableHighAccuracy: true, timeout: 20_000 }])
    expect(Geolocation.requestPermissions).not.toHaveBeenCalled()
  })

  it('takes 50 m as good enough and 50.1 m as not', async () => {
    const fake = fakeWatch()
    const outcome = track(waitForFix({ watch: fake.watch }))
    fake.fix(50.1)
    await vi.advanceTimersByTimeAsync(0)
    expect(outcome.state).toBe('pending')
    fake.fix(50)
    await vi.advanceTimersByTimeAsync(0)
    expect(outcome.state).toBe('resolved')
    expect(outcome.value).toMatchObject({ accuracyM: 50 })
  })

  it('takes goodM and maxWaitMs from its options', async () => {
    const fake = fakeWatch()
    const outcome = track(waitForFix({ watch: fake.watch, goodM: 20, maxWaitMs: 5_000 }))
    expect(fake.options[0]?.timeout).toBe(5_000)
    fake.fix(30)
    await vi.advanceTimersByTimeAsync(4_999)
    expect(outcome.state).toBe('pending')
    await vi.advanceTimersByTimeAsync(1)
    expect(outcome.state).toBe('rejected')
    expect(outcome.value).toEqual(new PoorFix(30))
  })

  it('with fixes at 80 m and 65 m, rejects with PoorFix(65) 20,000 ms after the first update, not before', async () => {
    const fake = fakeWatch()
    const outcome = track(waitForFix({ watch: fake.watch }))
    fake.fix(80)
    await vi.advanceTimersByTimeAsync(5_000)
    fake.fix(65)
    await vi.advanceTimersByTimeAsync(14_999)
    expect(outcome.state).toBe('pending')
    expect(fake.watch.clearWatch).not.toHaveBeenCalled()

    await vi.advanceTimersByTimeAsync(1)
    expect(outcome.state).toBe('rejected')
    expect(outcome.value).toBeInstanceOf(PoorFix)
    expect((outcome.value as PoorFix).bestAccuracyM).toBe(65)
    expect(fake.watch.clearWatch).toHaveBeenCalledExactlyOnceWith({ id: 'w1' })
  })

  it('keeps the best accuracy, not the last, when the fixes get worse', async () => {
    const fake = fakeWatch()
    const outcome = track(waitForFix({ watch: fake.watch }))
    fake.fix(65)
    fake.fix(120)
    await vi.advanceTimersByTimeAsync(20_000)
    expect((outcome.value as PoorFix).bestAccuracyM).toBe(65)
  })

  it('a good fix inside the window wins, and later updates change nothing', async () => {
    const fake = fakeWatch()
    const outcome = track(waitForFix({ watch: fake.watch }))
    fake.fix(90)
    await vi.advanceTimersByTimeAsync(19_000)
    fake.fix(40)
    fake.fix(10)
    await vi.advanceTimersByTimeAsync(30_000)

    expect(outcome.state).toBe('resolved')
    expect(outcome.value).toMatchObject({ accuracyM: 40 })
    expect(fake.watch.clearWatch).toHaveBeenCalledOnce()
  })

  it('the 20 s window starts at the first position: no update for 60,000 ms raises nothing', async () => {
    const fake = fakeWatch()
    const outcome = track(waitForFix({ watch: fake.watch }))
    await vi.advanceTimersByTimeAsync(60_000)
    expect(outcome.state).toBe('pending')
    expect(fake.watch.clearWatch).not.toHaveBeenCalled()

    fake.fix(80)
    await vi.advanceTimersByTimeAsync(19_999)
    expect(outcome.state).toBe('pending')
    await vi.advanceTimersByTimeAsync(1)
    expect(outcome.state).toBe('rejected')
    expect(outcome.value).toEqual(new PoorFix(80))
  })

  it('ignores an update with no usable numbers, and does not start the window for it', async () => {
    const fake = fakeWatch()
    const outcome = track(waitForFix({ watch: fake.watch }))
    fake.fix(Number.NaN)
    fake.fix(10, { lat: Number.NaN, lng: 121 })
    await vi.advanceTimersByTimeAsync(40_000)
    expect(outcome.state).toBe('pending')
  })

  it('a timeout before any position rejects with PoorFix(undefined): the web code 3, as a number or a name', async () => {
    for (const err of [{ code: 3, message: 'Timeout expired' }, { code: 'OS-PLUG-GLOC-0010', message: 'Timed out' }]) {
      const fake = fakeWatch()
      const outcome = track(waitForFix({ watch: fake.watch }))
      fake.fail(err)
      await vi.advanceTimersByTimeAsync(0)

      expect(outcome.state).toBe('rejected')
      expect(outcome.value).toBeInstanceOf(PoorFix)
      expect((outcome.value as PoorFix).bestAccuracyM).toBeUndefined()
      expect(fake.watch.clearWatch).toHaveBeenCalledOnce()
    }
  })

  it('a timeout after a position does not end the window early', async () => {
    const fake = fakeWatch()
    const outcome = track(waitForFix({ watch: fake.watch }))
    fake.fix(80)
    await vi.advanceTimersByTimeAsync(10_000)
    fake.fail({ code: 3 })
    fake.fail({ code: 'OS-PLUG-GLOC-0010' })
    await vi.advanceTimersByTimeAsync(9_999)
    expect(outcome.state).toBe('pending')
    fake.fix(30)
    await vi.advanceTimersByTimeAsync(0)
    expect(outcome.value).toMatchObject({ accuracyM: 30 })
  })

  it('a refused permission rejects with LocationDenied, with the browser code named', async () => {
    const fake = fakeWatch()
    const outcome = track(waitForFix({ watch: fake.watch }))
    fake.fail({ code: 1, message: 'User denied Geolocation' })
    await vi.advanceTimersByTimeAsync(0)

    expect(outcome.state).toBe('rejected')
    expect(outcome.value).toBeInstanceOf(LocationDenied)
    expect((outcome.value as LocationDenied).code).toBe('PERMISSION_DENIED')
    expect(fake.watch.clearWatch).toHaveBeenCalledOnce()
  })

  it('before any position, any other error rejects with LocationDenied and the code as it came', async () => {
    const cases: [unknown, string][] = [
      [{ code: 'OS-PLUG-GLOC-0007', message: 'Location services are not enabled' }, 'OS-PLUG-GLOC-0007'],
      [{ code: 'OS-PLUG-GLOC-0002' }, 'OS-PLUG-GLOC-0002'],
      [{ code: 2 }, 'POSITION_UNAVAILABLE'],
      [new Error('Something else'), 'unknown'],
    ]
    for (const [err, code] of cases) {
      const fake = fakeWatch()
      const outcome = track(waitForFix({ watch: fake.watch }))
      fake.fail(err)
      await vi.advanceTimersByTimeAsync(0)
      expect(outcome.value).toEqual(new LocationDenied(code))
      expect(fake.watch.clearWatch).toHaveBeenCalledOnce()
    }
  })

  it("after a position, only a refused permission ends the wait early, the browser's code or the plugin's", async () => {
    for (const code of [1, 'OS-PLUG-GLOC-0003']) {
      const fake = fakeWatch()
      const outcome = track(waitForFix({ watch: fake.watch }))
      fake.fix(80)
      fake.fail({ code })
      await vi.advanceTimersByTimeAsync(0)
      expect(outcome.state).toBe('rejected')
      expect(outcome.value).toBeInstanceOf(LocationDenied)
      expect(fake.watch.clearWatch).toHaveBeenCalledOnce()
    }
  })

  it('after a position, any other error is ignored and the 20 s window decides', async () => {
    const fake = fakeWatch()
    const outcome = track(waitForFix({ watch: fake.watch }))
    fake.fix(80)
    await vi.advanceTimersByTimeAsync(5_000)
    for (const code of [2, 'OS-PLUG-GLOC-0002', 'OS-PLUG-GLOC-0007', 'OS-PLUG-GLOC-0015', 'what-is-this']) {
      fake.fail({ code })
    }
    fake.fail(new Error('no code at all'))
    await vi.advanceTimersByTimeAsync(0)
    expect(outcome.state).toBe('pending')
    expect(fake.watch.clearWatch).not.toHaveBeenCalled()

    // A better fix after the errors still counts.
    fake.fix(40)
    await vi.advanceTimersByTimeAsync(0)
    expect(outcome.value).toMatchObject({ accuracyM: 40 })
  })

  it('after a position and some errors, the window still ends with PoorFix of the best accuracy at 20,000 ms', async () => {
    const fake = fakeWatch()
    const outcome = track(waitForFix({ watch: fake.watch }))
    fake.fix(90)
    fake.fix(70)
    fake.fail({ code: 2 })
    await vi.advanceTimersByTimeAsync(19_999)
    expect(outcome.state).toBe('pending')
    await vi.advanceTimersByTimeAsync(1)
    expect(outcome.value).toEqual(new PoorFix(70))
  })

  it('a watch that cannot start rejects with LocationDenied, and starts nothing to clear', async () => {
    const watch = {
      watchPosition: vi.fn(() => Promise.reject({ code: 'OS-PLUG-GLOC-0018' })),
      clearWatch: vi.fn(async () => {}),
    }
    const outcome = track(waitForFix({ watch }))
    await vi.advanceTimersByTimeAsync(0)
    expect(outcome.value).toEqual(new LocationDenied('OS-PLUG-GLOC-0018'))
    expect(watch.clearWatch).not.toHaveBeenCalled()
  })

  it('a watch that throws at once, as a browser without geolocation does, is a LocationDenied too', async () => {
    const watch = {
      watchPosition: vi.fn(() => {
        throw new TypeError('navigator.geolocation is undefined')
      }),
      clearWatch: vi.fn(async () => {}),
    }
    const outcome = track(waitForFix({ watch }))
    await vi.advanceTimersByTimeAsync(0)
    expect(outcome.value).toEqual(new LocationDenied('unknown'))
  })

  it('an aborted signal clears the watch and rejects with the signal\'s reason', async () => {
    const fake = fakeWatch('w3')
    const controller = new AbortController()
    const outcome = track(waitForFix({ watch: fake.watch, signal: controller.signal }))
    fake.fix(80)
    await vi.advanceTimersByTimeAsync(2_000)
    controller.abort(new Error('screen closed'))
    await vi.advanceTimersByTimeAsync(0)

    expect(outcome.state).toBe('rejected')
    expect((outcome.value as Error).message).toBe('screen closed')
    expect(fake.watch.clearWatch).toHaveBeenCalledExactlyOnceWith({ id: 'w3' })

    // The window's timer died with it: nothing more happens, and a late update does nothing.
    fake.fix(10)
    await vi.advanceTimersByTimeAsync(60_000)
    expect(fake.watch.clearWatch).toHaveBeenCalledOnce()
  })

  it('an abort before the watch has given its id still clears the watch once the id arrives', async () => {
    let giveId!: (id: string) => void
    const watch = {
      watchPosition: vi.fn(() => new Promise<string>((resolve) => (giveId = resolve))),
      clearWatch: vi.fn(async (_options: { id: string }) => {}),
    }
    const controller = new AbortController()
    const outcome = track(waitForFix({ watch, signal: controller.signal }))
    controller.abort()
    await vi.advanceTimersByTimeAsync(0)
    expect(outcome.state).toBe('rejected')
    expect(watch.clearWatch).not.toHaveBeenCalled()

    giveId('late')
    await vi.advanceTimersByTimeAsync(0)
    expect(watch.clearWatch).toHaveBeenCalledExactlyOnceWith({ id: 'late' })
  })

  it('a good fix before the watch has given its id clears it when the id arrives', async () => {
    let giveId!: (id: string) => void
    let callback!: WatchPositionCallback
    const watch = {
      watchPosition: vi.fn((_options: PositionOptions, cb: WatchPositionCallback) => {
        callback = cb
        return new Promise<string>((resolve) => (giveId = resolve))
      }),
      clearWatch: vi.fn(async (_options: { id: string }) => {}),
    }
    const outcome = track(waitForFix({ watch }))
    callback(position(10))
    await vi.advanceTimersByTimeAsync(0)
    expect(outcome.state).toBe('resolved')

    giveId('late')
    await vi.advanceTimersByTimeAsync(0)
    expect(watch.clearWatch).toHaveBeenCalledExactlyOnceWith({ id: 'late' })
  })

  it('an already aborted signal rejects before any watch starts', async () => {
    const fake = fakeWatch()
    const controller = new AbortController()
    controller.abort(new Error('gone'))
    await expect(waitForFix({ watch: fake.watch, signal: controller.signal })).rejects.toThrow('gone')
    expect(fake.watch.watchPosition).not.toHaveBeenCalled()
  })

  it('survives a clearWatch that fails, or one that gives no promise', async () => {
    for (const clearWatch of [vi.fn(() => Promise.reject(new Error('no such watch'))), vi.fn(() => undefined)]) {
      let callback!: WatchPositionCallback
      const watch = {
        watchPosition: vi.fn(async (_options: PositionOptions, cb: WatchPositionCallback) => {
          callback = cb
          return 'w'
        }),
        clearWatch: clearWatch as unknown as (options: { id: string }) => Promise<void>,
      }
      const outcome = track(waitForFix({ watch }))
      callback(position(10))
      await vi.advanceTimersByTimeAsync(0)
      expect(outcome.state).toBe('resolved')
      expect(clearWatch).toHaveBeenCalledOnce()
    }
  })

  it('never logs, and its source has no console call', async () => {
    const spies = (['log', 'info', 'warn', 'error', 'debug'] as const).map((name) =>
      vi.spyOn(console, name).mockImplementation(() => {}),
    )
    const fake = fakeWatch()
    const outcome = track(waitForFix({ watch: fake.watch }))
    fake.fix(80, { lat: 14.61, lng: 121.01 })
    fake.fail({ code: 2, message: 'Position unavailable' })
    fake.fail({ code: 1, message: 'User denied Geolocation' })
    await vi.advanceTimersByTimeAsync(0)
    expect(outcome.state).toBe('rejected')
    for (const spy of spies) expect(spy).not.toHaveBeenCalled()
    expect(geoSource).not.toMatch(/\bconsole\b/)
  })

  it("keeps a position out of its errors' messages", async () => {
    const fake = fakeWatch()
    const outcome = track(waitForFix({ watch: fake.watch }))
    fake.fix(80, { lat: 14.61234, lng: 121.01234 })
    await vi.advanceTimersByTimeAsync(20_000)
    const error = outcome.value as Error
    expect(`${error.name} ${error.message} ${JSON.stringify(error)}`).not.toMatch(/14\.61|121\.01/)
  })
})

describe('waitForFix in the APK', () => {
  beforeEach(() => {
    vi.spyOn(Capacitor, 'isNativePlatform').mockReturnValue(true)
    vi.spyOn(Capacitor, 'getPlatform').mockReturnValue('android')
  })

  it('asks for the location permission first, then watches with the Android intervals of 1 s', async () => {
    const order: string[] = []
    vi.mocked(Geolocation.requestPermissions).mockImplementation(async () => {
      order.push('permission')
      return { location: 'granted', coarseLocation: 'granted' }
    })
    const fake = fakeWatch()
    fake.watch.watchPosition.mockImplementation(async (opts, cb) => {
      order.push('watch')
      fake.options.push(opts)
      void cb
      return 'w1'
    })
    void waitForFix({ watch: fake.watch })
    await vi.advanceTimersByTimeAsync(0)

    expect(order).toEqual(['permission', 'watch'])
    expect(Geolocation.requestPermissions).toHaveBeenCalledExactlyOnceWith()
    expect(fake.options).toEqual([
      { enableHighAccuracy: true, timeout: 20_000, interval: 1_000, minimumUpdateInterval: 1_000 },
    ])
  })

  it('never counts the permission prompt in the window: a prompt open for 60 s, then 80 m fixes, still waits 20 s from the first', async () => {
    let allow!: () => void
    vi.mocked(Geolocation.requestPermissions).mockImplementation(
      () =>
        new Promise((resolve) => {
          allow = () => resolve({ location: 'granted', coarseLocation: 'granted' })
        }),
    )
    const fake = fakeWatch()
    const outcome = track(waitForFix({ watch: fake.watch }))
    await vi.advanceTimersByTimeAsync(60_000)
    expect(outcome.state).toBe('pending')
    expect(fake.watch.watchPosition).not.toHaveBeenCalled()

    allow()
    await vi.advanceTimersByTimeAsync(0)
    expect(fake.watch.watchPosition).toHaveBeenCalledOnce()
    await vi.advanceTimersByTimeAsync(15_000)
    fake.fix(80)
    await vi.advanceTimersByTimeAsync(19_999)
    expect(outcome.state).toBe('pending')
    await vi.advanceTimersByTimeAsync(1)
    expect(outcome.value).toEqual(new PoorFix(80))
  })

  it('a refusal on both aliases rejects with the plugin\'s own denial code, and starts no watch', async () => {
    vi.mocked(Geolocation.requestPermissions).mockResolvedValue({ location: 'denied', coarseLocation: 'denied' })
    const fake = fakeWatch()
    await expect(waitForFix({ watch: fake.watch })).rejects.toEqual(new LocationDenied('OS-PLUG-GLOC-0003'))
    expect(fake.watch.watchPosition).not.toHaveBeenCalled()
  })

  it('approximate location only (Android 12 and later) goes on to the watch, which then never reaches 50 m', async () => {
    vi.mocked(Geolocation.requestPermissions).mockResolvedValue({ location: 'denied', coarseLocation: 'granted' })
    const fake = fakeWatch()
    const outcome = track(waitForFix({ watch: fake.watch }))
    await vi.advanceTimersByTimeAsync(0)
    expect(fake.watch.watchPosition).toHaveBeenCalledOnce()
    fake.fix(900)
    await vi.advanceTimersByTimeAsync(20_000)
    expect(outcome.value).toEqual(new PoorFix(900))
    expect(locationLine(outcome.value)).toBe('location.poor')
  })

  it('a permission call that throws (location services off) rejects with the code it carries', async () => {
    vi.mocked(Geolocation.requestPermissions).mockRejectedValue({ code: 'OS-PLUG-GLOC-0007', message: 'off' })
    const fake = fakeWatch()
    await expect(waitForFix({ watch: fake.watch })).rejects.toEqual(new LocationDenied('OS-PLUG-GLOC-0007'))
    expect(fake.watch.watchPosition).not.toHaveBeenCalled()
  })

  it('an abort during the prompt rejects at once and starts no watch', async () => {
    vi.mocked(Geolocation.requestPermissions).mockReturnValue(new Promise(() => {}))
    const fake = fakeWatch()
    const controller = new AbortController()
    const outcome = track(waitForFix({ watch: fake.watch, signal: controller.signal }))
    await vi.advanceTimersByTimeAsync(1_000)
    controller.abort(new Error('closed'))
    await vi.advanceTimersByTimeAsync(0)
    expect(outcome.state).toBe('rejected')
    expect((outcome.value as Error).message).toBe('closed')
    expect(fake.watch.watchPosition).not.toHaveBeenCalled()
  })

  it('a prompt that is answered after the abort starts no watch', async () => {
    let allow!: () => void
    vi.mocked(Geolocation.requestPermissions).mockImplementation(
      () =>
        new Promise((resolve) => {
          allow = () => resolve({ location: 'granted', coarseLocation: 'granted' })
        }),
    )
    const fake = fakeWatch()
    const controller = new AbortController()
    const outcome = track(waitForFix({ watch: fake.watch, signal: controller.signal }))
    controller.abort()
    allow()
    await vi.advanceTimersByTimeAsync(0)
    expect(outcome.state).toBe('rejected')
    expect(fake.watch.watchPosition).not.toHaveBeenCalled()
  })

  it('leaves the Android intervals off on iOS and the web', async () => {
    vi.mocked(Capacitor.getPlatform).mockReturnValue('ios')
    vi.mocked(Geolocation.requestPermissions).mockResolvedValue({ location: 'granted', coarseLocation: 'granted' })
    const fake = fakeWatch()
    void waitForFix({ watch: fake.watch })
    await vi.advanceTimersByTimeAsync(0)
    expect(fake.options).toEqual([{ enableHighAccuracy: true, timeout: 20_000 }])
  })
})

describe('locationLine', () => {
  it('gives each of the native codes 0003, 0007, 0009, 0010 and 0017 its own line', () => {
    const lines = [
      'OS-PLUG-GLOC-0003',
      'OS-PLUG-GLOC-0007',
      'OS-PLUG-GLOC-0009',
      'OS-PLUG-GLOC-0010',
      'OS-PLUG-GLOC-0017',
    ].map((code) => locationLine(new LocationDenied(code)))
    expect(new Set(lines).size).toBe(5)
    expect(lines).toEqual([
      'location.denied',
      'location.servicesOff',
      'location.enableDenied',
      'location.poor',
      'location.allOff',
    ])
  })

  it('says the poor-fix line for a PoorFix, with or without a best accuracy, and the same one for the native timeout', () => {
    expect(locationLine(new PoorFix(65))).toBe('location.poor')
    expect(locationLine(new PoorFix(undefined))).toBe('location.poor')
    expect(locationLine(new LocationDenied('OS-PLUG-GLOC-0010'))).toBe(locationLine(new PoorFix(undefined)))
  })

  it('says the browser refusal line for the browser code, and a plain line for any code it does not know', () => {
    expect(locationLine(new LocationDenied('PERMISSION_DENIED'))).toBe('location.denied')
    for (const code of ['POSITION_UNAVAILABLE', 'unknown', 'OS-PLUG-GLOC-0002', '__proto__', 'constructor']) {
      expect(locationLine(new LocationDenied(code))).toBe('location.unavailable')
    }
    expect(locationLine(new Error('not ours'))).toBe('location.unavailable')
    expect(locationLine(undefined)).toBe('location.unavailable')
  })

  it('names lines that exist in both tables, and the poor-fix line asks for precise location', () => {
    for (const code of ['0003', '0007', '0009', '0010', '0017', '0002']) {
      const key = locationLine(new LocationDenied(`OS-PLUG-GLOC-${code}`))
      expect(EN[key].text.length).toBeGreaterThan(10)
      expect(FIL[key].text.length).toBeGreaterThan(10)
    }
    expect(EN['location.poor'].text).toMatch(/precise location/)
    expect(EN['location.poor'].text).toMatch(/Android 12/)
    expect(EN['location.poor'].text).toMatch(/open sky|clear view of the sky/)
  })

  it('the poor-fix line never tells the person to move, in either language, and keeps the precise-location part', () => {
    expect(EN['location.poor'].text).toContain('A clear view of the sky helps the phone find you.')
    for (const line of [EN['location.poor'].text, FIL['location.poor'].text]) {
      expect(line).not.toMatch(
        /\b(move|go to|go somewhere|walk|step|head|relocate|pumunta|lumipat|lumapit|lumabas|umalis|maglakad)\b/i,
      )
      expect(line).toMatch(/precise location/)
      expect(line).toMatch(/Android 12/)
    }
    expect(FIL['location.poor'].text).toMatch(/langit/)
  })
})

describe('the errors', () => {
  it('carry only a code or a best accuracy, and are told apart by name and class', () => {
    expect(new PoorFix(65)).toMatchObject({ name: 'PoorFix', bestAccuracyM: 65 })
    expect(new LocationDenied('PERMISSION_DENIED')).toMatchObject({ name: 'LocationDenied', code: 'PERMISSION_DENIED' })
    expect(new PoorFix(1)).toBeInstanceOf(Error)
    expect(new LocationDenied('x')).not.toBeInstanceOf(PoorFix)
  })
})
