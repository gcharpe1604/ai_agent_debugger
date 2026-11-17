"""Structured output schema: proposal §9 tests 17 and 18 (O)."""

import json
import unittest

from pydantic import ValidationError

from agent_debugger_api.investigator.schema import (
    InvalidOutput,
    InvestigatorOutput,
    output_json_schema,
    parse_output,
)
from tests.investigator.factories import RESERVE, evidence, finding, output_dict, sid


def invalid(raw):
    try:
        parse_output(raw)
    except InvalidOutput as error:
        return str(error)
    return None


class OutputSchemaTests(unittest.TestCase):
    def test_17_a_valid_output_parses_from_an_object_and_from_text(self):
        full = finding(
            evidence=[
                evidence(RESERVE),
                evidence(RESERVE, "event", event_index=0, quote="ToolError"),
                evidence(RESERVE, "attribute", key="debugger.step"),
                {"span_id": sid(RESERVE), "content_hash": "0123456789ab", "field": "input_payload", "quote": '"quantity":0'},
            ],
            relations=[{"kind": "parent_of", "from_span_id": sid(2), "to_span_id": sid(RESERVE)}],
            limitations=["The tool's own error code is not recorded."],
        )
        raw = output_dict(full, limitations=["Payloads were captured."])
        parsed = parse_output(raw)
        self.assertEqual(parsed, parse_output(json.dumps(raw)))
        self.assertEqual(parsed.findings[0].evidence[1].event_index, 0)
        self.assertEqual(parsed.findings[0].suspicious_span_id, sid(RESERVE))
        with self.assertRaises(ValidationError):  # frozen: grounding cannot change its input
            parsed.findings[0].priority = "LOW"

    def test_17_each_limit_and_unknown_field_is_rejected(self):
        cases = {
            "unknown field on the output": {**output_dict(finding()), "confidence": 0.9},
            "unknown field on a finding": output_dict(finding(root_cause=True)),
            "unknown field on an evidence ref": output_dict(finding(evidence=[evidence(RESERVE, note="x")])),
            "seventh evidence ref": output_dict(finding(evidence=[evidence(RESERVE)] * 7)),
            "no evidence": output_dict(finding(evidence=[])),
            "sixth finding": output_dict(*[finding()] * 6),
            "over-long explanation": output_dict(finding(explanation="x" * 601)),
            "over-long quote": output_dict(finding(evidence=[evidence(RESERVE, "error_payload", quote="q" * 201)])),
            "over-long limitation": output_dict(finding(), limitations=["l" * 301]),
            "fifth relation": output_dict(finding(relations=[{"kind": "parent_of", "from_span_id": sid(2), "to_span_id": sid(5)}] * 5)),
            "span id that is not 16 hex": output_dict(finding(suspicious_span_id="reserve")),
            "unknown category": output_dict(finding(category="root_cause")),
            "unknown claim type": output_dict(finding(claim_type="proven_root_cause")),
            "priority as a number": output_dict(finding(priority=0.9)),
            "unknown evidence field": output_dict(finding(evidence=[evidence(RESERVE, "stack_trace")])),
            "negative event index": output_dict(finding(evidence=[evidence(RESERVE, "event", event_index=-1)])),
            "wrong schema version": {**output_dict(finding()), "schema_version": 2},
            "missing verdict": {"schema_version": 1, "findings": []},
        }
        for name, raw in cases.items():
            with self.subTest(name):
                self.assertEqual(invalid(raw), "schema_mismatch")
        # The boundary values themselves are accepted.
        parse_output(output_dict(*[finding(evidence=[evidence(RESERVE)] * 6, explanation="x" * 600)] * 5))

    def test_18_verdict_and_findings_must_agree(self):
        self.assertEqual(invalid(output_dict(verdict="findings")), "schema_mismatch")
        self.assertEqual(invalid(output_dict(finding(), verdict="no_issue_found")), "schema_mismatch")
        self.assertEqual(invalid(output_dict(finding(), verdict="insufficient_evidence")), "schema_mismatch")
        for verdict in ("no_issue_found", "insufficient_evidence"):
            self.assertEqual(parse_output(output_dict(verdict=verdict)).findings, ())

    def test_text_that_is_not_one_json_object_is_invalid(self):
        self.assertEqual(invalid("I found no issue."), "not_json")
        self.assertEqual(invalid('```json\n{"verdict": "no_issue_found"}\n```'), "not_json")
        self.assertEqual(invalid("[]"), "not_an_object")
        self.assertEqual(invalid('"no_issue_found"'), "not_an_object")

    def test_an_invalid_output_error_never_repeats_the_output(self):
        secret = "sk-synthetic-secret-value"
        self.assertNotIn(secret, invalid(output_dict(finding(explanation=secret, extra=secret))))
        self.assertNotIn(secret, invalid(secret))

    def test_the_json_schema_handed_to_the_provider_describes_the_output(self):
        schema = output_json_schema()
        self.assertEqual(sorted(schema["properties"]), ["findings", "limitations", "schema_version", "verdict"])
        self.assertFalse(schema["additionalProperties"])
        self.assertEqual(schema["properties"]["findings"]["maxItems"], 5)
        self.assertEqual(schema["$defs"]["CandidateFinding"]["properties"]["evidence"]["maxItems"], 6)
        json.dumps(schema)  # plain data
        self.assertEqual(InvestigatorOutput.model_validate(output_dict()).verdict, "no_issue_found")


if __name__ == "__main__":
    unittest.main()
