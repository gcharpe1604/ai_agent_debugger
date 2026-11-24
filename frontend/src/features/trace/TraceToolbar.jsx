import { useRef } from 'react'
import Icon from '../../components/Icon.jsx'
import Input from '../../components/ui/Input.jsx'
import Select from '../../components/ui/Select.jsx'
import { Popover, PopoverContent, PopoverTrigger } from '../../components/ui/Popover.jsx'
import { types, typeLabel } from './treeModel.js'
import { FitSelected } from './TimelineControls.jsx'

const statusOptions = [{ value: '', label: 'All raw statuses' }, ...['OK', 'ERROR', 'UNSET'].map(value => ({ value, label: value })), { value: 'unknown', label: 'Unknown / unrecognized' }]

export default function TraceToolbar({ ui, filter, patch, index, jump, wide, switchView, timing, timeWindowChange, children }) {
  const jumpInput = useRef(null)
  const activeFilters = Number(!!ui.type) + Number(!!ui.status)
  return <div className="trace-toolbar">
    <h2 className="sr-only">Execution</h2>
    <div className="trace-view-toggle segmented" role="group" aria-label="Execution view" data-inspector-trigger>{['tree', 'timeline'].map(view => <button key={view} type="button" aria-pressed={ui.view === view} onClick={() => switchView(view)}>{view === 'tree' ? 'Tree' : 'Timeline'}</button>)}</div>
    <Input icon="search" className="trace-search" type="search" aria-label="Search loaded spans" aria-keyshortcuts="/" data-shortcut="search" placeholder="Search loaded names or IDs…" value={ui.search} onChange={event => filter({ search: event.target.value })}/>
    <button type="button" className="button trace-error-filter" aria-label="Focus errors" aria-pressed={ui.status === 'ERROR'} title="Focus on recorded errors and keep their ancestor context" onClick={() => filter({ status: ui.status === 'ERROR' ? '' : 'ERROR' })}><Icon name="error"/><span>Errors</span></button>
    <Popover>
      <PopoverTrigger><button type="button" className={`button icon-only trace-filter-button${activeFilters ? ' has-filters' : ''}`} aria-label="Span filters" aria-description={`${activeFilters} active filters`} title={`Span filters · ${activeFilters} active`}><Icon name="filter"/>{activeFilters > 0 && <span className="trace-filter-count" aria-hidden="true">{activeFilters}</span>}</button></PopoverTrigger>
      <PopoverContent className="trace-popover">
        <span className="field"><span id="span-type-label">Operation type</span><Select aria-labelledby="span-type-label" value={ui.type} onValueChange={type => filter({ type })} options={[{ value: '', label: 'All operation types' }, ...types.map(type => ({ value: type, label: typeLabel(type) }))]}/></span>
        <span className="field"><span id="span-status-label">Span status</span><Select aria-labelledby="span-status-label" value={ui.status} onValueChange={status => filter({ status })} options={statusOptions}/></span>
        <button type="button" className="button" onClick={() => filter({ search: '', type: '', status: '' })}>Clear span filters</button>
        <p>Search and filters cover loaded structure only. Matching ancestors remain visible.</p>
      </PopoverContent>
    </Popover>
    {children}
    <Popover>
      <PopoverTrigger><button type="button" className="button icon-only" aria-label="Execution options" title="Execution options"><Icon name="more"/></button></PopoverTrigger>
      <PopoverContent className="trace-popover">
        {ui.view === 'timeline' && <><FitSelected selected={timing.byId.get(ui.selected)} extent={timing.navigationExtent} change={timeWindowChange}/><p>Timing scope: {timing.extent.source === 'run' ? 'recorded run extent' : timing.extent.source === 'loaded' ? 'loaded timing only' : timing.extent.source === 'point' ? 'zero extent; 1 ms navigation view' : 'unavailable'}. Loaded spans: {timing.missingCount} missing, {timing.invalidCount} invalid, {timing.outsideCount} outside reported run bounds, {timing.mismatchCount} duration disagreements. Minimum drawing marks do not change recorded durations.</p></>}
        <button type="button" className="button" onClick={() => patch({ collapsed: [] })}>Expand loaded branches</button>
        <button type="button" className="button" disabled={!!(ui.search || ui.type || ui.status)} title="Matching ancestor paths stay expanded while filtering" onClick={() => patch({ collapsed: index.spans.map(span => span.id), scrollTop: 0, anchor: null })}>Collapse loaded branches</button>
        <label className="trace-check" title={ui.view === 'timeline' ? 'The optional ID column is a Tree presentation. IDs remain searchable and copyable in Details.' : !wide ? 'The ID column needs at least 840 px of tree width. IDs remain available in Details and search.' : undefined}><input type="checkbox" checked={ui.showIds || false} disabled={!wide} onChange={event => patch({ showIds: event.target.checked })}/>Span ID column</label>
        <form onSubmit={event => { event.preventDefault(); jump(jumpInput.current.value.trim().toLowerCase()) }}><label>Jump to loaded span ID<input className="input mono" ref={jumpInput} placeholder="Full span ID"/></label><button className="button" type="submit">Jump to span</button></form>
      </PopoverContent>
    </Popover>
  </div>
}
