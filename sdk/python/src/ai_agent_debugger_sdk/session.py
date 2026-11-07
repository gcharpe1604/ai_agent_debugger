"""Opt-in instrumentation of actual calls with a private, explicitly flushed provider."""
from contextlib import contextmanager
from functools import wraps
import inspect
import os
import sys
from urllib.parse import urlsplit

from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.trace import Status, StatusCode, format_span_id, format_trace_id

from .transport import HttpSpanExporter, LOCAL_ENDPOINT


class TraceSession:
    """A CLI-owned run; no global provider replacement or argument/payload capture.

    No endpoint means no instrumentation. HTTP errors remain telemetry and never
    replace the agent's result. This implementation exports only to local capture.
    """

    def __init__(self, service_name, *, model=None, provider=None, endpoint=None, local_dependencies=False, execution_mode="live"):
        self.endpoint = endpoint if endpoint is not None else os.environ.get("AGENT_DEBUGGER_ENDPOINT")
        self.service_name, self.model, self.provider_name = service_name, model, provider
        self.local_dependencies = local_dependencies
        self.execution_mode = execution_mode
        self.provider = self.exporter = self.tracer = self.root = None
        self.trace_id = None
        self._previous_attempts = {}

    @classmethod
    def local(cls, service_name, **kwargs):
        """Explicit local integration for example CLIs; an empty env value opts out.

        General TraceSession callers remain opt-in. No global provider is changed.
        """
        kwargs.setdefault("endpoint", os.environ.get("AGENT_DEBUGGER_ENDPOINT", LOCAL_ENDPOINT))
        return cls(service_name, **kwargs)

    def __enter__(self):
        if not self.endpoint:
            return self
        self.exporter = HttpSpanExporter(self.endpoint)
        self.provider = TracerProvider(resource=Resource.create({"service.name": self.service_name}))
        self.provider.add_span_processor(BatchSpanProcessor(self.exporter, max_queue_size=256, max_export_batch_size=64, schedule_delay_millis=1000))
        self.tracer = self.provider.get_tracer("ai_agent_debugger_sdk")
        self._root_context = self.operation("run", self.service_name)
        self.root = self._root_context.__enter__()
        self.trace_id = format_trace_id(self.root.get_span_context().trace_id)
        self.root.set_attribute("debugger.execution.mode", self.execution_mode)
        self.root.set_attribute("debugger.local_dependencies", self.local_dependencies)
        if self.model:
            self.root.set_attribute("debugger.model.name", self.model)
        if self.provider_name:
            self.root.set_attribute("debugger.model.provider", urlsplit(self.provider_name).hostname or "Not recorded")
        return self

    def __exit__(self, kind, error, traceback):
        if not self.provider:
            return False
        try:
            self._root_context.__exit__(kind, error, traceback)
            flushed = self.provider.force_flush(timeout_millis=10000)
            delivered = flushed and not self.exporter.failures
            print(f"Trace {self.trace_id}: {'exported' if delivered else 'delivery failed'} ({self.exporter.exported_spans} acknowledged spans)", file=sys.stderr)
        finally:
            self.provider.shutdown()
        return False

    @contextmanager
    def operation(self, kind, name, attributes=None):
        if not self.tracer:
            yield None
            return
        with self.tracer.start_as_current_span(name, record_exception=False, set_status_on_exception=False) as span:
            span.set_attribute("debugger.operation.type", kind)
            for key, value in (attributes or {}).items():
                span.set_attribute(key, value)
            try:
                yield span
            except BaseException as error:
                span.set_status(Status(StatusCode.ERROR))
                # Preserve failure type without exporting credentials, prompts or stacks.
                span.add_event("exception", {"exception.type": type(error).__name__, "exception.message": f"{type(error).__name__} during {name}"})
                raise
            else:
                if span.status.status_code == StatusCode.UNSET:
                    span.set_status(Status(StatusCode.OK))

    def record_result(self, result):
        if self.root is None:
            return
        status = getattr(result, "status", None)
        if isinstance(status, str):
            self.root.set_attribute("debugger.result.status", status)
            if status == "failed":
                self.root.set_status(Status(StatusCode.ERROR))
        if getattr(result, "execution_error", None):
            self.root.set_status(Status(StatusCode.ERROR))

    def wrap_callable(self, function, kind, name, *, stage_name=False):
        if not self.tracer:
            return function

        def attributes(kwargs):
            step, attempt = kwargs.get("step_id"), kwargs.get("attempt")
            if isinstance(step, str) and type(attempt) is int:
                return {"debugger.step": step, "debugger.attempt": attempt}
            return {}

        def begin(span, kwargs):
            if span is None:
                return
            step, attempt = kwargs.get("step_id"), kwargs.get("attempt")
            if kind == "tool" and isinstance(step, str) and type(attempt) is int:
                previous = self._previous_attempts.get(step)
                if attempt > 1 and previous is not None:
                    span.set_attribute("debugger.retry_of", previous)
                self._previous_attempts[step] = format_span_id(span.get_span_context().span_id)

        def finish(span, result):
            if span is not None and kind == "api":
                status = getattr(result, "status_code", None)
                if type(status) is int:
                    span.set_attribute("http.response.status_code", status)
                    if status >= 400:
                        span.set_status(Status(StatusCode.ERROR))

        def label(args, kwargs):
            if stage_name and args and isinstance(args[0], str):
                return "model." + args[0][:80]
            if kind == "tool" and "step_id" in kwargs:
                return f"{name} · {kwargs['step_id']} · attempt {kwargs.get('attempt', 1)}"
            return name

        if inspect.iscoroutinefunction(function):
            @wraps(function)
            async def asynchronous(*args, **kwargs):
                with self.operation(kind, label(args, kwargs), attributes(kwargs)) as span:
                    begin(span, kwargs)
                    result = await function(*args, **kwargs)
                    finish(span, result)
                    return result
            return asynchronous

        @wraps(function)
        def synchronous(*args, **kwargs):
            with self.operation(kind, label(args, kwargs), attributes(kwargs)) as span:
                begin(span, kwargs)
                result = function(*args, **kwargs)
                finish(span, result)
                return result
        return synchronous

    def instrument(self, instance, operations):
        """Wrap explicit methods on a caller-owned instance; never patch classes globally."""
        if self.tracer:
            for method, (kind, name) in operations.items():
                setattr(instance, method, self.wrap_callable(getattr(instance, method), kind, name, stage_name=method == "_request"))
        return instance
