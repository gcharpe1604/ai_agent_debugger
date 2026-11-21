"""Investigator end to end on real controlled runs (proposal §9, scenario tests 47-56 in part).

Each scenario runs through its agent CLI, the SDK's durable exporter and the real
POST /api/v1/traces route (in-memory publisher, no Kafka). The published SpanRecords go
into an InMemoryTraceStore; the real snapshot builder, a ScriptedProvider and the real
grounding then run through `Investigator`.

Spans are found by name and `debugger.step`, never by a fixed ID, and quotes are
checked against the snapshot's own excerpts before they are used, so a test fails
loudly if the agent's recorded text changes.

Covered here: 53 (TOOL-07 HIGH on pay attempt 1 -> LOW), 55-like (fabricated span ->
rejected), the RAG-04 inconsistency now that payloads exist (§8.2 row 6, "after payload
capture"), TOOL-03 observed failure, and a metadata-only RAG-04 (payloads removed from
the stored records) where the same finding cannot be grounded. Not covered:
FactsEchoProvider (47-52) and the scorer (56), which do not exist yet.
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

from show_payload_states import DurableApp

from agent_debugger_api.contracts import PayloadState
from agent_debugger_api.contracts.fakes import InMemoryTraceStore
from agent_debugger_api.investigator.attempts import InMemoryAttemptStore
from agent_debugger_api.investigator.engine import Investigator
from agent_debugger_api.investigator.grounding import PAYLOAD_LIMITATION, GroundingReportEntry
from agent_debugger_api.investigator.provider import ScriptedProvider
from agent_debugger_api.investigator.snapshot import build_snapshot
from agent_debugger_api.trace_writer.content_hash import content_hash

FABRICATED = "0123456789abcdef"


def setUpModule():
    global durable
    durable = DurableApp().__enter__()


def tearDownModule():
    durable.__exit__(None, None, None)


def metadata_only(record):
    """The same span with no payload recorded, as a metadata-only exporter would send it."""
    update = {}
    for kind in ("input", "output", "error"):
        update[f"{kind}_state"] = PayloadState.UNAVAILABLE
        update[f"{kind}_payload"] = ""
    return record.model_copy(update=update)


class Scenario:
    """One controlled run, stored, plus helpers to cite its spans."""

    def __init__(self, scenario_id, transform=None):
        records = durable.run_scenario(scenario_id)
        if transform is not None:
            records = [transform(record) for record in records]
        self.records = records
        self.project_id = records[0].project_id
        self.trace_id = records[0].trace_id
        self.traces = InMemoryTraceStore(content_hash)
        self.traces.insert_spans(records)
        self.snapshot = build_snapshot(self.traces.get_trace(self.project_id, self.trace_id), self.project_id, self.trace_id)

    def span_id(self, name=None, step=None, attempt=None):
        matches = [
            record
            for record in self.records
            if (name is None or record.span_name == name)
            and (step is None or record.attributes.get("debugger.step") == step)
            and (attempt is None or record.attempt == attempt)
        ]
        if len(matches) != 1:
            raise AssertionError(f"{len(matches)} spans match name={name} step={step} attempt={attempt}")
        return matches[0].span_id

    def excerpt(self, span_id, kind):
        (span,) = self.snapshot.versions(span_id)
        return getattr(span, kind).excerpt

    def investigate(self, *findings, verdict=None, limitations=()):
        output = {
            "schema_version": 1,
            "verdict": verdict or ("findings" if findings else "no_issue_found"),
            "findings": list(findings),
            "limitations": list(limitations),
        }
        attempts = InMemoryAttemptStore()
        attempt = Investigator(self.traces, ScriptedProvider([output]), attempts).investigate(
            self.project_id, self.trace_id
        )
        assert attempts.get(attempt.attempt_id) == attempt
        return attempt


def ref(span_id, field, quote=None):
    out = {"span_id": span_id, "field": field}
    if quote is not None:
        out["quote"] = quote
    return out


class Rag04InconsistencyTests(unittest.TestCase):
    """RAG-04: the retrieved KB-01 says 14 days; the answer cites KB-01 and says 30 days."""

    @classmethod
    def setUpClass(cls):
        cls.scenario = Scenario("RAG-04")
        cls.search = cls.scenario.span_id(name="ScenarioAwareRetriever.search")
        cls.answer = cls.scenario.span_id(name="controlled.generate_answer")

    def finding(self, *, search=None, answer_quote="30 days", retrieved_quote="restored for 14 days"):
        return {
            "category": "output_contradicts_evidence",
            "claim_type": "inconsistency",
            "suspicious_span_id": self.answer,
            "priority": "HIGH",
            "explanation": "The answer says 30 days; the document it cites says 14 days.",
            "evidence": [
                ref(search or self.search, "output_payload", retrieved_quote),
                ref(self.answer, "output_payload", answer_quote),
            ],
        }

    def test_the_quotes_are_in_the_snapshot(self):
        self.assertIn("restored for 14 days", self.scenario.excerpt(self.search, "output"))
        self.assertIn("30 days", self.scenario.excerpt(self.answer, "output"))

    def test_a_correct_inconsistency_is_grounded_and_kept(self):
        attempt = self.scenario.investigate(self.finding())
        self.assertEqual((attempt.status, attempt.outcome, attempt.has_failure_findings), ("completed", "findings", True))
        (kept,) = attempt.findings
        self.assertEqual((kept.suspicious_span_id, kept.claim_type, kept.priority), (self.answer, "inconsistency", "HIGH"))
        self.assertEqual(attempt.grounding_report, ())

    def test_a_fabricated_span_id_is_rejected_as_unknown_span(self):
        attempt = self.scenario.investigate(self.finding(search=FABRICATED))
        self.assertEqual((attempt.outcome, attempt.findings), ("insufficient_evidence", ()))
        self.assertEqual(attempt.grounding_report, (GroundingReportEntry(candidate_index=0, code="unknown_span", kept=False),))

    def test_an_altered_quote_is_rejected_as_quote_mismatch(self):
        attempt = self.scenario.investigate(self.finding(retrieved_quote="restored for 15 days"))
        self.assertEqual((attempt.outcome, attempt.findings), ("insufficient_evidence", ()))
        self.assertEqual(attempt.grounding_report, (GroundingReportEntry(candidate_index=0, code="quote_mismatch", kept=False),))


class Rag04MetadataOnlyTests(unittest.TestCase):
    """The same RAG-04 run with every payload removed: nothing semantic can be grounded."""

    @classmethod
    def setUpClass(cls):
        cls.scenario = Scenario("RAG-04", transform=metadata_only)

    def test_the_snapshot_says_payloads_were_not_captured(self):
        self.assertFalse(self.scenario.snapshot.completeness.payloads_captured)

    def test_the_same_inconsistency_is_rejected_as_not_recorded(self):
        search = self.scenario.span_id(name="ScenarioAwareRetriever.search")
        answer = self.scenario.span_id(name="controlled.generate_answer")
        guess = {
            "category": "output_contradicts_evidence",
            "claim_type": "inconsistency",
            "suspicious_span_id": answer,
            "priority": "HIGH",
            "explanation": "The answer probably contradicts the document.",
            "evidence": [ref(search, "output_payload", "14 days"), ref(answer, "output_payload", "30 days")],
        }
        attempt = self.scenario.investigate(guess)
        self.assertEqual((attempt.outcome, attempt.findings, attempt.has_failure_findings), ("insufficient_evidence", (), False))
        self.assertEqual(
            attempt.grounding_report, (GroundingReportEntry(candidate_index=0, code="field_not_recorded", kept=False),)
        )

    def test_no_issue_found_carries_the_payload_limitation(self):
        attempt = self.scenario.investigate()
        self.assertEqual((attempt.outcome, attempt.findings), ("no_issue_found", ()))
        self.assertIn(PAYLOAD_LIMITATION, attempt.limitations)


class Tool03ObservedFailureTests(unittest.TestCase):
    """TOOL-03: the planner passed quantity 0; reserve failed with ToolError."""

    @classmethod
    def setUpClass(cls):
        cls.scenario = Scenario("TOOL-03")
        cls.reserve = cls.scenario.span_id(step="reserve")

    def observed(self, span_id, quote):
        return {
            "category": "tool_failure",
            "claim_type": "observed_failure",
            "suspicious_span_id": span_id,
            "priority": "HIGH",
            "explanation": "reserve_inventory failed; it was called with quantity 0.",
            "evidence": [ref(span_id, "status_code"), ref(span_id, "input_payload", quote)],
        }

    def quantity_quote(self):
        excerpt = self.scenario.excerpt(self.reserve, "input")
        quote = next(q for q in ('"quantity":0', '"quantity": 0') if q in excerpt)
        return quote

    def test_a_correct_observed_failure_is_grounded_and_kept_high(self):
        self.assertIn(self.reserve, self.scenario.snapshot.facts.originating_error_span_ids)
        attempt = self.scenario.investigate(self.observed(self.reserve, self.quantity_quote()))
        self.assertEqual((attempt.outcome, attempt.has_failure_findings), ("findings", True))
        (kept,) = attempt.findings
        self.assertEqual((kept.suspicious_span_id, kept.claim_type, kept.priority), (self.reserve, "observed_failure", "HIGH"))

    def test_an_altered_quote_is_rejected(self):
        attempt = self.scenario.investigate(self.observed(self.reserve, '"quantity": 7'))
        self.assertEqual(attempt.grounding_report, (GroundingReportEntry(candidate_index=0, code="quote_mismatch", kept=False),))

    def test_a_failure_claimed_on_the_ok_plan_span_is_rejected(self):
        plan = self.scenario.span_id(name="controlled.plan")
        claim = {
            "category": "tool_failure",
            "claim_type": "observed_failure",
            "suspicious_span_id": plan,
            "priority": "HIGH",
            "explanation": "The plan failed.",
            "evidence": [ref(plan, "status_code")],
        }
        attempt = self.scenario.investigate(claim)
        self.assertEqual(attempt.grounding_report, (GroundingReportEntry(candidate_index=0, code="no_failure_evidence", kept=False),))


class Tool07RecoveredRetryTests(unittest.TestCase):
    """TOOL-07: pay fails once, the retry succeeds, the run completes (test 53, A1)."""

    @classmethod
    def setUpClass(cls):
        cls.scenario = Scenario("TOOL-07")
        cls.first = cls.scenario.span_id(step="pay", attempt=1)

    def test_a_high_failure_on_attempt_1_is_stored_as_a_low_recovered_failure(self):
        flagged = {
            "category": "tool_failure",
            "claim_type": "observed_failure",
            "suspicious_span_id": self.first,
            "priority": "HIGH",
            "explanation": "charge_payment failed.",
            "evidence": [ref(self.first, "status_code"), ref(self.first, "error_type", "TransientToolError")],
        }
        attempt = self.scenario.investigate(flagged)
        self.assertEqual(attempt.outcome, "findings")
        (kept,) = attempt.findings
        self.assertEqual((kept.claim_type, kept.category, kept.priority), ("recovered_failure", "recovered_retry", "LOW"))
        self.assertFalse(attempt.has_failure_findings)
        self.assertNotIn("HIGH", [finding.priority for finding in attempt.findings])
        self.assertIn(GroundingReportEntry(candidate_index=0, code="clamped_recovered_retry", kept=True), attempt.grounding_report)


if __name__ == "__main__":
    unittest.main()
