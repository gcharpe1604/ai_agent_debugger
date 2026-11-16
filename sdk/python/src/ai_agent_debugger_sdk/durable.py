"""Protocol "1" exporter for the durable path: POST /api/v1/traces.

Kept apart from transport.py (local-1: loopback only, metadata only). This one
sends payloads: the capture attributes SpanHandle writes (`debugger.input`,
`debugger.output` and their flags) become `input_*` / `output_*` payload fields
with a state, and the first exception event becomes the error payload.

Policy is docs/proposals/clickhouse-span-record.md §9. No API key yet (handoff
action 6); plain http is accepted for loopback hosts only.
"""

import http.client
import json
import math
import re
import ssl
import threading
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
    """

    def __init__(self, endpoint, capture=None):
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
        self.exported_spans = 0
        self.failures = 0
        self.closed = False
        self.lock = threading.Lock()

    def export(self, spans):
        with self.lock:
            if self.closed:
                self.failures += 1
                return SpanExportResult.FAILURE
            try:
                bodies = encode_bodies(spans, self.capture)
            except Exception:
                # Fail open without logging captured content or exceptions.
                self.failures += 1
                return SpanExportResult.FAILURE
            delivered = True
            for body, count in bodies:
                if self._post(body, count):
                    self.exported_spans += count
                else:
                    self.failures += 1
                    delivered = False
            return SpanExportResult.SUCCESS if delivered else SpanExportResult.FAILURE

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
            connection.request("POST", self.path, body=body, headers={"Content-Type": "application/json"})
            response = connection.getresponse()
            receipt = json.loads(response.read(65537))
            # 202 = every span is in the ingestion buffer, not yet stored.
            return response.status == 202 and receipt.get("spans") == count
        except Exception:
            return False
        finally:
            if connection:
                connection.close()

    def shutdown(self):
        with self.lock:
            self.closed = True

    def force_flush(self, timeout_millis=30000):
        return True  # No internal queue: the host's BatchSpanProcessor owns flushing.
