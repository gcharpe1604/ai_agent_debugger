import * as RadixPopover from '@radix-ui/react-popover'
import { containEscape, cx } from './cx.js'

// Non-modal panel for small forms and option lists (filters, view options).
export const Popover = props => <RadixPopover.Root {...props}/>
export const PopoverTrigger = props => <RadixPopover.Trigger asChild {...props}/>

export function PopoverContent({ className, align = 'end', sideOffset = 4, onEscapeKeyDown, ...props }) {
  return <RadixPopover.Portal>
    <RadixPopover.Content className={cx('ui-layer popover-content', className)} align={align} sideOffset={sideOffset} collisionPadding={8} onEscapeKeyDown={containEscape(onEscapeKeyDown)} {...props}/>
  </RadixPopover.Portal>
}
