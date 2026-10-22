// No seeded records, fabricated sessions or fallback telemetry.
const unavailable = message => async () => { throw Object.assign(new Error(message), { kind: 'disconnected' }) }

export const disconnectedRuns = Object.freeze({
  projects: [], listRuns: unavailable('Run data is not connected.'),
})
export const disconnectedTraces = Object.freeze({
  readTrace: unavailable('Trace data is not connected.'),
  readSpan: unavailable('Span data is not connected.'),
})
export const disconnectedInvestigations = Object.freeze({
  readInvestigation: unavailable('Investigation is not connected.'),
  readSource: unavailable('Historical evidence is not connected.'),
})
export const disconnectedProjects = Object.freeze({
  mode: 'disconnected', initialProjects: [],
  listProjects: unavailable('Project data is not connected.'),
  createProject: unavailable('Project creation is not connected.'),
  updateProject: unavailable('Project settings are not connected.'),
})
