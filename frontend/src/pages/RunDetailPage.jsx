import { useMemo, useState } from 'react'
import AppShell from '../components/AppShell.jsx'
import Icon from '../components/Icon.jsx'
import { runsHref, evidenceHref } from '../app/routes.jsx'
import InvestigationControl from '../features/evidence/InvestigationControl.jsx'
import { useTraceRead } from '../features/trace/useTraceRead.js'
import { returnQuery } from '../features/trace/traceState.js'
import TraceFacts from '../features/trace/TraceFacts.jsx'
import { traceStats } from '../features/trace/traceStats.js'
import TraceWorkspace from '../features/trace/TraceWorkspace.jsx'
import { downloadTrace } from '../features/trace/download.js'
import '../features/trace/trace.css'

export default function RunDetailPage({ repository, investigationRepository, route, project, projects, cache }) {
  const live = project.dataSource === 'local'
  const scope = `${project.id}/${route.runId}`
  const [limit, setLimit] = useState(() => {
    const value = Number(new URLSearchParams(route.search).get('loaded'))
    return value > 0 ? Math.min(2100, Math.floor(value)) : cache.get(scope)?.limit
  })
  const { data, busy, error, retry } = useTraceRead(repository, project.id, route.runId, limit)
  const stats = useMemo(() => data ? traceStats(data.spans) : null, [data])
  const [copyNotice, setCopyNotice] = useState('')
  const back = runsHref(project.id, returnQuery(route.search))
  async function copy() { try { await navigator.clipboard.writeText(data.run.traceId); setCopyNotice('Trace ID copied') } catch { setCopyNotice(`Copy unavailable. Trace ID: ${data.run.traceId}`) } }
  const traceId = data?.run.traceId
  const outcome = data?.run.outcome
  const copyId = traceId && <button className="trace-copy mono" onClick={copy} title={traceId} aria-label="Copy trace ID">{traceId.slice(0, 8)}…{traceId.slice(-4)}<Icon name="copy"/></button>
  const crumbs = [<a key="traces" href={back} aria-label="Back to Traces">Tracing</a>, live && copyId ? copyId : route.runId]
  const actions = <>
    <button className="button small" onClick={retry} disabled={busy} title="Read this trace again"><Icon name="refresh"/><span className="button-label">{busy && data ? 'Refreshing…' : 'Refresh'}</span></button>
    <button className="button small" disabled={!data} onClick={() => downloadTrace(data)} title="Download this trace's run summary and span metadata as JSON"><Icon name="download"/><span className="button-label">Download JSON</span></button>
  </>
  return <AppShell projects={projects} project={project} route={{ ...route, search: returnQuery(route.search) }} crumbs={crumbs} actions={actions}>
    <div className="trace-page">
      {data ? <>
        <header className="trace-heading">
          <div className="trace-title">
            <span className="trace-title-icon" aria-hidden="true"><Icon name="branch"/></span>
            <h1 title={data.run.service && data.run.service !== data.run.name ? `${data.run.name} · ${data.run.service}` : undefined}>{data.run.name || route.runId}</h1>
            {outcome && <span className="badge" data-state={outcome}>{outcome}</span>}
            {!live && <div className="trace-run-actions">
              {copyId}
              {new URLSearchParams(route.search).has('evidenceAttempt') && <a className="button small" href={evidenceHref(project.id, route.runId, route.search)} aria-label="Back to evidence">Back to evidence</a>}
              <InvestigationControl repository={investigationRepository} projectId={project.id} runId={route.runId} search={route.search}/>
            </div>}
          </div>
          {stats && <TraceFacts run={data.run} stats={stats} spansNote={live ? `${data.spans.length.toLocaleString('en')} ${data.spans.length === 1 ? 'span' : 'spans'} received · completeness unknown` : `Capture ${data.run.completeness}${data.run.investigation ? ` · Investigation ${data.run.investigation}` : ''}`}/>}
        </header>
        {data.quality && <div className="trace-quality"><Icon name="error"/>{data.quality}</div>}
        <TraceWorkspace data={data} route={route} repository={repository} cache={cache} busy={busy} error={error} retryRead={retry} loadMore={setLimit} receivedOnly={live}/>
      </>
        : <section className="boundary" aria-busy={busy}>{busy ? <p role="status">Loading captured trace structure…</p> : <><h2>Trace unavailable</h2><p role="alert">{error}</p><button className="button" onClick={retry}>Retry trace read</button></>}</section>}
      <span className="sr-only" aria-live="polite">{copyNotice}</span>
    </div>
  </AppShell>
}
