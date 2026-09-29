# AI Agent Execution Debugging & Trace Analysis Platform

## Product Requirements Document

## 1. Document Information

| Field | Value |
|---|---|
| Product | AI Agent Execution Debugging & Trace Analysis Platform |
| Stage | OJT MVP |
| Primary user | AI application developer |
| Backend | Python, FastAPI |
| Instrumentation | Thin Python SDK built on OpenTelemetry |
| Telemetry ingestion | Batched HTTPS/JSON → FastAPI → Kafka |
| Telemetry storage | ClickHouse |
| Transactional storage | PostgreSQL |
| Authoritative knowledge | PostgreSQL + pgvector-compatible vector capability |
| Frontend | React + JavaScript |
| Semantic investigation | Existing capable LLM API |

## 2. Product Goal

Enable developers to understand supported AI-agent executions, identify the steps most worth investigating, and inspect the evidence behind those findings without requiring a known-good historical run.

The platform records execution activity as structured traces, reconstructs the execution, uses one controlled LLM-based debugger investigator for semantic reasoning, validates cited evidence deterministically, and presents the results in a developer-facing interface.

The product reports:

> **Suspicious step(s) + explanation + supporting evidence + limitations**

It does not claim guaranteed root-cause proof.

## 3. Problem Statement

AI-agent applications may involve models, tools, APIs, retrieval systems, databases, state, memory, and other agents. When the final result is wrong, ordinary logs often fail to answer four practical questions:

1. What actually happened during the execution?
2. Which step first became suspicious or inconsistent?
3. Was the problem caused by reasoning, retrieval, a tool, or an upstream agent?
4. What recorded evidence supports that conclusion?

The problem becomes harder when executions are asynchronous, partially recorded, contain retries, or are internally consistent despite having retrieved incorrect knowledge.

The platform therefore needs both execution telemetry and controlled semantic investigation.

## 4. Target Users

### 4.1 Primary User — AI Application Developer

The primary user builds or maintains an AI-agent application and needs to investigate incorrect, unexpected, or suspicious outcomes.

Typical tasks include:

- instrumenting an agent with minimal code changes;
- browsing previous executions;
- inspecting model, tool, retrieval, and agent steps;
- understanding failures and retries;
- identifying suspicious steps;
- comparing agent-retrieved information with optional authoritative project knowledge;
- validating debugger findings against exact evidence.

## 5. Product Scope

### 5.1 In Scope

#### Trace Instrumentation

- Thin Python debugger SDK built on the OpenTelemetry API/SDK.
- Root Run boundary represented by an OpenTelemetry trace for the supported SDK profile.
- Spans for agent, model, tool, retrieval, API, state, and custom operations where instrumented.
- Automatic parent-child context propagation through OpenTelemetry.
- Explicit relationship metadata only when the application or instrumentation can establish it.
- Capture controls, payload limits, redaction hooks, and known-secret exclusion.

#### Trace Collection

- Batched HTTPS/JSON export from the SDK.
- Project-authenticated FastAPI ingestion endpoint.
- Validation of supported trace payloads before acceptance.
- Kafka-backed ingestion buffer so receiving telemetry is decoupled from analytical storage writes.
- At-least-once delivery semantics; duplicate delivery must not create misleading duplicate execution steps.
- Support for late, out-of-order, and partial telemetry.

#### Telemetry Storage

- ClickHouse as the primary store for high-volume execution telemetry.
- Core typed fields for project, trace, span, parent, operation type, status, and time.
- Flexible model/tool/retrieval payloads and provider-specific metadata.
- Efficient trace reconstruction and filtering by project, trace, operation type, status, time, and agent identity.

#### Transactional Platform Data

PostgreSQL stores lower-volume transactional/control-plane data such as:

- projects;
- integration credentials;
- project configuration;
- analysis attempts;
- findings;
- evidence metadata;
- authoritative document metadata and embeddings.

#### Trace Reconstruction

- Reconstruct hierarchy from trace/span identity and parentage.
- Preserve incomplete traces rather than fabricating missing information.
- Do not treat backend arrival order or timestamp order as proof of causality.
- Preserve explicit relationships such as dependency, handoff, consumption, or retry where captured.

#### Debugger Investigation

- One controlled LLM debugger investigator, not a multi-agent swarm.
- Direct analysis for bounded runs.
- Bounded read-only trace/knowledge access for large or structurally complex runs.
- Structured candidate findings with cited evidence and explicit limitations.

#### Deterministic Validation and Grounding

Deterministic code remains responsible for objective checks such as:

- malformed or inconsistent structure;
- explicit statuses/errors;
- missing references;
- evidence-reference validation;
- stable presentation ordering.

It is not a large semantic rule engine.

#### Optional Authoritative Knowledge

- Project-specific document upload.
- Text extraction, chunking, embeddings, and project-scoped vector retrieval.
- Initial implementation uses PostgreSQL-compatible vector search such as pgvector.
- Used when trace evidence alone cannot determine whether retrieved information was itself correct.
- Not a general-purpose RAG or knowledge-management platform.

#### Debugging Interface

- Run Explorer.
- Execution hierarchy/timeline view.
- Step Inspector.
- Findings with evidence and limitations.
- Optional authoritative comparison.

#### Controlled Evaluation

Use the existing controlled agent workloads to evaluate expected suspicious-step identification, evidence validity, false positives, recovered retry handling, retrieval-vs-reasoning failures, stability, latency, and cost.

## 6. Feature Priorities

| Priority | Capabilities |
|---|---|
| Must | OpenTelemetry-based SDK, batched ingestion, Kafka buffering, ClickHouse telemetry persistence, trace reconstruction, one controlled debugger investigator, evidence grounding, Run Explorer, Step Inspector, findings, PostgreSQL project/analysis persistence |
| Should | Optional authoritative knowledge, bounded large-run investigation, project-scoped vector retrieval, analysis history, controlled evaluation metrics |
| Could | Framework-specific adapters, historical comparison, background analysis, richer knowledge management |
| Future | Replay, counterfactual execution, automatic remediation, enterprise IAM/compliance, multi-region observability infrastructure |

## 7. User Stories

### US-001 — Instrument an Agent

As a developer, I want to add the debugger SDK to a Python agent so that meaningful execution steps are captured without rewriting the application.

Acceptance criteria:

- SDK initialization is small and explicit.
- OpenTelemetry provides trace/span identity and context propagation.
- The SDK can create run, agent, model, retrieval, and tool spans.
- Instrumentation failure is fail-open and does not intentionally fail the observed agent.

### US-002 — Submit Telemetry Reliably

As a developer, I want completed spans to be exported in batches so that debugging telemetry does not require one synchronous database write per span.

Acceptance criteria:

- SDK exports batches over authenticated HTTPS/JSON.
- FastAPI validates the project and supported payload shape.
- Accepted payloads are published to Kafka before the ingestion request is acknowledged.
- Kafka/ClickHouse implementation details remain hidden from SDK users.

### US-003 — Browse Previous Runs

As a developer, I want to browse captured runs and open one for investigation.

Acceptance criteria:

- Runs are scoped by project.
- Run summaries can be derived efficiently from ClickHouse telemetry.
- Partial runs remain visible with an appropriate completeness indicator.

### US-004 — Understand Execution Structure

As a developer, I want to see parent-child and explicitly observed relationships so I can understand the execution without assuming unsupported causality.

### US-005 — Inspect an Execution Step

As a developer, I want to inspect captured inputs, outputs, errors, attributes, events, and timing for a selected span.

### US-006 — Identify Suspicious Steps

As a developer, I want one controlled debugger investigator to identify the steps most worth investigating and explain why.

Acceptance criteria:

- Findings are structured.
- Findings reference exact trace or authoritative evidence.
- Findings include uncertainty/limitations.
- Priority is investigation priority, not root-cause probability.

### US-007 — Verify Evidence

As a developer, I want the platform to verify that evidence cited by the investigator actually exists and matches the analyzed sources.

### US-008 — Debug Wrong Retrieval

As a developer, I want to optionally provide authoritative documents so that the debugger can distinguish a retrieval/knowledge mismatch from downstream reasoning that merely followed bad retrieved information.

### US-009 — Evaluate the Debugger

As an evaluator, I want controlled scenarios with hidden expected outcomes so that debugger quality can be measured objectively.

## 8. Functional Requirements

### FR-001 — Project-Authenticated Trace Submission

The platform shall require project-scoped integration credentials for trace submission.

### FR-002 — OpenTelemetry Run and Span Model

For the supported MVP SDK profile, one Debugger Run shall map to one OpenTelemetry trace. Nested operations shall be represented as spans in that trace when context propagation is preserved.

### FR-003 — Batched Export

The SDK shall batch completed spans before export and shall use bounded queues/timeouts so debugger unavailability does not block the application indefinitely.

### FR-004 — Ingestion Buffer

Validated trace batches shall be published to Kafka before successful ingestion acknowledgement. Kafka is an internal backend boundary and is not exposed to SDK users.

### FR-005 — Telemetry Persistence

A trace-writer consumer shall persist accepted execution telemetry into ClickHouse in batches suitable for analytical ingestion.

### FR-006 — Duplicate and Retry Handling

The platform shall tolerate at-least-once delivery. Equivalent re-delivery shall not produce misleading duplicate execution steps. Application retries are separate execution attempts and shall remain distinguishable from transport duplicates.

### FR-007 — Out-of-Order and Partial Trace Handling

Late spans, missing parents, and out-of-order arrival shall not be rejected solely because execution order is incomplete.

### FR-008 — Trace Reconstruction

The platform shall reconstruct a safe execution view from stored telemetry without inferring causality from arrival order or timestamps alone.

### FR-009 — Run and Span Inspection

The platform shall expose project-scoped APIs for run browsing, trace detail, and step inspection.

### FR-010 — Semantic Debugger Investigation

The platform shall allow a developer to request analysis of a reconstructed run using one controlled LLM-based debugger investigator.

For bounded runs, the normalized run may be supplied directly. For larger runs, the same investigator may use a bounded set of read-only trace and authoritative-knowledge access capabilities.

### FR-011 — Candidate Findings

The investigator shall return structured candidate findings containing a suspicious step when applicable, category, explanation, cited evidence, and limitations.

### FR-012 — Evidence Grounding

Before a candidate is presented as grounded, deterministic code shall verify that cited trace spans/fields or authoritative passages exist and match the analyzed sources.

### FR-013 — Stable Analysis Input

Each analysis attempt shall correspond to a stable normalized input snapshot or equivalent immutable input representation so later telemetry does not silently change an earlier result.

### FR-014 — Recorded vs Derived Data

Recorded execution telemetry in ClickHouse shall remain distinct from derived analysis data in PostgreSQL.

### FR-015 — Authoritative Knowledge

When enabled, project-scoped authoritative documents shall be searchable by the investigator through a bounded read-only interface.

### FR-016 — Findings and Priority

Grounded findings shall be stored in PostgreSQL and may use High, Medium, or Low investigation priority. Priority shall not be presented as causal probability.

### FR-017 — Controlled Evaluation

The platform shall support repeatable controlled agent executions and evaluation of expected suspicious-step hit rate, evidence validity, false positives, retry handling, and retrieval-vs-reasoning classification where authority exists.

## 9. Product States

### 9.1 Run State

The platform distinguishes the observed application state from telemetry completeness. A completed agent run may still have incomplete telemetry, and a failed child span does not automatically make the whole run failed.

### 9.2 Analysis State

Analysis attempts may be:

- pending;
- running;
- completed;
- failed.

A completed analysis may contain zero grounded findings.

## 10. Product Principles

### 10.1 Preserve Debugging Capability While Minimizing Complexity

Reuse solved infrastructure and add components only when they provide a concrete debugging capability.

### 10.2 Record Facts Before Interpretation

Captured execution facts remain separate from derived analysis.

### 10.3 Evidence Before Conclusion

A presented finding must be tied to recorded trace evidence or explicitly provided authoritative knowledge.

### 10.4 Arrival Order Is Not Execution Order

Kafka arrival order, HTTP arrival order, ClickHouse insertion order, and timestamps do not by themselves establish causality.

### 10.5 Fail Open at the Agent Boundary

Debugger outages should not intentionally cause the developer's agent to fail.

### 10.6 Separate Workloads by Storage Type

High-volume analytical telemetry belongs in ClickHouse. Transactional application and analysis data belongs in PostgreSQL.

### 10.7 Queueing Decouples Ingestion from Persistence

Kafka absorbs bursts and prevents the ingestion API from requiring synchronous ClickHouse writes for every incoming span batch.

### 10.8 Semantic Reasoning Is LLM-Based; Grounding Is Deterministic

The investigator handles arbitrary semantic inconsistencies. Deterministic code handles objective structure and evidence validation.

## 11. Out of Scope

The OJT MVP does not require:

- universal framework compatibility;
- production-scale Kafka clusters or multi-region replication;
- Kubernetes;
- microservice decomposition beyond the minimal Kafka consumer boundary;
- enterprise DLP, SSO, billing, or compliance certification;
- model training or fine-tuning;
- dedicated debugger memory products;
- a separate vector-database service;
- automatic remediation;
- replay or counterfactual execution as required functionality.

## 12. Success Criteria

| Area | Success criterion |
|---|---|
| Instrumentation | A sample agent produces a correct OpenTelemetry trace with run/agent/model/tool/retrieval spans and captured evidence. |
| Ingestion | Batched telemetry is accepted through FastAPI and can be published to Kafka without one DB write per span. |
| Storage | A Kafka consumer persists trace telemetry to ClickHouse and the trace can be queried by project/trace ID. |
| Reconstruction | Parent-child structure and partial-trace warnings are reconstructed correctly. |
| Investigation | The LLM debugger produces structured candidate findings for controlled scenarios. |
| Grounding | Invalid evidence references are rejected or marked ungrounded. |
| Authority | At least one controlled scenario distinguishes wrong retrieval from downstream reasoning using uploaded authoritative knowledge. |
| UI | A developer can browse a run, inspect steps, and view grounded findings/evidence. |
| Evaluation | Controlled scenarios report expected suspicious-step hit, evidence validity, false positives, and basic latency/cost. |
| End-to-End | At least one execution successfully travels through SDK → FastAPI → Kafka → ClickHouse → reconstruction → investigator → grounding → PostgreSQL findings → UI. |
