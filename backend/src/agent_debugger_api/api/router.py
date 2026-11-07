from fastapi import APIRouter

from agent_debugger_api.api.routes import health, ingestion, runs

api_router = APIRouter()

api_router.include_router(health.router)
api_router.include_router(ingestion.router)
api_router.include_router(runs.router)
