import { afterEach, expect, it, vi } from 'vitest'
import { readItem, removeItem, writeItem } from './storage'

afterEach(() => {
  vi.restoreAllMocks()
  vi.unstubAllGlobals()
  localStorage.clear()
})

it('storage writes, reads back and removes an item', () => {
  writeItem('lusot.lang', 'fil')
  expect(readItem('lusot.lang')).toBe('fil')

  removeItem('lusot.lang')
  expect(readItem('lusot.lang')).toBeNull()
})

it('storage survives a throwing localStorage', () => {
  vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => {
    throw new Error('blocked')
  })
  expect(readItem('lusot.lang')).toBeNull()
})

it('storage drops a write or a removal that localStorage refuses', () => {
  vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
    throw new DOMException('full', 'QuotaExceededError')
  })
  vi.spyOn(Storage.prototype, 'removeItem').mockImplementation(() => {
    throw new Error('blocked')
  })

  expect(() => writeItem('lusot.lang', 'fil')).not.toThrow()
  expect(() => removeItem('lusot.lang')).not.toThrow()
})

it('storage works with no localStorage at all', () => {
  vi.stubGlobal('localStorage', undefined)

  expect(readItem('lusot.lang')).toBeNull()
  expect(() => writeItem('lusot.lang', 'fil')).not.toThrow()
  expect(() => removeItem('lusot.lang')).not.toThrow()
})
