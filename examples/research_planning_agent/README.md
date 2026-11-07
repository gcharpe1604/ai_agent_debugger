# Meridian Research Planning Agent

## Platform integration

Both `ask` and `run SCENARIO` entry points send spans from actual execution through the local debugger SDK to FastAPI at `127.0.0.1:8008` by default. `ask` calls the configured live model; `run` retains the existing controlled workload and is explicitly marked `controlled` (its deterministic methods are not labeled model/API calls). React reads received spans, with no seeded telemetry or log replay. Set `AGENT_DEBUGGER_ENDPOINT` to override the loopback endpoint, or set it to an empty string to disable export. [Normal backend/frontend and uv commands](../../docs/local-development.md).

From this agent directory, use `uv sync --locked` and `uv run --locked python -m research_planning_agent ask "<your request>"`. The SDK source is declared in `tool.uv.sources`; a standalone pip install also requires installing the repository SDK first. Add `--extra test` to uv when deliberately running the test tools described below.

The earlier domain-workload documentation follows. Model calls are live; the existing tools/evidence remain local.

A standalone research-planning workload with deterministic controlled scenarios
and an optional live semantic model. Both modes compare two fictional field
stations using the same local evidence, workflow, revisions, and deterministic
support validation. There is no database, web search, or sibling
example import. The configured model endpoint is the only live external service.

## Run

Python 3.10+. From this directory in PowerShell:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e '.[test]'
.\.venv\Scripts\python.exe -m research_planning_agent run RP-01
.\.venv\Scripts\python.exe -m research_planning_agent run RP-09 --json
.\.venv\Scripts\python.exe -m research_planning_agent ask "Recommend the cheapest eligible field station between Ridge and Vale for 40 people, requiring 10 kW, a daily budget of 1000 credits, open access and an approved permit as of 2026-06-01." --json
```

With the environment activated, use `python -m research_planning_agent run RP-01`.
The console entry point is `research-planning-agent`. On Unix, use `python3` and
`.venv/bin/python`. Installation requires a package index or cached dependencies;
controlled execution and all tests are offline and credential-free.

CLI exit 0 means execution succeeded, including an intentional blocked, incomplete,
or incorrect completed scenario. Configuration errors return 1; invalid command syntax returns 2.
The CLI does not evaluate ground truth. A blocked result retains its rejected
draft, if synthesis was reached; that draft is not an approved recommendation.

## Live mode

Copy `.env.example` to `.env` and set a key and model, or use shell variables.
The nearest `.env` from the current directory upward is loaded for `ask` only;
existing shell values take precedence.

| Variable | Meaning |
| --- | --- |
| `RESEARCH_PLANNING_AGENT_API_KEY` | Required bearer token; masked in models and omitted from results/errors. |
| `RESEARCH_PLANNING_AGENT_MODEL` | Required OpenAI-compatible Chat Completions model. |
| `RESEARCH_PLANNING_AGENT_BASE_URL` | Defaults to `https://api.openai.com/v1`; HTTPS is required except loopback HTTP. |
| `RESEARCH_PLANNING_AGENT_TIMEOUT_SECONDS` | Finite value greater than zero and at most 120; defaults to 30. |

`ask` preserves the exact input as `original_request` and retains the validated,
trimmed request and extracted constraints in `task`. The live model supplies
decomposition, the initial plan, evidence assessment, any revision, and the cited
draft. Every response is strict Pydantic-validated JSON. Python verifies that
normalized constraints occur in the original request, plans retain the task and
dependencies, assessments match supplied evidence metadata, and reports cite only
supported supplied evidence.

Evidence loading and collection, prerequisite enforcement, current/superseded and
as-of rules, revision limits, terminal status, and final support validation remain
deterministic. Missing evidence produces an incomplete result with no unsupported
recommendation. Each semantic stage permits one structured-output repair and one
shared transient retry for `429`, `500`, `502`, `503`, or `504`, for at most three
HTTP requests. Refusals, other HTTP errors, network failures, and timeouts remain
errors rather than research outcomes.

## Architecture

```text
controlled CLI -> scenario loader -> factory --\
live CLI -> LiveModelClient --------------------> ResearchPlanningAgent
                                                |-> EvidenceSource (local corpus)

request -> decompose -> plan -> required-fact coverage check
        -> resolve prerequisites / collect each fact
        -> assess -> optional task-preserving revision / follow-up / reassess
        -> synthesize -> independently validate support -> result
```

`agent.py` contains ordinary orchestration. `model_client.py` implements the six
controlled model boundaries: decomposition, planning, assessment, revision,
synthesis and validation. Live mode replaces the first five and inherits the same
deterministic support validation. `evidence.py` owns corpus loading and exact
topic-based collection.
`scenarios.py` owns configuration validation, prepared model responses and factory
construction. It strips IDs and all scenario metadata before constructing runtime
dependencies. Source exclusions prepare a fresh local corpus at the same boundary.
There is no ranker, tool framework or duplicated sibling-agent implementation.

Every run has fresh result state, explicit assessment invocation numbers and no
consumed override counters. Reusing an agent yields identical output. Application
output retains plans, collection prerequisites, evidence IDs/content, assessments,
the proposed revision, the draft, issues and operation names. These are domain
results, not debugger Run/Span/Trace or finding abstractions.

## Domain and model

The documented request template accepts positive integer people, power and budget
constraints and an ISO date. Candidates and criteria are deliberately fixed:

> Recommend the cheapest eligible field station between Ridge and Vale for 40 people, requiring 10 kW, a daily budget of 1000 credits, open access and an approved permit as of 2026-06-01.

Each site needs capacity, power, daily cost, access and permit facts. The permit
lookup requires resolved access evidence. Ridge costs 600 credits but its current
capacity is 30; Vale costs 900 and accommodates 60. Vale's initial permit records
conflict. The follow-up registry decision explicitly supersedes both. The corpus
also includes Ridge's superseded capacity of 80 and irrelevant visitor capacity.

- `ResearchTask`: original request and parsed constraints/date.
- `Plan` / `PlanStep`: task, ordered required facts, prerequisite facts and initial
  or follow-up source query. Required facts are ten stable `site.topic` keys.
- `EvidenceItem`: ID, title/source, content, site/topic, typed value, version/date,
  currentness, query availability and explicit supersession references.
- `EvidenceAssessment`: selected supporting IDs, missing facts, conflicting IDs
  and stale IDs. Conflicts cannot be resolved by simply preferring the newest date;
  an explicit newer superseding record is required.
- `PlanRevision`: proposed plan and reason. The original task is retained and any
  changed constraint rejects the revision. One revision is allowed.
- `Report` / `Claim`: recommendation, typed factual claims with citations, and
  unresolved facts. Every resolved decision fact must appear, including facts that
  disqualify the cheaper candidate.
- `ResearchResult`: retained workflow outputs, status and validation issues.

Normal selection excludes superseded and future-dated records. Validation
recomputes support from the complete collected evidence rather than trusting the
assessment replacement. It checks citations, values, omitted facts, unresolved
facts and the cheapest eligible decision. All facts must be resolved before a
recommendation; a fully researched decision with no eligible site is completed
with no recommendation. Missing/conflicting facts produce incomplete output.
Invalid plans and revisions produce blocked output. Normal validation also blocks
unsupported drafts; prepared validation responses let selected controlled scenarios
retain an incorrect terminal report without weakening the normal validator.

Evidence assertions use typed values alongside human-readable content. This makes
support checks exact and inspectable; it does not implement natural-language
entailment. Correctness of the fictional local records is an input assumption.

## Scenarios and evaluation

See [SCENARIOS.md](SCENARIOS.md) for the ten definitions written before code.
RP-01 and RP-02 are correct references. RP-03 through RP-10 expose stale selection,
suppressed conflict, omitted prerequisite, wrong ordering, task drift, failed
revision, unsupported synthesis and ignored decision evidence respectively.

Runtime JSON lives in `src/research_planning_agent/data/scenarios/` and contains
only the ID, request and injected dependency/model behavior. Typed assessment
replacements target invocation 1 or 2. Plan, synthesis, revision and validation
each occur at most once. Invalid JSON keys/constants, duplicate IDs/coordinates, extra fields,
invalid references, impossible evidence values and supersession cycles are
rejected. Semantic plan/revision/claim faults remain representable intentionally;
normal runtime guards expose some, while prepared validation responses allow four
draft-level faults to reach terminal output.

`ground_truth/` manifests and `tests/ground_truth_schema.py` are evaluation-only.
The strict schema records expected execution, origin/category, suspicious
operations, collection order, revision behavior, draft decision and issues.
Runtime never reads these labels. Tests verify actual intermediate behavior
against manifests and prove each catalogue injection is reached. The catalogue
retains four internally blocked failures and four incorrect completed reports;
a correct incomplete result is not an agent failure.

## Verify and package

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m ruff check src tests
.\.venv\Scripts\python.exe -m ruff format --check src tests
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -m pip wheel . --no-deps --no-build-isolation -w dist
```

The wheel build requires setuptools >=77 in the environment when using
`--no-build-isolation`. Packaging tests build offline, inspect the ZIP and execute
all ten CLI scenarios from an isolated wheel installation outside this source
tree. Only runtime code/config and evidence ship; tests, evaluation schema and
ground truth do not. Mocked live tests cover grounding, revision, incomplete
results, structured repair, provider failures, configuration, and isolation. Test
tools are optional development dependencies.

Scope is intentionally a bounded two-site comparison: no live source discovery,
iterative search engine, production planner, provider registry, persistence, or
instrumentation. No changes to the main debugger are needed.
