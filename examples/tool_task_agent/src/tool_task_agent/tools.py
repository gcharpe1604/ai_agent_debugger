"""Local services. Preconditions are enforced before any state mutation."""

from typing import Literal

from pydantic import ValidationError

from .models import Model, Payment, PositiveInt, Reservation, Shipment, State, Text


class ToolError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


class TransientToolError(ToolError):
    pass


class ToolTimeout(TimeoutError):
    """A fake service deadline expired before it committed a write."""


class OrderArgs(Model):
    order_id: Text


class ReserveArgs(OrderArgs):
    sku: Text
    quantity: PositiveInt


class PaymentArgs(OrderArgs):
    amount_cents: PositiveInt


class StockArgs(Model):
    sku: Literal["SENSOR-KIT"]


ARGUMENT_MODELS = {
    "get_order": OrderArgs,
    "get_stock": StockArgs,
    "reserve_inventory": ReserveArgs,
    "charge_payment": PaymentArgs,
    "create_shipment": OrderArgs,
    "inspect_fulfillment": OrderArgs,
}


class LocalTools:
    def __init__(self):
        self.state = State()

    def invoke(self, tool: str, arguments: dict, *, step_id: str, attempt: int):
        if tool not in ARGUMENT_MODELS:
            raise ToolError("unknown_tool", f"Unknown tool: {tool}")
        try:
            args = ARGUMENT_MODELS[tool].model_validate(arguments)
        except ValidationError as exc:
            raise ToolError(
                "invalid_arguments", f"Invalid arguments for {tool}"
            ) from exc
        if tool == "get_stock":
            return {"sku": args.sku, "available_stock": self.state.available_stock}
        if args.order_id != self.state.order.order_id:
            raise ToolError("order_not_found", "Order does not exist")
        return getattr(self, tool)(args)

    def get_order(self, args: OrderArgs):
        return self.state.order.model_dump()

    def reserve_inventory(self, args: ReserveArgs):
        state = self.state
        if (args.sku, args.quantity) != (state.order.sku, state.order.quantity):
            raise ToolError("order_mismatch", "Reservation must match the order")
        if state.reservation:
            return state.reservation.model_dump()
        if state.available_stock < args.quantity:
            raise ToolError("insufficient_stock", "Not enough stock")
        state.reservation = Reservation(
            reservation_id="RES-100",
            **args.model_dump(),
        )
        state.available_stock -= args.quantity
        return state.reservation.model_dump()

    def charge_payment(self, args: PaymentArgs):
        state = self.state
        if state.reservation is None:
            raise ToolError("reservation_required", "Reserve stock before payment")
        if args.amount_cents != state.order.total_cents:
            raise ToolError("amount_mismatch", "Payment must match the order total")
        if state.payment is None:
            state.payment = Payment(payment_id="PAY-100", **args.model_dump())
        return state.payment.model_dump()

    def create_shipment(self, args: OrderArgs):
        state = self.state
        if state.reservation is None:
            raise ToolError("reservation_required", "Reserve stock before shipment")
        if state.payment is None:
            raise ToolError("payment_required", "Pay before shipment")
        if state.shipment is None:
            state.shipment = Shipment(
                shipment_id="SHIP-100",
                order_id=args.order_id,
                reservation_id=state.reservation.reservation_id,
                payment_id=state.payment.payment_id,
                quantity=state.reservation.quantity,
            )
        return state.shipment.model_dump()

    def inspect_fulfillment(self, args: OrderArgs):
        return self.state.model_dump()
