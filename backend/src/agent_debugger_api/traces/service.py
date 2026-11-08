from datetime import datetime, timezone

from agent_debugger_api.traces.schemas import FirstError


def first_error(spans):
    """Earliest ERROR span with no ERROR descendants. A recorded fact, not a cause.

    Ancestors often carry a descendant's error, even through OK spans in
    between (run ERROR > agent OK > tool ERROR), so only the deepest recorded
    error sites qualify. "originating_error_span_count" is the number of those
    originating ERROR spans (ERROR spans with no ERROR descendant), including the
    chosen one. Earliest start wins; span ID breaks ties so the choice is stable
    across reads. Missing parents and parent cycles end the ancestor walk.
    """
    errors = [span for span in spans.values() if span["status"]["code"] == "ERROR"]
    carries_descendant_error = set()
    for span in errors:
        seen, parent = {span["span_id"]}, spans.get(span["parent_span_id"])
        while parent is not None and parent["span_id"] not in seen:
            carries_descendant_error.add(parent["span_id"])
            seen.add(parent["span_id"])
            parent = spans.get(parent["parent_span_id"])
    leaves = sorted((span for span in errors if span["span_id"] not in carries_descendant_error),
                    key=lambda span: (int(span["start_time_unix_nano"]), span["span_id"]))
    if not leaves:
        return None
    chosen = leaves[0]
    exception = next((event["attributes"] for event in chosen["events"] if event["name"] == "exception"), {})
    return FirstError(
        span_id=chosen["span_id"],
        span_name=chosen["name"],
        operation_type=chosen["operation_type"],
        exception_type=exception.get("exception.type"),
        originating_error_span_count=len(leaves),
    ).model_dump()


def run_summary(trace_id, spans):
    ordered = sorted(spans.values(), key=lambda span: (int(span["start_time_unix_nano"]), span["span_id"]))
    root = next((span for span in ordered if span["parent_span_id"] is None and span["operation_type"] == "run"), None)
    first = root or ordered[0]
    return {
        "trace_id": trace_id,
        "name": first["name"],
        "root_span_id": root["span_id"] if root else None,
        "start_time_unix_nano": first["start_time_unix_nano"],
        "end_time_unix_nano": root["end_time_unix_nano"] if root else None,
        "started_at": datetime.fromtimestamp(int(first["start_time_unix_nano"]) / 1e9, timezone.utc).isoformat().replace("+00:00", "Z"),
        "status": root["status"]["code"] if root else "UNSET",
        "service": first["resource"].get("service.name", "Not recorded"),
        "execution_mode": first["attributes"].get("debugger.execution.mode"),
        "local_dependencies": first["attributes"].get("debugger.local_dependencies"),
        "captured_span_count": len(ordered),
        "recorded_error_spans": sum(span["status"]["code"] == "ERROR" for span in ordered),
        "first_error": first_error(spans),
        "recorded_recovered_retry": any(span["status"]["code"] == "OK" and spans.get(span["attributes"].get("debugger.retry_of"), {}).get("status", {}).get("code") == "ERROR" for span in ordered),
        "completeness": "Unknown",
    }
