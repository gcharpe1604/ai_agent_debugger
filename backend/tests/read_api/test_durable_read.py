"""Durable read API (GET /api/v1/projects/...) through the real route.

`DurableReadClickHouseTests` reads from a real ClickHouse (scratch database,
production schema). The other classes need no server.
"""

import os
import unittest
from concurrent.futures import ThreadPoolExecutor
from unittest import mock

from fastapi.testclient import TestClient

from agent_debugger_api.api.routes.durable_runs import get_trace_store
from agent_debugger_api.auth.deps import current_user
from agent_debugger_api.contracts.fakes import InMemoryTraceStore
from agent_debugger_api.ingest.settings import DEFAULT_PROJECT_ID
from agent_debugger_api.main import app
from agent_debugger_api.trace_writer.clickhouse_store import ClickHouseTraceStore
from agent_debugger_api.trace_writer.content_hash import content_hash
from agent_debugger_api.trace_writer.settings import WriterSettings
from agent_debugger_api.traces.read_store import LazyReadStore, read_client
from tests.auth.factories import make_user
from tests.clickhouse.harness import ClickHouseTestCase
from tests.contracts.factories import PROJECT_B, T0, make_span

ROOT, CHILD, GRANDCHILD, RETRY, OTHER = ("a" * 16, "b" * 16, "c" * 16, "d" * 16, "e" * 16)
ABSENT = "f" * 16
RUNS = "/api/v1/projects/default/runs"
HOUR = 3_600_000_000_000  # ns; each list test gets its own hour so tests do not see each other's runs


def trace(n: int) -> str:
    return f"{n:032x}"


def span(**overrides):
    """A SpanRecord in the project the read API serves."""
    overrides.setdefault("project_id", DEFAULT_PROJECT_ID)
    return make_span(**overrides)


class _ApiCase(unittest.TestCase):
    store = None

    def setUp(self):
        app.dependency_overrides[get_trace_store] = lambda: self.store
        # A logged-in user whose project is DEFAULT_PROJECT_ID; the real current_user is
        # tested in tests/auth/test_authorization.py.
        self.user = make_user(project_id=DEFAULT_PROJECT_ID)
        app.dependency_overrides[current_user] = lambda: self.user
        self.addCleanup(app.dependency_overrides.clear)
        # Not a loopback client, and local mode is off: the local-1 gate must not apply.
        env = mock.patch.dict(os.environ)
        env.start()
        self.addCleanup(env.stop)
        os.environ.pop("AGENT_DEBUGGER_LOCAL_MODE", None)
        self.client = TestClient(app, client=("203.0.113.7", 50000))

    def get(self, path, **params):
        return self.client.get(path, params=params)


class _FirstErrorCases:
    """first_error in the run list, the same on ClickHouse and on the in-memory store."""

    def list_by_trace(self, *spans):
        self.store.insert_spans(list(spans))
        # Every run here starts at T0; other tests in the class start an hour or more later.
        return {r["trace_id"]: r for r in self.get(RUNS, started_from=T0, started_to=T0 + HOUR, limit=200).json()["runs"]}

    def test_run_list_first_error_is_the_deepest_error_of_a_failed_run(self):
        t = trace(0xE01)
        runs = self.list_by_trace(
            span(trace_id=t, status_code="ERROR", started_at=T0, ended_at=T0 + 900),
            # An OK span between two ERROR spans: the root still carries the tool's error.
            span(trace_id=t, span_id=CHILD, parent_span_id=ROOT, operation_type="agent", span_name="agent.run",
                 started_at=T0 + 10, ended_at=T0 + 800),
            span(trace_id=t, span_id=GRANDCHILD, parent_span_id=CHILD, operation_type="tool", span_name="tool.pay",
                 status_code="ERROR", error_type="ToolTimeout", started_at=T0 + 20, ended_at=T0 + 30),
        )
        self.assertEqual(
            runs[t]["first_error"],
            {"span_id": GRANDCHILD, "span_name": "tool.pay", "operation_type": "tool",
             "error_type": "ToolTimeout", "originating_error_span_count": 1},
        )

    def test_run_list_first_error_is_null_for_a_completed_run(self):
        t = trace(0xE02)
        runs = self.list_by_trace(
            span(trace_id=t, started_at=T0, ended_at=T0 + 900),
            span(trace_id=t, span_id=CHILD, parent_span_id=ROOT, operation_type="tool", started_at=T0 + 10, ended_at=T0 + 20),
        )
        self.assertEqual(runs[t]["status"], "OK")
        self.assertIsNone(runs[t]["first_error"])

    def test_run_list_first_error_is_null_for_a_recovered_retry(self):
        t = trace(0xE03)
        runs = self.list_by_trace(
            span(trace_id=t, started_at=T0, ended_at=T0 + 900),
            span(trace_id=t, span_id=CHILD, parent_span_id=ROOT, operation_type="tool", span_name="tool.pay",
                 status_code="ERROR", error_type="Unavailable", attempt=1, started_at=T0 + 10, ended_at=T0 + 20),
            span(trace_id=t, span_id=RETRY, parent_span_id=ROOT, operation_type="tool", span_name="tool.pay",
                 attempt=2, retry_of_span_id=CHILD, started_at=T0 + 30, ended_at=T0 + 40),
        )
        self.assertEqual((runs[t]["status"], runs[t]["error_span_count"]), ("OK", 1))
        self.assertIsNone(runs[t]["first_error"])

    def test_run_list_first_error_counts_every_originating_error(self):
        t = trace(0xE04)
        runs = self.list_by_trace(
            span(trace_id=t, status_code="ERROR", started_at=T0, ended_at=T0 + 900),
            span(trace_id=t, span_id=OTHER, parent_span_id=ROOT, status_code="ERROR", span_name="later",
                 started_at=T0 + 50, ended_at=T0 + 60),
            span(trace_id=t, span_id=CHILD, parent_span_id=ROOT, status_code="ERROR", span_name="earlier",
                 started_at=T0 + 10, ended_at=T0 + 20),
        )
        self.assertEqual((runs[t]["first_error"]["span_name"], runs[t]["first_error"]["originating_error_span_count"]), ("earlier", 2))


class DurableReadClickHouseTests(ClickHouseTestCase, _FirstErrorCases, _ApiCase):
    def setUp(self):
        self.store = ClickHouseTraceStore(self.client, table=self.table)
        self.clickhouse = self.client
        _ApiCase.setUp(self)  # replaces self.client with the HTTP test client

    # --- run list -----------------------------------------------------------------

    def test_run_list_is_newest_first_with_root_facts_and_counts(self):
        base = T0 + 1 * HOUR
        old, new, rootless = trace(0x101), trace(0x102), trace(0x103)
        self.store.insert_spans(
            [
                span(trace_id=old, started_at=base, ended_at=base + 500, service_name="tool_agent", execution_mode="controlled"),
                span(trace_id=old, span_id=CHILD, parent_span_id=ROOT, operation_type="tool", span_name="tool.search",
                     status_code="ERROR", started_at=base + 10, ended_at=base + 900),
                span(trace_id=new, started_at=base + 2_000, ended_at=base + 2_500, status_code="ERROR", span_name="rag.failed"),
                span(trace_id=rootless, span_id=CHILD, parent_span_id=ABSENT, started_at=base + 1_000, ended_at=base + 1_001),
                # Another project's run in the same window must not appear.
                span(project_id=PROJECT_B, trace_id=trace(0x1FF), started_at=base + 50, ended_at=base + 60),
            ]
        )
        response = self.get(RUNS, started_from=base, started_to=base + HOUR)
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["project"], "default")
        self.assertIsNone(body["next_cursor"])
        self.assertEqual([r["trace_id"] for r in body["runs"]], [new, rootless, old])
        self.assertEqual(
            body["runs"][2],
            {
                "trace_id": old,
                "name": "rag.run",
                "missing_root": False,
                "status": "OK",
                "service": "tool_agent",
                "execution_mode": "controlled",
                "start_time_unix_nano": str(base),
                "end_time_unix_nano": str(base + 900),  # latest span end, not the root's
                "span_count": 2,
                "error_span_count": 1,
                "first_error": None,  # the root is OK: a completed run has no first error
            },
        )
        self.assertEqual((body["runs"][0]["status"], body["runs"][0]["name"]), ("ERROR", "rag.failed"))
        missing = body["runs"][1]
        self.assertEqual(
            (missing["missing_root"], missing["name"], missing["status"], missing["service"]),
            (True, None, None, None),
        )

    def test_time_range_is_inclusive_from_and_exclusive_to(self):
        base = T0 + 2 * HOUR
        self.store.insert_spans(
            [
                span(trace_id=trace(0x201), started_at=base, ended_at=base + 1),
                span(trace_id=trace(0x202), started_at=base + 100, ended_at=base + 101),
            ]
        )
        ids = lambda **p: [r["trace_id"] for r in self.get(RUNS, **p).json()["runs"]]  # noqa: E731
        self.assertEqual(ids(started_from=base, started_to=base + 100), [trace(0x201)])
        self.assertEqual(ids(started_from=base + 1, started_to=base + 101), [trace(0x202)])
        self.assertEqual(ids(started_from=base + 101, started_to=base + HOUR), [])

    def test_paging_returns_every_run_once_even_when_start_times_tie(self):
        base = T0 + 3 * HOUR
        starts = {0x301: 0, 0x302: 50, 0x303: 50, 0x304: 50, 0x305: 90}  # three runs share a start
        self.store.insert_spans(
            [span(trace_id=trace(n), started_at=base + s, ended_at=base + s + 1) for n, s in starts.items()]
        )
        seen, cursor, pages = [], None, 0
        while True:
            params = {"started_from": base, "started_to": base + HOUR, "limit": 2}
            if cursor:
                params["cursor"] = cursor
            body = self.get(RUNS, **params).json()
            seen += [r["trace_id"] for r in body["runs"]]
            pages += 1
            cursor = body["next_cursor"]
            if cursor is None:
                break
            self.assertEqual(len(body["runs"]), 2)
        self.assertEqual(pages, 3)
        # Newest first; ties in descending trace_id.
        self.assertEqual(seen, [trace(n) for n in (0x305, 0x304, 0x303, 0x302, 0x301)])

    def test_a_full_last_page_has_no_next_cursor(self):
        base = T0 + 4 * HOUR
        self.store.insert_spans(
            [span(trace_id=trace(0x400 + i), started_at=base + i, ended_at=base + i + 1) for i in range(2)]
        )
        body = self.get(RUNS, started_from=base, started_to=base + HOUR, limit=2).json()
        self.assertEqual(len(body["runs"]), 2)
        self.assertIsNone(body["next_cursor"])

    def test_identical_redelivery_is_one_span_in_the_list_and_in_the_run(self):
        base = T0 + 5 * HOUR
        t = trace(0x501)
        batch = [span(trace_id=t, started_at=base, ended_at=base + 1)]
        self.store.insert_spans(batch)
        self.store.insert_spans(batch)
        [run] = self.get(RUNS, started_from=base, started_to=base + HOUR).json()["runs"]
        self.assertEqual(run["span_count"], 1)
        body = self.get(f"{RUNS}/{t}").json()
        self.assertEqual(len(body["spans"]), 1)
        self.assertFalse(body["run"]["conflicted"])
        self.assertEqual(body["tree"]["warnings"], [])

    # --- one run ------------------------------------------------------------------

    def test_run_is_reconstructed_from_parent_ids_not_insert_order(self):
        t = trace(0x601)
        start = T0 + 6 * HOUR + 123_456_789  # needs all nine sub-second digits
        # Inserted deepest first, in two batches: arrival order is the reverse of the tree.
        self.store.insert_spans(
            [span(trace_id=t, span_id=GRANDCHILD, parent_span_id=CHILD, operation_type="tool", span_name="tool.search",
                  status_code="ERROR", error_type="TimeoutError", started_at=start + 20, ended_at=start + 30)]
        )
        self.store.insert_spans(
            [
                span(trace_id=t, span_id=OTHER, parent_span_id=ROOT, operation_type="model", span_name="model.answer",
                     started_at=start + 40, ended_at=start + 50),
                span(trace_id=t, span_id=CHILD, parent_span_id=ROOT, operation_type="agent", span_name="agent.plan",
                     started_at=start + 10, ended_at=start + 35),
                span(trace_id=t, started_at=start, ended_at=start + 60, status_code="ERROR", service_name="rag_agent",
                     execution_mode="live", input_payload='{"q":"secret question"}'),
            ]
        )
        response = self.get(f"{RUNS}/{t}")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["cache-control"], "no-store")
        body = response.json()
        self.assertEqual(
            [(n["span_id"], n["depth"], n["parent_span_id"]) for n in body["tree"]["nodes"]],
            [(ROOT, 0, None), (CHILD, 1, ROOT), (GRANDCHILD, 2, CHILD), (OTHER, 1, ROOT)],
        )
        self.assertEqual(body["tree"]["top_level"], [ROOT])
        self.assertEqual(body["tree"]["warnings"], [])
        self.assertTrue(all(n["flags"] == [] for n in body["tree"]["nodes"]))
        self.assertEqual([s["span_id"] for s in body["spans"]], [ROOT, CHILD, GRANDCHILD, OTHER])
        run = body["run"]
        self.assertEqual(
            {k: run[k] for k in ("trace_id", "name", "status", "service", "execution_mode", "root_span_id",
                                 "span_count", "error_span_count", "missing_root", "conflicted")},
            {"trace_id": t, "name": "rag.run", "status": "ERROR", "service": "rag_agent", "execution_mode": "live",
             "root_span_id": ROOT, "span_count": 4, "error_span_count": 2, "missing_root": False, "conflicted": False},
        )
        # Exact nanoseconds, as strings.
        self.assertEqual((run["start_time_unix_nano"], run["end_time_unix_nano"]), (str(start), str(start + 60)))
        # The deepest ERROR span, not the root that carries it.
        self.assertEqual(
            run["first_error"],
            {"span_id": GRANDCHILD, "span_name": "tool.search", "operation_type": "tool",
             "error_type": "TimeoutError", "originating_error_span_count": 1},
        )
        # The run read carries payload states but no payload text.
        root = body["spans"][0]
        self.assertEqual(root["input_state"], "captured")
        self.assertNotIn("input_payload", root)
        self.assertNotIn("secret question", response.text)
        self.assertNotIn("project_id", root)

    def test_orphan_second_root_cycle_and_conflict_are_kept_and_flagged(self):
        t = trace(0x701)
        base = T0 + 7 * HOUR
        loop_a, loop_b = "1" * 16, "2" * 16
        self.store.insert_spans(
            [
                span(trace_id=t, started_at=base, ended_at=base + 100),
                span(trace_id=t, span_id=OTHER, started_at=base + 5, ended_at=base + 6, span_name="second.root"),
                span(trace_id=t, span_id=CHILD, parent_span_id=ABSENT, started_at=base + 10, ended_at=base + 20),
                span(trace_id=t, span_id=loop_a, parent_span_id=loop_b, started_at=base + 30, ended_at=base + 31),
                span(trace_id=t, span_id=loop_b, parent_span_id=loop_a, started_at=base + 32, ended_at=base + 33),
                span(trace_id=t, span_id=GRANDCHILD, parent_span_id=ROOT, started_at=base + 40, ended_at=base + 41,
                     span_name="tool.v1", received_at=base + 1_000_000),
            ]
        )
        # Same span identity, different content, received later: a conflict.
        self.store.insert_spans(
            [span(trace_id=t, span_id=GRANDCHILD, parent_span_id=ROOT, started_at=base + 40, ended_at=base + 41,
                  span_name="tool.v2", status_code="ERROR", received_at=base + 9_000_000)]
        )
        self.clickhouse.command(f"OPTIMIZE TABLE {self.table} FINAL")  # a merge must not hide the conflict

        body = self.get(f"{RUNS}/{t}").json()
        flags = {n["span_id"]: n["flags"] for n in body["tree"]["nodes"]}
        self.assertEqual(
            flags,
            {ROOT: [], OTHER: [], CHILD: ["missing_parent"], loop_a: ["cycle", "cycle_break"],
             loop_b: ["cycle"], GRANDCHILD: ["conflict"]},
        )
        self.assertEqual(body["tree"]["top_level"], [ROOT, OTHER, CHILD, loop_a])
        nodes = {n["span_id"]: n for n in body["tree"]["nodes"]}
        self.assertEqual((nodes[CHILD]["parent_span_id"], nodes[CHILD]["recorded_parent_span_id"]), (None, ABSENT))
        self.assertEqual(nodes[loop_b]["parent_span_id"], loop_a)
        self.assertEqual(
            [(w["code"], w["span_ids"]) for w in body["tree"]["warnings"]],
            [("multiple_roots", [ROOT, OTHER]), ("missing_parent", [CHILD]),
             ("cycle", [loop_a, loop_b]), ("conflict", [GRANDCHILD])],
        )
        # Both versions are returned, each with its own hash and receipt time; neither is dropped.
        versions = [s for s in body["spans"] if s["span_id"] == GRANDCHILD]
        self.assertEqual([v["name"] for v in versions], ["tool.v1", "tool.v2"])
        self.assertEqual(len({v["content_hash"] for v in versions}), 2)
        self.assertEqual(nodes[GRANDCHILD]["versions"], [v["content_hash"] for v in versions])
        self.assertEqual([v["received_at_unix_nano"] for v in versions], [str(base + 1_000_000), str(base + 9_000_000)])
        run = body["run"]
        self.assertTrue(run["conflicted"])
        self.assertEqual((run["span_count"], run["error_span_count"]), (6, 1))  # the conflicted span counts once
        self.assertEqual((run["name"], run["root_span_id"]), ("rag.run", ROOT))  # the earliest root

    def test_trace_with_no_root_is_readable(self):
        t = trace(0x801)
        base = T0 + 8 * HOUR
        self.store.insert_spans(
            [span(trace_id=t, span_id=CHILD, parent_span_id=ABSENT, started_at=base, ended_at=base + 5,
                  operation_type="tool", span_name="tool.only")]
        )
        body = self.get(f"{RUNS}/{t}").json()
        self.assertEqual([w["code"] for w in body["tree"]["warnings"]], ["missing_root", "missing_parent"])
        run = body["run"]
        self.assertEqual((run["missing_root"], run["name"], run["status"], run["root_span_id"]), (True, None, None, None))
        self.assertEqual(run["span_count"], 1)

    def test_unknown_trace_and_other_projects_trace_are_404(self):
        t = trace(0x901)
        self.store.insert_spans([span(project_id=PROJECT_B, trace_id=t)])
        for path in (f"{RUNS}/{t}", f"{RUNS}/{t}/spans/{ROOT}", f"{RUNS}/{trace(0x9FF)}"):
            response = self.get(path)
            self.assertEqual((response.status_code, response.json()), (404, {"detail": "Trace not found"}), path)

    # --- one span -----------------------------------------------------------------

    def test_span_read_has_payloads_states_events_and_retry_links(self):
        t = trace(0xA01)
        base = T0 + 10 * HOUR
        self.store.insert_spans(
            [
                span(trace_id=t, started_at=base, ended_at=base + 100),
                span(trace_id=t, span_id=CHILD, parent_span_id=ROOT, operation_type="tool", span_name="tool.search",
                     status_code="ERROR", status_description="timed out", error_type="TimeoutError",
                     started_at=base + 10, ended_at=base + 20, attempt=1,
                     input_state="redacted", input_payload='{"api_key":"[redacted]","q":"refund"}',
                     output_state="unavailable", error_state="captured",
                     error_payload='{"type":"TimeoutError","message":"no answer"}',
                     attributes={"debugger.step": "search"},
                     events=[{"name": "exception", "time": base + 19, "attributes": {"exception.type": "TimeoutError"}}],
                     links=[{"trace_id": t, "span_id": ROOT, "relation": "depends_on"}],
                     model="m-1", provider="p", input_tokens=3, output_tokens=4, total_tokens=7, cost="0.00125"),
                span(trace_id=t, span_id=RETRY, parent_span_id=ROOT, operation_type="tool", span_name="tool.search",
                     started_at=base + 30, ended_at=base + 40, attempt=2, retry_of_span_id=CHILD),
            ]
        )
        response = self.get(f"{RUNS}/{t}/spans/{CHILD}")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["cache-control"], "no-store")
        body = response.json()
        self.assertEqual((body["span_id"], body["parent_span_id"], body["flags"], body["conflicted"]), (CHILD, ROOT, [], False))
        [version] = body["versions"]
        expected = {
            "name": "tool.search", "operation_type": "tool", "parent_span_id": ROOT,
            "status": {"code": "ERROR", "description": "timed out"}, "error_type": "TimeoutError",
            "start_time_unix_nano": str(base + 10), "end_time_unix_nano": str(base + 20), "attempt": 1,
            "input_state": "redacted", "input_payload": '{"api_key":"[redacted]","q":"refund"}',
            "output_state": "unavailable", "output_payload": "",
            "error_state": "captured", "error_payload": '{"type":"TimeoutError","message":"no answer"}',
            "attributes": {"debugger.step": "search"},
            "events": [{"name": "exception", "time_unix_nano": str(base + 19), "attributes": {"exception.type": "TimeoutError"}}],
            "links": [{"trace_id": t, "span_id": ROOT, "relation": "depends_on"}],
            "model": "m-1", "provider": "p", "input_tokens": 3, "output_tokens": 4, "total_tokens": 7,
            "cost": "0.001250000",  # Decimal(18, 9) text; same number as sent
            "retry_of_span_id": None,
        }
        self.assertEqual({k: version[k] for k in expected}, expected)
        self.assertEqual(len(version["content_hash"]), 64)
        self.assertIsNone(body["retry_of"])
        self.assertEqual(
            body["retries"],
            [{"span_id": RETRY, "name": "tool.search", "operation_type": "tool", "status": {"code": "OK"}, "attempt": 2}],
        )
        self.assertTrue(body["run"]["recorded_recovered_retry"])

        retry = self.get(f"{RUNS}/{t}/spans/{RETRY}").json()
        self.assertEqual(retry["retry_of"]["span_id"], CHILD)
        self.assertEqual(retry["retry_of"]["status"], {"code": "ERROR"})
        self.assertEqual(retry["versions"][0]["retry_of_span_id"], CHILD)

    def test_conflicted_span_read_returns_every_version_with_its_payload(self):
        t = trace(0xB01)
        base = T0 + 11 * HOUR
        common = dict(trace_id=t, started_at=base, ended_at=base + 1)
        self.store.insert_spans([span(**common, output_payload='"first"', received_at=base + 2_000_000)])
        self.store.insert_spans([span(**common, output_payload='"second"', received_at=base + 5_000_000)])
        body = self.get(f"{RUNS}/{t}/spans/{ROOT}").json()
        self.assertTrue(body["conflicted"])
        self.assertEqual(body["flags"], ["conflict"])
        self.assertEqual([v["output_payload"] for v in body["versions"]], ['"first"', '"second"'])
        self.assertEqual(len({v["content_hash"] for v in body["versions"]}), 2)

    def test_span_not_in_the_trace_is_404(self):
        t = trace(0xC01)
        self.store.insert_spans([span(trace_id=t)])
        response = self.get(f"{RUNS}/{t}/spans/{ABSENT}")
        self.assertEqual((response.status_code, response.json()), (404, {"detail": "Span not found"}))

    # --- the shared client ----------------------------------------------------------

    def test_one_shared_client_serves_parallel_reads(self):
        # What main.py builds: one LazyReadStore, called from many request threads.
        t = trace(0xD01)
        self.store.insert_spans([span(trace_id=t)])
        clients = []

        def factory():
            clients.append(read_client(WriterSettings()))
            return ClickHouseTraceStore(clients[-1], table=self.table)

        lazy = LazyReadStore(factory)
        self.addCleanup(lambda: [c.close() for c in clients])
        with ThreadPoolExecutor(max_workers=16) as pool:
            results = list(pool.map(lambda _: lazy.get_trace(DEFAULT_PROJECT_ID, t), range(64)))
        self.assertEqual({len(r.spans) for r in results}, {1})
        self.assertEqual(len(clients), 1)  # connected once


class DurableReadValidationTests(_ApiCase):
    """Request checks that must be answered before the store is touched."""

    def setUp(self):
        self.store = mock.Mock(spec=InMemoryTraceStore)
        super().setUp()

    def test_only_the_default_project_exists(self):
        for path in ("/api/v1/projects/other/runs", f"/api/v1/projects/other/runs/{trace(1)}",
                     f"/api/v1/projects/other/runs/{trace(1)}/spans/{ROOT}",
                     "/api/v1/projects/local/runs", f"/api/v1/projects/{DEFAULT_PROJECT_ID}/runs"):
            response = self.get(path)
            self.assertEqual((response.status_code, response.json()), (404, {"detail": "Project not found"}), path)
        self.assertEqual(self.store.mock_calls, [])

    def test_default_project_is_read_with_the_users_project_id_never_the_string(self):
        self.user = make_user(project_id=PROJECT_B)
        self.store.list_runs.return_value = []
        self.store.get_trace.return_value = None
        self.get(RUNS)
        self.get(f"{RUNS}/{trace(1)}")
        self.get(f"{RUNS}/{trace(1)}/spans/{ROOT}")
        self.assertEqual(self.store.list_runs.call_args.args[0], PROJECT_B)
        self.assertEqual(self.store.get_trace.call_args_list, [mock.call(PROJECT_B, trace(1))] * 2)

    def test_default_list_window_is_all_time_first_page_of_fifty(self):
        self.store.list_runs.return_value = []
        self.assertEqual(self.get(RUNS).json(), {"project": "default", "runs": [], "next_cursor": None})
        # limit + 1: the extra row only says whether another page exists.
        self.assertEqual(self.store.list_runs.call_args.args, (DEFAULT_PROJECT_ID, 0, 2**63 - 1, 51, None))

    def test_bad_list_parameters_are_422(self):
        for params in ({"limit": 0}, {"limit": 201}, {"started_from": -1}, {"started_to": 2**63},
                       {"started_from": "yesterday"}, {"cursor": "abc"}, {"cursor": f"1:{'G' * 32}"},
                       {"cursor": f"{2**63}:{trace(1)}"}, {"cursor": f"1:{trace(1)}0"}):
            self.assertEqual(self.get(RUNS, **params).status_code, 422, params)
        self.assertEqual(self.store.mock_calls, [])

    def test_malformed_trace_and_span_ids_are_422(self):
        for path in (f"{RUNS}/not-a-trace", f"{RUNS}/{'A' * 32}", f"{RUNS}/{trace(1)}/spans/xyz",
                     f"{RUNS}/{trace(1)}/spans/{'A' * 16}"):
            self.assertEqual(self.get(path).status_code, 422, path)
        self.assertEqual(self.store.mock_calls, [])

    def test_cursor_is_passed_to_the_store_as_start_time_and_trace_id(self):
        self.store.list_runs.return_value = []
        self.get(RUNS, cursor=f"{T0}:{trace(7)}", limit=10)
        self.assertEqual(self.store.list_runs.call_args.args, (DEFAULT_PROJECT_ID, 0, 2**63 - 1, 11, (T0, trace(7))))

    def test_project_listing_is_the_users_one_project_and_needs_no_store_or_local_mode(self):
        response = self.get("/api/v1/projects")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), [{"id": "default", "name": "Ada"}])
        self.assertEqual(response.headers["cache-control"], "no-store")
        self.assertEqual(self.store.mock_calls, [])
        # The local profile is still gated on its own switch.
        self.assertEqual(self.get("/api/v1/local/status").status_code, 503)


class DurableReadUnavailableStoreTests(_ApiCase):
    def test_unreachable_clickhouse_is_503_not_empty_data(self):
        settings = WriterSettings(clickhouse_host="127.0.0.1", clickhouse_port=9)  # nothing listens here
        self.store = LazyReadStore(lambda: ClickHouseTraceStore(read_client(settings)))
        for path in (RUNS, f"{RUNS}/{trace(1)}", f"{RUNS}/{trace(1)}/spans/{ROOT}"):
            response = self.get(path)
            self.assertEqual(response.status_code, 503, path)
            self.assertEqual(response.headers["retry-after"], "1")
            self.assertEqual(response.json(), {"detail": "Trace store unavailable; nothing was read. Retry later."})

    def test_store_is_reconnected_after_a_failure(self):
        working = InMemoryTraceStore(content_hash=content_hash)
        working.insert_spans([span()])
        attempts = []

        def factory():
            attempts.append(1)
            if len(attempts) == 1:
                raise OSError("connection refused")
            return working

        self.store = LazyReadStore(factory)
        self.assertEqual(self.get(RUNS).status_code, 503)
        response = self.get(RUNS)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()["runs"]), 1)
        self.assertEqual(len(attempts), 2)

    def test_a_bug_in_the_store_is_not_reported_as_unavailable(self):
        def broken(*_args):
            raise KeyError("programming error")

        self.store = mock.Mock(spec=InMemoryTraceStore)
        self.store.list_runs.side_effect = broken
        with self.assertRaises(KeyError):
            self.get(RUNS)


class DurableReadFakeStoreTests(_FirstErrorCases, _ApiCase):
    """The same route over InMemoryTraceStore: the fake and ClickHouse must page alike."""

    def setUp(self):
        self.store = InMemoryTraceStore(content_hash=content_hash)
        super().setUp()

    def test_paging_with_tied_start_times_matches_the_clickhouse_order(self):
        starts = {0x301: 0, 0x302: 50, 0x303: 50, 0x304: 50, 0x305: 90}
        self.store.insert_spans([span(trace_id=trace(n), started_at=T0 + s, ended_at=T0 + s + 1) for n, s in starts.items()])
        seen, cursor = [], None
        while True:
            body = self.get(RUNS, limit=2, **({"cursor": cursor} if cursor else {})).json()
            seen += [r["trace_id"] for r in body["runs"]]
            cursor = body["next_cursor"]
            if cursor is None:
                break
        self.assertEqual(seen, [trace(n) for n in (0x305, 0x304, 0x303, 0x302, 0x301)])

    def test_list_row_and_run_read_agree_on_the_shared_fields(self):
        t = trace(0x10)
        self.store.insert_spans(
            [
                span(trace_id=t, service_name="svc", execution_mode="controlled", status_code="ERROR"),
                span(trace_id=t, span_id=CHILD, parent_span_id=ROOT, status_code="ERROR", started_at=T0 + 1, ended_at=T0 + 9_000),
            ]
        )
        [row] = self.get(RUNS).json()["runs"]
        run = self.get(f"{RUNS}/{t}").json()["run"]
        self.assertEqual(row, {key: run[key] for key in row})


if __name__ == "__main__":
    unittest.main()
