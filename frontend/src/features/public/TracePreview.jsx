import Icon from '../../components/Icon.jsx'

// An illustration of the trace view, drawn with the product's own tokens (not a
// screenshot): a payment call fails, is retried and succeeds, so the run completes.
const TOTAL = 1840
const rows = [
  { depth: 0, type: 'run', name: 'tool-task-agent', start: 0, end: 1840, status: 'ok' },
  { depth: 1, type: 'agent', name: 'TaskAgent.run', start: 20, end: 1820, status: 'ok' },
  { depth: 2, type: 'model', name: 'model.request · plan', start: 40, end: 380, status: 'ok' },
  { depth: 2, type: 'tool', name: 'inventory.check', start: 400, end: 620, status: 'ok' },
  { depth: 2, type: 'tool', name: 'payment.charge', start: 640, end: 900, status: 'error', note: 'attempt 1', selected: true },
  { depth: 2, type: 'tool', name: 'payment.charge', start: 1180, end: 1420, status: 'ok', note: 'retry · attempt 2' },
  { depth: 2, type: 'tool', name: 'shipment.create', start: 1440, end: 1640, status: 'ok' },
  { depth: 2, type: 'model', name: 'model.request · respond', start: 1660, end: 1800, status: 'ok' },
]
const ms = value => value >= 1000 ? `${(value / 1000).toFixed(2)} s` : `${value} ms`

export default function TracePreview() {
  return <figure className="preview">
    <div className="preview-window" aria-hidden="true">
      <div className="preview-bar">
        <span className="preview-dots"><i/><i/><i/></span>
        <span className="preview-title">Tracing / <span className="mono">4f2a9c1e…</span></span>
        <span className="preview-stats"><span className="preview-status ok">Completed</span><span>8 spans</span><span>1.84 s</span><span className="preview-errors">1 error</span></span>
      </div>
      <div className="preview-body">
        <div className="preview-tree">
          {rows.map((row, index) => <div key={index} className={`preview-row${row.selected ? ' selected' : ''}`}>
            <span className="preview-name" style={{ paddingLeft: row.depth * 16 }}>
              <Icon name={row.type}/><span>{row.name}</span>
              {row.note && <span className="preview-note">{row.note}</span>}
            </span>
            <span className={`preview-dot ${row.status}`}/>
            <span className="preview-track">
              <span className={`preview-span ${row.status === 'error' ? 'error' : ''}`} style={{ left: `${row.start / TOTAL * 100}%`, width: `${(row.end - row.start) / TOTAL * 100}%`, background: row.status === 'error' ? undefined : `var(--type-${row.type})` }}/>
            </span>
            <span className="preview-duration">{ms(row.end - row.start)}</span>
          </div>)}
        </div>
        <div className="preview-inspector">
          <div className="preview-inspector-head"><Icon name="tool"/><strong>payment.charge</strong><span className="preview-status error">Error</span></div>
          <div className="preview-tabs"><span>Input</span><span>Output</span><span>Metadata</span><span className="active">Errors</span></div>
          <pre className="preview-json">{`{
  "type": "GatewayTimeout",
  "message": "payment provider timed out"
}`}</pre>
          <p className="preview-hint">Input <span className="mono">{'{"order": "ORD-100", "attempt": 1}'}</span></p>
        </div>
      </div>
    </div>
    <figcaption>Illustration of the trace view. The first <span className="mono">payment.charge</span> call fails and is retried; the retry succeeds, so the run is <strong>Completed</strong> with one recorded error, not counted as a failed run.</figcaption>
  </figure>
}
