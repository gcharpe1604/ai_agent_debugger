import { typeLabel } from '../trace/treeModel.js'

export const ERROR_SPANS_TOOLTIP = "Spans with ERROR status, including parents that carry a child's error, so it is not a count of independent failures."

// Timestamp · Name · Trace ID · Status · Latency · Spans · Errors, then the
// columns that only some sources supply.
const allColumns = [['startedAt', 'Timestamp'], ['name', 'Name'], ['traceId', 'Trace ID'], ['outcome', 'Status'], ['durationMs', 'Latency'], ['spanCount', 'Spans'], ['recordedErrorCount', 'Errors'], ['model', 'Model'], ['totalTokens', 'Tokens'], ['costUsd', 'Cost'], ['completeness', 'Completeness'], ['investigation', 'Investigation']]
// Only show these columns when a visible row supplies a value.
const placeholder = { completeness: 'Unknown', investigation: 'Unavailable' }
// Columns that appear only once some visible trace records them.
const optional = ['spanCount', 'model', 'totalTokens', 'costUsd']
export const numericColumns = ['durationMs', 'spanCount', 'recordedErrorCount', 'totalTokens', 'costUsd']
// Columns the table can sort by (the trace ID is an identifier, not an order).
export const unsortableColumns = ['traceId']

// Hidden columns, chosen in the Columns menu. The Name column always stays.
export const hideableColumns = allColumns.map(([field]) => field).filter(field => field !== 'name')
// A stored hidden-column list is accepted only if every entry is a known column.
export const isHiddenColumnList = value => value === '' || value.split(',').every(field => hideableColumns.includes(field))

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

// Error count tone: grey at 0, red only when the run itself failed. A completed
// run with error spans (e.g. a recovered retry) keeps the normal text colour.
export const errorTone = run => !run.recordedErrorCount ? 'muted' : run.outcome === 'Failed' ? 'error' : 'plain'

// "ToolTimeout · LocalTools.invoke · pay · attempt 1 (+2)": exception type, span
// name, then the other deepest ERROR spans.
export function firstErrorText(firstError) {
  if (!firstError) return null
  const others = Number.isSafeInteger(firstError.leafErrorCount) && firstError.leafErrorCount > 1 ? ` (+${firstError.leafErrorCount - 1})` : ''
  return [firstError.exceptionType, firstError.spanName].filter(Boolean).join(' · ') + others
}
export const firstErrorTitle = firstError => `Open ${typeLabel(firstError.operationType)} span ${firstError.spanId}. Earliest recorded ERROR span without ERROR descendants. The extra count uses the same rule. This link identifies an error to inspect, not a cause.`

export const executionModeLabel = mode => ({ controlled: 'Controlled', live: 'Live' }[mode] ?? null)

// Column widths in px (the colgroup widths in index.css); Name takes the rest
// and needs at least NAME_MIN. Used to decide which columns fit.
const columnWidths = { startedAt: 148, traceId: 112, outcome: 112, durationMs: 96, spanCount: 72, recordedErrorCount: 72, model: 140, totalTokens: 88, costUsd: 88, completeness: 120, investigation: 136 }
const NAME_MIN = 160
const GUTTERS = 24
// Timestamp, Name, Status and Latency always stay; these go first, in order.
export const columnDropOrder = ['traceId', 'spanCount', 'recordedErrorCount', 'model', 'totalTokens', 'costUsd', 'completeness', 'investigation']

// The visible fields that fit `width` px of table. An unknown width keeps all.
export function fitRunColumns(fields, width) {
  if (!(width > 0)) return fields
  let kept = [...fields]
  const needed = () => kept.reduce((sum, field) => sum + (field === 'name' ? NAME_MIN : columnWidths[field] ?? 100), GUTTERS)
  for (const field of columnDropOrder) {
    if (needed() <= width) break
    kept = kept.filter(item => item !== field)
  }
  return kept
}
