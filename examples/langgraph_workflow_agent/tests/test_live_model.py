import builtins
import json
from pathlib import Path

import httpx
import pytest
from pydantic import SecretStr, ValidationError

from langgraph_workflow_agent.agent import WorkflowAgent
from langgraph_workflow_agent.cli import main
from langgraph_workflow_agent.live_model import (
    LiveConfig,
    LiveModelClient,
    LiveOutputError,
    LiveProviderError,
    LiveTimeoutError,
)
from langgraph_workflow_agent.models import Request

TASK = {"service": "beacon", "incident": "worker_stalled", "telemetry": "ready"}
ANSWER = {"status": "resolved", "message": "The simulated remediation succeeded."}


@pytest.fixture(autouse=True)
def environment(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".env").write_text("", encoding="utf-8")
    for suffix in ("API_KEY", "MODEL", "BASE_URL", "TIMEOUT_SECONDS"):
        monkeypatch.delenv("LANGGRAPH_AGENT_" + suffix, raising=False)

    def deny(*args, **kwargs):
        raise AssertionError("Tests must use HTTPX MockTransport")

    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", deny)


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


@pytest.mark.parametrize(
    "incident,telemetry,action,retries",
    [
        ("worker_stalled", "ready", "restart", 0),
        ("host_unavailable", "delayed", "failover", 1),
    ],
)
def test_live_graph(config, incident, telemetry, action, retries):
    requests = []
    task = {**TASK, "incident": incident, "telemetry": telemetry}
    original_request = "  A Beacon incident  "
    with client_for(
        [
            completion({"request": task}),
            completion({"action": action}),
            completion(ANSWER),
        ],
        requests,
    ) as client:
        model = LiveModelClient(config, client)
        result = WorkflowAgent(model).run(model.parse_request(original_request))
    assert result.state["final_status"] == "resolved"
    assert result.state["selected_action"] == action
    assert result.state["retry_count"] == retries
    assert result.state["action_result"].context_revision == retries + 1
    assert result.state["validation"] == []
    assert result.path == ["classify", "gather_context", "evaluate"] + (
        ["retry_context", "gather_context", "evaluate"] if retries else []
    ) + ["execute_action", "validate", "respond"]
    assert len(requests) == 3
    for request, stage in zip(
        requests, ["parse_request", "evaluate", "respond"], strict=True
    ):
        body = json.loads(request.content)
        assert f"Stage: {stage}." in body["messages"][0]["content"]
        if stage == "parse_request":
            assert json.loads(body["messages"][1]["content"]) == {
                "request": original_request
            }
        assert body["response_format"] == {"type": "json_object"}
        assert request.headers["authorization"] == "Bearer test-token"
        assert str(request.url) == "https://provider.invalid/v1/chat/completions"
        assert set(request.extensions["timeout"].values()) == {30.0}


@pytest.mark.parametrize("telemetry,retries", [("denied", 0), ("unavailable", 2)])
def test_live_preserves_terminal_and_retry_policy(config, telemetry, retries):
    requests = []
    with client_for(
        [completion({"status": "aborted", "message": "Operator review required."})],
        requests,
    ) as client:
        model = LiveModelClient(config, client)
        result = WorkflowAgent(model).run(Request(**{**TASK, "telemetry": telemetry}))
    assert result.state["final_status"] == "aborted"
    assert result.state["retry_count"] == retries
    assert "execute_action" not in result.path
    assert result.path.count("gather_context") == retries + 1
    assert len(requests) == 1  # No model is asked to override a retry/abort gate.


@pytest.mark.parametrize(
    "bad",
    [
        "not json",
        "[]",
        '{"request": NaN}',
        {"request": {**TASK, "incident": "unknown"}},
        {"request": TASK, "extra": 1},
        '{"request": null, "request": null}',
        {"request": {**TASK, "telemetry": True}},
    ],
)
def test_repair_and_exhausted_invalid_output(config, bad):
    requests = []
    with client_for(
        [completion(bad), completion({"request": TASK})], requests
    ) as client:
        assert LiveModelClient(config, client).parse_request(
            "Beacon worker stuck"
        ) == Request(**TASK)
    assert len(requests) == 2
    assert len(json.loads(requests[1].content)["messages"]) == 3
    requests.clear()
    with (
        client_for([completion(bad), completion(bad)], requests) as client,
        pytest.raises(LiveOutputError, match="after one repair"),
    ):
        LiveModelClient(config, client).parse_request("Beacon worker stuck")
    assert len(requests) == 2


@pytest.mark.parametrize("code", [429, 500, 502, 503, 504])
def test_transient_success_and_exhaustion(config, code):
    requests = []
    with client_for(
        [httpx.Response(code), completion({"request": TASK})], requests
    ) as client:
        LiveModelClient(config, client).parse_request("Beacon worker stuck")
    assert len(requests) == 2
    assert requests[0].content == requests[1].content
    requests.clear()
    with (
        client_for([httpx.Response(code), httpx.Response(code)], requests) as client,
        pytest.raises(LiveProviderError, match=f"HTTP {code}"),
    ):
        LiveModelClient(config, client).parse_request("Beacon worker stuck")
    assert len(requests) == 2


@pytest.mark.parametrize(
    "sequence",
    [
        [httpx.Response(429), completion("bad"), completion({"request": TASK})],
        [completion("bad"), httpx.Response(503), completion({"request": TASK})],
    ],
)
def test_shared_three_request_ceiling(config, sequence):
    requests = []
    with client_for(sequence, requests) as client:
        LiveModelClient(config, client).parse_request("Beacon worker stuck")
    assert len(requests) == 3


def test_http_budget_is_not_reset_for_repair(config):
    requests = []
    with (
        client_for(
            [httpx.Response(429), completion("bad"), httpx.Response(503)], requests
        ) as client,
        pytest.raises(LiveProviderError, match="503"),
    ):
        LiveModelClient(config, client).parse_request("Beacon worker stuck")
    assert len(requests) == 3


@pytest.mark.parametrize("code", [301, 400, 401, 403, 404, 501])
def test_nontransient_provider_error(config, code):
    requests = []
    with (
        client_for([httpx.Response(code, text="secret-token")], requests) as client,
        pytest.raises(LiveProviderError) as error,
    ):
        LiveModelClient(config, client).parse_request("Beacon worker stuck")
    assert "secret-token" not in str(error.value)
    assert len(requests) == 1


@pytest.mark.parametrize(
    "exception,kind",
    [
        (httpx.ReadTimeout("secret-token"), LiveTimeoutError),
        (httpx.ConnectError("secret-token"), LiveProviderError),
    ],
)
def test_transport_failure(config, exception, kind):
    requests = []
    with client_for([exception], requests) as client, pytest.raises(kind) as error:
        WorkflowAgent(LiveModelClient(config, client)).run(Request(**TASK))
    assert "secret-token" not in str(error.value)
    assert len(requests) == 1


@pytest.mark.parametrize(
    "response",
    [
        completion(None, message={"refusal": "denied"}),
        completion(None, finish_reason="content_filter"),
    ],
)
def test_refusal_not_repaired(config, response):
    requests = []
    with (
        client_for([response], requests) as client,
        pytest.raises(LiveProviderError, match="refused"),
    ):
        LiveModelClient(config, client).parse_request("Beacon worker stuck")
    assert len(requests) == 1


@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(200, json={}),
        completion({"request": TASK}, finish_reason="length"),
        completion(None, message={"content": None}),
        httpx.Response(200, text="bad envelope"),
    ],
)
def test_bad_envelope_repaired(config, response):
    requests = []
    with client_for([response, completion({"request": TASK})], requests) as client:
        LiveModelClient(config, client).parse_request("Beacon worker stuck")
    assert len(requests) == 2


def test_action_and_response_consistency_repair(config):
    requests = []
    sequence = [
        completion({"action": "failover"}),
        completion({"action": "restart"}),
        completion({**ANSWER, "status": "aborted"}),
        completion(ANSWER),
    ]
    with client_for(sequence, requests) as client:
        result = WorkflowAgent(LiveModelClient(config, client)).run(Request(**TASK))
    assert result.state["selected_action"] == "restart"
    assert result.state["response"].status == "resolved"
    assert len(requests) == 4


def test_invalid_action_cannot_execute(config):
    requests = []
    with client_for([completion({"action": "failover"})] * 2, requests) as client:
        agent = WorkflowAgent(LiveModelClient(config, client))
        with pytest.raises(LiveOutputError):
            agent.run(Request(**TASK))
    assert len(requests) == 2


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
        "LANGGRAPH_AGENT_API_KEY=file-token\nLANGGRAPH_AGENT_MODEL=file-model\n"
        "LANGGRAPH_AGENT_BASE_URL=https://provider.invalid/v1/\nLANGGRAPH_AGENT_TIMEOUT_SECONDS=12\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("LANGGRAPH_AGENT_MODEL", "shell-model")
    # Register the other names with monkeypatch so dotenv writes are cleaned up.
    for suffix in ("API_KEY", "BASE_URL", "TIMEOUT_SECONDS"):
        monkeypatch.setenv("LANGGRAPH_AGENT_" + suffix, "")
        monkeypatch.delenv("LANGGRAPH_AGENT_" + suffix)
    config = LiveConfig.from_env()
    assert config.model == "shell-model"
    assert config.api_key.get_secret_value() == "file-token"
    assert config.base_url == "https://provider.invalid/v1"
    assert config.timeout == 12


@pytest.mark.parametrize("timeout", [None, "invalid", "nan", "inf", "0"])
def test_config_cli_error_is_sanitized(monkeypatch, capsys, timeout):
    if timeout is not None:
        monkeypatch.setenv("LANGGRAPH_AGENT_API_KEY", "private-token")
        monkeypatch.setenv("LANGGRAPH_AGENT_MODEL", "a-model")
        monkeypatch.setenv("LANGGRAPH_AGENT_TIMEOUT_SECONDS", timeout)
    assert main(["ask", "Beacon worker stuck", "--json"]) == 1
    output = capsys.readouterr()
    assert not output.out
    assert "Invalid live configuration" in output.err
    assert "private-token" not in output.err


def test_live_cli_isolation_and_client_cleanup(config, monkeypatch, capsys):
    requests = []
    client = client_for(
        [
            completion({"request": TASK}),
            completion({"action": "restart"}),
            completion(ANSWER),
        ],
        requests,
    )
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
    original_request = "  Beacon worker stuck  "
    assert main(["ask", original_request, "--json"]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["state"]["final_status"] == "resolved"
    assert result["original_request"] == original_request
    assert client.is_closed
    for request in requests:
        assert not any(
            term in request.content
            for term in [b"LG-", b"scenario_id", b"expected_outcome", b"suspicious"]
        )


def test_provider_cli_error_closes_client(config, monkeypatch, capsys):
    client = client_for([httpx.Response(401)], [])
    monkeypatch.setattr(httpx, "Client", lambda: client)
    monkeypatch.setattr(LiveConfig, "from_env", lambda: config)
    assert main(["ask", "Beacon worker stuck", "--json"]) == 1
    output = capsys.readouterr()
    assert not output.out and "HTTP 401" in output.err
    assert client.is_closed


def test_unsupported_and_empty_input(config):
    with client_for([completion({"request": None})], []) as client:
        model = LiveModelClient(config, client)
        with pytest.raises(ValueError, match="nonempty"):
            model.parse_request(" ")
        with pytest.raises(ValueError, match="Unsupported"):
            model.parse_request("Unrelated task")


def test_controlled_does_not_load_live_configuration(monkeypatch, capsys):
    def deny():
        raise AssertionError("Controlled mode must not load live configuration")

    monkeypatch.setattr(LiveConfig, "from_env", deny)
    monkeypatch.setenv("LANGGRAPH_AGENT_TIMEOUT_SECONDS", "invalid")
    assert main(["run", "LG-01", "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["state"]["final_status"] == "resolved"
