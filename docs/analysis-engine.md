# Trace Analysis Engine

## AI Agent Execution Debugging & Trace Analysis Platform

## 1. Purpose and Scope

The Trace Analysis Engine is the deterministic debugging layer of the **AI Agent Execution Debugging & Trace Analysis Platform**.

It analyzes persisted, reconstructed Runs and Spans and produces evidence-backed findings that help developers prioritize suspicious execution steps.

```text
Recorded Run / Spans
        ↓
Trace Reconstruction
        ↓
Trace Analysis Engine
        ↓
Findings + Evidence
        ↓
Suspicious-Step Ranking
        ↓
Developer Investigation
```

The engine answers questions such as:

- Which execution steps contain objective failure signals?
- Which steps violate supported structural or known workflow conditions?
- Which suspicious steps should be investigated first?
- What evidence caused each finding?

Its output represents:

```text
suspicion + evidence
```

not guaranteed causal diagnosis.

### 1.1 Version 1 Scope

Version 1 supports:

- explicit execution failures;
- explicit timeouts;
- invalid execution relationships;
- selected retry conditions;
- selected controlled workflow checks;
- failure categorization;
- severity;
- suspicion scoring and ranking;
- structured evidence;
- persisted analysis history;
- deterministic re-analysis.

New rules should only be introduced when sufficient evidence exists to evaluate them reliably.

### 1.2 Out of Scope

Version 1 does not provide:

- probabilistic root-cause prediction;
- ML anomaly detection;
- automatic causal inference;
- generic semantic evaluation of arbitrary LLM outputs;
- automatic workflow discovery;
- replay or counterfactual execution;
- LLM-generated findings as the authoritative analysis result.

A future LLM layer may summarize deterministic findings but must not silently change them.


## 2. Design Principles

### 2.1 Evidence Before Interpretation

Every finding must be supported by recorded trace data, deterministic reconstruction output, or an explicitly applicable controlled workflow contract.

For example:

```text
Recorded:
status = timeout

Supported:
Explicit timeout observed

Unsupported:
The payment provider was definitely the root cause.
```

### 2.2 Recorded Trace Is Immutable

Analysis reads Runs and Spans but does not modify them.

```text
Recorded Trace
      ↓ read only
Analysis
      ↓
Findings
```

Findings are stored separately so analysis logic may evolve while the execution evidence remains unchanged.

### 2.3 Deterministic Behavior

Given:

```text
same immutable trace
+
same reconstructed structure
+
same analysis version
```

the engine should produce semantically equivalent findings, categories, severity values, scores, evidence, and ranking.

Generated database IDs and persistence timestamps may differ.

### 2.4 Missing Evidence Does Not Produce a Conclusion

Examples:

```text
No retry metadata
    ≠
Retry exhaustion
```

```text
No workflow contract
    ≠
Workflow violation
```

Rules skip unsupported conclusions rather than guessing.

### 2.5 Explainability

Every finding should expose:

```text
rule
suspicious Span when applicable
category
severity
score
evidence
rank
```

The engine therefore favors simple deterministic rules over opaque weighted models.

### 2.6 Conservative Structural Interpretation

Reconstruction problems such as:

```text
missing parent
self-parent
cycle
cross-Run parent
```

may become findings.

However, malformed trace structure alone does not prove that the agent suffered an orchestration failure. Generic structural findings therefore use conservative classification unless stronger evidence exists.


## 3. Analysis Boundary and Execution Model

The engine operates after trace persistence and before analysis-result persistence.

```text
Trace Ingestion
      ↓
PostgreSQL
      ↓
Load Run / Spans
      ↓
Create Analysis Run
      ↓
Trace Reconstruction
      ↓
Trace Analysis Engine
      ↓
Persist Findings
      ↓
Trace & Analysis APIs
```

### 3.1 Input

The engine consumes a reconstructed representation such as:

```text
ReconstructedTrace
├── run
├── spans_by_id
├── ordered_spans
├── children_by_parent
├── roots
└── structural_problems
```

Exact Python models belong in the LLD.

### 3.2 Output

Rules first produce finding drafts.

The engine then applies severity, scoring, and ranking.

```text
Rules
  ↓
Finding Drafts
  ↓
Severity / Scores
  ↓
Suspicious-Step Ranking
  ↓
Ranked Findings
  ↓
Persistence
```

Persistence adds database-managed fields such as:

```text
finding_id
analysis_run_id
created_at
```

`rank` is assigned by the analysis layer, not by persistence.

### 3.3 Automatic Analysis Timing

Version 1 performs finalized automatic analysis after a Run reaches:

```text
success
error
timeout
cancelled
```

Still-running traces remain inspectable but do not require finalized automatic analysis.

### 3.4 Analysis Run Lifecycle

An Analysis Run uses:

```text
running
completed
failed
```

and is created **before reconstruction begins**.

This allows reconstruction or analysis failures to be recorded as:

```text
status = failed
```

Agent Run status and Analysis Run status are independent.

For example:

```text
Agent Run      = error
Analysis Run   = completed
```

is valid.


## 4. Core Analysis Model

The engine uses four main concepts:

```text
Rule
  ↓
Finding
  ↓
Evidence
  ↓
Suspicious-Step Priority
```

### 4.1 Rule

A Rule is a deterministic check over reconstructed execution information.

Examples:

```text
explicit_failure
explicit_timeout
invalid_relationship
retry_exhausted
```

A conceptual interface is:

```python
class AnalysisRule(Protocol):
    rule_id: str

    def evaluate(
        self,
        trace: ReconstructedTrace,
    ) -> list[FindingDraft]:
        ...
```

Exact implementation belongs in the LLD.

Rules should not:

- mutate trace data;
- write directly to PostgreSQL;
- call external services;
- call an LLM;
- depend on previous Analysis Runs;
- rely on hidden mutable state.

Version 1 uses an explicit registry rather than dynamic plugin discovery.

### 4.2 Finding

A logical finding contains:

| Field | Purpose |
|---|---|
| `suspicious_span_id` | Span associated with the finding, nullable |
| `rule_id` | Stable rule identifier |
| `category` | Evidence-supported failure category |
| `severity` | Investigation importance |
| `message` | Human-readable explanation |
| `suspicion_score` | Deterministic priority score |
| `rank` | Suspicious-step rank |
| `evidence` | Machine-readable supporting observations |

A Run-level finding may use:

```text
suspicious_span_id = null
rank = null
```

### 4.3 Evidence

Evidence explains why the rule triggered.

Example:

```json
{
  "observations": [
    {
      "source": "span",
      "field": "status",
      "observed": "timeout"
    }
  ],
  "context": {
    "run_status": "success"
  }
}
```

### 4.4 Suspicious Step

A suspicious step is a Span associated with one or more findings.

It represents:

> an execution step worth investigating based on recorded evidence.

It does not represent proven causal responsibility.


## 5. Failure Taxonomy

Version 1 defines:

```text
MODEL_ERROR
RETRIEVAL_ERROR
TOOL_SELECTION_ERROR
TOOL_INPUT_ERROR
TOOL_EXECUTION_ERROR
STATE_ERROR
ORCHESTRATION_ERROR
TIMEOUT
POLICY_VIOLATION
UNKNOWN
```

Categories are derived analysis values, not Trace Protocol statuses.

### 5.1 Generic Explicit-Failure Mapping

For:

```text
status = error
```

the generic mapping is:

| `span_type` | Category |
|---|---|
| `model` | `MODEL_ERROR` |
| `retrieval` | `RETRIEVAL_ERROR` |
| `tool` | `TOOL_EXECUTION_ERROR` |
| `state` | `STATE_ERROR` |
| `agent` | `ORCHESTRATION_ERROR` |
| `api` | `UNKNOWN` |
| `custom` | `UNKNOWN` |

This identifies the scope where an explicit failure occurred.

It does not infer more specific causes.

### 5.2 Categories Requiring Additional Evidence

The following require an explicit workflow or validation contract:

```text
TOOL_SELECTION_ERROR
TOOL_INPUT_ERROR
POLICY_VIOLATION
```

A successful tool call, for example, does not reveal whether that tool should have been selected.

### 5.3 Structural Findings

Generic structural problems use:

```text
category = UNKNOWN
```

unless additional evidence supports a more specific classification.

This applies to:

```text
missing parent
self-parent
cycle
cross-Run parent
```

### 5.4 Semantic Model Errors

A successful model call does not guarantee that its output was semantically correct.

`MODEL_ERROR` may represent semantic mismatch only when a controlled workflow provides an objectively known expected result.


## 6. Severity, Suspicion Score, and Ranking

### 6.1 Severity

Version 1 uses:

```text
HIGH
MEDIUM
LOW
```

| Severity | Meaning |
|---|---|
| `HIGH` | Strong execution or controlled-contract problem |
| `MEDIUM` | Clear suspicious evidence with uncertain or recovered impact |
| `LOW` | Weaker but still useful debugging signal |

Examples:

```text
Explicit failure + unsuccessful Run
    → HIGH

Explicit failure + successful recovery
    → MEDIUM

Cycle in recorded structure
    → HIGH

Missing parent
    → MEDIUM
```

Severity is not probability.

### 6.2 Suspicion Score

Step-level findings use a deterministic score from:

```text
0–100
```

The score is an investigation-priority heuristic.

It is **not**:

```text
probability
confidence
root-cause likelihood
```

Initial scores:

| Condition | Score |
|---|---:|
| Controlled known-contract violation | 95 |
| Explicit failure | 90 |
| Explicit timeout | 90 |
| Retry exhausted | 85 |
| Serious structural problem | 80 |
| Missing parent | 70 |

Simple fixed values are preferred over opaque weighted formulas.

### 6.3 Span-Level Score

If a Span has multiple findings:

```text
span_suspicion_score =
    max(finding.suspicion_score)
```

Example:

```text
explicit_failure = 90
retry_exhausted  = 85

Span score = 90
```

Scores are not added.

### 6.4 Ranking

Suspicious Spans are ordered by:

```text
1. suspicion score descending
2. execution position ascending
3. span_id ascending
```

Execution position comes from Trace Reconstruction.

Earlier position is used only when evidence strength is tied.

All findings for the same suspicious Span may share the same rank.

Run-level findings use:

```text
rank = null
```


## 7. Initial Generic Rule Set

Version 1 starts with a deliberately small generic rule set.

| Rule | Priority | Trigger | Category | Score | Severity |
|---|---|---|---|---:|---|
| `explicit_failure` | MUST | `span.status == "error"` | By Span type | 90 | HIGH if Run unsuccessful, otherwise MEDIUM |
| `explicit_timeout` | MUST | `span.status == "timeout"` | `TIMEOUT` | 90 | HIGH if Run unsuccessful, otherwise MEDIUM |
| `invalid_relationship` | MUST | Reconstruction problem exists | `UNKNOWN` | 70 or 80 | MEDIUM or HIGH |
| `retry_exhausted` | SHOULD | Final allowed retry failed | By failed Span where supported | 85 | HIGH if Run unsuccessful, otherwise MEDIUM |

### 7.1 `explicit_failure`

Relevant evidence may include:

```text
span_id
span_type
status
error.type
error.message
error.code
```

Example:

```json
{
  "observations": [
    {
      "source": "span",
      "field": "status",
      "observed": "error"
    },
    {
      "source": "span.error",
      "field": "type",
      "observed": "ToolExecutionError"
    }
  ]
}
```

The rule states that the Span explicitly failed. It does not claim that the Span caused the Run outcome.

### 7.2 `explicit_timeout`

Trigger:

```text
span.status == "timeout"
```

A long duration alone does not trigger this rule.

```text
long duration ≠ timeout
```

`error.type = TimeoutError` may strengthen evidence but is not required when explicit timeout status exists.

### 7.3 `invalid_relationship`

Supported conditions:

| Condition | Score | Severity |
|---|---:|---|
| Missing parent | 70 | MEDIUM |
| Self-parent | 80 | HIGH |
| Cycle | 80 | HIGH |
| Cross-Run parent | 80 | HIGH |

Example evidence:

```json
{
  "relationship_problem": "missing_parent",
  "child_span_id": "span_5",
  "referenced_parent_span_id": "span_4"
}
```

Multiple roots do not automatically trigger this rule because forests are valid protocol input.

### 7.4 `retry_exhausted`

Retry metadata semantics are fixed as:

```text
attempt
    = 1-based current attempt number

max_attempts
    = total allowed attempts including the first
```

Example:

```text
attempt = 3
max_attempts = 3
```

means the third attempt is the final allowed attempt.

Trigger:

```text
attempt == max_attempts
AND
attempt >= 1
AND
status IN ("error", "timeout")
```

Invalid retry metadata such as:

```text
attempt <= 0
max_attempts <= 0
attempt > max_attempts
```

does not trigger the rule.

Retries must not be inferred from similar Span names.


## 8. Controlled Workflow Rules

Some categories require explicit knowledge of expected behavior.

These rules are enabled only for an applicable controlled profile.

```text
Generic Agent
    ↓
Generic Rules

Controlled Workflow
    ↓
Generic Rules
+
Known-Contract Rules
```

The initial controlled profile is primarily used by the refund-agent evaluation scenarios.

### 8.1 Controlled Profile

A profile may define:

```text
allowed tools
expected tool inputs
expected retrieval results
required state transitions
workflow constraints
policy constraints
expected structured decisions
```

Profiles may remain repository-defined for version 1.

### 8.2 Initial Controlled Rules

| Rule | Example Condition | Category | Score | Severity |
|---|---|---|---:|---|
| `controlled_tool_input_violation` | Tool input violates known constraint | `TOOL_INPUT_ERROR` | 95 | HIGH |
| `controlled_tool_selection_violation` | Wrong tool selected for known state | `TOOL_SELECTION_ERROR` | 95 | HIGH |
| `controlled_retrieval_mismatch` | Wrong known policy/document retrieved | `RETRIEVAL_ERROR` | 95 | HIGH |
| `controlled_state_violation` | Known state invariant/transition violated | Fixed by rule | 95 | HIGH |
| `controlled_policy_violation` | Explicit application policy violated | `POLICY_VIOLATION` | 95 | HIGH |
| Controlled model-output mismatch | Structured model result differs from known expected result | `MODEL_ERROR` | 95 | HIGH |

Example:

```text
Expected:
request_manual_review

Observed:
issue_refund
```

may trigger:

```text
controlled_tool_selection_violation
```

even if the selected tool itself successfully executes.

Controlled rules must not be applied when the expected behavior is unknown.


## 9. Evidence Model

Evidence is stored as structured derived data.

### 9.1 Requirements

Evidence should be:

- machine-readable;
- derived from trace data, reconstruction, or the applicable controlled profile;
- sufficient to explain the trigger;
- limited to relevant information;
- deterministic for the same trace and analysis version.

### 9.2 Source Examples

```text
run.status
span.status
span.error.type
span.attributes.retry.attempt
span.attributes.retry.max_attempts
reconstruction.missing_parent
reconstruction.cycle
controlled_profile.expected_tool
controlled_profile.expected_value
```

### 9.3 Recommended Shape

```json
{
  "observations": [
    {
      "source": "span",
      "field": "status",
      "observed": "timeout"
    }
  ],
  "related_span_ids": [],
  "context": {
    "run_status": "success"
  }
}
```

### 9.4 Avoid Duplicating Complete Payloads

Prefer:

```json
{
  "observed_status": "timeout",
  "error_type": "TimeoutError"
}
```

over copying a complete model or tool payload into every finding.

The full Span remains available through trace APIs.

Sensitive information should only be duplicated into evidence when required for the rule.


## 10. Engine Execution Flow

One finalized automatic analysis follows:

```text
Terminal persisted Run
        ↓
Load Run / Spans
        ↓
Create Analysis Run
status = running
        ↓
Reconstruct Trace
        ↓
Execute Generic Rules
        ↓
Execute Applicable Controlled Rules
        ↓
Collect Finding Drafts
        ↓
Assign Severity / Scores
        ↓
Rank Suspicious Spans
        ↓
Assign Finding Ranks
        ↓
Persist Findings
        ↓
Analysis Run = completed
```

If reconstruction, rule execution, ranking, or persistence fails unexpectedly:

```text
Analysis Run = failed
```

The recorded trace remains unchanged.

### 10.1 Rule Independence

Enabled rules receive the same reconstructed trace.

Rule results must not depend on side effects from previously executed rules.

### 10.2 Rank After Rule Collection

All finding drafts are collected before ranking.

```text
Findings
   ↓
Group by suspicious Span
   ↓
Calculate Span score
   ↓
Rank Spans
   ↓
Assign finding ranks
```

Therefore, registry order does not determine investigation rank.

### 10.3 No Automatic Causal Merge

Version 1 does not transform:

```text
Retrieval finding
+
Model finding
+
Tool finding
```

into a guaranteed causal chain.

The developer uses trace structure and evidence to make the final causal judgment.

### 10.4 Stable Presentation Order

Findings may be presented using:

```text
rank
↓
suspicion_score descending
↓
rule_id
↓
suspicious_span_id
```

with Run-level findings handled separately.


## 11. Incomplete Traces and Timing

Analysis must distinguish execution failure from incomplete telemetry.

### 11.1 Running Records

A Span remaining:

```text
status = running
```

does not automatically imply:

```text
error
timeout
```

Missing completion telemetry is different from observed failure.

### 11.2 Missing Parent

An unresolved parent may produce an `invalid_relationship` finding.

This indicates a structural issue, not necessarily application failure.

### 11.3 Multiple Roots

Multiple roots are allowed by the Trace Protocol and do not automatically produce findings.

### 11.4 Running Span in a Terminal Run

A terminal Run may contain a Span that remains `running` because completion telemetry was lost.

Version 1 may expose this as incomplete reconstruction information without classifying it as an application failure.

### 11.5 Latency

Recorded duration may be calculated from timestamps.

However:

```text
long duration ≠ timeout
```

Only explicit:

```text
status = timeout
```

triggers `explicit_timeout`.

Future rules may introduce configured latency thresholds, but such findings should mean:

```text
high latency observed
```

not timeout unless explicitly recorded.


## 12. Analysis Versioning and Persistence

Every Analysis Run records:

```text
analysis_version
```

A version represents behavior such as:

```text
enabled rules
rule semantics
category mappings
severity behavior
scores
ranking logic
controlled-profile semantics
```

A simple:

```text
MAJOR.MINOR
```

scheme is sufficient for version 1.

### 12.1 Re-Analysis

New analysis behavior creates a new Analysis Run:

```text
Recorded Trace
    │
    ├── Analysis 1.0
    │      └── Findings
    │
    └── Analysis 1.1
           └── Findings
```

Historical findings are preserved.

### 12.2 Persistence Boundary

```text
Reconstructed Trace
        ↓
Rules
        ↓
Finding Drafts
        ↓
Scoring / Ranking
        ↓
Analysis Service
        ↓
Repository
        ↓
PostgreSQL
```

Rules remain independent from database persistence.

### 12.3 Completion

An Analysis Run becomes:

```text
completed
```

only after required findings have been successfully persisted.

Unexpected reconstruction, rule, ranking, or persistence failure results in:

```text
failed
```

with diagnostic information optionally stored in:

```text
analysis_runs.error
```

Version 1 does not report an unknown partial rule execution as fully completed.


## 13. Controlled Evaluation

The refund sample agent provides deliberately injected failures with known ground truth.

Ground truth remains separate from analysis input.

```text
Controlled Scenario
├── execution configuration
├── injected failure
└── expected findings
        ↑
     evaluator only
```

The engine receives:

```text
recorded trace
+
reconstructed structure
+
applicable profile
```

but never the expected findings.

### 13.1 Example

```json
{
  "scenario_id": "wrong-refund-tool-input",
  "expected_findings": [
    {
      "rule_id": "controlled_tool_input_violation",
      "category": "TOOL_INPUT_ERROR",
      "span_role": "issue_refund"
    }
  ]
}
```

### 13.2 Evaluation Checks

Evaluation may measure:

- expected rule triggered;
- expected suspicious Span identified;
- expected category produced;
- expected findings missing;
- unexpected findings produced;
- ranking correctness;
- repeated same-version determinism.

These results describe controlled scenarios and should not automatically be presented as universal root-cause accuracy.

### 13.3 Similar Symptoms, Different Internal Failures

Useful scenarios include:

```text
Wrong retrieval
      ↓
Incorrect final outcome
```

```text
Correct retrieval
Wrong model decision
      ↓
Incorrect final outcome
```

```text
Correct decision
Wrong tool input
      ↓
Incorrect final outcome
```

The engine should surface different suspicious steps based on the recorded evidence.


## 14. Runtime Behavior and Performance

### 14.1 Rule Failure

An unexpected rule exception may fail the Analysis Run.

The recorded trace remains inspectable.

Missing optional metadata should normally cause only the affected rule to skip evaluation.

### 14.2 Unknown Classification

When evidence cannot support a specific category:

```text
UNKNOWN
```

is preferred over an invented explanation.

### 14.3 Safe Structural Input

Reconstruction provides cycle-safe structural-problem information.

Rules consume that representation rather than recursively traversing malformed relationships themselves.

### 14.4 Analyze In Memory

For one Analysis Run:

```text
Load once
   ↓
Reconstruct once
   ↓
Evaluate rules in memory
```

The engine should avoid database queries per rule per Span.

Most initial rules should operate approximately in:

```text
O(number of spans + relationships)
```

### 14.5 No Worker Infrastructure Required

Version 1 does not require:

```text
Celery
Kafka
RabbitMQ
distributed workers
```

Analysis may execute synchronously inside the FastAPI modular monolith.

Execution strategy can evolve later if measurements justify it.


## 15. Extensibility

A new deterministic rule should define:

```text
rule_id
trigger
required evidence
category behavior
severity behavior
suspicion score
message
tests
analysis-version impact
```

New categories should only be introduced when they represent a meaningful evidence-backed debugging distinction.

Generic rules should operate on the common Trace Protocol rather than depend on LangChain, LangGraph, or another framework.

Framework-specific metadata may be used when explicitly available.

### 15.1 Future LLM Explanation

A future explanation layer may consume:

```text
Finding
+
Evidence
+
selected trace context
```

but must not silently modify:

```text
rule_id
category
severity
suspicion_score
rank
```

### 15.2 Future Analysis Methods

Possible future work includes:

- richer controlled workflow validation;
- configurable latency thresholds;
- cross-Span dependency analysis;
- broader framework metadata;
- additional controlled profiles;
- calibrated statistical methods if sufficient evaluation data exists.


## 16. Out of Scope

Version 1 excludes:

- probabilistic root-cause prediction;
- ML anomaly detection;
- generic semantic correctness evaluation;
- automatic workflow discovery;
- full causal propagation proof;
- replay and counterfactual analysis;
- arbitrary user-written executable rules.

These features may be explored later without changing the core version 1 contract.


## 17. Key Analysis Decisions

| Decision | Version 1 Choice |
|---|---|
| Primary method | Deterministic rules |
| Input | Persisted reconstructed trace |
| Trace mutation | Never |
| Finalized automatic analysis | Terminal Runs |
| Execution | Synchronous, in-process |
| Analysis Run creation | Before reconstruction |
| Rule registry | Explicit |
| Rule behavior | Pure where practical |
| Missing evidence | Do not infer |
| Structural category | `UNKNOWN` unless stronger evidence exists |
| Timeout | Explicit `status = timeout` |
| Long latency as timeout | Not allowed |
| Retry numbering | 1-based |
| `max_attempts` | Total attempts including first |
| Finding output | Suspicion + evidence |
| Root-cause guarantee | Not claimed |
| Severity | HIGH / MEDIUM / LOW |
| Suspicion score | Deterministic 0–100 heuristic |
| Score as probability | Not allowed |
| Span aggregation | Maximum finding score |
| Ranking | Score → execution position → `span_id` |
| Finding rank ownership | Analysis layer |
| Run-level finding rank | `null` |
| Re-analysis | New Analysis Run |
| Historical findings | Preserved |
| Controlled rules | Require explicit contract |
| LLM diagnosis | Not authoritative |
| ML anomaly detection | Out of scope |
| Replay | Future |


## 18. Initial Delivery Priority

Implementation order:

```text
1. Finding and evidence models
2. Rule interface and registry
3. explicit_failure
4. explicit_timeout
5. invalid_relationship
6. severity and suspicion scoring
7. suspicious-step ranking
8. Analysis Run / Finding persistence
9. retry_exhausted
10. selected controlled workflow rules
11. controlled evaluation
```

The first eight items form the protected core.

```text
Persisted Trace
      ↓
Reconstruction
      ↓
Deterministic Rules
      ↓
Evidence
      ↓
Ranking
      ↓
Persisted Findings
      ↓
Debugging UI
```

A small complete engine is preferable to a large partially implemented rule system.


## 19. References

| Document | Responsibility |
|---|---|
| [`HLD.md`](./HLD.md) | Overall architecture and analysis boundary |
| [`trace-protocol.md`](./trace-protocol.md) | Recorded Run/Span contract |
| [`database.md`](./database.md) | Analysis persistence |
| [`LLD.md`](./LLD.md) | Modules, classes, service flow, and algorithms |
| [`future/replay-counterfactual.md`](./future/replay-counterfactual.md) | Future replay work |

### 19.1 Analysis Engine Position

```text
AI Agent
   ↓
Instrumentation SDK
   ↓
Trace Ingestion
   ↓
PostgreSQL
   ↓
Trace Reconstruction
   ↓
============================
    TRACE ANALYSIS ENGINE
----------------------------
Deterministic Rules
Categories
Severity
Suspicion Scores
Ranking
Evidence
============================
   ↓
Analysis Runs / Findings
   ↓
Debugging Interface
   ↓
Developer Investigation
```

The engine follows:

```text
Recorded Fact
      ↓
Deterministic Rule
      ↓
Evidence-Backed Finding
      ↓
Suspicious-Step Priority
```

without converting heuristic suspicion into unsupported causal certainty.