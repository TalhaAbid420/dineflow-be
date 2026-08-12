"""Dineflow agent definition."""

from __future__ import annotations

from agents import Agent, ModelSettings
from openai.types.shared import Reasoning

from app.config import get_settings
from app.tools.menu import get_menu
from app.tools.ordering import add_item, place_order
from app.tools.status import cancel_order, check_order_status, list_my_orders

_FAST_REASONING = ModelSettings(reasoning=Reasoning(effort="minimal"))


def build_agent(instructions: str) -> Agent:
    settings = get_settings()
    return Agent(
        name="Dineflow",
        instructions=instructions,
        tools=[
            get_menu,
            place_order,
            add_item,
            check_order_status,
            cancel_order,
            list_my_orders,
        ],
        model=settings.openai_model or None,
        model_settings=_FAST_REASONING,
    )
