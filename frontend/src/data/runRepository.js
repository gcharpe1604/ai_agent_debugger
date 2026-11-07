/** In-process read interface only. Replacing this adapter does not define an HTTP API.
 * listRuns({projectId, query, signal}) resolves {items,total,projectTotal,page,pageSize}.
 * All outcome, capture, count and investigation values remain independently supplied.
 */
export function selectRuns(records, projectId, query, timeWindow = null) {
  const projectRuns = records.filter(run => run.projectId === projectId)
  const needle = query.search.trim().toLocaleLowerCase('en')
  const lower = query.time === 'recent' ? timeWindow?.recentStart : timeWindow?.start
  const filtered = projectRuns.filter(run =>
    (!needle || run.name.toLocaleLowerCase('en').includes(needle) || run.traceId.toLowerCase().includes(needle)) &&
    (!query.outcomes.length || query.outcomes.includes(run.outcome)) &&
    (!query.completeness.length || query.completeness.includes(run.completeness)) &&
    (!query.investigations.length || query.investigations.includes(run.investigation)) &&
    (!query.hasErrors || run.recordedErrorCount > 0) &&
    (query.minMs === null || (run.durationMs !== null && run.durationMs >= query.minMs)) &&
    (query.maxMs === null || (run.durationMs !== null && run.durationMs <= query.maxMs)) &&
    (!timeWindow || query.time === 'all' || (run.startedAt >= lower && run.startedAt <= timeWindow.end)))
  filtered.sort((a, b) => {
    const left = a[query.sort], right = b[query.sort]
    if (left == null || right == null) return left == null && right == null ? a.id.localeCompare(b.id) : left == null ? 1 : -1
    const order = typeof left === 'number' ? left - right : left.localeCompare(right, 'en')
    return order ? order * (query.direction === 'asc' ? 1 : -1) : a.id.localeCompare(b.id, 'en')
  })
  const page = Math.min(query.page, Math.max(1, Math.ceil(filtered.length / query.pageSize)))
  return { items: filtered.slice((page - 1) * query.pageSize, page * query.pageSize), total: filtered.length, projectTotal: projectRuns.length, page, pageSize: query.pageSize }
}
