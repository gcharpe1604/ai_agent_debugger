import json

import pytest
from pydantic import ValidationError

from tool_task_agent.models import State
from tool_task_agent.scenarios import (
    ScenarioConfig,
    build_agent,
    load_scenario,
    read_json,
)
from tool_task_agent.tools import LocalTools, ToolError


def invoke(tools, name, arguments):
    return tools.invoke(name, arguments, step_id="test", attempt=1)


@pytest.mark.parametrize(
    "name,args,code",
    [
        ("unknown", {}, "unknown_tool"),
        ("get_order", {}, "invalid_arguments"),
        ("get_order", {"order_id": "ORD-999"}, "order_not_found"),
        ("get_order", {"order_id": "ORD-100", "extra": 1}, "invalid_arguments"),
        ("get_stock", {"sku": "OTHER"}, "invalid_arguments"),
        (
            "reserve_inventory",
            {"order_id": "ORD-100", "sku": "OTHER", "quantity": 2},
            "order_mismatch",
        ),
        (
            "reserve_inventory",
            {"order_id": "ORD-100", "sku": "SENSOR-KIT", "quantity": 1},
            "order_mismatch",
        ),
        (
            "charge_payment",
            {"order_id": "ORD-100", "amount_cents": 5000},
            "reservation_required",
        ),
        ("create_shipment", {"order_id": "ORD-100"}, "reservation_required"),
    ],
)
def test_tool_rejections_preserve_state(name, args, code):
    tools = LocalTools()
    with pytest.raises(ToolError) as caught:
        invoke(tools, name, args)
    assert caught.value.code == code
    assert tools.state == State()


@pytest.mark.parametrize("quantity", [0, -1, True, "2", 2.0, None])
def test_strict_reservation_argument_types(quantity):
    tools = LocalTools()
    with pytest.raises(ToolError) as caught:
        invoke(
            tools,
            "reserve_inventory",
            {"order_id": "ORD-100", "sku": "SENSOR-KIT", "quantity": quantity},
        )
    assert caught.value.code == "invalid_arguments"
    assert tools.state == State()


def test_stock_and_payment_preconditions_and_idempotency():
    tools = LocalTools()
    reserve_args = {"order_id": "ORD-100", "sku": "SENSOR-KIT", "quantity": 2}
    tools.state.available_stock = 1
    with pytest.raises(ToolError) as caught:
        invoke(tools, "reserve_inventory", reserve_args)
    assert caught.value.code == "insufficient_stock"
    assert tools.state.available_stock == 1 and tools.state.reservation is None
    tools.state.available_stock = 5
    for name, args in [
        ("reserve_inventory", reserve_args),
        ("charge_payment", {"order_id": "ORD-100", "amount_cents": 5000}),
        ("create_shipment", {"order_id": "ORD-100"}),
    ]:
        first = invoke(tools, name, args)
        before = tools.state.model_copy(deep=True)
        assert invoke(tools, name, args) == first
        assert tools.state == before
    before = tools.state.model_copy(deep=True)
    with pytest.raises(ToolError) as caught:
        invoke(tools, "charge_payment", {"order_id": "ORD-100", "amount_cents": 1})
    assert caught.value.code == "amount_mismatch"
    assert tools.state == before
    assert invoke(tools, "get_stock", {"sku": "SENSOR-KIT"})["available_stock"] == 3


@pytest.mark.parametrize(
    "update",
    [
        {"schema_version": True},
        {"schema_version": "1"},
        {"schema_version": 2},
        {"scenario_id": "../TOOL-01"},
        {"request": " "},
        {"extra": 1},
        {"expected_outcome": "correct"},
        {"ground_truth": {}},
        {"plan_override": []},
        {"tool_faults": [{"step_id": "pay", "attempt": 0, "effect": "timeout"}]},
        {"tool_faults": [{"step_id": "pay", "attempt": 4, "effect": "timeout"}]},
        {"tool_faults": [{"step_id": "pay", "attempt": True, "effect": "timeout"}]},
        {"tool_faults": [{"step_id": "pay", "attempt": 2, "effect": "timeout"}]},
        {"tool_faults": [{"step_id": "pay", "attempt": 1, "effect": "random"}]},
        {
            "tool_faults": [
                {"step_id": "pay", "attempt": 1, "effect": "timeout", "response": {}}
            ]
        },
        {
            "tool_faults": [
                {"step_id": "pay", "attempt": 1, "effect": "replace_response"}
            ]
        },
        {
            "tool_faults": [
                {
                    "step_id": "pay",
                    "attempt": 1,
                    "effect": "corrupt_shipment",
                    "shipment_quantity": 1,
                }
            ]
        },
        {"response_override": {"status": "completed", "message": " ", "quantity": 1}},
    ],
)
def test_invalid_configuration_rejected(update):
    payload = load_scenario("TOOL-01").model_dump()
    with pytest.raises(ValidationError):
        ScenarioConfig.model_validate({**payload, **update})


def test_duplicate_steps_faults_and_absent_targets_rejected():
    payload = load_scenario("TOOL-07").model_dump()
    plan = build_agent(load_scenario("TOOL-01")).model.plan(payload["request"])
    with pytest.raises(ValidationError, match="Duplicate"):
        ScenarioConfig.model_validate(
            {**payload, "tool_faults": payload["tool_faults"] * 2}
        )
    with pytest.raises(ValidationError, match="unique"):
        ScenarioConfig.model_validate({**payload, "plan_override": [plan[0], plan[0]]})
    with pytest.raises(ValidationError, match="absent"):
        ScenarioConfig.model_validate({**payload, "plan_override": [plan[0]]})


@pytest.mark.parametrize(
    "text",
    [
        '{"schema_version":1,"schema_version":1}',
        '{"nested":{"attempt":1,"attempt":2}}',
        '{"quantity":NaN}',
        '{"quantity":Infinity}',
        "{broken",
    ],
)
def test_strict_json_reader(tmp_path, text):
    path = tmp_path / "invalid.json"
    path.write_text(text, encoding="utf-8")
    with pytest.raises(ValueError):
        read_json(path)


@pytest.mark.parametrize("scenario_id", ["../TOOL-01", "TOOL-01.json", "", "TOOL-99"])
def test_invalid_or_missing_id(scenario_id):
    with pytest.raises((ValueError, FileNotFoundError)):
        load_scenario(scenario_id)


def test_filename_id_mismatch(tmp_path, monkeypatch):
    payload = load_scenario("TOOL-01").model_dump()
    (tmp_path / "TOOL-02.json").write_text(json.dumps(payload), encoding="utf-8")
    monkeypatch.setattr("tool_task_agent.scenarios.DATA_DIR", tmp_path)
    with pytest.raises(ValueError, match="disagree"):
        load_scenario("TOOL-02")


def test_configuration_is_copied_at_construction():
    config = load_scenario("TOOL-07")
    agent = build_agent(config)
    config.tool_faults[0].effect = "permanent_error"
    assert agent.run(config.request).status == "completed"
    assert build_agent(config).run(config.request).status == "failed"
