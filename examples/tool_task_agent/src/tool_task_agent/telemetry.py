"""What each traced step records on the durable trace: plain dicts only.

Each entry is `(input_fn, output_fn)` for `TraceSession.instrument(..., payloads=...)`.
`input_fn` receives the wrapped call's arguments and `output_fn` its result.
Nothing here runs on the local (metadata-only) route. A failed call has no
output; its error type is recorded by the session.
"""


def _tool_input(tool, arguments, *, step_id, attempt):
    return {"tool": tool, "arguments": dict(arguments), "step_id": step_id, "attempt": attempt}


def _request_input(stage, output_type, instruction, context, validate=None):
    # The system text is fixed apart from these parts; the schema is not recorded.
    return {"stage": stage, "instruction": instruction, "context": context}


TOOL_PAYLOADS = {"invoke": (_tool_input, lambda result: {"result": result})}

CONTROLLED_MODEL_PAYLOADS = {
    "plan": (
        lambda request: {"request": request},
        lambda plan: {"plan": [call.model_dump() for call in plan]},
    ),
    "respond": (
        lambda status, state, error_code: {
            "status": status,
            "error_code": error_code,
            "state": state.model_dump(),
        },
        lambda response: response.model_dump(),
    ),
}

LIVE_MODEL_PAYLOADS = {"_request": (_request_input, lambda output: output.model_dump())}
