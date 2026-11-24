import { useRef } from 'react'
import { cx } from './cx.js'
import { splitKeyWidth } from './split.js'

// Vertical divider between two panes. `value` is the right pane's width in px;
// drag it or use the arrow keys. Enter resets to the default width.
export default function SplitDivider({ value, min, max, onChange, onReset, label, controls, className }) {
  const drag = useRef(null)
  const clamp = width => Math.max(min, Math.min(max, Math.round(width)))
  return <div className={cx('split-divider', className)} role="separator" tabIndex="0" aria-label={label} aria-controls={controls} aria-orientation="vertical" aria-valuemin={min} aria-valuemax={max} aria-valuenow={Math.round(value)} title="Drag to resize · arrow keys · Enter resets"
    onKeyDown={event => {
      if (event.key === 'Enter' && onReset) { event.preventDefault(); onReset(); return }
      const next = splitKeyWidth(event.key, value, min, max)
      if (next !== undefined) { event.preventDefault(); onChange(next) }
    }}
    onPointerDown={event => { drag.current = { x: event.clientX, width: value }; event.currentTarget.setPointerCapture?.(event.pointerId) }}
    onPointerMove={event => { if (drag.current) onChange(clamp(drag.current.width + drag.current.x - event.clientX)) }}
    onPointerUp={event => { drag.current = null; event.currentTarget.releasePointerCapture?.(event.pointerId) }}
    onPointerCancel={() => { drag.current = null }}><span/></div>
}
