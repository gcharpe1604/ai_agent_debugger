# Local development: actual agent traces

The four existing agents use their real live-model clients and export ended OpenTelemetry spans through the SDK, normal FastAPI modules and React API adapter. There is no trace generator, replayed feed or controlled-scenario fallback in this path. `refund-agent` is excluded.

## Start

Use the original repository root in each terminal. If port 8008 or 5175 is already running, reuse that process; do not start a second copy. Check backend readiness at `http://127.0.0.1:8008/api/v1/local/status`.

Backend:

```powershell
$env:AGENT_DEBUGGER_LOCAL_MODE = '1'
uv run --project backend --locked uvicorn agent_debugger_api.main:app --host 127.0.0.1 --port 8008 --workers 1 --no-proxy-headers
```

Frontend:

```powershell
cd frontend
npm.cmd run dev
```

Open [Runs](http://127.0.0.1:5175/). There is no source flag or special Vite mode. The frontend uses the normal `/api` proxy and backend adapter.

## Execute an agent

From the repository root, in a third terminal:

```powershell
uv run --directory examples/tool_task_agent --locked python -m tool_task_agent ask 'Please fulfill order ORD-100.'

uv run --directory examples/rag_agent --locked python -m rag_agent ask 'How long are deleted files kept in the trash before permanent deletion?'

uv run --directory examples/research_planning_agent --locked python -m research_planning_agent ask 'Recommend the cheapest eligible field station between Ridge and Vale for 40 people, requiring 10 kW, a daily budget of 1000 credits, open access and an approved permit as of 2026-06-01.'

uv run --directory examples/langgraph_workflow_agent --locked python -m langgraph_workflow_agent ask 'The Beacon service has a stalled worker. Please remediate the incident with ready telemetry.'
```

Run any one command, then **Refresh** Runs. Each execution creates new SDK trace/span IDs. The CLI prints the trace ID and acknowledged span count to stderr; the normal result remains on stdout. Export failures are reported and never silently replaced with fixtures. The SDK is a local editable dependency declared in each agent's uv configuration. `uv run` prepares required dependencies; no separate instrumentation launcher is needed.

The agents load their existing ignored `.env` files from their own directories. Keep provider credentials there; do not paste them into commands, telemetry or browser storage. `--directory` is intentional: it selects the correct agent directory and configuration. Existing shell values take precedence. Live runs incur the configured provider's normal usage.

No telemetry environment variable is required for these four CLIs. Both `ask` and `run SCENARIO` export actual executed operations to the loopback backend by default. `ask` uses the configured live model. The existing scenario commands below execute deterministic controlled agents without a provider call; their root explicitly records `debugger.execution.mode=controlled` and their deterministic planner functions are custom operations, never model/API calls. No spans are reconstructed from saved domain logs.

```powershell
uv run --directory examples/tool_task_agent --locked python -m tool_task_agent run TOOL-01
uv run --directory examples/rag_agent --locked python -m rag_agent run RAG-01
uv run --directory examples/research_planning_agent --locked python -m research_planning_agent run RP-01
uv run --directory examples/langgraph_workflow_agent --locked python -m langgraph_workflow_agent run LG-01
```

Use `ask` when demonstrating real model requests. The agents' original controlled scenario data and business logic are unchanged. `refund-agent` remains excluded. Direct Python calls outside these CLI entry points still require an explicit SDK session; there is no global monkey patch.

To use a different supported loopback port, set `AGENT_DEBUGGER_ENDPOINT` to its `/api/v1/local/traces` URL. To run without telemetry, explicitly set `$env:AGENT_DEBUGGER_ENDPOINT = ''`. A stopped backend reports delivery failure while preserving the workload result. React currently reads on **Refresh**, not a push/streaming connection.

## Captured operations and boundaries

- Tool task: live plan/response model stages, actual HTTP attempts, local tool invocations and explicit step/attempt retry references.
- RAG: live classify/query/assessment/answer stages, actual HTTP attempts and local lexical retrieval.
- Research planning: live semantic stages, actual HTTP attempts, evidence collection and support validation.
- LangGraph: live parsing/decisions/response, actual HTTP attempts, executed graph nodes and dependency calls. Parentage is captured through actual execution context, not reconstructed from saved result logs.

All four models call the configured provider. Their existing inventory/payment/shipping services, research evidence, knowledge documents and service-remediation actions are local domain implementations. They are not real commerce or infrastructure services. The integration records their actual execution; it does not change their business behavior or insert faults.

Input/output capture is disabled for this metadata-only profile. No prompts, model responses, credentials, headers or exception stacks are exported. Attributes include recorded operation type, model/provider identity, HTTP status, step/attempt and explicit retry IDs. Exception types are recorded with sanitized operation context. Global/host-owned OpenTelemetry providers are not replaced.

## Storage and production boundary

The normal backend contains an **explicit loopback-only local profile**, enabled by `AGENT_DEBUGGER_LOCAL_MODE=1`. It uses bounded process memory: 100 traces, 200 spans per trace, 4,000 spans total, 16 MiB serialized records and four-hour trace expiry. Restarting the backend clears it. Do not restart before inspecting a run you need; rerun the agent after restarting.

This is not durable persistence or a production deployment. The declared authenticated Kafka → ClickHouse ingestion path remains unimplemented. Its acceptance semantics are unchanged: these local receipts do not claim Kafka delivery. PostgreSQL-backed health remains separate and may be unavailable while local capture works. Production authentication, ownership, payload capture and investigation are not implemented by this change.

The server reports a local capture workspace; it is not a persisted authenticated project. Local access checks loopback peer/Host/Origin and requires the explicit exporter header. Disabling the local profile returns 503; it never silently enables unauthenticated production ingestion.

Local endpoints in the normal application:

- `GET /api/v1/local/status`: runtime profile and local workspace.
- `POST /api/v1/local/traces`: bounded `local-1` batches of ended spans; receipt states temporary memory storage.
- `GET /api/v1/local/runs`: received execution summaries.
- `GET /api/v1/local/runs/{trace_id}`: exact captured spans.
- `GET /api/v1/local/runs/{trace_id}/spans/{span_id}`: exact span and explicitly recorded retry references.

Full capture completeness is not inferred from root arrival. Raw `UNSET`/`OK`/`ERROR`, missing parents and unknown child totals remain distinct. Refresh reads a current bounded snapshot; there is no streaming or backend-wide search claim.

Implementation: SDK `transport.py` / `session.py`; backend `api/routes/{ingestion,runs}.py` and `traces/{schemas,repository,service}.py`; frontend `data/apiRepository.js`; the four agents' existing `cli.py` files. The separate demo app/exporter/launcher/adapter and demo evidence were removed.

Historical agent-integration verification artifacts were removed during repository cleanup.

## Durable-pipeline infrastructure (Docker)

`compose.yaml` runs the infrastructure for the planned durable path. No backend code uses Kafka or ClickHouse yet; the local profile above still stores in memory.

```powershell
docker compose up -d
docker compose ps                  # postgres, kafka, clickhouse: healthy
docker compose logs kafka-init     # lists spanhelix.traces.v1 and spanhelix.traces.v1.dlq
```

| Service | From the host (Windows) | From other containers |
|---|---|---|
| PostgreSQL 17 | `localhost:5433` | `postgres:5432` |
| Kafka 4.3.2 (single-node KRaft) | `localhost:9092` | `kafka:29092` |
| ClickHouse 26.8 | HTTP `localhost:8123`, native `localhost:9000` | `clickhouse:8123` |

- Topics are created only by `kafka-init` (auto-creation is off). It is idempotent and exits after listing topics.
- Dev-only credentials: see `compose.yaml` and `.env.example`. Do not reuse them outside this machine.
- Data persists in named volumes across `docker compose down` / `up`. `docker compose down -v` deletes it.
- Kafka here is one broker with replication factor 1: restarts keep acknowledged data, losing the volume does not.
