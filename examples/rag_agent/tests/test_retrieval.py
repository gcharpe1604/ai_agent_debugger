import asyncio

import pytest

from rag_agent.retrieval import LocalRetriever
from rag_agent.scenarios import ScenarioAwareRetriever


def ids(results):
    return [item.document.document_id for item in results]


def test_workspace_top_k_and_repeatability(kb):
    retriever = LocalRetriever(kb)
    query = "deleted workspace restore deletion policy"
    first = asyncio.run(retriever.search(query))
    assert ids(first)[0] == "KB-01"
    assert len(first) <= 3
    assert all(result.score > 0 for result in first)
    assert asyncio.run(retriever.search(query)) == first
    assert ids(asyncio.run(retriever.search(query, top_k=1))) == ["KB-01"]


def test_superseded_never_in_normal_index(kb):
    retriever = LocalRetriever(kb)
    assert "KB-02" not in [document.document_id for document in retriever.documents]
    queries = [
        "deleted workspace restore deletion policy",
        "Pro downgrade to Starter plan",
        "workspace export download link validity",
        "NovaCloud data residency storage region India",
        "NovaCloud official data hosting location residency policy",
    ] + [d.title + " " + d.content for d in kb.documents]
    for query in queries:
        assert "KB-02" not in ids(asyncio.run(retriever.search(query, top_k=100)))


def test_multidocument_queries_allow_a_real_retry(kb):
    retriever = LocalRetriever(kb)
    first = ids(asyncio.run(retriever.search("Pro downgrade to Starter plan")))
    second = ids(
        asyncio.run(retriever.search("workspace export download link validity"))
    )
    assert "KB-05" in first and "KB-04" not in first
    assert "KB-04" in second


@pytest.mark.parametrize("top_k", [0, -1, 1.5, True])
def test_invalid_top_k(kb, top_k):
    with pytest.raises(ValueError, match="top_k"):
        asyncio.run(LocalRetriever(kb).search("workspace", top_k))


@pytest.mark.parametrize("query", ["", "the and of", "xyzzynonexistent"])
def test_no_positive_matches_returns_empty(kb, query):
    assert asyncio.run(LocalRetriever(kb).search(query)) == []


def test_override_is_exact_ordered_and_attempt_local(kb):
    base = LocalRetriever(kb)
    wrapper = ScenarioAwareRetriever(base, {1: [kb.get("KB-03"), kb.get("KB-02")]})
    assert ids(asyncio.run(wrapper.search("workspace", top_k=1))) == ["KB-03", "KB-02"]
    assert asyncio.run(wrapper.search("workspace", attempt_number=2)) == asyncio.run(
        base.search("workspace")
    )
    assert ids(asyncio.run(wrapper.search("workspace"))) == ["KB-03", "KB-02"]
