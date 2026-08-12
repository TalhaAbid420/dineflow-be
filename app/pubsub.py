"""In-memory pub/sub used to push order status changes to users over SSE."""

from __future__ import annotations

import asyncio
from collections import defaultdict

_subscribers: dict[str, list[asyncio.Queue]] = defaultdict(list)

# Channel that every chef subscribes to; order updates are broadcast here too.
CHEF_CHANNEL = "chef"


def subscribe(user_key: str) -> asyncio.Queue:
    queue: asyncio.Queue = asyncio.Queue(maxsize=100)
    _subscribers[user_key].append(queue)
    return queue


def unsubscribe(user_key: str, queue: asyncio.Queue) -> None:
    try:
        _subscribers[user_key].remove(queue)
        if not _subscribers[user_key]:
            del _subscribers[user_key]
    except (ValueError, KeyError):
        pass


async def publish(user_key: str, event: dict) -> None:
    for queue in list(_subscribers.get(user_key, [])):
        try:
            queue.put_nowait(event)
        except asyncio.QueueFull:
            # Drop the oldest event to keep the stream moving.
            try:
                queue.get_nowait()
                queue.put_nowait(event)
            except (asyncio.QueueEmpty, asyncio.QueueFull):
                pass


async def publish_to_chefs(event: dict) -> None:
    await publish(CHEF_CHANNEL, event)
