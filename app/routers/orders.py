"""Orders: chef management + customer view, with live status updates."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app import pubsub
from app.db import postgres
from app.deps import get_current_user, require_chef

router = APIRouter(prefix="/orders", tags=["orders"])

ALLOWED_STATUSES = {"pending", "baking", "baked", "in-delivery"}


class StatusUpdate(BaseModel):
    status: str


@router.get("")
async def list_all_orders(
    user: dict[str, Any] = Depends(require_chef),
) -> list[dict[str, Any]]:
    """Chef-only: every order, newest first."""
    return await postgres.list_all_orders()


@router.get("/mine")
async def my_orders(
    user: dict[str, Any] = Depends(get_current_user),
) -> list[dict[str, Any]]:
    """The current customer's orders."""
    return await postgres.list_orders(user["id"])


@router.patch("/{order_id}/status")
async def set_order_status(
    order_id: int,
    body: StatusUpdate,
    user: dict[str, Any] = Depends(require_chef),
) -> dict[str, Any]:
    """Chef-only: change an order's status and push it to the customer live."""
    if body.status not in ALLOWED_STATUSES:
        raise HTTPException(
            status_code=400,
            detail=f"Status must be one of: {', '.join(sorted(ALLOWED_STATUSES))}",
        )
    order = await postgres.update_order_status(order_id, body.status)
    if order is None:
        raise HTTPException(status_code=404, detail="Order not found")
    if order.get("user_id"):
        await pubsub.publish(str(order["user_id"]), {"type": "order_status", "order": order})
    await pubsub.publish_to_chefs({"type": "order_status", "order": order})
    return order
