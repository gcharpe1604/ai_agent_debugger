-- telemetry_spans schema (clickhouse-span-record.md §2, decided 2026-11-12).
-- Applied by trace_writer.schema.ensure_schema(client, database), which replaces
-- {database} and runs each statement. Both statements are idempotent.
-- Comments are stripped before the statements are split on ';'.

CREATE DATABASE IF NOT EXISTS {database};

CREATE TABLE IF NOT EXISTS {database}.telemetry_spans
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
