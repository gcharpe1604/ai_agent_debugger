import builtins
import json
from copy import deepcopy
from pathlib import Path

import httpx
import pytest
from pydantic import SecretStr, ValidationError

from research_planning_agent.agent import ResearchPlanningAgent
from research_planning_agent.cli import main
from research_planning_agent.evidence import EvidenceSource, load_evidence
from research_planning_agent.live_model import (
    LiveConfig,
    LiveModelClient,
    LiveOutputError,
    LiveProviderError,
    LiveTimeoutError,
)
from research_planning_agent.model_client import ModelClient

REQUEST = (
    "Recommend the cheapest eligible field station between Ridge and Vale for 40 "
    "people, requiring 10 kW, a daily budget of 1000 credits, open access and an "
    "approved permit as of 2026-06-01."
)
EARLY_REQUEST = REQUEST.replace("2026-06-01", "2025-01-01")


@pytest.fixture(autouse=True)
def environment(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".env").write_text("", encoding="utf-8")
    for suffix in ("API_KEY", "MODEL", "BASE_URL", "TIMEOUT_SECONDS"):
        monkeypatch.delenv("RESEARCH_PLANNING_AGENT_" + suffix, raising=False)

    def deny(*args, **kwargs):
        raise AssertionError("Tests must use HTTPX MockTransport")

    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", deny)
    monkeypatch.setattr("research_planning_agent.live_model.time.sleep", lambda _: None)


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


def controlled_result(request=REQUEST):
    return ResearchPlanningAgent(ModelClient(), EvidenceSource(load_evidence())).run(
        request
    )


def live_responses(result):
    responses = [
        completion({"task": result.task.model_dump()}),
        completion(result.plan.model_dump()),
        completion(result.assessments[0].model_dump()),
    ]
    if result.revision is not None:
        responses.extend(
            [
                completion(result.revision.model_dump()),
                completion(result.assessments[1].model_dump()),
            ]
        )
    responses.append(completion(result.draft.model_dump()))
    return responses


def test_healthy_live_recommendation_collects_and_revises(config):
    expected = controlled_result()
    requests = []
    with client_for(live_responses(expected), requests) as client:
        result = ResearchPlanningAgent(
            LiveModelClient(config, client), EvidenceSource(load_evidence())
        ).run(REQUEST)
    assert result.status == "completed"
    assert result.draft.recommendation == "vale"
    assert result.revision is not None
    assert len(result.collections) == 11
    assert len(result.assessments) == 2
    assert result.assessments[0].conflicts["vale.permit"] == [
        "VALE-PERMIT-1",
        "VALE-PERMIT-2",
    ]
    assert result.assessments[1].selected["vale.permit"] == ["VALE-PERMIT-3"]
    assert {"VALE-PERMIT-1", "VALE-PERMIT-2"} <= set(result.assessments[1].stale)
    assert len(requests) == 6
    for request in requests:
        body = json.loads(request.content)
        assert body["response_format"] == {"type": "json_object"}
        assert request.headers["authorization"] == "Bearer test-token"
        assert str(request.url) == "https://provider.invalid/v1/chat/completions"
        assert set(request.extensions["timeout"].values()) == {30.0}
    assessment_context = json.loads(
        json.loads(requests[2].content)["messages"][1]["content"]
    )
    assert {
        "evidence_id",
        "topic",
        "version",
        "published_on",
        "status",
        "content",
    } <= assessment_context["evidence"][0].keys()


def test_missing_evidence_returns_incomplete_without_recommendation(config):
    expected = controlled_result(EARLY_REQUEST)
    requests = []
    with client_for(live_responses(expected), requests) as client:
        result = ResearchPlanningAgent(
            LiveModelClient(config, client), EvidenceSource(load_evidence())
        ).run(EARLY_REQUEST)
    assert result.status == "incomplete"
    assert result.draft.recommendation is None
    assert len(result.draft.claims) == 0
    assert len(result.draft.unresolved) == 10
    assert result.issues == []
    assert result.revision is not None
    assert len(requests) == 6


def test_ambiguous_normalization_fails_explicitly(config):
    requests = []
    with (
        client_for([completion({"task": None})], requests) as client,
        pytest.raises(ValueError, match="Unsupported or ambiguous"),
    ):
        LiveModelClient(config, client).decompose("Which station is best?")
    assert len(requests) == 1


def test_normalization_accepts_grounded_free_text(config):
    request = (
        "As of 2026-06-01, recommend the lowest cost option between Ridge and Vale "
        "for 40 researchers needing 10 kilowatts and no more than 1,000 credits "
        "daily; access must be open and the permit must be approved."
    )
    task = controlled_result().task.model_copy(update={"request": request})
    with client_for([completion({"task": task.model_dump()})], []) as client:
        assert LiveModelClient(config, client).decompose(request) == task


def test_normalization_rejects_ambiguous_constraint_values(config):
    request = REQUEST.replace("40 people", "40 people or 50 people")
    task = controlled_result().task.model_copy(update={"request": request})
    requests = []
    with (
        client_for([completion({"task": task.model_dump()})] * 2, requests) as client,
        pytest.raises(LiveOutputError, match="after one repair"),
    ):
        LiveModelClient(config, client).decompose(request)
    assert len(requests) == 2


def test_task_drift_and_invalid_plan_are_repaired(config):
    expected = controlled_result()
    drifted_task = expected.task.model_copy(update={"people": 99})
    wrong_plan = expected.plan.model_copy(deep=True)
    wrong_plan.steps[-1].requires = []
    requests = []
    with client_for(
        [
            completion({"task": drifted_task.model_dump()}),
            completion({"task": expected.task.model_dump()}),
            completion(wrong_plan.model_dump()),
            completion(expected.plan.model_dump()),
        ],
        requests,
    ) as client:
        model = LiveModelClient(config, client)
        task = model.decompose(REQUEST)
        plan = model.create_plan(task)
    assert task == expected.task and plan == expected.plan
    assert len(requests) == 4
    assert len(json.loads(requests[1].content)["messages"]) == 3


def test_wrong_assessment_and_unsupported_synthesis_are_repaired(config):
    expected = controlled_result()
    wrong_assessment = expected.assessments[-1].model_copy(deep=True)
    wrong_assessment.selected["ridge.capacity"] = ["RIDGE-CAPACITY-1"]
    wrong_report = expected.draft.model_copy(deep=True)
    wrong_report.claims[0].evidence_ids = ["UNKNOWN"]
    requests = []
    with client_for(
        [
            completion(wrong_assessment.model_dump()),
            completion(expected.assessments[-1].model_dump()),
            completion(wrong_report.model_dump()),
            completion(expected.draft.model_dump()),
        ],
        requests,
    ) as client:
        model = LiveModelClient(config, client)
        assessment = model.assess_evidence(
            expected.task, expected.evidence, invocation=2
        )
        report = model.synthesize_report(expected.task, assessment, expected.evidence)
    assert assessment == expected.assessments[-1]
    assert report == expected.draft
    assert len(requests) == 4


def test_contradictory_unresolved_fact_is_repaired_with_specific_feedback(config):
    expected = controlled_result()
    wrong_report = expected.draft.model_copy(deep=True)
    wrong_report.unresolved = ["ridge.capacity"]
    requests = []
    with client_for(
        [
            completion(wrong_report.model_dump()),
            completion(expected.draft.model_dump()),
        ],
        requests,
    ) as client:
        report = LiveModelClient(config, client).synthesize_report(
            expected.task, expected.assessments[-1], expected.evidence
        )

    assert report == expected.draft
    assert len(requests) == 2
    context = json.loads(json.loads(requests[0].content)["messages"][1]["content"])
    assert context["required_unresolved"] == []
    repair = json.loads(requests[1].content)["messages"][-1]["content"]
    assert "unresolved_facts_mismatch" in repair


def test_invalid_revision_and_unsupported_report_stop_after_repair(config):
    expected = controlled_result()
    wrong_revision = expected.revision.model_copy(deep=True)
    wrong_revision.plan.steps = []
    wrong_report = expected.draft.model_copy(deep=True)
    wrong_report.claims[0].value = 999
    requests = []
    with (
        client_for([completion(wrong_revision.model_dump())] * 2, requests) as client,
        pytest.raises(LiveOutputError, match="after one repair"),
    ):
        LiveModelClient(config, client).revise_plan(
            expected.task, expected.assessments[0]
        )
    assert len(requests) == 2
    requests.clear()
    with (
        client_for([completion(wrong_report.model_dump())] * 2, requests) as client,
        pytest.raises(LiveOutputError, match="after one repair"),
    ):
        LiveModelClient(config, client).synthesize_report(
            expected.task, expected.assessments[-1], expected.evidence
        )
    assert len(requests) == 2


@pytest.mark.parametrize(
    ("failure", "feedback"),
    [
        ("bare_plan", "plan: Field required"),
        ("missing_query", "Revision violates query or dependency rules"),
        ("wrong_requires", "Revision violates query or dependency rules"),
    ],
)
def test_near_valid_revision_is_repaired_with_actionable_feedback(
    config, failure, feedback
):
    expected = controlled_result()
    valid = expected.revision.model_dump()
    invalid = deepcopy(valid)
    if failure == "bare_plan":
        invalid = {**invalid["plan"], "reason": invalid["reason"]}
    elif failure == "missing_query":
        del invalid["plan"]["steps"][0]["query"]
    else:
        invalid["plan"]["steps"][0]["requires"] = []

    requests = []
    with client_for([completion(invalid), completion(valid)], requests) as client:
        revision = LiveModelClient(config, client).revise_plan(
            expected.task, expected.assessments[0]
        )

    assert revision == expected.revision
    assert len(requests) == 2
    first_body = json.loads(requests[0].content)
    context = json.loads(first_body["messages"][1]["content"])
    assert context["required_steps"] == valid["plan"]["steps"]
    repair = json.loads(requests[1].content)["messages"][-1]["content"]
    assert "Validation feedback:" in repair
    assert feedback in repair


@pytest.mark.parametrize(
    "bad",
    [
        "not json",
        "[]",
        '{"task": NaN}',
        {"task": {}},
        {"task": None, "extra": True},
        '{"task": null, "task": null}',
    ],
)
def test_structured_output_repair_and_exhaustion(config, bad):
    expected = controlled_result()
    valid = {"task": expected.task.model_dump()}
    requests = []
    with client_for([completion(bad), completion(valid)], requests) as client:
        assert LiveModelClient(config, client).decompose(REQUEST) == expected.task
    assert len(requests) == 2
    requests.clear()
    with (
        client_for([completion(bad)] * 2, requests) as client,
        pytest.raises(LiveOutputError, match="after one repair"),
    ):
        LiveModelClient(config, client).decompose(REQUEST)
    assert len(requests) == 2


@pytest.mark.parametrize("code", [429, 500, 502, 503, 504])
def test_transient_retry_success_and_exhaustion(config, code):
    valid = {"task": controlled_result().task.model_dump()}
    requests = []
    with client_for([httpx.Response(code), completion(valid)], requests) as client:
        LiveModelClient(config, client).decompose(REQUEST)
    assert len(requests) == 2
    assert requests[0].content == requests[1].content
    requests.clear()
    with (
        client_for([httpx.Response(code), httpx.Response(code)], requests) as client,
        pytest.raises(LiveProviderError, match=f"HTTP {code}"),
    ):
        LiveModelClient(config, client).decompose(REQUEST)
    assert len(requests) == 2


@pytest.mark.parametrize(
    "sequence",
    [
        [httpx.Response(429), completion("bad")],
        [completion("bad"), httpx.Response(503)],
    ],
)
def test_shared_three_request_ceiling(config, sequence):
    valid = completion({"task": controlled_result().task.model_dump()})
    requests = []
    with client_for([*sequence, valid], requests) as client:
        LiveModelClient(config, client).decompose(REQUEST)
    assert len(requests) == 3


def test_http_retry_budget_is_not_reset_for_repair(config):
    requests = []
    with (
        client_for(
            [httpx.Response(429), completion("bad"), httpx.Response(503)], requests
        ) as client,
        pytest.raises(LiveProviderError, match="503"),
    ):
        LiveModelClient(config, client).decompose(REQUEST)
    assert len(requests) == 3


@pytest.mark.parametrize("code", [301, 400, 401, 403, 404, 501])
def test_nontransient_provider_error_is_not_retried(config, code):
    requests = []
    with (
        client_for([httpx.Response(code, text="private-token")], requests) as client,
        pytest.raises(LiveProviderError) as error,
    ):
        LiveModelClient(config, client).decompose(REQUEST)
    assert "private-token" not in str(error.value)
    assert len(requests) == 1


@pytest.mark.parametrize(
    "exception,kind",
    [
        (httpx.ReadTimeout("private-token"), LiveTimeoutError),
        (httpx.ConnectError("private-token"), LiveProviderError),
    ],
)
def test_transport_failure_is_not_retried_or_returned_as_research(
    config, exception, kind
):
    requests = []
    with (
        client_for([exception], requests) as client,
        pytest.raises(kind) as error,
    ):
        ResearchPlanningAgent(
            LiveModelClient(config, client), EvidenceSource(load_evidence())
        ).run(REQUEST)
    assert "private-token" not in str(error.value)
    assert len(requests) == 1


def test_refusal_is_not_repaired(config):
    requests = []
    response = completion(None, message={"refusal": "denied"})
    with (
        client_for([response], requests) as client,
        pytest.raises(LiveProviderError, match="refused"),
    ):
        LiveModelClient(config, client).decompose(REQUEST)
    assert len(requests) == 1


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
        "RESEARCH_PLANNING_AGENT_API_KEY=file-token\n"
        "RESEARCH_PLANNING_AGENT_MODEL=file-model\n"
        "RESEARCH_PLANNING_AGENT_BASE_URL=https://provider.invalid/v1/\n"
        "RESEARCH_PLANNING_AGENT_TIMEOUT_SECONDS=12\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("RESEARCH_PLANNING_AGENT_MODEL", "shell-model")
    config = LiveConfig.from_env()
    assert config.model == "shell-model"
    assert config.api_key.get_secret_value() == "file-token"
    assert config.base_url == "https://provider.invalid/v1"
    assert config.timeout == 12
    assert "file-token" not in config.model_dump_json()
    monkeypatch.setenv("RESEARCH_PLANNING_AGENT_API_KEY", "")
    with pytest.raises(ValueError, match="Invalid live configuration"):
        LiveConfig.from_env()


def test_live_cli_isolated_and_preserves_original_request(config, monkeypatch, capsys):
    expected = controlled_result()
    requests = []
    client = client_for(live_responses(expected), requests)
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
    original_request = f"  {REQUEST}  "
    assert main(["ask", original_request, "--json"]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["original_request"] == original_request
    assert result["task"]["request"] == REQUEST
    assert result["status"] == "completed"
    assert client.is_closed
    assert json.loads(requests[0].content)["messages"][1]["content"] == json.dumps(
        {"original_request": original_request}
    )
    for request in requests:
        assert not any(
            term in request.content
            for term in [
                b"RP-",
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
    assert main(["ask", REQUEST, "--json"]) == 1
    output = capsys.readouterr()
    assert not output.out
    assert "HTTP 401" in output.err
    assert "private-token" not in output.err
    assert client.is_closed


def test_controlled_mode_does_not_load_live_config(monkeypatch, capsys):
    def deny():
        raise AssertionError("Controlled mode must not load live configuration")

    monkeypatch.setattr(LiveConfig, "from_env", deny)
    monkeypatch.setenv("RESEARCH_PLANNING_AGENT_TIMEOUT_SECONDS", "invalid")
    assert main(["run", "RP-01", "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["status"] == "completed"
