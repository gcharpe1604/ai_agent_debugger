import { useState } from 'react'
import Icon from '../../components/Icon.jsx'
import { runsHref, evidenceHref } from '../../app/routes.jsx'
import { exactDuration, formatDuration } from '../../app/format.js'
import Timestamp from '../../components/Timestamp.jsx'
import { ERROR_SPANS_TOOLTIP, errorTone, formatCost, numericColumns, runColumns, unsortableColumns } from './runColumns.js'

const columnClass = { startedAt: 'col-start', name: 'col-run', traceId: 'col-trace-id', outcome: 'col-status', durationMs: 'col-duration', spanCount: 'col-count', recordedErrorCount: 'col-count', model: 'col-model', totalTokens: 'col-tokens', costUsd: 'col-cost', completeness: 'col-capture', investigation: 'col-investigation' }
const count = value => Number.isFinite(value) ? value.toLocaleString('en') : '—'

// One line per trace (Langfuse-style). hidden: optional columns the user turned
// off. onPeek: open the trace preview (row click or the eye button).
export default function RunTable({ items, projectId, search, query, onSort, busy, children, live = false, hidden = [], peek = null, onPeek }) {
  const [copyNotice, setCopyNotice] = useState('')
  const columns = runColumns(items).filter(([field]) => field === 'name' || !hidden.includes(field))
  async function copy(run) {
    try { await navigator.clipboard.writeText(run.traceId); setCopyNotice(`Trace ID copied for ${run.id}`) }
    catch { setCopyNotice(`Copy unavailable. Trace ID: ${run.traceId}`) }
  }
  const cells = {
    startedAt: run => <td key="startedAt" className="tabular"><Timestamp value={run.startedAt}/></td>,
    name: run => <td key="name"><div className="run-name-line">
      <a className="run-link" href={runsHref(projectId, search, run.id)} aria-label={`${run.name} ${run.id}`} title={`${run.name} · ${run.service}`}><span>{run.name}</span></a>
      {onPeek && <button type="button" className="row-peek row-hover-action" data-peek-id={run.id} aria-label={`Preview ${run.name} ${run.id}`} aria-pressed={peek === run.id} title="Preview trace" onClick={() => onPeek(run.id)}><Icon name="eye"/></button>}
    </div></td>,
    traceId: run => <td key="traceId"><div className="trace-id-cell"><span className="mono" title={run.traceId}>{run.traceId.slice(0, 8)}</span><button type="button" className="identity-copy row-hover-action" onClick={() => copy(run)} aria-label={`Copy trace ID for ${run.id}`} title="Copy trace ID"><Icon name="copy"/></button></div></td>,
    outcome: run => <td key="outcome"><span className="run-status" data-state={run.outcome}><span className="status-dot" aria-hidden="true"/>{run.outcome}</span></td>,
    durationMs: run => <td key="durationMs" className="numeric" title={run.durationMs == null ? undefined : exactDuration(run.durationMs)}>{run.durationMs == null ? 'Unknown' : formatDuration(run.durationMs)}</td>,
    spanCount: run => <td key="spanCount" className="numeric">{count(run.spanCount)}</td>,
    recordedErrorCount: run => <td key="recordedErrorCount" className="numeric" title={run.recovered ? 'Recovered after a retry' : undefined}><span className="error-count" data-tone={errorTone(run)}>{count(run.recordedErrorCount)}</span>{run.recovered && <span className="sr-only"> Recovered</span>}</td>,
    model: run => <td key="model" className="cell-clip">{run.model ?? '—'}</td>,
    totalTokens: run => <td key="totalTokens" className="numeric">{count(run.totalTokens)}</td>,
    costUsd: run => <td key="costUsd" className="numeric">{formatCost(run.costUsd)}</td>,
    completeness: run => <td key="completeness"><span className="run-status" data-state={run.completeness}><span className="status-dot" aria-hidden="true"/>{run.completeness}</span></td>,
    investigation: run => <td key="investigation" className="cell-clip">{run.investigation === 'Completed' ? run.findingCount > 0 ? <a href={evidenceHref(projectId, run.id, search)} aria-label={`View ${run.findingCount} finding${run.findingCount === 1 ? '' : 's'} for ${run.name}`}>{run.findingCount} finding{run.findingCount === 1 ? '' : 's'}</a> : <span>{run.findingCount == null ? 'Count unavailable' : '0 findings'}</span> : <span className={run.investigation === 'Failed' ? 'analysis-error' : ''}>{run.investigation === 'Failed' && <Icon name="error"/>}{run.investigation}</span>}</td>,
  }
  const headerTitle = (field, label) => field === 'recordedErrorCount' ? live ? ERROR_SPANS_TOOLTIP : 'Supplied error-operation groups, not individual ERROR spans' : `Sort by ${label.toLowerCase()}`
  return <><div className="table-region" role="region" aria-label="Recorded traces" tabIndex="0" aria-busy={busy}>
    <table className="runs-table"><caption className="sr-only">{live ? "Captured SDK traces. Errors count every ERROR span, including parents that carry a child's error." : "Recorded traces. Outcomes, capture completeness, recorded error counts and investigation states are independent."}</caption><colgroup>{columns.map(([field]) => <col key={field} className={columnClass[field]}/>)}</colgroup>
      <thead><tr>{columns.map(([field, label]) => <th key={field} scope="col" className={numericColumns.includes(field) ? 'numeric' : ''} aria-sort={unsortableColumns.includes(field) ? undefined : query.sort === field ? query.direction === 'asc' ? 'ascending' : 'descending' : 'none'}>{unsortableColumns.includes(field) ? label : <button className="sort-button" aria-label={`Sort by ${label.toLowerCase()}`} title={headerTitle(field, label)} onClick={() => onSort(field)}>{label}{query.sort === field && <span aria-hidden="true">{query.direction === 'asc' ? '↑' : '↓'}</span>}</button>}</th>)}</tr></thead>
      {/* A click on the row's empty space previews it; links and buttons keep their own action. */}
      <tbody>{items.map(run => <tr key={run.id} data-peekable={onPeek ? 'true' : undefined} data-peeked={peek === run.id || undefined} onClick={onPeek ? event => { if (!event.target.closest('a, button, input, select, summary, label')) onPeek(run.id) } : undefined}>{columns.map(([field]) => cells[field](run))}</tr>)}</tbody>
    </table>{children}
  </div><div className="sr-only" aria-live="polite">{copyNotice}</div>{copyNotice.startsWith('Copy unavailable') && <p className="copy-failure" role="status">{copyNotice}</p>}</>
}
