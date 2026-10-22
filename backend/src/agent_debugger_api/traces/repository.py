"""Bounded local memory repository. Not Kafka or durable ClickHouse storage."""
import json
import threading
import time
from fastapi import HTTPException

MAX_RUNS, MAX_SPANS, MAX_BYTES = 100, 4000, 16 * 1024 * 1024
TTL_SECONDS = 4 * 60 * 60

class LocalMemoryRepository:
    """Bounded immutable ended spans; identical redelivery is idempotent."""

    def __init__(self):
        self.runs = {}
        self.created = {}
        self.lock = threading.Lock()

    def _expire(self):
        for trace_id in list(self.created):
            if time.monotonic() - self.created[trace_id] > TTL_SECONDS:
                del self.runs[trace_id]
                del self.created[trace_id]

    def ingest(self, batch):
        with self.lock:
            self._expire()
            planned = {trace_id: dict(spans) for trace_id, spans in self.runs.items()}
            for span in batch.spans:
                values = span.model_dump()
                trace = planned.setdefault(span.trace_id, {})
                if span.span_id in trace and trace[span.span_id] != values:
                    raise HTTPException(409, "Conflicting redelivery; captured spans are immutable")
                trace[span.span_id] = values
            if (len(planned) > MAX_RUNS or sum(map(len, planned.values())) > MAX_SPANS
                    or any(len(spans) > 200 for spans in planned.values())
                    or len(json.dumps(planned).encode()) > MAX_BYTES):
                raise HTTPException(507, "Local memory storage is full; restart only after exporting needed traces")
            for trace_id in planned:
                self.created.setdefault(trace_id, time.monotonic())
            self.runs = planned
            return {"accepted": len(batch.spans), "trace_ids": sorted({span.trace_id for span in batch.spans}), "storage": "temporary process memory"}

    def read(self, trace_id=None):
        with self.lock:
            self._expire()
            if trace_id is not None and trace_id not in self.runs:
                raise HTTPException(404, "Captured trace unavailable in this process")
            # Deep copy so request/serialization never changes a stored record.
            return json.loads(json.dumps(self.runs.get(trace_id) if trace_id else self.runs))
