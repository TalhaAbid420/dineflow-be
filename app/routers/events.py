"""SSE endpoint: streams live order-status updates to the authenticated user.

Customers receive updates about their own orders; chefs receive a broadcast
channel with every order update so their dashboard stays live.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from app import pubsub
from app.deps import get_current_user

router = APIRouter()


@router.get("/events")
async def events(user: dict[str, Any] = Depends(get_current_user)):
    keys = [str(user["id"])]
    if user["role"] == "chef":
        keys.append(pubsub.CHEF_CHANNEL)
    queues = {key: pubsub.subscribe(key) for key in keys}

    async def generate():
        merged: asyncio.Queue = asyncio.Queue(maxsize=100)

        async def pump(queue: asyncio.Queue) -> None:
            while True:
                item = await queue.get()
                try:
                    merged.put_nowait(item)
                except asyncio.QueueFull:
                    pass

        pumps = [asyncio.create_task(pump(q)) for q in queues.values()]
        try:
            while True:
                try:
                    event = await asyncio.wait_for(merged.get(), timeout=15)
                    yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
                except asyncio.TimeoutError:
                    yield ": keep-alive\n\n"
        finally:
            for p in pumps:
                p.cancel()
            for key, queue in queues.items():
                pubsub.unsubscribe(key, queue)

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
