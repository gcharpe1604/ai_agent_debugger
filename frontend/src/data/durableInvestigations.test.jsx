import { describe, it, expect, vi } from 'vitest'
import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import App from '../app/App.jsx'
import { createDurableAdapters } from './durableRepository.js'
import { resolveCitation } from '../features/evidence/evidenceState.js'

const traceId = '1234567890abcdef1234567890abcdef'
const ROOT = 'aaaaaaaaaaaaaaaa', TOOL = 'cccccccccccccccc'
const START = '1792584000000000000'
const projects = { projects: [{ id: 'local', name: 'Durable traces', storage: 'clickhouse', authentication: 'none' }] }
const run = { trace_id: traceId, name: 'tool.run', missing_root: false, status: 'ERROR', service: 'tool_agent', execution_mode: 'controlled', start_time_unix_nano: START, end_time_unix_nano: '1792584000250000000', span_count: 2, error_span_count: 1, root_span_id: ROOT, conflicted: false, recorded_recovered_retry: false, first_error: null }
function version(overrides) {
  return {
    trace_id: traceId, span_id: ROOT, parent_span_id: null, name: 'tool.run', operation_type: 'run', service: 'tool_agent', execution_mode: 'controlled',
    status: { code: 'OK', description: '' }, error_type: null, start_time_unix_nano: START, end_time_unix_nano: '1792584000250000000',
    attempt: null, retry_of_span_id: null, model: null, provider: null, input_tokens: null, output_tokens: null, total_tokens: null, cost: null,
    input_state: 'unavailable', output_state: 'unavailable', error_state: 'unavailable', attributes: {}, events: [], links: [],
    content_hash: 'h-' + (overrides.span_id || ROOT), received_at_unix_nano: '1792584001000000000', ...overrides,
  }
}
const tool = version({ span_id: TOOL, parent_span_id: ROOT, name: 'LocalTools.invoke', operation_type: 'tool', status: { code: 'ERROR', description: 'bad quantity' }, error_type: 'ToolError', start_time_unix_nano: '1792584000010000000', end_time_unix_nano: '1792584000090000000' })
const traceBody = {
  run,
  tree: { top_level: [ROOT], warnings: [], nodes: [
    { span_id: ROOT, parent_span_id: null, recorded_parent_span_id: null, depth: 0, children: [TOOL], flags: [], versions: ['h-' + ROOT] },
    { span_id: TOOL, parent_span_id: ROOT, recorded_parent_span_id: ROOT, depth: 1, children: [], flags: [], versions: ['h-' + TOOL] },
  ] },
  spans: [version({}), tool],
}
const scripted = { kind: 'scripted', name: 'stub-scripted', model_id: 'scripted-1', region: null }
const bedrock = { kind: 'bedrock', name: 'bedrock', model_id: 'us.example.model-v1:0', region: 'us-east-1' }
const CITED = '{"tool":"reserve_inventory","arguments":{"quantity":0}}'
function attempt(overrides = {}) {
  return {
    attempt_id: '7f000000-0000-4000-8000-000000000001', project: 'local', trace_id: traceId, status: 'completed', outcome: 'findings',
    failure_code: null, failure_detail: '', provider: scripted, prompt_version: 'investigator-v2', snapshot_hash: 'ab'.repeat(32),
    candidate_count: 2,
    findings: [{
      candidate_index: 0, category: 'tool_failure', claim_type: 'observed_failure', suspicious_span_id: TOOL, priority: 'HIGH',
      explanation: 'reserve_inventory failed; it was called with quantity 0.', relations: [], limitations: [],
      evidence: [
        { span_id: TOOL, content_hash: null, field: 'status_code', key: null, event_index: null, quote: null, cited_value: 'ERROR' },
        { span_id: TOOL, content_hash: null, field: 'input_payload', key: null, event_index: null, quote: '"quantity":0', cited_value: CITED },
      ],
    }],
    rejected: [{ candidate_index: 1, code: 'unknown_span' }], adjustments: [], limitations: [], has_failure_findings: true,
    provider_calls: 1, input_tokens: null, output_tokens: null, latency_ms: 0, created_at: '1', started_at: '2', finished_at: '3',
    ...overrides,
  }
}
const ok = (body, status = 200) => ({ ok: true, status, json: async () => body })
const fail = status => ({ ok: false, status, json: async () => ({ detail: 'server text that must not be shown sk-secret' }) })
const INV = `/api/v1/projects/local/runs/${traceId}/investigations`

function fetcher({ latest = fail(404), post = ok(attempt(), 201), provider = ok(scripted) } = {}) {
  const state = { latest }
  return vi.fn(async (url, init = {}) => {
    if (url === '/api/v1/projects') return ok(projects)
    if (url === '/api/v1/projects/local/investigator') return provider
    if (url === INV && init.method === 'POST') { if (post.ok) state.latest = ok(await post.json()); return post }
    if (url === INV + '/latest') return state.latest
    if (url.endsWith('/runs/' + traceId)) return ok(traceBody)
    if (url.includes('/local/runs?')) return ok({ project: 'local', runs: [run], next_cursor: null })
    throw new Error('unexpected read: ' + url)
  })
}
async function connected(fetch) {
  const adapters = createDurableAdapters(fetch)
  await adapters.projectAdapter.listProjects()
  return adapters
}

describe('durable investigation adapter', () => {
  it('reports no attempt as not requested and names the configured provider', async () => {
    const { investigationRepository } = await connected(fetcher())
    const data = await investigationRepository.readInvestigation({ projectId: 'local', runId: traceId })
    expect(data.state).toBe('Not requested')
    expect(data.attempts).toEqual([])
    expect(data.provider).toEqual({ kind: 'scripted', label: 'Scripted stub · no model called' })
    expect(data.run).toMatchObject({ id: traceId, outcome: 'Failed' })
  })

  it('maps grounded findings with their cited spans, quotes and rejection codes', async () => {
    const fetch = fetcher()
    const { investigationRepository } = await connected(fetch)
    const data = await investigationRepository.requestInvestigation({ projectId: 'local', runId: traceId })
    expect(fetch).toHaveBeenCalledWith(INV, expect.objectContaining({ method: 'POST' }))
    const [latest] = data.attempts
    expect(data.state).toBe('Completed')
    expect(latest.provider.label).toBe('Scripted stub · no model called')
    expect(latest.referenceState).toBe('Grounded: 1 kept, 1 rejected (unknown_span)')
    const [finding] = latest.findings
    expect(finding).toMatchObject({ id: 'F-01', priority: 'High', category: 'Tool failure', title: 'Observed failure · LocalTools.invoke' })
    expect(finding.citations.map(citation => [citation.spanId, citation.field])).toEqual([[TOOL, 'status_code'], [TOOL, 'input_payload']])

    const source = await investigationRepository.readSource({ projectId: 'local', runId: traceId, attemptId: latest.id, citationId: finding.citations[1].id })
    expect(source).toMatchObject({ snapshotId: latest.snapshotId, state: 'captured', value: CITED, displayValue: '"quantity":0' })
    expect(resolveCitation(finding.citations[1], source, latest.snapshotId)).toEqual({ available: true, resolved: true })
  })

  it('names a Bedrock provider with model and region', async () => {
    const { investigationRepository } = await connected(fetcher({ latest: ok(attempt({ provider: bedrock })), provider: ok(bedrock) }))
    const data = await investigationRepository.readInvestigation({ projectId: 'local', runId: traceId })
    expect(data.attempts[0].provider.label).toBe('Bedrock · us.example.model-v1:0 · us-east-1')
    expect(data.provider.label).toBe('Bedrock · us.example.model-v1:0 · us-east-1')
  })

  it('shows a failed attempt by its code and kind only', async () => {
    const failed = attempt({ status: 'failed', outcome: null, failure_code: 'provider_error', failure_detail: 'rate_limited', findings: [], rejected: [] })
    const { investigationRepository } = await connected(fetcher({ latest: ok(failed) }))
    const data = await investigationRepository.readInvestigation({ projectId: 'local', runId: traceId })
    expect(data.state).toBe('Failed')
    expect(data.attempts[0].error).toBe('The investigator provider failed (rate_limited). No findings were stored. Trace data remains available.')
  })

  it('surfaces a failed request without server text', async () => {
    const { investigationRepository } = await connected(fetcher({ post: fail(503) }))
    const request = investigationRepository.requestInvestigation({ projectId: 'local', runId: traceId })
    await expect(request).rejects.toThrow('Investigation could not start: the trace store or the investigator provider is unavailable or not configured.')
    await expect(request).rejects.not.toThrow(/sk-secret/)
  })
})

describe('durable investigation UI', () => {
  it('runs an investigation from a run, labels the provider and opens the grounded finding', async () => {
    const fetch = fetcher()
    window.history.replaceState(null, '', `/?source=durable#/projects/local/runs/${traceId}`)
    const user = userEvent.setup()
    render(<App {...createDurableAdapters(fetch)}/>)
    expect(await screen.findByText('Provider: Scripted stub · no model called')).toBeTruthy()
    await user.click(screen.getByRole('button', { name: 'Investigate' }))
    const link = await screen.findByRole('link', { name: 'View 1 finding' })
    expect(fetch.mock.calls.filter(([url, init]) => url === INV && init?.method === 'POST')).toHaveLength(1)
    expect(screen.getByRole('button', { name: 'Investigate again' })).toBeTruthy()

    await user.click(link)
    expect(await screen.findByRole('heading', { name: 'Observed failure · LocalTools.invoke' })).toBeTruthy()
    expect(screen.getByText('reserve_inventory failed; it was called with quantity 0.')).toBeTruthy()
    const paneB = screen.getByRole('region', { name: 'Source B' })
    expect((await within(paneB).findAllByText('"quantity":0')).length).toBeGreaterThan(0)
    expect(paneB.querySelector('.evidence-passage mark').textContent).toBe('"quantity":0')
    expect(screen.getAllByText(/Scripted stub · no model called/).length).toBeGreaterThan(0)
  })

  it('shows a request failure as an alert and stores nothing', async () => {
    window.history.replaceState(null, '', `/?source=durable#/projects/local/runs/${traceId}`)
    const user = userEvent.setup()
    render(<App {...createDurableAdapters(fetcher({ post: fail(503) }))}/>)
    await user.click(await screen.findByRole('button', { name: 'Investigate' }))
    expect((await screen.findByRole('alert')).textContent).toMatch(/could not start/)
    expect(screen.queryByRole('link', { name: /finding/ })).toBeNull()
  })
})
