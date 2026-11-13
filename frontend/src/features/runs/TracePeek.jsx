import { useEffect, useMemo, useRef, useState } from 'react'
import Icon from '../../components/Icon.jsx'
import { runsHref } from '../../app/routes.jsx'
import { exactDuration } from '../../app/format.js'
import { useTraceRead } from '../trace/useTraceRead.js'
import { buildIndex, durationText, executionPath, operationLabel, statusText, typeLabel, types, visibleTree } from '../trace/treeModel.js'
import { traceStats } from '../trace/traceStats.js'
import { TreeGuides } from '../trace/ExecutionTree.jsx'
import ExecutionPath from '../trace/ExecutionPath.jsx'
import InspectorResize from '../trace/InspectorResize.jsx'
import { executionModeLabel, firstErrorText } from './runColumns.js'
import '../trace/trace.css'
import '../trace/timeline.css'
import './peek.css'

const everything = { search: '', type: '', status: '' }
const PEEK_ROW_HEIGHT = 30

// Langfuse-style trace preview over the list: read-only, opened from a row,
// J/K step through the visible rows, Esc closes. Every span links to the full
// trace page with that span selected; nothing here is editable.
export default function TracePeek({ repository, projectId, runId, listSearch, position, previous, next, close, width, minWidth, maxWidth, resize, resetWidth }) {
  const { data, busy, error, retry } = useTraceRead(repository, projectId, runId)
  const panel = useRef(null)
  const [notice, setNotice] = useState('')
  useEffect(() => { panel.current?.focus({ preventScroll: true }) }, [runId])
  const index = useMemo(() => data ? buildIndex(data.spans) : null, [data])
  const rows = useMemo(() => index ? visibleTree(index, new Set(data.spans.map(span => span.id)), everything).rows : [], [index, data])
  const stats = useMemo(() => data ? traceStats(data.spans, index) : null, [data, index])
  const path = useMemo(() => index ? executionPath(index) : { steps: [], hidden: 0 }, [index])
  const fullTrace = spanId => {
    const query = new URLSearchParams(listSearch)
    if (spanId) query.set('span', spanId)
    return runsHref(projectId, query.toString(), runId)
  }
  const run = data?.run
  const total = Number.isFinite(run?.durationMs) && run.durationMs > 0 ? run.durationMs : 0
  const share = span => total && Number.isFinite(span.duration) && span.duration > 0 ? Math.min(1, span.duration / total) : 0
  async function copy() {
    try { await navigator.clipboard.writeText(runId); setNotice('Trace ID copied') } catch { setNotice(`Copy unavailable. Trace ID: ${runId}`) }
  }
  return <div className="peek-layer" style={{ '--peek-width': `${width}px` }}>
    <InspectorResize width={width} min={minWidth} max={maxWidth} resize={resize} reset={resetWidth} label="Resize trace preview"/>
    <section className="trace-peek" role="region" aria-label="Trace preview" tabIndex="-1" ref={panel}>
      <header className="peek-header">
        <div className="peek-heading">
          <p className="section-label">Trace {position.index >= 0 ? <span className="peek-position">{position.index + 1} of {position.total}</span> : null}</p>
          <div className="peek-title"><Icon name="branch"/><h2 title={run?.name}>{run?.name || runId}</h2>{run && <span className="badge" data-state={run.outcome}>{run.outcome}</span>}</div>
        </div>
        <div className="peek-toolbar">
          <button type="button" className="trace-icon-button" aria-label="Previous trace" title="Previous trace (K)" disabled={!previous} onClick={previous || undefined}><Icon name="up"/></button>
          <button type="button" className="trace-icon-button" aria-label="Next trace" title="Next trace (J)" disabled={!next} onClick={next || undefined}><Icon name="down"/></button>
          <a className="trace-icon-button" href={fullTrace(null)} aria-label="Open full trace" title="Open full trace"><Icon name="external"/></a>
          <button type="button" className="trace-icon-button" aria-label="Close trace preview" title="Close (Esc)" onClick={close}><Icon name="close"/></button>
        </div>
      </header>
      <div className="peek-body">
        {!data ? <div className="peek-state" aria-busy={busy}>{busy ? <p role="status">Loading trace…</p> : <><p role="alert">{error}</p><button className="button small" onClick={retry}>Retry</button></>}</div> : <>
          <dl className="peek-facts">
            <div><dt>Duration</dt><dd className="mono" title={exactDuration(run.durationMs)}>{durationText(run.durationMs)}</dd></div>
            <div><dt>Started</dt><dd>{run.startedAt.replace('T', ' ').replace(/(\.\d+)?Z$/, ' UTC')}</dd></div>
            <div><dt>Trace ID</dt><dd><button type="button" className="trace-copy mono" onClick={copy} title={runId} aria-label="Copy trace ID">{runId.slice(0, 8)}…{runId.slice(-4)}<Icon name="copy"/></button></dd></div>
            {executionModeLabel(run.executionMode) && <div><dt>Mode</dt><dd>{executionModeLabel(run.executionMode)}</dd></div>}
            <div><dt>Spans</dt><dd>{stats.spans} received · depth {stats.depth}</dd></div>
            <div><dt>Error spans</dt><dd className={stats.errors ? 'error-text' : undefined}>{stats.errors}</dd></div>
          </dl>
          <ul className="peek-types" aria-label="Spans by type">{stats.byType.map(([type, count]) => <li key={type} data-type={type}><Icon name={type}/>{count} {typeLabel(type)}</li>)}</ul>
          {run.outcome === 'Failed' && run.firstError && <a className="peek-error" href={fullTrace(run.firstError.spanId)}><Icon name="error"/><span><strong>First recorded error</strong> {firstErrorText(run.firstError)}</span><Icon name="arrow"/></a>}
          <ExecutionPath path={path} selected={null} select={id => { window.location.hash = fullTrace(id) }}/>
          <ol className="peek-tree" aria-label="Spans" style={{ '--trace-row-height': `${PEEK_ROW_HEIGHT}px` }}>
            {rows.map(row => {
              if (row.group) return <li key={row.id} className="peek-group">{row.name}</li>
              const type = types.includes(row.span.type) ? row.span.type : 'custom'
              return <li key={row.id}>
                <a className="peek-row" href={fullTrace(row.id)} title={`${row.span.name} · ${typeLabel(row.span.type)} · ${statusText(row.span.status)} · ${exactDuration(row.span.duration)}`}>
                  <span className="trace-operation" data-type={type} data-error={row.span.status === 'ERROR' || undefined} style={{ '--span-depth': Math.min(row.depth, 8) }}>
                    {row.depth > 0 && row.depth <= 8 && <TreeGuides depth={row.depth} guides={row.guides} last={row.last} leaf={!row.childLoaded}/>}
                    <span className="tree-disclosure"/>
                    <Icon name={type}/>
                    <span className="trace-operation-name">{operationLabel(row.span)}</span>
                  </span>
                  <span className="status-dot" role="img" data-state={row.span.status} aria-label={statusText(row.span.status)}/>
                  <span className="mono latency-bar" style={{ '--share': share(row.span) }}>{durationText(row.span.duration)}</span>
                </a>
              </li>
            })}
          </ol>
        </>}
      </div>
      <footer className="peek-footer"><Icon name="keyboard"/><span><kbd>J</kbd> next · <kbd>K</kbd> previous · <kbd>Esc</kbd> close</span></footer>
      <span className="sr-only" aria-live="polite">{notice}</span>
    </section>
  </div>
}
