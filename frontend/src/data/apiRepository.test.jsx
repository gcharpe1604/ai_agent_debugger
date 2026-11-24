import { describe, it, expect, vi } from 'vitest'
import { render, screen, waitFor, within } from '@testing-library/react'
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
  expect(await screen.findByText('Input and output not captured')).toBeTruthy()
  expect(screen.queryByRole('group', { name: /format$/ })).toBeNull()
  // "received · completeness unknown" is only in the Spans tooltip.
  expect(screen.queryByText(/completeness unknown/)).toBeNull()
  expect(document.querySelector('[data-stat="spans"]').textContent).toBe('1 span')
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

it('shows local Settings with server-reported retention, the SDK endpoint and no key creation', async () => {
  const fetcher = vi.fn(async url => ({ ok: true, json: async () => url.endsWith('/status') ? { ...status, ttl_seconds: 14400 } : ({ mode: 'local', runs: [] }) }))
  window.history.replaceState(null, '', '/#/projects/local/runs')
  const user = userEvent.setup()
  render(<App {...createApiAdapters(fetcher)}/> )
  await user.click(await screen.findByRole('link', { name: 'Project settings' }))
  expect(await screen.findByRole('heading', { name: 'Settings' })).toBeTruthy()
  expect(screen.getByText('Traces are kept for 4 h, then removed.')).toBeTruthy()
  expect(screen.getByText(/AGENT_DEBUGGER_ENDPOINT=http:\/\/127\.0\.0\.1:8008\/api\/v1\/local\/traces/)).toBeTruthy()
  expect(screen.getByRole('button', { name: 'Create API key' }).disabled).toBe(true)
  expect(screen.getByRole('link', { name: 'Docs (opens in a new tab)' }).getAttribute('target')).toBe('_blank')
})

it('renders an empty captured store without inserting sample executions', async () => {
  const fetcher = vi.fn(async url => ({ ok: true, json: async () => url.endsWith('/status') ? status : ({ mode: 'local', runs: [] }) }))
  window.history.replaceState(null, '', '/#/projects/local/runs')
  render(<App {...createApiAdapters(fetcher)}/> )
  expect(await screen.findByRole('heading', { name: 'No traces yet' })).toBeTruthy()
  expect(within(screen.getByRole('main')).getByRole('link', { name: 'Set up tracing' }).getAttribute('href')).toBe('#/projects/local')
  expect(screen.queryByRole('link', { name: /sample/i })).toBeNull()
  expect(screen.queryByRole('link', { name: /R-10/ })).toBeNull()
  expect(fetcher).toHaveBeenCalledWith('/api/v1/local/runs', expect.objectContaining({ cache: 'no-store' }))
})

it('keeps the Home setup steps available offline and verifies only the requested trace after reconnecting', async () => {
  const missingId = 'abcdef1234567890abcdef1234567890'
  let reachable = false
  const adapters = createApiAdapters(async url => {
    if (!reachable) throw new TypeError('Connection refused')
    if (url.endsWith('/status')) return { ok: true, json: async () => status }
    if (url.endsWith(traceId)) return { ok: true, json: async () => ({ run, spans: [span] }) }
    return { ok: false, status: 404 }
  })
  window.history.replaceState(null, '', '/#/projects/local/runs')
  const user = userEvent.setup()
  render(<App {...adapters}/> )
  await user.click(await screen.findByRole('link', { name: 'Home' }))
  expect(await screen.findByRole('heading', { name: 'Home' })).toBeTruthy()
  expect(await screen.findByText('Backend unavailable')).toBeTruthy()
  expect(screen.queryByRole('combobox', { name: 'Project' })).toBeNull()
  reachable = true
  await user.click(screen.getByRole('button', { name: 'Check connection' }))
  expect(await screen.findByText('Backend reachable')).toBeTruthy()
  // The overview read can fail on its own; the setup steps keep their own result.
  const setup = () => within(screen.getByRole('region', { name: 'Send your first trace' }))
  const input = setup().getByRole('textbox', { name: 'Trace ID' })
  await user.type(input, missingId)
  await user.click(setup().getByRole('button', { name: 'Verify trace' }))
  expect(await setup().findByText(/Captured data is unavailable/)).toBeTruthy()
  expect(screen.queryByRole('link', { name: 'Open trace' })).toBeNull()
  await user.clear(input)
  await user.type(input, traceId)
  await user.click(screen.getByRole('button', { name: 'Verify trace' }))
  await user.click(await screen.findByRole('link', { name: 'Open trace' }))
  expect(await screen.findByRole('heading', { name: 'Captured run' })).toBeTruthy()
})

it('shows a backend failure without a sample fallback even with a legacy sample query', async () => {
  window.history.replaceState(null, '', '/?source=sample#/projects/local/runs')
  render(<App {...createApiAdapters(async url => url.endsWith('/status') ? { ok: true, json: async () => status } : { ok: false, status: 503 })}/> )
  expect(await screen.findByRole('alert')).toHaveProperty('textContent', expect.stringContaining('Could not load traces'))
  expect(screen.getByRole('button', { name: 'Retry' })).toBeTruthy()
  expect(screen.queryByRole('link', { name: /sample|refund-policy-review/i })).toBeNull()
  expect(screen.queryByRole('heading', { name: 'No traces yet' })).toBeNull()
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

describe('failed local run: first error surfacing', () => {
  const failedId = 'abcdefabcdefabcdefabcdefabcdef01'
  const at = offset => String(BigInt(run.start_time_unix_nano) + BigInt(offset) * 1000000n)
  const item = (id, parent, name, type, code, start, exception) => ({ trace_id: failedId, span_id: id, parent_span_id: parent, name, operation_type: type, start_time_unix_nano: at(start), end_time_unix_nano: at(start + 1), status: { code }, attributes: type === 'run' ? { 'debugger.execution.mode': 'controlled' } : {}, resource: { 'service.name': 'tool-task-agent' }, events: exception ? [{ name: 'exception', time_unix_nano: at(start), attributes: { 'exception.type': exception } }] : [] })
  const spans = [item('a000000000000001', null, 'tool-task-agent', 'run', 'ERROR', 0), item('a000000000000002', 'a000000000000001', 'LocalTools.invoke', 'tool', 'ERROR', 1, 'ToolTimeout'), item('a000000000000003', 'a000000000000001', 'LocalTools.invoke', 'tool', 'ERROR', 2, 'ToolError')]
  const failed = { ...run, trace_id: failedId, name: 'tool-task-agent', status: 'ERROR', execution_mode: 'controlled', recorded_error_spans: 3, end_time_unix_nano: at(4),
    first_error: { span_id: 'a000000000000002', span_name: 'LocalTools.invoke', operation_type: 'tool', exception_type: 'ToolTimeout', originating_error_span_count: 2 } }
  spans[1].attributes = { 'debugger.step': 'pay', 'debugger.attempt': 1 }
  spans[2].attributes = { 'debugger.step': 'pay', 'debugger.attempt': 2, 'debugger.retry_of': spans[1].span_id }
  const recovered = { ...run, trace_id: 'abcdefabcdefabcdefabcdefabcdef02', name: 'Recovered run', recorded_error_spans: 1, recorded_recovered_retry: true }
  const fetcher = vi.fn(async url => {
    const selected = spans.find(value => url.endsWith('/spans/' + value.span_id))
    return { ok: true, json: async () => url.endsWith('/status') ? status : selected ? { run: failed, span: selected, retry_of: null, retries: [] } : url.endsWith(failedId) ? { run: failed, spans } : { mode: 'local', runs: [failed, recovered, run] } }
  })
  const selectedRow = async () => (await screen.findAllByRole('treeitem')).find(row => row.getAttribute('aria-selected') === 'true')

  it('lists each run on one line with no first-error line or mode badge, and hides all-unknown columns', async () => {
    window.history.replaceState(null, '', '/#/projects/local/runs')
    render(<App {...createApiAdapters(fetcher)}/> )
    const link = await screen.findByRole('link', { name: `tool-task-agent ${failedId}` })
    const row = link.closest('tr')
    expect(within(row).queryByRole('link', { name: /First recorded error/ })).toBeNull()
    expect(within(row).queryByText('Controlled')).toBeNull()
    expect(row.querySelector('.error-count').textContent).toBe('3')
    expect(row.querySelector('.error-count').dataset.tone).toBe('error')
    const clean = screen.getByRole('link', { name: `Captured run ${traceId}` }).closest('tr')
    expect(clean.querySelector('.error-count').dataset.tone).toBe('muted')
    expect(screen.queryByText(/root cause|cause:/i)).toBeNull()
    expect(screen.getByRole('button', { name: 'Sort by errors' }).title).toMatch(/including parents that carry a child's error/)
    expect(screen.queryByRole('columnheader', { name: /Completeness/ })).toBeNull()
    expect(screen.queryByRole('columnheader', { name: /Investigation/ })).toBeNull()
  })

  it('keeps recovered runs in Has span errors and preserves that filter after opening a failed run at its first error', async () => {
    window.history.replaceState(null, '', '/#/projects/local/runs')
    const user = userEvent.setup()
    render(<App {...createApiAdapters(fetcher)}/> )
    await screen.findByRole('link', { name: /Recovered run/ })
    const filters = screen.getByRole('complementary', { name: 'Trace filters' })
    await user.click(within(filters).getByRole('checkbox', { name: /^Failed/ }))
    await waitFor(() => expect(screen.queryByRole('link', { name: /Recovered run/ })).toBeNull())
    await user.click(screen.getByRole('button', { name: 'Remove Status: Failed' }))
    await user.click(within(filters).getByRole('checkbox', { name: /^Has error spans/ }))
    await screen.findByRole('link', { name: /Recovered run/ })
    await waitFor(() => expect(screen.queryByRole('link', { name: /Captured run/ })).toBeNull())
    await user.click(screen.getByRole('link', { name: `tool-task-agent ${failedId}` }))
    expect((await selectedRow()).getAttribute('data-span-id')).toBe('a000000000000002')
    const inspector = await screen.findByRole('region', { name: 'Span inspector' })
    expect(within(inspector).getByRole('heading', { name: 'Pay · attempt 1' })).toBeTruthy()
    // The full operation name is in the Details popover.
    await user.click(within(inspector).getByRole('button', { name: 'Details' }))
    expect(within(await screen.findByRole('dialog')).getByText('LocalTools.invoke')).toBeTruthy()
    await user.keyboard('{Escape}')
    await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull())
    expect(screen.getByRole('region', { name: 'Span inspector' })).toBeTruthy()
    expect(screen.queryByText('0 loaded')).toBeNull()
    await user.click(screen.getByRole('link', { name: 'Back to Traces' }))
    expect(await screen.findByRole('link', { name: /Recovered run/ })).toBeTruthy()
    expect(within(screen.getByRole('complementary', { name: 'Trace filters' })).getByRole('checkbox', { name: /^Has error spans/ }).checked).toBe(true)
  })

  it('selects first_error when the URL has no span, and an explicit span always wins', async () => {
    window.history.replaceState(null, '', `/#/projects/local/runs/${failedId}`)
    const first = render(<App {...createApiAdapters(fetcher)}/> )
    expect((await selectedRow()).getAttribute('data-span-id')).toBe('a000000000000002')
    first.unmount()
    window.history.replaceState(null, '', `/#/projects/local/runs/${failedId}?span=a000000000000003`)
    render(<App {...createApiAdapters(fetcher)}/> )
    expect((await selectedRow()).getAttribute('data-span-id')).toBe('a000000000000003')
  })

  it('summarises the project on Home and links failures to their first error', async () => {
    window.history.replaceState(null, '', '/#/projects/local')
    render(<App {...createApiAdapters(fetcher)}/> )
    expect(await screen.findByRole('heading', { name: 'Home' })).toBeTruthy()
    const traces = await screen.findByRole('region', { name: 'Traces' })
    expect(within(traces).getByText('3')).toBeTruthy()
    const status = screen.getByRole('region', { name: 'Execution status' })
    expect(within(status).getByText(/1 recovered after a retry/)).toBeTruthy()
    const failures = screen.getByRole('region', { name: 'Recent failed traces' })
    expect(within(failures).getByRole('link', { name: 'tool-task-agent' }).getAttribute('href')).toBe(`#/projects/local/runs/${failedId}?span=a000000000000002`)
    expect(within(failures).getByText('ToolTimeout · LocalTools.invoke (+1)')).toBeTruthy()
    // Traces exist, so the setup steps move below the summary instead of leading the page.
    expect(screen.getByRole('region', { name: 'Send your first trace' })).toBeTruthy()
    expect(screen.getByRole('button', { name: 'Refresh' })).toBeTruthy()
    expect(screen.getByRole('link', { name: 'Home' }).getAttribute('aria-current')).toBe('page')
  })

  it('turns the filter panel into a drawer on a narrow layout: Filters opens it, Esc closes it', async () => {
    window.history.replaceState(null, '', '/#/projects/local/runs')
    // A 700 px trace layout (1024 px window less the sidebar) has no room for an inline panel.
    const measure = HTMLElement.prototype.getBoundingClientRect
    vi.spyOn(HTMLElement.prototype, 'getBoundingClientRect').mockImplementation(function () { return this.classList.contains('traces-layout') ? { width: 700, height: 600, top: 0, left: 0, right: 700, bottom: 600 } : measure.call(this) })
    const user = userEvent.setup()
    render(<App {...createApiAdapters(fetcher)}/> )
    await screen.findByRole('link', { name: /Recovered run/ })
    expect(screen.queryByRole('complementary', { name: 'Trace filters' })).toBeNull()
    const toggle = screen.getByRole('button', { name: 'Filters' })
    expect(toggle.getAttribute('aria-expanded')).toBe('false')
    await user.click(toggle)
    const drawer = screen.getByRole('complementary', { name: 'Trace filters' })
    expect(drawer.closest('.filters-drawer')).toBeTruthy()
    expect(toggle.getAttribute('aria-expanded')).toBe('true')
    expect(document.activeElement).toBe(screen.getByRole('button', { name: 'Close filters' }))
    await user.keyboard('{Escape}')
    expect(screen.queryByRole('complementary', { name: 'Trace filters' })).toBeNull()
    expect(document.activeElement).toBe(screen.getByRole('button', { name: 'Filters' }))
    // The drawer's choice is not saved as the inline panel preference.
    expect(localStorage.getItem('agent-debugger.frontend.v1.traces.filters')).toBeNull()
    vi.restoreAllMocks()
  })

  it('opens filters from the left, moves focus between the toggles and offers JSON downloads in the top bar', async () => {
    window.history.replaceState(null, '', '/#/projects/local/runs')
    const user = userEvent.setup()
    render(<App {...createApiAdapters(fetcher)}/> )
    await screen.findByRole('link', { name: /Recovered run/ })
    expect(screen.queryByText('Matching traces')).toBeNull()
    await user.click(screen.getByRole('button', { name: 'Hide filters' }))
    expect(screen.queryByRole('complementary', { name: 'Trace filters' })).toBeNull()
    expect(document.activeElement).toBe(screen.getByRole('button', { name: 'Show filters' }))
    await user.click(screen.getByRole('button', { name: 'Show filters' }))
    expect(screen.getByRole('complementary', { name: 'Trace filters' })).toBeTruthy()
    expect(document.activeElement).toBe(screen.getByRole('button', { name: 'Hide filters' }))
    const topbar = () => within(document.querySelector('.topbar'))
    expect(topbar().getByRole('button', { name: 'Download JSON' }).disabled).toBe(false)
    expect(topbar().getByRole('button', { name: 'Refresh' })).toBeTruthy()
    await user.click(screen.getByRole('link', { name: `tool-task-agent ${failedId}` }))
    await screen.findByRole('heading', { name: 'tool-task-agent' })
    expect(topbar().getByRole('button', { name: 'Download JSON' }).disabled).toBe(false)
    expect(topbar().getByRole('link', { name: 'Back to Traces' })).toBeTruthy()
  })

  it('previews a trace from its row, steps with J and K, and closes with Esc back to the row', async () => {
    window.history.replaceState(null, '', '/#/projects/local/runs')
    const user = userEvent.setup()
    render(<App {...createApiAdapters(fetcher)}/> )
    await screen.findByRole('link', { name: /Recovered run/ })
    // A click on the row's empty space opens the preview; the ID stays in the URL.
    await user.click(screen.getByRole('link', { name: `tool-task-agent ${failedId}` }).closest('tr').lastElementChild)
    const peek = await screen.findByRole('region', { name: 'Trace preview' })
    expect(window.location.hash).toContain(`peek=${failedId}`)
    expect(within(peek).getByText('2 of 3')).toBeTruthy()
    expect(await within(peek).findByText('First recorded error')).toBeTruthy()
    expect(within(peek).getByText('Errors').nextElementSibling.textContent).toBe('3')
    // Shortcuts are listed on the info button, not in a footer.
    expect(within(peek).getByRole('button', { name: 'Keyboard shortcuts: J next trace · K previous trace · Esc close' })).toBeTruthy()
    expect(within(peek).queryByText('next')).toBeNull()
    // Beside the preview the table keeps Timestamp, Name, Status and Latency.
    expect(screen.getAllByRole('columnheader').map(cell => cell.textContent.replace(/[↑↓]/g, ''))).toEqual(expect.arrayContaining(['Timestamp', 'Name', 'Status', 'Latency']))
    expect(screen.getByRole('separator', { name: 'Resize trace preview' })).toBeTruthy()
    expect(within(peek).getByRole('link', { name: /Pay · attempt 1/ }).getAttribute('href')).toBe(`#/projects/local/runs/${failedId}?time=all&span=a000000000000002`)
    expect(within(peek).getByRole('link', { name: 'Open full trace' }).getAttribute('href')).toBe(`#/projects/local/runs/${failedId}?time=all`)
    await user.keyboard('j')
    await waitFor(() => expect(window.location.hash).toContain(`peek=${recovered.trace_id}`))
    expect(within(screen.getByRole('region', { name: 'Trace preview' })).getByRole('button', { name: 'Next trace' }).disabled).toBe(true)
    await user.keyboard('k'); await user.keyboard('k')
    await waitFor(() => expect(window.location.hash).toContain(`peek=${traceId}`))
    expect(within(screen.getByRole('region', { name: 'Trace preview' })).getByRole('button', { name: 'Previous trace' }).disabled).toBe(true)
    await user.keyboard('{Escape}')
    await waitFor(() => expect(screen.queryByRole('region', { name: 'Trace preview' })).toBeNull())
    expect(window.location.hash).not.toContain('peek=')
    await waitFor(() => expect(document.activeElement).toBe(screen.getByRole('button', { name: `Preview Captured run ${traceId}` })))
  })

  it('focuses search with / and hides columns like Langfuse table controls', async () => {
    window.history.replaceState(null, '', '/#/projects/local/runs')
    const user = userEvent.setup()
    render(<App {...createApiAdapters(fetcher)}/> )
    await screen.findByRole('link', { name: /Recovered run/ })
    await user.keyboard('/')
    expect(document.activeElement).toBe(screen.getByRole('searchbox', { name: 'Search traces' }))
    // No "/" or "↵" hints in the field.
    expect(document.querySelector('.search-field').textContent).toBe('')
    await user.click(screen.getByLabelText('Columns, 6 of 6 shown'))
    await user.click(screen.getByRole('menuitemcheckbox', { name: 'Timestamp' }))
    expect(screen.queryByRole('columnheader', { name: /Timestamp/ })).toBeNull()
    expect(localStorage.getItem('agent-debugger.frontend.v1.traces.columns.hidden')).toBe('startedAt')
    expect(screen.getByLabelText('Columns, 5 of 6 shown')).toBeTruthy()
    expect(screen.queryByLabelText(/Row height/)).toBeNull()
  })

  it('works the Columns menu and Rows per page select from the keyboard alone', async () => {
    window.history.replaceState(null, '', '/#/projects/local/runs')
    const user = userEvent.setup()
    render(<App {...createApiAdapters(fetcher)}/> )
    await screen.findByRole('link', { name: /Recovered run/ })
    // Columns menu: Enter opens it on the first item, Space toggles and keeps it open, Escape returns focus.
    const columns = screen.getByLabelText('Columns, 6 of 6 shown')
    columns.focus()
    await user.keyboard('{Enter}')
    const menu = await screen.findByRole('menu')
    expect(within(menu).getByRole('menuitemcheckbox', { name: 'Name' }).getAttribute('aria-disabled')).toBe('true')
    const latency = within(menu).getByRole('menuitemcheckbox', { name: 'Latency' })
    while (document.activeElement !== latency) await user.keyboard('{ArrowDown}')
    await user.keyboard(' ')
    expect(latency.getAttribute('aria-checked')).toBe('false')
    expect(screen.getByRole('menu')).toBeTruthy()
    expect(screen.queryByRole('columnheader', { name: /Latency/ })).toBeNull()
    await user.keyboard('{Escape}')
    await waitFor(() => expect(screen.queryByRole('menu')).toBeNull())
    expect(document.activeElement).toBe(screen.getByLabelText('Columns, 5 of 6 shown'))
    // Rows per page: a combobox; arrows move, Enter picks, Escape cancels without a change.
    const rows = screen.getByRole('combobox', { name: 'Rows per page' })
    expect(rows.textContent).toBe('25')
    rows.focus()
    await user.keyboard('{Enter}')
    const listbox = await screen.findByRole('listbox')
    expect(within(listbox).getAllByRole('option').map(option => option.textContent)).toEqual(['5', '10', '25', '50'])
    await user.keyboard('{Escape}')
    await waitFor(() => expect(screen.queryByRole('listbox')).toBeNull())
    expect(rows.textContent).toBe('25')
    expect(document.activeElement).toBe(rows)
    await user.keyboard('{Enter}')
    await screen.findByRole('listbox')
    const ten = screen.getByRole('option', { name: '10' })
    while (document.activeElement !== ten) await user.keyboard('{ArrowUp}')
    await user.keyboard('{Enter}')
    await waitFor(() => expect(screen.getByRole('combobox', { name: 'Rows per page' }).textContent).toBe('10'))
    expect(window.location.hash).toContain('pageSize=10')
  })
})
