import asyncio
import importlib.util
import json
from contextlib import contextmanager
from pathlib import Path

import ai_agent_debugger_sdk
import ai_agent_debugger_sdk.client as client
import pytest
from ai_agent_debugger_sdk import Debugger
from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.trace import Status, StatusCode


@pytest.fixture
def local(monkeypatch):
    sink = InMemorySpanExporter()
    monkeypatch.setattr(client, "ConsoleSpanExporter", lambda: sink)
    debugger = Debugger("sdk-tests")
    yield debugger, sink
    debugger._provider.shutdown()


@contextmanager
def configured(**options):
    sink = InMemorySpanExporter()
    provider = TracerProvider(
        resource=Resource({"service.name": "host", "host.id": "test-host"})
    )
    provider.add_span_processor(SimpleSpanProcessor(sink))
    try:
        yield Debugger("sdk-tests", tracer_provider=provider, **options), sink, provider
    finally:
        provider.shutdown()


def named(sink):
    return {span.name: span for span in sink.get_finished_spans()}


def test_import_is_from_this_repository():
    source = Path(__file__).resolve().parents[1] / "src"
    assert Path(ai_agent_debugger_sdk.__file__).resolve().is_relative_to(source)


def test_operation_types_parentage_and_capture(local):
    debugger, sink = local
    with debugger.run("run"):
        with debugger.agent("agent"):
            for kind in ("model", "tool", "retrieval"):
                with getattr(debugger, kind)(kind) as handle:
                    handle.set_input({"question": "hello"})
                    handle.set_output({"answer": True})
                    handle.set_attribute("attempt", 1)
    spans = named(sink)
    assert len(spans) == 5
    assert len({span.context.trace_id for span in spans.values()}) == 1
    assert spans["run"].parent is None
    assert spans["agent"].parent.span_id == spans["run"].context.span_id
    for kind in ("model", "tool", "retrieval"):
        span = spans[kind]
        assert span.parent.span_id == spans["agent"].context.span_id
        assert span.attributes["debugger.operation.type"] == kind
        assert json.loads(span.attributes["debugger.input"]) == {"question": "hello"}
        assert json.loads(span.attributes["debugger.output"]) == {"answer": True}
        assert span.attributes["attempt"] == 1


def test_nested_runs_inherit_context_and_sequential_runs_are_independent(local):
    debugger, sink = local
    with debugger.run("outer"):
        with debugger.run("inner"):
            pass
    with debugger.run("next"):
        pass
    spans = named(sink)
    assert spans["inner"].parent.span_id == spans["outer"].context.span_id
    assert spans["inner"].context.trace_id == spans["outer"].context.trace_id
    assert spans["next"].parent is None
    assert spans["next"].context.trace_id != spans["outer"].context.trace_id
    assert not trace.get_current_span().is_recording()


def test_async_tasks_keep_their_own_span_context(local):
    debugger, sink = local

    async def worker(name):
        with debugger.agent(name):
            await asyncio.sleep(0)
            with debugger.tool(name + "-tool"):
                await asyncio.sleep(0)

    async def run():
        with debugger.run("run"):
            await asyncio.gather(worker("a"), worker("b"))

    asyncio.run(run())
    spans = named(sink)
    for name in ("a", "b"):
        assert spans[name].parent.span_id == spans["run"].context.span_id
        assert spans[name + "-tool"].parent.span_id == spans[name].context.span_id
    assert len({span.context.trace_id for span in spans.values()}) == 1
    assert not trace.get_current_span().is_recording()


def test_user_exception_propagates_unchanged_and_is_recorded_once(local):
    debugger, sink = local
    error = ValueError("synthetic agent failure")
    with pytest.raises(ValueError) as caught:
        with debugger.tool("tool"):
            raise error
    assert caught.value is error
    span = named(sink)["tool"]
    assert span.status.status_code is StatusCode.ERROR
    assert [event.name for event in span.events] == ["exception"]


def test_recovered_child_failure_does_not_fail_parent(local):
    debugger, sink = local
    with debugger.run("run"):
        try:
            with debugger.tool("child"):
                raise ValueError("synthetic child failure")
        except ValueError:
            pass
    spans = named(sink)
    assert spans["child"].status.status_code is StatusCode.ERROR
    assert spans["run"].status.status_code is StatusCode.UNSET
    assert spans["run"].events == ()


class Hostile:
    def __str__(self):
        raise AssertionError("Application __str__ must not be invoked")

    def __repr__(self):
        raise AssertionError("Application __repr__ must not be invoked")

    def __iter__(self):
        raise AssertionError("Application iteration must not be invoked")


class HostileDict(dict):
    def items(self):
        raise AssertionError("Subclass items must not be invoked")


@pytest.mark.parametrize(
    "value",
    [Hostile(), HostileDict(), b"binary", {1, 2}],
    ids=["object", "subclass", "bytes", "set"],
)
def test_unknown_objects_are_marked_without_running_application_methods(local, value):
    debugger, sink = local
    with debugger.tool("tool") as span:
        span.set_input(value)
    recorded = named(sink)["tool"]
    assert json.loads(recorded.attributes["debugger.input"]) == "[unsupported]"
    assert recorded.attributes["debugger.input.unsupported"] is True
    assert recorded.status.status_code is StatusCode.UNSET


def test_recursive_secret_fields_are_redacted_without_mutating_input(local):
    debugger, sink = local
    value = {
        "PASSWORD": "synthetic",
        "child": [
            {"api-key": "synthetic", "Authorization": Hostile(), "message": "visible"}
        ],
    }
    with debugger.tool("tool") as span:
        span.set_input(value)
        span.set_attribute("http.request.header.authorization", Hostile())
    recorded = named(sink)["tool"]
    assert json.loads(recorded.attributes["debugger.input"]) == {
        "PASSWORD": "[redacted]",
        "child": [
            {
                "api-key": "[redacted]",
                "Authorization": "[redacted]",
                "message": "visible",
            }
        ],
    }
    assert recorded.attributes["debugger.input.redacted"] is True
    assert recorded.attributes["http.request.header.authorization"] == "[redacted]"
    assert value["PASSWORD"] == "synthetic"


def test_capture_failure_does_not_mask_later_agent_exception(local, monkeypatch):
    debugger, sink = local
    error = ValueError("synthetic agent failure")

    def broken(*args, **kwargs):
        raise RuntimeError("synthetic capture failure")

    monkeypatch.setattr(json, "dumps", broken)
    with pytest.raises(ValueError) as caught:
        with debugger.tool("tool") as span:
            span.set_input({"question": "hello"})
            raise error
    assert caught.value is error
    recorded = named(sink)["tool"]
    assert "debugger.input" not in recorded.attributes
    assert recorded.attributes["debugger.input.capture_error"] is True
    assert recorded.status.status_code is StatusCode.ERROR


def test_circular_and_nonfinite_data_remains_valid_json(local):
    debugger, sink = local
    value = {"nan": float("nan"), "infinity": float("inf"), "tuple": (1, True)}
    value["cycle"] = value
    with debugger.tool("tool") as span:
        span.set_input(value)
    recorded = named(sink)["tool"]
    assert json.loads(recorded.attributes["debugger.input"]) == {
        "nan": "[unsupported]",
        "infinity": "[unsupported]",
        "tuple": [1, True],
        "cycle": "[circular]",
    }


def test_invalid_attributes_fail_open(local):
    debugger, sink = local
    with debugger.tool("tool") as span:
        span.set_attribute(Hostile(), Hostile())
        span.set_attribute("unknown", Hostile())
        span.set_attribute("nonfinite", float("nan"))
        span.set_output({"ok": True})
    recorded = named(sink)["tool"]
    assert "unknown" not in recorded.attributes
    assert "nonfinite" not in recorded.attributes
    assert json.loads(recorded.attributes["debugger.output"]) == {"ok": True}


def test_capture_controls_and_additional_secret_fields():
    from ai_agent_debugger_sdk import CaptureConfig

    capture = CaptureConfig(capture_inputs=False, secret_fields=("session_id",))
    with configured(capture=capture) as (debugger, sink, _):
        with debugger.tool("tool") as span:
            span.set_input(Hostile())
            span.set_output(
                {"session_id": "synthetic", "password": "synthetic", "ok": True}
            )
        recorded = named(sink)["tool"]
        assert "debugger.input" not in recorded.attributes
        assert recorded.attributes["debugger.input.disabled"] is True
        assert json.loads(recorded.attributes["debugger.output"]) == {
            "session_id": "[redacted]",
            "password": "[redacted]",
            "ok": True,
        }


def test_output_capture_can_be_disabled():
    from ai_agent_debugger_sdk import CaptureConfig

    with configured(capture=CaptureConfig(capture_outputs=False)) as (
        debugger,
        sink,
        _,
    ):
        with debugger.tool("tool") as span:
            span.set_output(Hostile())
        recorded = named(sink)["tool"]
        assert "debugger.output" not in recorded.attributes
        assert recorded.attributes["debugger.output.disabled"] is True


@pytest.mark.parametrize(
    "value",
    ["é" * 10000, ["x" * 1000] * 1000, 1 << 100000, "\ud800"],
    ids=["unicode", "wide", "huge-int", "surrogate"],
)
def test_serialized_size_is_bounded_and_json_decodable(value):
    from ai_agent_debugger_sdk import CaptureConfig

    with configured(capture=CaptureConfig(max_payload_bytes=64)) as (debugger, sink, _):
        with debugger.tool("tool") as span:
            span.set_input(value)
        text = named(sink)["tool"].attributes["debugger.input"]
        assert len(text.encode("utf-8")) <= 64
        json.loads(text)


def test_depth_and_node_limits_are_reported():
    from ai_agent_debugger_sdk import CaptureConfig

    with configured(capture=CaptureConfig(max_depth=1, max_nodes=4)) as (
        debugger,
        sink,
        _,
    ):
        with debugger.tool("deep") as span:
            span.set_input({"a": {"b": {"c": 1}}})
        with debugger.tool("wide") as span:
            span.set_input(list(range(10000)))
        for span in sink.get_finished_spans():
            assert span.attributes["debugger.input.truncated"] is True
            assert len(span.attributes["debugger.input"]) < 200


def test_supplied_host_provider_retains_resource_processors_events_and_status():
    global_provider = trace.get_tracer_provider()
    with configured() as (debugger, sink, provider):
        resource = provider.resource
        with provider.get_tracer("host").start_as_current_span("host"):
            with debugger.run("run"):
                trace.get_current_span().add_event("checkpoint", {"stage": 1})
                trace.get_current_span().set_status(Status(StatusCode.OK))
        spans = named(sink)
        assert spans["run"].resource is resource
        assert spans["run"].resource.attributes["host.id"] == "test-host"
        assert spans["run"].parent.span_id == spans["host"].context.span_id
        assert [event.name for event in spans["run"].events] == ["checkpoint"]
        assert spans["run"].status.status_code is StatusCode.OK
        with provider.get_tracer("host").start_as_current_span("still-active"):
            pass
        assert "still-active" in named(sink)
    assert trace.get_tracer_provider() is global_provider


def test_configured_global_provider_is_reused_without_console_processor(monkeypatch):
    sink = InMemorySpanExporter()
    provider = TracerProvider(resource=Resource({"service.name": "host"}))
    provider.add_span_processor(SimpleSpanProcessor(sink))
    monkeypatch.setattr(trace, "get_tracer_provider", lambda: provider)

    def forbidden():
        raise AssertionError("Host-owned provider must not get a console exporter")

    monkeypatch.setattr(client, "ConsoleSpanExporter", forbidden)
    try:
        debugger = Debugger("sdk-tests")
        with debugger.run("run"):
            pass
        assert named(sink)["run"].resource.attributes["service.name"] == "host"
    finally:
        provider.shutdown()


def test_depth_limit_also_bounds_wide_container_traversal():
    from ai_agent_debugger_sdk import CaptureConfig

    with configured(capture=CaptureConfig(max_depth=0, max_nodes=4)) as (
        debugger,
        sink,
        _,
    ):
        with debugger.tool("wide") as span:
            span.set_input(list(range(10000)))
        recorded = named(sink)["wide"]
        assert json.loads(recorded.attributes["debugger.input"]) == ["[truncated]"] * 3
        assert recorded.attributes["debugger.input.truncated"] is True


def test_demo_import_has_no_tracing_side_effects_and_main_still_works(monkeypatch):
    sink = InMemorySpanExporter()
    monkeypatch.setattr(client, "ConsoleSpanExporter", lambda: sink)
    demo_path = Path(__file__).resolve().parents[3] / "test_sdk.py"
    spec = importlib.util.spec_from_file_location("sdk_demo", demo_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert sink.get_finished_spans() == ()
    module.main()
    assert set(named(sink)) == {
        "refund-run",
        "refund-agent",
        "refund-policy-search",
        "get-order",
        "final-response",
    }


@pytest.mark.parametrize(
    "options",
    [
        {"max_payload_bytes": 0},
        {"max_payload_bytes": True},
        {"max_payload_bytes": 1_048_577},
        {"max_depth": -1},
        {"max_depth": 33},
        {"max_depth": 1.5},
        {"max_nodes": 0},
        {"max_nodes": 10_001},
        {"max_nodes": True},
        {"capture_inputs": 1},
        {"capture_outputs": "false"},
        {"secret_fields": ["field"]},
        {"secret_fields": (Hostile(),)},
    ],
    ids=[
        "zero-bytes",
        "bool-bytes",
        "large-bytes",
        "negative-depth",
        "large-depth",
        "float-depth",
        "zero-nodes",
        "large-nodes",
        "bool-nodes",
        "input-bool",
        "output-bool",
        "fields-list",
        "fields-object",
    ],
)
def test_invalid_capture_configuration_fails_explicitly(options):
    from ai_agent_debugger_sdk import CaptureConfig

    with pytest.raises(ValueError):
        CaptureConfig(**options)


def test_non_string_keys_and_subclass_values_are_not_coerced(local):
    debugger, sink = local
    value = {Hostile(): "hidden", 1: "hidden", "safe": 2}
    with debugger.tool("tool") as span:
        span.set_input(value)
    recorded = named(sink)["tool"]
    assert json.loads(recorded.attributes["debugger.input"]) == {"safe": 2}
    assert recorded.attributes["debugger.input.unsupported"] is True


def test_repeated_capture_clears_stale_markers_and_failed_replacement(
    local, monkeypatch
):
    debugger, sink = local
    with debugger.tool("tool") as span:
        span.set_input(Hostile())
        span.set_input({"ok": True})
    recorded = named(sink)["tool"]
    assert recorded.attributes["debugger.input.unsupported"] is False
    original = json.dumps
    with debugger.tool("failed-replacement") as span:
        span.set_input({"old": True})
        monkeypatch.setattr(
            json, "dumps", lambda *args, **kwargs: (_ for _ in ()).throw(ValueError())
        )
        span.set_input({"new": True})
        monkeypatch.setattr(json, "dumps", original)
    recorded = named(sink)["failed-replacement"]
    assert json.loads(recorded.attributes["debugger.input"]) == "[capture unavailable]"
    assert recorded.attributes["debugger.input.capture_error"] is True


def test_disabled_capture_cannot_be_bypassed_by_reserved_attribute(local):
    from ai_agent_debugger_sdk import CaptureConfig

    with configured(capture=CaptureConfig(capture_inputs=False)) as (debugger, sink, _):
        with debugger.tool("tool") as span:
            span.set_attribute("debugger.input", "synthetic")
        assert "debugger.input" not in named(sink)["tool"].attributes


def test_attribute_write_failure_does_not_mask_agent_code(local, monkeypatch):
    debugger, _ = local
    error = ValueError("synthetic agent failure")
    with pytest.raises(ValueError) as caught:
        with debugger.tool("tool") as span:

            def unavailable(*args, **kwargs):
                raise RuntimeError("synthetic attribute failure")

            monkeypatch.setattr(span._span, "set_attribute", unavailable)
            span.set_input({"ok": True})
            span.set_output({"ok": True})
            span.set_attribute("attempt", 1)
            raise error
    assert caught.value is error


def test_unrecovered_child_exception_marks_each_affected_span_once(local):
    debugger, sink = local
    error = RuntimeError("synthetic unrecovered failure")
    with pytest.raises(RuntimeError) as caught:
        with debugger.run("run"):
            with debugger.agent("agent"):
                with debugger.tool("tool"):
                    raise error
    assert caught.value is error
    for span in sink.get_finished_spans():
        assert span.status.status_code is StatusCode.ERROR
        assert [event.name for event in span.events] == ["exception"]
    assert len(sink.get_finished_spans()) == 3


@pytest.mark.parametrize(
    "key", ["X-API-Key", "refreshToken", "http.request.header.cookie", "private_key"]
)
def test_secret_aliases_redact_values_before_inspecting_them(local, key):
    debugger, sink = local
    with debugger.tool("tool") as span:
        span.set_output({key: Hostile()})
    recorded = named(sink)["tool"]
    assert json.loads(recorded.attributes["debugger.output"]) == {key: "[redacted]"}
    assert recorded.attributes["debugger.output.redacted"] is True


def test_reuse_of_container_is_not_mistaken_for_a_cycle(local):
    debugger, sink = local
    shared = {"number": 1}
    with debugger.tool("tool") as span:
        span.set_input([shared, shared])
    recorded = named(sink)["tool"]
    assert json.loads(recorded.attributes["debugger.input"]) == [
        {"number": 1},
        {"number": 1},
    ]
    assert recorded.attributes["debugger.input.truncated"] is False
