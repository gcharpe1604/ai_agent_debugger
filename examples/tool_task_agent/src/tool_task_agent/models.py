from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

Text = Annotated[str, StringConstraints(min_length=1, strip_whitespace=True)]
PositiveInt = Annotated[int, Field(gt=0)]
StepId = Literal["order", "reserve", "pay", "ship", "inspect"]
ToolName = Literal[
    "get_order",
    "get_stock",
    "reserve_inventory",
    "charge_payment",
    "create_shipment",
    "inspect_fulfillment",
]
MAX_ATTEMPTS = 3


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class Order(Model):
    order_id: Text
    sku: Text
    quantity: PositiveInt
    total_cents: PositiveInt


class Reservation(Model):
    reservation_id: Text
    order_id: Text
    sku: Text
    quantity: PositiveInt


class Payment(Model):
    payment_id: Text
    order_id: Text
    amount_cents: PositiveInt


class Shipment(Model):
    shipment_id: Text
    order_id: Text
    reservation_id: Text
    payment_id: Text
    quantity: PositiveInt


class State(Model):
    order: Order = Field(
        default_factory=lambda: Order(
            order_id="ORD-100",
            sku="SENSOR-KIT",
            quantity=2,
            total_cents=5000,
        )
    )
    available_stock: int = Field(default=5, ge=0)
    reservation: Reservation | None = None
    payment: Payment | None = None
    shipment: Shipment | None = None


class ToolCall(Model):
    step_id: StepId
    tool: ToolName
    arguments: dict[str, Any]


class FinalResponse(Model):
    status: Literal["completed", "failed"]
    message: Text
    shipment_id: Text | None = None
    quantity: PositiveInt | None = None


class Event(Model):
    sequence: PositiveInt
    operation: Text
    step_id: Text
    attempt: int = Field(default=0, ge=0, le=MAX_ATTEMPTS)
    status: Literal["ok", "error"]
    inputs: dict[str, Any] = Field(default_factory=dict)
    output: Any = None
    error_code: str | None = None
    state: State


class AgentResult(Model):
    request: Text
    status: Literal["completed", "failed"]
    final_response: FinalResponse
    events: list[Event]
    state: State
    error_code: str | None = None
