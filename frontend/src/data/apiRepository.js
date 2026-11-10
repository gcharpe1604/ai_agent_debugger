// Actual SDK captures from the normal backend. No seeded records or fallback.
import { selectRuns } from './runRepository.js'

const elapsed = (end, start) => Number(BigInt(end) - BigInt(start)) / 1e6

function runView(run) {
  return {
    id: run.trace_id, traceId: run.trace_id, projectId: 'local',
    name: run.name, startedAt: run.started_at, service: run.service,
    durationMs: run.end_time_unix_nano ? elapsed(run.end_time_unix_nano, run.start_time_unix_nano) : null,
    outcome: run.status === 'OK' ? 'Completed' : run.status === 'ERROR' ? 'Failed' : 'Unknown',
    completeness: 'Unknown', recordedErrorCount: run.recorded_error_spans, executionMode: run.execution_mode, localDependencies: run.local_dependencies,
    recovered: run.recorded_recovered_retry === true, investigation: 'Unavailable', findingCount: null,
    firstError: firstErrorView(run.first_error),
  }
}

// Earliest ERROR span with no ERROR children (backend rule). A pointer, not a cause.
function firstErrorView(value) {
  if (!value || typeof value.span_id !== 'string') return null
  return {
    spanId: value.span_id, spanName: value.span_name, operationType: value.operation_type,
    exceptionType: value.exception_type ?? null, leafErrorCount: value.originating_error_span_count,
  }
}

function spanIdentity(span) {
  return {
    id: span.span_id, name: span.name, type: span.operation_type, status: span.status.code,
    step: span.attributes['debugger.step'], attempt: span.attributes['debugger.attempt'],
  }
}

function spanView(span, run) {
  return {
    ...spanIdentity(span), parentId: span.parent_span_id,
    start: elapsed(span.start_time_unix_nano, run.start_time_unix_nano),
    end: elapsed(span.end_time_unix_nano, run.start_time_unix_nano),
    duration: elapsed(span.end_time_unix_nano, span.start_time_unix_nano),
    retryOf: span.attributes['debugger.retry_of'] || null,
    // We know received children, not the total number the application emitted.
    childCount: null,
  }
}

export function createApiAdapters(fetcher = fetch) {
  let workspace
  const scope = projectId => { if (projectId !== workspace?.id) throw new Error('Captured workspace unavailable') }
  async function read(path, signal) {
    const response = await fetcher('/api/v1/local/' + path, { signal, cache: 'no-store', headers: { Accept: 'application/json' } })
    if (!response.ok) throw new Error(response.status === 404 ? 'Captured data is unavailable. The memory storage may have restarted; execute the agent again.' : 'Telemetry read failed. Check the backend on 127.0.0.1:8008 and retry. No sample data was substituted.')
    return response.json()
  }
  const repository = {
    get projects() { return workspace ? [workspace] : [] },
    async listRuns({ projectId, query, signal }) {
      scope(projectId)
      const response = await read('runs', signal)
      if (response.mode !== 'local' || !Array.isArray(response.runs)) throw new Error('Unexpected telemetry response')
      return selectRuns(response.runs.map(runView), projectId, { ...query, time: 'all' }, null, Date.now())
    },
  }
  const traceRepository = {
    async readTrace({ projectId, runId, signal }) {
      scope(projectId)
      const response = await read('runs/' + encodeURIComponent(runId), signal)
      if (response.run.trace_id !== runId || !Array.isArray(response.spans)) throw new Error('Captured trace identity mismatch')
      return { run: runView(response.run), spans: response.spans.map(span => spanView(span, response.run)), knownCount: null }
    },
    async readSpan({ projectId, runId, spanId, signal }) {
      scope(projectId)
      const { span, run, retry_of, retries } = await read(`runs/${encodeURIComponent(runId)}/spans/${encodeURIComponent(spanId)}`, signal)
      if (span.trace_id !== runId || span.span_id !== spanId) throw new Error('Captured span identity mismatch')
      const exception = span.events.find(event => event.name === 'exception')?.attributes
      const reference = value => value ? spanIdentity(value) : null
      return {
        ...spanView(span, run),
        attributes: { ...span.attributes, 'otel.trace_id': span.trace_id, 'otel.span_id': span.span_id, 'otel.parent_span_id': span.parent_span_id, 'otel.start_time_unix_nano': span.start_time_unix_nano, 'otel.end_time_unix_nano': span.end_time_unix_nano, ...Object.fromEntries(Object.entries(span.resource).map(([key, value]) => ['resource.' + key, value])) },
        events: span.events.map(event => ({ name: event.name, atMs: elapsed(event.time_unix_nano, run.start_time_unix_nano), attributes: event.attributes })),
        error: exception?.['exception.message'], errorType: exception?.['exception.type'],
        retryOf: reference(retry_of), retries: retries.map(reference),
        inputCapture: { state: 'disabled', reason: 'This profile captures span metadata only.' },
        outputCapture: { state: 'disabled', reason: 'This profile captures span metadata only.' },
      }
    },
  }
  return {
    repository, traceRepository,
    // Server-reported local workspace is not persisted project ownership or authorization.
    projectAdapter: { mode: 'local', async listProjects({ signal } = {}) {
      const response = await read('status', signal)
      if (response.mode !== 'local' || response.workspace?.id !== 'local' || typeof response.workspace.name !== 'string' || response.workspace.dataSource !== 'local') throw new Error('Unexpected workspace response')
      workspace = response.workspace
      return [workspace]
    } },
  }
}
