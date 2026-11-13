import { buildIndex, types } from './treeModel.js'

// Counts over the received spans only: how many, how many recorded ERROR, the
// deepest parent chain, and spans per operation type. Nothing is inferred about
// spans that were not received.
export function traceStats(spans, index = buildIndex(spans)) {
  const byType = {}
  let errors = 0, depth = 0
  const levels = new Map()
  const level = span => {
    if (levels.has(span.id)) return levels.get(span.id)
    // Iterative walk; cycles and missing parents stop at the last known span.
    const chain = [], seen = new Set()
    let node = span
    while (node && !levels.has(node.id) && !seen.has(node.id)) { seen.add(node.id); chain.push(node); node = index.byId.get(node.parentId) }
    let base = node && levels.has(node.id) ? levels.get(node.id) : 0
    for (let i = chain.length - 1; i >= 0; i--) { base += 1; levels.set(chain[i].id, base) }
    return levels.get(span.id)
  }
  for (const span of spans) {
    const type = types.includes(span.type) ? span.type : 'custom'
    byType[type] = (byType[type] || 0) + 1
    if (span.status === 'ERROR') errors++
    depth = Math.max(depth, level(span))
  }
  return { spans: spans.length, errors, depth, byType: types.filter(type => byType[type]).map(type => [type, byType[type]]) }
}
