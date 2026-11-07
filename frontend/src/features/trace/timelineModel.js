// Relative milliseconds supplied by the data adapter. Never infer dependencies.
export function interval(span) {
  if (span.start == null) return { state: 'missing', reason: 'Start not recorded' }
  if (!Number.isFinite(span.start)) return { state: 'invalid', reason: 'Invalid recorded start' }
  const explicitEnd = Object.hasOwn(span, 'end')
  if (explicitEnd && span.end == null) return { state: 'missing', reason: 'End not recorded' }
  if (!explicitEnd && span.duration == null) return { state: 'missing', reason: 'End and duration not recorded' }
  const end = explicitEnd ? span.end : span.start + span.duration
  if ((!explicitEnd && (!Number.isFinite(span.duration) || span.duration < 0)) || !Number.isFinite(end) || end < span.start || !Number.isFinite(end - span.start)) return { state: 'invalid', reason: 'Invalid recorded interval' }
  const duration = end - span.start
  const tolerance = Number.EPSILON * Math.max(1, Math.abs(span.start), Math.abs(end), Math.abs(duration)) * 8
  return { state: 'valid', start: span.start, end, duration, mismatch: Number.isFinite(span.duration) && Math.abs(span.duration - duration) > tolerance }
}

export function buildTimingIndex(spans, runDuration) {
  const byId = new Map()
  let missingCount = 0, invalidCount = 0, outsideCount = 0, mismatchCount = 0
  let min = 0, max = -Infinity
  const hasRun = Number.isFinite(runDuration) && runDuration >= 0
  for (const span of spans) {
    const timing = interval(span)
    byId.set(span.id, timing)
    if (timing.state === 'missing') missingCount++
    else if (timing.state === 'invalid') invalidCount++
    else {
      min = Math.min(min, timing.start); max = Math.max(max, timing.end)
      if (timing.mismatch) mismatchCount++
      if (hasRun && (timing.start < 0 || timing.end > runDuration)) outsideCount++
    }
  }
  let extent
  if (hasRun && runDuration > 0) extent = { start: 0, end: runDuration, source: 'run', available: true }
  else if (!hasRun && max > min) extent = { start: min, end: max, source: 'loaded', available: true }
  else if (hasRun || Number.isFinite(max)) extent = { start: hasRun ? 0 : min, end: (hasRun ? 0 : min) + 1, source: 'point', available: true }
  else extent = { start: 0, end: 1, source: 'unavailable', available: false }
  // Navigation may reach loaded clock outliers; Fit run retains reported bounds.
  const navigationExtent = { ...extent, start: Math.min(extent.start, min), end: Math.max(extent.end, max) }
  if (!Number.isFinite(navigationExtent.end - navigationExtent.start)) Object.assign(navigationExtent, extent)
  return { byId, extent, navigationExtent, missingCount, invalidCount, outsideCount, mismatchCount }
}

const clamp = (n, min, max) => Math.max(min, Math.min(max, n))
export function normalizeWindow(window, extent) {
  const full = { start: extent.start, end: extent.end }
  if (!window || !Number.isFinite(window.start) || !Number.isFinite(window.end) || window.end <= window.start) return full
  const span = clamp(window.end - window.start, Math.min(1, extent.end - extent.start), extent.end - extent.start)
  const start = clamp(window.start, extent.start, extent.end - span)
  return { start, end: start + span }
}
export function zoomWindow(window, factor, extent) {
  const width = (window.end - window.start) * factor, center = window.start + (window.end - window.start) / 2
  return normalizeWindow({ start: center - width / 2, end: center + width / 2 }, extent)
}
export function panWindow(window, direction, extent) {
  const shift = (window.end - window.start) * direction
  return normalizeWindow({ start: window.start + shift, end: window.end + shift }, extent)
}
export function fitInterval(timing, extent) {
  if (timing?.state !== 'valid') return null
  const padding = Math.max(Math.min(0.5, (extent.end - extent.start) / 2), timing.duration * .1)
  return normalizeWindow({ start: timing.start - padding, end: timing.end + padding }, extent)
}
export function projectInterval(timing, window) {
  if (!timing || timing.state !== 'valid') return { kind: timing?.state || 'missing' }
  const point = timing.duration === 0
  if (timing.end < window.start || (!point && timing.end === window.start)) return { kind: 'before' }
  if (timing.start > window.end || (!point && timing.start === window.end)) return { kind: 'after' }
  const span = window.end - window.start
  const start = Math.max(timing.start, window.start), end = Math.min(timing.end, window.end)
  return { kind: point ? 'point' : 'bar', left: (start - window.start) / span * 100, width: (end - start) / span * 100, clippedStart: timing.start < window.start, clippedEnd: timing.end > window.end }
}
export function timeLabel(value) {
  if (!Number.isFinite(value)) return 'Unavailable'
  return `${Number((Math.abs(value) >= 1000 ? value / 1000 : value).toFixed(3))}${Math.abs(value) >= 1000 ? ' s' : ' ms'}`
}
export function intervalLabel(timing) {
  return timing?.state === 'valid' ? `Recorded ${timeLabel(timing.start)} to ${timeLabel(timing.end)}, duration ${timeLabel(timing.duration)}${timing.mismatch ? '; recorded duration disagrees with endpoints' : ''}` : timing?.reason || 'Timing not recorded'
}
