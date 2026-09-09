from pathlib import Path
from typing import Annotated, Literal

from pydantic import Field, StringConstraints, field_validator, model_validator

from research_planning_agent.evidence import read_json
from research_planning_agent.models import Fact, Model, Site, Text, unique


class GroundTruth(Model):
    schema_version: int = Field(ge=1, le=1)
    scenario_id: Annotated[str, StringConstraints(pattern=r"^RP-\d{2}$")]
    request: Text
    injected_behavior: Text
    expected_execution_behavior: Text
    expected_outcome: Literal["correct", "failure"]
    expected_status: Literal["completed", "incomplete", "blocked"]
    failure_category: (
        Literal[
            "stale_selection",
            "conflict_suppressed",
            "required_dependency_omitted",
            "dependency_order",
            "task_drift",
            "revision_no_progress",
            "unsupported_claim",
            "ignored_evidence",
        ]
        | None
    )
    failure_origin: (
        Literal["assess_evidence", "create_plan", "revise_plan", "synthesize_report"]
        | None
    )
    expected_suspicious_operations: list[Text]
    expected_issues: list[Text]
    expected_draft_recommendation: Site | None
    expected_collections: list[Text]
    expected_assessment_count: int = Field(ge=0, le=2)
    expected_unresolved: list[Fact]
    expected_revision: Literal["absent", "accepted", "rejected"]

    _unique = field_validator(
        "expected_suspicious_operations",
        "expected_issues",
        "expected_collections",
        "expected_unresolved",
    )(unique)

    @model_validator(mode="after")
    def consistent_outcome(self):
        failure = self.expected_outcome == "failure"
        if failure != (self.failure_category is not None) or failure != (
            self.failure_origin is not None
        ):
            raise ValueError("Failure outcome requires a category and origin")
        if failure != bool(self.expected_suspicious_operations):
            raise ValueError("Only injected failures have suspicious operations")
        if (self.expected_status == "blocked") != bool(self.expected_issues):
            raise ValueError(
                "Blocked results require issues, and only blocked results have issues"
            )
        if not failure and self.expected_status == "blocked":
            raise ValueError("Correct outcomes cannot be blocked")
        if self.expected_status == "incomplete" and (
            not self.expected_unresolved
            or self.expected_draft_recommendation is not None
        ):
            raise ValueError("Incomplete results must retain gaps and abstain")
        return self


def load_truth(path: Path):
    truth = GroundTruth.model_validate(read_json(path))
    if truth.scenario_id != path.stem:
        raise ValueError("Ground truth filename and ID disagree")
    return truth
