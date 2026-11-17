"""Structured output of the investigator model (`docs/proposals/investigator.md` §5).

This is shape only. Whether a cited span, event, field or quote exists is the
grounding step's job (`grounding.py`), not the schema's.
"""

from __future__ import annotations

import json
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StrictInt, StrictStr, ValidationError, model_validator

SCHEMA_VERSION = 1
MAX_FINDINGS = 5
MAX_EVIDENCE = 6

SpanId = Annotated[StrictStr, Field(pattern=r"^[0-9a-f]{16}$")]
HashPrefix = Annotated[StrictStr, Field(pattern=r"^[0-9a-f]{12}$")]
Limitation = Annotated[StrictStr, Field(min_length=1, max_length=300)]

Verdict = Literal["findings", "no_issue_found", "insufficient_evidence"]
Category = Literal[
    "tool_failure",
    "timeout",
    "retry_exhausted",
    "recovered_retry",
    "model_or_api_error",
    "output_contradicts_evidence",
    "unsupported_output",
    "control_flow_anomaly",
    "incomplete_run",
    "telemetry_incomplete",
    "other",
]
ClaimType = Literal["observed_failure", "suspected_origin", "recovered_failure", "inconsistency", "completeness"]
Priority = Literal["HIGH", "MEDIUM", "LOW"]
EvidenceField = Literal[
    "status_code",
    "status_description",
    "error_type",
    "span_name",
    "attempt",
    "retry_of_span_id",
    "attribute",
    "event",
    "input_payload",
    "output_payload",
    "error_payload",
]
PAYLOAD_FIELDS = frozenset({"input_payload", "output_payload", "error_payload"})


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class EvidenceRef(_Strict):
    span_id: SpanId
    content_hash: HashPrefix | None = None  # required when the span is conflicted (R2)
    field: EvidenceField
    key: StrictStr | None = None  # attribute key, when field = "attribute"
    event_index: Annotated[StrictInt, Field(ge=0)] | None = None  # when field = "event"
    quote: Annotated[StrictStr, Field(max_length=200)] | None = None  # exact substring of the cited value


class Relation(_Strict):
    kind: Literal["parent_of", "retry_of", "link"]
    from_span_id: SpanId
    to_span_id: SpanId


class CandidateFinding(_Strict):
    category: Category
    claim_type: ClaimType
    suspicious_span_id: SpanId | None = None
    priority: Priority  # a proposal; grounding may lower it
    explanation: Annotated[StrictStr, Field(min_length=1, max_length=600)]
    evidence: Annotated[tuple[EvidenceRef, ...], Field(min_length=1, max_length=MAX_EVIDENCE)]
    relations: Annotated[tuple[Relation, ...], Field(max_length=4)] = ()
    limitations: Annotated[tuple[Limitation, ...], Field(max_length=3)] = ()


class InvestigatorOutput(_Strict):
    schema_version: Literal[1]
    verdict: Verdict
    findings: Annotated[tuple[CandidateFinding, ...], Field(max_length=MAX_FINDINGS)] = ()
    limitations: Annotated[tuple[Limitation, ...], Field(max_length=5)] = ()

    @model_validator(mode="after")
    def _verdict_matches_findings(self) -> InvestigatorOutput:
        # §6.1: "findings" with an empty list, or another verdict with findings, is invalid output.
        if (self.verdict == "findings") != bool(self.findings):
            raise ValueError("verdict and findings disagree")
        return self


class InvalidOutput(Exception):
    """The provider's output is not JSON or does not match the schema.

    The message names the problem's kind only; it never repeats the output.
    """


def parse_output(raw: dict | str) -> InvestigatorOutput:
    """Validate a provider response: a parsed object, or text that must be one JSON object."""
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except ValueError:
            raise InvalidOutput("not_json") from None
    if not isinstance(raw, dict):
        raise InvalidOutput("not_an_object")
    try:
        return InvestigatorOutput.model_validate(raw)
    except ValidationError:
        raise InvalidOutput("schema_mismatch") from None


def output_json_schema() -> dict:
    """JSON Schema handed to the provider with every request."""
    return InvestigatorOutput.model_json_schema()
