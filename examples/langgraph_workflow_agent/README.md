# LangGraph Workflow Agent

Standalone, deterministic Beacon incident-remediation workload. LangGraph runs
the nodes, conditional edges, state merges and loops. There is no real model,
network operation, debugger SDK, database, or persistent service state.

## Install and run

From this directory, using Python 3.10 or newer:

```console
python -m venv .venv
.venv\Scripts\activate
python -m pip install -e ".[test]"
python -m langgraph_workflow_agent run LG-01
python -m langgraph_workflow_agent run LG-01 --json
```

Use `source .venv/bin/activate` on POSIX. Installation needs the dependencies
available from a package index or local cache; execution and tests are offline
and credential-free. Dependencies are LangGraph 1.0.x and Pydantic 2.x.
`langchain-core`, LangGraph's SDK/checkpoint/prebuilt packages and LangSmith are
transitive framework requirements. The `langchain` meta-package is not used.
`run()` disables ambient LangSmith tracing with a per-call context so environment
tracing flags do not cause network activity or mutate process-wide settings.

The CLI returns zero for an executed controlled scenario, even when that
scenario intentionally fails or reaches the recursion ceiling. Configuration
errors return one; argument errors return two. Inspect `execution_error`, graph
state and response separately. An early END may leave `final_status="running"`.

## Graph and domain

```text
START -> classify -> gather_context -> evaluate
                         ^             |  |  |
                         |             |  |  +-> abort ---------+
                         +-- retry_context |                    |
                              |            +-> execute_action --+
                 terminal retry guard                           |
                              +---------------------> validate <-+
                                                        |
                                                     respond -> END
```

Restart resolves `worker_stalled`; failover resolves `host_unavailable`.
`ready` telemetry succeeds immediately, `delayed` succeeds on acquisition two,
`denied` is terminal, and `unavailable` stays retryable. The normal policy allows
two retries, then aborts. The independent LangGraph recursion ceiling is 18 node
executions and bounds LG-08's intentionally broken routing policy.

`classify` and `evaluate` use conditional edges. Controlled routing overrides
may skip context acquisition or select END; these destinations are explicitly
declared in the graph. `retry_context` checks terminal denials before retrying.
`execute_action` and `abort` both flow through `validate`, then `respond`.

## State and output

`GraphState` is an explicit `TypedDict` containing `request`, `classification`,
`context`, `retry_count`, `selected_action`, `next_node`, `action_result`,
`validation`, `final_status`, and `response`. Nested request/context/action/
response values use strict Pydantic models. Context revisions are deterministic
acquisition numbers; action results retain the revision actually used.

Nodes return partial updates; LangGraph's default state semantics overwrite
only the supplied fields. `next_node` holds the most recent routing decision,
and becomes `__end__` when `respond` runs. No reducers, checkpoints, clocks,
randomness, thread IDs, spans or trace structures are needed.

JSON includes `path`, native LangGraph `updates`, the last native streamed
`state`, and `execution_error`. Path names are derived from update keys, not a
manually maintained in-graph log. START/END are not node updates and are omitted
from `path`. A recursion error preserves the last emitted graph state and does
not synthesize a successful answer or pretend that validation executed.

## Scenarios and injection boundaries

The pre-implementation [scenario specification](SCENARIOS.md) describes all ten
requests, injections, observed paths, outcomes, categories and suspicious nodes.
LG-01 and LG-02 are healthy primary and retry/recovery references. Four faults
are caught by workflow validation, one by the framework ceiling, and three
survive as incorrect terminal results.

Runtime JSON lives in `src/langgraph_workflow_agent/data/scenarios/`. Strict
schemas reject unknown fields, invalid targets/types, duplicate JSON keys,
nonstandard JSON constants, duplicate override coordinates and overlapping
wildcard/attempt routing overrides. Config files and IDs must agree.

`build_agent()` copies and validates configuration, passing only prepared
dependencies and node wrappers into the graph. Scenario IDs remain loader
labels. There are three bounded injection surfaces:

- Routing dependency overrides select an allowed edge at a source/attempt, or
  every attempt when omitted. Attempts are context-acquisition numbers.
- Context dependency overrides replace the response at a specific acquisition.
- The execute-action node wrapper drops its result update *after* calling the
  real node; the response dependency can independently replace final wording
  and status.

Normal graph/dependency code has no scenario IDs, evaluation labels or imports
of scenario configuration. Dependencies use no mutable attempt counters, so
one compiled agent supports repeat and concurrent runs without shared state.
Overrides are structurally checked; a configured coordinate need not be
reachable for arbitrary combinations. Tests prove the supplied faults execute
and that removing them restores each request's normal outcome.

Evaluation-only `ground_truth/LG-*.json` files contain expected paths, ideal and
observed statuses, retries, validation issues, action results and detection
operations. Their strict schema lives in `tests/ground_truth_schema.py`.
Runtime never reads these files; neither tests nor ground truth enter the wheel.

## Verification

```console
python -m pytest -q
python -m ruff check src tests
python -m ruff format --check src tests
python -m pip check
python -m pip wheel . --no-deps --no-build-isolation -w dist
```

If Windows prevents access to pytest's default temporary directory, add
`--basetemp=.venv/test-temp` to pytest. Packaging tests require pip, setuptools
and wheel already installed; they use `PIP_NO_INDEX=1` and build without an
isolated build environment. They inspect wheel members/metadata, install to a
fresh target and execute all ten module CLIs under `python -I` from outside the
source tree, denying network and source/evaluation reads. Installed results
must exactly match source results; dependencies come from the test interpreter.

Tests cover graph construction, branch policy, state propagation, retry bounds,
all outcomes, strict schemas, injection removal, repeated and concurrent runs,
isolation, CLI errors, and wheel execution.

## Deliberate boundaries

Validation checks structural state consistency; it does not second-guess an
unjustified abort (LG-03), run after early END (LG-09), or inspect a later
response (LG-10). Stale state is detected after a simulated action (LG-05).
These are evaluation cases, not claims of a safe production remediator.
Action execution records a deterministic result only; it changes no real
service or filesystem. Unexpected dependency exceptions propagate; only
`GraphRecursionError` is converted to a bounded execution-error result.

No debugger architecture, instrumentation, external services or production
workflow infrastructure are included.

Framework API references: [StateGraph and state semantics](https://docs.langchain.com/oss/python/langgraph/graph-api),
[native updates/values streaming](https://docs.langchain.com/oss/python/langgraph/streaming).
