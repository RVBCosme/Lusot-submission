// A spoken question as the WAV Meta's transcription takes (Ask's spec §4.7, C718): 16 kHz mono 16-bit PCM. The
// microphone runs at the phone's own rate, usually 48 or 44.1 kHz, so the clip is brought down to 16 kHz here.

// The low-pass keeps speech up to about 5 kHz and removes what would alias past 16 kHz's 8 kHz limit. The spec leaves
// the filter to the builder (§7), as long as the clip stays intelligible.
const CUTOFF_HZ = 6000
const HALF_WIDTH_S = 0.0015 // the filter's reach on each side of an output sample

// `input` at `fromRate`, resampled to 16 kHz. Slower than that, it is brought up by linear interpolation; faster, each
// output sample is a Blackman-windowed sinc low-pass of the input around its own time, weighted to sum to 1, so a
// constant level stays the same to the edges. A clip already at 16 kHz is copied.
export function downsample(input: Float32Array, fromRate: number, toRate: 16000): Float32Array {
  if (fromRate === toRate) return input.slice()
  const length = Math.floor((input.length * toRate) / fromRate)
  const out = new Float32Array(length)
  const step = fromRate / toRate
  if (fromRate < toRate) {
    for (let i = 0; i < length; i++) {
      const at = i * step
      const k = Math.floor(at)
      const next = Math.min(k + 1, input.length - 1)
      out[i] = input[k] + (input[next] - input[k]) * (at - k)
    }
    return out
  }
  const half = Math.ceil(fromRate * HALF_WIDTH_S)
  const fc = CUTOFF_HZ / fromRate // the cutoff in cycles per input sample
  // The weights depend only on where an output sample falls between two input samples, which repeats (once at 48 kHz,
  // 160 times at 44.1), so each phase's kernel is made once: a 15 s clip then takes milliseconds, not a second.
  const kernels = new Map<number, { from: number; weights: Float64Array }>()
  const kernelAt = (phase: number) => {
    const key = Math.round(phase * 1e9)
    let kernel = kernels.get(key)
    if (kernel === undefined) {
      const from = Math.ceil(phase - half) // the first input sample's offset from floor(at)
      const weights = new Float64Array(Math.floor(phase + half) - from + 1)
      for (let j = 0; j < weights.length; j++) {
        const d = from + j - phase
        const x = 2 * fc * d
        const sinc = x === 0 ? 1 : Math.sin(Math.PI * x) / (Math.PI * x)
        const w = (d + half) / (2 * half) // 0 to 1 across the window
        weights[j] = sinc * (0.42 - 0.5 * Math.cos(2 * Math.PI * w) + 0.08 * Math.cos(4 * Math.PI * w))
      }
      kernel = { from, weights }
      kernels.set(key, kernel)
    }
    return kernel
  }
  for (let i = 0; i < length; i++) {
    const at = i * step
    const base = Math.floor(at)
    const { from, weights } = kernelAt(at - base)
    // At the edges, only the samples there are, weighted to sum to 1.
    const first = Math.max(0, -(base + from))
    const last = Math.min(weights.length, input.length - (base + from))
    let sum = 0
    let total = 0
    for (let j = first, k = base + from + first; j < last; j++, k++) {
      sum += input[k] * weights[j]
      total += weights[j]
    }
    out[i] = total === 0 ? 0 : sum / total
  }
  return out
}

// RIFF/WAVE, PCM (format 1), mono, 16-bit little-endian, each sample clipped to ±1.
export function encodeWav(samples: Float32Array, rate: 16000): Uint8Array {
  const bytes = new Uint8Array(44 + samples.length * 2)
  const view = new DataView(bytes.buffer)
  const ascii = (at: number, text: string) => {
    for (let i = 0; i < text.length; i++) bytes[at + i] = text.charCodeAt(i)
  }
  ascii(0, 'RIFF')
  view.setUint32(4, 36 + samples.length * 2, true)
  ascii(8, 'WAVE')
  ascii(12, 'fmt ')
  view.setUint32(16, 16, true)
  view.setUint16(20, 1, true) // PCM
  view.setUint16(22, 1, true) // mono
  view.setUint32(24, rate, true)
  view.setUint32(28, rate * 2, true) // bytes a second
  view.setUint16(32, 2, true) // bytes a sample
  view.setUint16(34, 16, true)
  ascii(36, 'data')
  view.setUint32(40, samples.length * 2, true)
  for (let i = 0; i < samples.length; i++) {
    const s = Math.max(-1, Math.min(1, samples[i]))
    view.setInt16(44 + 2 * i, Math.round(s < 0 ? s * 0x8000 : s * 0x7fff), true)
  }
  return bytes
}
