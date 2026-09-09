from concurrent.futures import ThreadPoolExecutor

import pytest

from research_planning_agent.agent import ResearchPlanningAgent
from research_planning_agent.evidence import EvidenceSource, load_evidence
from research_planning_agent.model_client import ModelClient, assess
from research_planning_agent.models import FACTS, Claim
from research_planning_agent.scenarios import build_agent, load_scenario


def run(number=1):
    config = load_scenario(f"RP-{number:02}")
    return build_agent(config).run(config.request)


def test_healthy_workflow_and_actual_support():
    result = run()
    assert result.status == "completed"
    assert result.draft.recommendation == "vale"
    assert len(result.collections) == 11
    assert list(result.assessments[0].conflicts) == ["vale.permit"]
    assert not result.assessments[1].conflicts
    assert result.assessments[1].selected["vale.permit"] == ["VALE-PERMIT-3"]
    assert result.revision.plan.task == result.task
    assert [(s.fact, s.query) for s in result.revision.plan.steps] == [
        ("vale.permit", "followup")
    ]
    assert result.operations[-3:] == [
        "synthesize_report",
        "validate_support",
        "final_result",
    ]
    by_id = {item.evidence_id: item for item in result.evidence}
    assert {claim.fact for claim in result.draft.claims} == set(FACTS)
    for claim in result.draft.claims:
        assert all(
            by_id[eid].value == claim.value and by_id[eid].fact == claim.fact
            for eid in claim.evidence_ids
        )
    for collection in result.collections:
        assert set(collection.prerequisites) == set(collection.step.requires)
        for fact, ids in collection.prerequisites.items():
            assert all(by_id[eid].fact == fact for eid in ids)


def test_missing_evidence_is_correct_incomplete_after_followup():
    result = run(2)
    assert result.status == "incomplete"
    assert result.issues == []
    assert result.draft.recommendation is None
    assert result.draft.unresolved == ["vale.permit"]
    assert [a.missing for a in result.assessments] == [["vale.permit"], ["vale.permit"]]
    assert result.collections[-1].evidence_ids == []


def test_currentness_conflicts_and_partial_relevance():
    result = run()
    first, final = result.assessments
    assert first.selected["ridge.capacity"] == ["RIDGE-CAPACITY-2"]
    assert "RIDGE-CAPACITY-1" in first.stale
    assert "RIDGE-VISITORS-1" in [item.evidence_id for item in result.evidence]
    assert all("RIDGE-VISITORS-1" not in ids for ids in first.selected.values())
    assert first.conflicts["vale.permit"] == ["VALE-PERMIT-1", "VALE-PERMIT-2"]
    assert {"VALE-PERMIT-1", "VALE-PERMIT-2"} <= set(final.stale)


def test_future_resolution_cannot_resolve_present_conflict():
    result = run()
    task = result.task.model_copy(update={"as_of": "2026-05-19"})
    assessment = assess(task, result.evidence)
    assert "vale.permit" in assessment.conflicts
    assert "VALE-PERMIT-3" not in str(assessment.selected)


def test_wrong_order_stops_before_dependent_source_call():
    result = run(6)
    assert len(result.collections) == 8
    assert result.issues == ["dependency_order:vale.permit"]
    assert result.operations[-1] == "resolve_dependencies:vale.permit:initial"
    assert not any(c.step.fact == "vale.permit" for c in result.collections)


def test_source_enforces_evidence_prerequisite_itself():
    result = run()
    source = EvidenceSource(load_evidence())
    with pytest.raises(ValueError, match="requires resolved access"):
        source.collect(result.plan.steps[-1], {})


@pytest.mark.parametrize(
    "number,issue", [(7, "task_drift"), (8, "revision_no_progress")]
)
def test_rejected_revision_keeps_original_task_and_conflict(number, issue):
    result = run(number)
    assert result.task.people == result.plan.task.people == 40
    assert result.issues == [issue]
    assert result.assessments[-1].conflicts
    assert result.draft is None
    assert result.revision is not None
    assert len(result.collections) == 10


@pytest.mark.parametrize(
    "number,expected_issue",
    [
        (3, "unsupported_claim:ridge.capacity:RIDGE-CAPACITY-1"),
        (4, "unresolved_facts_mismatch"),
        (9, "unsupported_claim:vale.power:VALE-POWER-1"),
        (10, "ignored_evidence:ridge.capacity"),
    ],
)
def test_faulty_drafts_survive_prepared_validation(number, expected_issue):
    result = run(number)
    assert result.status == "completed"
    assert result.draft is not None
    assert result.issues == []
    assert "validate_support" in result.operations
    assert expected_issue in ModelClient().validate_support(
        result.task, result.draft, result.evidence
    )


def test_stale_selection_reaches_both_assessments():
    result = run(3)
    assert all(
        a.selected["ridge.capacity"] == ["RIDGE-CAPACITY-1"] for a in result.assessments
    )
    assert len(result.assessments) == 2
    assert result.draft.recommendation == "ridge"


def test_suppressed_conflict_skips_revision_and_reaches_terminal_report():
    result = run(4)
    assert not result.assessments[0].conflicts
    assert result.revision is None
    assert "vale.permit" in assess(result.task, result.evidence).conflicts
    assert "unresolved_facts_mismatch" in ModelClient().validate_support(
        result.task, result.draft, result.evidence
    )


def test_ignored_evidence_is_actually_collected():
    result = run(10)
    assert any(
        item.evidence_id == "RIDGE-CAPACITY-2" and item.value == 30
        for item in result.evidence
    )
    assert not any(claim.fact == "ridge.capacity" for claim in result.draft.claims)
    assert "ignored_evidence:ridge.capacity" in ModelClient().validate_support(
        result.task, result.draft, result.evidence
    )


def test_validation_rejects_unknown_wrong_fact_duplicate_and_omitted_citations():
    result = run()
    report = result.draft.model_copy(deep=True)
    report.claims[0].evidence_ids = ["UNKNOWN"]
    report.claims[1].evidence_ids = ["RIDGE-COST-1"]
    report.claims.append(
        Claim(fact="vale.power", value=12, evidence_ids=["VALE-POWER-1"])
    )
    report.claims = [c for c in report.claims if c.fact != "vale.access"]
    issues = ModelClient().validate_support(result.task, report, result.evidence)
    assert "unsupported_claim:ridge.capacity:UNKNOWN" in issues
    assert "unsupported_claim:ridge.power:RIDGE-COST-1" in issues
    assert "duplicate_claim:vale.power" in issues
    assert "ignored_evidence:vale.access" in issues


def test_plain_model_and_source_work_without_scenario_loader():
    request = load_scenario("RP-01").request
    agent = ResearchPlanningAgent(ModelClient(), EvidenceSource(load_evidence()))
    assert agent.run(request) == run()
    assert (
        agent.run(request.replace("40 people", "20 people")).draft.recommendation
        == "ridge"
    )
    no_site = agent.run(request.replace("40 people", "100 people"))
    assert no_site.status == "completed" and no_site.draft.recommendation is None


def test_empty_corpus_abstains_without_synthesizing_missing_dependencies():
    agent = ResearchPlanningAgent(ModelClient(), EvidenceSource([]))
    result = agent.run(load_scenario("RP-01").request)
    assert result.status == "incomplete"
    assert result.draft.recommendation is None
    assert set(result.draft.unresolved) == set(FACTS)
    assert result.issues == []
    assert "defer_evidence:ridge.permit:initial" in result.operations


@pytest.mark.parametrize("number", range(1, 11))
def test_reused_concurrent_agent_and_config_mutation_are_isolated(number):
    config = load_scenario(f"RP-{number:02}")
    agent = build_agent(config)
    original = agent.run(config.request).model_dump_json()
    config.excluded_evidence.append("RIDGE-CAPACITY-2")
    with ThreadPoolExecutor(max_workers=2) as pool:
        outputs = list(
            pool.map(lambda _: agent.run(config.request).model_dump_json(), range(2))
        )
    assert outputs == [original, original]
    changed = agent.run(config.request)
    changed.plan.steps.clear()
    changed.evidence.clear()
    assert agent.run(config.request).model_dump_json() == original
