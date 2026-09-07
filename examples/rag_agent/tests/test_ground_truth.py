from pathlib import Path

import pytest
import yaml
from ground_truth_schema import GroundTruth, load_ground_truth
from pydantic import ValidationError

DIRECTORY = Path(__file__).resolve().parents[1] / "ground_truth"


@pytest.mark.parametrize(
    "scenario_id, expected_facts, faulty_facts",
    [
        ("RAG-01", {"workspace_restore_days": 14}, None),
        ("RAG-02", {"workspace_restore_days": 14}, None),
        ("RAG-03", {"workspace_restore_days": 14}, {"workspace_restore_days": 30}),
        ("RAG-04", {"workspace_restore_days": 14}, {"workspace_restore_days": 30}),
        ("RAG-05", {"data_residency_evidence_available": False}, None),
        (
            "RAG-06",
            {"data_residency_evidence_available": False, "evidence_sufficient": False},
            {"india_only_storage_guarantee": True},
        ),
        (
            "RAG-07",
            {
                "downgrade_effective_time": "next billing renewal",
                "export_link_validity_hours": 48,
            },
            None,
        ),
    ],
)
def test_label_facts_preserve_existing_semantics(
    scenario_id, expected_facts, faulty_facts, kb
):
    truth = load_ground_truth(DIRECTORY / f"{scenario_id}.yaml")
    assert truth.expected_facts.model_dump(exclude_unset=True) == expected_facts
    observed = truth.observed_faulty_facts
    assert (
        observed.model_dump(exclude_unset=True) if observed else None
    ) == faulty_facts
    for document_id in truth.important_document_ids:
        kb.get(document_id)
    if truth.correct_source:
        assert truth.correct_source in truth.important_document_ids
    for document_id in truth.wrongly_supplied_sources or []:
        assert document_id in truth.important_document_ids


@pytest.mark.parametrize(
    "updates",
    [
        {"schema_version": 2},
        {"schema_version": "1"},
        {"schema_version": True},
        {"scenario_id": "RAG-99"},
        {"expected_outcome": "unknown"},
        {"expected_outcome": "correct"},
        {"expected_failure": None},
        {
            "expected_failure": {
                "operation": "generate_answer",
                "category": "wrong_document_retrieval",
            }
        },
        {
            "expected_failure": {
                "operation": "search_knowledge_base",
                "category": "unknown",
                "retrieval_attempts": [1],
            }
        },
        {
            "expected_failure": {
                "operation": "search_knowledge_base",
                "category": "wrong_document_retrieval",
            }
        },
        {
            "expected_failure": {
                "operation": "search_knowledge_base",
                "category": "wrong_document_retrieval",
                "retrieval_attempts": [True],
            }
        },
        {
            "expected_failure": {
                "operation": "search_knowledge_base",
                "category": "wrong_document_retrieval",
                "retrieval_attempts": [1, 1],
            }
        },
        {
            "expected_failure": {
                "operation": "search_knowledge_base",
                "category": "wrong_document_retrieval",
                "retrieval_attempts": [1],
                "extra": True,
            }
        },
        {"expected_retrieval_attempts": 1},
        {"expected_retrieval_attempts": 3},
        {"expected_retrieval_attempts": True},
        {"expected_status": "success"},
        {"important_operations": []},
        {"important_operations": ["search"]},
        {"important_operations": ["generate_answer"]},
        {"important_document_ids": ["KB-99"]},
        {"important_document_ids": "KB-01"},
        {"correct_source": "KB-99"},
        {"correct_source": None},
        {"wrongly_supplied_sources": []},
        {"expected_facts": {}},
        {"expected_facts": {"workspace_restore_days": "14"}},
        {"expected_facts": {"workspace_restore_days": True}},
        {"expected_facts": {"workspace_restore_days": 0}},
        {"expected_facts": {"workspace_restore_days": None}},
        {"expected_facts": {"data_residency_evidence_available": "false"}},
        {"expected_facts": {"invented_fact": 14}},
        {"observed_faulty_facts": {"india_only_storage_guarantee": "true"}},
        {"observed_faulty_facts": {"invented_fact": True}},
        {"required_facts": ["invented_fact"]},
        {"expected_behavior": "answer"},
        {"notes": " "},
        {"extra": True},
    ],
)
def test_malformed_labels_rejected_at_load(tmp_path, updates):
    payload = load_ground_truth(DIRECTORY / "RAG-02.yaml").model_dump(
        exclude_unset=True
    )
    path = tmp_path / "RAG-02.yaml"
    path.write_text(yaml.safe_dump({**payload, **updates}), encoding="utf-8")
    with pytest.raises(ValidationError):
        load_ground_truth(path)


@pytest.mark.parametrize(
    "field",
    [
        "schema_version",
        "scenario_id",
        "expected_outcome",
        "expected_failure",
        "important_operations",
        "important_document_ids",
        "expected_status",
        "expected_retrieval_attempts",
        "expected_facts",
    ],
)
def test_missing_required_fields_rejected(field):
    payload = load_ground_truth(DIRECTORY / "RAG-01.yaml").model_dump(
        exclude_unset=True
    )
    del payload[field]
    with pytest.raises(ValidationError):
        GroundTruth.model_validate(payload)


@pytest.mark.parametrize(
    "extra_yaml",
    [
        "schema_version: 1\n",
        "expected_facts:\n  workspace_restore_days: 14\n  workspace_restore_days: 30\n",
    ],
)
def test_duplicate_yaml_keys_rejected(tmp_path, extra_yaml):
    source = (DIRECTORY / "RAG-01.yaml").read_text(encoding="utf-8")
    # Remove the original facts so the second case exercises a nested duplicate.
    source = (
        source.split("expected_facts:")[0]
        if extra_yaml.startswith("expected_facts:")
        else source
    )
    path = tmp_path / "RAG-01.yaml"
    path.write_text(source + extra_yaml, encoding="utf-8")
    with pytest.raises(yaml.YAMLError, match="unique string mapping keys"):
        load_ground_truth(path)


def test_label_filename_must_match_id(tmp_path):
    path = tmp_path / "RAG-02.yaml"
    path.write_text(
        (DIRECTORY / "RAG-01.yaml").read_text(encoding="utf-8"), encoding="utf-8"
    )
    with pytest.raises(ValueError, match="filename and scenario_id disagree"):
        load_ground_truth(path)
