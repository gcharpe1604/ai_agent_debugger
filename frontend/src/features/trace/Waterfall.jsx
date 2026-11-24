import { exactDuration } from '../../app/format.js'
import { durationText } from './treeModel.js'
import { waterfallPosition } from './timelineModel.js'

// Duration cell: a mini waterfall (offset and length on the trace) plus the value.
export default function DurationBar({ span, timing, extent, className = 'trace-duration' }) {
  const position = waterfallPosition(timing, extent)
  const share = position ? ` · starts at ${(position.left * 100).toFixed(1)}%, ${(position.width * 100).toFixed(1)}% of the trace` : ''
  return <span className={className} title={`${exactDuration(span.duration)}${share}`}>
    <span className="waterfall" aria-hidden="true">{position && <span className="waterfall-bar" data-error={span.status === 'ERROR' || undefined} style={{ '--left': position.left, '--width': position.width }}/>}</span>
    <span className="waterfall-value tabular">{durationText(span.duration)}</span>
  </span>
}
