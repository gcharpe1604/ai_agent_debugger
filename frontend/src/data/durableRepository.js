// Durable read API (GET /api/v1/projects/local/...): spans read from ClickHouse,
// tree and structure flags reconstructed by the backend. Read failures are
// thrown; nothing here substitutes sample or local-profile data.
import { selectRuns } from './runRepository.js'

const BASE = '/api/v1/projects'
const PAGE = 200
// The run list is filtered and sorted in the browser, so it is read in full,
// newest first, up to this many runs. Beyond it the list says it is partial.
export const MAX_RUNS = 1000

const elapsed = (end, start) => Number(BigInt(end) - BigInt(start)) / 1e6
const isoTime = nanos => new Date(Number(BigInt(nanos) / 1000000n)).toISOString()
const NO_ROOT = 'Root span not received'

// Structure flags set by the backend reconstruction. cycle_break only marks
// where a cycle was cut; the cycle label already covers that span.
export const flagLabels = { missing_parent: 'Parent not received', cycle: 'Parent cycle', conflict: 'Conflicting versions' }

const captureReasons = {
  redacted: 'Secret fields were replaced with "[redacted]" before export.',
  truncated: 'Cut at the capture size limit. Everything shown is real; some is missing.',
  disabled: 'Capture was switched off for this span.',
  unavailable: 'The span did not record this payload.',
}

function runView(run) {
  return {
    id: run.trace_id, traceId: run.trace_id, projectId: 'local',
    name: run.name ?? NO_ROOT, startedAt: isoTime(run.start_time_unix_nano), service: run.service ?? 'Not recorded',
    // First span start to last span end: the root may be missing or may not be the last to end.
    durationMs: elapsed(run.end_time_unix_nano, run.start_time_unix_nano),
    outcome: run.status === 'OK' ? 'Completed' : run.status === 'ERROR' ? 'Failed' : 'Unknown',
    completeness: 'Unknown', recordedErrorCount: run.error_span_count, executionMode: run.execution_mode ?? undefined,
    recovered: run.recorded_recovered_retry === true, investigation: 'Unavailable', findingCount: null,
    firstError: firstErrorView(run.first_error),
    missingRoot: run.missing_root === true, conflicted: run.conflicted === true,
  }
}

// Earliest ERROR span with no ERROR descendant (backend rule). A pointer, not a cause.
function firstErrorView(value) {
  if (!value || typeof value.span_id !== 'string') return null
  return {
    spanId: value.span_id, spanName: value.span_name, operationType: value.operation_type,
    exceptionType: value.error_type ?? null, leafErrorCount: value.originating_error_span_count,
  }
}

const reference = value => value ? { id: value.span_id, name: value.name, type: value.operation_type, status: value.status.code, attempt: value.attempt ?? undefined } : null

// One row per span_id. `version` is the stored version that places the span;
// a conflicted span has more, listed by readSpan.
function spanView(version, node, run) {
  return {
    id: version.span_id, name: version.name, type: version.operation_type, status: version.status.code,
    step: version.attributes['debugger.step'], attempt: version.attempt ?? undefined,
    // Parent in the backend's reconstructed tree: null for an orphan and for the
    // span where a cycle was cut. recordedParentId is what the span itself said.
    parentId: node.parent_span_id, recordedParentId: node.recorded_parent_span_id,
    flags: node.flags, versionCount: node.versions.length,
    start: elapsed(version.start_time_unix_nano, run.start_time_unix_nano),
    end: elapsed(version.end_time_unix_nano, run.start_time_unix_nano),
    duration: elapsed(version.end_time_unix_nano, version.start_time_unix_nano),
    retryOf: version.retry_of_span_id || null,
    childCount: null,
  }
}

function payload(text, state) {
  const capture = captureReasons[state] ? { state, reason: captureReasons[state] } : { state }
  if (!['captured', 'truncated', 'redacted'].includes(state)) return { capture }
  try { return { value: JSON.parse(text), capture } } catch { return { value: text, capture } }
}

function recordedError(version) {
  const stored = payload(version.error_payload, version.error_state).value
  const exception = version.events.find(event => event.name === 'exception')?.attributes
  const message = (stored && typeof stored === 'object' ? stored.message : stored) || exception?.['exception.message'] || version.status.description
  const type = version.error_type || (stored && typeof stored === 'object' ? stored.type : null) || exception?.['exception.type']
  return { error: message || undefined, errorType: type || undefined }
}

export function createDurableAdapters(fetcher = fetch) {
  let workspace
  const scope = projectId => { if (projectId !== workspace?.id) throw new Error('Captured workspace unavailable') }
  async function read(path, signal) {
    const response = await fetcher(BASE + path, { signal, cache: 'no-store', headers: { Accept: 'application/json' } })
    if (response.ok) return response.json()
    throw new Error(
      response.status === 404 ? 'This trace or span is not in durable storage.'
        : response.status === 503 ? 'The trace store (ClickHouse) is unavailable, so nothing was read. Start it and retry. No sample data was substituted.'
          : 'Durable telemetry read failed. Check the backend on 127.0.0.1:8008 and retry. No sample data was substituted.')
  }
  async function readTraceBody(runId, signal) {
    const body = await read(`/local/runs/${encodeURIComponent(runId)}`, signal)
    if (body.run?.trace_id !== runId || !Array.isArray(body.spans) || !Array.isArray(body.tree?.nodes)) throw new Error('Captured trace identity mismatch')
    return body
  }
  const repository = {
    get projects() { return workspace ? [workspace] : [] },
    async listRuns({ projectId, query, signal }) {
      scope(projectId)
      const runs = []
      let cursor = null, partial
      do {
        const page = await read(`/local/runs?limit=${PAGE}${cursor ? `&cursor=${encodeURIComponent(cursor)}` : ''}`, signal)
        if (page.project !== 'local' || !Array.isArray(page.runs)) throw new Error('Unexpected telemetry response')
        runs.push(...page.runs)
        cursor = page.next_cursor
        partial = !!cursor && runs.length >= MAX_RUNS
      } while (cursor && !partial)
      const result = selectRuns(runs.map(runView), projectId, { ...query, time: 'all' }, null, Date.now())
      // Older runs exist but were not read: counts and filters cover the newest runs only.
      return partial ? { ...result, partialAt: runs.length } : result
    },
  }
  const traceRepository = {
    async readTrace({ projectId, runId, signal }) {
      scope(projectId)
      const body = await readTraceBody(runId, signal)
      const versions = new Map(body.spans.map(span => [span.content_hash + span.span_id, span]))
      // Backend pre-order: parents before children, siblings by start time.
      const spans = body.tree.nodes.map(node => spanView(versions.get(node.versions[0] + node.span_id), node, body.run))
      const warnings = body.tree.warnings
      return {
        run: runView(body.run), spans, knownCount: null, warnings,
        quality: warnings.length ? `Structure: ${warnings.map(warning => warning.message).join(' ')} Nothing was dropped or re-parented.` : undefined,
      }
    },
    async readSpan({ projectId, runId, spanId, signal }) {
      scope(projectId)
      const body = await read(`/local/runs/${encodeURIComponent(runId)}/spans/${encodeURIComponent(spanId)}`, signal)
      if (body.span_id !== spanId || body.run?.trace_id !== runId || !body.versions?.length) throw new Error('Captured span identity mismatch')
      const version = body.versions[0]
      const node = { parent_span_id: body.parent_span_id, recorded_parent_span_id: body.recorded_parent_span_id, flags: body.flags, versions: body.versions }
      const input = payload(version.input_payload, version.input_state), output = payload(version.output_payload, version.output_state)
      const recorded = Object.fromEntries(Object.entries({
        'debugger.execution.mode': version.execution_mode, 'debugger.attempt': version.attempt, 'debugger.model.name': version.model,
        'debugger.model.provider': version.provider, 'debugger.tokens.input': version.input_tokens, 'debugger.tokens.output': version.output_tokens,
        'debugger.tokens.total': version.total_tokens, 'debugger.cost': version.cost, 'resource.service.name': version.service,
      }).filter(([, value]) => value !== null && value !== undefined))
      return {
        ...spanView(version, node, body.run), source: 'durable',
        attributes: { ...recorded, ...version.attributes, 'otel.trace_id': version.trace_id, 'otel.span_id': version.span_id, 'otel.parent_span_id': version.parent_span_id, 'otel.start_time_unix_nano': version.start_time_unix_nano, 'otel.end_time_unix_nano': version.end_time_unix_nano },
        events: version.events.map(event => ({ name: event.name, atMs: elapsed(event.time_unix_nano, body.run.start_time_unix_nano), attributes: event.attributes })),
        ...recordedError(version),
        retryOf: reference(body.retry_of), retries: body.retries.map(reference),
        input: input.value, inputCapture: input.capture, output: output.value, outputCapture: output.capture,
        // Every stored version of a conflicted span. The first one is displayed; none is "correct".
        versions: body.versions.map(item => ({ contentHash: item.content_hash, receivedAt: item.received_at_unix_nano, name: item.name, status: item.status.code, parentId: item.parent_span_id })),
      }
    },
  }
  return {
    repository, traceRepository,
    // No authentication yet: the server names one project and grants nothing.
    projectAdapter: { mode: 'durable', async listProjects({ signal } = {}) {
      const body = await read('', signal)
      const project = body.projects?.find(item => item.id === 'local')
      if (!project || typeof project.name !== 'string' || project.storage !== 'clickhouse') throw new Error('Unexpected workspace response')
      // dataSource 'local' = real captured telemetry (not fixtures); storage says where it lives.
      workspace = { id: 'local', name: project.name, initial: 'D', environment: 'SDK telemetry · ClickHouse storage', dataSource: 'local', storage: 'durable', retentionSeconds: null }
      return [workspace]
    } },
  }
}
