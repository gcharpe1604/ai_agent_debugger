/** In-process read interface only. Replacing this adapter does not define an HTTP API.
 * Summary counts cover the matching results before pagination.
 * Facet counts for one filter group apply every other active filter, so each
 * count says how many traces that choice would add or keep.
 * All outcome, capture, count and investigation values remain independently supplied.
 */
const RANGE_MS = { '15m': 15 * 60 * 1000, '1h': 60 * 60 * 1000, '4h': 4 * 60 * 60 * 1000 }

function predicates(query, timeWindow, now) {
  const needle = query.search.trim().toLocaleLowerCase('en')
  const lower = query.time === 'recent' ? timeWindow?.recentStart : timeWindow?.start
  const since = query.range && RANGE_MS[query.range] && Number.isFinite(now) ? now - RANGE_MS[query.range] : null
  return {
    search: run => !needle || run.name.toLocaleLowerCase('en').includes(needle) || run.traceId.toLowerCase().includes(needle),
    outcome: run => !query.outcomes.length || query.outcomes.includes(run.outcome),
    completeness: run => !query.completeness.length || query.completeness.includes(run.completeness),
    investigation: run => !query.investigations.length || query.investigations.includes(run.investigation),
    errors: run => !query.hasErrors || run.recordedErrorCount > 0,
    duration: run => (query.minMs === null || (run.durationMs !== null && run.durationMs >= query.minMs)) && (query.maxMs === null || (run.durationMs !== null && run.durationMs <= query.maxMs)),
    window: run => !timeWindow || query.time === 'all' || (run.startedAt >= lower && run.startedAt <= timeWindow.end),
    mode: run => !query.modes?.length || query.modes.includes(run.executionMode),
    agent: run => !query.agents?.length || query.agents.includes(run.name),
    range: run => since === null || Date.parse(run.startedAt) >= since,
  }
}
const passes = (run, tests, skip) => Object.entries(tests).every(([key, test]) => key === skip || test(run))

export function selectRuns(records, projectId, query, timeWindow = null, now = null) {
  const projectRuns = records.filter(run => run.projectId === projectId)
  const tests = predicates(query, timeWindow, now)
  const filtered = projectRuns.filter(run => passes(run, tests))
  filtered.sort((a, b) => {
    const left = a[query.sort], right = b[query.sort]
    if (left == null || right == null) return left == null && right == null ? a.id.localeCompare(b.id) : left == null ? 1 : -1
    const order = typeof left === 'number' ? left - right : left.localeCompare(right, 'en')
    return order ? order * (query.direction === 'asc' ? 1 : -1) : a.id.localeCompare(b.id, 'en')
  })
  const page = Math.min(query.page, Math.max(1, Math.ceil(filtered.length / query.pageSize)))
  const summary = { failed: 0, withSpanErrors: 0 }
  for (const run of filtered) {
    if (run.outcome === 'Failed') summary.failed++
    if (run.recordedErrorCount > 0) summary.withSpanErrors++
  }
  const count = (skip, key) => {
    const counts = {}
    for (const run of projectRuns) if (passes(run, tests, skip)) { const value = key(run); counts[value] = (counts[value] || 0) + 1 }
    return counts
  }
  const facets = {
    outcome: count('outcome', run => run.outcome),
    mode: count('mode', run => run.executionMode ?? 'unrecorded'),
    agent: count('agent', run => run.name),
    errors: count('errors', run => run.recordedErrorCount > 0 ? 'with' : 'without'),
  }
  return { items: filtered.slice((page - 1) * query.pageSize, page * query.pageSize), total: filtered.length, projectTotal: projectRuns.length, page, pageSize: query.pageSize, summary, facets }
}
