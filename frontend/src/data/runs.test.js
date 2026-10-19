import { describe, it, expect } from 'vitest'
import { selectRuns, fixtureRepository } from './runRepository.js'
import { parseQuery, queryString, changeQuery } from '../features/runs/query.js'

const items = [
  { id: 'a', projectId: 'one', name: 'alpha', traceId: 'abc000', startedAt: '2026-10-15T10:00:00Z', outcome: 'Completed', completeness: 'Partial', durationMs: 500, recordedErrorCount: 2, investigation: 'Not requested' },
  { id: 'b', projectId: 'one', name: 'beta', traceId: 'def000', startedAt: '2026-10-15T10:02:00Z', outcome: 'Failed', completeness: 'Complete', durationMs: 200, recordedErrorCount: 1, investigation: 'Failed' },
  { id: 'c', projectId: 'one', name: 'gamma', traceId: 'ghi000', startedAt: '2026-10-15T10:02:00Z', outcome: 'Completed', completeness: 'Complete', durationMs: 900, recordedErrorCount: 0, investigation: 'Completed' },
  { id: 'private', projectId: 'two', name: 'alpha', traceId: 'other', startedAt: '2026-10-15T10:03:00Z', outcome: 'Completed', completeness: 'Complete', durationMs: 100 },
]
const q = (patch = {}) => ({ ...parseQuery(''), time: 'all', ...patch })

describe('project-scoped run query', () => {
  it('never includes another project, even when names match', () => expect(selectRuns(items, 'one', q({ search: 'alpha' })).items.map(r => r.id)).toEqual(['a']))
  it('matches trace IDs case-insensitively', () => expect(selectRuns(items, 'one', q({ search: 'DEF' })).items.map(r => r.id)).toEqual(['b']))
  it('combines independent outcome, capture, investigation and duration filters', () => expect(selectRuns(items, 'one', q({ outcomes: ['Completed'], completeness: ['Partial'], investigations: ['Not requested'], minMs: 400, maxMs: 600 })).items.map(r => r.id)).toEqual(['a']))
  it('uses OR within a facet and retains completed runs containing errors', () => expect(selectRuns(items, 'one', q({ outcomes: ['Completed', 'Failed'], hasErrors: true })).items.map(r => r.id)).toEqual(['b', 'a']))
  it('sorts numerically and breaks ties by stable identity', () => {
    expect(selectRuns([...items].reverse(), 'one', q()).items.map(r => r.id)).toEqual(['b', 'c', 'a'])
    expect(selectRuns(items, 'one', q({ sort: 'durationMs', direction: 'asc' })).items.map(r => r.id)).toEqual(['b', 'a', 'c'])
  })
  it('paginates the filtered result and clamps stale pages', () => {
    const result = selectRuns(items, 'one', q({ pageSize: 2, page: 9 }))
    expect(result.items.map(r => r.id)).toEqual(['a']); expect(result.page).toBe(2); expect(result.total).toBe(3)
  })
  it('applies an explicit fixed sample time window, not the computer clock', () => expect(selectRuns(items, 'one', q({ time: 'recent' })).total).toBe(0))
  it('returns distinct first-use empty and no-match counts', () => {
    expect(selectRuns(items, 'one', q({ search: 'missing' })).projectTotal).toBe(3)
    expect(selectRuns(items, 'absent', q()).projectTotal).toBe(0)
  })
  it('fails explicitly for unknown projects and honors cancellation', async () => {
    await expect(fixtureRepository.listRuns({ projectId: 'missing', query: q() })).rejects.toThrow('Project unavailable')
    const controller = new AbortController(); controller.abort()
    await expect(fixtureRepository.listRuns({ projectId: 'agent-examples', query: q(), signal: controller.signal })).rejects.toMatchObject({ name: 'AbortError' })
  })
})

describe('restorable URL query', () => {
  it('round trips filters, sort and pagination without payloads', () => {
    const query = q({ search: 'refund & order', outcomes: ['Failed'], page: 2, pageSize: 5, minMs: 0, sort: 'durationMs', direction: 'asc' })
    expect(parseQuery(queryString(query))).toEqual(query)
  })
  it('resets pages on query changes but retains the chosen time window', () => expect(changeQuery(q({ page: 3, time: 'recent' }), { search: 'beta' })).toMatchObject({ page: 1, time: 'recent', search: 'beta' }))
  it('rejects malformed query values and unbounded page sizes', () => expect(parseQuery('sort=payload&direction=no&page=-2&pageSize=100000&minMs=-4')).toMatchObject({ sort: 'startedAt', direction: 'desc', page: 1, pageSize: 25, minMs: null }))
})
