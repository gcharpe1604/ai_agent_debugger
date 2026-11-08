# ClickHouse span record — PROPOSAL

**Status: PROPOSAL for the user's review (2026-11-08). Not a decision, not applied, no code.**
Prefix renamed 2026-11-08; name not approved. (Database `telemetry`, topics `agentdbg.traces.v1` / `agentdbg.traces.v1.dlq`.)
It does not change `database.md` or `LLD.md`. Those stay authoritative until the user decides. The user writes the ClickHouse writer and Kafka consumer. This file only gives them a contract and a test list to build against.

Sources: `LLD.md` §5–6, `database.md` §3, §5, §8, §11, `trace-protocol.md` §5, §10, §11, §13, handoff §8 action 3.

**Checked so far (2026-11-08), and only this:** the §2 DDL (re-checked after the `telemetry` rename) parses and creates in `clickhouse local` 26.8.36.3 (inside the compose ClickHouse container, in-process; **not** applied to the compose server). Smoke check of option A with 4 inserts: an equivalent redelivery collapsed to 1 physical row after `OPTIMIZE … FINAL`, and a same-ID/different-hash pair kept 2 rows (2 versions). That is not the §6 test suite; the writer and its tests are still to be written.

---

## 0. Five ClickHouse ideas you need first

1. **Column store.** Each column is stored in its own file. A query that reads `span_name, status_code` never touches the payload columns, so big payloads in the same table cost disk, not read time, unless you select them.
2. **Parts and merges.** Each `INSERT` writes an immutable *part*: a sorted chunk of rows. A background process later *merges* small parts into bigger ones. You don't control when merges happen.
3. **Sorting key (`ORDER BY`).** Rows inside each part are sorted by it. ClickHouse keeps a *sparse index*: one entry per ~8,192 rows (a *granule*). A query whose `WHERE` matches a **prefix** of the sorting key skips most granules. A filter on a column that isn't a prefix scans much more.
4. **ReplacingMergeTree.** It's a MergeTree that, **during merges**, keeps only one row per identical sorting key. That makes it "eventually deduplicated": before a merge, duplicates are still visible. It also only deduplicates rows **in the same partition**.
5. **Partitions (`PARTITION BY`).** They split data into separate directories, mainly for dropping or expiring old data. They aren't a speed feature, and too many partitions hurt.

Everything below follows from those five.

---

## 1. Logical columns

**Plain version:** one row per ended span. The row holds the identity (`project_id`, `trace_id`, `span_id`), what ran, when, how it ended, what was captured (and *why* something wasn't), plus receipt metadata. A few fields are promoted from `attributes` into real columns because queries filter on them.

| Column | Type (draft) | Why / source | LLD §6.2 item |
|---|---|---|---|
| `project_id` | `UUID` | Derived server-side from the credential, never from the client | project_id |
| `trace_id` | `FixedString(32)` hex | Run ID (one Run = one trace) | trace_id |
| `span_id` | `FixedString(16)` hex | Span identity | span_id |
| `parent_span_id` | `Nullable(FixedString(16))` | `NULL` = root. A missing parent is kept, not rejected | parent_span_id |
| `service_name` | `LowCardinality(String)` | Resource `service.name` | service_name |
| `operation_type` | `LowCardinality(String)` | run/agent/model/retrieval/tool/api/state/custom, validated by the API | operation_type |
| `span_name` | `String` | OTel span name | span_name |
| `display_label` | `String DEFAULT ''` | **New.** Short label that tells repeated operations apart (tool `pay`, evidence source `policy-kb`) | attributes (promoted) |
| `execution_mode` | `LowCardinality(String) DEFAULT ''` | **New.** `live` / `controlled`; today only the root span carries it | attributes (promoted) |
| `graph_node_id`, `graph_node_parent_id` | `String DEFAULT ''` | **New.** Workflow-graph node (e.g. LangGraph) and its graph parent. **Not** span parentage; never used for the tree | links/relationships |
| `status_code` | `Enum8('UNSET'=0,'OK'=1,'ERROR'=2)` | OTel status | status |
| `status_description` | `String DEFAULT ''` | OTel status text | status |
| `error_type` | `LowCardinality(String) DEFAULT ''` | First `exception.type`; promoted for "find errors" | error data |
| `started_at`, `ended_at` | `DateTime64(9,'UTC')` | Nanosecond OTel times | started_at, ended_at |
| `duration_ns` | `UInt64` | `ended_at − started_at`, computed by the writer (the API already rejects reversed times) | duration |
| `attempt`, `retry_of_span_id` | `Nullable(UInt16)`, `Nullable(FixedString(16))` | **Suggested (not in your list).** Promoted from `debugger.attempt` / `debugger.retry_of` for "find retries" | attributes (promoted) |
| `model`, `provider` | `LowCardinality(Nullable(String))` | **New.** `NULL` = not recorded | attributes (promoted) |
| `input_tokens`, `output_tokens`, `total_tokens` | `Nullable(UInt32)` | **New.** `NULL` ≠ 0 | attributes (promoted) |
| `cost` | `Nullable(Decimal(18,9))` | **New.** Currency and provenance are open questions (§7) | attributes (promoted) |
| `input_state`, `output_state`, `error_state` | `Enum8('captured','disabled','redacted','truncated','unavailable')` | **New.** Says *why* a payload is empty or partial. The UI must never infer it from an empty string | input/output/error data |
| `input_payload`, `output_payload`, `error_payload` | `String DEFAULT '' CODEC(ZSTD(3))` | Bounded serialized JSON, redacted before export | input/output/error data |
| `attributes` | `Map(LowCardinality(String), String)` | Remaining flexible attributes (values stringified; see §7 Q6) | attributes |
| `events` | `Array(Tuple(name, time, attributes))` | Span events incl. exceptions; kept on the span (`database.md` §5.4) | events |
| `links` | `Array(Tuple(trace_id, span_id, relation))` | OTel links / `depends_on`, `handoff_from`, `consumes`, `retry_of` | links |
| `protocol_version` | `LowCardinality(String)` | Envelope version (`"1"`) | receive metadata |
| `received_at` | `DateTime64(3,'UTC')` | **New.** FastAPI receipt time (per envelope) | receive metadata |
| `persisted_at` | `DateTime64(3,'UTC') DEFAULT now64(3)` | Insert time | persist metadata |
| `kafka_partition`, `kafka_offset` | `UInt16`, `UInt64` | Where the writer read it. Debugging and an optional insert-dedup token (§3, option C) | persist metadata |
| `content_hash` | `FixedString(64)` hex SHA-256 | **New.** Fingerprint of the immutable content (§5) | content hash |

**Payload states, simply:** `captured` = stored as given; `disabled` = capture switched off; `redacted` = removed by a secret rule; `truncated` = cut at the size limit (the stored prefix is real but partial); `unavailable` = not produced or lost. Each payload carries its own state, so "the output was truncated but the error was captured" is representable.

---

## 2. Draft DDL (not applied)

```sql
-- PROPOSAL ONLY. Do not apply until §3/§4/§7 are decided.
CREATE TABLE telemetry.telemetry_spans
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

    attributes            Map(LowCardinality(String), String),
    events                Array(Tuple(name LowCardinality(String), time DateTime64(9, 'UTC'), attributes Map(LowCardinality(String), String))),
    links                 Array(Tuple(trace_id FixedString(32), span_id FixedString(16), relation LowCardinality(String))),

    protocol_version      LowCardinality(String),
    received_at           DateTime64(3, 'UTC'),
    persisted_at          DateTime64(3, 'UTC') DEFAULT now64(3),
    kafka_partition       UInt16,
    kafka_offset          UInt64,

    -- Data-skipping indexes for project-wide filters (§4). Measure before keeping.
    INDEX idx_status   status_code    TYPE set(3)       GRANULARITY 4,
    INDEX idx_optype   operation_type TYPE set(16)      GRANULARITY 4,
    INDEX idx_errtype  error_type     TYPE bloom_filter GRANULARITY 4
)
ENGINE = ReplacingMergeTree(received_at)          -- option A in §3
PARTITION BY toYYYYMM(started_at)                 -- candidate P1 in §4
PRIMARY KEY (project_id, trace_id, span_id)       -- index prefix; keeps the hash out of memory
ORDER BY (project_id, trace_id, span_id, content_hash);  -- = dedup key for ReplacingMergeTree

-- Run list (LLD §6.3 "list runs for project/time range"). Root spans only.
CREATE TABLE telemetry.telemetry_runs
(
    project_id     UUID,
    trace_id       FixedString(32),
    root_span_id   FixedString(16),
    content_hash   FixedString(64),
    run_name       String,
    service_name   LowCardinality(String),
    execution_mode LowCardinality(String),
    status_code    Enum8('UNSET' = 0, 'OK' = 1, 'ERROR' = 2),
    started_at     DateTime64(9, 'UTC'),
    ended_at       DateTime64(9, 'UTC'),
    received_at    DateTime64(3, 'UTC')
)
ENGINE = ReplacingMergeTree(received_at)
PARTITION BY toYYYYMM(started_at)
ORDER BY (project_id, started_at, trace_id, content_hash);

CREATE MATERIALIZED VIEW telemetry.telemetry_runs_mv TO telemetry.telemetry_runs AS
SELECT project_id, trace_id, span_id AS root_span_id, content_hash, span_name AS run_name,
       service_name, execution_mode, status_code, started_at, ended_at, received_at
FROM telemetry.telemetry_spans
WHERE parent_span_id IS NULL AND operation_type = 'run';
```

Notes on the DDL:
- **`PRIMARY KEY` shorter than `ORDER BY`.** It's allowed when the primary key is a prefix. The in-memory index then holds only the identity, while the full `ORDER BY` still defines what ReplacingMergeTree treats as "the same row".
- **The materialized view runs on each insert block.** It sees duplicates too, which is why `telemetry_runs` is also a ReplacingMergeTree. It only knows root spans: a run whose root span never arrived **does not appear in the run list** (the local profile today falls back to the earliest span). See §7 Q4.
- **Error/span counts per run are not in `telemetry_runs`.** Compute them for the listed page only: `WHERE project_id = ? AND trace_id IN (<page of ≤50>)` on `telemetry_spans` uses the primary key.

---

## 3. Deduplication: three options

**The problem, simply:** Kafka is at-least-once. If the writer inserts a batch and then crashes **before** committing the offset, it reads the same messages again and inserts them again. Those copies are *transport duplicates* and must show up as one span. A *different* row with the same `(project_id, trace_id, span_id)` is a **conflict**: it must be kept and surfaced, never silently merged (`database.md` §8.1, `trace-protocol.md` §13.3). Real application retries have **different** `span_id`s, so none of this touches them.

### A. ReplacingMergeTree, with the content hash in the sorting key (+ query-time dedup)

**Simply:** the table cleans up exact duplicates by itself in the background, sometime later. Until it does, every read also removes duplicates.

- **How:** `ORDER BY (project_id, trace_id, span_id, content_hash)`. Same identity + same content → same sorting key → collapsed on merge. Same identity + different content → different hash → **both rows survive**, so the conflict stays detectable. Reads use `LIMIT 1 BY span_id, content_hash` (or `FINAL`); never assume a merge has happened.
- **Against LLD §6.5 (duplicates):** meets it, as long as reads dedup at query time. Storage converges to one row per duplicate. Conflicts are never merged away, because the hash is in the key.
- **Against LLD §6.6 (late / out-of-order):** a late span is just a new key, and merges don't depend on arrival order. One condition: **the partition key must give duplicates the same partition** (it's derived from `started_at`, which is part of the hashed content). Partitioning by `received_at` would break this, because a redelivery across a month boundary lands in a different partition and is never merged.
- **Cost:** you must not put `started_at` in the sorting key ahead of `span_id` and also drop the hash. The `database.md` hypothesis `(project_id, trace_id, started_at, span_id)` used as a ReplacingMergeTree key would **silently merge** two conflicting versions that share a start time.

### B. Plain MergeTree, dedup only at query time

**Simply:** store every row exactly as it arrives and clean up when reading.

- **How:** `ENGINE = MergeTree`, any sorting key (the `database.md` hypothesis is fine here). Every read uses `LIMIT 1 BY span_id, content_hash`; a conflict check uses `uniqExact(content_hash) > 1`.
- **Against §6.5:** meets it **only if every read path dedups**. A forgotten `LIMIT 1 BY` in one query shows duplicate operations. Duplicates stay on disk forever, but they are rare (crash between insert and commit), so the size cost is small at OJT scale.
- **Against §6.6:** same as A. The sorting key is free to include `started_at`, so a trace read comes back in time order without a sort.
- **Cost:** simplest writer and engine; the correctness burden moves into every query.

### C. Insert-time dedup (stop duplicates before they are written)

**Simply:** recognise a repeated insert and skip it.

- **C1 — ClickHouse block dedup:** give each insert an `insert_deduplication_token` derived from the Kafka position, e.g. `"{topic}:{partition}:{first_offset}-{last_offset}"`. On a non-replicated table this needs the `non_replicated_deduplication_window` setting (verify the exact behaviour on 26.8). It only catches a retry of the **same batch with the same token**. If the writer rebatches differently after a crash, the token differs and the duplicate gets in, and the window only remembers the last N blocks.
- **C2 — read-before-write:** the writer looks up existing `(project_id, trace_id, span_id, content_hash)` before inserting. That costs one query per batch, and two writers during a consumer-group rebalance can both miss each other's rows.
- **Against §6.5:** **neither is sufficient alone** under every crash timing; each needs A or B as a backstop.
- **Against §6.6:** neutral.

**Recommendation (proposal):** **A**, with `LIMIT 1 BY` on every read, plus a conflict query in the read API. Add C1 later only if duplicate volume ever matters. **B** is the fallback if ReplacingMergeTree makes your tests hard to reason about. A's key is the one handoff action 3 already lists "under test".

Reference read and conflict queries for A or B:

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

---

## 4. ORDER BY and PARTITION BY candidates

**Simply:** the sorting key decides which questions are cheap. A query is fast when its `WHERE` pins the **leftmost** key columns. No single key makes everything cheap, so the plan is a span table keyed for "one trace", plus a small run table keyed for "runs by time".

### Sorting-key candidates

- **K1** `(project_id, trace_id, span_id, content_hash)`: identity first (recommended with option A).
- **K2** `(project_id, trace_id, started_at, span_id)`: the `database.md` §5.2 hypothesis (safe only with option B).
- **K3** `(project_id, toDate(started_at), trace_id, span_id, content_hash)`: time bucket first.
- **R1** `telemetry_runs` `(project_id, started_at, trace_id, content_hash)`: the run-list companion to K1 or K2.

| LLD §6.3 query | K1 | K2 | K3 | With R1 |
|---|---|---|---|---|
| List runs for project + time range | Poor: `trace_id` is random, so the whole project is scanned | Poor (same reason) | Fair: days pruned, but it aggregates every span in range | **Good**: range on the 2nd key column |
| All spans of one trace | **Good**: one contiguous range | **Good**, already time-ordered | Fair if the trace's days are known (from R1), poor otherwise; long runs cross days | n/a |
| One span | **Good**: full key prefix | Good: trace range, then a tiny scan | Fair (as above) | n/a |
| Filter by operation type / status / agent, **within a trace** | Good (trace is small) | Good | Fair | n/a |
| …**across a project** | Poor without skip indexes; `idx_status`/`idx_optype` help only if matches are rare | Poor (same) | Fair: day pruning + skip indexes | R1 covers run status only |
| Find errors / retries | Within trace: good. Across project: `idx_status`, `idx_errtype`, promoted `retry_of_span_id` | Same | Same + day pruning | R1 gives failed runs; then per-trace reads |
| Related spans (parent, children, links) | **Good**: same-trace = trace read; cross-trace link = point lookup on the full prefix | Good same-trace; cross-trace lookups need `started_at`, else trace-range scan | Poor for cross-trace lookups | n/a |
| Investigator metadata search (bounded) | Good when scoped to one trace (the normal case) | Good | Fair | R1 picks candidate runs by time |

**Reading the table:** K1 + R1 makes every LLD §6.3 query either a key-prefix read or bounded to one trace. The weak spot is "filter across a whole project by status/type", which only matters for future dashboards; skip indexes are the cheap first fix to measure. **Validate with `EXPLAIN indexes = 1`** on real data before freezing anything. That is the "validate the ordering key with a query" criterion in action 3.

### Partition candidates

| | Plain meaning | Dedup safety (option A) | Use |
|---|---|---|---|
| **P0** none | One directory; simplest | Safe | Fine at OJT volume; no cheap retention |
| **P1** `toYYYYMM(started_at)` | One directory per month of execution | Safe: duplicates share `started_at` | Cheap `DROP PARTITION`/TTL by month. Used in the §2 draft |
| **P2** `toYYYYMM(received_at)` | Per month of arrival | **Unsafe**: a redelivery across months is never merged | Avoid with A |
| **P3** by `project_id` | Per project | Safe, but unbounded partition count | Avoid |

---

## 5. `content_hash` definition (what makes two rows "the same")

**Simply:** a fingerprint of everything the SDK recorded about the span. Same fingerprint = same span delivered twice; different fingerprint under the same ID = conflict.

- **Included:** `trace_id`, `span_id`, `parent_span_id`, name, operation type, start/end, status + description, attributes, events, links, the three payloads **and** their states, model/provider/tokens/cost, display label, execution mode, graph node IDs.
- **Excluded:** `project_id` (already in the key), `received_at`, `persisted_at`, `kafka_partition`, `kafka_offset`, `protocol_version`. These change on redelivery, and including them would turn every redelivery into a fake conflict.
- **Canonical form:** JSON with keys sorted at every level, no insignificant whitespace, UTF-8, and one number form (`1` vs `1.0` must not differ; RFC 8785 / JCS is the standard). Lists keep their order: event order is content, not presentation. Then SHA-256, lowercase hex.
- **Where:** in one place only. The writer is simplest; the API also works. See §7 Q7.

---

## 6. Tests the writer must pass (real ClickHouse, not mocks — `database.md` §14)

1. **Duplicate → one logical row.** Insert the same span in two batches. The trace read returns it once; after `OPTIMIZE TABLE … FINAL` (tests only) exactly one physical row remains.
2. **Crash after insert, before commit.** Kill the consumer between the insert and the offset commit, restart it, and the span is still one logical row (action 4).
3. **Late span.** Read a trace, then insert a new child. The next read includes it, and earlier rows are unchanged.
4. **Out-of-order span.** Insert a child before its parent, and spans in reverse start order. The read returns all of them, sorted by `(started_at, span_id)`; nothing relies on insertion order.
5. **Conflicting duplicate.** Same `(project_id, trace_id, span_id)`, different content. **Both** rows are stored, the conflict query reports it, and `OPTIMIZE … FINAL` does **not** remove either one.
6. **Hash is key-order independent.** The same span with attributes in a different key order gets the same `content_hash`.
7. **Hash ignores receipt metadata.** The same span with a different `received_at` / Kafka offset gets the same `content_hash`.
8. **Project isolation.** The same `trace_id`/`span_id` under two projects are two spans; a read for project A never returns project B.
9. **Missing parent / multiple roots** are stored as-is (no rejection, no invented parent).
10. **Batching.** N spans produce one `INSERT`, not N (LLD §6.4).
11. **Payload states.** A disabled payload is stored as `''` with state `disabled`, a truncated one keeps its prefix with state `truncated`, and neither is stored as the text `"null"`.
12. **Nulls stay null.** A span without model usage reads back `NULL` tokens/cost, not `0`.
13. **Partition safety** (if P1). A duplicate redelivered later lands in the same partition as the original.
14. **Trace with no root span:** spans are stored and readable by trace_id.

---

## 7. Open questions for you

1. **Dedup:** A (ReplacingMergeTree + `LIMIT 1 BY`) or B (MergeTree + `LIMIT 1 BY` everywhere)? Add C1 now or later?
2. **Version column:** `ReplacingMergeTree(received_at)` keeps the **latest** redelivery's receipt time. Do you need the **first** receipt time? If yes, take `min(received_at)` at query time, or use B.
3. **Partitioning:** P0 (none) or P1 (month of `started_at`)? That depends on whether a retention period is a requirement for the demo or deployment.
4. **Run list:** root-span materialized view (R1) as drafted, a projection, or query-time aggregation? With R1, runs whose root span never arrived are invisible. Is that acceptable, or do you want an "incomplete traces" query? (A ReplacingMergeTree projection needs `deduplicate_merge_projection_mode`; verify on 26.8.)
   - **Known limitation:** the SDK exports only ended spans, and the root ends last. A run whose process crashes never sends its root, so the R1 run list never shows it. An orphan-traces query is planned for the read-API step (handoff action 5).
5. **ID encoding:** hex `FixedString(32/16)` (readable, 2× size) or raw bytes `FixedString(16/8)` (compact, hex at the edges)?
6. **`attributes` type:** `Map(String, String)` (simple, loses value types) or the ClickHouse `JSON` type (keeps types; newer; test it on 26.8 first)?
7. **Where to compute `content_hash`:** the trace-writer (single owner, part of your core piece) or FastAPI before Kafka?
8. **`execution_mode` and `display_label`:** root span only or every span? Which SDK attribute names feed them (the local-1 exporter has no `display_label` today)?
9. **`cost`:** currency and source (provider-reported vs computed from a price table)? `Decimal` (exact) or `Float64`?
10. **`graph_node_parent_id`:** confirm it means graph topology only and must never feed the span tree.
11. **Conflict surfacing:** when a trace has a conflict, should the read API return both versions with a flag, the earliest-received version with a warning, or refuse the trace?
12. **Payload limits:** max bytes per payload and the redaction marker format, which is still open in handoff action 7.
