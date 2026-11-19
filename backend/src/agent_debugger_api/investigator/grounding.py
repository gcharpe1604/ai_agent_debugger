"""Deterministic grounding (`docs/proposals/investigator.md` §6). NOT IMPLEMENTED.

The user writes this module (handoff §12: grounding validation is a core
piece). What is here: the result types the engine stores, the function
signatures, and the rules each function must apply. No tests exist for it yet.
The test list is proposal §9, tests 19 to 37, one per rule:

  19 R1  fabricated span ID in evidence, as suspicious_span_id, as a relation
         endpoint, a real ID from another trace, the ID of a collapsed span
  20 R2  conflicted span cited without a hash, with a wrong hash, with the right one
  21 R3  event_index out of range
  22 R4  attribute key not on the span
  23 R5  payload with state unavailable; empty error_type; a redacted payload
         quoted outside its markers (kept); a quote containing "[redacted]"
  24 R6  quote differing by one character; quote from the omitted middle
  25 R7  retry_of relation between unrelated spans
  26 R8  suspect with no evidence on itself
  27 R9  observed_failure citing only OK spans
  28 R10 inconsistency on a metadata-only snapshot; with two payload quotes on
         two spans (kept)
  29 R11 suspected_origin without a relation to a failing span, or without a limitation
  30 A1  HIGH tool_failure on attempt 1 of a recovered group -> recovered_failure, LOW
  31 A1  does not fire for an exhausted group
  32 A2/A3 suspected_origin HIGH -> MEDIUM; observed_failure on a non-originating
         error HIGH -> MEDIUM
  33 A4  duplicate (suspect, category) -> one finding
  34     one bad candidate does not affect a good one in the same output
  35     all candidates rejected -> insufficient_evidence, zero findings, codes recorded
  36     no_issue_found on a metadata-only snapshot carries PAYLOAD_LIMITATION
  37     pure: same inputs, same result; the snapshot is not changed

Contract
- Input: the snapshot and the parsed output. Nothing else. No ClickHouse read,
  no provider call, no clock. The snapshot is the only source of truth for the
  attempt (`analysis-engine.md` §9.1).
- Pure: the same inputs give the same result, and neither input is changed
  (both are frozen pydantic models).
- A candidate that fails a reject rule is dropped whole. A grounded finding
  never contains a reference that was not checked.
- Grounding does not prove the explanation is right or that the cited step
  caused the outcome (§6.5).

Where the data is
- `snapshot.spans`: rendered spans. `snapshot.versions(span_id)` returns one
  entry, several for a conflicted span (each with a 12-hex `content_hash`), or
  () for an unknown or collapsed span.
- `span.events[i].index`: the citable event position.
- `span.input` / `.output` / `.error`: `PayloadView(state, excerpt, full_length)`.
  The excerpt is the cited value of a payload field. It is None when the state
  is `disabled` or `unavailable`, or when a reduction dropped it. A long
  payload is rendered as head + "…[N chars omitted]…" + tail, so text from the
  omitted middle is not in the excerpt.
- `snapshot.facts.originating_error_span_ids`, `snapshot.facts.retry_groups`
  (`snapshot.retry_group_of(span_id)`), `snapshot.completeness`.
- Parent index: `span.parent_span_id`. Retry edge: `span.retry_of_span_id`.
  Links: `span.links`.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Literal

from pydantic import BaseModel, ConfigDict

from .schema import (
    PAYLOAD_FIELDS,
    CandidateFinding,
    Category,
    ClaimType,
    EvidenceRef,
    InvestigatorOutput,
    Priority,
    Relation,
)
from .snapshot import Snapshot, SnapshotSpan

RejectionCode = Literal[
    "unknown_span",  # R1
    "ambiguous_version",  # R2
    "unknown_event",  # R3
    "unknown_field",  # R4
    "field_not_recorded",  # R5
    "quote_mismatch",  # R6
    "unknown_relationship",  # R7
    "unsupported_suspect",  # R8
    "no_failure_evidence",  # R9
    "insufficient_evidence",  # R10
    "unsupported_suspicion",  # R11
]
AdjustmentCode = Literal[
    "clamped_recovered_retry",  # A1
    "clamped_suspicion",  # A2
    "clamped_priority",  # A3
    "duplicate",  # A4
]
Outcome = Literal["findings", "no_issue_found", "insufficient_evidence"]

# §6.4: added to the attempt when the model found no issue and no input or
# output payload was captured.
PAYLOAD_LIMITATION = "payloads were not captured; semantic checks were not possible"


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class GroundedFinding(_Model):
    """A candidate that passed R1 to R11, after A1 to A3."""

    candidate_index: int  # position in InvestigatorOutput.findings
    category: Category
    claim_type: ClaimType
    suspicious_span_id: str | None = None
    priority: Priority
    explanation: str
    evidence: tuple[EvidenceRef, ...]
    relations: tuple[Relation, ...] = ()
    limitations: tuple[str, ...] = ()


class GroundingReportEntry(_Model):
    """One rejection or adjustment. Kept for evaluation; never shown as a finding."""

    candidate_index: int
    code: RejectionCode | AdjustmentCode
    kept: bool  # False for R1 to R11 and for A4 (duplicate); True for A1 to A3


class GroundingResult(_Model):
    findings: tuple[GroundedFinding, ...]
    report: tuple[GroundingReportEntry, ...]
    outcome: Outcome  # §6.4
    limitations: tuple[str, ...] = ()  # attempt-level, e.g. PAYLOAD_LIMITATION
    # False when there is no finding, or every finding is a recovered_failure (A1).
    has_failure_findings: bool


_PAYLOAD_ATTR = {"input_payload": "input", "output_payload": "output", "error_payload": "error"}
_SPAN_ATTR = {
    "status_description": "status_description",
    "error_type": "error_type",
    "span_name": "name",
    "retry_of_span_id": "retry_of_span_id",
}


def cited_value(span: SnapshotSpan, ref: EvidenceRef) -> str | None:
    """The text `ref` points at on `span`, as the snapshot renders it; None when not recorded.

    Per `ref.field`:
    - status_code, status_description, error_type, span_name, attempt,
      retry_of_span_id: the span's value as text. Empty or None means "not
      recorded" and returns None.
    - attribute: `span.attributes[ref.key]`. The caller checks R4 (key present)
      first.
    - event: the event at `ref.event_index`. The caller checks R3 first. Decide
      and document what text a quote is matched against (for example the
      event's name and attribute values).
    - input_payload, output_payload, error_payload: the payload view's
      `excerpt`. None when the state is not captured, truncated or redacted, or
      when the excerpt was dropped by a reduction.

    Used by R5 (recorded at all) and R6 (quote is an exact substring).
    """
    field = ref.field
    value: object | None
    if field == "attribute":
        value = span.attributes.get(ref.key) if ref.key is not None else None
    elif field == "event":
        event = next((e for e in span.events if e.index == ref.event_index), None)
        value = None if event is None else "\n".join([event.name, *event.attributes.values()])
    elif field in PAYLOAD_FIELDS:
        value = getattr(span, _PAYLOAD_ATTR[field]).excerpt
    elif field == "status_code":
        value = span.status_code.value
    elif field == "attempt":
        value = span.attempt
    else:
        value = getattr(span, _SPAN_ATTR[field])
    if value is None or value == "":
        return None
    return str(value)


def _span_ids(candidate: CandidateFinding) -> set[str]:
    ids = {ref.span_id for ref in candidate.evidence}
    for rel in candidate.relations:
        ids.update((rel.from_span_id, rel.to_span_id))
    if candidate.suspicious_span_id is not None:
        ids.add(candidate.suspicious_span_id)
    return ids


def version_for(snapshot: Snapshot, ref: EvidenceRef) -> SnapshotSpan | None:
    """The rendered version `ref` cites: the only one, or for a conflicted span the one with its hash.

    None when the span is not rendered, or is conflicted and `ref.content_hash` matches no version.
    """
    versions = snapshot.versions(ref.span_id)
    if len(versions) == 1:
        return versions[0]
    return next((v for v in versions if ref.content_hash is not None and v.content_hash == ref.content_hash), None)


def _cited(snapshot: Snapshot, candidate: CandidateFinding) -> list[tuple[EvidenceRef, SnapshotSpan | None]]:
    return [(ref, version_for(snapshot, ref)) for ref in candidate.evidence]


# Reject rules. Each returns True when the candidate satisfies the rule; `_RULES` is the order they run in.


def _r1_rendered_spans(snapshot: Snapshot, candidate: CandidateFinding) -> bool:
    return all(snapshot.versions(span_id) for span_id in _span_ids(candidate))


def _r2_one_version(snapshot: Snapshot, candidate: CandidateFinding) -> bool:
    return all(version is not None for _, version in _cited(snapshot, candidate))


def _r3_event_exists(snapshot: Snapshot, candidate: CandidateFinding) -> bool:
    return all(
        version is not None and any(event.index == ref.event_index for event in version.events)
        for ref, version in _cited(snapshot, candidate)
        if ref.field == "event"
    )


def _r4_attribute_exists(snapshot: Snapshot, candidate: CandidateFinding) -> bool:
    return all(
        version is not None and ref.key is not None and ref.key in version.attributes
        for ref, version in _cited(snapshot, candidate)
        if ref.field == "attribute"
    )


_RULES: tuple[tuple[RejectionCode, Callable[[Snapshot, CandidateFinding], bool]], ...] = (
    ("unknown_span", _r1_rendered_spans),
    ("ambiguous_version", _r2_one_version),
    ("unknown_event", _r3_event_exists),
    ("unknown_field", _r4_attribute_exists),
)


def reject_code(snapshot: Snapshot, candidate: CandidateFinding) -> RejectionCode | None:
    """First failing reject rule for one candidate, or None when it passes all (§6.2).

    The rules run in this order and the first failure wins:

    R1  unknown_span          every evidence span_id, the suspicious_span_id and
                              every relation endpoint is a rendered span of this
                              snapshot. A collapsed span is not rendered. An ID
                              from another trace is not in this snapshot.
    R2  ambiguous_version     an evidence ref on a conflicted span gives a
                              content_hash that matches one rendered version.
    R3  unknown_event         field = "event": event_index exists on that span.
    R4  unknown_field         field = "attribute": key exists on that span.
    R5  field_not_recorded    the cited field has a value (`cited_value` is not
                              None). A quote that contains "[redacted]" cites a
                              value that was not recorded (D7); the rest of a
                              redacted payload is readable.
    R6  quote_mismatch        quote, when given, is an exact substring of the
                              cited value. One different character fails. Text
                              from the omitted middle of a long payload fails.
    R7  unknown_relationship  parent_of: `to` has `from` as parent_span_id.
                              retry_of: `from` has retry_of_span_id = `to`.
                              link: `from` has a link to `to`.
    R8  unsupported_suspect   suspicious_span_id, when given, has at least one
                              evidence ref on that same span.
    R9  no_failure_evidence   observed_failure: at least one evidence ref points
                              at status_code of an ERROR span, or at an event
                              named "exception".
    R10 insufficient_evidence inconsistency: at least two evidence refs on two
                              different spans, each with a quote from a payload
                              field. On a metadata-only snapshot this can never
                              pass, which is the backstop for abstention.
    R11 unsupported_suspicion suspected_origin: `relations` connect the suspect
                              to a span that satisfies R9's condition, and
                              `limitations` is not empty. The tests read
                              "connect" as an undirected path over the given
                              relations (two siblings are connected through
                              their parent by two parent_of relations).
    """
    for code, satisfied in _RULES:
        if not satisfied(snapshot, candidate):
            return code
    return None


def adjust(snapshot: Snapshot, candidate_index: int, candidate: CandidateFinding) -> tuple[GroundedFinding, tuple[AdjustmentCode, ...]]:
    """Apply A1 to A3 to a candidate that passed `reject_code` (§6.3).

    A1  clamped_recovered_retry  the suspect, or any ERROR span in the evidence,
                                 belongs to a retry group with outcome
                                 "recovered", and no evidence points at an ERROR
                                 span outside a recovered group: claim_type
                                 becomes recovered_failure, category
                                 recovered_retry, priority LOW. A recovered
                                 retry is not a failure. Does not fire for an
                                 "exhausted" group.
    A2  clamped_suspicion        suspected_origin: priority at most MEDIUM.
    A3  clamped_priority         HIGH is kept only for an observed_failure whose
                                 suspect is an originating error outside a
                                 recovered group, or for an inconsistency (it
                                 passed R10). Any other HIGH becomes MEDIUM.

    Returns the finding and the codes of the adjustments that changed it, in
    rule order. A rule that changes nothing reports no code.
    """
    raise NotImplementedError("grounding is written by the user: see the module docstring")


def ground(snapshot: Snapshot, output: InvestigatorOutput) -> GroundingResult:
    """Ground every candidate of `output` against `snapshot` (§6.2 to §6.4).

    For each candidate, in order: `reject_code`; a rejected candidate adds a
    report entry (kept=False) and nothing else. A passing candidate goes
    through `adjust`; each adjustment adds a report entry (kept=True).
    A4: a second finding with the same (suspicious_span_id, category) as an
    earlier grounded one is dropped with code "duplicate" (kept=False). The
    comparison uses the values after A1 to A3.

    One bad candidate never affects another candidate.

    Outcome (§6.4):
    - "findings": at least one grounded finding.
    - "no_issue_found": the model returned it. When
      `snapshot.completeness.payloads_captured` is False, add
      PAYLOAD_LIMITATION to `limitations`.
    - "insufficient_evidence": the model returned it, or the model returned
      findings and every one was rejected.

    The model's own `output.limitations` are carried into `limitations`.
    `has_failure_findings` is False when no finding remains or all of them are
    recovered_failure.

    Not this function's job: provider errors, invalid output and unknown traces
    (§6.1) are handled by the engine before grounding is called.
    """
    raise NotImplementedError("grounding is written by the user: see the module docstring")
