// Project Home summary, derived only from the trace summaries a list read
// returned. Nothing is estimated: a trace without a duration is left out of
// latency, and statuses stay the recorded outcome values.

// Nearest-rank percentile of finite values; null when there are none.
export function percentile(values, p) {
  const sorted = values.filter(Number.isFinite).sort((a, b) => a - b)
  if (!sorted.length) return null
  return sorted[Math.min(sorted.length - 1, Math.max(0, Math.ceil((p / 100) * sorted.length) - 1))]
}

export function overview(runs, failureLimit = 5) {
  const agents = new Map()
  const status = { Completed: 0, Failed: 0, Unknown: 0 }
  let withErrorSpans = 0, recovered = 0
  for (const run of runs) {
    const agent = agents.get(run.name) || { name: run.name, count: 0, failed: 0, durations: [] }
    agent.count++
    if (run.outcome === 'Failed') agent.failed++
    if (Number.isFinite(run.durationMs)) agent.durations.push(run.durationMs)
    agents.set(run.name, agent)
    status[run.outcome in status ? run.outcome : 'Unknown']++
    if (run.recordedErrorCount > 0) withErrorSpans++
    if (run.recovered) recovered++
  }
  const byStart = (a, b) => (b.startedAt || '').localeCompare(a.startedAt || '')
  return {
    total: runs.length,
    status, withErrorSpans, recovered,
    agents: [...agents.values()]
      .map(({ durations, ...agent }) => ({ ...agent, p50: percentile(durations, 50), p95: percentile(durations, 95), max: durations.length ? Math.max(...durations) : null }))
      .sort((a, b) => b.count - a.count || a.name.localeCompare(b.name, 'en')),
    failures: runs.filter(run => run.outcome === 'Failed').sort(byStart).slice(0, failureLimit),
    latest: [...runs].sort(byStart)[0]?.startedAt ?? null,
  }
}
