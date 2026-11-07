"""Explicit local ingestion; production Kafka acknowledgement is not implemented here."""
import ipaddress
import os
from fastapi import APIRouter, HTTPException, Request
from agent_debugger_api.traces.schemas import Batch

router = APIRouter(tags=["local telemetry"])
MAX_BODY = 256 * 1024

def local_repository(request: Request):
    if os.environ.get("AGENT_DEBUGGER_LOCAL_MODE") != "1":
        raise HTTPException(503, "Local capture is disabled. Authenticated Kafka ingestion is not configured.")
    try:
        allowed = request.client and ipaddress.ip_address(request.client.host).is_loopback
    except ValueError:
        allowed = False
    origin = request.headers.get("origin")
    if not allowed or request.url.hostname not in {"127.0.0.1", "localhost", "::1"} or (origin and origin not in {"http://127.0.0.1:5175", "http://localhost:5175", "http://127.0.0.1:4173", "http://localhost:4173"}):
        raise HTTPException(403, "Local capture is restricted to loopback clients and the local frontend")
    return request.app.state.trace_repository

@router.post("/local/traces")
async def ingest(request: Request):
    repository = local_repository(request)
    if request.headers.get("x-agent-debugger-local") != "1":
        raise HTTPException(403, "Explicit local exporter header required")
    if request.headers.get("content-type", "").split(";")[0] != "application/json":
        raise HTTPException(415, "JSON required")
    body = bytearray()
    async for chunk in request.stream():
        if len(body) + len(chunk) > MAX_BODY:
            raise HTTPException(413, "Batch exceeds 256 KiB")
        body.extend(chunk)
    try:
        batch = Batch.model_validate_json(body)
    except ValueError:
        raise HTTPException(422, "Invalid metadata-only local-1 batch") from None
    # The receipt explicitly states memory storage; it is not Kafka acceptance.
    return repository.ingest(batch)
