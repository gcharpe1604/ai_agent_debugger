import { useEffect, useRef, useState } from 'react'
import Icon from '../../components/Icon.jsx'
import { executionModeLabel } from './runColumns.js'

const toggle = (values, value) => values.includes(value) ? values.filter(item => item !== value) : [...values, value]

// One group of checkboxes. A value shows when it has matches or is selected,
// so an active filter can always be cleared from where it was set.
function FacetGroup({ title, values, counts, selected, label = value => value, onChange }) {
  const shown = values.filter(value => counts[value] > 0 || selected.includes(value))
  return <fieldset className="facet-group">
    <legend>{title}{selected.length > 0 && <button type="button" className="text-button" onClick={() => onChange([])} aria-label={`Clear ${title} filter`}>Clear</button>}</legend>
    {shown.length ? shown.map(value => <label key={value} className="facet-option">
      <input type="checkbox" checked={selected.includes(value)} onChange={() => onChange(toggle(selected, value))}/>
      <span className="facet-name" title={label(value)}>{label(value)}</span>
      <span className="facet-count">{(counts[value] || 0).toLocaleString('en')}</span>
    </label>) : <p className="facet-empty">No values in matching traces</p>}
  </fieldset>
}

function DurationFilter({ query, onChange }) {
  const form = useRef(null)
  const [error, setError] = useState('')
  useEffect(() => { form.current.reset() }, [query.minMs, query.maxMs])
  function submit(event) {
    event.preventDefault()
    const data = new FormData(event.currentTarget)
    const read = name => data.get(name) === '' ? null : Number(data.get(name))
    const minimum = read('minimum'), maximum = read('maximum')
    if ([minimum, maximum].some(value => value !== null && (!Number.isFinite(value) || value < 0)) || (minimum !== null && maximum !== null && minimum > maximum)) { setError('Enter non-negative values; maximum must be at least minimum.'); return }
    setError('')
    onChange({ minMs: minimum, maxMs: maximum })
  }
  return <form ref={form} className="facet-group facet-form" onSubmit={submit} aria-label="Duration filter">
    <fieldset><legend>Duration · ms</legend>
      <div className="facet-duration"><label>Min<input name="minimum" type="number" min="0" step="any" inputMode="decimal" defaultValue={query.minMs ?? ''}/></label><label>Max<input name="maximum" type="number" min="0" step="any" inputMode="decimal" defaultValue={query.maxMs ?? ''}/></label><button type="submit" className="button small">Apply</button></div>
      {error && <p className="inline-error" role="alert">{error}</p>}
    </fieldset>
  </form>
}

export default function FacetSidebar({ query, facets, onChange, onClose }) {
  const counts = facets || { outcome: {}, mode: {}, agent: {}, errors: {} }
  const agents = Object.keys(counts.agent).concat(query.agents.filter(name => !(name in counts.agent))).sort((a, b) => a.localeCompare(b, 'en'))
  const active = query.outcomes.length + query.modes.length + query.agents.length + Number(query.hasErrors) + Number(query.minMs !== null || query.maxMs !== null)
  return <aside className="facet-sidebar" aria-label="Trace filters">
    <header className="facet-header">
      <button type="button" id="hide-filters" className="trace-icon-button" aria-label="Hide filters" aria-expanded="true" title="Hide filters" onClick={onClose}><Icon name="panel-left"/></button>
      <strong>Filters</strong>
      {active > 0 && <button type="button" className="text-button" onClick={() => onChange({ outcomes: [], modes: [], agents: [], hasErrors: false, minMs: null, maxMs: null })}>Clear all</button>}
    </header>
    <FacetGroup title="Status" values={['Completed', 'Failed', 'Unknown']} counts={counts.outcome} selected={query.outcomes} onChange={outcomes => onChange({ outcomes })}/>
    <fieldset className="facet-group">
      <legend>Error spans</legend>
      <label className="facet-option"><input type="checkbox" checked={query.hasErrors} onChange={() => onChange({ hasErrors: !query.hasErrors })}/><span className="facet-name">Has error spans</span><span className="facet-count">{(counts.errors.with || 0).toLocaleString('en')}</span></label>
    </fieldset>
    <FacetGroup title="Execution mode" values={['controlled', 'live']} counts={counts.mode} selected={query.modes} label={mode => executionModeLabel(mode)} onChange={modes => onChange({ modes })}/>
    <FacetGroup title="Agent" values={agents} counts={counts.agent} selected={query.agents} onChange={names => onChange({ agents: names })}/>
    <DurationFilter query={query} onChange={onChange}/>
  </aside>
}
