import { useEffect, useRef, useState } from 'react'
import Icon from '../../components/Icon.jsx'
import { investigationOptions } from './query.js'

function Search({ value, onSearch }) {
  const input = useRef(null)
  // The draft stays native/uncommitted. URL changes update it without remounting
  // the focused field; unrelated filters do not erase unfinished typing.
  useEffect(() => { if (input.current.value !== value) input.current.value = value }, [value])
  return <form className="search-form" role="search" onSubmit={event => { event.preventDefault(); onSearch(input.current.value.trim()) }}><div className="search-field"><Icon name="search"/><input ref={input} type="search" aria-label="Search runs" placeholder="Search name or trace ID…" defaultValue={value} maxLength={256}/><button className="search-submit" type="submit" aria-label="Search">↵</button></div></form>
}
function AdvancedFilters({ query, onChange, live }) {
  const details = useRef(null)
  const form = useRef(null)
  const [error, setError] = useState('')
  const investigationKey = query.investigations.join(',')
  useEffect(() => { form.current.reset() }, [query.minMs, query.maxMs, investigationKey, query.hasErrors])
  const active = query.investigations.length + Number(query.hasErrors) + Number(query.minMs !== null || query.maxMs !== null)
  function submit(event) {
    event.preventDefault()
    const data = new FormData(event.currentTarget)
    const minimum = data.get('minimum') === '' ? null : Number(data.get('minimum'))
    const maximum = data.get('maximum') === '' ? null : Number(data.get('maximum'))
    if ((minimum !== null && (!Number.isFinite(minimum) || minimum < 0)) || (maximum !== null && (!Number.isFinite(maximum) || maximum < 0)) || (minimum !== null && maximum !== null && minimum > maximum)) { setError('Enter non-negative durations; maximum must be at least minimum.'); return }
    setError(''); onChange({ minMs: minimum, maxMs: maximum, investigations: data.getAll('investigation'), hasErrors: data.has('errors') }); details.current.open = false; details.current.querySelector('summary').focus()
  }
  return <details className="filter-disclosure" ref={details}><summary className="button" onClick={() => setError('')}><Icon name="filter"/>Filters{active > 0 && <span className="count">{active}</span>}</summary><form ref={form} className="filter-panel" onSubmit={submit} aria-label="Additional run filters">
    <fieldset><legend>Duration · milliseconds</legend><div className="duration-fields"><label>Minimum<input name="minimum" type="number" min="0" step="any" defaultValue={query.minMs ?? ''} aria-describedby={error ? 'duration-error' : undefined}/></label><label>Maximum<input name="maximum" type="number" min="0" step="any" defaultValue={query.maxMs ?? ''} aria-describedby={error ? 'duration-error' : undefined}/></label></div>{error && <p className="inline-error" id="duration-error" role="alert">{error}</p>}</fieldset>
    {!live && <fieldset><legend>Investigation · match any selected</legend>{investigationOptions.map(value => <label className="check-field" key={value}><input type="checkbox" name="investigation" value={value} defaultChecked={query.investigations.includes(value)}/>{value}</label>)}</fieldset>}
    <label className="check-field"><input type="checkbox" name="errors" defaultChecked={query.hasErrors}/>With recorded errors</label><button type="submit" className="button solid">Apply filters</button>
  </form></details>
}
export default function RunToolbar({ query, onChange, onReset, live = false }) {
  const chips = [
    ...(query.search ? [{ label: `Search: ${query.search}`, patch: { search: '' } }] : []),
    ...query.outcomes.map(value => ({ label: `Outcome: ${value}`, patch: { outcomes: query.outcomes.filter(item => item !== value) } })),
    ...query.completeness.map(value => ({ label: `Capture: ${value}`, patch: { completeness: query.completeness.filter(item => item !== value) } })),
    ...query.investigations.map(value => ({ label: `Investigation: ${value}`, patch: { investigations: query.investigations.filter(item => item !== value) } })),
    ...(query.hasErrors ? [{ label: 'Recorded errors', patch: { hasErrors: false } }] : []),
    ...(query.minMs !== null || query.maxMs !== null ? [{ label: `Duration: ${query.minMs ?? 0}–${query.maxMs ?? '∞'} ms`, patch: { minMs: null, maxMs: null } }] : []),
  ]
  return <><div className="query-toolbar">
    <Search value={query.search} onSearch={search => onChange({ search })}/>
    {live && <><label className="sr-only" htmlFor="time-window">Local captured times</label><select id="time-window" className="time-filter" disabled value="all"><option value="all">All locally captured times</option></select></>}
    <label className="sr-only" htmlFor="outcome">Execution outcome</label><select id="outcome" value={query.outcomes.length > 1 ? 'multiple' : query.outcomes[0] || ''} onChange={event => onChange({ outcomes: event.target.value ? [event.target.value] : [] })}><option value="">All outcomes</option>{query.outcomes.length > 1 && <option value="multiple" disabled>Multiple outcomes</option>}{['Completed', 'Failed', 'Unknown'].map(value => <option key={value}>{value}</option>)}</select>
    <label className="sr-only" htmlFor="capture">Telemetry completeness</label><select id="capture" value={query.completeness.length > 1 ? 'multiple' : query.completeness[0] || ''} onChange={event => onChange({ completeness: event.target.value ? [event.target.value] : [] })}><option value="">All completeness</option>{query.completeness.length > 1 && <option value="multiple" disabled>Multiple capture states</option>}{['Complete', 'Partial', 'Unknown'].map(value => <option key={value}>{value}</option>)}</select>
    <AdvancedFilters live={live} query={query} onChange={onChange}/>
  </div>{(chips.length > 0 || query.time !== (live ? 'all' : 'window')) && <div className="active-filters" aria-label="Active run filters">{chips.map(chip => <button className="filter-chip" key={chip.label} aria-label={`Remove ${chip.label}`} onClick={() => onChange(chip.patch)}>{chip.label}<span aria-hidden="true">×</span></button>)}{chips.length > 0 && <button className="text-button" onClick={() => onChange({ search: '', outcomes: [], completeness: [], investigations: [], minMs: null, maxMs: null, hasErrors: false })}>Clear filters</button>}<button className="text-button secondary" onClick={onReset}>Reset query</button></div>}</>
}
