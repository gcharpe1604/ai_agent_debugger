"""In-memory `SpanPublisher` and `TraceStore` for tests. Not for production use."""

from __future__ import annotations

import hashlib
from collections import defaultdict
from collections.abc import Sequence
from uuid import UUID

from .interfaces import PublishError, RunSummary, SpanConflict, StoredSpan, TraceRead
from .span_record import SpanRecord, StatusCode

# Fields that change on redelivery and must not change the hash (§5).
_RECEIPT_FIELDS = {"project_id", "received_at", "protocol_version"}


def placeholder_content_hash(record: SpanRecord) -> str:
    """PLACEHOLDER; real content_hash is owned by the ClickHouse writer (§5).

    SHA-256 of pydantic's JSON dump without receipt fields. It is NOT the
    canonical form: it depends on dict insertion order, so two spans whose
    attributes differ only in key order get different hashes. Do not copy
    this into the writer.
    """
    body = record.model_dump_json(exclude=_RECEIPT_FIELDS)
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


class InMemorySpanPublisher:
    """Records published spans as (key, record) in publish order.

    `fail_after=n` acks the first n spans of every later publish call, then
    raises PublishError (n=0 fails at once). The acked spans stay recorded,
    like messages that reached Kafka before the failure.
    """

    def __init__(self, fail_after: int | None = None) -> None:
        self.fail_after = fail_after
        self.acked: list[tuple[bytes, SpanRecord]] = []

    async def publish(self, spans: Sequence[SpanRecord]) -> None:
        for index, span in enumerate(spans):
            if self.fail_after is not None and index >= self.fail_after:
                raise PublishError(f"broker did not ack span {span.span_id}")
            self.acked.append((span.kafka_key, span))


class InMemoryTraceStore:
    """Mirrors option A: rows keyed by (project_id, trace_id, span_id, content_hash).

    Same identity and same hash collapse to one row (the later one wins, like
    ReplacingMergeTree(persisted_at)); a different hash is kept as a conflict.
    """

    def __init__(self) -> None:
        self._rows: dict[tuple[UUID, str, str, str], SpanRecord] = {}
        self.insert_batch_sizes: list[int] = []  # one entry per insert_spans call

    def insert_spans(
        self,
        spans: Sequence[SpanRecord],
        positions: Sequence[tuple[int, int]] | None = None,
    ) -> None:
        # positions (Kafka partition/offset) are accepted for the Protocol and ignored here.
        self.insert_batch_sizes.append(len(spans))
        for span in spans:
            key = (span.project_id, span.trace_id, span.span_id, placeholder_content_hash(span))
            self._rows[key] = span

    def _trace_rows(self, project_id: UUID, trace_id: str) -> list[StoredSpan]:
        return [
            StoredSpan(record=record, content_hash=content_hash)
            for (project, trace, _span, content_hash), record in self._rows.items()
            if project == project_id and trace == trace_id
        ]

    def get_trace(self, project_id: UUID, trace_id: str) -> TraceRead | None:
        rows = self._trace_rows(project_id, trace_id)
        if not rows:
            return None
        rows.sort(key=lambda row: (row.record.started_at, row.record.span_id, row.content_hash))
        conflicts = self.get_conflicts(project_id, trace_id)
        return TraceRead(
            spans=tuple(rows),
            conflicted_span_ids=frozenset(conflict.span_id for conflict in conflicts),
        )

    def get_conflicts(self, project_id: UUID, trace_id: str) -> list[SpanConflict]:
        versions: dict[str, int] = defaultdict(int)
        for row in self._trace_rows(project_id, trace_id):
            versions[row.record.span_id] += 1
        return [
            SpanConflict(span_id=span_id, versions=count)
            for span_id, count in sorted(versions.items())
            if count > 1
        ]

    def list_runs(
        self, project_id: UUID, started_from: int, started_to: int, limit: int = 50
    ) -> list[RunSummary]:
        by_trace: dict[str, list[SpanRecord]] = defaultdict(list)
        for (project, trace, _span, _hash), record in self._rows.items():
            if project == project_id:
                by_trace[trace].append(record)

        runs = []
        for trace_id, records in by_trace.items():
            roots = [r for r in records if r.parent_span_id is None]
            modes = [r.execution_mode for r in records if r.execution_mode]
            run = RunSummary(
                trace_id=trace_id,
                run_started_at=min(r.started_at for r in records),
                run_ended_at=max(r.ended_at for r in records),
                root_name=roots[0].span_name if roots else None,
                missing_root=not roots,
                execution_mode=modes[0] if modes else "",
                span_count=len(records),
                error_span_count=sum(r.status_code is StatusCode.ERROR for r in records),
            )
            if started_from <= run.run_started_at < started_to:
                runs.append(run)

        runs.sort(key=lambda run: run.run_started_at, reverse=True)
        return runs[:limit]
