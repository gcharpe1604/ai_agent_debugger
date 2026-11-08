# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

AI Agent Debugger: a platform for debugging AI agent executions through structured OpenTelemetry traces. It is a monorepo of independent packages, and each has its own `pyproject.toml`/`uv.lock` or `package.json`:

- `sdk/python` — `ai_agent_debugger_sdk`, a thin OTel-based capture SDK (`Debugger`, `TraceSession`, `HttpSpanExporter`).
- `backend` — `agent_debugger_api`, a FastAPI app (`agent_debugger_api.main:app`).
- `frontend` — a React 19 + Vite UI (JavaScript, no TypeScript).
- `examples/{tool_task_agent,rag_agent,research_planning_agent,langgraph_workflow_agent}` — four standalone agent workloads. Each depends on the SDK as an editable path dependency (`[tool.uv.sources]`). `examples/refund-agent` is legacy and **excluded** from the integration.

The development shell is Windows PowerShell. The docs use `npm.cmd` and `.\.venv\Scripts\python.exe`.

## Commands

Run the local integration from the repo root (full details in `docs/local-development.md`):

```powershell
# Backend (port 8008). Local capture only works with this env var set.
$env:AGENT_DEBUGGER_LOCAL_MODE = '1'
uv run --project backend --locked uvicorn agent_debugger_api.main:app --host 127.0.0.1 --port 8008 --workers 1 --no-proxy-headers

# Frontend (port 5175, strictPort; proxies /api -> 127.0.0.1:8008)
cd frontend; npm.cmd run dev

# Run an agent. `ask` calls the live model; `run <SCENARIO>` is deterministic and makes no provider call.
uv run --directory examples/rag_agent --locked python -m rag_agent ask '<question>'
uv run --directory examples/rag_agent --locked python -m rag_agent run RAG-01
```

If port 8008 or 5175 is already in use, reuse the running process; do not start a second copy. Backend readiness: `GET http://127.0.0.1:8008/api/v1/local/status`. `--directory` is intentional, because it selects the agent's own `.env` and config. Set `AGENT_DEBUGGER_ENDPOINT=''` to disable export.

Tests and lint:

```powershell
# Frontend (Vitest + jsdom + Testing Library; setup in src/test/setup.js)
cd frontend; npm.cmd test; npm.cmd run lint; npm.cmd run build
npx vitest run src/features/trace/treeModel.test.js        # single file
npx vitest run -t "name of test"                            # single test

# SDK (from sdk/python)
.\.venv\Scripts\python.exe -B -m pytest -q -p no:cacheprovider

# Each example agent (from examples/<agent>; install with pip install -e '.[test]')
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m pytest tests/test_retrieval.py::test_name -q
.\.venv\Scripts\python.exe -m ruff check src tests
.\.venv\Scripts\python.exe -m ruff format --check src tests

# Cross-package telemetry regressions (unittest; puts backend/src and sdk/python/src on sys.path)
python -m unittest tests/integration/test_telemetry.py
```

If pytest can't use its default temp dir on Windows, add `--basetemp=.venv/test-temp`. `.github/workflows/ci.yml` is currently empty, so there is no CI gate.

## Architecture

**Data flow (current, implemented):** agent CLI → `TraceSession.local(...)` (SDK, private OTel provider + BatchSpanProcessor) → `HttpSpanExporter` POSTs `local-1` JSON batches of *ended* spans → `POST /api/v1/local/traces` → `LocalMemoryRepository` (in-process memory) → `GET /api/v1/local/runs[/{trace_id}[/spans/{span_id}]]` → frontend `data/apiRepository.js` → UI. The UI reads on **Refresh**; there is no streaming.

Key files along this path: SDK `transport.py`/`session.py`; backend `api/routes/{ingestion,runs}.py` and `traces/{schemas,repository,service}.py`; frontend `src/data/apiRepository.js`; each agent's `cli.py`.

**The local profile is deliberately bounded and gated.** If you change it, preserve these invariants:
- Ingestion returns 503 unless `AGENT_DEBUGGER_LOCAL_MODE=1`. It never silently falls back to unauthenticated production ingestion.
- It accepts loopback clients and Host only, Origin only from the local frontend ports (5175/4173), and requires the header `x-agent-debugger-local: 1`.
- Storage is limited to 100 traces, 200 spans/trace, 4,000 spans total, 16 MiB and a 4h TTL. It is cleared on restart, and identical redelivery is idempotent.
- The export is metadata-only. No prompts, model outputs, credentials, headers or stack traces are exported.
- Receipts must not claim Kafka/durable acceptance.

**Target architecture (documented, mostly unimplemented):** FastAPI → Kafka → Trace Writer → ClickHouse for telemetry. PostgreSQL holds only control-plane, analysis and knowledge data. A single controlled LLM "investigator" with deterministic grounding replaces the older rule engine. See `docs/ARCHITECTURE_UPDATE_NOTES.md` (it supersedes parts of `HLD.md`/`LLD.md`), `docs/trace-protocol.md` (the SDK↔backend contract: one Run = one OTel trace, `trace_id` is the Run ID, arrival order is not execution order, partial traces are preserved) and `docs/analysis-engine.md`.

Leftovers from the older design still exist in `backend/`: `db/` (SQLAlchemy/asyncpg, `config.py` reads `DATABASE_URL` from the root `.env`), `alembic.ini`/`migrations/`, `analysis/` (rule engine) and `api/routes/analysis.py`. The analysis route is **not registered** in `api/router.py`. PostgreSQL is reached through `compose.yaml` on host port 5433.

**SDK semantics worth knowing** (`sdk/python/README.md` has the full spec):
- `Debugger` never replaces a global/host OTel provider. It reuses one if present, otherwise it creates a private console-exporting provider.
- `run()` follows normal OTel parentage, so a nested run is a child span, not a new trace.
- Capture accepts only exact built-in JSON-like types. It does not call `str()`/`repr()` on application objects, redacts secret field names recursively, and is bounded by bytes, depth and node count.
- Instrumentation is fail-open: capture errors are swallowed, and user exceptions propagate unchanged.
- There is no global monkey patching. `TraceSession` wraps explicitly named methods on caller-owned instances.

**Example agents:** each has a controlled (deterministic) mode and a live mode (one OpenAI-compatible HTTP endpoint, configured by the agent's ignored `.env`). Controlled runs mark the root span `debugger.execution.mode=controlled`, and their planner functions are recorded as custom operations, not model calls. `data/scenarios/*` are runtime inputs. `ground_truth/*` are evaluation-only expected outcomes, validated by `tests/ground_truth_schema.py` and never read at runtime or packaged.

**Frontend:** `src/main.jsx` wires `createApiAdapters()` into `App`. `App`'s defaults are "disconnected" adapters, and tests inject fixture repositories (`src/test/fixtureRepository.js`, `src/data/*Fixtures.js`). Routing is hash-based (`app/routes.jsx`, default `#/projects/local/runs`). Features live in `src/features/{runs,trace,evidence,access}`, with pure model logic (`treeModel.js`, `timelineModel.js`, `*State.js`) kept separate from components and unit-tested. The API adapter must surface read failures and never substitute sample data. UI design references are in `docs/frontend/design-spec.md`.

## Project handoff and working rules (OJT)

@docs/handoff.md

`docs/handoff.md` is the current-state doc and the single shared plan. Read it at session start, then run `git status` and check recent commits before trusting its status matrix. Evidence for the matrix is in `docs/claude/audit-2026-11-07.md`; the OJT rubric is in `docs/claude/ojt-evaluation-rubric.md`.

**Role.** Act as a senior engineering mentor, backend architect and reviewer. The user is learning, so explain unfamiliar concepts simply first, then internals, then how they map to this project. The user writes the core pieces (ClickHouse writer, Kafka consumer, investigator grounding validation). You explain, review and draft routine parts. Challenge weak designs; do not agree by default.

**Sources of truth, in order:** (1) repo code and tests actually run, (2) the design docs in `docs/`, (3) confirmed user decisions, (4) `docs/handoff.md`. Earlier assistant replies are not sources of truth. When sources conflict, report the conflict with dates; do not silently reconcile.

**Rules**
- Never report tests as passing unless you ran them. Label status with the handoff vocabulary (IMPLEMENTED + TESTED, LOCAL-DEMO-ONLY, SCAFFOLD, PLANNED, DEPLOYED, UNKNOWN).
- A separate AI-generated reference implementation exists (location unknown). Its results are not progress in this repo. Study it; do not paste it.
- Architecture is fixed: SDK/OTel -> FastAPI -> Kafka -> trace-writer -> ClickHouse, with PostgreSQL for control-plane and analysis data. Kafka and ClickHouse are required. Replay and counterfactual debugging are out of scope. Do not revert to Postgres-only or rule-engine designs.
- The local profile (`/api/v1/local/*`, protocol `local-1`) and the durable contract (`/api/v1/traces`, protocol `"1"`) are different. Do not reuse local loopback gating or payload rejection in the durable path.
- Investigator: findings must cite real span/event IDs validated server-side; abstain when evidence is insufficient; suspicion is not a proven root cause; a recovered retry is not a failure; provider errors never become findings; inputs bounded, outputs structured.
- Small, testable increments on feature branches. No unrelated refactors. Do not edit the design docs without an explicit decision. No secrets in code, docs or logs.
- After a change is verified, update the status matrix and next-actions table in `docs/handoff.md` with the date and evidence, and add a changelog line.
- Prompts for other coding agents: exact scope and files, acceptance criteria, verification steps.

**Style.** Direct and terse. Lead with the answer. No praise or recap. Prefer code over documentation.
