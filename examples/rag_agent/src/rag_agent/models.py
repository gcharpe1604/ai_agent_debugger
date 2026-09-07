from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class DomainModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class KnowledgeDocument(DomainModel):
    document_id: Text
    title: Text
    content: Text
    version: int = Field(ge=1)
    status: Literal["current", "superseded"]
    topic: Text
    superseded_by: Text | None = None

    @model_validator(mode="after")
    def validate_replacement(self) -> "KnowledgeDocument":
        if self.status == "superseded" and not self.superseded_by:
            raise ValueError("A superseded document must name its replacement")
        if self.superseded_by == self.document_id:
            raise ValueError("A document cannot supersede itself")
        if self.status == "current" and self.superseded_by:
            raise ValueError("A current document cannot name a replacement")
        return self


class QuestionClassification(DomainModel):
    topics: list[Text] = Field(min_length=1)
    required_facts: list[Text] = Field(min_length=1)


class RetrievalQuery(DomainModel):
    query: Text


class EvidenceAssessment(DomainModel):
    sufficient: bool
    supported_facts: list[Text]
    missing_facts: list[Text]


class GeneratedAnswer(DomainModel):
    status: Literal["answered", "insufficient_evidence"]
    answer: Text
    supporting_document_ids: list[Text]


class RetrievalResult(DomainModel):
    document: KnowledgeDocument
    score: float = Field(ge=0, allow_inf_nan=False)


class RetrievalAttempt(DomainModel):
    attempt_number: int = Field(ge=1, le=2)
    query: Text
    results: list[RetrievalResult]
    assessment: EvidenceAssessment


class AgentContext(DomainModel):
    question: Text
    classification: QuestionClassification
    retrieval_attempts: list[RetrievalAttempt] = Field(default_factory=list)


class AgentResult(GeneratedAnswer):
    question: Text
    context: AgentContext
