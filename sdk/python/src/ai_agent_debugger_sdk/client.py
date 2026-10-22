from collections.abc import Iterator
from contextlib import contextmanager

from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import ConsoleSpanExporter, SimpleSpanProcessor
from opentelemetry.trace import Tracer

from ai_agent_debugger_sdk.capture import CaptureConfig
from ai_agent_debugger_sdk.span import SpanHandle


class Debugger:
    def __init__(
        self,
        service_name: str,
        *,
        capture: CaptureConfig | None = None,
        tracer_provider: trace.TracerProvider | None = None,
    ) -> None:
        self._capture = capture if capture is not None else CaptureConfig()
        if type(self._capture) is not CaptureConfig:
            raise TypeError("capture must be a CaptureConfig")
        provider = (
            tracer_provider
            if tracer_provider is not None
            else trace.get_tracer_provider()
        )
        if tracer_provider is None and isinstance(provider, trace.ProxyTracerProvider):
            resource = Resource.create({"service.name": service_name})
            provider = TracerProvider(resource=resource)
            provider.add_span_processor(SimpleSpanProcessor(ConsoleSpanExporter()))
        # Host-owned providers retain their resource, processors and lifecycle.
        # Never register/replace the global provider or shut down a supplied one.
        self._provider = provider
        self._tracer: Tracer = self._provider.get_tracer("ai_agent_debugger_sdk")

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
            yield SpanHandle(span, self._capture)

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
