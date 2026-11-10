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

// Exact recorded value for titles and Details: no rounding.
export const exactDuration = ms => Number.isFinite(ms) ? `${ms} ms` : 'Unavailable'
