import { it, expect } from 'vitest'
import { traceRepository } from './traceRepository.js'

it('keeps structural records separate from captured payloads', async () => {
  const trace = await traceRepository.readTrace({ projectId: 'agent-examples', runId: 'R-1040' })
  expect(trace.run.name).toBe('order-status-lookup')
  expect(trace.spans).toHaveLength(10)
  expect(trace.spans[0]).not.toHaveProperty('input')
  const failed = trace.spans.find(s => s.name.includes('attempt 1'))
  const detail = await traceRepository.readSpan({ projectId: 'agent-examples', runId: 'R-1040', spanId: failed.id })
  expect(detail.status).toBe('ERROR')
  expect(detail.retries[0].status).toBe('OK')
  expect(detail.outputCapture.state).toBe('unavailable')
})
it('uses exact deterministic scale sizes and distinguishes partial capture from local limits', async () => {
  for (const [id, known, loaded] of [['R-6100', 100, 100], ['R-7000', 1000, 1000], ['R-8100', 2100, 840]]) {
    const trace = await traceRepository.readTrace({ projectId: 'agent-examples', runId: id })
    expect(trace.knownCount).toBe(known); expect(trace.spans).toHaveLength(loaded)
    expect(new Set(trace.spans.map(s => s.id)).size).toBe(loaded)
  }
  const more = await traceRepository.readTrace({ projectId: 'agent-examples', runId: 'R-8100', limit: 1260 })
  expect(more.spans).toHaveLength(1260); expect(more.run.completeness).toBe('Partial')
})
it('rejects cross-project IDs and aborted reads', async () => {
  await expect(traceRepository.readTrace({ projectId: 'sandbox', runId: 'R-1040' })).rejects.toThrow('Run unavailable')
  const controller = new AbortController(); controller.abort()
  await expect(traceRepository.readTrace({ projectId: 'agent-examples', runId: 'R-1040', signal: controller.signal })).rejects.toMatchObject({ name: 'AbortError' })
})
it('does not infer retry relationships from neighboring shipping operations', async () => {
  const trace = await traceRepository.readTrace({ projectId: 'agent-examples', runId: 'R-6100' })
  const validation = trace.spans.find(span => span.name === 'validate-shipping-quote')
  const detail = await traceRepository.readSpan({ projectId: 'agent-examples', runId: 'R-6100', spanId: validation.id })
  expect(detail.retryOf).toBeUndefined()
  expect(detail.retries).toEqual([])
})
