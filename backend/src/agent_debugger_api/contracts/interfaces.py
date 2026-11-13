"""Ports between FastAPI, Kafka and ClickHouse (`docs/proposals/clickhouse-span-record.md` §8.5).

FastAPI depends on `SpanPublisher`; the trace-writer and the read API depend on
`TraceStore`. Real implementations (Kafka producer, ClickHouse client) come
later; `fakes.py` has in-memory versions for tests.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol, runtime_checkable
from uuid import UUID

from .span_record import SpanRecord


class PublishError(Exception):
    """At least one span was not broker-acked. The ingest must answer 503, never 202.

    Spans acked before the failure stay in Kafka; the client's retry redelivers
    them and option A dedup (§3) makes that harmless.
    """


@dataclass(frozen=True, slots=True)
class StoredSpan:
    """One stored version of a span: the record plus the writer-owned hash."""

    record: SpanRecord
    content_hash: str


@dataclass(frozen=True, slots=True)
class TraceRead:
    """A deduplicated trace (§3). Conflicting spans appear once per version."""

    spans: tuple[StoredSpan, ...]  # ordered by (started_at, span_id)
    conflicted_span_ids: frozenset[str]

    @property
    def conflicted(self) -> bool:
        return bool(self.conflicted_span_ids)


@dataclass(frozen=True, slots=True)
class SpanConflict:
    """Same (project_id, trace_id, span_id) with more than one content version."""

    span_id: str
    versions: int


@dataclass(frozen=True, slots=True)
class RunSummary:
    """One row of the query-time run list (§4)."""

    trace_id: str
    run_started_at: int  # ns
    run_ended_at: int  # ns
    root_name: str | None  # None when no root span has arrived
    missing_root: bool
    execution_mode: str  # "" when no span carries it
    span_count: int  # conflicting versions count once each
    error_span_count: int


@runtime_checkable
class SpanPublisher(Protocol):
    async def publish(self, spans: Sequence[SpanRecord]) -> None:
        """Return only after every span is broker-acked; otherwise raise PublishError."""
        ...


@runtime_checkable
class TraceStore(Protocol):
    """Synchronous: the trace-writer is a plain consumer loop. Async callers must
    not call it on the event loop (use a thread, e.g. `run_in_threadpool`)."""

    def insert_spans(self, spans: Sequence[SpanRecord]) -> None:
        """Persist one batch (one INSERT). Identical redelivery is one logical row."""
        ...

    def get_trace(self, project_id: UUID, trace_id: str) -> TraceRead | None:
        """Deduplicated spans of one trace, conflicts flagged; None if the trace is unknown."""
        ...

    def get_conflicts(self, project_id: UUID, trace_id: str) -> list[SpanConflict]:
        """Spans of one trace that have more than one content version."""
        ...

    def list_runs(
        self, project_id: UUID, started_from: int, started_to: int, limit: int = 50
    ) -> list[RunSummary]:
        """Runs whose first span started in [started_from, started_to) ns, newest first."""
        ...
