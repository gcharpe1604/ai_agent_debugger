import { useRef } from 'react'
import Tooltip from '../../components/ui/Tooltip.jsx'
import { formatTimestamp } from '../../app/format.js'
import { useElementSize } from '../trace/useElementSize.js'

const HEIGHT = 200, LEFT = 36, BOTTOM = 24, TOP = 8
const label = (bucket, withTime) => formatTimestamp(bucket.start, withTime ? { withSeconds: false } : { time: false })

// Stacked bars per time bucket: completed (bottom), failed, then other
// outcomes. Each bar has a tooltip with its counts and is reachable by Tab.
export default function TracesChart({ buckets }) {
  const box = useRef(null)
  const { width } = useElementSize(box, { width: 800, height: HEIGHT })
  if (!buckets.some(bucket => bucket.total)) return <div ref={box} className="chart-empty"><p>No traces in this time range.</p></div>
  const hourly = buckets[0].unit === 'hour'
  const max = Math.max(1, ...buckets.map(bucket => bucket.total))
  const ticks = max <= 4 ? Array.from({ length: max + 1 }, (_, i) => i) : [0, Math.round(max / 2), max]
  const inner = Math.max(1, width - LEFT - 8), plot = HEIGHT - TOP - BOTTOM
  const slot = inner / buckets.length, bar = Math.max(2, Math.min(40, slot * 0.7))
  const y = value => TOP + plot - (value / max) * plot
  const every = Math.max(1, Math.ceil(buckets.length / Math.max(2, Math.floor(inner / (hourly ? 96 : 56)))))
  return <div ref={box} className="traces-chart">
    <svg width="100%" height={HEIGHT} viewBox={`0 0 ${Math.max(width, 1)} ${HEIGHT}`} role="img" aria-label={`Traces over time: ${buckets.reduce((sum, bucket) => sum + bucket.total, 0)} traces in ${buckets.length} ${hourly ? 'hours' : 'days'}`}>
      {ticks.map(tick => <g key={tick} className="chart-grid">
        <line x1={LEFT} x2={LEFT + inner} y1={y(tick)} y2={y(tick)}/>
        <text x={LEFT - 8} y={y(tick)} dy="0.32em" textAnchor="end">{tick}</text>
      </g>)}
      {buckets.map((bucket, index) => {
        const x = LEFT + index * slot + (slot - bar) / 2
        const parts = [['completed', bucket.completed], ['failed', bucket.failed], ['other', bucket.other]]
        let base = 0
        const name = `${label(bucket, hourly)}: ${bucket.completed} completed, ${bucket.failed} failed${bucket.other ? `, ${bucket.other} other` : ''}`
        return <Tooltip key={bucket.start} content={name}>
          <g className="chart-bar" tabIndex={bucket.total ? 0 : -1} aria-label={name} data-bucket={bucket.start}>
            <rect className="chart-hit" x={LEFT + index * slot} y={TOP} width={slot} height={plot}/>
            {parts.map(([kind, count]) => { if (!count) return null; const top = y(base + count), rect = <rect key={kind} className={`chart-${kind}`} x={x} y={top} width={bar} height={y(base) - top}/>; base += count; return rect })}
          </g>
        </Tooltip>
      })}
      {buckets.map((bucket, index) => index % every === 0 && <text key={bucket.start} className="chart-axis" x={LEFT + index * slot + slot / 2} y={HEIGHT - 6} textAnchor="middle">{label(bucket, hourly)}</text>)}
    </svg>
    <ul className="chart-legend" aria-hidden="true"><li data-kind="completed">Completed</li><li data-kind="failed">Failed</li>{buckets.some(bucket => bucket.other) && <li data-kind="other">Other</li>}</ul>
  </div>
}
