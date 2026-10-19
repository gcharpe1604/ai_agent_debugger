import { useRef } from 'react'

export default function InspectorResize({ width, max, resize, reset }) {
  const drag = useRef(null)
  return <div className="inspector-resize" role="separator" tabIndex="0" aria-label="Resize span inspector" aria-orientation="vertical" aria-valuemin={480} aria-valuemax={max} aria-valuenow={Math.round(width)} onKeyDown={event => {
    if (event.key === 'Enter') { event.preventDefault(); reset(); return }
    const next = { ArrowLeft: width + 16, ArrowRight: width - 16, Home: 480, End: max }[event.key]
    if (next !== undefined) { event.preventDefault(); resize(next) }
  }} onPointerDown={event => { drag.current = { x: event.clientX, width }; event.currentTarget.setPointerCapture(event.pointerId) }} onPointerMove={event => { if (drag.current) resize(drag.current.width + drag.current.x - event.clientX) }} onPointerUp={event => { drag.current = null; event.currentTarget.releasePointerCapture(event.pointerId) }} onPointerCancel={() => { drag.current = null }}><span/></div>
}
