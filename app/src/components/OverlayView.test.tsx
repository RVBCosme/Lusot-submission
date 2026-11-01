import { act, cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import type { ComponentProps } from 'react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { LanguageProvider, makeT } from '../i18n'
import { EN } from '../i18n/en'
import { FIL } from '../i18n/fil'
import type { OverlayData } from '../lib/api'
import { writeItem } from '../lib/storage'
import { levelLayers } from '../mock/fixtures'
import { orderLayers, REVEAL_MS, refLabel, revealStep } from '../overlay/layers'
import { contrastRatio, tokenBlocks } from '../styles/contrast'
import tokensCss from '../styles/tokens.css?raw'
import { deferred } from '../test/camera'
import { prefersReducedMotion } from '../test/motion'
import { OverlayView } from './OverlayView'

// The app's fetch is whatever a test sets: the layers file comes through it, as it does in the app.
const net = vi.hoisted(() => ({ fetch: undefined as unknown as typeof fetch }))
vi.mock('../lib/apiFetch', () => ({
  apiFetch: (input: RequestInfo | URL, init?: RequestInit) => net.fetch(input, init),
}))

const PHOTO = 'https://photos.example.test/blurred/photo.jpg?sig=1'
const OVERLAY = 'https://photos.example.test/overlay/photo.jpg?sig=2'
const LAYERS = 'https://photos.example.test/overlay/photo.json?sig=3'
const PHOTO_ALT = EN['sample.photoAlt'].text

const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), { status, headers: { 'content-type': 'application/json' } })

// What the layers link answers, and how often it is asked.
function serve(answer: unknown | (() => Response | Promise<Response>)) {
  const fetchFn = vi.fn<typeof fetch>(async () => (typeof answer === 'function' ? await answer() : json(answer)))
  net.fetch = fetchFn
  return fetchFn
}

type Props = Partial<ComponentProps<typeof OverlayView>>

function renderOverlay(props: Props = {}, lang: 'en' | 'fil' = 'en') {
  if (lang === 'fil') writeItem('lusot.lang', 'fil')
  const view = (next: Props) => (
    <LanguageProvider>
      <OverlayView photoUrl={PHOTO} overlayUrl={OVERLAY} layersUrl={LAYERS} onExpired={() => {}} {...next} />
    </LanguageProvider>
  )
  const result = render(view(props))
  return { ...result, again: (next: Props) => result.rerender(view(next)) }
}

const photo = () => screen.getByRole('img', { name: PHOTO_ALT })
const overlayJpeg = (container: HTMLElement) => container.querySelector(`img[src="${OVERLAY}"]`)
const drawn = () => screen.findByTestId('overlay-svg')
// Serves the layers file, draws the overlay, and waits for its SVG.
async function draw(file: unknown, props: Props = {}, lang: 'en' | 'fil' = 'en') {
  serve(file)
  renderOverlay(props, lang)
  return drawn()
}
// Lets what is waiting settle, inside act, so a state change that follows is not a warning.
const flush = () =>
  act(async () => {
    await new Promise((resolve) => setTimeout(resolve, 0))
  })

// Most tests check the final frame, so they ask for reduced motion; the timing tests ask for motion.
beforeEach(() => {
  net.fetch = () => Promise.reject(new TypeError('No layers link answers'))
  prefersReducedMotion(true)
})

afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
  localStorage.clear()
  document.documentElement.removeAttribute('lang')
})

describe('the overlay draws itself (C615)', () => {
  const drawnLayers = (container: HTMLElement) =>
    [...container.querySelectorAll('[data-testid="overlay-svg"] [data-layer]')].map((layer) => layer.getAttribute('data-layer'))
  // Each layer drawn, with the reference it belongs to, since kinds repeat from one reference to the next.
  const drawnRefs = (container: HTMLElement) =>
    [...container.querySelectorAll('[data-testid="overlay-svg"] [data-layer]')].map(
      (layer) => `${layer.closest('[data-ref]')?.getAttribute('data-ref') ?? 'water'}:${layer.getAttribute('data-layer')}`,
    )
  const expected = (file: OverlayData) =>
    orderLayers(file).map((layer) => `${layer.kind === 'water' ? 'water' : layer.ref.id}:${layer.kind}`)
  // Lets the layers file's answer through with the clock stopped: it settles on promises alone.
  const settle = () =>
    act(async () => {
      for (let i = 0; i < 20; i += 1) await Promise.resolve()
    })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('shows layer i at i x step, one after another, and the last by 2,000 ms', async () => {
    prefersReducedMotion(false)
    vi.useFakeTimers()
    const file = levelLayers('knee')
    const count = orderLayers(file).length
    const step = revealStep(count)
    expect(count).toBeGreaterThan(2)
    expect(REVEAL_MS).toBe(2000)
    expect(step * (count - 1)).toBeCloseTo(2000, 6)
    serve(file)
    const { container } = renderOverlay()
    await settle()

    // The water first, at once; then each layer at its own time, in C524's order, and never before it.
    expect(drawnLayers(container)).toEqual(['water'])
    for (let i = 1; i < count; i += 1) {
      await act(async () => {
        vi.advanceTimersByTime(Math.round(i * step) - 1 - (Math.round((i - 1) * step)))
      })
      expect(drawnLayers(container), `layer ${i} waits for its time`).toHaveLength(i)
      await act(async () => {
        vi.advanceTimersByTime(1)
      })
      expect(drawnLayers(container), `layer ${i} at ${Math.round(i * step)} ms`).toHaveLength(i + 1)
      // In C524's order at every step: the first i + 1 layers, never others.
      expect(drawnRefs(container)).toEqual(expected(file).slice(0, i + 1))
    }
    // Every layer by 2,000 ms, in the order the still drawing has.
    expect(Math.round((count - 1) * step)).toBeLessThanOrEqual(2000)
    expect(drawnLayers(container)).toEqual(orderLayers(file).map((layer) => layer.kind))
    // The legend's words are there from the start, so a screen reader never waits for the drawing.
    expect(screen.getAllByRole('listitem')).toHaveLength(3)
  })

  it('with prefers-reduced-motion: reduce, shows the final frame at once, with no timer to wait for', async () => {
    prefersReducedMotion(true)
    vi.useFakeTimers()
    const file = levelLayers('knee')
    serve(file)
    const { container } = renderOverlay()
    await settle()

    expect(drawnLayers(container)).toEqual(orderLayers(file).map((layer) => layer.kind))
    expect(vi.getTimerCount(), 'no timer for the drawing').toBe(0)
  })

  it('leaves no timer behind when the card goes mid-drawing', async () => {
    prefersReducedMotion(false)
    vi.useFakeTimers()
    serve(levelLayers('knee'))
    const { unmount } = renderOverlay()
    await settle()
    expect(vi.getTimerCount()).toBeGreaterThan(0)
    unmount()
    expect(vi.getTimerCount()).toBe(0)
  })

  it('draws itself again for a new layers link, from its first layer', async () => {
    prefersReducedMotion(false)
    vi.useFakeTimers()
    serve(levelLayers('knee'))
    const { container, again } = renderOverlay()
    await settle()
    await act(async () => {
      vi.advanceTimersByTime(REVEAL_MS)
    })
    expect(drawnLayers(container).length).toBeGreaterThan(1)

    serve(levelLayers('floor'))
    again({ layersUrl: `${LAYERS}&next=1` })
    await settle()
    expect(drawnLayers(container)).toEqual(['water'])
  })

  it('fades the overlay JPEG in over the photo once it has loaded, a fade that reduced motion cuts to its end', () => {
    const { container } = renderOverlay({ layersUrl: undefined })
    const jpeg = overlayJpeg(container)!
    expect(jpeg.getAttribute('class')).toMatch(/\btransition-opacity\b/)
    // Hidden until it arrives, so a slow link doesn't spend the fade before there is anything to show.
    expect(jpeg.getAttribute('class')).toMatch(/\bopacity-0\b/)
    fireEvent.load(jpeg)
    expect(jpeg.getAttribute('class')).toMatch(/\bopacity-100\b/)
    expect(jpeg.getAttribute('class')).not.toMatch(/\bopacity-0\b/)
  })
})

describe('the photo', () => {
  it('is the blurred photo, with the same alt as everywhere else, and no overlay yet while the layers load', async () => {
    const { container } = renderOverlay()
    expect(photo().getAttribute('src')).toBe(PHOTO)
    expect(screen.queryByTestId('overlay-svg')).toBeNull()
    // The overlay JPEG waits too: it must not flash up and then be replaced by the vectors.
    expect(overlayJpeg(container)).toBeNull()
    await flush()
  })

  it('is alone when there is no overlay at all', async () => {
    const fetchFn = serve(levelLayers('knee'))
    renderOverlay({ overlayUrl: undefined, layersUrl: undefined })
    await flush()
    expect(photo()).toBeTruthy()
    expect(screen.queryByTestId('overlay-svg')).toBeNull()
    expect(fetchFn).not.toHaveBeenCalled()
  })
})

describe('the layers, drawn as one SVG over the photo (C615)', () => {
  it("fetches the layers link once, and sizes the SVG to the file's width and height so it scales with the photo", async () => {
    const fetchFn = serve(levelLayers('knee'))
    const { container } = renderOverlay()
    const svg = await drawn()

    expect(fetchFn).toHaveBeenCalledTimes(1)
    expect(String(fetchFn.mock.calls[0][0])).toBe(LAYERS)
    expect(svg.tagName.toLowerCase()).toBe('svg')
    expect(svg.getAttribute('viewBox')).toBe('0 0 800 600')
    // One SVG, in the same box as the photo, so the photo's size alone sets its size.
    expect(container.querySelectorAll('svg')).toHaveLength(1)
    expect(svg.parentElement).toBe(photo().parentElement)
    expect(svg.getAttribute('preserveAspectRatio')).not.toBe('none')
    expect(svg.getAttribute('class')).toMatch(/pointer-events-none/)
  })

  it("draws in C524's order: the water, then each reference's outline, rim outline, box, fitted rim, waterline and label", async () => {
    const svg = await draw(levelLayers('knee'))
    const order = [...svg.querySelectorAll('[data-layer]')].map((layer) => {
      const owner = layer.closest('[data-ref]')?.getAttribute('data-ref')
      return `${owner ?? 'water'}:${layer.getAttribute('data-layer')}`
    })
    expect(order).toEqual([
      'water:water',
      // The wheel decides, with a fitted rim.
      '1:outline',
      '1:rim_outline',
      '1:box',
      '1:fitted_rim',
      '1:waterline',
      '1:label',
      // The adult has no rim.
      '2:outline',
      '2:box',
      '2:waterline',
      '2:label',
      // The dropped person has no waterline.
      '3:outline',
      '3:box',
      '3:label',
    ])
  })

  it("scales every mark with the photo: polygons, boxes and the rim are in the file's pixels", async () => {
    const svg = await draw(levelLayers('knee'))
    const layers = levelLayers('knee')
    const water = svg.querySelector('[data-layer="water"] polygon')
    expect(water?.getAttribute('points')).toBe(layers.water[0].map(([x, y]) => `${x},${y}`).join(' '))
    const box = svg.querySelector('[data-ref="1"] [data-layer="box"] rect')
    expect([box?.getAttribute('x'), box?.getAttribute('y'), box?.getAttribute('width'), box?.getAttribute('height')]).toEqual([
      '238',
      '358',
      '124',
      '124',
    ])
    const rim = svg.querySelector('[data-ref="1"] [data-layer="fitted_rim"] ellipse')
    // cv2's axes are full lengths, so the ellipse's radii are half of them, turned about its centre.
    expect([rim?.getAttribute('cx'), rim?.getAttribute('cy'), rim?.getAttribute('rx'), rim?.getAttribute('ry')]).toEqual([
      '300',
      '420',
      '40.2',
      '38.9',
    ])
    expect(rim?.getAttribute('transform')).toBe('rotate(12.5 300 420)')
    const line = svg.querySelector('[data-ref="1"] [data-layer="waterline"] line')
    expect([line?.getAttribute('x1'), line?.getAttribute('y1'), line?.getAttribute('x2'), line?.getAttribute('y2')]).toEqual([
      '238',
      '405',
      '362',
      '405',
    ])
  })

  it("lists every reference under the photo, one line each as refLabel gives it, in a list with the overlay's short label (C615)", async () => {
    const svg = await draw(levelLayers('knee'))
    const t = makeT('en')
    const legend = screen.getByRole('list', { name: EN['overlay.title'].text })
    const items = within(legend).getAllByRole('listitem')
    const refs = levelLayers('knee').refs
    expect(items.map((item) => item.textContent)).toEqual(refs.map((ref) => refLabel(t, ref).text))
    // The measured wheel, the adult, and the person who may not be an adult: a dropped reference shows its cause.
    expect(items[0].textContent).toMatch(/^Wheel 1: Knee\. .* Measured from the size of the wheel rim\.$/)
    expect(items[2].textContent).toBe('Person 3: Not used, since this person may not be an adult.')
    // Under the photo: the legend follows the photo's box, in the same figure.
    expect(photo().parentElement?.nextElementSibling).toBe(legend)
    expect(svg.parentElement?.nextElementSibling).toBe(legend)
  })

  it('numbers each legend line as its chip on the photo is numbered, and marks a dropped one', async () => {
    const svg = await draw(levelLayers('knee'))
    const legend = screen.getByRole('list')
    for (const ref of levelLayers('knee').refs) {
      const item = legend.querySelector(`[data-ref="${ref.id}"]`) as HTMLElement
      const chip = svg.querySelector(`[data-ref="${ref.id}"] [data-layer="label"] text`)?.textContent ?? ''
      expect(chip.startsWith(`${ref.id}`), `chip ${ref.id}`).toBe(true)
      expect(item.textContent, `legend ${ref.id}`).toContain(`${ref.id}:`)
      expect(item.getAttribute('data-dimmed')).toBe(String(ref.dropped !== null))
    }
    expect(legend.querySelectorAll('li')).toHaveLength(svg.querySelectorAll('[data-ref]').length)
  })

  it('leaves the SVG to the legend for screen readers, so nothing is said twice', async () => {
    const svg = await draw(levelLayers('knee'))
    expect(svg.getAttribute('aria-hidden')).toBe('true')
    // The only image a screen reader finds is the photo, and no group repeats a legend line.
    expect(screen.getAllByRole('img')).toEqual([photo()])
    expect(svg.querySelector('[aria-label], [role]')).toBeNull()
    expect(screen.getAllByText(/Not used, since this person may not be an adult\./)).toHaveLength(1)
  })

  it("writes the legend in the screen's language", async () => {
    serve(levelLayers('knee'))
    renderOverlay({}, 'fil')
    await drawn()
    const legend = screen.getByRole('list', { name: FIL['overlay.title'].text })
    const dropped = within(legend).getAllByRole('listitem')[2]
    expect(dropped.textContent).toBe(
      `${FIL['overlay.ref.person'].text.replace('{id}', '3')}: ${FIL['dropped.person_not_adult'].text}`,
    )
  })

  it('has no legend while the layers load, when they fail, or when they hold nothing', async () => {
    const answer = deferred<Response>()
    serve(() => answer.promise)
    renderOverlay()
    await flush()
    expect(screen.queryByRole('list')).toBeNull()
    answer.resolve(json({ error: 'AccessDenied' }, 403))
    await flush()
    expect(screen.queryByRole('list')).toBeNull()
    cleanup()

    serve({ version: 1, width: 800, height: 600, water: [], refs: [] })
    renderOverlay()
    await flush()
    expect(screen.queryByRole('list')).toBeNull()
  })

  it('has no legend for water alone, and lists only the references it drew', async () => {
    const layers = levelLayers('knee')
    serve({ ...layers, refs: [] })
    renderOverlay()
    await drawn()
    expect(screen.queryByRole('list')).toBeNull()
    cleanup()

    const broken = { ...layers.refs[1], id: 9, box: [1, 2, Number.NaN, 4] }
    serve({ ...layers, refs: [layers.refs[0], broken] })
    renderOverlay()
    await drawn()
    expect(within(screen.getByRole('list')).getAllByRole('listitem')).toHaveLength(1)
  })

  // Rene's screenshot, Nov 2: "5: Not used", "6: Not used" and "4: N7: Not used" ran into each other where people
  // stood close. The photo now carries each number, and the reading only where it set the level.
  it('shows every reference\'s number on the photo, the short reading only on those that set the level, and never "Not used"', async () => {
    const svg = await draw(levelLayers('knee'))
    const words = (id: number) => svg.querySelector(`[data-ref="${id}"] [data-layer="label"] text`)?.textContent
    expect(words(1)).toBe('1: Knee')
    expect(words(2)).toBe('2: Knee')
    expect(words(3)).toBe('3')
    expect(svg.textContent).not.toMatch(/Not used/)
    // The legend keeps the dropped one's cause, word for word.
    expect(within(screen.getByRole('list')).getByText('Person 3: Not used, since this person may not be an adult.')).toBeTruthy()
    cleanup()

    // A reference used at a shallower level helped, but didn't set the level: its number alone.
    const layers = levelLayers('knee')
    const shallower = await draw({ ...layers, refs: layers.refs.map((ref) => (ref.id === 1 ? { ...ref, level: 'half_knee' as const } : ref)) })
    const shown = (id: number) => shallower.querySelector(`[data-ref="${id}"] [data-layer="label"] text`)?.textContent
    expect(shown(1)).toBe('1')
    expect(shown(2)).toBe('2: Knee')
  })

  // The screenshot's seven references: two people side by side at the left with a third box between them, and a car body
  // at the right with three small people beside it. Person 3 set the level.
  type Box = [number, number, number, number]
  const crowd = (): OverlayData => {
    const layers = levelLayers('knee')
    const [, adult, child] = layers.refs
    const at = (box: Box) => ({ box, outline: [[[box[0], box[1]], [box[2], box[1]], [box[2], box[3]], [box[0], box[3]]]] as [number, number][][] })
    const dropped = (id: number, box: Box) => ({ ...child, id, ...at(box) })
    return {
      ...layers,
      refs: [
        { ...dropped(1, [440, 200, 620, 330]), kind: 'body', dropped: 'vehicle_moving' },
        dropped(2, [225, 160, 265, 255]),
        { ...adult, id: 3, ...at([520, 215, 560, 330]), waterline: [[520, 300], [560, 300]] },
        dropped(4, [500, 205, 540, 320]),
        dropped(5, [60, 170, 220, 560]),
        dropped(6, [220, 165, 380, 560]),
        dropped(7, [505, 210, 545, 325]),
      ],
    }
  }

  it('lists every reference under the photo, the one that set the level first, then the rest in their order', async () => {
    await draw(crowd())
    const items = within(screen.getByRole('list')).getAllByRole('listitem')
    expect(items.map((item) => item.getAttribute('data-ref'))).toEqual(['3', '1', '2', '4', '5', '6', '7'])
    expect(items[0].textContent).toBe('Person 3: Knee. Water reaches the knees of an adult in the photo.')
    expect(items[1].textContent).toBe('Car body 1: Not used, since the vehicle may be moving.')
    cleanup()

    // Two that share the deepest level both come first, in their own order.
    await draw(levelLayers('knee'))
    const knee = within(screen.getByRole('list')).getAllByRole('listitem')
    expect(knee.map((item) => item.getAttribute('data-ref'))).toEqual(['1', '2', '3'])
  })

  it('keeps the numbers of references that stand close together from covering each other', async () => {
    const svg = await draw(crowd())
    const refs = crowd().refs
    const badges = [...svg.querySelectorAll('[data-layer="label"] rect')].map((rect) => {
      const [x, y, width, height] = ['x', 'y', 'width', 'height'].map((name) => Number(rect.getAttribute(name)))
      return { x, y, width, height }
    })
    expect(badges).toHaveLength(refs.length)
    for (const [i, a] of badges.entries()) {
      for (const b of badges.slice(i + 1)) {
        const overlap = a.x < b.x + b.width && b.x < a.x + a.width && a.y < b.y + b.height && b.y < a.y + a.height
        expect(overlap, `${JSON.stringify(a)} and ${JSON.stringify(b)}`).toBe(false)
      }
    }
  })

  it('gives the badge of a reference that set the level its place first, ahead of one listed before it', async () => {
    const layers = crowd()
    const [car, , person] = layers.refs
    // A dropped box listed first, whose badge would take the deciding one's place.
    const svg = await draw({ ...layers, refs: [{ ...car, box: [515, 212, 600, 330] }, person] })
    const rect = svg.querySelector('[data-ref="3"] [data-layer="label"] rect') as SVGElement
    // Its own place: on its box's left edge, just above it (font 800 / 21, a badge 1.4 fonts high, a gap of a sixth).
    const font = 800 / 21
    expect(Number(rect.getAttribute('x'))).toBe(520)
    expect(Number(rect.getAttribute('y'))).toBeCloseTo(215 - font * 1.4 - (font * 1.4) / 6, 0)
  })

  it('draws a reference that set the level apart from the rest: a filled badge and a heavier box, and a dropped one dashed', async () => {
    const svg = await draw(levelLayers('knee'))
    const group = (id: number) => svg.querySelector(`[data-ref="${id}"]`) as SVGElement
    expect(group(1).getAttribute('data-decides')).toBe('true')
    expect(group(3).getAttribute('data-decides')).toBe('false')
    const badge = (id: number) => group(id).querySelector('[data-layer="label"] rect')?.getAttribute('class') ?? ''
    const number = (id: number) => group(id).querySelector('[data-layer="label"] text')?.getAttribute('class') ?? ''
    // Filled in ink with the number in the surface colour, against an outlined badge with the number in ink.
    expect(badge(1)).toContain('fill-ink')
    expect(number(1)).toContain('fill-surface')
    expect(badge(3)).toContain('fill-surface')
    expect(number(3)).toContain('fill-ink')
    const box = (id: number) => group(id).querySelector('[data-layer="box"] rect:last-child') as SVGElement
    expect(Number(box(1).getAttribute('stroke-width'))).toBeGreaterThan(Number(box(3).getAttribute('stroke-width')))
    expect(box(1).getAttribute('stroke-dasharray')).toBeNull()
    expect(box(3).getAttribute('stroke-dasharray')).toBeTruthy()
    // Its dashes aren't the water's, so the two aren't mistaken.
    const water = svg.querySelector('[data-layer="water"] polygon')?.getAttribute('stroke-dasharray')
    expect(box(3).getAttribute('stroke-dasharray')).not.toBe(water)
    expect(group(3).querySelector('[data-layer="outline"] polygon:last-child')?.getAttribute('stroke-dasharray')).not.toBe(water)
  })

  // The photo is drawn the full width of its box, so the file's width sets the scale: a word's size on screen is its
  // font-size in the file times the shown width over the file's width (I3). 276 px is the photo of a card at 360 px.
  it.each([
    ['4:3', 800, 600],
    ['16:9', 1600, 900],
    ['3:2', 1500, 1000],
    ['portrait 9:16', 900, 1600],
    ['a full-size still', 1600, 1200],
  ])('sets the words to read on a phone, 12 px or more on the 276 px photo of a card at 360 px wide, for %s', async (_shape, width, height) => {
    const svg = await draw({ ...levelLayers('knee'), width, height })
    const words = [...svg.querySelectorAll('text')]
    expect(words.length).toBeGreaterThan(0)
    for (const text of words) {
      const size = Number(text.getAttribute('font-size'))
      expect((size * 276) / width, `${width} x ${height}`).toBeGreaterThanOrEqual(12)
      // And no larger than the photo can hold: a line of the longest short label fits across it.
      expect((size * 276) / width).toBeLessThanOrEqual(16)
    }
  })

  it('squeezes a label that is wider than the photo to fit it, and leaves a shorter one alone', async () => {
    const layers = levelLayers('floor')
    const refs = layers.refs.map((ref) => ({ ...ref, level: 'below_gutter', level_is_floor: true }))
    const svg = await draw({ ...layers, refs }, {}, 'fil')
    const label = svg.querySelector('[data-ref="1"] [data-layer="label"] text') as SVGElement
    // "1: Hindi bababa sa mas mababa sa gutter" is longer than the photo is wide at this size.
    expect(label.textContent).toBe('1: Hindi bababa sa mas mababa sa gutter')
    expect(Number(label.getAttribute('textLength'))).toBeLessThanOrEqual(800)
    expect(label.getAttribute('lengthAdjust')).toBe('spacingAndGlyphs')
    cleanup()

    const short = await draw(levelLayers('knee'))
    expect(short.querySelector('text')?.getAttribute('textLength')).toBeNull()
  })

  it('draws a dropped reference dimmed, in a token colour at reduced opacity, and no other', async () => {
    const svg = await draw(levelLayers('knee'))
    const dropped = svg.querySelector('[data-ref="3"]') as SVGElement
    const used = svg.querySelector('[data-ref="1"]') as SVGElement
    expect(dropped.getAttribute('data-dimmed')).toBe('true')
    expect(used.getAttribute('data-dimmed')).toBe('false')
    const opacity = (element: Element) => Number(element.getAttribute('opacity') ?? 1)
    expect(opacity(dropped.querySelector('[data-layer="outline"]') as Element)).toBeLessThan(1)
    expect(opacity(dropped.querySelector('[data-layer="outline"]') as Element)).toBeGreaterThan(0)
    // Its label stays readable: dimmer than a used one, but less than its marks.
    expect(opacity(dropped.querySelector('[data-layer="label"]') as Element)).toBeLessThan(1)
    expect(opacity(dropped.querySelector('[data-layer="label"]') as Element)).toBeGreaterThan(
      opacity(dropped.querySelector('[data-layer="outline"]') as Element),
    )
    expect(opacity(used.querySelector('[data-layer="outline"]') as Element)).toBe(1)
    expect(opacity(used.querySelector('[data-layer="label"]') as Element)).toBe(1)
    // The colour is the secondary-text token, the one a used mark never takes.
    expect(dropped.querySelector('[data-layer="outline"] polygon:last-child')?.getAttribute('class')).toContain('stroke-ink-2')
    expect(used.querySelector('[data-layer="outline"] polygon:last-child')?.getAttribute('class')).not.toContain('stroke-ink-2')
  })

  it('draws each line twice, a halo in the surface colour under the mark, so it shows on a bright photo and a dark one', async () => {
    const svg = await draw(levelLayers('knee'))
    const outline = svg.querySelectorAll('[data-ref="1"] [data-layer="outline"] polygon')
    expect(outline).toHaveLength(2)
    expect(outline[0].getAttribute('class')).toContain('stroke-surface')
    expect(Number(outline[0].getAttribute('stroke-width'))).toBeGreaterThan(Number(outline[1].getAttribute('stroke-width')))
    // Each number sits on its own badge, ringed in the other colour, so it reads on a bright photo and a dark one.
    for (const id of [1, 3]) {
      const badge = svg.querySelector(`[data-ref="${id}"] [data-layer="label"] rect`)?.getAttribute('class') ?? ''
      expect(badge, String(id)).toMatch(/\bfill-(ink|surface)\b/)
      expect(badge, String(id)).toMatch(/\bstroke-(ink|surface)\b/)
      expect(badge.match(/\bfill-(\w+)/)?.[1], String(id)).not.toBe(badge.match(/\bstroke-(\w+)/)?.[1])
    }
  })

  it('tells the marks apart by more than colour: the water is dashed, a rim outline is dotted, the others are solid', async () => {
    const svg = await draw(levelLayers('knee'))
    const dash = (selector: string) => svg.querySelector(selector)?.getAttribute('stroke-dasharray')
    expect(dash('[data-layer="water"] polygon')).toBeTruthy()
    expect(dash('[data-ref="1"] [data-layer="rim_outline"] polygon')).toBeTruthy()
    expect(dash('[data-layer="water"] polygon')).not.toBe(dash('[data-ref="1"] [data-layer="rim_outline"] polygon'))
    for (const layer of ['outline', 'box']) expect(dash(`[data-ref="1"] [data-layer="${layer}"] > *`), layer).toBeNull()
    // The waterline carries a tick at each end (the JPEG's too): the line and two ticks.
    expect(svg.querySelectorAll('[data-ref="1"] [data-layer="waterline"] line')).toHaveLength(2 * 3)
  })

  it('uses only the palette: token classes, no colour of its own', async () => {
    const svg = await draw(levelLayers('knee'))
    const html = svg.outerHTML
    expect(html).not.toMatch(/#[0-9a-fA-F]{3,8}\b|\b(?:rgb|hsl|oklch)a?\(|style=/)
    const used = new Set<string>()
    for (const element of svg.querySelectorAll('[class]')) for (const name of element.classList) used.add(name)
    const colourClasses = [...used].filter((name) => /^(stroke|fill)-/.test(name))
    expect(colourClasses.length).toBeGreaterThan(0)
    const allowed = /^(stroke|fill)-(surface|ink|ink-2|action|focus|outline|depth-[1-9]|none)$/
    for (const name of colourClasses) expect(name).toMatch(allowed)
  })

  it('draws every mark in a colour that holds 3:1 against the halo under it, in the light theme and the dark one', async () => {
    const svg = await draw(levelLayers('knee'))
    // The class each mark takes, and the token it names (index.css maps each to its --lusot-* variable).
    const token: Record<string, string> = {
      'stroke-action': '--lusot-action',
      'stroke-ink': '--lusot-text',
      'stroke-ink-2': '--lusot-text-2',
      'stroke-depth-6': '--lusot-depth-6',
      'fill-ink': '--lusot-text',
    }
    const used = new Set<string>()
    for (const element of svg.querySelectorAll('[class]')) {
      for (const name of element.classList) if (name in token) used.add(name)
    }
    // Every colour class the SVG uses, bar the halo and the surface fill a badge or its number takes, is one this test
    // knows.
    for (const element of svg.querySelectorAll('[class]')) {
      for (const name of element.classList) {
        expect(name === 'stroke-surface' || name === 'fill-surface' || name === 'fill-none' || name in token, name).toBe(true)
      }
    }
    expect([...used].sort()).toEqual(['fill-ink', 'stroke-action', 'stroke-depth-6', 'stroke-ink', 'stroke-ink-2'])
    const blocks = tokenBlocks(tokensCss)
    for (const theme of [':root, :root[data-theme="light"]', ':root[data-theme="dark"]']) {
      const colours = blocks[theme]
      for (const name of used) {
        const ratio = contrastRatio(colours[token[name]], colours['--lusot-surface'])
        expect(ratio, `${name} on the surface, ${theme}`).toBeGreaterThanOrEqual(3)
      }
      // A badge's number is ink on the surface colour, or the surface colour on ink: text, so 4.5:1.
      expect(contrastRatio(colours['--lusot-text'], colours['--lusot-surface']), theme).toBeGreaterThanOrEqual(4.5)
    }
  })

  it('shows a floor reference as a floor, in its label and on the photo, as the result card does', async () => {
    const layers = levelLayers('floor')
    const floor: OverlayData = { ...layers, refs: layers.refs.map((ref) => ({ ...ref, level_is_floor: true })) }
    const svg = await draw(floor)
    expect(svg.querySelector('[data-ref="1"] [data-layer="label"] text')?.textContent).toBe('1: At least tire')
    expect(within(screen.getByRole('list')).getByText(/^Wheel 1: At least tire\. /)).toBeTruthy()
  })

  it('shows the same reading as its level when level_is_floor is false, null or absent', async () => {
    const layers = levelLayers('floor')
    for (const flag of [false, null, undefined]) {
      const refs = layers.refs.map((ref) => {
        const { level_is_floor: _drop, ...rest } = ref
        return (flag === undefined ? rest : { ...rest, level_is_floor: flag }) as OverlayData['refs'][number]
      })
      serve({ ...layers, refs })
      const { unmount } = renderOverlay()
      const svg = await drawn()
      expect(svg.querySelector('[data-ref="1"] [data-layer="label"] text')?.textContent, String(flag)).toBe('1: Tire')
      unmount()
    }
  })

  it('keeps every label inside the photo: above a box when there is room, inside it at the top, and clear of the right edge', async () => {
    const layers = levelLayers('knee')
    const near = (id: number, box: [number, number, number, number]): OverlayData['refs'][number] => ({
      ...layers.refs[0],
      id,
      box,
    })
    const svg = await draw({
      ...layers,
      refs: [near(1, [238, 358, 362, 482]), near(2, [10, 0, 110, 90]), near(3, [790, 300, 800, 400])],
    })
    const at = (id: number) => {
      const text = svg.querySelector(`[data-ref="${id}"] [data-layer="label"] text`) as SVGElement
      return { x: Number(text.getAttribute('x')), y: Number(text.getAttribute('y')) }
    }
    expect(at(1).y).toBeLessThan(358)
    expect(at(2).y).toBeGreaterThan(0)
    expect(at(3).x).toBeGreaterThanOrEqual(0)
    expect(at(3).x).toBeLessThan(790)
    for (const id of [1, 2, 3]) {
      expect(at(id).y).toBeGreaterThan(0)
      expect(at(id).y).toBeLessThan(600)
    }
  })

  it('draws nothing in the SVG when the file holds nothing to draw, and does not fall back to the JPEG either', async () => {
    serve({ version: 1, width: 800, height: 600, water: [], refs: [] })
    const { container } = renderOverlay()
    await flush()
    expect(net.fetch).toHaveBeenCalled()
    expect(screen.queryByTestId('overlay-svg')).toBeNull()
    expect(overlayJpeg(container)).toBeNull()
    expect(photo()).toBeTruthy()
  })

  it('draws the water of a file with no reference, and a reference of a file with no water', async () => {
    const layers = levelLayers('knee')
    serve({ ...layers, refs: [] })
    const first = renderOverlay()
    expect((await drawn()).querySelectorAll('[data-layer]')).toHaveLength(1)
    first.unmount()

    serve({ ...layers, water: [], refs: layers.refs.slice(0, 1) })
    renderOverlay()
    const svg = await drawn()
    expect(svg.querySelector('[data-layer="water"]')).toBeNull()
    expect(svg.querySelector('[data-ref="1"]')).toBeTruthy()
  })

  it('takes the file as it is, so a file that has gone out of date in one reference never throws', async () => {
    const layers = levelLayers('knee')
    const messy = { ...layers, refs: [{ ...layers.refs[0], outline: undefined, rim: undefined, waterline: undefined, rim_outline: undefined }] }
    const svg = await draw(messy)
    expect([...svg.querySelectorAll('[data-layer]')].map((layer) => layer.getAttribute('data-layer'))).toEqual([
      'water',
      'box',
      'label',
    ])
  })

  it('tells the card what the layers hold once they load, and that they failed when they do', async () => {
    const onLayers = vi.fn()
    serve(levelLayers('knee'))
    const first = renderOverlay({ onLayers })
    await drawn()
    expect(onLayers).toHaveBeenCalledExactlyOnceWith(expect.objectContaining({ width: 800, height: 600 }))
    first.unmount()

    const failed = vi.fn()
    serve(() => json({ error: 'AccessDenied' }, 403))
    renderOverlay({ onLayers: failed })
    await waitFor(() => expect(failed).toHaveBeenCalledExactlyOnceWith(undefined))
  })
})

describe('without layers: the overlay JPEG, then the photo alone', () => {
  it('shows the overlay JPEG over the photo when there is no layers link, and asks for nothing', () => {
    const fetchFn = serve(levelLayers('knee'))
    const { container } = renderOverlay({ layersUrl: undefined })
    const jpeg = overlayJpeg(container) as HTMLImageElement
    expect(jpeg).toBeTruthy()
    // It is the same picture as the photo with marks on it, so a screen reader hears the photo once.
    expect(jpeg.getAttribute('alt')).toBe('')
    expect(jpeg.getAttribute('aria-hidden')).toBe('true')
    expect(jpeg.parentElement).toBe(photo().parentElement)
    expect(jpeg.getAttribute('class')).toMatch(/absolute/)
    expect(fetchFn).not.toHaveBeenCalled()
    expect(screen.queryByTestId('overlay-svg')).toBeNull()
  })

  it.each([
    ['the link is refused', () => json({ error: 'AccessDenied' }, 403)],
    ['the network fails', () => Promise.reject(new TypeError('Failed to fetch'))],
    ['the file is not in the layers shape', () => json({ version: 2, width: 1, height: 1, water: [], refs: [] })],
    ['the file is not JSON', () => new Response('<html>', { status: 200 })],
    ['the file has no usable size', () => json({ version: 1, width: 0, height: 0, water: [], refs: [] })],
  ])('shows the overlay JPEG when %s', async (_name, answer) => {
    serve(answer)
    const { container } = renderOverlay()
    await waitFor(() => expect(overlayJpeg(container)).toBeTruthy())
    expect(screen.queryByTestId('overlay-svg')).toBeNull()
    expect(photo()).toBeTruthy()
  })

  it('shows the photo alone when the layers fail and there is no overlay JPEG either', async () => {
    serve(() => json({ error: 'AccessDenied' }, 403))
    const onLayers = vi.fn()
    const { container } = renderOverlay({ overlayUrl: undefined, onLayers })
    await waitFor(() => expect(onLayers).toHaveBeenCalled())
    expect(container.querySelectorAll('img')).toHaveLength(1)
    expect(photo()).toBeTruthy()
  })

  it('drops an overlay JPEG that fails to load and keeps the photo, without asking for a new photo link', async () => {
    const onExpired = vi.fn()
    const { container } = renderOverlay({ layersUrl: undefined, onExpired })
    fireEvent.error(overlayJpeg(container) as Element)
    expect(overlayJpeg(container)).toBeNull()
    expect(photo()).toBeTruthy()
    expect(onExpired).not.toHaveBeenCalled()
  })

  it('tries a new overlay link after the old one failed, and keeps its failure for the old link only', async () => {
    const { container, again } = renderOverlay({ layersUrl: undefined })
    fireEvent.error(overlayJpeg(container) as Element)
    expect(overlayJpeg(container)).toBeNull()

    const fresh = `${OVERLAY}&fresh=1`
    again({ layersUrl: undefined, overlayUrl: fresh })
    expect(container.querySelector(`img[src="${fresh}"]`)).toBeTruthy()

    // Back to the link that failed: it is not tried again.
    again({ layersUrl: undefined, overlayUrl: OVERLAY })
    expect(overlayJpeg(container)).toBeNull()
  })

  it('waits for the layers before showing the JPEG, and shows the SVG when they come', async () => {
    const answer = deferred<Response>()
    serve(() => answer.promise)
    const { container } = renderOverlay()
    await flush()
    expect(overlayJpeg(container)).toBeNull()
    expect(screen.queryByTestId('overlay-svg')).toBeNull()

    answer.resolve(json(levelLayers('knee')))
    await drawn()
    expect(overlayJpeg(container)).toBeNull()
  })
})

describe('an expired photo link', () => {
  it('refetches once: the first image error calls onExpired once, and a second error shows no photo', async () => {
    const onExpired = vi.fn()
    serve(levelLayers('knee'))
    const { container } = renderOverlay({ onExpired })
    await drawn()
    expect(onExpired).not.toHaveBeenCalled()

    fireEvent.error(photo())
    expect(onExpired).toHaveBeenCalledTimes(1)
    // The card asks for a new link and gives a new one; the photo is still there to load it.
    expect(photo()).toBeTruthy()

    fireEvent.error(photo())
    expect(onExpired).toHaveBeenCalledTimes(1)
    expect(container.querySelector('img')).toBeNull()
    expect(screen.queryByTestId('overlay-svg')).toBeNull()
    expect(container.textContent).toBe('')
  })

  it('goes on with a new link: the same box, a new source, and a second error only after that', async () => {
    const onExpired = vi.fn()
    const { again } = renderOverlay({ onExpired, layersUrl: undefined, overlayUrl: undefined })
    fireEvent.error(photo())
    again({ onExpired, photoUrl: 'https://photos.example.test/blurred/photo.jpg?sig=9', layersUrl: undefined, overlayUrl: undefined })
    expect(photo().getAttribute('src')).toBe('https://photos.example.test/blurred/photo.jpg?sig=9')
    expect(onExpired).toHaveBeenCalledTimes(1)
  })

  it('tells the card when the photo is gone, so it can drop what it said about the photo', () => {
    const onGone = vi.fn()
    renderOverlay({ onGone, layersUrl: undefined, overlayUrl: undefined })
    fireEvent.error(photo())
    expect(onGone).not.toHaveBeenCalled()
    fireEvent.error(photo())
    expect(onGone).toHaveBeenCalledTimes(1)
  })

  it('shows no photo at the first error when nothing can ask for a new link', () => {
    const { container } = renderOverlay({ onExpired: undefined, layersUrl: undefined, overlayUrl: undefined })
    fireEvent.error(photo())
    expect(container.querySelector('img')).toBeNull()
  })
})

describe('a new layers link', () => {
  it('fetches the new one and ignores a late answer from the old one', async () => {
    const old = deferred<Response>()
    const first = vi.fn<typeof fetch>(async (input) => (String(input) === LAYERS ? old.promise : json(levelLayers('landmark'))))
    net.fetch = first
    const { again, container } = renderOverlay()
    again({ layersUrl: `${LAYERS}&new=1` })
    const svg = await drawn()
    expect(svg.querySelectorAll('[data-ref]')).toHaveLength(1)

    old.resolve(json(levelLayers('knee')))
    await flush()
    expect(container.querySelector('svg')?.querySelectorAll('[data-ref]')).toHaveLength(1)
    expect(first).toHaveBeenCalledTimes(2)
  })

  it('does not set state once it has gone', async () => {
    const answer = deferred<Response>()
    serve(() => answer.promise)
    const onLayers = vi.fn()
    const errors = vi.spyOn(console, 'error').mockImplementation(() => {})
    const { unmount } = renderOverlay({ onLayers })
    unmount()
    answer.resolve(json(levelLayers('knee')))
    await flush()
    expect(onLayers).not.toHaveBeenCalled()
    expect(errors).not.toHaveBeenCalled()
  })
})

describe('what it never shows or logs', () => {
  it('writes no link, no id and no number that is a place into the page text or the console', async () => {
    const log = vi.spyOn(console, 'log')
    const warn = vi.spyOn(console, 'warn')
    const error = vi.spyOn(console, 'error')
    serve(levelLayers('knee'))
    const { container } = renderOverlay()
    await drawn()
    const text = container.textContent ?? ''
    expect(text).not.toMatch(/https?:|r_[0-9a-f]{32}|sig=/)
    const labels = [...container.querySelectorAll('li, [aria-label]')].map(
      (element) => `${element.textContent} ${element.getAttribute('aria-label') ?? ''}`,
    )
    expect(labels.length).toBeGreaterThan(3)
    for (const label of labels) {
      expect(label).not.toMatch(/https?:|r_[0-9a-f]{32}|sig=|safe|ligtas/i)
    }
    expect(log).not.toHaveBeenCalled()
    expect(warn).not.toHaveBeenCalled()
    expect(error).not.toHaveBeenCalled()
    expect(within(container).queryByRole('link')).toBeNull()
  })
})
