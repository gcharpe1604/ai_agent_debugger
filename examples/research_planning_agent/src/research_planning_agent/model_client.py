import re

from .models import (
    FACTS,
    Claim,
    EvidenceAssessment,
    Plan,
    PlanRevision,
    PlanStep,
    Report,
    ResearchTask,
)


def required_dependencies(fact):
    return [fact.replace(".permit", ".access")] if fact.endswith(".permit") else []


def assess(task, evidence):
    selected, conflicts, missing = {}, {}, []
    current = [
        item
        for item in evidence
        if item.status == "current" and item.published_on <= task.as_of
    ]
    superseded = {old for item in current for old in item.supersedes}
    stale = sorted(
        {
            item.evidence_id
            for item in evidence
            if item.status == "superseded" or item.evidence_id in superseded
        }
    )
    for fact in FACTS:
        matching = sorted(
            [
                item
                for item in current
                if item.fact == fact and item.evidence_id not in superseded
            ],
            key=lambda item: item.evidence_id,
        )
        ids = [item.evidence_id for item in matching]
        if not matching:
            missing.append(fact)
        elif len({item.value for item in matching}) > 1:
            conflicts[fact] = ids
        else:
            selected[fact] = ids
    return EvidenceAssessment(
        selected=selected, missing=missing, conflicts=conflicts, stale=stale
    )


def report_from(task, assessment, evidence):
    by_id = {item.evidence_id: item for item in evidence}
    claims = [
        Claim(fact=fact, value=by_id[ids[0]].value, evidence_ids=ids)
        for fact, ids in assessment.selected.items()
    ]
    unresolved = [fact for fact in FACTS if fact not in assessment.selected]
    values = {claim.fact: claim.value for claim in claims}
    eligible = []
    if not unresolved:
        for site in ("ridge", "vale"):
            if (
                values[f"{site}.capacity"] >= task.people
                and values[f"{site}.power"] >= task.power_kw
                and values[f"{site}.cost"] <= task.budget
                and values[f"{site}.access"] == "open"
                and values[f"{site}.permit"] == "approved"
            ):
                eligible.append(site)
    recommendation = (
        min(eligible, key=lambda site: (values[f"{site}.cost"], site))
        if eligible
        else None
    )
    return Report(recommendation=recommendation, claims=claims, unresolved=unresolved)


class ModelClient:
    """Deterministic fake model. Every method is an explicit replacement boundary."""

    def decompose(self, request):
        match = re.fullmatch(
            r"Recommend the cheapest eligible field station between Ridge and Vale for (\d+) people, "
            r"requiring (\d+) kW, a daily budget of (\d+) credits, open access and an approved permit "
            r"as of (\d{4}-\d{2}-\d{2})\.",
            request,
        )
        if match is None:
            raise ValueError(
                "Unsupported request; use the documented field-station template"
            )
        people, power, budget, as_of = match.groups()
        return ResearchTask(
            request=request,
            people=int(people),
            power_kw=int(power),
            budget=int(budget),
            as_of=as_of,
        )

    def create_plan(self, task):
        return Plan(
            task=task.model_copy(deep=True),
            steps=[
                PlanStep(fact=fact, requires=required_dependencies(fact))
                for fact in FACTS
            ],
        )

    def assess_evidence(self, task, evidence, *, invocation):
        return assess(task, evidence)

    def revise_plan(self, task, assessment):
        gaps = set(assessment.missing) | set(assessment.conflicts)
        return PlanRevision(
            plan=Plan(
                task=task.model_copy(deep=True),
                steps=[
                    PlanStep(
                        fact=fact,
                        requires=required_dependencies(fact),
                        query="followup",
                    )
                    for fact in FACTS
                    if fact in gaps
                ],
            ),
            reason="Resolve missing or conflicting facts using follow-up records",
        )

    def synthesize_report(self, task, assessment, evidence):
        return report_from(task, assessment, evidence)

    def validate_support(self, task, report, evidence):
        # Recompute from source evidence; never trust a prior model assessment.
        actual = assess(task, evidence)
        expected = report_from(task, actual, evidence)
        by_id = {item.evidence_id: item for item in evidence}
        issues = []
        seen = set()
        for claim in report.claims:
            if claim.fact in seen:
                issues.append(f"duplicate_claim:{claim.fact}")
            seen.add(claim.fact)
            allowed = actual.selected.get(claim.fact, [])
            for evidence_id in claim.evidence_ids:
                item = by_id.get(evidence_id)
                if (
                    item is None
                    or evidence_id not in allowed
                    or item.value != claim.value
                ):
                    issues.append(f"unsupported_claim:{claim.fact}:{evidence_id}")
        for fact in actual.selected:
            if fact not in seen:
                issues.append(f"ignored_evidence:{fact}")
        if set(report.unresolved) != set(expected.unresolved):
            issues.append("unresolved_facts_mismatch")
        if report.recommendation != expected.recommendation:
            issues.append("recommendation_mismatch")
        return issues
