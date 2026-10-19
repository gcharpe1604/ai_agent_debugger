import { useState } from 'react'
import AppShell from '../components/AppShell.jsx'
import Icon from '../components/Icon.jsx'
import { runsHref, evidenceHref } from '../app/routes.jsx'
import InvestigationControl from '../features/evidence/InvestigationControl.jsx'
import { useTraceRead } from '../features/trace/useTraceRead.js'
import { returnQuery } from '../features/trace/traceState.js'
import { durationText } from '../features/trace/treeModel.js'
import TraceWorkspace from '../features/trace/TraceWorkspace.jsx'
import '../features/trace/trace.css'

export default function RunDetailPage({ repository, investigationRepository, route, project, projects, cache }) {
  const scope = `${project.id}/${route.runId}`
  const [limit, setLimit] = useState(() => {
    const value = Number(new URLSearchParams(route.search).get('loaded'))
    return value > 0 ? Math.min(2100, Math.floor(value)) : cache.get(scope)?.limit
  })
  const { data, busy, error, retry } = useTraceRead(repository, project.id, route.runId, limit)
  const [copyNotice, setCopyNotice] = useState('')
  const back = runsHref(project.id, returnQuery(route.search))
  async function copy() { try { await navigator.clipboard.writeText(data.run.traceId); setCopyNotice('Trace ID copied') } catch { setCopyNotice(`Copy unavailable. Trace ID: ${data.run.traceId}`) } }
  const header = <header className="app-header trace-app-header"><div className="trace-run-identity"><nav className="breadcrumbs" aria-label="Breadcrumb"><a href={back} aria-label="Back to Runs">Runs</a><span aria-hidden="true">/</span><span aria-current="page">{route.runId}</span></nav><h1>{data?.run.name || route.runId}</h1></div><div className="trace-run-actions">{data && <><button className="trace-copy mono" onClick={copy} title={data.run.traceId} aria-label="Copy trace ID">{data.run.traceId.slice(0, 8)}…{data.run.traceId.slice(-4)}<Icon name="copy"/></button>{new URLSearchParams(route.search).has('evidenceAttempt') && <a className="button small" href={evidenceHref(project.id, route.runId, route.search)} aria-label="Back to evidence">Back to evidence</a>}<InvestigationControl repository={investigationRepository} projectId={project.id} runId={route.runId} search={route.search}/></>}<span className="sample-badge">Sample data</span></div></header>
  return <AppShell projects={projects} project={project} route={{ ...route, search: returnQuery(route.search) }} header={header}>
    <div className="trace-page">
      {data ? <><div className="trace-metadata"><span className={`status ${data.run.outcome === 'Failed' ? 'error-badge' : ''}`}>{['Completed', 'Failed'].includes(data.run.outcome) && <Icon name={data.run.outcome === 'Failed' ? 'error' : 'check'}/>}{data.run.outcome}</span><span className="mono">{durationText(data.run.durationMs)}</span><span>Capture <strong>{data.run.completeness}</strong></span><span>{data.run.startedAt.replace('T', ' ').replace('Z', ' UTC')}</span><span>{data.run.service}</span><span className="trace-investigation-small">Investigation · {data.run.investigation}</span></div>{data.quality && <div className="trace-quality"><Icon name="error"/>{data.quality}</div>}<TraceWorkspace data={data} route={route} repository={repository} cache={cache} busy={busy} error={error} retryRead={retry} loadMore={setLimit}/></>
        : <section className="boundary" aria-busy={busy}>{busy ? <p role="status">Loading sample trace structure…</p> : <><h2>Run unavailable</h2><p role="alert">{error}</p><button className="button" onClick={retry}>Retry trace read</button></>}</section>}
      <span className="sr-only" aria-live="polite">{copyNotice}</span>
    </div>
  </AppShell>
}
