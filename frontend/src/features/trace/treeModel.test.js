import { describe, it, expect } from 'vitest'
import { ROW_HEIGHT, buildIndex, visibleTree, windowRows, restoreAnchor, statusText } from './treeModel.js'

const spans = [
  { id: 'root', parentId: null, name: 'Run', type: 'run', status: 'OK', duration: 1000 },
  { id: 'agent', parentId: 'root', name: 'Agent', type: 'agent', status: 'UNSET', duration: 990 },
  { id: 'a1', parentId: 'agent', name: 'shipping quote attempt 1', type: 'tool', status: 'ERROR', duration: 600 },
  { id: 'api', parentId: 'a1', name: 'GET quote', type: 'api', status: 'ERROR', duration: 580 },
  { id: 'a2', parentId: 'agent', name: 'shipping quote attempt 2', type: 'tool', status: 'OK', duration: 260, retryOf: 'a1' },
  { id: 'orphan', parentId: 'missing', name: 'Orphan', type: 'custom', status: 'VENDOR_PENDING', duration: 10 },
]
const query = { search: '', type: '', status: '' }
describe('recorded execution hierarchy', () => {
  it('retains nesting and separates missing parents without inventing spans', () => {
    const result = visibleTree(buildIndex(spans), new Set(spans.map(s => s.id)), query)
    expect(result.rows.filter(r => r.span).map(r => [r.id, r.depth])).toEqual([['root', 0], ['agent', 1], ['a1', 2], ['api', 3], ['a2', 2], ['orphan', 0]])
    expect(result.rows.filter(r => r.group).map(r => r.name)).toEqual(['Parent unavailable'])
  })
  it('collapses a branch while retaining independent descendant expansion', () => {
    const index = buildIndex(spans)
    const collapsed = visibleTree(index, new Set(['root', 'a1']), query)
    expect(collapsed.rows.filter(r => r.span).map(r => r.id)).toEqual(['root', 'agent', 'orphan'])
    expect(visibleTree(index, new Set(['root', 'agent', 'a1']), query).rows.some(r => r.id === 'api')).toBe(true)
  })
  it('filters loaded names/IDs and keeps ancestors even when collapsed', () => {
    const result = visibleTree(buildIndex(spans), new Set(), { search: 'SHIPPING', type: 'tool', status: 'ERROR' })
    expect(result.matches).toEqual(['a1'])
    expect(result.rows.map(r => r.id)).toEqual(['root', 'agent', 'a1'])
    expect(result.rows[0].context).toBe(true)
  })
  it('matches only supplied raw statuses, never treating UNSET/unknown as OK', () => {
    expect(statusText('UNSET')).toBe('UNSET'); expect(statusText(null)).toBe('Unknown')
    expect(statusText('VENDOR_PENDING')).toBe('Unknown · VENDOR_PENDING')
    expect(visibleTree(buildIndex(spans), new Set(), { ...query, status: 'unknown' }).matches).toEqual(['orphan'])
  })
  it('terminates on cyclic or self-parent records and keeps them inspectable', () => {
    const cyclic = buildIndex([{ id: 'a', parentId: 'b', name: 'a' }, { id: 'b', parentId: 'a', name: 'b' }, { id: 'c', parentId: 'c', name: 'c' }])
    expect(visibleTree(cyclic, new Set(['a', 'b', 'c']), query).rows.filter(r => r.span).map(r => r.id).sort()).toEqual(['a', 'b', 'c'])
  })
})
describe('bounded row rendering and anchors', () => {
  it('windows a 2,100-row list, retaining an offscreen active descendant', () => {
    const result = windowRows(Array.from({ length: 2100 }, (_, i) => ({ id: String(i) })), 1000 * ROW_HEIGHT, 480, '0')
    expect(result.length).toBeLessThanOrEqual(27)
    expect(result.some(r => r.id === '0')).toBe(true)
    expect(result.some(r => r.id === '1000')).toBe(true)
  })
  it('restores a stable anchor when structure is appended or reordered', () => {
    expect(restoreAnchor([{ id: 'new' }, { id: 'root' }, { id: 'agent' }], { id: 'agent', offset: 7 })).toBe(2 * ROW_HEIGHT + 7)
  })
})
