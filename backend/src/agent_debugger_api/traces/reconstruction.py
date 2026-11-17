"""Rebuild the span tree of one trace from parent IDs (LLD §8, trace-protocol.md §8, §9, §14).

Pure functions: the input is a `TraceRead` (what `TraceStore.get_trace` returns),
the output is a `Reconstruction`. Nothing here reads a database, and nothing
changes the recorded spans.

Rules:
- The hierarchy comes only from `parent_span_id`. The order of the input is
  never used; siblings are ordered by (started_at, span_id).
- A span whose parent is not in the trace is kept as a top-level node and
  flagged `missing_parent`. No parent is invented.
- More than one span with `parent_span_id = None` is kept as several roots and
  reported (`multiple_roots`). No root at all is reported (`missing_root`).
- A parent cycle (including a span that names itself as parent) is broken at
  one deterministic member, which becomes a top-level node. Every member is
  flagged `cycle`; the member where the cycle was cut is also `cycle_break`.
- A span_id with more than one content version (a conflict, trace-protocol.md
  §13.3) is one node with all its versions, flagged `conflict`. One version
  places the node in the tree; that is a placement rule, not a winner.

Flags and warnings describe the structure of the telemetry. They are not
findings about the agent.
"""

from __future__ import annotations

from dataclasses import dataclass

from agent_debugger_api.contracts import StatusCode, StoredSpan, TraceRead

MISSING_PARENT = "missing_parent"
MISSING_ROOT = "missing_root"
MULTIPLE_ROOTS = "multiple_roots"
CYCLE = "cycle"
CYCLE_BREAK = "cycle_break"
CONFLICT = "conflict"


@dataclass(frozen=True, slots=True)
class TreeNode:
    span_id: str
    # Parent in the reconstructed tree. None for every top-level node, including
    # an orphan and the span where a cycle was cut; `recorded_parent_span_id`
    # still has what the span said.
    parent_span_id: str | None
    recorded_parent_span_id: str | None
    depth: int  # 0 = top level
    children: tuple[str, ...]  # ordered by (started_at, span_id)
    flags: tuple[str, ...]  # sorted
    # Every stored version, ordered by (received_at, content_hash). versions[0]
    # places the node (parent, start time). More than one version = conflict.
    versions: tuple[StoredSpan, ...]

    @property
    def placement(self) -> StoredSpan:
        return self.versions[0]


@dataclass(frozen=True, slots=True)
class StructuralWarning:
    code: str
    span_ids: tuple[str, ...]  # sorted; empty for missing_root
    message: str


@dataclass(frozen=True, slots=True)
class Reconstruction:
    nodes: tuple[TreeNode, ...]  # pre-order: a parent is always before its children
    top_level: tuple[str, ...]  # roots, orphans and cycle breaks, by (started_at, span_id)
    warnings: tuple[StructuralWarning, ...]

    def node(self, span_id: str) -> TreeNode | None:
        return next((n for n in self.nodes if n.span_id == span_id), None)

    @property
    def root_span_ids(self) -> tuple[str, ...]:
        """Spans that recorded no parent. Orphans and cycle breaks are not roots."""
        return tuple(n.span_id for n in self.nodes if n.recorded_parent_span_id is None)


def reconstruct(trace: TraceRead) -> Reconstruction:
    versions: dict[str, list[StoredSpan]] = {}
    for stored in trace.spans:
        versions.setdefault(stored.record.span_id, []).append(stored)
    for group in versions.values():
        group.sort(key=lambda s: (s.record.received_at, s.content_hash))

    def order(span_id: str) -> tuple[int, str]:
        return (versions[span_id][0].record.started_at, span_id)

    recorded_parent = {sid: group[0].record.parent_span_id for sid, group in versions.items()}
    flags: dict[str, set[str]] = {sid: set() for sid in versions}
    for sid, group in versions.items():
        if len(group) > 1:
            flags[sid].add(CONFLICT)

    # Effective parent: the recorded parent when it exists in the trace.
    parent: dict[str, str | None] = {}
    for sid, recorded in recorded_parent.items():
        if recorded is None:
            parent[sid] = None
        elif recorded not in versions:
            parent[sid] = None
            flags[sid].add(MISSING_PARENT)
        else:
            parent[sid] = recorded

    _break_cycles(parent, flags, order)

    children: dict[str, list[str]] = {sid: [] for sid in versions}
    for sid, p in parent.items():
        if p is not None:
            children[p].append(sid)
    for kids in children.values():
        kids.sort(key=order)
    top_level = sorted((sid for sid, p in parent.items() if p is None), key=order)

    # Iterative pre-order walk: a deep trace must not hit the recursion limit.
    nodes: list[TreeNode] = []
    stack = [(sid, 0) for sid in reversed(top_level)]
    while stack:
        sid, depth = stack.pop()
        nodes.append(
            TreeNode(
                span_id=sid,
                parent_span_id=parent[sid],
                recorded_parent_span_id=recorded_parent[sid],
                depth=depth,
                children=tuple(children[sid]),
                flags=tuple(sorted(flags[sid])),
                versions=tuple(versions[sid]),
            )
        )
        stack.extend((child, depth + 1) for child in reversed(children[sid]))

    return Reconstruction(
        nodes=tuple(nodes),
        top_level=tuple(top_level),
        warnings=_warnings(versions, recorded_parent, flags),
    )


def _break_cycles(parent: dict[str, str | None], flags: dict[str, set[str]], order) -> None:
    """Cut every parent cycle in place, at its member with the lowest (started_at, span_id)."""
    done: set[str] = set()  # spans whose ancestor chain is known to end at a top-level node
    for start in sorted(parent, key=order):
        path: list[str] = []
        position: dict[str, int] = {}
        current: str | None = start
        while current is not None and current not in done and current not in position:
            position[current] = len(path)
            path.append(current)
            current = parent[current]
        if current is not None and current in position:
            members = path[position[current] :]
            cut = min(members, key=order)
            for member in members:
                flags[member].add(CYCLE)
            flags[cut].add(CYCLE_BREAK)
            parent[cut] = None
        done.update(path)


def _warnings(versions, recorded_parent, flags) -> tuple[StructuralWarning, ...]:
    def flagged(flag: str) -> tuple[str, ...]:
        return tuple(sorted(sid for sid, f in flags.items() if flag in f))

    def count(n: int, noun: str) -> str:
        return f"{n} {noun}" if n == 1 else f"{n} {noun}s"

    out: list[StructuralWarning] = []
    roots = tuple(sorted(sid for sid, p in recorded_parent.items() if p is None))
    if versions and not roots:
        out.append(StructuralWarning(MISSING_ROOT, (), "No root span has been received for this trace."))
    if len(roots) > 1:
        out.append(StructuralWarning(MULTIPLE_ROOTS, roots, f"{len(roots)} spans recorded no parent."))
    orphans = flagged(MISSING_PARENT)
    if orphans:
        out.append(
            StructuralWarning(
                MISSING_PARENT,
                orphans,
                f"{count(len(orphans), 'span')} named a parent that has not been received.",
            )
        )
    cyclic = flagged(CYCLE)
    if cyclic:
        out.append(
            StructuralWarning(
                CYCLE,
                cyclic,
                f"{count(len(cyclic), 'span')} {'names itself as parent' if len(cyclic) == 1 else 'form a parent cycle'}; "
                f"cut at {', '.join(flagged(CYCLE_BREAK))}.",
            )
        )
    conflicted = flagged(CONFLICT)
    if conflicted:
        out.append(
            StructuralWarning(
                CONFLICT,
                conflicted,
                f"{count(len(conflicted), 'span')} {'was' if len(conflicted) == 1 else 'were'} received "
                "with more than one content version.",
            )
        )
    return tuple(out)


def error_leaves(tree: Reconstruction) -> list[TreeNode]:
    """ERROR spans with no ERROR descendant, ordered by (started_at, span_id).

    Same rule as the local profile (`traces/service.py`): an ancestor often
    carries a descendant's error, so only the deepest recorded error sites
    count. A span with conflicting versions is ERROR if any version is ERROR,
    like the run list (clickhouse-span-record.md D14).
    """
    by_id = {n.span_id: n for n in tree.nodes}
    errors = [n for n in tree.nodes if any(v.record.status_code is StatusCode.ERROR for v in n.versions)]
    carries: set[str] = set()
    for n in errors:
        p = n.parent_span_id
        while p is not None and p not in carries:  # the tree has no cycles
            carries.add(p)
            p = by_id[p].parent_span_id
    leaves = [n for n in errors if n.span_id not in carries]
    return sorted(leaves, key=lambda n: (n.placement.record.started_at, n.span_id))


def first_error(tree: Reconstruction) -> TreeNode | None:
    """Earliest ERROR span with no ERROR descendant. A recorded fact, not a cause."""
    leaves = error_leaves(tree)
    return leaves[0] if leaves else None
