# Tool-Using Task Agent

A standalone order-fulfillment workload with deterministic controlled scenarios
and an optional live semantic model. Both modes use the same `TaskAgent`, local
inventory/payment/shipping tools, in-memory state, validation, and safety rules.
There is no debugger SDK, backend, database, UI, replay, or production commerce
integration. The configured model endpoint is the only live external service.

## Install and run

Python 3.10+; runtime dependencies are Pydantic, HTTPX, and python-dotenv.
Controlled execution and all tests remain offline and credential-free.
Installation needs a package index or an existing wheel cache.

From the repository root in PowerShell:

```powershell
cd examples/tool_task_agent
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e '.[test]'
.\.venv\Scripts\python.exe -m tool_task_agent list
.\.venv\Scripts\python.exe -m tool_task_agent run TOOL-01
.\.venv\Scripts\python.exe -m tool_task_agent run TOOL-07 --json
.\.venv\Scripts\python.exe -m tool_task_agent ask "Please fulfill order ORD-100" --json
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m ruff check src tests
.\.venv\Scripts\python.exe -m ruff format --check src tests
```

On Linux/macOS use `python3` and `.venv/bin/python`. The installed console command
is `tool-task-agent`. Runtime JSON ships inside the package, so both entry points
work outside this directory. CLI exit 0 means a scenario executed, including an
intentional failure; invalid configuration/IDs exit 1, invalid CLI syntax exits 2.
The CLI never reads or scores ground truth.

## Live mode

Copy `.env.example` to `.env` and set a key and model, or use shell variables.
The nearest `.env` from the current directory upward is loaded for `ask` only.
Existing shell values take precedence, including empty values, which fail
validation.

| Variable | Meaning |
| --- | --- |
| `TOOL_TASK_AGENT_API_KEY` | Required bearer token; excluded from output and sanitized errors. |
| `TOOL_TASK_AGENT_MODEL` | Required OpenAI-compatible Chat Completions model. |
| `TOOL_TASK_AGENT_BASE_URL` | Defaults to `https://api.openai.com/v1`; HTTPS is required except loopback HTTP. |
| `TOOL_TASK_AGENT_TIMEOUT_SECONDS` | Finite value greater than zero and at most 120; defaults to 30. |

`ask` sends the free-text request to `LiveModelClient.plan()`, then gives the
validated `ToolCall` list to the existing workflow. The exact original request is
preserved as `original_request`; the trimmed request used by the workflow remains
in `request`, and the interpreted structured plan is recorded in the first event.
Unknown tools, duplicate logical steps, and tools that are ineligible for a step
are rejected before tool execution. Resolved arguments are validated by the real
tool argument models before any side effect.

The LLM creates the plan and final wording. Deterministic Python resolves result
references, invokes tools, controls retries, enforces payment and shipment
preconditions, validates every response, mutates state, verifies final state, and
records events. Final response status and shipment facts must match workflow/tool
state. Natural-language wording is model-generated and is not semantically parsed.

Each semantic stage allows one structured-output repair and one shared transient
HTTP retry for `429`, `500`, `502`, `503`, or `504`. The shared budget permits at
most three HTTP requests per stage. Refusals, other HTTP errors, network failures,
and timeouts are not retried or converted into fulfillment results. Redirects are
disabled and the CLI closes its HTTPX client on success or error.

```python
from tool_task_agent.scenarios import build_agent, load_scenario

scenario = load_scenario("TOOL-01")
agent = build_agent(scenario)
result = agent.run(scenario.request)
assert result.status == "completed"
```

## Architecture and workflow

```text
runtime scenario JSON -> build_agent -> prepared planner + fresh local tool services

request: "Fulfill order ORD-100."
  -> interpret_plan
  -> get_order -> validate_result
  -> reserve_inventory -> validate_result
  -> charge_payment -> validate_result
  -> create_shipment -> validate_result
  -> inspect_fulfillment -> validate_result
  -> validate_state
  -> generate_response
```

The planner recognizes `Fulfill order ORD-<digits>.` (case-insensitive, optional
period). Only ORD-100 exists: two SENSOR-KIT units, total 5000 integer cents,
initial stock five. Unsupported requests fail explicitly; unknown orders fail lookup.
Plans are ordered tool calls with stable logical step IDs (`order`, `reserve`,
`pay`, `ship`, `inspect`). `$order.quantity` and similar references bind arguments
to actual validated earlier results. Tools enforce state prerequisites even when
the planner omits or rearranges steps.

`TaskAgent` receives a model and a tool factory. It knows no scenario IDs, fault
categories, or expected outcomes. Controlled mode uses prepared planner outputs to
inject selection/argument/order faults, prepared tools to inject service errors or
corrupt responses/state, and a prepared response override for final disagreement.
Live mode supplies the same two model methods without importing scenario code.
There is no scenario branch in orchestration or general planning framework.

Workflow and tool work is synchronous and local. Every `run()` allocates fresh
services, state, and attempt counters. Controlled mode has stable domain IDs and
no random values, timestamps, network calls, or sleeps. Each result includes a journal:
operation, logical step, attempt, arguments, raw output/error, and a deep state
snapshot. This is ordinary workload output, not debugger Run/Span/Trace data.
The JSON result includes both operational status and structured final response.

## Tools and state

| Tool | Inputs | Result / effect |
| --- | --- | --- |
| `get_order` | order ID | Order SKU, quantity, total cents; read only. |
| `get_stock` | SKU | Available count; read only. Plausible but wrong substitute for reservation. |
| `reserve_inventory` | order ID, SKU, quantity | Creates RES-100, decrements stock 5 -> 3. Arguments must match order. |
| `charge_payment` | order ID, amount cents | Requires reservation and matching total; creates PAY-100. |
| `create_shipment` | order ID | Requires reservation and payment; creates SHIP-100 referencing both. |
| `inspect_fulfillment` | order ID | Reads current order, stock, reservation, payment, shipment. |

Write tools are idempotent for this single order. Preconditions and argument
validation happen before writes. Three attempts **total** are allowed per call;
only `TransientToolError` and `ToolTimeout` are retryable. Timeout injection raises
an explicit simulated pre-commit deadline exception, without measuring wall time.
Permanent errors and malformed responses are not retried. Successful retry stops
the retry loop immediately; downstream steps run once.

Final state validation requires all records, matching order identities, SKU,
quantities, total, reservation/payment links, and stock conservation. The stored
state must agree with inspection. Partial state is preserved on failure; there is
no automatic rollback, refund, or reservation release. A malformed post-commit
reservation response therefore leaves stock reserved and must not be retried blindly.

## Scenario catalogue

| ID | Injection | Expected behavior |
| --- | --- | --- |
| TOOL-01 | None | Healthy fulfillment, two units shipped. |
| TOOL-02 | Planner selects `get_stock` instead of reserve | Read succeeds; reservation response validation fails; no writes. |
| TOOL-03 | Planner gives reservation quantity 0 | Invalid arguments rejected before mutation. |
| TOOL-04 | Permanent payment failure | Stock reserved; payment fails once; no shipment. |
| TOOL-05 | Payment timeout on attempts 1, 2, 3 | Retry budget exhausted; no payment/shipment. |
| TOOL-06 | Replace reservation response with `{"accepted": true}` | Reservation commits; response validation fails; partial state retained. |
| TOOL-07 | Transient payment failure on attempt 1 | Attempt 2 succeeds; correct fulfillment; exactly one charge. |
| TOOL-08 | Transient payment failure on attempts 1, 2, 3 | Retry exhaustion; reserved stock remains. |
| TOOL-09 | Planner omits reserve | Payment rejects missing reservation. |
| TOOL-10 | Planner puts ship before pay | Shipment rejects missing payment. |
| TOOL-11 | Shipment receipt says 2 but stored quantity becomes 1 | Inspection exposes corruption; state validation fails. |
| TOOL-12 | Final response claims 1 unit after tools ship 2 | Operational completion with incorrect final response. |

## Runtime configuration and ground truth

```text
src/tool_task_agent/
  models.py, tools.py, controlled_model.py, agent.py, scenarios.py, cli.py
  data/scenarios/TOOL-01.json ... TOOL-12.json
ground_truth/TOOL-01.json ... TOOL-12.json
tests/ground_truth_schema.py, test_*.py
```

Runtime schema version 1 permits `scenario_id`, `request`, optional `plan_override`,
`tool_faults`, and `response_override`. Extra structured fields, duplicate JSON
keys, nonstandard JSON constants, duplicate step IDs/fault coordinates, invalid
attempts and unreachable later attempts without earlier retryable errors are
rejected. Tool argument dictionaries intentionally permit faulty values; the
actual tool validates those at invocation. Complete plans can be replaced to
represent missing/reordered steps, but no step may be duplicated. A configured
fault targets a step in the plan; an earlier execution failure can still prevent
that step from being reached. Tests prove every catalogue injection is reached.

Evaluation-only manifests retain NovaCloud's `schema_version`, `scenario_id`,
`expected_outcome` (`correct`/`failure`), `expected_status`, `expected_failure`,
`important_operations`, and `expected_facts` conventions, using JSON instead of
YAML to avoid an extra dependency. Additional fields are:

- `expected_failure`: category, origin operation/step, detection operation/step.
  Detection is null for TOOL-12 because runtime does not check final-answer semantics.
  TOOL-07 records its recovered intermediate failure despite a correct outcome.
- `expected_suspicious_steps`: stable logical IDs to investigate. A missing step
  can be named even though it has no invocation event (TOOL-09's `reserve`).
- `expected_tool_calls`: exact invocation order, including retries.
- `expected_retry_behaviour`: maximum attempts, retried step, attempt/retry counts,
  and whether recovery occurs. Null step and zero counts mean no retry episode.
- `injected_fault`: exact runtime override fields, empty for the healthy case.
- `expected_error_code`: terminal error, null for operational completion.
- `expected_facts`: stock, reservation quantity, charged cents, stored shipment
  quantity, and final claimed quantity. Null means that record/claim is absent.
- `expected_causal_explanation`: concise explanation of the injected causal chain.

Ground truth and its validation schema remain outside the runtime package and
wheel. Only tests read them. Labels distinguish an intermediate failure recovered
correctly (TOOL-07), an operational failure with partial state, and an incorrect
answer after operational success (TOOL-12). These are known injection causes, not
claims about what a future debugger has diagnosed.

## Verification and limits

Tests cover each scenario's exact calls and JSON hash, state transitions,
response/error, bounded retries, idempotency, invalid arguments, ordering,
malformed config, ground-truth consistency, isolation, and fresh/reused/concurrent
repeatability. Live tests use HTTPX MockTransport and cover plan/tool validation,
tool failures, response consistency, repair/retry bounds, provider errors,
configuration, request preservation, and scenario isolation.

This is a small evaluation agent, not a production autonomous service.
It has one order/SKU, fixed identifiers, no arbitrary natural-language planning,
real scheduling, live timeouts, concurrency contention, or ambiguous post-commit
payment retries. Each run is an isolated fulfillment, not a shared warehouse.
Controlled final-response semantic validation remains deliberately absent to
expose TOOL-12; its operational `completed` status is not an evaluation verdict.
Live mode validates structured status/shipment fields without changing that
controlled scenario. No integration with existing refund scaffolding or
NovaCloud runtime is required.

