import json
from pathlib import Path

import pytest
from ground_truth_schema import GroundTruth, load_truth
from pydantic import ValidationError

from langgraph_workflow_agent import scenarios
from langgraph_workflow_agent.scenarios import (
    RuntimeScenario,
    build_agent,
    load_scenario,
    read_json,
)

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize(
    "change",
    [
        {"schema_version": 2},
        {"schema_version": "1"},
        {"schema_version": True},
        {"scenario_id": "../LG-01"},
        {"expected_outcome": "correct"},
        {"failure_category": "wrong_branch"},
        {"ground_truth": {}},
        {"unknown": 1},
        {
            "request": {
                "service": "unknown",
                "incident": "worker_stalled",
                "telemetry": "ready",
            }
        },
        {"request": ""},
        {"request": {"service": "beacon"}},
        {
            "route_overrides": [
                {"source": "classify", "attempt": 2, "destination": "evaluate"}
            ]
        },
        {
            "route_overrides": [
                {"source": "evaluate", "attempt": 0, "destination": "abort"}
            ]
        },
        {
            "route_overrides": [
                {"source": "evaluate", "attempt": True, "destination": "abort"}
            ]
        },
        {"route_overrides": [{"source": "gather_context", "destination": "abort"}]},
        {"route_overrides": [{"source": "evaluate", "destination": "classify"}]},
        {"route_overrides": [{"source": "classify", "destination": "execute_action"}]},
        {"route_overrides": [{"source": "evaluate", "destination": "validate"}]},
        {
            "route_overrides": [
                {"source": "evaluate", "destination": "abort", "extra": 1}
            ]
        },
        {"route_overrides": [{"source": "evaluate", "destination": "abort"}] * 2},
        {
            "route_overrides": [
                {"source": "evaluate", "destination": "abort"},
                {"source": "evaluate", "attempt": 1, "destination": "retry_context"},
            ]
        },
        {"node_overrides": [{"node": "unknown", "drop_update": "action_result"}]},
        {"node_overrides": [{"node": "execute_action", "drop_update": "request"}]},
        {
            "node_overrides": [
                {"node": "execute_action", "drop_update": "action_result"}
            ]
            * 2
        },
        {
            "context_overrides": [
                {
                    "attempt": 1,
                    "response": {
                        "revision": 0,
                        "availability": "ready",
                        "incident": "worker_stalled",
                    },
                }
            ]
        },
        {
            "context_overrides": [
                {
                    "attempt": 1,
                    "response": {
                        "revision": True,
                        "availability": "ready",
                        "incident": "worker_stalled",
                    },
                }
            ]
        },
        {
            "context_overrides": [
                {
                    "attempt": 1,
                    "response": {
                        "revision": 1,
                        "availability": "invented",
                        "incident": "worker_stalled",
                    },
                }
            ]
        },
        {
            "context_overrides": [
                {
                    "attempt": 1,
                    "response": {
                        "revision": 1,
                        "availability": "ready",
                        "incident": "worker_stalled",
                    },
                }
            ]
            * 2
        },
        {"response_override": {"status": "running", "message": "invalid"}},
        {"response_override": {"status": "resolved", "message": " "}},
    ],
)
def test_strict_runtime_schema(change):
    raw = load_scenario("LG-01").model_dump()
    with pytest.raises(ValidationError):
        RuntimeScenario.model_validate({**raw, **change})


@pytest.mark.parametrize(
    "content",
    [
        '{"a": 1, "a": 2}',
        '{"nested": {"x": 1, "x": 2}}',
        '{"a": NaN}',
        '{"a": Infinity}',
        '{"a": -Infinity}',
        "{broken",
    ],
)
def test_malformed_json(tmp_path, content):
    path = tmp_path / "bad.json"
    path.write_text(content, encoding="utf-8")
    with pytest.raises(ValueError):
        read_json(path)


@pytest.mark.parametrize("content", ["null", "[]", '"text"', "42"])
def test_nonobject_configuration(tmp_path, monkeypatch, content):
    monkeypatch.setattr(scenarios, "DATA_DIR", tmp_path)
    (tmp_path / "LG-01.json").write_text(content, encoding="utf-8")
    with pytest.raises(ValidationError):
        load_scenario("LG-01")


def test_filename_and_missing_scenario_errors(tmp_path, monkeypatch):
    raw = load_scenario("LG-01").model_dump()
    monkeypatch.setattr(scenarios, "DATA_DIR", tmp_path)
    (tmp_path / "LG-02.json").write_text(json.dumps(raw), encoding="utf-8")
    with pytest.raises(ValueError, match="filename"):
        load_scenario("LG-02")
    with pytest.raises(FileNotFoundError):
        load_scenario("LG-99")
    for name in ("../LG-01", "LG-01.json", "lg-01", "LG-1"):
        with pytest.raises(ValueError, match="Expected scenario"):
            load_scenario(name)


def test_builder_revalidates_mutated_config():
    config = load_scenario("LG-01")
    config.request.telemetry = "nonsense"
    with pytest.raises(ValidationError):
        build_agent(config)


def test_complete_separate_manifest_inventory():
    runtime_ids = {path.stem for path in scenarios.DATA_DIR.glob("*.json")}
    truth_paths = sorted((ROOT / "ground_truth").glob("*.json"))
    assert runtime_ids == {f"LG-{n:02}" for n in range(1, 11)}
    assert {path.stem for path in truth_paths} == runtime_ids
    truths = [load_truth(path) for path in truth_paths]
    assert sum(t.expected_outcome == "correct" for t in truths) == 2
    assert len({t.failure_category for t in truths if t.failure_category}) == 8
    for truth in truths:
        with pytest.raises(ValidationError):
            RuntimeScenario.model_validate(truth.model_dump())
        with pytest.raises(ValidationError):
            GroundTruth.model_validate(load_scenario(truth.scenario_id).model_dump())


@pytest.mark.parametrize(
    "change",
    [
        {"unexpected": True},
        {"schema_version": True},
        {"failure_category": "invented"},
        {"expected_outcome": "correct"},
        {"expected_suspicious_operations": []},
        {"expected_suspicious_operations": ["classify", "classify"]},
        {"expected_suspicious_operations": ["execute_action"]},
        {"detection_operation": "gather_context"},
        {"expected_path": []},
        {"expected_termination": "recursion_limit"},
        {"expected_validation": None},
        {"expected_response_status": None},
        {"expected_retries": -1},
        {"expected_retries": 5},
    ],
)
def test_strict_ground_truth_schema(change):
    raw = load_truth(ROOT / "ground_truth" / "LG-04.json").model_dump()
    with pytest.raises(ValidationError):
        GroundTruth.model_validate({**raw, **change})


def test_truth_filename_mismatch(tmp_path):
    content = (ROOT / "ground_truth" / "LG-01.json").read_text(encoding="utf-8")
    path = tmp_path / "LG-99.json"
    path.write_text(content, encoding="utf-8")
    with pytest.raises(ValueError, match="filename"):
        load_truth(path)
