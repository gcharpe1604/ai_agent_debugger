import math
import re
from collections import Counter
from typing import Protocol

from .knowledge_base import KnowledgeBase
from .models import RetrievalResult

STOP_WORDS = frozenset(
    [
        "a",
        "an",
        "and",
        "are",
        "as",
        "at",
        "be",
        "by",
        "can",
        "for",
        "from",
        "how",
        "i",
        "in",
        "is",
        "it",
        "of",
        "on",
        "only",
        "or",
        "that",
        "the",
        "their",
        "this",
        "to",
        "up",
        "when",
        "will",
        "with",
        "novacloud",
    ]
)


def tokenize(text: str) -> list[str]:
    return [
        word[:-1] if word.endswith("s") and len(word) > 3 else word
        for word in re.findall(r"[a-z0-9]+", text.lower())
        if word not in STOP_WORDS
    ]


class Retriever(Protocol):
    async def search(
        self, query: str, top_k: int = 3, *, attempt_number: int = 1
    ) -> list[RetrievalResult]: ...


class LocalRetriever:
    """BM25 over current documents, with document ID as the stable tie breaker."""

    def __init__(self, knowledge_base: KnowledgeBase):
        self.documents = [d for d in knowledge_base.documents if d.status == "current"]
        self.terms = [
            Counter(tokenize(d.title + " " + d.content)) for d in self.documents
        ]
        self.lengths = [sum(terms.values()) for terms in self.terms]
        self.average_length = sum(self.lengths) / max(len(self.lengths), 1) or 1
        self.frequencies = Counter(term for terms in self.terms for term in terms)

    async def search(
        self, query: str, top_k: int = 3, *, attempt_number: int = 1
    ) -> list[RetrievalResult]:
        if type(top_k) is not int or top_k < 1:
            raise ValueError("top_k must be a positive integer")
        query_terms = sorted(set(tokenize(query)))
        results = []
        for document, terms, length in zip(self.documents, self.terms, self.lengths):
            score = 0.0
            for term in query_terms:
                count = terms[term]
                if count:
                    frequency = self.frequencies[term]
                    idf = math.log1p(
                        (len(self.documents) - frequency + 0.5) / (frequency + 0.5)
                    )
                    score += (
                        idf
                        * count
                        * 2.5
                        / (count + 1.5 * (0.25 + 0.75 * length / self.average_length))
                    )
            if score > 0:
                results.append(RetrievalResult(document=document, score=score))
        return sorted(
            results, key=lambda result: (-result.score, result.document.document_id)
        )[:top_k]
