"""Analysis attempt record and its store port (`docs/proposals/investigator.md` §2, §6.1, §6.4).

In memory only for now. PostgreSQL (`analysis_attempts`, `findings`,
`finding_evidence`) comes with handoff action 6; the fields follow
`database.md` §4.3 to §4.5 plus the additions listed in the proposal's C7.
"""

from __future__ import annotations

from typing import Literal, Protocol, runtime_checkable
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from .grounding import GroundedFinding, GroundingReportEntry, Outcome

AttemptStatus = Literal["pending", "running", "completed", "failed"]
FailureCode = Literal[
    "trace_not_found",  # unknown trace or zero spans; no provider call
    "input_too_large",  # over a snapshot limit after every reduction; no provider call
    "provider_error",  # the investigator's provider failed; never a finding
    "invalid_output",  # not JSON, wrong shape, or verdict and findings disagree
    "internal_error",  # snapshot build or grounding raised; nothing ungrounded is kept
]

# pending -> running -> completed | failed; pending -> failed when no snapshot can be built.
_NEXT: dict[str, frozenset[str]] = {
    "pending": frozenset({"running", "failed"}),
    "running": frozenset({"completed", "failed"}),
    "completed": frozenset(),
    "failed": frozenset(),
}
_IDENTITY = ("attempt_id", "project_id", "trace_id", "mode", "created_at")
_SNAPSHOT = ("snapshot_json", "snapshot_hash")


class AnalysisAttempt(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    attempt_id: UUID
    project_id: UUID
    trace_id: str
    mode: Literal["direct"] = "direct"  # bounded read-only mode is out of the MVP (C1)
    status: AttemptStatus = "pending"
    outcome: Outcome | None = None  # set when completed
    failure_code: FailureCode | None = None  # set when failed
    # A code-like detail: the provider error kind, the reductions tried, or the
    # step that raised. Never provider text and never model output.
    failure_detail: str = ""

    # The exact evidence sent to the provider. Fixed once the attempt is running.
    snapshot_json: str | None = None
    snapshot_hash: str | None = None

    # Investigator configuration identity (database.md §4.3).
    provider_name: str
    model_id: str
    provider_region: str | None = None  # e.g. the AWS region; None for a stub. Never a credential.
    prompt_version: str
    provider_calls: int = 0
    input_tokens: int | None = None
    output_tokens: int | None = None
    latency_ms: int | None = None

    candidate_count: int = 0  # findings the model proposed, before grounding
    findings: tuple[GroundedFinding, ...] = ()
    grounding_report: tuple[GroundingReportEntry, ...] = ()
    limitations: tuple[str, ...] = ()
    has_failure_findings: bool = False

    created_at: int  # ns
    started_at: int | None = None
    finished_at: int | None = None


class IllegalTransition(Exception):
    pass


@runtime_checkable
class AttemptStore(Protocol):
    def create(self, attempt: AnalysisAttempt) -> None:
        """Store a new pending attempt."""
        ...

    def update(self, attempt: AnalysisAttempt) -> None:
        """Replace an attempt. Raises IllegalTransition for a status change the lifecycle does not allow."""
        ...

    def get(self, attempt_id: UUID) -> AnalysisAttempt | None: ...

    def list_for_trace(self, project_id: UUID, trace_id: str) -> list[AnalysisAttempt]:
        """Attempts of one trace, oldest first."""
        ...


class InMemoryAttemptStore:
    """Enforces the lifecycle so a test fails where a real store would reject the write."""

    def __init__(self) -> None:
        self._attempts: dict[UUID, AnalysisAttempt] = {}
        self.history: list[tuple[UUID, str]] = []  # (attempt_id, status) per write

    def create(self, attempt: AnalysisAttempt) -> None:
        if attempt.attempt_id in self._attempts:
            raise IllegalTransition("attempt already exists")
        if attempt.status != "pending":
            raise IllegalTransition("a new attempt must be pending")
        self._write(attempt)

    def update(self, attempt: AnalysisAttempt) -> None:
        current = self._attempts.get(attempt.attempt_id)
        if current is None:
            raise IllegalTransition("unknown attempt")
        if attempt.status not in _NEXT[current.status]:
            raise IllegalTransition(f"{current.status} -> {attempt.status}")
        if any(getattr(attempt, name) != getattr(current, name) for name in _IDENTITY):
            raise IllegalTransition("identity fields cannot change")
        if current.status == "running" and any(getattr(attempt, name) != getattr(current, name) for name in _SNAPSHOT):
            raise IllegalTransition("the snapshot is fixed once the attempt is running")
        if attempt.status == "running" and attempt.snapshot_json is None:
            raise IllegalTransition("a running attempt needs its snapshot")
        if attempt.status == "failed" and (attempt.findings or attempt.failure_code is None):
            raise IllegalTransition("a failed attempt has a failure code and no findings")
        if attempt.status == "completed" and attempt.outcome is None:
            raise IllegalTransition("a completed attempt has an outcome")
        self._write(attempt)

    def _write(self, attempt: AnalysisAttempt) -> None:
        self._attempts[attempt.attempt_id] = attempt  # frozen, so safe to share
        self.history.append((attempt.attempt_id, attempt.status))

    def get(self, attempt_id: UUID) -> AnalysisAttempt | None:
        return self._attempts.get(attempt_id)

    def list_for_trace(self, project_id: UUID, trace_id: str) -> list[AnalysisAttempt]:
        return sorted(
            (a for a in self._attempts.values() if a.project_id == project_id and a.trace_id == trace_id),
            # Stable sort: attempts created in the same clock tick keep their creation order
            # (a random attempt_id is no tie-break for "latest").
            key=lambda attempt: attempt.created_at,
        )
