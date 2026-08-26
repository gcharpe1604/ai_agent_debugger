from fastapi import FastAPI

from agent_debugger_api.api.router import api_router

app = FastAPI(
    title="AI Agent Debugger API",
    version="0.1.0",
)

app.include_router(api_router, prefix="/api/v1")