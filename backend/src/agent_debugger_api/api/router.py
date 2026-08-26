from fastapi import APIRouter

from agent_debugger_api.api.routes import health

api_router = APIRouter()

api_router.include_router(health.router)