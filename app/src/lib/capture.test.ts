import { expect, it } from 'vitest'
import { scaledSize } from './capture'

it('scaledSize brings the longest side down to 1600 px', () => {
  expect(scaledSize(2000, 1500)).toEqual({ width: 1600, height: 1200 })
  expect(scaledSize(1500, 2000)).toEqual({ width: 1200, height: 1600 })
})

it('scaledSize leaves a photo of 1600 px or less unscaled', () => {
  expect(scaledSize(1600, 1200)).toEqual({ width: 1600, height: 1200 })
  expect(scaledSize(800, 600)).toEqual({ width: 800, height: 600 })
})
