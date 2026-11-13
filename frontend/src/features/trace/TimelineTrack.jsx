import { intervalLabel, projectInterval, timeLabel } from './timelineModel.js'

export function TimelineAxis({ window, available }) {
  return <div className="trace-columns trace-grid timeline-grid" aria-hidden="true"><span>Operation / recorded hierarchy</span><div className="timeline-axis">{available ? [0, .25, .5, .75, 1].map((part, i) => <span key={part} className={`timeline-tick tick-${i}`} style={{ left: `${part * 100}%` }}>{timeLabel(window.start + part * (window.end - window.start))}</span>) : 'Timing unavailable'}</div></div>
}

export default function TimelineTrack({ timing, window, status, type = 'custom', label }) {
  const drawing = projectInterval(timing, window)
  const labels = { before: 'Before window', after: 'After window', missing: 'Timing unavailable', invalid: 'Invalid timing' }
  const description = intervalLabel(timing) + (drawing.clippedStart || drawing.clippedEnd ? '; drawing clipped at window edge' : '') + (drawing.kind === 'before' || drawing.kind === 'after' ? `; ${labels[drawing.kind]}` : '')
  // The duration label sits after the bar, or before it when the bar ends near the right edge.
  const end = drawing.left + (drawing.width || 0)
  const labelStyle = end > 72 ? { right: `calc(${100 - drawing.left}% + 6px)` } : { left: `calc(${end}% + 6px)` }
  return <div className={`timeline-track ${status === 'ERROR' ? 'has-error' : ''}`} data-type={type} data-timing={drawing.kind} title={description} aria-label={description}>
    {labels[drawing.kind] ? <span className="timeline-unavailable">{labels[drawing.kind]}</span> : <>
      {[0, .25, .5, .75, 1].map(part => <span className="timeline-gridline" key={part} style={{ left: `${part * 100}%` }}/>)}
      <span className={`timeline-${drawing.kind}${drawing.clippedStart ? ' clipped-start' : ''}${drawing.clippedEnd ? ' clipped-end' : ''}`} data-left={drawing.left} data-width={drawing.width} style={{ left: `${drawing.left}%`, width: drawing.kind === 'point' ? '3px' : `max(3px, ${drawing.width}%)` }}/>
      {label && <span className="timeline-label mono" aria-hidden="true" style={labelStyle}>{label}</span>}
      {timing.mismatch && <span className="timeline-mismatch">!</span>}
    </>}
  </div>
}
