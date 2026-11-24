import { useLayoutEffect, useRef, useState } from 'react'
import Icon from '../../components/Icon.jsx'
import StatusLabel from '../../components/StatusLabel.jsx'
import { useSpanRead } from './useTraceRead.js'
import { durationText, statusText, typeLabel, operationLabel } from './treeModel.js'
import { exactDuration } from '../../app/format.js'
import Timestamp from '../../components/Timestamp.jsx'
import { Popover, PopoverContent, PopoverTrigger } from '../../components/ui/Popover.jsx'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../../components/ui/Tabs.jsx'
import { flagLabels } from '../../data/durableRepository.js'
import Payload from './Payload.jsx'
import JsonView from './JsonView.jsx'
import { breadcrumb, inspectorTabs, spanErrorCount } from './inspectorModel.js'

// Internal tab keys stay stable (URL/cache state); labels follow developer vocabulary.
const tabLabels = { Content: 'Input / Output', Attributes: 'Metadata', Events: 'Events', Errors: 'Errors' }
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

function SpanMetadata({ span, data, ui, patch, copy }) {
  const attributes = data.attributes || {}
  const idRow = (label, value) => value ? <div><dt>{label}</dt><dd><code>{value}</code><button className="trace-icon-button" aria-label={`Copy ${label.toLowerCase()}`} title={`Copy ${label.toLowerCase()}`} onClick={() => copy(value)}><Icon name="copy"/></button></dd></div> : null
  const started = attributes['otel.start_time_unix_nano'], ended = attributes['otel.end_time_unix_nano']
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
      <div><dt>Duration</dt><dd className="tabular" title={exactDuration(span.duration)}>{durationText(span.duration)}</dd></div>
      {typeof started === 'string' && <div><dt>Started</dt><dd><Timestamp value={started}/></dd></div>}
      {typeof ended === 'string' && <div><dt>Ended</dt><dd><Timestamp value={ended}/></dd></div>}
      {facts.map(([label, value]) => <div key={label}><dt>{label}</dt><dd>{value}</dd></div>)}
      {idRow('Span ID', span.id)}
      {idRow('Parent span ID', span.recordedParentId === undefined ? span.parentId : span.recordedParentId)}
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

function SpanContent({ data, span, ui, patch, jump }) {
  const isTool = span.type === 'tool'
  const payloads = [
    { slot: 'input', label: isTool ? 'Arguments' : 'Input', value: data.input, capture: data.inputCapture },
    { slot: 'output', label: isTool ? 'Result' : 'Output', value: data.output, capture: data.outputCapture },
  ]
  const disabled = payloads.every(({ capture }) => capture?.state === 'disabled')
  const disabledReasons = disabled ? [...new Set(payloads.map(({ capture }) => capture.reason).filter(Boolean))] : []
  const capturedFacts = summaryFields.flatMap(([field, label]) => {
    const value = data.attributes?.[field]
    return typeof value === 'number' || (typeof value === 'string' && value.length > 0) ? [[label, value]] : []
  })
  const retries = data.retries || []

  const versions = data.versions?.length > 1 ? data.versions : []
  const structure = (data.flags || []).filter(flag => flag !== 'conflict' && flagLabels[flag])

  return <>
    {versions.length > 0 && <div className="inspector-structure" role="note" aria-label="Conflicting versions">
      <Icon name="error"/>
      <div>
        <strong>{versions.length} conflicting versions received</strong>
        <p>The same span ID arrived with different content. Version 1 is shown below; none is treated as the correct one.</p>
        <ol>{versions.map(version => <li key={version.contentHash}><code title={version.contentHash}>{version.contentHash.slice(0, 12)}</code> · {version.name} · {statusText(version.status)} · received <Timestamp value={version.receivedAt} fallback="time not recorded"/></li>)}</ol>
      </div>
    </div>}
    {structure.length > 0 && <div className="inspector-structure" role="note" aria-label="Structure flags"><Icon name="error"/><div><strong>{structure.map(flag => flagLabels[flag]).join(' · ')}</strong><p>{data.flags.includes('missing_parent') ? <>Recorded parent <code>{data.recordedParentId}</code> is not in this trace, so the span is shown at the top level. </> : null}{data.flags.includes('cycle') ? 'This span is part of a parent cycle. The cycle was cut at one span so the trace can be shown.' : null}</p></div></div>}
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
      <p>Name, type, status and timing are recorded; see Metadata.{data.source === 'durable' ? '' : ' Input/output capture with redaction is planned for durable ingestion.'}</p>
    </div> : <div className="payload-layout">{payloads.map(payload => <Payload key={payload.slot} {...payload} format={ui.formats?.[payload.slot] || 'Readable'} onFormat={format => patch({ formats: { ...ui.formats, [payload.slot]: format } })}/>)}</div>}
  </>
}

function SpanDetails({ span, data, copy }) {
  const inferredEnd = !Object.hasOwn(span, 'end')
  const end = inferredEnd && Number.isFinite(span.start) && Number.isFinite(span.duration) && span.duration >= 0 ? span.start + span.duration : span.end
  const startTime = data?.attributes?.['otel.start_time_unix_nano']
  const endTime = data?.attributes?.['otel.end_time_unix_nano']
  return <Popover>
    <PopoverTrigger><button type="button" className="trace-icon-button" aria-label="Details" title="Span identifiers and timing"><Icon name="info"/></button></PopoverTrigger>
    <PopoverContent className="trace-popover identity-details" align="end">
      <dl>
        <dt>Operation</dt><dd>{span.name}</dd>
        <dt>Span ID</dt><dd><code>{span.id}</code><button className="trace-icon-button" aria-label="Copy span ID" onClick={() => copy(span.id)}><Icon name="copy"/></button></dd>
        <dt>Recorded parent</dt><dd><code>{(span.recordedParentId === undefined ? span.parentId : span.recordedParentId) ?? 'Root'}</code>{span.parentId && <button className="trace-icon-button" aria-label="Copy parent span ID" onClick={() => copy(span.parentId)}><Icon name="copy"/></button>}</dd>
        <dt>Raw status</dt><dd><code>{span.status ?? 'Not recorded'}</code></dd>
        <dt>Start offset</dt><dd>{exactDuration(span.start)}</dd>
        <dt>End offset</dt><dd>{exactDuration(end)}{inferredEnd && Number.isFinite(end) && <span className="secondary"> · start + captured duration</span>}</dd>
        <dt>Captured duration (ms)</dt><dd>{span.duration == null ? 'Not recorded' : String(span.duration)}</dd>
        {typeof startTime === 'string' && <><dt>Start (Unix ns)</dt><dd><code>{startTime}</code></dd></>}
        {typeof endTime === 'string' && <><dt>End (Unix ns)</dt><dd><code>{endTime}</code></dd></>}
      </dl>
    </PopoverContent>
  </Popover>
}

export default function SpanInspector({ repository, projectId, runId, span, path = [], ui, patch, dispatch, single, close, back, jump, inspectorRef }) {
  const { data, busy, error, retry } = useSpanRead(repository, projectId, runId, span.id)
  const body = useRef(null)
  const [copyNotice, setCopyNotice] = useState('')
  const errors = spanErrorCount(span, data)
  const tabs = inspectorTabs(errors)
  const tab = tabs.includes(ui.tab) ? ui.tab : 'Content'
  const readingKey = `${span.id}:${tab}`
  const readingPosition = ui.reading[readingKey] || 0
  const startTime = data?.attributes?.['otel.start_time_unix_nano']
  useLayoutEffect(() => { if (body.current && data) body.current.scrollTop = readingPosition }, [span.id, tab, data, readingPosition])
  async function copy(value) {
    try { await navigator.clipboard.writeText(value); setCopyNotice('Span identifier copied') }
    catch { setCopyNotice(`Copy unavailable. Identifier: ${value}`) }
  }
  function content() {
    if (busy) return <p className="inspector-read-state" role="status">Loading selected span details…</p>
    if (error) return <div className="inspector-read-state" role="alert"><p>{error}</p><button className="button" onClick={retry}>Retry span read</button></div>
    if (!data) return null
    if (tab === 'Content') return <SpanContent data={data} span={span} ui={ui} patch={patch} jump={jump}/>
    if (tab === 'Attributes') return <SpanMetadata span={span} data={data} ui={ui} patch={patch} copy={copy}/>
    if (tab === 'Events') return <div className="inspector-tab-content">{data.events === undefined ? <p>Events unavailable in this capture.</p> : !data.events.length ? <p>No recorded events.</p> : data.events.map((event, index) => <section className="recorded-event" key={index}><h3>{event.name}</h3><p className="secondary">{Number.isFinite(event.atMs) ? `Recorded offset ${durationText(event.atMs)}` : 'Time not recorded'}</p><JsonView value={event.attributes || {}}/></section>)}</div>
    return <div className="inspector-tab-content">{data.error ? <><h3 className="error-text">{data.errorType || 'Recorded error'}</h3><p className="error-detail">{data.error}</p><JsonView value={{ status: data.status, type: data.errorType, message: data.error, recorded_owner: data.errorOwner }}/></> : <p>{data.status === 'ERROR' ? 'ERROR status recorded; exception details unavailable.' : 'No recorded exception details for this span.'}</p>}</div>
  }
  return <section id="span-inspector" className="span-inspector" role="region" aria-label="Span inspector" aria-describedby="span-title" tabIndex="-1" ref={inspectorRef}>
    {single && <button className="inspector-back" onClick={back}><Icon name="back"/>Back to execution</button>}
    <header className="inspector-header">
      <div className="inspector-identity">
        {path.length > 0 && <nav className="inspector-path" aria-label="Span ancestry"><ol>{breadcrumb(path).map((item, position) => <li key={item.span?.id ?? `hidden-${position}`}>{item.span ? <button type="button" className="text-button" onClick={() => jump(item.span.id)} title={`${item.span.name} · ${item.span.id}`}>{operationLabel(item.span)}</button> : <span title={`${item.hidden} more ${item.hidden === 1 ? 'ancestor' : 'ancestors'}`}>…</span>}</li>)}</ol></nav>}
        <div className="inspector-operation" data-type={span.type}><Icon name={span.type}/><h2 id="span-title" title={span.name}>{operationLabel(span)}</h2></div>
        <div className="inspector-meta">
          <StatusLabel state={span.status}>{statusText(span.status)}</StatusLabel>
          <span className="inspector-fact tabular" title={exactDuration(span.duration)}><Icon name="timer"/>{durationText(span.duration)}</span>
          {typeof startTime === 'string' && <span className="inspector-fact"><Icon name="calendar"/><Timestamp value={startTime}/></span>}
          <span className="inspector-fact">{typeLabel(span.type)}</span>
        </div>
      </div>
      <div className="inspector-actions">
        <SpanDetails span={span} data={data} copy={copy}/>
        <button className="trace-icon-button" aria-label="Close span inspector" title="Close inspector (Esc)" onClick={close}><Icon name="close"/></button>
      </div>
    </header>
    <Tabs className="inspector-tabs-root" value={tab} onValueChange={next => patch({ tab: next })}>
      <TabsList className="inspector-tabs" aria-label="Span detail sections">{tabs.map(key => <TabsTrigger key={key} value={key}>{tabLabels[key]}{key === 'Errors' && <span className="tab-count">{errors}</span>}</TabsTrigger>)}</TabsList>
      {/* One panel element for every tab, so the reading position logic keeps one scroll container. */}
      <TabsContent value={tab} className="inspector-body" aria-busy={busy} ref={body} onScroll={event => dispatch({ type: 'read-position', key: readingKey, top: event.currentTarget.scrollTop })}>{content()}</TabsContent>
    </Tabs>
    <span className="sr-only" aria-live="polite">{copyNotice}</span>
  </section>
}
