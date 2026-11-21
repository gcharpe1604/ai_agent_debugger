"""scripts/bedrock_smoke.py with a fake client: one line per failure, exit codes, no secret or provider text."""

import contextlib
import io
import os
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

import bedrock_smoke
from botocore.exceptions import ClientError, EndpointConnectionError, NoCredentialsError, ReadTimeoutError

from agent_debugger_api.investigator.engine import INSTRUCTIONS

SECRET = "ABSKsynthetic-bedrock-key-0123456789"
ENV = {"BEDROCK_MODEL_ID": "us.example.model-v1:0", "AWS_REGION": "us-east-1", "AWS_BEARER_TOKEN_BEDROCK": SECRET}


def client_error(code):
    return ClientError({"Error": {"Code": code, "Message": f"provider text with {SECRET}"}}, "Converse")


class FakeClient:
    def __init__(self, answer):
        self.answer = answer

    def converse(self, **kwargs):
        if isinstance(self.answer, BaseException):
            raise self.answer
        return self.answer


def run(argv=(), env=ENV, answer=None):
    out = io.StringIO()
    with mock.patch.dict(os.environ, env, clear=True), mock.patch.object(
        bedrock_smoke, "make_client", return_value=FakeClient(answer)
    ), contextlib.redirect_stdout(out):
        code = bedrock_smoke.main(list(argv))
    return code, out.getvalue()


class SmokeTests(unittest.TestCase):
    def test_ok_prints_stop_reason_and_usage_only(self):
        answer = {
            "output": {"message": {"role": "assistant", "content": [{"text": "model text ok"}]}},
            "stopReason": "end_turn",
            "usage": {"inputTokens": 12, "outputTokens": 2, "totalTokens": 14},
        }
        code, out = run(answer=answer)
        self.assertEqual(code, 0)
        self.assertEqual(out.splitlines(), ["ok: stopReason=end_turn", "inputTokens=12 outputTokens=2 totalTokens=14"])

    def test_missing_env_exits_2_and_names_the_variables(self):
        code, out = run(env={})
        self.assertEqual(code, 2)
        self.assertIn("BEDROCK_MODEL_ID, AWS_REGION, AWS_BEARER_TOKEN_BEDROCK", out)

    def test_each_failure_is_one_line_with_its_exit_code_and_no_provider_text(self):
        cases = [
            (client_error("UnrecognizedClientException"), 3, "credentials"),
            (NoCredentialsError(), 3, "credentials"),
            (client_error("AccessDeniedException"), 4, "access denied"),
            (client_error("ResourceNotFoundException"), 5, "model not found"),
            (client_error("ValidationException"), 5, "request rejected"),
            (EndpointConnectionError(endpoint_url="https://bedrock-runtime.nowhere-1.amazonaws.com"), 5, "AWS_REGION"),
            (client_error("ThrottlingException"), 6, "throttled"),
            (ReadTimeoutError(endpoint_url="https://bedrock-runtime.example"), 7, "timed out"),
            (client_error("ServiceUnavailableException"), 7, "unavailable"),
            (RuntimeError(f"unexpected {SECRET}"), 1, "failed"),
        ]
        for error, expected_code, phrase in cases:
            with self.subTest(error=type(error).__name__, expected=expected_code):
                code, out = run(answer=error)
                self.assertEqual(code, expected_code)
                self.assertEqual(len(out.splitlines()), 1)
                self.assertIn(phrase, out)
                self.assertNotIn(SECRET, out)
                self.assertNotIn("provider text", out)

    def test_dry_run_prints_shape_and_sizes_without_prompt_or_key(self):
        code, out = run(["--dry-run"])
        self.assertEqual(code, 0)
        self.assertIn("snapshot 12 bytes", out)
        self.assertIn("'temperature': 0", out)
        self.assertNotIn(SECRET, out)
        self.assertNotIn(INSTRUCTIONS.splitlines()[0], out)

    def test_dry_run_needs_no_env(self):
        code, out = run(["--dry-run"], env={})
        self.assertEqual(code, 0)
        self.assertIn("modelId=<unset> region=<unset>", out)


if __name__ == "__main__":
    unittest.main()
