"""POST /api/v1/traces (protocol "1") with the in-memory publisher."""

import json
import os
import time
import unittest
import uuid
from unittest import mock

from fastapi import HTTPException
from fastapi.testclient import TestClient

from agent_debugger_api.api.routes.traces import get_span_publisher
from agent_debugger_api.auth.deps import ingest_user
from agent_debugger_api.contracts.fakes import InMemorySpanPublisher
from agent_debugger_api.ingest.kafka_publisher import KafkaSpanPublisher
from agent_debugger_api.ingest.schemas import MAX_PAYLOAD_BYTES
from agent_debugger_api.ingest.settings import DEFAULT_PROJECT_ID
from agent_debugger_api.main import app
from tests.auth.factories import make_user

T0 = 1_763_000_000_000_000_000
TRACE_1 = "1" * 32
TRACE_2 = "2" * 32
ROOT = "a" * 16
CHILD = "b" * 16
CLIENT_PROJECT = "00000000-0000-4000-8000-0000000000ff"
USER_PROJECT = uuid.UUID("00000000-0000-4000-8000-0000000000aa")


def wire_span(**overrides) -> dict:
    span = {
        "trace_id": TRACE_1,
        "span_id": ROOT,
        "parent_span_id": None,
        "name": "rag.run",
        "operation_type": "run",
        "start_time": T0,
        "end_time": T0 + 1_000,
        "status": {"code": "OK"},
    }
    span.update(overrides)
    return span


def batch(*spans) -> dict:
    return {"protocol_version": "1", "spans": list(spans) or [wire_span()]}


class DurableIngestTests(unittest.TestCase):
    def setUp(self):
        self.publisher = InMemorySpanPublisher()
        app.dependency_overrides[get_span_publisher] = lambda: self.publisher
        # The key's owner; the real ingest_user is tested in tests/auth/test_authorization.py.
        self.user = make_user(project_id=USER_PROJECT)
        app.dependency_overrides[ingest_user] = lambda: self.user
        self.addCleanup(app.dependency_overrides.clear)
        # A non-loopback client: the local-1 gating must not apply here.
        self.client = TestClient(app, client=("203.0.113.7", 50000))

    def post(self, body, **kwargs):
        return self.client.post("/api/v1/traces", json=body, **kwargs)

    def published(self):
        return [record for _, record in self.publisher.acked]

    # 202
    def test_valid_batch_is_published_one_message_per_span_keyed_by_trace(self):
        before = time.time_ns()
        response = self.post(batch(
            wire_span(),
            wire_span(span_id=CHILD, parent_span_id=ROOT, name="llm.generate", operation_type="model",
                      start_time=T0 + 100, end_time=T0 + 900),
            wire_span(trace_id=TRACE_2),
        ))
        after = time.time_ns()

        self.assertEqual(response.status_code, 202)
        self.assertEqual(response.json(), {"status": "accepted", "protocol_version": "1", "spans": 3})
        self.assertEqual([key for key, _ in self.publisher.acked],
                         [TRACE_1.encode(), TRACE_1.encode(), TRACE_2.encode()])
        records = self.published()
        self.assertEqual([r.span_name for r in records], ["rag.run", "llm.generate", "rag.run"])
        self.assertEqual({r.protocol_version for r in records}, {"1"})
        # received_at: one value for the whole envelope, taken during the request.
        self.assertEqual(len({r.received_at for r in records}), 1)
        self.assertTrue(before <= records[0].received_at <= after)

    def test_wire_fields_map_to_span_record(self):
        self.post(batch(wire_span(
            status={"code": "ERROR", "description": "timeout"},
            error_type="TimeoutError",
            service_name="rag_agent",
            model="gpt-4o-mini", input_tokens=12, output_tokens=3, total_tokens=15, cost="0.00125",
            input_state="captured", input_payload='{"q": "hi"}',
            links=[{"trace_id": TRACE_2, "span_id": CHILD, "relation": "retry_of"}],
        )))
        [record] = self.published()
        self.assertEqual((record.started_at, record.ended_at), (T0, T0 + 1_000))
        self.assertEqual((record.status_code.value, record.status_description, record.error_type),
                         ("ERROR", "timeout", "TimeoutError"))
        self.assertEqual((record.model, record.total_tokens, record.cost), ("gpt-4o-mini", 15, "0.00125"))
        # Payloads are accepted on the durable path (local-1 rejects them).
        self.assertEqual((record.input_state.value, record.input_payload), ("captured", '{"q": "hi"}'))
        # Payload states the client did not send are "unavailable", never guessed.
        self.assertEqual((record.output_state.value, record.error_state.value), ("unavailable", "unavailable"))
        self.assertEqual(record.links[0].relation, "retry_of")

    def test_attribute_values_are_stringified(self):
        attributes = {"s": "text", "i": 3, "f": 0.2, "b": True, "l": ["a", 1, False]}
        self.post(batch(wire_span(
            attributes=attributes,
            events=[{"name": "retry", "time": T0 + 1, "attributes": {"attempt": 2, "final": False}}],
        )))
        [record] = self.published()
        self.assertEqual(record.attributes, {"s": "text", "i": "3", "f": "0.2", "b": "true", "l": '["a",1,false]'})
        self.assertEqual(record.events[0].attributes, {"attempt": "2", "final": "false"})

    # project_id
    def test_project_id_is_the_authenticated_users(self):
        self.post(batch(wire_span(), wire_span(trace_id=TRACE_2)))
        self.assertEqual({record.project_id for record in self.published()}, {USER_PROJECT})

    # authentication
    def test_authentication_runs_before_the_body_is_read(self):
        def reject():
            raise HTTPException(401, "Invalid API key")

        app.dependency_overrides[ingest_user] = reject
        cases = {
            "valid batch": dict(json=batch()),
            "over 4 MiB": dict(json=batch(wire_span(input_state="captured", input_payload="x" * (4 * 1024 * 1024)))),
            "not JSON": dict(content=b"<xml/>", headers={"content-type": "application/xml"}),
            "malformed JSON": dict(content=b"{", headers={"content-type": "application/json"}),
        }
        for label, kwargs in cases.items():
            response = self.client.post("/api/v1/traces", **kwargs)
            self.assertEqual((response.status_code, response.json()), (401, {"detail": "Invalid API key"}), label)
        self.assertEqual(self.published(), [])

    def test_client_project_id_is_rejected_in_span_and_envelope(self):
        in_span = self.post(batch(wire_span(project_id=CLIENT_PROJECT)))
        in_envelope = self.post({**batch(), "project_id": CLIENT_PROJECT})
        self.assertEqual((in_span.status_code, in_envelope.status_code), (422, 422))
        self.assertEqual(self.published(), [])

    def test_default_project_id_is_the_documented_value(self):
        self.assertEqual(str(DEFAULT_PROJECT_ID), "00000000-0000-4000-8000-000000000001")

    # 503
    def test_publish_failure_is_503_never_202(self):
        self.publisher.fail_after = 1
        response = self.post(batch(wire_span(), wire_span(span_id=CHILD, parent_span_id=ROOT)))
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.headers["retry-after"], "1")
        # The first span was acked before the failure and stays (§8.3); the client retries the batch.
        self.assertEqual(len(self.published()), 1)

    def test_publish_failure_before_any_ack_is_503(self):
        self.publisher.fail_after = 0
        self.assertEqual(self.post(batch()).status_code, 503)
        self.assertEqual(self.published(), [])

    # 422 and other rejections: nothing is published
    def test_invalid_batches_are_422_and_publish_nothing(self):
        cases = {
            "local-1 protocol": {"protocol_version": "local-1", "spans": [wire_span()]},
            "missing protocol": {"spans": [wire_span()]},
            "no spans": {"protocol_version": "1", "spans": []},
            "too many spans": {"protocol_version": "1", "spans": [wire_span(span_id=f"{i:016x}") for i in range(257)]},
            "missing name": batch({k: v for k, v in wire_span().items() if k != "name"}),
            "uppercase trace_id": batch(wire_span(trace_id="A" * 32)),
            "unknown operation": batch(wire_span(operation_type="planner")),
            "time as string": batch(wire_span(start_time=str(T0))),
            "end before start": batch(wire_span(end_time=T0 - 1)),
            "received_at from client": batch(wire_span(received_at=T0)),
            "unknown field": batch(wire_span(colour="blue")),
            "object attribute": batch(wire_span(attributes={"nested": {"a": 1}})),
            "null attribute": batch(wire_span(attributes={"x": None})),
            "payload with disabled state": batch(wire_span(input_state="disabled", input_payload="x")),
            "cost as number": batch(wire_span(cost=0.001)),
        }
        for label, body in cases.items():
            with self.subTest(label):
                self.assertEqual(self.post(body).status_code, 422)
        self.assertEqual(self.published(), [])

    def test_422_does_not_echo_submitted_values(self):
        response = self.post(batch(wire_span(input_state="disabled", input_payload="sk-live-SECRET")))
        self.assertEqual(response.status_code, 422)
        self.assertNotIn("SECRET", response.text)
        self.assertTrue(all(set(e) == {"loc", "msg", "type"} for e in response.json()["detail"]))

    # Payload cap (clickhouse-span-record.md §9 P9)
    def test_payload_at_the_cap_is_accepted_for_each_kind(self):
        at_cap = "x" * MAX_PAYLOAD_BYTES
        for kind in ("input", "output", "error"):
            with self.subTest(kind):
                response = self.post(batch(wire_span(**{f"{kind}_state": "captured", f"{kind}_payload": at_cap})))
                self.assertEqual(response.status_code, 202)
        self.assertEqual([len(r.input_payload) for r in self.published()], [MAX_PAYLOAD_BYTES, 0, 0])

    def test_payload_over_the_cap_is_422_names_the_field_and_publishes_nothing(self):
        over = "sk-live-SECRET" + "x" * MAX_PAYLOAD_BYTES
        for kind in ("input", "output", "error"):
            with self.subTest(kind):
                response = self.post(batch(
                    wire_span(),
                    wire_span(span_id=CHILD, parent_span_id=ROOT,
                              **{f"{kind}_state": "truncated", f"{kind}_payload": over}),
                ))
                self.assertEqual(response.status_code, 422)
                [error] = response.json()["detail"]
                self.assertEqual(error["loc"], ["spans", 1, f"{kind}_payload"])
                self.assertEqual(error["type"], "payload_too_large")
                self.assertIn("131072 bytes", error["msg"])
                self.assertNotIn("SECRET", response.text)
                self.assertLess(len(response.content), 1024)
        # The valid span in the same batch is not published either.
        self.assertEqual(self.published(), [])

    def test_payload_cap_counts_utf8_bytes_not_characters(self):
        # 65,536 two-byte characters are exactly the cap; one more is 2 bytes over.
        fits, over = "é" * (MAX_PAYLOAD_BYTES // 2), "é" * (MAX_PAYLOAD_BYTES // 2 + 1)
        self.assertLess(len(over), MAX_PAYLOAD_BYTES)
        self.assertEqual(self.post(batch(wire_span(output_state="captured", output_payload=fits))).status_code, 202)
        self.assertEqual(self.post(batch(wire_span(output_state="captured", output_payload=over))).status_code, 422)
        self.assertEqual(len(self.published()), 1)

    def test_payload_cap_is_the_decided_value(self):
        self.assertEqual(MAX_PAYLOAD_BYTES, 131_072)

    def test_malformed_json_is_422(self):
        response = self.client.post("/api/v1/traces", content=b"{not json",
                                    headers={"content-type": "application/json"})
        self.assertEqual(response.status_code, 422)

    def test_non_json_content_type_is_415(self):
        response = self.client.post("/api/v1/traces", content=json.dumps(batch()),
                                    headers={"content-type": "text/plain"})
        self.assertEqual(response.status_code, 415)
        self.assertEqual(self.published(), [])

    def test_content_type_is_case_insensitive(self):
        for content_type in ("Application/JSON", "APPLICATION/JSON; charset=UTF-8"):
            with self.subTest(content_type):
                response = self.client.post("/api/v1/traces", content=json.dumps(batch()),
                                            headers={"content-type": content_type})
                self.assertEqual(response.status_code, 202)
        self.assertEqual(len(self.published()), 2)

    def test_span_too_large_for_kafka_is_413_and_publishes_nothing(self):
        # The real publisher's size check runs before it creates a producer, so
        # no broker is needed; a created producer would mean something was sent.
        created = []
        kafka = KafkaSpanPublisher("unused:9092", "agentdbg.traces.v1", max_request_size=2048,
                                   producer_factory=lambda: created.append(1))
        app.dependency_overrides[get_span_publisher] = lambda: kafka
        small = wire_span()
        big = wire_span(span_id=CHILD, parent_span_id=ROOT, input_state="captured", input_payload="x" * 4096)

        response = self.post(batch(small, big))

        self.assertEqual(response.status_code, 413)
        self.assertNotIn("retry-after", response.headers)
        self.assertTrue(response.json()["detail"].startswith("Span 1 is "))
        self.assertIn("limit is 2048 bytes", response.json()["detail"])
        self.assertEqual(created, [])

    def test_body_over_4_mib_is_413(self):
        big = wire_span(input_state="captured", input_payload="x" * (4 * 1024 * 1024))
        self.assertEqual(self.post(batch(big)).status_code, 413)
        self.assertEqual(self.published(), [])

    # Not the local profile
    def test_no_local_gating_mode_header_or_origin_needed(self):
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("AGENT_DEBUGGER_LOCAL_MODE", None)
            response = self.post(batch(), headers={"origin": "https://example.com"})
        self.assertEqual(response.status_code, 202)

    def test_local_endpoint_is_unchanged(self):
        # Still gated: LOCAL_MODE unset -> 503, and it never reaches the durable publisher.
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("AGENT_DEBUGGER_LOCAL_MODE", None)
            response = self.client.post("/api/v1/local/traces", json=batch())
        self.assertEqual(response.status_code, 503)
        self.assertEqual(self.published(), [])


if __name__ == "__main__":
    unittest.main()
