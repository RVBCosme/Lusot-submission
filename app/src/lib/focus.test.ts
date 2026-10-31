import { afterEach, expect, it } from 'vitest'
import { focusFell } from './focus'

afterEach(() => {
  document.body.replaceChildren()
})

it('focus has fallen when it is on nothing, the body, or the scrolling <main> a click on plain text focuses', () => {
  const main = document.createElement('main')
  main.tabIndex = 0
  const button = document.createElement('button')
  main.append(button)
  document.body.append(main)

  expect(focusFell(null)).toBe(true)
  expect(focusFell(document.body)).toBe(true)
  main.focus()
  expect(focusFell()).toBe(true)
  button.focus()
  expect(focusFell()).toBe(false)
})
