import { describe, it, expect } from 'vitest'
import { autoSelectedSpan } from './traceState.js'

const failed = { outcome: 'Failed', firstError: { spanId: 'a000000000000002' } }

describe('auto-select of first_error', () => {
  it('selects first_error for a failed run opened without span=', () => {
    expect(autoSelectedSpan('', undefined, failed)).toBe('a000000000000002')
    expect(autoSelectedSpan('panel=pinned', undefined, failed)).toBe('a000000000000002')
  })
  it('never overrides an explicit span= in the URL', () => {
    expect(autoSelectedSpan('span=a000000000000003', undefined, failed)).toBeNull()
  })
  it('keeps a remembered selection from this session', () => {
    expect(autoSelectedSpan('', { selected: 'a000000000000001' }, failed)).toBeNull()
  })
  it('does nothing for completed runs or runs without first_error', () => {
    expect(autoSelectedSpan('', undefined, { ...failed, outcome: 'Completed' })).toBeNull()
    expect(autoSelectedSpan('', undefined, { outcome: 'Failed', firstError: null })).toBeNull()
  })
})
