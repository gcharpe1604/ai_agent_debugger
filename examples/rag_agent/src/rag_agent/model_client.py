from typing import Protocol

from .models import (
    EvidenceAssessment,
    GeneratedAnswer,
    KnowledgeDocument,
    QuestionClassification,
    RetrievalQuery,
)


class ModelClient(Protocol):
    async def classify_question(self, question: str) -> QuestionClassification: ...

    async def formulate_query(
        self, question: str, classification: QuestionClassification
    ) -> RetrievalQuery: ...

    async def assess_evidence(
        self,
        question: str,
        classification: QuestionClassification,
        documents: list[KnowledgeDocument],
    ) -> EvidenceAssessment: ...

    async def refine_query(
        self,
        question: str,
        classification: QuestionClassification,
        assessment: EvidenceAssessment,
        previous_query: RetrievalQuery,
    ) -> RetrievalQuery: ...

    async def generate_answer(
        self,
        question: str,
        classification: QuestionClassification,
        documents: list[KnowledgeDocument],
        assessment: EvidenceAssessment,
    ) -> GeneratedAnswer: ...
