import * as RadixSelect from '@radix-ui/react-select'
import Icon from '../Icon.jsx'
import { containEscape, cx } from './cx.js'

// Radix reserves the empty string for "no value"; our "All …" options use it.
const EMPTY = '__all__'
const toRadix = value => value === '' || value === null || value === undefined ? EMPTY : String(value)
const fromRadix = value => value === EMPTY ? '' : value

// options: [{ value, label, disabled? }]. Values are strings ('' allowed).
// Name the trigger with aria-label or a <label htmlFor={id}>.
export default function Select({ value, onValueChange, options, id, placeholder, disabled, className, align = 'start', ...props }) {
  return <RadixSelect.Root value={toRadix(value)} onValueChange={next => onValueChange(fromRadix(next))} disabled={disabled}>
    <RadixSelect.Trigger id={id} className={cx('select-trigger', className)} {...props}>
      <RadixSelect.Value placeholder={placeholder}/>
      <RadixSelect.Icon className="select-chevron"><Icon name="chevron-down"/></RadixSelect.Icon>
    </RadixSelect.Trigger>
    <RadixSelect.Portal>
      <RadixSelect.Content className="ui-layer menu-content select-content" position="popper" sideOffset={4} align={align} onEscapeKeyDown={containEscape()}>
        <RadixSelect.Viewport>
          {options.map(option => <RadixSelect.Item key={toRadix(option.value)} value={toRadix(option.value)} disabled={option.disabled} className="menu-item">
            <RadixSelect.ItemText>{option.label}</RadixSelect.ItemText>
            <RadixSelect.ItemIndicator className="menu-indicator"><Icon name="check"/></RadixSelect.ItemIndicator>
          </RadixSelect.Item>)}
        </RadixSelect.Viewport>
      </RadixSelect.Content>
    </RadixSelect.Portal>
  </RadixSelect.Root>
}
