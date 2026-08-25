# Trace Protocol

## AI Agent Execution Debugging & Trace Analysis Platform

## 1. Purpose and Scope

The Trace Protocol defines the common execution-data contract between instrumented AI agent applications and the **AI Agent Execution Debugging & Trace Analysis Platform**.

It provides a framework-independent representation of an agent execution using **Runs and Spans**.

The protocol defines the information required to:

- identify executions and execution steps;
- represent parent-child relationships;
- preserve timing and ordering information;
- record statuses, inputs, outputs, errors, and metadata;
- support out-of-order Span arrival;
- support idempotent trace submission;
- reconstruct persisted executions.

The protocol forms the integration boundary between the Python instrumentation SDK and the debugging backend.

It does not define:

- FastAPI route structure;
- PostgreSQL table design;
- frontend response formats;
- deterministic analysis rules;
- internal SDK module behavior.

Those concerns are documented separately.

### 1.1 Protocol Scope

Protocol version 1 targets the OJT debugging workflow and primarily supports Python-based AI agents.

It can represent operations such as:

- agent or orchestration steps;
- model calls;
- retrieval operations;
- tool interactions;
- external API calls;
- meaningful state changes.

The initial execution model uses parent-child Span relationships together with timestamps and optional sequence information.

Arbitrary distributed execution graphs and production-scale telemetry semantics are outside version 1.

### 1.2 Recorded Trace vs. Analysis

The Trace Protocol represents **recorded execution information**.

Analysis findings are derived separately.

```text
Agent Execution
      ↓
Trace Protocol
      ↓
Recorded Run / Spans
      ↓
Reconstruction
      ↓
Deterministic Analysis
      ↓
Findings + Evidence
```

This keeps the original execution inspectable even when analysis rules change later.

## 2. Protocol Design Principles

### 2.1 Framework Independence

Framework-specific instrumentation should translate execution activity into the common Run/Span representation before sending it to the backend.

```text
Python Application ───────┐
LangGraph Adapter ────────┤
Future Adapter ───────────┼── Common Trace Protocol → Backend
Future SDK ────────────────┘
```

The backend therefore depends on the protocol rather than on a specific agent framework.

### 2.2 Record Facts Before Interpretation

The protocol records observable information such as:

```text
status = timeout
error.type = TimeoutError
```

It does not record unsupported conclusions such as:

```text
root_cause = retrieval_failure
```

Debugging interpretations belong to the Trace Analysis Engine.

### 2.3 Arrival Order Is Not Execution Order

Backend request arrival order is not treated as execution order.

Execution reconstruction uses:

* parent relationships;
* timestamps;
* optional sequence information.

### 2.4 Partial Traces Are Preserved

Runs may be incomplete because of crashes, network problems, instrumentation failures, or interrupted execution.

Successfully accepted trace data should remain inspectable even if the complete execution was not received.

### 2.5 Stable Core, Flexible Metadata

The protocol keeps a small stable set of common fields.

Framework-, provider-, model-, tool-, or application-specific information is represented through extensible metadata rather than continuously expanding the core schema.

## 3. Core Concepts

The protocol uses three primary concepts:

```text
Project
   ↓
Run
   ↓
Span
```

### 3.1 Project

A Project represents one AI agent integration within the hosted debugging platform.

Project association is established from authenticated integration context rather than trusted solely from payload data.

Credential and Project persistence behavior are defined outside this protocol.

### 3.2 Run

A Run represents one complete execution of an AI agent for a request, task, or workflow.

Examples include:

```text
Process one refund request
Answer one support request
Perform one research task
```

Each Run has a globally unique canonical `run_id`.

Protocol version 1 does not introduce a separate platform `trace_id`, because `run_id` already identifies the complete execution.

A Run may contain zero or more Spans and may be complete or incomplete.

### 3.3 Span

A Span represents one meaningful operation within a Run.

Examples include:

```text
Model Call
Retrieval
Tool Execution
External API Request
State Update
Agent Step
```

Each Span has a globally unique `span_id` and belongs to exactly one Run through `run_id`.

A Span may reference one optional parent using `parent_span_id`.

A Span without a parent is a root Span.

The protocol permits multiple root Spans so that partial or intentionally independent execution branches can still be represented.

### 3.4 Execution Structure

Version 1 supports one optional parent per Span.

This produces a tree or forest:

```text
Run
│
├── Retrieve Policy
└── Process Refund
    ├── Validate Order
    └── Issue Refund
```

Arbitrary graph links may be introduced in a future protocol version if real distributed or multi-agent requirements justify them.

## 4. Run Model

A Run is the top-level execution unit inspected by the debugging platform.

### 4.1 Run Fields

| Field              | Required    | Description                          |
| ------------------ | ----------- | ------------------------------------ |
| `protocol_version` | Yes         | Trace Protocol version               |
| `run_id`           | Yes         | Globally unique execution identifier |
| `name`             | No          | Human-readable execution name        |
| `status`           | Yes         | Current lifecycle status             |
| `started_at`       | Yes         | Execution start timestamp            |
| `ended_at`         | Conditional | Terminal completion timestamp        |
| `input`            | No          | Captured execution input             |
| `output`           | No          | Captured final output                |
| `error`            | No          | Structured error information         |
| `attributes`       | No          | Additional execution metadata        |

Lifecycle rules are defined in Section 7.

### 4.2 Run Identity

`run_id` is the canonical identifier for one agent execution.

Example:

```text
run_01K2M7X4N5YQ8R3J6T9P0ABCDEF
```

The identifier:

* must be globally unique;
* remains stable for the lifetime of the Run;
* is treated as opaque by protocol consumers.

The exact ID-generation algorithm is an SDK implementation decision.

### 4.3 Project Association

A Run belongs to the Project identified by the authenticated integration context.

```text
Integration Credential
        ↓
Trace Submission
        ↓
Backend identifies Project
        ↓
Stored Run
```

A client must not be able to change Project ownership merely by supplying a different Project identifier in trace payload data.

### 4.4 Run Name

`name` is an optional developer-readable execution label.

Examples:

```text
refund_request
customer_support_request
research_task
```

It is not an identity field.

### 4.5 Run Input, Output, and Attributes

`input` and `output` may contain any JSON-compatible value.

For example:

```json
{
  "input": {
    "order_id": "ORD-1042"
  },
  "output": {
    "refund_status": "completed"
  }
}
```

Capture may be reduced or omitted because of privacy, payload limits, or application requirements.

`attributes` contains optional additional metadata:

```json
{
  "attributes": {
    "agent_name": "refund-agent",
    "environment": "development",
    "agent_version": "0.3.0"
  }
}
```

Core protocol fields such as identity, status, and timestamps must remain explicit rather than being hidden inside `attributes`.

### 4.6 Example Run

```json
{
  "protocol_version": "1.0",
  "run_id": "run_01K2M7X4N5YQ8R3J6T9P0ABCDEF",
  "name": "refund_request",
  "status": "success",
  "started_at": "2026-08-25T10:20:30.123Z",
  "ended_at": "2026-08-25T10:20:34.812Z",
  "input": {
    "order_id": "ORD-1042"
  },
  "output": {
    "refund_status": "completed"
  },
  "error": null,
  "attributes": {
    "agent_name": "refund-agent",
    "environment": "development"
  }
}
```

## 5. Span Model

A Span represents one meaningful operation inside a Run.

### 5.1 Span Fields

| Field              | Required    | Description                     |
| ------------------ | ----------- | ------------------------------- |
| `protocol_version` | Yes         | Trace Protocol version          |
| `run_id`           | Yes         | Run containing the Span         |
| `span_id`          | Yes         | Globally unique Span identifier |
| `parent_span_id`   | No          | Logical parent Span identifier  |
| `name`             | Yes         | Human-readable operation name   |
| `span_type`        | Yes         | High-level operation category   |
| `status`           | Yes         | Current execution status        |
| `sequence_no`      | No          | Run-scoped ordering hint        |
| `started_at`       | Yes         | Operation start timestamp       |
| `ended_at`         | Conditional | Terminal completion timestamp   |
| `input`            | No          | Captured operation input        |
| `output`           | No          | Captured operation output       |
| `error`            | No          | Structured error information    |
| `attributes`       | No          | Additional operation metadata   |

### 5.2 Span Identity and Run Association

Every Span has a globally unique `span_id`.

Example:

```text
span_01K2M7X8TWZH6Y1E4C9B3KJQPA
```

Each Span also contains the `run_id` of the Run to which it belongs.

```json
{
  "run_id": "run_123",
  "span_id": "span_456"
}
```

Both identifiers remain stable after creation.

A Span must not be moved from one Run to another.

### 5.3 Parent Relationship

`parent_span_id` identifies the logical parent of a Span.

```text
Process Refund
│
├── Validate Order
└── Issue Refund
```

A root Span contains:

```json
{
  "parent_span_id": null
}
```

A child may arrive before its parent:

```text
1. Child Span arrives
2. Parent Span arrives
3. Reconstruction connects them
```

The parent therefore does not need to exist at ingestion time.

If the parent never arrives, the child remains recorded and the unresolved relationship is handled during reconstruction.

### 5.4 Span Name and Type

`name` is the developer-readable operation name.

Examples:

```text
retrieve_refund_policy
generate_refund_decision
issue_refund
payment_provider_request
```

`span_type` provides the broader standardized operation category.

For example:

```json
{
  "name": "issue_refund",
  "span_type": "tool"
}
```

The allowed types are defined in Section 6.

### 5.5 Sequence Information

`sequence_no` is an optional run-scoped ordering hint.

Example:

```text
1   Retrieve Policy
2   Generate Decision
3   Issue Refund
```

It supports stable reconstruction but does not establish causality or replace parent relationships and timestamps.

Detailed ordering semantics are defined in Section 9.

### 5.6 Span Payloads and Attributes

`input` and `output` contain optional JSON-compatible operation data.

```json
{
  "input": {
    "order_id": "ORD-1042",
    "amount": 1200
  },
  "output": {
    "refund_id": "REF-9821"
  }
}
```

Operation-specific metadata belongs in `attributes`.

```json
{
  "attributes": {
    "tool": {
      "name": "issue_refund"
    }
  }
}
```

Unknown valid attributes should be preserved by the backend.

### 5.7 Example Span

A timed-out tool execution may be represented as:

```json
{
  "protocol_version": "1.0",
  "run_id": "run_01K2M7X4N5YQ8R3J6T9P0ABCDEF",
  "span_id": "span_01K2M7X8TWZH6Y1E4C9B3KJQPA",
  "parent_span_id": "span_01K2M7X6N2QF7P4J5A8C9RMWXD",
  "name": "issue_refund",
  "span_type": "tool",
  "status": "timeout",
  "sequence_no": 4,
  "started_at": "2026-08-25T10:20:32.100Z",
  "ended_at": "2026-08-25T10:20:34.600Z",
  "input": {
    "order_id": "ORD-1042",
    "amount": 1200
  },
  "output": null,
  "error": {
    "type": "TimeoutError",
    "message": "Payment provider did not respond before the configured timeout"
  },
  "attributes": {
    "tool": {
      "name": "issue_refund"
    }
  }
}
```

The protocol records the timeout as an observed execution fact.

It does not add a causal conclusion such as:

```text
root_cause = payment_provider
```

Such interpretations belong to the analysis layer.

## 6. Span Types

`span_type` identifies the high-level category of operation represented by a Span.

Protocol version 1 defines:

| `span_type` | Represents |
|---|---|
| `agent` | Agent reasoning, orchestration, workflow, or logical agent-level execution |
| `model` | Interaction with an LLM or other model |
| `retrieval` | Retrieval of documents, memory, context, or similar information |
| `tool` | Invocation of an agent-visible tool or function |
| `api` | Direct interaction with an external API or service |
| `state` | Meaningful application or agent state change |
| `custom` | Operation that does not fit another standard category |

### 6.1 Agent

An `agent` Span represents a meaningful logical agent or orchestration step.

For example:

```text
Process Refund                 agent
│
├── Retrieve Refund Policy    retrieval
├── Generate Decision         model
└── Issue Refund              tool
```

Instrumentation should use agent Spans for useful execution boundaries rather than every internal function call.

### 6.2 Model

A `model` Span represents interaction with an LLM or another model.

Examples:

```text
generate_refund_decision
classify_customer_request
summarize_context
```

Provider, model, token, and generation metadata may be recorded through structured attributes defined in Section 11.

### 6.3 Retrieval

A `retrieval` Span represents information retrieval used by the agent.

Possible sources include:

* vector databases;
* document stores;
* search services;
* memory systems;
* application-specific retrieval systems.

Retrieval remains distinct from generic API activity because it is a useful debugging category for AI-agent execution.

### 6.4 Tool

A `tool` Span represents invocation of an agent-visible tool or function.

Examples:

```text
issue_refund
lookup_order
send_customer_email
```

A failed tool Span records the observed tool execution outcome. It does not by itself determine whether the underlying debugging category is tool selection, tool input, or tool execution failure.

### 6.5 API

An `api` Span represents a direct external service interaction.

For example:

```text
Issue Refund            tool
└── Payment Request     api
```

This allows the debugger to distinguish the logical tool operation from an external dependency used by that tool.

### 6.6 State

A `state` Span represents a meaningful state update or transition.

Examples:

```text
update_refund_status
store_selected_policy
set_current_workflow_step
```

Only state operations useful for execution understanding or debugging should normally be captured.

### 6.7 Custom

A `custom` Span provides an extension point for meaningful operations that do not map naturally to a standard type.

```json
{
  "name": "fraud_risk_check",
  "span_type": "custom",
  "attributes": {
    "operation_category": "risk_check"
  }
}
```

Framework-specific operations should map to a standard type where a reasonable mapping exists.

### 6.8 Span Type vs. Failure Category

`span_type` describes **what kind of operation occurred**.

It does not describe **why it failed**.

For example:

```text
span_type = tool
status = error
```

does not automatically imply:

```text
failure_category = TOOL_EXECUTION_ERROR
```

Failure categories are derived separately by the Trace Analysis Engine using recorded evidence.

## 7. Lifecycle and Status Model

Runs and Spans use a small lifecycle model describing their recorded execution outcome.

| Status      | Terminal | Meaning                                                    |
| ----------- | -------: | ---------------------------------------------------------- |
| `running`   |       No | Execution has started but has not reached a terminal state |
| `success`   |      Yes | Execution completed successfully                           |
| `error`     |      Yes | Execution ended with an explicit failure                   |
| `timeout`   |      Yes | An explicit execution timeout occurred                     |
| `cancelled` |      Yes | Execution was intentionally stopped                        |

### 7.1 Lifecycle

The allowed lifecycle is:

```text
running
   │
   ├──→ success
   ├──→ error
   ├──→ timeout
   └──→ cancelled
```

A terminal state does not transition back to `running` or to another terminal state.

The first accepted submission may already be terminal; the protocol does not require a separate `running` submission first.

### 7.2 Running Records

For:

```text
status = running
```

`started_at` is required and `ended_at` is not yet present.

Output and error information may also be absent.

A record that remains `running` because completion telemetry was never received is treated as potentially incomplete telemetry rather than automatically as an execution failure.

### 7.3 Terminal Records

For:

```text
success
error
timeout
cancelled
```

both `started_at` and `ended_at` are required, with:

```text
ended_at >= started_at
```

Duration is derived from those timestamps.

A successful record should normally have no error information.

An `error` record may contain structured error details when available.

A `timeout` status should be used only when instrumentation observed an actual timeout condition. Long execution duration alone does not prove a timeout.

`cancelled` represents intentional termination and is therefore distinct from `error`.

### 7.4 Parent and Child Statuses

Parent and child statuses are not automatically propagated.

For example:

```text
Run                         success
│
├── API Attempt 1           timeout
└── API Attempt 2           success
```

is valid if the Run recovered successfully.

Likewise, a successful child operation does not imply that its parent or overall Run must succeed.

Each status represents the outcome of its own recorded execution scope.

### 7.5 Incomplete Is Not a Status

Protocol version 1 does not define:

```text
status = incomplete
```

Incomplete telemetry describes what the debugger received, not necessarily what happened in the agent.

For example:

```text
Span = running
        ↓
Agent process stops
        ↓
No completion telemetry received
```

The stored Span remains `running`, while reconstruction may identify the trace as incomplete.

### 7.6 Status vs. Failure Taxonomy

The protocol separates:

```text
span_type
    = what operation occurred

status
    = how the recorded operation ended

failure_category
    = debugging classification derived from evidence
```

Failure taxonomy and analysis logic are defined outside the Trace Protocol.

## 8. Parent-Child Relationships

Each Span may reference one logical parent through:

```text
parent_span_id
```

A Span with no parent is a root Span.

Version 1 therefore represents execution as a tree or forest rather than an arbitrary directed graph.

### 8.1 Relationship Rules

A valid relationship follows these rules:

1. a Span has at most one direct parent;
2. parent and child logically belong to the same Run;
3. a Span must not parent itself;
4. parent relationships must not form cycles;
5. the parent does not need to arrive before the child.

For example:

```text
Process Refund
span_id = span_3
parent_span_id = null

Validate Order
span_id = span_4
parent_span_id = span_3
```

### 8.2 Multiple Roots

A Run may contain multiple root Spans:

```text
Run
│
├── Root A
│   └── Child A
│
└── Root B
    └── Child B
```

This may represent independent execution branches, partial instrumentation, or malformed structure.

The protocol does not require exactly one root Span.

### 8.3 Parent May Arrive Later

This ingestion order is valid:

```text
1. Child Span arrives
2. Parent Span arrives
```

The persistence model must therefore allow a child to be recorded before its parent exists.

If the referenced parent never arrives, the child remains inspectable and the unresolved relationship is handled during reconstruction.

### 8.4 Invalid Relationships

Examples of structurally invalid relationships include:

```text
Self-reference:

span_id = span_123
parent_span_id = span_123
```

```text
Cycle:

Span A → Span B → Span C → Span A
```

and a parent reference that resolves to a Span in another Run.

Such relationships must not cause Runs to be merged or reconstruction to loop indefinitely.

Where the individual records are otherwise valid, the original trace data should remain inspectable and structural problems should be reported separately.

### 8.5 Relationship Does Not Prove Causality

A parent-child link records logical execution structure.

For example:

```text
Process Refund
└── Payment API Request
        status = timeout
```

shows that the API request occurred within the refund operation.

It does not prove that the timeout caused the final Run outcome.

## 9. Execution Ordering

Backend request arrival order is not considered execution order.

Reconstruction uses recorded execution information instead:

1. parent-child relationships;
2. `started_at`;
3. optional `sequence_no`;
4. `span_id` as a stable final tie-breaker where necessary.

### 9.1 Timestamps

`started_at` and `ended_at` use timezone-aware timestamps, preferably RFC 3339 / ISO 8601 UTC representation.

Example:

```text
2026-08-25T10:20:32.125Z
```

Sub-second precision should be preserved when available.

For terminal operations:

```text
duration = ended_at - started_at
```

Timestamps remain authoritative; duration may be derived for API or UI convenience.

### 9.2 Sequence Number

`sequence_no` is an optional **run-scoped ordering hint** assigned by instrumentation.

Lower sequence numbers represent operations observed earlier by the instrumentation context than higher sequence numbers.

Example:

```text
1   Retrieve Policy
2   Generate Decision
3   Issue Refund
```

Sequence numbers:

* remain stable once assigned;
* do not need to be contiguous;
* may be absent;
* do not establish causality.

Concurrent operations may overlap even when their sequence numbers differ.

### 9.3 Deterministic Reconstruction Ordering

For sibling or otherwise comparable Spans, the platform may use:

```text
started_at
    ↓
sequence_no
    ↓
span_id
```

to obtain stable deterministic ordering.

`span_id` is only a tie-breaker and does not carry execution semantics.

The detailed reconstruction algorithm belongs in the LLD.

### 9.4 Arrival Order Example

An execution may occur logically as:

```text
Span A
   ↓
Span B
   ↓
Span C
```

while arriving at the backend as:

```text
1. Span C
2. Span A
3. Span B
```

The backend must not infer `C → A → B` from transport order.

### 9.5 Timing Inconsistencies

Recorded parent-child timing may occasionally appear inconsistent because of clock differences, instrumentation problems, or malformed telemetry.

Where record-level timestamp rules remain valid, such data should generally remain inspectable and may be reported as structural or analysis evidence.

The platform should not silently rewrite recorded timestamps.

### 9.6 Recorded vs. Derived Ordering

Recorded information includes:

```text
parent_span_id
started_at
ended_at
sequence_no
```

Derived information may include:

```text
reconstructed tree
display ordering
structural warnings
```

Reconstruction must not modify the original recorded ordering information.

## 10. Inputs, Outputs, Errors, and Attributes

Runs and Spans may contain:

```text
input
output
error
attributes
```

These fields provide debugging context without expanding the stable core schema for every operation type.

### 10.1 Input and Output

`input` and `output` may contain any JSON-compatible value:

```text
object
array
string
number
boolean
null
```

Example:

```json
{
  "input": {
    "order_id": "ORD-1042",
    "amount": 1200
  },
  "output": {
    "refund_id": "REF-9821"
  }
}
```

The protocol does not require complete payload capture.

A missing input or output does not automatically represent an execution failure.

### 10.2 Structured Error

`error` contains structured information about an observed failure when available.

Recommended fields are:

| Field         | Required | Description                                  |
| ------------- | -------- | -------------------------------------------- |
| `type`        | No       | Error or exception type                      |
| `message`     | No       | Human-readable description                   |
| `code`        | No       | Application- or provider-specific error code |
| `stack_trace` | No       | Captured stack information when appropriate  |
| `details`     | No       | Additional structured metadata               |

Example:

```json
{
  "error": {
    "type": "TimeoutError",
    "message": "Payment provider did not respond",
    "code": "PAYMENT_TIMEOUT",
    "stack_trace": null,
    "details": {}
  }
}
```

`status` remains the authoritative recorded execution outcome.

The presence of an error object does not itself constitute a debugging diagnosis.

### 10.3 Attributes

`attributes` is a JSON object containing extensible metadata.

Example:

```json
{
  "attributes": {
    "environment": "development",
    "tool": {
      "name": "issue_refund"
    }
  }
}
```

Core protocol concepts such as:

```text
run_id
span_id
parent_span_id
status
started_at
ended_at
sequence_no
```

must remain explicit fields rather than being hidden inside `attributes`.

Unknown valid attributes should be preserved even when the backend does not understand their semantics.

Operation-specific attribute conventions are defined in Section 11.

### 10.4 Sensitive and Large Payloads

Inputs, outputs, errors, and attributes may contain sensitive or large data.

The protocol therefore allows payload information to be omitted or reduced.

Future capture controls may include:

* truncation;
* selective capture;
* redaction;
* size limits.

Missing payload information must not automatically be interpreted as failure.

### 10.5 Recorded Payloads Remain Evidence

Captured payload data represents what instrumentation recorded.

Analysis may derive findings from that information, but it should not modify the original recorded values in a way that changes their debugging meaning.

## 11. Operation-Specific Metadata

Operation-specific information is represented through structured namespaces inside `attributes`.

These fields are optional. A Span remains valid even when provider- or framework-specific metadata is unavailable.

### 11.1 Standard Namespaces

Protocol version 1 recommends the following namespaces:

```text
attributes.model
attributes.tool
attributes.retrieval
attributes.api
attributes.state
attributes.retry
```

Framework-specific integrations may use their own namespaces, for example:

```json
{
  "attributes": {
    "langgraph": {
      "node_name": "refund_processor"
    }
  }
}
```

Unknown valid attributes should be preserved by the backend.

### 11.2 Model Metadata

A `model` Span may contain:

| Field           | Description                            |
| --------------- | -------------------------------------- |
| `provider`      | Model provider or runtime              |
| `name`          | Model identifier                       |
| `input_tokens`  | Input token count when available       |
| `output_tokens` | Output token count when available      |
| `total_tokens`  | Total token count when available       |
| `temperature`   | Generation temperature when applicable |
| `finish_reason` | Provider-reported completion reason    |

Example:

```json
{
  "attributes": {
    "model": {
      "provider": "openai",
      "name": "example-model",
      "input_tokens": 420,
      "output_tokens": 86,
      "total_tokens": 506,
      "temperature": 0.2,
      "finish_reason": "stop"
    }
  }
}
```

The protocol does not attempt to normalize every provider-specific model parameter.

### 11.3 Tool Metadata

A `tool` Span may contain:

| Field     | Description                                        |
| --------- | -------------------------------------------------- |
| `name`    | Invoked tool name                                  |
| `version` | Tool version when available                        |
| `call_id` | Framework- or agent-provided invocation identifier |

Tool arguments and results normally belong in `input` and `output` rather than being duplicated in metadata.

### 11.4 Retrieval Metadata

A `retrieval` Span may contain:

| Field          | Description                                     |
| -------------- | ----------------------------------------------- |
| `source`       | Logical retrieval source                        |
| `result_count` | Number of retrieved results                     |
| `collection`   | Collection, index, or knowledge-base name       |
| `document_ids` | Retrieved document identifiers when appropriate |

The retrieval query may be stored in `input`, while returned context or a reduced representation may be stored in `output`.

### 11.5 API Metadata

An `api` Span may contain:

| Field         | Description                         |
| ------------- | ----------------------------------- |
| `service`     | External service name               |
| `method`      | HTTP or equivalent operation method |
| `endpoint`    | Safe logical endpoint or route      |
| `status_code` | External response status            |

Instrumentation should avoid automatically recording credentials, authorization headers, or other sensitive transport data.

### 11.6 State Metadata

A `state` Span may contain:

| Field       | Description                                          |
| ----------- | ---------------------------------------------------- |
| `operation` | State operation such as `set`, `update`, or `delete` |
| `key`       | Logical state key or field                           |
| `scope`     | Application-defined state scope                      |

Only state changes useful for execution understanding or debugging should normally be captured.

### 11.7 Retry Metadata

Retries may be represented as separate Spans when each attempt is a meaningful execution operation.

Example:

```text
Payment Request - Attempt 1     timeout
Payment Request - Attempt 2     success
```

Optional retry metadata may include:

```json
{
  "attributes": {
    "retry": {
      "attempt": 2,
      "max_attempts": 3
    }
  }
}
```

For protocol version 1, `attempt` is the 1-based current attempt number and
`max_attempts` is the total number of allowed attempts, including the first attempt.

Retry information should reflect explicitly recorded application or instrumentation data.

The analysis layer should not infer a retry solely from similar Span names.

### 11.8 Metadata Is Optional Evidence

Operation-specific metadata may improve debugging and deterministic analysis, but it is not guaranteed to exist.

The system should distinguish between:

```text
Evidence exists and supports condition X
```

and:

```text
Evidence required to evaluate condition X was not captured
```

Missing metadata is not automatically a failure.

## 12. Trace Ingestion Semantics

Trace ingestion defines how Run and Span records are accepted by the hosted platform.

Exact HTTP routes, request envelopes, responses, and status codes are defined in the API and LLD documentation.

### 12.1 Authenticated Project Context

Trace submissions use a project-scoped integration credential.

```text
Python SDK
    ↓
Integration Credential
    ↓
Trace Ingestion API
    ↓
Authenticated Project
```

The backend determines Project ownership from authenticated context.

Trace payloads must not override that Project association.

### 12.2 Run Before Span

Protocol version 1 requires the Run to be accepted before Spans belonging to it.

```text
1. Submit Run
2. Submit Spans
3. Complete Run
```

A child Span may arrive before its parent Span, but the Run must already exist before any Span belonging to that Run is accepted.

This keeps the initial ingestion model simple while still supporting out-of-order Span relationships.

### 12.3 Independent Span Submission

Spans may be submitted separately as execution progresses.

The backend does not require an entire Run to finish before accepting its individual Spans.

This allows useful partial telemetry to remain available if execution is interrupted.

### 12.4 Parent Presence Is Not Required

A Span may be accepted even when its `parent_span_id` does not yet resolve.

For example:

```text
1. Child Span arrives
2. Parent Span arrives
```

is valid.

Parent relationships are validated during reconstruction.

### 12.5 Validation and Persistence

The ingestion flow is conceptually:

```text
Receive
   ↓
Validate Protocol Record
   ↓
Persist
   ↓
Acknowledge Success
```

A record should not be acknowledged as successfully accepted before its accepted state is durably persisted.

Validation includes:

* required fields;
* field types;
* supported protocol version;
* supported statuses and Span types;
* timestamp rules;
* immutable identity fields;
* correct Run association.

Structural issues such as a missing parent are not necessarily ingestion failures.

### 12.6 Analysis Is Separate From Ingestion

Successful ingestion means that valid recorded trace data was persisted.

Analysis success is not required for that ingestion to remain successful.

```text
Trace
  ↓
Validate
  ↓
Persist Recorded Data
  ↓
Accepted

Then:
Reconstruct
  ↓
Analyze
  ↓
Persist Findings
```

If analysis fails, the recorded trace remains available.

The Trace Protocol does not define when analysis is triggered; that behavior belongs to the implementation design.

### 12.7 Ingestion Failure

Authentication, protocol validation, compatibility, or persistence failure may cause a submission to be rejected.

SDK export failures should normally remain fail-open so that debugging instrumentation does not cause the agent itself to fail.

Retry behavior must remain bounded.

## 13. Idempotency and Duplicate Handling

Trace requests may be retried because the SDK cannot always know whether a previous request succeeded.

Protocol version 1 therefore supports idempotent resubmission.

The core rule is:

```text
Same identity + equivalent canonical content
        ↓
Idempotent retry

Same identity + conflicting content
        ↓
Conflict
```

### 13.1 Record Identity

A Run is identified by globally unique:

```text
run_id
```

A Span is identified by globally unique:

```text
span_id
```

Each Span additionally contains `run_id` to establish execution membership.

An identifier must not be reused for another logical execution or operation.

### 13.2 Equivalent Resubmission

Submitting the same logical record again must not create another execution step.

For example:

```text
First submission
      ↓
Stored Span

Equivalent retry
      ↓
Same stored Span
```

Equivalent terminal completion submissions are also safe idempotent retries.

### 13.3 Canonical Comparison

Equivalence should be determined from canonical protocol content rather than raw JSON bytes.

For example:

```json
{
  "span_id": "span_123",
  "status": "success"
}
```

and:

```json
{
  "status": "success",
  "span_id": "span_123"
}
```

represent equivalent field content despite serialization order.

The backend may use canonical serialization or a deterministic payload hash internally.

The exact algorithm belongs in the implementation design.

### 13.4 Conflicting Submission

A conflicting submission reuses an existing identity with incompatible execution content.

For example:

```text
Stored:
span_id = span_123
name = issue_refund

New:
span_id = span_123
name = send_email
```

The new submission must not overwrite the original record.

The backend should report a conflict while preserving the previously accepted trace data.

### 13.5 Lifecycle Updates

A valid lifecycle update is not a conflicting duplicate.

For example:

```text
running
   ↓
success
```

may add terminal information such as:

```text
ended_at
output
error
final attributes
```

when permitted by Section 15.

Once terminal, materially different content is a conflict.

### 13.6 Duplicate Handling and Analysis

Transport retries must not create duplicate stored Spans or duplicate findings.

```text
One logical Span
      ↓
One canonical stored record
      ↓
Analysis
```

Idempotency therefore protects both trace integrity and downstream analysis consistency.

## 14. Incomplete and Structurally Invalid Traces

The platform distinguishes between:

```text
Invalid protocol record
        ↓
Reject
```

and:

```text
Valid record with imperfect execution structure
        ↓
Preserve
        ↓
Report during reconstruction
```

This distinction is important because malformed structure may itself be useful debugging evidence.

### 14.1 Incomplete Execution

A Run may remain partially recorded:

```text
Run                         running
│
├── Retrieve Policy        success
├── Generate Decision      success
└── Issue Refund           running
```

If completion telemetry is never received, the accepted records remain inspectable.

Missing telemetry must not automatically be interpreted as agent failure.

### 14.2 Missing Parent

A Span whose referenced parent never arrives remains recorded.

Reconstruction may report the unresolved parent while preserving the original `parent_span_id`.

### 14.3 Multiple Roots

Multiple root Spans are valid protocol input.

They may represent:

* independent branches;
* partial instrumentation;
* missing telemetry;
* malformed execution structure.

Reconstruction may represent the result as a forest.

### 14.4 Invalid Relationships

Structural problems may include:

```text
self-parent
cycle
cross-Run parent reference
```

These relationships must not cause Runs to merge or reconstruction to loop indefinitely.

Where the individual records are otherwise valid, they should remain inspectable and the structural problem should be reported separately.

### 14.5 Timestamp Problems

A record with:

```text
ended_at < started_at
```

violates the basic lifecycle contract and should normally be rejected during protocol validation.

More contextual timing inconsistencies, such as unusual parent-child overlap, may remain recorded and be reported during reconstruction or analysis.

The platform should not silently rewrite captured timestamps.

### 14.6 Preserve Recorded Truth

Reconstruction may derive:

```text
reconstructed structure
display ordering
structural warnings
```

but must preserve the original:

```text
parent references
timestamps
statuses
```

as recorded execution evidence.

## 15. Immutability and Updates

The protocol allows active Runs and Spans to be completed later while preserving the stability of previously recorded execution facts.

### 15.1 Stable Fields

For a Run, the following fields are stable after initial acceptance:

```text
protocol_version
run_id
name
started_at
input
```

For a Span:

```text
protocol_version
run_id
span_id
parent_span_id
name
span_type
started_at
sequence_no
input
```

These fields define identity, structure, the beginning of execution, or execution input and must not be changed after initial acceptance.

### 15.2 Running Record Updates

While:

```text
status = running
```

the record may later be completed by adding or finalizing:

```text
status
ended_at
output
error
attributes
```

For example:

```text
running
started_at = T1
```

may become:

```text
success
started_at = T1
ended_at = T2
output = {...}
```

Attributes may be enriched with metadata that only becomes available after execution, such as token usage or finish information.

However, already-recorded identity, structure, input, and existing attribute values must not be silently rewritten.

Newly available metadata may be added; previously recorded facts remain stable.

### 15.3 Allowed Status Transition

Version 1 permits:

```text
running
   │
   ├──→ success
   ├──→ error
   ├──→ timeout
   └──→ cancelled
```

A terminal state cannot transition back to `running` or to another terminal status.

### 15.4 First Submission May Be Terminal

The first accepted record may already contain a terminal state.

For example:

```text
Operation executes
      ↓
SDK captures final result
      ↓
First submission = success
```

A preliminary `running` submission is not required.

### 15.5 Terminal Immutability

Once a record reaches:

```text
success
error
timeout
cancelled
```

its canonical recorded execution data becomes immutable.

Equivalent terminal resubmission is permitted for idempotency.

Materially different terminal content is treated as conflict.

### 15.6 Hosted Version 1 Trace Finalization

In the hosted version 1 implementation, terminalizing a Run marks the end of
normal Span mutation for that Run.

After Run terminalization:

- equivalent retries of already accepted records remain valid;
- new Span identities are not accepted;
- material updates to existing Spans are not accepted.

The SDK should therefore finalize the Run only after all intended Span records
have been submitted.

### 15.7 Derived Data Remains Independent

Recorded trace immutability does not prevent re-analysis.

```text
Recorded Run / Spans
        │
        ├── Analysis Version 1
        │      └── Findings
        │
        └── Analysis Version 2
               └── Findings
```

Analysis results may evolve while the original recorded execution remains unchanged.

## 16. Protocol Versioning

The Trace Protocol is versioned so SDKs and backend implementations can evolve without silently interpreting incompatible trace structures.

Every Run and Span contains:

```text
protocol_version
```

Example:

```json
{
  "protocol_version": "1.0"
}
```

### 16.1 Version Format

Protocol versions use:

```text
MAJOR.MINOR
```

For example:

```text
1.0
1.1
2.0
```

A minor version represents backward-compatible additions, such as new optional metadata conventions.

A major version represents an incompatible change to core protocol semantics, such as identity, lifecycle, or required-field behavior.

### 16.2 Compatibility

The backend validates `protocol_version` before accepting a record.

```text
Incoming Record
      ↓
Check Version
   ↙       ↘
supported  unsupported
   ↓           ↓
accept       reject clearly
```

An unsupported major version must not be silently interpreted as compatible.

Unknown fields inside supported extension points such as `attributes` do not automatically make a record incompatible.

For example:

```json
{
  "protocol_version": "1.0",
  "attributes": {
    "custom_framework": {
      "node_name": "refund_processor"
    }
  }
}
```

may remain valid even when the core backend does not understand the custom metadata.


## 17. Complete Example Trace

The following example demonstrates a successful refund Run containing retrieval, model, tool, timeout, and retry activity.

It is shown as one documentation object for readability. Actual ingestion may submit the Run and its Spans separately.

```json
{
  "run": {
    "protocol_version": "1.0",
    "run_id": "run_01K2REFUND001",
    "name": "refund_request",
    "status": "success",
    "started_at": "2026-08-25T10:20:30.000Z",
    "ended_at": "2026-08-25T10:20:36.500Z",
    "input": {
      "order_id": "ORD-1042",
      "requested_action": "refund"
    },
    "output": {
      "refund_status": "completed"
    },
    "error": null,
    "attributes": {
      "agent_name": "refund-agent",
      "environment": "development"
    }
  },

  "spans": [
    {
      "protocol_version": "1.0",
      "run_id": "run_01K2REFUND001",
      "span_id": "span_01K2REFUND001A",
      "parent_span_id": null,
      "name": "process_refund",
      "span_type": "agent",
      "status": "success",
      "sequence_no": 1,
      "started_at": "2026-08-25T10:20:30.100Z",
      "ended_at": "2026-08-25T10:20:36.400Z",
      "input": {
        "order_id": "ORD-1042"
      },
      "output": {
        "result": "refund_completed"
      },
      "error": null,
      "attributes": {}
    },

    {
      "protocol_version": "1.0",
      "run_id": "run_01K2REFUND001",
      "span_id": "span_01K2REFUND001B",
      "parent_span_id": "span_01K2REFUND001A",
      "name": "retrieve_refund_policy",
      "span_type": "retrieval",
      "status": "success",
      "sequence_no": 2,
      "started_at": "2026-08-25T10:20:30.300Z",
      "ended_at": "2026-08-25T10:20:30.800Z",
      "input": {
        "query": "refund policy for ORD-1042"
      },
      "output": {
        "document_ids": ["policy_12"]
      },
      "error": null,
      "attributes": {
        "retrieval": {
          "source": "refund-policy-index",
          "result_count": 1
        }
      }
    },

    {
      "protocol_version": "1.0",
      "run_id": "run_01K2REFUND001",
      "span_id": "span_01K2REFUND001C",
      "parent_span_id": "span_01K2REFUND001A",
      "name": "generate_refund_decision",
      "span_type": "model",
      "status": "success",
      "sequence_no": 3,
      "started_at": "2026-08-25T10:20:31.000Z",
      "ended_at": "2026-08-25T10:20:32.000Z",
      "input": {
        "order_id": "ORD-1042",
        "policy_id": "policy_12"
      },
      "output": {
        "decision": "approve_refund"
      },
      "error": null,
      "attributes": {
        "model": {
          "provider": "example-provider",
          "name": "example-model",
          "input_tokens": 310,
          "output_tokens": 42
        }
      }
    },

    {
      "protocol_version": "1.0",
      "run_id": "run_01K2REFUND001",
      "span_id": "span_01K2REFUND001D",
      "parent_span_id": "span_01K2REFUND001A",
      "name": "issue_refund_attempt_1",
      "span_type": "tool",
      "status": "timeout",
      "sequence_no": 4,
      "started_at": "2026-08-25T10:20:32.100Z",
      "ended_at": "2026-08-25T10:20:34.100Z",
      "input": {
        "order_id": "ORD-1042",
        "amount": 1200
      },
      "output": null,
      "error": {
        "type": "TimeoutError",
        "message": "Payment provider did not respond within the configured timeout",
        "code": "PAYMENT_TIMEOUT"
      },
      "attributes": {
        "tool": {
          "name": "issue_refund"
        },
        "retry": {
          "attempt": 1,
          "max_attempts": 2
        }
      }
    },

    {
      "protocol_version": "1.0",
      "run_id": "run_01K2REFUND001",
      "span_id": "span_01K2REFUND001E",
      "parent_span_id": "span_01K2REFUND001A",
      "name": "issue_refund_attempt_2",
      "span_type": "tool",
      "status": "success",
      "sequence_no": 5,
      "started_at": "2026-08-25T10:20:34.300Z",
      "ended_at": "2026-08-25T10:20:36.100Z",
      "input": {
        "order_id": "ORD-1042",
        "amount": 1200
      },
      "output": {
        "refund_id": "REF-9821"
      },
      "error": null,
      "attributes": {
        "tool": {
          "name": "issue_refund"
        },
        "retry": {
          "attempt": 2,
          "max_attempts": 2
        }
      }
    }
  ]
}
```

The reconstructed execution may appear as:

```text
Refund Request Run                         success
│
└── Process Refund                        success
    │
    ├── Retrieve Refund Policy            success
    ├── Generate Refund Decision          success
    ├── Issue Refund - Attempt 1          timeout
    └── Issue Refund - Attempt 2          success
```

The first tool attempt timed out, but the retry succeeded and the overall Run completed successfully.

The Trace Protocol records those execution facts without declaring the timed-out Span to be the root cause of the Run.

The analysis layer may separately highlight the timeout as suspicious evidence.


## 18. Validation Boundaries

Validation occurs at different stages of the trace pipeline.

```text
SDK
 ↓
Protocol Validation
 ↓
Persistence
 ↓
Reconstruction
 ↓
Analysis
```

Each layer has a different responsibility.

| Layer | Responsibility | Example |
|---|---|---|
| SDK | Help applications produce valid records | Reject unsupported status before export |
| Ingestion | Validate protocol contract | Missing `span_id`, unsupported version |
| Persistence | Preserve accepted data | Store Run and Span state |
| Reconstruction | Validate execution structure | Missing parent, cycle, cross-Run parent |
| Analysis | Produce debugging findings | Timeout, explicit failure, workflow violation |

### 18.1 Protocol-Level Rejection

Examples that should normally fail ingestion include:

```text
missing run_id
missing span_id
unsupported protocol_version
unsupported status
unsupported span_type
invalid field type
ended_at < started_at
Span references a Run that does not exist
```

The backend validates independently even when the SDK has already performed validation.

### 18.2 Structural Problems

Conditions such as:

```text
missing parent
cycle
cross-Run parent
multiple roots
unusual parent-child timing
incomplete execution
```

are generally evaluated during reconstruction rather than treated as malformed protocol payloads.

The original records remain inspectable where possible.

### 18.3 Analysis Findings

Execution conditions such as:

```text
explicit failure
timeout
supported state violation
workflow violation
invalid execution relationship
```

may become evidence-backed findings produced by the Trace Analysis Engine.

They are not part of the original Trace Protocol record.


## 19. Out-of-Scope and Future Extensions

Protocol version 1 intentionally supports the execution model required for the initial debugging platform.

The following capabilities are outside the initial protocol.

### 19.1 Arbitrary Execution Graphs

Version 1 supports one optional parent per Span and therefore produces a tree or forest.

Additional relationship types may be added later if distributed or multi-agent execution requires them.

### 19.2 Separate Event Model

Version 1 does not define a separate Event object.

Short or point-in-time operations may be represented as short-duration or effectively zero-duration Spans.

### 19.3 Separate Platform Trace ID

`run_id` is the canonical identifier for one complete execution.

Version 1 does not introduce a duplicate platform `trace_id`.

External telemetry adapters may map their own trace identifiers to platform Runs.

### 19.4 Framework and OpenTelemetry Adapters

The core protocol does not depend directly on LangChain, LangGraph, OpenTelemetry, or another tracing framework.

Future adapters may translate external execution representations into the common Run/Span model.

### 19.5 Advanced Ingestion

Future implementations may add:

- batch submission;
- asynchronous exporters;
- buffering;
- queued processing;
- Span-before-Run ingestion.

These capabilities are not required by protocol version 1.

### 19.6 Production Telemetry Controls

Future extensions may include:

- sampling;
- redaction;
- selective capture;
- payload truncation indicators;
- retention controls.

These should be introduced only when their behavior is clearly defined.

### 19.7 Replay and Counterfactual Metadata

Future replay functionality may require additional information such as model configuration, dependency versions, external-response references, side-effect classifications, or replay provenance.

Replay and counterfactual debugging are outside protocol version 1 and are documented separately.

### 19.8 Delivery Guarantee

The protocol supports:

```text
possible retries
      +
stable identifiers
      +
idempotent ingestion
```

It does not require distributed exactly-once delivery semantics.


## 20. References

Related documents define responsibilities outside the Trace Protocol.

| Document | Responsibility |
|---|---|
| [`HLD.md`](./HLD.md) | Overall architecture and component boundaries |
| [`LLD.md`](./LLD.md) | Implementation-level module and runtime behavior |
| [`database.md`](./database.md) | Persistence model |
| [`analysis-engine.md`](./analysis-engine.md) | Analysis rules, findings, evidence, and ranking |
| [`future/replay-counterfactual.md`](./future/replay-counterfactual.md) | Future replay direction |

### 20.1 Protocol Position in the System

```text
AI Agent Application
        ↓
Python Instrumentation SDK
        ↓
=============================
      TRACE PROTOCOL
 Run / Span execution contract
=============================
        ↓
Trace Ingestion API
        ↓
PostgreSQL
        ↓
Trace Reconstruction
        ↓
Deterministic Analysis
        ↓
Debugging Interface
```

The Trace Protocol is the stable execution-data boundary between instrumentation and the debugging backend.

Database representation, API implementation, analysis behavior, and UI presentation may evolve independently as long as the defined protocol semantics remain preserved.