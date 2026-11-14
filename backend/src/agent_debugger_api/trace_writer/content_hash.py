import hashlib
import json

from agent_debugger_api.contracts.span_record import SpanRecord

# Fields about the delivery, not about the span itself.
EXCLUDED_FIELDS = {"project_id", "received_at", "protocol_version"}


def content_hash(record: SpanRecord) -> str:
    # 1. Span -> plain dict, without the delivery fields.
    data = record.model_dump(mode="json", exclude=EXCLUDED_FIELDS)
    # 2. Dict -> text, always written the same way (sorted keys, no spaces).
    text = json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    # 3. Text -> 64-character fingerprint.
    return hashlib.sha256(text.encode("utf-8")).hexdigest()
