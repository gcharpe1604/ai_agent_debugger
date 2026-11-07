import { it, expect, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import App from '../app/App.jsx'
import { parseQuery } from '../features/runs/query.js'
import { createApiAdapters } from './apiRepository.js'

const workspace = { id: "local", name: "Local captures", initial: "L", environment: "SDK telemetry · memory storage", dataSource: "local" }
const status = { mode: "local", workspace }
const traceId = '1234567890abcdef1234567890abcdef'
const run = { trace_id: traceId, name: 'Captured run', started_at: '2026-10-21T12:00:00Z', start_time_unix_nano: '1792584000000000000', end_time_unix_nano: '1792584000004000000', status: 'OK', service: 'unit-test', recorded_error_spans: 0 }
const span = { trace_id: traceId, span_id: '1234567890abcdef', parent_span_id: null, name: 'Captured run', operation_type: 'run', start_time_unix_nano: run.start_time_unix_nano, end_time_unix_nano: run.end_time_unix_nano, status: { code: 'UNSET' }, attributes: {}, resource: { 'service.name': 'unit-test' }, events: [] }

it('opens actual trace IDs through Run Explorer and preserves raw status and metadata-only boundaries', async () => {
  const fetcher = vi.fn(async url => ({ ok: true, json: async () => url.endsWith('/status') ? status : url.endsWith('/spans/' + span.span_id) ? { run, span, retry_of: null, retries: [] } : url.endsWith(traceId) ? { run, spans: [span] } : { mode: 'local', runs: [run] } }))
  window.history.replaceState(null, '', '/?source=local#/projects/local/runs')
  const user = userEvent.setup()
  render(<App {...createApiAdapters(fetcher)}/> )
  await user.click(await screen.findByRole('link', { name: `Captured run ${traceId}` }))
  await user.click(await screen.findByRole('treeitem', { name: /Captured run · Run · UNSET/ }))
  expect(await screen.findByText('Input capture is disabled for this metadata-only capture profile.')).toBeTruthy()
  expect(screen.getAllByText('Captured SDK data').length).toBeGreaterThan(0)
  expect(screen.queryByText('Sample data')).toBeNull()
  expect(screen.queryByLabelText('Investigation details')).toBeNull()
  expect(window.location.hash).toContain(traceId)
  await waitFor(() => expect(fetcher).toHaveBeenCalledWith(expect.stringContaining(traceId + '/spans/' + span.span_id), expect.objectContaining({ cache: 'no-store' })))
})

it('keeps backend failure explicit without fixture fallback and rejects another project scope', async () => {
  const adapters = createApiAdapters(async url => url.endsWith('/status') ? { ok: true, json: async () => status } : { ok: false, status: 503 })
  await adapters.projectAdapter.listProjects()
  const { repository } = adapters
  await expect(repository.listRuns({ projectId: 'local', query: parseQuery('') })).rejects.toThrow('No sample data was substituted')
  await expect(repository.listRuns({ projectId: 'agent-examples', query: parseQuery('') })).rejects.toThrow('Captured workspace unavailable')
})

it('starts without seeded projects or telemetry when no adapter is connected', async () => {
  window.history.replaceState(null, '', '/#/projects')
  render(<App/> )
  expect(await screen.findByRole('heading', { name: 'Project service unavailable' })).toBeTruthy()
  expect(screen.getByLabelText('Project').disabled).toBe(true)
  expect(screen.queryByRole('link', { name: /sample/i })).toBeNull()
  expect(screen.queryByRole('link', { name: /refund-policy-review/ })).toBeNull()
  expect(screen.queryByRole('link', { name: 'Create project' })).toBeNull()
})

it('renders an empty captured store without inserting sample executions', async () => {
  const fetcher = vi.fn(async url => ({ ok: true, json: async () => url.endsWith('/status') ? status : ({ mode: 'local', runs: [] }) }))
  window.history.replaceState(null, '', '/#/projects/local/runs')
  render(<App {...createApiAdapters(fetcher)}/> )
  expect(await screen.findByRole('heading', { name: 'No runs recorded' })).toBeTruthy()
  expect(screen.queryByRole('link', { name: /sample/i })).toBeNull()
  expect(screen.queryByRole('link', { name: /R-10/ })).toBeNull()
  expect(fetcher).toHaveBeenCalledWith('/api/v1/local/runs', expect.objectContaining({ cache: 'no-store' }))
})

it('shows a backend failure without a sample fallback even with a legacy sample query', async () => {
  window.history.replaceState(null, '', '/?source=sample#/projects/local/runs')
  render(<App {...createApiAdapters(async url => url.endsWith('/status') ? { ok: true, json: async () => status } : { ok: false, status: 503 })}/> )
  expect(await screen.findByRole('alert')).toHaveProperty('textContent', expect.stringContaining('Could not load runs'))
  expect(screen.getByRole('button', { name: 'Retry' })).toBeTruthy()
  expect(screen.queryByRole('link', { name: /sample|refund-policy-review/i })).toBeNull()
  expect(screen.queryByRole('heading', { name: 'No runs recorded' })).toBeNull()
})

it('does not offer simulated project creation or settings in the captured workspace', async () => {
  window.history.replaceState(null, '', '/#/projects')
  render(<App {...createApiAdapters(async () => ({ ok: true, json: async () => status }))}/> )
  await screen.findByRole('list', { name: 'Available projects' })
  expect(screen.queryByRole('link', { name: 'Create project' })).toBeNull()
  expect(screen.queryByRole('link', { name: /Settings for/ })).toBeNull()
  window.location.hash = '#/projects/new'
  expect(await screen.findByRole('heading', { name: 'Project service unavailable' })).toBeTruthy()
  expect(screen.queryByRole('button', { name: 'Create project' })).toBeNull()
})
