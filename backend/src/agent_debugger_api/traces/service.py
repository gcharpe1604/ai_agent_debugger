from datetime import datetime, timezone

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
        "recorded_recovered_retry": any(span["status"]["code"] == "OK" and spans.get(span["attributes"].get("debugger.retry_of"), {}).get("status", {}).get("code") == "ERROR" for span in ordered),
        "completeness": "Unknown",
    }
