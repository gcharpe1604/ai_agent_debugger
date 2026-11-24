// One display format for every duration/offset in milliseconds. Exact values
// belong in title attributes and the inspector Details, not here.
//   < 10 ms   → "4.27 ms"     < 1000 ms → "245.3 ms"
//   < 60 s    → "12.35 s"     otherwise → "1m 05s"
// Units are chosen after rounding, so 9.999 ms reads "10.0 ms", not "10.00 ms".
export function formatDuration(ms) {
  if (!Number.isFinite(ms)) return 'Unavailable'
  const sign = ms < 0 ? '-' : '', value = Math.abs(ms)
  if (Number(value.toFixed(2)) < 10) return `${sign}${value.toFixed(2)} ms`
  if (Number(value.toFixed(1)) < 1000) return `${sign}${value.toFixed(1)} ms`
  if (Number((value / 1000).toFixed(2)) < 60) return `${sign}${(value / 1000).toFixed(2)} s`
  const seconds = Math.round(value / 1000)
  return `${sign}${Math.floor(seconds / 60)}m ${String(seconds % 60).padStart(2, '0')}s`
}

// Span and run durations. A recorded 0 means the operation finished within one
// tick of the recording clock, so "<1 ms" is true where "0.00 ms" misleads.
// Sub-millisecond values read in microseconds. Offsets keep formatDuration.
export function formatSpanDuration(ms) {
  if (!Number.isFinite(ms) || ms < 0) return formatDuration(ms)
  if (ms === 0) return '<1 ms'
  if (ms >= 1) return formatDuration(ms)
  const micros = Math.round(ms * 1000)
  return micros < 1 ? '<1 µs' : micros >= 1000 ? formatDuration(ms) : `${micros} µs`
}

// The one date format in the UI. A value is either a Unix-nanosecond string (span
// timestamps) or an ISO 8601 string (run summaries). Unusable values give null.
function parseTimestamp(value) {
  if (typeof value === 'string' && /^\d{1,20}$/.test(value)) {
    const nanos = BigInt(value)
    const date = new Date(Number(nanos / 1000000n))
    // Keep every recorded digit: ms from the Date, the remaining µs/ns appended.
    return Number.isNaN(date.getTime()) ? null : { date, iso: date.toISOString().replace('Z', `${String(nanos % 1000000n).padStart(6, '0')}Z`) }
  }
  if (typeof value !== 'string' || !value) return null
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? null : { date, iso: date.toISOString() }
}

// "24 Nov, 11:41:18" (or "24 Nov, 11:41" without seconds) in the viewer's time
// zone; timeZone is for tests only. null when the value is unusable.
export function formatTimestamp(value, { withSeconds = true, timeZone } = {}) {
  const parsed = parseTimestamp(value)
  if (!parsed) return null
  const parts = Object.fromEntries(new Intl.DateTimeFormat('en-GB', { timeZone, day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit', ...(withSeconds && { second: '2-digit' }), hourCycle: 'h23' }).formatToParts(parsed.date).map(part => [part.type, part.value]))
  return `${parts.day} ${parts.month}, ${parts.hour}:${parts.minute}${withSeconds ? `:${parts.second}` : ''}`
}

// Full UTC ISO time for the title attribute, e.g. "2026-11-10T19:53:08.420125900Z".
export const timestampTitle = value => parseTimestamp(value)?.iso ?? null

// Freshness label for the last data read.
export function agoText(then, now) {
  const seconds = Math.max(0, Math.round((now - then) / 1000))
  if (seconds < 10) return 'Updated just now'
  if (seconds < 60) return `Updated ${seconds} s ago`
  const minutes = Math.floor(seconds / 60)
  return minutes < 60 ? `Updated ${minutes} min ago` : `Updated ${Math.floor(minutes / 60)} h ago`
}

// Exact recorded value for titles and Details: no rounding.
export const exactDuration = ms => Number.isFinite(ms) ? `${ms} ms` : 'Unavailable'
