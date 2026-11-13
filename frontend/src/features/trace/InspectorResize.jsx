import { useRef } from 'react'

// Drag (or arrow keys) on the inspector's left edge. Moving left widens it.
// data-inspector-trigger keeps a drag from counting as an outside click that
// would dismiss the overlay.
export default function InspectorResize({ width, min = 480, max, resize, reset, label = 'Resize span inspector' }) {
  const drag = useRef(null)
  return <div className="inspector-resize" data-inspector-trigger role="separator" tabIndex="0" aria-label={label} title="Drag to resize · Enter resets" aria-orientation="vertical" aria-valuemin={min} aria-valuemax={max} aria-valuenow={Math.round(width)} onKeyDown={event => {
    if (event.key === 'Enter') { event.preventDefault(); reset(); return }
    const next = { ArrowLeft: width + 16, ArrowRight: width - 16, Home: min, End: max }[event.key]
    if (next !== undefined) { event.preventDefault(); resize(next) }
  }} onPointerDown={event => { drag.current = { x: event.clientX, width }; event.currentTarget.setPointerCapture?.(event.pointerId) }} onPointerMove={event => { if (drag.current) resize(drag.current.width + drag.current.x - event.clientX) }} onPointerUp={event => { drag.current = null; event.currentTarget.releasePointerCapture?.(event.pointerId) }} onPointerCancel={() => { drag.current = null }}><span/></div>
}
