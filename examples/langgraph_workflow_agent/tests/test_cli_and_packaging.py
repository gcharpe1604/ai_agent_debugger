import ast
import json
import os
import subprocess
import sys
from email import message_from_bytes
from pathlib import Path
from zipfile import ZipFile

import pytest

from langgraph_workflow_agent.cli import main
from langgraph_workflow_agent.scenarios import build_agent, load_scenario

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "src" / "langgraph_workflow_agent"
IDS = [f"LG-{number:02}" for number in range(1, 11)]


@pytest.mark.parametrize("scenario_id", IDS)
def test_cli_json_and_text(scenario_id, capsys):
    config = load_scenario(scenario_id)
    expected = build_agent(config).run(config.request)
    assert main(["run", scenario_id, "--json"]) == 0
    assert json.loads(capsys.readouterr().out) == expected.model_dump(mode="json")
    assert main(["run", scenario_id]) == 0
    output = capsys.readouterr().out
    assert f"State status: {expected.state['final_status']}" in output
    assert " -> ".join(expected.path) in output


def test_cli_errors(capsys):
    assert main(["run", "LG-99"]) == 1
    assert "Error:" in capsys.readouterr().err
    assert main(["run", "../LG-01"]) == 1
    assert "Expected scenario ID" in capsys.readouterr().err
    with pytest.raises(SystemExit) as error:
        main([])
    assert error.value.code == 2


def test_no_runtime_evaluation_imports_or_scenario_branches():
    forbidden = {"scenario_id", "expected_outcome", "failure_category", "ground_truth"}
    for path in PACKAGE.glob("*.py"):
        source = path.read_text(encoding="utf-8")
        assert "ground_truth" not in source
        if path.name in {"agent.py", "dependencies.py", "models.py"}:
            assert "LG-" not in source
            for node in ast.walk(ast.parse(source)):
                if isinstance(node, ast.Name):
                    assert node.id not in forbidden
                if isinstance(node, ast.Constant) and isinstance(node.value, str):
                    assert node.value not in forbidden
                if isinstance(node, ast.ImportFrom):
                    assert node.module not in {"scenarios", "ground_truth_schema"}


def test_no_evaluation_file_reads(monkeypatch):
    original = Path.read_text

    def read(path, *args, **kwargs):
        assert "ground_truth" not in path.parts and "tests" not in path.parts
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", read)
    for scenario_id in IDS:
        config = load_scenario(scenario_id)
        build_agent(config).run(config.request)


def test_ambient_tracing_is_disabled_without_environment_mutation(monkeypatch):
    import langsmith
    from langsmith import utils

    monkeypatch.setenv("LANGSMITH_TRACING", "true")
    monkeypatch.setenv("LANGCHAIN_TRACING_V2", "true")

    def deny_client(*args, **kwargs):
        raise AssertionError("Remote tracing client must not be constructed")

    monkeypatch.setattr(langsmith.Client, "__init__", deny_client)
    utils.get_env_var.cache_clear()
    try:
        for scenario_id in IDS:
            config = load_scenario(scenario_id)
            build_agent(config).run(config.request)
        assert os.environ["LANGSMITH_TRACING"] == "true"
        assert os.environ["LANGCHAIN_TRACING_V2"] == "true"
    finally:
        utils.get_env_var.cache_clear()


def test_wheel_contents_and_all_isolated_cli_results(tmp_path):
    env = {**os.environ, "PIP_NO_INDEX": "1", "PIP_DISABLE_PIP_VERSION_CHECK": "1"}
    wheel_dir = tmp_path / "wheels"
    built = subprocess.run(
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
    assert built.returncode == 0, built.stdout + built.stderr
    wheels = list(wheel_dir.glob("*.whl"))
    assert len(wheels) == 1
    with ZipFile(wheels[0]) as archive:
        names = archive.namelist()
        assert not any("ground_truth" in name or "tests/" in name for name in names)
        expected_sources = {
            f"langgraph_workflow_agent/{path.name}" for path in PACKAGE.glob("*.py")
        }
        assert expected_sources <= set(names)
        assert sorted(Path(name).stem for name in names if "/scenarios/" in name) == IDS
        for scenario_id in IDS:
            name = f"langgraph_workflow_agent/data/scenarios/{scenario_id}.json"
            assert (
                archive.read(name)
                == (PACKAGE / "data/scenarios" / f"{scenario_id}.json").read_bytes()
            )
        metadata = message_from_bytes(
            archive.read(next(n for n in names if n.endswith("/METADATA")))
        )
        assert any(
            dep.startswith("langgraph<1.1,>=1.0")
            for dep in metadata.get_all("Requires-Dist")
        )
        assert not any(
            dep.startswith("langchain") for dep in metadata.get_all("Requires-Dist")
        )
    target = tmp_path / "installed"
    installed = subprocess.run(
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
    assert installed.returncode == 0, installed.stdout + installed.stderr
    script = """
import pathlib, runpy, sys
target, root, scenario = sys.argv[1:]
sys.path = [target] + [p for p in sys.path if not p.lower().startswith(root.lower())]
# Dependencies belong to the test venv inside root; restore only site-packages.
sys.path.append(str(pathlib.Path(sys.executable).parents[1] / 'Lib' / 'site-packages')
    if sys.platform == 'win32' else str(pathlib.Path(sys.prefix) / 'lib' / ('python%d.%d' % sys.version_info[:2]) / 'site-packages'))
def guard(event, args):
    if event in {'socket.connect', 'socket.getaddrinfo', 'socket.sendto'}:
        raise AssertionError('Network forbidden')
    if event == 'open' and isinstance(args[0], (str, bytes)):
        value = str(args[0]).lower().replace('\\\\', '/')
        if '/ground_truth/' in value or '/tests/' in value or '/src/langgraph_workflow_agent/' in value:
            raise AssertionError('Source/evaluation access forbidden: ' + value)
sys.addaudithook(guard)
import langgraph_workflow_agent
assert pathlib.Path(langgraph_workflow_agent.__file__).is_relative_to(target)
sys.argv = ['langgraph_workflow_agent', 'run', scenario, '--json']
runpy.run_module('langgraph_workflow_agent', run_name='__main__')
"""
    for scenario_id in IDS:
        completed = subprocess.run(
            [sys.executable, "-I", "-c", script, str(target), str(ROOT), scenario_id],
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
