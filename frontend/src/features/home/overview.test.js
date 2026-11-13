import { describe, expect, it } from 'vitest'
import { overview, percentile } from './overview.js'

const run = (name, outcome, durationMs, startedAt, extra = {}) => ({ id: `${name}-${startedAt}`, name, outcome, durationMs, startedAt, recordedErrorCount: 0, ...extra })

describe('home overview', () => {
  it('uses nearest-rank percentiles and ignores missing durations', () => {
    expect(percentile([40, 10, 30, 20], 50)).toBe(20)
    expect(percentile([40, 10, 30, 20], 95)).toBe(40)
    expect(percentile([null, undefined, NaN], 50)).toBeNull()
  })
  it('groups by agent, counts recorded outcomes and lists the newest failures first', () => {
    const runs = [
      run('rag', 'Completed', 10, '2026-11-11T10:00:00Z'),
      run('rag', 'Failed', 30, '2026-11-11T10:05:00Z', { recordedErrorCount: 2 }),
      run('tool', 'Completed', null, '2026-11-11T10:02:00Z', { recordedErrorCount: 1, recovered: true }),
      run('tool', 'Failed', 5, '2026-11-11T10:09:00Z'),
      run('rag', 'VENDOR', 20, '2026-11-11T09:00:00Z'),
    ]
    const result = overview(runs)
    expect(result.total).toBe(5)
    expect(result.status).toEqual({ Completed: 2, Failed: 2, Unknown: 1 })
    expect(result.withErrorSpans).toBe(2)
    expect(result.recovered).toBe(1)
    expect(result.agents).toEqual([
      { name: 'rag', count: 3, failed: 1, p50: 20, p95: 30, max: 30 },
      { name: 'tool', count: 2, failed: 1, p50: 5, p95: 5, max: 5 },
    ])
    expect(result.failures.map(item => item.name)).toEqual(['tool', 'rag'])
    expect(result.latest).toBe('2026-11-11T10:09:00Z')
  })
  it('handles an empty store', () => {
    expect(overview([])).toMatchObject({ total: 0, agents: [], failures: [], latest: null })
  })
})
