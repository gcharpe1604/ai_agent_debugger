import unittest

from agent_debugger_api.contracts import PublishError, SpanPublisher, TraceStore
from agent_debugger_api.contracts.fakes import (
    InMemorySpanPublisher,
    InMemoryTraceStore,
    placeholder_content_hash,
)
from tests.contracts.factories import PROJECT_A, PROJECT_B, T0, TRACE_1, TRACE_2, make_span

ROOT = "a" * 16
CHILD = "b" * 16


class PlaceholderHashTests(unittest.TestCase):
    def test_is_sha256_hex_and_ignores_receipt_metadata(self):
        span = make_span()
        digest = placeholder_content_hash(span)
        self.assertRegex(digest, r"^[0-9a-f]{64}$")
        self.assertEqual(digest, placeholder_content_hash(make_span(received_at=T0 + 99)))
        self.assertEqual(digest, placeholder_content_hash(make_span(project_id=PROJECT_B)))

    def test_changes_with_content(self):
        self.assertNotEqual(placeholder_content_hash(make_span()), placeholder_content_hash(make_span(span_name="other")))


class InMemorySpanPublisherTests(unittest.IsolatedAsyncioTestCase):
    async def test_satisfies_protocol_and_records_keyed_spans(self):
        publisher = InMemorySpanPublisher()
        self.assertIsInstance(publisher, SpanPublisher)
        spans = [make_span(), make_span(span_id=CHILD, parent_span_id=ROOT, trace_id=TRACE_2)]
        await publisher.publish(spans)
        self.assertEqual(publisher.acked, [(b"1" * 32, spans[0]), (b"2" * 32, spans[1])])

    async def test_partial_failure_raises_and_keeps_already_acked_spans(self):
        publisher = InMemorySpanPublisher(fail_after=1)
        first, second = make_span(), make_span(span_id=CHILD)
        with self.assertRaises(PublishError):
            await publisher.publish([first, second])
        self.assertEqual([record for _, record in publisher.acked], [first])

    async def test_fail_after_zero_acks_nothing(self):
        publisher = InMemorySpanPublisher(fail_after=0)
        with self.assertRaises(PublishError):
            await publisher.publish([make_span()])
        self.assertEqual(publisher.acked, [])


class InMemoryTraceStoreTests(unittest.TestCase):
    def setUp(self):
        self.store = InMemoryTraceStore()

    def test_satisfies_protocol(self):
        self.assertIsInstance(self.store, TraceStore)

    def test_unknown_trace_is_none(self):
        self.assertIsNone(self.store.get_trace(PROJECT_A, TRACE_1))
        self.assertEqual(self.store.list_runs(PROJECT_A, 0, 2**63), [])

    def test_identical_redelivery_is_one_logical_row(self):
        self.store.insert_spans([make_span()])
        self.store.insert_spans([make_span(received_at=T0 + 10_000)])
        trace = self.store.get_trace(PROJECT_A, TRACE_1)
        self.assertEqual(len(trace.spans), 1)
        self.assertFalse(trace.conflicted)
        self.assertEqual(self.store.insert_batch_sizes, [1, 1])

    def test_conflicting_versions_are_both_kept_and_flagged(self):
        self.store.insert_spans([make_span(), make_span(status_code="ERROR")])
        trace = self.store.get_trace(PROJECT_A, TRACE_1)
        self.assertEqual(len(trace.spans), 2)
        self.assertEqual(trace.conflicted_span_ids, frozenset({ROOT}))
        self.assertNotEqual(trace.spans[0].content_hash, trace.spans[1].content_hash)
        conflicts = self.store.get_conflicts(PROJECT_A, TRACE_1)
        self.assertEqual([(c.span_id, c.versions) for c in conflicts], [(ROOT, 2)])

    def test_out_of_order_spans_are_read_in_execution_order(self):
        child = make_span(span_id=CHILD, parent_span_id=ROOT, started_at=T0 + 100, ended_at=T0 + 200)
        root = make_span()
        self.store.insert_spans([child])
        self.store.insert_spans([root])
        trace = self.store.get_trace(PROJECT_A, TRACE_1)
        self.assertEqual([s.record.span_id for s in trace.spans], [ROOT, CHILD])

    def test_projects_are_isolated(self):
        self.store.insert_spans([make_span(), make_span(project_id=PROJECT_B, span_name="b.run")])
        a = self.store.get_trace(PROJECT_A, TRACE_1)
        b = self.store.get_trace(PROJECT_B, TRACE_1)
        self.assertEqual([s.record.span_name for s in a.spans], ["rag.run"])
        self.assertEqual([s.record.span_name for s in b.spans], ["b.run"])
        self.assertEqual(len(self.store.list_runs(PROJECT_B, 0, 2**63)), 1)

    def test_run_list_aggregates_per_trace(self):
        self.store.insert_spans(
            [
                make_span(execution_mode="controlled"),
                make_span(span_id=CHILD, parent_span_id=ROOT, status_code="ERROR", started_at=T0 + 10, ended_at=T0 + 5_000),
            ]
        )
        [run] = self.store.list_runs(PROJECT_A, 0, 2**63)
        self.assertEqual(
            (run.trace_id, run.run_started_at, run.run_ended_at, run.root_name, run.missing_root),
            (TRACE_1, T0, T0 + 5_000, "rag.run", False),
        )
        self.assertEqual((run.execution_mode, run.span_count, run.error_span_count), ("controlled", 2, 1))

    def test_trace_without_root_is_listed_as_missing_root(self):
        self.store.insert_spans([make_span(span_id=CHILD, parent_span_id=ROOT)])
        [run] = self.store.list_runs(PROJECT_A, 0, 2**63)
        self.assertTrue(run.missing_root)
        self.assertIsNone(run.root_name)
        self.assertEqual(len((self.store.get_trace(PROJECT_A, TRACE_1)).spans), 1)

    def test_run_list_filters_time_range_sorts_newest_first_and_limits(self):
        self.store.insert_spans(
            [
                make_span(trace_id=TRACE_1, started_at=T0, ended_at=T0),
                make_span(trace_id=TRACE_2, started_at=T0 + 10, ended_at=T0 + 10),
            ]
        )
        runs = self.store.list_runs(PROJECT_A, T0, T0 + 11)
        self.assertEqual([r.trace_id for r in runs], [TRACE_2, TRACE_1])
        self.assertEqual([r.trace_id for r in self.store.list_runs(PROJECT_A, T0, T0 + 10)], [TRACE_1])
        self.assertEqual(len(self.store.list_runs(PROJECT_A, 0, 2**63, limit=1)), 1)


if __name__ == "__main__":
    unittest.main()
