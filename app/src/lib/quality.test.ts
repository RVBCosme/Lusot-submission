import { describe, expect, it } from 'vitest'
import qualityPy from '../../../backend/analysis/src/lusot_analysis/pipeline/quality.py?raw'
import tuningPy from '../../../backend/analysis/src/lusot_analysis/tuning.py?raw'
import golden from './quality.golden.json'
import { BRIGHTNESS_MIN, qualityRefusal, qualityScores, SHARPNESS_MIN } from './quality'

// The golden scores come from the server's own quality_scores on PNGs of these pixels
// (backend/analysis/probes/make_quality_golden.py), so the phone and the server agree.
type Case = { name: string; width: number; height: number; rgb: number[]; brightness: number; sharpness: number }
const CASES = (golden as { cases: Case[] }).cases

// RGB as ImageData's RGBA, with an alpha the scores must ignore.
function rgba({ width, height, rgb }: Case) {
  const data = new Uint8ClampedArray(width * height * 4)
  for (let p = 0; p < width * height; p += 1) {
    data.set([rgb[p * 3]!, rgb[p * 3 + 1]!, rgb[p * 3 + 2]!, p % 2 === 0 ? 255 : 7], p * 4)
  }
  return { width, height, data }
}

describe('the scores follow OpenCV, as the server computes them', () => {
  it('has the six golden images', () => {
    expect(CASES.map((c) => c.name)).toEqual(['flat_30', 'flat_200', 'checkerboard', 'gradient', 'noise', 'odd_3x5'])
  })

  it.each(CASES.map((c) => [c.name, c] as const))('%s matches the server within 1e-6 and 1e-4', (_, c) => {
    const scores = qualityScores(rgba(c))
    expect(Math.abs(scores.brightness - c.brightness)).toBeLessThan(1e-6)
    expect(Math.abs(scores.sharpness - c.sharpness)).toBeLessThan(1e-4)
  })
})

describe('the cutoffs are the server\'s', () => {
  it('reads them where quality.py takes them, from tuning.py, and they equal the constants here', () => {
    expect(qualityPy).toContain('BRIGHTNESS_MIN = TUNING.brightness_min')
    expect(qualityPy).toContain('SHARPNESS_MIN = TUNING.sharpness_min')
    expect(tuningPy).toMatch(/^\s+brightness_min: float = 40\.0\b/m)
    expect(tuningPy).toMatch(/^\s+sharpness_min: float = 25\.0\b/m)
    expect(BRIGHTNESS_MIN).toBe(40)
    expect(SHARPNESS_MIN).toBe(25)
  })

  it('refuses under a cutoff only, with dark checked first', () => {
    expect(qualityRefusal({ brightness: 39.9, sharpness: 100 })).toBe('too_dark')
    expect(qualityRefusal({ brightness: 40, sharpness: 25 })).toBeNull()
    expect(qualityRefusal({ brightness: 120, sharpness: 24.9 })).toBe('too_blurry')
    expect(qualityRefusal({ brightness: 10, sharpness: 0 })).toBe('too_dark')
  })
})
