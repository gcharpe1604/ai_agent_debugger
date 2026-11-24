import { useState } from 'react'
import Icon from '../../components/Icon.jsx'
import { captureLabels, hasCapturedValue } from './capture.js'
import JsonView from './JsonView.jsx'

// Raw JSON, always wrapped so long values never scroll sideways.
export function JsonValue({ value }) {
  return <pre className="captured-json wrap"><code>{JSON.stringify(value, null, 2) ?? 'Unavailable'}</code></pre>
}

// One captured payload (Input, Output, Arguments, Result) with its own
// Formatted/Raw toggle and copy button. `format` is 'Readable' (Formatted) or
// 'JSON' (Raw); pass `onFormat` to keep the choice outside this panel.
export default function Payload({ label, slot = label.toLowerCase(), value, capture, format = 'Readable', onFormat }) {
  const [notice, setNotice] = useState('')
  const [local, setLocal] = useState(format)
  const current = onFormat ? format : local
  const choose = onFormat || setLocal
  const state = capture?.state || 'unavailable'
  const canRead = hasCapturedValue(value, capture)
  async function copy() {
    try { await navigator.clipboard.writeText(typeof value === 'string' ? value : JSON.stringify(value, null, 2)); setNotice(`${label} captured value copied`) }
    catch { setNotice('Clipboard unavailable. Select and copy the displayed captured value.') }
  }
  return <section className="payload-section" data-payload={slot} aria-label={label}>
    <div className="payload-heading">
      <h3>{label}</h3>
      <span className="payload-state" data-state={state}>{captureLabels[state] || 'Capture state unknown'}</span>
      {canRead && <div className="payload-tools">
        <div className="segmented small" role="group" aria-label={`${label} format`}>{[['Readable', 'Formatted'], ['JSON', 'Raw']].map(([key, text]) => <button key={key} type="button" aria-pressed={current === key} onClick={() => choose(key)}>{text}</button>)}</div>
        <button type="button" className="trace-icon-button" onClick={copy} aria-label={`Copy captured ${label.toLowerCase()}`} title={`Copy captured ${label.toLowerCase()}`}><Icon name="copy"/></button>
      </div>}
    </div>
    {capture?.reason && <p className="capture-reason">{capture.reason}</p>}
    {canRead ? current === 'JSON' ? <JsonValue value={value}/> : <JsonView value={value}/> : !capture?.reason && <p className="payload-unavailable">Reason not recorded.</p>}
    <span className="sr-only" aria-live="polite">{notice}</span>
  </section>
}
