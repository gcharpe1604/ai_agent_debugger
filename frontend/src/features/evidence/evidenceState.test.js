import { describe, it, expect } from 'vitest'
import { resolveCitation, initialEvidenceState, traceQuery } from './evidenceState.js'

describe('evidence identity and grounding presentation', () => {
  it.each([false, 0, null, '', []])('resolves the exact captured path including %j', value => {
    expect(resolveCitation({ path: ['value'] }, { snapshotId: 's1', state: 'captured', value: { value }, citedValue: value }, 's1')).toEqual({ available: true, resolved: true })
  })
  it('rejects inherited paths and mismatched values without guessing a highlight', () => {
    const source = { snapshotId: 's1', state: 'captured', value: { value: false }, citedValue: true }
    expect(resolveCitation({ path: ['value'] }, source, 's1').resolved).toBe(false)
    expect(resolveCitation({ path: ['toString'] }, source, 's1').resolved).toBe(false)
    expect(resolveCitation({ path: ['value'] }, source, 's2').available).toBe(false)
  })
  it('requires a captured quote and exact valid range for a document highlight', () => {
    const source = { snapshotId: 's', state: 'captured', value: 'Policy: 14 days.' }
    expect(resolveCitation({ range: { start: 8, end: 15 }, quote: '14 days' }, source, 's').resolved).toBe(true)
    expect(resolveCitation({ range: { start: 0, end: 7 }, quote: '14 days' }, source, 's').resolved).toBe(false)
    expect(resolveCitation({ range: { start: -1, end: 15 }, quote: '14 days' }, source, 's').resolved).toBe(false)
  })
  it('retains stale citation IDs for an explicit unavailable view and keeps trace return query', () => {
    const state = initialEvidenceState('evidenceA=deleted', [{ id: 'one' }, { id: 'two' }])
    expect(state.a).toBe('deleted')
    expect(traceQuery('span=s1&view=timeline&from=50&evidenceA=one&evidenceAttempt=a1&search=refund')).toBe('span=s1&view=timeline&from=50&search=refund')
  })
})
