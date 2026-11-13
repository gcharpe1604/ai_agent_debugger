import { describe, expect, it } from 'vitest'
import { traceStats } from './traceStats.js'

describe('trace stats', () => {
  it('counts received spans, ERROR spans, depth and types in a fixed type order', () => {
    const spans = [
      { id: 'r', parentId: null, type: 'run', status: 'ERROR' },
      { id: 'a', parentId: 'r', type: 'agent', status: 'UNSET' },
      { id: 't1', parentId: 'a', type: 'tool', status: 'ERROR' },
      { id: 't2', parentId: 'a', type: 'tool', status: 'OK' },
      { id: 'x', parentId: 't2', type: 'vendor.thing', status: 'OK' },
    ]
    expect(traceStats(spans)).toEqual({ spans: 5, errors: 2, depth: 4, byType: [['run', 1], ['agent', 1], ['tool', 2], ['custom', 1]] })
  })
  it('stops at missing parents and cycles instead of looping', () => {
    const spans = [{ id: 'a', parentId: 'b', type: 'tool' }, { id: 'b', parentId: 'a', type: 'tool' }, { id: 'o', parentId: 'gone', type: 'custom' }]
    const result = traceStats(spans)
    expect(result.spans).toBe(3)
    expect(result.depth).toBeLessThanOrEqual(2)
  })
})
