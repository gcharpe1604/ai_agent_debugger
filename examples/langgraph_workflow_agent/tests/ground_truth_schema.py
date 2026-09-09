from pathlib import Path
from typing import Annotated, Literal

from pydantic import Field, StringConstraints, model_validator

from langgraph_workflow_agent.models import (
    Action,
    ActionResult,
    Issue,
    Model,
    Node,
    Request,
    Status,
    Text,
)
from langgraph_workflow_agent.scenarios import read_json


class GroundTruth(Model):
    schema_version: int = Field(ge=1, le=1)
    scenario_id: Annotated[str, StringConstraints(pattern=r"^LG-\d{2}$")]
    request: Request
    injected_behavior: Text
    expected_outcome: Literal["correct", "failure"]
    failure_category: (
        Literal[
            "wrong_branch",
            "skipped_node",
            "stale_state",
            "lost_state_update",
            "incorrect_failure_transition",
            "retry_limit_ignored",
            "premature_termination",
            "response_state_contradiction",
        ]
        | None
    )
    expected_path: list[Node] = Field(min_length=1)
    expected_termination: Literal["end", "recursion_limit"]
    expected_status: Status
    ideal_status: Literal["resolved", "aborted"]
    expected_response_status: Literal["resolved", "aborted", "blocked"] | None
    expected_validation: list[Issue] | None
    expected_retries: int = Field(ge=0)
    expected_context_revision: int | None = Field(ge=1)
    expected_action: Action | None
    expected_action_result: ActionResult | None
    expected_suspicious_operations: list[Node]
    detection_operation: Node | Literal["langgraph.recursion_limit"] | None

    @model_validator(mode="after")
    def coherent(self):
        failure = self.expected_outcome == "failure"
        if failure != (self.failure_category is not None) or failure != bool(
            self.expected_suspicious_operations
        ):
            raise ValueError(
                "Only failures require a category and suspicious operations"
            )
        operations = self.expected_suspicious_operations
        if len(operations) != len(set(operations)):
            raise ValueError("Duplicate suspicious operation")
        if not set(operations) <= set(self.expected_path):
            raise ValueError("Suspicious operations must execute")
        if self.expected_path[0] != "classify":
            raise ValueError("Path must start at classify")
        if self.expected_retries > self.expected_path.count("retry_context"):
            raise ValueError("Retry count exceeds executed retry nodes")
        framework_error = self.expected_termination == "recursion_limit"
        if framework_error != (self.detection_operation == "langgraph.recursion_limit"):
            raise ValueError("Framework failure must identify recursion detection")
        if (
            self.detection_operation
            and not framework_error
            and self.detection_operation not in operations
        ):
            raise ValueError("Detection node must be suspicious and executed")
        if (self.expected_validation is not None) != ("validate" in self.expected_path):
            raise ValueError("Validation presence must match the executed path")
        if (self.expected_response_status is not None) != (
            "respond" in self.expected_path
        ):
            raise ValueError("Response presence must match the executed path")
        if (self.expected_status == "blocked") != bool(self.expected_validation):
            raise ValueError("Blocked state requires validation issues")
        if not failure and (
            self.expected_status != self.ideal_status
            or self.expected_response_status != self.expected_status
            or self.detection_operation is not None
        ):
            raise ValueError("Correct references require a consistent ideal result")
        return self


def load_truth(path: Path):
    truth = GroundTruth.model_validate(read_json(path))
    if truth.scenario_id != path.stem:
        raise ValueError("Ground truth filename and ID disagree")
    return truth
