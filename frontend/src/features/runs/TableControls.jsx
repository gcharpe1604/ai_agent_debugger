import Icon from '../../components/Icon.jsx'

const densities = [['small', 'Small', 'Name only'], ['medium', 'Medium', 'Name and first error'], ['large', 'Large', 'Name, first error, trace ID and preview']]

// Show or hide the optional columns. The Trace column always stays, so a row can
// always be opened. Like Langfuse's "Columns n/m" control.
export function ColumnMenu({ columns, hidden, onChange }) {
  const optional = columns.filter(([field]) => field !== 'name')
  const shown = columns.length - hidden.filter(field => columns.some(([key]) => key === field)).length
  const toggle = field => onChange(hidden.includes(field) ? hidden.filter(item => item !== field) : [...hidden, field])
  return <details className="table-menu">
    <summary className="button small" aria-label={`Columns, ${shown} of ${columns.length} shown`} title="Show or hide columns"><Icon name="columns"/>Columns <span className="count">{shown}/{columns.length}</span></summary>
    <div className="menu-popover table-menu-popover" role="group" aria-label="Visible columns">
      <p className="menu-label">Columns</p>
      <label className="menu-check"><input type="checkbox" checked disabled/>Trace<span className="secondary">always shown</span></label>
      {optional.map(([field, label]) => <label key={field} className="menu-check"><input type="checkbox" checked={!hidden.includes(field)} onChange={() => toggle(field)}/>{label}</label>)}
      {hidden.length > 0 && <button type="button" className="text-button" onClick={() => onChange([])}>Show all columns</button>}
    </div>
  </details>
}

export function DensityMenu({ density, onChange }) {
  return <details className="table-menu">
    <summary className="button small icon-only" aria-label={`Row height: ${densities.find(([value]) => value === density)[1]}`} title="Row height"><Icon name={density === 'small' ? 'rows-compact' : 'rows'}/></summary>
    <div className="menu-popover table-menu-popover" role="radiogroup" aria-label="Row height">
      <p className="menu-label">Row height</p>
      {densities.map(([value, label, detail]) => <label key={value} className="menu-check"><input type="radio" name="row-height" checked={density === value} onChange={() => onChange(value)}/>{label}<span className="secondary">{detail}</span></label>)}
    </div>
  </details>
}
