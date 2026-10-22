from fastapi import FastAPI
from agent_debugger_api.traces.repository import LocalMemoryRepository

from agent_debugger_api.api.router import api_router

app = FastAPI(
    title="AI Agent Debugger API",
    version="0.1.0",
)

app.include_router(api_router, prefix="/api/v1")
# Local memory is an explicit runtime profile, not a substitute for Kafka/ClickHouse.
app.state.trace_repository = LocalMemoryRepository()

@app.middleware("http")
async def uncached_telemetry(request, call_next):
    response = await call_next(request)
    if request.url.path.startswith("/api/v1/local/"):
        response.headers["Cache-Control"] = "no-store"
    return response
