# ClickHouse span record — DECISION

**Status: DECISION (user decision 2026-11-12). Docs only: no code written, nothing applied to the ClickHouse or Kafka server.**
**Exception: §9 (payload capture policy) is a PROPOSAL, written 2026-11-16, not yet approved.**
Names: ClickHouse database `telemetry`, table `telemetry.telemetry_spans`. Kafka topic `agentdbg.traces.v1` (3 partitions) and DLQ `agentdbg.traces.v1.dlq` (1 partition). The `agentdbg` prefix is an identifier only, not an approved product name.
This file is the contract for the ClickHouse writer and Kafka consumer, which the user writes. `database.md` and `LLD.md` are not edited. Where they differ (the `database.md` §5.2 ordering-key hypothesis, the run-list table), this decision governs the implementation (§7).

Sources: `LLD.md` §5–6, `database.md` §3, §5, §8, §11, `trace-protocol.md` §5, §10, §11, §13, handoff §8 action 3.

**Checked so far, and only this:** on 2026-11-08 the *earlier draft* DDL parsed and created in `clickhouse local` 26.8.36.3 (in-process, not the compose server). A smoke check of option A with 4 inserts collapsed an equivalent redelivery to 1 physical row after `OPTIMIZE … FINAL` and kept 2 rows for a same-ID/different-hash pair. **2026-11-13: the §2 DDL as written (after the 2026-11-12 edit) was created on the compose ClickHouse server 26.8 in a throwaway database `scratch_ddl_check`: no errors, 40 columns, `SHOW CREATE TABLE` matched the DDL (ClickHouse added only the default `SETTINGS index_granularity = 8192`); the scratch database was then dropped.** `telemetry` was not touched and no data was inserted, so this checks syntax and types only, not dedup behaviour. The §6 tests are not written.

---

## 0. Five ClickHouse ideas you need first

1. **Column store.** Each column is stored in its own file. A query that reads `span_name, status_code` never touches the payload columns, so big payloads in the same table cost disk, not read time, unless you select them.
2. **Parts and merges.** Each `INSERT` writes an immutable *part*: a sorted chunk of rows. A background process later *merges* small parts into bigger ones. You don't control when merges happen.
3. **Sorting key (`ORDER BY`).** Rows inside each part are sorted by it. ClickHouse keeps a *sparse index*: one entry per ~8,192 rows (a *granule*). A query whose `WHERE` matches a **prefix** of the sorting key skips most granules. A filter on a column that isn't a prefix scans much more.
4. **ReplacingMergeTree.** It's a MergeTree that, **during merges**, keeps only one row per identical sorting key. That makes it "eventually deduplicated": before a merge, duplicates are still visible. It also only deduplicates rows **in the same partition**.
5. **Partitions (`PARTITION BY`).** They split data into separate directories, mainly for dropping or expiring old data. They aren't a speed feature, and too many partitions hurt. This table has none (§4).

Everything below follows from those five.

---

## 1. Logical columns

**Plain version:** one row per ended span. The row holds the identity (`project_id`, `trace_id`, `span_id`), what ran, when, how it ended, what was captured (and *why* something wasn't), plus receipt metadata. A few fields are promoted from `attributes` into real columns because queries filter on them.

| Column | Type | Why / source | LLD §6.2 item |
|---|---|---|---|
| `project_id` | `UUID` | Derived server-side from the credential, never from the client | project_id |
| `trace_id` | `FixedString(32)` lowercase hex | Run ID (one Run = one trace) | trace_id |
| `span_id` | `FixedString(16)` lowercase hex | Span identity | span_id |
| `parent_span_id` | `Nullable(FixedString(16))` | `NULL` = root. A missing parent is kept, not rejected | parent_span_id |
| `service_name` | `LowCardinality(String)` | Resource `service.name` | service_name |
| `operation_type` | `LowCardinality(String)` | run/agent/model/retrieval/tool/api/state/custom, validated by the API | operation_type |
| `span_name` | `String` | OTel span name | span_name |
| `display_label` | `String DEFAULT ''` | Short label that tells repeated operations apart (tool `pay`, evidence source `policy-kb`) | attributes (promoted) |
| `execution_mode` | `LowCardinality(String) DEFAULT ''` | `live` / `controlled`; today only the root span carries it | attributes (promoted) |
| `graph_node_id`, `graph_node_parent_id` | `String DEFAULT ''` | Workflow-graph node (e.g. LangGraph) and its graph parent. **Not** span parentage; never used for the tree | links/relationships |
| `status_code` | `Enum8('UNSET'=0,'OK'=1,'ERROR'=2)` | OTel status | status |
| `status_description` | `String DEFAULT ''` | OTel status text | status |
| `error_type` | `LowCardinality(String) DEFAULT ''` | First `exception.type`; promoted for "find errors" | error data |
| `started_at`, `ended_at` | `DateTime64(9,'UTC')` | Nanosecond OTel times | started_at, ended_at |
| `duration_ns` | `UInt64` | `ended_at − started_at`, computed by the writer (the API already rejects reversed times) | duration |
| `attempt`, `retry_of_span_id` | `Nullable(UInt16)`, `Nullable(FixedString(16))` | Promoted from `debugger.attempt` / `debugger.retry_of` for "find retries" | attributes (promoted) |
| `model`, `provider` | `LowCardinality(Nullable(String))` | `NULL` = not recorded | attributes (promoted) |
| `input_tokens`, `output_tokens`, `total_tokens` | `Nullable(UInt32)` | `NULL` ≠ 0 | attributes (promoted) |
| `cost` | `Nullable(Decimal(18,9))` | `NULL` unless the span supplies a cost. Never computed by the writer (§7 D10) | attributes (promoted) |
| `input_state`, `output_state`, `error_state` | `Enum8('captured','disabled','redacted','truncated','unavailable')` | Says *why* a payload is empty or partial. The UI must never infer it from an empty string | input/output/error data |
| `input_payload`, `output_payload`, `error_payload` | `String DEFAULT '' CODEC(ZSTD(3))` | Bounded serialized JSON, redacted before export | input/output/error data |
| `attributes` | `Map(String, String)` | Remaining flexible attributes; values stringified | attributes |
| `events` | `Array(Tuple(name, time, attributes))` | Span events incl. exceptions; kept on the span (`database.md` §5.4) | events |
| `links` | `Array(Tuple(trace_id, span_id, relation))` | OTel links / `depends_on`, `handoff_from`, `consumes`, `retry_of` | links |
| `protocol_version` | `LowCardinality(String)` | Envelope version (`"1"`) | receive metadata |
| `received_at` | `DateTime64(3,'UTC')` | FastAPI receipt time (per envelope) | receive metadata |
| `persisted_at` | `DateTime64(3,'UTC') DEFAULT now64(3)` | Insert time | persist metadata |
| `kafka_partition`, `kafka_offset` | `UInt16`, `UInt64` | Where the writer read it. Debugging only | persist metadata |
| `content_hash` | `FixedString(64)` lowercase hex SHA-256 | Fingerprint of the immutable content, computed by the writer (§5) | content hash |

**Payload states, simply:** `captured` = stored as given; `disabled` = capture switched off; `redacted` = removed by a secret rule; `truncated` = cut at the size limit (the stored prefix is real but partial); `unavailable` = not produced or lost. Each payload carries its own state, so "the output was truncated but the error was captured" is representable.

---

## 2. DDL (decided; not applied)

The writer's schema bootstrap must run `CREATE DATABASE IF NOT EXISTS telemetry`; do not rely on `CLICKHOUSE_DB`, which the image only applies on an empty volume.

```sql
-- DECISION 2026-11-12. Not applied to `telemetry`. Parsed and created in a scratch database on 2026-11-13 (see header).
CREATE TABLE IF NOT EXISTS telemetry.telemetry_spans
(
    project_id            UUID,
    trace_id              FixedString(32),
    span_id               FixedString(16),
    parent_span_id        Nullable(FixedString(16)),
    content_hash          FixedString(64),

    service_name          LowCardinality(String),
    operation_type        LowCardinality(String),
    span_name             String,
    display_label         String DEFAULT '',
    execution_mode        LowCardinality(String) DEFAULT '',
    graph_node_id         String DEFAULT '',
    graph_node_parent_id  String DEFAULT '',

    status_code           Enum8('UNSET' = 0, 'OK' = 1, 'ERROR' = 2),
    status_description    String DEFAULT '',
    error_type            LowCardinality(String) DEFAULT '',
    started_at            DateTime64(9, 'UTC'),
    ended_at              DateTime64(9, 'UTC'),
    duration_ns           UInt64,
    attempt               Nullable(UInt16),
    retry_of_span_id      Nullable(FixedString(16)),

    model                 LowCardinality(Nullable(String)),
    provider              LowCardinality(Nullable(String)),
    input_tokens          Nullable(UInt32),
    output_tokens         Nullable(UInt32),
    total_tokens          Nullable(UInt32),
    cost                  Nullable(Decimal(18, 9)),

    input_state           Enum8('captured' = 1, 'disabled' = 2, 'redacted' = 3, 'truncated' = 4, 'unavailable' = 5),
    input_payload         String DEFAULT '' CODEC(ZSTD(3)),
    output_state          Enum8('captured' = 1, 'disabled' = 2, 'redacted' = 3, 'truncated' = 4, 'unavailable' = 5),
    output_payload        String DEFAULT '' CODEC(ZSTD(3)),
    error_state           Enum8('captured' = 1, 'disabled' = 2, 'redacted' = 3, 'truncated' = 4, 'unavailable' = 5),
    error_payload         String DEFAULT '' CODEC(ZSTD(3)),

    attributes            Map(String, String),
    events                Array(Tuple(name LowCardinality(String), time DateTime64(9, 'UTC'), attributes Map(String, String))),
    links                 Array(Tuple(trace_id FixedString(32), span_id FixedString(16), relation LowCardinality(String))),

    protocol_version      LowCardinality(String),
    received_at           DateTime64(3, 'UTC'),
    persisted_at          DateTime64(3, 'UTC') DEFAULT now64(3),
    kafka_partition       UInt16,
    kafka_offset          UInt64
)
ENGINE = ReplacingMergeTree(received_at)                 -- option A (§3)
PRIMARY KEY (project_id, trace_id, span_id)              -- index prefix; keeps the hash out of memory
ORDER BY (project_id, trace_id, span_id, content_hash);  -- = dedup key; no PARTITION BY (P0, §4)
```

Notes on the DDL:
- **`PRIMARY KEY` shorter than `ORDER BY`.** Allowed because the primary key is a prefix. The in-memory index holds only the identity, while the full `ORDER BY` still defines what ReplacingMergeTree treats as "the same row".
- **No partitioning (P0).** One partition means every duplicate can be merged with its original, whatever its timestamps. There is no cheap per-month retention; add it later only with a partition key derived from hashed content (e.g. `started_at`), never from `received_at`.
- **No run table, no materialized view, no skip indexes.** The run list is a query over `telemetry_spans` (§4). Skip indexes are deferred until a measured query needs one.

---

## 3. Deduplication: option A (decided)

**The problem, simply:** Kafka is at-least-once. If the writer inserts a batch and then crashes **before** committing the offset, it reads the same messages again and inserts them again. Those copies are *transport duplicates* and must show up as one span. A *different* row with the same `(project_id, trace_id, span_id)` is a **conflict**: it is kept and surfaced, never silently merged (`database.md` §8.1, `trace-protocol.md` §13.3). Real application retries have **different** `span_id`s, so none of this touches them.

**Decision: A — ReplacingMergeTree with the content hash in the sorting key, plus query-time dedup.**

- **How:** `ORDER BY (project_id, trace_id, span_id, content_hash)`. Same identity + same content → same sorting key → collapsed on merge. Same identity + different content → different hash → **both rows survive**, so the conflict stays detectable.
- **Every read deduplicates** with `LIMIT 1 BY span_id, content_hash` (or `FINAL`). No read path may assume a merge has happened.
- **Late / out-of-order spans:** a late span is just a new key; merges don't depend on arrival order. With no partitioning, duplicates always share a partition.
- **Not allowed:** a ReplacingMergeTree key of `(project_id, trace_id, started_at, span_id)` without the hash (the `database.md` §5.2 hypothesis). It would silently merge two conflicting versions that share a start time.

Alternatives considered and not chosen: **B** (plain MergeTree, dedup only at read time; duplicates stay on disk forever) and **C** (insert-time dedup via `insert_deduplication_token` or read-before-write; neither is sufficient alone under every crash timing). C1 can be added later as an optimisation on top of A, never instead of it.

Reference read and conflict queries:

```sql
-- One trace, deduplicated, in execution-time order.
SELECT * FROM telemetry.telemetry_spans
WHERE project_id = {project:UUID} AND trace_id = {trace:FixedString(32)}
ORDER BY started_at, span_id
LIMIT 1 BY span_id, content_hash;

-- Conflicts in one trace: same identity, more than one content version.
SELECT span_id, uniqExact(content_hash) AS versions
FROM telemetry.telemetry_spans
WHERE project_id = {project:UUID} AND trace_id = {trace:FixedString(32)}
GROUP BY span_id HAVING versions > 1;
```

**Conflict surfacing (decided):** the read API returns **both** versions of a conflicting span, each with its `content_hash` and `received_at`, and flags the span (and the trace) as conflicted. It does not pick a winner and does not refuse the trace.

---

## 4. ORDER BY, partitioning and the run list (decided)

**Sorting key: K1 `(project_id, trace_id, span_id, content_hash)`.** Partitioning: **P0 (none).**

| LLD §6.3 query | With K1 |
|---|---|
| All spans of one trace | **Good**: one contiguous key range |
| One span | **Good**: full key prefix |
| Filter by operation type / status / agent **within a trace** | Good (a trace is small) |
| Related spans (parent, children, links) | Good: same-trace = trace read; cross-trace link = point lookup on the full prefix |
| Investigator metadata search (bounded to one trace) | Good |
| **List runs for project + time range** | **Scans the project** (`trace_id` is random). Accepted at OJT volume |
| Filter / find errors **across a project** | Scans the project; skip indexes deferred until measured |

**Run list = query-time aggregation (decided).** No `telemetry_runs` table and no materialized view. One consequence is a gain: a trace whose root span never arrived (crashed process; the SDK exports only ended spans and the root ends last) **still appears**, flagged as having no root.

```sql
-- Run list for one project and time range. Dedup first, then group by trace.
SELECT
    trace_id,
    min(started_at)                                   AS run_started_at,
    max(ended_at)                                     AS run_ended_at,
    anyIf(span_name, parent_span_id IS NULL)          AS root_name,
    countIf(parent_span_id IS NULL) = 0               AS missing_root,
    anyIf(execution_mode, execution_mode != '')       AS execution_mode,
    uniqExact(span_id)                                AS span_count,
    uniqExactIf(span_id, status_code = 'ERROR')       AS error_span_count
FROM
(
    SELECT * FROM telemetry.telemetry_spans
    WHERE project_id = {project:UUID}
    LIMIT 1 BY trace_id, span_id, content_hash
)
GROUP BY trace_id
HAVING run_started_at >= {from:DateTime64(9)} AND run_started_at < {to:DateTime64(9)}
ORDER BY run_started_at DESC
LIMIT 50;
```

`span_count` and `error_span_count` count **distinct span_ids** (D14, user decision 2026-11-15): a span with conflicting versions counts once, and counts as an error span if any version is ERROR. The read API reports conflicts separately (§3). **Validate with `EXPLAIN indexes = 1`** and a timing on realistic data before action 5 is called done. If the run list becomes the bottleneck, the next step is a measured change (a run table or projection), recorded as a new decision.

---

## 5. `content_hash` definition (decided: computed in the writer)

**Simply:** a fingerprint of everything the SDK recorded about the span. Same fingerprint = same span delivered twice; different fingerprint under the same ID = conflict.

- **Where:** in the **trace-writer**, once, just before insert. FastAPI does not compute it.
- **Included:** `trace_id`, `span_id`, `parent_span_id`, name, operation type, start/end, status + description, attributes, events, links, the three payloads **and** their states, model/provider/tokens/cost, display label, execution mode, graph node IDs.
- **Excluded:** `project_id` (already in the key), `received_at`, `persisted_at`, `kafka_partition`, `kafka_offset`, `protocol_version`. These change on redelivery; including them would turn every redelivery into a fake conflict.
- **Canonical form:**
  - JSON with keys sorted at every level, no insignificant whitespace, UTF-8 (RFC 8785 / JCS style).
  - **Timestamps as integer nanoseconds since the Unix epoch** (span start/end and event times). Never ISO strings or floats.
  - **`cost` as a decimal string** (e.g. `"0.001250000"`, the `Decimal(18,9)` form), or `null`. Never a float.
  - Token counts and `attempt` as JSON integers; IDs as lowercase hex strings.
  - Lists keep their order: event order is content, not presentation.
  - Built with `model_dump(mode="json", exclude=<excluded fields>, exclude_defaults=True)`: a field still at its default value is left out of the hashed JSON. An optional field explicitly set to its default (e.g. `parent_span_id=None`) hashes the same as one that omits it, and adding a defaulted `SpanRecord` field later does not change the hash of existing spans (D15).
  - Then SHA-256, lowercase hex.
- **Hashed fields are classified explicitly.** A test pins the exact set of hashed fields (every `SpanRecord` field except `project_id`, `received_at`, `protocol_version`). A new `SpanRecord` field fails that test until it is deliberately classified as span content or delivery metadata.

**Known limitations:**
- **Cost formatting.** `cost` is hashed as the string it arrives as. The same value formatted differently (e.g. `"0.00125"` and `"0.001250000"`) gives two different hashes, so it would show up as a conflict. This is not expected from redeliveries, which carry the same bytes; it would only happen if the same span were re-sent with its cost re-formatted.

---

## 6. Tests the writer must pass (real ClickHouse, not mocks — `database.md` §14)

1. **Duplicate → one logical row.** Insert the same span in two batches. The trace read returns it once; after `OPTIMIZE TABLE … FINAL` (tests only) exactly one physical row remains.
2. **Crash after insert, before commit.** Kill the consumer between the insert and the offset commit, restart it, and the span is still one logical row (action 4).
3. **Late span.** Read a trace, then insert a new child. The next read includes it, and earlier rows are unchanged.
4. **Out-of-order span.** Insert a child before its parent, and spans in reverse start order. The read returns all of them, sorted by `(started_at, span_id)`; nothing relies on insertion order.
5. **Conflicting duplicate.** Same `(project_id, trace_id, span_id)`, different content. **Both** rows are stored, the conflict query reports it, the read API returns both versions with a conflict flag, and `OPTIMIZE … FINAL` does **not** remove either one.
6. **Hash is key-order independent.** The same span with attributes in a different key order gets the same `content_hash`.
7. **Hash ignores receipt metadata.** The same span with a different `received_at` / Kafka offset gets the same `content_hash`.
8. **Project isolation.** The same `trace_id`/`span_id` under two projects are two spans; a read for project A never returns project B.
9. **Missing parent / multiple roots** are stored as-is (no rejection, no invented parent).
10. **Batching.** N spans produce one `INSERT`, not N (LLD §6.4).
11. **Payload states.** A disabled payload is stored as `''` with state `disabled`, a truncated one keeps its prefix with state `truncated`, and neither is stored as the text `"null"`.
12. **Nulls stay null.** A span without model usage reads back `NULL` tokens/cost, not `0`.
13. **Trace with no root span:** spans are stored, readable by `trace_id`, and the trace appears in the run list with `missing_root = 1`.
14. **Mixed batch.** A batch with valid and invalid messages: the valid spans are inserted in one `INSERT`, the invalid ones reach the DLQ with original bytes, error and source partition/offset, and offsets are committed only after both the insert and the DLQ acks (§8.4).
15. **All-invalid batch.** Every message fails validation: no `INSERT` runs, all of them reach the DLQ, and offsets are committed after the DLQ acks.
16. **DLQ publish failure.** The DLQ publish fails: no commit; after a restart the same messages are read again and, once the DLQ is reachable, land there exactly as in test 15.

(The former partition-safety test was removed on 2026-11-12: there is no partitioning. The former test 14 is now 13.)

---

## 7. Decisions (2026-11-12, user decision)

Replaces the earlier open-questions list. Each row is a **user decision, 2026-11-12**.

| # | Topic | Decision |
|---|---|---|
| D1 | Names | ClickHouse database `telemetry`; Kafka topic `agentdbg.traces.v1` (3 partitions); DLQ `agentdbg.traces.v1.dlq` (1 partition). Anything created under `spans.v1` or `spanhelix` names is renamed |
| D2 | Deduplication | **Option A**: `ReplacingMergeTree(received_at)`, `ORDER BY (project_id, trace_id, span_id, content_hash)`, `LIMIT 1 BY span_id, content_hash` on every read. C1 not now |
| D3 | Partitioning | **P0**: no `PARTITION BY` |
| D4 | Run list | **No `telemetry_runs` table and no materialized view**; query-time aggregation over `telemetry_spans` (§4) |
| D5 | Skip indexes | **Deferred** until a measured query needs one |
| D6 | ID encoding | Lowercase **hex** `FixedString(32)` trace IDs, `FixedString(16)` span IDs |
| D7 | `attributes` type | `Map(String, String)` (also for event attributes); values stringified |
| D8 | `content_hash` location | Computed in the **trace-writer** |
| D9 | `content_hash` canonical form | Timestamps as **integer nanoseconds**; `cost` as a **decimal string**; sorted-key JSON; SHA-256 lowercase hex (§5) |
| D10 | `cost` | `Nullable(Decimal(18,9))`; **`NULL` unless the span supplies a cost**; the writer never computes it from a price table |
| D11 | Conflicts | Read API **returns both versions** with a conflict flag (§3) |
| D12 | Tests | Partition-safety test removed (§6) |
| D13 | Kafka message and consumer rules | **Decided (user decision, 2026-11-13).** See §8 |
| D14 | Run-list span counts | **Decided (user decision, 2026-11-15).** `span_count` / `error_span_count` count distinct span_ids, so a conflicted span counts once (§4). Replaces "counted once per version" |
| D15 | `content_hash` and defaults | content_hash excludes default-valued fields (user decision 2026-11-16, review finding 2). See §5 |
| D16 | Duplicate deliveries before a merge | Before a merge, reads return the latest received_at for duplicate deliveries (`ORDER BY ... received_at DESC` before `LIMIT 1 BY span_id, content_hash`), matching what ReplacingMergeTree keeps after a merge; resolves the first-vs-latest receipt question (user decision 2026-11-16, review finding 5) |

**Still open (not decided on 2026-11-12):**
- `execution_mode` and `display_label`: root span only or every span, and which SDK attribute names feed them.
- `cost` currency.
- Confirm `graph_node_parent_id` is graph topology only and never feeds the span tree.
- Payload limits and redaction marker format (handoff action 7): proposed in §9, awaiting a decision.

---

## 8. Kafka message and consumer rules (user decision, 2026-11-13)

**Simply:** FastAPI turns each accepted span into one Kafka message and answers 202 only once Kafka has all of them. The trace-writer reads a batch, writes it to ClickHouse in one insert, and only then tells Kafka it is done. Bad messages go to the DLQ; ClickHouse outages never do.

### 8.1 Topics

| Topic | Partitions | Use |
|---|---|---|
| `agentdbg.traces.v1` | 3 | One message per span |
| `agentdbg.traces.v1.dlq` | 1 | Messages the writer cannot parse or validate |

### 8.2 Message

- **One message per span.**
- **Key:** `trace_id` (lowercase hex). All spans of a trace land on the same partition.
- **Value:** JSON `SpanRecord` = the §1 columns **minus** `content_hash`, `persisted_at`, `kafka_partition`, `kafka_offset`.
  - `duration_ns` is **not** in the message: the writer computes it from `ended_at − started_at` (§1).
  - Timestamps (`started_at`, `ended_at`, event times) are **integer nanoseconds** since the Unix epoch.
  - `cost` is a **decimal string** or `null`.
  - `received_at` is set by **FastAPI, once per envelope**: every span from one request carries the same value. It is **integer nanoseconds** in the message; the writer truncates it to milliseconds for the `DateTime64(3)` column.
  - `attributes` values are strings: the ingest **stringifies attribute values before publishing**, matching the `Map(String, String)` column.
  - `project_id` is set server-side by the ingest from `DEFAULT_PROJECT_ID` (fixed UUID, documented default) via a single `resolve_project_id()` function; never accepted from the client payload.

### 8.3 Producer (FastAPI, `POST /api/v1/traces`)

- Return **202 only after the broker acks every span in the batch**.
- If any publish fails or times out, raise `PublishError` and return **503**. **Never 202 on a failed publish.** (Spans that were acked before the failure stay in Kafka; the client's retry redelivers them, and option A dedup (§3) makes that harmless.)

### 8.4 Consumer (trace-writer)

- **Group:** `agentdbg-trace-writer`. **Auto-commit off.**
- **Loop:** poll up to **N** messages or **T** seconds → **one `INSERT`** → **commit offsets only after the insert succeeds.** N and T are writer config values; defaults **N = 1000 messages, T = 1 s**.
- **Parse/validation failure:** publish the **original bytes + error + source partition/offset** to the DLQ, then continue with the rest of the batch.
- **ClickHouse failure:** **no commit**; retry with backoff. **Never** send these messages to the DLQ.
- **The writer adds** `content_hash` (§5), `kafka_partition`, `kafka_offset` and `persisted_at`.

**Commit rule for DLQ messages (from handoff action 4's acceptance criteria, not restated in the 2026-11-13 decision):** a DLQ'd message's offset is committed only after the DLQ publish is acked, together with the batch commit. Consequences:
- a batch with valid and invalid messages commits after **both** the insert and the DLQ acks;
- a batch with only invalid messages has no `INSERT` and commits after the DLQ acks;
- if the DLQ publish fails, treat it like a ClickHouse failure: no commit, retry.

The non-envelope test message at `agentdbg.traces.v1` partition 0 offset 0 (handoff §3.4) is the first real input for the DLQ path.

### 8.5 Interfaces

| Interface | Methods | Owner |
|---|---|---|
| `SpanPublisher` | `publish(spans)`: returns only when every span is broker-acked; otherwise raises `PublishError` | FastAPI |
| `TraceStore` | `insert_spans(spans, positions=None)`, `get_trace`, `get_conflicts`, `list_runs` | trace-writer (insert) and read API (reads) |

`positions` is optional: `positions[i]` is the `(kafka_partition, kafka_offset)` that `spans[i]` was read from. The trace-writer passes it so the ClickHouse store can fill those two columns; other callers (tests, fakes) may omit it, and the in-memory fake ignores it.

`get_trace` returns deduplicated spans with conflicting versions flagged (§3). `get_conflicts` runs the §3 conflict query. `list_runs` runs the §4 run-list query.

**Read API project mapping:** the route's `local` project (`#/projects/local/...`, `projectId: 'local'` in the frontend) maps to the same `DEFAULT_PROJECT_ID` value, resolved through the same `resolve_project_id()`. The read API never queries ClickHouse with the string `local`.

---

## 9. Payload capture policy — PROPOSAL (2026-11-16, not decided)

**Status: PROPOSAL, assistant-written, awaiting user approval.** It is implemented on branch `feat/payload-capture` (SDK only) so it can be tested. Any row can be rejected; the code then changes. Durable path only: local-1 still exports no payloads.

**Simply:** before a span leaves the agent process, the SDK turns each input, output and error into a small JSON text, removes secret fields, cuts it to a size limit, and labels it with one state. The server stores what it gets and never guesses a state.

### 9.1 Proposals

| # | Topic | Proposal | Why, and what was rejected |
|---|---|---|---|
| P1 | Redaction marker | The value of a secret field is replaced by the JSON string `"[redacted]"`. The key stays. Fields match by name (case and punctuation ignored; built-in list plus `CaptureConfig.secret_fields`), at any depth, and the value is never inspected | The key staying shows that the field existed, so "absent" and "removed" look different. Rejected: dropping the key (hides that); an object marker such as `{"$redacted": true}` (changes the value's type); a hash of the value (leaks equality and can be brute-forced for short secrets). Limit: an application value that really is `"[redacted]"` looks the same |
| P2 | Truncation rule | **Valid JSON, cut inside the structure. Not a raw byte prefix.** A long string keeps a real prefix; list items and dict keys that no longer fit are dropped; no marker is inserted for a size cut. The budget counts bytes of the final ASCII-escaped JSON (escapes, quotes, commas, brackets) | `*_payload` is "bounded serialized JSON" (§1), so the UI, the investigator and ClickHouse JSON functions need one parser path. A raw prefix makes every truncated payload unparseable. Cost: the payload does not show where it was cut; the state says it is partial |
| P3 | Per-payload cap | Default **16,384 bytes** (unchanged). Hard maximum **131,072 bytes (128 KiB)**, down from 1,048,576. `CaptureConfig` rejects a larger value | With the old maximum, one payload could fill the 1 MiB Kafka record and the batch would get a 413 that no retry fixes. Size math in §9.3 |
| P4 | One state per payload | Most limiting first: `disabled` > `unavailable` > `truncated` > `redacted` > `captured` (§9.2). Flags the state cannot express are kept as attributes: `debugger.input.redacted`, `.truncated`, `.unsupported` (and the same for `output`), value `true` | A payload can be both redacted and truncated but the column holds one value. `truncated` wins because missing content changes what a reader may conclude; redaction is visible in the payload itself |
| P5 | Values that are not JSON | Only exact `None`, `bool`, `int`, finite `float`, `str`, `dict`, `list`, `tuple` are captured. Anything else is never passed to `str()`, `repr()` or iteration. Nested: the value becomes `"[unsupported]"` and the state is not changed. Whole payload: state `unavailable`, payload `''` | Calling `str()` on an application object can run application code and can leak fields. A marker never stands in for a whole payload |
| P6 | Error payload | `{"type": ..., "message": ...}` from the span's first `exception` event, bounded by the same cap. **No stack trace is exported** (not in the payload, not in events). New switch `CaptureConfig.capture_errors` (default `True`); when off: `error_state = disabled`, and `exception.message` and the status description are not exported either. `error_type` is still sent | Exception messages can carry user data, so they need the same switch as inputs and outputs. `TraceSession` already records the message as `"<Type> during <operation>"` |
| P7 | Transport | `DurableSpanExporter` posts to `/api/v1/traces` only. `https` is required unless the host is loopback. Requests are split at 256 spans and 4 MiB (the route's limits). Success = HTTP 202 with a matching span count. A failed request is counted and dropped (no retry) | Payloads over plain HTTP to another machine would expose prompts. No API key until action 6 |
| P8 | Non-payload bounds | Per span: attributes 32 KiB serialized, events 32 KiB and 32 events, strings 1,024 characters, lists 32 items. Attributes past the budget are dropped and counted in `debugger.export.dropped_attributes`. An attribute whose **key** is a secret name is sent as `"[redacted]"` | Needed for the guarantee in §9.3 |
| P9 | Server-side cap | **Not implemented.** Proposed: the ingest rejects a payload over 131,072 bytes with 422 and never truncates it itself | The server did not capture the value and cannot cut JSON safely. This changes `trace-protocol.md` §4.1 (a decided doc), so it needs its own decision |

### 9.2 State mapping (as implemented)

| Condition, checked in this order | State | Payload |
|---|---|---|
| Capture switched off for this kind | `disabled` | `''` |
| Never set, capture failed, the whole value is not JSON (P5), or the text is over the hard cap | `unavailable` | `''` |
| Something was cut: a string, dropped items, depth, node count, a cycle, an oversized integer | `truncated` | the cut JSON (`''` if nothing fit) |
| At least one secret field was replaced | `redacted` | JSON with `"[redacted]"` values |
| Otherwise | `captured` | the JSON |

For errors: no exception event → `unavailable`; `capture_errors` off → `disabled`.

### 9.3 Size math against the Kafka record limit

The producer rejects a record over `max_request_size` = 1,048,576 bytes (§8.3: 413, nothing published).

- A payload is already JSON text. Stored inside the `SpanRecord` JSON it is a JSON *string*, so every `"` and `\` in it is escaped again. Worst case: **2 ×** its size.
- Three payloads at the hard cap: 3 × 2 × 131,072 = **786,432 bytes**.
- Attributes and events: at most 2 × (32 + 32) KiB = 131,072 bytes (list values are stringified by the ingest, which can double them).
- Fixed fields (IDs, name, status, model, times): under 16 KiB.
- Worst case total ≈ 934,000 bytes, about 110 KiB under the limit.

**Measured (2026-11-16):** a span with input, output and error all cut at 131,072 bytes of `"` characters, plus attributes filled to their budget, is a Kafka record of **802,032 bytes** by aiokafka's own size estimate (the case in `tests/integration/test_durable_payloads.py`).

At the default cap, three payloads are at most 3 × 2 × 16,384 = 98,304 bytes per span.

### 9.4 What this does not cover

- **Example agents send no input or output payloads yet.** `TraceSession.wrap_callable` records no arguments or results, and the agents' results are application objects (P5 would mark them `unavailable`). Pointed at `/api/v1/traces` they export error payloads only. The agents need explicit capture calls with plain data.
- **`investigator.md` treats `redacted` as "no excerpt"** (its snapshot test 5 and grounding rule R5). Under P1 a `redacted` payload still holds everything except the secret fields, so the investigator could read it like `captured`. `investigator.md` is not edited here.
- **§1 wording.** §1 says of `truncated`: "the stored prefix is real but partial". Under P2 the precise statement is "everything stored is real, and some is missing". §1 is not edited until P2 is decided.
- **OpenTelemetry's 128-attribute limit** evicts the *oldest* attributes first, and the captured payloads are attributes. A span with more than about 115 application attributes can lose its payload; it is then exported as `unavailable`.
- **`execution_mode`** is fed from `debugger.execution.mode` (the only attribute that exists). §7 still lists the attribute names as open. `display_label`, token counts, cost and OTel links are not sent.
- Redaction is by field name. A secret inside prose (a prompt, an exception message) is not found.
