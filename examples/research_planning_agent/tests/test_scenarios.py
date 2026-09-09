import json
from pathlib import Path

import pytest
from ground_truth_schema import GroundTruth, load_truth
from pydantic import ValidationError

from research_planning_agent.evidence import DATA_DIR, load_evidence, read_json
from research_planning_agent.models import EvidenceItem
from research_planning_agent.scenarios import (
    RuntimeScenario,
    build_agent,
    load_scenario,
)

ROOT = Path(__file__).resolve().parents[1]
IDS = [f"RP-{number:02}" for number in range(1, 11)]


@pytest.mark.parametrize("scenario_id", IDS)
def test_scenarios_match_strict_evaluation_manifests(scenario_id):
    truth = load_truth(ROOT / "ground_truth" / f"{scenario_id}.json")
    config = load_scenario(scenario_id)
    result = build_agent(config).run(config.request)
    assert truth.request == config.request == result.task.request
    assert result.status == truth.expected_status
    assert result.issues == truth.expected_issues
    assert (
        result.draft.recommendation if result.draft else None
    ) == truth.expected_draft_recommendation
    assert [
        f"{c.step.fact}:{c.step.query}" for c in result.collections
    ] == truth.expected_collections
    assert len(result.assessments) == truth.expected_assessment_count
    assert (
        result.draft.unresolved if result.draft else []
    ) == truth.expected_unresolved
    revision = (
        "absent"
        if result.revision is None
        else "accepted"
        if len(result.assessments) == 2
        else "rejected"
    )
    assert revision == truth.expected_revision
    operations = {op.split(":")[0] for op in result.operations}
    assert set(truth.expected_suspicious_operations) <= operations
    for override in config.assessment_overrides:
        assert result.assessments[override.invocation - 1] == override.response
    if config.plan_override is not None:
        assert result.plan == config.plan_override
    if config.revision_override is not None:
        assert result.revision == config.revision_override
    if config.synthesis_override is not None:
        assert result.draft == config.synthesis_override
    if config.validation_override is not None:
        assert result.issues == config.validation_override
    assert not set(config.excluded_evidence) & {e.evidence_id for e in result.evidence}


def test_complete_catalogue_and_reference_count():
    assert sorted(p.stem for p in (DATA_DIR / "scenarios").glob("*.json")) == IDS
    assert sorted(p.stem for p in (ROOT / "ground_truth").glob("*.json")) == IDS
    truths = [load_truth(ROOT / "ground_truth" / f"{sid}.json") for sid in IDS]
    assert sum(t.expected_outcome == "correct" for t in truths) == 2
    assert (
        sum(
            t.expected_outcome == "failure" and t.expected_status == "completed"
            for t in truths
        )
        == 4
    )
    assert sum(t.expected_status == "blocked" for t in truths) == 4
    assert len({t.failure_category for t in truths if t.failure_category}) == 8


@pytest.mark.parametrize(
    "text", ['{"x":1,"x":2}', '{"x":{"y":1,"y":2}}', '{"x":NaN}', '{"x":Infinity}', "{"]
)
def test_invalid_json_rejected(tmp_path, text):
    path = tmp_path / "bad.json"
    path.write_text(text, encoding="utf-8")
    with pytest.raises(ValueError):
        read_json(path)


@pytest.mark.parametrize(
    "change",
    [
        {"expected_outcome": "correct"},
        {"schema_version": 2},
        {"excluded_evidence": ["A", "A"]},
        {"validation_override": [""]},
        {"request": ""},
        {"request": "research anything"},
    ],
)
def test_invalid_runtime_schema_rejected(change):
    raw = load_scenario("RP-01").model_dump()
    raw.update(change)
    with pytest.raises(ValueError):
        RuntimeScenario.model_validate(raw)


def test_duplicate_overrides_steps_and_bad_invocations_rejected():
    raw = load_scenario("RP-03").model_dump()
    raw["assessment_overrides"].append(raw["assessment_overrides"][0])
    with pytest.raises(ValidationError, match="Duplicate"):
        RuntimeScenario.model_validate(raw)
    raw = load_scenario("RP-03").model_dump()
    raw["assessment_overrides"][0]["invocation"] = 3
    with pytest.raises(ValidationError):
        RuntimeScenario.model_validate(raw)
    raw = load_scenario("RP-05").model_dump()
    raw["plan_override"]["steps"].append(raw["plan_override"]["steps"][0])
    with pytest.raises(ValidationError, match="Duplicate"):
        RuntimeScenario.model_validate(raw)


def test_assessment_partition_and_references_rejected():
    raw = load_scenario("RP-03").model_dump()
    raw["assessment_overrides"][0]["response"]["missing"] = ["ridge.capacity"]
    with pytest.raises(ValueError, match="partition"):
        RuntimeScenario.model_validate(raw)
    for eid in ("UNKNOWN", "VALE-POWER-1"):
        raw = load_scenario("RP-03").model_dump()
        raw["assessment_overrides"][0]["response"]["selected"]["ridge.capacity"] = [eid]
        with pytest.raises(ValueError, match="references"):
            build_agent(RuntimeScenario.model_validate(raw))
    raw = load_scenario("RP-01").model_dump()
    raw["excluded_evidence"] = ["UNKNOWN"]
    with pytest.raises(ValueError, match="Unknown"):
        build_agent(RuntimeScenario.model_validate(raw))


@pytest.mark.parametrize(
    "scenario_id", ["../RP-01", "RP-1", "RP-01.json", "rp-01", "RP-99"]
)
def test_invalid_or_unknown_id(scenario_id):
    with pytest.raises((ValueError, FileNotFoundError)):
        load_scenario(scenario_id)


@pytest.mark.parametrize(
    "mutation",
    [
        "duplicate",
        "unknown_parent",
        "self_parent",
        "wrong_topic",
        "bad_value",
        "bad_date",
        "extra",
        "empty",
    ],
)
def test_malformed_evidence_rejected(tmp_path, mutation):
    raw = [item.model_dump() for item in load_evidence()]
    item = next(item for item in raw if item["evidence_id"] == "RIDGE-CAPACITY-2")
    if mutation == "duplicate":
        raw.append(raw[0])
    elif mutation == "unknown_parent":
        item["supersedes"] = ["UNKNOWN"]
    elif mutation == "self_parent":
        item["supersedes"] = [item["evidence_id"]]
    elif mutation == "wrong_topic":
        item["supersedes"] = ["RIDGE-POWER-1"]
    elif mutation == "bad_value":
        item["value"] = "many"
    elif mutation == "bad_date":
        item["published_on"] = "2026-02-30"
    elif mutation == "extra":
        item["expected_failure"] = True
    else:
        raw = []
    path = tmp_path / "corpus.json"
    path.write_text(json.dumps(raw), encoding="utf-8")
    with pytest.raises(ValueError):
        load_evidence(path)


def test_ground_truth_schema_rejects_extra_fields_and_inconsistent_labels():
    raw = read_json(ROOT / "ground_truth" / "RP-01.json")
    with pytest.raises(ValidationError):
        GroundTruth.model_validate({**raw, "unexpected": 1})
    with pytest.raises(ValidationError):
        GroundTruth.model_validate({**raw, "expected_outcome": "failure"})
    with pytest.raises(ValidationError):
        EvidenceItem.model_validate({"evidence_id": "only-id"})


def test_uncollected_references_and_unreachable_second_assessment_rejected():
    raw = load_scenario("RP-04").model_dump()
    raw["assessment_overrides"][0]["response"]["selected"]["vale.permit"] = [
        "VALE-PERMIT-3"
    ]
    with pytest.raises(ValueError, match="references"):
        build_agent(RuntimeScenario.model_validate(raw))
    raw = load_scenario("RP-04").model_dump()
    second = {**raw["assessment_overrides"][0], "invocation": 2}
    raw["assessment_overrides"].append(second)
    with pytest.raises(ValueError, match="require an evidence gap"):
        build_agent(RuntimeScenario.model_validate(raw))


@pytest.mark.parametrize("value", [True, "1", 1.0])
def test_schema_version_is_strict_integer(value):
    raw = load_scenario("RP-01").model_dump()
    raw["schema_version"] = value
    with pytest.raises(ValueError):
        RuntimeScenario.model_validate(raw)
