import builtins
import json
from copy import deepcopy
from pathlib import Path

import httpx
import pytest
from pydantic import SecretStr, ValidationError

from tool_task_agent.agent import TaskAgent
from tool_task_agent.cli import main
from tool_task_agent.live_model import (
    LiveConfig,
    LiveModelClient,
    LiveOutputError,
    LiveProviderError,
    LiveTimeoutError,
)
from tool_task_agent.tools import LocalTools, ToolError

PLAN = [
    {"step_id": "order", "tool": "get_order", "arguments": {"order_id": "ORD-100"}},
    {
        "step_id": "reserve",
        "tool": "reserve_inventory",
        "arguments": {
            "order_id": "$order.order_id",
            "sku": "$order.sku",
            "quantity": "$order.quantity",
        },
    },
    {
        "step_id": "pay",
        "tool": "charge_payment",
        "arguments": {
            "order_id": "$order.order_id",
            "amount_cents": "$order.total_cents",
        },
    },
    {
        "step_id": "ship",
        "tool": "create_shipment",
        "arguments": {"order_id": "$order.order_id"},
    },
    {
        "step_id": "inspect",
        "tool": "inspect_fulfillment",
        "arguments": {"order_id": "$order.order_id"},
    },
]
COMPLETED = {
    "status": "completed",
    "message": "The simulated fulfillment completed.",
    "shipment_id": "SHIP-100",
    "quantity": 2,
}


@pytest.fixture(autouse=True)
def environment(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".env").write_text("", encoding="utf-8")
    for suffix in ("API_KEY", "MODEL", "BASE_URL", "TIMEOUT_SECONDS"):
        monkeypatch.delenv("TOOL_TASK_AGENT_" + suffix, raising=False)

    def deny(*args, **kwargs):
        raise AssertionError("Tests must use HTTPX MockTransport")

    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", deny)
    monkeypatch.setattr("tool_task_agent.live_model.time.sleep", lambda _: None)


@pytest.fixture
def config():
    return LiveConfig(
        api_key=SecretStr("test-token"),
        model="test-model",
        base_url="https://provider.invalid/v1",
    )


def completion(value, **updates):
    return httpx.Response(
        200,
        json={
            "choices": [
                {
                    "message": {
                        "content": value
                        if isinstance(value, str)
                        else json.dumps(value)
                    },
                    "finish_reason": "stop",
                    **updates,
                }
            ]
        },
    )


def client_for(responses, requests):
    pending = iter(responses)

    def handle(request):
        requests.append(request)
        response = next(pending)
        if isinstance(response, Exception):
            raise response
        return response

    return httpx.Client(transport=httpx.MockTransport(handle))


def test_successful_live_multitool_fulfillment(config):
    requests = []
    with client_for(
        [completion({"calls": PLAN}), completion(COMPLETED)], requests
    ) as client:
        result = TaskAgent(LiveModelClient(config, client), LocalTools).run(
            "Please fulfill order ORD-100"
        )
    assert result.status == "completed"
    assert result.state.available_stock == 3
    assert result.state.reservation is not None
    assert result.state.payment is not None
    assert result.state.shipment is not None
    assert [event.operation for event in result.events if event.attempt] == [
        "get_order",
        "reserve_inventory",
        "charge_payment",
        "create_shipment",
        "inspect_fulfillment",
    ]
    assert len(requests) == 2
    for request, stage in zip(requests, ["plan", "respond"], strict=True):
        body = json.loads(request.content)
        assert f"Stage: {stage}." in body["messages"][0]["content"]
        assert body["response_format"] == {"type": "json_object"}
        assert request.headers["authorization"] == "Bearer test-token"
        assert str(request.url) == "https://provider.invalid/v1/chat/completions"
        assert set(request.extensions["timeout"].values()) == {30.0}


@pytest.mark.parametrize("invalid_plan", ["wrong_tool", "duplicate_step"])
def test_invalid_plan_is_repaired_before_execution(config, invalid_plan):
    wrong = deepcopy(PLAN)
    if invalid_plan == "wrong_tool":
        wrong[1] = {
            "step_id": "reserve",
            "tool": "get_stock",
            "arguments": {"sku": "SENSOR-KIT"},
        }
    else:
        wrong[-1] = deepcopy(wrong[2])
    requests = []
    with client_for(
        [
            completion({"calls": wrong}),
            completion({"calls": PLAN}),
            completion(COMPLETED),
        ],
        requests,
    ) as client:
        result = TaskAgent(LiveModelClient(config, client), LocalTools).run(
            "Fulfill ORD-100"
        )
    assert result.status == "completed"
    assert len(requests) == 3
    assert len(json.loads(requests[1].content)["messages"]) == 3


def test_invalid_arguments_fail_without_side_effect(config):
    invalid = deepcopy(PLAN)
    invalid[1]["arguments"]["quantity"] = 0
    failed = {
        "status": "failed",
        "message": "The simulated fulfillment failed.",
        "shipment_id": None,
        "quantity": None,
    }
    with client_for([completion({"calls": invalid}), completion(failed)], []) as client:
        result = TaskAgent(LiveModelClient(config, client), LocalTools).run(
            "Fulfill ORD-100"
        )
    assert result.status == "failed"
    assert result.error_code == "invalid_arguments"
    assert result.state.available_stock == 5
    assert result.state.reservation is None
    assert result.state.payment is None
    assert result.state.shipment is None


def test_unknown_tool_never_executes(config):
    unknown = deepcopy(PLAN)
    unknown[0]["tool"] = "invented_tool"
    requests = []
    with (
        client_for([completion({"calls": unknown})] * 2, requests) as client,
        pytest.raises(LiveOutputError, match="after one repair"),
    ):
        TaskAgent(LiveModelClient(config, client), LocalTools).run("Fulfill ORD-100")
    assert len(requests) == 2


class PaymentFailureTools(LocalTools):
    def charge_payment(self, args):
        raise ToolError("payment_declined", "Payment was declined")


def test_payment_failure_stops_before_shipment(config):
    failed = {
        "status": "failed",
        "message": "Payment failed and no shipment was created.",
        "shipment_id": None,
        "quantity": None,
    }
    requests = []
    with client_for(
        [completion({"calls": PLAN}), completion(failed)], requests
    ) as client:
        result = TaskAgent(LiveModelClient(config, client), PaymentFailureTools).run(
            "Fulfill ORD-100"
        )
    assert result.error_code == "payment_declined"
    assert result.state.reservation is not None
    assert result.state.payment is None
    assert result.state.shipment is None
    assert not any(event.operation == "create_shipment" for event in result.events)
    response_context = json.loads(
        json.loads(requests[-1].content)["messages"][1]["content"]
    )
    assert response_context["error_code"] == "payment_declined"


@pytest.mark.parametrize(
    "bad",
    [
        "not json",
        "[]",
        '{"calls": NaN}',
        {"calls": []},
        {"calls": PLAN, "extra": True},
        '{"calls": [], "calls": []}',
    ],
)
def test_structured_output_repair_and_exhaustion(config, bad):
    requests = []
    with client_for([completion(bad), completion({"calls": PLAN})], requests) as client:
        assert len(LiveModelClient(config, client).plan("Fulfill ORD-100")) == 5
    assert len(requests) == 2
    requests.clear()
    with (
        client_for([completion(bad)] * 2, requests) as client,
        pytest.raises(LiveOutputError, match="after one repair"),
    ):
        LiveModelClient(config, client).plan("Fulfill ORD-100")
    assert len(requests) == 2


@pytest.mark.parametrize("code", [429, 500, 502, 503, 504])
def test_transient_retry_success_and_exhaustion(config, code):
    requests = []
    with client_for(
        [httpx.Response(code), completion({"calls": PLAN})], requests
    ) as client:
        LiveModelClient(config, client).plan("Fulfill ORD-100")
    assert len(requests) == 2
    assert requests[0].content == requests[1].content
    requests.clear()
    with (
        client_for([httpx.Response(code), httpx.Response(code)], requests) as client,
        pytest.raises(LiveProviderError, match=f"HTTP {code}"),
    ):
        LiveModelClient(config, client).plan("Fulfill ORD-100")
    assert len(requests) == 2


@pytest.mark.parametrize(
    "sequence",
    [
        [httpx.Response(429), completion("bad"), completion({"calls": PLAN})],
        [completion("bad"), httpx.Response(503), completion({"calls": PLAN})],
    ],
)
def test_shared_three_request_ceiling(config, sequence):
    requests = []
    with client_for(sequence, requests) as client:
        LiveModelClient(config, client).plan("Fulfill ORD-100")
    assert len(requests) == 3


def test_http_budget_is_not_reset_for_repair(config):
    requests = []
    with (
        client_for(
            [httpx.Response(429), completion("bad"), httpx.Response(503)], requests
        ) as client,
        pytest.raises(LiveProviderError, match="503"),
    ):
        LiveModelClient(config, client).plan("Fulfill ORD-100")
    assert len(requests) == 3


@pytest.mark.parametrize("code", [301, 400, 401, 403, 404, 501])
def test_nontransient_provider_error_is_not_retried(config, code):
    requests = []
    with (
        client_for([httpx.Response(code, text="private-token")], requests) as client,
        pytest.raises(LiveProviderError) as error,
    ):
        LiveModelClient(config, client).plan("Fulfill ORD-100")
    assert "private-token" not in str(error.value)
    assert len(requests) == 1


@pytest.mark.parametrize(
    "exception,kind",
    [
        (httpx.ReadTimeout("private-token"), LiveTimeoutError),
        (httpx.ConnectError("private-token"), LiveProviderError),
    ],
)
def test_transport_failure_is_not_retried(config, exception, kind):
    requests = []
    with client_for([exception], requests) as client, pytest.raises(kind) as error:
        TaskAgent(LiveModelClient(config, client), LocalTools).run("Fulfill ORD-100")
    assert "private-token" not in str(error.value)
    assert len(requests) == 1


def test_refusal_is_not_repaired(config):
    requests = []
    response = completion(None, message={"refusal": "denied"})
    with (
        client_for([response], requests) as client,
        pytest.raises(LiveProviderError, match="refused"),
    ):
        LiveModelClient(config, client).plan("Fulfill ORD-100")
    assert len(requests) == 1


@pytest.mark.parametrize(
    "wrong",
    [
        {**COMPLETED, "status": "failed"},
        {**COMPLETED, "shipment_id": "SHIP-INVENTED", "quantity": 99},
    ],
)
def test_final_response_consistency_is_repaired(config, wrong):
    requests = []
    with client_for(
        [completion({"calls": PLAN}), completion(wrong), completion(COMPLETED)],
        requests,
    ) as client:
        result = TaskAgent(LiveModelClient(config, client), LocalTools).run(
            "Fulfill ORD-100"
        )
    assert result.final_response.shipment_id == result.state.shipment.shipment_id
    assert result.final_response.quantity == result.state.shipment.quantity
    assert len(requests) == 3


@pytest.mark.parametrize(
    "change",
    [
        {"api_key": SecretStr("")},
        {"api_key": SecretStr("bad\ntoken")},
        {"model": " "},
        {"timeout": 0},
        {"timeout": 121},
        {"timeout": float("nan")},
        {"base_url": "http://remote.invalid"},
        {"base_url": "https://user:pass@host.invalid"},
        {"base_url": "https://host.invalid?q=secret"},
        {"base_url": "https://host.invalid/#frag"},
        {"base_url": "nonsense"},
    ],
)
def test_invalid_config(config, change):
    with pytest.raises(ValidationError):
        LiveConfig.model_validate({**config.model_dump(), **change})


def test_dotenv_and_shell_precedence(tmp_path, monkeypatch):
    (tmp_path / ".env").write_text(
        "TOOL_TASK_AGENT_API_KEY=file-token\n"
        "TOOL_TASK_AGENT_MODEL=file-model\n"
        "TOOL_TASK_AGENT_BASE_URL=https://provider.invalid/v1/\n"
        "TOOL_TASK_AGENT_TIMEOUT_SECONDS=12\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("TOOL_TASK_AGENT_MODEL", "shell-model")
    for suffix in ("API_KEY", "BASE_URL", "TIMEOUT_SECONDS"):
        monkeypatch.setenv("TOOL_TASK_AGENT_" + suffix, "")
        monkeypatch.delenv("TOOL_TASK_AGENT_" + suffix)
    config = LiveConfig.from_env()
    assert config.model == "shell-model"
    assert config.api_key.get_secret_value() == "file-token"
    assert config.base_url == "https://provider.invalid/v1"
    assert config.timeout == 12
    assert "file-token" not in config.model_dump_json()
    monkeypatch.setenv("TOOL_TASK_AGENT_API_KEY", "")
    with pytest.raises(ValueError, match="Invalid live configuration"):
        LiveConfig.from_env()


def test_live_cli_isolated_and_preserves_original_request(config, monkeypatch, capsys):
    requests = []
    client = client_for([completion({"calls": PLAN}), completion(COMPLETED)], requests)
    monkeypatch.setattr(httpx, "Client", lambda: client)
    monkeypatch.setattr(LiveConfig, "from_env", lambda: config)
    original_import = builtins.__import__
    original_read = Path.read_text

    def guarded_import(name, *args, **kwargs):
        assert "scenarios" not in name and "ground_truth" not in name
        return original_import(name, *args, **kwargs)

    def guarded_read(path, *args, **kwargs):
        assert "scenarios" not in path.parts and "ground_truth" not in path.parts
        return original_read(path, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", guarded_import)
    monkeypatch.setattr(Path, "read_text", guarded_read)
    original_request = "  Please fulfill order ORD-100  "
    assert main(["ask", original_request, "--json"]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["original_request"] == original_request
    assert result["request"] == original_request.strip()
    assert result["status"] == "completed"
    assert client.is_closed
    for request in requests:
        assert not any(
            term in request.content
            for term in [
                b"TOOL-",
                b"scenario_id",
                b"expected_outcome",
                b"ground_truth",
                b"suspicious",
            ]
        )


def test_live_cli_error_is_sanitized_and_closes_client(config, monkeypatch, capsys):
    client = client_for([httpx.Response(401, text="private-token")], [])
    monkeypatch.setattr(httpx, "Client", lambda: client)
    monkeypatch.setattr(LiveConfig, "from_env", lambda: config)
    assert main(["ask", "Fulfill ORD-100", "--json"]) == 1
    output = capsys.readouterr()
    assert not output.out
    assert "HTTP 401" in output.err
    assert "private-token" not in output.err
    assert client.is_closed


def test_controlled_mode_does_not_load_live_config(monkeypatch, capsys):
    def deny():
        raise AssertionError("Controlled mode must not load live configuration")

    monkeypatch.setattr(LiveConfig, "from_env", deny)
    monkeypatch.setenv("TOOL_TASK_AGENT_TIMEOUT_SECONDS", "invalid")
    assert main(["run", "TOOL-01", "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["status"] == "completed"
