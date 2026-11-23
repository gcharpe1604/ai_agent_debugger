"""Run a controlled example-agent scenario through the real POST /api/v1/traces route.

The agent CLI exports with the SDK's durable exporter over HTTP to the app
served by uvicorn on a loopback port. Only the publisher (in memory) and the
API-key lookup (every request is the DEFAULT_PROJECT_ID user) are replaced, so
no broker or database is needed and what comes back is the `SpanRecord`s the
trace-writer would receive.

Prints one line per span with its payload states; --payloads also prints the payload text:

    uv run --project backend --locked --with "opentelemetry-api>=1,<2" --with "opentelemetry-sdk>=1,<2" --with "PyYAML>=6,<7" python scripts/show_payload_states.py TOOL-03 [--payloads]
"""

import contextlib
import io
import os
from pathlib import Path
import socket
import sys
import threading
import time

ROOT = Path(__file__).resolve().parents[1]
for directory in [
    "backend/src",
    "sdk/python/src",
    "examples/tool_task_agent/src",
    "examples/rag_agent/src",
]:
    if str(ROOT / directory) not in sys.path:
        sys.path.insert(0, str(ROOT / directory))

# Importing the app requires SESSION_SECRET; this in-process app serves no sessions.
os.environ.setdefault("SESSION_SECRET", "show-payload-states-only")

import uvicorn

from agent_debugger_api.api.routes.traces import get_span_publisher
from agent_debugger_api.auth.deps import ingest_user
from agent_debugger_api.contracts.fakes import InMemorySpanPublisher
from agent_debugger_api.db.models import User
from agent_debugger_api.ingest.settings import DEFAULT_PROJECT_ID
from agent_debugger_api.main import app

LOCAL_USER = User(id=DEFAULT_PROJECT_ID, email="local@example.com", name="local", password_hash="unused",
                  project_id=DEFAULT_PROJECT_ID, key_prefix="adbg_sk_none", key_hash="unused")


class DurableApp:
    """The backend app on a loopback port with an in-memory publisher."""

    def __enter__(self):
        self.publisher = InMemorySpanPublisher()
        app.dependency_overrides[get_span_publisher] = lambda: self.publisher
        app.dependency_overrides[ingest_user] = lambda: LOCAL_USER
        self._listener = socket.socket()
        self._listener.bind(("127.0.0.1", 0))
        self.endpoint = f"http://127.0.0.1:{self._listener.getsockname()[1]}/api/v1/traces"
        self._server = uvicorn.Server(uvicorn.Config(app, log_level="error"))
        self._thread = threading.Thread(
            target=self._server.run, kwargs={"sockets": [self._listener]}, daemon=True
        )
        self._thread.start()
        deadline = time.monotonic() + 10
        while not self._server.started and time.monotonic() < deadline:
            time.sleep(0.02)
        if not self._server.started:
            raise RuntimeError("backend app did not start")
        return self

    def __exit__(self, *exc):
        self._server.should_exit = True
        self._thread.join(timeout=10)
        self._listener.close()
        app.dependency_overrides.pop(get_span_publisher, None)
        app.dependency_overrides.pop(ingest_user, None)
        return False

    def run_scenario(self, scenario_id):
        """Run `<agent> run <scenario_id>` and return its SpanRecords in start order."""
        if scenario_id.startswith("TOOL-"):
            from tool_task_agent.cli import main
        elif scenario_id.startswith("RAG-"):
            from rag_agent.cli import main
        else:
            raise ValueError(f"no agent for {scenario_id}")
        before = len(self.publisher.acked)
        previous = os.environ.get("AGENT_DEBUGGER_ENDPOINT")
        os.environ["AGENT_DEBUGGER_ENDPOINT"] = self.endpoint
        try:
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()) as log:
                code = main(["run", scenario_id])
        finally:
            if previous is None:
                del os.environ["AGENT_DEBUGGER_ENDPOINT"]
            else:
                os.environ["AGENT_DEBUGGER_ENDPOINT"] = previous
        if code != 0 or "exported" not in log.getvalue():
            raise RuntimeError(f"{scenario_id}: exit {code}; {log.getvalue().strip()}")
        records = [record for _, record in self.publisher.acked[before:]]
        return sorted(records, key=lambda record: (record.started_at, record.span_id))


def payload_state_table(records):
    """One line per span, in tree order: status and the three payload states."""
    by_id = {record.span_id: record for record in records}
    children = {}
    for record in records:  # already in start order
        parent = record.parent_span_id if record.parent_span_id in by_id else None
        children.setdefault(parent, []).append(record)
    ordered, depth = [], {}
    stack = [(record, 0) for record in reversed(children.get(None, []))]
    while stack:
        record, level = stack.pop()
        ordered.append(record)
        depth[record.span_id] = level
        stack.extend((child, level + 1) for child in reversed(children.get(record.span_id, [])))
    records = ordered
    rows = [("span", "type", "status", "input", "output", "error", "attempt", "retry_of")]
    for record in records:
        rows.append((
            "  " * depth[record.span_id] + record.span_name,
            record.operation_type,
            record.status_code.value,
            f"{record.input_state.value} ({len(record.input_payload)})",
            f"{record.output_state.value} ({len(record.output_payload)})",
            f"{record.error_state.value} ({len(record.error_payload)})",
            "" if record.attempt is None else str(record.attempt),
            record.retry_of_span_id or "",
        ))
    widths = [max(len(row[column]) for row in rows) for column in range(len(rows[0]))]
    return "\n".join(
        "  ".join(cell.ljust(width) for cell, width in zip(row, widths)).rstrip() for row in rows
    )


if __name__ == "__main__":
    scenario = sys.argv[1] if len(sys.argv) > 1 else "TOOL-03"
    sys.stdout.reconfigure(encoding="utf-8")
    with DurableApp() as durable:
        spans = durable.run_scenario(scenario)
    print(f"{scenario}  trace {spans[0].trace_id}  {len(spans)} spans  (payload sizes in characters)\n")
    print(payload_state_table(spans))
    if "--payloads" in sys.argv:
        for span in spans:
            for kind in ("input", "output", "error"):
                payload = getattr(span, f"{kind}_payload")
                if payload:
                    print(f"\n{span.span_name} [{span.span_id}] {kind}:\n  {payload}")
