import ast
import hashlib
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
CONTROLLED_JSON_SHA256 = {
    "TOOL-01": "c445cb49cdf2973eabcda7ca1aa76f3b46223366e18067fb14a849bf938e0bb4",
    "TOOL-02": "3142c8f3295b9ac43da30ae8d90e81c43ebf7be0cff1de8a8fcbc4b4f5d26544",
    "TOOL-03": "ef407a86044569058720edd1025427072e0dd9a3c959b2adcb903f7bae884a46",
    "TOOL-04": "b1af9795b4a5e1500a658effc415f43e7f59b2ddc27b6021310ba6ec90b8cfda",
    "TOOL-05": "3fad02c4ca2b37a8d87605018ec22df0b4084680f1971fbb1ea7dcd012fcc21d",
    "TOOL-06": "f1f2deaf070e3c8eab3b4b9ae45f9ae1d843885f7946f28d53fe7335c353c8ab",
    "TOOL-07": "815c97c84202a6207ed6c55ec5655d1736f4872e8993d958e432d9f770290839",
    "TOOL-08": "8bd6d44be8a0dcb25897ea04d0f97d54d5be8c0b21317a38a4e78b9be6066392",
    "TOOL-09": "c445733647a1973242198fb952daa356a3900861cfedd9b8d20151ea50e95f77",
    "TOOL-10": "97705f96f9cf7474afb4317cee1ed4712105542d337f156322f437c5d0835c59",
    "TOOL-11": "98a0078c60883c4d99c509ec1ca3e972afce6c97df6ac1018255657c8daf1a36",
    "TOOL-12": "873b7faf72da10b6ae89db6dfed9afb0d595c606990c151c365b8708060b98be",
}


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
    assert (
        hashlib.sha256(process.stdout.encode()).hexdigest()
        == (CONTROLLED_JSON_SHA256[scenario_id])
    )
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
