"""Evaluation-only schema; excluded from the runtime distribution."""

from pathlib import Path
from typing import Annotated, Any, Literal

from pydantic import Field, StringConstraints, model_validator

from tool_task_agent.models import Model, PositiveInt, StepId, Text, ToolName
from tool_task_agent.scenarios import read_json

Operation = Literal[
    "interpret_plan",
    "get_order",
    "get_stock",
    "reserve_inventory",
    "charge_payment",
    "create_shipment",
    "inspect_fulfillment",
    "validate_result",
    "validate_state",
    "generate_response",
    "resolve_arguments",
]
Step = Literal["plan", "order", "reserve", "pay", "ship", "inspect", "verify", "final"]
Category = Literal[
    "wrong_tool_selection",
    "incorrect_tool_arguments",
    "tool_failure",
    "tool_timeout",
    "malformed_tool_response",
    "retry_then_success",
    "retry_exhaustion",
    "required_step_skipped",
    "invalid_step_order",
    "inconsistent_intermediate_state",
    "final_output_inconsistent",
]


class Failure(Model):
    category: Category
    operation: Operation
    step_id: Step
    detection_operation: Operation | None
    detection_step: Step | None


class Retry(Model):
    max_attempts: int = Field(ge=3, le=3)
    step_id: StepId | None
    attempts: int = Field(ge=0, le=3)
    retries: int = Field(ge=0, le=2)
    recovered: bool

    @model_validator(mode="after")
    def consistent_counts(self):
        if self.step_id is None:
            if self.attempts or self.retries or self.recovered:
                raise ValueError(
                    "No retry episode requires zero counts and no recovery"
                )
        elif self.attempts < 2 or self.retries != self.attempts - 1:
            raise ValueError("Retries must equal attempts minus one")
        return self


class Facts(Model):
    available_stock: int = Field(ge=0)
    reserved_quantity: PositiveInt | None
    payment_amount_cents: PositiveInt | None
    shipment_quantity: PositiveInt | None
    final_quantity: PositiveInt | None


class GroundTruth(Model):
    schema_version: int = Field(ge=1, le=1)
    scenario_id: Annotated[str, StringConstraints(pattern=r"^TOOL-(0[1-9]|1[0-2])$")]
    expected_outcome: Literal["correct", "failure"]
    expected_status: Literal["completed", "failed"]
    expected_error_code: Text | None
    expected_failure: Failure | None
    expected_suspicious_steps: list[Step]
    important_operations: list[Operation] = Field(min_length=1)
    expected_tool_calls: list[ToolName] = Field(min_length=1)
    expected_retry_behaviour: Retry
    injected_fault: dict[str, Any]
    expected_facts: Facts
    expected_causal_explanation: Text

    @model_validator(mode="after")
    def consistent_labels(self):
        if (self.expected_status == "failed") != (self.expected_error_code is not None):
            raise ValueError("Terminal errors require failed status")
        if len(set(self.expected_suspicious_steps)) != len(
            self.expected_suspicious_steps
        ):
            raise ValueError("Suspicious steps must be unique")
        if self.expected_failure is None:
            if (
                self.injected_fault
                or self.expected_suspicious_steps
                or self.expected_outcome != "correct"
            ):
                raise ValueError("Healthy labels cannot describe a fault")
        else:
            failure = self.expected_failure
            if (
                not self.injected_fault
                or failure.step_id not in self.expected_suspicious_steps
            ):
                raise ValueError("Failure requires injection and suspicious origin")
            if failure.operation not in self.important_operations:
                raise ValueError("Failure origin must be an important operation")
            if (failure.detection_step is None) != (
                failure.detection_operation is None
            ):
                raise ValueError("Detection operation and step must be paired")
            if (
                failure.detection_step
                and failure.detection_step not in self.expected_suspicious_steps
            ):
                raise ValueError("Detection step must be suspicious")
            recovered = failure.category == "retry_then_success"
            if recovered != self.expected_retry_behaviour.recovered:
                raise ValueError("Recovery category and retry labels disagree")
            if (self.expected_outcome == "correct") != recovered:
                raise ValueError(
                    "Injected faults are correct outcomes only after recovery"
                )
        if self.expected_outcome == "correct" and self.expected_status != "completed":
            raise ValueError("Correct outcomes must complete")
        return self


def load_ground_truth(path: Path) -> GroundTruth:
    truth = GroundTruth.model_validate(read_json(path))
    if truth.scenario_id != path.stem:
        raise ValueError("Ground-truth filename and scenario_id disagree")
    return truth
