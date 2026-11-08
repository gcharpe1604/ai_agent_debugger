# SpanHelix — Authoritative Project Handoff

**Project:** AI Agent Execution Debugging & Trace Analysis Platform (product name **SpanHelix**, accepted 2026-10-17). OJT software-engineering project.
**Repo:** `C:\Users\govin\Desktop\My_Projects\ai-agent-debugger` · GitHub `gcharpe1604/ai_agent_debugger`
**This file:** the only active handoff, model-agnostic, for any assistant (Claude, ChatGPT or other) and for the user. Written **2026-11-07** from a read-only repo audit, the project docs, test runs on a scratch copy, and user-confirmed decisions. Previous handoffs are archived at `claude/archive/` and are **not authoritative**. (The `claude/` folder name is historical; its contents are not assistant-specific.)

**How to use:** Treat this as current state + plan. For architecture detail, read the design docs (HLD, LLD, PRD, database, trace-protocol, analysis-engine); do not restate or re-litigate them. For file-level evidence behind any status claim, see `claude/audit-2026-11-07.md`. Re-verify against code before declaring anything done. Collaboration rules are in §11.

## 0. Status vocabulary (used everywhere below)

| Label | Meaning |
|---|---|
| **IMPLEMENTED + TESTED** | Code exists in the main repo and tests were actually run (2026-11-07, scratch copy) |
| **LOCAL-DEMO-ONLY** | Works on one machine in the loopback/in-memory profile; not durable, not authenticated, not deployable |
| **SCAFFOLD** | File/dir exists but is empty or a stub |
| **PLANNED** | Specified in design docs; no code |
| **DEPLOYED** | Running at a reachable URL. **Nothing is deployed.** |
| **UNKNOWN** | Not established. Do not guess. |

## 1. Scope and confirmed decisions

- **Goal:** capture AI-agent executions via SDK → durable pipeline → reconstructed trace UI → evidence-grounded failure investigation.
- **Out of scope for the OJT MVP: replay and counterfactual debugging.** Future extension only. (The 2026-10-17 "build the full replay product" reversal is withdrawn; see §9.)
- **Architecture is fixed** (per design docs): Python SDK on OpenTelemetry → FastAPI → **Kafka** → trace-writer consumer → **ClickHouse** (spans) · **PostgreSQL** (projects, keys, analysis attempts, findings, evidence) · React frontend · one controlled LLM investigator with deterministic evidence grounding. Do not revert to PostgreSQL-only or deterministic-only designs.
- **Kafka and ClickHouse are required by the program** (user-stated; no formal mentor confirmation on file).
- **LLM provider: UNDECIDED.** User, 2026-11-07: no AWS credits are currently available (earlier Bedrock decision assumed them), and no AI-provider credits. The investigator starts behind a provider interface with a deterministic stub; the real provider (Bedrock once credits exist, a local model, or a low-cost hosted API) is decided before action 8. A stub validates orchestration, grounding and abstention, not real-model debugging quality. Details in §6.
- **Deferred:** pgvector / authoritative knowledge base (not on the critical path), replay, multi-framework adapters, MSK/ECS-style production infra.
- **Product rules:** not a general observability platform, not a commercial SaaS. Smallest reliable end-to-end workflow first.

## 2. Deadlines and program requirements

| Item | Date | Status |
|---|---|---|
| Today (handoff written) | 2026-11-07 | — |
| 3rd-month viva (not final) | **Nov 15–22**, exact day UNKNOWN | User expects ~75–85% of work done; rubric for the viva UNKNOWN |
| Demo video submission | **Nov 25** | Confirmed by user |
| Deployment link submission | **Nov 25** | Confirmed by user; product must be deployable by then, changes allowed after |
| Final OJT end/submission date | UNKNOWN | — |

Evaluation framework the user pasted (saved at `claude/ojt-evaluation-rubric.md`): 10 parameters scored 1–5 across Technical Understanding (stack, architecture, problem solving), Engineering Execution (decomposition, code quality, debugging, testing, workflow) and Professional Capability (ownership, communication). Implication: the user writes core pieces (ClickHouse writer, Kafka consumer, investigator validation); assistants explain and review; use branches/PRs/issues; show edge-case tests.

**Candid framing:** 75–85% by feature count is not reachable by Nov 15–22. The defensible viva position is "working durable vertical slice (SDK → Kafka → ClickHouse → UI) plus investigator in progress". Confirm what the viva actually measures.

## 3. Implementation status (verified 2026-11-07; updated 2026-11-08)

### 3.1 Matrix

| Component | Status | Evidence |
|---|---|---|
| Python SDK (`sdk/python/src/ai_agent_debugger_sdk`) | **IMPLEMENTED + TESTED**, local-only; on `main` via PR #2 (2026-11-08) | `TraceSession` with `BatchSpanProcessor(256 / 64 / 1000 ms)`; `HttpSpanExporter` hard-locked to loopback. **54 SDK tests passed** |
| SDK payload capture | **PARTIAL** | `CaptureConfig` exists (`capture_inputs/outputs` default True, 16 KiB, depth 8, 512 nodes, `secret_fields`) but the exporter whitelists 10 metadata attributes only; payloads are not exported |
| FastAPI local ingestion + read API | **LOCAL-DEMO-ONLY**; on `main` via PR #3 (2026-11-08) | `/api/v1/local/*`, in-memory `LocalMemoryRepository`, loopback + header + origin gating. **Integration suite: 5 passed, 7 subtests** (main). Branch `feat/ui-failure-surfacing` (2026-11-08, not merged): run summary adds `first_error` (earliest ERROR span with no ERROR descendants); **integration suite 12 passed** |
| Auth / API keys | **PLANNED** | No auth on ingest. Frontend `accessAdapters.js` is a disconnected adapter |
| Kafka | **SCAFFOLD** (infra only) | `compose.yaml`: `apache/kafka:4.3.2`, single-node KRaft; listeners `localhost:9092` (host) and `kafka:29092` (containers); auto topic creation off; `kafka-init` creates `spanhelix.traces.v1` (3 partitions) and `spanhelix.traces.v1.dlq`. Healthy and both topics created on the user's machine 2026-11-08. **Round-trip verified 2026-11-08** (§3.4): console producer → `spanhelix.traces.v1` → console consumer (group `phase-b-verify-20261108T112615Z`) read it at partition 1, offset 0; group lag 0. That one non-envelope test message stays in the topic. No producer/consumer code or Python dependency |
| ClickHouse | **SCAFFOLD** (infra only) | `compose.yaml`: `clickhouse/clickhouse-server:26.8`, database `spanhelix`, HTTP `:8123`, native `:9000`. Healthy on the user's machine 2026-11-08; `SELECT version()` over HTTP `:8123` → `26.8.36.3` (2026-11-08, §3.4). No schema, no client code or dependency. Span-record contract: **PROPOSAL only**, `docs/proposals/clickhouse-span-record.md` (2026-11-08; DDL parsed in `clickhouse local`, not applied) |
| PostgreSQL | **SCAFFOLD** | `compose.yaml` has `postgres:17` only (container healthy 2026-11-08, `docker compose ps`); `/health` runs `SELECT 1`; `db/models.py`, `db/base.py` empty; `backend/migrations/versions/` empty; no alembic dependency |
| Trace reconstruction (backend) | **SCAFFOLD** | `traces/reconstruction.py` is 0 bytes. Tree/timeline are built **in the frontend** from parent IDs |
| Investigator (backend) | **SCAFFOLD** | `analysis/{engine,models,repository,service}.py`, `analysis/rules/*`, `routes/analysis.py` all 0 bytes |
| Frontend (React/Vite, `frontend/`, 92 tracked files) | **IMPLEMENTED + TESTED** | **137 vitest tests passed, 15 files** (main). Branch `feat/ui-failure-surfacing` (2026-11-08, not merged): **166 passed, 18 files**; lint and build pass; run list shows "First error", opening a failed run selects it, "Error spans" column, all-unknown columns hidden, Controlled/Live badge, one duration formatter. Manually checked at 1440×900 and 1280×800 against controlled TOOL-03/05, RAG-01, RP-01, LG-03. Run Explorer, virtualized tree, timeline, inspector, evidence UI. `apiRepository.js` reads real local runs; `investigationRepository.js` is **fixture-based**; auth adapter disconnected |
| Example agents (`examples/`) | Present, own tests **not run** | Use OpenAI-compatible `*_API_KEY/*_BASE_URL/*_MODEL` env vars |
| Bedrock integration | **PLANNED** | No `boto3`/Bedrock code anywhere |
| CI (`.github/workflows/ci.yml`) | **IMPLEMENTED** | Jobs: SDK tests (py3.10, py3.12), backend+SDK integration, frontend lint/test/build. All green on `main` `8b34c54` (GitHub check runs, 2026-11-08) |
| Dockerfile (`backend/Dockerfile`) | **SCAFFOLD** | 0 bytes |
| Deployment | **Not started. DEPLOYED: none** | — |

Other zero-byte files: SDK `context.py`, `errors.py`, `models.py`, `trace.py`. There is **no backend-specific test directory**; backend behaviour is covered only through the integration suite.

### 3.2 What actually works end-to-end today

Example agent → SDK (OTel spans, batched) → `POST /api/v1/local/traces` (loopback only) → in-memory store → `GET /api/v1/local/runs…` → React renders run list, tree, timeline, span inspector. **Metadata only; no model I/O; data lost on backend restart.** Docs: `docs/local-development.md` (backend port 8008, frontend 5175).

### 3.3 Two contracts: do not conflate

| | **Implemented: local** | **Target: durable** |
|---|---|---|
| Endpoint | `POST /api/v1/local/traces` | `POST /api/v1/traces` |
| Protocol field | `"local-1"` | `"1"` |
| Auth | none; loopback client + `x-agent-debugger-local: 1` + allowed origin (`127.0.0.1:5175`, `localhost:5175`, `:4173`) + `AGENT_DEBUGGER_LOCAL_MODE=1` | project-scoped credential; server derives `project_id` |
| Span time fields | `start_time_unix_nano` / `end_time_unix_nano` | `start_time` / `end_time`, plus `links` |
| Payloads | rejected: backend refuses `debugger.input*` / `debugger.output*` | governed by capture/redaction policy (to be decided, §8 action 7) |
| Limits | body ≤256 KiB, 1–64 spans/batch; store ≤100 traces, 200 spans/trace, 4,000 total, 16 MiB, 4 h TTL; idempotent redelivery, 409 on conflict | per `trace-protocol.md` |
| Persistence | none (cleared on restart) | Kafka ack → ClickHouse; Postgres metadata |
| Ack semantics | synchronous | HTTP 202 after broker accepts; at-least-once; consumer commits offsets only after ClickHouse persist |

The durable contract exists **only in docs**. Local-1 was a deliberate stepping stone; the durable path must not silently reuse its loopback gating or its payload rejection.

### 3.4 Compose stack verification (2026-11-08, user's machine, branch `feat/ui-failure-surfacing`)

Infra only. This proves the containers work; it says nothing about producer/consumer/writer code (none exists).

| Check | Command | Outcome |
|---|---|---|
| Start | `docker compose up -d` | exit 0; postgres, kafka, clickhouse already running; kafka-init re-ran |
| Health | `docker compose ps -a` | postgres, kafka, clickhouse `Up (healthy)`; kafka-init `Exited (0)` |
| Topics | `docker compose logs kafka-init` | lists `spanhelix.traces.v1` and `spanhelix.traces.v1.dlq` (plus a benign Kafka warning about `.`/`_` in topic names) |
| ClickHouse | `curl -u spanhelix:… "http://127.0.0.1:8123/?query=SELECT%20version()"` | `26.8.36.3` |
| Kafka produce | `docker exec -i agent-debugger-kafka /opt/kafka/bin/kafka-console-producer.sh --bootstrap-server localhost:9092 --topic spanhelix.traces.v1` with `{"verification":"phase-b","marker":"20261108T112615Z"}` | exit 0 |
| Kafka consume | `kafka-console-consumer.sh --bootstrap-server localhost:9092 --topic spanhelix.traces.v1 --group phase-b-verify-20261108T112615Z --from-beginning --timeout-ms 15000` | read the marker at partition 1, offset 0; "Processed a total of 1 messages" |
| Consumed? | `kafka-consumer-groups.sh --describe --group phase-b-verify-20261108T112615Z` | committed offset 1 on partition 1, lag 0 on all 3 partitions |

**Side effect to know about:** `spanhelix.traces.v1` partition 1 offset 0 now holds that non-envelope JSON. A new trace-writer group reading from the earliest offset will see it first. It should be rejected to the DLQ, which makes it a ready-made invalid-message test. No compose or `.env.example` change was needed.

## 4. Architecture pointers (not duplicated here)

- One Debugger Run = one OTel trace. Reconstruction from parent IDs, never arrival order; tolerate missing parents, multiple roots, cycles, late spans.
- ClickHouse `telemetry_spans`: identity `(project_id, trace_id, span_id)`; the sort-key `(project_id, trace_id, started_at, span_id)` is a **hypothesis to validate**, not a settled fact; logical dedup required (ReplacingMergeTree merges are eventual).
- PostgreSQL: `projects`, `api_keys`, `analysis_attempts`, `findings`, `finding_evidence` (+ optional pgvector, deferred).
- Investigator: direct and bounded read-only modes; structured candidate findings; **deterministic grounding** of every cited span/event ID; abstain when evidence is insufficient; High/Medium/Low investigation priority (not a probability); recovered retries are not failures; provider errors never become findings.
- Source of truth for all of this: `HLD.md`, `LLD.md`, `PRD.md`, `database.md`, `trace-protocol.md`, `analysis-engine.md`. Repo copies on `main` and the working branch had no diff in these six docs at audit time.

## 5. Critical path

```
SDK → FastAPI (/api/v1/traces) → Kafka → trace-writer → ClickHouse
   → read API + backend reconstruction → investigator (Bedrock)
   → deterministic grounding → PostgreSQL findings/evidence → UI
```

Everything off this line (pgvector, knowledge, extra frontend polish, replay) waits. **If time runs out, cut investigator scope first; never cut Kafka or ClickHouse.**

## 6. AWS Bedrock: verified vs unverified

- **Superseded 2026-11-07 (user):** the Bedrock decision assumed AWS credits; none are currently available. Bedrock is now one candidate provider, not the decision (see §1).
- **UNKNOWN:** AWS region; which models are enabled; IAM permissions; quotas; whether Anthropic models need an access/use-case request. **Nothing is configured as far as the record shows.**
- **Repo state:** no Bedrock/boto3 code or env vars. Current examples use OpenAI-compatible variables.
- **Proposal (not a decision):** Bedrock Converse API with tool-use to get schema-validated structured output; keep the provider behind a thin interface so a stub provider drives tests and demos when Bedrock is unavailable.
- **First step, owned by user, ~0.5 h (estimate):** in the AWS console confirm region and model access, make one successful Converse call, and record region + model ID here.
- Prior provider history (reference implementation only): Gemini 503/429, then OpenRouter; V10 passed, V11 partial. Not a main-repo result.

## 7. Deployment (proposal, not a decision)

**Hosting is UNRESOLVED (2026-11-07):** no AWS credits currently, and local Docker does not satisfy the Nov 25 public deployment link. Earlier proposal: single EC2 instance (≥ ~8 GB RAM, since ClickHouse and Kafka are memory-hungry) running `docker compose`, instead of MSK/ECS. Region, instance, domain/TLS: UNKNOWN. A Dockerfile and a compose profile for the backend, trace-writer and frontend are required (both currently absent).

## 8. Next 10 actions

**All durations are ESTIMATES** (focused hours, single developer with assistant help), not commitments. The total (~80–120 h over 18 days) is tight; the cut order is in §5. This is the one shared plan; it is not split by assistant (§11).

| # | Action | Depends on | Acceptance criteria | Est. |
|---|---|---|---|---|
| 1 | **DONE 2026-11-08** (PRs #2, #3; CI green on `8b34c54`). **Hygiene + CI baseline.** Fix `.env.example` (port 5432 vs compose 5433), correct any README text claiming durable storage, minimal CI running SDK + integration + frontend tests, work on a feature branch | — | CI green on a PR; README matches reality | 2–3 h |
| 2 | **DONE 2026-11-08** (all three healthy, topics created, user's machine; re-verified 2026-11-08 with a Kafka produce/consume round-trip and ClickHouse `SELECT version()`, §3.4). **Compose: Kafka (KRaft) + ClickHouse + Postgres** with healthchecks and a topic init | 1 | `docker compose up` brings all three healthy; documented in `local-development.md` | 2–4 h |
| 3 | **ClickHouse schema + writer** (user writes). *2026-11-08: span-record contract drafted as a PROPOSAL (`docs/proposals/clickhouse-span-record.md`); awaiting the user's answers to its §7 open questions. No schema applied, no writer code.* Storage interface replacing direct `LocalMemoryRepository` use; insert, dedup, read-by-trace. Start with a standalone producer → topic → consumer → ClickHouse proof outside FastAPI | 2 | Tests: identical redelivery = one logical row; conflicting content under the same span identity is **detected and surfaced, not silently merged** (`database.md` §5, `trace-protocol.md` §13.3); out-of-order and late spans stored; canonical `content_hash` is key-order independent; validate the ordering key with a query. *Proposal under test (not a decision):* `ReplacingMergeTree(ingested_at) ORDER BY (project_id, trace_id, span_id, content_hash)`, because the `ORDER BY` columns are the dedup key and must not include `started_at` or omit the hash | 6–10 h |
| 4 | **Durable ingest: `POST /api/v1/traces` (protocol `"1"`) → Kafka producer; trace-writer consumer → ClickHouse** | 3 | Mixed batches split per `(project_id, trace_id)` and keyed by trace; 202 only after **every** message is broker-acked; consumer commits only after CH persist; transient CH failure → retry/backoff without commit; invalid message → DLQ, commit only after the DLQ publish succeeds; injected crash **after insert, before commit** yields one logical row; acknowledged records survive tested process/container restarts with volumes preserved (single broker, RF 1: not disk-loss durable) | 8–12 h |
| 5 | **Durable read API + backend reconstruction** from parent IDs; point `apiRepository.js` at it | 4 | UI shows a run from ClickHouse after full restart; reconstruction tests for missing parent, multiple roots, cycle | 8–12 h |
| 6 | **API-key auth + Postgres `projects`/`api_keys`** with Alembic migration; `project_id` derived from the credential | 4 (parallel with 5) | Invalid/missing key → 401; keys stored hashed; cross-project reads blocked (test) | 6–8 h |
| 7 | **SDK → durable contract:** new exporter target `/api/v1/traces`, API key config, **payload capture + redaction + size policy**, remove loopback lock for the durable mode | 4, 6 | SDK test against the real endpoint; secrets-field redaction test; decision recorded on payload storage | 6–8 h |
| 8 | **Investigator on Bedrock:** provider interface + stub, direct mode, structured output, deterministic grounding (reject unknown span/event IDs), abstention, `analysis_attempts`/`findings`/`finding_evidence` tables | 5, 6, §6 first step | Grounding tests (fabricated ID rejected; recovered retry not flagged; insufficient evidence → abstain); one live Bedrock run recorded | 16–24 h |
| 9 | **Frontend ↔ real findings/evidence/auth;** replace fixture investigation repo and disconnected access adapter | 8, 6 | UI shows grounded findings from the API with working evidence navigation | 8–12 h |
| 10 | **Deploy + e2e + demo:** Dockerfiles, EC2 compose, full run (agent → UI → finding), README/runbook, demo video, submit link | 1–9 | Public URL reachable; e2e script passes on the deployed stack; video recorded by **Nov 25** | 10–16 h |

**Estimated calendar (estimate, not commitment):**
- Nov 7–9: actions 1–3
- Nov 10–12: actions 4–5
- Nov 13–14: viva buffer and rehearsal, merge to main
- Nov 15–22: actions 6–8, with deploy prep begun
- Nov 22–25: actions 9–10

**Viva target (estimate):** actions 1–5 done, so the demo is a real durable slice.

## 9. History (concise; none of this overrides §1–§8)

- **Naming:** original concept "AI Agent Replay & Counterfactual Debugging Platform" → OJT title "AI Agent Execution Debugging & Trace Analysis Platform" → product name **SpanHelix** (2026-10-17; no formal domain/trademark check done).
- **2026-08:** HLD/LLD/database/protocol/analysis docs written for a PostgreSQL-only, deterministic-analysis design. Mentor feedback (08-18): go beyond a log viewer; reconstruction, failure taxonomy, evidence-ranked suspicious steps, controlled failure scenarios. **Superseded** by the September architecture; current design docs replaced it.
- **2026-09:** PRD reviewed/approved (≈09-14/15). Architecture moved to OTel SDK + FastAPI + Kafka + ClickHouse + PostgreSQL + bounded LLM investigator. Viva 09-17 (HLD, technology rationale, PostgreSQL+JSONB vs MongoDB).
- **2026-09-22 / 10-14:** backend and SDK migrated to `uv`; SDK `0.1.0` wheel built.
- **2026-10-16/17 frontend milestones (reported at the time):** 28 → 62 → 79 → 104 → 118 tests (M1, 2A, 2B, 3, 3.1); 4A signup/auth presentation (13 focused tests). All fixture-backed then. Today's measured total: 137 tests passing.
- **2026-10-17 — WITHDRAWN:** an instruction to build the full replay/counterfactual product first was recorded. On 2026-11-07 the user confirmed replay/counterfactual is **out of scope for the OJT MVP**. It must not generate implementation tasks.
- **2026-10-18:** roadmap prioritised backend/SDK/telemetry. **2026-10-22:** local SDK → FastAPI (in-memory) → React demo worked; model I/O absent; this is the current high-water mark of the main repo.
- **Reference implementation (separate AI-generated build; location UNKNOWN):** had Kafka, ClickHouse, PostgreSQL, auth, reconstruction and an investigator. Its numbers (12 runs/6 scenarios, Recall@3 1.0, 0 false positives, p95 ≈476 ms, 2,105-span read ≈1.26 MB/≈236 ms, V10 passed, V11 partial, tests 23→35 backend) are **reference-only, not main-repo results**. Use it to study approaches; never count it as done work.
- **2026-11-07:** full audit, rubric saved, handoff rewritten. Old handoffs archived.

## 10. Discrepancies and unknowns

**Discrepancies found (docs vs code):**
1. Docs specify `/api/v1/traces` + protocol `"1"` + auth; code implements only `/api/v1/local/traces` + `local-1` + loopback gating (§3.3).
2. Docs/handoffs imply durable storage; code has no Kafka/ClickHouse/Alembic dependencies and an in-memory store. Any README claim of a durable ClickHouse/PostgreSQL path is unsupported by the code.
3. SDK `CaptureConfig` defaults to capturing inputs/outputs, but nothing is exported and the backend rejects payload attributes.
4. *(Resolved 2026-11-07: `.env.example` now uses `:5433`.)* `.env.example` pointed to Postgres on `:5432`; `compose.yaml` publishes `:5433`. `config.py` only reads `database_url`; the health route is the only DB consumer.
5. *(`ci.yml` resolved 2026-11-08.)* `backend/Dockerfile`, `db/*`, `analysis/*`, `traces/reconstruction.py`, `routes/analysis.py` and four SDK modules are empty files.
6. Backend reconstruction is documented as a backend responsibility; today it exists only in the frontend.
7. Design docs name an ordering key as a hypothesis; it is unvalidated against real queries.
8. The Claude Project's own instructions describe `handoff.md` as "historical context"; it is now the current-state document. (Project settings text, outside the repo; user to update.)

**Unknowns (do not assume):**
- Exact viva day and its rubric; final OJT submission date.
- Whether the mentor formally confirmed Kafka + ClickHouse as mandatory (user-stated only).
- Bedrock region, enabled models, IAM/quota state.
- Location and current state of the reference implementation.
- Whether the Oct-16/17 frontend work was ever pushed; remote sync status was not re-verified in this rewrite (see audit doc for the branch/HEAD at audit time, and re-run `git status` before relying on it).
- Example agents' own test results (not run).

**Housekeeping note:** the audit left an empty file `.git/stale-maintenance-lock-from-audit` (a renamed stale lock). It is safe for the user to delete.

## 11. Multi-assistant collaboration

This project uses **Claude and ChatGPT** as general-purpose engineering collaborators. Rules (user-confirmed 2026-11-07):

- **No fixed division of labor.** Either assistant may take any task: architecture, coding, debugging, testing, review, research, documentation. No assistant owns a component, and no assistant's output has more authority than the other's.
- **One handoff, one plan.** This file is the single shared context. Do not create assistant-specific handoffs, workflows, implementation plans or task assignments. §8 is the only plan.
- **Sources of truth, in order:** (1) the repository and verified implementation, including tests actually run; (2) the current design docs; (3) confirmed user decisions; (4) this handoff. **Previous assistant responses are not sources of truth** and never override the above.
- **The user has final authority** on project decisions. An assistant may recommend and challenge, then follows the user's decision.
- **Disagreements between assistants:** verify against the repo and docs, not by deferring to whichever replied last. Report the conflict and its evidence to the user; do not silently pick a side.
- **Keeping this file current:** after a change is verified (tests run, behavior observed), update the §3 matrix and §8 status in this file, with the date and the evidence. Record new user decisions in §1 or §6 with the date and label them "user decision". Add a line to §13. Never record a plan, a suggestion or an unverified claim as fact. Do not edit the archived copies or the design docs without an explicit user decision.
- **Starting a session:** read this file, then check the repo (`git status`, recent commits) before relying on §3, since another assistant or the user may have changed it since the last update.

## 12. Working agreements

- **Ownership of learning:** the user writes the core pieces (ClickHouse writer, Kafka consumer, grounding validation); assistants explain, review, and draft routine parts. Explain unfamiliar concepts simply first, then internals, then how they map to SpanHelix.
- **Evidence rules:** investigator findings must cite real span/event IDs validated server-side; never fabricate evidence; abstain when unsupported; separate recorded facts, derived structure, and interpretation; suspicion ≠ proven root cause.
- **Truthfulness:** never claim tests passed unless run; label status with §0 vocabulary; never present reference results as main-repo progress.
- **Change discipline:** small testable increments on feature branches/PRs; no unrelated refactors; do not edit the design docs without an explicit new decision; no secrets in code, docs or logs.
- **Prompts for coding agents:** concise, exact scope and files, acceptance criteria, verification steps.

## 13. Document map and changelog

| Doc | Role |
|---|---|
| `handoff.md` | This file; the only active handoff |
| `HLD.md`, `LLD.md`, `PRD.md`, `database.md`, `trace-protocol.md`, `analysis-engine.md` | Current design authority |
| `ARCHITECTURE_UPDATE_NOTES.md` (2026-09-29) | Change notes behind the current design |
| `local-development.md` | Documents the in-memory local profile only (port 8008/5175) |
| `replay-counterfactual.md` | Future-scope note; not MVP |
| `claude/audit-2026-11-07.md` | Evidence for §3, with the plan and risk detail |
| `claude/ojt-evaluation-rubric.md` | OJT rubric |
| `proposals/clickhouse-span-record.md` | PROPOSAL (not a decision): ClickHouse span columns, draft DDL, dedup/ORDER BY options, writer test list, open questions for action 3 |
| `claude/archive/handoff-2026-11-07-original.md`, `claude/archive/project-handoff-2026-09-22.md` | Archived, historical only (not copied into the repo) |

**Changelog**
- 2026-11-07: Handoff rewritten as the single current-state document; old handoffs archived.
- 2026-11-07: Added §11 multi-assistant collaboration rules (user decision); made the file model-agnostic.
- 2026-11-07: Copied into the repo at `docs/handoff.md` so Claude Code loads it via `CLAUDE.md`. From here the repo copy is authoritative; the claude.ai Project copy is a stale mirror.
- 2026-11-08: Actions 1–2 marked done with evidence (PRs #2/#3, green CI on `8b34c54`; compose Kafka/ClickHouse/Postgres healthy). LLM provider and hosting marked undecided (no AWS credits currently, user 2026-11-07). Actions 3–4 acceptance criteria tightened: conflict detection, insert-before-commit crash test, DLQ commit rule, partial-ack rule, precise durability wording.
- 2026-11-08: Branch `feat/ui-failure-surfacing` (not merged): UI failure surfacing (`first_error` in the local run summary, auto-select, "Error spans", hidden all-unknown columns, mode badge, shared duration format); integration 12 passed, frontend 166 passed (18 files), lint/build pass, manual check at 1440×900 and 1280×800. Compose stack re-verified (§3.4).
- 2026-11-08: Added `claude/proposals/clickhouse-span-record.md` (PROPOSAL for action 3: columns incl. payload states, model/tokens/cost, display_label, graph node IDs, execution_mode, received_at, content_hash; draft DDL parsed in `clickhouse local` 26.8, not applied; dedup and ORDER BY/PARTITION BY options; writer test list; 12 open questions). `database.md`/`LLD.md` unchanged.
