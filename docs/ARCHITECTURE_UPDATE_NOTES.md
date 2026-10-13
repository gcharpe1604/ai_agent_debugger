# Architecture Update Notes

This package updates the earlier PostgreSQL-only / deterministic-analysis design.

## Superseded decisions

- PostgreSQL as primary trace/span store → **ClickHouse telemetry store**.
- Direct FastAPI → PostgreSQL trace persistence → **FastAPI → Kafka → Trace Writer → ClickHouse**.
- PostgreSQL as single source of all platform data → **PostgreSQL for transactional/control-plane/analysis/knowledge only**.
- Large deterministic semantic rule engine / 0–100 suspicion score → **one controlled LLM debugger investigator + deterministic grounding + High/Medium/Low investigation priority**.
- Trace-only debugging as sufficient for all semantic failures → **optional project-scoped authoritative knowledge for retrieval-vs-reasoning failures**.

## Preserved decisions

- Thin Python SDK built on OpenTelemetry.
- Custom batched HTTPS/JSON exporter.
- One Run = one OpenTelemetry trace for the supported SDK profile.
- Fail-open instrumentation.
- Partial/out-of-order trace support.
- Modular-monolith application design.
- Replay/counterfactual debugging remains future scope.
