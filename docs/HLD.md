# High-Level Design (HLD)
## AI Agent Execution Debugging & Trace Analysis Platform

## 1. Purpose and Design Philosophy

This High-Level Design defines the system boundaries, major components, information flow, deployment model, and principal architecture decisions for the AI Agent Execution Debugging & Trace Analysis Platform.

The platform helps developers understand supported AI-agent executions and identify the steps most worth investigating. It captures structured execution telemetry, stores and reconstructs traces, uses one controlled LLM debugger investigator to propose evidence-backed findings, validates cited evidence, and presents the result through a debugging interface.

The governing principle is:

> **Preserve debugging capability while minimizing implementation complexity. Reuse solved infrastructure, and introduce complexity only when it provides a concrete debugging capability.**

The platform guides investigation. It does not claim guaranteed root cause, causal proof, or universal framework compatibility.

### 1.1 Architecture Goals

- Capture supported Python agent executions through a thin debugger SDK built on OpenTelemetry.
- Decouple high-volume trace ingestion from analytical persistence.
- Store execution telemetry in a database designed for append-heavy analytical workloads.
- Keep transactional/control-plane data separate from telemetry.
- Reconstruct incomplete and out-of-order traces without inventing causality.
- Use one controlled LLM investigator for semantic debugging.
- Ground every presented finding in recorded trace evidence or optional project-scoped authoritative knowledge.
- Keep recorded execution facts separate from derived analysis.
- Provide a hosted debugging workflow through FastAPI, Kafka, ClickHouse, PostgreSQL, and React.

### 1.2 Non-Goals

The OJT MVP does not provide a general observability platform, general-purpose RAG platform, dedicated debugger-memory service, autonomous investigator swarm, calibrated root-cause probabilities, enterprise-scale Kafka operations, or universal framework support. Replay and counterfactual debugging remain future scope.

## 2. System Context and Boundaries

The debugger operates beside the developer's AI-agent application. The developer owns application logic, models, tools, APIs, databases, retrieval systems, orchestration, business knowledge, and agent memory.

The platform owns instrumentation helpers, trace export, authenticated ingestion, Kafka buffering, telemetry persistence, trace reconstruction, debugger investigation, optional authoritative-knowledge indexing, evidence grounding, analysis history, APIs, and the web interface.

Supported multi-agent executions use the same Run/Span model. This does not create a separate multi-agent debugger architecture.

See `diagrams/system_context_diagram.mermaid`.

## 3. High-Level Architecture

The platform uses:

- a thin Python debugger SDK built on OpenTelemetry;
- batched authenticated HTTPS/JSON trace export;
- a FastAPI modular-monolith application boundary;
- Kafka as the trace-ingestion buffer;
- ClickHouse as the primary execution-telemetry store;
- PostgreSQL for transactional/control-plane, analysis, and knowledge data;
- PostgreSQL-compatible vector search such as pgvector for optional authoritative knowledge;
- one controlled LLM debugger investigator;
- deterministic evidence grounding;
- a React JavaScript frontend.

See `diagrams/high_level_architecture.mermaid`.

### 3.1 Instrumentation and Transport

The Python debugger SDK is intentionally thin and built on OpenTelemetry. OpenTelemetry provides trace/span identity, context propagation, spans, events, links, processing, and batching. The debugger layer adds AI-agent-specific semantics for model, retrieval, tool, API, state, and orchestration activity.

For the supported MVP SDK profile, one Debugger Run maps to one OpenTelemetry trace.

Captured ended spans are batched and exported over authenticated HTTPS/JSON to FastAPI. The SDK does not know whether the backend uses Kafka, ClickHouse, PostgreSQL, or any other internal storage component.

### 3.2 Trace Ingestion Buffer

FastAPI validates project authentication and supported trace payloads, then publishes accepted telemetry to Kafka.

Kafka provides:

- burst absorption;
- decoupling between HTTP ingestion and analytical storage writes;
- replay/retry capability for backend persistence;
- a stable boundary for future additional telemetry consumers.

The OJT implementation keeps Kafka deliberately small. The architecture does not require a large multi-broker production cluster.

### 3.3 Telemetry Storage — ClickHouse

ClickHouse is the primary store for high-volume execution telemetry such as traces, spans, events, attributes, timing, model/tool/retrieval payloads, and explicit errors.

The choice separates append-heavy analytical telemetry from transactional application data and avoids requiring PostgreSQL to be the primary span store.

Trace reconstruction and large-run read-only investigation query ClickHouse through backend services. The browser and SDK never access ClickHouse directly.

### 3.4 Transactional and Knowledge Storage — PostgreSQL

PostgreSQL stores lower-volume relational/control-plane data:

- projects;
- integration credentials;
- project configuration;
- analysis attempts;
- findings;
- evidence metadata;
- authoritative document metadata;
- optional vector embeddings through pgvector-compatible capability.

PostgreSQL is no longer the primary trace/span store.

### 3.5 Trace Reconstruction

The reconstruction layer queries ClickHouse and builds a safe execution view from trace/span identity, parentage, events, and explicit observed relationships.

It does not treat HTTP arrival order, Kafka order, ClickHouse insertion order, or timestamps alone as proof of causality.

### 3.6 Investigation and Grounding

Semantic debugging is handled by one controlled LLM debugger investigator.

For bounded runs, the investigator receives a normalized run directly. For large or structurally complex runs, the same investigator may use a bounded set of read-only trace and authoritative-knowledge access capabilities.

Deterministic code is limited to objective responsibilities such as structural validation, explicit statuses/errors, evidence-reference verification, and stable presentation ordering. It is not a large semantic rule engine.

### 3.7 Optional Authoritative Knowledge

Projects may upload authoritative documents when trace evidence alone cannot establish whether retrieved information was correct.

The platform performs text extraction, chunking, embeddings, and project-scoped vector retrieval, preferably using PostgreSQL-compatible vector search such as pgvector. This is optional and is not a general-purpose RAG platform.

### 3.8 Debugging Interface

The React interface presents run exploration, execution structure, step inspection, errors/retries, grounded findings, supporting evidence, and optional authoritative comparison.

## 4. Major Component Responsibilities

### 4.1 Thin Debugger SDK

- Runs inside the developer application.
- Creates OpenTelemetry-based run/agent/model/tool/retrieval spans.
- Captures debugger-specific metadata and selected payloads.
- Exports completed spans in batches.
- Fails open on debugger/backend failure.

### 4.2 FastAPI Ingestion Boundary

- Authenticates the project integration.
- Validates supported trace batches.
- Normalizes transport-level data when needed.
- Publishes accepted telemetry to Kafka.
- Returns success only after the batch is accepted by the ingestion buffer.

### 4.3 Kafka

- Buffers accepted telemetry.
- Decouples HTTP request handling from ClickHouse persistence.
- Allows trace-writer retry/replay without making the SDK aware of storage failures.

### 4.4 Trace Writer

- Consumes telemetry from Kafka.
- Groups writes into efficient ClickHouse inserts.
- Commits Kafka progress only after the corresponding persistence step succeeds.
- Preserves at-least-once semantics; duplicate delivery is handled logically by trace identity/content rules.

### 4.5 ClickHouse Telemetry Store

- Stores high-volume execution telemetry.
- Supports trace/run reads, filtering, span lookup, error queries, and large-run investigation access.
- Does not own projects, credentials, findings, or authoritative knowledge.

### 4.6 PostgreSQL Platform Store

- Stores project ownership, credentials, settings, analysis attempts, findings, and knowledge metadata/vector data.
- Maintains transactional relationships and constraints for platform data.

### 4.7 Trace Reconstruction

- Builds inspectable execution structure from ClickHouse telemetry.
- Preserves partial/incomplete traces.
- Avoids unsupported causal inference.

### 4.8 Debugger Investigator and Grounding

- One bounded LLM investigator identifies candidate suspicious steps.
- Direct analysis handles bounded runs.
- Bounded read-only investigation handles larger runs.
- Deterministic grounding verifies cited trace/knowledge evidence before presentation.

### 4.9 Debugging APIs and React Interface

- Expose project-scoped run, trace, analysis, finding, evidence, and knowledge views.
- Browser never accesses Kafka, ClickHouse, PostgreSQL, or provider credentials directly.

## 5. End-to-End Data Flow

1. A supported agent records operations through the debugger SDK and OpenTelemetry.
2. Completed spans are batched by the SDK.
3. The custom exporter submits authenticated HTTPS/JSON batches to FastAPI.
4. FastAPI validates project access and payload shape.
5. Accepted telemetry is published to Kafka.
6. A trace-writer consumer batches and persists telemetry to ClickHouse.
7. When a developer opens or analyzes a run, the backend reconstructs it from ClickHouse.
8. A bounded run is analyzed directly; a complex run may be inspected through bounded read-only trace access.
9. Optional authoritative passages are retrieved from project-scoped PostgreSQL/vector knowledge when needed.
10. Deterministic grounding validates cited evidence.
11. Analysis attempts/findings are persisted in PostgreSQL.
12. The React UI displays the trace, findings, evidence, and limitations.

See `diagrams/end_to_end_data_flow.mermaid`.

## 6. High-Level Data Concepts

| Concept | Architectural meaning |
|---|---|
| Project | Transactional ownership/access boundary stored in PostgreSQL. |
| Run | One supported logical execution; one OpenTelemetry trace in the MVP SDK profile. |
| Span | Duration-bearing execution operation stored as telemetry in ClickHouse. |
| Event / Relationship | Instantaneous observation or explicitly observed connection associated with telemetry. |
| Analysis Attempt | One debugger investigation of a stable normalized run input, stored in PostgreSQL. |
| Finding | Evidence-backed investigation hypothesis stored in PostgreSQL and referencing trace/knowledge evidence. |
| Knowledge Document | Optional project-scoped authoritative source material stored/indexed through PostgreSQL-compatible knowledge storage. |

Recorded telemetry remains separate from derived analysis. Re-analysis creates new derived results rather than rewriting the original trace.

## 7. Deployment Architecture

The developer environment contains the AI-agent application and debugger SDK.

The hosted platform contains:

- React application;
- FastAPI modular monolith;
- Kafka;
- trace-writer consumer;
- ClickHouse;
- PostgreSQL with optional vector capability;
- access to an existing capable LLM API.

The OJT architecture does not require Kubernetes, a service mesh, or broad microservice decomposition.

See `diagrams/deployment_architecture.mermaid`.

## 8. Technology Choices

| Area | Technology | Reason |
|---|---|---|
| Backend / SDK | Python | Shared ecosystem for instrumentation, backend services, and debugger orchestration. |
| Backend framework | FastAPI | Typed HTTP boundary for ingestion and debugging APIs. |
| Tracing foundation | OpenTelemetry API/SDK | Standard trace/span identity, context propagation, events, links, processing, batching. |
| SDK transport | Batched HTTPS/JSON | Simple debugger-specific ingestion contract. |
| Ingestion buffer | Kafka | Decouples bursty trace ingestion from analytical persistence and supports retry/replay. |
| Telemetry store | ClickHouse | High-ingest analytical storage suited to trace/span workloads. |
| Transactional store | PostgreSQL | Relational integrity and transactions for projects, credentials, analyses, findings, and knowledge metadata. |
| Vector search | pgvector-compatible PostgreSQL capability | Keeps authoritative retrieval project-scoped without another database service. |
| Database access | SQLAlchemy/Alembic for PostgreSQL; ClickHouse-native client/repository for telemetry | Avoids forcing analytical storage through ORM semantics. |
| Investigator | Existing capable LLM API | Semantic cross-step reasoning without a hard-coded semantic rule engine. |
| Frontend | React + JavaScript | Interactive debugging workflow. |
| Packaging/deployment | Docker | Reproducible development/testing/deployment where appropriate. |

## 9. Reliability, Security, and Data Principles

### 9.1 Reliability

- Instrumentation fails open.
- SDK batching is bounded.
- FastAPI does not synchronously write each individual span to the analytical database.
- Kafka absorbs bursts and decouples ingestion from ClickHouse persistence.
- Trace-writer offsets are committed only after the corresponding persistence step succeeds.
- At-least-once delivery is accepted; exact-once delivery is not claimed.
- Incomplete/out-of-order traces remain inspectable.
- Investigator/knowledge/grounding failure does not destroy access to the recorded trace.
- Authoritative knowledge is optional.

### 9.2 Security and Data Handling

- External SDK/browser traffic uses HTTPS.
- Integration credentials and all reads are project-scoped.
- Browser and SDK never connect directly to Kafka, ClickHouse, or PostgreSQL.
- Provider/database credentials remain backend-only.
- Sensitive trace data is minimized, bounded, and redacted where practical before export.
- Uploaded knowledge remains isolated to its project.
- Captured trace content is treated as untrusted input and cannot override debugger system instructions.

## 10. Scalability and Evolution

The architecture separates transactional and analytical workloads from the start while keeping the application itself relatively simple.

Initial scaling work should focus on batching, ClickHouse ordering/index design, Kafka consumer throughput, query efficiency, pagination, payload limits, and bounded analysis.

Possible future evolution includes OTLP/Collector interoperability, additional language SDKs, framework-specific adapters, retention/object-storage strategies, historical comparison, background analysis, additional consumers, and selective service extraction.

Kafka, ClickHouse, and PostgreSQL are already explicit responsibilities; Kubernetes and broad microservices are not introduced without measured need.

## 11. Future Replay and Counterfactual Layer

Replay and counterfactual debugging remain future capabilities. They require additional side-effect controls, replay-safe execution boundaries, comparison semantics, and UI work and are intentionally outside the required OJT MVP.

## 12. Key Architecture Decisions

| Area | Decision | Why |
|---|---|---|
| Design philosophy | Preserve capability with minimum necessary complexity. | Keeps the OJT focused on debugging value. |
| Instrumentation | Thin debugger SDK over OpenTelemetry. | Reuses standard tracing/context mechanics. |
| Run mapping | One Debugger Run = one OTel trace for supported SDK profile. | Clear execution boundary. |
| SDK transport | Batched authenticated HTTPS/JSON. | Simple client contract independent of backend internals. |
| Ingestion buffer | Kafka. | Absorbs bursts and decouples HTTP ingestion from ClickHouse writes. |
| Telemetry storage | ClickHouse. | Better fit for high-volume append-heavy analytical trace data. |
| Transactional storage | PostgreSQL. | Strong relational/transactional fit for projects, credentials, analyses, findings, and knowledge. |
| Knowledge vector search | PostgreSQL-compatible vector capability such as pgvector. | Avoids another service while supporting authoritative comparison. |
| Semantic analysis | One controlled LLM debugger investigator. | General semantic reasoning without a rule-engine swarm. |
| Large-run analysis | Same investigator + bounded read-only trace/knowledge access. | Preserves focus and cost control. |
| Grounding | Deterministically verify cited evidence. | Prevents unsupported citations. |
| Ranking | High/Medium/Low investigation priority; not root-cause probability. | Avoids unsupported precision. |
| Memory | No dedicated debugger memory service. | No current requirement justifies one. |
| Replay | Future only. | Keeps MVP focused. |

## 13. Documentation Boundary

This HLD owns system-level architecture. Lower-level mechanics remain in:

| Document | Detail deferred from HLD |
|---|---|
| `LLD.md` | module structure, Kafka producer/consumer flow, repository boundaries, runtime error handling |
| `trace-protocol.md` | trace fields, relationship semantics, batching, duplicate semantics, payload rules |
| `database.md` | PostgreSQL + ClickHouse logical schemas, indexes/order keys, cross-store references, migrations |
| `analysis-engine.md` | investigator contract, bounded tools, analysis snapshot, grounding, findings, priority |
| `future/replay-counterfactual.md` | future replay/counterfactual execution |
