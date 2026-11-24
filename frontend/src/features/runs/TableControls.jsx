import Icon from '../../components/Icon.jsx'
import { Menu, MenuCheckboxItem, MenuContent, MenuItem, MenuLabel, MenuSeparator, MenuTrigger } from '../../components/ui/Menu.jsx'

// Show or hide the optional columns. The Name column always stays, so a row can
// always be opened. Like Langfuse's "Columns n/m" control.
export function ColumnMenu({ columns, hidden, onChange }) {
  const optional = columns.filter(([field]) => field !== 'name')
  const shown = columns.length - hidden.filter(field => columns.some(([key]) => key === field)).length
  const toggle = field => onChange(hidden.includes(field) ? hidden.filter(item => item !== field) : [...hidden, field])
  // Keep the menu open while columns are toggled.
  const stay = event => event.preventDefault()
  return <Menu>
    <MenuTrigger><button type="button" className="button" aria-label={`Columns, ${shown} of ${columns.length} shown`} title="Show or hide columns"><Icon name="columns"/>Columns <span className="count">{shown}/{columns.length}</span></button></MenuTrigger>
    <MenuContent align="end" aria-label="Visible columns">
      <MenuLabel>Columns</MenuLabel>
      <MenuCheckboxItem checked disabled>Name</MenuCheckboxItem>
      {optional.map(([field, label]) => <MenuCheckboxItem key={field} checked={!hidden.includes(field)} onCheckedChange={() => toggle(field)} onSelect={stay}>{label}</MenuCheckboxItem>)}
      {hidden.length > 0 && <><MenuSeparator/><MenuItem onSelect={() => onChange([])}>Show all columns</MenuItem></>}
    </MenuContent>
  </Menu>
}
