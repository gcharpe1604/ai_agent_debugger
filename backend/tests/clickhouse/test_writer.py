"""ClickHouseTraceStore against a real ClickHouse (docs/proposals/clickhouse-span-record.md §6).

Every test uses its own trace_id because the scratch database is shared by the
whole class. Tests 2 and 14-16 need the Kafka consumer and live elsewhere;
tests 6-7 (hash) are in tests/trace_writer.
"""

import unittest
from unittest import mock

from agent_debugger_api.contracts import TraceStore
from agent_debugger_api.trace_writer.clickhouse_store import ClickHouseTraceStore
from tests.clickhouse.harness import ClickHouseTestCase
from tests.contracts.factories import PROJECT_A, PROJECT_B, T0, make_span

ROOT = "a" * 16
CHILD = "b" * 16
GRANDCHILD = "c" * 16
ABSENT = "f" * 16  # a parent that never arrives


def trace(n: int) -> str:
    """A distinct 32-char hex trace_id per test."""
    return f"{n:032x}"


class WriterTests(ClickHouseTestCase):
    def setUp(self):
        self.store = ClickHouseTraceStore(self.client, table=self.table)

    def physical_rows(self, trace_id: str) -> int:
        """Rows on disk for a trace, without the read-time LIMIT 1 BY."""
        result = self.client.query(
            f"SELECT count() FROM {self.table} WHERE trace_id = %(t)s", parameters={"t": trace_id}
        )
        return result.result_rows[0][0]

    def optimize_final(self) -> None:
        self.client.command(f"OPTIMIZE TABLE {self.table} FINAL")

    # §6.1
    def test_duplicate_is_one_logical_row(self):
        span = make_span()
        self.store.insert_spans([span])
        self.store.insert_spans([span])         # redelivery = second part
        rows = self.store.get_rows(span.project_id, span.trace_id)
        self.assertEqual(len(rows), 1)

    def test_duplicate_collapses_to_one_physical_row_after_optimize_final(self):
        span = make_span(trace_id=trace(1))
        self.store.insert_spans([span], positions=[(0, 10)])
        self.store.insert_spans([span], positions=[(0, 11)])  # redelivery from a later offset
        self.assertEqual(self.physical_rows(trace(1)), 2)  # two parts before the merge
        self.optimize_final()
        self.assertEqual(self.physical_rows(trace(1)), 1)

    def test_received_at_is_stored_in_ms(self):
        # Own trace: received_at is not hashed, so on the shared default trace this
        # would be the same logical row as test_duplicate_is_one_logical_row's span.
        span = make_span(trace_id=trace(2), received_at=1_700_000_000_123_456_789)
        self.store.insert_spans([span])
        row = self.store.get_rows(span.project_id, span.trace_id)[0]
        self.assertEqual(row["received_at"], 1_700_000_000_123)

    # §6.5 (storage half; the conflict query and flag are in PendingReadMethodTests)
    def test_duplicate_deliveries_read_back_the_latest_received_at(self):
        # D16: before a merge, LIMIT 1 BY keeps the latest receipt, the same row
        # ReplacingMergeTree(received_at) keeps after one. Earlier receipt inserted second,
        # so insertion order cannot make this pass.
        early, late = 1_700_000_000_000_000_000, 1_700_000_060_000_000_000
        span = make_span(trace_id=trace(30))
        self.store.insert_spans([span.model_copy(update={"received_at": late})])
        self.store.insert_spans([span.model_copy(update={"received_at": early})])
        self.assertEqual(self.physical_rows(trace(30)), 2)
        [row] = self.store.get_rows(span.project_id, span.trace_id)
        self.assertEqual(row["received_at"], late // 1_000_000)  # get_rows returns the raw ms column

    def test_conflicting_duplicate_keeps_both_versions_after_optimize_final(self):
        ok = make_span(trace_id=trace(5))
        failed = make_span(trace_id=trace(5), status_code="ERROR", error_type="TimeoutError")
        self.store.insert_spans([ok])
        self.store.insert_spans([failed])
        self.optimize_final()

        self.assertEqual(self.physical_rows(trace(5)), 2)
        rows = self.store.get_rows(PROJECT_A, trace(5))
        self.assertEqual(len(rows), 2)
        self.assertEqual({r["span_id"] for r in rows}, {ROOT})
        self.assertEqual(len({r["content_hash"] for r in rows}), 2)
        self.assertEqual(sorted(r["status_code"] for r in rows), ["ERROR", "OK"])

    # §6.5 (conflict query)
    def test_get_conflicts_reports_the_conflicting_span(self):
        t = trace(105)
        self.store.insert_spans([make_span(trace_id=t)])
        self.store.insert_spans([make_span(trace_id=t, status_code="ERROR")])
        self.store.insert_spans([make_span(trace_id=t)])      #plain redelivery: must not add a version
        conflicts = self.store.get_conflicts(PROJECT_A, t)
        self.assertEqual([(c.span_id, c.versions) for c in conflicts], [(ROOT, 2)])

    def test_get_conflicts_are_ordered_by_span_id(self):
        t = trace(107)
        # Inserted CHILD first so that insert order and span_id order differ.
        for span_id in (CHILD, ROOT):
            self.store.insert_spans([make_span(trace_id=t, span_id=span_id)])
            self.store.insert_spans([make_span(trace_id=t, span_id=span_id, status_code="ERROR")])
        conflicts = self.store.get_conflicts(PROJECT_A, t)
        self.assertEqual([(c.span_id, c.versions) for c in conflicts], [(ROOT, 2), (CHILD, 2)])

    # §6.3
    def test_late_span_is_added_and_earlier_rows_are_unchanged(self):
        root = make_span(trace_id=trace(3))
        self.store.insert_spans([root])
        before = self.store.get_rows(PROJECT_A, trace(3))

        late = make_span(
            trace_id=trace(3), span_id=CHILD, parent_span_id=ROOT,
            started_at=T0 + 100, ended_at=T0 + 900, received_at=T0 + 60_000_000_000,
        )
        self.store.insert_spans([late])
        after = self.store.get_rows(PROJECT_A, trace(3))

        self.assertEqual([r["span_id"] for r in after], [ROOT, CHILD])
        self.assertEqual(after[0], before[0])  # every column, persisted_at included

    # §6.4
    def test_out_of_order_spans_are_read_by_started_at_then_span_id(self):
        t = trace(4)
        root = make_span(trace_id=t, started_at=T0, ended_at=T0 + 1_000)
        child = make_span(trace_id=t, span_id=CHILD, parent_span_id=ROOT, started_at=T0 + 200, ended_at=T0 + 500)
        # Same started_at as `child`, smaller span_id: the tie is broken by span_id.
        sibling = make_span(trace_id=t, span_id="0" * 16, parent_span_id=ROOT, started_at=T0 + 200, ended_at=T0 + 300)
        grandchild = make_span(trace_id=t, span_id=GRANDCHILD, parent_span_id=CHILD, started_at=T0 + 300, ended_at=T0 + 400)

        self.store.insert_spans([grandchild])        # child before its parent, separate parts
        self.store.insert_spans([child, sibling])
        self.store.insert_spans([root])              # root last

        rows = self.store.get_rows(PROJECT_A, t)
        self.assertEqual([r["span_id"] for r in rows], [ROOT, "0" * 16, CHILD, GRANDCHILD])
        self.assertEqual([r["started_at"] for r in rows], [T0, T0 + 200, T0 + 200, T0 + 300])

    # §6.8
    def test_projects_are_isolated(self):
        t = trace(8)
        a = make_span(project_id=PROJECT_A, trace_id=t, span_name="a.run")
        b = make_span(project_id=PROJECT_B, trace_id=t, span_name="b.run")
        self.store.insert_spans([a, b])

        rows_a = self.store.get_rows(PROJECT_A, t)
        rows_b = self.store.get_rows(PROJECT_B, t)
        self.assertEqual([(r["project_id"], r["span_name"]) for r in rows_a], [(PROJECT_A, "a.run")])
        self.assertEqual([(r["project_id"], r["span_name"]) for r in rows_b], [(PROJECT_B, "b.run")])
        self.assertEqual(self.physical_rows(t), 2)  # same trace_id/span_id, two spans

    # §6.9
    def test_missing_parent_and_multiple_roots_are_stored_as_is(self):
        t = trace(9)
        spans = [
            make_span(trace_id=t, span_id=ROOT),
            make_span(trace_id=t, span_id=CHILD, started_at=T0 + 10, ended_at=T0 + 20),  # second root
            make_span(trace_id=t, span_id=GRANDCHILD, parent_span_id=ABSENT, started_at=T0 + 30, ended_at=T0 + 40),
        ]
        self.store.insert_spans(spans)

        rows = self.store.get_rows(PROJECT_A, t)
        self.assertEqual(
            [(r["span_id"], r["parent_span_id"]) for r in rows],
            [(ROOT, None), (CHILD, None), (GRANDCHILD, ABSENT)],
        )

    # §6.10
    def test_batch_of_n_spans_is_one_insert(self):
        t = trace(10)
        spans = [
            make_span(trace_id=t, span_id=f"{i:016x}", parent_span_id=None if i == 0 else f"{0:016x}",
                      started_at=T0 + i, ended_at=T0 + i + 1)
            for i in range(25)
        ]
        with mock.patch.object(self.client, "insert", wraps=self.client.insert) as insert:
            self.store.insert_spans(spans, positions=[(1, 100 + i) for i in range(25)])

        self.assertEqual(insert.call_count, 1)
        self.assertEqual(len(insert.call_args.args[1]), 25)
        self.assertEqual(len(self.store.get_rows(PROJECT_A, t)), 25)

    # §6.11
    def test_payload_states_are_stored_with_their_payloads(self):
        t = trace(11)
        span = make_span(
            trace_id=t,
            input_state="disabled", input_payload="",
            output_state="truncated", output_payload='{"answer": "The first part of a long ans',
            error_state="unavailable", error_payload="",
        )
        self.store.insert_spans([span])

        [row] = self.store.get_rows(PROJECT_A, t)
        self.assertEqual((row["input_state"], row["input_payload"]), ("disabled", ""))
        self.assertEqual((row["output_state"], row["output_payload"]), ("truncated", '{"answer": "The first part of a long ans'))
        self.assertEqual((row["error_state"], row["error_payload"]), ("unavailable", ""))
        stored_as_null_text = self.client.query(
            f"SELECT count() FROM {self.table} WHERE trace_id = %(t)s "
            "AND 'null' IN (input_payload, output_payload, error_payload)",
            parameters={"t": t},
        ).result_rows[0][0]
        self.assertEqual(stored_as_null_text, 0)

    # §6.12
    def test_span_without_model_usage_reads_back_null_not_zero(self):
        t = trace(12)
        self.store.insert_spans([make_span(trace_id=t)])

        [row] = self.store.get_rows(PROJECT_A, t)
        for column in ("model", "provider", "input_tokens", "output_tokens", "total_tokens", "cost",
                       "attempt", "retry_of_span_id", "parent_span_id"):
            self.assertIsNone(row[column], column)
        nulls = self.client.query(
            f"SELECT isNull(input_tokens) AND isNull(output_tokens) AND isNull(total_tokens) AND isNull(cost) "
            f"FROM {self.table} WHERE trace_id = %(t)s",
            parameters={"t": t},
        ).result_rows[0][0]
        self.assertEqual(nulls, 1)

    # §6.13 (storage half; the run list is in PendingReadMethodTests)
    def test_trace_without_root_is_stored_and_readable(self):
        t = trace(13)
        spans = [
            make_span(trace_id=t, span_id=CHILD, parent_span_id=ROOT, started_at=T0 + 10, ended_at=T0 + 20),
            make_span(trace_id=t, span_id=GRANDCHILD, parent_span_id=CHILD, started_at=T0 + 15, ended_at=T0 + 18),
        ]
        self.store.insert_spans(spans)

        rows = self.store.get_rows(PROJECT_A, t)
        self.assertEqual([r["span_id"] for r in rows], [CHILD, GRANDCHILD])
        self.assertTrue(all(r["parent_span_id"] is not None for r in rows))

    def insert_conflict(self, t: str) -> None:
        self.store.insert_spans([make_span(trace_id=t)])
        self.store.insert_spans([make_span(trace_id=t, status_code="ERROR")])

    # Needs ClickHouseTraceStore.get_trace to return TraceRead (it returns list[dict]),
    # built on get_conflicts (§6.5: "the read API returns both versions with a conflict flag").
    def test_get_trace_flags_conflicting_versions(self):
        self.insert_conflict(trace(106))
        read = self.store.get_trace(PROJECT_A, trace(106))
        self.assertEqual(len(read.spans), 2)
        self.assertEqual(read.conflicted_span_ids, frozenset({ROOT}))

    # Needs ClickHouseTraceStore.list_runs (§6.13: "appears in the run list with missing_root = 1").
    def test_trace_without_root_is_listed_with_missing_root(self):
        t = trace(113)
        self.store.insert_spans([make_span(trace_id=t, span_id=CHILD, parent_span_id=ROOT)])
        [run] = [r for r in self.store.list_runs(PROJECT_A, 0, 2**63) if r.trace_id == t]
        self.assertTrue(run.missing_root)
        self.assertIsNone(run.root_name)

    # Same case as InMemoryTraceStoreTests.test_run_list_counts_a_conflicted_span_once.
    def test_run_list_counts_a_conflicted_span_once(self):
        t = trace(114)
        self.insert_conflict(t)
        self.store.insert_spans([make_span(trace_id=t, span_id=CHILD, parent_span_id=ROOT,
                                           started_at=T0 + 10, ended_at=T0 + 20)])
        [run] = [r for r in self.store.list_runs(PROJECT_A, 0, 2**63) if r.trace_id == t]
        self.assertEqual((run.span_count, run.error_span_count), (2, 1))

    # Needs ClickHouseTraceStore.get_conflicts and list_runs: the TraceStore Protocol has four methods.
    def test_store_satisfies_trace_store_protocol(self):
        self.assertIsInstance(self.store, TraceStore)

if __name__ == "__main__":
    unittest.main()
