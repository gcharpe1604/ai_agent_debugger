import { describe, it, expect } from 'vitest'
import { interval, buildTimingIndex, normalizeWindow, zoomWindow, panWindow, fitInterval, projectInterval } from './timelineModel.js'
import { initialTraceState, returnQuery } from './traceState.js'

describe('Recorded interval and shared timeline scale', () => {
  it('uses recorded endpoints and supports elapsed-duration fixtures without coercing missing timestamps', () => {
    expect(interval({ start: 100, end: 350, duration: 250 })).toMatchObject({ start: 100, end: 350, duration: 250, state: 'valid' })
    expect(interval({ start: 100, duration: 250 })).toMatchObject({ start: 100, end: 350, state: 'valid' })
    expect(interval({ start: null, duration: 250 }).state).toBe('missing')
    expect(interval({ start: 0, end: null, duration: 250 }).state).toBe('missing')
    expect(interval({ start: 10, end: 9 }).state).toBe('invalid')
    expect(interval({ start: 10, duration: -1 }).state).toBe('invalid')
    expect(interval({ start: NaN, end: 40 }).state).toBe('invalid')
  })
  it('keeps a duration mismatch explicit and never uses negative or nonfinite drawing widths', () => {
    expect(interval({ start: 0, end: 10, duration: 8 })).toMatchObject({ duration: 10, mismatch: true })
    expect(projectInterval(interval({ start: Infinity, end: 10 }), { start: 0, end: 100 })).toMatchObject({ kind: 'invalid' })
    expect(interval({ start: .1, duration: .2 }).mismatch).toBe(false)
  })
  it('places overlapping operations on exactly the same shared origin and scale', () => {
    const window = { start: 100, end: 500 }
    expect(projectInterval(interval({ start: 200, end: 400 }), window)).toMatchObject({ kind: 'bar', left: 25, width: 50 })
    expect(projectInterval(interval({ start: 300, end: 450 }), window)).toMatchObject({ left: 50, width: 37.5 })
  })
  it('clips only drawings, explicitly marks outside intervals, and preserves zero-duration points', () => {
    const window = { start: 100, end: 300 }
    expect(projectInterval(interval({ start: 50, end: 150 }), window)).toMatchObject({ left: 0, width: 25, clippedStart: true })
    expect(projectInterval(interval({ start: 50, end: 100 }), window)).toMatchObject({ kind: 'before' })
    expect(projectInterval(interval({ start: 300, end: 400 }), window)).toMatchObject({ kind: 'after' })
    expect(projectInterval(interval({ start: 200, end: 200 }), window)).toMatchObject({ kind: 'point', left: 50, width: 0 })
  })
  it('uses the supplied run extent independently of filtering or out-of-run records', () => {
    const index = buildTimingIndex([{ id: 'a', start: 900, end: 1200 }, { id: 'b', start: null }], 1000)
    expect(index.extent).toEqual({ start: 0, end: 1000, source: 'run', available: true })
    expect(index.outsideCount).toBe(1)
    expect(index.missingCount).toBe(1)
    expect(index.navigationExtent).toMatchObject({ start: 0, end: 1200 })
    const selected = fitInterval(index.byId.get('a'), index.navigationExtent)
    expect(projectInterval(index.byId.get('a'), selected).kind).toBe('bar')
  })
  it('labels a loaded-only fallback and disables timing without any valid extent', () => {
    expect(buildTimingIndex([{ id: 'a', start: -50, end: 100 }], null).extent).toMatchObject({ start: -50, end: 100, source: 'loaded' })
    expect(buildTimingIndex([{ id: 'a', start: null }], null).extent.available).toBe(false)
    expect(buildTimingIndex([{ id: 'a', start: 0, end: 0 }], 0).extent).toMatchObject({ start: 0, end: 1, source: 'point' })
  })
  it('zooms around the center, clamps panning and fits selected intervals explicitly', () => {
    const extent = { start: 0, end: 1000, available: true }
    expect(zoomWindow(extent, .5, extent)).toEqual({ start: 250, end: 750 })
    expect(panWindow({ start: 250, end: 750 }, 1, extent)).toEqual({ start: 500, end: 1000 })
    expect(panWindow({ start: 250, end: 750 }, -1, extent)).toEqual({ start: 0, end: 500 })
    expect(normalizeWindow({ start: 900, end: 1400 }, extent)).toEqual({ start: 500, end: 1000 })
    expect(fitInterval(interval({ start: 400, end: 500 }), extent)).toEqual({ start: 390, end: 510 })
    expect(normalizeWindow({ start: NaN, end: 200 }, extent)).toEqual({ start: 0, end: 1000 })
  })
  it('restores validated view/window deep links and excludes timing query from Runs navigation', () => {
    const query = 'search=order&view=timeline&from=100&to=500&span=abc'
    expect(initialTraceState(query, null, 'overlay')).toMatchObject({ view: 'timeline', timeWindow: { start: 100, end: 500 } })
    expect(returnQuery(query)).toBe('search=order')
    expect(initialTraceState('view=garbage&from=bad&to=0', null, 'overlay')).toMatchObject({ view: 'tree', timeWindow: null })
  })
})
