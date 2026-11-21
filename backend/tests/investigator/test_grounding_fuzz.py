"""Grounding on random schema-valid output: it never raises, never changes its inputs,
and every candidate ends either kept (a finding) or rejected with exactly one code.

Seeded, so a failure is reproducible: the subtest names the snapshot and the seed.
"""

import random
import typing
import unittest

from agent_debugger_api.investigator import grounding
from agent_debugger_api.investigator.schema import (
    Category,
    ClaimType,
    EvidenceField,
    InvestigatorOutput,
    Priority,
)
from tests.investigator.factories import failed_tool_trace, retry_trace, snapshot_of

SEEDS = range(150)
CATEGORIES = typing.get_args(Category)
CLAIMS = typing.get_args(ClaimType)
FIELDS = typing.get_args(EvidenceField)
PRIORITIES = typing.get_args(Priority)
REJECTION_CODES = set(typing.get_args(grounding.RejectionCode))
FABRICATED = ("0123456789abcdef", "ffffffffffffffff")


def snapshots():
    return {
        "failed_tool": snapshot_of(*failed_tool_trace()),
        "failed_tool_metadata_only": snapshot_of(*failed_tool_trace(payloads=False)),
        "recovered_retry": snapshot_of(*retry_trace("ERROR", "OK")),
        "exhausted_retry": snapshot_of(*retry_trace("ERROR", "ERROR", "ERROR")),
    }


def random_quote(rng, span, field):
    """Often a real substring of the cited value, sometimes junk, sometimes none."""
    roll = rng.random()
    if roll < 0.3:
        return None
    if roll < 0.8:
        value = grounding.cited_value(span, _probe(span, field)) or ""
        if value:
            start = rng.randrange(len(value))
            return value[start : start + rng.randint(1, 40)][:200]
    return rng.choice(["", "x", "ERROR", "[redacted]", "…[3 chars omitted]…", "quantity 0"])


def _probe(span, field):
    from agent_debugger_api.investigator.schema import EvidenceRef

    key = next(iter(span.attributes), None) if field == "attribute" else None
    return EvidenceRef(span_id=span.span_id, field=field, key=key, event_index=0 if field == "event" else None)


def random_ref(rng, snapshot):
    span = rng.choice(snapshot.spans)
    span_id = span.span_id if rng.random() < 0.9 else rng.choice(FABRICATED)
    field = rng.choice(FIELDS)
    ref = {"span_id": span_id, "field": field}
    if field == "attribute":
        ref["key"] = rng.choice([*span.attributes, "no.such.key"]) if span.attributes else "no.such.key"
    if field == "event":
        ref["event_index"] = rng.randint(0, 3)
    if rng.random() < 0.2:
        ref["content_hash"] = rng.choice(["0" * 12, "abcdefabcdef"])
    quote = random_quote(rng, span, field)
    if quote is not None:
        ref["quote"] = quote
    return ref


def random_candidate(rng, snapshot):
    ids = [span.span_id for span in snapshot.spans] + list(FABRICATED)
    evidence = [random_ref(rng, snapshot) for _ in range(rng.randint(1, 4))]
    candidate = {
        "category": rng.choice(CATEGORIES),
        "claim_type": rng.choice(CLAIMS),
        "priority": rng.choice(PRIORITIES),
        "explanation": "random candidate",
        "evidence": evidence,
        "relations": [
            {"kind": rng.choice(["parent_of", "retry_of", "link"]), "from_span_id": rng.choice(ids), "to_span_id": rng.choice(ids)}
            for _ in range(rng.randint(0, 2))
        ],
        "limitations": ["random"] if rng.random() < 0.5 else [],
    }
    if rng.random() < 0.8:
        candidate["suspicious_span_id"] = rng.choice([ref["span_id"] for ref in evidence] + ids)
    return candidate


def random_output(rng, snapshot):
    findings = [random_candidate(rng, snapshot) for _ in range(rng.randint(0, 5))]
    verdict = "findings" if findings else rng.choice(["no_issue_found", "insufficient_evidence"])
    return InvestigatorOutput.model_validate(
        {"schema_version": 1, "verdict": verdict, "findings": findings, "limitations": []}
    )


class GroundingFuzzTests(unittest.TestCase):
    def test_random_output_is_kept_or_rejected_with_a_code_and_inputs_are_unchanged(self):
        kept_total = rejected_total = 0
        for name, snapshot in snapshots().items():
            for seed in SEEDS:
                with self.subTest(snapshot=name, seed=seed):
                    rng = random.Random(seed)
                    output = random_output(rng, snapshot)
                    snapshot_before = snapshot.model_dump()
                    output_before = output.model_dump()

                    result = grounding.ground(snapshot, output)

                    self.assertEqual(snapshot.model_dump(), snapshot_before)
                    self.assertEqual(output.model_dump(), output_before)
                    self.assertEqual(grounding.ground(snapshot, output), result)  # deterministic

                    kept = {finding.candidate_index for finding in result.findings}
                    rejected = [entry for entry in result.report if not entry.kept]
                    rejected_indexes = [entry.candidate_index for entry in rejected]
                    self.assertEqual(len(rejected_indexes), len(set(rejected_indexes)))  # one code each
                    self.assertEqual(kept | set(rejected_indexes), set(range(len(output.findings))))
                    self.assertFalse(kept & set(rejected_indexes))
                    for entry in rejected:
                        self.assertIn(entry.code, REJECTION_CODES | {"duplicate"})

                    rendered = {span.span_id for span in snapshot.spans}
                    for finding in result.findings:
                        self.assertTrue({ref.span_id for ref in finding.evidence} <= rendered)
                    kept_total += len(kept)
                    rejected_total += len(rejected)
        # The generator must exercise both paths, or the test proves little.
        self.assertGreaterEqual(kept_total, 10)  # 14 with these seeds
        self.assertGreaterEqual(rejected_total, 200)


if __name__ == "__main__":
    unittest.main()
