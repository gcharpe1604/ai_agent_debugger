import { intervalLabel, projectInterval, timeLabel } from './timelineModel.js'

export function TimelineAxis({ window, available }) {
  return <div className="trace-columns trace-grid timeline-grid" aria-hidden="true"><span>Operation / recorded hierarchy</span><div className="timeline-axis">{available ? [0, .25, .5, .75, 1].map((part, i) => <span key={part} className={`timeline-tick tick-${i}`} style={{ left: `${part * 100}%` }}>{timeLabel(window.start + part * (window.end - window.start))}</span>) : 'Timing unavailable'}</div><span className="trace-duration">Duration</span></div>
}

export default function TimelineTrack({ timing, window, status }) {
  const drawing = projectInterval(timing, window)
  const labels = { before: 'Before window', after: 'After window', missing: 'Timing unavailable', invalid: 'Invalid timing' }
  const description = intervalLabel(timing) + (drawing.clippedStart || drawing.clippedEnd ? '; drawing clipped at window edge' : '') + (drawing.kind === 'before' || drawing.kind === 'after' ? `; ${labels[drawing.kind]}` : '')
  return <div className={`timeline-track ${status === 'ERROR' ? 'has-error' : ''}`} data-timing={drawing.kind} title={description} aria-label={description}>
    {labels[drawing.kind] ? <span className="timeline-unavailable">{labels[drawing.kind]}</span> : <>
      {[0, .25, .5, .75, 1].map(part => <span className="timeline-gridline" key={part} style={{ left: `${part * 100}%` }}/>)}
      <span className={`timeline-${drawing.kind}${drawing.clippedStart ? ' clipped-start' : ''}${drawing.clippedEnd ? ' clipped-end' : ''}`} data-left={drawing.left} data-width={drawing.width} style={{ left: `${drawing.left}%`, width: drawing.kind === 'point' ? '2px' : `max(1px, ${drawing.width}%)` }}/>
      {timing.mismatch && <span className="timeline-mismatch">!</span>}
    </>}
  </div>
}
