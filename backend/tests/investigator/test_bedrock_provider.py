"""Bedrock provider with a fake boto3 client: request shape, schema, error kinds, secrets. No network."""

import json
import os
import unittest
from unittest import mock

from agent_debugger_api.contracts.fakes import InMemoryTraceStore
from agent_debugger_api.investigator.attempts import InMemoryAttemptStore
from agent_debugger_api.investigator.bedrock_provider import (
    UNSUPPORTED_KEYWORDS,
    BedrockProvider,
    bedrock_output_schema,
)
from agent_debugger_api.investigator.engine import (
    INSTRUCTIONS,
    MAX_OUTPUT_TOKENS,
    PROMPT_VERSION,
    Investigator,
)
from agent_debugger_api.investigator.factory import provider_from_env
from agent_debugger_api.investigator.provider import (
    InvestigationRequest,
    InvestigatorProvider,
    ProviderError,
    ScriptedProvider,
)
from agent_debugger_api.investigator.schema import output_json_schema, parse_output
from agent_debugger_api.investigator.snapshot import SnapshotLimits
from agent_debugger_api.trace_writer.content_hash import content_hash
from botocore.exceptions import (
    ClientError,
    ConnectTimeoutError,
    EndpointConnectionError,
    NoCredentialsError,
    ReadTimeoutError,
)

from tests.contracts.factories import PROJECT_A, TRACE_1
from tests.investigator.factories import failed_tool_trace, finding, output_dict

SECRET = "ABSKsynthetic-bedrock-key-0123456789"
MODEL = "us.example.model-v1:0"


def converse_response(text, stop_reason="end_turn"):
    return {
        "output": {"message": {"role": "assistant", "content": [{"text": text}]}},
        "stopReason": stop_reason,
        "usage": {"inputTokens": 1200, "outputTokens": 340, "totalTokens": 1540},
        "metrics": {"latencyMs": 812},
    }


def client_error(code):
    # The message carries the key, as a worst case: it must never reach a stored field.
    return ClientError({"Error": {"Code": code, "Message": f"denied for token {SECRET}"}}, "Converse")


class FakeClient:
    def __init__(self, *answers):
        self.answers = list(answers)
        self.calls = []

    def converse(self, **kwargs):
        self.calls.append(kwargs)
        answer = self.answers.pop(0)
        if isinstance(answer, BaseException):
            raise answer
        return answer


def request(**changes):
    values = {
        "instructions": INSTRUCTIONS,
        "snapshot_json": '{"spans": []}',
        "output_schema": output_json_schema(),
        "max_output_tokens": MAX_OUTPUT_TOKENS,
        "timeout_s": 60.0,
    }
    values.update(changes)
    return InvestigationRequest(**values)


def walk(node):
    if isinstance(node, dict):
        yield node
        for value in node.values():
            yield from walk(value)
    elif isinstance(node, list):
        for item in node:
            yield from walk(item)


class SchemaTests(unittest.TestCase):
    def setUp(self):
        self.schema = bedrock_output_schema(output_json_schema())

    def test_no_keyword_bedrock_rejects_is_left(self):
        for node in walk(self.schema):
            self.assertFalse(UNSUPPORTED_KEYWORDS & node.keys(), node)
            if "minItems" in node:
                self.assertIn(node["minItems"], (0, 1))

    def test_every_object_is_closed_and_has_no_optional_property(self):
        objects = [node for node in walk(self.schema) if "properties" in node]
        self.assertGreaterEqual(len(objects), 4)  # output, finding, evidence, relation
        for node in objects:
            self.assertIs(node["additionalProperties"], False)
            self.assertEqual(sorted(node["required"]), sorted(node["properties"]))

    def test_union_typed_properties_stay_under_the_limit(self):
        unions = [
            prop
            for node in walk(self.schema)
            if "properties" in node
            for prop in node["properties"].values()
            if "anyOf" in prop or isinstance(prop.get("type"), list)
        ]
        self.assertLessEqual(len(unions), 16)

    def test_the_pydantic_schema_is_not_changed(self):
        original = output_json_schema()
        bedrock_output_schema(original)
        self.assertEqual(original, output_json_schema())

    def test_output_with_explicit_nulls_and_empty_lists_still_parses(self):
        # What a model under the all-required schema sends for an omitted field.
        raw = output_dict(finding())
        for candidate in raw["findings"]:
            candidate.setdefault("suspicious_span_id", None)
            candidate.setdefault("relations", [])
            candidate.setdefault("limitations", [])
            for ref in candidate["evidence"]:
                for key in ("content_hash", "key", "event_index", "quote"):
                    ref.setdefault(key, None)
        self.assertEqual(parse_output(json.dumps(raw)).verdict, "findings")


class RequestTests(unittest.TestCase):
    def test_converse_request_shape(self):
        client = FakeClient(converse_response(json.dumps(output_dict())))
        provider = BedrockProvider(MODEL, "us-east-1", client=client)
        self.assertIsInstance(provider, InvestigatorProvider)
        provider.investigate(request())
        (call,) = client.calls
        self.assertEqual(call["modelId"], MODEL)
        self.assertEqual(call["system"], [{"text": INSTRUCTIONS}])
        self.assertEqual(call["inferenceConfig"], {"maxTokens": MAX_OUTPUT_TOKENS, "temperature": 0})
        (message,) = call["messages"]
        self.assertEqual(message["content"][-1], {"text": '{"spans": []}'})  # snapshot only in the user turn
        text_format = call["outputConfig"]["textFormat"]
        self.assertEqual(text_format["type"], "json_schema")
        schema = json.loads(text_format["structure"]["jsonSchema"]["schema"])
        self.assertEqual(schema, bedrock_output_schema(output_json_schema()))

    def test_a_valid_response_returns_text_and_usage(self):
        text = json.dumps(output_dict())
        provider = BedrockProvider(MODEL, "us-east-1", client=FakeClient(converse_response(text)))
        response = provider.investigate(request())
        self.assertEqual((response.output, response.input_tokens, response.output_tokens, response.latency_ms), (text, 1200, 340, 812))

    def test_a_response_without_text_is_bad_response(self):
        empty = {"output": {"message": {"role": "assistant", "content": []}}, "stopReason": "end_turn"}
        for answer in (empty, {"stopReason": "end_turn"}):
            with self.subTest(answer=answer), self.assertRaises(ProviderError) as raised:
                BedrockProvider(MODEL, "us-east-1", client=FakeClient(answer)).investigate(request())
            self.assertEqual(raised.exception.kind, "bad_response")

    def test_missing_config_is_refused(self):
        with self.assertRaises(ValueError):
            BedrockProvider.from_env({"AWS_REGION": "us-east-1"}, client=FakeClient())
        with self.assertRaises(ValueError):
            BedrockProvider.from_env({"BEDROCK_MODEL_ID": MODEL}, client=FakeClient())


class ErrorKindTests(unittest.TestCase):
    CASES = (
        (client_error("ThrottlingException"), "rate_limited"),
        (client_error("ModelTimeoutException"), "timeout"),
        (ReadTimeoutError(endpoint_url="https://bedrock-runtime.example"), "timeout"),
        (ConnectTimeoutError(endpoint_url="https://bedrock-runtime.example"), "timeout"),
        (client_error("ServiceUnavailableException"), "unavailable"),
        (client_error("InternalServerException"), "unavailable"),
        (client_error("ModelNotReadyException"), "unavailable"),
        (EndpointConnectionError(endpoint_url="https://bedrock-runtime.example"), "unavailable"),
        (client_error("AccessDeniedException"), "auth"),
        (client_error("UnrecognizedClientException"), "auth"),
        (NoCredentialsError(), "auth"),
        (client_error("ValidationException"), "bad_response"),
        (client_error("ModelErrorException"), "bad_response"),
        (RuntimeError(f"unexpected {SECRET}"), "bad_response"),
    )

    def test_each_failure_maps_to_its_kind_without_provider_text(self):
        for error, kind in self.CASES:
            with self.subTest(error=type(error).__name__, kind=kind):
                provider = BedrockProvider(MODEL, "us-east-1", client=FakeClient(error))
                with self.assertRaises(ProviderError) as raised:
                    provider.investigate(request())
                self.assertEqual(raised.exception.kind, kind)
                self.assertNotIn(SECRET, str(raised.exception))
                self.assertIsNone(raised.exception.__cause__)
                self.assertTrue(raised.exception.__suppress_context__)


class EngineWithBedrockTests(unittest.TestCase):
    """The provider behind the real engine: what a stored attempt holds."""

    def investigate(self, *answers, limits=None):
        traces = InMemoryTraceStore(content_hash)
        traces.insert_spans(failed_tool_trace())
        attempts = InMemoryAttemptStore()
        self.client = FakeClient(*answers)
        with mock.patch.dict(os.environ, {"AWS_BEARER_TOKEN_BEDROCK": SECRET}):
            provider = BedrockProvider(MODEL, "us-east-1", client=self.client)
            engine = Investigator(traces, provider, attempts, **({"limits": limits} if limits else {}))
            attempt = engine.investigate(PROJECT_A, TRACE_1)
        self.assertEqual(attempts.get(attempt.attempt_id), attempt)
        self.assertNotIn(SECRET, attempt.model_dump_json())
        self.assertNotIn(SECRET, repr(vars(provider)))
        return attempt

    def test_a_valid_response_completes_the_attempt(self):
        attempt = self.investigate(converse_response(json.dumps(output_dict())))
        self.assertEqual((attempt.status, attempt.provider_name, attempt.model_id), ("completed", "bedrock", MODEL))
        self.assertEqual((attempt.input_tokens, attempt.output_tokens, attempt.latency_ms), (1200, 340, 812))

    def test_the_attempt_records_prompt_version_model_and_region(self):
        attempt = self.investigate(converse_response(json.dumps(output_dict())))
        self.assertEqual(
            (attempt.prompt_version, attempt.model_id, attempt.provider_region), (PROMPT_VERSION, MODEL, "us-east-1")
        )

    def test_a_snapshot_over_the_limit_fails_before_any_provider_call(self):
        attempt = self.investigate(limits=SnapshotLimits(max_bytes=200))
        self.assertEqual((attempt.status, attempt.failure_code), ("failed", "input_too_large"))
        self.assertEqual(self.client.calls, [])
        self.assertIsNone(attempt.input_tokens)

    def test_a_response_cut_at_max_tokens_fails_as_invalid_output(self):
        text = json.dumps(output_dict(finding()))
        attempt = self.investigate(converse_response(text[: len(text) // 2], stop_reason="max_tokens"))
        self.assertEqual((attempt.status, attempt.failure_code, attempt.failure_detail), ("failed", "invalid_output", "not_json"))
        self.assertEqual((attempt.input_tokens, attempt.output_tokens), (1200, 340))  # tokens are kept on a failed attempt

    def test_a_throttled_call_is_retried_once(self):
        attempt = self.investigate(client_error("ThrottlingException"), converse_response(json.dumps(output_dict())))
        self.assertEqual((attempt.status, attempt.provider_calls), ("completed", 2))

    def test_provider_errors_store_only_the_kind(self):
        for code, kind in (("AccessDeniedException", "auth"), ("ValidationException", "bad_response")):
            with self.subTest(kind=kind):
                attempt = self.investigate(client_error(code))
                self.assertEqual((attempt.failure_code, attempt.failure_detail), ("provider_error", kind))
                self.assertNotIn(code, attempt.model_dump_json())


class FactoryTests(unittest.TestCase):
    def test_a_scripted_attempt_has_no_region(self):
        traces = InMemoryTraceStore(content_hash)
        traces.insert_spans(failed_tool_trace())
        attempt = Investigator(traces, provider_from_env({}), InMemoryAttemptStore()).investigate(PROJECT_A, TRACE_1)
        self.assertEqual((attempt.provider_name, attempt.provider_region), ("stub-scripted", None))

    def test_default_is_scripted_and_abstains_on_every_call(self):
        provider = provider_from_env({})
        self.assertIsInstance(provider, ScriptedProvider)
        for _ in range(3):
            self.assertEqual(parse_output(provider.investigate(request()).output).verdict, "insufficient_evidence")

    def test_bedrock_is_chosen_by_name(self):
        provider = provider_from_env({"INVESTIGATOR_PROVIDER": "Bedrock", "BEDROCK_MODEL_ID": MODEL, "AWS_REGION": "us-east-1"})
        self.assertIsInstance(provider, BedrockProvider)
        self.assertEqual(provider.model_id, MODEL)

    def test_an_unknown_name_is_refused(self):
        with self.assertRaises(ValueError):
            provider_from_env({"INVESTIGATOR_PROVIDER": "openai"})


if __name__ == "__main__":
    unittest.main()
