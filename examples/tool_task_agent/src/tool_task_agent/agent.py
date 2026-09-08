from copy import deepcopy

from pydantic import ValidationError

from .models import (
    MAX_ATTEMPTS,
    AgentResult,
    Event,
    FinalResponse,
    Order,
    Payment,
    Reservation,
    Shipment,
    State,
)
from .tools import ToolError, ToolTimeout, TransientToolError

RESPONSE_MODELS = {
    "order": Order,
    "reserve": Reservation,
    "pay": Payment,
    "ship": Shipment,
    "inspect": State,
}


def validate_state(state: State, initial: State) -> None:
    """Check records against each other and the original request's order."""
    order, reserve, payment, shipment = (
        state.order,
        state.reservation,
        state.payment,
        state.shipment,
    )
    if (
        order != initial.order
        or reserve is None
        or payment is None
        or shipment is None
        or {reserve.order_id, payment.order_id, shipment.order_id} != {order.order_id}
        or reserve.sku != order.sku
        or reserve.quantity != order.quantity
        or shipment.quantity != order.quantity
        or payment.amount_cents != order.total_cents
        or shipment.reservation_id != reserve.reservation_id
        or shipment.payment_id != payment.payment_id
        or state.available_stock != initial.available_stock - order.quantity
    ):
        raise ToolError(
            "inconsistent_state",
            "Order, stock, reservation, payment and shipment disagree",
        )


class TaskAgent:
    """Bounded execution; receives dependencies, never scenario IDs or labels."""

    def __init__(self, model, tools_factory):
        self.model = model
        self.tools_factory = tools_factory

    def run(self, request: str) -> AgentResult:
        if not isinstance(request, str) or not request.strip():
            raise ValueError("request must be a nonempty string")
        request = request.strip()
        tools = self.tools_factory()
        initial = tools.state.model_copy(deep=True)
        events = []
        outputs = {}

        def record(
            operation, step_id, *, attempt=0, inputs=None, output=None, error=None
        ):
            events.append(
                Event(
                    sequence=len(events) + 1,
                    operation=operation,
                    step_id=step_id,
                    attempt=attempt,
                    status="error" if error else "ok",
                    inputs=deepcopy(inputs or {}),
                    output=deepcopy(output),
                    error_code=error,
                    state=tools.state.model_copy(deep=True),
                )
            )

        error_code = None
        try:
            plan = self.model.plan(request)
            record(
                "interpret_plan",
                "plan",
                inputs={"request": request},
                output=[call.model_dump() for call in plan],
            )
            for call in plan:
                arguments = {}
                for key, value in call.arguments.items():
                    if isinstance(value, str) and value.startswith("$"):
                        step, _, field = value[1:].partition(".")
                        if step not in outputs or field not in outputs[step]:
                            record(
                                "resolve_arguments",
                                call.step_id,
                                inputs=call.arguments,
                                error="missing_dependency",
                            )
                            raise ToolError(
                                "missing_dependency",
                                "A referenced result is unavailable",
                            )
                        value = outputs[step][field]
                    arguments[key] = value
                for attempt in range(1, MAX_ATTEMPTS + 1):
                    try:
                        raw = tools.invoke(
                            call.tool, arguments, step_id=call.step_id, attempt=attempt
                        )
                    except (ToolError, ToolTimeout) as exc:
                        code = (
                            "tool_timeout" if isinstance(exc, ToolTimeout) else exc.code
                        )
                        record(
                            call.tool,
                            call.step_id,
                            attempt=attempt,
                            inputs=arguments,
                            error=code,
                        )
                        if (
                            isinstance(exc, (TransientToolError, ToolTimeout))
                            and attempt < MAX_ATTEMPTS
                        ):
                            continue
                        raise
                    record(
                        call.tool,
                        call.step_id,
                        attempt=attempt,
                        inputs=arguments,
                        output=raw,
                    )
                    break
                try:
                    output = RESPONSE_MODELS[call.step_id].model_validate(raw)
                except ValidationError as exc:
                    record(
                        "validate_result",
                        call.step_id,
                        inputs={"response": raw},
                        error="malformed_response",
                    )
                    raise ToolError(
                        "malformed_response", "Tool response violates the step contract"
                    ) from exc
                outputs[call.step_id] = output.model_dump()
                record("validate_result", call.step_id, output=outputs[call.step_id])

            try:
                if "inspect" not in outputs:
                    raise ToolError(
                        "verification_required", "Final inspection was skipped"
                    )
                verified = State.model_validate(outputs["inspect"])
                validate_state(verified, initial)
                if verified != tools.state:
                    raise ToolError(
                        "inconsistent_state", "Inspection disagrees with stored state"
                    )
            except ToolError as exc:
                record("validate_state", "verify", error=exc.code)
                raise
            record("validate_state", "verify", output=verified.model_dump())
        except (ToolError, ToolTimeout) as exc:
            error_code = "tool_timeout" if isinstance(exc, ToolTimeout) else exc.code
            if not events:
                record(
                    "interpret_plan",
                    "plan",
                    inputs={"request": request},
                    error=error_code,
                )

        status = "failed" if error_code else "completed"
        final = self.model.respond(
            status, tools.state.model_copy(deep=True), error_code
        )
        record(
            "generate_response",
            "final",
            inputs={"status": status, "error_code": error_code},
            output=final.model_dump(),
        )
        return AgentResult(
            request=request,
            status=status,
            final_response=FinalResponse.model_validate(final),
            events=events,
            state=tools.state.model_copy(deep=True),
            error_code=error_code,
        )
