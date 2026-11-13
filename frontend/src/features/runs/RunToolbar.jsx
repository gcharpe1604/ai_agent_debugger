import { useEffect, useRef, useState } from 'react'
import Icon from '../../components/Icon.jsx'
import { investigationOptions, rangeOptions } from './query.js'
import { executionModeLabel } from './runColumns.js'

function Search({ value, onSearch }) {
  const input = useRef(null)
  // The draft stays native/uncommitted. URL changes update it without remounting
  // the focused field; unrelated filters do not erase unfinished typing.
  useEffect(() => { if (input.current.value !== value) input.current.value = value }, [value])
  return <form className="search-form" role="search" onSubmit={event => { event.preventDefault(); onSearch(input.current.value.trim()) }}><div className="search-field"><Icon name="search"/><input ref={input} type="search" aria-label="Search traces" aria-keyshortcuts="/" data-shortcut="search" placeholder="Search by agent name or trace ID…" defaultValue={value} maxLength={256}/><kbd className="search-hint" aria-hidden="true" title="Press / to search">/</kbd><button className="search-submit" type="submit" aria-label="Search">↵</button></div></form>
}
function AdvancedFilters({ query, onChange, live }) {
  const details = useRef(null)
  const form = useRef(null)
  const [error, setError] = useState('')
  const investigationKey = query.investigations.join(',')
  useEffect(() => { form.current.reset() }, [query.minMs, query.maxMs, investigationKey, query.hasErrors])
  const active = (live ? 0 : query.investigations.length + Number(query.hasErrors)) + Number(query.minMs !== null || query.maxMs !== null)
  function submit(event) {
    event.preventDefault()
    const data = new FormData(event.currentTarget)
    const minimum = data.get('minimum') === '' ? null : Number(data.get('minimum'))
    const maximum = data.get('maximum') === '' ? null : Number(data.get('maximum'))
    if ((minimum !== null && (!Number.isFinite(minimum) || minimum < 0)) || (maximum !== null && (!Number.isFinite(maximum) || maximum < 0)) || (minimum !== null && maximum !== null && minimum > maximum)) { setError('Enter non-negative durations; maximum must be at least minimum.'); return }
    setError('')
    onChange({ minMs: minimum, maxMs: maximum, ...(!live && { investigations: data.getAll('investigation'), hasErrors: data.has('errors') }) })
    details.current.open = false
    details.current.querySelector('summary').focus()
  }
  return <details className="filter-disclosure" ref={details}><summary className="button" onClick={() => setError('')}><Icon name="filter"/>Filters{active > 0 && <span className="count">{active}</span>}</summary><form ref={form} className="filter-panel" onSubmit={submit} aria-label="Additional run filters">
    <fieldset><legend>Duration · milliseconds</legend><div className="duration-fields"><label>Minimum<input name="minimum" type="number" min="0" step="any" defaultValue={query.minMs ?? ''} aria-describedby={error ? 'duration-error' : undefined}/></label><label>Maximum<input name="maximum" type="number" min="0" step="any" defaultValue={query.maxMs ?? ''} aria-describedby={error ? 'duration-error' : undefined}/></label></div>{error && <p className="inline-error" id="duration-error" role="alert">{error}</p>}</fieldset>
    {!live && <fieldset><legend>Investigation · match any selected</legend>{investigationOptions.map(value => <label className="check-field" key={value}><input type="checkbox" name="investigation" value={value} defaultChecked={query.investigations.includes(value)}/>{value}</label>)}</fieldset>}
    {!live && <label className="check-field"><input type="checkbox" name="errors" defaultChecked={query.hasErrors}/>With error spans</label>}
    <button type="submit" className="button solid">Apply filters</button>
  </form></details>
}
export default function RunToolbar({ query, onChange, onReset, live = false, filtersOpen = false, toggleFilters, children }) {
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
    {live && !filtersOpen && <button type="button" id="show-filters" className="button" aria-expanded="false" onClick={toggleFilters} title="Show the filter panel"><Icon name="panel-left"/>Show filters{sidebarFilters > 0 && <span className="count">{sidebarFilters}</span>}</button>}
    <Search value={query.search} onSearch={search => onChange({ search })}/>
    {live && <><label className="sr-only" htmlFor="time-range">Time range</label><select id="time-range" value={query.range || ''} onChange={event => onChange({ range: event.target.value })}>{rangeOptions.map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></>}
    {!live && <><label className="sr-only" htmlFor="outcome">Execution outcome</label><select id="outcome" value={query.outcomes.length > 1 ? 'multiple' : query.outcomes[0] || ''} onChange={event => onChange({ outcomes: event.target.value ? [event.target.value] : [] })}><option value="">All outcomes</option>{query.outcomes.length > 1 && <option value="multiple" disabled>Multiple outcomes</option>}{['Completed', 'Failed', 'Unknown'].map(value => <option key={value}>{value}</option>)}</select></>}
    {!live && <><label className="sr-only" htmlFor="capture">Telemetry completeness</label><select id="capture" value={query.completeness.length > 1 ? 'multiple' : query.completeness[0] || ''} onChange={event => onChange({ completeness: event.target.value ? [event.target.value] : [] })}><option value="">All completeness</option>{query.completeness.length > 1 && <option value="multiple" disabled>Multiple capture states</option>}{['Complete', 'Partial', 'Unknown'].map(value => <option key={value}>{value}</option>)}</select></>}
    {!live && <AdvancedFilters live={live} query={query} onChange={onChange}/>}
    {children && <div className="toolbar-end">{children}</div>}
  </div>{(chips.length > 0 || resettableView) && <div className="active-filters" aria-label="Active trace filters">
    {chips.map(chip => <button className="filter-chip" key={chip.label} aria-label={`Remove ${chip.label}`} onClick={() => onChange(chip.patch)}>{chip.label}<span aria-hidden="true">×</span></button>)}
    {chips.length > (live ? 1 : 0) && <button className="text-button" onClick={() => onChange({ search: '', range: '', outcomes: [], completeness: [], investigations: [], modes: [], agents: [], minMs: null, maxMs: null, hasErrors: false })}>Clear filters</button>}
    {resettableView && <button className="text-button" onClick={onReset}>Reset view</button>}
  </div>}</>
}
