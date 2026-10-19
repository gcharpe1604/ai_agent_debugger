import { describe, it, expect } from 'vitest'
import { investigationRepository } from './investigationRepository.js'

describe('authored investigation adapter', () => {
  it('scopes attempts and immutable evidence by project, run and snapshot', async () => {
    const args = { projectId: 'agent-examples', runId: 'R-1042' }
    const result = await investigationRepository.readInvestigation(args)
    expect(result.attempts[0].findings[0].citations).toHaveLength(3)
    const source = await investigationRepository.readSource({ ...args, attemptId: 'analysis-1042-1', citationId: 'retrieval' })
    expect(source.snapshotId).toBe('snap-1042-a')
    expect(source.value.refund_window_days).toBe(30)
    expect(Object.isFrozen(source.value)).toBe(true)
    await expect(investigationRepository.readInvestigation({ ...args, projectId: 'sandbox' })).rejects.toThrow(/unavailable/i)
    await expect(investigationRepository.readSource({ ...args, attemptId: 'other', citationId: 'retrieval' })).rejects.toThrow(/unavailable/i)
  })
  it('retains failed, pending, not-requested and completed zero findings independently', async () => {
    const get = (runId, projectId = 'agent-examples') => investigationRepository.readInvestigation({ projectId, runId })
    expect((await get('R-1040')).attempts[0].findings).toEqual([])
    expect((await get('R-1038')).state).toBe('Failed')
    expect((await get('R-1036')).attempts).toEqual([])
    expect((await get('R-2040', 'sandbox')).state).toBe('Pending')
    expect((await get('R-2041', 'sandbox')).state).toBe('Skipped')
  })
  it('returns historical unavailability without replacing the source and respects cancellation', async () => {
    const args = { projectId: 'agent-examples', runId: 'R-1042' }
    const missing = await investigationRepository.readSource({ ...args, attemptId: 'analysis-1042-0', citationId: 'prior-document' })
    expect(missing.state).toBe('unavailable')
    expect(missing.value).toBeUndefined()
    const controller = new AbortController(); controller.abort()
    await expect(investigationRepository.readInvestigation({ ...args, signal: controller.signal })).rejects.toThrow()
  })
})
