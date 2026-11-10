// A trace as the UI received it: run summary plus span metadata. Nothing is
// fetched or added; payload fields absent from the read stay absent.
export function traceDocument(data, exportedAt = new Date().toISOString()) {
  return { format: 'agent-debugger.trace.v1', exported_at: exportedAt, trace_id: data.run.traceId, run: data.run, spans: data.spans }
}

export function downloadTrace(data, { document: doc = globalThis.document, url = globalThis.URL } = {}) {
  const blob = new Blob([JSON.stringify(traceDocument(data), null, 2)], { type: 'application/json' })
  const href = url.createObjectURL(blob)
  const link = doc.createElement('a')
  link.href = href
  link.download = `trace-${data.run.traceId}.json`
  doc.body.appendChild(link)
  link.click()
  link.remove()
  url.revokeObjectURL(href)
}
