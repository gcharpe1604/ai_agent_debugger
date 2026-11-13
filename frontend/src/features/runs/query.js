export const sortFields = ['name', 'startedAt', 'outcome', 'durationMs', 'model', 'totalTokens', 'costUsd', 'completeness', 'recordedErrorCount', 'investigation']
export const outcomeOptions = ['Completed', 'Failed', 'Unknown']
export const completenessOptions = ['Complete', 'Partial', 'Unknown']
export const investigationOptions = ['Not requested', 'Pending', 'Running', 'Completed', 'Failed', 'Skipped']
export const modeOptions = ['controlled', 'live']
// Relative time ranges, newest first in the picker. '' means no time limit.
export const rangeOptions = [['', 'All time'], ['15m', 'Last 15 minutes'], ['1h', 'Last hour'], ['4h', 'Last 4 hours']]
const facet = (params, key, allowed) => params.getAll(key).filter((value, i, values) => allowed.includes(value) && values.indexOf(value) === i)
// Agent names are free text from captured data: bounded, de-duplicated.
const names = (params, key) => params.getAll(key).map(value => value.slice(0, 128)).filter((value, i, values) => value && values.indexOf(value) === i).slice(0, 20)
const duration = value => value !== null && value !== '' && Number.isFinite(Number(value)) && Number(value) >= 0 ? Number(value) : null

export function parseQuery(search) {
  const p = new URLSearchParams(search)
  return {
    search: (p.get('search') || '').slice(0, 256), time: ['all', 'recent'].includes(p.get('time')) ? p.get('time') : 'window',
    outcomes: facet(p, 'outcome', outcomeOptions), completeness: facet(p, 'capture', completenessOptions), investigations: facet(p, 'investigation', investigationOptions),
    hasErrors: p.get('errors') === 'yes', minMs: duration(p.get('minMs')), maxMs: duration(p.get('maxMs')),
    modes: facet(p, 'mode', modeOptions), agents: names(p, 'agent'), range: rangeOptions.some(([value]) => value && value === p.get('range')) ? p.get('range') : '',
    sort: sortFields.includes(p.get('sort')) ? p.get('sort') : 'startedAt', direction: p.get('direction') === 'asc' ? 'asc' : 'desc',
    page: Math.min(100000, Math.max(1, Math.floor(Number(p.get('page')) || 1))),
    pageSize: [5, 10, 25, 50].includes(Number(p.get('pageSize'))) ? Number(p.get('pageSize')) : 25,
  }
}
export function queryString(query) {
  const p = new URLSearchParams()
  if (query.search) p.set('search', query.search)
  if (query.time !== 'window') p.set('time', query.time)
  for (const [key, values] of [['outcome', query.outcomes], ['capture', query.completeness], ['investigation', query.investigations], ['mode', query.modes || []], ['agent', query.agents || []]]) values.forEach(value => p.append(key, value))
  if (query.range) p.set('range', query.range)
  if (query.hasErrors) p.set('errors', 'yes')
  if (query.minMs !== null) p.set('minMs', query.minMs)
  if (query.maxMs !== null) p.set('maxMs', query.maxMs)
  if (query.sort !== 'startedAt') p.set('sort', query.sort)
  if (query.direction !== 'desc') p.set('direction', query.direction)
  if (query.page !== 1) p.set('page', query.page)
  if (query.pageSize !== 25) p.set('pageSize', query.pageSize)
  return p.toString()
}
export function changeQuery(query, patch) {
  return { ...query, ...patch, page: Object.hasOwn(patch, 'page') ? patch.page : 1 }
}
