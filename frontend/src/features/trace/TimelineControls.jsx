import { fitInterval, panWindow, projectInterval, timeLabel, zoomWindow } from './timelineModel.js'

export default function TimelineControls({ timing, window, selected, change }) {
  const { extent: fitExtent, navigationExtent: extent } = timing
  const full = extent.end - extent.start, width = window.end - window.start
  const room = Math.max(0, full - width)
  const selectedDrawing = selected?.state === 'valid' ? projectInterval(selected, extent) : null
  const source = (extent.source === 'unavailable' ? 'Timing extent unavailable' : extent.source === 'loaded' ? 'Loaded timing only' : extent.source === 'point' ? 'Zero extent · 1 ms view' : 'Recorded run extent') + (timing.outsideCount ? `; navigation includes ${timing.outsideCount} loaded intervals outside reported run timing` : '')
  return <div className="timeline-controls" data-inspector-trigger role="group" aria-label="Timeline navigation">
    <button className="trace-icon-button" aria-label="Zoom out" title="Zoom out" disabled={!extent.available || width >= full} onClick={() => change(zoomWindow(window, 2, extent))}>−</button>
    <button className="trace-icon-button" aria-label="Zoom in" title="Zoom in" disabled={!extent.available || width <= Math.min(1, full)} onClick={() => change(zoomWindow(window, .5, extent))}>+</button>
    <button className="button small timeline-fit" aria-label={fitExtent.source === 'loaded' ? 'Fit loaded timing' : 'Fit run'} title={source} disabled={!extent.available} onClick={() => change(null)}>Fit</button>
    <button className="trace-icon-button" aria-label="Previous time window" title="Previous time window" disabled={!extent.available || window.start <= extent.start} onClick={() => change(panWindow(window, -.5, extent))}>←</button>
    <output className="timeline-window mono" aria-label="Visible time window" title={`${timeLabel(window.start)} – ${timeLabel(window.end)} · ${source}`} aria-live="polite">{extent.available ? `${timeLabel(window.start)}–${timeLabel(window.end)}` : 'Timing unavailable'}</output>
    <button className="trace-icon-button" aria-label="Next time window" title="Next time window" disabled={!extent.available || window.end >= extent.end} onClick={() => change(panWindow(window, .5, extent))}>→</button>
    <div className="timeline-overview" title={`${source}. Highlight shows the visible window; the thin marker is the selected interval.`}>
      <span className="timeline-overview-window" style={{ left: `${(window.start - extent.start) / full * 100}%`, width: `${width / full * 100}%` }}/>
      {selectedDrawing && ['bar', 'point'].includes(selectedDrawing.kind) && <span className="timeline-overview-selected" style={{ left: `${selectedDrawing.left}%`, width: `${selectedDrawing.width}%` }}/>}
      <input type="range" min="0" max="1000" step="1" value={room ? Math.round((window.start - extent.start) / room * 1000) : 0} disabled={!extent.available || !room} aria-label="Timeline window start" aria-valuetext={`${timeLabel(window.start)}; ${source}`} onChange={event => { const start = extent.start + room * Number(event.target.value) / 1000; change({ start, end: start + width }) }}/>
    </div>
    <span className="sr-only">{source}. Timing does not establish causal dependencies.</span>
  </div>
}

export function FitSelected({ selected, extent, change }) {
  return <button className="button small" disabled={!extent.available || selected?.state !== 'valid'} onClick={() => change(fitInterval(selected, extent))}>Fit selected interval</button>
}
