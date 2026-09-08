import asyncio

from rag_agent.controlled_model import ControlledModelClient
from rag_agent.models import RetrievalQuery


def test_classification_and_query_are_deterministic(scenarios):
    async def check():
        model = ControlledModelClient()
        for scenario in scenarios.values():
            classification = await model.classify_question(scenario.question)
            assert await model.classify_question(scenario.question) == classification
            query = await model.formulate_query(scenario.question, classification)
            assert (
                await model.formulate_query(scenario.question, classification) == query
            )
        workspace = await model.classify_question(scenarios["RAG-01"].question)
        assert workspace.required_facts == ["workspace_restore_period"]
        residency = await model.classify_question(scenarios["RAG-05"].question)
        assert residency.required_facts == ["data_residency"]
        multi = await model.classify_question(scenarios["RAG-07"].question)
        assert multi.topics == ["plan_changes", "data_export"]
        assert multi.required_facts == [
            "downgrade_effective_time",
            "export_link_validity",
        ]

    asyncio.run(check())


def test_accumulated_support_and_refinement(kb, scenarios):
    async def check():
        model = ControlledModelClient()
        question = scenarios["RAG-07"].question
        classification = await model.classify_question(question)
        first = await model.assess_evidence(question, classification, [kb.get("KB-05")])
        assert first.supported_facts == ["downgrade_effective_time"]
        assert first.missing_facts == ["export_link_validity"]
        assert not first.sufficient
        assert (
            "export"
            in (
                await model.refine_query(
                    question,
                    classification,
                    first,
                    RetrievalQuery(query="Pro downgrade to Starter plan"),
                )
            ).query
        )
        second_alone = await model.assess_evidence(
            question, classification, [kb.get("KB-04")]
        )
        assert second_alone.missing_facts == ["downgrade_effective_time"]
        combined = await model.assess_evidence(
            question, classification, [kb.get("KB-05"), kb.get("KB-04")]
        )
        assert combined.sufficient and combined.missing_facts == []

    asyncio.run(check())


def test_generation_uses_only_supplied_support(kb, scenarios):
    async def check():
        model = ControlledModelClient()
        question = scenarios["RAG-01"].question
        classification = await model.classify_question(question)
        for document_id, days in [("KB-01", "14 days"), ("KB-02", "30 days")]:
            documents = [kb.get(document_id)]
            assessment = await model.assess_evidence(
                question, classification, documents
            )
            answer = await model.generate_answer(
                question, classification, documents, assessment
            )
            assert assessment.sufficient
            assert days in answer.answer
            assert answer.supporting_document_ids == [document_id]
        for documents in [[], [kb.get("KB-03")]]:
            assessment = await model.assess_evidence(
                question, classification, documents
            )
            answer = await model.generate_answer(
                question, classification, documents, assessment
            )
            assert assessment.missing_facts == ["workspace_restore_period"]
            assert answer.status == "insufficient_evidence"
            assert answer.supporting_document_ids == []

    asyncio.run(check())


def test_unknown_question_abstains(kb):
    from rag_agent.agent import RAGAgent
    from rag_agent.retrieval import LocalRetriever

    result = asyncio.run(
        RAGAgent(ControlledModelClient(), LocalRetriever(kb)).run(
            "What is my lucky number?"
        )
    )
    assert result.status == "insufficient_evidence"
    assert len(result.context.retrieval_attempts) == 2
