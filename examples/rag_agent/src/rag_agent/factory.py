from pathlib import Path

from .agent import RAGAgent
from .controlled_model import ControlledModelClient
from .knowledge_base import KnowledgeBase
from .retrieval import LocalRetriever
from .scenarios import ScenarioAwareRetriever, ScenarioConfig

DATA_DIR = Path(__file__).resolve().parent / "data"


def build_agent(
    scenario: ScenarioConfig, knowledge_base: KnowledgeBase | None = None
) -> RAGAgent:
    kb = (
        knowledge_base
        if knowledge_base is not None
        else KnowledgeBase(DATA_DIR / "knowledge_base")
    )
    scenario.validate_documents(kb)
    retriever = ScenarioAwareRetriever(
        LocalRetriever(kb),
        {
            override.attempt: [
                kb.get(doc_id) for doc_id in override.replace_with_document_ids
            ]
            for override in scenario.retrieval_overrides
        },
    )
    model = ControlledModelClient(
        {
            override.invocation: override.output
            for override in scenario.model_overrides.generate_answer
        }
    )
    return RAGAgent(model=model, retriever=retriever)
