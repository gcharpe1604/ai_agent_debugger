"""SDK protocol "1" export against the real POST /api/v1/traces route.

The SDK builds the request body; the route validates it and hands SpanRecords
to an in-memory publisher. No broker or database: the API-key lookup
(ingest_user) is replaced too. One test serves the app on a loopback port and
posts to it with the SDK exporter.
"""

import json
import os
from pathlib import Path
import socket
import sys
import threading
import time
import unittest

ROOT = Path(__file__).resolve().parents[2]
for directory in ["backend/src", "sdk/python/src"]:
    sys.path.insert(0, str(ROOT / directory))
# Importing the app requires SESSION_SECRET; this test-only value signs nothing real.
os.environ.setdefault("SESSION_SECRET", "test-only-session-secret")

from fastapi import HTTPException, Request
from fastapi.testclient import TestClient
import uvicorn
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor, SpanExportResult
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from agent_debugger_api.api.routes.traces import get_span_publisher
from agent_debugger_api.auth.deps import ingest_user
from agent_debugger_api.contracts import PayloadState
from agent_debugger_api.contracts.fakes import InMemorySpanPublisher
from agent_debugger_api.db.models import User
from agent_debugger_api.ingest.kafka_publisher import DEFAULT_MAX_REQUEST_SIZE, KafkaSpanPublisher
from agent_debugger_api.ingest.schemas import MAX_PAYLOAD_BYTES as INGEST_MAX_PAYLOAD_BYTES
from agent_debugger_api.ingest.settings import DEFAULT_PROJECT_ID
from agent_debugger_api.main import app
from ai_agent_debugger_sdk import CaptureConfig, Debugger, DurableSpanExporter
from ai_agent_debugger_sdk.capture import MAX_PAYLOAD_BYTES
from ai_agent_debugger_sdk.durable import encode_bodies

SECRET = "sk-synthetic-secret-value"
API_KEY = "adbg_sk_integration-test-key"
USER = User(id=DEFAULT_PROJECT_ID, email="ada@example.com", name="Ada", password_hash="unused",
            project_id=DEFAULT_PROJECT_ID, key_prefix=API_KEY[:12], key_hash="unused")


def key_owner(request: Request) -> User:
    """Stands in for ingest_user (no database): API_KEY as a bearer token is USER, anything else 401."""
    if request.headers.get("authorization") != f"Bearer {API_KEY}":
        raise HTTPException(401, "Invalid API key")
    return USER


class Unserializable:
    def __str__(self):
        raise AssertionError("Application __str__ must not be invoked")

    __repr__ = __str__


class DurablePayloadTests(unittest.TestCase):
    def setUp(self):
        self.publisher = InMemorySpanPublisher()
        app.dependency_overrides[get_span_publisher] = lambda: self.publisher
        app.dependency_overrides[ingest_user] = key_owner
        self.addCleanup(app.dependency_overrides.clear)
        self.client = TestClient(app, client=("203.0.113.7", 50000), headers={"Authorization": f"Bearer {API_KEY}"})

    @staticmethod
    def spans_from(work, capture):
        sink = InMemorySpanExporter()
        provider = TracerProvider(resource=Resource({"service.name": "integration"}))
        provider.add_span_processor(SimpleSpanProcessor(sink))
        try:
            work(Debugger("integration", capture=capture, tracer_provider=provider))
        finally:
            provider.shutdown()
        return sink.get_finished_spans()

    def run_and_ingest(self, work, **capture_options):
        """Run `work(debugger)`, export its spans as the SDK would, return SpanRecords by name."""
        capture = CaptureConfig(**capture_options)
        for body, count in encode_bodies(self.spans_from(work, capture), capture):
            response = self.client.post("/api/v1/traces", content=body, headers={"Content-Type": "application/json"})
            self.assertEqual(response.status_code, 202, response.text)
            self.assertEqual(response.json()["spans"], count)
        return {record.span_name: record for _, record in self.publisher.acked}

    def test_states_and_payloads_reach_the_span_record(self):
        def work(debugger):
            with debugger.run("run"):
                with debugger.tool("redacted") as span:
                    span.set_input({"order": 42, "api_key": SECRET})
                with debugger.retrieval("truncated") as span:
                    span.set_output({"document": "policy " * 10_000})
                with debugger.tool("unsupported") as span:
                    span.set_input(Unserializable())
                    span.set_output({"rows": 3})
                try:
                    with debugger.model("failed"):
                        raise TimeoutError("provider timed out")
                except TimeoutError:
                    pass

        records = self.run_and_ingest(work, max_payload_bytes=2048)
        redacted, truncated, unsupported, failed, run = (
            records[name] for name in ("redacted", "truncated", "unsupported", "failed", "run")
        )

        self.assertIs(redacted.input_state, PayloadState.REDACTED)
        self.assertEqual(json.loads(redacted.input_payload), {"order": 42, "api_key": "[redacted]"})
        self.assertIs(redacted.output_state, PayloadState.UNAVAILABLE)

        self.assertIs(truncated.output_state, PayloadState.TRUNCATED)
        self.assertLessEqual(len(truncated.output_payload.encode()), 2048)
        self.assertTrue(("policy " * 10_000).startswith(json.loads(truncated.output_payload)["document"]))

        self.assertIs(unsupported.input_state, PayloadState.UNAVAILABLE)
        self.assertEqual(unsupported.input_payload, "")
        self.assertEqual(unsupported.attributes["debugger.input.unsupported"], "true")
        self.assertIs(unsupported.output_state, PayloadState.CAPTURED)
        self.assertEqual(json.loads(unsupported.output_payload), {"rows": 3})

        self.assertIs(failed.error_state, PayloadState.CAPTURED)
        self.assertEqual(failed.error_type, "TimeoutError")
        self.assertEqual(
            json.loads(failed.error_payload), {"type": "TimeoutError", "message": "provider timed out"}
        )
        self.assertEqual(failed.status_code.value, "ERROR")

        self.assertIsNone(run.parent_span_id)
        self.assertEqual(redacted.parent_span_id, run.span_id)
        self.assertEqual(run.service_name, "integration")
        self.assertNotIn(SECRET, "".join(record.model_dump_json() for record in records.values()))

    def test_disabled_capture_is_stored_as_disabled_and_empty(self):
        def work(debugger):
            try:
                with debugger.tool("tool") as span:
                    span.set_input({"prompt": SECRET})
                    span.set_output(Unserializable())
                    raise ValueError(SECRET)
            except ValueError:
                pass

        record = self.run_and_ingest(
            work, capture_inputs=False, capture_outputs=False, capture_errors=False
        )["tool"]
        for kind in ("input", "output", "error"):
            self.assertIs(getattr(record, f"{kind}_state"), PayloadState.DISABLED)
            self.assertEqual(getattr(record, f"{kind}_payload"), "")
        self.assertEqual(record.error_type, "ValueError")
        self.assertNotIn(SECRET, record.model_dump_json())

    def test_sdk_and_ingest_agree_on_the_payload_cap(self):
        # The SDK never produces a payload the ingest would reject (§9 P3, P9).
        self.assertEqual(MAX_PAYLOAD_BYTES, INGEST_MAX_PAYLOAD_BYTES)

    def test_three_payloads_at_the_hard_cap_fit_one_kafka_record(self):
        # Quotes are the worst case: each doubles when the payload text is a JSON string.
        worst = '"' * (MAX_PAYLOAD_BYTES * 2)

        def work(debugger):
            try:
                with debugger.tool("tool") as span:
                    span.set_input(worst)
                    span.set_output(worst)
                    for index in range(100):
                        span.set_attribute(f"attribute.{index}", "é" * 4000)
                    raise ValueError(worst)
            except ValueError:
                pass

        record = self.run_and_ingest(work, max_payload_bytes=MAX_PAYLOAD_BYTES)["tool"]
        for kind in ("input", "output", "error"):
            self.assertIs(getattr(record, f"{kind}_state"), PayloadState.TRUNCATED)
            self.assertGreater(len(getattr(record, f"{kind}_payload")), MAX_PAYLOAD_BYTES - 16)
        # The size check the real publisher runs before sending (no broker needed).
        ((_, value),) = KafkaSpanPublisher("unused:9092", "unused")._encode([record])
        self.assertLess(len(value), DEFAULT_MAX_REQUEST_SIZE - 64 * 1024)

    def test_exporter_delivers_over_http_to_the_running_app(self):
        # The app served by uvicorn on a loopback port; only the publisher and the key lookup are replaced.
        listener = socket.socket()
        listener.bind(("127.0.0.1", 0))
        server = uvicorn.Server(uvicorn.Config(app, log_level="error"))
        thread = threading.Thread(target=server.run, kwargs={"sockets": [listener]}, daemon=True)
        thread.start()

        def stop():
            server.should_exit = True
            thread.join(timeout=10)
            listener.close()

        self.addCleanup(stop)
        deadline = time.monotonic() + 10
        while not server.started and time.monotonic() < deadline:
            time.sleep(0.02)
        self.assertTrue(server.started)

        def work(debugger):
            with debugger.run("run"):
                with debugger.tool("lookup") as span:
                    span.set_input({"order": 42, "token": SECRET})
                    span.set_output({"status": "shipped"})

        capture = CaptureConfig()
        endpoint = f"http://127.0.0.1:{listener.getsockname()[1]}/api/v1/traces"
        # Without the key: 401, dropped, not retried.
        keyless = DurableSpanExporter(endpoint, capture, api_key="")
        self.assertIs(keyless.export(self.spans_from(work, capture)), SpanExportResult.FAILURE)
        self.assertEqual((keyless.failures, keyless.dropped_spans, keyless.retries), (1, 2, 0))
        self.assertEqual(self.publisher.acked, [])

        exporter = DurableSpanExporter(endpoint, capture, api_key=API_KEY)
        result = exporter.export(self.spans_from(work, capture))

        self.assertIs(result, SpanExportResult.SUCCESS)
        self.assertEqual((exporter.exported_spans, exporter.failures), (2, 0))
        records = {record.span_name: record for _, record in self.publisher.acked}
        self.assertEqual(set(records), {"run", "lookup"})
        self.assertIs(records["lookup"].input_state, PayloadState.REDACTED)
        self.assertEqual(json.loads(records["lookup"].input_payload), {"order": 42, "token": "[redacted]"})
        self.assertEqual(json.loads(records["lookup"].output_payload), {"status": "shipped"})
        self.assertEqual(records["run"].received_at, records["lookup"].received_at)


if __name__ == "__main__":
    unittest.main()
