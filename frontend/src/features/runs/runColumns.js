import { typeLabel } from '../trace/treeModel.js'

export const ERROR_SPANS_TOOLTIP = "Counts every span with ERROR status, including parents that carry a child's error, so it is not a count of independent failures."

const allColumns = [['name', 'Trace'], ['outcome', 'Execution status'], ['startedAt', 'Started'], ['durationMs', 'Duration'], ['model', 'Model'], ['totalTokens', 'Tokens'], ['costUsd', 'Cost'], ['completeness', 'Completeness'], ['recordedErrorCount', 'Error spans'], ['investigation', 'Investigation']]
// Only show these columns when a visible row supplies a value.
const placeholder = { completeness: 'Unknown', investigation: 'Unavailable' }
// Model usage columns appear only once some visible trace records them.
const optional = ['model', 'totalTokens', 'costUsd']

export function runColumns(items) {
  return allColumns.filter(([field]) => optional.includes(field) ? items.some(run => run[field] != null) : !(field in placeholder) || items.some(run => run[field] !== placeholder[field]))
}

// "input → output" as one short line, when the read supplies previews.
export function ioPreview(run, limit = 80) {
  const clip = value => typeof value === 'string' && value.trim() ? (value.length > limit ? value.slice(0, limit - 1) + '…' : value) : null
  const input = clip(run.inputPreview), output = clip(run.outputPreview)
  return input || output ? `${input ?? '—'} → ${output ?? '—'}` : null
}
export const formatCost = value => Number.isFinite(value) ? `$${value < 0.01 && value > 0 ? value.toFixed(4) : value.toFixed(2)}` : '—'

// "ToolTimeout · LocalTools.invoke · pay · attempt 1 (+2)": exception type, span
// name, then the other deepest ERROR spans.
export function firstErrorText(firstError) {
  if (!firstError) return null
  const others = Number.isSafeInteger(firstError.leafErrorCount) && firstError.leafErrorCount > 1 ? ` (+${firstError.leafErrorCount - 1})` : ''
  return [firstError.exceptionType, firstError.spanName].filter(Boolean).join(' · ') + others
}
export const firstErrorTitle = firstError => `Open ${typeLabel(firstError.operationType)} span ${firstError.spanId}. Earliest recorded ERROR span without ERROR descendants. The extra count uses the same rule. This link identifies an error to inspect, not a cause.`

export const executionModeLabel = mode => ({ controlled: 'Controlled', live: 'Live' }[mode] ?? null)
