import { evidenceHref } from '../../app/routes.jsx'
import { useInvestigationRead } from './useInvestigationRead.js'
import { evidenceQuery } from './evidenceState.js'
import './evidence.css'

export function InvestigationState({ data }) {
  const attempt = data.attempts[0]
  if (data.state === 'Not requested') return <><h2>Investigation not requested</h2><p>Requesting investigation is unavailable in this fixture-only frontend.</p></>
  if (data.state === 'Pending') return <><h2>Investigation pending</h2><p>No findings are available for this supplied pending attempt.</p></>
  if (data.state === 'Running') return <><h2>Investigation running</h2><p>This supplied attempt is in progress. No completed findings are available yet.</p></>
  if (data.state === 'Failed') return <><h2>Investigation failed</h2><p>{attempt?.error}</p><p>Retry is unavailable without an approved investigation integration.</p></>
  if (data.state !== 'Completed') return <><h2>Investigation unavailable</h2><p>Supplied state: {data.state || 'Unknown'}. Trace inspection remains available.</p></>
  return <><h2>No grounded findings returned</h2><p>{attempt?.limitations}</p></>
}
export default function InvestigationControl({ repository, projectId, runId, search }) {
  const { data, busy, error, retry } = useInvestigationRead(repository, projectId, runId)
  const attempt = data?.attempts[0], count = attempt?.findings.length || 0
  return <div className="investigation-control">
    {count > 0 && <a className="investigation-link" href={evidenceHref(projectId, runId, search)} aria-label={`View ${count} finding${count === 1 ? '' : 's'}`}>{count} finding{count === 1 ? '' : 's'}</a>}
    <details className="trace-menu investigation-details"><summary aria-label="Investigation details">{count > 0 ? 'Details' : `Investigation · ${busy ? 'Loading…' : data?.state || 'Unavailable'}`}</summary><div className="trace-popover">
      {busy ? <p role="status">Loading supplied investigation…</p> : error ? <><p role="alert">{error}</p><button className="button small" onClick={retry}>Retry investigation read</button></> : <>
        <strong>Investigation · {data.state}</strong>
        {attempt && <><p>{attempt.label} · <span className="mono">{attempt.id}</span></p><p>Analyzed <span className="mono">{attempt.snapshotId}</span></p><p>{attempt.referenceState}</p><p>{attempt.limitations}</p></>}
        {!count && <InvestigationState data={data}/>}
        {data.attempts.slice(1).filter(previous => previous.state === 'Completed' && previous.findings.length > 0).map(previous => <p key={previous.id}><a href={evidenceHref(projectId, runId, evidenceQuery(search, { Attempt: previous.id, Finding: previous.findings[0].id, A: '', B: '', Focus: '' }))} aria-label={`View earlier findings · ${previous.label}`}>Earlier results · {previous.label} · {previous.findings.length} finding{previous.findings.length === 1 ? '' : 's'}</a></p>)}
        <p className="secondary">Request/retry is disconnected. This preview cannot create or advance an attempt.</p>
        <button className="button small" disabled>{data.state === 'Failed' ? 'Retry investigation' : 'Request investigation'}</button>
      </>}
    </div></details>
  </div>
}
