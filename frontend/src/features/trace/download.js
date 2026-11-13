// A trace as the UI received it: run summary plus span metadata. Nothing is
// fetched or added; payload fields absent from the read stay absent.
export function traceDocument(data, exportedAt = new Date().toISOString()) {
  return { format: 'agent-debugger.trace.v1', exported_at: exportedAt, trace_id: data.run.traceId, run: data.run, spans: data.spans }
}

// The trace summaries on the current list page, with the query that selected
// them. Summaries only: spans are not read for this export.
export function traceListDocument({ projectId, query, result }, exportedAt = new Date().toISOString()) {
  return { format: 'agent-debugger.trace-list.v1', exported_at: exportedAt, project_id: projectId, query, total_matching: result.total, page: result.page, page_size: result.pageSize, traces: result.items }
}

function saveJson(value, filename, { document: doc = globalThis.document, url = globalThis.URL } = {}) {
  const blob = new Blob([JSON.stringify(value, null, 2)], { type: 'application/json' })
  const href = url.createObjectURL(blob)
  const link = doc.createElement('a')
  link.href = href
  link.download = filename
  doc.body.appendChild(link)
  link.click()
  link.remove()
  url.revokeObjectURL(href)
}

export function downloadTrace(data, environment) {
  saveJson(traceDocument(data), `trace-${data.run.traceId}.json`, environment)
}

export function downloadTraceList(list, environment) {
  saveJson(traceListDocument(list), `traces-${list.projectId}-page-${list.result.page}.json`, environment)
}
