"""Span-tree reconstruction: pure functions, no database."""

import itertools
import random
import unittest

from agent_debugger_api.contracts import StoredSpan, TraceRead
from agent_debugger_api.traces.reconstruction import (
    CONFLICT,
    CYCLE,
    CYCLE_BREAK,
    MISSING_PARENT,
    MISSING_ROOT,
    MULTIPLE_ROOTS,
    error_leaves,
    first_error,
    reconstruct,
)

from ..contracts.factories import T0, make_span

A, B, C, D, E, F = ("a" * 16, "b" * 16, "c" * 16, "d" * 16, "e" * 16, "f" * 16)
GONE = "9" * 16


def stored(span_id, parent, start=0, content_hash=None, **overrides) -> StoredSpan:
    record = make_span(
        span_id=span_id,
        parent_span_id=parent,
        started_at=T0 + start,
        ended_at=T0 + start + 10,
        **overrides,
    )
    return StoredSpan(record=record, content_hash=content_hash or f"hash-{span_id[0]}")


def trace(*spans) -> TraceRead:
    by_span = {}
    for s in spans:
        by_span.setdefault(s.record.span_id, set()).add(s.content_hash)
    return TraceRead(
        spans=tuple(spans),
        conflicted_span_ids=frozenset(sid for sid, hashes in by_span.items() if len(hashes) > 1),
    )


def shape(tree):
    """(span_id initial, depth) in output order: enough to see the whole tree."""
    return [(n.span_id[0], n.depth) for n in tree.nodes]


def codes(tree):
    return [w.code for w in tree.warnings]


class WellFormedTreeTests(unittest.TestCase):
    def test_empty_trace_has_no_nodes_and_no_warnings(self):
        tree = reconstruct(trace())
        self.assertEqual(tree.nodes, ())
        self.assertEqual(tree.top_level, ())
        self.assertEqual(tree.warnings, ())

    def test_single_root(self):
        tree = reconstruct(trace(stored(A, None)))
        self.assertEqual(shape(tree), [("a", 0)])
        self.assertEqual(tree.root_span_ids, (A,))
        self.assertEqual(tree.nodes[0].flags, ())
        self.assertEqual(tree.warnings, ())

    def test_children_hang_off_parent_ids_in_pre_order(self):
        tree = reconstruct(
            trace(stored(A, None, 0), stored(B, A, 1), stored(C, B, 2), stored(D, A, 3), stored(E, D, 4))
        )
        self.assertEqual(shape(tree), [("a", 0), ("b", 1), ("c", 2), ("d", 1), ("e", 2)])
        self.assertEqual(tree.node(A).children, (B, D))
        self.assertEqual(tree.node(C).parent_span_id, B)
        self.assertEqual(tree.warnings, ())

    def test_arrival_order_never_changes_the_result(self):
        spans = [stored(A, None, 0), stored(B, A, 1), stored(C, B, 2), stored(D, A, 3), stored(E, GONE, 4)]
        expected = reconstruct(trace(*spans))
        for permutation in itertools.permutations(spans):
            self.assertEqual(reconstruct(trace(*permutation)), expected)

    def test_child_that_arrived_and_started_before_its_parent_is_still_its_child(self):
        # Clock skew or a late parent: placement follows the parent ID, not the clock.
        tree = reconstruct(trace(stored(B, A, 0), stored(A, None, 50)))
        self.assertEqual(shape(tree), [("a", 0), ("b", 1)])

    def test_siblings_are_ordered_by_start_time_then_span_id(self):
        tree = reconstruct(trace(stored(A, None, 0), stored(D, A, 5), stored(C, A, 5), stored(B, A, 9)))
        self.assertEqual(tree.node(A).children, (C, D, B))

    def test_a_trace_deeper_than_the_recursion_limit_is_reconstructed(self):
        ids = [f"{i:016x}" for i in range(1, 3001)]
        spans = [stored(ids[0], None, 0)] + [stored(ids[i], ids[i - 1], i) for i in range(1, len(ids))]
        random.Random(7).shuffle(spans)
        tree = reconstruct(trace(*spans))
        self.assertEqual([n.span_id for n in tree.nodes], ids)
        self.assertEqual(tree.nodes[-1].depth, 2999)
        self.assertEqual(tree.warnings, ())

    def test_recorded_spans_are_not_changed(self):
        orphan = stored(B, GONE, 1)
        tree = reconstruct(trace(stored(A, None), orphan))
        self.assertIs(tree.node(B).versions[0], orphan)
        self.assertEqual(tree.node(B).versions[0].record.parent_span_id, GONE)


class MissingParentTests(unittest.TestCase):
    def test_orphan_is_top_level_flagged_and_keeps_its_recorded_parent(self):
        tree = reconstruct(trace(stored(A, None, 0), stored(B, GONE, 1), stored(C, B, 2)))
        self.assertEqual(shape(tree), [("a", 0), ("b", 0), ("c", 1)])
        orphan = tree.node(B)
        self.assertEqual(orphan.flags, (MISSING_PARENT,))
        self.assertIsNone(orphan.parent_span_id)
        self.assertEqual(orphan.recorded_parent_span_id, GONE)
        self.assertEqual(tree.node(C).flags, ())  # its parent is present
        self.assertEqual(tree.top_level, (A, B))
        self.assertEqual(tree.root_span_ids, (A,))  # an orphan is not a root

    def test_orphans_are_reported_once_with_all_span_ids(self):
        tree = reconstruct(trace(stored(A, None), stored(C, GONE, 2), stored(B, GONE, 1)))
        (warning,) = tree.warnings
        self.assertEqual(warning.code, MISSING_PARENT)
        self.assertEqual(warning.span_ids, (B, C))
        self.assertIn("2 spans", warning.message)

    def test_no_root_at_all_is_reported(self):
        # A crashed process: the root ends last, so it may never be exported.
        tree = reconstruct(trace(stored(B, GONE, 1), stored(C, B, 2)))
        self.assertEqual(codes(tree), [MISSING_ROOT, MISSING_PARENT])
        self.assertEqual(tree.root_span_ids, ())
        self.assertEqual(shape(tree), [("b", 0), ("c", 1)])


class MultipleRootsTests(unittest.TestCase):
    def test_every_root_is_kept_and_reported(self):
        tree = reconstruct(trace(stored(B, None, 5), stored(A, None, 9), stored(C, B, 6)))
        self.assertEqual(shape(tree), [("b", 0), ("c", 1), ("a", 0)])
        (warning,) = tree.warnings
        self.assertEqual(warning.code, MULTIPLE_ROOTS)
        self.assertEqual(warning.span_ids, (A, B))
        self.assertEqual(tree.node(A).flags, ())  # a root is not a damaged span


class CycleTests(unittest.TestCase):
    def test_self_parent_is_cut_and_flagged(self):
        tree = reconstruct(trace(stored(A, None, 0), stored(B, B, 1)))
        self.assertEqual(shape(tree), [("a", 0), ("b", 0)])
        self.assertEqual(tree.node(B).flags, (CYCLE, CYCLE_BREAK))
        self.assertIsNone(tree.node(B).parent_span_id)
        self.assertEqual(tree.node(B).recorded_parent_span_id, B)
        self.assertEqual(codes(tree), [CYCLE])

    def test_two_span_cycle_is_cut_at_the_earliest_start(self):
        tree = reconstruct(trace(stored(A, None, 0), stored(B, C, 5), stored(C, B, 3)))
        self.assertEqual(shape(tree), [("a", 0), ("c", 0), ("b", 1)])
        self.assertEqual(tree.node(C).flags, (CYCLE, CYCLE_BREAK))
        self.assertEqual(tree.node(B).flags, (CYCLE,))
        self.assertEqual(tree.node(B).parent_span_id, C)  # the other edge is kept

    def test_equal_start_times_cut_at_the_lower_span_id(self):
        tree = reconstruct(trace(stored(C, B, 3), stored(B, C, 3)))
        self.assertEqual(tree.node(B).flags, (CYCLE, CYCLE_BREAK))
        self.assertEqual(shape(tree), [("b", 0), ("c", 1)])

    def test_span_hanging_off_a_cycle_is_kept_but_not_flagged(self):
        # B -> C -> D -> B is the cycle; E is a child of D, F a child of E.
        spans = [stored(B, D, 1), stored(C, B, 2), stored(D, C, 3), stored(E, D, 4), stored(F, E, 5)]
        tree = reconstruct(trace(*spans))
        self.assertEqual(shape(tree), [("b", 0), ("c", 1), ("d", 2), ("e", 3), ("f", 4)])
        self.assertEqual(tree.node(E).flags, ())
        (cycle,) = [w for w in tree.warnings if w.code == CYCLE]
        self.assertEqual(cycle.span_ids, (B, C, D))
        self.assertIn(B, cycle.message)

    def test_two_separate_cycles_are_each_cut_once(self):
        spans = [stored(A, B, 1), stored(B, A, 2), stored(C, D, 4), stored(D, C, 3), stored(E, None, 0)]
        tree = reconstruct(trace(*spans))
        self.assertEqual(tree.top_level, (E, A, D))
        breaks = sorted(n.span_id for n in tree.nodes if CYCLE_BREAK in n.flags)
        self.assertEqual(breaks, [A, D])
        self.assertEqual(len(tree.nodes), 5)  # nothing lost, nothing listed twice

    def test_every_span_appears_exactly_once_for_any_arrival_order(self):
        spans = [stored(B, D, 1), stored(C, B, 2), stored(D, C, 3), stored(E, D, 4), stored(A, A, 0)]
        expected = reconstruct(trace(*spans))
        for permutation in itertools.permutations(spans):
            tree = reconstruct(trace(*permutation))
            self.assertEqual(tree, expected)
            self.assertEqual(sorted(n.span_id for n in tree.nodes), [A, B, C, D, E])


class ConflictTests(unittest.TestCase):
    def test_conflicting_versions_are_one_node_with_every_version(self):
        first = stored(B, A, 1, content_hash="h1", span_name="tool.first", received_at=T0 + 100)
        second = stored(B, A, 1, content_hash="h2", span_name="tool.second", received_at=T0 + 200)
        tree = reconstruct(trace(stored(A, None), second, first))
        self.assertEqual(shape(tree), [("a", 0), ("b", 1)])
        node = tree.node(B)
        self.assertEqual(node.flags, (CONFLICT,))
        self.assertEqual([v.content_hash for v in node.versions], ["h1", "h2"])  # by received_at
        (warning,) = tree.warnings
        self.assertEqual((warning.code, warning.span_ids), (CONFLICT, (B,)))

    def test_versions_with_equal_receipt_time_are_ordered_by_hash(self):
        one = stored(B, None, content_hash="h2")
        two = stored(B, None, content_hash="h1")
        self.assertEqual([v.content_hash for v in reconstruct(trace(one, two)).node(B).versions], ["h1", "h2"])
        self.assertEqual([v.content_hash for v in reconstruct(trace(two, one)).node(B).versions], ["h1", "h2"])

    def test_versions_that_disagree_on_the_parent_are_placed_by_the_first_received(self):
        early = stored(C, A, 2, content_hash="h1", received_at=T0 + 100)
        late = stored(C, B, 2, content_hash="h2", received_at=T0 + 200)
        tree = reconstruct(trace(stored(A, None, 0), stored(B, A, 1), late, early))
        node = tree.node(C)
        self.assertEqual(node.parent_span_id, A)
        self.assertEqual(tree.node(A).children, (B, C))
        self.assertEqual(tree.node(B).children, ())  # not also listed under the other parent
        self.assertEqual({v.record.parent_span_id for v in node.versions}, {A, B})  # both still visible

    def test_a_conflicted_span_can_also_be_an_orphan(self):
        tree = reconstruct(trace(stored(B, GONE, content_hash="h1"), stored(B, GONE, content_hash="h2")))
        self.assertEqual(tree.node(B).flags, (CONFLICT, MISSING_PARENT))
        self.assertEqual(codes(tree), [MISSING_ROOT, MISSING_PARENT, CONFLICT])

    def test_identical_span_delivered_once_is_not_a_conflict(self):
        tree = reconstruct(trace(stored(A, None), stored(B, A, 1)))
        self.assertEqual(tree.warnings, ())


class FirstErrorTests(unittest.TestCase):
    def test_no_error_spans(self):
        tree = reconstruct(trace(stored(A, None), stored(B, A, 1)))
        self.assertIsNone(first_error(tree))
        self.assertEqual(error_leaves(tree), [])

    def test_deepest_error_wins_over_ancestors_that_carry_it(self):
        # run ERROR > agent OK > tool ERROR: the tool is the recorded error site.
        tree = reconstruct(
            trace(
                stored(A, None, 0, status_code="ERROR"),
                stored(B, A, 1),
                stored(C, B, 2, status_code="ERROR"),
            )
        )
        self.assertEqual(first_error(tree).span_id, C)
        self.assertEqual(len(error_leaves(tree)), 1)

    def test_earliest_of_several_error_sites_and_the_count(self):
        tree = reconstruct(
            trace(
                stored(A, None, 0, status_code="ERROR"),
                stored(B, A, 5, status_code="ERROR"),
                stored(C, A, 3, status_code="ERROR"),
            )
        )
        self.assertEqual(first_error(tree).span_id, C)
        self.assertEqual([n.span_id for n in error_leaves(tree)], [C, B])

    def test_a_conflicted_span_is_an_error_if_any_version_is(self):
        ok = stored(B, A, 1, content_hash="h1")
        failed = stored(B, A, 1, content_hash="h2", status_code="ERROR")
        self.assertEqual(first_error(reconstruct(trace(stored(A, None), ok, failed))).span_id, B)

    def test_an_error_inside_a_cycle_does_not_loop(self):
        tree = reconstruct(trace(stored(B, C, 1, status_code="ERROR"), stored(C, B, 2, status_code="ERROR")))
        self.assertEqual(first_error(tree).span_id, C)  # B was the cut, C is its child


if __name__ == "__main__":
    unittest.main()
