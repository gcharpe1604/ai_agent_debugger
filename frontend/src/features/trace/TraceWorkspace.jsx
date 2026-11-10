import { useCallback, useEffect, useLayoutEffect, useMemo, useReducer, useRef } from 'react'
import { usePreference } from '../../app/preferences.js'
import { parseRoute } from '../../app/routes.jsx'
import { ROW_HEIGHT, ancestors, buildIndex, restoreAnchor, visibleTree, knownCount, operationLabel } from './treeModel.js'
import { autoSelectedSpan, initialTraceState, traceReducer } from './traceState.js'
import { useElementSize } from './useElementSize.js'
import ExecutionTree from './ExecutionTree.jsx'
import TraceToolbar from './TraceToolbar.jsx'
import SpanInspector from './SpanInspector.jsx'
import InspectorResize from './InspectorResize.jsx'
import { buildTimingIndex, normalizeWindow } from './timelineModel.js'
import TimelineControls from './TimelineControls.jsx'
import { TimelineAxis } from './TimelineTrack.jsx'
import './timeline.css'

const widthValues = ['auto', ...Array.from({ length: 161 }, (_, index) => String(480 + index))]
export default function TraceWorkspace({ data, route, repository, cache, loadMore, busy, error, retryRead, receivedOnly = false }) {
  const scope = `${route.projectId}/${route.runId}`
  const [modePreference, setModePreference] = usePreference('inspector.mode', ['overlay', 'pinned'], 'overlay')
  const [widthPreference, setWidthPreference] = usePreference('inspector.width', widthValues, 'auto')
  const index = useMemo(() => buildIndex(data.spans), [data.spans])
  const timing = useMemo(() => buildTimingIndex(data.spans, data.run.durationMs), [data.spans, data.run.durationMs])
  const total = knownCount(data.knownCount)
  const [ui, dispatch] = useReducer(traceReducer, null, () => {
    const cached = cache.get(scope)
    const state = initialTraceState(route.search, cached, modePreference)
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
  const single = size.width < 928
  const effectiveMode = single ? 'single' : ui.mode
  // Reserve room for execution columns and, in pinned mode, the resize handle.
  const executionReserve = ui.mode === 'pinned' ? 530 : 402
  const maxWidth = Math.max(480, Math.floor(Math.min(640, size.width - executionReserve)))
  const width = single ? size.width : Math.min(maxWidth, Math.max(480, widthPreference === 'auto' ? Math.min(600, size.width / 2) : Number(widthPreference)))
  const expanded = useMemo(() => { const collapsed = new Set(ui.collapsed); return new Set(data.spans.filter(span => !collapsed.has(span.id)).map(span => span.id)) }, [data.spans, ui.collapsed])
  const view = useMemo(() => visibleTree(index, expanded, { search: ui.search, type: ui.type, status: ui.status }), [index, expanded, ui.search, ui.type, ui.status])
  const contextCount = view.rows.filter(row => row.context).length
  const loaded = data.spans.length.toLocaleString('en')
  const span = index.byId.get(ui.selected)
  const explorerSize = useElementSize(treeRef)
  const top = ui.anchor ? restoreAnchor(view.rows, ui.anchor, index) : ui.scrollTop
  const selectedPosition = view.rows.findIndex(row => row.id === ui.selected)
  const selectionHidden = !!span && (selectedPosition < 0 || selectedPosition * ROW_HEIGHT < top || (selectedPosition + 1) * ROW_HEIGHT > top + explorerSize.height)
  const showIds = ui.view !== 'timeline' && !!ui.showIds && explorerSize.width >= 840
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
  useEffect(() => {
    if (!ui.open || effectiveMode !== 'overlay') return
    function outside(event) {
      // React may replace the clicked payload control before this event bubbles.
      // Its original event path still identifies an inspector-origin activation.
      if (event.composedPath().includes(inspectorRef.current) || inspectorRef.current?.contains(event.target)) return
      if (event.target.closest('[data-inspector-trigger]')) return
      if (event.target.closest('a[href], #project')) return
      if (event.target.closest('[data-span-id]') && !event.target.closest('[data-disclosure]')) return
      close()
    }
    // Dismiss after the activated control's click, before removing adjacent actions.
    document.addEventListener('click', outside)
    return () => document.removeEventListener('click', outside)
  }, [ui.open, effectiveMode, close])
  useEffect(() => { if (single && ui.open && span) inspectorRef.current?.focus({ preventScroll: true }) }, [single, ui.open, span])
  function filter(value) {
    dispatch({ type: 'filter', value })
    const next = { ...ui, ...value }
    writeUrl({ spanSearch: next.search, spanType: next.type, spanStatus: next.status })
  }
  function select(id) {
    patch({ selected: id, active: id, open: true, notice: '' })
    writeUrl({ span: id, panel: ui.mode })
  }
  function jump(id) {
    if (!index.byId.has(id)) { patch({ pending: id, notice: `Span ${id} is not in loaded structure.${total === null ? ' Total structure size is unknown; lookup covers loaded spans only.' : data.spans.length < total ? ' Load more local spans to continue.' : ' It is unavailable in the received trace.'}` }); return }
    const path = ancestors(index, id).map(parent => parent.id)
    const currentVisible = view.rows.some(row => row.id === id)
    const reveal = !currentVisible && view.filtered ? { search: ui.search, type: ui.type, status: ui.status } : ui.reveal
    patch({ selected: id, active: id, open: true, collapsed: ui.collapsed.filter(value => !path.includes(value)), anchor: { id, offset: 0 }, reveal, ...(reveal ? { search: '', type: '', status: '' } : {}), pending: null, notice: '' })
    writeUrl({ span: id, panel: ui.mode, ...(reveal ? { spanSearch: '', spanType: '', spanStatus: '' } : {}) })
  }
  function pin() {
    const mode = ui.mode === 'pinned' ? 'overlay' : 'pinned'
    setModePreference(mode); patch({ mode }); writeUrl({ panel: mode })
  }
  function resize(value) { setWidthPreference(String(Math.max(480, Math.min(maxWidth, Math.round(value))))) }
  function switchView(view) { patch({ view }); writeUrl({ view }) }
  function timeWindowChange(timeWindow) { patch({ timeWindow }); writeUrl({ from: timeWindow ? String(timeWindow.start) : '', to: timeWindow ? String(timeWindow.end) : '' }) }
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
  function exposeKeyboardFocus(event) {
    // Compact chrome normally fits to the overlay's visible left. If a focus
    // target/popover is still occluded, expose it by dismissing, never trap it.
    const target = event.target
    if (!ui.open || effectiveMode !== 'overlay' || target === treeRef.current || !treeRef.current?.parentElement.contains(target)) return
    const panel = inspectorRef.current?.getBoundingClientRect(), rect = target.getBoundingClientRect()
    if (panel && rect.width && rect.height && rect.right > panel.left && rect.left < panel.right && rect.bottom > panel.top && rect.top < panel.bottom) close()
  }
  return <div className="trace-workbench" data-mode={ui.open && span ? effectiveMode : 'explore'} data-view={ui.view} data-single={single} data-open={!!(ui.open && span)} data-show-ids={showIds} ref={root} style={{ '--inspector-width': `${width}px`, '--tree-gutter': `${explorerSize.gutter || 0}px`, '--trace-row-height': `${ROW_HEIGHT}px` }} onFocusCapture={exposeKeyboardFocus} onKeyDown={event => {
    if (event.key === 'Escape' && !document.querySelector('.trace-menu[open]') && ui.open && effectiveMode !== 'pinned') { event.preventDefault(); close(); treeRef.current?.focus({ preventScroll: true }) }
    if (event.key === 'F6' && ui.open && span) { event.preventDefault(); if (single) close(); else if (inspectorRef.current?.contains(document.activeElement)) treeRef.current.focus({ preventScroll: true }); else inspectorRef.current.focus({ preventScroll: true }) }
  }}>
    <div className="trace-explorer">
      <TraceToolbar ui={ui} filter={filter} patch={patch} index={index} jump={jump} projectId={route.projectId} search={route.search} wide={ui.view !== 'timeline' && explorerSize.width >= 840} switchView={switchView} timing={timing} timeWindowChange={timeWindowChange}/>
      {(!receivedOnly || view.filtered || ui.selected || ui.reveal) && <div className="trace-context">
        {!receivedOnly && <span className="trace-loaded">{total === null ? `${loaded} loaded` : `${loaded} / ${total.toLocaleString('en')} loaded`}</span>}
        {view.filtered && <span>{view.matches.length} {view.matches.length === 1 ? 'match' : 'matches'}{contextCount > 0 ? ` · ${contextCount} ${contextCount === 1 ? 'ancestor' : 'ancestors'}` : ''}</span>}
        {span && <details className="trace-menu trace-path"><summary aria-label={`Selected operation path and full name: ${span.name}`}>Selected path</summary><div className="trace-popover">{[...ancestors(index, span.id), span].map(parent => <button key={parent.id} data-inspector-trigger className="text-button" onClick={() => jump(parent.id)} title={`${parent.name} · ${parent.id}`}>{operationLabel(parent)}</button>)}</div></details>}
        {selectionHidden && <button className="text-button" data-inspector-trigger onClick={() => jump(ui.selected)}>Reveal selected span</button>}
        {ui.selected && !span && <span>Selected span is not loaded.</span>}
        {ui.open && span && <button className="text-button" data-inspector-trigger onClick={() => inspectorRef.current?.focus({ preventScroll: true })}>Focus inspector</button>}
        {view.filtered && view.matches.length > 0 && <div className="trace-match-navigation" data-inspector-trigger><button className="trace-icon-button" aria-label="Previous matching span" onClick={() => matchingOperation(-1)}>↑</button><button className="trace-icon-button" aria-label="Next matching span" onClick={() => matchingOperation(1)}>↓</button></div>}
        {ui.reveal && <><span>Filters temporarily relaxed</span><button className="text-button" onClick={() => { const previous = ui.reveal; patch({ ...previous, reveal: null, anchor: null, scrollTop: 0 }); writeUrl({ spanSearch: previous.search, spanType: previous.type, spanStatus: previous.status }) }}>Restore filters</button></>}
      </div>}
      {ui.notice && <div className="trace-notice" role="status">{ui.notice}{ui.pending && index.byId.has(ui.pending) && <button className="text-button" onClick={() => jump(ui.pending)}>Open loaded requested span</button>}</div>}
      {error && <div className="trace-notice error-text" role="alert">{error} · Previously loaded structure remains visible.<button className="text-button" onClick={retryRead}>Retry structure read</button></div>}
      {ui.view === 'timeline' && <TimelineControls timing={timing} window={timeWindow} selected={timing.byId.get(ui.selected)} change={timeWindowChange}/>}
      {ui.view === 'timeline' ? <TimelineAxis window={timeWindow} available={timing.extent.available}/> : <div className="trace-columns trace-grid"><span>Operation</span>{showIds && <span className="trace-id-cell">Span ID</span>}<span className="trace-start-cell">Start offset</span><span className="trace-type-cell">Type</span><span>Status</span><span className="trace-duration">Duration</span></div>}
      <ExecutionTree index={index} rows={view.rows} ui={{ ...ui, scrollTop: top }} treeRef={treeRef} select={select} patch={patch} toggle={toggleBranch} filtered={view.filtered} showIds={showIds} timing={timing} timeWindow={timeWindow} receivedOnly={receivedOnly}/>
      <footer className="trace-footer"><span>{view.rows.filter(row => row.span).length.toLocaleString('en')} operations in hierarchy view{busy ? ' · Loading structure…' : ''}</span>{total !== null && data.spans.length < total && <button className="text-button" disabled={busy} onClick={() => loadMore(Math.min(total, data.spans.length + 420))}>Load {Math.min(420, total - data.spans.length)} more local spans</button>}</footer>
    </div>
    {ui.open && span && effectiveMode === 'pinned' && <InspectorResize width={width} max={maxWidth} resize={resize} reset={() => setWidthPreference('auto')}/>}
    {ui.open && span && <SpanInspector repository={repository} projectId={route.projectId} runId={route.runId} span={span} ui={ui} patch={patch} dispatch={dispatch} mode={effectiveMode} width={width} maxWidth={maxWidth} canPin={!single} pin={pin} close={close} back={() => single ? close() : treeRef.current?.focus({ preventScroll: true })} resize={resize} resetWidth={() => setWidthPreference('auto')} jump={jump} inspectorRef={inspectorRef}/>}
  </div>
}
