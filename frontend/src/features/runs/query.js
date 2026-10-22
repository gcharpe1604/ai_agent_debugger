export const sortFields = ['name', 'startedAt', 'outcome', 'durationMs', 'completeness', 'recordedErrorCount', 'investigation']
export const outcomeOptions = ['Completed', 'Failed', 'Unknown']
export const completenessOptions = ['Complete', 'Partial', 'Unknown']
export const investigationOptions = ['Not requested', 'Pending', 'Running', 'Completed', 'Failed', 'Skipped']
const facet = (params, key, allowed) => params.getAll(key).filter((value, i, values) => allowed.includes(value) && values.indexOf(value) === i)
const duration = value => value !== null && value !== '' && Number.isFinite(Number(value)) && Number(value) >= 0 ? Number(value) : null

export function parseQuery(search) {
  const p = new URLSearchParams(search)
  return {
    search: (p.get('search') || '').slice(0, 256), time: ['all', 'recent'].includes(p.get('time')) ? p.get('time') : 'window',
    outcomes: facet(p, 'outcome', outcomeOptions), completeness: facet(p, 'capture', completenessOptions), investigations: facet(p, 'investigation', investigationOptions),
    hasErrors: p.get('errors') === 'yes', minMs: duration(p.get('minMs')), maxMs: duration(p.get('maxMs')),
    sort: sortFields.includes(p.get('sort')) ? p.get('sort') : 'startedAt', direction: p.get('direction') === 'asc' ? 'asc' : 'desc',
    page: Math.min(100000, Math.max(1, Math.floor(Number(p.get('page')) || 1))),
    pageSize: [5, 10, 25, 50].includes(Number(p.get('pageSize'))) ? Number(p.get('pageSize')) : 25,
  }
}
export function queryString(query) {
  const p = new URLSearchParams()
  if (query.search) p.set('search', query.search)
  if (query.time !== 'window') p.set('time', query.time)
  for (const [key, values] of [['outcome', query.outcomes], ['capture', query.completeness], ['investigation', query.investigations]]) values.forEach(value => p.append(key, value))
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
