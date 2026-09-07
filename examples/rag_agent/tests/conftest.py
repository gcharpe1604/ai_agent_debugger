import asyncio

import pytest

from rag_agent.factory import DATA_DIR, build_agent
from rag_agent.knowledge_base import KnowledgeBase
from rag_agent.scenarios import load_scenario


@pytest.fixture(scope="session")
def kb():
    return KnowledgeBase(DATA_DIR / "knowledge_base")


@pytest.fixture(scope="session")
def scenarios(kb):
    return {
        path.stem: load_scenario(path, kb)
        for path in sorted((DATA_DIR / "scenarios").glob("*.yaml"))
    }


@pytest.fixture(scope="session")
def results(kb, scenarios):
    return {
        name: asyncio.run(build_agent(scenario, kb).run(scenario.question))
        for name, scenario in scenarios.items()
    }
