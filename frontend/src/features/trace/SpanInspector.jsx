import { useLayoutEffect, useRef, useState } from 'react'
import Icon from '../../components/Icon.jsx'
import { useSpanRead } from './useTraceRead.js'
import { durationText, statusText, typeLabel, operationLabel } from './treeModel.js'
import { exactDuration } from '../../app/format.js'
import Payload, { JsonValue } from './Payload.jsx'
import { hasCapturedValue } from './capture.js'

const tabs = ['Content', 'Attributes', 'Events', 'Errors']
// Internal tab keys stay stable (URL/cache state); labels follow developer vocabulary.
const tabLabels = { Content: 'Input / Output', Attributes: 'Metadata', Events: 'Events', Errors: 'Errors' }
const formatLabels = { Readable: 'Formatted', JSON: 'Raw' }
// Readable metadata, in display order. Everything else stays in the raw table.
const metadataFields = [
  ['debugger.execution.mode', 'Execution mode'],
  ['debugger.step', 'Step'],
  ['debugger.attempt', 'Attempt'],
  ['debugger.model.name', 'Model'],
  ['debugger.model.provider', 'Provider'],
  ['debugger.result.status', 'Result status'],
  ['http.response.status_code', 'HTTP status'],
  ['resource.service.name', 'Service'],
]
// "2026-11-10 19:53:08.420 UTC" from a Unix-nanosecond string; null when unusable.
export function wallClock(nanos) {
  if (typeof nanos !== 'string' || !/^\d{1,20}$/.test(nanos)) return null
  const date = new Date(Number(BigInt(nanos) / 1000000n))
  return Number.isNaN(date.getTime()) ? null : date.toISOString().replace('T', ' ').replace('Z', ' UTC')
}

function SpanMetadata({ span, data, ui, patch, copy }) {
  const attributes = data.attributes || {}
  const idRow = (label, value) => value ? <div><dt>{label}</dt><dd><code>{value}</code><button className="trace-icon-button" aria-label={`Copy ${label.toLowerCase()}`} title={`Copy ${label.toLowerCase()}`} onClick={() => copy(value)}><Icon name="copy"/></button></dd></div> : null
  const started = wallClock(attributes['otel.start_time_unix_nano']), ended = wallClock(attributes['otel.end_time_unix_nano'])
  const facts = metadataFields.flatMap(([key, label]) => {
    const value = attributes[key]
    return ['string', 'number', 'boolean'].includes(typeof value) && value !== '' ? [[label, String(value)]] : []
  })
  const raw = Object.entries(attributes).filter(([key, value]) => (key + ' ' + JSON.stringify(value)).toLowerCase().includes(ui.attributeSearch.toLowerCase()))
  return <div className="inspector-tab-content">
    <dl className="span-metadata">
      <div><dt>Operation</dt><dd>{span.name}</dd></div>
      <div><dt>Type</dt><dd>{typeLabel(span.type)}</dd></div>
      <div><dt>Status</dt><dd>{statusText(span.status)}</dd></div>
      <div><dt>Duration</dt><dd className="mono" title={exactDuration(span.duration)}>{durationText(span.duration)}</dd></div>
      {started && <div><dt>Started</dt><dd className="mono">{started}</dd></div>}
      {ended && <div><dt>Ended</dt><dd className="mono">{ended}</dd></div>}
      {facts.map(([label, value]) => <div key={label}><dt>{label}</dt><dd>{value}</dd></div>)}
      {idRow('Span ID', span.id)}
      {idRow('Parent span ID', span.parentId)}
      {idRow('Trace ID', attributes['otel.trace_id'])}
    </dl>
    <details className="raw-attributes" open={ui.rawAttributes || undefined} onToggle={event => { if (event.currentTarget.open !== !!ui.rawAttributes) patch({ rawAttributes: event.currentTarget.open }) }}>
      <summary>All recorded attributes <span className="secondary">({Object.keys(attributes).length})</span></summary>
      <label className="attribute-search">Filter attributes<input type="search" value={ui.attributeSearch} onChange={event => patch({ attributeSearch: event.target.value })}/></label>
      <table className="span-attributes"><tbody>{raw.map(([key, value]) => <tr key={key}><th scope="row">{key}</th><td><code>{typeof value === 'string' ? value : JSON.stringify(value)}</code></td></tr>)}</tbody></table>
      {!raw.length && <p>No matching captured attributes.</p>}
    </details>
  </div>
}
const summaryFields = [
  ['debugger.result.status', 'Result status'],
  ['http.response.status_code', 'HTTP status'],
  ['debugger.model.name', 'Model'],
  ['debugger.model.provider', 'Provider'],
]

function SpanContent({ data, span, ui, patch, jump, jumpPayload }) {
  const isTool = span.type === 'tool'
  const payloads = [
    { slot: 'input', label: isTool ? 'Arguments' : 'Input', value: data.input, capture: data.inputCapture },
    { slot: 'output', label: isTool ? 'Result' : 'Output', value: data.output, capture: data.outputCapture },
  ]
  const readable = payloads.filter(({ value, capture }) => hasCapturedValue(value, capture))
  const disabled = payloads.every(({ capture }) => capture?.state === 'disabled')
  const disabledReasons = disabled ? [...new Set(payloads.map(({ capture }) => capture.reason).filter(Boolean))] : []
  const capturedFacts = summaryFields.flatMap(([field, label]) => {
    const value = data.attributes?.[field]
    return typeof value === 'number' || (typeof value === 'string' && value.length > 0) ? [[label, value]] : []
  })
  const retries = data.retries || []

  return <>
    {(data.error || data.errorType || data.status === 'ERROR') && <div className="inspector-error"><Icon name="error"/><div><strong>{data.errorType || 'Recorded error'}</strong><p>{data.error || 'Exception message unavailable.'}</p></div></div>}
    {(data.retryOf || retries.length > 0) && <div className="retry-navigation">
      <Icon name="retry"/>
      <div>
        {data.retryOf && <button className="text-button" onClick={() => jump(data.retryOf.id)}>Recorded previous → {operationLabel(data.retryOf)} · {statusText(data.retryOf.status)}</button>}
        {retries.map(target => <button className="text-button" key={target.id} onClick={() => jump(target.id)} aria-label={`Open recorded retry ${operationLabel(target)}`}>Recorded retry → {operationLabel(target)} · {statusText(target.status)}</button>)}
      </div>
    </div>}
    {capturedFacts.length > 0 && <dl className="span-summary-facts">{capturedFacts.map(([label, value]) => <div key={label}><dt>{label}</dt><dd>{value}</dd></div>)}</dl>}
    {disabled ? <div className="payload-disabled">
      <strong>Input and output not captured</strong>
      {disabledReasons.map(reason => <p key={reason}>{reason}</p>)}
      <p>Name, type, status and timing are recorded; see Metadata. Input/output capture with redaction is planned for durable ingestion.</p>
    </div> : <>
      {readable.length > 0 && <div className="payload-controls">
        <div role="group" aria-label="Payload format">{['Readable', 'JSON'].map(format => <button key={format} className="format-button" aria-pressed={ui.format === format} onClick={() => patch({ format })}>{formatLabels[format]}</button>)}</div>
        {readable.length > 1 && <div>{readable.map(({ slot, label }) => <button className="text-button" key={slot} onClick={() => jumpPayload(slot)}>{label} ↓</button>)}</div>}
        {ui.format === 'JSON' && <label className="trace-check"><input type="checkbox" checked={ui.wrap} onChange={event => patch({ wrap: event.target.checked })}/>Wrap</label>}
      </div>}
      <div className={`payload-layout ${readable.reduce((total, { value }) => total + (JSON.stringify(value)?.length || 0), 0) > 1000 ? 'long-payload' : ''}`}>{payloads.map(payload => <Payload key={payload.slot} {...payload} format={ui.format} wrap={ui.wrap}/>)}</div>
    </>}
  </>
}

function SpanDetails({ span, data, copy }) {
  const inferredEnd = !Object.hasOwn(span, 'end')
  const end = inferredEnd && Number.isFinite(span.start) && Number.isFinite(span.duration) && span.duration >= 0 ? span.start + span.duration : span.end
  const startTime = data?.attributes?.['otel.start_time_unix_nano']
  const endTime = data?.attributes?.['otel.end_time_unix_nano']
  return <details className="trace-menu">
    <summary>Details</summary>
    <div className="trace-popover identity-details">
      <dl>
        <dt>Operation</dt><dd>{span.name}</dd>
        <dt>Span ID</dt><dd><code>{span.id}</code><button className="trace-icon-button" aria-label="Copy span ID" onClick={() => copy(span.id)}><Icon name="copy"/></button></dd>
        <dt>Recorded parent</dt><dd><code>{span.parentId ?? 'Root'}</code>{span.parentId && <button className="trace-icon-button" aria-label="Copy parent span ID" onClick={() => copy(span.parentId)}><Icon name="copy"/></button>}</dd>
        <dt>Raw status</dt><dd><code>{span.status ?? 'Not recorded'}</code></dd>
        <dt>Start offset</dt><dd>{exactDuration(span.start)}</dd>
        <dt>End offset</dt><dd>{exactDuration(end)}{inferredEnd && Number.isFinite(end) && <span className="secondary"> · start + captured duration</span>}</dd>
        <dt>Captured duration (ms)</dt><dd>{span.duration == null ? 'Not recorded' : String(span.duration)}</dd>
        {typeof startTime === 'string' && <><dt>Start (Unix ns)</dt><dd><code>{startTime}</code></dd></>}
        {typeof endTime === 'string' && <><dt>End (Unix ns)</dt><dd><code>{endTime}</code></dd></>}
      </dl>
    </div>
  </details>
}

export default function SpanInspector({ repository, projectId, runId, span, ui, patch, dispatch, mode, width, maxWidth, canPin, pin, close, back, resize, resetWidth, jump, inspectorRef }) {
  const { data, busy, error, retry } = useSpanRead(repository, projectId, runId, span.id)
  const body = useRef(null)
  const [copyNotice, setCopyNotice] = useState('')
  const readingKey = `${span.id}:${ui.tab}:${ui.format}`
  const readingPosition = ui.reading[readingKey] || 0
  useLayoutEffect(() => { if (body.current && data) body.current.scrollTop = readingPosition }, [span.id, ui.tab, ui.format, data, readingPosition])
  async function copy(value) {
    try { await navigator.clipboard.writeText(value); setCopyNotice('Span identifier copied') }
    catch { setCopyNotice(`Copy unavailable. Identifier: ${value}`) }
  }
  function jumpPayload(direction) {
    const target = body.current.querySelector(`[data-payload="${direction}"]`)
    if (target) body.current.scrollTop += target.getBoundingClientRect().top - body.current.getBoundingClientRect().top - 44
  }
  function content() {
    if (busy) return <p className="inspector-read-state" role="status">Loading selected span details…</p>
    if (error) return <div className="inspector-read-state" role="alert"><p>{error}</p><button className="button" onClick={retry}>Retry span read</button></div>
    if (!data) return null
    if (ui.tab === 'Content') return <SpanContent data={data} span={span} ui={ui} patch={patch} jump={jump} jumpPayload={jumpPayload}/>
    if (ui.tab === 'Attributes') return <SpanMetadata span={span} data={data} ui={ui} patch={patch} copy={copy}/>
    if (ui.tab === 'Events') return <div className="inspector-tab-content">{data.events === undefined ? <p>Events unavailable in this capture.</p> : !data.events.length ? <p>No recorded events.</p> : data.events.map((event, index) => <section className="recorded-event" key={index}><h3>{event.name}</h3><p className="secondary">{Number.isFinite(event.atMs) ? `Recorded offset ${durationText(event.atMs)}` : 'Time not recorded'}</p><JsonValue value={event.attributes || {}}/></section>)}</div>
    return <div className="inspector-tab-content">{data.error ? <><h3 className="error-text">{data.errorType || 'Recorded error'}</h3><p className="error-detail">{data.error}</p><JsonValue value={{ status: data.status, type: data.errorType, message: data.error, recorded_owner: data.errorOwner }}/></> : <p>{data.status === 'ERROR' ? 'ERROR status recorded; exception details unavailable.' : 'No recorded exception details for this span.'}</p>}</div>
  }
  return <section className="span-inspector" role="region" aria-label="Span inspector" aria-describedby="span-title" tabIndex="-1" ref={inspectorRef}>
    {mode === 'single' && <button className="inspector-back" onClick={back}><Icon name="back"/>Back to execution</button>}
    <header className="inspector-header">
      <div className="inspector-identity">
        <p className="section-label">Selected span</p>
        <div className="inspector-operation" data-type={span.type}><Icon name={span.type}/><h2 id="span-title" title={span.name}>{operationLabel(span)}</h2></div>
        <div className="inspector-meta">
          <span>{typeLabel(span.type)}</span>
          <span className="badge" data-state={span.status}>{statusText(span.status)}</span>
          <span className="mono">{durationText(span.duration)}</span>
          <SpanDetails span={span} data={data} copy={copy}/>
        </div>
      </div>
      <div className="inspector-actions">
        {mode !== 'single' && <button className="trace-icon-button" aria-label="Back to execution" title="Back to execution" onClick={back}><Icon name="back"/></button>}
        {canPin && <button className="trace-icon-button" aria-label={ui.mode === 'pinned' ? 'Unpin span inspector' : 'Pin span inspector'} title={ui.mode === 'pinned' ? 'Unpin inspector' : 'Pin inspector'} aria-pressed={ui.mode === 'pinned'} onClick={pin}><Icon name="pin"/></button>}
        <details className="trace-menu">
          <summary className="trace-icon-button" aria-label="Inspector options" title="Inspector options">⋯</summary>
          <div className="trace-popover">
            <strong>{mode === 'pinned' ? 'Pinned split' : mode === 'single' ? 'Single pane' : 'Overlay'} inspector</strong>
            {mode !== 'single' && <>
              <label>Inspector width<input aria-label="Inspector width" type="range" min="480" max={maxWidth} step="1" value={Math.round(width)} onChange={event => resize(Number(event.target.value))}/><span>{Math.round(width)} px · keyboard splitter steps 16 px</span></label>
              <button className="button small" onClick={resetWidth}>Reset inspector width</button>
            </>}
            <p>Only available captured values are displayed. Raw statuses and recorded relationships are preserved.</p>
          </div>
        </details>
        <button className="trace-icon-button" aria-label="Close span inspector" title="Close inspector" onClick={close}><Icon name="close"/></button>
      </div>
    </header>
    <div className="inspector-tabs" role="tablist" aria-label="Span detail sections">{tabs.map((tab, index) => <button key={tab} role="tab" id={`inspector-tab-${tab}`} aria-controls="inspector-panel" aria-selected={ui.tab === tab} tabIndex={ui.tab === tab ? 0 : -1} onClick={() => patch({ tab })} onKeyDown={event => { const next = { ArrowRight: (index + 1) % tabs.length, ArrowLeft: (index + tabs.length - 1) % tabs.length, Home: 0, End: tabs.length - 1 }[event.key]; if (next !== undefined) { event.preventDefault(); patch({ tab: tabs[next] }); event.currentTarget.parentElement.children[next].focus() } }}>{tabLabels[tab]}</button>)}</div>
    <div className="inspector-body" role="tabpanel" id="inspector-panel" aria-labelledby={`inspector-tab-${ui.tab}`} aria-busy={busy} ref={body} onScroll={event => dispatch({ type: 'read-position', key: readingKey, top: event.currentTarget.scrollTop })}>{content()}</div>
    <span className="sr-only" aria-live="polite">{copyNotice}</span>
  </section>
}
