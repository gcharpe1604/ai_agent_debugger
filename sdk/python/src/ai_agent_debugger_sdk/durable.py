"""Protocol "1" exporter for the durable path: POST /api/v1/traces.

Kept apart from transport.py (local-1: loopback only, metadata only). This one
sends payloads: the capture attributes SpanHandle writes (`debugger.input`,
`debugger.output` and their flags) become `input_*` / `output_*` payload fields
with a state, and the first exception event becomes the error payload.

Policy is docs/proposals/clickhouse-span-record.md §9 (user decision
2026-11-16). The API key (`api_key=` or AGENT_DEBUGGER_API_KEY) is sent as
`Authorization: Bearer <key>` and never logged. Plain http is accepted for
loopback hosts only, so a key leaves the machine only over https.
"""

import http.client
import json
import logging
import math
import os
import queue
import re
import ssl
import threading
import time
from urllib.parse import urlsplit

from opentelemetry.sdk.trace.export import SpanExporter, SpanExportResult
from opentelemetry.trace import format_span_id, format_trace_id

from .capture import MAX_PAYLOAD_BYTES, CaptureConfig, serialize_capture

DURABLE_PATH = "/api/v1/traces"
MAX_BODY_BYTES = 4 * 1024 * 1024  # the route's body limit
MAX_SPANS_PER_BODY = 256  # the route's batch limit
# Serialized bytes allowed for everything that is not a payload, per span.
ATTRIBUTE_BUDGET = 32 * 1024
EVENT_BUDGET = 32 * 1024
MAX_EVENTS = 32
MAX_STRING = 1024
MAX_LIST_ITEMS = 32
# Seconds waited before each retry of a 503: three retries, doubling.
RETRY_DELAYS = (1.0, 2.0, 4.0)
# Requests that may wait for a retry at once; each body is at most 4 MiB.
MAX_PENDING_RETRIES = 8

_OPERATIONS = frozenset({"run", "agent", "model", "retrieval", "tool", "api", "state", "custom"})
_LOOPBACK = frozenset({"127.0.0.1", "localhost", "::1"})
_SPAN_ID = re.compile(r"[0-9a-f]{16}\Z")
_FLAGS = ("redacted", "truncated", "unsupported")
# Mapped to payload fields; never copied into wire attributes.
_CAPTURE_KEYS = frozenset(
    f"debugger.{kind}{suffix}"
    for kind in ("input", "output")
    for suffix in ("", ".disabled", ".capture_error", *(f".{flag}" for flag in _FLAGS))
)
_SKIP = object()
_logger = logging.getLogger(__name__)
_DELIVERED, _RETRY, _REJECTED = "delivered", "retry", "rejected"


def _text(value, limit):
    """Clip, and replace lone surrogates: they are not valid in a JSON request."""
    return value[:limit].encode("utf-8", "replace").decode("utf-8")


def _payload(attributes, kind):
    """(state, payload, flags) for `debugger.<kind>` as SpanHandle recorded it.

    One state per payload, most limiting first: disabled, unavailable,
    truncated, redacted, captured. Flags the state cannot express stay visible
    as boolean attributes. A marker never stands in for a whole payload.
    """
    key = f"debugger.{kind}"
    if attributes.get(f"{key}.disabled") is True:
        return "disabled", "", {}
    flags = {f"{key}.{flag}": True for flag in _FLAGS if attributes.get(f"{key}.{flag}") is True}
    text = attributes.get(key)
    if attributes.get(f"{key}.capture_error") is True or type(text) is not str or not text:
        return "unavailable", "", flags
    text = _text(text, MAX_PAYLOAD_BYTES + 1)
    if len(text.encode("utf-8")) > MAX_PAYLOAD_BYTES:  # written past SpanHandle
        return "unavailable", "", flags
    if text == '"[unsupported]"' and f"{key}.unsupported" in flags:
        return "unavailable", "", flags
    if f"{key}.truncated" in flags:
        return "truncated", "" if text == '"[truncated]"' else text, flags
    return ("redacted" if f"{key}.redacted" in flags else "captured"), text, flags


def _error(span, capture):
    """(state, payload, error_type) from the first exception event. Never a stack trace."""
    event = next((event for event in span.events if event.name == "exception"), None)
    if event is None:
        return "unavailable", "", ""
    attributes = event.attributes or {}
    kind, message = attributes.get("exception.type"), attributes.get("exception.message")
    error_type = _text(kind, 256) if type(kind) is str else ""
    if not capture.capture_errors:
        return "disabled", "", error_type
    try:
        captured = serialize_capture(
            {"type": error_type, "message": message if type(message) is str else ""}, capture
        )
    except Exception:
        return "unavailable", "", error_type
    state = "truncated" if captured.truncated else "redacted" if captured.redacted else "captured"
    return state, captured.text, error_type


def _value(value):
    kind = type(value)
    if kind is bool:
        return value
    if kind is int:
        return value if value.bit_length() <= 64 else _SKIP
    if kind is float:
        return value if math.isfinite(value) else _SKIP
    if kind is str:
        return _text(value, MAX_STRING)
    return _SKIP


def _attributes(source, capture, budget, skip=frozenset()):
    """Primitive attributes within a serialized-byte budget -> (attributes, dropped, budget left)."""
    result, dropped = {}, 0
    for key, value in source.items():
        if type(key) is not str or not key or key in skip:
            continue
        key = _text(key, 256)
        if capture.is_secret(key):
            clean = "[redacted]"
        elif type(value) in (tuple, list):
            clean = [item for item in map(_value, value[:MAX_LIST_ITEMS]) if item is not _SKIP]
        else:
            clean = _value(value)
            if clean is _SKIP:
                continue
        cost = len(json.dumps(key)) + len(json.dumps(clean)) + 2
        if cost > budget:
            dropped += 1
            continue
        budget -= cost
        result[key] = clean
    return result, dropped, budget


def encode_span(span, capture):
    """One ended OTel span -> one protocol "1" span (trace-protocol.md §4.1)."""
    if span.end_time is None:
        raise ValueError("Only ended spans are exported")
    source = span.attributes or {}
    operation = source.get("debugger.operation.type")
    record = {
        "trace_id": format_trace_id(span.context.trace_id),
        "span_id": format_span_id(span.context.span_id),
        "parent_span_id": format_span_id(span.parent.span_id) if span.parent else None,
        "name": _text(span.name, 256) or "unnamed",
        "operation_type": operation if operation in _OPERATIONS else "custom",
        "start_time": span.start_time,
        "end_time": max(span.end_time, span.start_time),
        "status": {"code": span.status.status_code.name},
        "service_name": _text(str(span.resource.attributes.get("service.name", "")), 256),
    }
    description = span.status.description
    if capture.capture_errors and type(description) is str and description:
        record["status"]["description"] = _text(description, MAX_STRING)

    # Promoted columns (clickhouse-span-record.md §1). The attributes stay too.
    mode, attempt, retry_of = (
        source.get("debugger.execution.mode"),
        source.get("debugger.attempt"),
        source.get("debugger.retry_of"),
    )
    if type(mode) is str and mode:
        record["execution_mode"] = _text(mode, 64)
    if type(attempt) is int and 0 <= attempt <= 65535:
        record["attempt"] = attempt
    if type(retry_of) is str and _SPAN_ID.match(retry_of):
        record["retry_of_span_id"] = retry_of
    for field, key in (("model", "debugger.model.name"), ("provider", "debugger.model.provider")):
        value = source.get(key)
        if type(value) is str and value:
            record[field] = _text(value, 256)

    attributes, dropped, _ = _attributes(source, capture, ATTRIBUTE_BUDGET, _CAPTURE_KEYS)
    for kind in ("input", "output"):
        state, payload, flags = _payload(source, kind)
        record[f"{kind}_state"], record[f"{kind}_payload"] = state, payload
        attributes.update(flags)
    record["error_state"], record["error_payload"], error_type = _error(span, capture)
    if error_type:
        record["error_type"] = error_type
    if dropped:
        attributes["debugger.export.dropped_attributes"] = dropped
    record["attributes"] = attributes

    hidden = {"exception.stacktrace"} | (set() if capture.capture_errors else {"exception.message"})
    events, budget = [], EVENT_BUDGET
    for event in span.events[:MAX_EVENTS]:
        name = _text(event.name, 128) or "event"
        budget -= len(json.dumps(name)) + 64
        if budget < 0:
            break
        event_attributes, _, budget = _attributes(event.attributes or {}, capture, budget, hidden)
        events.append({"name": name, "time": event.timestamp, "attributes": event_attributes})
    record["events"] = events
    return record


def encode_bodies(spans, capture=None):
    """Request bodies for a batch: [(bytes, span count)], each within the route's limits."""
    capture = capture if capture is not None else CaptureConfig()
    head, tail = b'{"protocol_version":"1","spans":[', b"]}"
    bodies, chunk, size = [], [], len(head) + len(tail)
    for span in spans:
        item = json.dumps(encode_span(span, capture), allow_nan=False, separators=(",", ":")).encode("ascii")
        if chunk and (len(chunk) == MAX_SPANS_PER_BODY or size + len(item) + 1 > MAX_BODY_BYTES):
            bodies.append((head + b",".join(chunk) + tail, len(chunk)))
            chunk, size = [], len(head) + len(tail)
        chunk.append(item)
        size += len(item) + 1
    if chunk:
        bodies.append((head + b",".join(chunk) + tail, len(chunk)))
    return bodies


class DurableSpanExporter(SpanExporter):
    """Sends ended spans, with payloads, to POST /api/v1/traces.

    `capture` supplies the error-capture switch, the limits for the error
    payload and the secret field names applied to attribute keys. Input and
    output payloads were already bounded and redacted when they were recorded.

    Delivery: `export` makes one attempt on the calling thread. A 503 (the
    ingest could not buffer the batch) hands the request to this exporter's own
    daemon thread, which resends it after each of RETRY_DELAYS and then drops
    it. Every other failure is dropped at once: a 413 or 422 fails the same way
    again. A 401 (no key, or a key the server does not know) logs one warning
    per exporter and drops the batch; it is never retried. `export` never waits
    for a backoff. Counters: `exported_spans`
    (acknowledged), `retries`, `failures` (requests given up) and
    `dropped_spans`. `force_flush` waits for pending retries up to its timeout;
    `shutdown` gives them up.
    """

    def __init__(self, endpoint, capture=None, api_key=None):
        url = urlsplit(endpoint)
        if (url.scheme not in ("http", "https") or not url.hostname or url.path != DURABLE_PATH
                or url.query or url.fragment or url.username or url.password
                or (url.scheme == "http" and url.hostname not in _LOOPBACK)):
            raise ValueError("Exporter requires https://<host>/api/v1/traces (http only for loopback)")
        self.capture = capture if capture is not None else CaptureConfig()
        if type(self.capture) is not CaptureConfig:
            raise TypeError("capture must be a CaptureConfig")
        self.secure = url.scheme == "https"
        self.host, self.port, self.path = url.hostname, url.port or (443 if self.secure else 80), url.path
        key = (api_key if api_key is not None else os.environ.get("AGENT_DEBUGGER_API_KEY", "")).strip()
        self._headers = {"Content-Type": "application/json"}
        if key:
            self._headers["Authorization"] = f"Bearer {key}"
        self._warned_unauthorized = False
        self.exported_spans = 0
        self.failures = 0
        self.dropped_spans = 0
        self.retries = 0
        self.lock = threading.Lock()  # counters and retry bookkeeping; never held during a request
        self._settled = threading.Condition(self.lock)
        self._stop = threading.Event()
        self._retry_queue = queue.SimpleQueue()
        self._pending = 0  # requests waiting for, or in, a retry
        self._worker = None

    @property
    def closed(self):
        return self._stop.is_set()

    def export(self, spans):
        if self._stop.is_set():
            self._drop(len(spans))
            return SpanExportResult.FAILURE
        try:
            bodies = encode_bodies(spans, self.capture)
        except Exception:
            # Fail open without logging captured content or exceptions.
            self._drop(len(spans))
            return SpanExportResult.FAILURE
        delivered = True
        for body, count in bodies:
            outcome = self._post(body, count)
            if outcome is _DELIVERED:
                with self.lock:
                    self.exported_spans += count
                continue
            delivered = False  # dropped, or not delivered yet: see the counters after force_flush
            if outcome is not _RETRY or not self._schedule(body, count):
                self._drop(count)
        return SpanExportResult.SUCCESS if delivered else SpanExportResult.FAILURE

    def _drop(self, count):
        with self.lock:
            self.failures += 1
            self.dropped_spans += count

    def _schedule(self, body, count):
        """Queue a request for the retry thread. False when shut down or the queue is full."""
        with self.lock:
            if self._stop.is_set() or self._pending >= MAX_PENDING_RETRIES:
                return False
            self._pending += 1
            if self._worker is None:
                self._worker = threading.Thread(
                    target=self._retry_loop, name="AgentDebuggerExportRetry", daemon=True
                )
                self._worker.start()
            # Inside the lock, so nothing is queued behind shutdown's stop marker.
            self._retry_queue.put((body, count, time.monotonic()))
        return True

    def _retry_loop(self):
        while True:
            item = self._retry_queue.get()
            if item is None:
                return
            body, count, failed_at = item
            outcome = _RETRY
            for delay in RETRY_DELAYS:
                # Counted from the failed attempt, so queued requests do not add up each other's waits.
                if self._stop.wait(max(0.0, failed_at + delay - time.monotonic())):
                    break  # shut down: give up
                with self.lock:
                    self.retries += 1
                outcome = self._post(body, count)
                if outcome is not _RETRY:
                    break
                failed_at = time.monotonic()
            with self._settled:
                if outcome is _DELIVERED:
                    self.exported_spans += count
                else:
                    self.failures += 1
                    self.dropped_spans += count
                self._pending -= 1
                self._settled.notify_all()

    def _post(self, body, count):
        connection = None
        try:
            # http.client ignores environment proxies and does not follow redirects.
            if self.secure:
                connection = http.client.HTTPSConnection(
                    self.host, self.port, timeout=5, context=ssl.create_default_context()
                )
            else:
                connection = http.client.HTTPConnection(self.host, self.port, timeout=5)
            connection.request("POST", self.path, body=body, headers=self._headers)
            response = connection.getresponse()
            answer = response.read(65537)
            if response.status == 503:
                return _RETRY
            if response.status == 401:
                self._warn_unauthorized()
                return _REJECTED
            # 202 = every span is in the ingestion buffer, not yet stored.
            if response.status == 202 and json.loads(answer).get("spans") == count:
                return _DELIVERED
            return _REJECTED
        except Exception:
            return _REJECTED
        finally:
            if connection:
                connection.close()

    def _warn_unauthorized(self):
        with self.lock:
            if self._warned_unauthorized:
                return
            self._warned_unauthorized = True
        # Never the key itself, nor any part of it.
        _logger.warning(
            "Agent Debugger rejected the API key (HTTP 401): spans are dropped. "
            "Set AGENT_DEBUGGER_API_KEY to a current key (scripts/create_user.py or POST /api/v1/auth/key/rotate)."
        )

    def shutdown(self):
        with self.lock:
            if self._stop.is_set():
                return
            self._stop.set()  # wakes a retry that is waiting; it is dropped and counted
            self._retry_queue.put(None)
        # Lets the counters settle. A request already on the wire gets at most 1 s.
        self.force_flush(timeout_millis=1000)

    def force_flush(self, timeout_millis=30000):
        """True when no retry is pending. `export` itself has no queue."""
        with self._settled:
            return self._settled.wait_for(lambda: self._pending == 0, timeout_millis / 1000)
