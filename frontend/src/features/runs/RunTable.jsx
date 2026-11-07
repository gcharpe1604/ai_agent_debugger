import { useState } from 'react'
import Icon from '../../components/Icon.jsx'
import { runsHref, evidenceHref } from '../../app/routes.jsx'

const columns = [['name', 'Run'], ['startedAt', 'Started'], ['outcome', 'Execution status'], ['durationMs', 'Duration'], ['completeness', 'Completeness'], ['recordedErrorCount', 'Recorded errors'], ['investigation', 'Investigation']]
const clock = new Intl.DateTimeFormat('en-GB', { timeZone: 'UTC', hour: '2-digit', minute: '2-digit', second: '2-digit', hourCycle: 'h23' })
const calendar = new Intl.DateTimeFormat('en-GB', { timeZone: 'UTC', day: '2-digit', month: 'short', year: 'numeric' })
function Started({ value }) {
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? <span>Unknown</span> : <><time className="tabular" dateTime={value}>{clock.format(date)}</time><div className="row-secondary">{calendar.format(date)} · UTC</div></>
}
export default function RunTable({ items, projectId, search, query, onSort, busy, children, live = false }) {
  const [copyNotice, setCopyNotice] = useState('')
  async function copy(run) {
    try { await navigator.clipboard.writeText(run.traceId); setCopyNotice(`Trace ID copied for ${run.id}`) }
    catch { setCopyNotice(`Copy unavailable. Trace ID: ${run.traceId}`) }
  }
  return <><div className="table-region" role="region" aria-label="Recorded runs" tabIndex="0" aria-busy={busy}>
    <table className="runs-table"><caption className="sr-only">{live ? "Locally captured SDK runs. Recorded errors count ERROR spans; capture completeness remains unknown." : "Recorded runs. Outcomes, capture completeness, recorded error counts and investigation states are independent."}</caption><colgroup><col className="col-run"/><col className="col-start"/><col className="col-status"/><col className="col-duration"/><col className="col-capture"/><col className="col-errors"/><col className="col-investigation"/></colgroup>
      <thead><tr>{columns.map(([field, label]) => <th key={field} scope="col" className={['durationMs', 'recordedErrorCount'].includes(field) ? 'numeric' : ''} aria-sort={query.sort === field ? query.direction === 'asc' ? 'ascending' : 'descending' : 'none'}><button className="sort-button" aria-label={`Sort by ${label.toLowerCase()}`} title={field === 'recordedErrorCount' ? live ? 'Received spans with raw ERROR status; parent and child spans are counted separately' : 'Supplied error-operation groups, not individual ERROR spans' : `Sort by ${label.toLowerCase()}`} onClick={() => onSort(field)}>{label}{query.sort === field && <span aria-hidden="true">{query.direction === 'asc' ? '↑' : '↓'}</span>}</button></th>)}</tr></thead>
      <tbody>{items.map(run => <tr key={run.id}><td><a className="run-link" href={runsHref(projectId, search, run.id)} aria-label={`${run.name} ${run.id}`} title={`${run.name} · ${run.service}`}><span>{run.name}</span><Icon name="arrow"/></a><div className="row-secondary">{!live && <span>{run.id}</span>}<button className="identity-copy mono" onClick={() => copy(run)} aria-label={`Copy trace ID for ${run.id}`} title={run.traceId}>{run.traceId.slice(0, 8)}…{run.traceId.slice(-4)}<Icon name="copy"/></button></div></td>
        <td><Started value={run.startedAt}/></td>
        <td><span className={`status ${run.outcome === 'Failed' ? 'error-badge' : ''}`}>{['Failed', 'Completed'].includes(run.outcome) && <Icon name={run.outcome === 'Failed' ? 'error' : 'check'}/>} {run.outcome}</span></td>
        <td className="numeric mono">{run.durationMs == null ? 'Unknown' : run.durationMs >= 1000 ? `${(run.durationMs / 1000).toFixed(3)} s` : `${run.durationMs} ms`}</td>
        <td><span className={`status ${run.completeness === 'Partial' ? 'partial' : ''}`}>{run.completeness === 'Partial' && <Icon name="error"/>}{run.completeness}</span></td>
        <td className="numeric"><span className={run.recordedErrorCount ? 'error-count mono' : 'mono muted'}>{run.recordedErrorCount > 0 && <Icon name="error"/>}{run.recordedErrorCount ?? 'Unknown'}</span>{run.recovered && <div className="row-secondary align-right">Recovered</div>}</td>
        <td>{run.investigation === 'Completed' ? <>{run.findingCount > 0 ? <a href={evidenceHref(projectId, run.id, search)} aria-label={`View ${run.findingCount} finding${run.findingCount === 1 ? '' : 's'} for ${run.name}`}>{run.findingCount} finding{run.findingCount === 1 ? '' : 's'}</a> : <span>{run.findingCount == null ? 'Count unavailable' : '0 findings'}</span>}<div className="row-secondary">Completed</div></> : <span className={run.investigation === 'Failed' ? 'analysis-error' : ''}>{run.investigation === 'Failed' && <Icon name="error"/>}{run.investigation}</span>}</td></tr>)}</tbody>
    </table>{children}
  </div><div className="sr-only" aria-live="polite">{copyNotice}</div>{copyNotice.startsWith('Copy unavailable') && <p className="copy-failure" role="status">{copyNotice}</p>}</>
}
