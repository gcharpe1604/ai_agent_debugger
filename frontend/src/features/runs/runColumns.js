import { typeLabel } from '../trace/treeModel.js'

export const ERROR_SPANS_TOOLTIP = "Counts every span with ERROR status, including parents that carry a child's error, so it is not a count of independent failures."

const allColumns = [['name', 'Run'], ['startedAt', 'Started'], ['outcome', 'Execution status'], ['durationMs', 'Duration'], ['completeness', 'Completeness'], ['recordedErrorCount', 'Error spans'], ['investigation', 'Investigation']]
// A column whose every visible row has no real value only repeats "Unknown";
// the workspace banner already explains why. It returns once any row has a value.
const placeholder = { completeness: 'Unknown', investigation: 'Unavailable' }

export function runColumns(items) {
  return allColumns.filter(([field]) => !(field in placeholder) || items.some(run => run[field] !== placeholder[field]))
}

// "ToolTimeout · LocalTools.invoke · pay · attempt 1 (+2)": exception type, span
// name, then the other deepest ERROR spans. Labelled "First error", never a cause.
export function firstErrorText(firstError) {
  if (!firstError) return null
  const others = Number.isSafeInteger(firstError.leafErrorCount) && firstError.leafErrorCount > 1 ? ` (+${firstError.leafErrorCount - 1})` : ''
  return [firstError.exceptionType, firstError.spanName].filter(Boolean).join(' · ') + others
}
export const firstErrorTitle = firstError => `First error: ${firstErrorText(firstError)} · ${typeLabel(firstError.operationType)} span ${firstError.spanId}. The earliest ERROR span with no ERROR descendants; not a cause.`

export const executionModeLabel = mode => ({ controlled: 'Controlled', live: 'Live' }[mode] ?? null)
