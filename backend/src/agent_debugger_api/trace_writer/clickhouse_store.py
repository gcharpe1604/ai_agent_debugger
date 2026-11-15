from decimal import Decimal

from agent_debugger_api.contracts.span_record import SpanRecord
from agent_debugger_api.trace_writer.content_hash import content_hash
from agent_debugger_api.contracts.interfaces import SpanConflict, StoredSpan, TraceRead, RunSummary

# Columns we insert: every SpanRecord field + the 4 the writer adds.
# persisted_at is left out so ClickHouse fills it (DEFAULT now64(3)).
WRITER_COLUMNS = ["content_hash", "duration_ns", "kafka_partition", "kafka_offset"]
INSERT_COLUMNS = list(SpanRecord.model_fields) + WRITER_COLUMNS
WRITER_ONLY = {"content_hash", "duration_ns", "persisted_at", "kafka_partition", "kafka_offset"}

def to_row(record: SpanRecord, position: tuple[int, int] | None) -> list:
    """Convert a SpanRecord to a list of values for ClickHouse insertion.
    The order of the values must match the order of INSERT_COLUMNS.
    """
    d = record.model_dump(mode="python")
    d["content_hash"] = content_hash(record)                #hash the incoming message
    d["duration_ns"] = record.ended_at - record.started_at  #int ns, writer-computed
    d["received_at"] = record.received_at // 1_000_000      #ns -> ms ticks for DateTime64(3)
    d["cost"] = Decimal(record.cost) if record.cost is not None else None 
    d["kafka_partition"], d["kafka_offset"] = position or (0, 0)
    return [d[col] for col in INSERT_COLUMNS]

def from_row(row: dict) -> StoredSpan:
    d = {k: v for k, v in row.items() if k not in WRITER_ONLY}       # drop columns SpanRecord doesn't have
    d["received_at"] = row["received_at"] * 1_000_000                # ms ticks -> ns
    d["cost"] = None if row["cost"] is None else format(row["cost"], "f")
    return StoredSpan(record=SpanRecord.model_validate(d), content_hash=row["content_hash"])

class ClickHouseTraceStore:
    """Write SpanRecords to ClickHouse and read them back as a list of dicts keyed by the tuple element names.
    The dicts are in the same order as the rows were inserted.
    """
    def __init__(self, client, table: str = "telemetry.telemetry_spans"):
        self._client = client
        self._table = table

    def insert_spans(self, spans, positions=None) -> None:
        """Insert a list of SpanRecords into ClickHouse.
        The positions argument is a list of (partition, offset) tuples for each span.
        If positions is None, the spans are inserted with (0, 0) for all.
        """
        if not spans:
            return
        if positions is not None and len(positions) != len(spans):
            raise ValueError("positions must match spans one-to-one")
        rows = [to_row(s, positions[i] if positions else None) for i, s in enumerate(spans,)]
        self._client.insert(self._table, rows, column_names=INSERT_COLUMNS)                   #One insert per batch

    def get_rows(self, project_id, trace_id) -> list[dict]:
        """Get all SpanRecords for a given project_id and trace_id from ClickHouse.
        Returns a list of dicts keyed by the tuple element names, in the order they were inserted.
        """
        result = self._client.query(
            f"SELECT * FROM {self._table} "
            "WHERE project_id = {p:UUID} AND trace_id = {t:FixedString(32)} "
            "ORDER BY started_at, span_id, content_hash, received_at DESC "
            "LIMIT 1 BY span_id, content_hash",          # hides unmerged duplicates
            parameters={"p": project_id, "t": trace_id},
            query_formats={"DateTime64": "int", "FixedString": "string"},  # keep ns, str IDs
        )
        return list(result.named_results())

    def get_conflicts(self, project_id, trace_id):
        result = self._client.query(
            f"SELECT span_id, groupArray(content_hash) AS hashes "
            f"FROM (SELECT DISTINCT span_id, content_hash FROM {self._table} "
            "      WHERE project_id = {p:UUID} AND trace_id = {t:FixedString(32)}) "
            "GROUP BY span_id HAVING length(hashes) > 1 "
            "ORDER BY span_id",  # same order as InMemoryTraceStore.get_conflicts
            parameters={"p": project_id, "t": trace_id},
            query_formats={"FixedString": "string"},
        )
        return [
            SpanConflict(span_id=row["span_id"], versions=len(row["hashes"]))
            for row in result.named_results()
        ]     #build SpanConflict objects from result.named_results()

    def get_trace(self, project_id, trace_id):
        rows = self.get_rows(project_id, trace_id)
        if not rows:
            return None
        hashes_by_span = {}
        for r in rows:
            hashes_by_span.setdefault(r["span_id"], set()).add(r["content_hash"])
        conflicted = frozenset(s for s, h in hashes_by_span.items() if len(h) > 1)
        return TraceRead(
            spans=tuple(from_row(r) for r in rows),
            conflicted_span_ids=conflicted
        )

    def list_runs(self, project_id, started_from, started_to, limit=50):
        result = self._client.query(
            "SELECT trace_id, "
            "  toUnixTimestamp64Nano(min(started_at)) AS run_started_at, "
            "  toUnixTimestamp64Nano(max(ended_at))   AS run_ended_at, "
            "  argMinIf(span_name, started_at, parent_span_id IS NULL) AS root_name, "
            "  countIf(parent_span_id IS NULL) = 0                    AS missing_root, "
            "  anyIf(execution_mode, execution_mode != '')            AS execution_mode, "
            "  uniqExact(span_id)                                     AS span_count, "
            "  uniqExactIf(span_id, status_code = 'ERROR')            AS error_span_count "
            f"FROM (SELECT DISTINCT trace_id, span_id, content_hash, span_name, parent_span_id, "
            f"        execution_mode, status_code, started_at, ended_at "
            f"      FROM {self._table} WHERE project_id = {{p:UUID}}) "
            "GROUP BY trace_id "
            "HAVING run_started_at >= {f:UInt64} AND run_started_at < {to:UInt64} "
            "ORDER BY run_started_at DESC "
            "LIMIT {n:UInt32}",
            parameters={"p": project_id, "f": started_from, "to": started_to, "n": limit},
            query_formats={"FixedString": "string"}
        )
        return [
            RunSummary(
                trace_id=r["trace_id"],
                run_started_at=r["run_started_at"],
                run_ended_at=r["run_ended_at"],
                root_name=None if r["missing_root"] else r["root_name"],
                missing_root=bool(r["missing_root"]),
                execution_mode=r["execution_mode"],
                span_count=r["span_count"],
                error_span_count=r["error_span_count"],
            ) for r in result.named_results()
        ]