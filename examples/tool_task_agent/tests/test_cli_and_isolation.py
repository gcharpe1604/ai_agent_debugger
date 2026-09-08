import ast
import json
import os
import socket
import subprocess
import sys
from pathlib import Path

import pytest

from tool_task_agent import agent, controlled_model, tools
from tool_task_agent.scenarios import build_agent, load_scenario

IDS = [f"TOOL-{i:02}" for i in range(1, 13)]


def cli(tmp_path, *args):
    return subprocess.run(
        [sys.executable, "-m", "tool_task_agent", *args],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )


@pytest.mark.parametrize("scenario_id", IDS)
def test_json_cli_from_another_directory(tmp_path, scenario_id):
    process = cli(tmp_path, "run", scenario_id, "--json")
    assert process.returncode == 0, process.stderr
    assert not process.stderr
    config = load_scenario(scenario_id)
    assert json.loads(process.stdout) == {
        "scenario_id": scenario_id,
        **build_agent(config).run(config.request).model_dump(),
    }


def test_text_cli_and_scenario_listing(tmp_path):
    process = cli(tmp_path, "list")
    assert process.returncode == 0 and process.stdout.splitlines() == IDS
    process = cli(tmp_path, "run", "TOOL-07")
    assert process.returncode == 0
    assert "pay/charge_payment attempt=1: error" in process.stdout
    assert "pay/charge_payment attempt=2: ok" in process.stdout
    assert "Order ORD-100 shipped as SHIP-100 with 2 units." in process.stdout


@pytest.mark.parametrize(
    "args,code",
    [
        (["run", "TOOL-99"], 1),
        (["run", "../TOOL-01"], 1),
        ([], 2),
        (["run"], 2),
    ],
)
def test_cli_input_errors(tmp_path, args, code):
    process = cli(tmp_path, *args)
    assert process.returncode == code
    assert process.stderr
    assert "Traceback" not in process.stderr


def test_all_scenarios_are_offline_and_do_not_read_ground_truth(monkeypatch):
    original = Path.read_text

    def no_labels(path, *args, **kwargs):
        assert "ground_truth" not in path.parts, "Runtime read evaluation labels"
        return original(path, *args, **kwargs)

    def deny(*args, **kwargs):
        raise AssertionError("Network is forbidden")

    monkeypatch.setattr(Path, "read_text", no_labels)
    monkeypatch.setattr(socket, "getaddrinfo", deny)
    monkeypatch.setattr(socket, "create_connection", deny)
    for name in ["connect", "connect_ex", "sendto", "send", "sendall"]:
        monkeypatch.setattr(socket.socket, name, deny)
    for key in list(os.environ):
        if "API_KEY" in key or key.endswith("_TOKEN") or key == "DATABASE_URL":
            monkeypatch.delenv(key)
    with pytest.raises(AssertionError, match="Network"):
        socket.create_connection(("example.invalid", 443))
    for scenario_id in IDS:
        config = load_scenario(scenario_id)
        assert build_agent(config).run(config.request).events


def test_agent_and_tools_do_not_import_scenarios_or_evaluation_labels():
    for module in [agent, controlled_model, tools]:
        source = Path(module.__file__).read_text(encoding="utf-8")
        assert "scenario_id" not in source
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                names = [node.module or ""]
            elif isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            else:
                continue
            assert all(
                name.split(".")[0]
                not in {
                    "scenarios",
                    "ground_truth",
                    "backend",
                    "sdk",
                    "rag_agent",
                    "refund_agent",
                }
                for name in names
            )
