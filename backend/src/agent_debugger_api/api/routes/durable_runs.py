"""Durable read API: runs, one reconstructed run, one span, read from ClickHouse.

    GET /api/v1/projects
    GET /api/v1/projects/{project}/runs
    GET /api/v1/projects/{project}/runs/{trace_id}
    GET /api/v1/projects/{project}/runs/{trace_id}/spans/{span_id}

Separate from the local profile (`/api/v1/local/*`): no loopback, origin or
header gating here, and no in-memory repository.

Every route needs a session (auth/deps.py current_user; 401 without one). A
user has one project, `default` in URLs, which maps to the user's project_id;
ClickHouse is never queried with the string `default`. Any other project is
404, and so is another project's run or span: it is not found in the user's.

The store is synchronous, so every call goes through run_in_threadpool. A
store failure is 503: the API never answers with empty or sample data instead.
"""

from __future__ import annotations

import re
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.concurrency import run_in_threadpool

from agent_debugger_api.auth.deps import current_user
from agent_debugger_api.contracts import TraceStore
from agent_debugger_api.contracts.span_record import SpanId, TraceId
from agent_debugger_api.db.models import User
from agent_debugger_api.traces.read_store import TraceStoreUnavailable
from agent_debugger_api.traces.read_views import (
    run_from_summary,
    run_from_tree,
    span_reference,
    span_version,
    tree_view,
)
from agent_debugger_api.traces.reconstruction import reconstruct

router = APIRouter(tags=["durable read"])

PROJECT = "default"
MAX_NANOS = 2**63 - 1
MAX_PAGE = 200
_CURSOR = re.compile(r"^(\d{1,19}):([0-9a-f]{32})$")


def get_trace_store(request: Request) -> TraceStore:
    return request.app.state.trace_store


def project_id(project: str, user: User = Depends(current_user)) -> UUID:
    if project != PROJECT:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Project not found")
    return user.project_id


async def _read(call, *args):
    try:
        return await run_in_threadpool(call, *args)
    except TraceStoreUnavailable:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Trace store unavailable; nothing was read. Retry later.",
            headers={"Retry-After": "1"},
        ) from None


async def _tree(store: TraceStore, project: UUID, trace_id: str):
    trace = await _read(store.get_trace, project, trace_id)
    if trace is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Trace not found")
    return trace, reconstruct(trace)


@router.get("/projects")
def projects(user: User = Depends(current_user)):
    return [{"id": PROJECT, "name": user.name}]


@router.get("/projects/{project}/runs")
async def list_runs(
    project: UUID = Depends(project_id),
    started_from: int = Query(0, ge=0, le=MAX_NANOS, description="Unix ns, inclusive"),
    started_to: int = Query(MAX_NANOS, ge=0, le=MAX_NANOS, description="Unix ns, exclusive"),
    limit: int = Query(50, ge=1, le=MAX_PAGE),
    cursor: str | None = Query(None, description="next_cursor of the previous page"),
    store: TraceStore = Depends(get_trace_store),
):
    before = None
    if cursor is not None:
        match = _CURSOR.match(cursor)
        if not match or int(match[1]) > MAX_NANOS:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Invalid cursor")
        before = (int(match[1]), match[2])
    # One extra row tells whether another page exists without a second query.
    runs = await _read(store.list_runs, project, started_from, started_to, limit + 1, before)
    page = runs[:limit]
    more = len(runs) > limit
    return {
        "project": PROJECT,
        "runs": [run_from_summary(run) for run in page],
        "next_cursor": f"{page[-1].run_started_at}:{page[-1].trace_id}" if more else None,
    }


@router.get("/projects/{project}/runs/{trace_id}")
async def get_run(
    trace_id: TraceId,
    project: UUID = Depends(project_id),
    store: TraceStore = Depends(get_trace_store),
):
    trace, tree = await _tree(store, project, trace_id)
    return {
        "run": run_from_tree(trace_id, tree),
        "tree": tree_view(tree),
        # Every stored version, without payload text (read one span for that).
        "spans": [span_version(v, payloads=False) for node in tree.nodes for v in node.versions],
    }


@router.get("/projects/{project}/runs/{trace_id}/spans/{span_id}")
async def get_span(
    trace_id: TraceId,
    span_id: SpanId,
    project: UUID = Depends(project_id),
    store: TraceStore = Depends(get_trace_store),
):
    _, tree = await _tree(store, project, trace_id)
    by_id = {n.span_id: n for n in tree.nodes}
    node = by_id.get(span_id)
    if node is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Span not found")
    retry_of = by_id.get(node.placement.record.retry_of_span_id)
    return {
        "run": run_from_tree(trace_id, tree),
        "span_id": span_id,
        "parent_span_id": node.parent_span_id,
        "recorded_parent_span_id": node.recorded_parent_span_id,
        "flags": list(node.flags),
        "conflicted": len(node.versions) > 1,
        # A conflicted span has more than one version; none of them is "the" span.
        "versions": [span_version(v, payloads=True) for v in node.versions],
        "retry_of": span_reference(retry_of) if retry_of else None,
        "retries": [
            span_reference(n) for n in tree.nodes if n.placement.record.retry_of_span_id == span_id
        ],
    }
