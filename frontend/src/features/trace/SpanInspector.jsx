import { useLayoutEffect, useRef, useState } from 'react'
import Icon from '../../components/Icon.jsx'
import { useSpanRead } from './useTraceRead.js'
import { durationText, statusText, typeLabel } from './treeModel.js'
import { timeLabel } from './timelineModel.js'
import Payload, { JsonValue } from './Payload.jsx'

const tabs = ['Content', 'Attributes', 'Events', 'Errors']
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
  const attributes = Object.entries(data?.attributes || {}).filter(([key, value]) => (key + ' ' + JSON.stringify(value)).toLowerCase().includes(ui.attributeSearch.toLowerCase()))
  function content() {
    if (busy) return <p className="inspector-read-state" role="status">Loading selected span details…</p>
    if (error) return <div className="inspector-read-state" role="alert"><p>{error}</p><button className="button" onClick={retry}>Retry span read</button></div>
    if (!data) return null
    if (ui.tab === 'Content') return <>
      <div className="payload-controls"><div role="group" aria-label="Payload format">{['Readable', 'JSON'].map(format => <button key={format} className="format-button" aria-pressed={ui.format === format} onClick={() => patch({ format })}>{format === 'JSON' ? 'Captured JSON' : format}</button>)}</div><div><button className="text-button" onClick={() => jumpPayload('input')}>Input ↓</button><button className="text-button" onClick={() => jumpPayload('output')}>Output ↓</button></div>{ui.format === 'JSON' && <label className="trace-check"><input type="checkbox" checked={ui.wrap} onChange={event => patch({ wrap: event.target.checked })}/>Wrap</label>}</div>
      {data.error && <div className="inspector-error"><Icon name="error"/><div><strong>{data.errorType || 'Recorded error'}</strong><p>{data.error}</p></div></div>}
      {(data.retryOf || data.retries.length > 0) && <div className="retry-navigation"><Icon name="retry"/>{data.retryOf && <button className="text-button" onClick={() => jump(data.retryOf.id)}>Open recorded previous attempt · {statusText(data.retryOf.status)}</button>}{data.retries.map(target => <button className="text-button" key={target.id} onClick={() => jump(target.id)} aria-label={`Open recorded retry ${target.name}`}>Recorded retry → {target.name} · {statusText(target.status)}</button>)}</div>}
      <div className={`payload-layout ${(JSON.stringify(data.input)?.length || 0) + (JSON.stringify(data.output)?.length || 0) > 1000 ? 'long-payload' : ''}`}><Payload label="Input" value={data.input} capture={data.inputCapture} format={ui.format} wrap={ui.wrap}/><Payload label="Output" value={data.output} capture={data.outputCapture} format={ui.format} wrap={ui.wrap}/></div>
    </>
    if (ui.tab === 'Attributes') return <div className="inspector-tab-content"><label className="attribute-search">Filter attributes<input type="search" value={ui.attributeSearch} onChange={event => patch({ attributeSearch: event.target.value })}/></label><table className="span-attributes"><tbody>{attributes.map(([key, value]) => <tr key={key}><th scope="row">{key}</th><td><code>{typeof value === 'string' ? value : JSON.stringify(value)}</code></td></tr>)}</tbody></table>{!attributes.length && <p>No matching captured attributes.</p>}</div>
    if (ui.tab === 'Events') return <div className="inspector-tab-content">{data.events === undefined ? <p>Events unavailable in this capture.</p> : !data.events.length ? <p>No recorded events.</p> : data.events.map((event, index) => <section className="recorded-event" key={index}><h3>{event.name}</h3><p className="secondary">{Number.isFinite(event.atMs) ? `Recorded offset ${durationText(event.atMs)}` : 'Time not recorded'}</p><JsonValue value={event.attributes || {}}/></section>)}</div>
    return <div className="inspector-tab-content">{data.error ? <><h3 className="error-text">{data.errorType || 'Recorded error'}</h3><p className="error-detail">{data.error}</p><JsonValue value={{ status: data.status, type: data.errorType, message: data.error, recorded_owner: data.errorOwner }}/></> : <p>{data.status === 'ERROR' ? 'ERROR status recorded; exception details unavailable.' : 'No recorded exception details for this span.'}</p>}</div>
  }
  return <section className="span-inspector" role="region" aria-label="Span inspector" aria-describedby="span-title" tabIndex="-1" ref={inspectorRef}>
    <header className="inspector-header"><div className="inspector-identity"><div className="inspector-operation"><Icon name={span.type}/><h2 id="span-title" title={span.name}>{span.name}</h2></div><div className="inspector-meta"><span>{typeLabel(span.type)}</span><span className={span.status === 'ERROR' ? 'error-text' : ''}>{statusText(span.status)}</span><span className="mono">{durationText(span.duration)}</span><details className="trace-menu"><summary>Details</summary><div className="trace-popover identity-details"><dl><dt>Operation</dt><dd>{span.name}</dd><dt>Span ID</dt><dd><code>{span.id}</code><button className="trace-icon-button" aria-label="Copy span ID" onClick={() => copy(span.id)}><Icon name="copy"/></button></dd><dt>Recorded parent</dt><dd><code>{span.parentId ?? 'Root'}</code>{span.parentId && <button className="trace-icon-button" aria-label="Copy parent span ID" onClick={() => copy(span.parentId)}><Icon name="copy"/></button>}</dd><dt>Raw status</dt><dd><code>{span.status == null ? 'Not recorded' : span.status}</code></dd><dt>Start offset</dt><dd>{timeLabel(span.start)}</dd><dt>End offset</dt><dd>{timeLabel(Object.hasOwn(span, 'end') ? span.end : Number.isFinite(span.start) && Number.isFinite(span.duration) && span.duration >= 0 ? span.start + span.duration : null)}{!Object.hasOwn(span, 'end') && <span className="secondary"> · start + captured duration</span>}</dd><dt>Captured duration (ms)</dt><dd>{span.duration == null ? 'Not recorded' : String(span.duration)}</dd></dl></div></details></div></div>
      <div className="inspector-actions"><button className="trace-icon-button" aria-label="Back to execution" title="Back to execution" onClick={back}><Icon name="back"/></button>{canPin && <button className="trace-icon-button" aria-label={ui.mode === 'pinned' ? 'Unpin span inspector' : 'Pin span inspector'} title={ui.mode === 'pinned' ? 'Unpin inspector' : 'Pin inspector'} aria-pressed={ui.mode === 'pinned'} onClick={pin}><Icon name="pin"/></button>}<details className="trace-menu"><summary className="trace-icon-button" aria-label="Inspector options" title="Inspector options">⋯</summary><div className="trace-popover"><strong>{mode === 'pinned' ? 'Pinned split' : mode === 'single' ? 'Single pane' : 'Overlay'} inspector</strong>{mode !== 'single' && <label>Inspector width<input aria-label="Inspector width" type="range" min="480" max={maxWidth} step="1" value={Math.round(width)} onChange={event => resize(Number(event.target.value))}/><span>{Math.round(width)} px · keyboard splitter steps 16 px</span></label>}{mode !== 'single' && <button className="button small" onClick={resetWidth}>Reset inspector width</button>}<p>Payloads are captured sample values. Raw statuses and recorded relationships are preserved.</p></div></details><button className="trace-icon-button" aria-label="Close span inspector" title="Close inspector" onClick={close}><Icon name="close"/></button></div>
    </header>
    <div className="inspector-tabs" role="tablist" aria-label="Span detail sections">{tabs.map((tab, index) => <button key={tab} role="tab" id={`inspector-tab-${tab}`} aria-controls="inspector-panel" aria-selected={ui.tab === tab} tabIndex={ui.tab === tab ? 0 : -1} onClick={() => patch({ tab })} onKeyDown={event => { const next = { ArrowRight: (index + 1) % tabs.length, ArrowLeft: (index + tabs.length - 1) % tabs.length, Home: 0, End: tabs.length - 1 }[event.key]; if (next !== undefined) { event.preventDefault(); patch({ tab: tabs[next] }); event.currentTarget.parentElement.children[next].focus() } }}>{tab}</button>)}</div>
    <div className="inspector-body" role="tabpanel" id="inspector-panel" aria-labelledby={`inspector-tab-${ui.tab}`} aria-busy={busy} ref={body} onScroll={event => dispatch({ type: 'read-position', key: readingKey, top: event.currentTarget.scrollTop })}>{content()}</div>
    <span className="sr-only" aria-live="polite">{copyNotice}</span>
  </section>
}
