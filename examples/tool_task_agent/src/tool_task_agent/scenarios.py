import json
import re
from functools import partial
from pathlib import Path
from typing import Annotated, Any, Literal

from pydantic import Field, StringConstraints, model_validator

from .agent import TaskAgent
from .controlled_model import ControlledModel
from .models import (
    MAX_ATTEMPTS,
    FinalResponse,
    Model,
    PositiveInt,
    StepId,
    Text,
    ToolCall,
)
from .tools import LocalTools, ToolError, ToolTimeout, TransientToolError

DATA_DIR = Path(__file__).resolve().parent / "data" / "scenarios"


class ToolFault(Model):
    step_id: StepId
    attempt: int = Field(ge=1, le=MAX_ATTEMPTS)
    effect: Literal[
        "permanent_error",
        "timeout",
        "transient_error",
        "replace_response",
        "corrupt_shipment",
    ]
    response: dict[str, Any] | None = None
    shipment_quantity: PositiveInt | None = None

    @model_validator(mode="after")
    def check_payload(self):
        if (self.effect == "replace_response") != (self.response is not None):
            raise ValueError("Only replace_response requires a response")
        if (self.effect == "corrupt_shipment") != (self.shipment_quantity is not None):
            raise ValueError("Only corrupt_shipment requires shipment_quantity")
        return self


class ScenarioConfig(Model):
    schema_version: int = Field(ge=1, le=1)
    scenario_id: Annotated[str, StringConstraints(pattern=r"^TOOL-\d{2}$")]
    request: Text
    plan_override: list[ToolCall] | None = Field(default=None, min_length=1)
    tool_faults: list[ToolFault] = Field(default_factory=list)
    response_override: FinalResponse | None = None

    @model_validator(mode="after")
    def check_overrides(self):
        # Validate request syntax even when a plan replacement is supplied.
        default_plan = ControlledModel().plan(self.request)
        plan = self.plan_override if self.plan_override is not None else default_plan
        calls = {call.step_id: call for call in plan}
        if len(calls) != len(plan):
            raise ValueError("Plan step IDs must be unique")
        overrides = {
            (fault.step_id, fault.attempt): fault for fault in self.tool_faults
        }
        if len(overrides) != len(self.tool_faults):
            raise ValueError("Duplicate tool fault step/attempt")
        for fault in self.tool_faults:
            if fault.step_id not in calls:
                raise ValueError("Fault targets a step absent from the plan")
            if (
                fault.effect == "corrupt_shipment"
                and calls[fault.step_id].tool != "create_shipment"
            ):
                raise ValueError("Shipment corruption requires create_shipment")
            for attempt in range(1, fault.attempt):
                prior = overrides.get((fault.step_id, attempt))
                if prior is None or prior.effect not in {"timeout", "transient_error"}:
                    raise ValueError(
                        "Later fault attempts require earlier retryable failures"
                    )
        return self


def read_json(path: Path) -> dict:
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


def load_scenario(scenario_id: str) -> ScenarioConfig:
    if not re.fullmatch(r"TOOL-\d{2}", scenario_id):
        raise ValueError("Expected a scenario ID such as TOOL-01")
    scenario = ScenarioConfig.model_validate(
        read_json(DATA_DIR / f"{scenario_id}.json")
    )
    if scenario.scenario_id != scenario_id:
        raise ValueError("Scenario filename and scenario_id disagree")
    return scenario


class PreparedTools(LocalTools):
    """Faults depend only on explicit per-run step and attempt coordinates."""

    def __init__(self, faults: list[ToolFault]):
        super().__init__()
        self.faults = {(fault.step_id, fault.attempt): fault for fault in faults}

    def invoke(self, tool: str, arguments: dict, *, step_id: str, attempt: int):
        fault = self.faults.get((step_id, attempt))
        if fault:
            if fault.effect == "permanent_error":
                raise ToolError(
                    "tool_failure", "Payment provider rejected the transaction"
                )
            if fault.effect == "timeout":
                raise ToolTimeout("Simulated deadline expired before service commit")
            if fault.effect == "transient_error":
                raise TransientToolError(
                    "temporarily_unavailable", "Service temporarily unavailable"
                )
        response = super().invoke(tool, arguments, step_id=step_id, attempt=attempt)
        if fault:
            if fault.effect == "replace_response":
                return fault.model_copy(deep=True).response
            if fault.effect == "corrupt_shipment":
                self.state.shipment.quantity = fault.shipment_quantity
        return response


def build_agent(scenario: ScenarioConfig) -> TaskAgent:
    # Copy configuration so caller mutation cannot alter an already built agent.
    prepared = scenario.model_copy(deep=True)
    return TaskAgent(
        ControlledModel(prepared.plan_override, prepared.response_override),
        partial(PreparedTools, prepared.tool_faults),
    )
