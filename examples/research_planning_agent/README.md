# Meridian Research Planning Agent

A standalone deterministic workload for research-plan debugging and evaluation.
It compares two fictional field stations using local evidence, resolves a permit
conflict through a plan revision, and checks whether the final decision follows
all required facts. No network, credentials, real model, debugger SDK, database or
sibling example imports are used at runtime.

## Run

Python 3.10+. From this directory in PowerShell:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e '.[test]'
.\.venv\Scripts\python.exe -m research_planning_agent run RP-01
.\.venv\Scripts\python.exe -m research_planning_agent run RP-09 --json
```

With the environment activated, use `python -m research_planning_agent run RP-01`.
The console entry point is `research-planning-agent`. On Unix, use `python3` and
`.venv/bin/python`. Installation requires a package index or cached dependencies;
all subsequent execution and tests are offline and credential-free.

CLI exit 0 means execution succeeded, including an intentional blocked, incomplete,
or incorrect completed scenario. Configuration errors return 1; invalid command syntax returns 2.
The CLI does not evaluate ground truth. A blocked result retains its rejected
draft, if synthesis was reached; that draft is not an approved recommendation.

## Architecture

```text
CLI -> scenario loader -> factory -> ResearchPlanningAgent
                                   |-> ModelClient (deterministic fake)
                                   |-> EvidenceSource (local corpus)

request -> decompose -> plan -> required-fact coverage check
        -> resolve prerequisites / collect each fact
        -> assess -> optional task-preserving revision / follow-up / reassess
        -> synthesize -> independently validate support -> result
```

`agent.py` contains ordinary orchestration. `model_client.py` implements the six
model boundaries: decomposition, planning, assessment, revision, synthesis and
validation. `evidence.py` owns corpus loading and exact topic-based collection.
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
ground truth do not. Test tools are optional development dependencies.

Scope is intentionally a bounded two-site comparison: no arbitrary-language
research, live source discovery, iterative search engine, production planner,
external services or instrumentation. No changes to the main debugger are needed.
