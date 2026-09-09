import re
from typing import Annotated

from pydantic import Field, StringConstraints, field_validator, model_validator

from .agent import ResearchPlanningAgent
from .evidence import DATA_DIR, EvidenceSource, load_evidence, read_json
from .model_client import ModelClient, assess
from .models import (
    FACTS,
    EvidenceAssessment,
    Model,
    Plan,
    PlanRevision,
    Report,
    Text,
    unique,
)


class AssessmentOverride(Model):
    invocation: int = Field(ge=1, le=2)
    response: EvidenceAssessment


class RuntimeScenario(Model):
    schema_version: int = Field(ge=1, le=1)
    scenario_id: Annotated[str, StringConstraints(pattern=r"^RP-\d{2}$")]
    request: Text
    excluded_evidence: list[Text] = Field(default_factory=list)
    plan_override: Plan | None = None
    assessment_overrides: list[AssessmentOverride] = Field(default_factory=list)
    revision_override: PlanRevision | None = None
    synthesis_override: Report | None = None
    validation_override: list[Text] | None = None

    _unique = field_validator("excluded_evidence")(unique)

    @model_validator(mode="after")
    def check_overrides(self):
        ModelClient().decompose(self.request)
        unique([override.invocation for override in self.assessment_overrides])
        for override in self.assessment_overrides:
            response = override.response
            partition = [*response.selected, *response.missing, *response.conflicts]
            if len(partition) != len(FACTS) or set(partition) != set(FACTS):
                raise ValueError(
                    "Assessment must partition all required facts exactly once"
                )
            for ids in [*response.selected.values(), *response.conflicts.values()]:
                unique(ids)
        return self


def load_scenario(scenario_id: str) -> RuntimeScenario:
    if not re.fullmatch(r"RP-\d{2}", scenario_id):
        raise ValueError("Expected scenario ID such as RP-01")
    config = RuntimeScenario.model_validate(
        read_json(DATA_DIR / "scenarios" / f"{scenario_id}.json")
    )
    if config.scenario_id != scenario_id:
        raise ValueError("Scenario ID disagrees with filename")
    return config


class PreparedModel(ModelClient):
    def __init__(self, *, plan, assessments, revision, synthesis, validation):
        self.plan = plan
        self.assessments = {item.invocation: item.response for item in assessments}
        self.revision = revision
        self.synthesis = synthesis
        self.validation = validation

    def create_plan(self, task):
        return (
            self.plan.model_copy(deep=True)
            if self.plan is not None
            else super().create_plan(task)
        )

    def assess_evidence(self, task, evidence, *, invocation):
        if invocation in self.assessments:
            return self.assessments[invocation].model_copy(deep=True)
        return super().assess_evidence(task, evidence, invocation=invocation)

    def revise_plan(self, task, assessment):
        return (
            self.revision.model_copy(deep=True)
            if self.revision is not None
            else super().revise_plan(task, assessment)
        )

    def synthesize_report(self, task, assessment, evidence):
        return (
            self.synthesis.model_copy(deep=True)
            if self.synthesis is not None
            else super().synthesize_report(task, assessment, evidence)
        )

    def validate_support(self, task, report, evidence):
        return (
            list(self.validation)
            if self.validation is not None
            else super().validate_support(task, report, evidence)
        )


def build_agent(config: RuntimeScenario) -> ResearchPlanningAgent:
    prepared = config.model_copy(deep=True)
    corpus = load_evidence()
    by_id = {item.evidence_id: item for item in corpus}
    if not set(prepared.excluded_evidence) <= by_id.keys():
        raise ValueError("Unknown excluded evidence ID")
    available = [
        item for item in corpus if item.evidence_id not in prepared.excluded_evidence
    ]
    model = ModelClient()
    task = model.decompose(prepared.request)
    plan = prepared.plan_override or model.create_plan(task)
    initial = [
        item
        for item in available
        if any(
            item.fact == step.fact and item.availability == step.query
            for step in plan.steps
        )
    ]
    first = next(
        (
            item.response
            for item in prepared.assessment_overrides
            if item.invocation == 1
        ),
        assess(task, initial),
    )
    gaps = set(first.missing) | set(first.conflicts)
    if not gaps and (
        prepared.revision_override is not None
        or any(item.invocation == 2 for item in prepared.assessment_overrides)
    ):
        raise ValueError("Revision and second assessment require an evidence gap")
    revision = prepared.revision_override or model.revise_plan(task, first)
    reachable = {1: {item.evidence_id for item in initial}}
    reachable[2] = reachable[1] | {
        item.evidence_id
        for item in available
        if any(
            item.fact == step.fact and item.availability == step.query
            for step in revision.plan.steps
        )
    }
    for override in prepared.assessment_overrides:
        response = override.response
        for fact, ids in {**response.selected, **response.conflicts}.items():
            if any(
                eid not in by_id
                or by_id[eid].fact != fact
                or eid in prepared.excluded_evidence
                or eid not in reachable[override.invocation]
                for eid in ids
            ):
                raise ValueError(
                    "Assessment references unavailable or wrong-topic evidence"
                )
        if not set(response.stale) <= by_id.keys():
            raise ValueError("Unknown stale evidence ID")
    return ResearchPlanningAgent(
        PreparedModel(
            plan=prepared.plan_override,
            assessments=prepared.assessment_overrides,
            revision=prepared.revision_override,
            synthesis=prepared.synthesis_override,
            validation=prepared.validation_override,
        ),
        EvidenceSource(available),
    )
