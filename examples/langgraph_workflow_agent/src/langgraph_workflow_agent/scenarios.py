import json
import re
from pathlib import Path
from typing import Annotated, Literal

from pydantic import Field, StringConstraints, model_validator

from .agent import ROUTED_NODES, WorkflowAgent
from .dependencies import LocalDependencies
from .models import Context, Destination, Model, Request, Response

DATA_DIR = Path(__file__).resolve().parent / "data" / "scenarios"


def read_json(path: Path):
    def unique_keys(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"Duplicate JSON key: {key}")
            result[key] = value
        return result

    def reject_constant(value):
        raise ValueError(f"Invalid JSON constant: {value}")

    return json.loads(
        path.read_text(encoding="utf-8"),
        object_pairs_hook=unique_keys,
        parse_constant=reject_constant,
    )


class RouteOverride(Model):
    source: Literal["classify", "evaluate"]
    attempt: int | None = Field(default=None, ge=1, le=6)
    destination: Destination

    @model_validator(mode="after")
    def valid_edge(self):
        allowed = {
            "classify": {"gather_context", "evaluate", "__end__"},
            "evaluate": {"retry_context", "execute_action", "abort", "__end__"},
        }
        if self.destination not in allowed[self.source]:
            raise ValueError("Destination is not an allowed edge for source")
        if self.source == "classify" and self.attempt not in {None, 1}:
            raise ValueError("classify executes once")
        return self


class ContextOverride(Model):
    attempt: int = Field(ge=1, le=6)
    response: Context


class NodeOverride(Model):
    node: Literal["execute_action"]
    drop_update: Literal["action_result"]


class RuntimeScenario(Model):
    schema_version: int = Field(ge=1, le=1)
    scenario_id: Annotated[str, StringConstraints(pattern=r"^LG-\d{2}$")]
    request: Request
    route_overrides: list[RouteOverride] = Field(default_factory=list)
    context_overrides: list[ContextOverride] = Field(default_factory=list)
    node_overrides: list[NodeOverride] = Field(default_factory=list)
    response_override: Response | None = None

    @model_validator(mode="after")
    def unique_overrides(self):
        for field, key in (
            (self.context_overrides, lambda item: item.attempt),
            (self.node_overrides, lambda item: item.node),
            (self.route_overrides, lambda item: (item.source, item.attempt)),
        ):
            keys = [key(item) for item in field]
            if len(keys) != len(set(keys)):
                raise ValueError("Duplicate override target")
        for source in ("classify", "evaluate"):
            matches = [item for item in self.route_overrides if item.source == source]
            if len(matches) > 1 and any(item.attempt is None for item in matches):
                raise ValueError("Overlapping wildcard and attempt overrides")
        return self


def load_scenario(scenario_id: str) -> RuntimeScenario:
    if not re.fullmatch(r"LG-\d{2}", scenario_id):
        raise ValueError("Expected scenario ID such as LG-01")
    scenario = RuntimeScenario.model_validate(
        read_json(DATA_DIR / f"{scenario_id}.json")
    )
    if scenario.scenario_id != scenario_id:
        raise ValueError("Scenario filename and ID disagree")
    return scenario


class PreparedDependencies(LocalDependencies):
    def __init__(self, *, routes, contexts, response):
        self.routes = routes
        self.contexts = {item.attempt: item.response for item in contexts}
        self.response = response

    def route(self, source, state, proposed):
        for override in self.routes:
            if override.source == source and override.attempt in {
                None,
                state["retry_count"] + 1,
            }:
                return override.destination
        return super().route(source, state, proposed)

    def gather(self, request, *, attempt):
        if attempt in self.contexts:
            return self.contexts[attempt].model_copy(deep=True)
        return super().gather(request, attempt=attempt)

    def respond(self, state):
        if self.response is not None:
            return self.response.model_copy(deep=True)
        return super().respond(state)


def build_agent(config: RuntimeScenario, *, tracing=None) -> WorkflowAgent:
    prepared = RuntimeScenario.model_validate(config.model_dump())
    dependencies = PreparedDependencies(
        routes=prepared.route_overrides,
        contexts=prepared.context_overrides,
        response=prepared.response_override,
    )
    if prepared.node_overrides:

        def lose_action_update(node):
            def invoke(state):
                update = node(state)
                update["action_result"] = None
                return update

            return invoke

        nodes = {"execute_action": lose_action_update}
    else:
        nodes = None
    if tracing is not None:
        # Compose with scenario fault wrappers; capture actual graph execution.
        overrides = nodes or {}
        names = ("classify", "gather_context", "evaluate", "retry_context", "execute_action", "abort", "validate", "respond")
        def wrap_node(name):
            def wrap(function):
                if name in overrides:
                    function = overrides[name](function)
                return tracing.wrap_callable(function, "custom", "node." + name)
            return wrap
        nodes = {name: wrap_node(name) for name in names}
        routers = traced_routers(tracing)
    else:
        routers = None
    return WorkflowAgent(dependencies, nodes=nodes, routers=routers)


def traced_routers(tracing):
    """Record each conditional-edge decision as its own span, e.g. route.evaluate."""
    return {
        source: (
            lambda function, source=source: tracing.wrap_callable(
                function, "custom", "route." + source
            )
        )
        for source in ROUTED_NODES
    }
