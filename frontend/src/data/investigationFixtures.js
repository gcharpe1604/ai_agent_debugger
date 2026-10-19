import { authoredTraces } from './authoredTraces.js'
import { runs } from './fixtures.js'

// Authored client view models, NOT an investigator result or proposed citation/API schema.
const clone = value => JSON.parse(JSON.stringify(value))
function freeze(value) {
  if (value && typeof value === 'object') { Object.values(value).forEach(freeze); Object.freeze(value) }
  return value
}
const span = (number, key) => authoredTraces.find(run => run.label === `R-${number}`).spans.find(item => item.key === key)
const captured = (number, key, field) => clone(span(number, key)[field])
const citation = (id, label, title, kind, field, extra = {}) => ({ id, label, title, kind, field, ...extra })
const traceCitation = (number, id, label, key, direction, path) => citation(id, label, span(number, key).name, span(number, key).type, `${direction}.${path.join('.')}`, { spanId: span(number, key).id, path })
const source = (snapshotId, value, extra = {}) => ({ snapshotId, state: 'captured', value, ...extra })
const limitation = 'Policy applicability and any approved exception require confirmation. These references alone do not prove a causal root cause.'
const authority = {
  text: 'Customers may request a refund within 14 days of delivery. Requests outside this window require a documented exception approved by the support lead.',
  context: [
    'Scope. Applies to standard retail orders. Subscription renewals and damaged goods are covered by separate policies. The delivery date recorded by the fulfillment service starts the refund window; the order creation date does not substitute for it.',
    'Exceptions. A request outside the standard window requires a documented exception approved by the support lead. The approval must identify the order and the reason for the exception. A model recommendation or a cached policy excerpt is not an exception approval. No exception approval was supplied to this authored analysis.',
    'Source revision. This passage belongs to Revision 7, effective 1 October 2026. Earlier cached excerpts can describe a different refund window. Reviewers must confirm the policy revision and its applicability to the order before deciding that a discrepancy establishes an incorrect business outcome.',
    'Required review. Confirm the delivery date, the policy applicable to the item and any recorded exception. If the supplied records omit one of these facts, report the missing information. Do not infer an approved exception from a completed execution, a successful tool response or an approved refund message.',
    'Record retention. Preserve the policy passage and its revision with the reviewed decision. A newer document is useful for a separate current-policy check, but must not replace a historical cited passage. Where the analyzed revision is inaccessible, identify the source as unavailable and keep other captured evidence inspectable.',
  ].join('\n\n'),
}
const documentCitation = citation('document', 'Authoritative passage', 'Refund policy', 'Document', '§ 2.1 · Standard refund window', { documentId: 'policy-refunds-v7', revision: 'Revision 7', effective: '2026-10-01', quote: 'within 14 days of delivery', range: { start: 31, end: 57 } })
// Use an exact captured range. The renderer validates both offsets and quote.
documentCitation.range = { start: authority.text.indexOf(documentCitation.quote), end: authority.text.indexOf(documentCitation.quote) + documentCitation.quote.length }

function build(run) {
  const number = Number(run.id.slice(2)), snapshotId = `snap-${number}-a`
  const base = { run, state: run.investigation, attempts: [], sources: {} }
  if (['Not requested', 'Skipped'].includes(run.investigation)) return base
  const attempt = { id: `analysis-${number}-1`, label: 'Attempt 1', state: run.investigation, snapshotId, referenceState: 'Not provided', limitations: 'Authored presentation fixture; no investigator was run.', findings: [] }
  base.attempts.push(attempt)
  if (run.investigation === 'Failed') { attempt.error = 'Investigation could not be completed. Trace data remains available.'; return base }
  if (run.investigation === 'Pending') { attempt.limitations = 'No diagnosis is available while this supplied attempt is pending.'; return base }
  if (number === 1042) {
    const citations = [traceCitation(number, 'retrieval', 'Retrieval output', 'retrieve', 'output', ['refund_window_days']), documentCitation, traceCitation(number, 'model', 'Model input', 'compose', 'input', ['refund_window_days'])]
    attempt.referenceState = 'References verified'
    attempt.limitations = limitation
    attempt.findings = [{ id: 'F-01', title: 'Retrieved policy differs from the authoritative source', category: 'Context mismatch', priority: 'High', explanation: 'Retrieval supplied a 30-day window. The cited policy states 14 days; the 21-day order was approved using the retrieved value.', limitation, citations }]
    base.sources[attempt.id] = {
      retrieval: source(snapshotId, captured(number, 'retrieve', 'output'), { citedValue: 30, displayValue: '30 days' }),
      model: source(snapshotId, captured(number, 'compose', 'input'), { citedValue: 30, displayValue: '30 days' }),
      document: source(snapshotId, authority.text, { citedValue: documentCitation.quote, displayValue: '14 days', context: authority.context }),
    }
    // Explicit earlier authored review attempt: demonstrates retained history,
    // multiple findings, one-source reading and missing/mismatched evidence.
    const prior = { id: 'analysis-1042-0', label: 'Earlier review sample', state: 'Completed', snapshotId: 'snap-1042-prior', referenceState: 'Unavailable', limitations: 'Historical source retention is incomplete in this review fixture.', findings: [
      { id: 'F-01', title: 'Historical policy citation is unavailable', category: 'Context review', priority: 'Medium', explanation: 'This earlier authored finding refers to a fixed policy passage whose captured value is unavailable.', limitation: 'The current policy must not substitute for the missing analyzed revision.', citations: [citation('prior-document', 'Historical passage', 'Refund policy', 'Document', '§ 2.1 · Standard refund window', { documentId: 'policy-refunds-v6', revision: 'Revision 6' })] },
      { id: 'F-02', title: 'Model context requires snapshot confirmation', category: 'Context review', priority: 'Low', explanation: 'The supplied source identity does not match the analyzed snapshot.', limitation: 'No value can be highlighted until the exact analyzed source is available.', citations: [traceCitation(number, 'mismatch', 'Model input', 'compose', 'input', ['refund_window_days'])] },
    ] }
    base.attempts.push(prior)
    base.sources[prior.id] = { 'prior-document': { state: 'unavailable', snapshotId: prior.snapshotId, reason: 'Captured Revision 6 is no longer available in this authored sample.' }, mismatch: source('snap-1042-other', { refund_window_days: 30 }, { citedValue: 30 }) }
  } else if (number === 1041) {
    attempt.referenceState = 'References verified'
    attempt.limitations = 'Citations do not establish that the tool result or underlying business rule is correct.'
    attempt.findings = [{ id: 'F-01', title: 'Eligibility result is contradicted by the response', category: 'Reasoning inconsistency', priority: 'High', explanation: 'The eligibility tool returned false. The model received that value, then returned true and approved the request.', limitation: attempt.limitations, citations: [traceCitation(number, 'tool', 'Tool output', 'check', 'output', ['eligible']), traceCitation(number, 'model-output', 'Model output', 'compose', 'output', ['eligible']), traceCitation(number, 'model-input', 'Model input', 'compose', 'input', ['eligible'])] }]
    base.sources[attempt.id] = { tool: source(snapshotId, captured(number, 'check', 'output'), { citedValue: false }), 'model-output': source(snapshotId, captured(number, 'compose', 'output'), { citedValue: true }), 'model-input': source(snapshotId, captured(number, 'compose', 'input'), { citedValue: false }) }
  } else {
    attempt.limitations = number === 1040 ? 'No grounded findings returned. The recorded failed attempt and successful retry remain inspectable; this result does not establish that the run is correct.' : run.completeness === 'Partial' ? 'No grounded findings returned. The analyzed trace was partial; missing telemetry limits this result.' : 'No grounded findings returned. This does not establish correctness or the absence of execution errors.'
  }
  return base
}
export const investigationFixtures = new Map(runs.map(run => [`${run.projectId}/${run.id}`, freeze(build(run))]))
