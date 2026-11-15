from contextlib import asynccontextmanager

from fastapi import FastAPI
from agent_debugger_api.traces.repository import LocalMemoryRepository

from agent_debugger_api.api.router import api_router
from agent_debugger_api.ingest.kafka_publisher import KafkaSpanPublisher
from agent_debugger_api.ingest.settings import get_ingest_settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    # The producer connects lazily on the first durable batch; close it if it did.
    await app.state.span_publisher.close()


app = FastAPI(
    title="AI Agent Debugger API",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(api_router, prefix="/api/v1")
# Local memory is an explicit runtime profile, not a substitute for Kafka/ClickHouse.
app.state.trace_repository = LocalMemoryRepository()
# Durable path (protocol "1"): POST /api/v1/traces -> Kafka.
_ingest = get_ingest_settings()
app.state.span_publisher = KafkaSpanPublisher(
    _ingest.kafka_bootstrap_servers, _ingest.kafka_trace_topic, timeout_s=_ingest.kafka_publish_timeout_s
)

@app.middleware("http")
async def uncached_telemetry(request, call_next):
    response = await call_next(request)
    if request.url.path.startswith("/api/v1/local/"):
        response.headers["Cache-Control"] = "no-store"
    return response
