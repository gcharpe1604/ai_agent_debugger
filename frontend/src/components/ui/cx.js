// Joins class names, skipping falsy parts.
export const cx = (...parts) => parts.filter(Boolean).join(' ')

// Radix layers close on Escape from a document capture listener. Stopping the
// event there keeps page-level Escape handlers (trace preview, inspector) from
// also acting on the same key press; the layer itself still closes.
export function containEscape(handler) {
  return event => { handler?.(event); event.stopPropagation() }
}
