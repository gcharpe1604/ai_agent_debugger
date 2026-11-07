import { describe, it, expect, vi } from 'vitest'
import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import App from '../test/FixtureApp.jsx'
import { fixtureRepository } from '../test/fixtureRepository.js'
import { investigationRepository } from '../data/investigationRepository.js'
import { traceRepository } from '../data/traceRepository.js'
import { buildIndex, visibleTree } from '../features/trace/treeModel.js'
import CapturedEvidence from '../features/evidence/CapturedEvidence.jsx'
import Payload from '../features/trace/Payload.jsx'
import { parseQuery } from '../features/runs/query.js'
import { selectRuns } from '../data/runRepository.js'

const navigate = search => { window.location.hash = '#/projects/agent-examples/runs/R-1042/evidence' + search }
describe('Milestone 3.1 repairs', () => {
  it('retains Running in Run Explorer query filters instead of silently widening the query', () => {
    const query = parseQuery('investigation=Running&time=all')
    expect(query.investigations).toEqual(['Running'])
    expect(selectRuns([{ id: 'a', projectId: 'p', name: 'active', traceId: 'a', investigation: 'Running' }, { id: 'b', projectId: 'p', name: 'done', traceId: 'b', investigation: 'Completed' }], 'p', query).items.map(item => item.id)).toEqual(['a'])
  })
  it('opens the actual latest supplied attempt when a stale link follows a cached earlier attempt', async () => {
    window.history.replaceState(null, '', '/#/projects/agent-examples/runs/R-1042/evidence?evidenceAttempt=analysis-1042-0')
    const user = userEvent.setup(); render(<App/>)
    await screen.findByRole('heading', { name: 'Historical policy citation is unavailable' })
    navigate('?evidenceAttempt=deleted')
    await user.click(await screen.findByRole('link', { name: 'Open latest supplied attempt' }))
    await screen.findByRole('heading', { name: 'Retrieved policy differs from the authoritative source' })
    expect(screen.getByLabelText('Investigation attempt').value).toBe('analysis-1042-1')
    expect(window.location.hash).toContain('evidenceAttempt=analysis-1042-1')
  })
  it.each(['Pending', 'Running'])('presents %s accurately without an early zero-findings conclusion', async state => {
    window.history.replaceState(null, '', '/#/projects/agent-examples/runs/R-1042/evidence')
    const repository = { ...investigationRepository, readInvestigation: async args => {
      const data = await investigationRepository.readInvestigation(args)
      return { ...data, state, attempts: [{ ...data.attempts[0], state, findings: [] }] }
    } }
    render(<App investigationRepository={repository}/> )
    expect(await screen.findByRole('heading', { name: `Investigation ${state.toLowerCase()}` })).toBeTruthy()
    expect(screen.queryByText('No grounded findings returned')).toBeNull()
  })
  it('keeps earlier findings reachable from a newer failed investigation and labels the earlier attempt', async () => {
    window.history.replaceState(null, '', '/#/projects/agent-examples/runs/R-1042')
    const repository = { ...investigationRepository, readInvestigation: async args => {
      const data = await investigationRepository.readInvestigation(args)
      return { ...data, state: 'Failed', attempts: [{ ...data.attempts[0], id: 'analysis-1042-2', label: 'Attempt 2', state: 'Failed', findings: [], error: 'Investigation failed safely' }, ...data.attempts] }
    } }
    const user = userEvent.setup(); render(<App investigationRepository={repository}/> )
    await screen.findByRole('tree', { name: 'Execution spans' })
    await user.click(screen.getByLabelText('Investigation details'))
    await user.click(await screen.findByRole('link', { name: /View earlier findings.*Attempt 1/ }))
    await screen.findByRole('heading', { name: 'Retrieved policy differs from the authoritative source' })
    expect(screen.getByLabelText('Investigation attempt').value).toBe('analysis-1042-1')
    expect(screen.getByLabelText('Investigation attempt').textContent).toContain('Attempt 2 · Failed')
  })
  it('shows a useful zero-project state without a fabricated project destination', async () => {
    render(<App repository={{ ...fixtureRepository, projects: [] }}/> )
    expect(await screen.findByRole('heading', { name: 'Create your first project' })).toBeTruthy()
    expect(screen.getByLabelText('Project').disabled).toBe(true)
    expect(screen.queryByRole('link', { name: 'Open sample Runs' })).toBeNull()
  })
  it.each([['array', []], ['object', {}]])('renders an empty captured %s in Readable and JSON', (_name, value) => {
    const props = { source: { value }, citation: { path: [] }, resolved: true }
    const view = render(<CapturedEvidence {...props} format="Readable"/> )
    expect(view.container.textContent).toBe(JSON.stringify(value))
    view.rerender(<CapturedEvidence {...props} format="JSON"/> )
    expect(view.container.querySelector('code').textContent.trim()).toBe(JSON.stringify(value))
  })
  it('does not guess a highlight for an unresolved path resembling an internal marker', () => {
    const view = render(<CapturedEvidence source={{ value: { __unresolved_citation__: 'captured text' } }} citation={{ path: ['missing'] }} resolved={false} format="Readable"/> )
    expect(view.container.querySelector('mark')).toBeNull()
    expect(view.container.textContent).toContain('captured text')
  })
  it('keeps unknown totals distinct from loaded children and reveals unloaded-child limits', () => {
    const spans = [{ id: 'p', parentId: null, name: 'parent', type: 'agent', childCount: null }, { id: 'c', parentId: 'p', name: 'child', type: 'tool', childCount: 0 }, { id: 'u', parentId: null, name: 'unloaded', type: 'agent', childCount: 3 }]
    const rows = visibleTree(buildIndex(spans), new Set(['p', 'u']), { search: '', type: '', status: '' }).rows
    expect(rows.find(row => row.id === 'p')).toMatchObject({ childLoaded: 1, childKnown: null })
    expect(rows.find(row => row.id === 'c')).toMatchObject({ childKnown: 0 })
    expect(rows.find(row => row.id === 'u')).toMatchObject({ childLoaded: 0, childKnown: 3, hasChildren: true })
  })
  it('shows unknown and unloaded counts in both Tree and Timeline without claiming a leaf', async () => {
    window.history.replaceState(null, '', '/#/projects/agent-examples/runs/R-1040')
    const repository = { ...traceRepository, readTrace: async args => {
      const data = await traceRepository.readTrace(args)
      return { ...data, knownCount: null, spans: data.spans.map((span, i) => ({ ...span, childCount: i === 0 ? null : i === data.spans.length - 1 ? 2 : span.childCount })) }
    } }
    const user = userEvent.setup(); render(<App traceRepository={repository}/> )
    const tree = await screen.findByRole('tree', { name: 'Execution spans' })
    expect(await screen.findByText('10 loaded · total unknown')).toBeTruthy()
    expect(within(tree).getByText('1 loaded · total unknown')).toBeTruthy()
    expect(within(tree).getByText('0/2 children')).toBeTruthy()
    await user.click(screen.getByRole('button', { name: 'Expand record-decision' }))
    expect(await screen.findByText(/Children are not loaded.*record-decision/)).toBeTruthy()
    await user.click(screen.getByRole('button', { name: 'Timeline', exact: true }))
    expect(within(tree).getByText(/1 loaded · total unknown/)).toBeTruthy()
    await user.click(screen.getByLabelText('Execution options'))
    await user.type(screen.getByLabelText('Jump to loaded span ID'), '00000000000000ff')
    await user.click(screen.getByRole('button', { name: 'Jump to span' }))
    expect(await screen.findByText(/Total structure size is unknown; lookup covers loaded spans only/)).toBeTruthy()
  })
  it('leaves an obscured background control focused and exposed rather than trapping focus', async () => {
    window.history.replaceState(null, '', '/#/projects/agent-examples/runs/R-1040?span=a9e5d27100000007&panel=overlay')
    const user = userEvent.setup(); render(<App/> )
    const inspector = await screen.findByRole('region', { name: 'Span inspector' })
    const control = screen.getByLabelText('Span filters')
    vi.spyOn(inspector, 'getBoundingClientRect').mockReturnValue({ left: 700, right: 1250, top: 96, bottom: 780, width: 550, height: 684 })
    vi.spyOn(control, 'getBoundingClientRect').mockReturnValue({ left: 1180, right: 1210, top: 100, bottom: 130, width: 30, height: 30 })
    screen.getByRole('searchbox', { name: 'Search loaded spans' }).focus(); await user.tab()
    expect(document.activeElement).toBe(control)
    expect(screen.queryByRole('region', { name: 'Span inspector' })).toBeNull()
    expect(screen.getByRole('treeitem', { name: /lookup-order · attempt 2/ }).getAttribute('aria-selected')).toBe('true')
    expect(screen.getByRole('tree', { name: 'Execution spans' })).toBeTruthy()
  })
  it('contains malformed trace data and retries the read without losing Runs navigation', async () => {
    window.history.replaceState(null, '', '/#/projects/agent-examples/runs/R-1040?search=order')
    vi.spyOn(console, 'error').mockImplementation(() => {})
    let first = true
    const repository = { ...traceRepository, readTrace: async args => {
      const data = await traceRepository.readTrace(args)
      if (first) { first = false; return { ...data, spans: null } }
      return data
    } }
    const user = userEvent.setup(); render(<App traceRepository={repository}/> )
    const retry = await screen.findByRole('button', { name: 'Retry view' })
    expect(document.activeElement).toBe(screen.getByRole('alert'))
    expect(screen.getByRole('link', { name: 'Back to Runs' }).getAttribute('href')).toContain('search=order')
    await user.click(retry)
    await screen.findByRole('tree', { name: 'Execution spans' })
  })
  it('keeps unexpected message entries inert and inspectable rather than crashing', () => {
    render(<Payload label="Input" capture={{ state: 'captured' }} value={{ messages: [null, 42, { role: { unexpected: true }, content: '<script>no()</script>' }] }} format="Readable"/> )
    expect(screen.getByText('42')).toBeTruthy()
    expect(document.querySelector('script')).toBeNull()
    expect(screen.getByText(/<script>no\(\)<\/script>/)).toBeTruthy()
  })
})
