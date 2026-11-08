import { useState } from 'react'
import Icon from '../../components/Icon.jsx'
import { runsHref, evidenceHref } from '../../app/routes.jsx'
import { exactDuration, formatDuration } from '../../app/format.js'
import { ERROR_SPANS_TOOLTIP, executionModeLabel, firstErrorText, firstErrorTitle, runColumns } from './runColumns.js'

const columnClass = { name: 'col-run', startedAt: 'col-start', outcome: 'col-status', durationMs: 'col-duration', completeness: 'col-capture', recordedErrorCount: 'col-errors', investigation: 'col-investigation' }
const clock = new Intl.DateTimeFormat('en-GB', { timeZone: 'UTC', hour: '2-digit', minute: '2-digit', second: '2-digit', hourCycle: 'h23' })
const calendar = new Intl.DateTimeFormat('en-GB', { timeZone: 'UTC', day: '2-digit', month: 'short', year: 'numeric' })
function Started({ value }) {
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? <span>Unknown</span> : <><time className="tabular" dateTime={value}>{clock.format(date)}</time><div className="row-secondary">{calendar.format(date)} · UTC</div></>
}
export default function RunTable({ items, projectId, search, query, onSort, busy, children, live = false }) {
  const [copyNotice, setCopyNotice] = useState('')
  const columns = runColumns(items)
  async function copy(run) {
    try { await navigator.clipboard.writeText(run.traceId); setCopyNotice(`Trace ID copied for ${run.id}`) }
    catch { setCopyNotice(`Copy unavailable. Trace ID: ${run.traceId}`) }
  }
  const cells = {
    name: run => {
      const mode = executionModeLabel(run.executionMode), firstError = run.outcome === 'Failed' ? firstErrorText(run.firstError) : null
      return <td key="name"><div className="run-name-line"><a className="run-link" href={runsHref(projectId, search, run.id)} aria-label={`${run.name} ${run.id}`} title={`${run.name} · ${run.service}`}><span>{run.name}</span><Icon name="arrow"/></a>{mode && <span className="mode-badge" title={`Execution mode recorded on the root span: ${run.executionMode}`}>{mode}</span>}</div>
        {firstError && <div className="row-secondary first-error" title={firstErrorTitle(run.firstError)}><span className="first-error-label">First error</span><span className="first-error-text">{firstError}</span></div>}
        <div className="row-secondary">{!live && <span>{run.id}</span>}<button className="identity-copy mono" onClick={() => copy(run)} aria-label={`Copy trace ID for ${run.id}`} title={run.traceId}>{run.traceId.slice(0, 8)}…{run.traceId.slice(-4)}<Icon name="copy"/></button></div></td>
    },
    startedAt: run => <td key="startedAt"><Started value={run.startedAt}/></td>,
    outcome: run => <td key="outcome"><span className={`status ${run.outcome === 'Failed' ? 'error-badge' : ''}`}>{['Failed', 'Completed'].includes(run.outcome) && <Icon name={run.outcome === 'Failed' ? 'error' : 'check'}/>} {run.outcome}</span></td>,
    durationMs: run => <td key="durationMs" className="numeric mono" title={run.durationMs == null ? undefined : exactDuration(run.durationMs)}>{run.durationMs == null ? 'Unknown' : formatDuration(run.durationMs)}</td>,
    completeness: run => <td key="completeness"><span className={`status ${run.completeness === 'Partial' ? 'partial' : ''}`}>{run.completeness === 'Partial' && <Icon name="error"/>}{run.completeness}</span></td>,
    recordedErrorCount: run => <td key="recordedErrorCount" className="numeric"><span className={run.recordedErrorCount ? 'error-count mono' : 'mono muted'}>{run.recordedErrorCount > 0 && <Icon name="error"/>}{run.recordedErrorCount ?? 'Unknown'}</span>{run.recovered && <div className="row-secondary align-right">Recovered</div>}</td>,
    investigation: run => <td key="investigation">{run.investigation === 'Completed' ? <>{run.findingCount > 0 ? <a href={evidenceHref(projectId, run.id, search)} aria-label={`View ${run.findingCount} finding${run.findingCount === 1 ? '' : 's'} for ${run.name}`}>{run.findingCount} finding{run.findingCount === 1 ? '' : 's'}</a> : <span>{run.findingCount == null ? 'Count unavailable' : '0 findings'}</span>}<div className="row-secondary">Completed</div></> : <span className={run.investigation === 'Failed' ? 'analysis-error' : ''}>{run.investigation === 'Failed' && <Icon name="error"/>}{run.investigation}</span>}</td>,
  }
  const headerTitle = (field, label) => field === 'recordedErrorCount' ? live ? ERROR_SPANS_TOOLTIP : 'Supplied error-operation groups, not individual ERROR spans' : `Sort by ${label.toLowerCase()}`
  return <><div className="table-region" role="region" aria-label="Recorded runs" tabIndex="0" aria-busy={busy}>
    <table className="runs-table"><caption className="sr-only">{live ? "Locally captured SDK runs. Error spans count every ERROR span, including parents that carry a child's error; capture completeness remains unknown." : "Recorded runs. Outcomes, capture completeness, recorded error counts and investigation states are independent."}</caption><colgroup>{columns.map(([field]) => <col key={field} className={columnClass[field]}/>)}</colgroup>
      <thead><tr>{columns.map(([field, label]) => <th key={field} scope="col" className={['durationMs', 'recordedErrorCount'].includes(field) ? 'numeric' : ''} aria-sort={query.sort === field ? query.direction === 'asc' ? 'ascending' : 'descending' : 'none'}><button className="sort-button" aria-label={`Sort by ${label.toLowerCase()}`} title={headerTitle(field, label)} onClick={() => onSort(field)}>{label}{query.sort === field && <span aria-hidden="true">{query.direction === 'asc' ? '↑' : '↓'}</span>}</button></th>)}</tr></thead>
      <tbody>{items.map(run => <tr key={run.id}>{columns.map(([field]) => cells[field](run))}</tr>)}</tbody>
    </table>{children}
  </div><div className="sr-only" aria-live="polite">{copyNotice}</div>{copyNotice.startsWith('Copy unavailable') && <p className="copy-failure" role="status">{copyNotice}</p>}</>
}
