import { useEffect } from 'react'
import AppShell from '../../components/AppShell.jsx'
import { runsHref, evidenceHref } from '../../app/routes.jsx'
import { returnQuery } from '../trace/traceState.js'
import { durationText } from '../trace/treeModel.js'
import { useInvestigationRead } from './useInvestigationRead.js'
import { InvestigationState } from './InvestigationControl.jsx'
import { evidenceQuery, traceQuery } from './evidenceState.js'
import EvidenceWorkspace from './EvidenceWorkspace.jsx'
import '../trace/trace.css'
import './evidence.css'

export default function EvidencePage({ repository, route, project, projects, cache }) {
  const { data, busy, error, retry } = useInvestigationRead(repository, project.id, route.runId)
  const scope = `${project.id}/${route.runId}`, params = new URLSearchParams(route.search)
  const attemptId = params.get('evidenceAttempt') || cache.get(scope)?.attemptId || data?.attempts[0]?.id
  const attempt = data?.attempts.find(item => item.id === attemptId)
  const findingId = params.get('evidenceFinding') || cache.get(`${scope}/${attemptId}`)?.findingId || attempt?.findings[0]?.id
  const finding = attempt?.findings.find(item => item.id === findingId)
  // The adapter's supplied order defines latest. Cached UI preference does not.
  const latest = data?.attempts[0], latestFinding = latest?.findings[0]
  const latestHref = evidenceHref(project.id, route.runId, evidenceQuery(route.search, { Attempt: latest?.id, Finding: latestFinding?.id, A: latestFinding?.citations[0]?.id, B: latestFinding?.citations[1]?.id, Focus: '' }))
  const run = data?.run
  const back = runsHref(project.id, traceQuery(route.search), route.runId)
  useEffect(() => {
    if (attempt) cache.set(scope, { attemptId: attempt.id })
    if (finding) cache.set(`${scope}/${attempt.id}`, { findingId: finding.id })
  }, [cache, scope, attempt, finding])
  function chooseAttempt(id) {
    window.history.replaceState(null, '', evidenceHref(project.id, route.runId, evidenceQuery(route.search, { Attempt: id, Finding: '', A: '', B: '', Focus: '' })))
    window.dispatchEvent(new HashChangeEvent('hashchange'))
  }
  function chooseFinding(id) {
    window.history.replaceState(null, '', evidenceHref(project.id, route.runId, evidenceQuery(route.search, { Attempt: attempt.id, Finding: id, A: '', B: '', Focus: '' })))
    window.dispatchEvent(new HashChangeEvent('hashchange'))
  }
  const header = <header className="app-header trace-app-header"><div className="trace-run-identity"><nav className="breadcrumbs" aria-label="Breadcrumb"><a href={runsHref(project.id, returnQuery(route.search))}>Runs</a><span aria-hidden="true">/</span><a href={back}>{route.runId}</a><span aria-hidden="true">/</span><span aria-current="page">Evidence</span></nav><h1>{run?.name || 'Evidence Focus'}</h1></div><div className="trace-run-actions"><a className="button small" href={back} aria-label="Back to trace">← Back to trace</a><span className="sample-badge">Sample data</span></div></header>
  return <AppShell projects={projects} project={project} route={{ ...route, search: returnQuery(route.search) }} header={header}><section className="evidence-page" aria-label="Evidence Focus" aria-busy={busy}>
    {run && <div className="trace-metadata"><span className={run.outcome === 'Failed' ? 'error-text' : ''}>{run.outcome}</span><span className="mono">{durationText(run.durationMs)}</span><span>Capture <strong>{run.completeness}</strong></span><span>{run.startedAt.replace('T', ' ').replace('Z', ' UTC')}</span><span>{run.service}</span></div>}
    {!data ? <div className="boundary">{busy ? <p role="status">Loading supplied investigation…</p> : <><h2>Investigation unavailable</h2><p role="alert">{error}</p><button className="button" onClick={retry}>Retry investigation read</button></>}</div> : <>
      {attempt && <div className="evidence-attempt">
        {data.attempts.length > 1 ? <label>Attempt<select aria-label="Investigation attempt" value={attempt.id} onChange={event => chooseAttempt(event.target.value)}>{data.attempts.map(item => <option key={item.id} value={item.id}>{item.label} · {item.state}</option>)}</select></label> : <span>{attempt.label} · {attempt.state}</span>}
        <span>Analyzed <strong className="mono">{attempt.snapshotId}</strong></span>
        <details className="evidence-attempt-details"><summary>Analysis details</summary><div><span className="mono">{attempt.id}</span><p>{attempt.limitations}</p><p>{attempt.referenceState}. Reference checks establish source grounding only; they do not prove semantic correctness or causality.</p></div></details>
        <span className="evidence-reference-state">{attempt.referenceState}</span>
      </div>}
      {attemptId && !attempt ? <div className="boundary"><h2>Analysis attempt unavailable</h2><p>This exact attempt is not present in this sample. No newer result has been substituted.</p>{latest && <a className="button" href={latestHref}>Open latest supplied attempt</a>}</div>
        : !attempt?.findings.length ? <div className="boundary evidence-state"><InvestigationState data={{ ...data, state: attempt?.state || data.state, attempts: attempt ? [attempt] : [] }}/></div>
          : !finding ? <div className="boundary"><h2>Finding unavailable</h2><p>The requested finding is not in this analyzed attempt.</p></div>
            : <>
              {attempt.findings.length > 1 && <label className="finding-selector">Finding<select aria-label="Finding" value={finding.id} onChange={event => chooseFinding(event.target.value)}>{attempt.findings.map((item, index) => <option key={item.id} value={item.id}>{index + 1} / {attempt.findings.length} · {item.title}</option>)}</select></label>}
              <EvidenceWorkspace key={`${scope}/${attempt.id}/${finding.id}`} repository={repository} projectId={project.id} runId={route.runId} attempt={attempt} finding={finding} search={route.search} cache={cache}/>
            </>}
    </>}
  </section></AppShell>
}
