# Low-Level Design (LLD)
## AI Agent Execution Debugging & Trace Analysis Platform

## 1. Purpose and Scope

This LLD defines the implementation boundaries for the OJT MVP. It expands the HLD without redesigning it.

Authoritative supporting documents:

| Document | Responsibility |
|---|---|
| `HLD.md` | System-level architecture and technology boundaries |
| `trace-protocol.md` | Trace payload and execution semantics |
| `database.md` | PostgreSQL/ClickHouse persistence model |
| `analysis-engine.md` | Investigator, grounding, findings, and analysis lifecycle |

### 1.1 Frozen Runtime Direction

```text
Developer Agent
  ↓
Thin SDK + OpenTelemetry
  ↓
BatchSpanProcessor
  ↓
Custom HTTP/JSON SpanExporter
  ↓
FastAPI ingestion
  ↓
Kafka
  ↓
Trace Writer Consumer
  ↓
ClickHouse
  ↓
Trace Reconstruction / Read APIs
```

Separately:

```text
PostgreSQL
├── projects / integration keys / settings
├── analysis attempts / findings / evidence metadata
└── authoritative knowledge + vector search
```

Version 1 does not require Kubernetes, a service mesh, distributed analysis workers, or a multi-agent debugger swarm.

## 2. Application and Module Structure

Recommended backend structure:

```text
backend/src/agent_debugger_api/
├── api/
│   ├── routes/
│   │   ├── health.py
│   │   ├── ingestion.py
│   │   ├── runs.py
│   │   ├── analysis.py
│   │   └── knowledge.py
│   └── dependencies.py
├── ingestion/
│   ├── schemas.py
│   ├── service.py
│   ├── producer.py
│   └── auth.py
├── telemetry/
│   ├── clickhouse.py
│   ├── repository.py
│   ├── reconstruction.py
│   └── queries.py
├── consumer/
│   ├── worker.py
│   └── writer.py
├── projects/
├── analysis/
├── knowledge/
├── db/
│   ├── postgres.py
│   └── models.py
└── config.py
```

Recommended SDK structure:

```text
sdk/python/src/ai_agent_debugger_sdk/
├── __init__.py
├── client.py
├── span.py
├── transport.py
├── context.py
└── errors.py
```

Do not create modules solely to fill folders. Add modules only when a distinct responsibility exists.

### 2.1 Dependency Direction

```text
API routes
   ↓
services
   ↓
repositories / Kafka producer / ClickHouse client
```

The investigator does not directly own HTTP routes or database clients. The SDK does not import backend modules.

### 2.2 Configuration

Configuration is environment-driven. At minimum:

- PostgreSQL connection URL;
- ClickHouse host/port/database/user/password/TLS settings;
- Kafka bootstrap servers/topic/consumer group;
- LLM provider configuration;
- integration-key hashing secret/strategy;
- payload and analysis limits.

Secrets are never committed to the repository.

## 3. Python SDK Design

### 3.1 Public API

Initial public API:

```python
from ai_agent_debugger_sdk import Debugger

debugger = Debugger(
    service_name="refund-agent",
    endpoint="https://debug.example.com/api/v1/traces",
    api_key="...",
)

with debugger.run("refund-run"):
    with debugger.agent("refund-agent"):
        with debugger.retrieval("policy-search") as span:
            span.set_input({"query": "refund policy"})
            result = search(...)
            span.set_output(result)
```

Public helpers:

- `run()`
- `agent()`
- `model()`
- `tool()`
- `retrieval()`

A small `SpanHandle` exposes controlled helpers such as `set_input`, `set_output`, and `set_attribute`.

### 3.2 OpenTelemetry Ownership

OpenTelemetry owns:

- trace IDs;
- span IDs;
- current-span context;
- parent-child propagation;
- span lifecycle;
- exception events/status behavior;
- span processing;
- batching abstraction.

The debugger SDK owns semantic naming, selected captured payloads, redaction/capture controls, and the custom exporter.

### 3.3 Resource Identity

The SDK sets standard OpenTelemetry resource metadata such as `service.name` rather than inventing duplicate debugger fields for service identity.

### 3.4 Span Semantics

All operation helpers delegate to one generic internal operation primitive. The debugger operation type is attached as an attribute such as `debugger.operation.type`.

### 3.5 Input / Output Capture

Arbitrary application values are serialized into bounded JSON-compatible representations before being attached/exported. Payload size limits and redaction are applied before export.

### 3.6 Error Recording

Escaping exceptions are allowed to flow through OpenTelemetry so exception events and error status are recorded automatically. The SDK must not duplicate exception events unnecessarily.

A failed child operation does not automatically mark its parent or the entire run failed if the application catches and recovers from the failure.

### 3.7 Batch Export

Production/demo exporter path:

```text
ended span
  ↓
BatchSpanProcessor
  ↓
DebuggerHTTPExporter
  ↓
POST /api/v1/traces
```

The exporter sends multiple completed spans per request where possible.

### 3.8 Fail-Open Behavior

Exporter failures must not intentionally raise into developer application logic. Retries/timeouts are bounded. Shutdown/flush attempts to deliver queued spans without blocking indefinitely.

## 4. Ingestion API and Authentication

### 4.1 Endpoint

Initial endpoint:

```text
POST /api/v1/traces
```

Request body is a versioned trace-batch envelope defined in `trace-protocol.md`.

### 4.2 Authentication

The SDK sends a project-scoped integration credential. FastAPI resolves the credential against PostgreSQL and obtains the authoritative `project_id`.

The client cannot choose another project by placing an arbitrary project ID in the body.

### 4.3 Validation

FastAPI validates:

- protocol version;
- batch size/request limits;
- required span identity fields;
- supported field types;
- obvious malformed identifiers;
- project authentication.

Structural issues that require wider trace context are not necessarily request-rejection conditions.

### 4.4 Kafka Publish Boundary

After validation, FastAPI builds a normalized ingestion envelope and publishes it to the configured trace topic.

Successful response means:

> the backend accepted the batch into the ingestion buffer.

It does not mean ClickHouse persistence or later analysis is already complete.

Recommended response:

```text
202 Accepted
```

If Kafka publish fails and the batch was not accepted by the broker, return a retryable server error rather than falsely acknowledging ingestion.

## 5. Kafka Ingestion Design

### 5.1 Responsibility

Kafka decouples HTTP ingestion from telemetry persistence.

It is not used as the long-term trace database.

### 5.2 Message Shape

Each Kafka message contains a validated batch envelope or bounded sub-batch with:

- protocol version;
- project ID from authenticated context;
- receive timestamp;
- spans;
- optional transport metadata.

Exact wire naming belongs in `trace-protocol.md`.

### 5.3 Partitioning

Partitioning should preserve reasonable locality for a project's traces without requiring global execution order. Exact partition key is an implementation decision validated during load testing; trace ID is the default candidate because it keeps one trace's telemetry together.

### 5.4 Delivery Semantics

The system uses at-least-once delivery semantics.

Do not claim exactly-once trace persistence.

Application retry attempts and transport duplicates are different concepts:

- separate span IDs / attempt metadata → real application retries;
- equivalent repeated span identity/content → transport duplicate.

### 5.5 Consumer Group

A trace-writer consumer group reads telemetry and writes ClickHouse batches. More consumers may be added later if throughput requires it.

### 5.6 Offset Commit

Offsets are committed only after the corresponding ClickHouse persistence step succeeds.

If ClickHouse is unavailable, the consumer retries according to bounded operational policy and leaves uncommitted messages available for replay.

## 6. ClickHouse Telemetry Persistence

### 6.1 Responsibility

ClickHouse is the primary durable execution-telemetry store.

It stores high-volume data needed for reconstruction, run browsing, step inspection, and large-run investigator queries.

### 6.2 Logical Span Record

The physical table design may evolve, but a logical telemetry row includes:

- `project_id`
- `trace_id`
- `span_id`
- `parent_span_id`
- `service_name`
- `operation_type`
- `span_name`
- `status`
- `started_at`
- `ended_at`
- duration
- serialized input/output/error data
- attributes
- events
- links/explicit relationships where captured
- receive/persist metadata
- optional content hash/version metadata for duplicate conflict handling

### 6.3 Query Patterns

The schema/order strategy must efficiently support:

- list traces/runs for project/time range;
- get all spans for one trace;
- get one span;
- filter by operation type/status/agent;
- find errors/retries;
- fetch related spans;
- search bounded trace metadata for investigator tools.

### 6.4 Batch Inserts

The trace writer performs batched inserts. It must not perform one network/database insert per span.

### 6.5 Duplicate Handling

Kafka retries can redeliver telemetry. Equivalent duplicates must not appear as separate execution operations in reconstructed output.

The exact ClickHouse engine/dedup strategy is implementation-specific and must be verified with integration tests before being frozen. The protocol-level identity remains `(project_id, trace_id, span_id)` plus immutable accepted content semantics.

### 6.6 Late and Out-of-Order Spans

ClickHouse accepts late spans. Reconstruction queries determine the current trace view from stored identities and relationships rather than insertion order.

## 7. PostgreSQL Transactional Persistence

### 7.1 PostgreSQL Owns

- projects;
- integration/API-key metadata;
- settings;
- analysis attempts;
- findings;
- evidence references/metadata;
- authoritative documents/chunks/embeddings;
- optional analysis input snapshots.

### 7.2 PostgreSQL Does Not Own

PostgreSQL is not the primary store for raw high-volume spans/events.

### 7.3 Cross-Store References

PostgreSQL findings reference ClickHouse evidence using stable identifiers such as:

- project ID;
- trace ID;
- span ID;
- field/path or excerpt metadata where needed.

There is no cross-database foreign key. Backend services validate cross-store references explicitly.

## 8. Trace Reconstruction

### 8.1 Input

Trace reconstruction queries ClickHouse for the relevant project + trace ID.

### 8.2 Reconstruction Rules

- Build hierarchy from explicit parent span IDs.
- Preserve multiple roots/missing parents as warnings rather than inventing parents.
- Do not use Kafka ordering or ClickHouse insertion order as execution order.
- Timestamps aid display but do not prove causal dependency.
- Explicit relationship metadata is used only when present.

### 8.3 Safe Output

The reconstructed representation contains:

- normalized spans;
- hierarchy;
- explicit relationships;
- structural warnings;
- completeness indicators;
- stable display ordering.

It does not mutate recorded telemetry.

## 9. Analysis Execution

### 9.1 Analysis Lifecycle

1. Developer requests analysis.
2. Backend reconstructs the current run from ClickHouse.
3. Backend creates a stable normalized analysis input.
4. PostgreSQL creates an Analysis Attempt.
5. The LLM investigator runs in direct or bounded-tool mode.
6. Candidate findings are grounded against trace/knowledge evidence.
7. Valid grounded findings are persisted in PostgreSQL.
8. Attempt becomes completed or failed.

### 9.2 Stable Snapshot

Late spans must not silently change the evidence behind an existing analysis. Each attempt preserves the normalized input it analyzed or an equivalent immutable snapshot representation.

### 9.3 Direct Mode

For bounded runs, the investigator receives the normalized run in one request.

### 9.4 Bounded Read-Only Mode

For larger runs, the same investigator may call bounded read-only capabilities such as run overview, span lookup, related-span lookup, filtered trace search, and authoritative knowledge search.

Exact function names are not part of the public product contract.

## 10. Evidence Grounding

Grounding verifies objective references only:

- cited trace/span exists;
- cited field/path/excerpt exists and matches;
- evidence belonged to the analyzed snapshot;
- relied-on relationship exists when explicitly claimed;
- authoritative citation belongs to the same project knowledge set.

Grounding does not prove semantic correctness or causal root cause.

## 11. Read and Debugging APIs

Initial API categories:

- projects/configuration;
- run explorer;
- run/trace detail;
- selected span detail;
- analysis request/status;
- findings/evidence;
- knowledge upload/list/delete.

The browser never receives raw database credentials and never talks directly to Kafka/ClickHouse/PostgreSQL.

## 12. Frontend

Core screens:

- Run Explorer
- Run Detail / Execution View
- Step Inspector
- Debugger Findings
- Optional Knowledge Management

UI must distinguish:

- execution failure vs telemetry incompleteness;
- candidate/ungrounded vs grounded findings;
- recovered failures/retries;
- investigation priority vs root-cause probability.

## 13. Error Handling and Edge Cases

### 13.1 SDK / Network Failure

Fail open. Drop or retry within bounded limits; do not intentionally break the observed agent.

### 13.2 Kafka Failure

If the producer cannot publish, ingestion returns a retryable failure. Do not acknowledge telemetry that never reached the durable ingestion boundary.

### 13.3 ClickHouse Failure

Consumer does not commit offsets for the affected batch. Telemetry remains replayable from Kafka according to retention policy.

### 13.4 PostgreSQL Failure

Project auth/config/analysis writes may fail independently from trace storage. Existing ClickHouse telemetry remains intact.

### 13.5 Investigator Failure

Trace remains inspectable; analysis attempt becomes failed; previous findings are unchanged.

### 13.6 Knowledge Failure

Trace-based analysis may continue without authoritative comparison, and the limitation is reported.

### 13.7 Duplicate Telemetry

Equivalent redelivery is not a new application retry. Real retries remain separate spans.

## 14. Testing Strategy

| Layer | Required tests |
|---|---|
| SDK | hierarchy/context propagation, operation types, input/output capture, exception recording, fail-open behavior |
| Exporter | batch serialization, headers/auth, retryable failure handling, flush/shutdown |
| Ingestion | authentication, validation, request limits, Kafka publish success/failure |
| Kafka consumer | batching, retry, offset commit after persistence, redelivery handling |
| ClickHouse | real integration tests for insert/query/order strategy and duplicate semantics |
| PostgreSQL | project/auth/analysis/knowledge constraints using real PostgreSQL where DB behavior matters |
| Reconstruction | missing parent, multiple roots, out-of-order data, retries, explicit relationships |
| Investigator | structured output, bounded tool limits, evidence citations, controlled scenarios |
| Grounding | valid/invalid span evidence, stale snapshot, project knowledge isolation |
| End-to-end | sample agent → SDK → FastAPI → Kafka → ClickHouse → reconstruction → analysis → PostgreSQL finding → read API |

Automated semantic tests should use deterministic model stubs where practical; controlled live-model evaluation is separate.

## 15. Implementation Order

To avoid blocking on infrastructure, implementation proceeds in stable dependency order:

1. SDK OpenTelemetry foundation and console exporter.
2. Batch processor and custom HTTP/JSON exporter.
3. FastAPI ingestion contract and validation.
4. Kafka producer/consumer path.
5. ClickHouse persistence and trace queries.
6. Reconstruction.
7. PostgreSQL project/analysis/knowledge synchronization.
8. Investigator and grounding.
9. UI.
10. Controlled evaluation and hardening.

A temporary console/in-memory ingestion sink may be used for early demonstrations, but the target OJT persistence architecture remains Kafka → ClickHouse.

## 16. Key Low-Level Decisions

| Concern | Decision |
|---|---|
| SDK tracing | OpenTelemetry API/SDK |
| SDK batching | `BatchSpanProcessor` |
| SDK transport | custom authenticated HTTP/JSON exporter |
| HTTP acknowledgement | after Kafka acceptance, not ClickHouse persistence |
| Queue | Kafka, at-least-once |
| Telemetry persistence | batched ClickHouse writes |
| Transactional persistence | PostgreSQL |
| Cross-store joins | application/service-level by stable identifiers |
| Analysis | one controlled LLM investigator |
| Grounding | deterministic evidence validation |
| Priority | High/Medium/Low, not probability |
| Exactly once | not claimed |
