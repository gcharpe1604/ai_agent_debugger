import { useRef } from 'react'
import Icon from '../../components/Icon.jsx'
import { types, typeLabel } from './treeModel.js'
import { FitSelected } from './TimelineControls.jsx'

export default function TraceToolbar({ ui, filter, patch, index, jump, wide, switchView, timing, timeWindowChange }) {
  const jumpInput = useRef(null)
  const activeFilters = Number(!!ui.type) + Number(!!ui.status)
  return <div className="trace-toolbar">
    <h2 className="sr-only">Execution</h2>
    <div className="trace-view-toggle" role="group" aria-label="Execution view" data-inspector-trigger>{['tree', 'timeline'].map(view => <button key={view} aria-pressed={ui.view === view} onClick={() => switchView(view)}>{view === 'tree' ? 'Tree' : 'Timeline'}</button>)}</div>
    <div className="trace-search"><Icon name="search"/><input type="search" aria-label="Search loaded spans" aria-keyshortcuts="/" data-shortcut="search" placeholder="Search loaded names or IDs…" value={ui.search} onChange={event => filter({ search: event.target.value })}/><kbd className="search-hint" aria-hidden="true" title="Press / to search">/</kbd></div>
    <button type="button" className="button small trace-error-filter" aria-label="Focus errors" aria-pressed={ui.status === 'ERROR'} title="Focus on recorded errors and keep their ancestor context" onClick={() => filter({ status: ui.status === 'ERROR' ? '' : 'ERROR' })}><Icon name="error"/><span>Errors</span></button>
    <details className="trace-menu"><summary className={`trace-icon-button ${activeFilters ? 'has-filters' : ''}`} aria-label="Span filters" aria-description={`${activeFilters} active filters`} title={`Span filters · ${activeFilters} active`}><Icon name="filter"/>{activeFilters > 0 && <span className="trace-filter-count" aria-hidden="true">{activeFilters}</span>}</summary><div className="trace-popover">
      <label>Operation type<select value={ui.type} onChange={event => filter({ type: event.target.value })}><option value="">All operation types</option>{types.map(type => <option key={type} value={type}>{typeLabel(type)}</option>)}</select></label>
      <label>Span status<select value={ui.status} onChange={event => filter({ status: event.target.value })}><option value="">All raw statuses</option>{['OK', 'ERROR', 'UNSET'].map(status => <option key={status}>{status}</option>)}<option value="unknown">Unknown / unrecognized</option></select></label>
      <button className="button small" onClick={() => filter({ search: '', type: '', status: '' })}>Clear span filters</button>
      <p>Search and filters cover loaded structure only. Matching ancestors remain visible.</p>
    </div></details>
    <details className="trace-menu"><summary className="trace-icon-button" aria-label="Execution options" title="Execution options">⋯</summary><div className="trace-popover">
      {ui.view === 'timeline' && <><FitSelected selected={timing.byId.get(ui.selected)} extent={timing.navigationExtent} change={timeWindowChange}/><p>Timing scope: {timing.extent.source === 'run' ? 'recorded run extent' : timing.extent.source === 'loaded' ? 'loaded timing only' : timing.extent.source === 'point' ? 'zero extent; 1 ms navigation view' : 'unavailable'}. Loaded spans: {timing.missingCount} missing, {timing.invalidCount} invalid, {timing.outsideCount} outside reported run bounds, {timing.mismatchCount} duration disagreements. Minimum drawing marks do not change recorded durations.</p></>}
      <button className="button small" onClick={() => patch({ collapsed: [] })}>Expand loaded branches</button>
      <button className="button small" disabled={!!(ui.search || ui.type || ui.status)} title="Matching ancestor paths stay expanded while filtering" onClick={() => patch({ collapsed: index.spans.map(span => span.id), scrollTop: 0, anchor: null })}>Collapse loaded branches</button>
      <label className="trace-check" title={ui.view === 'timeline' ? 'The optional ID column is a Tree presentation. IDs remain searchable and copyable in Details.' : !wide ? 'The ID column requires at least 840 px of explorer width. IDs remain available in Details and search.' : undefined}><input type="checkbox" checked={ui.showIds || false} disabled={!wide} onChange={event => patch({ showIds: event.target.checked })}/>Span ID column</label>
      <form onSubmit={event => { event.preventDefault(); jump(jumpInput.current.value.trim().toLowerCase()) }}><label>Jump to loaded span ID<input className="trace-text-input mono" ref={jumpInput} placeholder="Full span ID"/></label><button className="button small" type="submit">Jump to span</button></form>
    </div></details>
  </div>
}
