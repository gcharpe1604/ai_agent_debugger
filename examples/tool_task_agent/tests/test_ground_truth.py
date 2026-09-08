from pathlib import Path

import pytest
from ground_truth_schema import GroundTruth, load_ground_truth
from pydantic import ValidationError

from tool_task_agent.scenarios import DATA_DIR, build_agent, load_scenario

DIRECTORY = Path(__file__).resolve().parents[1] / "ground_truth"
IDS = [f"TOOL-{i:02}" for i in range(1, 13)]
CATEGORIES = [
    None,
    "wrong_tool_selection",
    "incorrect_tool_arguments",
    "tool_failure",
    "tool_timeout",
    "malformed_tool_response",
    "retry_then_success",
    "retry_exhaustion",
    "required_step_skipped",
    "invalid_step_order",
    "inconsistent_intermediate_state",
    "final_output_inconsistent",
]


def test_catalogue_has_exactly_one_runtime_and_truth_file_per_scenario():
    assert sorted(p.stem for p in DIRECTORY.glob("*.json")) == IDS
    assert sorted(p.stem for p in DATA_DIR.glob("*.json")) == IDS


@pytest.mark.parametrize("scenario_id,category", list(zip(IDS, CATEGORIES)))
def test_ground_truth_against_actual_execution_and_injection(scenario_id, category):
    truth = load_ground_truth(DIRECTORY / f"{scenario_id}.json")
    config = load_scenario(scenario_id)
    result = build_agent(config).run(config.request)
    assert truth.expected_status == result.status
    assert truth.expected_error_code == result.error_code
    assert (
        truth.expected_failure.category if truth.expected_failure else None
    ) == category
    calls = [event for event in result.events if event.attempt]
    assert truth.expected_tool_calls == [event.operation for event in calls]
    state = result.state
    assert truth.expected_facts.model_dump() == {
        "available_stock": state.available_stock,
        "reserved_quantity": state.reservation.quantity if state.reservation else None,
        "payment_amount_cents": state.payment.amount_cents if state.payment else None,
        "shipment_quantity": state.shipment.quantity if state.shipment else None,
        "final_quantity": result.final_response.quantity,
    }
    runtime_fault = config.model_dump(exclude_unset=True)
    for key in ["schema_version", "scenario_id", "request"]:
        del runtime_fault[key]
    assert truth.injected_fault == runtime_fault
    for fault in config.tool_faults:
        assert any(
            e.step_id == fault.step_id and e.attempt == fault.attempt for e in calls
        )
    retry = truth.expected_retry_behaviour
    if retry.step_id:
        attempts = [event for event in calls if event.step_id == retry.step_id]
        assert len(attempts) == retry.attempts
        assert [e.status for e in attempts] == ["error"] * retry.retries + [
            "ok" if retry.recovered else "error"
        ]
    else:
        assert all(event.attempt == 1 for event in calls)
    failure = truth.expected_failure
    if failure:
        assert any(
            e.operation == failure.operation and e.step_id == failure.step_id
            for e in result.events
        )
        if failure.detection_step:
            assert any(
                e.operation == failure.detection_operation
                and e.step_id == failure.detection_step
                and e.status == "error"
                for e in result.events
            )
    # Independent task-success criterion, separate from operational status.
    task_correct = (
        result.status == "completed"
        and state.shipment is not None
        and state.shipment.quantity == state.order.quantity
        and result.final_response.quantity == state.shipment.quantity
        and result.final_response.shipment_id == state.shipment.shipment_id
    )
    assert (truth.expected_outcome == "correct") == task_correct


@pytest.mark.parametrize(
    "update",
    [
        {"schema_version": True},
        {"schema_version": 2},
        {"scenario_id": "TOOL-99"},
        {"expected_outcome": "unknown"},
        {"expected_status": "failed"},
        {"expected_failure": None},
        {"injected_fault": {}},
        {"expected_suspicious_steps": []},
        {"expected_suspicious_steps": ["pay", "pay"]},
        {"important_operations": ["unknown"]},
        {"expected_tool_calls": ["unknown"]},
        {"expected_facts": {}},
        {"expected_causal_explanation": " "},
        {"extra": True},
        {
            "expected_retry_behaviour": {
                "max_attempts": 3,
                "step_id": "pay",
                "attempts": 2,
                "retries": 0,
                "recovered": True,
            }
        },
    ],
)
def test_malformed_ground_truth_rejected(update):
    payload = load_ground_truth(DIRECTORY / "TOOL-07.json").model_dump()
    with pytest.raises(ValidationError):
        GroundTruth.model_validate({**payload, **update})


@pytest.mark.parametrize("field", list(GroundTruth.model_fields))
def test_missing_truth_fields_rejected(field):
    payload = load_ground_truth(DIRECTORY / "TOOL-01.json").model_dump()
    del payload[field]
    with pytest.raises(ValidationError):
        GroundTruth.model_validate(payload)


def test_ground_truth_filename_must_match(tmp_path):
    path = tmp_path / "TOOL-02.json"
    path.write_text(
        (DIRECTORY / "TOOL-01.json").read_text(encoding="utf-8"), encoding="utf-8"
    )
    with pytest.raises(ValueError, match="disagree"):
        load_ground_truth(path)
