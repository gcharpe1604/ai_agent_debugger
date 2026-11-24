import { useCallback, useEffect, useLayoutEffect, useMemo, useReducer, useRef } from 'react'
import { parseRoute } from '../../app/routes.jsx'
import { useSessionValue } from '../../app/sessionMemory.js'
import { ROW_HEIGHT, ancestors, buildIndex, restoreAnchor, visibleTree, knownCount, operationLabel } from './treeModel.js'
import { autoSelectedSpan, initialTraceState, traceReducer } from './traceState.js'
import { useElementSize } from './useElementSize.js'
import ExecutionTree from './ExecutionTree.jsx'
import TraceToolbar from './TraceToolbar.jsx'
import SpanInspector from './SpanInspector.jsx'
import SplitDivider from '../../components/ui/SplitDivider.jsx'
import { Popover, PopoverContent, PopoverTrigger } from '../../components/ui/Popover.jsx'
import { buildTimingIndex, normalizeWindow } from './timelineModel.js'
import TimelineControls from './TimelineControls.jsx'
import { TimelineAxis } from './TimelineTrack.jsx'
import { INSPECTOR_MIN_WIDTH, TREE_MIN_WIDTH, treeColumns, treeGridTemplate } from './treeColumns.js'
import './timeline.css'

const DIVIDER = 1
const columnLabels = { name: 'Name', id: 'Span ID', start: 'Start', type: 'Type', duration: 'Duration' }

// Tree (left) and span inspector (right) side by side with a draggable divider.
// The inspector width is kept for this browser session only. When the two
// minimum widths do not fit, the inspector replaces the tree (single pane).
export default function TraceWorkspace({ data, route, repository, cache, loadMore, busy, error, retryRead, receivedOnly = false }) {
  const scope = `${route.projectId}/${route.runId}`
  const [widthPreference, setWidthPreference] = useSessionValue('trace.inspector.width', null)
  const index = useMemo(() => buildIndex(data.spans), [data.spans])
  const timing = useMemo(() => buildTimingIndex(data.spans, data.run.durationMs), [data.spans, data.run.durationMs])
  const total = knownCount(data.knownCount)
  const [ui, dispatch] = useReducer(traceReducer, null, () => {
    const cached = cache.get(scope)
    const state = initialTraceState(route.search, cached)
    const firstError = autoSelectedSpan(route.search, cached, data.run)
    if (firstError && index.byId.has(firstError)) Object.assign(state, { selected: firstError, active: firstError, open: new URLSearchParams(route.search).get('panel') !== 'closed' })
    if (state.selected && state.selected !== cached?.selected) {
      const path = ancestors(index, state.selected).map(span => span.id)
      state.collapsed = state.collapsed.filter(id => !path.includes(id))
      state.anchor = { id: state.selected, offset: 0 }
    }
    return state
  })
  const patch = useCallback(value => dispatch({ type: 'patch', value }), [dispatch])
  const root = useRef(null), treeRef = useRef(null), inspectorRef = useRef(null)
  const returnFocus = useRef(false)
  const size = useElementSize(root)
  const single = size.width < TREE_MIN_WIDTH + INSPECTOR_MIN_WIDTH + DIVIDER
  const maxWidth = Math.max(INSPECTOR_MIN_WIDTH, Math.floor(size.width - TREE_MIN_WIDTH - DIVIDER))
  const width = single ? size.width : Math.min(maxWidth, Math.max(INSPECTOR_MIN_WIDTH, widthPreference ?? Math.min(560, Math.round(size.width * 0.42))))
  const expanded = useMemo(() => { const collapsed = new Set(ui.collapsed); return new Set(data.spans.filter(span => !collapsed.has(span.id)).map(span => span.id)) }, [data.spans, ui.collapsed])
  const view = useMemo(() => visibleTree(index, expanded, { search: ui.search, type: ui.type, status: ui.status }), [index, expanded, ui.search, ui.type, ui.status])
  const contextCount = view.rows.filter(row => row.context).length
  const loaded = data.spans.length.toLocaleString('en')
  const span = index.byId.get(ui.selected)
  const open = !!(ui.open && span)
  const path = useMemo(() => span ? ancestors(index, span.id) : [], [index, span])
  const pathIds = useMemo(() => new Set(path.map(parent => parent.id)), [path])
  const explorerSize = useElementSize(treeRef)
  // Columns follow the tree pane's own width, so the split never hides Duration.
  const treeWidth = open && !single ? Math.min(explorerSize.width, size.width - width - DIVIDER) : explorerSize.width
  const columns = treeColumns(treeWidth, { showIds: !!ui.showIds })
  const top = ui.anchor ? restoreAnchor(view.rows, ui.anchor, index) : ui.scrollTop
  const selectedPosition = view.rows.findIndex(row => row.id === ui.selected)
  const selectionHidden = !!span && (selectedPosition < 0 || selectedPosition * ROW_HEIGHT < top || (selectedPosition + 1) * ROW_HEIGHT > top + explorerSize.height)
  const timeWindow = ui.timeWindow ? normalizeWindow(ui.timeWindow, timing.navigationExtent) : { start: timing.extent.start, end: timing.extent.end }
  useEffect(() => { cache.set(scope, { ...ui, limit: data.spans.length }) }, [cache, scope, ui, data.spans.length])
  const writeUrl = useCallback(values => {
    // Several controls may update during one click (for example restore + dismiss).
    // Merge into the current URL so a later dismissal cannot overwrite that query.
    const p = new URLSearchParams(parseRoute(window.location.hash).search)
    for (const [key, value] of Object.entries(values)) { if (value) p.set(key, value); else p.delete(key) }
    window.history.replaceState(null, '', `#/projects/${route.projectId}/runs/${route.runId}${p.size ? '?' + p : ''}`)
    window.dispatchEvent(new HashChangeEvent('hashchange'))
  }, [route.projectId, route.runId])
  const close = useCallback(() => {
    returnFocus.current = single || inspectorRef.current?.contains(document.activeElement)
    patch({ open: false }); writeUrl({ panel: 'closed' })
  }, [patch, writeUrl, single])
  useLayoutEffect(() => {
    // The narrow explorer becomes focusable only after the inspector is removed.
    if (!ui.open && returnFocus.current) { treeRef.current?.focus({ preventScroll: true }); returnFocus.current = false }
  }, [ui.open])
  useEffect(() => { if (single && ui.open && span) inspectorRef.current?.focus({ preventScroll: true }) }, [single, ui.open, span])
  function filter(value) {
    dispatch({ type: 'filter', value })
    const next = { ...ui, ...value }
    writeUrl({ spanSearch: next.search, spanType: next.type, spanStatus: next.status })
  }
  function select(id) {
    patch({ selected: id, active: id, open: true, notice: '' })
    writeUrl({ span: id, panel: '' })
  }
  function jump(id) {
    if (!index.byId.has(id)) { patch({ pending: id, notice: `Span ${id} is not in loaded structure.${total === null ? ' Total structure size is unknown; lookup covers loaded spans only.' : data.spans.length < total ? ' Load more local spans to continue.' : ' It is unavailable in the received trace.'}` }); return }
    const parents = ancestors(index, id).map(parent => parent.id)
    const currentVisible = view.rows.some(row => row.id === id)
    const reveal = !currentVisible && view.filtered ? { search: ui.search, type: ui.type, status: ui.status } : ui.reveal
    patch({ selected: id, active: id, open: true, collapsed: ui.collapsed.filter(value => !parents.includes(value)), anchor: { id, offset: 0 }, reveal, ...(reveal ? { search: '', type: '', status: '' } : {}), pending: null, notice: '' })
    writeUrl({ span: id, panel: '', ...(reveal ? { spanSearch: '', spanType: '', spanStatus: '' } : {}) })
  }
  function resize(value) { setWidthPreference(Math.max(INSPECTOR_MIN_WIDTH, Math.min(maxWidth, Math.round(value)))) }
  function switchView(next) { patch({ view: next }); writeUrl({ view: next }) }
  function timeWindowChange(next) { patch({ timeWindow: next }); writeUrl({ from: next ? String(next.start) : '', to: next ? String(next.end) : '' }) }
  function matchingOperation(direction) {
    const position = view.matches.indexOf(ui.selected)
    const next = position < 0 ? (direction > 0 ? 0 : view.matches.length - 1) : (position + direction + view.matches.length) % view.matches.length
    jump(view.matches[next])
  }
  function toggleBranch(id) {
    if (!(index.children.get(id)?.length)) {
      const operation = index.byId.get(id)
      patch({ notice: `Children are not loaded for ${operation.name}. ${knownCount(operation.childCount) === null ? 'Child total is unknown.' : `${operation.childCount} children recorded.`} Additional child reads are not connected.` })
      return
    }
    dispatch({ type: 'toggle', id })
  }
  // "Selected path" lists the selection's ancestors; "Focus inspector" moves focus there.
  const selection = span && <div className="segmented selection-tools" role="group" aria-label="Selected span">
    <Popover><PopoverTrigger><button type="button" aria-label={`Selected path: ${span.name}`}>Selected path</button></PopoverTrigger><PopoverContent className="trace-popover path-popover" align="end">
      <ol aria-label="Ancestors of the selected span">{[...path, span].map(parent => <li key={parent.id}><button type="button" className="text-button" aria-current={parent.id === span.id ? 'true' : undefined} onClick={() => jump(parent.id)} title={`${parent.name} · ${parent.id}`}>{operationLabel(parent)}</button></li>)}</ol>
    </PopoverContent></Popover>
    {open && <button type="button" onClick={() => inspectorRef.current?.focus({ preventScroll: true })}>Focus inspector</button>}
  </div>
  return <div className="trace-workbench" data-mode={open ? single ? 'single' : 'split' : 'explore'} data-view={ui.view} data-open={open} ref={root} style={{ '--inspector-width': `${width}px`, '--tree-gutter': `${explorerSize.gutter || 0}px`, '--trace-row-height': `${ROW_HEIGHT}px`, '--tree-grid': treeGridTemplate(columns, treeWidth) }} onKeyDown={event => {
    if (event.defaultPrevented) return
    if (event.key === 'Escape' && ui.open) { event.preventDefault(); close(); treeRef.current?.focus({ preventScroll: true }) }
    if (event.key === 'F6' && open) { event.preventDefault(); if (single) close(); else if (inspectorRef.current?.contains(document.activeElement)) treeRef.current.focus({ preventScroll: true }); else inspectorRef.current.focus({ preventScroll: true }) }
  }}>
    <div className="trace-explorer">
      <TraceToolbar ui={ui} filter={filter} patch={patch} index={index} jump={jump} wide={ui.view !== 'timeline' && treeWidth >= 840} switchView={switchView} timing={timing} timeWindowChange={timeWindowChange}>{selection}</TraceToolbar>
      {(!receivedOnly || view.filtered || selectionHidden || ui.reveal || (ui.selected && !span)) && <div className="trace-context">
        {!receivedOnly && <span className="trace-loaded">{total === null ? `${loaded} loaded` : `${loaded} / ${total.toLocaleString('en')} loaded`}</span>}
        {view.filtered && <span>{view.matches.length} {view.matches.length === 1 ? 'match' : 'matches'}{contextCount > 0 ? ` · ${contextCount} ${contextCount === 1 ? 'ancestor' : 'ancestors'}` : ''}</span>}
        {selectionHidden && <button className="text-button" onClick={() => jump(ui.selected)}>Reveal selected span</button>}
        {ui.selected && !span && <span>Selected span is not loaded.</span>}
        {view.filtered && view.matches.length > 0 && <div className="trace-match-navigation"><button className="trace-icon-button" aria-label="Previous matching span" onClick={() => matchingOperation(-1)}>↑</button><button className="trace-icon-button" aria-label="Next matching span" onClick={() => matchingOperation(1)}>↓</button></div>}
        {ui.reveal && <><span>Filters temporarily relaxed</span><button className="text-button" onClick={() => { const previous = ui.reveal; patch({ ...previous, reveal: null, anchor: null, scrollTop: 0 }); writeUrl({ spanSearch: previous.search, spanType: previous.type, spanStatus: previous.status }) }}>Restore filters</button></>}
      </div>}
      {ui.notice && <div className="trace-notice" role="status">{ui.notice}{ui.pending && index.byId.has(ui.pending) && <button className="text-button" onClick={() => jump(ui.pending)}>Open loaded requested span</button>}</div>}
      {error && <div className="trace-notice error-text" role="alert">{error} · Previously loaded structure remains visible.<button className="text-button" onClick={retryRead}>Retry structure read</button></div>}
      {ui.view === 'timeline' && <TimelineControls timing={timing} window={timeWindow} selected={timing.byId.get(ui.selected)} change={timeWindowChange}/>}
      {ui.view === 'timeline' ? <TimelineAxis window={timeWindow} available={timing.extent.available}/> : <div className="trace-columns trace-grid">{columns.map(column => <span key={column} className={`trace-${column}-cell`}>{columnLabels[column]}</span>)}</div>}
      <ExecutionTree index={index} rows={view.rows} ui={{ ...ui, scrollTop: top }} treeRef={treeRef} select={select} patch={patch} toggle={toggleBranch} filtered={view.filtered} columns={columns} pathIds={pathIds} timing={timing} timeWindow={timeWindow} receivedOnly={receivedOnly}/>
      <footer className="trace-footer"><span>{view.rows.filter(row => row.span).length.toLocaleString('en')} operations in hierarchy view{busy ? ' · Loading structure…' : ''}</span>{total !== null && data.spans.length < total && <button className="text-button" disabled={busy} onClick={() => loadMore(Math.min(total, data.spans.length + 420))}>Load {Math.min(420, total - data.spans.length)} more local spans</button>}</footer>
    </div>
    {open && !single && <SplitDivider value={width} min={INSPECTOR_MIN_WIDTH} max={maxWidth} onChange={resize} onReset={() => setWidthPreference(null)} label="Resize span inspector" controls="span-inspector"/>}
    {open && <SpanInspector repository={repository} projectId={route.projectId} runId={route.runId} span={span} path={path} ui={ui} patch={patch} dispatch={dispatch} single={single} close={close} back={() => single ? close() : treeRef.current?.focus({ preventScroll: true })} jump={jump} inspectorRef={inspectorRef}/>}
  </div>
}
