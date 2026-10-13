# Debugger Investigation and Evidence Grounding
## AI Agent Execution Debugging & Trace Analysis Platform

## 1. Purpose and Scope

This document defines the semantic debugging layer of the platform.

The old design centered on a deterministic semantic rule engine. That design is superseded.

The current model is:

```text
Reconstructed Trace
   ↓
Stable Analysis Input
   ↓
One Controlled LLM Debugger Investigator
   ↓
Structured Candidate Findings
   ↓
Deterministic Evidence Grounding
   ↓
Grounded Findings
```

Deterministic logic remains for objective structural checks and evidence verification, not for hard-coding arbitrary semantic business contradictions.

## 2. Design Principles

### 2.1 Evidence Before Conclusion

A finding must cite concrete trace evidence and, when used, project-scoped authoritative knowledge.

### 2.2 Recorded Trace Is Immutable

Analysis never rewrites ClickHouse telemetry.

### 2.3 Semantic Reasoning Is LLM-Based

The investigator reasons across model outputs, retrievals, tool results, agent handoffs, and other captured evidence.

### 2.4 Grounding Is Deterministic

Machine-checkable evidence references are verified by backend code before findings are presented as grounded.

### 2.5 Missing Evidence Reduces Certainty

The investigator must state limitations when telemetry or authoritative knowledge is insufficient.

### 2.6 No Guaranteed Root Cause

The product reports suspicious steps and evidence. It does not claim causal proof.

## 3. Analysis Input

### 3.1 Reconstruction Source

Trace data is read from ClickHouse and reconstructed into a normalized run representation.

### 3.2 Stable Snapshot

Before investigation, the backend creates an immutable analysis input snapshot or equivalent stable representation and associates it with a PostgreSQL Analysis Attempt.

This prevents late ClickHouse spans from silently changing what an earlier analysis means.

### 3.3 Normalized Run

The normalized representation may include:

- run/trace identity;
- spans and hierarchy;
- operation types;
- selected inputs/outputs;
- statuses/errors/events;
- explicit relationships;
- structural warnings;
- retry grouping metadata;
- completeness indicators.

## 4. Investigator Execution Modes

### 4.1 Direct Mode

For bounded runs that fit within configured analysis limits:

```text
Complete Normalized Run
  ↓
LLM Debugger
  ↓
Candidate Findings
```

### 4.2 Bounded Read-Only Mode

Large or structurally complex runs are not blindly dumped into one prompt.

The same investigator may use a small set of backend-owned read-only capabilities conceptually equivalent to:

- run overview;
- span lookup;
- related-span lookup;
- filtered trace search;
- authoritative knowledge search.

The exact tool names are an implementation detail.

### 4.3 Bounds

The investigator is limited by:

- maximum tool calls;
- token/context budget;
- wall-clock timeout;
- read-only permissions;
- project scope.

It cannot mutate the agent, trace, ClickHouse, or PostgreSQL business state.

## 5. Investigator Responsibilities

The investigator may identify patterns such as:

- tool fails but downstream output claims success;
- retrieval says X but a model concludes incompatible Y;
- one agent supplies evidence but a supervisor contradicts it;
- a decision is unsupported by available evidence;
- retrieval output conflicts with project authoritative knowledge;
- retries recover from an earlier failure and therefore change investigation priority.

The investigator should identify the earliest important inconsistency where evidence permits, but must not fabricate causal order when execution relations are ambiguous.

## 6. Candidate Finding Contract

A candidate finding contains:

- finding category;
- suspicious span/operation when applicable;
- explanation;
- investigation priority proposal;
- trace evidence references;
- optional authoritative evidence references;
- limitations/uncertainty.

Candidate findings are not yet guaranteed grounded.

## 7. Investigation Priority

The platform does not use a 0–100 root-cause probability.

Priority levels:

- **HIGH** — strong grounded contradiction or important unrecovered failure;
- **MEDIUM** — material execution/structural issue worth investigation;
- **LOW** — recovered failure, completeness warning, or weakly connected concern.

Priority expresses investigation order, not probability that the step caused the final outcome.

Stable deterministic tie-breaking may be used for presentation.

## 8. Structural Deterministic Checks

Objective checks may run before or alongside LLM investigation:

- malformed identifiers/required fields;
- impossible/self-parenting relationships;
- cycle detection;
- explicit error/status/cancellation markers;
- missing referenced spans;
- retry grouping/recovery status;
- telemetry completeness warnings.

These checks provide facts/context. They are not the primary semantic debugger.

## 9. Evidence Model

### 9.1 Trace Evidence

Trace evidence references stable identifiers:

- project ID;
- trace ID;
- span ID;
- field/path or bounded excerpt where useful.

The source value is read from the stable analysis snapshot/ClickHouse-backed reconstruction used for that attempt.

### 9.2 Authoritative Evidence

Knowledge evidence references project-owned document/chunk identifiers and bounded excerpts retrieved from PostgreSQL-compatible knowledge storage.

### 9.3 No Full-Payload Duplication in Findings

Findings should reference evidence rather than copying entire large model/tool payloads into PostgreSQL.

## 10. Evidence Grounding

Grounding verifies:

- cited trace/span exists;
- cited field/path or excerpt exists;
- cited value/excerpt matches;
- evidence belonged to the analyzed snapshot;
- explicit relationship exists when the claim relies on it;
- authoritative document/chunk belongs to the same project.

Grounding does **not** prove:

- semantic interpretation is correct;
- the cited evidence caused the outcome;
- an authoritative document is universally true.

Unsupported references cause the candidate to be rejected or marked ungrounded according to product policy.

## 11. Authoritative Knowledge

### 11.1 Why It Exists

Trace evidence shows what the agent saw. It cannot always prove that retrieved information was correct.

Example:

```text
Authoritative policy = 14 days
Agent retrieval = 30 days
Agent decision follows 30-day result
```

Without an independent source, the trace is internally consistent. Optional authoritative knowledge lets the investigator identify the retrieval/knowledge step as suspicious.

### 11.2 Scope

The knowledge capability remains narrow:

- uploaded project documents;
- extraction/chunking/embeddings;
- project-scoped vector search;
- bounded investigator access.

No general-purpose knowledge platform is required.

## 12. Analysis Lifecycle

1. Validate project access.
2. Reconstruct trace from ClickHouse.
3. Build stable normalized snapshot.
4. Create PostgreSQL Analysis Attempt (`pending`).
5. Mark attempt `running`.
6. Execute investigator in direct or bounded-read mode.
7. Parse structured candidate findings.
8. Ground each candidate.
9. Persist grounded findings and evidence metadata in PostgreSQL.
10. Mark attempt `completed` or `failed`.

A completed attempt may contain zero findings.

## 13. Re-Analysis

Re-analysis never mutates old findings.

A new attempt receives a new stable snapshot. This allows later telemetry or knowledge changes to produce new results while preserving historical interpretation.

## 14. Failure Handling

### 14.1 Investigator Failure

- mark attempt failed;
- keep trace accessible;
- preserve previous attempts/findings.

### 14.2 ClickHouse Read Failure

- do not create misleading findings from incomplete backend reads;
- surface analysis failure/temporary unavailability.

### 14.3 Knowledge Search Failure

Trace-only investigation may continue when appropriate, but the investigator must not invent authoritative facts and must state the limitation.

### 14.4 Grounding Failure

Invalid evidence references are not presented as grounded findings.

## 15. Security and Prompt-Injection Considerations

Captured trace payloads and uploaded documents are untrusted data.

The investigator receives system-level instructions that explicitly treat captured content as evidence, not instructions. Tool access is read-only and project-scoped.

Provider secrets and backend credentials are never exposed to the investigator as trace evidence.

## 16. Controlled Evaluation

Existing sample workloads provide hidden-ground-truth scenarios across:

- RAG/retrieval;
- tool-task workflows;
- research/planning workflows;
- LangGraph workflows.

Evaluation measures:

- expected suspicious-step hit;
- Recall@K where meaningful;
- evidence-reference validity;
- false positives;
- unsupported findings;
- recovered retry handling;
- retrieval-vs-reasoning failure when authority exists;
- stability across repeated runs;
- latency and cost.

Automated tests may use deterministic model stubs. Live model evaluation is measured separately.

## 17. Performance

For bounded runs, direct analysis avoids unnecessary tool orchestration.

For large runs, read-only trace tools query ClickHouse selectively to avoid sending every span/payload into one prompt.

Kafka is not part of analysis execution; it is only the ingestion buffer.

## 18. Key Analysis Decisions

| Area | Decision |
|---|---|
| Primary semantic method | one controlled LLM debugger investigator |
| Deterministic logic | structural facts + evidence grounding |
| Large runs | same investigator + bounded read-only trace/knowledge access |
| Analysis input | stable immutable snapshot |
| Trace source | ClickHouse reconstruction |
| Finding persistence | PostgreSQL |
| Knowledge source | optional PostgreSQL/pgvector project knowledge |
| Priority | High/Medium/Low investigation priority |
| Root-cause probability | not claimed |
| Multi-agent debugger swarm | not used |
| Dedicated memory service | not used |
