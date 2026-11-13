import { useMemo } from 'react'
import AppShell from '../components/AppShell.jsx'
import Icon from '../components/Icon.jsx'
import UpdatedAgo from '../components/UpdatedAgo.jsx'
import { runsHref } from '../app/routes.jsx'
import { formatSpanDuration } from '../app/format.js'
import { useRuns } from '../features/runs/useRuns.js'
import { parseQuery } from '../features/runs/query.js'
import { firstErrorText } from '../features/runs/runColumns.js'
import { overview } from '../features/home/overview.js'
import SetupGuide from '../features/home/SetupGuide.jsx'
import '../features/home/home.css'

// Every trace the project holds, newest first, for the summary. The local store
// keeps at most 100 traces, so one read covers it.
const allTraces = { ...parseQuery(''), time: 'all', pageSize: 10000 }
const durationLabel = value => value === null ? '—' : formatSpanDuration(value)
const started = value => value ? value.replace('T', ' ').replace(/(\.\d+)?Z$/, ' UTC') : 'Unknown'

function Bar({ value, total, tone }) {
  const share = total ? Math.round((value / total) * 100) : 0
  return <span className="home-bar" data-tone={tone} aria-hidden="true"><span style={{ width: `${share}%` }}/></span>
}

function Overview({ project, result }) {
  const summary = useMemo(() => overview(result.items), [result.items])
  const tracing = runsHref(project.id)
  const shownAgents = summary.agents.slice(0, 6)
  const statusRows = [['Completed', 'success'], ['Failed', 'error'], ['Unknown', undefined]]
  return <>
    <div className="home-grid">
      <section className="home-tile" aria-labelledby="tile-traces">
        <header><h2 id="tile-traces">Traces</h2><a href={tracing}>Open Tracing<Icon name="arrow"/></a></header>
        <p className="home-figure"><strong>{summary.total.toLocaleString('en')}</strong><span>{summary.agents.length === 1 ? '1 agent' : `${summary.agents.length} agents`}</span></p>
        <ul className="home-rows" aria-label="Traces by agent">
          {shownAgents.map(agent => <li key={agent.name}>
            <a href={runsHref(project.id, new URLSearchParams([['agent', agent.name]]).toString())} title={`Show ${agent.name} traces`}>{agent.name}</a>
            <Bar value={agent.count} total={summary.total}/>
            <span className="home-count">{agent.count}</span>
          </li>)}
        </ul>
        {summary.agents.length > shownAgents.length && <p className="home-note">+{summary.agents.length - shownAgents.length} more in Tracing</p>}
      </section>
      <section className="home-tile" aria-labelledby="tile-status">
        <header><h2 id="tile-status">Execution status</h2></header>
        <ul className="home-rows" aria-label="Traces by recorded status">
          {statusRows.map(([label, tone]) => <li key={label}>
            <a href={runsHref(project.id, `outcome=${label}`)}>{label}</a>
            <Bar value={summary.status[label]} total={summary.total} tone={tone}/>
            <span className="home-count">{summary.status[label]}</span>
          </li>)}
        </ul>
        <p className="home-note">{summary.withErrorSpans} with error spans{summary.recovered ? ` · ${summary.recovered} recovered after a retry` : ''}. A recovered retry is not a failed trace.</p>
      </section>
      <section className="home-tile" aria-labelledby="tile-latency">
        <header><h2 id="tile-latency">Latency by agent</h2></header>
        <table className="home-table">
          <thead><tr><th scope="col">Agent</th><th scope="col" className="numeric">p50</th><th scope="col" className="numeric">p95</th><th scope="col" className="numeric">Max</th></tr></thead>
          <tbody>{shownAgents.map(agent => <tr key={agent.name}><th scope="row">{agent.name}</th><td className="numeric mono">{durationLabel(agent.p50)}</td><td className="numeric mono">{durationLabel(agent.p95)}</td><td className="numeric mono">{durationLabel(agent.max)}</td></tr>)}</tbody>
        </table>
      </section>
    </div>
    <section className="home-section" aria-labelledby="recent-failures">
      <header className="home-section-heading"><h2 id="recent-failures">Recent failed traces</h2></header>
      {summary.failures.length ? <ul className="home-failures">
        {summary.failures.map(run => {
          const href = runsHref(project.id, run.firstError ? `span=${encodeURIComponent(run.firstError.spanId)}` : '', run.id)
          return <li key={run.id}>
            <a href={href}>{run.name}</a>
            <span className="error-text">{firstErrorText(run.firstError) || 'Failed'}</span>
            <time className="secondary" dateTime={run.startedAt}>{started(run.startedAt)}</time>
          </li>
        })}
      </ul> : <p className="home-note">No failed traces.</p>}
    </section>
  </>
}

function ProjectHome(props) {
  const runs = useRuns(props.repository, props.project.id, allTraces, 'home')
  return <HomeLayout {...props} runs={runs}/>
}

function HomeLayout({ project, projects, route, local, runs, traceRepository, checking, checkConnection }) {
  const result = runs?.result
  const empty = !result || result.projectTotal === 0
  const retention = project?.retentionSeconds ? `${+(project.retentionSeconds / 3600).toFixed(1)} h` : null
  const actions = runs && <>
    {!runs.busy && <UpdatedAgo at={runs.loadedAt}/>}
    <button className="button small" onClick={runs.refresh} disabled={runs.busy} title="Read the latest captured traces"><Icon name="refresh"/><span className="button-label">{runs.busy && result ? 'Refreshing…' : 'Refresh'}</span></button>
  </>
  const setup = local && <SetupGuide traceRepository={traceRepository} projectId={route.projectId} connected={!!project} checking={checking} checkConnection={checkConnection}/>
  return <AppShell projects={projects} project={project} route={route} local={local} actions={actions}>
    <section className="home-page" aria-labelledby="home-heading">
      <div className="view-heading">
        <h1 id="home-heading">Home</h1>
        {result && <span className="secondary">{result.projectTotal} {result.projectTotal === 1 ? 'trace' : 'traces'} held{local ? ` in backend memory${retention ? ` · kept ${retention}` : ''}` : ''}</span>}
      </div>
      {empty && setup}
      {runs?.error && <div className="read-error" role="alert"><Icon name="error"/><div><strong>Could not load the overview</strong><p>{runs.error}</p></div><button className="button small" onClick={runs.refresh}>Retry</button></div>}
      {!result && runs?.busy && <p className="secondary home-loading">Loading overview…</p>}
      {result && result.projectTotal > 0 && <Overview project={project} result={result}/>}
      {!empty && setup}
    </section>
  </AppShell>
}

export default function HomePage(props) {
  return props.project ? <ProjectHome {...props}/> : <HomeLayout {...props} runs={null}/>
}
