"""Focused telemetry regressions; no providers, DBs or external requests."""

from copy import deepcopy
import json
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
for directory in ["backend/src", "sdk/python/src"]:
    sys.path.insert(0, str(ROOT / directory))

from fastapi import HTTPException
from pydantic import ValidationError
from agent_debugger_api.traces.schemas import Batch
from agent_debugger_api.traces.repository import LocalMemoryRepository
from agent_debugger_api.traces.service import run_summary
from agent_debugger_api.api.routes.ingestion import local_repository
from starlette.requests import Request
from types import SimpleNamespace
from ai_agent_debugger_sdk import Debugger, CaptureConfig
from ai_agent_debugger_sdk.transport import HttpSpanExporter
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor, SpanExportResult
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter


def record(span_id="1" * 16, parent=None, kind="run", status="OK"):
    return {"trace_id": "1" * 32, "span_id": span_id, "parent_span_id": parent,
            "name": "controlled operation", "operation_type": kind,
            "start_time_unix_nano": "1000000", "end_time_unix_nano": "2000000",
            "status": {"code": status}, "attributes": {}, "events": [],
            "resource": {"service.name": "unit-test"}}


def batch(*spans):
    return Batch.model_validate({"protocol_version": "local-1", "spans": list(spans)})


class StoreTests(unittest.TestCase):
    def test_local_access_is_explicit_and_rejects_foreign_peer_host_and_origin(self):
        repository = LocalMemoryRepository()
        def request(peer="127.0.0.1", host="127.0.0.1:8008", origin=None):
            headers = [(b"host", host.encode())]
            if origin:
                headers.append((b"origin", origin.encode()))
            return Request({"type": "http", "scheme": "http", "path": "/api/v1/local/status", "query_string": b"", "method": "GET", "headers": headers, "client": (peer, 1234), "server": ("127.0.0.1", 8008), "app": SimpleNamespace(state=SimpleNamespace(trace_repository=repository))})
        with patch.dict(os.environ, {"AGENT_DEBUGGER_LOCAL_MODE": "0"}), self.assertRaises(HTTPException) as denied:
            local_repository(request())
        self.assertEqual(denied.exception.status_code, 503)
        with patch.dict(os.environ, {"AGENT_DEBUGGER_LOCAL_MODE": "1"}):
            self.assertIs(local_repository(request()), repository)
            for values in [{"peer": "192.0.2.2"}, {"host": "example.invalid"}, {"origin": "https://example.invalid"}]:
                with self.subTest(values=values), self.assertRaises(HTTPException) as denied:
                    local_repository(request(**values))
                self.assertEqual(denied.exception.status_code, 403)

    def test_child_before_root_idempotency_and_immutable_conflict(self):
        store = LocalMemoryRepository()
        child = record("2" * 16, "1" * 16, "tool", "ERROR")
        store.ingest(batch(child))
        self.assertIsNone(run_summary("1" * 32, store.read("1" * 32))["root_span_id"])
        store.ingest(batch(record()))
        store.ingest(batch(child))
        self.assertEqual(len(store.read("1" * 32)), 2)
        summary = run_summary("1" * 32, store.read("1" * 32))
        self.assertEqual((summary["status"], summary["recorded_error_spans"], summary["completeness"]), ("OK", 1, "Unknown"))
        conflict = deepcopy(child)
        conflict["name"] = "changed after capture"
        with self.assertRaises(HTTPException) as error:
            store.ingest(batch(conflict))
        self.assertEqual(error.exception.status_code, 409)
        self.assertEqual(store.read("1" * 32)[child["span_id"]]["name"], child["name"])

    def test_capacity_failure_is_atomic_and_ttl_is_explicit(self):
        store = LocalMemoryRepository()
        store.ingest(batch(record()))
        second = record("2" * 16)
        second["trace_id"] = "2" * 32
        with patch("agent_debugger_api.traces.repository.MAX_RUNS", 1), self.assertRaises(HTTPException):
            store.ingest(batch(second))
        self.assertEqual(list(store.read()), ["1" * 32])
        store.created["1" * 32] -= 4 * 60 * 60 + 1
        self.assertEqual(store.read(), {})

    def test_invalid_identity_timing_payload_and_batch_size_are_rejected(self):
        for change in [{"span_id": "0" * 16}, {"parent_span_id": "1" * 16}, {"end_time_unix_nano": "1"}, {"attributes": {"debugger.input": "not allowed"}}]:
            with self.subTest(change=change), self.assertRaises(ValidationError):
                batch({**record(), **change})
        with self.assertRaises(ValidationError):
            batch(*[record()] * 65)


class FirstErrorTests(unittest.TestCase):
    """first_error = earliest ERROR span with no ERROR descendants; null without ERROR spans."""

    @staticmethod
    def spans(*items):
        return {span["span_id"]: span for span in items}

    @staticmethod
    def timed(span_id, parent, kind, status, start, exception=None):
        span = record(span_id, parent, kind, status)
        span["start_time_unix_nano"], span["end_time_unix_nano"] = str(start), str(start + 10)
        if exception:
            span["events"] = [{"name": "exception", "time_unix_nano": str(start + 5), "attributes": {"exception.type": exception}}]
        return span

    def test_no_error_spans_gives_null(self):
        summary = run_summary("1" * 32, self.spans(record(), record("2" * 16, "1" * 16, "tool")))
        self.assertIsNone(summary["first_error"])

    def test_nested_errors_pick_the_deepest_not_the_parents(self):
        spans = self.spans(
            self.timed("1" * 16, None, "run", "ERROR", 100),
            self.timed("2" * 16, "1" * 16, "agent", "ERROR", 200),
            self.timed("3" * 16, "2" * 16, "tool", "ERROR", 300, "ToolTimeout"),
            self.timed("4" * 16, "2" * 16, "model", "OK", 150),
        )
        self.assertEqual(run_summary("1" * 32, spans)["first_error"], {
            "span_id": "3" * 16, "span_name": "controlled operation", "operation_type": "tool",
            "exception_type": "ToolTimeout", "error_span_count_without_error_children": 1})

    def test_error_carried_through_an_ok_span_does_not_select_the_root(self):
        # Shape of controlled TOOL-05: run ERROR > agent OK > three failed pay attempts.
        spans = self.spans(
            self.timed("1" * 16, None, "run", "ERROR", 100),
            self.timed("2" * 16, "1" * 16, "agent", "OK", 110),
            self.timed("3" * 16, "2" * 16, "tool", "ERROR", 200, "ToolTimeout"),
            self.timed("4" * 16, "2" * 16, "tool", "ERROR", 300, "ToolTimeout"),
            self.timed("5" * 16, "2" * 16, "tool", "ERROR", 400, "ToolTimeout"),
        )
        first = run_summary("1" * 32, spans)["first_error"]
        self.assertEqual((first["span_id"], first["exception_type"], first["error_span_count_without_error_children"]), ("3" * 16, "ToolTimeout", 3))

    def test_missing_parent_keeps_the_orphan_error(self):
        orphan = self.timed("3" * 16, "9" * 16, "tool", "ERROR", 50, "ToolError")
        spans = self.spans(self.timed("1" * 16, None, "run", "ERROR", 100), orphan)
        first = run_summary("1" * 32, spans)["first_error"]
        self.assertEqual((first["span_id"], first["error_span_count_without_error_children"]), ("3" * 16, 2))

    def test_sibling_leaves_earliest_start_wins_and_all_are_counted(self):
        spans = self.spans(
            self.timed("1" * 16, None, "run", "ERROR", 100),
            self.timed("2" * 16, "1" * 16, "tool", "ERROR", 500),
            self.timed("3" * 16, "1" * 16, "tool", "ERROR", 300),
            self.timed("4" * 16, "1" * 16, "api", "ERROR", 400),
        )
        first = run_summary("1" * 32, spans)["first_error"]
        self.assertEqual((first["span_id"], first["exception_type"], first["error_span_count_without_error_children"]), ("3" * 16, None, 3))

    def test_retries_failed_attempt_is_first_error_even_when_recovered(self):
        failed = self.timed("2" * 16, "1" * 16, "tool", "ERROR", 200, "ToolTimeout")
        retry = self.timed("3" * 16, "1" * 16, "tool", "OK", 300)
        retry["attributes"]["debugger.retry_of"] = "2" * 16
        summary = run_summary("1" * 32, self.spans(self.timed("1" * 16, None, "run", "OK", 100), failed, retry))
        self.assertEqual((summary["status"], summary["recorded_recovered_retry"]), ("OK", True))
        self.assertEqual(summary["first_error"]["span_id"], "2" * 16)

    def test_both_attempts_fail_earlier_attempt_wins_ties_break_on_span_id(self):
        spans = self.spans(
            self.timed("1" * 16, None, "run", "ERROR", 100),
            self.timed("3" * 16, "1" * 16, "tool", "ERROR", 200),
            self.timed("2" * 16, "1" * 16, "tool", "ERROR", 200),
            self.timed("4" * 16, "1" * 16, "tool", "ERROR", 300),
        )
        first = run_summary("1" * 32, spans)["first_error"]
        self.assertEqual((first["span_id"], first["error_span_count_without_error_children"]), ("2" * 16, 3))


class ExporterTests(unittest.TestCase):
    def test_no_external_endpoints_and_no_proxy_or_payload_export(self):
        for endpoint in ["https://example.com/api/v1/local/traces", "http://127.0.0.1:8008/api/v1/spans", "http://user:pass@localhost/api/v1/local/traces"]:
            with self.assertRaises(ValueError):
                HttpSpanExporter(endpoint)
        memory, provider = InMemorySpanExporter(), TracerProvider()
        provider.add_span_processor(SimpleSpanProcessor(memory))
        debugger = Debugger("unit", capture=CaptureConfig(capture_inputs=False, capture_outputs=False), tracer_provider=provider)
        with debugger.run("actual unit span"):
            from opentelemetry.trace import get_current_span
            span = get_current_span()
            span.set_attribute("api_key", "MUST_NOT_EXPORT")
            span.set_attribute("debugger.input", "MUST_NOT_EXPORT")
        sent = []

        class Connection:
            def __init__(self, host, port, timeout):
                self.assertions = (host, port, timeout)

            def request(self, method, path, body, headers):
                sent.append(json.loads(body))

            def getresponse(self):
                return self

            status = 200

            def read(self, limit):
                return json.dumps({"accepted": 1, "trace_ids": [sent[0]["spans"][0]["trace_id"]]}).encode()

            def close(self):
                pass

        exporter = HttpSpanExporter()
        with patch("ai_agent_debugger_sdk.transport.http.client.HTTPConnection", Connection):
            self.assertEqual(exporter.export(memory.get_finished_spans()), SpanExportResult.SUCCESS)
        self.assertNotIn("MUST_NOT_EXPORT", json.dumps(sent))
        self.assertEqual(exporter.exported_spans, 1)
        with patch("ai_agent_debugger_sdk.transport.http.client.HTTPConnection", side_effect=OSError):
            self.assertEqual(exporter.export(memory.get_finished_spans()), SpanExportResult.FAILURE)
        self.assertEqual(exporter.failures, 1)
        provider.shutdown()


if __name__ == "__main__":
    unittest.main()
