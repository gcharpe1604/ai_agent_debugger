from decimal import Decimal

from agent_debugger_api.contracts.span_record import SpanRecord
from agent_debugger_api.trace_writer.content_hash import content_hash

# Columns we insert: every SpanRecord field + the 4 the writer adds.
# persisted_at is left out so ClickHouse fills it (DEFAULT now64(3)).
WRITER_COLUMNS = ["content_hash", "duration_ns", "kafka_partition", "kafka_offset"]
INSERT_COLUMNS = list(SpanRecord.model_fields) + WRITER_COLUMNS

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

    def get_trace(self, project_id, trace_id) -> list[dict]:
        """Get all SpanRecords for a given project_id and trace_id from ClickHouse.
        Returns a list of dicts keyed by the tuple element names, in the order they were inserted.
        """
        result = self._client.query(
            f"SELECT * FROM {self._table} "
            "WHERE project_id = {p:UUID} AND trace_id = {t:FixedString(32)} "
            "ORDER BY started_at, span_id "
            "LIMIT 1 BY span_id, content_hash",          # hides unmerged duplicates
            parameters={"p": project_id, "t": trace_id},
            query_formats={"DateTime64": "int", "FixedString": "string"},  # keep ns, str IDs
        )
        return list(result.named_results())