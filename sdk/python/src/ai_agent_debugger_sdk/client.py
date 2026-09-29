from contextlib import contextmanager
from collections.abc import Iterator

from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import (
    ConsoleSpanExporter,
    SimpleSpanProcessor
)
from opentelemetry.trace import Span, Tracer

from ai_agent_debugger_sdk.span import SpanHandle

class Debugger:
    def __init__(self, service_name: str) -> None:
        resource = Resource.create(
            {
                "service.name": service_name,
            }
        )

        self._provider = TracerProvider(resource=resource)
        self._provider.add_span_processor(
            SimpleSpanProcessor(ConsoleSpanExporter())
        )
        self._tracer: Tracer = self._provider.get_tracer(
            "ai_agent_debugger_sdk"
        )

    @contextmanager
    def _operation(
        self,
        name: str,
        operation_type: str,
    ) -> Iterator[SpanHandle]:
        with self._tracer.start_as_current_span(name) as span:
            span.set_attribute(
                "debugger.operation.type",
                operation_type,
            )
            yield SpanHandle(span)

    @contextmanager
    def run(self, name: str) -> Iterator[SpanHandle]:
        with self._operation(name, "run") as span:
            yield span

    @contextmanager
    def agent(self, name: str) -> Iterator[SpanHandle]:
        with self._operation(name, "agent") as span:
            yield span

    @contextmanager
    def model(self, name: str) -> Iterator[SpanHandle]:
        with self._operation(name, "model") as span:
            yield span

    @contextmanager
    def tool(self, name: str) -> Iterator[SpanHandle]:
        with self._operation(name, "tool") as span:
            yield span

    @contextmanager
    def retrieval(self, name: str) -> Iterator[SpanHandle]:
        with self._operation(name, "retrieval") as span:
            yield span