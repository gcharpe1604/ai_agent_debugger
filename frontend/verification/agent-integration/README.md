# Actual agent integration — 21 October 2026

All four existing live `ask` paths completed once against their configured Google Gemini endpoint. They exported actual ended OpenTelemetry spans through `sdk/.../transport.py`, the normal FastAPI app and React `apiRepository.js`. No scenario files, saved domain event logs or synthetic trace records were converted into telemetry. `refund-agent` was not modified or executed.

| Agent | Exact SDK/backend trace ID | Spans | Model calls |
| --- | --- | ---: | ---: |
| tool-task-agent | `b36ea49ed9316c843eb7e1307ffc5c59` | 11 | 2 |
| rag-agent | `528853c861cf4be8d8a54093d68ed997` | 11 | 4 |
| research-planning-agent | `2dc95312580d778b456874a442993204` | 26 | 6 |
| langgraph-workflow-agent | `37de9fec1b69fe02f9cf3ef330a25035` | 16 | 3 |

Total: **64 spans**, **15 actual provider HTTP requests**, all returned HTTP 200. Each CLI reported acknowledged delivery. Backend reads matched the exact CLI trace IDs/counts, every span's trace identity matched, and every recorded parent resolved within its trace. These checks establish this local execution path, not production durability, completeness guarantees or scalability.

Machine-readable capture evidence (historical report removed during cleanup) contains identifiers/counts/statuses only. It is verification output, not runtime input. The agents' existing tools, knowledge documents and business evidence remain local; their models and execution telemetry are live.

## Browser observations

- Opened the normal app root with no source flag or Vite mode. Run Explorer displayed the four actual agent services and matching captured trace IDs.
- Opened LangGraph trace `37de9fec1b69fe02f9cf3ef330a25035`: its actual run/model/API/agent/graph-node/tool hierarchy contained 16 received spans.
- Selected API span `77fd2bc24f4213ff`; Attributes showed `http.response.status_code=200`, the exact trace ID, its recorded model parent `49df63922b06fa40`, service and decimal nanosecond timestamps. Content honestly reported payload capture disabled. The existing pinned inspector rendered the data.
- [Run Explorer screenshot](live-agents.png) and [actual HTTP span screenshot](live-span.png) are representative browser captures, not a size/theme matrix.

## Focused verification

- SDK: `uv run --directory sdk/python --extra test --locked pytest -q tests/test_sdk.py tests/test_session.py` — **52 passed**. Covers existing capture/provider behavior plus sync/async instrumentation, actual parent context, sanitized failures, HTTP error statuses and explicit retry references.
- Backend: `uv run --project backend --locked --offline --with-editable ./sdk/python python -m unittest discover -s tests/integration -v` — **5 passed**. Covers atomic/idempotent bounded storage, invalid records, exporter bounds/allowlist and explicit local access gating/peer/Host/Origin checks.
- Frontend: `node node_modules/vitest/vitest.mjs run src/data/apiRepository.test.jsx src/app/App.test.jsx src/features/trace/TraceDetail.test.jsx` — **33 passed**. Includes actual API adapter composition, empty/error/no-fallback behavior and existing scoped explorer/inspector regressions.
- Browser inspection also found wrapping in narrow pinned rows. A two-rule CSS overflow fix keeps fixed-height rows legible; full names and unknown child totals remain available in existing row labels/tooltips. The updated screenshot was inspected, and the production build was rerun successfully.
- Frontend ESLint and production Vite build passed. No repeated provider executions or broad example test matrix was run.
- `git diff --name-only -- examples/refund-agent` returned no changes. Existing unrelated work was preserved. A pre-existing whitespace change in SDK `models.py` was left untouched.

## Normal source files

- SDK `transport.py`, new `session.py`, public exports, SDK tests and uv lock.
- Backend `main.py`, normal API router, `api/routes/ingestion.py`, `api/routes/runs.py`, and `traces/schemas.py`, `repository.py`, `service.py`; backend dependency extra cleanup and focused tests.
- Four existing `cli.py` live paths, their SDK dependency declarations/uv locks and integration notes.
- Frontend `data/apiRepository.js`, entry, normal Vite proxy and conditional capture labels, plus the focused pinned-row overflow fix in `features/trace/trace.css`. No source selector, dedicated launcher or sample fallback.

Retired: `demo_exporter.py`, `dev_demo.py`, `scripts/local_demo.py`, `localDemoRepository.js`, its old tests, the separate local-demo test directory/runbook and old demo evidence. Historical design previews and isolated regression fixtures remain separate from runtime.

## Remaining boundaries

This runs the normal modules in the explicitly enabled, loopback-only memory profile. It is not production authenticated Kafka → ClickHouse ingestion. Storage is bounded and clears on backend restart/expiry; full capture completeness remains Unknown. Inputs/outputs, investigation, production auth/ownership and remote exporter transport remain outside this change. Existing standalone CLI `run SCENARIO` paths remain offline and do not populate the feed.

[Repeatable startup and four normal uv commands](../../../docs/local-development.md). Backend and frontend were left running after verification; reuse them rather than binding their ports again.
