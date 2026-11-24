import * as RadixTooltip from '@radix-ui/react-tooltip'

// Wrap the app once; tooltips share one open delay.
export const TooltipProvider = ({ children }) => <RadixTooltip.Provider delayDuration={300} skipDelayDuration={100}>{children}</RadixTooltip.Provider>

// A text label shown on hover and keyboard focus. The trigger keeps its own
// accessible name; the tooltip only repeats it visually.
export default function Tooltip({ content, side = 'top', disabled = false, children }) {
  if (disabled || !content) return children
  return <RadixTooltip.Root>
    <RadixTooltip.Trigger asChild>{children}</RadixTooltip.Trigger>
    <RadixTooltip.Portal>
      <RadixTooltip.Content className="ui-layer tooltip-content" side={side} sideOffset={6} collisionPadding={8}>{content}</RadixTooltip.Content>
    </RadixTooltip.Portal>
  </RadixTooltip.Root>
}
