import asyncio
import inspect
from pathlib import Path

import pytest
import yaml
from ground_truth_schema import load_ground_truth
from pydantic import ValidationError

import rag_agent.agent as agent_module
import rag_agent.controlled_model as model_module
from rag_agent.agent import RAGAgent
from rag_agent.factory import DATA_DIR, build_agent
from rag_agent.scenarios import ScenarioConfig, load_scenario


def generation(**updates):
    return {
        "invocation": 1,
        "output": {
            "status": "answered",
            "answer": "Injected answer",
            "supporting_document_ids": [],
        },
        **updates,
    }


INVALID_UPDATES = [
    {"unexpected": "field"},
    {"expected_outcome": "correct"},
    {"expected_failure": None},
    {"failure_origin": "retrieval"},
    {"expected_suspicious_span": "S1"},
    {"failure_class": "retrieval"},
    {"schema_version": 2},
    {"schema_version": "1"},
    {"schema_version": True},
    {"question": " "},
    {"scenario_id": "../RAG-01"},
    {"retrieval_overrides": [{"attempt": 1, "replace_with_document_ids": []}]},
    {"retrieval_overrides": [{"attempt": 1, "replace_with_document_ids": ["KB-99"]}]},
    {
        "retrieval_overrides": [
            {"attempt": 1, "replace_with_document_ids": ["KB-01"], "extra": True}
        ]
    },
    {
        "retrieval_overrides": [{"attempt": 1, "replace_with_document_ids": ["KB-01"]}]
        * 2
    },
    {"model_overrides": {"assess_evidence": []}},
    {"model_overrides": {"generate_answer": [generation(invocation=0)]}},
    {"model_overrides": {"generate_answer": [generation(), generation()]}},
    {"model_overrides": {"generate_answer": [generation(extra=True)]}},
    {
        "model_overrides": {
            "generate_answer": [generation(output={"status": "answered"})]
        }
    },
    {
        "model_overrides": {
            "generate_answer": [
                generation(
                    output={
                        "status": "invalid",
                        "answer": "Bad",
                        "supporting_document_ids": [],
                    }
                )
            ]
        }
    },
    {
        "model_overrides": {
            "generate_answer": [
                generation(
                    output={
                        "status": "answered",
                        "answer": "Bad",
                        "supporting_document_ids": ["KB-99"],
                    }
                )
            ]
        }
    },
    {
        "model_overrides": {
            "generate_answer": [
                generation(
                    output={
                        "status": "answered",
                        "answer": "Bad",
                        "supporting_document_ids": [],
                        "confidence": 0.9,
                    }
                )
            ]
        }
    },
] + [
    {"retrieval_overrides": [{"attempt": n, "replace_with_document_ids": ["KB-01"]}]}
    for n in [0, 3, "1", True]
]

INVALID_UPDATES += [
    {"model_overrides": {"generate_answer": [generation(invocation=n)]}}
    for n in [-1, 2, "1", True, 1.0, None]
]


@pytest.mark.parametrize("updates", INVALID_UPDATES)
def test_invalid_runtime_configuration_rejected(kb, tmp_path, updates):
    payload = {
        "schema_version": 1,
        "scenario_id": "RAG-01",
        "question": "Restore workspace?",
        **updates,
    }
    path = tmp_path / "scenario.yaml"
    path.write_text(yaml.safe_dump(payload), encoding="utf-8")
    with pytest.raises(ValueError):
        load_scenario(path, kb)


def test_factory_validates_references_for_direct_configs(kb):
    scenario = ScenarioConfig.model_validate(
        {
            "schema_version": 1,
            "scenario_id": "RAG-01",
            "question": "Restore workspace?",
            "retrieval_overrides": [
                {"attempt": 1, "replace_with_document_ids": ["KB-99"]}
            ],
        }
    )
    with pytest.raises(ValueError, match="Unknown document ID"):
        build_agent(scenario, kb)


def test_generation_invocation_one_is_accepted(kb, tmp_path):
    path = tmp_path / "scenario.yaml"
    path.write_text(
        yaml.safe_dump(
            {
                "schema_version": 1,
                "scenario_id": "RAG-01",
                "question": "Restore workspace?",
                "model_overrides": {"generate_answer": [generation()]},
            }
        ),
        encoding="utf-8",
    )
    scenario = load_scenario(path, kb)
    assert scenario.model_overrides.generate_answer[0].invocation == 1
    result = asyncio.run(build_agent(scenario, kb).run(scenario.question))
    assert result.answer == "Injected answer"


def test_correct_references_have_no_overrides(scenarios):
    assert set(scenarios) == {f"RAG-{i:02}" for i in range(1, 8)}
    for name in ["RAG-01", "RAG-05", "RAG-07"]:
        assert scenarios[name].retrieval_overrides == []
        assert scenarios[name].model_overrides.generate_answer == []
    assert scenarios["RAG-03"].model_overrides.generate_answer == []
    for name in ["RAG-04", "RAG-06"]:
        assert scenarios[name].retrieval_overrides == []
        assert len(scenarios[name].model_overrides.generate_answer) == 1


def test_architecture_has_no_scenario_inputs_in_agent_or_model():
    assert set(inspect.signature(RAGAgent).parameters) == {
        "model",
        "retriever",
        "max_retrieval_attempts",
    }
    for module in [agent_module, model_module]:
        source = inspect.getsource(module)
        for forbidden in [
            "scenario_id",
            "ScenarioConfig",
            "ground_truth",
            "expected_outcome",
            "RAG-0",
        ]:
            assert forbidden not in source


def test_runtime_never_reads_ground_truth(kb, monkeypatch):
    original = Path.open

    def guarded_open(path, *args, **kwargs):
        assert "ground_truth" not in path.parts, (
            "Runtime attempted to read evaluation labels"
        )
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "open", guarded_open)
    for path in sorted((DATA_DIR / "scenarios").glob("*.yaml")):
        scenario = load_scenario(path, kb)
        asyncio.run(build_agent(scenario).run(scenario.question))


def test_renaming_scenario_does_not_change_execution(kb, scenarios, results):
    for name, scenario in scenarios.items():
        renamed = scenario.model_copy(update={"scenario_id": "RAG-99"})
        assert (
            asyncio.run(build_agent(renamed, kb).run(renamed.question)) == results[name]
        )


def test_ground_truth_is_separate_and_has_required_semantics(scenarios, results):
    directory = Path(__file__).resolve().parents[1] / "ground_truth"
    paths = sorted(directory.glob("*.yaml"))
    assert {path.stem for path in paths} == set(scenarios)
    failures = {
        "RAG-02": ("search_knowledge_base", "wrong_document_retrieval"),
        "RAG-03": ("search_knowledge_base", "superseded_document_retrieval"),
        "RAG-04": ("generate_answer", "evidence_contradiction"),
        "RAG-06": ("generate_answer", "unsupported_generation"),
    }
    for path in paths:
        truth = load_ground_truth(path).model_dump(exclude_unset=True)
        name = path.stem
        assert truth["schema_version"] == 1 and truth["scenario_id"] == name
        assert truth["expected_status"] == results[name].status
        assert truth["expected_retrieval_attempts"] == len(
            results[name].context.retrieval_attempts
        )
        if name in failures:
            assert truth["expected_outcome"] == "failure"
            assert (
                truth["expected_failure"]["operation"],
                truth["expected_failure"]["category"],
            ) == failures[name]
        else:
            assert (
                truth["expected_outcome"] == "correct"
                and truth["expected_failure"] is None
            )
        with pytest.raises(ValidationError):
            ScenarioConfig.model_validate(truth)
