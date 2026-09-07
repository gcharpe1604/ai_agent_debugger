import pytest
from pydantic import ValidationError

from rag_agent.controlled_model import CONTROLLED_FACT_VALUES, DOCUMENT_FACT_SUPPORT
from rag_agent.factory import DATA_DIR
from rag_agent.knowledge_base import KnowledgeBase
from rag_agent.models import KnowledgeDocument
from rag_agent.yaml_io import load_yaml


def test_documents_and_replacement(kb):
    assert len(kb.documents) == 10
    assert {d.document_id for d in kb.documents} == {f"KB-{i:02}" for i in range(1, 11)}
    assert all(
        d.title and d.content and d.topic and d.version > 0 for d in kb.documents
    )
    assert kb.get("KB-02").status == "superseded"
    assert kb.get("KB-02").superseded_by == "KB-01"
    assert kb.get("KB-01").status == "current"
    assert "does not apply to deleted workspaces" in kb.get("KB-03").content


def test_catalog_agrees_with_source_documents(kb):
    for (document_id, fact), value in CONTROLLED_FACT_VALUES.items():
        assert value in kb.get(document_id).content, (document_id, fact, value)
        assert fact in DOCUMENT_FACT_SUPPORT[document_id]


def test_duplicate_documents_rejected(tmp_path):
    source = (DATA_DIR / "knowledge_base" / "KB-01-workspace-deletion.md").read_text(
        encoding="utf-8"
    )
    (tmp_path / "first.md").write_text(source, encoding="utf-8")
    (tmp_path / "duplicate.md").write_text(source, encoding="utf-8")
    with pytest.raises(ValueError, match="Duplicate document ID"):
        KnowledgeBase(tmp_path)


@pytest.mark.parametrize(
    "updates",
    [
        {"version": 0},
        {"version": "2"},
        {"status": "obsolete"},
        {"title": " "},
        {"unknown": True},
        {"status": "superseded"},
        {"superseded_by": "KB-01"},
    ],
)
def test_invalid_metadata_rejected(kb, updates):
    with pytest.raises(ValidationError):
        KnowledgeDocument.model_validate({**kb.get("KB-01").model_dump(), **updates})


@pytest.mark.parametrize(
    "content", ["no metadata", "---\ntitle: missing end", "---\n[]\n---\ntext"]
)
def test_malformed_front_matter_rejected(tmp_path, content):
    (tmp_path / "bad.md").write_text(content, encoding="utf-8")
    with pytest.raises(ValueError):
        KnowledgeBase(tmp_path)


def test_empty_directory_and_unknown_id(tmp_path, kb):
    with pytest.raises(ValueError, match="No knowledge documents"):
        KnowledgeBase(tmp_path)
    with pytest.raises(ValueError, match="Unknown document ID"):
        kb.get("KB-99")


def test_missing_replacement_rejected(tmp_path):
    source = (DATA_DIR / "knowledge_base" / "KB-02-workspace-deletion-v1.md").read_text(
        encoding="utf-8"
    )
    (tmp_path / "old.md").write_text(source, encoding="utf-8")
    with pytest.raises(ValueError, match="Unknown document ID: KB-01"):
        KnowledgeBase(tmp_path)


def test_yaml_rejects_duplicate_keys_and_python_objects():
    import yaml

    for content in ["key: first\nkey: second", "!!python/object:builtins.object {}"]:
        with pytest.raises(yaml.YAMLError):
            load_yaml(content)
