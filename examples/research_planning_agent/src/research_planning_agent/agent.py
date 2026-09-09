from .model_client import assess, required_dependencies
from .models import FACTS, Collection, ResearchResult


class ResearchPlanningAgent:
    def __init__(self, model, evidence_source):
        self.model = model
        self.evidence_source = evidence_source

    def run(self, request: str) -> ResearchResult:
        task = self.model.decompose(request)
        plan = self.model.create_plan(task.model_copy(deep=True))
        result = ResearchResult(
            task=task,
            plan=plan,
            status="blocked",
            operations=["decompose_task", "create_plan", "check_plan"],
        )
        if plan.task != task:
            result.issues.append("task_drift")
        if {step.fact for step in plan.steps} != set(FACTS):
            result.issues.append("required_fact_omitted")
        if any(
            step.requires != required_dependencies(step.fact) for step in plan.steps
        ):
            result.issues.append("required_dependency_omitted")
        if result.issues:
            return result

        def collect(steps):
            for step in steps:
                result.operations.append(
                    f"resolve_dependencies:{step.fact}:{step.query}"
                )
                resolved = assess(task, result.evidence).selected
                if any(fact not in resolved for fact in step.requires):
                    attempted = {entry.step.fact for entry in result.collections}
                    if any(fact not in attempted for fact in step.requires):
                        result.issues.append(f"dependency_order:{step.fact}")
                        return False
                    result.operations.append(f"defer_evidence:{step.fact}:{step.query}")
                    continue
                prerequisites = {fact: resolved[fact] for fact in step.requires}
                items = self.evidence_source.collect(step, prerequisites)
                result.operations.append(f"collect_evidence:{step.fact}:{step.query}")
                result.collections.append(
                    Collection(
                        step=step.model_copy(deep=True),
                        prerequisites=prerequisites,
                        evidence_ids=[item.evidence_id for item in items],
                    )
                )
                known = {item.evidence_id: item for item in result.evidence}
                for item in items:
                    if item.evidence_id in known and known[item.evidence_id] != item:
                        raise ValueError(
                            "Evidence changed under an existing evidence_id"
                        )
                    known[item.evidence_id] = item
                result.evidence = list(known.values())
            return True

        def assessment(invocation):
            value = self.model.assess_evidence(
                task, result.evidence, invocation=invocation
            )
            result.assessments.append(value)
            result.operations.append(f"assess_evidence:{invocation}")
            return value

        if not collect(plan.steps):
            return result
        current = assessment(1)
        gaps = set(current.missing) | set(current.conflicts)
        if gaps:
            revision = self.model.revise_plan(task.model_copy(deep=True), current)
            result.revision = revision
            result.operations.extend(["revise_plan", "check_revision"])
            if revision.plan.task != task:
                result.issues.append("task_drift")
            elif not revision.plan.steps:
                result.issues.append("revision_no_progress")
            elif {step.fact for step in revision.plan.steps} != gaps or any(
                step.query != "followup"
                or step.requires != required_dependencies(step.fact)
                for step in revision.plan.steps
            ):
                result.issues.append("invalid_revision")
            if result.issues or not collect(revision.plan.steps):
                return result
            current = assessment(2)
        result.draft = self.model.synthesize_report(task, current, result.evidence)
        result.operations.append("synthesize_report")
        result.issues = self.model.validate_support(task, result.draft, result.evidence)
        result.operations.append("validate_support")
        if not result.issues:
            result.status = "incomplete" if result.draft.unresolved else "completed"
        result.operations.append("final_result")
        return result
