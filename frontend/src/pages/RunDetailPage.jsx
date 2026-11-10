import { useState } from 'react'
import AppShell from '../components/AppShell.jsx'
import Icon from '../components/Icon.jsx'
import { runsHref, evidenceHref } from '../app/routes.jsx'
import InvestigationControl from '../features/evidence/InvestigationControl.jsx'
import { useTraceRead } from '../features/trace/useTraceRead.js'
import { returnQuery } from '../features/trace/traceState.js'
import { durationText } from '../features/trace/treeModel.js'
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
  const [copyNotice, setCopyNotice] = useState('')
  const back = runsHref(project.id, returnQuery(route.search))
  async function copy() { try { await navigator.clipboard.writeText(data.run.traceId); setCopyNotice('Trace ID copied') } catch { setCopyNotice(`Copy unavailable. Trace ID: ${data.run.traceId}`) } }
  const traceId = data?.run.traceId
  const outcome = data?.run.outcome
  const copyId = traceId && <button className="trace-copy mono" onClick={copy} title={traceId} aria-label="Copy trace ID">{traceId.slice(0, 8)}…{traceId.slice(-4)}<Icon name="copy"/></button>
  const header = <header className="app-header trace-app-header">
    <div className="trace-run-identity">
      <nav className="breadcrumbs" aria-label="Breadcrumb"><a href={back} aria-label="Back to Traces">Traces</a><Icon name="chevron"/><span aria-current="page">{live && copyId ? copyId : route.runId}</span></nav>
      <div className="trace-title">
        <span className="trace-title-icon"><Icon name="branch"/></span>
        <h1>{data?.run.name || route.runId}</h1>
        {outcome && <span className="badge" data-state={outcome}>{outcome}</span>}
      </div>
    </div>
    {data && <button className="button small" onClick={() => downloadTrace(data)} title="Download this trace's run summary and span metadata as JSON"><Icon name="download"/>Download JSON</button>}
    {live && <span className="badge capture-context">Local capture</span>}
    {data && !live && <div className="trace-run-actions">
      {copyId}
      {new URLSearchParams(route.search).has('evidenceAttempt') && <a className="button small" href={evidenceHref(project.id, route.runId, route.search)} aria-label="Back to evidence">Back to evidence</a>}
      <InvestigationControl repository={investigationRepository} projectId={project.id} runId={route.runId} search={route.search}/>
    </div>}
  </header>
  return <AppShell projects={projects} project={project} route={{ ...route, search: returnQuery(route.search) }} header={header}>
    <div className="trace-page">
      {data ? <>
        <div className="trace-metadata">
          <span className="trace-fact"><Icon name="clock"/><span>Duration</span><strong className="mono">{durationText(data.run.durationMs)}</strong></span>
          <span className="trace-fact"><span>Started</span><strong>{data.run.startedAt.replace('T', ' ').replace('Z', ' UTC')}</strong></span>
          {live ? <span className="trace-loaded">{data.spans.length.toLocaleString('en')} {data.spans.length === 1 ? 'span' : 'spans'} received · completeness unknown</span>
            : <span className="badge" data-state={data.run.completeness}>Capture {data.run.completeness}</span>}
          {data.run.service !== data.run.name && <span>{data.run.service}</span>}
          {!live && <span className="trace-investigation-small">Investigation · {data.run.investigation}</span>}
        </div>
        {data.quality && <div className="trace-quality"><Icon name="error"/>{data.quality}</div>}
        <TraceWorkspace data={data} route={route} repository={repository} cache={cache} busy={busy} error={error} retryRead={retry} loadMore={setLimit} receivedOnly={live}/>
      </>
        : <section className="boundary" aria-busy={busy}>{busy ? <p role="status">Loading captured trace structure…</p> : <><h2>Trace unavailable</h2><p role="alert">{error}</p><button className="button" onClick={retry}>Retry trace read</button></>}</section>}
      <span className="sr-only" aria-live="polite">{copyNotice}</span>
    </div>
  </AppShell>
}
