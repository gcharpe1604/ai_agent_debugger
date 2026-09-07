"""Evaluation-label validation only; never imported by the runtime package."""

from pathlib import Path
from typing import Annotated, Literal

from pydantic import Field, StringConstraints, model_validator

from rag_agent.models import DomainModel, Text
from rag_agent.yaml_io import load_yaml

DocumentId = Annotated[str, StringConstraints(pattern=r"^KB-(0[1-9]|10)$")]
Attempt = Annotated[int, Field(ge=1, le=2)]
Operation = Literal[
    "classify_question",
    "formulate_query",
    "search_knowledge_base",
    "assess_evidence",
    "refine_query",
    "generate_answer",
]


class RetrievalFailure(DomainModel):
    operation: Literal["search_knowledge_base"]
    category: Literal["wrong_document_retrieval", "superseded_document_retrieval"]
    retrieval_attempts: list[Attempt] = Field(min_length=1)


class GenerationFailure(DomainModel):
    operation: Literal["generate_answer"]
    category: Literal["evidence_contradiction", "unsupported_generation"]


class FactFields(DomainModel):
    @model_validator(mode="after")
    def nonempty_facts(self) -> "FactFields":
        if not self.model_fields_set or any(
            getattr(self, name) is None for name in self.model_fields_set
        ):
            raise ValueError("Facts must be nonempty and cannot contain null values")
        return self


class ExpectedFacts(FactFields):
    workspace_restore_days: int | None = Field(default=None, gt=0)
    data_residency_evidence_available: bool | None = None
    evidence_sufficient: bool | None = None
    downgrade_effective_time: Text | None = None
    export_link_validity_hours: int | None = Field(default=None, gt=0)


class FaultyFacts(FactFields):
    workspace_restore_days: int | None = Field(default=None, gt=0)
    india_only_storage_guarantee: bool | None = None


class GroundTruth(DomainModel):
    schema_version: int = Field(ge=1, le=1)
    scenario_id: Annotated[str, StringConstraints(pattern=r"^RAG-0[1-7]$")]
    expected_outcome: Literal["correct", "failure"]
    expected_failure: RetrievalFailure | GenerationFailure | None
    important_operations: list[Operation] = Field(min_length=1)
    important_document_ids: list[DocumentId]
    expected_status: Literal["answered", "insufficient_evidence"]
    expected_retrieval_attempts: Attempt
    expected_facts: ExpectedFacts
    observed_faulty_facts: FaultyFacts | None = None
    correct_source: DocumentId | None = None
    wrongly_supplied_sources: list[DocumentId] | None = Field(
        default=None, min_length=1
    )
    notes: Text | None = None
    expected_behavior: Literal["abstention"] | None = None
    required_facts: (
        list[Literal["downgrade_effective_time", "export_link_validity"]] | None
    ) = Field(default=None, min_length=1)

    @model_validator(mode="after")
    def consistent_labels(self) -> "GroundTruth":
        if any(
            getattr(self, name) is None
            for name in self.model_fields_set - {"expected_failure"}
        ):
            raise ValueError("Only expected_failure may explicitly be null")
        failure = self.expected_failure
        if (self.expected_outcome == "failure") != (failure is not None):
            raise ValueError(
                "Failure details are required exactly for failure outcomes"
            )
        if failure and failure.operation not in self.important_operations:
            raise ValueError("Failure operation must be an important operation")
        if isinstance(failure, RetrievalFailure):
            attempts = failure.retrieval_attempts
            if (
                len(attempts) != len(set(attempts))
                or max(attempts) > self.expected_retrieval_attempts
            ):
                raise ValueError(
                    "Failure attempts must be unique and within the execution"
                )
            if not self.correct_source or not self.wrongly_supplied_sources:
                raise ValueError(
                    "Retrieval failures must identify correct and supplied sources"
                )
        if (
            self.expected_outcome == "correct"
            and self.observed_faulty_facts is not None
        ):
            raise ValueError("Correct outcomes cannot contain observed faulty facts")
        if (
            self.expected_behavior == "abstention"
            and self.expected_status != "insufficient_evidence"
        ):
            raise ValueError("Abstention requires insufficient_evidence status")
        return self


def load_ground_truth(path: Path) -> GroundTruth:
    truth = GroundTruth.model_validate(load_yaml(path.read_text(encoding="utf-8")))
    if truth.scenario_id != path.stem:
        raise ValueError("Ground-truth filename and scenario_id disagree")
    return truth
