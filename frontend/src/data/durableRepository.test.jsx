import { describe, it, expect, vi } from 'vitest'
import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import App from '../app/App.jsx'
import { parseQuery } from '../features/runs/query.js'
import { createApiAdapters, resolveSource } from './apiRepository.js'
import { createDurableAdapters, MAX_RUNS } from './durableRepository.js'

const traceId = '1234567890abcdef1234567890abcdef'
const ROOT = 'aaaaaaaaaaaaaaaa', ORPHAN = 'bbbbbbbbbbbbbbbb', TOOL = 'cccccccccccccccc', GONE = 'ffffffffffffffff'
const START = '1792584000000000000'
// GET /api/v1/projects: a bare list with the signed-in user's one project.
const projects = [{ id: 'default', name: 'Durable traces' }]
const me = { id: '6f1c0d52-0000-4000-8000-000000000001', name: 'Ada Lovelace', email: 'ada@example.com', key_prefix: 'adbg_sk_AbCd' }
const listRow = { trace_id: traceId, name: 'rag.run', missing_root: false, status: 'ERROR', service: 'rag_agent', execution_mode: 'controlled', start_time_unix_nano: START, end_time_unix_nano: '1792584000250000000', span_count: 3, error_span_count: 2 }
const run = { ...listRow, root_span_id: ROOT, conflicted: true, recorded_recovered_retry: false, first_error: { span_id: TOOL, span_name: 'tool.search', operation_type: 'tool', error_type: 'TimeoutError', originating_error_span_count: 1 } }

function version(overrides) {
  return {
    trace_id: traceId, span_id: ROOT, parent_span_id: null, name: 'rag.run', operation_type: 'run', service: 'rag_agent', execution_mode: 'controlled',
    status: { code: 'OK', description: '' }, error_type: null, start_time_unix_nano: START, end_time_unix_nano: '1792584000250000000',
    attempt: null, retry_of_span_id: null, model: null, provider: null, input_tokens: null, output_tokens: null, total_tokens: null, cost: null,
    input_state: 'unavailable', output_state: 'unavailable', error_state: 'unavailable', attributes: {}, events: [], links: [],
    content_hash: 'h-' + (overrides.span_id || ROOT), received_at_unix_nano: '1792584001000000000', ...overrides,
  }
}
const toolFirst = version({ span_id: TOOL, parent_span_id: ROOT, name: 'tool.search', operation_type: 'tool', status: { code: 'ERROR', description: 'timed out' }, error_type: 'TimeoutError', start_time_unix_nano: '1792584000010000000', end_time_unix_nano: '1792584000090000000', content_hash: 'aaaa1111bbbb2222cccc', input_state: 'redacted', output_state: 'unavailable', error_state: 'captured' })
const toolSecond = { ...toolFirst, name: 'tool.search.v2', status: { code: 'OK', description: '' }, content_hash: 'dddd3333eeee4444ffff', received_at_unix_nano: '1792584002000000000' }
const orphan = version({ span_id: ORPHAN, parent_span_id: GONE, name: 'late.step', operation_type: 'custom', start_time_unix_nano: '1792584000100000000', end_time_unix_nano: '1792584000120000000' })
const traceBody = {
  run,
  tree: {
    top_level: [ROOT, ORPHAN],
    nodes: [
      { span_id: ROOT, parent_span_id: null, recorded_parent_span_id: null, depth: 0, children: [TOOL], flags: [], versions: ['h-' + ROOT] },
      { span_id: TOOL, parent_span_id: ROOT, recorded_parent_span_id: ROOT, depth: 1, children: [], flags: ['conflict'], versions: [toolFirst.content_hash, toolSecond.content_hash] },
      { span_id: ORPHAN, parent_span_id: null, recorded_parent_span_id: GONE, depth: 0, children: [], flags: ['missing_parent'], versions: ['h-' + ORPHAN] },
    ],
    warnings: [
      { code: 'missing_parent', span_ids: [ORPHAN], message: '1 span named a parent that has not been received.' },
      { code: 'conflict', span_ids: [TOOL], message: '1 span was received with more than one content version.' },
    ],
  },
  // Deliberately not in tree order: the adapter must follow the tree, not this array.
  spans: [orphan, toolSecond, version({}), toolFirst],
}
const spanBody = {
  run, span_id: TOOL, parent_span_id: ROOT, recorded_parent_span_id: ROOT, flags: ['conflict'], conflicted: true,
  versions: [
    { ...toolFirst, input_payload: '{"api_key":"[redacted]","q":"refund policy"}', output_payload: '', error_payload: '{"type":"TimeoutError","message":"no answer in 30 s"}' },
    { ...toolSecond, input_payload: '{"q":"other"}', output_payload: '', error_payload: '' },
  ],
  retry_of: null, retries: [],
}
const orphanBody = { run, span_id: ORPHAN, parent_span_id: null, recorded_parent_span_id: GONE, flags: ['missing_parent'], conflicted: false, versions: [{ ...orphan, input_payload: '', output_payload: '', error_payload: '' }], retry_of: null, retries: [] }

const ok = body => ({ ok: true, status: 200, json: async () => body })
function durableFetcher(overrides = {}) {
  return vi.fn(async url => {
    if (url === '/api/v1/auth/me') return ok(me)
    if (!url.startsWith('/api/v1/projects')) throw new Error('unexpected read: ' + url)
    for (const [suffix, answer] of Object.entries(overrides)) if (url.includes(suffix)) return answer
    if (url === '/api/v1/projects') return ok(projects)
    if (url.endsWith('/spans/' + TOOL)) return ok(spanBody)
    if (url.endsWith('/spans/' + ORPHAN)) return ok(orphanBody)
    if (url.endsWith('/runs/' + traceId)) return ok(traceBody)
    return ok({ project: 'default', runs: [listRow], next_cursor: null })
  })
}
async function connected(fetcher) {
  const adapters = createDurableAdapters(fetcher)
  await adapters.projectAdapter.listProjects()
  return adapters
}

describe('source switch', () => {
  it('defaults to the durable source; only ?source=local selects the local profile', () => {
    expect(resolveSource()).toBe('durable')
    expect(resolveSource('')).toBe('durable')
    expect(resolveSource('?source=durable')).toBe('durable')
    expect(resolveSource('?source=local')).toBe('local')
    expect(resolveSource('?source=clickhouse')).toBe('durable')
    expect(resolveSource('?source=LOCAL')).toBe('durable')
  })

  it('reads only the local profile unless durable is selected, and only the durable API when it is', async () => {
    const local = vi.fn(async () => ok({ mode: 'local', workspace: { id: 'local', name: 'Local captures', dataSource: 'local' } }))
    await createApiAdapters(local).projectAdapter.listProjects()
    expect(local.mock.calls.map(([url]) => url)).toEqual(['/api/v1/local/status'])

    const durable = durableFetcher()
    const adapters = createApiAdapters(durable, { source: 'durable' })
    const [project] = await adapters.projectAdapter.listProjects()
    expect(project).toMatchObject({ id: 'default', name: 'Durable traces', storage: 'durable', dataSource: 'local' })
    expect(adapters.accountAdapter.mode).toBe('durable')
    expect(adapters.projectAdapter.createProject).toBeUndefined()
    expect(adapters.projectAdapter.updateProject).toBeUndefined()
    await adapters.repository.listRuns({ projectId: 'default', query: parseQuery('') })
    expect(durable.mock.calls.every(([url]) => url.startsWith('/api/v1/projects'))).toBe(true)
  })
})

describe('durable run list', () => {
  it('maps a run row and reports what the backend recorded', async () => {
    const rootless = { ...listRow, trace_id: 'f'.repeat(32), name: null, missing_root: true, status: null, service: null, execution_mode: null, error_span_count: 0 }
    const { repository } = await connected(durableFetcher({ '/runs?': ok({ project: 'default', runs: [listRow, rootless], next_cursor: null }) }))
    const result = await repository.listRuns({ projectId: 'default', query: parseQuery('') })
    const byId = Object.fromEntries(result.items.map(item => [item.id, item]))
    expect(byId[traceId]).toMatchObject({ name: 'rag.run', outcome: 'Failed', durationMs: 250, service: 'rag_agent', executionMode: 'controlled', recordedErrorCount: 2, startedAt: '2026-10-21T12:00:00.000Z', missingRoot: false })
    // No root span: the status is unknown, never guessed from the other spans.
    expect(byId['f'.repeat(32)]).toMatchObject({ name: 'Root span not received', outcome: 'Unknown', service: 'Not recorded', missingRoot: true })
    expect(result.partialAt).toBeUndefined()
  })

  it('follows next_cursor until the list ends', async () => {
    const row = n => ({ ...listRow, trace_id: n.toString(16).padStart(32, '0') })
    const fetcher = vi.fn(async url => url === '/api/v1/projects' ? ok(projects)
      : url.includes('cursor=c2') ? ok({ project: 'default', runs: [row(3)], next_cursor: null })
        : url.includes('cursor=c1') ? ok({ project: 'default', runs: [row(2)], next_cursor: 'c2' })
          : ok({ project: 'default', runs: [row(1)], next_cursor: 'c1' }))
    const { repository } = await connected(fetcher)
    const result = await repository.listRuns({ projectId: 'default', query: parseQuery('') })
    expect(result.total).toBe(3)
    expect(fetcher.mock.calls.map(([url]) => url).slice(1)).toEqual(['/api/v1/projects/default/runs?limit=200', '/api/v1/projects/default/runs?limit=200&cursor=c1', '/api/v1/projects/default/runs?limit=200&cursor=c2'])
  })

  it('stops at the run cap and says the list is partial', async () => {
    let page = 0
    const fetcher = vi.fn(async url => {
      if (url === '/api/v1/projects') return ok(projects)
      const runs = Array.from({ length: 200 }, (_, i) => ({ ...listRow, trace_id: (page * 200 + i).toString(16).padStart(32, '0') }))
      page++
      return ok({ project: 'default', runs, next_cursor: 'more' })
    })
    const { repository } = await connected(fetcher)
    const result = await repository.listRuns({ projectId: 'default', query: parseQuery('') })
    expect(result.partialAt).toBe(MAX_RUNS)
    expect(result.total).toBe(MAX_RUNS)
    expect(page).toBe(MAX_RUNS / 200)
  })

  it('surfaces a store failure and never falls back to the local profile or sample data', async () => {
    const fetcher = durableFetcher({ '/runs': { ok: false, status: 503 } })
    const { repository, traceRepository } = await connected(fetcher)
    await expect(repository.listRuns({ projectId: 'default', query: parseQuery('') })).rejects.toThrow('ClickHouse) is unavailable')
    await expect(repository.listRuns({ projectId: 'default', query: parseQuery('') })).rejects.toThrow('No sample data was substituted')
    await expect(traceRepository.readTrace({ projectId: 'default', runId: traceId })).rejects.toThrow('No sample data was substituted')
    await expect(repository.listRuns({ projectId: 'other', query: parseQuery('') })).rejects.toThrow('Captured workspace unavailable')
    expect(fetcher.mock.calls.some(([url]) => url.includes('/local/status') || url.includes('/api/v1/local/'))).toBe(false)
  })

  it('reports a missing trace, a wrong trace and an unexpected body as errors', async () => {
    const missing = await connected(durableFetcher({ ['/runs/' + traceId]: { ok: false, status: 404 } }))
    await expect(missing.traceRepository.readTrace({ projectId: 'default', runId: traceId })).rejects.toThrow('not in durable storage')
    const wrong = await connected(durableFetcher({ ['/runs/' + traceId]: ok({ ...traceBody, run: { ...run, trace_id: '0'.repeat(32) } }) }))
    await expect(wrong.traceRepository.readTrace({ projectId: 'default', runId: traceId })).rejects.toThrow('identity mismatch')
    const odd = await connected(durableFetcher({ '/runs?': ok({ runs: [] }) }))
    await expect(odd.repository.listRuns({ projectId: 'default', query: parseQuery('') })).rejects.toThrow('Unexpected telemetry response')
    await expect(createDurableAdapters(async () => ok([])).projectAdapter.listProjects()).rejects.toThrow('Unexpected workspace response')
    // The old { projects: [...] } shape is not accepted.
    await expect(createDurableAdapters(async () => ok({ projects })).projectAdapter.listProjects()).rejects.toThrow('Unexpected workspace response')
  })
})

describe('durable trace and span', () => {
  it('follows the backend tree: order, effective parent, flags and one row per span', async () => {
    const { traceRepository } = await connected(durableFetcher())
    const data = await traceRepository.readTrace({ projectId: 'default', runId: traceId })
    expect(data.spans.map(span => [span.id, span.parentId, span.recordedParentId, span.flags, span.versionCount])).toEqual([
      [ROOT, null, null, [], 1],
      [TOOL, ROOT, ROOT, ['conflict'], 2],
      [ORPHAN, null, GONE, ['missing_parent'], 1],
    ])
    // The conflicted span is shown with the version that places it (the first one).
    expect(data.spans[1]).toMatchObject({ name: 'tool.search', status: 'ERROR', start: 10, end: 90, duration: 80 })
    expect(data.quality).toBe('Structure: 1 span named a parent that has not been received. 1 span was received with more than one content version. Nothing was dropped or re-parented.')
    expect(data.run.firstError).toEqual({ spanId: TOOL, spanName: 'tool.search', operationType: 'tool', exceptionType: 'TimeoutError', leafErrorCount: 1 })
    expect(data.run.conflicted).toBe(true)
  })

  it('has no structure note for a clean trace', async () => {
    const clean = { ...traceBody, tree: { ...traceBody.tree, warnings: [] } }
    const { traceRepository } = await connected(durableFetcher({ ['/runs/' + traceId]: ok(clean) }))
    expect((await traceRepository.readTrace({ projectId: 'default', runId: traceId })).quality).toBeUndefined()
  })

  it('reads payloads by state, the stored error and every version of a conflicted span', async () => {
    const { traceRepository } = await connected(durableFetcher())
    const data = await traceRepository.readSpan({ projectId: 'default', runId: traceId, spanId: TOOL })
    expect(data.input).toEqual({ api_key: '[redacted]', q: 'refund policy' })
    expect(data.inputCapture.state).toBe('redacted')
    expect(data.inputCapture.reason).toContain('[redacted]')
    // Not captured: no value at all, never an empty string shown as content.
    expect(data.output).toBeUndefined()
    expect(data.outputCapture.state).toBe('unavailable')
    expect(data).toMatchObject({ error: 'no answer in 30 s', errorType: 'TimeoutError', source: 'durable', flags: ['conflict'] })
    expect(data.versions.map(item => [item.contentHash, item.name, item.status])).toEqual([[toolFirst.content_hash, 'tool.search', 'ERROR'], [toolSecond.content_hash, 'tool.search.v2', 'OK']])
    expect(data.attributes['otel.span_id']).toBe(TOOL)
    expect(data.attributes['resource.service.name']).toBe('rag_agent')
  })

  it('keeps a payload that is not JSON as text and rejects another span in the response', async () => {
    const text = { ...spanBody, versions: [{ ...spanBody.versions[0], input_state: 'truncated', input_payload: '{"q":"cut he' }] }
    const { traceRepository } = await connected(durableFetcher({ ['/spans/' + TOOL]: ok(text) }))
    const data = await traceRepository.readSpan({ projectId: 'default', runId: traceId, spanId: TOOL })
    expect(data.input).toBe('{"q":"cut he')
    expect(data.inputCapture.state).toBe('truncated')
    const other = await connected(durableFetcher({ ['/spans/' + TOOL]: ok(orphanBody) }))
    await expect(other.traceRepository.readSpan({ projectId: 'default', runId: traceId, spanId: TOOL })).rejects.toThrow('identity mismatch')
  })
})

describe('durable source in the app', () => {
  it('opens a durable trace and shows structure warnings, row flags and conflicting versions', async () => {
    const fetcher = durableFetcher()
    window.history.replaceState(null, '', '/?source=durable#/projects/default/runs')
    const user = userEvent.setup()
    render(<App {...createApiAdapters(fetcher, { source: resolveSource(window.location.search) })}/>)
    await user.click(await screen.findByRole('link', { name: `rag.run ${traceId}` }))
    expect(await screen.findByText(/Structure: 1 span named a parent that has not been received\./)).toBeTruthy()
    const orphanRow = await screen.findByRole('treeitem', { name: /late\.step · Custom · OK/ })
    expect(orphanRow.getAttribute('aria-level')).toBe('1')
    expect(within(orphanRow).getByText('Parent not received')).toBeTruthy()
    const toolRow = screen.getByRole('treeitem', { name: /tool\.search · Tool · ERROR/ })
    expect(toolRow.getAttribute('aria-level')).toBe('2')
    expect(within(toolRow).getByText('Conflicting versions')).toBeTruthy()
    expect(within(screen.getByRole('treeitem', { name: /rag\.run · Run · OK/ })).queryByText(/Parent not received|Conflicting versions/)).toBeNull()
    // The first error is selected on open, so the inspector shows the conflicted tool span.
    const note = await screen.findByRole('note', { name: 'Conflicting versions' })
    expect(within(note).getByText('2 conflicting versions received')).toBeTruthy()
    expect(within(note).getAllByRole('listitem').map(item => item.textContent)).toEqual([
      'aaaa1111bbbb · tool.search · ERROR · received 2026-10-21 12:00:01.000 UTC',
      'dddd3333eeee · tool.search.v2 · OK · received 2026-10-21 12:00:02.000 UTC',
    ])
    expect(screen.getByText('no answer in 30 s')).toBeTruthy()
    expect(screen.getByText('refund policy')).toBeTruthy()
    expect(screen.queryByText('Sample data')).toBeNull()
    await user.click(orphanRow)
    const structure = await screen.findByRole('note', { name: 'Structure flags' })
    expect(structure.textContent).toContain(GONE)
    expect(fetcher.mock.calls.every(([url]) => url.startsWith('/api/v1/projects') || url === '/api/v1/auth/me')).toBe(true)
  })

  it('shows a store failure as an error with a retry, not as an empty list', async () => {
    const fetcher = durableFetcher({ '/runs': { ok: false, status: 503 } })
    window.history.replaceState(null, '', '/?source=durable#/projects/default/runs')
    render(<App {...createApiAdapters(fetcher, { source: 'durable' })}/>)
    const alert = await screen.findByRole('alert')
    expect(alert.textContent).toContain('Could not load traces')
    expect(alert.textContent).toContain('No sample data was substituted')
    expect(screen.queryByRole('heading', { name: 'No traces yet' })).toBeNull()
    expect(screen.queryByRole('link', { name: /rag\.run/ })).toBeNull()
  })

  it('describes durable storage and the durable endpoint in Settings', async () => {
    window.history.replaceState(null, '', '/?source=durable#/projects/default/runs')
    const user = userEvent.setup()
    render(<App {...createApiAdapters(durableFetcher(), { source: 'durable' })}/>)
    await user.click(await screen.findByRole('link', { name: 'Project settings' }))
    expect(await screen.findByText(/ClickHouse, written by the trace-writer from Kafka/)).toBeTruthy()
    expect(screen.getByText(/AGENT_DEBUGGER_ENDPOINT=http:\/\/127\.0\.0\.1:8008\/api\/v1\/traces/)).toBeTruthy()
    expect(screen.getByText(/AGENT_DEBUGGER_API_KEY=adbg_sk_AbCd…/)).toBeTruthy()
    expect(screen.queryByText(/Temporary memory on the local backend/)).toBeNull()
    expect(screen.queryByRole('button', { name: 'Create API key' })).toBeNull()
    expect(screen.getByRole('button', { name: 'Rotate key' })).toBeTruthy()
  })
})
