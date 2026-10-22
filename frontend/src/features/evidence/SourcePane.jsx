import { useLayoutEffect, useRef, useState } from 'react'
import { runsHref } from '../../app/routes.jsx'
import { useEvidenceRead } from './useInvestigationRead.js'
import { resolveCitation } from './evidenceState.js'
import CapturedEvidence from './CapturedEvidence.jsx'

function ReadingRegion({ position, save, children }) {
  const ref = useRef(null)
  useLayoutEffect(() => { ref.current.scrollTop = position }, [position])
  return <div ref={ref} className="evidence-reading" role="region" aria-label="Captured source content" tabIndex="0" onScroll={event => save(event.currentTarget.scrollTop)}>{children}</div>
}
export default function SourcePane({ repository, projectId, runId, attempt, citations, citationId, slot, ui, patch, assign, focus, focusRequest, search }) {
  const citation = citations.find(item => item.id === citationId)
  const { data, busy, error, retry } = useEvidenceRead(repository, projectId, runId, attempt.id, citationId)
  const result = resolveCitation(citation || {}, data, attempt.snapshotId)
  const letter = slot.toUpperCase(), hidden = !!ui.focus && ui.focus !== slot
  const heading = useRef(null), [notice, setNotice] = useState('')
  const format = ui.formats[citationId] || 'Readable'
  const readingKey = `${citationId}:${ui.focus ? 'focused' : 'paired'}:${format}`
  useLayoutEffect(() => { if (focusRequest && !hidden) heading.current?.focus({ preventScroll: true }) }, [focusRequest, hidden])
  const traceParams = new URLSearchParams(search)
  traceParams.set('span', citation?.spanId || '')
  if (!['overlay', 'pinned'].includes(traceParams.get('panel'))) traceParams.set('panel', 'overlay')
  async function copy() {
    try { await navigator.clipboard.writeText(typeof data.value === 'string' ? data.value : JSON.stringify(data.value, null, 2)); setNotice(`Source ${letter} captured value copied`) }
    catch { setNotice('Clipboard unavailable. Select the captured text to copy it.') }
  }
  return <section className="source-pane" role="region" aria-label={`Source ${letter}`} hidden={hidden}>
    <div className="source-assignment"><label><span>{slot === 'a' ? 'Left · A' : 'Right · B'}</span><select aria-label={`Source ${letter} citation`} value={citationId || ''} onChange={event => assign(event.target.value)}>{!citation && <option value={citationId || ''}>Requested citation unavailable</option>}{citations.map((item, index) => <option value={item.id} key={item.id}>{index + 1} · {item.label}</option>)}</select></label>{citations.length > 1 && <button className="trace-icon-button" aria-label={ui.focus ? 'Restore source comparison' : `Focus source ${letter}`} title={ui.focus ? 'Compare sources' : `Focus source ${letter}`} onClick={focus}>{ui.focus ? '⊟' : '⛶'}</button>}</div>
    {!citation ? <div className="source-unavailable"><h3 ref={heading} tabIndex="-1">Citation unavailable</h3><p>The requested source is not in this finding. Select an explicitly supplied citation above.</p></div> : <>
      <div className="source-identity"><div><h3 ref={heading} tabIndex="-1">{citation.title}</h3><span>{citation.revision || citation.kind}</span><details data-inline><summary>Details</summary><div><p>Source <span className="mono">{citation.id}</span></p><p>{citation.spanId ? 'Span' : 'Document'} <span className="mono">{citation.spanId || citation.documentId}</span></p><p>Analyzed <span className="mono">{attempt.snapshotId}</span></p>{data?.snapshotId && <p>Resolved source <span className="mono">{data.snapshotId}</span></p>}{citation.effective && <p>Effective {citation.effective}</p>}</div></details></div><p className="mono source-field">{citation.field}</p></div>
      {busy ? <div className="source-unavailable" role="status">Loading captured source {letter}…</div> : error ? <div className="source-unavailable"><p role="alert">{error}</p><button className="button small" onClick={retry}>Retry source {letter}</button></div> : !result.available ? <div className="source-unavailable"><strong>Evidence unavailable</strong><p role="status">{result.reason}</p></div> : <>
        <div className="source-cited"><span title={`${data.state} source`}>Cited value</span>{result.resolved ? <mark className="mono">{data.displayValue ?? (typeof data.citedValue === 'string' ? data.citedValue : JSON.stringify(data.citedValue))}</mark> : <strong className="source-unresolved">Unresolved</strong>}<select aria-label={`Source ${letter} presentation`} value={format} onChange={event => { const mode = event.target.value; patch(previous => ({ formats: { ...previous.formats, [citationId]: mode } })) }}><option value="Readable">Readable</option><option value="JSON">Captured JSON</option></select><button className="text-button" onClick={copy} aria-label={`Copy source ${letter}`}>Copy source</button></div>
        {!result.resolved && <p className="source-resolution-warning">Cited value could not be resolved in this captured source. No guessed highlight is shown.</p>}
        {!hidden && <ReadingRegion key={readingKey} position={ui.reading[readingKey] || 0} save={top => patch(previous => ({ reading: { ...previous.reading, [readingKey]: top } }))}>
          {data.state !== 'captured' && <p className="capture-reason">{data.state === 'redacted' ? 'Redacted captured source' : 'Truncated captured source'}</p>}
          {data.reason && <p className="capture-reason">{data.reason}</p>}
          <CapturedEvidence source={data} citation={citation} resolved={result.resolved} format={format}/>
          {data.context && <details className="source-context" data-inline open={!!ui.context[citationId]} onToggle={event => { const open = event.currentTarget.open; if (open !== !!ui.context[citationId]) patch(previous => ({ context: { ...previous.context, [citationId]: open } })) }}><summary>Surrounding context</summary><div className="readable-prose">{data.context.split('\n\n').map((paragraph, index) => <p key={index}>{paragraph}</p>)}</div></details>}
          {citation.effective && <p className="source-effective">Effective {citation.effective} · Fixed analyzed revision</p>}
        </ReadingRegion>}
      </>}
      <footer className="source-footer">{citation.spanId ? <><span>Historical inspection unavailable</span><a href={runsHref(projectId, traceParams.toString(), runId)}>Open current span <span aria-hidden="true">→</span></a></> : <span>Fixed document passage · read only</span>}</footer>
    </>}
    <span className="sr-only" role="status">{notice}</span>
  </section>
}
