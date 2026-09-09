from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints
from typing_extensions import TypedDict

MAX_RETRIES = 2
RECURSION_LIMIT = 18
Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
Incident = Literal["worker_stalled", "host_unavailable"]
Action = Literal["restart", "failover"]
Status = Literal["running", "resolved", "aborted", "blocked"]
Node = Literal[
    "classify",
    "gather_context",
    "evaluate",
    "retry_context",
    "execute_action",
    "abort",
    "validate",
    "respond",
]
Destination = Literal[
    "gather_context",
    "evaluate",
    "retry_context",
    "execute_action",
    "abort",
    "validate",
    "__end__",
]
Issue = Literal[
    "missing_context",
    "stale_context",
    "missing_action_result",
    "action_mismatch",
    "action_failed",
    "terminal_retry",
]


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class Request(Model):
    service: Literal["beacon"]
    incident: Incident
    telemetry: Literal["ready", "delayed", "denied", "unavailable"]


class Context(Model):
    revision: int = Field(ge=1)
    availability: Literal["ready", "retryable", "terminal"]
    incident: Incident


class ActionResult(Model):
    action: Action
    context_revision: int = Field(ge=1)
    success: bool


class Response(Model):
    status: Literal["resolved", "aborted", "blocked"]
    message: Text


class GraphState(TypedDict):
    request: Request
    classification: Incident | None
    context: Context | None
    retry_count: int
    selected_action: Action | None
    next_node: Destination | None
    action_result: ActionResult | None
    validation: list[Issue] | None
    final_status: Status
    response: Response | None


class Result(Model):
    path: list[Node]
    updates: list[dict[str, dict]]
    state: GraphState
    execution_error: Literal["recursion_limit"] | None


def initial_state(request: Request) -> GraphState:
    return GraphState(
        request=request.model_copy(deep=True),
        classification=None,
        context=None,
        retry_count=0,
        selected_action=None,
        next_node=None,
        action_result=None,
        validation=None,
        final_status="running",
        response=None,
    )
