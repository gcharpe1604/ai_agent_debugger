"""Durable ingest: POST /api/v1/traces, protocol "1" (clickhouse-span-record.md §8.3).

202 means every span is acked by Kafka (in the ingestion buffer), not that
ClickHouse has stored it (trace-protocol.md §12.3). 503 means at least one span
was not acked; the client should retry the whole batch.

No authentication yet (handoff action 6): `project_id` comes from
resolve_project_id(). The local profile's loopback/origin/header gating and
payload rejection are deliberately not used here.
"""

from __future__ import annotations

import time

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from agent_debugger_api.contracts import PublishError, SpanPublisher
from agent_debugger_api.ingest.schemas import TraceBatch, to_span_record
from agent_debugger_api.ingest.settings import resolve_project_id

router = APIRouter(tags=["durable telemetry"])

MAX_BODY = 4 * 1024 * 1024  # 4 MiB: payloads are allowed here, unlike local-1's 256 KiB


def get_span_publisher(request: Request) -> SpanPublisher:
    return request.app.state.span_publisher


def _invalid(exc: ValidationError) -> JSONResponse:
    # Field locations and messages only: never echo submitted values (payloads, secrets).
    errors = [{"loc": list(e["loc"]), "msg": e["msg"], "type": e["type"]} for e in exc.errors()]
    return JSONResponse(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, content={"detail": errors})


@router.post("/traces", status_code=status.HTTP_202_ACCEPTED)
async def ingest_traces(request: Request, publisher: SpanPublisher = Depends(get_span_publisher)):
    if request.headers.get("content-type", "").split(";")[0].strip() != "application/json":
        raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, "JSON required")
    body = bytearray()
    async for chunk in request.stream():
        if len(body) + len(chunk) > MAX_BODY:
            raise HTTPException(status.HTTP_413_CONTENT_TOO_LARGE, "Batch exceeds 4 MiB")
        body.extend(chunk)

    try:
        batch = TraceBatch.model_validate_json(body)
    except ValidationError as exc:
        return _invalid(exc)

    project_id = resolve_project_id()
    received_at = time.time_ns()  # once per envelope (§8.2)
    try:
        records = [to_span_record(span, project_id, received_at) for span in batch.spans]
    except ValidationError as exc:
        return _invalid(exc)

    try:
        await publisher.publish(records)
    except PublishError:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Trace buffer unavailable; batch not accepted. Retry the whole batch.",
            headers={"Retry-After": "1"},
        ) from None
    return {"status": "accepted", "protocol_version": "1", "spans": len(records)}
