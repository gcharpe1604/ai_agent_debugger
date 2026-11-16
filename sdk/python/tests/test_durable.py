"""Protocol "1" export: capture flags -> payload fields and states.

Spans come from a real provider. HTTP goes to a stub server on loopback only.
"""

import json
import threading
import time
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest
from ai_agent_debugger_sdk import CaptureConfig, Debugger, DurableSpanExporter, TraceSession
from ai_agent_debugger_sdk import durable
from ai_agent_debugger_sdk.capture import MAX_PAYLOAD_BYTES
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor, SpanExportResult
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

SECRET = "sk-synthetic-secret-value"
KAFKA_RECORD_LIMIT = 1_048_576


class Hostile:
    def __str__(self):
        raise AssertionError("Application __str__ must not be invoked")

    def __repr__(self):
        raise AssertionError("Application __repr__ must not be invoked")

    def __iter__(self):
        raise AssertionError("Application iteration must not be invoked")


@contextmanager
def recording(**capture_options):
    capture = CaptureConfig(**capture_options)
    sink = InMemorySpanExporter()
    provider = TracerProvider(resource=Resource({"service.name": "durable-tests"}))
    provider.add_span_processor(SimpleSpanProcessor(sink))
    try:
        yield Debugger("durable-tests", capture=capture, tracer_provider=provider), sink, capture
    finally:
        provider.shutdown()


def wire(sink, capture, name="tool"):
    span = next(span for span in sink.get_finished_spans() if span.name == name)
    return durable.encode_span(span, capture)


# --- payload states -------------------------------------------------------


def test_secret_field_is_redacted_and_never_leaves_the_process():
    with recording() as (debugger, sink, capture):
        with debugger.tool("tool") as span:
            span.set_input({"query": "refund", "api_key": SECRET, "nested": [{"Authorization": SECRET}]})
            span.set_attribute("http.request.header.authorization", SECRET)
        record = wire(sink, capture)
    assert record["input_state"] == "redacted"
    assert json.loads(record["input_payload"]) == {
        "query": "refund",
        "api_key": "[redacted]",
        "nested": [{"Authorization": "[redacted]"}],
    }
    assert record["attributes"]["http.request.header.authorization"] == "[redacted]"
    assert SECRET not in json.dumps(record)


def test_secret_named_attribute_written_straight_to_the_otel_span_is_redacted():
    with recording() as (debugger, sink, capture):
        with debugger.tool("tool") as span:
            span._span.set_attribute("x-api-key", SECRET)
        record = wire(sink, capture)
    assert record["attributes"]["x-api-key"] == "[redacted]"
    assert SECRET not in json.dumps(record)


def test_oversized_payload_is_truncated_to_valid_json_with_a_real_prefix():
    document = "refund policy " * 10_000
    with recording(max_payload_bytes=1024) as (debugger, sink, capture):
        with debugger.retrieval("tool") as span:
            span.set_output({"document": document, "score": 0.9})
        record = wire(sink, capture)
    assert record["output_state"] == "truncated"
    assert len(record["output_payload"].encode("utf-8")) <= 1024
    stored = json.loads(record["output_payload"])["document"]
    assert len(stored) > 900 and document.startswith(stored)


def test_non_ascii_overflow_keeps_a_prefix_instead_of_collapsing():
    with recording(max_payload_bytes=64) as (debugger, sink, capture):
        with debugger.tool("tool") as span:
            span.set_input("é" * 10_000)
        record = wire(sink, capture)
    assert record["input_state"] == "truncated"
    assert len(record["input_payload"]) <= 64
    assert json.loads(record["input_payload"]) == "é" * 10


def test_items_past_the_byte_budget_are_dropped_and_the_rest_stays_valid_json():
    with recording(max_payload_bytes=128) as (debugger, sink, capture):
        with debugger.tool("tool") as span:
            span.set_input([f"item-{index}" for index in range(100)])
        record = wire(sink, capture)
    stored = json.loads(record["input_payload"])
    assert record["input_state"] == "truncated"
    assert len(record["input_payload"]) <= 128
    assert 5 < len(stored) < 100 and stored == [f"item-{index}" for index in range(len(stored))]


def test_disabled_capture_gives_state_disabled_and_an_empty_payload():
    with recording(capture_inputs=False, capture_outputs=False) as (debugger, sink, capture):
        with debugger.tool("tool") as span:
            span.set_input(Hostile())
            span.set_output({"answer": SECRET})
        record = wire(sink, capture)
    assert (record["input_state"], record["input_payload"]) == ("disabled", "")
    assert (record["output_state"], record["output_payload"]) == ("disabled", "")
    assert SECRET not in json.dumps(record)


def test_payload_that_was_never_set_is_unavailable():
    with recording() as (debugger, sink, capture):
        with debugger.tool("tool"):
            pass
        record = wire(sink, capture)
    for kind in ("input", "output", "error"):
        assert (record[f"{kind}_state"], record[f"{kind}_payload"]) == ("unavailable", "")


@pytest.mark.parametrize("value", [Hostile(), b"binary", {1, 2}], ids=["object", "bytes", "set"])
def test_non_json_object_is_never_stringified_and_is_unavailable(value):
    with recording() as (debugger, sink, capture):
        with debugger.tool("tool") as span:
            span.set_input(value)
        record = wire(sink, capture)
    assert (record["input_state"], record["input_payload"]) == ("unavailable", "")
    assert record["attributes"]["debugger.input.unsupported"] is True


def test_nested_non_json_object_becomes_a_marker_and_the_rest_is_captured():
    with recording() as (debugger, sink, capture):
        with debugger.tool("tool") as span:
            span.set_output({"rows": 3, "client": Hostile()})
        record = wire(sink, capture)
    assert record["output_state"] == "captured"
    assert json.loads(record["output_payload"]) == {"rows": 3, "client": "[unsupported]"}
    assert record["attributes"]["debugger.output.unsupported"] is True


def test_truncated_wins_over_redacted_and_the_redacted_flag_is_kept():
    with recording(max_payload_bytes=128) as (debugger, sink, capture):
        with debugger.tool("tool") as span:
            span.set_input({"password": SECRET, "text": "x" * 5000})
        record = wire(sink, capture)
    assert record["input_state"] == "truncated"
    assert record["attributes"]["debugger.input.redacted"] is True
    assert json.loads(record["input_payload"])["password"] == "[redacted]"


def test_capture_attributes_are_not_copied_into_wire_attributes():
    with recording() as (debugger, sink, capture):
        with debugger.tool("tool") as span:
            span.set_input({"q": "visible-input"})
        record = wire(sink, capture)
    assert record["input_state"] == "captured"
    assert "visible-input" not in json.dumps(record["attributes"])
    assert not [key for key in record["attributes"] if key.startswith("debugger.input")]


# --- error payload --------------------------------------------------------


def test_exception_becomes_a_bounded_error_payload_without_a_stack_trace():
    with recording() as (debugger, sink, capture):
        with pytest.raises(ValueError):
            with debugger.tool("tool"):
                raise ValueError("card declined")
        record = wire(sink, capture)
    assert record["status"]["code"] == "ERROR"
    assert record["error_type"] == "ValueError"
    assert record["error_state"] == "captured"
    assert json.loads(record["error_payload"]) == {"type": "ValueError", "message": "card declined"}
    body = json.dumps(record)
    assert "Traceback" not in body and "stacktrace" not in body


def test_long_exception_message_is_truncated():
    with recording(max_payload_bytes=128) as (debugger, sink, capture):
        with pytest.raises(ValueError):
            with debugger.tool("tool"):
                raise ValueError("x" * 5000)
        record = wire(sink, capture)
    assert record["error_state"] == "truncated"
    assert len(record["error_payload"]) <= 128
    assert json.loads(record["error_payload"])["type"] == "ValueError"


def test_error_capture_can_be_disabled_everywhere_the_message_appears():
    with recording(capture_errors=False) as (debugger, sink, capture):
        with pytest.raises(ValueError):
            with debugger.tool("tool"):
                raise ValueError(SECRET)
        record = wire(sink, capture)
    assert (record["error_state"], record["error_payload"]) == ("disabled", "")
    assert record["error_type"] == "ValueError"
    assert SECRET not in json.dumps(record)


# --- size bound -----------------------------------------------------------


def test_worst_case_span_stays_under_the_kafka_record_limit():
    # Quotes double when a JSON text is embedded as a JSON string: worst case.
    worst = '"' * (MAX_PAYLOAD_BYTES * 2)
    with recording(max_payload_bytes=MAX_PAYLOAD_BYTES) as (debugger, sink, capture):
        with pytest.raises(ValueError):
            with debugger.tool("tool") as span:
                span.set_input(worst)
                span.set_output(worst)
                # Stay under OTel's 128-attribute limit: past it the oldest
                # attributes, the captured payloads included, are evicted.
                for index in range(100):
                    span.set_attribute(f"attribute.{index}", "é" * 4000)
                raise ValueError(worst)
        record = wire(sink, capture)
    for kind in ("input", "output", "error"):
        assert record[f"{kind}_state"] == "truncated"
        assert MAX_PAYLOAD_BYTES - 16 <= len(record[f"{kind}_payload"]) <= MAX_PAYLOAD_BYTES
    assert record["attributes"]["debugger.export.dropped_attributes"] > 90
    assert len(json.dumps(record)) < KAFKA_RECORD_LIMIT - 64 * 1024


def test_payload_cap_cannot_be_configured_above_the_durable_maximum():
    assert MAX_PAYLOAD_BYTES == 131_072
    CaptureConfig(max_payload_bytes=MAX_PAYLOAD_BYTES)
    with pytest.raises(ValueError):
        CaptureConfig(max_payload_bytes=MAX_PAYLOAD_BYTES + 1)
    with pytest.raises(ValueError):
        CaptureConfig(capture_errors="yes")


def test_payload_written_past_the_sdk_cap_is_not_exported():
    with recording() as (debugger, sink, capture):
        with debugger.tool("tool") as span:
            span._span.set_attribute("debugger.input", "x" * (MAX_PAYLOAD_BYTES + 1))
        record = wire(sink, capture)
    assert (record["input_state"], record["input_payload"]) == ("unavailable", "")


# --- transport ------------------------------------------------------------


@pytest.mark.parametrize(
    "endpoint",
    [
        "http://127.0.0.1:8008/api/v1/local/traces",
        "http://collector.example/api/v1/traces",
        "https://collector.example/api/v1/traces?project=1",
        "https://user:pw@collector.example/api/v1/traces",
        "ftp://127.0.0.1/api/v1/traces",
    ],
    ids=["local-path", "plain-http-remote", "query", "userinfo", "scheme"],
)
def test_endpoint_must_be_the_durable_route_and_https_off_loopback(endpoint):
    with pytest.raises(ValueError):
        DurableSpanExporter(endpoint)


def test_https_remote_and_plain_loopback_endpoints_are_accepted():
    assert DurableSpanExporter("https://collector.example/api/v1/traces").secure is True
    assert DurableSpanExporter("http://localhost:8008/api/v1/traces").secure is False


class _Collector(BaseHTTPRequestHandler):
    def do_POST(self):
        body = self.rfile.read(int(self.headers["Content-Length"]))
        self.server.requests.append((self.path, dict(self.headers), body))
        self.server.times.append(time.monotonic())
        spans = len(json.loads(body)["spans"])
        answer = json.dumps({"status": "accepted", "protocol_version": "1", "spans": spans}).encode()
        # Scripted statuses first, then the default.
        self.send_response(self.server.script.pop(0) if self.server.script else self.server.status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(answer)))
        self.end_headers()
        self.wfile.write(answer)

    def log_message(self, *args):
        pass


@pytest.fixture
def collector():
    server = ThreadingHTTPServer(("127.0.0.1", 0), _Collector)
    server.requests, server.status, server.script, server.times = [], 202, [], []
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield server
    server.shutdown()
    server.server_close()
    thread.join(timeout=5)


def finished_spans(count):
    with recording() as (debugger, sink, capture):
        with debugger.run("run"):
            for index in range(count - 1):
                with debugger.tool(f"tool-{index}") as span:
                    span.set_input({"index": index})
        return sink.get_finished_spans()


def test_export_posts_a_protocol_1_envelope_and_counts_acknowledged_spans(collector):
    exporter = DurableSpanExporter(f"http://127.0.0.1:{collector.server_port}/api/v1/traces")
    spans = finished_spans(3)
    assert exporter.export(spans) is SpanExportResult.SUCCESS
    assert (exporter.exported_spans, exporter.failures) == (3, 0)
    (path, headers, body), = collector.requests
    envelope = json.loads(body)
    assert path == "/api/v1/traces" and headers["Content-Type"] == "application/json"
    assert envelope["protocol_version"] == "1" and len(envelope["spans"]) == 3
    root = next(span for span in envelope["spans"] if span["name"] == "run")
    child = next(span for span in envelope["spans"] if span["name"] == "tool-0")
    assert child["trace_id"] == root["trace_id"] and child["parent_span_id"] == root["span_id"]
    assert root["parent_span_id"] is None and root["operation_type"] == "run"
    assert type(child["start_time"]) is int and child["end_time"] >= child["start_time"]
    assert child["service_name"] == "durable-tests"
    assert "project_id" not in child and "received_at" not in child


def test_unreachable_collector_is_a_failure_and_never_raises():
    exporter = DurableSpanExporter("http://127.0.0.1:9/api/v1/traces")
    assert exporter.export(finished_spans(1)) is SpanExportResult.FAILURE
    assert (exporter.failures, exporter.dropped_spans, exporter.retries) == (1, 1, 0)


# --- retry on 503 ---------------------------------------------------------


@pytest.fixture
def fast_retries(monkeypatch):
    monkeypatch.setattr(durable, "RETRY_DELAYS", (0.05, 0.1, 0.2))


def endpoint(collector):
    return f"http://127.0.0.1:{collector.server_port}/api/v1/traces"


def test_retry_schedule_is_three_retries_with_exponential_backoff():
    assert durable.RETRY_DELAYS == (1.0, 2.0, 4.0)


def test_503_is_retried_on_the_background_thread_until_accepted(collector, fast_retries):
    collector.script = [503, 503]
    exporter = DurableSpanExporter(endpoint(collector))
    # Not delivered yet when export returns: the retry is pending.
    assert exporter.export(finished_spans(2)) is SpanExportResult.FAILURE
    assert exporter.force_flush(timeout_millis=5000) is True
    assert (exporter.exported_spans, exporter.failures, exporter.dropped_spans) == (2, 0, 0)
    assert exporter.retries == 2
    bodies = [body for _, _, body in collector.requests]
    assert len(bodies) == 3 and len(set(bodies)) == 1  # the same batch, resent whole


def test_503_is_dropped_and_counted_after_three_retries(collector, fast_retries):
    collector.status = 503
    exporter = DurableSpanExporter(endpoint(collector))
    assert exporter.export(finished_spans(2)) is SpanExportResult.FAILURE
    assert exporter.force_flush(timeout_millis=5000) is True
    assert len(collector.requests) == 4  # first attempt + 3 retries, then no more
    assert (exporter.exported_spans, exporter.failures, exporter.dropped_spans) == (0, 1, 2)
    assert exporter.retries == 3
    time.sleep(0.3)
    assert len(collector.requests) == 4


def test_backoff_grows_between_retries(collector, fast_retries):
    collector.status = 503
    exporter = DurableSpanExporter(endpoint(collector))
    exporter.export(finished_spans(1))
    assert exporter.force_flush(timeout_millis=5000) is True
    gaps = [later - earlier for earlier, later in zip(collector.times, collector.times[1:])]
    assert len(gaps) == 3
    for gap, delay in zip(gaps, durable.RETRY_DELAYS):
        assert gap >= delay - 0.01
    assert gaps[2] > gaps[0]


@pytest.mark.parametrize("status", [413, 422, 400, 500, 502], ids=str)
def test_other_rejections_are_dropped_at_once_and_never_retried(collector, fast_retries, status):
    collector.status = status
    exporter = DurableSpanExporter(endpoint(collector))
    assert exporter.export(finished_spans(2)) is SpanExportResult.FAILURE
    assert exporter.force_flush(timeout_millis=1000) is True
    time.sleep(0.3)
    assert len(collector.requests) == 1
    assert (exporter.failures, exporter.dropped_spans, exporter.retries) == (1, 2, 0)


def test_export_returns_without_waiting_for_the_backoff(collector, monkeypatch):
    monkeypatch.setattr(durable, "RETRY_DELAYS", (30.0, 30.0, 30.0))
    collector.status = 503
    exporter = DurableSpanExporter(endpoint(collector))
    started = time.monotonic()
    assert exporter.export(finished_spans(3)) is SpanExportResult.FAILURE
    assert time.monotonic() - started < 2
    assert exporter.force_flush(timeout_millis=100) is False  # still pending
    # Shutdown gives the pending batch up instead of waiting 30 s for it.
    exporter.shutdown()
    assert time.monotonic() - started < 4
    assert (exporter.exported_spans, exporter.failures, exporter.dropped_spans) == (0, 1, 3)
    assert len(collector.requests) == 1
    assert exporter.export(finished_spans(1)) is SpanExportResult.FAILURE


def test_retries_do_not_run_on_the_thread_that_called_export(collector, fast_retries, monkeypatch):
    seen = []
    original = DurableSpanExporter._post

    def recording_post(self, body, count):
        seen.append(threading.current_thread())
        return original(self, body, count)

    monkeypatch.setattr(DurableSpanExporter, "_post", recording_post)
    collector.script = [503]
    exporter = DurableSpanExporter(endpoint(collector))
    exporter.export(finished_spans(1))
    assert exporter.force_flush(timeout_millis=5000) is True
    assert len(seen) == 2
    assert seen[0] is threading.current_thread() and seen[1] is not threading.current_thread()
    assert seen[1].daemon is True


def test_pending_retries_are_bounded(collector, monkeypatch):
    monkeypatch.setattr(durable, "RETRY_DELAYS", (30.0, 30.0, 30.0))
    monkeypatch.setattr(durable, "MAX_PENDING_RETRIES", 1)
    collector.status = 503
    exporter = DurableSpanExporter(endpoint(collector))
    exporter.export(finished_spans(2))  # waits for its retry
    exporter.export(finished_spans(3))  # no room: dropped now
    assert (exporter.failures, exporter.dropped_spans) == (1, 3)
    exporter.shutdown()
    assert (exporter.failures, exporter.dropped_spans) == (2, 5)


def test_batch_is_split_so_no_request_exceeds_the_body_limit(collector, monkeypatch):
    monkeypatch.setattr(durable, "MAX_BODY_BYTES", 2048)
    exporter = DurableSpanExporter(f"http://127.0.0.1:{collector.server_port}/api/v1/traces")
    assert exporter.export(finished_spans(12)) is SpanExportResult.SUCCESS
    assert len(collector.requests) > 1
    assert all(len(body) <= 2048 for _, _, body in collector.requests)
    assert sum(len(json.loads(body)["spans"]) for _, _, body in collector.requests) == 12
    assert exporter.exported_spans == 12


# --- TraceSession ---------------------------------------------------------


def test_trace_session_picks_the_exporter_from_the_endpoint_path(collector):
    endpoint = f"http://127.0.0.1:{collector.server_port}/api/v1/traces"

    def failing():
        raise ValueError(SECRET)

    with pytest.raises(ValueError):
        with TraceSession("agent", endpoint=endpoint, execution_mode="controlled") as session:
            assert type(session.exporter) is DurableSpanExporter
            session.wrap_callable(failing, "tool", "pay")()
    spans = [span for _, _, body in collector.requests for span in json.loads(body)["spans"]]
    tool = next(span for span in spans if span["name"] == "pay")
    root = next(span for span in spans if span["name"] == "agent")
    assert root["execution_mode"] == "controlled"
    assert tool["error_type"] == "ValueError" and tool["error_state"] == "captured"
    # TraceSession records the exception type and operation, not its message.
    assert json.loads(tool["error_payload"]) == {"type": "ValueError", "message": "ValueError during pay"}
    assert (tool["input_state"], tool["output_state"]) == ("unavailable", "unavailable")
    assert all(SECRET not in body.decode() for _, _, body in collector.requests)


def test_trace_session_waits_for_a_pending_retry_when_the_run_ends(collector, fast_retries, capsys):
    collector.script = [503]
    with TraceSession("agent", endpoint=endpoint(collector)) as session:
        session.wrap_callable(lambda: 1, "tool", "lookup")()
    assert len(collector.requests) == 2
    assert (session.exporter.exported_spans, session.exporter.failures) == (2, 0)
    assert "exported (2 acknowledged spans)" in capsys.readouterr().err


def test_trace_session_still_uses_the_local_exporter_for_the_local_route():
    from ai_agent_debugger_sdk import HttpSpanExporter

    with TraceSession("agent", endpoint="http://127.0.0.1:9/api/v1/local/traces") as session:
        assert type(session.exporter) is HttpSpanExporter
