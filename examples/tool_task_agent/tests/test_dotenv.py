"""The CLI loads the nearest .env before any TraceSession; a shell variable still wins.

A stand-in for POST /api/v1/traces on loopback records the Authorization header
of every batch the session exports, so the tests see what the SDK actually sent.
"""

import http.server
import json
import threading

import pytest

from tool_task_agent.cli import main

SCENARIO = "TOOL-01"
DOTENV_KEY = "adbg_sk_" + "d" * 43
SHELL_KEY = "adbg_sk_" + "s" * 43
NAMES = ("AGENT_DEBUGGER_ENDPOINT", "AGENT_DEBUGGER_API_KEY")


@pytest.fixture
def ingest():
    batches = []

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_POST(self):
            body = self.rfile.read(int(self.headers.get("Content-Length", "0")))
            batches.append(
                (
                    self.path,
                    self.headers.get("Authorization"),
                    len(json.loads(body)["spans"]),
                )
            )
            self.send_response(202)
            self.send_header("Content-Length", "0")
            self.end_headers()

        def log_message(self, *args):
            pass

    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_port}/api/v1/traces", batches
    server.shutdown()
    server.server_close()


@pytest.fixture
def workdir(tmp_path, monkeypatch):
    # setenv then delenv records the variable, so whatever load_dotenv sets is undone afterwards.
    for name in NAMES:
        monkeypatch.setenv(name, "")
        monkeypatch.delenv(name)
    monkeypatch.chdir(tmp_path)
    return tmp_path


def test_dotenv_endpoint_and_key_reach_the_session(workdir, ingest):
    endpoint, batches = ingest
    (workdir / ".env").write_text(
        f"AGENT_DEBUGGER_ENDPOINT={endpoint}\nAGENT_DEBUGGER_API_KEY={DOTENV_KEY}\n",
        encoding="utf-8",
    )
    assert main(["run", SCENARIO]) == 0
    assert batches
    assert {(path, auth) for path, auth, _ in batches} == {
        ("/api/v1/traces", f"Bearer {DOTENV_KEY}")
    }
    assert sum(count for _, _, count in batches) > 0


def test_shell_value_overrides_dotenv(workdir, ingest, monkeypatch):
    endpoint, batches = ingest
    # The .env points nowhere useful and has another key; the shell values must win.
    (workdir / ".env").write_text(
        f"AGENT_DEBUGGER_ENDPOINT=http://127.0.0.1:9/api/v1/traces\nAGENT_DEBUGGER_API_KEY={DOTENV_KEY}\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("AGENT_DEBUGGER_ENDPOINT", endpoint)
    monkeypatch.setenv("AGENT_DEBUGGER_API_KEY", SHELL_KEY)
    assert main(["run", SCENARIO]) == 0
    assert batches
    assert {auth for _, auth, _ in batches} == {f"Bearer {SHELL_KEY}"}
