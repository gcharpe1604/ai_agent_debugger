# Database Design
## AI Agent Execution Debugging & Trace Analysis Platform

## 1. Purpose

The platform uses a **polyglot persistence model** because execution telemetry and transactional application data have different workload characteristics.

- **ClickHouse** is the primary store for high-volume execution telemetry.
- **PostgreSQL** is the transactional store for projects, credentials, analysis, findings, and authoritative knowledge.
- **Kafka is not a database**; it is the durable ingestion buffer between FastAPI and ClickHouse.

This document defines logical ownership, relationships, and persistence semantics. Exact ClickHouse engine parameters and production sizing are implementation details validated through tests.

## 2. Storage Ownership

| Data | Store | Reason |
|---|---|---|
| Projects / settings | PostgreSQL | relational ownership/transactions |
| Integration/API keys | PostgreSQL | secure transactional lifecycle |
| Analysis attempts | PostgreSQL | low-volume mutable workflow state |
| Findings | PostgreSQL | relational derived product data |
| Evidence references | PostgreSQL | references derived results to stable telemetry/knowledge identifiers |
| Knowledge documents/chunks | PostgreSQL | project-scoped metadata |
| Knowledge embeddings | PostgreSQL + pgvector-compatible extension | avoids separate vector DB |
| Traces / spans / events / attributes | ClickHouse | append-heavy analytical telemetry |
| Model/tool/retrieval payloads | ClickHouse | high-volume execution evidence |
| Kafka messages | Kafka (temporary durable log) | buffering/replay, not long-term product storage |

## 3. Identity Model

### 3.1 Project

`project_id` is generated and owned by PostgreSQL. Every accepted telemetry record is associated with the authenticated project ID by the backend.

### 3.2 Run / Trace

For the supported MVP SDK profile:

> one Debugger Run = one OpenTelemetry trace.

The OpenTelemetry `trace_id` is the stable run identity used across ClickHouse telemetry and PostgreSQL analysis references.

### 3.3 Span

A span is identified logically by:

```text
(project_id, trace_id, span_id)
```

A repeated equivalent record with the same identity is a delivery duplicate, not a second execution operation.

## 4. PostgreSQL Logical Schema

### 4.1 `projects`

Representative fields:

- `id` UUID primary key
- `name`
- `created_at`
- `updated_at`
- project settings JSONB where appropriate

### 4.2 `api_keys`

Representative fields:

- `id`
- `project_id` FK
- key prefix / lookup identifier
- secret hash
- `created_at`
- `revoked_at`

Raw integration secrets are not stored after provisioning.

### 4.3 `analysis_attempts`

Representative fields:

- `id` UUID
- `project_id` FK
- `trace_id` fixed-format textual/byte representation
- `status`
- `mode` (`direct` / `bounded_read_only`)
- investigator/model configuration identity
- normalized input snapshot or snapshot reference
- `created_at`, `started_at`, `completed_at`
- failure metadata

The analysis snapshot is immutable once investigation begins.

### 4.4 `findings`

Representative fields:

- `id`
- `analysis_attempt_id` FK
- `project_id` FK
- `trace_id`
- optional `suspicious_span_id`
- category
- explanation
- priority (`high`, `medium`, `low`)
- limitations/uncertainty
- grounding status
- created timestamp

No 0–100 root-cause probability is stored.

### 4.5 `finding_evidence`

Evidence can reference either telemetry or authoritative knowledge.

Trace evidence fields may include:

- `finding_id`
- `project_id`
- `trace_id`
- `span_id`
- field/path identifier or bounded excerpt
- expected captured value/excerpt hash where useful

Knowledge evidence may include:

- `finding_id`
- `knowledge_document_id`
- `knowledge_chunk_id`
- bounded excerpt

### 4.6 `knowledge_documents`

- `id`
- `project_id`
- filename/title
- media/type metadata
- processing status
- checksum
- timestamps

### 4.7 `knowledge_chunks`

- `id`
- `document_id` FK
- `project_id`
- chunk text
- chunk ordinal
- embedding vector
- metadata JSONB

Vector queries are always project-scoped.

## 5. ClickHouse Logical Schema

### 5.1 `telemetry_spans`

A single initial span-oriented table is preferred over prematurely splitting every event type into separate tables.

Logical columns:

| Column | Meaning |
|---|---|
| `project_id` | authenticated project ownership |
| `trace_id` | Run/trace identity |
| `span_id` | span identity |
| `parent_span_id` | structural parent when present |
| `service_name` | instrumented service/resource identity |
| `operation_type` | run/agent/model/tool/retrieval/api/state/custom |
| `span_name` | human-readable operation name |
| `status_code` | unset/ok/error representation |
| `status_description` | optional status text |
| `started_at` | span start |
| `ended_at` | span end |
| `duration_ns` | derived/stored duration for queries |
| `input_payload` | serialized bounded input |
| `output_payload` | serialized bounded output |
| `error_payload` | structured/serialized error data |
| `attributes` | flexible attributes |
| `events` | span events, including exceptions |
| `links` | OpenTelemetry links / explicit relationship metadata where represented |
| `received_at` | ingestion receive time |
| `content_hash` | optional canonical identity/conflict support |

Exact ClickHouse types may use native UUID/fixed strings, LowCardinality, DateTime64, JSON/Object/String, Array/Nested, or other appropriate types after implementation validation.

### 5.2 Ordering / Primary Data Layout

The design must prioritize the dominant queries:

- project + trace lookup;
- project + time range run browsing;
- trace + span lookup;
- operation/status filtering.

A candidate ordering prefix is:

```text
(project_id, trace_id, started_at, span_id)
```

This is a starting hypothesis, not a frozen engine parameter. It must be validated against run-explorer and time-range workloads before finalizing.

### 5.3 Run Summaries

The MVP may derive run summaries from root/run spans rather than maintaining a second strongly consistent `runs` table in ClickHouse. If run-list performance requires it, a materialized projection/view may be added without changing the SDK protocol.

### 5.4 Events

Events initially remain attached to their span record unless query requirements justify a separate event table. This minimizes schema fragmentation.

## 6. Kafka Persistence Boundary

Kafka stores accepted telemetry temporarily as a durable log until trace-writer consumers persist it to ClickHouse.

Kafka is not queried by the UI or investigator.

### 6.1 Acknowledgement

FastAPI acknowledges ingestion only after successful Kafka publish.

### 6.2 Consumer Commit

The trace writer commits Kafka offsets only after successful ClickHouse persistence for the corresponding message/batch.

### 6.3 Delivery Semantics

At-least-once delivery means duplicates are possible. The storage/reconstruction layer must therefore distinguish:

- transport redelivery of the same span;
- actual application retries represented by distinct spans.

Exactly-once delivery is not claimed.

## 7. Cross-Store Relationships

PostgreSQL cannot enforce foreign keys into ClickHouse.

Therefore:

- `project_id`, `trace_id`, and `span_id` are stable cross-store identifiers;
- grounding validates that referenced ClickHouse evidence exists at analysis time;
- application services enforce project ownership before cross-store reads;
- findings never assume a database-level cross-store FK.

## 8. Immutability and Late Data

### 8.1 Telemetry

Ended accepted spans are logically immutable. Equivalent redelivery is idempotent. Conflicting content using the same span identity is treated as a protocol/storage conflict and surfaced for diagnostics rather than silently merged.

### 8.2 Late Spans

Late spans may be added to ClickHouse. Existing analysis attempts do not change because each attempt uses a stable snapshot.

### 8.3 Re-Analysis

A new analysis after late telemetry creates a new Analysis Attempt and new findings in PostgreSQL.

## 9. Analysis Snapshot

The OJT implementation may store a normalized analysis snapshot as PostgreSQL JSONB because analysis volume is low relative to telemetry volume.

If snapshots become too large in future, object storage or a manifest/hash strategy can replace the physical representation without changing the analysis contract.

## 10. Indexing / Query Strategy

### 10.1 PostgreSQL

Indexes should support:

- project lookup;
- active API-key lookup;
- project + analysis history;
- finding by analysis;
- knowledge by project/document;
- vector search filtered by project.

### 10.2 ClickHouse

ClickHouse performance is primarily driven by table engine, ordering key, partitioning, data skipping, and batch size rather than OLTP-style secondary indexing.

Do not copy PostgreSQL indexing habits directly into ClickHouse.

## 11. Transactions and Consistency

### 11.1 PostgreSQL

Use ordinary PostgreSQL transactions for project/auth/analysis/knowledge changes.

### 11.2 Kafka → ClickHouse

There is no distributed transaction between Kafka and ClickHouse.

The consumer uses retry + at-least-once semantics. Offsets are committed after persistence, which can cause redelivery after crash and therefore requires logical dedupe.

### 11.3 Analysis

An analysis attempt is created transactionally in PostgreSQL, but trace reads come from ClickHouse. The stable snapshot separates analysis reproducibility from later telemetry arrival.

## 12. Retention and Deletion

Initial OJT retention can be simple and configuration-driven.

Future ClickHouse TTL/object-storage retention may be added when data volume justifies it.

Project deletion across PostgreSQL and ClickHouse is an application-level orchestration operation; cross-store atomic delete is not promised in the MVP.

## 13. Security

- Database credentials are backend-only.
- Queries always include authenticated project scope.
- Sensitive payloads should be redacted before export where practical.
- Known secret headers are excluded by default.
- Knowledge vector searches are project-scoped.

## 14. Testing Requirements

Real integration tests are required for:

- PostgreSQL constraints/transactions;
- Kafka producer/consumer acknowledgement behavior;
- ClickHouse batched insert/query behavior;
- duplicate/redelivery semantics;
- late spans;
- run/trace queries;
- cross-store evidence grounding.

SQLite is not a substitute for PostgreSQL-specific behavior, and mocked analytical storage is not sufficient for final ClickHouse semantics.

## 15. Key Database Decisions

| Area | Decision |
|---|---|
| Telemetry system of record | ClickHouse |
| Transactional system of record | PostgreSQL |
| Ingestion buffer | Kafka |
| Vector knowledge | PostgreSQL-compatible vector capability such as pgvector |
| Span identity | `(project_id, trace_id, span_id)` |
| Cross-store FK | application-level validation only |
| Delivery | at-least-once; duplicates possible |
| Analysis history | PostgreSQL |
| Trace mutation | ended spans logically immutable |
| Late telemetry | accepted; new analysis attempt required for updated interpretation |
