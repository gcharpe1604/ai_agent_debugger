from fastapi import APIRouter

from agent_debugger_api.api.routes import durable_runs, health, ingestion, runs, traces

api_router = APIRouter()

api_router.include_router(health.router)
api_router.include_router(ingestion.router)
api_router.include_router(runs.router)
api_router.include_router(traces.router)
api_router.include_router(durable_runs.router)
