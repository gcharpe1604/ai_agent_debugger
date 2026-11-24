import * as RadixTabs from '@radix-ui/react-tabs'
import { cx } from './cx.js'

// Underlined tabs. Arrow keys, Home and End move between tabs (Radix).
export const Tabs = props => <RadixTabs.Root {...props}/>
export const TabsList = ({ className, ...props }) => <RadixTabs.List className={cx('tabs-list', className)} {...props}/>
export const TabsTrigger = ({ className, ...props }) => <RadixTabs.Trigger className={cx('tabs-trigger', className)} {...props}/>
export const TabsContent = props => <RadixTabs.Content {...props}/>
