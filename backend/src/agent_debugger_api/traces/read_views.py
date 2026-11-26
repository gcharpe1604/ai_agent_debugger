"""JSON shapes of the durable read API. Pure functions over stored spans and the tree.

Nanosecond timestamps are sent as decimal strings: they do not fit a
JavaScript number (2^53), and the frontend does its arithmetic in BigInt.
`project_id` is never sent; the route's project segment already names it.
"""

from __future__ import annotations

from agent_debugger_api.contracts import RunSummary, StatusCode, StoredSpan
from agent_debugger_api.traces.reconstruction import Reconstruction, TreeNode, error_leaves


def run_from_summary(run: RunSummary) -> dict:
    """One row of the run list (query-time aggregate, clickhouse-span-record.md §4)."""
    return {
        "trace_id": run.trace_id,
        "name": run.root_name,
        "missing_root": run.missing_root,
        "status": run.root_status,
        "service": run.service_name or None,
        "execution_mode": run.execution_mode or None,
        "start_time_unix_nano": str(run.run_started_at),
        "end_time_unix_nano": str(run.run_ended_at),
        "span_count": run.span_count,
        "error_span_count": run.error_span_count,
        # Same shape as run_from_tree; null unless the run failed.
        "first_error": None
        if run.first_error is None
        else {
            "span_id": run.first_error.span_id,
            "span_name": run.first_error.span_name,
            "operation_type": run.first_error.operation_type,
            "error_type": run.first_error.error_type,
            "originating_error_span_count": run.first_error.originating_error_span_count,
        },
    }


def run_from_tree(trace_id: str, tree: Reconstruction) -> dict:
    """The same summary computed from one trace, plus what only a full read knows."""
    nodes = tree.nodes
    by_id = {n.span_id: n for n in nodes}
    # Earliest span that recorded no parent, like argMinIf(..., parent_span_id IS NULL) in the run list.
    root = next((by_id[sid] for sid in tree.top_level if by_id[sid].recorded_parent_span_id is None), None)
    record = root.placement.record if root else None
    versions = [v.record for n in nodes for v in n.versions]
    leaves = error_leaves(tree)
    first = leaves[0].placement.record if leaves else None

    def errored(node: TreeNode) -> bool:
        return any(v.record.status_code is StatusCode.ERROR for v in node.versions)

    recovered = any(
        n.placement.record.status_code is StatusCode.OK
        and n.placement.record.retry_of_span_id in by_id
        and errored(by_id[n.placement.record.retry_of_span_id])
        for n in nodes
    )
    return {
        "trace_id": trace_id,
        "name": record.span_name if record else None,
        "missing_root": root is None,
        "status": record.status_code.value if record else None,
        "service": (record.service_name or None) if record else None,
        "execution_mode": next((r.execution_mode for r in versions if r.execution_mode), None),
        "start_time_unix_nano": str(min(r.started_at for r in versions)),
        "end_time_unix_nano": str(max(r.ended_at for r in versions)),
        "span_count": len(nodes),
        "error_span_count": sum(errored(n) for n in nodes),
        "root_span_id": root.span_id if root else None,
        "conflicted": any(len(n.versions) > 1 for n in nodes),
        "recorded_recovered_retry": recovered,
        "first_error": None
        if first is None
        else {
            "span_id": first.span_id,
            "span_name": first.span_name,
            "operation_type": first.operation_type,
            "error_type": first.error_type or None,
            "originating_error_span_count": len(leaves),
        },
    }


def span_version(stored: StoredSpan, payloads: bool) -> dict:
    """One stored version of a span. Payload text only when asked: it can be 128 KiB each."""
    r = stored.record
    out = {
        "trace_id": r.trace_id,
        "span_id": r.span_id,
        "parent_span_id": r.parent_span_id,  # as recorded; the tree has the effective parent
        "name": r.span_name,
        "display_label": r.display_label or None,
        "operation_type": r.operation_type,
        "service": r.service_name or None,
        "execution_mode": r.execution_mode or None,
        "status": {"code": r.status_code.value, "description": r.status_description},
        "error_type": r.error_type or None,
        "start_time_unix_nano": str(r.started_at),
        "end_time_unix_nano": str(r.ended_at),
        "attempt": r.attempt,
        "retry_of_span_id": r.retry_of_span_id,
        "model": r.model,
        "provider": r.provider,
        "input_tokens": r.input_tokens,
        "output_tokens": r.output_tokens,
        "total_tokens": r.total_tokens,
        "cost": r.cost,
        "graph_node_id": r.graph_node_id or None,
        "graph_node_parent_id": r.graph_node_parent_id or None,
        "input_state": r.input_state.value,
        "output_state": r.output_state.value,
        "error_state": r.error_state.value,
        "attributes": dict(r.attributes),
        "events": [
            {"name": e.name, "time_unix_nano": str(e.time), "attributes": dict(e.attributes)} for e in r.events
        ],
        "links": [link.model_dump() for link in r.links],
        "content_hash": stored.content_hash,
        "received_at_unix_nano": str(r.received_at),
    }
    if payloads:
        out["input_payload"] = r.input_payload
        out["output_payload"] = r.output_payload
        out["error_payload"] = r.error_payload
    return out


def tree_view(tree: Reconstruction) -> dict:
    return {
        "top_level": list(tree.top_level),
        "nodes": [
            {
                "span_id": n.span_id,
                "parent_span_id": n.parent_span_id,
                "recorded_parent_span_id": n.recorded_parent_span_id,
                "depth": n.depth,
                "children": list(n.children),
                "flags": list(n.flags),
                "versions": [v.content_hash for v in n.versions],
            }
            for n in tree.nodes
        ],
        "warnings": [
            {"code": w.code, "span_ids": list(w.span_ids), "message": w.message} for w in tree.warnings
        ],
    }


def span_reference(node: TreeNode) -> dict:
    r = node.placement.record
    return {
        "span_id": r.span_id,
        "name": r.span_name,
        "operation_type": r.operation_type,
        "status": {"code": r.status_code.value},
        "attempt": r.attempt,
    }
