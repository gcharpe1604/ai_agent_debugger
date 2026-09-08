from concurrent.futures import ThreadPoolExecutor

import pytest

from tool_task_agent.agent import validate_state
from tool_task_agent.models import State
from tool_task_agent.scenarios import ScenarioConfig, build_agent, load_scenario
from tool_task_agent.tools import ToolError

IDS = [f"TOOL-{i:02}" for i in range(1, 13)]
HEALTHY_CALLS = [
    "get_order",
    "reserve_inventory",
    "charge_payment",
    "create_shipment",
    "inspect_fulfillment",
]


def run(scenario_id):
    scenario = load_scenario(scenario_id)
    return build_agent(scenario).run(scenario.request)


def invocations(result):
    return [event for event in result.events if event.attempt]


@pytest.mark.parametrize(
    "scenario_id,error,stock,reserved,paid,shipped,calls",
    [
        ("TOOL-01", None, 3, True, True, True, HEALTHY_CALLS),
        (
            "TOOL-02",
            "malformed_response",
            5,
            False,
            False,
            False,
            ["get_order", "get_stock"],
        ),
        ("TOOL-03", "invalid_arguments", 5, False, False, False, HEALTHY_CALLS[:2]),
        ("TOOL-04", "tool_failure", 3, True, False, False, HEALTHY_CALLS[:3]),
        (
            "TOOL-05",
            "tool_timeout",
            3,
            True,
            False,
            False,
            HEALTHY_CALLS[:2] + ["charge_payment"] * 3,
        ),
        ("TOOL-06", "malformed_response", 3, True, False, False, HEALTHY_CALLS[:2]),
        ("TOOL-07", None, 3, True, True, True, HEALTHY_CALLS[:3] + HEALTHY_CALLS[2:]),
        (
            "TOOL-08",
            "temporarily_unavailable",
            3,
            True,
            False,
            False,
            HEALTHY_CALLS[:2] + ["charge_payment"] * 3,
        ),
        (
            "TOOL-09",
            "reservation_required",
            5,
            False,
            False,
            False,
            ["get_order", "charge_payment"],
        ),
        (
            "TOOL-10",
            "payment_required",
            3,
            True,
            False,
            False,
            ["get_order", "reserve_inventory", "create_shipment"],
        ),
        ("TOOL-11", "inconsistent_state", 3, True, True, True, HEALTHY_CALLS),
        ("TOOL-12", None, 3, True, True, True, HEALTHY_CALLS),
    ],
)
def test_scenario_contract(scenario_id, error, stock, reserved, paid, shipped, calls):
    result = run(scenario_id)
    assert result.status == ("failed" if error else "completed")
    assert result.error_code == error
    assert [event.operation for event in invocations(result)] == calls
    assert result.state.available_stock == stock
    assert (result.state.reservation is not None) == reserved
    assert (result.state.payment is not None) == paid
    assert (result.state.shipment is not None) == shipped
    assert result.events[0].state == State()
    assert [event.sequence for event in result.events] == list(
        range(1, len(result.events) + 1)
    )
    assert result.events[-1].operation == "generate_response"
    if error:
        assert result.final_response.status == "failed"
        assert result.final_response.quantity is None
        assert error in result.final_response.message


def test_healthy_workflow_and_dependent_arguments():
    result = run("TOOL-01")
    assert [event.operation for event in result.events] == [
        "interpret_plan",
        *[op for tool in HEALTHY_CALLS for op in (tool, "validate_result")],
        "validate_state",
        "generate_response",
    ]
    order, reserve, pay, ship, inspect = invocations(result)
    assert reserve.inputs == {
        "order_id": order.output["order_id"],
        "sku": order.output["sku"],
        "quantity": order.output["quantity"],
    }
    assert pay.inputs["amount_cents"] == order.output["total_cents"]
    assert order.state.reservation is None
    assert reserve.state.reservation.quantity == 2
    assert reserve.state.available_stock == 3 and reserve.state.payment is None
    assert pay.state.payment.amount_cents == 5000 and pay.state.shipment is None
    assert ship.state.shipment.reservation_id == reserve.output["reservation_id"]
    assert ship.state.shipment.payment_id == pay.output["payment_id"]
    assert inspect.output == result.state.model_dump()
    assert result.final_response.quantity == 2
    assert result.final_response.shipment_id == "SHIP-100"
    assert (
        result.final_response.message
        == "Order ORD-100 shipped as SHIP-100 with 2 units."
    )
    # Earlier snapshots and raw results cannot change with the returned state.
    result.state.reservation.quantity = 1
    assert reserve.state.reservation.quantity == 2
    assert reserve.output["quantity"] == 2


@pytest.mark.parametrize(
    "scenario_id,attempts,recovered",
    [
        ("TOOL-04", 1, False),
        ("TOOL-05", 3, False),
        ("TOOL-07", 2, True),
        ("TOOL-08", 3, False),
    ],
)
def test_payment_retry_budget_and_precommit_errors(scenario_id, attempts, recovered):
    calls = invocations(run(scenario_id))
    payments = [event for event in calls if event.step_id == "pay"]
    assert [event.attempt for event in payments] == list(range(1, attempts + 1))
    assert all(event.inputs == payments[0].inputs for event in payments)
    assert sum(event.status == "ok" for event in payments) == int(recovered)
    for event in payments:
        assert event.state.available_stock == 3
        if event.status == "error":
            assert event.state.payment is None
            assert event.state.shipment is None
    assert sum(event.step_id == "ship" for event in calls) == int(recovered)


def test_skipped_and_reordered_plans_have_distinct_evidence():
    skipped, reordered = run("TOOL-09"), run("TOOL-10")
    assert [call["step_id"] for call in skipped.events[0].output] == [
        "order",
        "pay",
        "ship",
        "inspect",
    ]
    assert [call["step_id"] for call in reordered.events[0].output] == [
        "order",
        "reserve",
        "ship",
        "pay",
        "inspect",
    ]
    assert skipped.state.reservation is None
    assert reordered.state.reservation is not None


def test_postcommit_malformed_response_and_state_corruption_are_distinct():
    malformed = run("TOOL-06")
    reserve = invocations(malformed)[1]
    assert reserve.output == {"accepted": True}
    assert reserve.state.reservation.reservation_id == "RES-100"
    assert malformed.events[-2].operation == "validate_result"
    corrupt = run("TOOL-11")
    ship = next(event for event in invocations(corrupt) if event.step_id == "ship")
    assert ship.output["quantity"] == 2
    assert ship.state.shipment.quantity == 1
    assert corrupt.events[-2].operation == "validate_state"
    assert corrupt.events[-2].error_code == "inconsistent_state"


def test_final_output_fault_changes_only_generation():
    healthy, faulty = run("TOOL-01"), run("TOOL-12")
    assert faulty.state == healthy.state
    assert faulty.events[:-1] == healthy.events[:-1]
    assert faulty.state.shipment.quantity == 2
    assert faulty.final_response.quantity == 1
    assert faulty.status == "completed"


@pytest.mark.parametrize("scenario_id", IDS)
def test_deterministic_fresh_repeated_and_concurrent_runs(scenario_id):
    config = load_scenario(scenario_id)
    agent = build_agent(config)
    expected = agent.run(config.request).model_dump_json()
    for _ in range(3):
        assert agent.run(config.request).model_dump_json() == expected
        assert build_agent(config).run(config.request).model_dump_json() == expected
    with ThreadPoolExecutor(max_workers=3) as pool:
        results = list(pool.map(agent.run, [config.request] * 6))
    assert all(result.model_dump_json() == expected for result in results)


@pytest.mark.parametrize("scenario_id", IDS[1:])
def test_removing_injection_restores_healthy_execution(scenario_id):
    payload = load_scenario(scenario_id).model_dump()
    payload.update(plan_override=None, tool_faults=[], response_override=None)
    clean = ScenarioConfig.model_validate(payload)
    assert build_agent(clean).run(clean.request) == run("TOOL-01")


@pytest.mark.parametrize(
    "path,value",
    [
        ("order.quantity", 3),
        ("order.order_id", "ORD-999"),
        ("reservation", None),
        ("payment", None),
        ("shipment", None),
        ("reservation.order_id", "ORD-999"),
        ("payment.order_id", "ORD-999"),
        ("shipment.order_id", "ORD-999"),
        ("reservation.sku", "OTHER"),
        ("reservation.quantity", 1),
        ("shipment.quantity", 1),
        ("payment.amount_cents", 1),
        ("shipment.reservation_id", "RES-999"),
        ("shipment.payment_id", "PAY-999"),
        ("available_stock", 4),
    ],
)
def test_state_verification_rejects_inconsistencies(path, value):
    state = run("TOOL-01").state
    parts = path.split(".")
    target = getattr(state, parts[0]) if len(parts) == 2 else state
    setattr(target, parts[-1], value)
    with pytest.raises(ToolError, match="disagree"):
        validate_state(state, State())


def test_missing_inspection_and_unresolved_dependencies():
    config = load_scenario("TOOL-01")
    plan = build_agent(config).model.plan(config.request)
    config.plan_override = plan[:-1]
    assert build_agent(config).run(config.request).error_code == "verification_required"
    config.plan_override = plan[1:]
    result = build_agent(config).run(config.request)
    assert result.error_code == "missing_dependency"
    assert not invocations(result)
    assert result.state == State()


@pytest.mark.parametrize(
    "question,code",
    [
        ("Cancel order ORD-100", "unsupported_request"),
        ("Fulfill order ORD-999.", "order_not_found"),
    ],
)
def test_unsupported_request_and_unknown_order(question, code):
    result = build_agent(load_scenario("TOOL-01")).run(question)
    assert result.error_code == code
    assert result.state == State()


@pytest.mark.parametrize("question", ["", " ", None, 42])
def test_invalid_request_rejected(question):
    with pytest.raises(ValueError, match="nonempty string"):
        build_agent(load_scenario("TOOL-01")).run(question)
