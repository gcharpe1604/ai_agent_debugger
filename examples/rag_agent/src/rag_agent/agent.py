from .model_client import ModelClient
from .models import AgentContext, AgentResult, KnowledgeDocument, RetrievalAttempt
from .retrieval import Retriever


class RAGAgent:
    def __init__(
        self, model: ModelClient, retriever: Retriever, max_retrieval_attempts: int = 2
    ):
        if (
            type(max_retrieval_attempts) is not int
            or not 1 <= max_retrieval_attempts <= 2
        ):
            raise ValueError("max_retrieval_attempts must be 1 or 2")
        self.model = model
        self.retriever = retriever
        self.max_retrieval_attempts = max_retrieval_attempts

    async def run(self, question: str) -> AgentResult:
        if not isinstance(question, str) or not question.strip():
            raise ValueError("question must be a nonempty string")
        question = question.strip()
        classification = await self.model.classify_question(question)
        context = AgentContext(question=question, classification=classification)
        query = await self.model.formulate_query(question, classification)
        documents: dict[str, KnowledgeDocument] = {}
        for number in range(1, self.max_retrieval_attempts + 1):
            results = await self.retriever.search(query.query, attempt_number=number)
            for result in results:
                documents[result.document.document_id] = result.document
            accumulated = list(documents.values())
            assessment = await self.model.assess_evidence(
                question, classification, accumulated
            )
            context.retrieval_attempts.append(
                RetrievalAttempt(
                    attempt_number=number,
                    query=query.query,
                    results=results,
                    assessment=assessment,
                )
            )
            if assessment.sufficient or number == self.max_retrieval_attempts:
                break
            query = await self.model.refine_query(question, classification, assessment)
        answer = await self.model.generate_answer(
            question, classification, accumulated, assessment
        )
        return AgentResult(question=question, context=context, **answer.model_dump())
