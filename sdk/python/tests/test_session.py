import asyncio
import json

import pytest
from opentelemetry import trace
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from ai_agent_debugger_sdk import TraceSession


class RecordingExporter(InMemorySpanExporter):
    failures = 0
    exported_spans = 0

    def export(self, spans):
        self.exported_spans += len(spans)
        return super().export(spans)


@pytest.fixture
def captured(monkeypatch):
    exporter = RecordingExporter()
    monkeypatch.setattr("ai_agent_debugger_sdk.session.HttpSpanExporter", lambda endpoint: exporter)
    return exporter


def test_disabled_session_keeps_calls_and_global_provider_unchanged(monkeypatch):
    monkeypatch.delenv("AGENT_DEBUGGER_ENDPOINT", raising=False)
    provider = trace.get_tracer_provider()
    operation = lambda value: value + 1
    with TraceSession("unit") as session:
        assert session.wrap_callable(operation, "tool", "operation") is operation
        assert operation(4) == 5
    assert trace.get_tracer_provider() is provider


def test_local_session_defaults_to_loopback_and_records_controlled_mode(captured, monkeypatch):
    monkeypatch.delenv("AGENT_DEBUGGER_ENDPOINT", raising=False)
    with TraceSession.local("example", execution_mode="controlled") as session:
        assert session.endpoint == "http://127.0.0.1:8008/api/v1/local/traces"
    root = captured.get_finished_spans()[0]
    assert root.attributes["debugger.execution.mode"] == "controlled"


def test_local_session_respects_endpoint_override_and_explicit_disable(captured, monkeypatch):
    monkeypatch.setenv("AGENT_DEBUGGER_ENDPOINT", "http://localhost:8008/api/v1/local/traces")
    assert TraceSession.local("example").endpoint.startswith("http://localhost:")
    monkeypatch.setenv("AGENT_DEBUGGER_ENDPOINT", "")
    with TraceSession.local("example") as session:
        assert session.tracer is None
    assert not captured.get_finished_spans()


def test_actual_nested_call_parentage_and_sanitized_failures(captured):
    provider = trace.get_tracer_provider()
    with pytest.raises(ValueError, match="private-value"):
        with TraceSession("unit", endpoint="local", local_dependencies=True) as session:
            def failing():
                raise ValueError("private-value")
            with session.operation("agent", "agent.run"):
                session.wrap_callable(failing, "model", "model.plan")()
    spans = {span.name: span for span in captured.get_finished_spans()}
    assert spans["model.plan"].parent.span_id == spans["agent.run"].context.span_id
    assert spans["agent.run"].parent.span_id == spans["unit"].context.span_id
    assert len({span.context.trace_id for span in spans.values()}) == 1
    assert all(span.status.status_code.name == "ERROR" for span in spans.values())
    assert "private-value" not in json.dumps([dict(event.attributes) for span in spans.values() for event in span.events])
    assert trace.get_tracer_provider() is provider


def test_async_calls_and_http_error_status_are_recorded(captured):
    class Response:
        status_code = 429
    async def post():
        return Response()
    with TraceSession("async-unit", endpoint="local") as session:
        response = asyncio.run(session.wrap_callable(post, "api", "POST chat/completions")())
        assert response.status_code == 429
    span = next(span for span in captured.get_finished_spans() if span.name.startswith("POST"))
    assert span.attributes["http.response.status_code"] == 429
    assert span.status.status_code.name == "ERROR"


def test_retry_links_use_explicit_application_step_and_attempt(captured):
    def invoke(*, step_id, attempt):
        if attempt == 1:
            raise TimeoutError("not exported")
        return 42
    with TraceSession("retry-unit", endpoint="local") as session:
        wrapped = session.wrap_callable(invoke, "tool", "invoke")
        with pytest.raises(TimeoutError):
            wrapped(step_id="pay", attempt=1)
        assert wrapped(step_id="pay", attempt=2) == 42
    spans = [span for span in captured.get_finished_spans() if span.attributes["debugger.operation.type"] == "tool"]
    assert spans[1].attributes["debugger.retry_of"] == f"{spans[0].context.span_id:016x}"
    assert spans[0].status.status_code.name == "ERROR"
    assert spans[1].status.status_code.name == "OK"
