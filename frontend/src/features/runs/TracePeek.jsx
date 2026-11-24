import { useEffect, useMemo, useRef, useState } from 'react'
import Icon from '../../components/Icon.jsx'
import Timestamp from '../../components/Timestamp.jsx'
import Tooltip from '../../components/ui/Tooltip.jsx'
import StatusLabel from '../../components/StatusLabel.jsx'
import { runsHref } from '../../app/routes.jsx'
import { exactDuration } from '../../app/format.js'
import { useTraceRead } from '../trace/useTraceRead.js'
import { buildIndex, durationText, operationLabel, statusText, typeLabel, types, visibleTree } from '../trace/treeModel.js'
import { buildTimingIndex } from '../trace/timelineModel.js'
import { traceStats } from '../trace/traceStats.js'
import { TreeGuides } from '../trace/ExecutionTree.jsx'
import DurationBar from '../trace/Waterfall.jsx'
import { executionModeLabel, firstErrorText } from './runColumns.js'
import '../trace/trace.css'
import './peek.css'

const everything = { search: '', type: '', status: '' }
const PEEK_ROW_HEIGHT = 40
export const PEEK_SHORTCUTS = 'J next trace · K previous trace · Esc close'

// Langfuse-style trace preview beside the list: read-only, opened from a row,
// J/K step through the visible rows, Esc closes. Every span links to the full
// trace page with that span selected; nothing here is editable.
export default function TracePeek({ repository, projectId, runId, listSearch, position, previous, next, close }) {
  const { data, busy, error, retry } = useTraceRead(repository, projectId, runId)
  const panel = useRef(null)
  const [notice, setNotice] = useState('')
  useEffect(() => { panel.current?.focus({ preventScroll: true }) }, [runId])
  const index = useMemo(() => data ? buildIndex(data.spans) : null, [data])
  const rows = useMemo(() => index ? visibleTree(index, new Set(data.spans.map(span => span.id)), everything).rows : [], [index, data])
  const stats = useMemo(() => data ? traceStats(data.spans, index) : null, [data, index])
  const timing = useMemo(() => data ? buildTimingIndex(data.spans, data.run.durationMs) : null, [data])
  const fullTrace = spanId => {
    const query = new URLSearchParams(listSearch)
    if (spanId) query.set('span', spanId)
    return runsHref(projectId, query.toString(), runId)
  }
  const run = data?.run
  async function copy() {
    try { await navigator.clipboard.writeText(runId); setNotice('Trace ID copied') } catch { setNotice(`Copy unavailable. Trace ID: ${runId}`) }
  }
  return <section id="trace-peek" className="trace-peek" role="region" aria-label="Trace preview" tabIndex="-1" ref={panel}>
    <header className="peek-header">
      <div className="peek-heading">
        <p className="section-label">Trace {position.index >= 0 ? <span className="peek-position">{position.index + 1} of {position.total}</span> : null}</p>
        <div className="peek-title"><Icon name="branch"/><h2 title={run?.name}>{run?.name || runId}</h2>{run && <StatusLabel state={run.outcome}/>}</div>
      </div>
      <div className="peek-toolbar">
        <Tooltip content={PEEK_SHORTCUTS}><button type="button" className="trace-icon-button" aria-label={`Keyboard shortcuts: ${PEEK_SHORTCUTS}`}><Icon name="info"/></button></Tooltip>
        <button type="button" className="trace-icon-button" aria-label="Previous trace" title="Previous trace (K)" disabled={!previous} onClick={previous || undefined}><Icon name="up"/></button>
        <button type="button" className="trace-icon-button" aria-label="Next trace" title="Next trace (J)" disabled={!next} onClick={next || undefined}><Icon name="down"/></button>
        <a className="trace-icon-button" href={fullTrace(null)} aria-label="Open full trace" title="Open full trace"><Icon name="external"/></a>
        <button type="button" className="trace-icon-button" aria-label="Close trace preview" title="Close (Esc)" onClick={close}><Icon name="close"/></button>
      </div>
    </header>
    <div className="peek-body">
      {!data ? <div className="peek-state" aria-busy={busy}>{busy ? <p role="status">Loading trace…</p> : <><p role="alert">{error}</p><button className="button small" onClick={retry}>Retry</button></>}</div> : <>
        <dl className="peek-facts">
          <div><dt>Started</dt><dd><Timestamp value={run.startedAt}/></dd></div>
          <div><dt>Duration</dt><dd className="tabular" title={exactDuration(run.durationMs)}>{durationText(run.durationMs)}</dd></div>
          <div><dt>Spans</dt><dd className="tabular">{stats.spans} · depth {stats.depth}</dd></div>
          <div><dt>Errors</dt><dd className={stats.errors ? 'error-text tabular' : 'tabular'}>{stats.errors}</dd></div>
          <div><dt>Trace ID</dt><dd><button type="button" className="trace-copy mono" onClick={copy} title={runId} aria-label="Copy trace ID">{runId.slice(0, 8)}…{runId.slice(-4)}<Icon name="copy"/></button></dd></div>
          {executionModeLabel(run.executionMode) && <div><dt>Mode</dt><dd>{executionModeLabel(run.executionMode)}</dd></div>}
        </dl>
        <ul className="peek-types" aria-label="Spans by type">{stats.byType.map(([type, count]) => <li key={type} data-type={type}><Icon name={type}/>{count} {typeLabel(type)}</li>)}</ul>
        {run.outcome === 'Failed' && run.firstError && <a className="peek-error" href={fullTrace(run.firstError.spanId)}><Icon name="error"/><span><strong>First recorded error</strong> {firstErrorText(run.firstError)}</span><Icon name="arrow"/></a>}
        <ol className="peek-tree" aria-label="Spans" style={{ '--trace-row-height': `${PEEK_ROW_HEIGHT}px` }}>
          {rows.map(row => {
            if (row.group) return <li key={row.id} className="peek-group">{row.name}</li>
            const type = types.includes(row.span.type) ? row.span.type : 'custom'
            return <li key={row.id}>
              <a className="peek-row" href={fullTrace(row.id)} title={`${row.span.name} · ${typeLabel(row.span.type)} · ${statusText(row.span.status)} · ${exactDuration(row.span.duration)}`}>
                <span className="trace-operation" data-type={type} data-error={row.span.status === 'ERROR' || undefined} style={{ '--span-depth': Math.min(row.depth, 8) }}>
                  {row.depth <= 8 && <TreeGuides row={{ ...row, expanded: row.childLoaded > 0 }} capped={row.depth >= 8}/>}
                  <span className="tree-disclosure"/>
                  <span className="status-dot" role="img" data-state={row.span.status ?? 'unknown'} aria-label={statusText(row.span.status)}/>
                  <Icon name={type}/>
                  <span className="trace-operation-name">{operationLabel(row.span)}</span>
                </span>
                <DurationBar span={row.span} timing={timing.byId.get(row.id)} extent={timing.extent}/>
              </a>
            </li>
          })}
        </ol>
      </>}
    </div>
    <span className="sr-only" aria-live="polite">{notice}</span>
  </section>
}
