import { act, renderHook } from '@testing-library/react'
import { afterEach, expect, it } from 'vitest'
import { navigate, parseHash, routeHash, useRoute, type Route } from './router'

const PIN_ID = 'r_0123456789abcdef0123456789abcdef'

afterEach(() => {
  history.replaceState(null, '', '/')
})

it('parseHash reads an empty hash as the map', () => {
  expect(parseHash('')).toEqual({ name: 'map' })
  expect(parseHash('#')).toEqual({ name: 'map' })
  expect(parseHash('#/')).toEqual({ name: 'map' })
})

it('parseHash reads each page', () => {
  for (const name of ['map', 'report', 'tested', 'about', 'privacy', 'licences'] as const) {
    expect(parseHash(`#/${name}`), name).toEqual({ name })
  }
})

it("parseHash reads a pin's id", () => {
  expect(parseHash(`#/pin/${PIN_ID}`)).toEqual({ name: 'pin', id: PIN_ID })
  expect(parseHash('#/pin/A-z_9')).toEqual({ name: 'pin', id: 'A-z_9' })
  expect(parseHash(`#/pin/${'a'.repeat(64)}`)).toEqual({ name: 'pin', id: 'a'.repeat(64) })
})

it('parseHash reads any other hash as the map', () => {
  for (const hash of [
    '#/pin/a b',
    '#/r/x',
    '#/pin/',
    '#/pin',
    `#/pin/${'a'.repeat(65)}`,
    '#/pin/a%20b',
    '#/pin/a/b',
    '#/pin/a\n',
    '#/tested/',
    '#/Tested',
    '#tested',
    '/tested',
    '#/tested?x=1',
    '#/report#/tested',
  ]) {
    expect(parseHash(hash), JSON.stringify(hash)).toEqual({ name: 'map' })
  }
})

it('routeHash writes the hash that parseHash reads back', () => {
  const routes: Route[] = [
    { name: 'map' },
    { name: 'report' },
    { name: 'tested' },
    { name: 'about' },
    { name: 'privacy' },
    { name: 'licences' },
    { name: 'pin', id: PIN_ID },
  ]
  expect(routes.map(routeHash)).toEqual([
    '#/map',
    '#/report',
    '#/tested',
    '#/about',
    '#/privacy',
    '#/licences',
    `#/pin/${PIN_ID}`,
  ])
  for (const route of routes) expect(parseHash(routeHash(route))).toEqual(route)
})

it('useRoute reads the hash at first render, and follows it', () => {
  history.replaceState(null, '', '/#/tested')
  const { result } = renderHook(() => useRoute())
  expect(result.current).toEqual({ name: 'tested' })

  act(() => {
    history.replaceState(null, '', `/#/pin/${PIN_ID}`)
    window.dispatchEvent(new HashChangeEvent('hashchange'))
  })
  expect(result.current).toEqual({ name: 'pin', id: PIN_ID })
})

it('navigate sets the hash, and useRoute follows it', async () => {
  const { result } = renderHook(() => useRoute())
  expect(result.current).toEqual({ name: 'map' })

  const changed = new Promise((resolve) => window.addEventListener('hashchange', resolve, { once: true }))
  await act(async () => {
    navigate({ name: 'about' })
    await changed
  })

  expect(window.location.hash).toBe('#/about')
  expect(result.current).toEqual({ name: 'about' })
})
