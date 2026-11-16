# Trace Protocol
## AI Agent Execution Debugging & Trace Analysis Platform

## 1. Purpose and Scope

This document defines the framework-independent trace contract between the debugger SDK and backend ingestion boundary.

It defines what a Run/Span means, required identity/lifecycle semantics, payload rules, batching, duplicate handling, and the distinction between recorded telemetry and derived analysis.

It does **not** define ClickHouse table-engine parameters, Kafka deployment topology, PostgreSQL schemas, or investigator prompts.

## 2. Protocol Design Principles

1. **Framework independence** — protocol semantics do not depend on LangGraph or any single agent framework.
2. **OpenTelemetry foundation** — trace/span identity and context follow OpenTelemetry for the supported Python SDK.
3. **Record facts before interpretation** — the protocol records what happened; semantic diagnosis is derived later.
4. **Arrival order is not execution order** — HTTP, Kafka, and storage arrival order are non-authoritative.
5. **Partial traces are preserved** — missing parents or late spans do not automatically invalidate useful telemetry.
6. **Stable core, flexible metadata** — core identity/status/time fields are stable; provider/agent payloads remain extensible.
7. **At-least-once friendly** — the protocol supports safe redelivery without confusing transport duplicates with application retries.

## 3. Core Concepts

### 3.1 Project

A Project is the authenticated ownership boundary. The server derives `project_id` from the integration credential rather than trusting a client-supplied project identifier.

### 3.2 Run

For the supported MVP SDK profile:

> one Debugger Run maps to one OpenTelemetry trace.

`trace_id` is therefore the Run identity.

### 3.3 Span

A Span represents one meaningful duration-bearing operation such as:

- run/root execution;
- agent/workflow execution;
- model invocation;
- retrieval;
- tool call;
- external API/database operation;
- state/memory interaction;
- custom instrumented operation.

### 3.4 Event

An Event is an instantaneous observation within a span, such as an exception, retry scheduling observation, state transition, or stream lifecycle event.

### 3.5 Relationship

Parent-child represents structural execution nesting only. Additional relationships may be recorded when explicitly known, such as dependency, handoff, evidence consumption, or retry relation.

## 4. Trace Batch Envelope

The custom exporter submits batches rather than one request per span.

Conceptual shape:

```json
{
  "protocol_version": "1",
  "spans": [
    {
      "trace_id": "...",
      "span_id": "...",
      "parent_span_id": null,
      "name": "refund-run",
      "operation_type": "run",
      "start_time": "...",
      "end_time": "...",
      "status": {"code": "UNSET"},
      "attributes": {},
      "events": [],
      "links": []
    }
  ]
}
```

The authenticated project context is added/validated server-side.

### 4.1 Protocol "1" request fields (user decision 2026-11-16)

Field names and defaults for `POST /api/v1/traces` with `protocol_version: "1"`, as implemented in `backend/src/agent_debugger_api/ingest/schemas.py`. Unknown fields are rejected.

**Envelope:** `protocol_version` (the string `"1"`), `spans` (list of spans).

**Span, required:**

| Field | Type |
|---|---|
| `trace_id` | 32 lowercase hex characters |
| `span_id` | 16 lowercase hex characters |
| `name` | non-empty string |
| `operation_type` | `run`, `agent`, `model`, `retrieval`, `tool`, `api`, `state` or `custom` |
| `start_time`, `end_time` | integer nanoseconds since the Unix epoch (not strings) |

**Span, optional (default in brackets):**

| Field | Type |
|---|---|
| `parent_span_id` | 16 lowercase hex characters or `null` [`null`] |
| `status` | `{"code": "UNSET" \| "OK" \| "ERROR", "description": string}` [`{"code": "UNSET", "description": ""}`] |
| `service_name`, `display_label`, `execution_mode`, `graph_node_id`, `graph_node_parent_id`, `error_type` | string [`""`] |
| `attempt` | integer 0–65535 [`null`] |
| `retry_of_span_id` | 16 lowercase hex characters [`null`] |
| `model`, `provider` | string [`null`] |
| `input_tokens`, `output_tokens`, `total_tokens` | integer 0–4294967295 [`null`] |
| `cost` | non-negative decimal string with at most 9 digits before and 9 after the point, e.g. `"0.00125"`; never a number [`null`] |
| `input_state`, `output_state`, `error_state` | `captured`, `disabled`, `redacted`, `truncated` or `unavailable` [`"unavailable"`] |
| `input_payload`, `output_payload`, `error_payload` | string of at most 131,072 UTF-8 bytes [`""`] |
| `attributes` | object of string keys to a string, number, boolean or list of those [`{}`] |
| `events` | list of `{"name": string, "time": integer ns, "attributes": object}` [`[]`] |
| `links` | list of `{"trace_id", "span_id", "relation": string}` [`[]`] |

**Payload-state default:** a payload state the client does not send is `"unavailable"` (no payload was produced or captured). The server never guesses `captured`, `disabled` or any other state. A non-empty payload with a `disabled` or `unavailable` state is rejected.

**Payload size (user decision 2026-11-16):** each of the three payloads may be at most 131,072 bytes, counted as UTF-8. A larger payload is rejected with 422 (`type: payload_too_large`, `loc` naming the span index and field) and nothing from the batch is published. The server never truncates a payload: the client cuts it and sends the state `truncated` (`proposals/clickhouse-span-record.md` §9).

**Set by the server, rejected from the client:** `project_id`, `received_at`, and a per-span `protocol_version`.

## 5. Required Span Fields

Each ended span requires:

- trace ID;
- span ID;
- optional parent span ID;
- span name;
- debugger operation type;
- start time;
- end time;
- status representation;
- resource/service identity where available.

Optional evidence-bearing fields include:

- serialized input;
- serialized output;
- structured error information;
- attributes;
- events;
- links / explicit relationship metadata;
- agent identity;
- retry metadata.

## 6. Operation Types

Initial debugger operation types:

- `run`
- `agent`
- `model`
- `retrieval`
- `tool`
- `api`
- `state`
- `custom`

Operation type describes execution role, not failure category.

## 7. Lifecycle and Status

The MVP exporter primarily sends **ended spans**.

Because normal OpenTelemetry export occurs after a span ends:

- active spans may not be visible;
- a hard crash may lose active/queued telemetry;
- post-completion debugging is the primary scope.

A child span can be `ERROR` while a parent/run remains successful if the application catches/recover from the failure.

## 8. Parent-Child Semantics

- `parent_span_id = null` indicates a root span within the trace.
- A child may arrive before its parent.
- Missing parents are preserved as incomplete telemetry.
- Multiple roots may be represented if telemetry is incomplete or external instrumentation is imperfect.
- Parentage does not prove causality/evidence consumption.

## 9. Ordering

Display/reconstruction may use timestamps and stable tie-breaking, but:

- HTTP arrival order is not execution order;
- Kafka message order is not universal causal order;
- ClickHouse insertion order is not execution order;
- earlier timestamp alone does not prove dependency.

Explicit captured relationships take precedence over inferred assumptions.

## 10. Inputs, Outputs, Errors, and Attributes

### 10.1 Input / Output

Input and output payloads are optional because capture may be disabled or redacted.

Values are serialized into bounded JSON-compatible representations by the SDK/exporter.

### 10.2 Errors

OpenTelemetry exception events/status are preserved. Additional structured error metadata may be attached where useful.

### 10.3 Attributes

Attributes may contain provider/framework metadata but must respect size/type limits.

### 10.4 Sensitive Data

The SDK supports capture switches/redaction hooks and excludes known secret headers. Redacted/truncated payloads should be explicitly marked where possible.

## 11. Retry Semantics

Application retry attempts are distinct execution spans.

Example:

```text
charge-payment attempt 1 → timeout
charge-payment attempt 2 → success
```

Both remain visible.

Optional metadata may include operation grouping/attempt number or explicit `retry_of` relation.

Transport duplicate example:

```text
same project + trace_id + span_id + equivalent content
→ redelivery, not a new application attempt
```

## 12. Ingestion Semantics

### 12.1 SDK → FastAPI

The SDK sends an authenticated batch over HTTPS/JSON.

### 12.2 FastAPI Validation

The ingestion API validates authentication, version, limits, required fields, and basic field shape.

### 12.3 FastAPI → Kafka

Accepted validated telemetry is published to Kafka.

The HTTP success response means the backend accepted the batch into the ingestion buffer, not that ClickHouse persistence or analysis has completed.

### 12.4 Kafka → ClickHouse

The trace-writer consumer persists telemetry in batches and commits Kafka progress after persistence.

This internal path is not part of the SDK-facing protocol contract.

## 13. Idempotency and Duplicate Handling

### 13.1 Identity

Logical span identity:

```text
(project_id, trace_id, span_id)
```

### 13.2 Equivalent Redelivery

Equivalent content using the same identity is idempotent from the reconstructed-trace perspective.

### 13.3 Conflicting Redelivery

Different immutable content using the same identity is a conflict. It must not be silently interpreted as two valid spans.

### 13.4 Delivery Guarantee

The platform uses at-least-once delivery semantics between ingestion and telemetry storage. Exactly-once delivery is not promised.

## 14. Incomplete and Structurally Invalid Traces

The backend distinguishes request-level invalid data from reconstructable trace-quality problems.

Examples preserved as warnings when possible:

- missing parent;
- multiple roots;
- late spans;
- inconsistent timestamps;
- incomplete execution.

Self-parenting/cycles or malformed identifiers are objective structural problems and may be rejected or flagged according to the relevant boundary.

## 15. Immutability and Updates

Ended accepted spans are logically immutable.

Late new spans may extend the current trace view but do not mutate earlier analysis snapshots.

The protocol does not support arbitrary mutation of already-ended spans as a normal workflow.

## 16. Explicit Relationships

A small optional relationship vocabulary may be used where instrumentation truly knows the relation:

- `depends_on`
- `handoff_from`
- `consumes`
- `retry_of`

Missing relationship metadata reduces certainty. The platform does not manufacture these links from timing alone.

## 17. Analysis Boundary

The protocol records execution evidence. It does not contain root-cause conclusions.

The investigator operates on a normalized reconstruction and produces candidate findings. Grounding later verifies the cited evidence.

Recorded trace data in ClickHouse and derived analysis data in PostgreSQL remain separate.

## 18. Versioning

The batch contains an explicit protocol version. Backward-compatible optional fields may be added without redefining core identity semantics.

Breaking changes require a new protocol version and migration/compatibility plan.

## 19. Future Extensions

Possible future additions include:

- OTLP ingestion/Collector interoperability;
- additional language SDKs;
- framework adapters;
- richer execution links;
- object-storage retention;
- replay/counterfactual metadata.

These do not change the current MVP contract.
