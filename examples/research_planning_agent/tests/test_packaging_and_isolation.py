import ast
import json
import os
import socket
import subprocess
import sys
from pathlib import Path
from zipfile import ZipFile

import pytest

from research_planning_agent.cli import main
from research_planning_agent.scenarios import build_agent, load_scenario

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "src" / "research_planning_agent"
IDS = [f"RP-{number:02}" for number in range(1, 11)]


def test_all_scenarios_offline_without_ground_truth_reads(monkeypatch):
    def deny_network(*args, **kwargs):
        raise AssertionError("Network access forbidden")

    original = Path.read_text

    def guarded_read(path, *args, **kwargs):
        assert "ground_truth" not in str(path)
        assert "tests" not in path.parts
        return original(path, *args, **kwargs)

    monkeypatch.setattr(socket, "socket", deny_network)
    monkeypatch.setattr(socket, "create_connection", deny_network)
    monkeypatch.setattr(Path, "read_text", guarded_read)
    for scenario_id in IDS:
        config = load_scenario(scenario_id)
        result = build_agent(config).run(config.request)
        assert scenario_id not in result.model_dump_json()


def test_normal_runtime_has_no_injection_or_evaluation_dependencies():
    for name in ("agent.py", "model_client.py", "models.py", "evidence.py"):
        text = (PACKAGE / name).read_text(encoding="utf-8")
        tree = ast.parse(text)
        for node in ast.walk(tree):
            if isinstance(node, ast.Name):
                assert node.id not in {
                    "scenario_id",
                    "expected_outcome",
                    "ground_truth",
                }
            if isinstance(node, ast.ImportFrom):
                assert node.module not in {"scenarios", "ground_truth_schema"}
        assert "RP-" not in text
    for path in PACKAGE.glob("*.py"):
        assert "ground_truth" not in path.read_text(encoding="utf-8")


@pytest.mark.parametrize("scenario_id", IDS)
def test_json_cli(scenario_id, capsys):
    assert main(["run", scenario_id, "--json"]) == 0
    output = json.loads(capsys.readouterr().out)
    assert output["status"] == (
        "incomplete"
        if scenario_id == "RP-02"
        else "completed"
        if scenario_id in {"RP-01", "RP-03", "RP-04", "RP-09", "RP-10"}
        else "blocked"
    )


def test_text_cli_and_errors(capsys):
    assert main(["run", "RP-09"]) == 0
    output = capsys.readouterr().out
    assert "Recommendation: vale" in output
    assert "vale.power = 99 [VALE-POWER-1]" in output
    assert main(["run", "RP-99"]) == 1
    assert "Error:" in capsys.readouterr().err
    with pytest.raises(SystemExit) as exc:
        main([])
    assert exc.value.code == 2


def test_wheel_contents_and_all_installed_cli_scenarios(tmp_path):
    env = {**os.environ, "PIP_NO_INDEX": "1", "PIP_DISABLE_PIP_VERSION_CHECK": "1"}
    wheel_dir = tmp_path / "wheels"
    build = subprocess.run(
        [
            sys.executable,
            "-m",
            "pip",
            "wheel",
            str(ROOT),
            "--no-deps",
            "--no-build-isolation",
            "-w",
            str(wheel_dir),
        ],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        check=False,
        timeout=90,
    )
    assert build.returncode == 0, build.stdout + build.stderr
    wheels = list(wheel_dir.glob("*.whl"))
    assert len(wheels) == 1
    with ZipFile(wheels[0]) as archive:
        names = archive.namelist()
        assert not any("ground_truth" in name or "tests/" in name for name in names)
        assert "research_planning_agent/data/evidence.json" in names
        assert (
            len(json.loads(archive.read("research_planning_agent/data/evidence.json")))
            == 14
        )
        assert sorted(Path(name).stem for name in names if "/scenarios/" in name) == IDS
        assert "research_planning_agent/agent.py" in names
    target = tmp_path / "installed"
    install = subprocess.run(
        [
            sys.executable,
            "-m",
            "pip",
            "install",
            "--no-deps",
            "--target",
            str(target),
            str(wheels[0]),
        ],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        check=False,
        timeout=90,
    )
    assert install.returncode == 0, install.stdout + install.stderr
    script = """
import pathlib, runpy, socket, sys
target, source, scenario = sys.argv[1:]
sys.path = [target] + [p for p in sys.path if source.lower() not in p.lower()]
def deny_network(*args, **kwargs):
    raise AssertionError('Network is forbidden')
socket.socket = socket.create_connection = deny_network
def guard(event, args):
    if event == 'open' and isinstance(args[0], (str, bytes)):
        path = str(args[0]).lower()
        if 'ground_truth' in path or source.lower() in path:
            raise AssertionError('Source tree or evaluation read forbidden: ' + path)
sys.addaudithook(guard)
import research_planning_agent
assert pathlib.Path(research_planning_agent.__file__).is_relative_to(target)
sys.argv = ['research_planning_agent', 'run', scenario, '--json']
runpy.run_module('research_planning_agent', run_name='__main__')
"""
    for scenario_id in IDS:
        completed = subprocess.run(
            [
                sys.executable,
                "-I",
                "-c",
                script,
                str(target),
                str(ROOT / "src"),
                scenario_id,
            ],
            cwd=tmp_path,
            env=env,
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )
        assert completed.returncode == 0, completed.stdout + completed.stderr
        config = load_scenario(scenario_id)
        assert json.loads(completed.stdout) == build_agent(config).run(
            config.request
        ).model_dump(mode="json")
