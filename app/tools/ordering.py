"""Ordering tools: create orders and add items to them."""

from __future__ import annotations

import json

from agents import RunContextWrapper, function_tool

from app.agent.memory import AgentContext
from app.db import postgres


@function_tool
async def place_order(
    wrapper: RunContextWrapper[AgentContext],
    items: str,
    order_type: str = "dine_in",
    customer_name: str = "",
    delivery_address: str = "",
    phone: str = "",
) -> str:
    """Place a new order.

    Args:
        items: JSON array of ordered items, each with "name" (from the menu),
            "price" (from the menu) and "quantity" (integer).
        order_type: "dine_in" or "delivery". Always ask the customer which they
            want before placing the order.
        customer_name: Customer name, if provided.
        delivery_address: Delivery address — REQUIRED when order_type is
            "delivery". Ask the customer for it before placing the order.
        phone: Contact phone number, if provided.
    """
    try:
        parsed_items = json.loads(items)
    except json.JSONDecodeError:
        return "ERROR: 'items' must be a valid JSON array."
    if not parsed_items:
        return "ERROR: 'items' cannot be empty."

    if order_type not in ("dine_in", "delivery"):
        return (
            "ERROR: 'order_type' must be either 'dine_in' or 'delivery'. "
            "Ask the customer which they prefer before placing the order."
        )
    if order_type == "delivery" and not delivery_address.strip():
        return (
            "ERROR: delivery orders need a delivery address. Ask the customer "
            "for their delivery address before placing the order."
        )

    order_id = await postgres.create_order(
        wrapper.context.user_id,
        customer_name=customer_name,
        items=parsed_items,
        order_type=order_type,
        delivery_address=delivery_address.strip(),
    )
    order = await postgres.get_order(order_id)
    return json.dumps(order, ensure_ascii=False)


@function_tool
async def add_item(
    wrapper: RunContextWrapper[AgentContext],
    order_id: int,
    name: str,
    price: float,
    quantity: int = 1,
) -> str:
    """Add an item to an existing order.

    Args:
        order_id: The order id returned by place_order.
        name: Item name, taken exactly from the menu.
        price: Item price, taken exactly from the menu.
        quantity: Number of items to add (default 1).
    """
    order = await postgres.add_item_to_order(
        order_id,
        {"name": name, "price": price, "quantity": quantity},
    )
    return json.dumps(order, ensure_ascii=False)
