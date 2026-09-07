import asyncio

import pytest

from rag_agent.agent import RAGAgent
from rag_agent.controlled_model import ControlledModelClient
from rag_agent.factory import build_agent
from rag_agent.retrieval import LocalRetriever


def ids(attempt):
    return [item.document.document_id for item in attempt.results]


def test_rag_01(results):
    result = results["RAG-01"]
    assert len(result.context.retrieval_attempts) == 1
    assert result.context.retrieval_attempts[0].query == (
        "deleted workspace restore deletion policy"
    )
    assert "KB-01" in ids(result.context.retrieval_attempts[0])
    assert result.context.retrieval_attempts[0].assessment.sufficient
    assert result.status == "answered" and "14 days" in result.answer
    assert result.supporting_document_ids == ["KB-01"]


def test_rag_02(results):
    result = results["RAG-02"]
    assert len(result.context.retrieval_attempts) == 2
    for number, attempt in enumerate(result.context.retrieval_attempts, 1):
        assert attempt.attempt_number == number
        assert ids(attempt) == ["KB-03"]
        assert not attempt.assessment.sufficient
        assert attempt.assessment.missing_facts == ["workspace_restore_period"]
    assert result.status == "insufficient_evidence"
    assert result.supporting_document_ids == []


def test_rag_03(results, scenarios):
    result = results["RAG-03"]
    assert not scenarios["RAG-03"].model_overrides.generate_answer
    assert len(result.context.retrieval_attempts) == 1
    assert ids(result.context.retrieval_attempts[0]) == ["KB-02"]
    assert result.context.retrieval_attempts[0].assessment.sufficient
    assert result.status == "answered" and "30 days" in result.answer
    assert result.supporting_document_ids == ["KB-02"]


def test_rag_04(results):
    result = results["RAG-04"]
    assert len(result.context.retrieval_attempts) == 1
    attempt = result.context.retrieval_attempts[0]
    assert "KB-01" in ids(attempt) and attempt.assessment.sufficient
    assert "14 days" in next(
        item.document.content
        for item in attempt.results
        if item.document.document_id == "KB-01"
    )
    assert result.status == "answered" and "30 days" in result.answer
    assert result.supporting_document_ids == ["KB-01"]


@pytest.mark.parametrize("scenario_id", ["RAG-05", "RAG-06"])
def test_residency_evidence_remains_insufficient(results, scenario_id):
    result = results[scenario_id]
    assert len(result.context.retrieval_attempts) == 2
    first, second = result.context.retrieval_attempts
    assert first.query == "NovaCloud data residency storage region India"
    assert second.query == "NovaCloud official data hosting location residency policy"
    assert first.query != second.query
    for attempt in result.context.retrieval_attempts:
        assert not attempt.assessment.sufficient
        assert attempt.assessment.supported_facts == []
        assert attempt.assessment.missing_facts == ["data_residency"]
    assert result.supporting_document_ids == []
    if scenario_id == "RAG-05":
        assert result.status == "insufficient_evidence"
    else:
        assert result.status == "answered"
        assert "all customer data exclusively in India" in result.answer


def test_rag_07_accumulates_both_attempts(results):
    result = results["RAG-07"]
    assert len(result.context.retrieval_attempts) == 2
    first, second = result.context.retrieval_attempts
    assert first.query == "Pro downgrade to Starter plan"
    assert second.query == "workspace export download link validity"
    assert "KB-05" in ids(first) and "KB-04" not in ids(first)
    assert first.assessment.supported_facts == ["downgrade_effective_time"]
    assert first.assessment.missing_facts == ["export_link_validity"]
    assert not first.assessment.sufficient
    assert "KB-04" in ids(second)
    assert second.assessment.sufficient and second.assessment.missing_facts == []
    assert result.supporting_document_ids == ["KB-05", "KB-04"]
    assert result.status == "answered"
    assert "next billing renewal" in result.answer and "48 hours" in result.answer


def test_operation_order_and_retrieval_bound(kb, scenarios):
    calls = []

    class RecordingModel(ControlledModelClient):
        async def classify_question(self, *args):
            calls.append("classify_question")
            return await super().classify_question(*args)

        async def formulate_query(self, *args):
            calls.append("formulate_query")
            return await super().formulate_query(*args)

        async def assess_evidence(self, *args):
            calls.append("assess_evidence")
            return await super().assess_evidence(*args)

        async def refine_query(self, *args):
            calls.append("refine_query")
            return await super().refine_query(*args)

        async def generate_answer(self, *args):
            calls.append("generate_answer")
            return await super().generate_answer(*args)

    class RecordingRetriever(LocalRetriever):
        async def search(self, *args, **kwargs):
            calls.append("search_knowledge_base")
            return await super().search(*args, **kwargs)

    result = asyncio.run(
        RAGAgent(RecordingModel(), RecordingRetriever(kb)).run(
            scenarios["RAG-07"].question
        )
    )
    assert result.status == "answered"
    assert calls == [
        "classify_question",
        "formulate_query",
        "search_knowledge_base",
        "assess_evidence",
        "refine_query",
        "search_knowledge_base",
        "assess_evidence",
        "generate_answer",
    ]
    limited = asyncio.run(
        RAGAgent(ControlledModelClient(), LocalRetriever(kb), 1).run(
            scenarios["RAG-07"].question
        )
    )
    assert len(limited.context.retrieval_attempts) == 1
    assert limited.status == "insufficient_evidence"


@pytest.mark.parametrize("limit", [0, 3, -1, True, 1.5])
def test_invalid_limits(kb, limit):
    with pytest.raises(ValueError, match="max_retrieval_attempts"):
        RAGAgent(ControlledModelClient(), LocalRetriever(kb), limit)


@pytest.mark.parametrize("question", ["", "  ", None, 42])
def test_invalid_questions(kb, question):
    with pytest.raises(ValueError, match="question"):
        asyncio.run(RAGAgent(ControlledModelClient(), LocalRetriever(kb)).run(question))


def test_dependency_errors_propagate(kb):
    class BrokenRetriever(LocalRetriever):
        async def search(self, *args, **kwargs):
            raise OSError("Cannot read local index")

    with pytest.raises(OSError, match="Cannot read local index"):
        asyncio.run(
            RAGAgent(ControlledModelClient(), BrokenRetriever(kb)).run(
                "Restore workspace?"
            )
        )


@pytest.mark.parametrize("scenario_id", ["RAG-04", "RAG-06"])
def test_generation_override_changes_only_final_output(
    kb, scenarios, results, scenario_id
):
    from rag_agent.scenarios import ModelOverrides

    baseline = scenarios[scenario_id].model_copy(
        update={"model_overrides": ModelOverrides()}
    )
    normal = asyncio.run(build_agent(baseline, kb).run(baseline.question))
    assert normal.context == results[scenario_id].context
    assert normal.answer != results[scenario_id].answer
    assert normal.status == (
        "answered" if scenario_id == "RAG-04" else "insufficient_evidence"
    )
