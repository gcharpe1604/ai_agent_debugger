import { describe, it, expect, vi } from 'vitest'
import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { treeColumns, treeGridTemplate } from './treeColumns.js'
import { buildIndex, treeGuides, visibleTree } from './treeModel.js'
import { waterfallPosition } from './timelineModel.js'
import { breadcrumb, inspectorTabs, spanErrorCount } from './inspectorModel.js'
import JsonView, { ARRAY_PREVIEW, STRING_PREVIEW } from './JsonView.jsx'
import TraceFacts from './TraceFacts.jsx'
import SplitDivider from '../../components/ui/SplitDivider.jsx'
import { splitKeyWidth } from '../../components/ui/split.js'
import { TooltipProvider } from '../../components/ui/Tooltip.jsx'

describe('tree column priority', () => {
  it('never drops Name or Duration; Start and Type go below 640 px; Span ID needs 840 px', () => {
    expect(treeColumns(1200, { showIds: true })).toEqual(['name', 'id', 'start', 'type', 'duration'])
    expect(treeColumns(1200)).toEqual(['name', 'start', 'type', 'duration'])
    expect(treeColumns(839, { showIds: true })).toEqual(['name', 'start', 'type', 'duration'])
    expect(treeColumns(640)).toEqual(['name', 'start', 'type', 'duration'])
    expect(treeColumns(639)).toEqual(['name', 'duration'])
    expect(treeColumns(420)).toEqual(['name', 'duration'])
    expect(treeColumns(0)).toEqual(['name', 'duration'])
  })
  it('builds a grid template with a flexible name and a narrower duration on small trees', () => {
    expect(treeGridTemplate(['name', 'start', 'type', 'duration'], 900)).toBe('minmax(0,1fr) 76px 84px 176px')
    expect(treeGridTemplate(['name', 'duration'], 400)).toBe('minmax(0,1fr) 120px')
  })
})

describe('mini waterfall position', () => {
  const extent = { start: 0, end: 200, available: true, source: 'run' }
  it('gives offset and length as fractions of the trace', () => {
    expect(waterfallPosition({ state: 'valid', start: 50, end: 150 }, extent)).toEqual({ left: 0.25, width: 0.5 })
  })
  it('clamps spans that run past the trace bounds', () => {
    expect(waterfallPosition({ state: 'valid', start: -20, end: 260 }, extent)).toEqual({ left: 0, width: 1 })
  })
  it('draws nothing for unusable timing or a zero-length trace', () => {
    expect(waterfallPosition({ state: 'missing' }, extent)).toBeNull()
    expect(waterfallPosition({ state: 'valid', start: 0, end: 1 }, { ...extent, source: 'point' })).toBeNull()
    expect(waterfallPosition({ state: 'valid', start: 0, end: 1 }, { start: 0, end: 1, available: false, source: 'unavailable' })).toBeNull()
  })
})

describe('inspector model', () => {
  it('counts exception events, else one error for an ERROR span, and hides the Errors tab at 0', () => {
    expect(spanErrorCount({ status: 'OK' }, { status: 'OK', events: [] })).toBe(0)
    expect(inspectorTabs(0)).toEqual(['Content', 'Attributes', 'Events'])
    expect(spanErrorCount({ status: 'ERROR' }, null)).toBe(1)
    expect(spanErrorCount({ status: 'OK' }, { error: 'boom' })).toBe(1)
    expect(spanErrorCount({ status: 'ERROR' }, { status: 'ERROR', events: [{ name: 'exception' }, { name: 'retry' }, { name: 'exception' }] })).toBe(2)
    expect(inspectorTabs(2)).toEqual(['Content', 'Attributes', 'Events', 'Errors'])
  })
  it('keeps the root and two nearest ancestors in the breadcrumb', () => {
    const path = ['a', 'b', 'c', 'd', 'e'].map(id => ({ id }))
    expect(breadcrumb(path.slice(0, 3)).map(item => item.span.id)).toEqual(['a', 'b', 'c'])
    expect(breadcrumb(path)).toEqual([{ span: path[0] }, { hidden: 2 }, { span: path[3] }, { span: path[4] }])
  })
})

describe('JSON viewer', () => {
  it('colours values by type, mutes keys and collapses and expands objects', async () => {
    const user = userEvent.setup()
    render(<JsonView value={{ name: 'refund', count: 3, ok: true, missing: null, nested: { inner: 'x' } }}/>)
    expect(screen.getByText('refund').className).toBe('json-string quoted')
    expect(screen.getByText('3').className).toBe('json-number')
    expect(screen.getByText('true').className).toBe('json-boolean')
    expect(screen.getByText('null').className).toBe('json-null')
    expect(screen.getByText('"count"').className).toBe('json-key')
    const nested = screen.getByRole('button', { name: 'Collapse nested' })
    expect(nested.getAttribute('aria-expanded')).toBe('true')
    await user.click(nested)
    expect(screen.queryByText('x')).toBeNull()
    expect(screen.getByText('1 key')).toBeTruthy()
    await user.click(screen.getByRole('button', { name: 'Expand nested' }))
    expect(screen.getByText('x')).toBeTruthy()
    await user.click(screen.getByRole('button', { name: 'Collapse value' }))
    expect(screen.queryByText('refund')).toBeNull()
    expect(screen.getByText('5 keys')).toBeTruthy()
  })
  it(`shows the first ${ARRAY_PREVIEW} items of a longer array until Show more`, async () => {
    const user = userEvent.setup()
    render(<JsonView value={{ items: Array.from({ length: 15 }, (_, index) => `item-${index}`) }}/>)
    expect(screen.getByText('item-9')).toBeTruthy()
    expect(screen.queryByText('item-10')).toBeNull()
    await user.click(screen.getByRole('button', { name: 'Show 5 more items' }))
    expect(screen.getByText('item-14')).toBeTruthy()
    expect(screen.queryByRole('button', { name: /more items/ })).toBeNull()
  })
  it(`shortens strings over ${STRING_PREVIEW} characters until Show more, and back`, async () => {
    const user = userEvent.setup()
    const long = 'a'.repeat(STRING_PREVIEW) + 'TAIL'
    render(<JsonView value={{ text: long }}/>)
    expect(screen.queryByText(/TAIL/)).toBeNull()
    expect(screen.getByText('a'.repeat(STRING_PREVIEW) + '…')).toBeTruthy()
    await user.click(screen.getByRole('button', { name: 'Show more (4 characters)' }))
    expect(screen.getByText(long)).toBeTruthy()
    await user.click(screen.getByRole('button', { name: 'Show less' }))
    expect(screen.queryByText(/TAIL/)).toBeNull()
  })
  it('shows a top-level string as text and never renders markup', () => {
    render(<JsonView value={'<b>not bold</b>'}/>)
    expect(screen.getByText('<b>not bold</b>').className).toBe('json-string')
    expect(document.querySelector('b')).toBeNull()
  })
})

describe('split divider', () => {
  it('maps keys to widths within the limits', () => {
    expect(splitKeyWidth('ArrowLeft', 400, 360, 780)).toBe(416)
    expect(splitKeyWidth('ArrowRight', 370, 360, 780)).toBe(360)
    expect(splitKeyWidth('Home', 500, 360, 780)).toBe(360)
    expect(splitKeyWidth('End', 500, 360, 780)).toBe(780)
    expect(splitKeyWidth('a', 500, 360, 780)).toBeUndefined()
  })
  it('resizes from the keyboard and resets with Enter', async () => {
    const user = userEvent.setup()
    const onChange = vi.fn(), onReset = vi.fn()
    render(<SplitDivider value={400} min={360} max={780} onChange={onChange} onReset={onReset} label="Resize panel"/>)
    const divider = screen.getByRole('separator', { name: 'Resize panel' })
    expect(divider.getAttribute('aria-orientation')).toBe('vertical')
    expect([divider.getAttribute('aria-valuemin'), divider.getAttribute('aria-valuenow'), divider.getAttribute('aria-valuemax')]).toEqual(['360', '400', '780'])
    divider.focus()
    await user.keyboard('{ArrowLeft}')
    expect(onChange).toHaveBeenLastCalledWith(416)
    await user.keyboard('{ArrowRight}')
    expect(onChange).toHaveBeenLastCalledWith(384)
    await user.keyboard('{Enter}')
    expect(onReset).toHaveBeenCalledTimes(1)
  })
})

describe('trace header facts', () => {
  const run = { startedAt: '2026-11-24T11:41:18Z', durationMs: 1234 }
  const stats = { spans: 12, errors: 0, depth: 4, byType: [['agent', 1], ['tool', 3]] }
  const renderFacts = (props = {}) => render(<TooltipProvider><TraceFacts run={run} stats={stats} spansNote="12 spans received · completeness unknown" {...props}/></TooltipProvider>)
  it('lists Started, Duration, Spans, Errors and Depth in that order', () => {
    renderFacts()
    const items = within(screen.getByRole('list', { name: 'Trace facts' })).getAllByRole('listitem')
    expect(items.map(item => item.dataset.stat)).toEqual(['started', 'duration', 'spans', 'errors', 'depth'])
    expect(items.slice(1).map(item => item.textContent)).toEqual(['Duration 1.23 s', '12 spans', '0 errors', 'Depth 4'])
    expect(screen.queryByText(/completeness unknown/)).toBeNull()
  })
  it('marks errors red only when there are some', () => {
    renderFacts()
    expect(document.querySelector('[data-stat="errors"]').dataset.tone).toBeUndefined()
    renderFacts({ stats: { ...stats, errors: 2 } })
    expect(document.querySelectorAll('[data-stat="errors"]')[1].dataset.tone).toBe('error')
  })
  it('moves span-type counts into a Types popover', async () => {
    const user = userEvent.setup()
    renderFacts()
    expect(screen.queryByRole('list', { name: 'Spans by type' })).toBeNull()
    await user.click(screen.getByRole('button', { name: 'Types' }))
    const types = await screen.findByRole('list', { name: 'Spans by type' })
    expect(within(types).getAllByRole('listitem').map(item => item.textContent)).toEqual(['Agent1', 'Tool3'])
  })
})

describe('tree connector guides', () => {
  const span = (id, parentId) => ({ id, parentId, name: id, type: 'custom', status: 'OK', start: 0 })
  const all = { search: '', type: '', status: '' }
  const rowsFor = (spans, collapsed = []) => {
    const index = buildIndex(spans)
    const expanded = new Set(spans.map(item => item.id).filter(id => !collapsed.includes(id)))
    return Object.fromEntries(visibleTree(index, expanded, all).rows.map(row => [row.id, treeGuides(row)]))
  }
  it('gives the root no guide and a single child a └ in the root column', () => {
    const guides = rowsFor([span('r', null), span('a', 'r')])
    expect(guides.r).toEqual({ lines: [], elbow: null })
    expect(guides.a).toEqual({ lines: [], elbow: { column: 0, kind: 'end' } })
  })
  it('draws ├ for every sibling but the last, which gets └', () => {
    const guides = rowsFor([span('r', null), span('a', 'r'), span('b', 'r'), span('c', 'r')])
    expect([guides.a.elbow.kind, guides.b.elbow.kind, guides.c.elbow.kind]).toEqual(['tee', 'tee', 'end'])
  })
  it('keeps an ancestor line only while that ancestor has a later sibling', () => {
    // r ├ a ─ a1 ─ a2   (a has a later sibling b, so column 0 runs through a's subtree)
    //   └ b ─ b1 ─ b2   (b is last, so nothing runs below it)
    const guides = rowsFor([span('r', null), span('a', 'r'), span('a1', 'a'), span('a2', 'a1'), span('b', 'r'), span('b1', 'b'), span('b2', 'b1')])
    expect(guides.a1).toEqual({ lines: [0], elbow: { column: 1, kind: 'end' } })
    expect(guides.a2).toEqual({ lines: [0], elbow: { column: 2, kind: 'end' } })
    expect(guides.b1).toEqual({ lines: [], elbow: { column: 1, kind: 'end' } })
    expect(guides.b2).toEqual({ lines: [], elbow: { column: 2, kind: 'end' } })
  })
  it('handles a deep chain of last children with no lines at all', () => {
    const chain = [span('d0', null), ...Array.from({ length: 5 }, (_, i) => span(`d${i + 1}`, `d${i}`))]
    const guides = rowsFor(chain)
    expect(guides.d5).toEqual({ lines: [], elbow: { column: 4, kind: 'end' } })
  })
  it('hides a collapsed subtree and its guides; siblings keep theirs', () => {
    const spans = [span('r', null), span('a', 'r'), span('a1', 'a'), span('b', 'r')]
    const guides = rowsFor(spans, ['a'])
    expect(Object.keys(guides)).toEqual(['r', 'a', 'b'])
    expect(guides.a.elbow.kind).toBe('tee')
    expect(guides.b.elbow.kind).toBe('end')
  })
})
