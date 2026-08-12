"""MongoDB access layer.

Long-term memory: durable facts about a user (delivery address, phone number,
dietary / taste preferences, favourite dishes) that are extracted from
conversations and reused across sessions.
"""

from __future__ import annotations

import time
from typing import Any

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorCollection

from app.config import get_settings

_client: AsyncIOMotorClient | None = None
_memory_cache: dict[str, tuple[float, dict[str, Any]]] = {}
_MEMORY_CACHE_TTL_S = 30.0


def get_client() -> AsyncIOMotorClient:
    global _client
    if _client is None:
        settings = get_settings()
        _client = AsyncIOMotorClient(settings.mongodb_uri)
    return _client


def memories_collection() -> AsyncIOMotorCollection:
    settings = get_settings()
    return get_client()[settings.mongodb_db_name]["user_memories"]


async def ping() -> bool:
    try:
        await get_client().admin.command("ping")
        return True
    except Exception:
        return False


async def load_user_memory(user_key: str) -> dict[str, Any]:
    """Return the durable facts stored for a user key, or an empty dict."""
    now = time.monotonic()
    cached = _memory_cache.get(user_key)
    if cached and now - cached[0] < _MEMORY_CACHE_TTL_S:
        return cached[1]
    doc = await memories_collection().find_one({"_id": user_key})
    facts = dict(doc.get("facts", {})) if doc else {}
    _memory_cache[user_key] = (now, facts)
    return facts


async def save_facts(user_key: str, facts: dict[str, Any]) -> None:
    """Upsert durable facts for a user key."""
    if not facts:
        return
    await memories_collection().update_one(
        {"_id": user_key},
        {"$set": {"facts": facts, "updated_at": _now_iso()}},
        upsert=True,
    )
    _memory_cache[user_key] = (time.monotonic(), facts)


def _now_iso() -> str:
    import datetime as _dt

    return _dt.datetime.now(_dt.timezone.utc).isoformat()
