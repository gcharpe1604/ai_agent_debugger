from pathlib import Path
from typing import Annotated

from pydantic import Field, StringConstraints, model_validator

from .knowledge_base import KnowledgeBase
from .models import (
    DomainModel,
    GeneratedAnswer,
    KnowledgeDocument,
    RetrievalResult,
    Text,
)
from .retrieval import Retriever
from .yaml_io import load_yaml


class RetrievalOverride(DomainModel):
    attempt: int = Field(ge=1, le=2)
    replace_with_document_ids: list[Text] = Field(min_length=1)


class GenerationOverride(DomainModel):
    invocation: int = Field(ge=1, le=1)
    output: GeneratedAnswer


class ModelOverrides(DomainModel):
    generate_answer: list[GenerationOverride] = Field(default_factory=list)

    @model_validator(mode="after")
    def unique_invocations(self) -> "ModelOverrides":
        invocations = [override.invocation for override in self.generate_answer]
        if len(invocations) != len(set(invocations)):
            raise ValueError("Duplicate generate_answer invocation override")
        return self


class ScenarioConfig(DomainModel):
    schema_version: int = Field(ge=1, le=1)
    scenario_id: Annotated[str, StringConstraints(pattern=r"^RAG-\d{2}$")]
    question: Text
    retrieval_overrides: list[RetrievalOverride] = Field(default_factory=list)
    model_overrides: ModelOverrides = Field(default_factory=ModelOverrides)

    @model_validator(mode="after")
    def unique_attempts(self) -> "ScenarioConfig":
        attempts = [override.attempt for override in self.retrieval_overrides]
        if len(attempts) != len(set(attempts)):
            raise ValueError("Duplicate retrieval attempt override")
        return self

    def validate_documents(self, knowledge_base: KnowledgeBase) -> None:
        for override in self.retrieval_overrides:
            for document_id in override.replace_with_document_ids:
                knowledge_base.get(document_id)
        for override in self.model_overrides.generate_answer:
            for document_id in override.output.supporting_document_ids:
                knowledge_base.get(document_id)


def load_scenario(path: Path, knowledge_base: KnowledgeBase) -> ScenarioConfig:
    scenario = ScenarioConfig.model_validate(
        load_yaml(path.read_text(encoding="utf-8"))
    )
    scenario.validate_documents(knowledge_base)
    return scenario


class ScenarioAwareRetriever:
    def __init__(
        self, base: Retriever, replacements: dict[int, list[KnowledgeDocument]]
    ):
        self.base = base
        self.replacements = replacements

    async def search(
        self, query: str, top_k: int = 3, *, attempt_number: int = 1
    ) -> list[RetrievalResult]:
        if type(attempt_number) is not int or not 1 <= attempt_number <= 2:
            raise ValueError("attempt_number must be 1 or 2")
        if type(top_k) is not int or top_k < 1:
            raise ValueError("top_k must be a positive integer")
        if attempt_number in self.replacements:
            # A replacement is exact and ordered; zero denotes an injected, unranked result.
            return [
                RetrievalResult(document=document, score=0.0)
                for document in self.replacements[attempt_number]
            ]
        return await self.base.search(query, top_k, attempt_number=attempt_number)
