from pathlib import Path

from .models import KnowledgeDocument
from .yaml_io import load_yaml


class KnowledgeBase:
    def __init__(self, directory: Path):
        self._documents: dict[str, KnowledgeDocument] = {}
        for path in sorted(directory.glob("*.md")):
            lines = path.read_text(encoding="utf-8").splitlines()
            if not lines or lines[0] != "---" or "---" not in lines[1:]:
                raise ValueError(f"{path.name}: Markdown front matter is required")
            end = lines.index("---", 1)
            metadata = load_yaml("\n".join(lines[1:end]))
            if not isinstance(metadata, dict) or "content" in metadata:
                raise ValueError(
                    f"{path.name}: expected document metadata without content"
                )
            document = KnowledgeDocument.model_validate(
                {**metadata, "content": "\n".join(lines[end + 1 :]).strip()}
            )
            if document.document_id in self._documents:
                raise ValueError(f"Duplicate document ID: {document.document_id}")
            self._documents[document.document_id] = document
        if not self._documents:
            raise ValueError(f"No knowledge documents found in {directory}")
        for document in self.documents:
            if document.superseded_by:
                replacement = self.get(document.superseded_by)
                if (
                    replacement.topic != document.topic
                    or replacement.status != "current"
                ):
                    raise ValueError(
                        "Replacement must be current and cover the same topic"
                    )

    @property
    def documents(self) -> list[KnowledgeDocument]:
        return list(self._documents.values())

    def get(self, document_id: str) -> KnowledgeDocument:
        try:
            return self._documents[document_id]
        except KeyError as exc:
            raise ValueError(f"Unknown document ID: {document_id}") from exc
