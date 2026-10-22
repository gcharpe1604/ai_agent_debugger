import { useLayoutEffect, useState } from 'react'
import { evidenceHref } from '../../app/routes.jsx'
import { assignSource, evidenceQuery, initialEvidenceState } from './evidenceState.js'
import SourcePane from './SourcePane.jsx'

export default function EvidenceWorkspace({ repository, projectId, runId, attempt, finding, search, cache }) {
  const key = `${projectId}/${runId}/${attempt.id}/${finding.id}`
  const [ui, setUI] = useState(() => initialEvidenceState(search, finding.citations, cache.get(key)))
  const [focusRequest, setFocusRequest] = useState({ slot: null, revision: 0 })
  useLayoutEffect(() => { cache.set(key, ui) }, [cache, key, ui])
  function patch(value) { setUI(previous => ({ ...previous, ...(typeof value === 'function' ? value(previous) : value) })) }
  function query(next) {
    return evidenceQuery(search, { Attempt: attempt.id, Finding: finding.id, A: next.a, B: next.b, Focus: next.focus })
  }
  function navigate(next) {
    setUI(next)
    window.history.replaceState(null, '', evidenceHref(projectId, runId, query(next)))
    window.dispatchEvent(new HashChangeEvent('hashchange'))
  }
  function assign(slot, id, requestFocus = false) {
    const next = assignSource(ui, slot, id)
    if (requestFocus && ui.focus) next.focus = slot
    navigate(next)
    if (requestFocus) setFocusRequest(previous => ({ slot, revision: previous.revision + 1 }))
  }
  function focus(slot) {
    navigate({ ...ui, focus: slot })
    setFocusRequest(previous => ({ slot: slot || 'a', revision: previous.revision + 1 }))
  }
  const citations = finding.citations
  return <div className="evidence-workspace">
    <div className="finding-detail"><div className="finding-eyebrow"><span>{finding.id} · {finding.category}</span><span className="finding-priority">{finding.priority} priority</span></div><h2>{finding.title}</h2><p>{finding.explanation}</p><p className="finding-limitation"><span aria-hidden="true">ⓘ</span> {finding.limitation}</p></div>
    <nav className="evidence-citations" aria-label="Finding citations"><span>Citations</span>{citations.map((citation, index) => <button className="button small" key={citation.id} aria-label={`Assign citation ${index + 1} ${citation.label} to Source A`} aria-pressed={ui.a === citation.id} onClick={() => assign('a', citation.id, true)}>{index + 1} · {citation.label}{(ui.a === citation.id || ui.b === citation.id) && <span className="citation-slot">{ui.a === citation.id ? 'A' : 'B'}</span>}</button>)}{ui.focus && <button className="text-button compare-action" onClick={() => focus(null)}>Compare sources</button>}</nav>
    {citations.length ? <div className="evidence-sources" data-focused={!!ui.focus} data-single={citations.length === 1}>
      {['a', ...(citations.length > 1 ? ['b'] : [])].map(slot => <SourcePane key={slot} repository={repository} projectId={projectId} runId={runId} attempt={attempt} finding={finding} citations={citations} citationId={ui[slot]} slot={slot} ui={ui} patch={patch} assign={id => assign(slot, id)} focus={() => focus(ui.focus ? null : slot)} focusRequest={focusRequest.slot === slot ? focusRequest.revision : 0} search={query(ui)}/>) }
    </div> : <div className="boundary"><h3>No cited sources supplied</h3><p>This finding has no source available for inspection.</p></div>}
  </div>
}
