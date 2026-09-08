"""Small deterministic planner/response double, with prepared output overrides."""

import re

from .models import FinalResponse, State, ToolCall
from .tools import ToolError


class ControlledModel:
    def __init__(self, plan_override=None, response_override=None):
        self.plan_override = plan_override
        self.response_override = response_override

    def plan(self, request: str) -> list[ToolCall]:
        match = re.fullmatch(r"Fulfill order (ORD-\d+)\.?", request, re.IGNORECASE)
        if not match:
            raise ToolError("unsupported_request", "Use: Fulfill order ORD-100.")
        if self.plan_override is not None:
            return [call.model_copy(deep=True) for call in self.plan_override]
        order_id = match.group(1).upper()
        return [
            ToolCall(
                step_id="order", tool="get_order", arguments={"order_id": order_id}
            ),
            ToolCall(
                step_id="reserve",
                tool="reserve_inventory",
                arguments={
                    "order_id": "$order.order_id",
                    "sku": "$order.sku",
                    "quantity": "$order.quantity",
                },
            ),
            ToolCall(
                step_id="pay",
                tool="charge_payment",
                arguments={
                    "order_id": "$order.order_id",
                    "amount_cents": "$order.total_cents",
                },
            ),
            ToolCall(
                step_id="ship",
                tool="create_shipment",
                arguments={"order_id": "$order.order_id"},
            ),
            ToolCall(
                step_id="inspect",
                tool="inspect_fulfillment",
                arguments={"order_id": "$order.order_id"},
            ),
        ]

    def respond(
        self, status: str, state: State, error_code: str | None
    ) -> FinalResponse:
        if self.response_override is not None:
            return self.response_override.model_copy(deep=True)
        if status == "failed":
            return FinalResponse(
                status="failed",
                message=f"Fulfillment stopped: {error_code}. Partial state is retained.",
            )
        shipment = state.shipment
        return FinalResponse(
            status="completed",
            shipment_id=shipment.shipment_id,
            quantity=shipment.quantity,
            message=f"Order {shipment.order_id} shipped as {shipment.shipment_id} with {shipment.quantity} units.",
        )
