import { describe, expect, it } from 'vitest'
import { downsample, encodeWav } from './wav'

function tone(hz: number, rate: number, seconds = 1, amplitude = 0.5): Float32Array {
  const out = new Float32Array(Math.round(rate * seconds))
  for (let i = 0; i < out.length; i++) out[i] = amplitude * Math.sin((2 * Math.PI * hz * i) / rate)
  return out
}

// Mean square, away from the edges, where the filter sees only half its window.
function power(samples: Float32Array, edge = 200): number {
  let sum = 0
  for (let i = edge; i < samples.length - edge; i++) sum += samples[i] * samples[i]
  return sum / (samples.length - 2 * edge)
}

const ascii = (bytes: Uint8Array, at: number) => String.fromCharCode(...bytes.subarray(at, at + 4))

describe('encodeWav', () => {
  it('the header: RIFF, WAVE, fmt of 16, format 1, 1 channel, 16,000 Hz, 32,000 bytes a second, block 2, 16 bits, and data\'s size', () => {
    const wav = encodeWav(new Float32Array(16000), 16000)
    const view = new DataView(wav.buffer, wav.byteOffset, wav.byteLength)

    expect(wav.length).toBe(44 + 32000)
    expect(ascii(wav, 0)).toBe('RIFF')
    expect(view.getUint32(4, true)).toBe(36 + 32000)
    expect(ascii(wav, 8)).toBe('WAVE')
    expect(ascii(wav, 12)).toBe('fmt ')
    expect(view.getUint32(16, true)).toBe(16)
    expect(view.getUint16(20, true)).toBe(1)
    expect(view.getUint16(22, true)).toBe(1)
    expect(view.getUint32(24, true)).toBe(16000)
    expect(view.getUint32(28, true)).toBe(32000)
    expect(view.getUint16(32, true)).toBe(2)
    expect(view.getUint16(34, true)).toBe(16)
    expect(ascii(wav, 36)).toBe('data')
    expect(view.getUint32(40, true)).toBe(32000)
  })

  it('samples clip at ±1, little-endian 16-bit', () => {
    const wav = encodeWav(Float32Array.from([0, 1, -1, 2, -2, 0.5, -0.5]), 16000)
    const view = new DataView(wav.buffer, wav.byteOffset, wav.byteLength)
    const samples = Array.from({ length: 7 }, (_, i) => view.getInt16(44 + 2 * i, true))

    expect(samples).toEqual([0, 32767, -32768, 32767, -32768, 16384, -16384])
  })

  it('a silent clip of no samples is still a valid header', () => {
    const wav = encodeWav(new Float32Array(0), 16000)
    expect(wav.length).toBe(44)
    expect(new DataView(wav.buffer).getUint32(40, true)).toBe(0)
  })
})

describe('downsample', () => {
  it('48 kHz becomes a third as many samples, and 44.1 kHz its share', () => {
    expect(downsample(new Float32Array(48000), 48000, 16000)).toHaveLength(16000)
    expect(downsample(new Float32Array(44100), 44100, 16000)).toHaveLength(16000)
    expect(downsample(new Float32Array(4410), 44100, 16000)).toHaveLength(1600)
  })

  it('a 1 kHz tone keeps its energy through the downsampler, and a 7 kHz tone loses most of it', () => {
    for (const rate of [48000, 44100]) {
      const input = power(tone(1000, rate))
      expect(power(downsample(tone(1000, rate), rate, 16000)) / input, `1 kHz from ${rate}`).toBeGreaterThan(0.9)
      expect(power(downsample(tone(7000, rate), rate, 16000)) / input, `7 kHz from ${rate}`).toBeLessThan(0.1)
    }
  })

  it('a tone above 8 kHz, which would alias, is all but gone', () => {
    const input = power(tone(11000, 48000))
    expect(power(downsample(tone(11000, 48000), 48000, 16000)) / input).toBeLessThan(0.01)
  })

  it('keeps a constant level at the edges, and copies a clip that is already at 16 kHz', () => {
    const flat = downsample(new Float32Array(4800).fill(0.25), 48000, 16000)
    for (const sample of [flat[0], flat[800], flat[1599]]) expect(sample).toBeCloseTo(0.25, 6)

    const same = Float32Array.from([0.1, -0.2, 0.3])
    const copy = downsample(same, 16000, 16000)
    expect(copy).toEqual(same)
    expect(copy).not.toBe(same)
  })

  it('a slower input is brought up to 16 kHz by linear interpolation', () => {
    const up = downsample(Float32Array.from([0, 1, 0, -1]), 8000, 16000)
    expect(Array.from(up)).toEqual([0, 0.5, 1, 0.5, 0, -0.5, -1, -1])
  })
})

// The filter as first written: every tap computed for every output sample. The cached kernels must give the same.
function reference(input: Float32Array, fromRate: number): Float32Array {
  const out = new Float32Array(Math.floor((input.length * 16000) / fromRate))
  const step = fromRate / 16000
  const half = Math.ceil(fromRate * 0.0015)
  const fc = 6000 / fromRate
  for (let i = 0; i < out.length; i++) {
    const at = i * step
    let sum = 0
    let weights = 0
    for (let k = Math.max(0, Math.ceil(at - half)); k <= Math.min(input.length - 1, Math.floor(at + half)); k++) {
      const d = k - at
      const x = 2 * fc * d
      const sinc = x === 0 ? 1 : Math.sin(Math.PI * x) / (Math.PI * x)
      const w = (d + half) / (2 * half)
      const weight = sinc * (0.42 - 0.5 * Math.cos(2 * Math.PI * w) + 0.08 * Math.cos(4 * Math.PI * w))
      sum += input[k] * weight
      weights += weight
    }
    out[i] = weights === 0 ? 0 : sum / weights
  }
  return out
}

describe('downsample, against the filter computed sample by sample', () => {
  it.each([48000, 44100, 22050, 96000])('gives the same samples from %i Hz', (rate) => {
    let seed = 7
    const noise = Float32Array.from({ length: Math.round(rate * 0.25) }, () => {
      seed = (seed * 1103515245 + 12345) % 2147483648
      return seed / 1073741824 - 1
    })

    const fast = downsample(noise, rate, 16000)
    const slow = reference(noise, rate)

    expect(fast).toHaveLength(slow.length)
    let worst = 0
    for (let i = 0; i < slow.length; i++) worst = Math.max(worst, Math.abs(fast[i] - slow[i]))
    expect(worst).toBeLessThan(1e-6)
  })
})
