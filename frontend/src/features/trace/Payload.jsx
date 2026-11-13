import { useState } from 'react'
import Icon from '../../components/Icon.jsx'
import { captureLabels, hasCapturedValue } from './capture.js'

export function JsonValue({ value, wrap = true }) {
  return <pre className={`captured-json ${wrap ? 'wrap' : ''}`}><code>{JSON.stringify(value, null, 2) ?? 'Unavailable'}</code></pre>
}
function Readable({ value }) {
  if (typeof value === 'string' && value.length) return <div className="readable-prose">{value.split('\n\n').map((text, index) => <p key={index}>{text}</p>)}</div>
  if (value === null || typeof value !== 'object' || Array.isArray(value) || !Object.keys(value).length) return <span className="payload-value mono">{JSON.stringify(value)}</span>
  return <dl className="payload-fields">{Object.entries(value).map(([key, item]) => <div key={key} className={(typeof item === 'string' && item.length > 200) || (key === 'messages' && Array.isArray(item)) ? 'payload-long-field' : undefined}><dt>{key}</dt><dd>{key === 'messages' && Array.isArray(item) ? item.map((message, index) => <CapturedMessage key={index} message={message}/>) : typeof item === 'object' && item !== null ? <JsonValue value={item}/> : <Readable value={item}/>}</dd></div>)}</dl>
}

function CapturedMessage({ message }) {
  if (!message || typeof message.role !== 'string' || !Object.hasOwn(message, 'content')) return <JsonValue value={message}/>
  const { role, content, ...additionalFields } = message
  return <div className="captured-message">
    <strong>{role || 'Role unavailable'}</strong>
    <Readable value={content}/>
    {Object.keys(additionalFields).length > 0 && <Readable value={additionalFields}/>}
  </div>
}

export default function Payload({ label, slot = label.toLowerCase(), value, capture, format, wrap }) {
  const [notice, setNotice] = useState('')
  const state = capture?.state || 'unavailable'
  const canRead = hasCapturedValue(value, capture)
  async function copy() {
    try { await navigator.clipboard.writeText(typeof value === 'string' ? value : JSON.stringify(value, null, 2)); setNotice(`${label} captured value copied`) }
    catch { setNotice('Clipboard unavailable. Select and copy the displayed captured value.') }
  }
  return <section className="payload-section" data-payload={slot}>
    <div className="payload-heading"><h3>{label}</h3><span>{captureLabels[state] || 'Capture state unknown'}{canRead && <button className="trace-icon-button" onClick={copy} aria-label={`Copy captured ${label.toLowerCase()}`} title={`Copy captured ${label.toLowerCase()}`}><Icon name="copy"/></button>}</span></div>
    {capture?.reason && <p className="capture-reason">{capture.reason}</p>}
    {canRead ? format === 'JSON' ? <JsonValue value={value} wrap={wrap}/> : <Readable value={value}/> : !capture?.reason && <p className="payload-unavailable">Reason not recorded.</p>}
    <span className="sr-only" aria-live="polite">{notice}</span>
  </section>
}
