import { describe, it, expect } from 'vitest'
import { agentLatency, buckets, errorRate, kpis, percentText, percentile, recentFailures } from './dashboardModel.js'

const NOW = new Date(2026, 10, 24, 12, 30).getTime()
const at = (days, hours = 0) => new Date(NOW - days * 86400000 - hours * 3600000).toISOString()
const run = (name, outcome, durationMs, startedAt, extra = {}) => ({ id: `${name}-${startedAt}`, name, outcome, durationMs, startedAt, ...extra })

describe('percentile', () => {
  it('uses the nearest rank and ignores missing durations', () => {
    expect(percentile([5, 1, 3, 2, 4], 50)).toBe(3)
    expect(percentile([5, 1, 3, 2, 4], 95)).toBe(5)
    expect(percentile([10, null, undefined, NaN], 50)).toBe(10)
  })
  it('is null for no values and the only value for one', () => {
    expect(percentile([], 50)).toBeNull()
    expect(percentile([7], 95)).toBe(7)
  })
})

describe('KPIs and error rate', () => {
  it('handles empty input', () => {
    expect(errorRate([])).toBeNull()
    expect(kpis([])).toEqual({ traces: 0, failed: 0, errorRate: null, p50: null, p95: null })
    expect(percentText(null)).toBe('—')
  })
  it('handles a single run', () => {
    expect(kpis([run('a', 'Completed', 12, at(0))])).toEqual({ traces: 1, failed: 0, errorRate: 0, p50: 12, p95: 12 })
  })
  it('handles all failed runs', () => {
    const runs = [run('a', 'Failed', 1, at(0)), run('b', 'Failed', 2, at(1))]
    expect(kpis(runs)).toMatchObject({ traces: 2, failed: 2, errorRate: 1 })
    expect(percentText(1)).toBe('100%')
  })
  it('counts only Failed as an error; Unknown is neither', () => {
    expect(errorRate([run('a', 'Failed', 1, at(0)), run('a', 'Unknown', 1, at(0)), run('a', 'Completed', 1, at(0)), run('a', 'Completed', 1, at(0))])).toBe(0.25)
    expect(percentText(0.25)).toBe('25%')
    expect(percentText(0.05)).toBe('5.0%')
  })
})

describe('time buckets', () => {
  it('has 24 hourly buckets for 24h, ending with the current hour, all present when empty', () => {
    const list = buckets([], '24h', NOW)
    expect(list).toHaveLength(24)
    expect(list.every(bucket => bucket.unit === 'hour' && bucket.total === 0)).toBe(true)
    expect(new Date(list.at(-1).start).getHours()).toBe(12)
  })
  it('puts runs in their hour by outcome and leaves out runs outside the range', () => {
    const list = buckets([run('a', 'Completed', 1, at(0)), run('a', 'Failed', 1, at(0, 0.2)), run('a', 'Unknown', 1, at(0, 3)), run('a', 'Completed', 1, at(2))], '24h', NOW)
    expect(list.at(-1)).toMatchObject({ completed: 1, failed: 1, other: 0, total: 2 })
    expect(list.at(-4)).toMatchObject({ other: 1, total: 1 })
    expect(list.reduce((sum, bucket) => sum + bucket.total, 0)).toBe(3)
  })
  it('uses daily buckets for 7d and 30d', () => {
    expect(buckets([], '7d', NOW)).toHaveLength(7)
    const month = buckets([run('a', 'Failed', 1, at(29)), run('a', 'Completed', 1, at(0))], '30d', NOW)
    expect(month).toHaveLength(30)
    expect(month.every(bucket => bucket.unit === 'day')).toBe(true)
    expect(month[0]).toMatchObject({ failed: 1 })
    expect(month.at(-1)).toMatchObject({ completed: 1 })
  })
  it('runs All time from the earliest run day to today, and is empty without runs', () => {
    expect(buckets([], '', NOW)).toEqual([])
    const all = buckets([run('a', 'Completed', 1, at(40))], '', NOW)
    expect(all).toHaveLength(41)
    expect(all[0].total).toBe(1)
  })
})

describe('agents and failures', () => {
  it('groups by agent with runs, percentiles and error rate, most runs first', () => {
    const runs = [run('rag', 'Completed', 10, at(0)), run('tool', 'Failed', 30, at(0)), run('tool', 'Completed', 10, at(1)), run('tool', 'Completed', null, at(2))]
    expect(agentLatency(runs)).toEqual([
      { name: 'tool', runs: 3, p50: 10, p95: 30, errorRate: 1 / 3 },
      { name: 'rag', runs: 1, p50: 10, p95: 10, errorRate: 0 },
    ])
    expect(agentLatency([])).toEqual([])
  })
  it('lists failed runs newest first, up to the limit', () => {
    const runs = [run('a', 'Failed', 1, at(3)), run('b', 'Completed', 1, at(0)), run('c', 'Failed', 1, at(1)), run('d', 'Failed', 1, at(2))]
    expect(recentFailures(runs, 2).map(item => item.name)).toEqual(['c', 'd'])
    expect(recentFailures([])).toEqual([])
  })
})
