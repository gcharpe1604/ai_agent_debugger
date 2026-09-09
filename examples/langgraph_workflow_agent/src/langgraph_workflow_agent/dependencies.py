from .models import (
    MAX_RETRIES,
    ActionResult,
    Context,
    GraphState,
    Request,
    Response,
)


class LocalDependencies:
    """Pure deterministic decisions and simulated operations; no shared run state."""

    def classify(self, request: Request):
        return request.incident

    def gather(self, request: Request, *, attempt: int):
        availability = "ready"
        if request.telemetry == "denied":
            availability = "terminal"
        elif request.telemetry == "unavailable" or (
            request.telemetry == "delayed" and attempt == 1
        ):
            availability = "retryable"
        return Context(
            revision=attempt,
            availability=availability,
            incident=request.incident,
        )

    def decide(self, state: GraphState):
        context = state["context"]
        if context is None or context.availability == "terminal":
            return "abort", None
        if context.availability == "retryable":
            return (
                "retry_context" if state["retry_count"] < MAX_RETRIES else "abort",
                None,
            )
        action = (
            "restart" if state["classification"] == "worker_stalled" else "failover"
        )
        return "execute_action", action

    def route(self, source: str, state: GraphState, proposed: str):
        return proposed

    def execute(self, action, context: Context):
        return ActionResult(
            action=action,
            context_revision=context.revision,
            success=True,
        )

    def respond(self, state: GraphState):
        status = state["final_status"]
        messages = {
            "resolved": f"{state['request'].service} remediated by {state['selected_action']}.",
            "aborted": "Remediation aborted; operator intervention required.",
            "blocked": "Workflow state validation failed; operator review required.",
        }
        return Response(status=status, message=messages[status])
