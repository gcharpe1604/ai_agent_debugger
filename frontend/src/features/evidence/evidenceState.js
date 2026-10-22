export const evidenceKeys = ['evidenceAttempt', 'evidenceFinding', 'evidenceA', 'evidenceB', 'evidenceFocus']
export function traceQuery(search) {
  const params = new URLSearchParams(search)
  evidenceKeys.forEach(key => params.delete(key))
  return params.toString()
}
export function evidenceQuery(search, values) {
  const params = new URLSearchParams(search)
  for (const [key, value] of Object.entries(values)) {
    if (value) params.set(`evidence${key}`, value); else params.delete(`evidence${key}`)
  }
  return params.toString()
}
export function initialEvidenceState(search, citations, cached) {
  const params = new URLSearchParams(search)
  const ids = citations.map(item => item.id)
  const a = params.get('evidenceA') || cached?.a || ids[0]
  const b = params.get('evidenceB') || cached?.b || ids[1]
  // Explicit stale IDs must remain unavailable, never silently choose a new source.
  const focus = params.get('evidenceFocus') || cached?.focus
  return { reading: {}, formats: {}, context: {}, ...cached, a, b: b === a ? ids.find(id => id !== a) : b, focus: ['a', 'b'].includes(focus) && (focus !== 'b' || ids.length > 1) ? focus : null }
}
export function assignSource(ui, slot, id) {
  const other = slot === 'a' ? 'b' : 'a'
  return { ...ui, [slot]: id, ...(ui[other] === id ? { [other]: ui[slot] } : {}) }
}
export function resolveCitation(citation, source, snapshotId) {
  if (!source) return { available: false, reason: 'Captured source is not loaded.' }
  if (source.snapshotId !== snapshotId) return { available: false, reason: `Snapshot mismatch: source ${source.snapshotId || 'unknown'} does not match analyzed ${snapshotId}. No current value is substituted.` }
  if (!['captured', 'redacted', 'truncated'].includes(source.state) || !Object.hasOwn(source, 'value')) return { available: false, reason: source.reason || 'Captured historical source unavailable. No current value is substituted.' }
  let value = source.value, resolved = false
  if (citation.range && typeof value === 'string') {
    const { start, end } = citation.range
    resolved = Number.isInteger(start) && Number.isInteger(end) && start >= 0 && end > start && end <= value.length && value.slice(start, end) === citation.quote
  } else if (Array.isArray(citation.path)) {
    for (const part of citation.path) {
      if (value === null || typeof value !== 'object' || !Object.hasOwn(value, part)) return { available: true, resolved: false }
      value = value[part]
    }
    resolved = Object.hasOwn(source, 'citedValue') && JSON.stringify(value) === JSON.stringify(source.citedValue)
  }
  return { available: true, resolved }
}
