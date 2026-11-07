# AI Agent Debugger

A developer-focused platform for debugging AI agent executions through structured execution traces.

The goal is to help developers understand how an AI agent reached a particular result by capturing and visualizing model calls, tool calls, retrieved context and other execution steps, and by pointing at the steps most worth investigating, with evidence.

## Project status

**In development.** Only a local, in-memory slice works today. The durable pipeline, authentication and the investigator are not built yet.

| Area | Status |
|---|---|
| Python SDK on OpenTelemetry (batched export of ended spans) | Implemented. Exports to a loopback endpoint only |
| FastAPI ingestion and read API | Local profile only (`/api/v1/local/*`), stored in process memory and lost on restart |
| React UI (run list, execution tree, timeline, span inspector) | Implemented. Reads the local API on refresh |
| Prompt/response capture | Not exported yet. Traces are metadata only |
| Kafka ingestion, ClickHouse storage, backend trace reconstruction | Planned, no code |
| API-key authentication, PostgreSQL project and analysis data | Planned. `compose.yaml` runs a PostgreSQL container, but nothing stores data in it yet |
| AI investigator with evidence grounding | Planned, no code |
| Deployment | Not started |

Details and next steps: [`docs/handoff.md`](./docs/handoff.md).

## Run the current integration

[Start FastAPI/React and execute the four live agents with uv](docs/local-development.md). Real provider calls emit SDK spans; local memory storage is explicitly temporary. `refund-agent` is excluded.

## Target architecture

SDK (OpenTelemetry) -> FastAPI -> Kafka -> trace writer -> ClickHouse for telemetry, PostgreSQL for projects, keys and analysis results, a React UI, and one controlled LLM investigator whose findings are checked against recorded trace evidence. Replay and counterfactual debugging are future scope. See [`docs/HLD.md`](./docs/HLD.md) and [`docs/ARCHITECTURE_UPDATE_NOTES.md`](./docs/ARCHITECTURE_UPDATE_NOTES.md).

* **Backend:** Python, FastAPI
* **Instrumentation:** OpenTelemetry Python SDK
* **Telemetry transport and storage:** Kafka, ClickHouse
* **Relational data:** PostgreSQL
* **Frontend:** React, JavaScript
* **Deployment:** Docker

## Documentation

Design documents are in [`docs/`](./docs/): [PRD](./docs/PRD.md), [HLD](./docs/HLD.md), [LLD](./docs/LLD.md), [trace protocol](./docs/trace-protocol.md), [database](./docs/database.md) and [analysis engine](./docs/analysis-engine.md). Current state and plan: [`docs/handoff.md`](./docs/handoff.md).

## License

Licensed under the [Apache License 2.0](./LICENSE).
