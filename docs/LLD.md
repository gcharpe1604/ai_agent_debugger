# Low-Level Design (LLD)

## AI Agent Execution Debugging & Trace Analysis Platform

## 1. Purpose and Scope

This Low-Level Design defines how the **AI Agent Execution Debugging & Trace Analysis Platform** is implemented.

The surrounding design documents remain authoritative for their respective concerns:

| Document | Responsibility |
|---|---|
| `HLD.md` | System architecture and component boundaries |
| `trace-protocol.md` | Run and Span semantics |
| `database.md` | PostgreSQL persistence model |
| `analysis-engine.md` | Deterministic analysis behavior |
| `LLD.md` | Concrete implementation details |

The LLD defines the implementation of:

- FastAPI modules and endpoints;
- Pydantic, service, repository, and ORM boundaries;
- API-key authentication;
- Run and Span ingestion and lifecycle handling;
- idempotency and canonical hashing;
- transaction and concurrency behavior;
- trace reconstruction;
- analysis orchestration;
- read/debugging APIs;
- Python SDK behavior;
- React JavaScript integration;
- controlled sample-agent integration;
- implementation-level testing boundaries.

The version 1 runtime path is:

```text
AI Agent
   ↓
Python SDK
   ↓
FastAPI
   ↓
Trace Service
   ↓
PostgreSQL
   ↓
Trace Reconstruction
   ↓
Deterministic Analysis
   ↓
Read APIs
   ↓
React JavaScript UI
```

### 1.1 Version 1 Constraints

| Area | Decision |
|---|---|
| Backend | FastAPI modular monolith |
| Validation | Pydantic |
| Database | PostgreSQL |
| ORM | SQLAlchemy 2 async |
| Driver | asyncpg |
| SDK | Python |
| SDK HTTP | HTTPX |
| Frontend | React + JavaScript + Vite |
| Analysis | Synchronous deterministic rules |
| Deployment | Docker-based |

Version 1 does not require Kafka, Redis, Celery, RabbitMQ, Kubernetes, Elasticsearch, microservices, distributed locks, or dedicated analysis workers.

Replay and counterfactual debugging remain future work.


## 2. Application and Module Structure

The implementation follows the existing monorepo structure:

```text
backend/
├── migrations/
├── src/agent_debugger_api/
│   ├── api/
│   │   ├── dependencies.py
│   │   ├── router.py
│   │   └── routes/
│   │       ├── health.py
│   │       ├── ingestion.py
│   │       ├── runs.py
│   │       └── analysis.py
│   ├── traces/
│   │   ├── schemas.py
│   │   ├── repository.py
│   │   ├── service.py
│   │   └── reconstruction.py
│   ├── analysis/
│   │   ├── engine.py
│   │   ├── models.py
│   │   ├── repository.py
│   │   ├── service.py
│   │   └── rules/
│   │       ├── base.py
│   │       ├── explicit_failure.py
│   │       ├── timeout.py
│   │       └── invalid_relationship.py
│   ├── db/
│   │   ├── base.py
│   │   ├── models.py
│   │   └── session.py
│   └── settings.py
├── tests/
└── scripts/create_project_key.py

sdk/python/agent_debugger/
├── __init__.py
├── client.py
├── context.py
├── models.py
└── exporter.py

frontend/src/
├── api/
├── components/
├── features/
└── pages/

examples/refund-agent/
tests/contract/
```

Additional architectural layers such as `ports`, `adapters`, `use_cases`, or separate domain packages are not introduced unless implementation complexity creates a concrete need.

### 2.1 Backend Dependency Direction

Normal request handling follows:

```text
FastAPI Route
     ↓
Service
     ↓
Repository
     ↓
AsyncSession
     ↓
PostgreSQL
```

Responsibilities are separated as follows:

| Layer | Responsibility |
|---|---|
| Routes | HTTP parsing, dependencies, response mapping |
| Services | Lifecycle rules, transactions, orchestration |
| Repositories | Database reads/writes |
| Reconstruction | Pure trace-structure derivation |
| Analysis Engine | Pure deterministic analysis |

Routes must not contain database queries or trace lifecycle logic.

Repositories must not contain HTTP or analysis behavior.

The Analysis Engine must not depend on FastAPI, SQLAlchemy, or PostgreSQL.

### 2.2 Configuration

Configuration is loaded from environment variables through `settings.py`.

Initial settings include:

```text
DATABASE_URL
API_PREFIX=/api/v1
SUPPORTED_PROTOCOL_VERSION=1.0
ANALYSIS_VERSION=1.0
FRONTEND_ORIGINS
```

Operational limits such as request-size or SDK timeout configuration may be added when required.

The repository may contain `.env.example`, but real credentials must not be committed.

### 2.3 Database Session Ownership

FastAPI supplies an `AsyncSession` through dependency injection.

Services own transaction boundaries.

Repositories may execute:

```text
SELECT
INSERT
UPDATE
DELETE
FLUSH
```

but should not independently call `commit()`.

This keeps one logical service operation inside one explicit transaction.


## 3. Core Data Models

The implementation separates:

```text
Protocol / API Models
Database ORM Models
Reconstruction Models
Analysis Models
API Response Models
```

These models may contain overlapping fields but have different responsibilities.

### 3.1 Protocol Models

`traces/schemas.py` contains Pydantic models matching the Trace Protocol.

The main models are:

```text
TraceError
RunRecord
SpanRecord
```

`RunRecord` represents:

```text
protocol_version
run_id
name
status
started_at
ended_at
input
output
error
attributes
```

`SpanRecord` additionally contains:

```text
span_id
parent_span_id
span_type
sequence_no
```

Unknown top-level protocol fields are rejected.

Protocol extensibility belongs inside:

```text
attributes
```

rather than arbitrary new top-level fields.

Exact validation rules remain aligned with `trace-protocol.md`.

### 3.2 Protocol Models vs. ORM Models

Pydantic protocol models and SQLAlchemy models remain separate.

For example:

```text
RunRecord
    → external protocol representation

RunModel
    → PostgreSQL representation
```

Database-only fields such as:

```text
project_id
content_hash
created_at
updated_at
```

must not become part of the external Trace Protocol.

### 3.3 Field Presence

For optional JSON fields, ingestion may need to distinguish:

```text
field omitted
```

from:

```json
{
  "output": null
}
```

Pydantic field-presence metadata such as:

```python
model.model_fields_set
```

may be used while processing lifecycle updates and canonical content.

The persistence behavior is defined further in Section 6.

### 3.4 Stable and Mutable Fields

After first acceptance, Run fields are classified as:

| Run Fields | Behavior |
|---|---|
| `protocol_version`, `run_id`, `name`, `started_at`, `input` | Stable |
| `status`, `ended_at`, `output`, `error`, `attributes` | May be finalized while running |

Span fields are classified as:

| Span Fields | Behavior |
|---|---|
| `protocol_version`, `run_id`, `span_id`, `parent_span_id`, `name`, `span_type`, `sequence_no`, `started_at`, `input` | Stable |
| `status`, `ended_at`, `output`, `error`, `attributes` | May be finalized while running |

For `attributes`:

```text
new keys while running       → allowed
rewrite existing key/value   → rejected
```

Once a Run or Span becomes terminal, the accepted record is immutable except for an equivalent retry.


## 4. API Design and Authentication

All version 1 endpoints use:

```text
/api/v1
```

The same FastAPI application serves ingestion and debugging APIs, but their authentication purposes remain separate.

### 4.1 Ingestion API

| Method | Endpoint | Purpose |
|---|---|---|
| `POST` | `/api/v1/ingest/runs` | Create or update a Run |
| `POST` | `/api/v1/ingest/spans` | Create or update a Span |

Version 1 uses individual Run and Span submissions.

Batch ingestion is a future optimization.

`project_id` is never accepted from the trace payload.

### 4.2 Integration API-Key Authentication

SDK requests send:

```http
Authorization: Bearer <project-api-key>
```

A FastAPI dependency performs:

```text
Bearer Token
    ↓
SHA-256
    ↓
api_keys.key_hash lookup
    ↓
validate active / non-revoked key
    ↓
IntegrationContext
```

`IntegrationContext` contains at least:

```text
api_key_id
project_id
```

The authenticated `project_id` becomes the authoritative owner of all submitted Runs and Spans.

### 4.3 API-Key Generation and Storage

Keys are generated using a cryptographically secure source such as:

```python
secrets.token_urlsafe(32)
```

A recognizable prefix such as:

```text
adbg_
```

may be added.

Only the initial creation flow sees the complete secret.

PostgreSQL stores:

```text
key_prefix
SHA-256(full_api_key)
```

The hash is stored as a lowercase hexadecimal string.

The plain API key is never persisted.

Because these are high-entropy machine-generated credentials rather than user passwords, direct SHA-256 lookup is sufficient for version 1.

### 4.4 Project and Key Provisioning

A public project-management API is not required initially.

A backend command such as:

```text
backend/scripts/create_project_key.py
```

may:

```text
create Project
→ generate key
→ store prefix + hash
→ print the complete key once
```

A management UI may be added later.

### 4.5 Dashboard / Read Authentication Boundary

SDK API keys must never be embedded in the React application.

Version 1 does not introduce:

```text
users
organizations
SSO
RBAC
```

because those entities are outside the current database and project scope.

Therefore, the initial dashboard and read APIs are treated as **deployment-protected developer interfaces**.

For local development they may be accessible only through the local environment.

For any publicly reachable deployment, access to the dashboard and read APIs must be protected by a deployment-level access mechanism before stored traces are exposed.

Public unauthenticated trace-read endpoints are not part of version 1.

A proper human-user authentication system may be introduced later without changing integration API-key authentication.

### 4.6 Main HTTP Responses

| Situation | Status |
|---|---:|
| New record created | `201` |
| Valid lifecycle update | `200` |
| Equivalent retry | `200` |
| Invalid/revoked integration key | `401` |
| Referenced Run missing | `404` |
| Lifecycle/content conflict | `409` |
| Schema/protocol validation failure | `422` |
| Persistence failure | `500` |

Domain errors may include stable machine-readable codes:

```json
{
  "error": {
    "code": "trace_conflict",
    "message": "The stored terminal span conflicts with the submitted span."
  }
}
```

---

## 5. Trace Ingestion and Lifecycle

`TraceService` owns Run and Span lifecycle rules.

The general ingestion flow is:

```text
Authenticate
    ↓
Validate protocol record
    ↓
Load existing state
    ↓
Create / Duplicate / Valid Update / Conflict
    ↓
Persist and commit
    ↓
Acknowledge ingestion
```

The service may return an internal result such as:

```text
CREATED
UPDATED
DUPLICATE
```

Routes convert that result into the appropriate HTTP response.

### 5.1 Run Ingestion

For a new `run_id`:

1. validate the protocol record;
2. associate it with the authenticated `project_id`;
3. compute canonical `content_hash`;
4. insert the Run;
5. commit.

A Run may be submitted initially as either:

```text
running
```

or a terminal status:

```text
success
error
timeout
cancelled
```

For an existing Run, the row is loaded with a PostgreSQL row lock before lifecycle evaluation:

```sql
SELECT ...
FROM runs
WHERE run_id = :run_id
FOR UPDATE
```

The result is determined as follows:

| Existing State | Incoming State | Result |
|---|---|---|
| Same canonical content | Same content | Idempotent duplicate |
| `running` | Allowed enrichment / finalization | Update |
| `running` | Stable-field conflict | `409` |
| Terminal | Equivalent record | Idempotent duplicate |
| Terminal | Materially different record | `409` |

While running, only mutable fields may change:

```text
status
ended_at
output
error
new attribute keys
```

Stable fields and existing attribute values cannot be rewritten.

### 5.2 Span Ingestion

Span ingestion uses the same lifecycle and idempotency rules, with these additional requirements:

```text
Run must already exist
Run must belong to authenticated Project
```

The backend never creates an implicit Run.

The parent Span does **not** need to exist when a child arrives.

Therefore:

```text
child received first
      ↓
accepted

parent received later
      ↓
relationship resolves during reconstruction
```

`parent_span_id` is intentionally not validated as an immediate database parent relationship.

### 5.3 Terminal Run as the Version 1 Trace Boundary

Version 1 treats Run terminalization as the end of normal trace mutation.

The expected SDK sequence is:

```text
Create running Run
      ↓
Record and finalize Spans
      ↓
Finalize Run
      ↓
Automatic analysis
```

After the Run becomes terminal:

| Operation | Behavior |
|---|---|
| Equivalent Run retry | Allowed |
| Equivalent existing Span retry | Allowed |
| Conflicting Run update | Rejected |
| Material existing Span update | Rejected |
| New Span identity | Rejected |

This gives finalized analysis a stable Span set without introducing trace revisions or snapshots.

A Run accepted as terminal on its first submission therefore represents an already-complete execution, including the valid case of a zero-Span Run.

### 5.4 Automatic Analysis Trigger

Automatic analysis is attempted only when a Run becomes terminal for the first time.

Equivalent terminal retries do not start another automatic analysis.

The critical ordering is:

```text
Persist terminal Run
      ↓
COMMIT
      ↓
ingestion is durably successful
      ↓
attempt automatic analysis
```

Analysis runs **after** the trace transaction commits.

The ingestion route must catch failures from this post-commit analysis attempt separately.

Therefore:

```text
trace commit succeeds
+
analysis fails
        ↓
trace ingestion still returns success
```

The analysis attempt should be recorded as `failed` when possible, but it must not roll back or invalidate the accepted trace.

If creation of the Analysis Run itself fails unexpectedly, the failure is logged and ingestion still remains successful.


## 6. Persistence, Transactions, and Canonical Hashing

PostgreSQL is the source of truth for accepted trace state.

Repositories perform database operations; services decide whether those operations are valid.

### 6.1 Repository and Transaction Responsibilities

`TraceRepository` provides operations such as:

```text
get_run()
get_run_for_update()
insert_run()
update_run()

get_span()
get_span_for_update()
insert_span()
update_span()

list_runs()
list_spans_for_run()
find_spans_by_ids()
```

Repositories do not decide lifecycle semantics.

A normal mutation uses one service-controlled transaction:

```python
async with session.begin():
    existing = await repository.get_for_update(...)
    # validate lifecycle
    # insert or update
```

The complete:

```text
load
→ compare
→ validate
→ mutate
```

operation occurs inside the same transaction.

A successful ingestion acknowledgement is returned only after commit.

### 6.2 Canonical Content Hash

Each accepted Run and Span stores:

```text
content_hash
```

representing its complete accepted **protocol content**.

Database-only metadata is excluded:

```text
project_id
content_hash
created_at
updated_at
```

Canonicalization follows:

```text
Validated protocol state
      ↓
normalize datetimes to UTC
      ↓
normalize JSON-compatible values
      ↓
sort object keys
      ↓
compact UTF-8 JSON
      ↓
SHA-256
```

A consistent UTC timestamp representation is used, for example:

```text
2026-08-25T10:20:30.123000Z
```

Canonical JSON behavior is equivalent to:

```python
json.dumps(
    value,
    sort_keys=True,
    separators=(",", ":"),
    ensure_ascii=False,
    allow_nan=False,
)
```

Arrays preserve their order.

`NaN`, positive infinity, and negative infinity are rejected because they are not valid JSON protocol values.

The resulting UTF-8 bytes are hashed with SHA-256 and stored as a lowercase hexadecimal digest.

### 6.3 Updates and Hashing

For an allowed update, the backend hashes the **resulting accepted record**, not only the submitted changed fields.

```text
Stored accepted state
        +
allowed incoming changes
        ↓
resulting complete state
        ↓
canonicalize
        ↓
new content_hash
```

This means `content_hash` always represents the current complete accepted record.

For a duplicate request:

```text
incoming canonical hash
==
stored content_hash
```

provides the fast equivalence check.

### 6.4 Missing Field vs. Explicit JSON Null

Where protocol semantics require it, the implementation preserves the difference between:

```text
field omitted
```

and:

```json
{
  "output": null
}
```

Pydantic field-presence metadata is retained during request processing.

For JSONB persistence:

```text
omitted optional value
    → SQL NULL / absent protocol value

explicit JSON null
    → JSONB null
```

A small serialization/deserialization helper should isolate this behavior.

Contract and PostgreSQL integration tests must verify it.

Version 1 does not introduce additional presence columns unless implementation testing shows they are necessary.


## 7. Trace Reconstruction

Trace Reconstruction derives a safe deterministic execution structure from the persisted Run and Spans.

It never modifies recorded trace data.

### 7.1 Reconstruction Result

Conceptually:

```text
ReconstructedTrace
├── run
├── spans_by_id
├── ordered_spans
├── roots
├── children_by_parent
├── display_parent_by_span
└── structural_problems
```

The reconstruction is created in memory when required by analysis or read APIs.

No reconstruction table or graph cache is stored in version 1.

### 7.2 Relationship Resolution

The algorithm first builds:

```python
spans_by_id = {span.span_id: span for span in spans}
```

Each Span relationship is then classified:

| Condition | Reconstruction Result |
|---|---|
| `parent_span_id is null` | Root |
| `parent_span_id == span_id` | `self_parent` |
| Parent exists in same Run | Candidate valid edge |
| Parent ID exists in another Run | `cross_run_parent` |
| Parent ID exists nowhere | `missing_parent` |

Unresolved parent IDs should be collected and checked with one repository query rather than one query per Span.

### 7.3 Cycle Detection

Because each Span has at most one parent, cycle detection may use DFS states:

```text
WHITE = unvisited
GRAY  = currently visiting
BLACK = complete
```

Encountering a `GRAY` Span identifies a cycle.

Example:

```text
A → B → C → A
```

The detected cycle members are recorded in `structural_problems`.

Traversal must terminate safely even when the stored relationships are malformed.

### 7.4 Safe Display Structure

Original `parent_span_id` values are never rewritten.

Instead, reconstruction creates a safe derived hierarchy for UI traversal.

For:

```text
missing parent
cross-Run parent
self-parent
```

the affected Span is detached only in the derived display structure and exposed as a root.

For a cycle, one derived edge is removed so traversal cannot loop forever.

The Span appearing earliest in deterministic execution order is used as the cycle break point.

The original relationships and cycle membership remain preserved in `structural_problems`.

### 7.5 Deterministic Ordering

Spans are ordered by:

```text
1. started_at ascending
2. sequence_no ascending
3. span_id ascending
```

When timestamps are equal and one Span has no `sequence_no`, a present sequence number sorts before the missing value.

This ordering supports:

```text
stable UI rendering
analysis ranking tie-breaking
repeatable reconstruction
deterministic tests
```

It is an ordering rule, not a causal claim.

Multiple valid roots are returned directly; reconstruction does not invent a synthetic root Span.


## 8. Trace Analysis Execution

The low-level implementation follows the deterministic behavior defined in `analysis-engine.md`.

### 8.1 Component Boundary

The execution path is:

```text
AnalysisService
      ↓
load persisted Run / Spans
      ↓
Trace Reconstruction
      ↓
AnalysisEngine
      ↓
AnalysisRepository
```

`AnalysisEngine` is pure Python and must not:

```text
query PostgreSQL
write database rows
call external APIs
call an LLM
mutate Runs or Spans
```

### 8.2 Analysis Lifecycle

One analysis attempt follows:

```text
Create Analysis Run
status = running
      ↓
commit
      ↓
Reconstruct trace
      ↓
execute enabled rules
      ↓
collect findings
      ↓
score and rank
      ↓
persist findings
+
mark Analysis Run completed
      ↓
commit
```

Creating the Analysis Run before reconstruction allows failures during reconstruction or rule execution to be represented.

If analysis fails after the Analysis Run exists:

```text
analysis_run.status = failed
analysis_run.error = diagnostic information
```

is persisted in a recovery transaction.

### 8.3 Atomic Finding Completion

Findings and successful completion are persisted together.

Conceptually:

```text
BEGIN
    insert findings
    mark analysis_run = completed
COMMIT
```

A completed Analysis Run must therefore never represent an unknown partial set of findings.

Unexpected rule, reconstruction, scoring, ranking, or persistence failure causes the Analysis Run to fail instead.

### 8.4 Rule Execution and Ranking

Version 1 uses an explicit registry.

Protected core:

```text
explicit_failure
explicit_timeout
invalid_relationship
```

`retry_exhausted` is added after the protected core is stable.

Every rule receives the same immutable `ReconstructedTrace`.

Rules first produce finding drafts.

After all rules finish:

```text
Finding Drafts
      ↓
group by suspicious_span_id
      ↓
Span score = max finding score
      ↓
sort suspicious Spans
      ↓
assign Span ranks
      ↓
apply rank to findings
```

Ranking uses:

```text
1. suspicion score descending
2. reconstruction execution position ascending
3. span_id ascending
```

Run-level findings use:

```text
rank = null
```

Registry execution order must not affect final rank.

### 8.5 Finding Persistence Validation

Before persisting a non-null:

```text
suspicious_span_id
```

the service verifies that the referenced Span belongs to the same Run being analyzed.

This prevents a globally valid Span foreign key from accidentally linking a finding to another execution.

### 8.6 Controlled Profiles

Generic Runs receive generic deterministic rules only.

For explicitly configured controlled sample workflows:

```text
generic rules
+
applicable controlled profile
```

may be used.

The controlled profile may contain known workflow constraints, but evaluation ground truth remains separate.

The engine must not receive the expected suspicious Span or expected grading result used to evaluate its output.

---

## 9. Read and Debugging APIs

The read path supports the developer debugging workflow rather than general analytics.

### 9.1 Initial Endpoints

| Method | Endpoint | Purpose |
|---|---|---|
| `GET` | `/api/v1/health` | Service health |
| `GET` | `/api/v1/runs` | List Runs |
| `GET` | `/api/v1/runs/{run_id}` | Run details |
| `GET` | `/api/v1/runs/{run_id}/trace` | Reconstructed trace |
| `GET` | `/api/v1/runs/{run_id}/analyses` | Analysis history |
| `GET` | `/api/v1/runs/{run_id}/analysis/latest` | Latest analysis attempt |
| `POST` | `/api/v1/runs/{run_id}/analyses` | Optional manual re-analysis |

Manual re-analysis is not required for the first vertical slice.

Read APIs follow the deployment-protection boundary defined in Section 4 and must not expose stored traces through unauthenticated public endpoints.

### 9.2 Run Explorer

`GET /runs` initially supports:

```text
limit
offset
status
```

Default ordering:

```text
started_at DESC
run_id ASC
```

A default page size such as `50` is sufficient for version 1.

Cursor pagination and generalized search are unnecessary initially.

The response contains summary information required by the Run Explorer, such as:

```text
run_id
name
status
started_at
ended_at
duration
```

### 9.3 Run and Trace Detail

`GET /runs/{run_id}` returns the recorded Run without embedding derived analysis into the Run object.

`GET /runs/{run_id}/trace` returns the reconstructed execution.

Conceptually:

```json
{
  "run": {},
  "spans": [],
  "roots": [],
  "children_by_parent": {},
  "structural_problems": []
}
```

Spans are returned in deterministic reconstruction order.

The backend supplies the safe reconstructed structure so the frontend does not independently repair missing parents, cycles, or cross-Run relationships.

### 9.4 Analysis Responses

The latest-analysis endpoint returns analysis metadata and findings:

```json
{
  "analysis_run_id": "...",
  "analysis_version": "1.0",
  "status": "completed",
  "started_at": "...",
  "completed_at": "...",
  "findings": []
}
```

A failed analysis remains distinct from the trace:

```json
{
  "status": "failed",
  "findings": [],
  "error": {}
}
```

The Run and trace remain readable even when analysis is unavailable.

### 9.5 Frontend Read Pattern

A Run detail page may load:

```text
GET /runs/{run_id}
GET /runs/{run_id}/trace
GET /runs/{run_id}/analysis/latest
```

in parallel.

This keeps:

```text
recorded execution
```

independent from:

```text
derived analysis
```


## 10. Python SDK Design

The Python SDK is the developer-facing instrumentation layer that converts agent execution into Trace Protocol records and exports them to the backend.

### 10.1 SDK Structure

```text
agent_debugger/
├── __init__.py
├── client.py
├── context.py
├── models.py
└── exporter.py
```

| Module | Responsibility |
|---|---|
| `client.py` | Public instrumentation API |
| `context.py` | Current Run/Span context and sequence state |
| `models.py` | SDK-side protocol records |
| `exporter.py` | HTTP transport, retries, fail-open behavior |

### 10.2 Developer API

The initial SDK should expose a small context-manager API.

Example:

```python
from agent_debugger import Debugger

debugger = Debugger(
    base_url="https://debugger.example.com",
    api_key="..."
)

with debugger.run(
    "refund_request",
    input={"order_id": "ORD-1042"},
) as run:
    with run.span(
        "retrieve_refund_policy",
        span_type="retrieval",
    ) as span:
        result = retrieve_policy()
        span.set_output(result)
```

Convenience APIs may evolve as long as emitted records continue to follow the Trace Protocol.

### 10.3 Identifier and Context Management

The SDK generates opaque globally unique IDs, for example:

```text
run_<UUID4>
span_<UUID4>
```

No execution meaning is encoded in identifiers.

Python `ContextVar` stores the current Run and Span context.

For nested instrumentation:

```text
current Span
    ↓
new Span.parent_span_id
```

An explicit parent override may be added when required.

Each Run context also maintains a local `sequence_no` counter.

```text
new Span
   ↓
allocate next sequence number
```

The counter is only an ordering hint and does not establish causality.

Concurrent sequence allocation must avoid duplicate values within one locally instrumented Run.

### 10.4 Run and Span Lifecycle

Context-manager behavior is:

| Event | Recorded Behavior |
|---|---|
| Enter Run/Span | Create ID, record `started_at`, set `running`, export initial record |
| Normal exit | Set `success`, record `ended_at`, export final state |
| Uncaught exception | Set `error`, capture structured error, export final state, re-raise exception |
| Explicit timeout | Set `timeout` only when timeout is actually known |

Instrumentation must not infer timeout from duration alone.

The SDK must not swallow the application's original exception.

### 10.5 Run Completion Ordering

The version 1 exporter is synchronous.

Normal SDK execution should therefore produce:

```text
Run starts
   ↓
Spans start / complete
   ↓
all intended Span final states exported
   ↓
Run terminal state exported
```

This ordering supports the backend rule that terminalizing the Run closes normal trace mutation.

Asynchronous batching and buffered background export remain future extensions.

### 10.6 HTTP Export

HTTPX sends records to:

```text
Run  → POST /api/v1/ingest/runs
Span → POST /api/v1/ingest/spans
```

Each request contains:

```http
Authorization: Bearer <project-api-key>
Content-Type: application/json
```

### 10.7 Fail-Open and Retry Behavior

Debugger transport failure must not normally fail the observed application.

```text
export failure
    ↓
record/log instrumentation problem
    ↓
application continues
```

This includes backend outages, network failures, authentication rejection, and trace validation rejection where the SDK can safely continue.

Retries are bounded.

| Failure | Retry? |
|---|---|
| Connection failure | Yes |
| `429` | Yes |
| `5xx` | Yes |
| `401` | No |
| `404` | No |
| `409` | No |
| `422` | No |

A conservative default is no more than **three total attempts per export**, using a short exponential delay for transient failures.

There is no unbounded retry loop.


## 11. Frontend and Controlled Sample Agent

The frontend provides the developer debugging interface, while the refund sample agent validates the platform through the same SDK boundary available to external users.

### 11.1 Frontend Structure

The frontend uses React, JavaScript, and Vite.

A practical initial structure is:

```text
src/
├── api/
│   └── client.js
├── features/
│   ├── runs/
│   ├── trace/
│   └── analysis/
├── components/
└── pages/
```

React state and hooks are sufficient initially.

Redux or another global-state library is added only if implementation complexity demonstrates a real need.

### 11.2 Debugging Interface

The protected developer workflow is:

```text
Run Explorer
     ↓
Run Detail
     ↓
Trace Timeline / Tree
     ↓
Step Inspector
     ↓
Findings and Evidence
```

The initial UI should prioritize a readable timeline or nested tree.

React Flow or another graph library is optional after the core inspection workflow works correctly.

### 11.3 Run Explorer and Step Inspector

The Run Explorer displays concise execution information such as:

```text
Run name
Run ID
status
start time
duration
```

Initial filtering may be limited to status.

Selecting a Span opens the Step Inspector with recorded information such as:

```text
name
span_type
status
started_at / ended_at
input
output
error
attributes
parent relationship
```

Missing information remains visibly missing rather than being interpreted as failure.

### 11.4 Findings and Suspicious Steps

Analysis results are displayed separately from recorded trace fields.

A suspicious Span may show:

```text
Rank #1
Suspicion score: 90
Rule: explicit_failure
Category: TOOL_EXECUTION_ERROR
Severity: HIGH
```

The UI must not convert the score into language such as:

```text
90% probability of root cause
```

because the score is only a deterministic investigation-priority heuristic.

If analysis fails:

```text
trace view      → remains available
analysis panel  → shows analysis unavailable / failed
```

The page must not become unusable because analysis failed.

### 11.5 Controlled Refund Agent

The refund sample agent behaves as an external consumer of the platform.

It must interact through:

```text
Refund Agent
     ↓
Python SDK
     ↓
HTTP
     ↓
FastAPI Backend
```

It must not directly import backend repositories, ORM models, or analysis rules.

This validates the actual developer integration path rather than bypassing it during demonstrations.

### 11.6 Controlled Scenarios

The initial evaluation set should remain small and deterministic.

Representative scenarios include:

| Scenario | Purpose |
|---|---|
| Healthy execution | Verify no unsupported failure finding |
| Explicit tool failure | Validate `explicit_failure` |
| Explicit timeout | Validate timeout detection |
| Malformed relationship | Validate structural analysis |
| Retry exhaustion/recovery example | Validate explicit retry metadata behavior |
| One known-contract failure | Validate controlled expected-vs-actual analysis |

The exact final set may contain roughly three to five injected failure scenarios plus a healthy baseline.

Failure injection configuration belongs to the sample agent.

Evaluation ground truth remains separate from the trace and controlled profile supplied to the Analysis Engine.

---

## 12. Error Handling, Concurrency, and Edge Cases

Version 1 uses application-level exceptions, PostgreSQL transactions, row locking, and idempotency rather than distributed coordination.

### 12.1 Application Errors

Services may raise domain exceptions such as:

```text
AuthenticationError
RunNotFoundError
TraceConflictError
UnsupportedProtocolError
AnalysisExecutionError
```

Routes or global FastAPI exception handlers translate these into HTTP responses.

Lifecycle and persistence decisions remain inside services rather than being duplicated across routes.

### 12.2 Concurrency and Duplicate Handling

Potentially mutating Run and Span requests load the existing row using:

```sql
SELECT ...
FOR UPDATE
```

This serializes competing lifecycle updates for the same record.

The main behaviors are:

| Situation | Version 1 Behavior |
|---|---|
| Two equivalent terminal updates | First commits; second becomes idempotent success |
| Two conflicting terminal updates | First commits; second receives `409` |
| Duplicate request after lost HTTP response | Same ID + same canonical hash → success |
| Span references missing Run | Reject; no implicit Run creation |
| Child arrives before parent | Accept |
| Parent never arrives | Reconstruction reports missing parent |
| Parent belongs to another Run | Reconstruction reports cross-Run parent |
| Run/Span remains `running` | Preserve as running; do not infer failure |
| Trace persistence fails | Roll back and return server failure |
| Analysis fails after trace commit | Preserve trace; mark analysis failed when possible |
| Equivalent terminal retry | Accept |
| Material terminal mutation | Reject |

No distributed lock is required because PostgreSQL is the single source of truth in version 1.

### 12.3 Trace Persistence Failure

If a trace transaction fails:

```text
ROLLBACK
   ↓
do not acknowledge persistence
   ↓
return server error
```

The SDK may retry transient failures according to its bounded fail-open policy.

### 12.4 Analysis Failure

Analysis is derived processing and remains independent from trace durability.

```text
Trace commit succeeds
        ↓
analysis attempt fails
        ↓
trace remains accepted
analysis_run → failed when possible
frontend → trace still inspectable
```

A post-commit analysis exception must not cause the ingestion endpoint to report that trace persistence failed.

### 12.5 Exactly-Once Boundary

Version 1 does not implement distributed exactly-once delivery.

Instead it relies on:

```text
stable Run / Span identity
+
database uniqueness
+
canonical content comparison
+
safe retries
```

This provides practical idempotent ingestion for the supported SDK integration model.


## 13. Testing Strategy

Testing is organized by component responsibility.

The goal is to verify protocol behavior, database semantics, reconstruction, deterministic analysis, and the real SDK-to-backend integration path without depending on real LLM calls.

### 13.1 Test Matrix

| Area | Important Tests |
|---|---|
| Protocol models | Status/type validation, timestamps, terminal `ended_at`, `sequence_no`, JSON-compatible values, protocol version |
| Field presence | Omitted optional field vs explicit JSON `null` |
| Canonical hashing | Object-key ordering, timezone normalization, changed content, deterministic SHA-256 |
| Run lifecycle | Create, enrich, terminalize, equivalent retry, stable-field conflict, terminal mutation |
| Span lifecycle | Same lifecycle cases plus Run-before-Span |
| Attributes | New key while running allowed; existing value rewrite rejected |
| PostgreSQL | JSONB, TIMESTAMPTZ, foreign keys, row locking, SQL NULL vs JSON null |
| Concurrency | Equivalent and conflicting simultaneous terminal updates |
| Reconstruction | Single/multiple roots, missing parent, self-parent, cross-Run parent, cycle |
| Ordering | Same timestamps, optional `sequence_no`, deterministic tie-breaking |
| Analysis rules | Explicit failure, timeout, invalid relationship, later retry exhaustion |
| Ranking | Score → execution position → `span_id` |
| API-key auth | Valid, invalid, revoked, Project ownership |
| SDK contract | SDK-generated Run/Span accepted by backend |
| End-to-end | Sample agent → SDK → API → PostgreSQL → reconstruction → analysis → read API |

### 13.2 PostgreSQL Integration Tests

Database-specific behavior should use a real PostgreSQL test instance rather than relying only on SQLite.

This is required for behavior such as:

```text
JSONB
TIMESTAMPTZ
SELECT ... FOR UPDATE
foreign keys
SQL NULL vs JSON null
concurrent transactions
```

### 13.3 Reconstruction Tests

At minimum, reconstruction tests should cover:

```text
single root
multiple roots
nested hierarchy
child before parent
missing parent
self-parent
cross-Run parent
cycle
same started_at
missing sequence_no
deterministic repeated reconstruction
```

Malformed relationships must never cause infinite traversal.

### 13.4 Analysis Tests

Each deterministic rule receives focused unit tests.

Examples:

```text
explicit_failure
    status=error      → finding
    status=success    → no finding

explicit_timeout
    status=timeout    → finding
    high latency only → no timeout finding

invalid_relationship
    supported structural problem
        → finding
```

Ranking tests verify deterministic ordering and ensure rule-registry order does not affect final suspicious-step rank.

### 13.5 SDK / Backend Contract Tests

`tests/contract/` verifies that both sides follow the same Trace Protocol.

Conceptually:

```text
SDK record
   ↓
serialize
   ↓
FastAPI / Pydantic validation
   ↓
accepted
```

Important contract cases include:

```text
Run creation
Span creation
running → terminal update
attributes
errors
retry metadata
JSON null / omission
timestamps
```

### 13.6 End-to-End and Controlled Evaluation

The primary system test follows:

```text
Controlled Refund Agent
        ↓
Python SDK
        ↓
FastAPI
        ↓
PostgreSQL
        ↓
Reconstruction
        ↓
Analysis
        ↓
Read API
```

Controlled scenarios verify expected findings and suspicious-step ranking.

Tests should use deterministic stubs wherever possible.

Real LLM calls may be used for demonstrations later but are not required for the repeatable automated test suite.


## 14. Key Low-Level Decisions and References

### 14.1 Version 1 Implementation Decisions

| Area | Decision |
|---|---|
| Backend | FastAPI modular monolith |
| Database | PostgreSQL |
| ORM | SQLAlchemy 2 async + asyncpg |
| Route responsibility | HTTP only |
| Business logic | Services |
| Persistence operations | Repositories |
| Transaction owner | Service |
| Trace submission | Individual Run / Span requests |
| Project ownership | Authenticated integration context |
| Integration credential | Project-scoped bearer API key |
| Stored API key | Prefix + SHA-256 hash |
| Run before Span | Required |
| Parent before child | Not required |
| Idempotency | Stable ID + canonical `content_hash` |
| Content hash | SHA-256 |
| Canonical JSON | Sorted compact UTF-8 JSON |
| Timestamp canonicalization | UTC |
| Concurrent lifecycle updates | PostgreSQL row locking |
| Stable-field mutation | Rejected |
| Terminal record mutation | Rejected |
| Terminal Run | Version 1 trace-finalization boundary |
| Reconstruction | Derived in memory |
| Malformed relationships | Preserved as evidence; safe derived display structure |
| Reconstruction persistence | None |
| Analysis | Synchronous deterministic rules |
| Automatic analysis | First terminal Run transition |
| Analysis failure | Does not invalidate ingestion |
| Analysis Run creation | Before reconstruction |
| Finding completion | Findings + completed status persisted atomically |
| Rule registry | Explicit |
| Suspicious ranking | Score → execution position → `span_id` |
| SDK exporter | Synchronous |
| SDK behavior on exporter failure | Fail-open |
| SDK retries | Bounded |
| Frontend | React + JavaScript + Vite |
| Frontend state | React hooks/state initially |
| Trace visualization | Simple tree/timeline first |
| Sample agent | External SDK consumer |
| Automated tests | Deterministic; no required real LLM calls |
| Exactly-once delivery | Not required |
| Queue/worker infrastructure | Not required |
| Replay/counterfactual | Future |

### 14.2 End-to-End Runtime Flow

```text
Developer Agent
      ↓
Python SDK
      ↓
Run / Span Protocol Records
      ↓
HTTPS + Project API Key
      ↓
FastAPI
      ↓
Trace Service
      ↓
PostgreSQL
      ↓
Trace Reconstruction
      ↓
Deterministic Analysis
      ↓
Analysis Findings
      ↓
Read APIs
      ↓
React JavaScript Debugging UI
      ↓
Developer Investigation
```

### 14.3 References

The implementation is governed by the following project documents:

| Document | Responsibility |
|---|---|
| [`HLD.md`](./HLD.md) | Overall architecture and system boundaries |
| [`trace-protocol.md`](./trace-protocol.md) | Run and Span execution contract |
| [`database.md`](./database.md) | PostgreSQL schema and persistence semantics |
| [`analysis-engine.md`](./analysis-engine.md) | Deterministic findings, evidence, scoring, and ranking |
| [`future/replay-counterfactual.md`](./future/replay-counterfactual.md) | Future replay and counterfactual direction |

The current project does **not** require separate `testing.md`, `scope.md`, or `development-plan.md` documents for this design to be complete.

The implementation principle remains:

```text
Record execution facts
        ↓
persist them safely
        ↓
reconstruct without rewriting them
        ↓
analyze deterministically
        ↓
present evidence
        ↓
developer performs final investigation
```