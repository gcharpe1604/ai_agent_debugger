// Investigation API (POST/GET /api/v1/projects/local/runs/{id}/investigations):
// grounded findings from the backend investigator, mapped onto the evidence UI's
// view model. Read failures are thrown; nothing here substitutes fixture data.
// Server error text is never shown: only status-based messages.

const BASE = '/api/v1/projects/local'
const STATES = { pending: 'Pending', running: 'Running', completed: 'Completed', failed: 'Failed' }
const PRIORITY = { HIGH: 'High', MEDIUM: 'Medium', LOW: 'Low' }
const CLAIMS = { observed_failure: 'Observed failure', suspected_origin: 'Suspected origin', recovered_failure: 'Recovered failure', inconsistency: 'Inconsistency', completeness: 'Completeness' }
const FIELDS = { status_code: 'Status', status_description: 'Status description', error_type: 'Error type', span_name: 'Span name', attempt: 'Attempt', retry_of_span_id: 'Retry of', attribute: 'Attribute', event: 'Event', input_payload: 'Input', output_payload: 'Output', error_payload: 'Error payload' }
const FAILURES = {
  provider_error: detail => `The investigator provider failed (${detail || 'unknown'}). No findings were stored.`,
  invalid_output: () => 'The provider answer did not match the output schema. No findings were stored.',
  input_too_large: () => 'The trace is too large for one investigation snapshot. Nothing was sent to the provider.',
  trace_not_found: () => 'The trace was not found in durable storage.',
  internal_error: () => 'The investigator failed unexpectedly. No findings were stored.',
}
const DEFAULT_LIMITATION = 'Grounding checked that every cited span, field and quote exists in the analyzed snapshot. It does not prove the explanation or a cause.'

const sentence = text => text.charAt(0).toUpperCase() + text.slice(1).replaceAll('_', ' ')

export function providerLabel(provider) {
  if (!provider) return 'Unknown provider'
  if (provider.kind === 'scripted') return 'Scripted stub · no model called'
  const name = provider.kind === 'bedrock' ? 'Bedrock' : provider.name
  return [name, provider.model_id, provider.region].filter(Boolean).join(' · ')
}
const providerView = provider => ({ kind: provider.kind, label: providerLabel(provider) })

function citationView(evidence, index, spanNames, findingId) {
  const quote = evidence.quote ?? evidence.cited_value
  const start = typeof evidence.cited_value === 'string' && quote != null ? evidence.cited_value.indexOf(quote) : -1
  const detail = evidence.key ? ` · ${evidence.key}` : evidence.event_index != null ? ` · ${evidence.event_index}` : ''
  return {
    id: `${findingId}-e${index + 1}`, label: `${FIELDS[evidence.field] || evidence.field}${detail}`,
    title: spanNames.get(evidence.span_id) || `Span ${evidence.span_id}`, kind: 'Span', field: evidence.field + detail,
    spanId: evidence.span_id, contentHash: evidence.content_hash ?? undefined,
    ...(start >= 0 ? { quote, range: { start, end: start + quote.length } } : {}),
  }
}
function sourceView(evidence, snapshotId) {
  if (typeof evidence.cited_value !== 'string') return { state: 'unavailable', snapshotId, reason: 'The cited value is not in the analyzed snapshot.' }
  const shown = evidence.quote ?? evidence.cited_value
  return { snapshotId, state: 'captured', value: evidence.cited_value, citedValue: shown, displayValue: shown }
}

function attemptView(attempt, spanNames) {
  const snapshotId = attempt.snapshot_hash ? attempt.snapshot_hash.slice(0, 12) : 'not built'
  const provider = providerView(attempt.provider)
  const codes = [...new Set(attempt.rejected.map(entry => entry.code))]
  const view = {
    id: attempt.attempt_id, label: `Latest attempt · ${provider.label}`, state: STATES[attempt.status] || 'Unknown', provider, snapshotId,
    outcome: attempt.outcome,
    referenceState: attempt.status === 'completed' ? `Grounded: ${attempt.findings.length} kept, ${attempt.rejected.length} rejected${codes.length ? ` (${codes.join(', ')})` : ''}` : 'Not grounded',
    limitations: attempt.limitations.join(' ') || (attempt.outcome && attempt.outcome !== 'findings' ? `Outcome: ${attempt.outcome.replaceAll('_', ' ')}. This does not establish that the run is correct.` : DEFAULT_LIMITATION),
    findings: [], sources: {},
  }
  if (attempt.status === 'failed') view.error = `${(FAILURES[attempt.failure_code] || FAILURES.internal_error)(attempt.failure_detail)} Trace data remains available.`
  view.findings = attempt.findings.map((finding, index) => {
    const id = `F-${String(index + 1).padStart(2, '0')}`
    const citations = finding.evidence.map((evidence, j) => citationView(evidence, j, spanNames, id))
    finding.evidence.forEach((evidence, j) => { view.sources[citations[j].id] = sourceView(evidence, snapshotId) })
    const suspect = finding.suspicious_span_id ? spanNames.get(finding.suspicious_span_id) || finding.suspicious_span_id : 'No single span'
    return {
      id, title: `${CLAIMS[finding.claim_type] || sentence(finding.claim_type)} · ${suspect}`, category: sentence(finding.category),
      priority: PRIORITY[finding.priority] || finding.priority, explanation: finding.explanation,
      limitation: finding.limitations.join(' ') || DEFAULT_LIMITATION, citations,
    }
  })
  return view
}

export function createDurableInvestigations(fetcher, { readRun }) {
  const attempts = new Map()  // attempt id -> view, for readSource
  async function call(path, init, signal) {
    return fetcher(BASE + path, { signal, cache: 'no-store', headers: { Accept: 'application/json' }, ...init })
  }
  async function configured(signal) {
    const response = await call('/investigator', {}, signal)
    return response.ok ? providerView(await response.json()) : { kind: 'unknown', label: 'Not configured on the server' }
  }
  async function result(runId, attempt, signal) {
    const { run, spanNames } = await readRun(runId, signal)
    const view = attempt ? attemptView(attempt, spanNames) : null
    if (view) attempts.set(view.id, view)
    return { run, state: view ? view.state : 'Not requested', attempts: view ? [view] : [], provider: view ? view.provider : await configured(signal) }
  }
  return {
    async readInvestigation({ runId, signal }) {
      const response = await call(`/runs/${encodeURIComponent(runId)}/investigations/latest`, {}, signal)
      if (response.status === 404) return result(runId, null, signal)
      if (!response.ok) throw new Error('Investigation read failed. Check the backend on 127.0.0.1:8008 and retry.')
      return result(runId, await response.json(), signal)
    },
    async requestInvestigation({ runId, signal }) {
      const response = await call(`/runs/${encodeURIComponent(runId)}/investigations`, { method: 'POST' }, signal)
      if (!response.ok) throw new Error(response.status === 404 ? 'Investigation could not start: this trace is not in durable storage.'
        : 'Investigation could not start: the trace store or the investigator provider is unavailable or not configured.')
      return result(runId, await response.json(), signal)
    },
    async readSource({ runId, attemptId, citationId, signal }) {
      let attempt = attempts.get(attemptId)
      if (!attempt) { await this.readInvestigation({ runId, signal }); attempt = attempts.get(attemptId) }
      const source = attempt?.sources[citationId]
      if (!source) throw new Error('Analyzed evidence unavailable: only the latest attempt of this backend process is kept.')
      return source
    },
  }
}
