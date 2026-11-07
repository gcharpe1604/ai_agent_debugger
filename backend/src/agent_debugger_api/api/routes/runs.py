from fastapi import APIRouter, Request, HTTPException
from agent_debugger_api.api.routes.ingestion import local_repository
from agent_debugger_api.traces.schemas import TraceId, SpanId
from agent_debugger_api.traces.service import run_summary
from agent_debugger_api.traces.repository import TTL_SECONDS

router = APIRouter(tags=["local telemetry"])

@router.get("/local/status")
def status(request: Request):
    local_repository(request)
    return {"mode": "local", "storage": "temporary process memory", "ttl_seconds": TTL_SECONDS, "production_ingestion": False,
            "workspace": {"id": "local", "name": "Local captures", "initial": "L", "environment": "SDK telemetry · memory storage", "dataSource": "local"}}

@router.get("/local/runs")
def runs(request: Request):
    repository = local_repository(request)
    return {"mode": "local", "runs": [run_summary(trace_id, spans) for trace_id, spans in repository.read().items()]}

@router.get("/local/runs/{trace_id}")
def trace(request: Request, trace_id: TraceId):
    spans = local_repository(request).read(trace_id)
    return {"run": run_summary(trace_id, spans), "spans": list(spans.values())}

@router.get("/local/runs/{trace_id}/spans/{span_id}")
def span(request: Request, trace_id: TraceId, span_id: SpanId):
    spans = local_repository(request).read(trace_id)
    if span_id not in spans:
        raise HTTPException(404, "Captured span unavailable")
    selected = spans[span_id]
    return {"run": run_summary(trace_id, spans), "span": selected, "retry_of": spans.get(selected["attributes"].get("debugger.retry_of")), "retries": [item for item in spans.values() if item["attributes"].get("debugger.retry_of") == span_id]}
