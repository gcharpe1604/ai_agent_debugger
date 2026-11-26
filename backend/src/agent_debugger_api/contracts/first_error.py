"""First error of a run in the run list: the same rule as `traces.reconstruction.error_leaves`.

The run list is one aggregate query, so it has no reconstructed tree. It
returns, per trace, the ERROR spans and the recorded (span_id, parent_span_id)
links, and this module applies the rule to them. Both `TraceStore`
implementations call it, so the rule lives in one place.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class RunFirstError:
    """Earliest ERROR span with no ERROR descendant. A recorded fact, not a cause."""

    span_id: str
    span_name: str
    operation_type: str
    error_type: str | None
    originating_error_span_count: int  # ERROR spans with no ERROR descendant


# (span_id, started_at ns, span_name, operation_type, error_type)
ErrorSpan = tuple[str, int, str, str, str]


def run_first_error(
    root_status: str | None,
    error_spans: Iterable[ErrorSpan],
    links: Iterable[tuple[str, str | None]],
) -> RunFirstError | None:
    """`None` unless the run failed (its root span is ERROR).

    A completed run is `None` even when it recorded errors: a recovered retry is
    not a failure. A run whose root has not arrived is `None` too: its outcome
    is unknown. `links` are the recorded parent links of every span; a span with
    conflicting versions may have more than one, and each is followed. Cycles
    stop at the first span seen twice.
    """
    if root_status != "ERROR":
        return None
    first_seen: dict[str, ErrorSpan] = {}
    for span in error_spans:  # one row per stored version: keep each span's earliest
        if span[0] not in first_seen or span[1] < first_seen[span[0]][1]:
            first_seen[span[0]] = span
    if not first_seen:
        return None
    parents: dict[str, set[str]] = {}
    for span_id, parent in links:
        if parent:
            parents.setdefault(span_id, set()).add(parent)
    carries: set[str] = set()  # spans with an ERROR descendant
    for span_id in first_seen:
        stack = list(parents.get(span_id, ()))
        while stack:
            parent = stack.pop()
            if parent in carries:
                continue
            carries.add(parent)
            stack.extend(parents.get(parent, ()))
    leaves = sorted((s for s in first_seen.values() if s[0] not in carries), key=lambda s: (s[1], s[0]))
    if not leaves:  # every ERROR span is in a parent cycle with another one
        return None
    span_id, _, name, operation_type, error_type = leaves[0]
    return RunFirstError(span_id, name, operation_type, error_type or None, len(leaves))
