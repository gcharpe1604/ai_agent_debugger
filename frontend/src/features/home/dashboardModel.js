// Dashboard figures, derived only from the trace summaries a list read
// returned. Nothing is estimated: a trace without a duration is left out of
// latency, and statuses stay the recorded outcome values.

export const DASHBOARD_RANGES = [['24h', 'Last 24 hours'], ['7d', 'Last 7 days'], ['30d', 'Last 30 days'], ['', 'All time']]
export const DEFAULT_RANGE = '7d'
const HOUR = 3600 * 1000

// Nearest-rank percentile of finite values; null when there are none.
export function percentile(values, p) {
  const sorted = values.filter(Number.isFinite).sort((a, b) => a - b)
  if (!sorted.length) return null
  return sorted[Math.min(sorted.length - 1, Math.max(0, Math.ceil((p / 100) * sorted.length) - 1))]
}

// Failed / total, as a fraction 0..1; null for no runs.
export function errorRate(runs) {
  return runs.length ? runs.filter(run => run.outcome === 'Failed').length / runs.length : null
}

export function kpis(runs) {
  const durations = runs.map(run => run.durationMs)
  return { traces: runs.length, failed: runs.filter(run => run.outcome === 'Failed').length, errorRate: errorRate(runs), p50: percentile(durations, 50), p95: percentile(durations, 95) }
}

// Start of the local hour or day containing `ms`.
const floorTo = (ms, unit) => { const date = new Date(ms); if (unit === 'day') date.setHours(0, 0, 0, 0); else date.setMinutes(0, 0, 0); return date.getTime() }
const next = (ms, unit) => { const date = new Date(ms); if (unit === 'day') date.setDate(date.getDate() + 1); else date.setTime(ms + HOUR); return date.getTime() }

// Buckets for the chart: hourly for 24h, daily otherwise (local time). Fixed
// ranges end at `now` and always have every bucket; All time runs from the
// earliest run's day to today and is empty when there are no runs.
export function buckets(runs, range, now) {
  const unit = range === '24h' ? 'hour' : 'day'
  const times = runs.map(run => Date.parse(run.startedAt)).filter(Number.isFinite)
  const count = { '24h': 24, '7d': 7, '30d': 30 }[range]
  let start
  if (count) {
    start = floorTo(now, unit)
    for (let i = 1; i < count; i++) { const date = new Date(start); if (unit === 'day') date.setDate(date.getDate() - 1); else date.setTime(start - HOUR); start = date.getTime() }
  } else {
    if (!times.length) return []
    start = floorTo(Math.min(...times), unit)
  }
  const end = floorTo(count ? now : Math.max(now, ...times), unit)
  const list = []
  for (let at = start; at <= end; at = next(at, unit)) list.push({ start: new Date(at).toISOString(), startMs: at, endMs: next(at, unit), completed: 0, failed: 0, other: 0 })
  for (const run of runs) {
    const at = Date.parse(run.startedAt)
    const bucket = list.find(item => at >= item.startMs && at < item.endMs)
    if (!bucket) continue
    bucket[run.outcome === 'Completed' ? 'completed' : run.outcome === 'Failed' ? 'failed' : 'other']++
  }
  return list.map(item => ({ start: item.start, end: new Date(item.endMs).toISOString(), unit, completed: item.completed, failed: item.failed, other: item.other, total: item.completed + item.failed + item.other }))
}

// Per agent (run name): runs, p50, p95, error rate; most runs first.
export function agentLatency(runs) {
  const agents = new Map()
  for (const run of runs) {
    const list = agents.get(run.name) || []
    list.push(run)
    agents.set(run.name, list)
  }
  return [...agents].map(([name, list]) => ({ name, runs: list.length, p50: percentile(list.map(run => run.durationMs), 50), p95: percentile(list.map(run => run.durationMs), 95), errorRate: errorRate(list) }))
    .sort((a, b) => b.runs - a.runs || a.name.localeCompare(b.name, 'en'))
}

// Newest failed runs first.
export function recentFailures(runs, limit = 8) {
  return runs.filter(run => run.outcome === 'Failed').sort((a, b) => (b.startedAt || '').localeCompare(a.startedAt || '')).slice(0, limit)
}

export const percentText = value => value === null ? '—' : `${(value * 100).toFixed(value > 0 && value < 0.1 ? 1 : 0)}%`
