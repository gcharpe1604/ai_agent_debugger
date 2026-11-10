import { beforeEach, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import App from '../../test/FixtureApp.jsx'
import { traceRepository } from '../../data/traceRepository.js'

beforeEach(() => window.history.replaceState(null, '', '/#/projects/agent-examples/runs/R-1040?search=order'))
async function open(repository = traceRepository) {
  const user = userEvent.setup()
  render(<App traceRepository={repository}/>)
  await screen.findByRole('tree', { name: 'Execution spans' })
  return user
}
it('switches the same virtualized explorer without losing overlay, selection or payload presentation', async () => {
  const repository = { ...traceRepository, readSpan: vi.fn(traceRepository.readSpan) }
  const user = await open(repository)
  await user.click(screen.getByRole('treeitem', { name: /^lookup-order · attempt 1 · Tool/ }))
  await screen.findByText('Order service did not respond within 1,200 ms.')
  await user.click(screen.getByRole('button', { name: 'Raw' }))
  const tree = screen.getByRole('tree', { name: 'Execution spans' }), body = screen.getByRole('tabpanel')
  await user.click(screen.getByRole('button', { name: 'Timeline', exact: true }))
  expect(screen.getByRole('tree', { name: 'Execution spans' })).toBe(tree)
  expect(screen.getByRole('tabpanel')).toBe(body)
  expect(document.querySelector('.trace-row.selected').getAttribute('data-span-id')).toBe('a9e5d27100000005')
  expect(screen.getByRole('button', { name: 'Raw' }).getAttribute('aria-pressed')).toBe('true')
  await user.click(screen.getByRole('button', { name: 'Zoom in' }))
  expect(repository.readSpan).toHaveBeenCalledTimes(1)
  await user.click(screen.getByRole('button', { name: 'Tree', exact: true }))
  expect(screen.getByRole('tabpanel')).toBe(body)
  expect(window.location.hash).toContain('search=order')
})
it('keeps pinning, filters, row anchors and the explicit time window across view switches', async () => {
  window.history.replaceState(null, '', '/#/projects/agent-examples/runs/R-7000')
  const user = await open()
  await user.click(screen.getAllByRole('treeitem')[0])
  await user.click(screen.getByRole('button', { name: 'Pin span inspector' }))
  const tree = screen.getByRole('tree', { name: 'Execution spans' })
  tree.scrollTop = 4000; fireEvent.scroll(tree)
  await user.click(screen.getByRole('button', { name: 'Timeline', exact: true }))
  expect(tree.scrollTop).toBe(4000)
  await user.click(screen.getByRole('button', { name: 'Zoom in' }))
  const windowLabel = screen.getByLabelText('Visible time window').textContent
  await user.click(screen.getByRole('button', { name: 'Tree', exact: true }))
  await user.click(screen.getByRole('button', { name: 'Timeline', exact: true }))
  expect(screen.getByLabelText('Visible time window').textContent).toBe(windowLabel)
  expect(screen.getByRole('separator', { name: 'Resize span inspector' })).toBeTruthy()
  expect(screen.getAllByRole('treeitem').length).toBeLessThan(35)
})
it('keeps keyboard hierarchy navigation and changes only the explicit time window for timing keys', async () => {
  const user = await open()
  await user.click(screen.getByRole('button', { name: 'Timeline', exact: true }))
  const tree = screen.getByRole('tree', { name: 'Execution spans' })
  tree.focus(); await user.keyboard('{Home}{ArrowDown}{Enter}')
  expect(screen.getByRole('treeitem', { name: /^support-agent/ }).getAttribute('aria-selected')).toBe('true')
  await user.click(screen.getByRole('button', { name: 'Close span inspector' }))
  await user.click(screen.getByRole('button', { name: 'Zoom in' }))
  const start = screen.getByLabelText('Visible time window').textContent
  await user.click(screen.getByRole('button', { name: 'Next time window' }))
  expect(screen.getByLabelText('Visible time window').textContent).not.toBe(start)
  await user.click(screen.getByRole('button', { name: 'Fit run' }))
  expect(screen.getByLabelText('Visible time window').textContent).toContain('2.42 s')
})
it('shows missing/invalid timing and points without inventing a drawn interval', async () => {
  const repository = { ...traceRepository, async readTrace(args) {
    const data = await traceRepository.readTrace(args)
    return { ...data, spans: data.spans.map((span, i) => i === 2 ? { ...span, start: null } : i === 3 ? { ...span, end: span.start - 1 } : i === 4 ? { ...span, duration: 0 } : span) }
  } }
  const user = await open(repository)
  await user.click(screen.getByRole('button', { name: 'Timeline', exact: true }))
  expect(screen.getByText('Timing unavailable')).toBeTruthy()
  expect(screen.getByText('Invalid timing')).toBeTruthy()
  expect(document.querySelector('.timeline-point')).toBeTruthy()
})
it('moves to the last loaded match when Previous starts without a selected match', async () => {
  const user = await open()
  await user.type(screen.getByRole('searchbox', { name: 'Search loaded spans' }), 'GET /orders')
  await user.click(screen.getByRole('button', { name: 'Previous matching span' }))
  expect(document.querySelector('.trace-row.selected').getAttribute('data-span-id')).toBe('a9e5d27100000008')
})
it('does not automatically zoom to a selection outside the window; Fit selected is explicit', async () => {
  const user = await open()
  await user.click(screen.getByRole('button', { name: 'Timeline', exact: true }))
  await user.click(screen.getByRole('button', { name: 'Zoom in' }))
  await user.click(screen.getByRole('button', { name: 'Zoom in' }))
  const before = screen.getByLabelText('Visible time window').textContent
  await user.click(screen.getByRole('treeitem', { name: /^classify-request/ }))
  expect(screen.getByLabelText('Visible time window').textContent).toBe(before)
  expect(document.querySelector('[data-span-id="a9e5d27100000003"] [data-timing="before"]')).toBeTruthy()
  await user.click(screen.getByRole('button', { name: 'Pin span inspector' }))
  await user.click(screen.getByLabelText('Execution options'))
  await user.click(screen.getByRole('button', { name: 'Fit selected interval' }))
  expect(screen.getByLabelText('Visible time window').textContent).not.toBe(before)
  expect(screen.getByRole('region', { name: 'Span inspector' })).toBeTruthy()
})
it('disables unsupported timing controls when neither run bounds nor loaded timestamps are available', async () => {
  const repository = { ...traceRepository, async readTrace(args) { const data = await traceRepository.readTrace(args); return { ...data, run: { ...data.run, durationMs: null }, spans: data.spans.map(span => ({ ...span, start: null })) } } }
  const user = await open(repository)
  await user.click(screen.getByRole('button', { name: 'Timeline', exact: true }))
  expect(screen.getByRole('button', { name: 'Fit run' }).disabled).toBe(true)
  expect(screen.getByRole('button', { name: 'Zoom in' }).disabled).toBe(true)
  expect(screen.getByLabelText('Visible time window').textContent).toBe('Timing unavailable')
})
it('restores the timeline, window and selected span through browser workspace navigation', async () => {
  const user = await open()
  await user.click(screen.getByRole('button', { name: 'Timeline', exact: true }))
  await user.click(screen.getByRole('button', { name: 'Zoom in' }))
  await user.click(screen.getByRole('treeitem', { name: /^classify-request/ }))
  const before = screen.getByLabelText('Visible time window').textContent
  await user.click(screen.getByRole('link', { name: 'Back to Traces' }))
  await screen.findByRole('searchbox', { name: 'Search traces' })
  window.history.back()
  await screen.findByRole('region', { name: 'Span inspector' })
  expect(screen.getByRole('button', { name: 'Timeline', exact: true }).getAttribute('aria-pressed')).toBe('true')
  expect(screen.getByLabelText('Visible time window').textContent).toBe(before)
})
