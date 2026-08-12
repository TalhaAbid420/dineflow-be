"""Chat endpoint: streams the Dineflow agent's reply over SSE."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from agents import Runner

from app.agent.agent import build_agent
from app.agent.memory import (
    build_instructions,
    extract_and_store_preferences,
    load_context,
    load_short_term_history,
    persist_turn,
)
from app.deps import get_current_user

logger = logging.getLogger("dineflow.chat")

router = APIRouter()


class ChatRequest(BaseModel):
    message: str


_BROWSE_HINTS = (
    "menu",
    "show",
    "see",
    "display",
    "categories",
    "category",
    "what do you have",
    "what's on",
    "list",
    "starters",
    "mains",
    "beverages",
    "desserts",
    "drinks",
)
_ORDER_HINTS = (
    "want",
    "would like",
    "i'll have",
    "i will have",
    "ill have",
    "get me",
    "give me",
    "order",
    "add",
    "plus",
    "make it",
    "buy",
    "want a",
    "one ",
)


def _looks_like_browse(message: str) -> bool:
    m = message.lower()
    has_order = any(k in m for k in _ORDER_HINTS)
    has_browse = any(k in m for k in _BROWSE_HINTS)
    return has_browse and not has_order


def _sse(event: dict) -> str:
    return f"data: {json.dumps(event, ensure_ascii=False)}\n\n"


async def _stream_reply(agent, inputs, ctx, collected: list[str], suppress_menu: bool = False):
    """Yield SSE deltas and append the final assistant text to ``collected``."""
    try:
        result = Runner.run_streamed(agent, input=inputs, context=ctx)
        menu_events: list[str] = []
        placed = False
        async for event in result.stream_events():
            data = getattr(event, "data", None)
            if data is not None and getattr(data, "type", "") == "response.text.delta":
                delta = getattr(data, "delta", None)
                if delta:
                    yield _sse({"type": "delta", "content": delta})
                continue

            if event.__class__.__name__ != "RunItemStreamEvent":
                continue

            if event.name == "tool_called":
                raw = getattr(event.item, "raw_item", None)
                if raw is not None:
                    name = getattr(raw, "name", "")
                    if name == "place_order":
                        placed = True
                        menu_events.clear()
                    yield _sse(
                        {
                            "type": "tool",
                            "name": name,
                            "arguments": getattr(raw, "arguments", ""),
                        }
                    )
            elif event.name == "tool_output":
                output = getattr(event.item, "output", None)
                if isinstance(output, str):
                    try:
                        parsed = json.loads(output)
                        if (
                            isinstance(parsed, dict)
                            and isinstance(parsed.get("categories"), list)
                            and parsed["categories"]
                        ):
                            cats = [c for c in parsed["categories"] if isinstance(c, str)]
                            if cats:
                                menu_events.append(
                                    _sse({"type": "menu_categories", "categories": cats})
                                )
                        elif isinstance(parsed, list) and parsed and all(
                            isinstance(i, dict) and "name" in i for i in parsed
                        ):
                            menu_events.append(_sse({"type": "menu", "items": parsed}))
                        elif (
                            isinstance(parsed, dict)
                            and "id" in parsed
                            and "status" in parsed
                        ):
                            yield _sse({"type": "order", "order": parsed})
                    except json.JSONDecodeError:
                        pass
        if not placed and not suppress_menu:
            for ev in menu_events:
                yield ev
        collected.append(result.final_output or "")
    except Exception as exc:  # noqa: BLE001
        logger.exception("Streaming agent run failed")
        yield _sse({"type": "error", "message": f"Agent run failed: {exc}"})


@router.post("/chat")
async def chat(
    req: ChatRequest,
    user: dict[str, Any] = Depends(get_current_user),
):
    ctx_task = asyncio.create_task(load_context(user["id"]))
    history_task = asyncio.create_task(load_short_term_history(user["id"]))
    ctx, history = await asyncio.gather(ctx_task, history_task)
    instructions = build_instructions(ctx)
    agent = build_agent(instructions)
    inputs = history + [{"role": "user", "content": req.message}]

    async def generate():
        collected: list[str] = []
        suppress_menu = not _looks_like_browse(req.message)
        async for chunk in _stream_reply(agent, inputs, ctx, collected, suppress_menu):
            yield chunk

        if not collected:
            # Fallback: run non-streamed.
            try:
                result = await Runner.run(agent, input=inputs, context=ctx)
                collected.append(result.final_output or "")
                yield _sse({"type": "delta", "content": collected[0]})
            except Exception as exc:  # noqa: BLE001
                logger.exception("Fallback agent run failed")
                collected.append(f"Sorry, I hit an error: {exc}")
                yield _sse({"type": "error", "message": str(exc)})

        final = collected[0] if collected else ""
        await persist_turn(user["id"], req.message, final)
        asyncio.create_task(extract_and_store_preferences(ctx, req.message, final))
        yield _sse({"type": "done", "content": final})

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
