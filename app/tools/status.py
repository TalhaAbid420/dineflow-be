"""Status tools: track and cancel orders."""

from __future__ import annotations

import json

from agents import RunContextWrapper, function_tool

from app.agent.memory import AgentContext
from app.db import postgres
from app import pubsub


@function_tool
async def check_order_status(
    wrapper: RunContextWrapper[AgentContext], order_id: int
) -> str:
    """Check the current status of an order by its id.

    Args:
        order_id: The order id returned when the order was placed.
    """
    order = await postgres.get_order(order_id)
    if order is None:
        return f"ERROR: No order found with id {order_id}."
    return json.dumps(order, ensure_ascii=False)


@function_tool
async def cancel_order(
    wrapper: RunContextWrapper[AgentContext], order_id: int
) -> str:
    """Cancel a pending order by its id.

    Args:
        order_id: The order id returned when the order was placed.
    """
    order = await postgres.get_order(order_id)
    if order is None:
        return f"ERROR: No order found with id {order_id}."
    if order["status"] == "cancelled":
        return json.dumps(order, ensure_ascii=False)
    if order["status"] not in ("pending", "confirmed"):
        return (
            f"ERROR: Order {order_id} is already '{order['status']}' and "
            "cannot be cancelled."
        )
    cancelled = await postgres.update_order_status(order_id, "cancelled")
    if cancelled and cancelled.get("user_id"):
        await pubsub.publish(
            str(cancelled["user_id"]), {"type": "order_status", "order": cancelled}
        )
    await pubsub.publish_to_chefs({"type": "order_status", "order": cancelled})
    return json.dumps(cancelled, ensure_ascii=False)


@function_tool
async def list_my_orders(wrapper: RunContextWrapper[AgentContext]) -> str:
    """List orders placed by this customer in this conversation."""
    orders = await postgres.list_orders(wrapper.context.user_id)
    return json.dumps(orders, ensure_ascii=False)
