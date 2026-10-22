import { investigationFixtures } from './investigationFixtures.js'

// Replaceable presentation adapter only. No transport, lifecycle or wire contract.
export const investigationRepository = Object.freeze({
  async readInvestigation({ projectId, runId, signal }) {
    signal?.throwIfAborted()
    const record = investigationFixtures.get(`${projectId}/${runId}`)
    if (!record) throw new Error('Investigation unavailable in this sample project/run')
    await Promise.resolve(); signal?.throwIfAborted()
    return { run: record.run, state: record.state, attempts: record.attempts }
  },
  async readSource({ projectId, runId, attemptId, citationId, signal }) {
    signal?.throwIfAborted()
    const record = investigationFixtures.get(`${projectId}/${runId}`)
    const source = record?.sources[attemptId]?.[citationId]
    if (!source) throw new Error('Analyzed evidence unavailable for this attempt/source')
    await Promise.resolve(); signal?.throwIfAborted()
    return source
  },
})
