"""Durable-path contracts: the Kafka message (`SpanRecord`) and the publisher/store ports."""

from .first_error import RunFirstError, run_first_error
from .interfaces import (
    PublishError,
    RunSummary,
    SpanConflict,
    SpanPublisher,
    SpanTooLargeError,
    StoredSpan,
    TraceRead,
    TraceStore,
)
from .span_record import PayloadState, SpanEvent, SpanLink, SpanRecord, StatusCode

__all__ = [
    "PayloadState",
    "PublishError",
    "RunFirstError",
    "RunSummary",
    "SpanConflict",
    "SpanEvent",
    "SpanLink",
    "SpanPublisher",
    "SpanRecord",
    "SpanTooLargeError",
    "StatusCode",
    "StoredSpan",
    "TraceRead",
    "TraceStore",
    "run_first_error",
]
