"""Bounded HTTP/JSON exporter for the explicit local capture profile.

Remote authenticated production delivery remains outside this implementation.
"""

import http.client
import json
import threading
from urllib.parse import urlsplit

from opentelemetry.sdk.trace.export import SpanExporter, SpanExportResult
from opentelemetry.trace import format_span_id, format_trace_id

LOCAL_ENDPOINT = "http://127.0.0.1:8008/api/v1/local/traces"

_ATTRIBUTES = {"debugger.operation.type", "debugger.execution.mode", "debugger.local_dependencies", "debugger.model.name", "debugger.model.provider", "debugger.step", "debugger.attempt", "debugger.retry_of", "debugger.result.status", "http.response.status_code"}


class HttpSpanExporter(SpanExporter):
    def __init__(self, endpoint=LOCAL_ENDPOINT):
        url = urlsplit(endpoint)
        if (url.scheme != "http" or url.hostname not in {"127.0.0.1", "localhost", "::1"}
                or url.path != "/api/v1/local/traces" or url.query or url.fragment or url.username or url.password):
            raise ValueError("Exporter requires the explicit loopback local-capture endpoint")
        self.host, self.port, self.path = url.hostname, url.port or 80, url.path
        self.exported_spans = 0
        self.failures = 0
        self.closed = False
        self.lock = threading.Lock()

    def export(self, spans):
        with self.lock:
            if self.closed or len(spans) > 64:
                self.failures += 1
                return SpanExportResult.FAILURE
            connection = None
            try:
                records = []
                for span in spans:
                    if span.end_time is None:
                        raise ValueError("Only ended spans are exported")
                    attributes = {key: value[:1024] if isinstance(value, str) else value for key, value in (span.attributes or {}).items() if key in _ATTRIBUTES and type(value) in (str, int, float, bool)}
                    records.append({
                        "trace_id": format_trace_id(span.context.trace_id),
                        "span_id": format_span_id(span.context.span_id),
                        "parent_span_id": format_span_id(span.parent.span_id) if span.parent else None,
                        "name": span.name[:256],
                        "operation_type": attributes.get("debugger.operation.type", "custom"),
                        "start_time_unix_nano": str(span.start_time),
                        "end_time_unix_nano": str(span.end_time),
                        "status": {"code": span.status.status_code.name},
                        "attributes": attributes,
                        "resource": {"service.name": str(span.resource.attributes.get("service.name", "Not recorded"))[:256]},
                        "events": [{"name": event.name[:128], "time_unix_nano": str(event.timestamp), "attributes": {key: value[:1024] for key, value in (event.attributes or {}).items() if key in {"exception.type", "exception.message"} and isinstance(value, str)}} for event in span.events[:16]],
                    })
                body = json.dumps({"protocol_version": "local-1", "spans": records}, allow_nan=False).encode()
                if len(body) > 256 * 1024:
                    raise ValueError("Bounded local batch exceeded")
                # HTTPConnection ignores environment proxies and does not follow redirects.
                connection = http.client.HTTPConnection(self.host, self.port, timeout=2)
                connection.request("POST", self.path, body=body, headers={"Content-Type": "application/json", "X-Agent-Debugger-Local": "1"})
                response = connection.getresponse()
                receipt = json.loads(response.read(65537))
                if response.status != 200 or receipt.get("accepted") != len(records) or receipt.get("trace_ids") != sorted({record["trace_id"] for record in records}):
                    raise ValueError("Local ingestion did not acknowledge this batch")
                self.exported_spans += len(records)
                return SpanExportResult.SUCCESS
            except Exception:
                # Fail open without logging captured content, credentials or exceptions.
                self.failures += 1
                return SpanExportResult.FAILURE
            finally:
                if connection:
                    connection.close()

    def shutdown(self):
        with self.lock:
            self.closed = True

    def force_flush(self, timeout_millis=30000):
        return True  # No internal queue: the host's BatchSpanProcessor owns flushing.
