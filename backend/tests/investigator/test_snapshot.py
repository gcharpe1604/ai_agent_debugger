"""Snapshot builder and deterministic facts: proposal §9 tests 1 to 16 (S and F).

Test 7's "provider not called" half is in test_engine.py.
"""

import json
import random
import unittest

from agent_debugger_api.contracts import TraceRead
from agent_debugger_api.investigator.snapshot import (
    COLLAPSED_LEAVES,
    DROPPED_EXCERPTS,
    SHRUNK_EXCERPTS,
    InputTooLarge,
    SnapshotLimits,
    build_snapshot,
)
from tests.contracts.factories import PROJECT_A, T0, TRACE_1
from tests.investigator.factories import (
    AGENT,
    MS,
    ORDER,
    PAY_1,
    PAY_2,
    PAY_3,
    PLAN,
    RESERVE,
    ROOT,
    captured,
    error_span,
    failed_tool_trace,
    read,
    retry_trace,
    sid,
    snapshot_of,
    span,
)


def ids(snapshot):
    return [rendered.span_id for rendered in snapshot.spans]


def by_id(snapshot, number):
    (rendered,) = snapshot.versions(sid(number))
    return rendered


class SnapshotShapeTests(unittest.TestCase):
    def test_01_same_trace_gives_identical_bytes_whatever_the_insertion_order(self):
        records = failed_tool_trace()
        first = snapshot_of(*records)
        for seed in range(5):
            shuffled = records[:]
            random.Random(seed).shuffle(shuffled)
            again = snapshot_of(*shuffled)
            self.assertEqual(again.to_json(), first.to_json())
            self.assertEqual(again.snapshot_hash, first.snapshot_hash)
        # The TraceRead's own tuple order does not matter either.
        trace = read(*records)
        reversed_read = TraceRead(spans=tuple(reversed(trace.spans)), conflicted_span_ids=trace.conflicted_span_ids)
        self.assertEqual(build_snapshot(reversed_read, PROJECT_A, TRACE_1).to_json(), first.to_json())
        self.assertEqual(len(first.snapshot_hash), 64)
        self.assertEqual(json.loads(first.to_json())["schema_version"], 1)

    def test_02_spans_are_in_tree_preorder_and_arrival_order_has_no_effect(self):
        # Two branches; the later-starting branch (20) arrives first and has the lower received_at.
        records = [
            span(1, start=0, duration=100, operation_type="run", received_at=T0 + 900 * MS),
            span(10, 1, start=10, duration=30, received_at=T0 + 800 * MS),
            span(11, 10, start=12, received_at=T0 + 700 * MS),
            span(12, 10, start=11, received_at=T0 + 600 * MS),
            span(20, 1, start=50, duration=30, received_at=T0 + 100 * MS),
            span(21, 20, start=51, received_at=T0 + 50 * MS),
            # Same start as 12: the span ID breaks the tie.
            span(13, 10, start=11, received_at=T0 + 10 * MS),
        ]
        snapshot = snapshot_of(*records)
        self.assertEqual(ids(snapshot), [sid(n) for n in (1, 10, 12, 13, 11, 20, 21)])
        self.assertEqual([rendered.depth for rendered in snapshot.spans], [0, 1, 2, 2, 2, 1, 2])
        self.assertEqual(by_id(snapshot, 21).offset_ms, 51.0)
        self.assertEqual(by_id(snapshot, 20).duration_ms, 30.0)

        swapped = [record.model_copy(update={"received_at": T0 + (index + 1) * MS}) for index, record in enumerate(records)]
        self.assertEqual(snapshot_of(*swapped).to_json(), snapshot.to_json())

    def test_03_orphan_multiple_roots_no_root_and_cycle_are_reported_and_the_build_ends(self):
        with self.subTest("orphan"):
            snapshot = snapshot_of(span(1, operation_type="run"), span(2, 1, start=1), span(3, 99, start=2))
            self.assertEqual(snapshot.completeness.orphan_span_ids, (sid(3),))
            self.assertFalse(snapshot.completeness.missing_root)
            self.assertEqual(by_id(snapshot, 3).depth, 0)  # rendered at the top, parent ID kept
            self.assertEqual(by_id(snapshot, 3).parent_span_id, sid(99))
        with self.subTest("multiple roots"):
            snapshot = snapshot_of(span(1), span(2, start=5), span(3, 2, start=6))
            self.assertTrue(snapshot.completeness.multiple_roots)
            self.assertEqual(snapshot.run.root_span_id, sid(1))
            self.assertEqual(ids(snapshot), [sid(1), sid(2), sid(3)])
        with self.subTest("no root"):
            snapshot = snapshot_of(span(2, 1, start=1), span(3, 2, start=2))
            self.assertTrue(snapshot.completeness.missing_root)
            self.assertIsNone(snapshot.run.root_span_id)
            self.assertEqual(snapshot.completeness.orphan_span_ids, (sid(2),))
        with self.subTest("cycle"):
            # 2 -> 3 -> 4 -> 2 is a parent cycle; 5 hangs below it; 1 is a normal root.
            snapshot = snapshot_of(
                span(1, operation_type="run"),
                span(2, 4, start=3), span(3, 2, start=4), span(4, 3, start=5), span(5, 3, start=6),
            )
            self.assertEqual(snapshot.completeness.cycle_span_ids, (sid(2), sid(3), sid(4)))
            self.assertEqual(sorted(ids(snapshot)), [sid(n) for n in (1, 2, 3, 4, 5)])
            self.assertEqual(snapshot.run.span_count_rendered, 5)
        with self.subTest("self parent"):
            snapshot = snapshot_of(span(1, operation_type="run"), span(2, 2, start=1))
            self.assertEqual(snapshot.completeness.cycle_span_ids, (sid(2),))
            self.assertEqual(len(snapshot.spans), 2)

    def test_04_a_conflicted_span_renders_once_per_version_with_its_hash(self):
        records = [
            span(1, operation_type="run"),
            span(2, 1, start=1, status_description="first"),
            span(2, 1, start=1, status_description="second"),
            span(3, 1, start=2),
        ]
        snapshot = snapshot_of(*records)
        versions = snapshot.versions(sid(2))
        self.assertEqual(len(versions), 2)
        self.assertEqual({version.status_description for version in versions}, {"first", "second"})
        hashes = [version.content_hash for version in versions]
        self.assertEqual(len(set(hashes)), 2)
        self.assertTrue(all(len(value) == 12 for value in hashes))
        full = {stored.content_hash for stored in read(*records).spans if stored.record.span_id == sid(2)}
        self.assertEqual(set(hashes), {value[:12] for value in full})
        self.assertEqual(snapshot.completeness.conflicted_span_ids, (sid(2),))
        self.assertIsNone(by_id(snapshot, 3).content_hash)  # only conflicted spans carry one
        self.assertEqual((snapshot.run.span_count_total, snapshot.run.span_count_rendered), (3, 3))

    def test_05_payload_states_decide_whether_there_is_an_excerpt(self):
        long_text = "H" * 800 + "M" * 5000 + "T" * 400
        snapshot = snapshot_of(
            span(1, operation_type="run"),
            span(2, 1, start=1, input_state="disabled", output_state="unavailable"),
            span(3, 1, start=2, input_state="redacted", input_payload='{"order":42,"api_key":"[redacted]"}'),
            span(4, 1, start=3, **captured(output=long_text)),
            span(5, 1, start=4, output_state="truncated", output_payload='{"document":"policy"}'),
        )
        disabled = by_id(snapshot, 2)
        self.assertEqual((disabled.input.state.value, disabled.input.excerpt, disabled.input.full_length), ("disabled", None, 0))
        self.assertIsNone(disabled.output.excerpt)
        # D7: a redacted payload is read like a captured one, markers in place.
        redacted = by_id(snapshot, 3).input
        self.assertEqual((redacted.state.value, redacted.excerpt), ("redacted", '{"order":42,"api_key":"[redacted]"}'))
        excerpt = by_id(snapshot, 4).output
        self.assertEqual(excerpt.excerpt, "H" * 800 + "…[5000 chars omitted]…" + "T" * 400)
        self.assertEqual(excerpt.full_length, 6200)
        self.assertNotIn("M", excerpt.excerpt)
        self.assertEqual(by_id(snapshot, 5).output.excerpt, '{"document":"policy"}')
        self.assertTrue(snapshot.completeness.payloads_captured)
        self.assertFalse(snapshot_of(*failed_tool_trace(payloads=False)).completeness.payloads_captured)

    def test_09_attributes_outside_the_allowlist_are_absent_and_long_values_are_cut(self):
        snapshot = snapshot_of(
            span(1, operation_type="run", status_description="d" * 400, attributes={
                "debugger.step": "pay",
                "http.response.status_code": "503",
                "http.request.header.authorization": "Bearer sk-live",
                "service.internal": "x",
                "debugger.note": "n" * 400,
            }),
        )
        root = by_id(snapshot, 1)
        self.assertEqual(sorted(root.attributes), ["debugger.note", "debugger.step", "http.response.status_code"])
        self.assertEqual(root.attributes["debugger.note"], "n" * 256)
        self.assertEqual(root.status_description, "d" * 256)
        self.assertNotIn("sk-live", snapshot.to_json())
        self.assertNotIn("authorization", snapshot.to_json())

    def test_10_event_indexes_are_stable_for_equal_timestamps(self):
        def events(*names):
            return [{"name": name, "time": T0 + MS, "attributes": {"n": name}} for name in names]

        late = {"name": "aaa", "time": T0 + 2 * MS, "attributes": {}}
        first = snapshot_of(span(1, events=events("retry", "exception", "retry") + [late]))
        # Sorted by (time, name, original position); the same name keeps its recorded order.
        self.assertEqual([(e.index, e.name) for e in by_id(first, 1).events],
                         [(0, "exception"), (1, "retry"), (2, "retry"), (3, "aaa")])
        self.assertEqual(by_id(first, 1).events[3].offset_ms, 2.0)
        again = snapshot_of(span(1, events=events("retry", "exception", "retry") + [late]))
        self.assertEqual(by_id(again, 1).events, by_id(first, 1).events)
        many = snapshot_of(span(1, events=events(*[f"e{index:02}" for index in range(40)])))
        self.assertEqual([e.index for e in by_id(many, 1).events], list(range(16)))

    def test_run_summary_and_untouched_trace(self):
        snapshot = snapshot_of(*failed_tool_trace())
        self.assertEqual(snapshot.run.root_span_id, sid(ROOT))
        self.assertEqual((snapshot.run.execution_mode, snapshot.run.result_status), ("controlled", "failed"))
        self.assertEqual((snapshot.run.started_at_ns, snapshot.run.duration_ms), (T0, 50.0))
        self.assertEqual((snapshot.completeness.reductions, snapshot.rollups), ((), ()))
        self.assertEqual(by_id(snapshot, PLAN).output.excerpt, '{"plan":[{"step_id":"reserve","arguments":{"quantity":0}}]}')
        self.assertEqual(by_id(snapshot, RESERVE).events[0].name, "exception")
        with self.assertRaises(ValueError):
            build_snapshot(TraceRead(spans=(), conflicted_span_ids=frozenset()), PROJECT_A, TRACE_1)


class SnapshotReductionTests(unittest.TestCase):
    def wide_trace(self, leaves=30, payload=""):
        """root > agent > many OK leaves, then one failing retry group and a final model step."""
        records = [
            span(ROOT, start=0, duration=500, operation_type="run", status_code="ERROR"),
            span(AGENT, ROOT, start=1, duration=400, operation_type="agent"),
        ]
        extra = captured(output=payload) if payload else {}
        records += [span(100 + index, AGENT, start=10 + index, **extra) for index in range(leaves)]
        records += [
            error_span(PAY_1, AGENT, start=200, attempt=1, attributes={"debugger.step": "pay"}, **extra),
            error_span(PAY_2, AGENT, start=210, attempt=2, retry_of_span_id=sid(PAY_1),
                       attributes={"debugger.step": "pay"}, **extra),
            span(300, AGENT, start=220, operation_type="custom", span_name="controlled.respond", **extra),
        ]
        return records

    def test_06_over_the_span_limit_ok_leaves_collapse_and_decisive_spans_stay(self):
        snapshot = snapshot_of(*self.wide_trace(), limits=SnapshotLimits(max_spans=12))
        rendered = set(ids(snapshot))
        # Root, the error spans' ancestors, both retry attempts, the last custom step,
        # and the 5 siblings that ran just before the first originating error.
        self.assertEqual(rendered, {sid(n) for n in (ROOT, AGENT, PAY_1, PAY_2, 300, 125, 126, 127, 128, 129)})
        (rollup,) = snapshot.rollups
        self.assertEqual((rollup.parent_span_id, rollup.count, rollup.operation_types), (sid(AGENT), 25, ("tool",)))
        self.assertEqual((rollup.first_offset_ms, rollup.last_offset_ms), (10.0, 34.0))
        self.assertEqual(snapshot.completeness.reductions, (COLLAPSED_LEAVES,))
        self.assertEqual((snapshot.run.span_count_total, snapshot.run.span_count_rendered), (35, 10))
        self.assertEqual(snapshot.versions(sid(100)), ())  # a collapsed span is not citable

    def test_06_an_error_leaf_and_a_parent_are_never_collapsed(self):
        records = self.wide_trace(leaves=10) + [span(400, 105, start=16)]
        snapshot = snapshot_of(*records, limits=SnapshotLimits(max_spans=12))
        self.assertIn(sid(105), ids(snapshot))  # has a child, so it is not a leaf
        self.assertNotIn(sid(400), ids(snapshot))
        self.assertEqual({rollup.parent_span_id for rollup in snapshot.rollups}, {sid(AGENT), sid(105)})

    def test_07_still_over_a_limit_after_all_reductions_is_input_too_large(self):
        with self.subTest("span count"):
            records = [span(ROOT, operation_type="run", status_code="ERROR")]
            records += [error_span(10 + index, ROOT, start=index + 1) for index in range(20)]
            with self.assertRaises(InputTooLarge) as raised:
                snapshot_of(*records, limits=SnapshotLimits(max_spans=10))
            self.assertEqual(raised.exception.rendered_spans, 21)  # every ERROR span is decisive
            self.assertEqual(raised.exception.reductions, ())
        with self.subTest("size"):
            with self.assertRaises(InputTooLarge) as raised:
                snapshot_of(*self.wide_trace(payload="p" * 3000), limits=SnapshotLimits(max_bytes=2000))
            self.assertEqual(raised.exception.reductions, (DROPPED_EXCERPTS, COLLAPSED_LEAVES, SHRUNK_EXCERPTS))
            self.assertGreater(raised.exception.size_bytes, 2000)

    def test_08_each_reduction_is_recorded_in_order_and_only_when_needed(self):
        records = self.wide_trace(leaves=8, payload="p" * 3000)

        def size(snapshot):
            return len(snapshot.to_json().encode("utf-8"))

        full = snapshot_of(*records)
        self.assertEqual(full.completeness.reductions, ())

        dropped = snapshot_of(*records, limits=SnapshotLimits(max_bytes=size(full) - 1))
        self.assertEqual(dropped.completeness.reductions, (DROPPED_EXCERPTS,))
        self.assertIsNone(by_id(dropped, 100).output.excerpt)
        self.assertEqual((by_id(dropped, 100).output.state.value, by_id(dropped, 100).output.full_length), ("captured", 3000))
        self.assertEqual(len(by_id(dropped, PAY_1).output.excerpt), 800 + len("…[1800 chars omitted]…") + 400)

        collapsed = snapshot_of(*records, limits=SnapshotLimits(max_bytes=size(dropped) - 1))
        self.assertEqual(collapsed.completeness.reductions, (DROPPED_EXCERPTS, COLLAPSED_LEAVES))
        self.assertEqual(collapsed.rollups[0].count, 3)

        shrunk = snapshot_of(*records, limits=SnapshotLimits(max_bytes=size(collapsed) - 1))
        self.assertEqual(shrunk.completeness.reductions, (DROPPED_EXCERPTS, COLLAPSED_LEAVES, SHRUNK_EXCERPTS))
        self.assertEqual(by_id(shrunk, PAY_1).output.excerpt, "p" * 200 + "…[2700 chars omitted]…" + "p" * 100)
        self.assertLessEqual(size(shrunk), size(collapsed) - 1)

    def test_08_a_reduction_that_changes_nothing_is_not_recorded(self):
        # Over the span limit only, and nothing can be collapsed: no reduction is claimed.
        records = [span(ROOT, operation_type="run", status_code="ERROR")]
        records += [error_span(10 + index, ROOT, start=index + 1) for index in range(4)]
        with self.assertRaises(InputTooLarge) as raised:
            snapshot_of(*records, limits=SnapshotLimits(max_spans=3))
        self.assertEqual(raised.exception.reductions, ())

    def test_link_targets_of_decisive_spans_are_kept(self):
        records = self.wide_trace()
        records[-2] = error_span(PAY_2, AGENT, start=210, attempt=2, retry_of_span_id=sid(PAY_1),
                                 attributes={"debugger.step": "pay"},
                                 links=[{"trace_id": TRACE_1, "span_id": sid(103), "relation": "consumes"}])
        snapshot = snapshot_of(*records, limits=SnapshotLimits(max_spans=12))
        self.assertIn(sid(103), ids(snapshot))
        self.assertEqual(by_id(snapshot, PAY_2).links[0].span_id, sid(103))


class FactsTests(unittest.TestCase):
    def test_11_originating_error_is_an_error_span_with_no_error_descendant(self):
        snapshot = snapshot_of(*failed_tool_trace())
        # The root is ERROR too, but it has an ERROR descendant.
        self.assertEqual(snapshot.facts.originating_error_span_ids, (sid(RESERVE),))
        nested = snapshot_of(
            span(1, operation_type="run", status_code="ERROR"),
            error_span(2, 1, start=1), span(3, 2, start=2), error_span(4, 3, start=3),
            error_span(5, 1, start=5),
        )
        self.assertEqual(nested.facts.originating_error_span_ids, (sid(4), sid(5)))
        self.assertEqual(snapshot_of(span(1), span(2, 1, start=1)).facts.originating_error_span_ids, ())

    def test_12_chain_of_two_with_the_last_ok_is_recovered(self):
        snapshot = snapshot_of(*retry_trace("ERROR", "OK"))
        (group,) = snapshot.facts.retry_groups
        self.assertEqual((group.span_ids, group.outcome, group.basis, group.step),
                         ((sid(PAY_1), sid(PAY_2)), "recovered", "retry_of", "pay"))
        self.assertEqual(snapshot.retry_group_of(sid(PAY_2)), group)
        self.assertIsNone(snapshot.retry_group_of(sid(AGENT)))
        self.assertEqual(snapshot.facts.originating_error_span_ids, (sid(PAY_1),))

    def test_13_chain_of_three_all_error_is_exhausted(self):
        snapshot = snapshot_of(*retry_trace("ERROR", "ERROR", "ERROR"))
        (group,) = snapshot.facts.retry_groups
        self.assertEqual((group.span_ids, group.outcome), ((sid(PAY_1), sid(PAY_2), sid(PAY_3)), "exhausted"))
        self.assertEqual(snapshot.facts.originating_error_span_ids, (sid(PAY_1), sid(PAY_2), sid(PAY_3)))

    def test_13_the_highest_attempt_decides_not_the_latest_start(self):
        # Attempt 2 was recorded with an earlier start than attempt 1 (clock skew).
        snapshot = snapshot_of(
            span(ROOT, operation_type="run"),
            error_span(PAY_1, ROOT, start=20, attempt=1),
            span(PAY_2, ROOT, start=10, attempt=2, retry_of_span_id=sid(PAY_1)),
        )
        (group,) = snapshot.facts.retry_groups
        self.assertEqual((group.span_ids, group.outcome), ((sid(PAY_1), sid(PAY_2)), "recovered"))

    def test_14_fallback_grouping_by_parent_step_and_attempt_when_no_chain_exists(self):
        step = {"debugger.step": "pay"}
        snapshot = snapshot_of(
            span(ROOT, operation_type="run"),
            span(AGENT, ROOT, start=1, operation_type="agent"),
            error_span(PAY_1, AGENT, start=10, attempt=1, attributes=step),
            span(PAY_2, AGENT, start=12, attempt=2, attributes=step),
            # Same step under another parent, and another step: not part of the group.
            span(20, ROOT, start=30, attempt=1, attributes=step),
            span(21, AGENT, start=14, attempt=1, attributes={"debugger.step": "ship"}),
        )
        (group,) = snapshot.facts.retry_groups
        self.assertEqual((group.span_ids, group.outcome, group.basis, group.step),
                         ((sid(PAY_1), sid(PAY_2)), "recovered", "step_attempt", "pay"))

    def test_14_two_attempts_without_an_error_are_a_group_with_no_error(self):
        snapshot = snapshot_of(*retry_trace("OK", "OK"))
        self.assertEqual(snapshot.facts.retry_groups[0].outcome, "no_error")

    def test_15_two_retrieval_spans_without_step_or_attempt_are_not_a_retry_group(self):
        snapshot = snapshot_of(
            span(ROOT, operation_type="run"),
            span(10, ROOT, start=1, operation_type="retrieval", span_name="ScenarioAwareRetriever.search"),
            span(11, ROOT, start=5, operation_type="retrieval", span_name="ScenarioAwareRetriever.search"),
        )
        self.assertEqual(snapshot.facts.retry_groups, ())
        # The same attempt number twice is not a retry either.
        step = {"debugger.step": "pay"}
        same = snapshot_of(span(ROOT), span(10, ROOT, start=1, attempt=1, attributes=step),
                           span(11, ROOT, start=2, attempt=1, attributes=step))
        self.assertEqual(same.facts.retry_groups, ())

    def test_16_a_retry_chain_pointing_at_a_missing_span_is_reported_and_does_not_crash(self):
        snapshot = snapshot_of(
            span(ROOT, operation_type="run"),
            span(PAY_2, ROOT, start=10, attempt=2, retry_of_span_id=sid(99)),
        )
        self.assertEqual(snapshot.facts.dangling_retry_span_ids, (sid(PAY_2),))
        self.assertEqual(snapshot.facts.retry_groups, ())
        self.assertEqual(by_id(snapshot, PAY_2).retry_of_span_id, sid(99))


if __name__ == "__main__":
    unittest.main()
