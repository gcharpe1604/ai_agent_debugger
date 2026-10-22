// Regression-test data only. Never imported by the application entry point.
import { projects, runs, sampleWindow } from '../data/fixtures.js'
import { selectRuns } from '../data/runRepository.js'

export const fixtureTimeWindow = { ...sampleWindow, recentStart: '2026-10-15T10:30:00Z' }
export const fixtureRepository = Object.freeze({
  projects,
  async listRuns({ projectId, query, signal }) {
    signal?.throwIfAborted()
    if (!projects.some(project => project.id === projectId)) throw new Error('Project unavailable')
    await Promise.resolve()
    signal?.throwIfAborted()
    return selectRuns(runs, projectId, query, fixtureTimeWindow)
  },
})
