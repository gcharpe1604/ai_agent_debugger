import { runs } from './fixtures.js'
import { authoredTraces } from './authoredTraces.js'
import { createScaleTrace } from './scaleTraces.js'
import { timingFixture } from './timingFixture.js'

// Client view models only. No HTTP routes, pagination protocol or backend schema.
const cache = new Map()
function sandboxTrace(run) {
  const base = run.traceId.slice(0, 8)
  return { spans: [
    { key: 'root', id: base + '00000001', parent: null, name: run.name, type: 'run', status: run.outcome === 'Unknown' ? 'UNSET' : 'OK', start: 0, duration: run.durationMs, input: { request: run.name }, output: null },
    { key: 'plan', id: base + '00000002', parent: 'root', name: 'prepare-request', type: 'model', status: 'UNSET', start: 8, duration: Math.floor(run.durationMs / 4), input: false, output: 0, attributes: { 'sample.project': 'sandbox' }, events: [] },
    { key: 'lookup', id: base + '00000003', parent: 'root', name: 'lookup-catalog-entry', type: 'tool', status: run.outcome === 'Unknown' ? 'VENDOR_PENDING' : 'OK', start: Math.floor(run.durationMs / 3), duration: Math.floor(run.durationMs / 3), input: { account: '[redacted]' }, output: { excerpt: 'Captured prefix of the catalog entry…' }, inputCapture: { state: 'redacted', reason: 'Authored sample: account value removed at capture.' }, outputCapture: { state: 'truncated', reason: 'Authored sample: only the stored prefix is available.' }, events: [{ name: 'catalog.lookup', atMs: Math.floor(run.durationMs / 3) + 120, attributes: { source: 'authored fixture' } }] },
    { key: 'record', id: base + '00000004', parent: 'root', name: 'record-request', type: 'state', status: null, start: run.durationMs - 40, duration: 24, input: '', output: [], events: [] },
  ] }
}
function getFixture(projectId, runId) {
  const scope = `${projectId}/${runId}`
  if (cache.has(scope)) return cache.get(scope)
  let source, run = runs.find(item => item.projectId === projectId && item.id === runId)
  if (projectId === 'agent-examples' && runId === 'R-6008') {
    source = timingFixture
    run = { id: runId, projectId, traceId: source.traceId, name: source.name, service: source.service, startedAt: '2026-10-15T11:12:06Z', durationMs: 1000, outcome: 'Completed', completeness: 'Partial', recordedErrorCount: 0, investigation: 'Not requested', findingCount: null }
  } else if (projectId === 'agent-examples' && ['R-6100', 'R-7000', 'R-8100'].includes(runId)) {
    source = createScaleTrace(Number(runId.slice(2)) - 6000)
    run = { id: runId, projectId, traceId: source.traceId, name: source.name, service: source.service, startedAt: '2026-10-15T11:12:06Z', durationMs: source.duration, outcome: source.status, completeness: source.completeness, recordedErrorCount: source.recordedErrors, investigation: source.analysis, findingCount: null }
  } else if (run) source = projectId === 'sandbox' ? sandboxTrace(run) : authoredTraces.find(item => item.label === runId)
  if (!source || !run) throw new Error('Run unavailable in this sample project')
  const ids = new Map(source.spans.map(span => [span.key, span.id]))
  const sourceById = new Map(source.spans.map(span => [span.id, span]))
  const counts = new Map()
  source.spans.forEach(span => counts.set(span.parent, (counts.get(span.parent) || 0) + 1))
  const structures = source.spans.map(span => Object.freeze({ id: span.id, parentId: span.parent === null ? null : ids.get(span.parent) || span.parent, name: span.name, type: span.type, status: span.status, start: span.start, duration: span.duration, ...(Object.hasOwn(span, 'end') ? { end: span.end } : {}), retryOf: span.retryOf || null, childCount: counts.get(span.key) || 0 }))
  const result = { run, source, sourceById, structures }
  cache.set(scope, result)
  return result
}
const capture = (span, direction) => span[direction + 'Capture'] || (span[direction + 'Reason'] ? { state: 'unavailable', reason: span[direction + 'Reason'] } : Object.hasOwn(span, direction) ? { state: 'captured' } : { state: 'unavailable', reason: 'Reason not recorded' })
const reference = span => span && ({ id: span.id, name: span.name, status: span.status })

export const traceRepository = Object.freeze({
  async readTrace({ projectId, runId, limit, signal }) {
    signal?.throwIfAborted()
    const fixture = getFixture(projectId, runId)
    await Promise.resolve()
    signal?.throwIfAborted()
    const loaded = Math.min(fixture.structures.length, Math.max(1, limit ?? fixture.source.initialLoaded ?? fixture.structures.length))
    return { run: fixture.run, spans: fixture.structures.slice(0, loaded), knownCount: fixture.structures.length, quality: fixture.source.quality || null }
  },
  async readSpan({ projectId, runId, spanId, signal }) {
    signal?.throwIfAborted()
    const fixture = getFixture(projectId, runId)
    const span = fixture.sourceById.get(spanId)
    if (!span) throw new Error('Span unavailable in this sample run')
    await Promise.resolve()
    signal?.throwIfAborted()
    return { ...span, inputCapture: capture(span, 'input'), outputCapture: capture(span, 'output'), retryOf: reference(fixture.sourceById.get(span.retryOf)), retries: fixture.source.spans.filter(item => item.retryOf === span.id).map(reference) }
  },
})
