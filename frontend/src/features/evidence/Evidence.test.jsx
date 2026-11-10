import { describe, it, expect, vi } from 'vitest'
import { render, screen, within, waitFor, fireEvent } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import App from '../../test/FixtureApp.jsx'
import { investigationRepository } from '../../data/investigationRepository.js'

const hash = (run = 'R-1042', query = '') => `#/projects/agent-examples/runs/${run}/evidence${query ? '?' + query : ''}`
async function open(query = '', repository = investigationRepository, run = 'R-1042') {
  window.history.replaceState(null, '', '/' + hash(run, query))
  const user = userEvent.setup(); render(<App investigationRepository={repository}/>);
  await screen.findByRole('heading', { name: /Retrieved policy|Eligibility result|Historical policy/ })
  return user
}
const pane = slot => screen.getByRole('region', { name: `Source ${slot}` })
describe('Evidence Focus', () => {
  it('shows exact immutable sources with explicit snapshot, paths and revision', async () => {
    await open()
    expect(await within(pane('A')).findByText('30 days')).toBeTruthy()
    expect(await within(pane('B')).findByText('14 days')).toBeTruthy()
    expect(document.querySelector('.evidence-attempt strong').textContent).toBe('snap-1042-a')
    expect(screen.getByText('output.refund_window_days')).toBeTruthy()
    expect(screen.getByText('Revision 7')).toBeTruthy()
    expect(pane('B').querySelector('mark').textContent).toBe('14 days')
    expect(screen.queryByRole('button', { name: 'Inspect in analyzed trace' })).toBeNull()
  })
  it('explicitly assigns three citations, swaps occupied slots and restores paired/focused reading', async () => {
    const user = await open()
    await within(pane('B')).findByText('14 days')
    const body = pane('B').querySelector('.evidence-reading')
    body.scrollTop = 92; fireEvent.scroll(body)
    await user.selectOptions(screen.getByLabelText('Source A citation'), 'model')
    expect(await within(pane('A')).findByText('input.refund_window_days')).toBeTruthy()
    expect(within(pane('B')).getByText('Revision 7')).toBeTruthy()
    await user.click(screen.getByRole('button', { name: 'Focus source B' }))
    expect(document.querySelector('[aria-label="Source A"]').hidden).toBe(true)
    await user.click(screen.getByRole('button', { name: 'Compare sources', exact: true }))
    expect(pane('B').querySelector('.evidence-reading').scrollTop).toBe(92)
    await user.selectOptions(screen.getByLabelText('Source A citation'), 'document')
    expect(screen.getByLabelText('Source B citation').value).toBe('model')
    expect(screen.getAllByRole('button', { name: /Assign citation .* to Source A/ })).toHaveLength(3)
  })
  it('never substitutes a current source when historical evidence is missing or mismatched', async () => {
    const user = await open('evidenceAttempt=analysis-1042-0')
    expect(await screen.findByText(/Captured Revision 6 is no longer available/)).toBeTruthy()
    expect(screen.getAllByRole('region', { name: /Source [AB]/ })).toHaveLength(1)
    expect(screen.queryByRole('button', { name: 'Copy source A' })).toBeNull()
    await user.selectOptions(screen.getByLabelText('Finding'), 'F-02')
    expect(await screen.findByText(/Snapshot mismatch/)).toBeTruthy()
    expect(screen.queryByText('30 days')).toBeNull()
    expect(screen.queryByRole('button', { name: 'Copy source A' })).toBeNull()
  })
  it('keeps unresolved paths unhighlighted and captured HTML inert', async () => {
    const repository = { ...investigationRepository, readSource: async args => args.citationId === 'retrieval' ? { snapshotId: 'snap-1042-a', state: 'captured', value: { text: '<img src=x onerror=alert(1)>' }, citedValue: 30 } : investigationRepository.readSource(args) }
    await open('', repository)
    expect(await screen.findByText(/Cited value could not be resolved/)).toBeTruthy()
    expect(screen.getByText('<img src=x onerror=alert(1)>')).toBeTruthy()
    expect(pane('A').querySelector('img')).toBeNull()
    expect(pane('A').querySelector('mark')).toBeNull()
  })
  it.each([1, 2])('renders %i available citation(s) without fabricating comparison sources', async count => {
    const repository = { ...investigationRepository, readInvestigation: async args => {
      const data = await investigationRepository.readInvestigation(args)
      return { ...data, attempts: [{ ...data.attempts[0], referenceState: 'Not provided', findings: [{ ...data.attempts[0].findings[0], citations: data.attempts[0].findings[0].citations.slice(0, count) }] }] }
    } }
    await open('', repository, 'R-1041')
    expect(await within(pane('A')).findByText('false', { selector: 'mark.mono' })).toBeTruthy()
    expect(screen.getAllByRole('region', { name: /^Source [AB]$/ })).toHaveLength(count)
    expect(document.querySelector('.evidence-reference-state').textContent).toBe('Not provided')
  })
  it('preserves captured JSON and exact quote highlights through keyboard source assignment', async () => {
    const user = await open()
    await within(pane('B')).findByText('14 days')
    await user.selectOptions(screen.getByLabelText('Source B presentation'), 'JSON')
    const code = pane('B').querySelector('code')
    expect(JSON.parse(code.textContent)).toContain('within 14 days of delivery')
    expect(code.querySelector('mark').textContent).toBe('within 14 days of delivery')
    const chip = screen.getByRole('button', { name: 'Assign citation 3 Model input to Source A' })
    chip.focus(); await user.keyboard('{Enter}')
    expect(await within(pane('A')).findByText('input.refund_window_days')).toBeTruthy()
    expect(document.activeElement.textContent).toBe('compose-response')
  })
  it('shows the pending and skipped investigation states without offering findings', async () => {
    window.history.replaceState(null, '', '/#/projects/sandbox/runs/R-2040/evidence')
    const user = userEvent.setup(); render(<App/>)
    expect(await screen.findByRole('heading', { name: 'Investigation pending' })).toBeTruthy()
    await user.selectOptions(screen.getByLabelText('Project'), 'agent-examples')
    await screen.findByRole('searchbox', { name: 'Search runs' })
    window.location.hash = '#/projects/sandbox/runs/R-2041/evidence'
    expect(await screen.findByRole('heading', { name: 'Investigation unavailable' })).toBeTruthy()
    expect(screen.queryByRole('region', { name: 'Source A' })).toBeNull()
  })
  it('ignores a stale source response after assignment changes and keeps pane failure local', async () => {
    let resolve
    const repository = { ...investigationRepository, readSource: vi.fn(args => args.citationId === 'retrieval' ? new Promise(done => { resolve = done }) : args.citationId === 'document' ? Promise.reject(new Error('Historical read failed')) : investigationRepository.readSource(args)) }
    const user = await open('', repository)
    expect(await within(pane('B')).findByText('Historical read failed')).toBeTruthy()
    await user.selectOptions(screen.getByLabelText('Source A citation'), 'model')
    expect(await within(pane('A')).findByText('30 days')).toBeTruthy()
    resolve({ snapshotId: 'snap-1042-a', state: 'captured', value: 'STALE VALUE' })
    await waitFor(() => expect(screen.queryByText('STALE VALUE')).toBeNull())
    expect(within(pane('B')).getByRole('button', { name: 'Retry source B' })).toBeTruthy()
  })
  it('restores exact evidence choices after inspecting a current span and preserves trace context', async () => {
    const user = await open('span=7b83c2d900000003&panel=pinned&view=timeline&from=1071&to=3213&spanSearch=classify&search=refund')
    await user.selectOptions(screen.getByLabelText('Source A citation'), 'model')
    await user.click(within(pane('A')).getByRole('link', { name: 'Open current span' }))
    await screen.findByRole('region', { name: 'Span inspector' })
    expect(screen.getByRole('button', { name: 'Timeline' }).getAttribute('aria-pressed')).toBe('true')
    expect(screen.getByRole('searchbox', { name: 'Search loaded spans' }).value).toBe('classify')
    expect(screen.getByRole('button', { name: 'Reveal selected span' })).toBeTruthy()
    expect(window.location.hash).toContain('from=1071')
    await user.click(screen.getByRole('link', { name: 'Back to evidence' }))
    await screen.findByRole('heading', { name: 'Retrieved policy differs from the authoritative source' })
    expect(screen.getByLabelText('Source A citation').value).toBe('model')
    expect(screen.getByLabelText('Source B citation').value).toBe('document')
  })
  it('returns from evidence to the latest selected span with open overlay and inspector tab', async () => {
    window.history.replaceState(null, '', '/#/projects/agent-examples/runs/R-1042')
    const user = userEvent.setup(); render(<App/>)
    await screen.findByRole('tree', { name: 'Execution spans' })
    await user.click(screen.getByRole('treeitem', { name: /classify-request/ }))
    await user.click(screen.getByRole('tab', { name: 'Metadata' }))
    await user.click(screen.getByRole('link', { name: 'View 1 finding' }))
    await screen.findByRole('heading', { name: 'Retrieved policy differs from the authoritative source' })
    await user.click(screen.getByRole('link', { name: 'Back to trace' }))
    await screen.findByRole('tree', { name: 'Execution spans' })
    expect(screen.getByRole('treeitem', { name: /classify-request/ }).getAttribute('aria-selected')).toBe('true')
    expect(screen.getByRole('region', { name: 'Span inspector' })).toBeTruthy()
    expect(screen.getByRole('tab', { name: 'Metadata' }).getAttribute('aria-selected')).toBe('true')
  })
  it.each([['R-1040', 'No grounded findings returned'], ['R-1036', 'Investigation not requested'], ['R-1038', 'Investigation failed']])('shows %s without inventing findings or request success', async (run, message) => {
    window.history.replaceState(null, '', '/' + hash(run))
    render(<App/>); expect(await screen.findByRole('heading', { name: message })).toBeTruthy()
    expect(screen.queryByRole('region', { name: 'Source A' })).toBeNull()
    expect(screen.queryByText(/Run is correct/)).toBeNull()
  })
})
