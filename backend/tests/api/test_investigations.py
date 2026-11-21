"""POST/GET /api/v1/projects/local/runs/{trace_id}/investigations: route over the real engine and grounding.

The trace store is an InMemoryTraceStore, the provider a ScriptedProvider (or the
Bedrock provider over a fake client), the attempt store the in-memory one. No ClickHouse.
"""

import os
import unittest
from unittest import mock

from agent_debugger_api.api.routes.durable_runs import get_trace_store
from agent_debugger_api.api.routes.investigations import (
    get_attempt_store,
    get_investigator_provider,
)
from agent_debugger_api.contracts.fakes import InMemoryTraceStore
from agent_debugger_api.ingest.settings import DEFAULT_PROJECT_ID
from agent_debugger_api.investigator.attempts import InMemoryAttemptStore
from agent_debugger_api.investigator.bedrock_provider import BedrockProvider
from agent_debugger_api.investigator.provider import ProviderError, ScriptedProvider
from agent_debugger_api.main import app
from agent_debugger_api.trace_writer.content_hash import content_hash
from agent_debugger_api.traces.read_store import TraceStoreUnavailable
from botocore.exceptions import ClientError
from fastapi.testclient import TestClient

from tests.contracts.factories import TRACE_1
from tests.investigator.factories import (
    RESERVE,
    evidence,
    failed_tool_trace,
    finding,
    output_dict,
    sid,
)

BASE = f"/api/v1/projects/local/runs/{TRACE_1}/investigations"
QUOTE = '"quantity":0'
SECRET = "provider said sk-synthetic-secret"


def stored_trace():
    return [record.model_copy(update={"project_id": DEFAULT_PROJECT_ID}) for record in failed_tool_trace()]


def grounded():
    return finding(evidence=[evidence(RESERVE), evidence(RESERVE, "input_payload", quote=QUOTE)])


class UnavailableStore:
    def get_trace(self, project_id, trace_id):
        raise TraceStoreUnavailable("down")


class InvestigationRouteCase(unittest.TestCase):
    def setUp(self):
        self.store = InMemoryTraceStore(content_hash)
        self.store.insert_spans(stored_trace())
        self.attempts = InMemoryAttemptStore()
        self.provider = ScriptedProvider([output_dict(grounded())], repeat_last=True)
        app.dependency_overrides[get_trace_store] = lambda: self.store
        app.dependency_overrides[get_attempt_store] = lambda: self.attempts
        app.dependency_overrides[get_investigator_provider] = lambda: self.provider
        self.addCleanup(app.dependency_overrides.clear)
        self.client = TestClient(app)

    def post(self, path=BASE):
        return self.client.post(path)


class PostTests(InvestigationRouteCase):
    def test_a_grounded_finding_is_returned_with_its_cited_spans_and_quotes(self):
        response = self.post()
        self.assertEqual(response.status_code, 201)
        body = response.json()
        self.assertEqual((body["status"], body["outcome"], body["has_failure_findings"]), ("completed", "findings", True))
        self.assertEqual(body["provider"], {"kind": "scripted", "name": "stub-scripted", "model_id": "scripted-1", "region": None})
        (kept,) = body["findings"]
        self.assertEqual((kept["suspicious_span_id"], kept["claim_type"], kept["priority"]), (sid(RESERVE), "observed_failure", "HIGH"))
        status_ref, payload_ref = kept["evidence"]
        self.assertEqual((status_ref["span_id"], status_ref["field"], status_ref["cited_value"]), (sid(RESERVE), "status_code", "ERROR"))
        self.assertEqual((payload_ref["field"], payload_ref["quote"]), ("input_payload", QUOTE))
        self.assertIn(QUOTE, payload_ref["cited_value"])  # the analyzed value, as grounding checked it
        self.assertEqual(body["rejected"], [])
        self.assertNotIn("snapshot_json", body)
        self.assertEqual(len(body["snapshot_hash"]), 64)

    def test_a_fabricated_span_is_reported_as_a_rejection_code_not_a_finding(self):
        self.provider = ScriptedProvider([output_dict(finding(suspicious_span_id=sid(99), evidence=[evidence(99)]))])
        body = self.post().json()
        self.assertEqual((body["status"], body["outcome"], body["findings"]), ("completed", "insufficient_evidence", []))
        self.assertEqual(body["rejected"], [{"candidate_index": 0, "code": "unknown_span"}])
        self.assertEqual(body["candidate_count"], 1)

    def test_a_provider_error_is_a_failed_attempt_with_only_the_kind(self):
        self.provider = ScriptedProvider([ProviderError("auth", SECRET)])
        response = self.post()
        self.assertEqual(response.status_code, 201)
        body = response.json()
        self.assertEqual((body["status"], body["failure_code"], body["failure_detail"], body["findings"]), ("failed", "provider_error", "auth", []))
        self.assertNotIn("sk-synthetic", response.text)

    def test_an_unknown_trace_is_404_and_the_provider_is_not_called(self):
        response = self.post(f"/api/v1/projects/local/runs/{'2' * 32}/investigations")
        self.assertEqual(response.status_code, 404)
        self.assertEqual(self.provider.requests, [])

    def test_an_unknown_project_is_404(self):
        self.assertEqual(self.post(f"/api/v1/projects/other/runs/{TRACE_1}/investigations").status_code, 404)

    def test_a_malformed_trace_id_is_422(self):
        self.assertEqual(self.post("/api/v1/projects/local/runs/not-a-trace/investigations").status_code, 422)

    def test_store_unavailable_is_503_and_no_attempt_is_left_behind(self):
        self.store = UnavailableStore()
        response = self.post()
        self.assertEqual((response.status_code, response.headers.get("Retry-After")), (503, "1"))
        self.assertEqual(self.attempts.list_for_trace(DEFAULT_PROJECT_ID, TRACE_1), [])

    def test_bedrock_attempts_name_the_provider_model_and_region(self):
        client = mock.Mock()
        client.converse.side_effect = ClientError({"Error": {"Code": "ThrottlingException", "Message": SECRET}}, "Converse")
        self.provider = BedrockProvider("us.example.model-v1:0", "us-east-1", client=client)
        body = self.post().json()
        self.assertEqual(body["provider"], {"kind": "bedrock", "name": "bedrock", "model_id": "us.example.model-v1:0", "region": "us-east-1"})
        self.assertEqual((body["status"], body["failure_detail"], body["provider_calls"]), ("failed", "rate_limited", 2))


class CrashingProvider:
    name = "stub-scripted"
    model_id = "scripted-1"

    def investigate(self, request):
        raise RuntimeError(f"boom {SECRET}")


class RobustnessTests(InvestigationRouteCase):
    def test_a_provider_that_crashes_is_a_failed_attempt_without_its_text(self):
        self.provider = CrashingProvider()
        response = self.post()
        self.assertEqual(response.status_code, 201)
        body = response.json()
        self.assertEqual((body["status"], body["failure_code"], body["failure_detail"]), ("failed", "internal_error", "provider_crashed"))
        self.assertEqual(body["provider_calls"], 1)
        self.assertNotIn("boom", response.text)

    def test_a_running_investigation_makes_a_second_one_429_and_creates_no_attempt(self):
        from agent_debugger_api.api.routes import investigations

        self.assertTrue(investigations.RUNNING.acquire(blocking=False))
        try:
            response = self.post()
        finally:
            investigations.RUNNING.release()
        self.assertEqual(response.status_code, 429)
        self.assertEqual(response.json()["detail"], "An investigation is already running; retry shortly.")
        self.assertEqual(self.attempts.list_for_trace(DEFAULT_PROJECT_ID, TRACE_1), [])
        self.assertEqual(self.provider.requests, [])
        self.assertEqual(self.post().status_code, 201)  # released afterwards

    def test_the_slot_is_released_when_the_engine_raises(self):
        from agent_debugger_api.api.routes import investigations

        with mock.patch.object(investigations.Investigator, "investigate", side_effect=RuntimeError("engine bug")):
            with self.assertRaises(RuntimeError):
                self.post()
        self.assertEqual(self.post().status_code, 201)


class LatestTests(InvestigationRouteCase):
    def test_latest_is_404_before_any_attempt(self):
        response = self.client.get(BASE + "/latest")
        self.assertEqual(response.status_code, 404)

    def test_latest_returns_the_newest_attempt(self):
        first = self.post().json()["attempt_id"]
        second = self.post().json()["attempt_id"]
        self.assertNotEqual(first, second)
        body = self.client.get(BASE + "/latest").json()
        self.assertEqual((body["attempt_id"], body["status"]), (second, "completed"))
        self.assertEqual(body["findings"][0]["evidence"][1]["quote"], QUOTE)


class SameTickTests(unittest.TestCase):
    def test_attempts_created_in_the_same_clock_tick_list_in_creation_order(self):
        from uuid import UUID

        from agent_debugger_api.investigator.attempts import AnalysisAttempt

        store = InMemoryAttemptStore()
        # IDs chosen so that sorting by ID would put the second attempt first.
        ids = [UUID("ffffffff-ffff-4fff-8fff-ffffffffffff"), UUID("00000000-0000-4000-8000-000000000000")]
        for attempt_id in ids:
            store.create(AnalysisAttempt(attempt_id=attempt_id, project_id=DEFAULT_PROJECT_ID, trace_id=TRACE_1,
                                         provider_name="stub-scripted", model_id="scripted-1", prompt_version="v", created_at=5))
        self.assertEqual([a.attempt_id for a in store.list_for_trace(DEFAULT_PROJECT_ID, TRACE_1)], ids)


class ProviderConfigTests(unittest.TestCase):
    """The real dependency: INVESTIGATOR_PROVIDER read on first use."""

    def setUp(self):
        self.store = InMemoryTraceStore(content_hash)
        self.store.insert_spans(stored_trace())
        app.dependency_overrides[get_trace_store] = lambda: self.store
        app.dependency_overrides[get_attempt_store] = InMemoryAttemptStore
        self.addCleanup(app.dependency_overrides.clear)
        self.addCleanup(lambda: app.state._state.pop("investigator_provider", None))
        app.state._state.pop("investigator_provider", None)

    def test_default_is_the_scripted_stub_and_it_abstains(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            body = TestClient(app).post(BASE).json()
        self.assertEqual((body["provider"]["kind"], body["outcome"]), ("scripted", "insufficient_evidence"))

    def test_the_configured_provider_is_named_before_any_attempt(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            response = TestClient(app).get("/api/v1/projects/local/investigator")
        self.assertEqual(response.json(), {"kind": "scripted", "name": "stub-scripted", "model_id": "scripted-1", "region": None})
        with mock.patch.dict(os.environ, {"INVESTIGATOR_PROVIDER": "bedrock", "BEDROCK_MODEL_ID": "m", "AWS_REGION": "eu-west-1"}, clear=True):
            app.state._state.pop("investigator_provider", None)
            body = TestClient(app).get("/api/v1/projects/local/investigator").json()
        self.assertEqual(body, {"kind": "bedrock", "name": "bedrock", "model_id": "m", "region": "eu-west-1"})

    def test_a_bad_setting_is_503_without_echoing_it(self):
        with mock.patch.dict(os.environ, {"INVESTIGATOR_PROVIDER": "secret-provider-name"}, clear=True):
            response = TestClient(app).post(BASE)
        self.assertEqual(response.status_code, 503)
        self.assertNotIn("secret-provider-name", response.text)


if __name__ == "__main__":
    unittest.main()
