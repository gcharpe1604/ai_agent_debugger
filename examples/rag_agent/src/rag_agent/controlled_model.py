from collections.abc import Mapping

from .models import (
    EvidenceAssessment,
    GeneratedAnswer,
    KnowledgeDocument,
    QuestionClassification,
    RetrievalQuery,
    abstention,
)

# Controlled model semantics only. Every value is checked against its Markdown source.
CONTROLLED_FACT_VALUES = {
    ("KB-01", "workspace_restore_period"): "14 days",
    ("KB-01", "workspace_restore_actor"): "workspace owner",
    ("KB-02", "workspace_restore_period"): "30 days",
    ("KB-03", "file_trash_retention"): "30 days",
    ("KB-04", "export_generation_time"): "up to 24 hours",
    ("KB-04", "export_link_validity"): "48 hours",
    ("KB-05", "upgrade_effective_time"): "immediately",
    ("KB-05", "downgrade_effective_time"): "next billing renewal",
    ("KB-06", "billing_renewal"): "renewal date",
    ("KB-07", "storage_limits"): "100 GB",
    ("KB-08", "password_reset_expiry"): "30 minutes",
    ("KB-09", "enterprise_support_availability"): "24/7 priority support",
    ("KB-09", "severity_one_response_time"): "1 hour",
    ("KB-10", "api_rate_limits"): "300 requests/minute",
}
DOCUMENT_FACT_SUPPORT = {
    document_id: {
        fact for source, fact in CONTROLLED_FACT_VALUES if source == document_id
    }
    for document_id, _ in CONTROLLED_FACT_VALUES
}

QUERIES = {
    "workspace_restore_period": "deleted workspace restore deletion policy",
    "downgrade_effective_time": "Pro downgrade to Starter plan",
    "export_link_validity": "workspace export download link validity",
    "data_residency": "NovaCloud data residency storage region India",
}
ANSWER_TEMPLATES = {
    "workspace_restore_period": "You can restore a deleted workspace for up to {value} after deletion.",
    "downgrade_effective_time": "The downgrade takes effect at the {value}.",
    "export_link_validity": "Once generated, the export download link remains valid for {value}.",
}


class ControlledModelClient:
    """Deterministic semantic test double, not a general English interpreter."""

    def __init__(self, answer_overrides: Mapping[int, GeneratedAnswer] | None = None):
        self._answer_overrides = dict(answer_overrides or {})

    async def classify_question(self, question: str) -> QuestionClassification:
        text = question.lower()
        topics, facts = [], []
        # ponytail: keyword classification covers this workload; extend rules for new questions.
        if "workspace" in text and ("restore" in text or "delet" in text):
            topics.append("workspace_deletion")
            facts.append("workspace_restore_period")
        if "downgrade" in text:
            topics.append("plan_changes")
            facts.append("downgrade_effective_time")
        if "export" in text and "link" in text:
            topics.append("data_export")
            facts.append("export_link_validity")
        if "residency" in text or ("india" in text and "data" in text):
            topics.append("data_residency")
            facts.append("data_residency")
        return QuestionClassification(
            topics=topics or ["unknown"],
            required_facts=facts or ["unrecognized_question"],
        )

    async def formulate_query(
        self, question: str, classification: QuestionClassification
    ) -> RetrievalQuery:
        # The first required fact starts retrieval; missing facts drive the bounded retry.
        return RetrievalQuery(
            query=QUERIES.get(classification.required_facts[0], question)
        )

    async def assess_evidence(
        self,
        question: str,
        classification: QuestionClassification,
        documents: list[KnowledgeDocument],
    ) -> EvidenceAssessment:
        supported = {
            fact
            for document in documents
            for fact in DOCUMENT_FACT_SUPPORT.get(document.document_id, set())
        }
        missing = [
            fact for fact in classification.required_facts if fact not in supported
        ]
        return EvidenceAssessment(
            sufficient=not missing,
            supported_facts=[
                fact for fact in classification.required_facts if fact in supported
            ],
            missing_facts=missing,
        )

    async def refine_query(
        self,
        question: str,
        classification: QuestionClassification,
        assessment: EvidenceAssessment,
        previous_query: RetrievalQuery,
    ) -> RetrievalQuery:
        missing = assessment.missing_facts
        if "workspace_restore_period" in missing:
            return RetrievalQuery(
                query="NovaCloud deleted workspace restore recovery policy"
            )
        if "data_residency" in missing:
            return RetrievalQuery(
                query="NovaCloud official data hosting location residency policy"
            )
        return RetrievalQuery(
            query=" ".join(
                QUERIES.get(fact, fact.replace("_", " ")) for fact in missing
            )
            or question
        )

    async def generate_answer(
        self,
        question: str,
        classification: QuestionClassification,
        documents: list[KnowledgeDocument],
        assessment: EvidenceAssessment,
    ) -> GeneratedAnswer:
        # Each run has exactly one generation invocation, including after exhausted retrieval.
        # No instance counter: reusing an agent must not consume another run's overrides.
        if 1 in self._answer_overrides:
            return self._answer_overrides[1].model_copy(deep=True)
        if not assessment.sufficient:
            return abstention()
        sentences, sources = [], []
        for fact in classification.required_facts:
            source = next(
                (
                    d.document_id
                    for d in documents
                    if (d.document_id, fact) in CONTROLLED_FACT_VALUES
                ),
                None,
            )
            if source is None or fact not in ANSWER_TEMPLATES:
                return abstention()
            value = CONTROLLED_FACT_VALUES[source, fact]
            sentences.append(ANSWER_TEMPLATES[fact].format(value=value))
            if source not in sources:
                sources.append(source)
        return GeneratedAnswer(
            status="answered",
            answer=" ".join(sentences),
            supporting_document_ids=sources,
        )
