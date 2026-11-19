"""Deterministic grounding: proposal §9 tests 19 to 37 (G), and `cited_value`.

One test per rule, in the order of the module docstring of `grounding.py`.
`reject_code`, `adjust` and `ground` are not written yet, so the rule tests are
marked `@unittest.expectedFailure`. When a function is written, its tests turn
into "unexpected success"; delete the decorator on them then. The
`cited_value` tests are not marked: that function exists.

Every test builds its trace and candidate with `tests/investigator/factories.py`
and calls the functions through the `grounding` module.
"""

import unittest

from agent_debugger_api.contracts.fakes import InMemoryTraceStore
from agent_debugger_api.investigator import grounding
from agent_debugger_api.investigator.grounding import PAYLOAD_LIMITATION, GroundingReportEntry
from agent_debugger_api.investigator.schema import CandidateFinding, EvidenceRef
from agent_debugger_api.investigator.snapshot import PayloadView, SnapshotLimits, build_snapshot
from agent_debugger_api.trace_writer.content_hash import content_hash
from tests.contracts.factories import PROJECT_A, TRACE_1, TRACE_2
from tests.investigator.factories import (
    AGENT,
    ORDER,
    PAY_1,
    PAY_2,
    PAY_3,
    PLAN,
    RESERVE,
    RESERVE_INPUT,
    ROOT,
    captured,
    error_span,
    evidence,
    failed_tool_trace,
    finding,
    output,
    retry_trace,
    sid,
    snapshot_of,
    span,
)

# ---------------------------------------------------------------------------
# Builders
# ---------------------------------------------------------------------------


def candidate(**overrides) -> CandidateFinding:
    """The factories' default finding (an observed failure on the reserve span) with overrides."""
    return CandidateFinding.model_validate(finding(**overrides))


def plain(**overrides) -> CandidateFinding:
    """A candidate with no claim-specific rule: no suspect, `completeness`. Only R1 to R7 can reject it."""
    fields = {"category": "other", "claim_type": "completeness", "suspicious_span_id": None, "priority": "LOW"}
    fields.update(overrides)
    return candidate(**fields)


def relation(kind: str, source: int, target: int) -> dict:
    return {"kind": kind, "from_span_id": sid(source), "to_span_id": sid(target)}


def tool_snapshot(payloads: bool = True):
    """root (ERROR) > agent > plan (OK), order (OK), reserve (ERROR)."""
    return snapshot_of(*failed_tool_trace(payloads=payloads))


def origin_candidate(priority: str = "MEDIUM", **overrides) -> CandidateFinding:
    """A `suspected_origin` that passes R1 to R11 on `tool_snapshot()`: the plan asked for quantity 0.

    plan and reserve are siblings, so they connect through their parent with two `parent_of` relations.
    """
    fields = {
        "category": "unsupported_output",
        "claim_type": "suspected_origin",
        "suspicious_span_id": sid(PLAN),
        "priority": priority,
        "evidence": [evidence(PLAN, "output_payload", quote='"quantity":0')],
        "relations": [relation("parent_of", AGENT, PLAN), relation("parent_of", AGENT, RESERVE)],
        "limitations": ["The run does not record why quantity 0 was chosen."],
    }
    fields.update(overrides)
    return candidate(**fields)


def inconsistency_candidate(priority: str = "MEDIUM", **overrides) -> CandidateFinding:
    """An `inconsistency` that passes R1 to R11 on `tool_snapshot()`: two payload quotes on two spans."""
    fields = {
        "category": "output_contradicts_evidence",
        "claim_type": "inconsistency",
        "suspicious_span_id": sid(ORDER),
        "priority": priority,
        "evidence": [
            evidence(PLAN, "output_payload", quote='"quantity":0'),
            evidence(ORDER, "output_payload", quote='"quantity":2'),
        ],
    }
    fields.update(overrides)
    return candidate(**fields)


def reject(snapshot, **overrides):
    return grounding.reject_code(snapshot, candidate(**overrides))


def reject_plain(snapshot, **overrides):
    return grounding.reject_code(snapshot, plain(**overrides))


def other_trace_snapshot():
    """A real snapshot of a different trace: span 40 exists there and not in `tool_snapshot()`."""
    store = InMemoryTraceStore(content_hash)
    store.insert_spans([span(40, operation_type="run", trace_id=TRACE_2)])
    return build_snapshot(store.get_trace(PROJECT_A, TRACE_2), PROJECT_A, TRACE_2)


def collapsed_snapshot():
    """Span 3 is an OK leaf the snapshot collapsed into a rollup, so it is not rendered."""
    records = [
        span(1, operation_type="run", status_code="ERROR", start=0, duration=50),
        span(2, 1, start=1, duration=40, operation_type="agent"),
        *[span(number, 2, start=number) for number in range(3, 9)],
        error_span(9, 2, start=10),
    ]
    snapshot = snapshot_of(*records, limits=SnapshotLimits(max_spans=5, siblings_before_error=1))
    assert snapshot.versions(sid(3)) == () and snapshot.rollups, "fixture: span 3 must be collapsed"
    return snapshot


def conflicted_snapshot():
    """Span 2 is stored twice with different content: two rendered versions, each with a hash."""
    return snapshot_of(
        span(1, operation_type="run"),
        span(2, 1, start=1, status_description="first"),
        span(2, 1, start=1, status_description="second"),
    )


# ---------------------------------------------------------------------------
# Reject rules R1 to R11: tests 19 to 29
# ---------------------------------------------------------------------------


class RejectRuleTests(unittest.TestCase):
    def test_19_r1_every_cited_span_must_be_a_rendered_span_of_this_snapshot(self):
        snapshot = tool_snapshot()
        self.assertIsNone(reject(snapshot))  # control
        with self.subTest("fabricated span in evidence"):
            self.assertEqual(reject(snapshot, evidence=[evidence(RESERVE), evidence(99)]), "unknown_span")
        with self.subTest("fabricated suspicious_span_id"):
            self.assertEqual(reject(snapshot, suspicious_span_id=sid(99)), "unknown_span")
        with self.subTest("fabricated relation endpoint, from"):
            self.assertEqual(reject(snapshot, relations=[relation("parent_of", 99, RESERVE)]), "unknown_span")
        with self.subTest("fabricated relation endpoint, to"):
            self.assertEqual(reject(snapshot, relations=[relation("parent_of", AGENT, 99)]), "unknown_span")
        with self.subTest("a real span ID from another trace"):
            other = other_trace_snapshot()
            self.assertEqual(len(other.versions(sid(40))), 1)
            self.assertEqual(snapshot.versions(sid(40)), ())
            self.assertEqual(reject(snapshot, evidence=[evidence(40)], suspicious_span_id=None), "unknown_span")
        with self.subTest("the ID of a collapsed span"):
            collapsed = collapsed_snapshot()
            self.assertEqual(reject_plain(collapsed, evidence=[evidence(1), evidence(3)]), "unknown_span")
            self.assertIsNone(reject_plain(collapsed, evidence=[evidence(1), evidence(9)]))  # rendered neighbour

    def test_20_r2_a_conflicted_span_needs_a_hash_that_matches_one_version(self):
        snapshot = conflicted_snapshot()
        hashes = [version.content_hash for version in snapshot.versions(sid(2))]
        self.assertEqual(len(hashes), 2)
        wrong = "0" * 12
        self.assertNotIn(wrong, hashes)
        with self.subTest("no hash"):
            self.assertEqual(reject_plain(snapshot, evidence=[evidence(2, "status_description")]), "ambiguous_version")
        with self.subTest("wrong hash"):
            ref = evidence(2, "status_description", content_hash=wrong)
            self.assertEqual(reject_plain(snapshot, evidence=[ref]), "ambiguous_version")
        for value in hashes:
            with self.subTest("right hash", content_hash=value):
                ref = evidence(2, "status_description", content_hash=value)
                self.assertIsNone(reject_plain(snapshot, evidence=[ref]))
        with self.subTest("a span that is not conflicted needs no hash"):
            self.assertIsNone(reject_plain(snapshot, evidence=[evidence(1)]))

    def test_21_r3_event_index_must_exist_on_the_cited_span(self):
        snapshot = tool_snapshot()
        with self.subTest("index past the last event"):
            ref = evidence(RESERVE, "event", event_index=5)
            self.assertEqual(reject(snapshot, evidence=[evidence(RESERVE), ref]), "unknown_event")
        with self.subTest("span with no events"):
            self.assertEqual(reject_plain(snapshot, evidence=[evidence(PLAN, "event", event_index=0)]), "unknown_event")
        with self.subTest("no index given"):
            self.assertEqual(reject_plain(snapshot, evidence=[evidence(RESERVE, "event")]), "unknown_event")
        with self.subTest("existing event"):
            self.assertIsNone(reject(snapshot, evidence=[evidence(RESERVE, "event", event_index=0)]))

    def test_22_r4_attribute_key_must_be_on_the_span_in_the_snapshot(self):
        records = [
            span(1, operation_type="run"),
            span(2, 1, start=1, attributes={"debugger.step": "reserve", "service.internal": "x"}),
        ]
        snapshot = snapshot_of(*records)
        self.assertEqual(sorted(snapshot.versions(sid(2))[0].attributes), ["debugger.step"])
        with self.subTest("key on the span"):
            self.assertIsNone(reject_plain(snapshot, evidence=[evidence(2, "attribute", key="debugger.step")]))
        with self.subTest("key not on the span"):
            ref = evidence(2, "attribute", key="debugger.nope")
            self.assertEqual(reject_plain(snapshot, evidence=[ref]), "unknown_field")
        with self.subTest("key the snapshot's allowlist left out"):
            ref = evidence(2, "attribute", key="service.internal")
            self.assertEqual(reject_plain(snapshot, evidence=[ref]), "unknown_field")
        with self.subTest("no key given"):
            self.assertEqual(reject_plain(snapshot, evidence=[evidence(2, "attribute")]), "unknown_field")
        with self.subTest("key that exists on another span only"):
            self.assertEqual(reject_plain(snapshot, evidence=[evidence(1, "attribute", key="debugger.step")]), "unknown_field")

    def test_23_r5_the_cited_field_must_be_recorded(self):
        redacted_input = '{"order":42,"api_key":"[redacted]"}'
        snapshot = snapshot_of(
            span(1, operation_type="run"),
            span(2, 1, start=1, input_state="disabled", output_state="unavailable"),
            span(3, 1, start=2),  # OK: error_type is empty, no attempt, error payload unavailable
            span(4, 1, start=3, input_state="redacted", input_payload=redacted_input),
            span(5, 1, start=4, attempt=0),
        )
        with self.subTest("payload state unavailable"):
            self.assertEqual(reject_plain(snapshot, evidence=[evidence(2, "output_payload")]), "field_not_recorded")
        with self.subTest("payload state disabled"):
            self.assertEqual(reject_plain(snapshot, evidence=[evidence(2, "input_payload")]), "field_not_recorded")
        with self.subTest("error payload unavailable"):
            self.assertEqual(reject_plain(snapshot, evidence=[evidence(3, "error_payload")]), "field_not_recorded")
        with self.subTest("empty error_type"):
            self.assertEqual(reject_plain(snapshot, evidence=[evidence(3, "error_type")]), "field_not_recorded")
        with self.subTest("attempt not recorded"):
            self.assertEqual(reject_plain(snapshot, evidence=[evidence(3, "attempt")]), "field_not_recorded")
        with self.subTest("attempt 0 is recorded"):
            self.assertIsNone(reject_plain(snapshot, evidence=[evidence(5, "attempt", quote="0")]))
        with self.subTest("redacted payload cited without a quote"):
            self.assertIsNone(reject_plain(snapshot, evidence=[evidence(4, "input_payload")]))
        with self.subTest("redacted payload quoted outside its markers"):
            ref = evidence(4, "input_payload", quote='"order":42')
            self.assertIsNone(reject_plain(snapshot, evidence=[ref]))
        with self.subTest("a quote that contains the marker cites an unrecorded value"):
            # The quote is a substring of the excerpt, so R6 alone would pass it: R5 must stop it first.
            for quote in ('"api_key":"[redacted]"', "[redacted]"):
                self.assertIn(quote, snapshot.versions(sid(4))[0].input.excerpt)
                ref = evidence(4, "input_payload", quote=quote)
                self.assertEqual(reject_plain(snapshot, evidence=[ref]), "field_not_recorded")

    def test_24_r6_a_quote_must_be_an_exact_substring_of_the_cited_value(self):
        snapshot = tool_snapshot()
        self.assertIn('"quantity":0', RESERVE_INPUT)
        with self.subTest("exact quote"):
            self.assertIsNone(reject_plain(snapshot, evidence=[evidence(RESERVE, "input_payload", quote='"quantity":0')]))
        with self.subTest("one character different"):
            ref = evidence(RESERVE, "input_payload", quote='"quantity":1')
            self.assertEqual(reject_plain(snapshot, evidence=[ref]), "quote_mismatch")
        with self.subTest("one character different in case"):
            ref = evidence(RESERVE, "input_payload", quote='"Quantity":0')
            self.assertEqual(reject_plain(snapshot, evidence=[ref]), "quote_mismatch")
        with self.subTest("quote on a metadata field"):
            self.assertIsNone(reject_plain(snapshot, evidence=[evidence(RESERVE, "status_code", quote="ERROR")]))
            self.assertEqual(reject_plain(snapshot, evidence=[evidence(RESERVE, "status_code", quote="OK")]), "quote_mismatch")

        long_output = "H" * 800 + "M" * 5000 + "T" * 400
        long_snapshot = snapshot_of(span(1, operation_type="run"), span(2, 1, start=1, **captured(output=long_output)))
        self.assertNotIn("M", long_snapshot.versions(sid(2))[0].output.excerpt)
        with self.subTest("quote from the head"):
            self.assertIsNone(reject_plain(long_snapshot, evidence=[evidence(2, "output_payload", quote="H" * 50)]))
        with self.subTest("quote from the tail"):
            self.assertIsNone(reject_plain(long_snapshot, evidence=[evidence(2, "output_payload", quote="T" * 50)]))
        with self.subTest("quote from the omitted middle"):
            ref = evidence(2, "output_payload", quote="M" * 50)
            self.assertEqual(reject_plain(long_snapshot, evidence=[ref]), "quote_mismatch")

    def test_25_r7_a_relation_must_exist_in_the_snapshot(self):
        tool = tool_snapshot()
        with self.subTest("retry_of between unrelated spans"):
            self.assertEqual(reject_plain(tool, relations=[relation("retry_of", RESERVE, ORDER)]), "unknown_relationship")
        with self.subTest("parent_of, parent to child"):
            self.assertIsNone(reject_plain(tool, relations=[relation("parent_of", AGENT, RESERVE)]))
        with self.subTest("parent_of, child to parent"):
            self.assertEqual(reject_plain(tool, relations=[relation("parent_of", RESERVE, AGENT)]), "unknown_relationship")
        with self.subTest("parent_of, grandparent to grandchild"):
            self.assertEqual(reject_plain(tool, relations=[relation("parent_of", ROOT, RESERVE)]), "unknown_relationship")

        retries = snapshot_of(*retry_trace("ERROR", "ERROR", "OK"))
        evidence_on_retry = [evidence(PAY_1)]
        with self.subTest("retry_of, attempt 2 to attempt 1"):
            relations = [relation("retry_of", PAY_2, PAY_1)]
            self.assertIsNone(reject_plain(retries, evidence=evidence_on_retry, relations=relations))
        with self.subTest("retry_of, reversed"):
            relations = [relation("retry_of", PAY_1, PAY_2)]
            self.assertEqual(reject_plain(retries, evidence=evidence_on_retry, relations=relations), "unknown_relationship")
        with self.subTest("retry_of, attempt 3 to attempt 1 (not the direct predecessor)"):
            relations = [relation("retry_of", PAY_3, PAY_1)]
            self.assertEqual(reject_plain(retries, evidence=evidence_on_retry, relations=relations), "unknown_relationship")

        linked = snapshot_of(
            span(1, operation_type="run"),
            span(2, 1, start=1),
            span(3, 1, start=2, links=[{"trace_id": TRACE_1, "span_id": sid(2), "relation": "depends_on"}]),
        )
        with self.subTest("link, from the span that has it"):
            self.assertIsNone(reject_plain(linked, evidence=[evidence(1)], relations=[relation("link", 3, 2)]))
        with self.subTest("link, reversed"):
            result = reject_plain(linked, evidence=[evidence(1)], relations=[relation("link", 2, 3)])
            self.assertEqual(result, "unknown_relationship")
        with self.subTest("link to a span it does not point at"):
            result = reject_plain(linked, evidence=[evidence(1)], relations=[relation("link", 3, 1)])
            self.assertEqual(result, "unknown_relationship")

    def test_26_r8_the_suspect_needs_evidence_on_itself(self):
        snapshot = tool_snapshot()
        self.assertIsNone(reject(snapshot))  # suspect reserve, evidence on reserve
        with self.subTest("evidence only on another span"):
            result = reject(snapshot, suspicious_span_id=sid(AGENT), evidence=[evidence(RESERVE)])
            self.assertEqual(result, "unsupported_suspect")
        with self.subTest("evidence on the suspect among others"):
            result = reject(snapshot, suspicious_span_id=sid(AGENT), evidence=[evidence(RESERVE), evidence(AGENT, "span_name")])
            self.assertIsNone(result)
        with self.subTest("no suspect, no check"):
            self.assertIsNone(reject(snapshot, suspicious_span_id=None))

    def test_27_r9_an_observed_failure_cites_an_error_status_or_an_exception_event(self):
        snapshot = tool_snapshot()
        with self.subTest("only OK spans"):
            result = reject(snapshot, suspicious_span_id=sid(ORDER), evidence=[evidence(ORDER)])
            self.assertEqual(result, "no_failure_evidence")
        with self.subTest("several refs, all on OK spans"):
            result = reject(snapshot, suspicious_span_id=sid(ORDER), evidence=[evidence(ORDER), evidence(PLAN, "span_name")])
            self.assertEqual(result, "no_failure_evidence")
        with self.subTest("an ERROR span, but not its status_code"):
            result = reject(snapshot, evidence=[evidence(RESERVE, "span_name")])
            self.assertEqual(result, "no_failure_evidence")
        with self.subTest("status_code of an ERROR span"):
            self.assertIsNone(reject(snapshot, evidence=[evidence(RESERVE)]))
        with self.subTest("status_code of an ERROR span among OK refs"):
            result = reject(snapshot, evidence=[evidence(RESERVE, "span_name"), evidence(RESERVE)])
            self.assertIsNone(result)
        with self.subTest("the exception event"):
            self.assertEqual(snapshot.versions(sid(RESERVE))[0].events[0].name, "exception")
            self.assertIsNone(reject(snapshot, evidence=[evidence(RESERVE, "event", event_index=0)]))
        with self.subTest("other claim types are not held to R9"):
            result = reject_plain(snapshot, suspicious_span_id=sid(ORDER), evidence=[evidence(ORDER)])
            self.assertIsNone(result)

    def test_28_r10_an_inconsistency_needs_payload_quotes_on_two_spans(self):
        snapshot = tool_snapshot()
        self.assertIsNone(grounding.reject_code(snapshot, inconsistency_candidate()))  # two quotes, two spans: kept
        with self.subTest("metadata-only snapshot"):
            metadata_only = tool_snapshot(payloads=False)
            self.assertFalse(metadata_only.completeness.payloads_captured)
            metadata_quotes = inconsistency_candidate(
                suspicious_span_id=None,
                evidence=[evidence(ROOT, quote="ERROR"), evidence(RESERVE, quote="ERROR")],
            )
            self.assertEqual(grounding.reject_code(metadata_only, metadata_quotes), "insufficient_evidence")
        with self.subTest("two payload quotes on one span"):
            same_span = inconsistency_candidate(
                suspicious_span_id=None,
                evidence=[
                    evidence(RESERVE, "input_payload", quote='"quantity":0'),
                    evidence(RESERVE, "error_payload", quote="ToolError"),
                ],
            )
            self.assertEqual(grounding.reject_code(snapshot, same_span), "insufficient_evidence")
        with self.subTest("one payload quote and one metadata quote"):
            mixed = inconsistency_candidate(
                evidence=[evidence(PLAN, "output_payload", quote='"quantity":0'), evidence(ORDER, quote="OK")],
            )
            self.assertEqual(grounding.reject_code(snapshot, mixed), "insufficient_evidence")
        with self.subTest("payload fields without quotes"):
            no_quotes = inconsistency_candidate(
                evidence=[evidence(PLAN, "output_payload"), evidence(ORDER, "output_payload")],
            )
            self.assertEqual(grounding.reject_code(snapshot, no_quotes), "insufficient_evidence")
        with self.subTest("a single ref"):
            single = inconsistency_candidate(suspicious_span_id=None, evidence=[evidence(PLAN, "output_payload", quote='"quantity":0')])
            self.assertEqual(grounding.reject_code(snapshot, single), "insufficient_evidence")

    def test_29_r11_a_suspected_origin_connects_to_a_failing_span_and_names_a_limitation(self):
        snapshot = tool_snapshot()
        self.assertEqual(snapshot.versions(sid(PLAN))[0].status_code.value, "OK")
        with self.subTest("siblings connected through their parent"):
            self.assertIsNone(grounding.reject_code(snapshot, origin_candidate()))
        with self.subTest("a direct relation to a failing span"):
            direct = origin_candidate(
                suspicious_span_id=sid(AGENT),
                evidence=[evidence(AGENT, "span_name")],
                relations=[relation("parent_of", AGENT, RESERVE)],
            )
            self.assertIsNone(grounding.reject_code(snapshot, direct))
        with self.subTest("no relation"):
            self.assertEqual(grounding.reject_code(snapshot, origin_candidate(relations=[])), "unsupported_suspicion")
        with self.subTest("no limitation"):
            self.assertEqual(grounding.reject_code(snapshot, origin_candidate(limitations=[])), "unsupported_suspicion")
        with self.subTest("relations lead only to OK spans"):
            ok_only = origin_candidate(relations=[relation("parent_of", AGENT, PLAN), relation("parent_of", AGENT, ORDER)])
            self.assertEqual(grounding.reject_code(snapshot, ok_only), "unsupported_suspicion")
        with self.subTest("the failing span is related, but not to the suspect"):
            apart = origin_candidate(relations=[relation("parent_of", AGENT, RESERVE)])
            self.assertEqual(grounding.reject_code(snapshot, apart), "unsupported_suspicion")


# ---------------------------------------------------------------------------
# Adjustments A1 to A4: tests 30 to 33
# ---------------------------------------------------------------------------


def retry_candidate(span_number: int, **overrides) -> CandidateFinding:
    """HIGH `tool_failure` observed on one `pay` attempt."""
    fields = {"category": "tool_failure", "suspicious_span_id": sid(span_number), "evidence": [evidence(span_number)]}
    fields.update(overrides)
    return candidate(**{"priority": "HIGH", **fields})


class AdjustRuleTests(unittest.TestCase):
    @unittest.expectedFailure
    def test_30_a1_a_recovered_retry_is_not_a_failure(self):
        snapshot = snapshot_of(*retry_trace("ERROR", "OK"))
        self.assertEqual(snapshot.retry_group_of(sid(PAY_1)).outcome, "recovered")
        attempt_1 = retry_candidate(PAY_1)
        self.assertIsNone(grounding.reject_code(snapshot, attempt_1))

        adjusted, codes = grounding.adjust(snapshot, 3, attempt_1)
        self.assertEqual(codes, ("clamped_recovered_retry",))
        self.assertEqual(adjusted.claim_type, "recovered_failure")
        self.assertEqual(adjusted.category, "recovered_retry")
        self.assertEqual(adjusted.priority, "LOW")
        self.assertEqual(adjusted.candidate_index, 3)
        self.assertEqual(adjusted.suspicious_span_id, sid(PAY_1))
        self.assertEqual(adjusted.evidence, attempt_1.evidence)
        self.assertEqual(adjusted.explanation, attempt_1.explanation)

        with self.subTest("through ground: kept, recorded, and not a failure finding"):
            raw = finding(category="tool_failure", priority="HIGH", suspicious_span_id=sid(PAY_1), evidence=[evidence(PAY_1)])
            result = grounding.ground(snapshot, output(raw))
            self.assertEqual(result.outcome, "findings")
            self.assertEqual([f.claim_type for f in result.findings], ["recovered_failure"])
            self.assertEqual(
                result.report, (GroundingReportEntry(candidate_index=0, code="clamped_recovered_retry", kept=True),)
            )
            self.assertFalse(result.has_failure_findings)
        with self.subTest("no suspect: an ERROR span in the evidence is enough"):
            _, codes = grounding.adjust(snapshot, 0, retry_candidate(PAY_1, suspicious_span_id=None))
            self.assertEqual(codes, ("clamped_recovered_retry",))
        with self.subTest("evidence also points at an unrecovered ERROR span: no clamp to recovered"):
            with_other_error = snapshot_of(*retry_trace("ERROR", "OK"), error_span(9, AGENT, start=30))
            mixed = retry_candidate(PAY_1, evidence=[evidence(PAY_1), evidence(9)])
            adjusted, codes = grounding.adjust(with_other_error, 0, mixed)
            self.assertEqual(adjusted.claim_type, "observed_failure")
            self.assertEqual(adjusted.category, "tool_failure")
            # The suspect belongs to a recovered group, so A3 still lowers HIGH.
            self.assertEqual((adjusted.priority, codes), ("MEDIUM", ("clamped_priority",)))

    @unittest.expectedFailure
    def test_31_a1_does_not_fire_for_an_exhausted_group(self):
        snapshot = snapshot_of(*retry_trace("ERROR", "ERROR", "ERROR"))
        self.assertEqual(snapshot.retry_group_of(sid(PAY_1)).outcome, "exhausted")
        for number in (PAY_1, PAY_2, PAY_3):
            with self.subTest(attempt=number - PAY_1 + 1):
                original = retry_candidate(number)
                adjusted, codes = grounding.adjust(snapshot, 0, original)
                self.assertEqual(codes, ())
                self.assertEqual(adjusted.claim_type, "observed_failure")
                self.assertEqual(adjusted.category, "tool_failure")
                self.assertEqual(adjusted.priority, "HIGH")  # each attempt is an originating error outside a recovered group

    @unittest.expectedFailure
    def test_32_a2_and_a3_clamp_priority_to_what_the_claim_supports(self):
        snapshot = tool_snapshot()
        self.assertEqual(snapshot.facts.originating_error_span_ids, (sid(RESERVE),))
        with self.subTest("A2: suspected_origin proposed HIGH"):
            adjusted, codes = grounding.adjust(snapshot, 0, origin_candidate("HIGH"))
            self.assertEqual((adjusted.priority, codes), ("MEDIUM", ("clamped_suspicion",)))
        with self.subTest("A2: suspected_origin proposed MEDIUM or LOW is left alone"):
            for priority in ("MEDIUM", "LOW"):
                adjusted, codes = grounding.adjust(snapshot, 0, origin_candidate(priority))
                self.assertEqual((adjusted.priority, codes), (priority, ()))
        with self.subTest("A3: observed_failure on a non-originating error proposed HIGH"):
            parent_error = candidate(priority="HIGH", suspicious_span_id=sid(ROOT), evidence=[evidence(ROOT)])
            adjusted, codes = grounding.adjust(snapshot, 0, parent_error)
            self.assertEqual((adjusted.priority, codes), ("MEDIUM", ("clamped_priority",)))
            self.assertEqual(adjusted.claim_type, "observed_failure")
        with self.subTest("A3: observed_failure on the originating error keeps HIGH"):
            adjusted, codes = grounding.adjust(snapshot, 0, candidate(priority="HIGH"))
            self.assertEqual((adjusted.priority, codes), ("HIGH", ()))
        with self.subTest("A3: an inconsistency that passed R10 keeps HIGH"):
            adjusted, codes = grounding.adjust(snapshot, 0, inconsistency_candidate("HIGH"))
            self.assertEqual((adjusted.priority, codes), ("HIGH", ()))
        with self.subTest("A3: any other claim proposed HIGH becomes MEDIUM"):
            other = plain(priority="HIGH", evidence=[evidence(RESERVE)])
            adjusted, codes = grounding.adjust(snapshot, 0, other)
            self.assertEqual((adjusted.priority, codes), ("MEDIUM", ("clamped_priority",)))
        with self.subTest("an unchanged priority reports no code"):
            adjusted, codes = grounding.adjust(snapshot, 0, candidate(priority="MEDIUM"))
            self.assertEqual((adjusted.priority, codes), ("MEDIUM", ()))

    @unittest.expectedFailure
    def test_33_a4_the_same_suspect_and_category_twice_gives_one_finding(self):
        snapshot = tool_snapshot()
        with self.subTest("identical candidates"):
            result = grounding.ground(snapshot, output(finding(), finding()))
            self.assertEqual([f.candidate_index for f in result.findings], [0])
            self.assertEqual(result.report, (GroundingReportEntry(candidate_index=1, code="duplicate", kept=False),))
        with self.subTest("same suspect, different category: both kept"):
            result = grounding.ground(snapshot, output(finding(), finding(category="timeout")))
            self.assertEqual([f.candidate_index for f in result.findings], [0, 1])
            self.assertEqual(result.report, ())
        with self.subTest("different suspect, same category: both kept"):
            second = finding(suspicious_span_id=sid(ROOT), evidence=[evidence(ROOT)], priority="MEDIUM")
            result = grounding.ground(snapshot, output(finding(), second))
            self.assertEqual([f.candidate_index for f in result.findings], [0, 1])
        with self.subTest("compared after A1: two categories that both become recovered_retry"):
            retries = snapshot_of(*retry_trace("ERROR", "OK"))
            first = finding(category="tool_failure", suspicious_span_id=sid(PAY_1), evidence=[evidence(PAY_1)])
            second = finding(category="timeout", suspicious_span_id=sid(PAY_1), evidence=[evidence(PAY_1)])
            result = grounding.ground(retries, output(first, second))
            self.assertEqual([(f.candidate_index, f.category) for f in result.findings], [(0, "recovered_retry")])
            self.assertIn(GroundingReportEntry(candidate_index=1, code="duplicate", kept=False), result.report)


# ---------------------------------------------------------------------------
# ground(): tests 34 to 37
# ---------------------------------------------------------------------------


def fabricated(**overrides) -> dict:
    """A candidate R1 rejects: it cites a span that does not exist."""
    return finding(suspicious_span_id=sid(99), evidence=[evidence(99)], **overrides)


def only_ok_evidence() -> dict:
    """A candidate R9 rejects: an observed failure that cites an OK span."""
    return finding(suspicious_span_id=sid(ORDER), evidence=[evidence(ORDER)])


class GroundTests(unittest.TestCase):
    @unittest.expectedFailure
    def test_34_one_bad_candidate_does_not_affect_a_good_one(self):
        snapshot = tool_snapshot()
        alone = grounding.ground(snapshot, output(finding()))
        self.assertEqual(len(alone.findings), 1)
        for name, candidates, good_index in (
            ("bad first", (fabricated(), finding()), 1),
            ("bad last", (finding(), fabricated()), 0),
            ("bad between", (fabricated(), finding(), only_ok_evidence()), 1),
        ):
            with self.subTest(name):
                result = grounding.ground(snapshot, output(*candidates))
                self.assertEqual(result.outcome, "findings")
                self.assertEqual([f.candidate_index for f in result.findings], [good_index])
                # The good finding is the one it would be alone, apart from its position.
                self.assertEqual(result.findings[0], alone.findings[0].model_copy(update={"candidate_index": good_index}))
                self.assertTrue(result.has_failure_findings)
                self.assertTrue(all(not entry.kept for entry in result.report))
        with self.subTest("the report names the rejected one"):
            result = grounding.ground(snapshot, output(fabricated(), finding()))
            self.assertEqual(result.report, (GroundingReportEntry(candidate_index=0, code="unknown_span", kept=False),))

    @unittest.expectedFailure
    def test_35_all_candidates_rejected_gives_insufficient_evidence_and_records_the_codes(self):
        snapshot = tool_snapshot()
        result = grounding.ground(snapshot, output(fabricated(), only_ok_evidence()))
        self.assertEqual(result.outcome, "insufficient_evidence")
        self.assertEqual(result.findings, ())
        self.assertFalse(result.has_failure_findings)
        self.assertEqual(
            result.report,
            (
                GroundingReportEntry(candidate_index=0, code="unknown_span", kept=False),
                GroundingReportEntry(candidate_index=1, code="no_failure_evidence", kept=False),
            ),
        )
        with self.subTest("a single rejected candidate"):
            result = grounding.ground(snapshot, output(fabricated()))
            self.assertEqual((result.outcome, result.findings), ("insufficient_evidence", ()))
            self.assertEqual([entry.code for entry in result.report], ["unknown_span"])
        with self.subTest("the model's own verdict"):
            result = grounding.ground(snapshot, output(verdict="insufficient_evidence"))
            self.assertEqual((result.outcome, result.findings, result.report), ("insufficient_evidence", (), ()))

    @unittest.expectedFailure
    def test_36_no_issue_found_on_a_metadata_only_snapshot_carries_the_payload_limitation(self):
        metadata_only = tool_snapshot(payloads=False)
        self.assertFalse(metadata_only.completeness.payloads_captured)
        with self.subTest("metadata only"):
            result = grounding.ground(metadata_only, output())
            self.assertEqual((result.outcome, result.findings), ("no_issue_found", ()))
            self.assertIn(PAYLOAD_LIMITATION, result.limitations)
            self.assertFalse(result.has_failure_findings)
        with self.subTest("the model's own limitations are carried too"):
            result = grounding.ground(metadata_only, output(limitations=("Only metadata was checked.",)))
            self.assertIn("Only metadata was checked.", result.limitations)
            self.assertIn(PAYLOAD_LIMITATION, result.limitations)
        with self.subTest("payloads captured: no payload limitation"):
            with_payloads = tool_snapshot()
            self.assertTrue(with_payloads.completeness.payloads_captured)
            result = grounding.ground(with_payloads, output(limitations=("Checked every step.",)))
            self.assertEqual(result.outcome, "no_issue_found")
            self.assertEqual(result.limitations, ("Checked every step.",))

    @unittest.expectedFailure
    def test_37_grounding_is_pure(self):
        snapshot = tool_snapshot()
        model_output = output(
            finding(),
            fabricated(),
            finding(priority="HIGH", suspicious_span_id=sid(ROOT), evidence=[evidence(ROOT)]),
            finding(),
        )
        snapshot_before = (snapshot.snapshot_hash, snapshot.model_dump())
        output_before = model_output.model_dump()

        first = grounding.ground(snapshot, model_output)
        second = grounding.ground(snapshot, model_output)
        self.assertEqual(first, second)
        self.assertEqual({entry.code for entry in first.report}, {"unknown_span", "clamped_priority", "duplicate"})
        self.assertEqual((snapshot.snapshot_hash, snapshot.model_dump()), snapshot_before)
        self.assertEqual(model_output.model_dump(), output_before)

        for item in model_output.findings:
            self.assertEqual(grounding.reject_code(snapshot, item), grounding.reject_code(snapshot, item))
        accepted = model_output.findings[0]
        self.assertEqual(grounding.adjust(snapshot, 0, accepted), grounding.adjust(snapshot, 0, accepted))
        self.assertEqual((snapshot.snapshot_hash, snapshot.model_dump()), snapshot_before)


# ---------------------------------------------------------------------------
# cited_value: written, so not marked expectedFailure
# ---------------------------------------------------------------------------

LONG_OUTPUT = "H" * 800 + "M" * 5000 + "T" * 400
REDACTED_INPUT = '{"order":42,"api_key":"[redacted]"}'


def cited_snapshot():
    return snapshot_of(
        span(1, operation_type="run"),
        # ERROR: error type, exception event, error payload; status text, attempt 0, one attribute.
        error_span(2, 1, start=1, status_description="boom", attempt=0, attributes={"debugger.step": "reserve"}),
        span(3, 1, start=2, attempt=1, retry_of_span_id=sid(2)),
        span(4, 1, start=3),  # OK: nothing optional recorded
        span(5, 1, start=4, input_state="captured", input_payload='{"a":1}',
             output_state="truncated", output_payload='{"b":2}'),
        span(6, 1, start=5, **captured(output=LONG_OUTPUT)),
        span(7, 1, start=6, input_state="redacted", input_payload=REDACTED_INPUT),
        span(8, 1, start=7, input_state="disabled", output_state="unavailable"),
    )


def cited(snapshot, number: int, field: str, **more) -> str | None:
    rendered = snapshot.versions(sid(number))[0]
    return grounding.cited_value(rendered, EvidenceRef.model_validate(evidence(number, field, **more)))


class CitedValueTests(unittest.TestCase):
    def setUp(self):
        self.snapshot = cited_snapshot()

    def test_status_code_is_the_status_name_not_the_enum_repr(self):
        self.assertEqual(cited(self.snapshot, 2, "status_code"), "ERROR")
        self.assertEqual(cited(self.snapshot, 4, "status_code"), "OK")
        self.assertNotIn("StatusCode", cited(self.snapshot, 2, "status_code"))

    def test_attempt_zero_is_recorded_and_a_missing_attempt_is_not(self):
        self.assertEqual(cited(self.snapshot, 2, "attempt"), "0")
        self.assertEqual(cited(self.snapshot, 3, "attempt"), "1")
        self.assertIsNone(cited(self.snapshot, 4, "attempt"))

    def test_an_empty_error_type_is_not_recorded(self):
        self.assertIsNone(cited(self.snapshot, 4, "error_type"))
        self.assertEqual(cited(self.snapshot, 2, "error_type"), "ToolError")

    def test_other_span_fields_are_the_span_value_or_none(self):
        self.assertEqual(cited(self.snapshot, 2, "status_description"), "boom")
        self.assertIsNone(cited(self.snapshot, 4, "status_description"))
        self.assertEqual(cited(self.snapshot, 2, "span_name"), "span-2")
        self.assertEqual(cited(self.snapshot, 3, "retry_of_span_id"), sid(2))
        self.assertIsNone(cited(self.snapshot, 2, "retry_of_span_id"))

    def test_attribute_is_the_value_under_the_key(self):
        self.assertEqual(cited(self.snapshot, 2, "attribute", key="debugger.step"), "reserve")
        self.assertIsNone(cited(self.snapshot, 2, "attribute", key="debugger.nope"))
        self.assertIsNone(cited(self.snapshot, 2, "attribute"))  # no key
        self.assertIsNone(cited(self.snapshot, 4, "attribute", key="debugger.step"))  # key of another span

    def test_a_readable_payload_is_its_excerpt(self):
        self.assertEqual(cited(self.snapshot, 5, "input_payload"), '{"a":1}')  # captured
        self.assertEqual(cited(self.snapshot, 5, "output_payload"), '{"b":2}')  # truncated is readable
        self.assertEqual(cited(self.snapshot, 2, "error_payload"), self.snapshot.versions(sid(2))[0].error.excerpt)

    def test_a_disabled_or_unavailable_payload_is_not_recorded(self):
        self.assertIsNone(cited(self.snapshot, 8, "input_payload"))  # disabled
        self.assertIsNone(cited(self.snapshot, 8, "output_payload"))  # unavailable
        self.assertIsNone(cited(self.snapshot, 4, "error_payload"))  # unavailable

    def test_a_readable_payload_whose_excerpt_a_reduction_dropped_is_not_recorded(self):
        rendered = self.snapshot.versions(sid(5))[0]
        dropped = rendered.model_copy(update={"input": PayloadView(state=rendered.input.state, excerpt=None, full_length=7)})
        ref = EvidenceRef.model_validate(evidence(5, "input_payload"))
        self.assertIsNone(grounding.cited_value(dropped, ref))

    def test_a_redacted_payload_keeps_its_marker_in_the_excerpt(self):
        value = cited(self.snapshot, 7, "input_payload")
        self.assertEqual(value, REDACTED_INPUT)
        self.assertIn("[redacted]", value)

    def test_an_event_is_its_name_and_attribute_values(self):
        value = cited(self.snapshot, 2, "event", event_index=0)
        for part in ("exception", "ToolError", "ToolError during span-2"):
            self.assertIn(part, value)

    def test_an_event_that_does_not_exist_is_not_recorded(self):
        self.assertIsNone(cited(self.snapshot, 2, "event", event_index=5))
        self.assertIsNone(cited(self.snapshot, 2, "event"))  # no index
        self.assertIsNone(cited(self.snapshot, 4, "event", event_index=0))  # span with no events

    def test_events_are_picked_by_their_citable_index(self):
        events = [
            {"name": "first", "time": 1_763_000_000_001_000_000, "attributes": {"k": "alpha"}},
            {"name": "second", "time": 1_763_000_000_002_000_000, "attributes": {"k": "beta"}},
        ]
        snapshot = snapshot_of(span(1, operation_type="run", events=events))
        self.assertIn("alpha", cited(snapshot, 1, "event", event_index=0))
        self.assertIn("beta", cited(snapshot, 1, "event", event_index=1))
        self.assertNotIn("alpha", cited(snapshot, 1, "event", event_index=1))

    def test_a_long_payload_is_its_head_and_tail_only(self):
        value = cited(self.snapshot, 6, "output_payload")
        self.assertTrue(value.startswith("H" * 800))
        self.assertTrue(value.endswith("T" * 400))
        self.assertIn("5000 chars omitted", value)
        self.assertNotIn("M", value)


if __name__ == "__main__":
    unittest.main()
