from fastapi import APIRouter

from agent_debugger_api.api.routes import durable_runs, health, ingestion, investigations, runs, traces

api_router = APIRouter()

api_router.include_router(health.router)
api_router.include_router(ingestion.router)
api_router.include_router(runs.router)
api_router.include_router(traces.router)
api_router.include_router(durable_runs.router)
api_router.include_router(investigations.router)
