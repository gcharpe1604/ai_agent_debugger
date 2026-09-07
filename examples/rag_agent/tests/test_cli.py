import json
import subprocess
import sys

import pytest

from rag_agent.cli import main


@pytest.mark.parametrize("scenario_id", [f"RAG-{i:02}" for i in range(1, 8)])
def test_cli_standalone_from_another_directory(tmp_path, results, scenario_id):
    completed = subprocess.run(
        [sys.executable, "-m", "rag_agent", "run", scenario_id, "--json"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=True,
    )
    assert json.loads(completed.stdout) == results[scenario_id].model_dump()
    assert completed.stderr == ""


def test_readable_cli(capsys):
    assert main(["run", "RAG-07"]) == 0
    output = capsys.readouterr().out
    for text in [
        "Scenario: RAG-07",
        "Mode: controlled",
        "Retrieval attempts: 2",
        "KB-05",
        "KB-04",
        "48 hours",
    ]:
        assert text in output
    assert "expected_outcome" not in output


@pytest.mark.parametrize("scenario_id", ["RAG-99", "../RAG-01"])
def test_cli_errors_are_nonzero(scenario_id, capsys):
    assert main(["run", scenario_id]) == 1
    assert "Error:" in capsys.readouterr().err
