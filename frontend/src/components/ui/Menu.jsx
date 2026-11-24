import * as RadixMenu from '@radix-ui/react-dropdown-menu'
import Icon from '../Icon.jsx'
import { containEscape, cx } from './cx.js'

// Dropdown menu: actions, checkbox and radio items. Keyboard and screen-reader
// behaviour (arrow keys, typeahead, Escape, focus return) come from Radix.
export const Menu = props => <RadixMenu.Root {...props}/>
export const MenuTrigger = props => <RadixMenu.Trigger asChild {...props}/>

export function MenuContent({ className, align = 'start', side = 'bottom', sideOffset = 4, onEscapeKeyDown, ...props }) {
  return <RadixMenu.Portal>
    <RadixMenu.Content className={cx('ui-layer menu-content', className)} align={align} side={side} sideOffset={sideOffset} onEscapeKeyDown={containEscape(onEscapeKeyDown)} {...props}/>
  </RadixMenu.Portal>
}
export const MenuItem = ({ className, ...props }) => <RadixMenu.Item className={cx('menu-item', className)} {...props}/>
export const MenuLabel = ({ className, ...props }) => <RadixMenu.Label className={cx('menu-label', className)} {...props}/>
export const MenuSeparator = () => <RadixMenu.Separator className="menu-separator"/>

export function MenuCheckboxItem({ className, children, ...props }) {
  return <RadixMenu.CheckboxItem className={cx('menu-item', className)} {...props}>
    <span className="menu-indicator-slot"><RadixMenu.ItemIndicator className="menu-indicator"><Icon name="check"/></RadixMenu.ItemIndicator></span>
    {children}
  </RadixMenu.CheckboxItem>
}
export const MenuRadioGroup = props => <RadixMenu.RadioGroup {...props}/>
// indicator={false} drops the check mark, for segmented radio groups.
export function MenuRadioItem({ className, children, indicator = true, ...props }) {
  return <RadixMenu.RadioItem className={cx('menu-item', className)} {...props}>
    {indicator && <span className="menu-indicator-slot"><RadixMenu.ItemIndicator className="menu-indicator"><Icon name="check"/></RadixMenu.ItemIndicator></span>}
    {children}
  </RadixMenu.RadioItem>
}
