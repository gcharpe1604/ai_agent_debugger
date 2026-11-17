"""Bounded input snapshot and deterministic facts (`docs/proposals/investigator.md` §3, §4).

`build_snapshot` turns one `TraceRead` into the only document the provider and
the grounding step see. It is deterministic: the same stored spans give the
same bytes whatever order they arrive in. Structure comes from parent IDs and
start times, never from `received_at`.

Limits are the proposal's [P] values (`SnapshotLimits`); they are not a user
decision yet (D5).

Differences from the proposal text, kept small and listed in the handoff:
- a rendered span also carries `links`, because grounding rule R7 checks them;
- a retry group with more than one attempt and no ERROR attempt has outcome
  `no_error` (§4 names only `recovered`, `exhausted`, `single`); groups of one
  attempt are not emitted;
- `facts.dangling_retry_span_ids` lists spans whose `retry_of_span_id` is not
  in the trace (test 16 asks for it to be reported).
"""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from dataclasses import dataclass
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from ..contracts import PayloadState, SpanRecord, StatusCode, TraceRead

SCHEMA_VERSION = 1
REDACTED_MARKER = "[redacted]"
READABLE_STATES = frozenset({PayloadState.CAPTURED, PayloadState.TRUNCATED, PayloadState.REDACTED})
HASH_PREFIX = 12  # hex chars of content_hash shown for a conflicted span

# Reduction names, in the order §3.3 applies them.
DROPPED_EXCERPTS = "dropped_nondecisive_payload_excerpts"
COLLAPSED_LEAVES = "collapsed_ok_leaf_spans"
SHRUNK_EXCERPTS = "shrunk_decisive_payload_excerpts"

_ATTRIBUTE_PREFIX = "debugger."
_ATTRIBUTE_KEYS = frozenset({"http.response.status_code"})
_STEP = "debugger.step"
_RESULT_STATUS = "debugger.result.status"


@dataclass(frozen=True)
class SnapshotLimits:
    max_spans: int = 200  # rendered entries; a conflicted span counts once per version
    max_bytes: int = 48 * 1024  # UTF-8 bytes of the snapshot JSON
    excerpt_head: int = 800
    excerpt_tail: int = 400
    reduced_head: int = 200
    reduced_tail: int = 100
    max_text: int = 256  # status description, attribute values
    max_events: int = 16
    siblings_before_error: int = 5


class InputTooLarge(Exception):
    """Still over a limit after every reduction (§3.3 step 4). No provider call is made."""

    def __init__(self, reductions: tuple[str, ...], rendered_spans: int, size_bytes: int) -> None:
        super().__init__(
            f"snapshot has {rendered_spans} rendered spans and {size_bytes} bytes after {len(reductions)} reductions"
        )
        self.reductions = reductions
        self.rendered_spans = rendered_spans
        self.size_bytes = size_bytes


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class PayloadView(_Model):
    state: PayloadState
    excerpt: str | None = None  # only for a readable state, and only when not dropped
    full_length: int  # characters of the stored payload


class SnapshotEvent(_Model):
    index: int  # the citable position: (span_id, index)
    name: str
    offset_ms: float
    attributes: dict[str, str]


class SnapshotLink(_Model):
    trace_id: str
    span_id: str
    relation: str


class SnapshotSpan(_Model):
    span_id: str
    parent_span_id: str | None = None
    depth: int
    content_hash: str | None = None  # first 12 hex chars; only for a conflicted span
    name: str
    operation_type: str
    status_code: StatusCode
    status_description: str = ""
    error_type: str = ""
    offset_ms: float  # from the run start
    duration_ms: float
    attempt: int | None = None
    retry_of_span_id: str | None = None
    model: str | None = None
    provider: str | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None
    attributes: dict[str, str]
    events: tuple[SnapshotEvent, ...]
    links: tuple[SnapshotLink, ...]
    input: PayloadView
    output: PayloadView
    error: PayloadView


class Rollup(_Model):
    """Collapsed non-decisive OK leaves under one parent. Not citable."""

    parent_span_id: str | None = None
    count: int
    operation_types: tuple[str, ...]
    first_offset_ms: float
    last_offset_ms: float


class RetryGroup(_Model):
    span_ids: tuple[str, ...]  # in attempt order; the last one decides the outcome
    outcome: Literal["recovered", "exhausted", "no_error"]
    basis: Literal["retry_of", "step_attempt"]
    step: str | None = None


class Facts(_Model):
    originating_error_span_ids: tuple[str, ...]
    retry_groups: tuple[RetryGroup, ...]
    dangling_retry_span_ids: tuple[str, ...]


class Completeness(_Model):
    payloads_captured: bool  # at least one readable input or output payload
    missing_root: bool
    multiple_roots: bool
    orphan_span_ids: tuple[str, ...]
    cycle_span_ids: tuple[str, ...]
    conflicted_span_ids: tuple[str, ...]
    reductions: tuple[str, ...]


class RunInfo(_Model):
    root_span_id: str | None = None
    execution_mode: str
    result_status: str | None = None
    started_at_ns: int
    duration_ms: float
    span_count_total: int  # distinct span IDs in the trace
    span_count_rendered: int  # distinct span IDs rendered


class Snapshot(_Model):
    schema_version: Literal[1] = SCHEMA_VERSION
    project_id: UUID
    trace_id: str
    run: RunInfo
    completeness: Completeness
    facts: Facts
    spans: tuple[SnapshotSpan, ...]  # tree pre-order, siblings by (started_at, span_id)
    rollups: tuple[Rollup, ...]

    def to_json(self) -> str:
        """Canonical form: sorted keys, compact, None fields left out."""
        return json.dumps(
            self.model_dump(mode="json", exclude_none=True),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        )

    @property
    def snapshot_hash(self) -> str:
        return hashlib.sha256(self.to_json().encode("utf-8")).hexdigest()

    def versions(self, span_id: str) -> tuple[SnapshotSpan, ...]:
        """Rendered versions of one span: one, or several when it is conflicted; () if not rendered."""
        return tuple(span for span in self.spans if span.span_id == span_id)

    def retry_group_of(self, span_id: str) -> RetryGroup | None:
        return next((group for group in self.facts.retry_groups if span_id in group.span_ids), None)


def _ms(nanoseconds: int) -> float:
    return round(nanoseconds / 1_000_000, 3)


def _excerpt(text: str, head: int, tail: int) -> str:
    if len(text) <= head + tail:
        return text
    return f"{text[:head]}…[{len(text) - head - tail} chars omitted]…{text[len(text) - tail:]}"


class _Trace:
    """Parent index, order and facts for one trace. Built once; rendering reads it."""

    def __init__(self, trace: TraceRead, limits: SnapshotLimits) -> None:
        self.limits = limits
        versions: dict[str, list[tuple[str, SpanRecord]]] = defaultdict(list)
        for stored in trace.spans:
            versions[stored.record.span_id].append((stored.content_hash, stored.record))
        for items in versions.values():
            items.sort(key=lambda item: (item[1].started_at, item[0]))
        self.versions = dict(versions)
        # Structure is read from one version per span: the earliest, then lowest hash.
        self.primary = {span_id: items[0][1] for span_id, items in self.versions.items()}
        self.conflicted = {
            span_id
            for span_id, items in self.versions.items()
            if len(items) > 1 or span_id in trace.conflicted_span_ids
        }
        self.error = {
            span_id: any(record.status_code is StatusCode.ERROR for _, record in items)
            for span_id, items in self.versions.items()
        }
        self.run_start = min(record.started_at for record in self.primary.values())
        self.run_end = max(record.ended_at for items in self.versions.values() for _, record in items)
        self._index()
        self._facts()
        self._decisive()

    def key(self, span_id: str) -> tuple[int, str]:
        return (self.primary[span_id].started_at, span_id)

    def _index(self) -> None:
        primary = self.primary
        parent = {span_id: record.parent_span_id for span_id, record in primary.items()}
        self.roots = sorted((s for s in primary if parent[s] is None), key=self.key)
        self.orphans = sorted((s for s in primary if parent[s] is not None and parent[s] not in primary), key=self.key)

        children: dict[str, list[str]] = defaultdict(list)
        for span_id, parent_id in parent.items():
            if parent_id in primary:
                children[parent_id].append(span_id)

        reachable, stack = set(), self.roots + self.orphans
        while stack:
            span_id = stack.pop()
            if span_id not in reachable:
                reachable.add(span_id)
                stack.extend(children[span_id])

        # What is left hangs on a parent cycle. Each cycle is entered at its
        # earliest member; that member's parent edge is cut so the walk ends.
        on_cycle, entries = set(), []
        for span_id in sorted(set(primary) - reachable, key=self.key):
            if span_id in on_cycle:
                continue
            seen, current = [], span_id
            while current not in seen and current not in reachable and current not in on_cycle:
                seen.append(current)
                current = parent[current]
            if current in seen:
                members = seen[seen.index(current):]
                on_cycle.update(members)
                entries.append(min(members, key=self.key))
        self.cycle_span_ids = sorted(on_cycle)
        for entry in entries:
            children[parent[entry]].remove(entry)
        self.tops = sorted(self.roots + self.orphans + entries, key=self.key)
        self.tree_parent = {s: (parent[s] if parent[s] in primary and s not in entries else None) for s in primary}
        self.children = {s: sorted(children[s], key=self.key) for s in primary}

        self.order, self.depth = [], {}
        stack = [(span_id, 0) for span_id in reversed(self.tops)]
        while stack:
            span_id, depth = stack.pop()
            self.order.append(span_id)
            self.depth[span_id] = depth
            stack.extend((child, depth + 1) for child in reversed(self.children[span_id]))
        self.position = {span_id: index for index, span_id in enumerate(self.order)}

    def _facts(self) -> None:
        primary = self.primary
        error_below: dict[str, bool] = {}
        for span_id in reversed(self.order):  # children before parents
            error_below[span_id] = any(self.error[c] or error_below[c] for c in self.children[span_id])
        self.originating = [s for s in self.order if self.error[s] and not error_below[s]]

        # Chains: connected by retry_of_span_id.
        leader = {span_id: span_id for span_id in primary}

        def find(span_id: str) -> str:
            while leader[span_id] != span_id:
                leader[span_id] = leader[leader[span_id]]
                span_id = leader[span_id]
            return span_id

        dangling = []
        for span_id, record in primary.items():
            target = record.retry_of_span_id
            if target is None:
                continue
            if target in primary:
                leader[find(span_id)] = find(target)
            else:
                dangling.append(span_id)
        self.dangling = sorted(dangling)
        chains: dict[str, list[str]] = defaultdict(list)
        for span_id in primary:
            chains[find(span_id)].append(span_id)
        groups = [(members, "retry_of") for members in chains.values() if len(members) > 1]
        chained = {span_id for members, _ in groups for span_id in members}

        # Fallback: same parent, same debugger.step, distinct attempt numbers.
        by_step: dict[tuple[str | None, str], list[str]] = defaultdict(list)
        for span_id, record in primary.items():
            step = record.attributes.get(_STEP)
            if span_id not in chained and step and record.attempt is not None:
                by_step[(record.parent_span_id, step)].append(span_id)
        for members in by_step.values():
            attempts = {primary[span_id].attempt for span_id in members}
            if len(members) > 1 and len(attempts) == len(members):
                groups.append((members, "step_attempt"))

        retry_groups = []
        for members, basis in groups:
            ordered = sorted(
                members,
                key=lambda s: (-1 if primary[s].attempt is None else primary[s].attempt, primary[s].started_at, s),
            )
            if self.error[ordered[-1]]:
                outcome = "exhausted"
            elif any(self.error[span_id] for span_id in ordered[:-1]):
                outcome = "recovered"
            else:
                outcome = "no_error"
            steps = {primary[span_id].attributes.get(_STEP) for span_id in ordered}
            retry_groups.append(
                RetryGroup(
                    span_ids=tuple(ordered),
                    outcome=outcome,
                    basis=basis,
                    step=steps.pop() if len(steps) == 1 else None,
                )
            )
        retry_groups.sort(key=lambda group: min(self.position[span_id] for span_id in group.span_ids))
        self.retry_groups = tuple(retry_groups)

    def _decisive(self) -> None:
        """§3.3: spans that are never dropped and never collapsed."""
        primary = self.primary
        decisive = set(self.tops) | self.conflicted
        for span_id in primary:
            if self.error[span_id]:
                current = span_id  # the span and all its ancestors; the tree has no cycle
                while current is not None:
                    decisive.add(current)
                    current = self.tree_parent[current]
        for group in self.retry_groups:
            decisive.update(group.span_ids)
        for span_id in self.originating:
            parent = self.tree_parent[span_id]
            siblings = self.children[parent] if parent is not None else self.tops
            before = [s for s in siblings if self.key(s) < self.key(span_id)]
            decisive.update(before[-self.limits.siblings_before_error:])
        for top in self.tops:
            # The step that produced the final output: last-ending model/custom span below the top.
            best, stack = None, list(self.children[top])
            while stack:
                span_id = stack.pop()
                stack.extend(self.children[span_id])
                record = primary[span_id]
                if record.operation_type in ("model", "custom"):
                    candidate = (record.ended_at, span_id)
                    if best is None or candidate > best:
                        best = candidate
            if best is not None:
                decisive.add(best[1])
        for span_id in sorted(decisive):
            for _, record in self.versions[span_id]:
                decisive.update(link.span_id for link in record.links if link.span_id in primary)
        self.decisive = decisive

    def render(self, project_id: UUID, trace_id: str, reductions: tuple[str, ...]) -> Snapshot:
        limits, primary = self.limits, self.primary
        drop, collapse, shrink = (name in reductions for name in (DROPPED_EXCERPTS, COLLAPSED_LEAVES, SHRUNK_EXCERPTS))
        collapsed = set()
        if collapse:
            collapsed = {
                span_id
                for span_id in primary
                if span_id not in self.decisive
                and not self.children[span_id]
                and all(record.status_code is StatusCode.OK for _, record in self.versions[span_id])
            }

        def view(state: PayloadState, text: str, span_id: str) -> PayloadView:
            excerpt = None
            if state in READABLE_STATES:
                if span_id in self.decisive:
                    head, tail = (limits.reduced_head, limits.reduced_tail) if shrink else (limits.excerpt_head, limits.excerpt_tail)
                    excerpt = _excerpt(text, head, tail)
                elif not drop:
                    excerpt = _excerpt(text, limits.excerpt_head, limits.excerpt_tail)
            return PayloadView(state=state, excerpt=excerpt, full_length=len(text))

        spans = []
        for span_id in self.order:
            if span_id in collapsed:
                continue
            for content_hash, record in sorted(self.versions[span_id], key=lambda item: item[0]):
                events = sorted(enumerate(record.events), key=lambda item: (item[1].time, item[1].name, item[0]))
                spans.append(
                    SnapshotSpan(
                        span_id=span_id,
                        parent_span_id=record.parent_span_id,
                        depth=self.depth[span_id],
                        content_hash=content_hash[:HASH_PREFIX] if span_id in self.conflicted else None,
                        name=record.span_name,
                        operation_type=record.operation_type,
                        status_code=record.status_code,
                        status_description=record.status_description[: limits.max_text],
                        error_type=record.error_type,
                        offset_ms=_ms(record.started_at - self.run_start),
                        duration_ms=_ms(record.ended_at - record.started_at),
                        attempt=record.attempt,
                        retry_of_span_id=record.retry_of_span_id,
                        model=record.model,
                        provider=record.provider,
                        input_tokens=record.input_tokens,
                        output_tokens=record.output_tokens,
                        total_tokens=record.total_tokens,
                        attributes={
                            key: value[: limits.max_text]
                            for key, value in sorted(record.attributes.items())
                            if key.startswith(_ATTRIBUTE_PREFIX) or key in _ATTRIBUTE_KEYS
                        },
                        events=tuple(
                            SnapshotEvent(
                                index=index,
                                name=event.name,
                                offset_ms=_ms(event.time - self.run_start),
                                attributes={k: v[: limits.max_text] for k, v in sorted(event.attributes.items())},
                            )
                            for index, (_, event) in enumerate(events[: limits.max_events])
                        ),
                        links=tuple(
                            SnapshotLink(trace_id=link.trace_id, span_id=link.span_id, relation=link.relation)
                            for link in record.links
                        ),
                        input=view(record.input_state, record.input_payload, span_id),
                        output=view(record.output_state, record.output_payload, span_id),
                        error=view(record.error_state, record.error_payload, span_id),
                    )
                )

        by_parent: dict[str | None, list[str]] = defaultdict(list)
        for span_id in self.order:
            if span_id in collapsed:
                by_parent[self.tree_parent[span_id]].append(span_id)
        rollups = tuple(
            Rollup(
                parent_span_id=parent,
                count=len(members),
                operation_types=tuple(sorted({primary[s].operation_type for s in members})),
                first_offset_ms=_ms(min(primary[s].started_at for s in members) - self.run_start),
                last_offset_ms=_ms(max(primary[s].started_at for s in members) - self.run_start),
            )
            for parent, members in by_parent.items()
        )

        root = self.roots[0] if self.roots else None
        modes = [primary[s].execution_mode for s in ([root] if root else []) + self.order if primary[s].execution_mode]
        return Snapshot(
            project_id=project_id,
            trace_id=trace_id,
            run=RunInfo(
                root_span_id=root,
                execution_mode=modes[0] if modes else "",
                result_status=primary[root].attributes.get(_RESULT_STATUS) if root else None,
                started_at_ns=self.run_start,
                duration_ms=_ms(self.run_end - self.run_start),
                span_count_total=len(primary),
                span_count_rendered=len(primary) - len(collapsed),
            ),
            completeness=Completeness(
                payloads_captured=any(
                    record.input_state in READABLE_STATES or record.output_state in READABLE_STATES
                    for items in self.versions.values()
                    for _, record in items
                ),
                missing_root=not self.roots,
                multiple_roots=len(self.roots) > 1,
                orphan_span_ids=tuple(self.orphans),
                cycle_span_ids=tuple(self.cycle_span_ids),
                conflicted_span_ids=tuple(sorted(self.conflicted)),
                reductions=reductions,
            ),
            facts=Facts(
                originating_error_span_ids=tuple(self.originating),
                retry_groups=self.retry_groups,
                dangling_retry_span_ids=tuple(self.dangling),
            ),
            spans=tuple(spans),
            rollups=rollups,
        )


def build_snapshot(
    trace: TraceRead,
    project_id: UUID,
    trace_id: str,
    limits: SnapshotLimits = SnapshotLimits(),
) -> Snapshot:
    """Snapshot of one trace within `limits`; raises InputTooLarge when it cannot fit.

    Reductions (§3.3) are applied in order and only while a limit is exceeded:
    excerpts on non-decisive spans are dropped when the size is over; OK leaves
    outside the decisive set are collapsed when the size or the span count is
    over; excerpts on decisive spans are shrunk when the size is still over. A
    step that changes nothing is not recorded.
    """
    if not trace.spans:
        raise ValueError("a trace with no spans has no snapshot")
    index = _Trace(trace, limits)

    def measure(snapshot: Snapshot) -> tuple[bool, bool, int]:
        size = len(snapshot.to_json().encode("utf-8"))
        return len(snapshot.spans) > limits.max_spans, size > limits.max_bytes, size

    reductions: tuple[str, ...] = ()
    snapshot = index.render(project_id, trace_id, reductions)
    for step, applies_to_span_count in ((DROPPED_EXCERPTS, False), (COLLAPSED_LEAVES, True), (SHRUNK_EXCERPTS, False)):
        too_many, too_big, _ = measure(snapshot)
        if not (too_big or (too_many and applies_to_span_count)):
            continue
        candidate = index.render(project_id, trace_id, reductions + (step,))
        if (candidate.spans, candidate.rollups) != (snapshot.spans, snapshot.rollups):
            reductions, snapshot = reductions + (step,), candidate
    too_many, too_big, size = measure(snapshot)
    if too_many or too_big:
        raise InputTooLarge(reductions, len(snapshot.spans), size)
    return snapshot
