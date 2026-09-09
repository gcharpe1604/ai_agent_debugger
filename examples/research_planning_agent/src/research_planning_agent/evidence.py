import json
from pathlib import Path

from .models import EvidenceItem

DATA_DIR = Path(__file__).resolve().parent / "data"


def read_json(path: Path):
    def unique_keys(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"Duplicate JSON key: {key}")
            result[key] = value
        return result

    def reject_constant(value):
        raise ValueError(f"Invalid JSON constant: {value}")

    return json.loads(
        path.read_text(encoding="utf-8"),
        object_pairs_hook=unique_keys,
        parse_constant=reject_constant,
    )


def load_evidence(path: Path = DATA_DIR / "evidence.json") -> list[EvidenceItem]:
    raw = read_json(path)
    if not isinstance(raw, list) or not raw:
        raise ValueError("Evidence corpus must be a nonempty list")
    items = [EvidenceItem.model_validate(item) for item in raw]
    by_id = {item.evidence_id: item for item in items}
    if len(by_id) != len(items):
        raise ValueError("Duplicate evidence_id")
    for item in items:
        numeric = item.topic in {"capacity", "power", "cost", "visitors"}
        if numeric and (type(item.value) is not int or item.value < 0):
            raise ValueError("Numeric evidence must contain a nonnegative integer")
        if item.topic == "access" and item.value not in {"open", "closed"}:
            raise ValueError("Invalid access value")
        if item.topic == "permit" and item.value not in {"approved", "pending"}:
            raise ValueError("Invalid permit value")
        for previous_id in item.supersedes:
            previous = by_id.get(previous_id)
            if (
                previous is None
                or previous.fact != item.fact
                or previous.published_on >= item.published_on
                or previous.version >= item.version
            ):
                raise ValueError(
                    "Supersession must reference an older same-fact record"
                )
    return sorted(items, key=lambda item: item.evidence_id)


class EvidenceSource:
    def __init__(self, items: list[EvidenceItem]):
        self.items = [item.model_copy(deep=True) for item in items]

    def collect(self, step, prerequisites):
        if step.fact.endswith(".permit"):
            access = step.fact.replace(".permit", ".access")
            if not prerequisites.get(access):
                raise ValueError("Permit lookup requires resolved access evidence")
        site, topic = step.fact.split(".")
        return [
            item.model_copy(deep=True)
            for item in self.items
            if item.site == site
            and (
                item.topic == topic
                or (topic == "capacity" and item.topic == "visitors")
            )
            and item.availability == step.query
        ]
