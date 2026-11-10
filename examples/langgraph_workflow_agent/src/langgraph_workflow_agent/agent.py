from copy import deepcopy

from langgraph.errors import GraphRecursionError
from langgraph.graph import END, START, StateGraph
from langsmith import tracing_context

from .dependencies import LocalDependencies
from .models import RECURSION_LIMIT, GraphState, Request, Result, initial_state

ROUTED_NODES = ("classify", "evaluate", "retry_context")


class WorkflowAgent:
    def __init__(
        self,
        dependencies: LocalDependencies | None = None,
        *,
        nodes=None,
        routers=None,
    ):
        self.dependencies = (
            dependencies if dependencies is not None else LocalDependencies()
        )
        builder = StateGraph(GraphState)
        implementations = {
            "classify": self.classify,
            "gather_context": self.gather_context,
            "evaluate": self.evaluate,
            "retry_context": self.retry_context,
            "execute_action": self.execute_action,
            "abort": self.abort,
            "validate": self.validate,
            "respond": self.respond,
        }
        if nodes:
            if not nodes.keys() <= implementations.keys():
                raise ValueError("Unknown node override")
            for name, wrap in nodes.items():
                implementations[name] = wrap(implementations[name])
        for name, implementation in implementations.items():
            builder.add_node(name, implementation)
        # One router per conditional edge, so each routing decision can be
        # wrapped (and traced) under the name of the node it follows.
        routes = {source: self.route for source in ROUTED_NODES}
        if routers:
            if not routers.keys() <= routes.keys():
                raise ValueError("Unknown router override")
            for source, wrap in routers.items():
                routes[source] = wrap(routes[source])
        builder.add_edge(START, "classify")
        builder.add_conditional_edges(
            "classify",
            routes["classify"],
            ["gather_context", "evaluate", END],
        )
        builder.add_edge("gather_context", "evaluate")
        builder.add_conditional_edges(
            "evaluate",
            routes["evaluate"],
            ["retry_context", "execute_action", "abort", END],
        )
        builder.add_conditional_edges(
            "retry_context",
            routes["retry_context"],
            ["gather_context", "validate"],
        )
        builder.add_edge("execute_action", "validate")
        builder.add_edge("abort", "validate")
        builder.add_edge("validate", "respond")
        builder.add_edge("respond", END)
        self.graph = builder.compile()

    @staticmethod
    def route(state: GraphState):
        return state["next_node"]

    def classify(self, state: GraphState):
        return {
            "classification": self.dependencies.classify(state["request"]),
            "next_node": self.dependencies.route("classify", state, "gather_context"),
        }

    def gather_context(self, state: GraphState):
        return {
            "context": self.dependencies.gather(
                state["request"],
                attempt=state["retry_count"] + 1,
            ),
        }

    def evaluate(self, state: GraphState):
        destination, action = self.dependencies.decide(state)
        return {
            "selected_action": action,
            "next_node": self.dependencies.route("evaluate", state, destination),
        }

    @staticmethod
    def retry_context(state: GraphState):
        context = state["context"]
        if context is not None and context.availability == "terminal":
            return {"validation": ["terminal_retry"], "next_node": "validate"}
        return {"retry_count": state["retry_count"] + 1, "next_node": "gather_context"}

    def execute_action(self, state: GraphState):
        if state["context"] is None or state["selected_action"] is None:
            return {"action_result": None, "final_status": "resolved"}
        return {
            "action_result": self.dependencies.execute(
                state["selected_action"],
                state["context"],
            ),
            "final_status": "resolved",
        }

    @staticmethod
    def abort(state: GraphState):
        return {"final_status": "aborted"}

    @staticmethod
    def validate(state: GraphState):
        issues = list(state["validation"] or [])
        context = state["context"]
        if context is None:
            issues.append("missing_context")
        elif context.revision != state["retry_count"] + 1:
            issues.append("stale_context")
        if state["final_status"] == "resolved":
            result = state["action_result"]
            if result is None:
                issues.append("missing_action_result")
            else:
                if result.action != state["selected_action"] or (
                    context is not None and result.context_revision != context.revision
                ):
                    issues.append("action_mismatch")
                if not result.success:
                    issues.append("action_failed")
        return {
            "validation": issues,
            "final_status": "blocked" if issues else state["final_status"],
        }

    def respond(self, state: GraphState):
        return {"response": self.dependencies.respond(state), "next_node": END}

    @tracing_context(enabled=False, parent=False)
    def run(self, request: Request) -> Result:
        state = initial_state(Request.model_validate(request.model_dump()))
        updates = []
        error = None
        try:
            for mode, payload in self.graph.stream(
                state,
                config={"recursion_limit": RECURSION_LIMIT, "callbacks": []},
                stream_mode=["updates", "values"],
            ):
                if mode == "updates":
                    updates.append(deepcopy(payload))
                else:
                    state = deepcopy(payload)
        except GraphRecursionError:
            error = "recursion_limit"
        return Result(
            path=[node for update in updates for node in update],
            updates=updates,
            state=state,
            execution_error=error,
        )
