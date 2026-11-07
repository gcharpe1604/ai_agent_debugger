# LangGraph Workflow Agent

## Platform integration

Both `ask` and `run SCENARIO` entry points send spans from actual execution through the local debugger SDK to FastAPI at `127.0.0.1:8008` by default. `ask` calls the configured live model; `run` retains the existing controlled workload and is explicitly marked `controlled` (its deterministic methods are not labeled model/API calls). React reads received spans, with no seeded telemetry or log replay. Set `AGENT_DEBUGGER_ENDPOINT` to override the loopback endpoint, or set it to an empty string to disable export. [Normal backend/frontend and uv commands](../../docs/local-development.md).

From this agent directory, use `uv sync --locked` and `uv run --locked python -m langgraph_workflow_agent ask "<your request>"`. The SDK source is declared in `tool.uv.sources`; a standalone pip install also requires installing the repository SDK first. Add `--extra test` to uv when deliberately running the test tools described below.

The earlier domain-workload documentation follows. Model calls are live; the existing tools/evidence remain local.

Standalone Beacon incident-remediation workload with deterministic controlled
mode and optional live semantic decisions. LangGraph runs the same nodes,
conditional edges, state merges and loops in both modes. Context collection and
actions remain local simulations; there is no database or
persistent service state.

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
available from a package index or local cache; controlled execution and tests are offline
and credential-free. Dependencies are LangGraph 1.0.x and Pydantic 2.x.
`langchain-core`, LangGraph's SDK/checkpoint/prebuilt packages and LangSmith are
transitive framework requirements. The `langchain` meta-package is not used.
`run()` disables ambient LangSmith tracing with a per-call context so environment
tracing flags do not cause network activity or mutate process-wide settings.

## Live mode

Copy `.env.example` to `.env` and supply a key and model, or set shell variables.
The nearest `.env` found from the working directory upwards is loaded only for
`ask`; shell values take precedence, including empty values (which fail validation).

```console
python -m langgraph_workflow_agent ask "Beacon has a stalled worker" --json
python -m langgraph_workflow_agent ask "Beacon host is unavailable; telemetry is delayed"
```

| Variable | Meaning |
|---|---|
| `LANGGRAPH_AGENT_API_KEY` | Required bearer token; never printed by CLI errors. |
| `LANGGRAPH_AGENT_MODEL` | Required model supporting Chat Completions and JSON-object output. |
| `LANGGRAPH_AGENT_BASE_URL` | Default `https://api.openai.com/v1`; `/chat/completions` is appended. HTTPS required except loopback HTTP; credentials/query/fragment prohibited. |
| `LANGGRAPH_AGENT_TIMEOUT_SECONDS` | Finite number greater than zero and at most 120; default 30. Applies to HTTPX connect/read/write/pool timeouts, not a total wall-clock deadline. |

`LiveModelClient` replaces only semantic dependency methods. Before entering the
graph, `parse_request` maps free text to the existing strict `Request` model; an
unsupported or ambiguous request is an error. Graph state holds this normalized
request, while the live result preserves the original prose so normalization
remains inspectable. The existing `classify` node copies the normalized incident.
The LLM chooses a remediation action inside `evaluate` only after the inherited
Python policy permits execution, then generates the response inside `respond`.
Action choice must match incident policy and response status must match final
state; violations consume the one structured repair or raise an output error.
Natural-language response wording is model-generated, not mechanically verified.

The graph, state model, local telemetry/action methods, retry limits, routing and
validator are unchanged. `denied` telemetry aborts without asking a model to
authorize retries; `unavailable` exhausts exactly two local retries. `delayed`
recovers on the second acquisition. These are explicitly requested simulation
conditions, not real telemetry. There is no separate live graph or new node.

One private helper sends JSON-object requests with the domain schema in the
system instruction, then strictly validates JSON/Pydantic output and consistency.
Duplicate output keys are rejected. It requests no chain of thought. Each stage
has at most one output repair and one HTTP retry shared across initial/repair
requests for `429/500/502/503/504`, with a fixed 0.25-second delay: at most **three
HTTP requests per stage**, nine for a resolved run or six for a normal abort.
Refusals, other HTTP statuses, timeouts and network errors are not retried or
converted into domain aborts. Errors exit the CLI with code one and no success
JSON. Redirects are disabled; the CLI closes its HTTPX client on success/error.

Live mode never imports or reads scenario configuration or evaluation manifests.
There is no implicit fallback to RAG credentials. For Gemini, set these same four
variables to your Gemini configuration and use its
[OpenAI-compatible endpoint](https://ai.google.dev/gemini-api/docs/openai).
HTTPX and python-dotenv are declared runtime dependencies; no provider SDK or
LangChain model wrapper is added.

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
isolation, CLI errors, and wheel execution. Live tests use HTTPX MockTransport
and cover primary/recovery paths, repair/retry bounds, errors, configuration,
`.env` precedence, and isolation. Stored pre-live CLI-output hashes guard all ten
controlled scenarios against any JSON change. Packaging tests also verify the
installed live module imports from the isolated wheel target.

## Deliberate boundaries

Validation checks structural state consistency; it does not second-guess an
unjustified abort (LG-03), run after early END (LG-09), or inspect a later
response (LG-10). Stale state is detected after a simulated action (LG-05).
These are evaluation cases, not claims of a safe production remediator.
Action execution records a deterministic result only; it changes no real
service or filesystem. Unexpected dependency exceptions propagate; only
`GraphRecursionError` is converted to a bounded execution-error result.

No debugger architecture, instrumentation, additional external services or
production workflow infrastructure are included. The configured model endpoint
is the only external service used by `ask`.

Framework API references: [StateGraph and state semantics](https://docs.langchain.com/oss/python/langgraph/graph-api),
[native updates/values streaming](https://docs.langchain.com/oss/python/langgraph/streaming).
