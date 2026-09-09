from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from ground_truth_schema import load_truth
from langgraph.graph.state import CompiledStateGraph

from langgraph_workflow_agent.agent import WorkflowAgent
from langgraph_workflow_agent.dependencies import LocalDependencies
from langgraph_workflow_agent.models import (
    MAX_RETRIES,
    RECURSION_LIMIT,
    ActionResult,
    Context,
    Request,
    initial_state,
)
from langgraph_workflow_agent.scenarios import build_agent, load_scenario

ROOT = Path(__file__).resolve().parents[1]
IDS = [f"LG-{number:02}" for number in range(1, 11)]


@pytest.mark.parametrize("scenario_id", IDS)
def test_all_outcomes_and_paths(scenario_id):
    config = load_scenario(scenario_id)
    truth = load_truth(ROOT / "ground_truth" / f"{scenario_id}.json")
    assert config.request == truth.request
    result = build_agent(config).run(config.request)
    state = result.state
    assert result.path == truth.expected_path
    assert result.path == [node for update in result.updates for node in update]
    assert state["final_status"] == truth.expected_status
    assert state["validation"] == truth.expected_validation
    assert state["retry_count"] == truth.expected_retries
    assert state["selected_action"] == truth.expected_action
    assert state["action_result"] == truth.expected_action_result
    assert (
        state["context"].revision if state["context"] else None
    ) == truth.expected_context_revision
    assert (
        state["response"].status if state["response"] else None
    ) == truth.expected_response_status
    assert result.execution_error == (
        "recursion_limit" if truth.expected_termination == "recursion_limit" else None
    )
    assert scenario_id not in result.model_dump_json()


def test_construction_and_actual_langgraph_state_updates():
    agent = WorkflowAgent()
    assert isinstance(agent.graph, CompiledStateGraph)
    graph = agent.graph.get_graph()
    assert set(graph.nodes) == {
        "__start__",
        "classify",
        "gather_context",
        "evaluate",
        "retry_context",
        "execute_action",
        "abort",
        "validate",
        "respond",
        "__end__",
    }
    edges = {(edge.source, edge.target) for edge in graph.edges}
    assert {
        ("gather_context", "evaluate"),
        ("evaluate", "retry_context"),
        ("evaluate", "execute_action"),
        ("evaluate", "abort"),
        ("retry_context", "gather_context"),
        ("abort", "validate"),
        ("execute_action", "validate"),
        ("respond", "__end__"),
    } <= edges
    config = load_scenario("LG-02")
    result = agent.run(config.request)
    assert result.state == agent.graph.invoke(initial_state(config.request))
    contexts = [
        u["gather_context"]["context"] for u in result.updates if "gather_context" in u
    ]
    assert [(c.revision, c.availability) for c in contexts] == [
        (1, "retryable"),
        (2, "ready"),
    ]
    assert result.state["action_result"].context_revision == 2
    assert result.state["request"] == config.request
    assert result.state["classification"] == "host_unavailable"


@pytest.mark.parametrize(
    "telemetry,retries,destination",
    [
        ("ready", 0, "execute_action"),
        ("denied", 0, "abort"),
        ("unavailable", 0, "retry_context"),
        ("unavailable", 1, "retry_context"),
        ("unavailable", MAX_RETRIES, "abort"),
    ],
)
def test_routing_policy(telemetry, retries, destination):
    deps = LocalDependencies()
    task = Request(service="beacon", incident="worker_stalled", telemetry=telemetry)
    state = initial_state(task)
    state.update(
        classification=task.incident,
        retry_count=retries,
        context=deps.gather(task, attempt=retries + 1),
    )
    assert deps.decide(state)[0] == destination


def test_default_retry_exhaustion_and_terminal_denial():
    task = Request(service="beacon", incident="worker_stalled", telemetry="unavailable")
    result = WorkflowAgent().run(task)
    assert result.path.count("gather_context") == MAX_RETRIES + 1
    assert result.state["retry_count"] == MAX_RETRIES
    assert result.state["final_status"] == "aborted"
    assert result.execution_error is None
    denied = task.model_copy(update={"telemetry": "denied"})
    result = WorkflowAgent().run(denied)
    assert "retry_context" not in result.path
    assert "execute_action" not in result.path
    assert result.state["validation"] == []


def test_loop_keeps_real_partial_state_and_stops_at_framework_ceiling():
    config = load_scenario("LG-08")
    result = build_agent(config).run(config.request)
    assert len(result.path) == RECURSION_LIMIT
    assert result.state["retry_count"] > MAX_RETRIES
    assert result.state["final_status"] == "running"
    assert result.state["response"] is None
    assert result.execution_error == "recursion_limit"


def test_terminal_retry_guard_prevents_second_acquisition():
    config = load_scenario("LG-07")
    result = build_agent(config).run(config.request)
    assert result.path.count("gather_context") == 1
    assert {
        "retry_context": {"validation": ["terminal_retry"], "next_node": "validate"}
    } in result.updates


def test_node_override_loses_update_after_actual_execution():
    config = load_scenario("LG-06")
    agent = build_agent(config)
    calls = []
    original = agent.dependencies.execute

    def execute(action, context):
        result = original(action, context)
        calls.append(result)
        return result

    agent.dependencies.execute = execute
    result = agent.run(config.request)
    assert len(calls) == 1 and calls[0].success
    assert result.state["action_result"] is None
    assert result.state["validation"] == ["missing_action_result"]


@pytest.mark.parametrize("scenario_id", IDS)
def test_injection_removal_restores_normal_workflow(scenario_id):
    config = load_scenario(scenario_id)
    result = WorkflowAgent().run(config.request)
    expected = (
        "aborted"
        if config.request.telemetry in {"denied", "unavailable"}
        else "resolved"
    )
    assert result.state["final_status"] == expected
    assert result.state["validation"] == []
    assert result.state["response"].status == expected
    assert result.execution_error is None


@pytest.mark.parametrize("scenario_id", IDS)
def test_same_agent_repeated_and_concurrent_runs(scenario_id):
    config = load_scenario(scenario_id)
    agent = build_agent(config)
    original = config.model_dump_json()
    expected = agent.run(config.request).model_dump_json()
    assert all(
        agent.run(config.request).model_dump_json() == expected for _ in range(3)
    )
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(
            pool.map(lambda _: agent.run(config.request).model_dump_json(), range(8))
        )
    assert results == [expected] * 8
    assert config.model_dump_json() == original


def test_result_and_configuration_mutation_do_not_leak():
    config = load_scenario("LG-05")
    task = config.request.model_copy(deep=True)
    agent = build_agent(config)
    expected = agent.run(task).model_dump_json()
    config.context_overrides[0].response.revision = 99
    result = agent.run(task)
    result.state["context"].revision = 88
    result.updates.clear()
    assert agent.run(task).model_dump_json() == expected


@pytest.mark.parametrize("scenario_id", IDS)
def test_scenario_id_is_only_a_loader_label(scenario_id):
    config = load_scenario(scenario_id)
    renamed = config.model_copy(update={"scenario_id": "LG-99"})
    assert build_agent(config).run(config.request) == build_agent(renamed).run(
        renamed.request
    )


@pytest.mark.parametrize(
    "result,issue",
    [
        (None, "missing_action_result"),
        (
            ActionResult(action="failover", context_revision=1, success=True),
            "action_mismatch",
        ),
        (
            ActionResult(action="restart", context_revision=2, success=True),
            "action_mismatch",
        ),
        (
            ActionResult(action="restart", context_revision=1, success=False),
            "action_failed",
        ),
    ],
)
def test_validation_failure_paths(result, issue):
    state = initial_state(load_scenario("LG-01").request)
    state.update(
        context=Context(revision=1, availability="ready", incident="worker_stalled"),
        selected_action="restart",
        action_result=result,
        final_status="resolved",
    )
    assert WorkflowAgent.validate(state) == {
        "validation": [issue],
        "final_status": "blocked",
    }


def test_unknown_overrides_and_unexpected_dependency_errors():
    with pytest.raises(ValueError, match="Unknown node"):
        WorkflowAgent(nodes={"invented": lambda original: original})

    class Broken(LocalDependencies):
        def gather(self, request, *, attempt):
            raise RuntimeError("unexpected dependency failure")

    with pytest.raises(RuntimeError, match="unexpected dependency failure"):
        WorkflowAgent(Broken()).run(load_scenario("LG-01").request)
