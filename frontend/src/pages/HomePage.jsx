import { useMemo, useState } from 'react'
import AppShell from '../components/AppShell.jsx'
import Icon from '../components/Icon.jsx'
import Select from '../components/ui/Select.jsx'
import Timestamp from '../components/Timestamp.jsx'
import UpdatedAgo from '../components/UpdatedAgo.jsx'
import { runsHref } from '../app/routes.jsx'
import { exactDuration, formatSpanDuration } from '../app/format.js'
import { useRuns } from '../features/runs/useRuns.js'
import { parseQuery } from '../features/runs/query.js'
import { firstErrorText } from '../features/runs/runColumns.js'
import { DASHBOARD_RANGES, DEFAULT_RANGE, agentLatency, buckets, kpis, percentText, recentFailures } from '../features/home/dashboardModel.js'
import TracesChart from '../features/home/TracesChart.jsx'
import SetupGuide from '../features/home/SetupGuide.jsx'
import '../features/home/home.css'

const durationLabel = value => value === null ? '—' : formatSpanDuration(value)
// Every run in the range, newest first. The repository reads at most 1,000
// runs (newest first) and says so with partialAt.
const rangeQuery = range => ({ ...parseQuery(''), time: 'all', range, pageSize: 100000 })

function Tile({ label, value, title }) {
  return <section className="kpi-tile" aria-label={label}><span className="kpi-label">{label}</span><span className="kpi-value tabular" title={title}>{value}</span></section>
}

function Dashboard({ project, result, range, now }) {
  const runs = result.items
  const figures = useMemo(() => kpis(runs), [runs])
  const series = useMemo(() => buckets(runs, range, now), [runs, range, now])
  const agents = useMemo(() => agentLatency(runs), [runs])
  const failures = useMemo(() => recentFailures(runs), [runs])
  return <>
    <div className="kpi-row">
      <Tile label="Traces" value={figures.traces.toLocaleString('en')}/>
      <Tile label="Error rate" value={percentText(figures.errorRate)} title={`${figures.failed} failed of ${figures.traces}`}/>
      <Tile label="p50 latency" value={durationLabel(figures.p50)} title={figures.p50 === null ? undefined : exactDuration(figures.p50)}/>
      <Tile label="p95 latency" value={durationLabel(figures.p95)} title={figures.p95 === null ? undefined : exactDuration(figures.p95)}/>
    </div>
    <section className="dashboard-card" aria-labelledby="chart-title">
      <h2 id="chart-title">Traces over time</h2>
      <TracesChart buckets={series}/>
    </section>
    <div className="dashboard-tables">
      <section className="dashboard-card" aria-labelledby="latency-title">
        <h2 id="latency-title">Latency by agent</h2>
        {agents.length ? <table className="dashboard-table">
          <thead><tr><th scope="col">Agent</th><th scope="col" className="numeric">Runs</th><th scope="col" className="numeric">p50</th><th scope="col" className="numeric">p95</th><th scope="col" className="numeric">Error rate</th></tr></thead>
          <tbody>{agents.map(agent => <tr key={agent.name}>
            <th scope="row"><a href={runsHref(project.id, new URLSearchParams([['agent', agent.name]]).toString())} title={`Show ${agent.name} traces`}>{agent.name}</a></th>
            <td className="numeric">{agent.runs.toLocaleString('en')}</td>
            <td className="numeric">{durationLabel(agent.p50)}</td>
            <td className="numeric">{durationLabel(agent.p95)}</td>
            <td className="numeric" data-tone={agent.errorRate > 0 ? 'error' : undefined}>{percentText(agent.errorRate)}</td>
          </tr>)}</tbody>
        </table> : <p className="dashboard-empty">No traces in this time range.</p>}
      </section>
      <section className="dashboard-card" aria-labelledby="failures-title">
        <h2 id="failures-title">Recent failures</h2>
        {failures.length ? <table className="dashboard-table">
          <thead><tr><th scope="col" className="col-time">Timestamp</th><th scope="col">Name</th><th scope="col">First error</th></tr></thead>
          <tbody>{failures.map(run => <tr key={run.id}>
            <td className="tabular secondary"><Timestamp value={run.startedAt}/></td>
            <td><a href={runsHref(project.id, run.firstError ? `span=${encodeURIComponent(run.firstError.spanId)}` : '', run.id)} title={`Open ${run.name} ${run.id}`}>{run.name}</a></td>
            {/* The durable summary records no exception type; the span name stands in. */}
            <td className={run.firstError ? 'error-text' : 'secondary'} title={run.firstError ? firstErrorText(run.firstError) : 'Not in the run summary; open the trace'}>{run.firstError?.exceptionType || run.firstError?.spanName || '—'}</td>
          </tr>)}</tbody>
        </table> : <p className="dashboard-empty">No failed traces in this time range.</p>}
      </section>
    </div>
  </>
}

function ProjectHome(props) {
  const [range, setRange] = useState(DEFAULT_RANGE)
  const query = useMemo(() => rangeQuery(range), [range])
  const runs = useRuns(props.repository, props.project.id, query, `dashboard:${range}`)
  return <HomeLayout {...props} runs={runs} range={range} setRange={setRange}/>
}

function HomeLayout({ project, projects, route, local, runs, range, setRange, traceRepository, checking, checkConnection }) {
  const result = runs?.result
  const empty = !result || result.projectTotal === 0
  const actions = runs && <>
    {!runs.busy && <UpdatedAgo at={runs.loadedAt}/>}
    <button className="button small" onClick={runs.refresh} disabled={runs.busy} title="Read the latest captured traces"><Icon name="refresh"/><span className="button-label">{runs.busy && result ? 'Refreshing…' : 'Refresh'}</span></button>
  </>
  const setup = local && <SetupGuide traceRepository={traceRepository} projectId={route.projectId} connected={!!project} checking={checking} checkConnection={checkConnection}/>
  return <AppShell projects={projects} project={project} route={route} local={local} actions={actions}>
    <section className="home-page" aria-labelledby="home-heading">
      <div className="view-heading">
        <h1 id="home-heading">Dashboard</h1>
        {runs && <div className="view-heading-actions"><Select aria-label="Time range" value={range} onValueChange={setRange} align="end" options={DASHBOARD_RANGES.map(([value, label]) => ({ value, label }))}/></div>}
      </div>
      {result?.partialAt && <p className="dashboard-cap">Based on the latest {result.partialAt.toLocaleString('en')} runs</p>}
      {empty && setup}
      {runs?.error && <div className="read-error" role="alert"><Icon name="error"/><div><strong>Could not load the dashboard</strong><p>{runs.error}</p></div><button className="button small" onClick={runs.refresh}>Retry</button></div>}
      {!result && runs?.busy && <p className="secondary home-loading">Loading dashboard…</p>}
      {result && result.projectTotal > 0 && <Dashboard project={project} result={result} range={range} now={runs.loadedAt}/>}
      {!empty && setup}
    </section>
  </AppShell>
}

export default function HomePage(props) {
  return props.project ? <ProjectHome {...props}/> : <HomeLayout {...props} runs={null}/>
}
