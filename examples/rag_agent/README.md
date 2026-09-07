# NovaCloud Controlled RAG Support Agent

NovaCloud is a fictional SaaS workspace platform. This standalone sample answers
support questions using ten small local Markdown documents. It supplies repeatable
application behavior for later testing of the AI Agent Execution Debugging & Trace
Analysis Platform.

Task 1 implements **controlled mode only**: a deterministic model test double and
local lexical retrieval. Execution needs no internet, API credentials, debugger,
database, or running service. Installing dependencies initially needs a package
index or an existing offline wheel cache.

## Install and run

Requires Python 3.10 or newer. From the repository root on Windows PowerShell:

```powershell
cd examples/rag_agent
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e '.[test]'
.\.venv\Scripts\python.exe -m rag_agent run RAG-01
.\.venv\Scripts\python.exe -m rag_agent run RAG-07 --json
.\.venv\Scripts\python.exe -m pytest -q
```

On Linux/macOS, use `python3 -m venv .venv` and `.venv/bin/python` for the subsequent
commands. With the environment active, the equivalent entry points are
`python -m rag_agent run RAG-01` and `novacloud-rag run RAG-01`.

The human-readable CLI shows each query, retrieved documents, accumulated evidence
sufficiency, missing facts, and the final answer/status. `--json` outputs the full
`AgentResult`, including document contents and retrieval attempts. A deliberately
faulty scenario is still a successful CLI execution; malformed input or missing
files return a nonzero exit code. The CLI does not score outcomes against labels.

## Architecture

```text
Runtime YAML -> factory -> controlled model + wrapped local retriever -> RAGAgent

classify_question
  -> formulate_query
  -> search knowledge base
  -> assess accumulated evidence
  -> if insufficient: refine_query -> search -> assess accumulated evidence
  -> generate_answer (answer or abstention)
```

- `RAGAgent` owns this bounded workflow, with at most two retrieval attempts and
  exactly one generation call. It receives only model/retrieval dependencies and
  the attempt limit. Documents accumulate by ID in first-seen order.
- `ModelClient` and `Retriever` are small typing protocols. Their asynchronous
  methods provide the future wrapping boundaries; controlled implementations do
  their work locally and need no async test plugin.
- `KnowledgeBase` loads Markdown front matter and validates documents, unique IDs,
  and replacement references. It contains no model or ranking logic.
- `LocalRetriever` uses BM25 with `k1=1.5`, `b=0.75`, basic token normalization,
  positive-score filtering, and a default Top-K of three. Document IDs break score
  ties. Only current documents enter its index; KB-02 is always excluded.
- `ScenarioAwareRetriever` replaces a specified attempt with exactly the supplied
  documents, in configured order. These results have score `0.0` to indicate they
  were injected rather than ranked; exact replacement takes precedence over Top-K.
- `ControlledModelClient` classifies the supported question shapes, assesses facts
  from supplied document IDs, and produces deterministic answers from its small
  semantic catalog. It never receives a scenario ID or evaluation labels.
- `factory.build_agent()` is the construction point and validates referenced IDs
  before splitting retrieval replacements from generation overrides.

Retrieval receives an explicit per-run `attempt_number`. Generation invocation
numbers are also per run: this workflow reaches only invocation 1. There are no
consumable cross-run counters, so repeated and concurrent use of the same agent
preserves the same configured behavior.

The normal initial query addresses the first required fact. Refinement uses the
missing facts, so the combined downgrade/export question naturally searches for
plan changes first and export link validity second. Sufficiency after that retry
uses documents from both searches.
For missing data-residency evidence, refinement changes the initial storage-region
query to an official hosting-location and residency-policy query.

## Seven controlled scenarios

| Scenario | Configuration and expected application behavior |
| --- | --- |
| RAG-01 | No overrides. Current workspace policy supports a 14-day answer. |
| RAG-02 | Replace both retrieval attempts with KB-03 (file Trash policy). Workspace restoration remains unsupported, so the agent abstains. Retrieval is faulty even though the downstream abstention is appropriate. |
| RAG-03 | Replace the first retrieval with superseded KB-02. Normal assessment and generation use that supplied evidence and answer 30 days. No generation override. |
| RAG-04 | Normal current evidence says 14 days; override final generation to say 30 days while citing KB-01. |
| RAG-05 | No overrides. No India data-residency evidence exists; two searches lead to abstention. |
| RAG-06 | Normal retrieval and assessment remain insufficient; override only final generation to assert India-only storage, with no invented supporting document. |
| RAG-07 | No overrides. Retry obtains export information and combines it with plan-change evidence: downgrade at the next billing renewal, export link valid for 48 hours. |

KB-01 concerns deleted **workspaces**, with a current 14-day policy. KB-02 is the
superseded 30-day workspace policy. KB-03 concerns deleted **files and folders**,
with a current 30-day Trash policy. These distinctions are deliberate.

## Runtime configuration and evaluation labels

```text
src/rag_agent/
  agent.py, models.py, model_client.py, controlled_model.py
  knowledge_base.py, retrieval.py, scenarios.py, factory.py, cli.py, yaml_io.py
  data/
    knowledge_base/    # 10 Markdown documents
    scenarios/         # 7 runtime YAML files
ground_truth/          # 7 evaluation label files, never loaded by runtime
tests/
```

Runtime assets live inside the Python package so installed wheels work from any
working directory. Ground truth stays outside the runtime package and wheel.

Runtime YAML permits only schema version 1, scenario ID, question, retrieval
overrides, and model overrides. Unknown fields are forbidden at every structured
level. Invalid attempt numbers, duplicate overrides, invalid model outputs,
unknown document references, and duplicate YAML mapping keys are rejected.

Only `generate_answer` has model overrides in Task 1. A configured invocation must
be exactly the integer 1; other values are rejected during scenario validation.
Retrieval replacement attempts must be 1 or 2 and cannot have an empty document
list. Runtime input cannot contain `expected_outcome`, `expected_failure`,
`failure_origin`, or other evaluation fields.

Ground truth describes correct facts, expected faulty behavior, important sources,
and the operation worth investigating. `expected_status` describes the status
produced by the controlled scenario, which can differ from its `expected_outcome`:
an `answered` result can be wrong, and RAG-02's abstention follows failed retrieval.
Only tests read these labels; there is no runtime ground-truth loader or automatic
evaluation command.
The evaluation-only schema in `tests/ground_truth_schema.py` validates label fields,
fact types, failure structure, document IDs, and duplicate YAML keys. It stays
outside the runtime package and wheel.

Failures enter at actual dependency boundaries so the same orchestration exposes
different intermediate causes. This permits future investigation of an execution
without teaching the agent which scenario is supposed to fail.

## Verification

The full suite covers document/catalog consistency, deterministic ranking,
superseded exclusion, strict YAML validation, per-scenario intermediate behavior,
retrieval bounds, dependency error propagation, CLI execution from another working
directory, and architecture isolation.

Determinism tests compare entire domain results across fresh instances, repeated
use, and concurrent use. The offline test removes API-key/token environment values
and blocks socket connection/DNS/send-to calls while every scenario executes.
This is a programmatic network-denial check; it does not change the host network.

```powershell
.\.venv\Scripts\python.exe -m pytest -q
1..7 | ForEach-Object {
    .\.venv\Scripts\python.exe -m rag_agent run ('RAG-{0:00}' -f $_)
}
```

## Limitations and deferred work

Classification supports the specified workspace restoration, India residency, and
downgrade/export question shapes. It is a deterministic LLM test double, not a
general language model. Unknown questions abstain. The semantic catalog duplicates
selected KB facts; consistency tests must stay green when these documents change.
Evidence sufficiency tests fact coverage, not freshness or truth: this deliberately
allows RAG-03 to expose the outdated-retrieval failure. The catalog trusts document
IDs from the controlled corpus; it is not a general document interpreter.

Lexical retrieval and the small fact catalog target this inspectable workload.
There are no embeddings, vector services, autonomous loops, conversation memory,
confidence percentages, or causal-proof claims. Execution context contains only
application domain data, with no debugger Run/Span/Trace types.

**Live LLM mode is not implemented in Task 1.** Debugger SDK instrumentation will
be added later. Backend integration and evaluation against debugger findings also
remain deferred. Replay and counterfactual debugging are not current behavior.
