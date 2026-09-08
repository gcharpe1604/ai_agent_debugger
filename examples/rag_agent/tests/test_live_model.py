import asyncio
import json
from pathlib import Path

import httpx
import pytest
from pydantic import SecretStr, ValidationError

import rag_agent.live_model as live_model_module
from rag_agent.agent import RAGAgent
from rag_agent.cli import main
from rag_agent.live_model import (
    LiveConfig,
    LiveModelClient,
    LiveOutputError,
    LiveProviderError,
    LiveTimeoutError,
)
from rag_agent.models import (
    EvidenceAssessment,
    QuestionClassification,
    RetrievalQuery,
)
from rag_agent.retrieval import LocalRetriever

QUESTION = "How long can I restore a deleted NovaCloud workspace?"
CLASSIFICATION = {
    "topics": ["workspace_deletion"],
    "required_facts": ["restore_period"],
}
SUFFICIENT = {
    "sufficient": True,
    "supported_facts": ["restore_period"],
    "missing_facts": [],
}
ANSWER = {
    "status": "answered",
    "answer": "You have 14 days.",
    "supporting_document_ids": ["KB-01"],
}


@pytest.fixture(autouse=True)
def offline(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    for name in ["API_KEY", "MODEL", "BASE_URL", "TIMEOUT_SECONDS"]:
        monkeypatch.delenv("RAG_AGENT_" + name, raising=False)

    async def deny_network(*args, **kwargs):
        raise AssertionError("Live tests must use MockTransport")

    monkeypatch.setattr(httpx.AsyncHTTPTransport, "handle_async_request", deny_network)


@pytest.fixture
def config():
    return LiveConfig(
        api_key=SecretStr("test-key"),
        model="test-model",
        base_url="https://provider.invalid/v1",
    )


def completion(output, **choice_updates):
    return httpx.Response(
        200,
        json={
            "choices": [
                {
                    "message": {
                        "content": output
                        if isinstance(output, str)
                        else json.dumps(output)
                    },
                    "finish_reason": "stop",
                    **choice_updates,
                }
            ]
        },
    )


def scripted(responses, requests):
    pending = iter(responses)

    def handle(request):
        requests.append(request)
        response = next(pending)
        if isinstance(response, Exception):
            raise response
        return response

    return httpx.MockTransport(handle)


def run_model(config, responses, call):
    requests = []

    async def run():
        async with httpx.AsyncClient(transport=scripted(responses, requests)) as client:
            return await call(LiveModelClient(config, client))

    return asyncio.run(run()), requests


def test_live_workspace_uses_http_stages_and_real_retrieval(kb, config):
    result, requests = run_model(
        config,
        [
            completion(CLASSIFICATION),
            completion({"query": "deleted workspace restore deletion policy"}),
            completion(SUFFICIENT),
            completion(ANSWER),
        ],
        lambda model: RAGAgent(model, LocalRetriever(kb)).run(QUESTION),
    )
    assert result.answer == "You have 14 days." and result.status == "answered"
    assert len(result.context.retrieval_attempts) == 1
    assert result.supporting_document_ids == ["KB-01"]
    stages = [
        "classify_question",
        "formulate_query",
        "assess_evidence",
        "generate_answer",
    ]
    for request, stage in zip(requests, stages, strict=True):
        body = json.loads(request.content)
        assert request.method == "POST"
        assert str(request.url) == "https://provider.invalid/v1/chat/completions"
        assert request.headers["authorization"] == "Bearer test-key"
        assert request.extensions["timeout"]["read"] == 30.0
        assert body["model"] == "test-model"
        assert body["response_format"] == {"type": "json_object"}
        system = body["messages"][0]["content"]
        assert f"Stage: {stage}." in system
        assert "only supplied NovaCloud KB" in system
        assert "without reasoning" in system
        assert "JSON schema:" in system
        assert "scenario_id" not in request.content.decode()
    documents = json.loads(json.loads(requests[2].content)["messages"][1]["content"])[
        "documents"
    ]
    assert {d["document_id"] for d in documents} == {"KB-01", "KB-03", "KB-04"}
    assert all(
        {"document_id", "title", "status", "version", "content"} <= d.keys()
        for d in documents
    )
    assert (
        next(d for d in documents if d["document_id"] == "KB-01")["content"]
        == kb.get("KB-01").content
    )


def test_live_retry_accumulates_evidence_without_scenarios(kb, config):
    result, requests = run_model(
        config,
        [
            completion(
                {
                    "topics": ["plans", "export"],
                    "required_facts": ["downgrade", "export_validity"],
                }
            ),
            completion({"query": "Pro downgrade to Starter plan"}),
            completion(
                {
                    "sufficient": False,
                    "supported_facts": ["downgrade"],
                    "missing_facts": ["export_validity"],
                }
            ),
            completion({"query": "workspace export download link validity"}),
            completion(
                {
                    "sufficient": True,
                    "supported_facts": ["downgrade", "export_validity"],
                    "missing_facts": [],
                }
            ),
            completion(
                {
                    "status": "answered",
                    "answer": "Next billing renewal; 48 hours.",
                    "supporting_document_ids": ["KB-05", "KB-04"],
                }
            ),
        ],
        lambda model: RAGAgent(model, LocalRetriever(kb)).run(
            "When does my downgrade take effect and how long does an export link last?"
        ),
    )
    first, second = result.context.retrieval_attempts
    assert not first.assessment.sufficient and second.assessment.sufficient
    contexts = [
        json.loads(json.loads(request.content)["messages"][1]["content"])
        for request in requests
    ]
    assert contexts[3]["assessment"]["missing_facts"] == ["export_validity"]
    assert contexts[3]["previous_query"] == {"query": "Pro downgrade to Starter plan"}
    assert {"KB-05", "KB-04"} <= {d["document_id"] for d in contexts[4]["documents"]}
    assert contexts[5]["documents"] == contexts[4]["documents"]
    assert len(requests) == 6
    assert result.answer == "Next billing renewal; 48 hours."


@pytest.mark.parametrize("stage", ["formulate_query", "refine_query"])
@pytest.mark.parametrize(
    "question, fact, query, document_id",
    [
        (
            "When does a downgrade from Pro to Starter take effect?",
            "downgrade_time",
            "plan downgrade take effect",
            "KB-05",
        ),
        (
            "How long can I restore a deleted workspace?",
            "restore_period",
            "deleted workspace restore deletion policy",
            "KB-01",
        ),
        (
            "What is the Pro plan API rate limit?",
            "api_limit",
            "Pro API rate limit requests minute",
            "KB-10",
        ),
    ],
)
def test_query_stages_explain_lexical_retrieval_without_fixing_output(
    kb, config, stage, question, fact, query, document_id
):
    classification = QuestionClassification(topics=["support"], required_facts=[fact])
    assessment = EvidenceAssessment(
        sufficient=False, supported_facts=[], missing_facts=[fact]
    )
    previous_query = RetrievalQuery(query="earlier weak lexical query")

    async def call(model):
        if stage == "formulate_query":
            return await model.formulate_query(question, classification)
        return await model.refine_query(
            question, classification, assessment, previous_query
        )

    result, requests = run_model(config, [completion({"query": query})], call)
    assert (
        result.query == query
    )  # Provider output passes through, without a fixed query map.
    messages = json.loads(requests[0].content)["messages"]
    instruction = messages[0]["content"]
    for guidance in ["lexical BM25", "not semantic vector search", "concise keywords"]:
        assert guidance in instruction
    assert question not in instruction and document_id not in instruction
    assert query not in instruction
    for forbidden in [
        "When does a downgrade from Pro to Starter take effect?",
        "KB-05",
        "take effect",
    ]:
        assert forbidden not in instruction
    assert json.loads(messages[1]["content"])["question"] == question
    if stage == "refine_query":
        assert "not merely the order of the same terms" in instruction
        context = json.loads(messages[1]["content"])
        assert context["assessment"]["missing_facts"] == [fact]
        assert context["previous_query"] == previous_query.model_dump()
    retrieved = asyncio.run(LocalRetriever(kb).search(result.query))
    assert document_id in [item.document.document_id for item in retrieved]


def test_mocked_downgrade_refinement_recovers_with_unchanged_bm25(kb, config):
    result, requests = run_model(
        config,
        [
            completion(
                {"topics": ["plan_changes"], "required_facts": ["downgrade_time"]}
            ),
            completion(
                {"query": "downgrade from Pro to Starter effective date timing"}
            ),
            completion(
                {
                    "sufficient": False,
                    "supported_facts": [],
                    "missing_facts": ["downgrade_time"],
                }
            ),
            completion({"query": "plan downgrade take effect"}),
            completion(
                {
                    "sufficient": True,
                    "supported_facts": ["downgrade_time"],
                    "missing_facts": [],
                }
            ),
            completion(
                {
                    "status": "answered",
                    "answer": "The downgrade takes effect at the next billing renewal.",
                    "supporting_document_ids": ["KB-05"],
                }
            ),
        ],
        lambda model: RAGAgent(model, LocalRetriever(kb)).run(
            "When does a downgrade from Pro to Starter take effect?"
        ),
    )
    first, second = result.context.retrieval_attempts
    assert "KB-05" not in {item.document.document_id for item in first.results}
    assert not first.assessment.sufficient
    assert "KB-05" in [item.document.document_id for item in second.results]
    assert second.assessment.sufficient
    assert result.status == "answered" and "next billing renewal" in result.answer
    assert result.supporting_document_ids == ["KB-05"]
    assert len(requests) == 6


@pytest.mark.parametrize("generation_status", ["answered", "insufficient_evidence"])
def test_insufficient_evidence_always_abstains_after_real_generation_call(
    kb, config, generation_status
):
    missing = {
        "sufficient": False,
        "supported_facts": [],
        "missing_facts": ["residency"],
    }
    result, requests = run_model(
        config,
        [
            completion({"topics": ["residency"], "required_facts": ["residency"]}),
            completion({"query": "NovaCloud data residency storage region India"}),
            completion(missing),
            completion(
                {"query": "NovaCloud official data hosting location residency policy"}
            ),
            completion(missing),
            completion(
                {
                    "status": generation_status,
                    "answer": "All data stays in India.",
                    "supporting_document_ids": [],
                }
            ),
        ],
        lambda model: RAGAgent(model, LocalRetriever(kb)).run(
            "Is all customer data stored in India?"
        ),
    )
    assert len(result.context.retrieval_attempts) == 2 and len(requests) == 6
    assert not result.context.retrieval_attempts[-1].assessment.sufficient
    assert (
        "Stage: generate_answer."
        in json.loads(requests[-1].content)["messages"][0]["content"]
    )
    assert result.status == "insufficient_evidence"
    assert result.supporting_document_ids == []
    assert "India" not in result.answer


@pytest.mark.parametrize(
    "bad_response",
    [
        completion("not JSON"),
        completion({"topics": ["workspace"]}),
        completion({**CLASSIFICATION, "reasoning": "unrequested"}),
        completion({"topics": "workspace", "required_facts": ["restore_period"]}),
        completion(CLASSIFICATION, finish_reason="length"),
        httpx.Response(200, json={"choices": []}),
        httpx.Response(200, content=b"not JSON"),
    ],
)
def test_one_structured_repair_can_recover(config, bad_response):
    result, requests = run_model(
        config,
        [bad_response, completion(CLASSIFICATION)],
        lambda model: model.classify_question(QUESTION),
    )
    assert result == QuestionClassification.model_validate(CLASSIFICATION)
    assert len(requests) == 2
    assert "corrected" in json.loads(requests[1].content)["messages"][-1]["content"]


def test_invalid_output_stops_after_one_repair(config):
    requests = []

    async def run():
        async with httpx.AsyncClient(
            transport=scripted([completion("bad")] * 3, requests)
        ) as client:
            with pytest.raises(
                LiveOutputError, match="classify_question after one repair"
            ):
                await LiveModelClient(config, client).classify_question(QUESTION)

    asyncio.run(run())
    assert len(requests) == 2


@pytest.mark.parametrize(
    "assessment",
    [
        {
            "sufficient": "true",
            "supported_facts": ["restore_period"],
            "missing_facts": [],
        },
        {
            "sufficient": True,
            "supported_facts": [],
            "missing_facts": ["restore_period"],
        },
        {"sufficient": True, "supported_facts": [], "missing_facts": []},
        {"sufficient": True, "supported_facts": ["invented_fact"], "missing_facts": []},
        {
            "sufficient": False,
            "supported_facts": ["restore_period"],
            "missing_facts": ["restore_period"],
        },
        {
            "sufficient": True,
            "supported_facts": ["restore_period", "restore_period"],
            "missing_facts": [],
        },
    ],
)
def test_inconsistent_evidence_is_an_output_error(kb, config, assessment):
    with pytest.raises(LiveOutputError, match="assess_evidence"):
        run_model(
            config,
            [completion(assessment)] * 2,
            lambda model: model.assess_evidence(
                QUESTION,
                QuestionClassification.model_validate(CLASSIFICATION),
                [kb.get("KB-01")],
            ),
        )


def test_no_documents_cannot_support_a_fact(config):
    with pytest.raises(LiveOutputError, match="assess_evidence"):
        run_model(
            config,
            [completion(SUFFICIENT)] * 2,
            lambda model: model.assess_evidence(
                QUESTION, QuestionClassification.model_validate(CLASSIFICATION), []
            ),
        )


@pytest.mark.parametrize("source_ids", [["KB-99"], ["KB-02"], []])
def test_answers_require_supplied_citations(kb, config, source_ids):
    with pytest.raises(LiveOutputError, match="generate_answer"):
        run_model(
            config,
            [completion({**ANSWER, "supporting_document_ids": source_ids})] * 2,
            lambda model: model.generate_answer(
                QUESTION,
                QuestionClassification.model_validate(CLASSIFICATION),
                [kb.get("KB-01")],
                EvidenceAssessment.model_validate(SUFFICIENT),
            ),
        )


@pytest.mark.parametrize("status_code", [429, 500, 502, 503, 504])
def test_transient_http_status_retries_once_then_succeeds(
    config, monkeypatch, status_code
):
    delays = []

    async def no_sleep(delay):
        delays.append(delay)

    monkeypatch.setattr(live_model_module.asyncio, "sleep", no_sleep)
    result, requests = run_model(
        config,
        [httpx.Response(status_code), completion(CLASSIFICATION)],
        lambda model: model.classify_question(QUESTION),
    )
    assert result == QuestionClassification.model_validate(CLASSIFICATION)
    assert len(requests) == 2
    assert delays == [0.25]


def test_repeated_transient_failure_stops_after_one_retry(kb, config, monkeypatch):
    delays = []

    async def no_sleep(delay):
        delays.append(delay)

    monkeypatch.setattr(live_model_module.asyncio, "sleep", no_sleep)
    requests = []

    async def run():
        async with httpx.AsyncClient(
            transport=scripted([httpx.Response(503)] * 3, requests)
        ) as client:
            with pytest.raises(LiveProviderError, match="HTTP 503"):
                await RAGAgent(LiveModelClient(config, client), LocalRetriever(kb)).run(
                    QUESTION
                )

    asyncio.run(run())
    assert len(requests) == 2
    assert delays == [0.25]


def test_transient_retry_and_structured_repair_are_independently_bounded(
    config, monkeypatch
):
    delays = []

    async def no_sleep(delay):
        delays.append(delay)

    monkeypatch.setattr(live_model_module.asyncio, "sleep", no_sleep)
    result, requests = run_model(
        config,
        [completion("not JSON"), httpx.Response(503), completion(CLASSIFICATION)],
        lambda model: model.classify_question(QUESTION),
    )
    assert result == QuestionClassification.model_validate(CLASSIFICATION)
    assert len(requests) == 3
    assert delays == [0.25]
    assert "corrected" in json.loads(requests[-1].content)["messages"][-1]["content"]


@pytest.mark.parametrize(
    "failure, error, message",
    [
        (
            httpx.Response(401, text="secret provider detail"),
            LiveProviderError,
            "HTTP 401",
        ),
        (
            httpx.Response(302, headers={"Location": "https://other.invalid"}),
            LiveProviderError,
            "HTTP 302",
        ),
        (
            httpx.ConnectError("secret network detail"),
            LiveProviderError,
            "Network error",
        ),
        (httpx.ReadTimeout("secret timeout detail"), LiveTimeoutError, "Timeout"),
        (
            completion({}, message={"refusal": "No", "content": None}),
            LiveProviderError,
            "refused",
        ),
        (completion({}, finish_reason="content_filter"), LiveProviderError, "refused"),
    ],
)
def test_nontransient_provider_failures_are_not_retried_or_abstentions(
    config, failure, error, message
):
    requests = []

    async def run():
        async with httpx.AsyncClient(
            transport=scripted([failure], requests), follow_redirects=True
        ) as client:
            with pytest.raises(error, match=message) as caught:
                await LiveModelClient(config, client).classify_question(QUESTION)
            assert "secret" not in str(caught.value)

    asyncio.run(run())
    assert len(requests) == 1


def test_request_deadline_bounds_even_a_stalled_transport(config):
    cancelled = []

    async def stalled(request):
        try:
            await asyncio.Event().wait()
        finally:
            cancelled.append(True)

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(stalled)) as client:
            short = config.model_copy(update={"timeout": 0.01})
            with pytest.raises(LiveTimeoutError):
                await LiveModelClient(short, client).classify_question(QUESTION)

    asyncio.run(run())
    assert cancelled == [True]


@pytest.mark.parametrize(
    "name, value",
    [
        ("API_KEY", ""),
        ("API_KEY", "bad\nkey"),
        ("MODEL", " "),
        ("BASE_URL", "not-a-url"),
        ("BASE_URL", "https://name:password@host.invalid/v1"),
        ("BASE_URL", "https://host.invalid/v1?key=secret"),
        ("BASE_URL", "http://host.invalid/v1"),
        ("TIMEOUT_SECONDS", "0"),
        ("TIMEOUT_SECONDS", "-1"),
        ("TIMEOUT_SECONDS", "nan"),
        ("TIMEOUT_SECONDS", "inf"),
        ("TIMEOUT_SECONDS", "121"),
        ("TIMEOUT_SECONDS", "bad"),
    ],
)
def test_invalid_environment_is_rejected_without_exposing_values(
    monkeypatch, name, value
):
    monkeypatch.setenv("RAG_AGENT_API_KEY", "secret-key")
    monkeypatch.setenv("RAG_AGENT_MODEL", "test-model")
    monkeypatch.setenv("RAG_AGENT_" + name, value)
    with pytest.raises(ValueError, match="Invalid live configuration") as caught:
        LiveConfig.from_env()
    assert "secret-key" not in str(caught.value)


def test_environment_defaults_and_overrides(monkeypatch):
    with pytest.raises(ValueError, match="RAG_AGENT_API_KEY"):
        LiveConfig.from_env()
    monkeypatch.setenv("RAG_AGENT_API_KEY", "test-key")
    monkeypatch.setenv("RAG_AGENT_MODEL", "test-model")
    default = LiveConfig.from_env()
    assert default.base_url == "https://api.openai.com/v1" and default.timeout == 30
    assert "test-key" not in repr(default)
    monkeypatch.setenv("RAG_AGENT_BASE_URL", "http://127.0.0.1:8000/v1/")
    monkeypatch.setenv("RAG_AGENT_TIMEOUT_SECONDS", "5.5")
    config = LiveConfig.from_env()
    assert config.base_url == "http://127.0.0.1:8000/v1" and config.timeout == 5.5
    with pytest.raises(ValidationError):
        LiveConfig(api_key=SecretStr("key"), model="model", unexpected=True)


def test_environment_loads_dotenv_without_overriding_shell(monkeypatch, tmp_path):
    (tmp_path / ".env").write_text(
        "RAG_AGENT_API_KEY=dotenv-key\n"
        "RAG_AGENT_MODEL=dotenv-model\n"
        "RAG_AGENT_BASE_URL=https://dotenv.invalid/v1\n"
        "RAG_AGENT_TIMEOUT_SECONDS=12.5\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("RAG_AGENT_MODEL", "shell-model")

    config = LiveConfig.from_env()

    assert config.api_key.get_secret_value() == "dotenv-key"
    assert config.model == "shell-model"
    assert config.base_url == "https://dotenv.invalid/v1"
    assert config.timeout == 12.5


@pytest.mark.parametrize("as_json", [False, True])
def test_ask_cli_uses_only_live_dependencies(monkeypatch, capsys, as_json):
    monkeypatch.setenv("RAG_AGENT_API_KEY", "test-key")
    monkeypatch.setenv("RAG_AGENT_MODEL", "test-model")
    requests = []
    transport = scripted(
        [
            completion(CLASSIFICATION),
            completion({"query": "deleted workspace restore deletion policy"}),
            completion(SUFFICIENT),
            completion(ANSWER),
        ],
        requests,
    )
    original_client = httpx.AsyncClient
    clients = []

    def mock_client():
        client = original_client(transport=transport)
        clients.append(client)
        return client

    monkeypatch.setattr(httpx, "AsyncClient", mock_client)
    original_open = Path.open

    def guarded_open(path, *args, **kwargs):
        assert "scenarios" not in path.parts and "ground_truth" not in path.parts
        return original_open(path, *args, **kwargs)

    monkeypatch.setattr(Path, "open", guarded_open)
    import rag_agent.factory
    import rag_agent.scenarios

    def deny_controlled(*args, **kwargs):
        raise AssertionError("ask must not use controlled runtime dependencies")

    monkeypatch.setattr(rag_agent.factory, "build_agent", deny_controlled)
    monkeypatch.setattr(rag_agent.scenarios, "load_scenario", deny_controlled)
    assert main(["ask", QUESTION] + (["--json"] if as_json else [])) == 0
    output = capsys.readouterr()
    assert not output.err and len(requests) == 4
    assert clients[0].is_closed
    if as_json:
        assert json.loads(output.out)["answer"] == "You have 14 days."
    else:
        assert "Mode: live" in output.out and "Scenario:" not in output.out
        assert "KB-01" in output.out and "Status: answered" in output.out


def test_ask_missing_config_is_nonzero_and_offline(capsys):
    assert main(["ask", QUESTION]) == 1
    captured = capsys.readouterr()
    assert "RAG_AGENT_API_KEY" in captured.err and not captured.out


@pytest.mark.parametrize(
    "error",
    [
        LiveProviderError("Provider error"),
        LiveTimeoutError("Timeout"),
        LiveOutputError("Structured output error"),
    ],
)
def test_ask_errors_are_nonzero(monkeypatch, capsys, error):
    import rag_agent.cli

    async def fail(question):
        raise error

    monkeypatch.setattr(rag_agent.cli, "_ask", fail)
    assert main(["ask", QUESTION]) == 1
    captured = capsys.readouterr()
    assert str(error) in captured.err and not captured.out
