import { useEffect, useRef, useState } from 'react'
import Icon from '../../components/Icon.jsx'
import Input from '../../components/ui/Input.jsx'
import Select from '../../components/ui/Select.jsx'
import { Popover, PopoverContent, PopoverTrigger } from '../../components/ui/Popover.jsx'
import { investigationOptions, rangeOptions } from './query.js'
import { executionModeLabel } from './runColumns.js'

function Search({ value, onSearch }) {
  const input = useRef(null)
  // The draft stays native/uncommitted. URL changes update it without remounting
  // the focused field; unrelated filters do not erase unfinished typing.
  useEffect(() => { if (input.current.value !== value) input.current.value = value }, [value])
  return <form className="search-form" role="search" onSubmit={event => { event.preventDefault(); onSearch(input.current.value.trim()) }}><Input icon="search" className="search-field" ref={input} type="search" aria-label="Search traces" aria-keyshortcuts="/" data-shortcut="search" placeholder="Search by agent name or trace ID…" defaultValue={value} maxLength={256} enterKeyHint="search"/></form>
}
const choice = (all, multiple, values, selected) => [{ value: '', label: all }, ...(selected.length > 1 ? [{ value: 'multiple', label: multiple, disabled: true }] : []), ...values.map(value => ({ value, label: value }))]
function AdvancedFilters({ query, onChange, live }) {
  const [open, setOpen] = useState(false)
  const form = useRef(null)
  const [error, setError] = useState('')
  const investigationKey = query.investigations.join(',')
  useEffect(() => { form.current?.reset() }, [query.minMs, query.maxMs, investigationKey, query.hasErrors])
  const active = (live ? 0 : query.investigations.length + Number(query.hasErrors)) + Number(query.minMs !== null || query.maxMs !== null)
  function submit(event) {
    event.preventDefault()
    const data = new FormData(event.currentTarget)
    const minimum = data.get('minimum') === '' ? null : Number(data.get('minimum'))
    const maximum = data.get('maximum') === '' ? null : Number(data.get('maximum'))
    if ((minimum !== null && (!Number.isFinite(minimum) || minimum < 0)) || (maximum !== null && (!Number.isFinite(maximum) || maximum < 0)) || (minimum !== null && maximum !== null && minimum > maximum)) { setError('Enter non-negative durations; maximum must be at least minimum.'); return }
    setError('')
    onChange({ minMs: minimum, maxMs: maximum, ...(!live && { investigations: data.getAll('investigation'), hasErrors: data.has('errors') }) })
    setOpen(false)
  }
  return <Popover open={open} onOpenChange={next => { setOpen(next); setError('') }}><PopoverTrigger><button type="button" className="button"><Icon name="filter"/>Filters{active > 0 && <span className="count">{active}</span>}</button></PopoverTrigger><PopoverContent asChild><form ref={form} className="filter-panel" onSubmit={submit} aria-label="Additional run filters">
    <fieldset><legend>Duration · milliseconds</legend><div className="duration-fields"><label>Minimum<input name="minimum" type="number" min="0" step="any" defaultValue={query.minMs ?? ''} aria-describedby={error ? 'duration-error' : undefined}/></label><label>Maximum<input name="maximum" type="number" min="0" step="any" defaultValue={query.maxMs ?? ''} aria-describedby={error ? 'duration-error' : undefined}/></label></div>{error && <p className="inline-error" id="duration-error" role="alert">{error}</p>}</fieldset>
    {!live && <fieldset><legend>Investigation · match any selected</legend>{investigationOptions.map(value => <label className="check-field" key={value}><input type="checkbox" name="investigation" value={value} defaultChecked={query.investigations.includes(value)}/>{value}</label>)}</fieldset>}
    {!live && <label className="check-field"><input type="checkbox" name="errors" defaultChecked={query.hasErrors}/>With error spans</label>}
    <button type="submit" className="button solid">Apply filters</button>
  </form></PopoverContent></Popover>
}
export default function RunToolbar({ query, onChange, onReset, live = false, filtersOpen = false, filtersDrawer = false, toggleFilters, children }) {
  const resettableView = query.sort !== 'startedAt' || query.direction !== 'desc' || query.pageSize !== 25 || query.time !== (live ? 'all' : 'window')
  const modes = query.modes || [], agents = query.agents || []
  const chips = [
    ...(query.search ? [{ label: `Search: ${query.search}`, patch: { search: '' } }] : []),
    ...(query.range ? [{ label: `Time: ${rangeOptions.find(([value]) => value === query.range)[1]}`, patch: { range: '' } }] : []),
    ...query.outcomes.map(value => ({ label: `Status: ${value}`, patch: { outcomes: query.outcomes.filter(item => item !== value) } })),
    ...query.completeness.map(value => ({ label: `Capture: ${value}`, patch: { completeness: query.completeness.filter(item => item !== value) } })),
    ...query.investigations.map(value => ({ label: `Investigation: ${value}`, patch: { investigations: query.investigations.filter(item => item !== value) } })),
    ...modes.map(value => ({ label: `Mode: ${executionModeLabel(value)}`, patch: { modes: modes.filter(item => item !== value) } })),
    ...agents.map(value => ({ label: `Agent: ${value}`, patch: { agents: agents.filter(item => item !== value) } })),
    ...(query.hasErrors ? [{ label: live ? 'Has error spans' : 'Error spans', patch: { hasErrors: false } }] : []),
    ...(query.minMs !== null || query.maxMs !== null ? [{ label: `Duration: ${query.minMs ?? 0}–${query.maxMs ?? '∞'} ms`, patch: { minMs: null, maxMs: null } }] : []),
  ]
  const sidebarFilters = query.outcomes.length + modes.length + agents.length + Number(query.hasErrors) + Number(query.minMs !== null || query.maxMs !== null)
  return <><div className={`query-toolbar${live ? ' local-toolbar' : ''}`}>
    {live && (filtersDrawer || !filtersOpen) && <button type="button" id="show-filters" className="button" aria-expanded={filtersOpen} aria-controls={filtersOpen ? 'trace-filters' : undefined} onClick={toggleFilters} title={filtersDrawer ? 'Open the filter drawer' : 'Show the filter panel'}><Icon name={filtersDrawer ? 'filter' : 'panel-left'}/>{filtersDrawer ? 'Filters' : 'Show filters'}{sidebarFilters > 0 && <span className="count">{sidebarFilters}</span>}</button>}
    <Search value={query.search} onSearch={search => onChange({ search })}/>
    {live && <Select aria-label="Time range" value={query.range || ''} onValueChange={range => onChange({ range })} options={rangeOptions.map(([value, label]) => ({ value, label }))}/>}
    {!live && <Select aria-label="Execution outcome" value={query.outcomes.length > 1 ? 'multiple' : query.outcomes[0] || ''} onValueChange={value => onChange({ outcomes: value ? [value] : [] })} options={choice('All outcomes', 'Multiple outcomes', ['Completed', 'Failed', 'Unknown'], query.outcomes)}/>}
    {!live && <Select aria-label="Telemetry completeness" value={query.completeness.length > 1 ? 'multiple' : query.completeness[0] || ''} onValueChange={value => onChange({ completeness: value ? [value] : [] })} options={choice('All completeness', 'Multiple capture states', ['Complete', 'Partial', 'Unknown'], query.completeness)}/>}
    {!live && <AdvancedFilters live={live} query={query} onChange={onChange}/>}
    {children && <div className="toolbar-end">{children}</div>}
  </div>{(chips.length > 0 || resettableView) && <div className="active-filters" aria-label="Active trace filters">
    {chips.map(chip => <button className="filter-chip" key={chip.label} aria-label={`Remove ${chip.label}`} onClick={() => onChange(chip.patch)}>{chip.label}<span aria-hidden="true">×</span></button>)}
    {chips.length > (live ? 1 : 0) && <button className="text-button" onClick={() => onChange({ search: '', range: '', outcomes: [], completeness: [], investigations: [], modes: [], agents: [], minMs: null, maxMs: null, hasErrors: false })}>Clear filters</button>}
    {resettableView && <button className="text-button" onClick={onReset}>Reset view</button>}
  </div>}</>
}
