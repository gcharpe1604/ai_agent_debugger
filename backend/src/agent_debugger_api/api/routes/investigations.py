"""Investigation API over the durable trace store.

    POST /api/v1/projects/{project}/runs/{trace_id}/investigations         run one attempt now
    GET  /api/v1/projects/{project}/runs/{trace_id}/investigations/latest  the newest attempt
    GET  /api/v1/projects/{project}/investigator                           the configured provider

The attempt runs synchronously in a worker thread (a Bedrock call can take up to
the provider's read timeout) and the response is the stored attempt. The provider
comes from INVESTIGATOR_PROVIDER (default "scripted"), created on first use.

Attempts live in an in-memory store on `app.state`: lost on restart, one process
only. PostgreSQL `analysis_attempts` / `findings` / `finding_evidence` are not
built yet (handoff action 8).

Never returned: the snapshot JSON, provider error text, credentials. A finding's
evidence carries the cited value as it was in the analyzed snapshot, which is what
grounding checked the quote against.

No authentication yet (handoff action 6); same `local` project rule as the read API.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.concurrency import run_in_threadpool

from agent_debugger_api.api.routes.durable_runs import _read, get_trace_store, project_id
from agent_debugger_api.contracts import TraceRead, TraceStore
from agent_debugger_api.contracts.span_record import TraceId
from agent_debugger_api.investigator import grounding
from agent_debugger_api.investigator.attempts import AnalysisAttempt, AttemptStore, InMemoryAttemptStore
from agent_debugger_api.investigator.engine import Investigator
from agent_debugger_api.investigator.factory import provider_from_env
from agent_debugger_api.investigator.provider import InvestigatorProvider
from agent_debugger_api.investigator.snapshot import Snapshot

router = APIRouter(tags=["investigations"])

PROVIDER_KINDS = {"stub-scripted": "scripted", "bedrock": "bedrock"}


def get_attempt_store(request: Request) -> AttemptStore:
    state = request.app.state
    if not hasattr(state, "attempt_store"):
        state.attempt_store = InMemoryAttemptStore()
    return state.attempt_store


def get_investigator_provider(request: Request) -> InvestigatorProvider:
    state = request.app.state
    if not hasattr(state, "investigator_provider"):
        try:
            state.investigator_provider = provider_from_env()
        except ValueError:
            # The setting's value is not echoed: it could be anything an operator typed.
            raise HTTPException(
                status.HTTP_503_SERVICE_UNAVAILABLE,
                "Investigator provider is not configured. Check INVESTIGATOR_PROVIDER, and for bedrock "
                "BEDROCK_MODEL_ID and AWS_REGION.",
            ) from None
    return state.investigator_provider


class _OneTrace:
    """Hands the engine the trace this request already read, so the store is read once
    and a store failure is a 503 before any attempt exists."""

    def __init__(self, trace: TraceRead) -> None:
        self._trace = trace

    def get_trace(self, project_id, trace_id):
        return self._trace


def _ns(value: int | None) -> str | None:
    return None if value is None else str(value)


def _evidence(snapshot: Snapshot | None, ref) -> dict[str, Any]:
    item = ref.model_dump()
    cited = None
    if snapshot is not None:
        span = grounding.version_for(snapshot, ref)
        cited = grounding.cited_value(span, ref) if span is not None else None
    item["cited_value"] = cited
    return item


def provider_view(name: str, model_id: str, region: str | None) -> dict[str, Any]:
    return {"kind": PROVIDER_KINDS.get(name, name), "name": name, "model_id": model_id, "region": region}


def attempt_view(attempt: AnalysisAttempt) -> dict[str, Any]:
    snapshot = Snapshot.model_validate_json(attempt.snapshot_json) if attempt.snapshot_json else None
    return {
        "attempt_id": str(attempt.attempt_id),
        "project": "local",
        "trace_id": attempt.trace_id,
        "status": attempt.status,
        "outcome": attempt.outcome,
        "failure_code": attempt.failure_code,
        "failure_detail": attempt.failure_detail,
        "provider": provider_view(attempt.provider_name, attempt.model_id, attempt.provider_region),
        "prompt_version": attempt.prompt_version,
        "snapshot_hash": attempt.snapshot_hash,
        "candidate_count": attempt.candidate_count,
        "findings": [
            {
                **finding.model_dump(exclude={"evidence"}),
                "evidence": [_evidence(snapshot, ref) for ref in finding.evidence],
            }
            for finding in attempt.findings
        ],
        "rejected": [
            {"candidate_index": entry.candidate_index, "code": entry.code} for entry in attempt.grounding_report if not entry.kept
        ],
        "adjustments": [
            {"candidate_index": entry.candidate_index, "code": entry.code} for entry in attempt.grounding_report if entry.kept
        ],
        "limitations": list(attempt.limitations),
        "has_failure_findings": attempt.has_failure_findings,
        "provider_calls": attempt.provider_calls,
        "input_tokens": attempt.input_tokens,
        "output_tokens": attempt.output_tokens,
        "latency_ms": attempt.latency_ms,
        "created_at": _ns(attempt.created_at),
        "started_at": _ns(attempt.started_at),
        "finished_at": _ns(attempt.finished_at),
    }


@router.post("/projects/{project}/runs/{trace_id}/investigations", status_code=status.HTTP_201_CREATED)
async def create_investigation(
    project: str,
    trace_id: TraceId,
    store: TraceStore = Depends(get_trace_store),
    attempts: AttemptStore = Depends(get_attempt_store),
    provider: InvestigatorProvider = Depends(get_investigator_provider),
):
    pid = project_id(project)
    trace = await _read(store.get_trace, pid, trace_id)
    if trace is None or not trace.spans:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Trace not found")
    engine = Investigator(_OneTrace(trace), provider, attempts)
    attempt = await run_in_threadpool(engine.investigate, pid, trace_id)
    return attempt_view(attempt)


@router.get("/projects/{project}/runs/{trace_id}/investigations/latest")
def latest_investigation(project: str, trace_id: TraceId, attempts: AttemptStore = Depends(get_attempt_store)):
    found = attempts.list_for_trace(project_id(project), trace_id)
    if not found:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No investigation for this trace")
    return attempt_view(found[-1])


@router.get("/projects/{project}/investigator")
def investigator(project: str, provider: InvestigatorProvider = Depends(get_investigator_provider)):
    project_id(project)
    return provider_view(provider.name, provider.model_id, getattr(provider, "region", None))
