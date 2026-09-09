from datetime import date
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator

Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
Fact = Literal[
    "ridge.capacity",
    "ridge.power",
    "ridge.cost",
    "ridge.access",
    "ridge.permit",
    "vale.capacity",
    "vale.power",
    "vale.cost",
    "vale.access",
    "vale.permit",
]
Site = Literal["ridge", "vale"]
TOPICS = ("capacity", "power", "cost", "access", "permit")
FACTS = tuple(f"{site}.{topic}" for site in ("ridge", "vale") for topic in TOPICS)


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


def unique(values):
    if len(values) != len(set(values)):
        raise ValueError("Duplicate values are not allowed")
    return values


def iso_date(value):
    if date.fromisoformat(value).isoformat() != value:
        raise ValueError("Expected YYYY-MM-DD")
    return value


class ResearchTask(Model):
    request: Text
    people: int = Field(gt=0)
    power_kw: int = Field(gt=0)
    budget: int = Field(gt=0)
    as_of: Text

    _date = field_validator("as_of")(iso_date)


class PlanStep(Model):
    fact: Fact
    requires: list[Fact] = Field(default_factory=list)
    query: Literal["initial", "followup"] = "initial"

    _unique = field_validator("requires")(unique)


class Plan(Model):
    task: ResearchTask
    steps: list[PlanStep]

    @field_validator("steps")
    @classmethod
    def unique_steps(cls, steps):
        unique([step.fact for step in steps])
        return steps


class EvidenceItem(Model):
    evidence_id: Text
    title: Text
    source: Text
    content: Text
    site: Site
    topic: Literal["capacity", "power", "cost", "access", "permit", "visitors"]
    value: int | Text
    version: int = Field(gt=0)
    published_on: Text
    status: Literal["current", "superseded"]
    availability: Literal["initial", "followup"] = "initial"
    supersedes: list[Text] = Field(default_factory=list)

    _date = field_validator("published_on")(iso_date)
    _unique = field_validator("supersedes")(unique)

    @property
    def fact(self):
        return f"{self.site}.{self.topic}"


class EvidenceAssessment(Model):
    selected: dict[Fact, Annotated[list[Text], Field(min_length=1)]]
    missing: list[Fact]
    conflicts: dict[Fact, Annotated[list[Text], Field(min_length=2)]]
    stale: list[Text]

    _unique = field_validator("missing", "stale")(unique)


class PlanRevision(Model):
    plan: Plan
    reason: Text


class Claim(Model):
    fact: Fact
    value: int | Text
    evidence_ids: list[Text] = Field(min_length=1)

    _unique = field_validator("evidence_ids")(unique)


class Report(Model):
    recommendation: Site | None
    claims: list[Claim]
    unresolved: list[Fact]

    _unique = field_validator("unresolved")(unique)


class Collection(Model):
    step: PlanStep
    prerequisites: dict[Fact, list[Text]]
    evidence_ids: list[Text]


class ResearchResult(Model):
    task: ResearchTask
    plan: Plan
    status: Literal["completed", "incomplete", "blocked"]
    collections: list[Collection] = Field(default_factory=list)
    evidence: list[EvidenceItem] = Field(default_factory=list)
    assessments: list[EvidenceAssessment] = Field(default_factory=list)
    revision: PlanRevision | None = None
    draft: Report | None = None
    issues: list[Text] = Field(default_factory=list)
    operations: list[Text] = Field(default_factory=list)
