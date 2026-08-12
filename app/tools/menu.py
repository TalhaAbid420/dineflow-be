"""Menu tool: lets the agent browse the restaurant menu."""

from __future__ import annotations

import json

from agents import RunContextWrapper, function_tool

from app.agent.memory import AgentContext
from app.db import postgres

CATEGORY_ORDER = ["Starters", "Mains", "Beverages", "Desserts"]


@function_tool
async def get_menu(
    wrapper: RunContextWrapper[AgentContext], category: str | None = None
) -> str:
    """List menu categories, or the items in one category.

    Args:
        category: Optional category filter, e.g. "Starters", "Mains",
            "Beverages", "Desserts". Omit to list the available categories.
    """
    items = await postgres.list_menu(category=category)
    if not items:
        return "No menu items found" + (f" in category '{category}'." if category else ".")
    if category:
        return json.dumps(items, ensure_ascii=False)
    categories = list(dict.fromkeys(str(i.get("category") or "Other") for i in items))
    categories.sort(
        key=lambda c: (CATEGORY_ORDER.index(c) if c in CATEGORY_ORDER else len(CATEGORY_ORDER), c)
    )
    return json.dumps({"categories": categories}, ensure_ascii=False)
