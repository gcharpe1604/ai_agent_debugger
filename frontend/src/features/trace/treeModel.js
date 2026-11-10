import { formatSpanDuration } from '../../app/format.js'

export const ROW_HEIGHT = 36
export const types = ['run', 'agent', 'model', 'tool', 'retrieval', 'api', 'state', 'custom']
export const typeLabel = type => ({ run: 'Run', agent: 'Agent', model: 'Model', tool: 'Tool', retrieval: 'Retrieval', api: 'API', state: 'State', custom: 'Custom' }[type] || `Custom · ${type || 'unknown'}`)
export const statusText = status => ['OK', 'ERROR', 'UNSET'].includes(status) ? status : status === null || status === undefined || status === '' ? 'Unknown' : `Unknown · ${status}`
export const durationText = value => Number.isFinite(value) && value >= 0 ? formatSpanDuration(value) : 'Unavailable'
export const knownCount = value => Number.isSafeInteger(value) && value >= 0 ? value : null

export function recordedAttempt(span) {
  if (span.type !== 'tool' || typeof span.step !== 'string' || !Number.isSafeInteger(span.attempt) || span.attempt < 1) return null
  const step = span.step.trim()
  if (!step) return null
  const displayStep = step.charAt(0).toUpperCase() + step.slice(1)
  return { step: displayStep, attempt: span.attempt, label: `${displayStep} · attempt ${span.attempt}` }
}

export function operationLabel(span) {
  return recordedAttempt(span)?.label ?? span.name
}
export function childLabel(row) {
  // Visible text only; aria-description still states that the total is unknown.
  if (row.childKnown === null) return `${row.childLoaded} loaded`
  return `${row.childLoaded === row.childKnown ? row.childKnown : `${row.childLoaded}/${row.childKnown}`} ${row.childKnown === 1 ? 'child' : 'children'}`
}

export function buildIndex(spans) {
  const byId = new Map(spans.map(span => [span.id, span]))
  const children = new Map(), roots = [], missing = [], cyclic = new Set(), finished = new Set()
  for (const span of spans) {
    const path = [], positions = new Map()
    let node = span
    while (node && !finished.has(node.id)) {
      if (positions.has(node.id)) { path.slice(positions.get(node.id)).forEach(id => cyclic.add(id)); break }
      positions.set(node.id, path.length); path.push(node.id); node = byId.get(node.parentId)
    }
    path.forEach(id => finished.add(id))
  }
  for (const span of spans) {
    if (cyclic.has(span.id)) continue
    if (span.parentId === null || span.parentId === undefined) roots.push(span)
    else if (!byId.has(span.parentId)) missing.push(span)
    else { if (!children.has(span.parentId)) children.set(span.parentId, []); children.get(span.parentId).push(span) }
  }
  return { byId, children, roots, missing, cyclic: [...cyclic].map(id => byId.get(id)), spans }
}
export function ancestors(index, id) {
  const result = [], visited = new Set([id])
  let parent = index.byId.get(index.byId.get(id)?.parentId)
  while (parent && !visited.has(parent.id)) { result.unshift(parent); visited.add(parent.id); parent = index.byId.get(parent.parentId) }
  return result
}
export function visibleTree(index, expanded, query) {
  const filtered = !!(query.search.trim() || query.type || query.status)
  const needle = query.search.trim().toLowerCase()
  const direct = index.spans.filter(span => (!needle || `${span.name} ${span.id} ${operationLabel(span)}`.toLowerCase().includes(needle)) && (!query.type || span.type === query.type) && (!query.status || (query.status === 'unknown' ? !['OK', 'ERROR', 'UNSET'].includes(span.status) : span.status === query.status)))
  const matches = direct.map(span => span.id), matched = new Set(matches), included = new Set(matches)
  if (filtered) direct.forEach(span => ancestors(index, span.id).forEach(parent => included.add(parent.id)))
  const rows = [], visited = new Set()
  // guides[d] is true when the ancestor at depth d has later visible siblings,
  // so its parent's connector line continues through this row. `last` ends
  // this row's own connector at its midpoint.
  function walk(list, depth, guides) {
    const shown = list.filter(span => !visited.has(span.id) && (!filtered || included.has(span.id)))
    const positions = new Map(list.map((span, position) => [span.id, position]))
    for (const [order, span] of shown.entries()) {
      if (visited.has(span.id)) continue
      visited.add(span.id)
      const children = index.children.get(span.id) || []
      const childKnown = knownCount(span.childCount)
      const last = order === shown.length - 1
      rows.push({ id: span.id, span, depth, context: filtered && !matched.has(span.id), hasChildren: children.length > 0 || childKnown === null || childKnown > 0, childLoaded: children.length, childKnown, expanded: children.length > 0 && (filtered ? children.some(child => included.has(child.id)) : expanded.has(span.id)), position: positions.get(span.id) + 1, siblings: list.length, guides, last })
      if (filtered || expanded.has(span.id)) walk(children, depth + 1, [...guides, !last])
    }
  }
  walk(index.roots, 0, [])
  for (const [id, name, list] of [['missing', 'Parent unavailable', index.missing], ['cycle', 'Invalid parent cycle', index.cyclic]]) {
    if (list.some(span => !filtered || included.has(span.id))) { rows.push({ id: `group-${id}`, group: true, name }); walk(list, 0, []) }
  }
  return { rows, matches, filtered }
}

// The run's top-level steps in recorded start order: the children of the first
// operation that has more than one child, following single-child wrappers
// (run -> agent -> steps). Routing spans (route.*) mark decisions between steps.
// `repeat` flags a step name seen earlier, i.e. a loop or retry. Derived
// structure only: start order is not causal order.
export const PATH_PREFIXES = ['node.']
export function executionPath(index, limit = 40) {
  let parent = index.roots.length === 1 ? index.roots[0] : null
  const seen = new Set([parent?.id])
  while (parent && (index.children.get(parent.id)?.length || 0) === 1) {
    const only = index.children.get(parent.id)[0]
    if (seen.has(only.id)) break
    seen.add(only.id); parent = only
  }
  const children = parent ? [...(index.children.get(parent.id) || [])] : []
  if (children.length < 2) return { steps: [], hidden: 0 }
  children.sort((a, b) => (Number.isFinite(a.start) ? a.start : Infinity) - (Number.isFinite(b.start) ? b.start : Infinity) || a.id.localeCompare(b.id))
  const names = new Set()
  const steps = children.map(span => {
    const decision = span.name.startsWith('route.')
    const label = decision ? span.name.slice('route.'.length) : PATH_PREFIXES.reduce((name, prefix) => name.startsWith(prefix) ? name.slice(prefix.length) : name, operationLabel(span))
    const repeat = !decision && names.has(label)
    if (!decision) names.add(label)
    return { id: span.id, label, decision, repeat, error: span.status === 'ERROR', type: span.type }
  })
  return { steps: steps.slice(0, limit), hidden: Math.max(0, steps.length - limit) }
}
export function windowRows(rows, scrollTop, height, activeId) {
  const start = Math.max(0, Math.floor(scrollTop / ROW_HEIGHT) - 5)
  const end = Math.min(rows.length, Math.ceil((scrollTop + height) / ROW_HEIGHT) + 5)
  const indices = new Set(Array.from({ length: Math.max(0, end - start) }, (_, i) => start + i))
  const active = rows.findIndex(row => row.id === activeId)
  if (active >= 0) indices.add(active)
  return [...indices].sort((a, b) => a - b).map(index => ({ ...rows[index], index }))
}
export function restoreAnchor(rows, anchor, index) {
  if (!anchor) return 0
  let id = anchor.id, position = rows.findIndex(row => row.id === id)
  const seen = new Set()
  while (position < 0 && index && !seen.has(id)) { seen.add(id); id = index.byId.get(id)?.parentId; if (!id) break; position = rows.findIndex(row => row.id === id) }
  return position < 0 ? 0 : position * ROW_HEIGHT + Math.max(0, Math.min(ROW_HEIGHT - 1, anchor.offset || 0))
}
