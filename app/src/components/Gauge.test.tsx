import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'
import { LEVELS, OFF_GAUGE, type Level } from '../copy/levels'
import { LanguageProvider } from '../i18n'
import { Gauge } from './Gauge'

afterEach(() => {
  cleanup()
  localStorage.clear()
})

function draw(props: { level?: Level; isFloor?: boolean; noFlood?: boolean }) {
  const { container } = render(
    <LanguageProvider>
      <Gauge isFloor={false} {...props} />
    </LanguageProvider>,
  )
  const gauge = container.querySelector<HTMLElement>('[data-testid="gauge"]')
  if (gauge === null) throw new Error('no gauge was drawn')
  const cells = [...gauge.querySelectorAll<HTMLElement>('[data-cell]')]
  const byLevel = (level: Level) => cells.find((cell) => cell.dataset.cell === level) as HTMLElement
  const state = (level: Level) => byLevel(level).dataset.state
  return { gauge, cells, byLevel, state }
}

describe('the cells', () => {
  it('draws 9 cells, deepest at the top, and hides itself from screen readers', () => {
    const { gauge, cells } = draw({})
    expect(cells.map((cell) => cell.dataset.cell)).toEqual([...LEVELS].reverse())
    expect(gauge.getAttribute('aria-hidden')).toBe('true')
    expect(screen.queryByRole('img')).toBeNull()
  })

  it("draws 7 cells for MMDA's levels and 2 dashed ones for the added levels, labelled as outside MMDA's gauge", () => {
    const { cells } = draw({ level: 'knee' })
    const onGauge = cells.filter((cell) => cell.dataset.offGauge === 'false')
    const off = cells.filter((cell) => cell.dataset.offGauge === 'true')
    expect(onGauge).toHaveLength(7)
    expect(off.map((cell) => cell.dataset.cell).sort()).toEqual([...OFF_GAUGE].sort())
    for (const cell of off) expect(cell.className).toContain('border-dashed')
    for (const cell of onGauge) expect(cell.className).not.toContain('border-dashed')
    expect(screen.getAllByText("Outside MMDA's gauge")).toHaveLength(2)
  })

  it('names every level beside its cell, never on it', () => {
    const { cells } = draw({ level: 'tire' })
    for (const cell of cells) expect(cell.textContent, cell.dataset.cell).toBe('')
    for (const name of ['below gutter', 'gutter', 'half-knee', 'half-tire', 'knee', 'tire', 'waist', 'chest', 'above chest']) {
      expect(screen.getAllByText(name).length, name).toBeGreaterThan(0)
    }
  })

  it('gives every cell an outline edge, so a shallow fill never stands alone against the page', () => {
    const { cells } = draw({ level: 'gutter' })
    for (const cell of cells) expect(cell.className, cell.dataset.cell).toMatch(/\bborder-outline\b/)
  })
})

describe('the reading', () => {
  it('fills the cells up to the level, and marks that one with more than its fill', () => {
    const { state, byLevel, gauge } = draw({ level: 'knee' })
    expect(['below_gutter', 'gutter', 'half_knee', 'half_tire'].map((level) => state(level as Level))).toEqual([
      'filled',
      'filled',
      'filled',
      'filled',
    ])
    expect(state('knee')).toBe('marked')
    expect(['tire', 'waist', 'chest', 'above_chest'].map((level) => state(level as Level))).toEqual([
      'empty',
      'empty',
      'empty',
      'empty',
    ])
    // A thicker edge, and a pointer that sits beside the cell on the page, and a bold label.
    expect(byLevel('knee').className).toContain('border-4')
    expect(byLevel('gutter').className).not.toContain('border-4')
    expect(gauge.querySelectorAll('[data-pointer]')).toHaveLength(1)
    expect(gauge.querySelector('[data-pointer]')?.closest('[data-row]')?.getAttribute('data-row')).toBe('knee')
    expect(gauge.querySelector('[data-row="knee"] [data-label]')?.className).toContain('font-bold')
    expect(gauge.querySelector('[data-row="gutter"] [data-label]')?.className).not.toContain('font-bold')
  })

  it('fills from the bottom cell in the ramp of depth steps, shallowest first', () => {
    const { cells } = draw({ level: 'above_chest' })
    const bottomUp = [...cells].reverse()
    bottomUp.forEach((cell, index) => expect(cell.className, cell.dataset.cell).toContain(`bg-depth-${index + 1}`))
    expect(cells.every((cell) => cell.dataset.state !== 'empty')).toBe(true)
  })

  it('marks the lowest cell alone when that is the reading', () => {
    const { state } = draw({ level: 'below_gutter' })
    expect(state('below_gutter')).toBe('marked')
    for (const level of LEVELS.slice(1)) expect(state(level)).toBe('empty')
  })

  it('leaves every cell empty for "no flood seen", with no marker', () => {
    const { cells, gauge } = draw({ noFlood: true, level: 'knee' })
    expect(cells.every((cell) => cell.dataset.state === 'empty')).toBe(true)
    for (const cell of cells) expect(cell.className, cell.dataset.cell).not.toMatch(/bg-depth-/)
    expect(gauge.querySelectorAll('[data-pointer]')).toHaveLength(0)
  })

  it('leaves every cell empty when it has no level to show', () => {
    const { cells } = draw({})
    expect(cells.every((cell) => cell.dataset.state === 'empty')).toBe(true)
  })

  it('opens the top for a floor, and only for a floor', () => {
    const floor = draw({ level: 'tire', isFloor: true })
    expect(floor.gauge.getAttribute('data-open')).toBe('true')
    expect(floor.byLevel('tire').dataset.open).toBe('true')
    expect(floor.byLevel('tire').className).toContain('border-t-0')
    expect(floor.byLevel('knee').dataset.open).toBeUndefined()
    expect(screen.getAllByText('or deeper')).toHaveLength(1)
    cleanup()

    const exact = draw({ level: 'tire', isFloor: false })
    expect(exact.gauge.getAttribute('data-open')).toBe('false')
    expect(exact.byLevel('tire').dataset.open).toBeUndefined()
    expect(exact.byLevel('tire').className).not.toContain('border-t-0')
    expect(screen.queryByText('or deeper')).toBeNull()
  })

  it('is never open when there is nothing marked', () => {
    expect(draw({ noFlood: true, isFloor: true }).gauge.getAttribute('data-open')).toBe('false')
  })
})

describe('in Taglish', () => {
  it('names the levels and the added levels\' caption in Taglish, with the floor\'s caption', () => {
    localStorage.setItem('lusot.lang', 'fil')
    render(
      <LanguageProvider>
        <Gauge level="tire" isFloor />
      </LanguageProvider>,
    )
    expect(screen.getAllByText('Labas sa gauge ng MMDA')).toHaveLength(2)
    expect(screen.getByText('mas mababa sa gutter')).toBeTruthy()
    expect(screen.getByText('o mas malalim')).toBeTruthy()
  })
})
