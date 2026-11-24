// Errors recorded for one span: its exception events, or 1 when the span has an
// error message, an error type or an ERROR status but no exception event.
export function spanErrorCount(span, data) {
  const exceptions = Array.isArray(data?.events) ? data.events.filter(event => event?.name === 'exception').length : 0
  if (exceptions) return exceptions
  return data?.error || data?.errorType || (data?.status ?? span?.status) === 'ERROR' ? 1 : 0
}

// Inspector tabs in order. The Errors tab is left out when the span has none.
export function inspectorTabs(errorCount) {
  return ['Content', 'Attributes', 'Events', ...(errorCount > 0 ? ['Errors'] : [])]
}

// The ancestor breadcrumb keeps the root and the two nearest parents; the rest
// collapse into one "…" item (count of hidden ancestors).
export function breadcrumb(path, keep = 2) {
  if (path.length <= keep + 1) return path.map(span => ({ span }))
  return [{ span: path[0] }, { hidden: path.length - keep - 1 }, ...path.slice(-keep).map(span => ({ span }))]
}
