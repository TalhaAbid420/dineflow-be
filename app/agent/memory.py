"""Conversation context and long-term memory helpers for the Dineflow agent."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any

from agents import Agent, ModelSettings, RunContextWrapper, Runner
from agents.exceptions import AgentsException
from openai.types.shared import Reasoning

from app.agent.prompts import EXTRACTION_PROMPT
from app.config import get_settings
from app.db import mongodb, postgres

logger = logging.getLogger("dineflow.memory")

SHORT_TERM_WINDOW = 20


@dataclass
class AgentContext:
    """Per-request context passed to the agent and its tools."""

    user_id: int
    memory: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Memory wiring
# ---------------------------------------------------------------------------


def _format_memory(facts: dict[str, Any]) -> str:
    if not facts:
        return "No long-term details on file for this customer yet."
    lines = []
    for key, value in facts.items():
        if isinstance(value, (list, dict)):
            value = ", ".join(str(v) for v in value)
        lines.append(f"- {key}: {value}")
    return "\n".join(lines)


async def load_context(user_id: int) -> AgentContext:
    facts = await mongodb.load_user_memory(str(user_id))
    return AgentContext(user_id=user_id, memory=facts)


def build_instructions(ctx: AgentContext) -> str:
    from app.agent.prompts import SYSTEM_PROMPT

    return SYSTEM_PROMPT.format(memory_context=_format_memory(ctx.memory))


async def load_short_term_history(user_id: int) -> list[dict[str, Any]]:
    messages = await postgres.load_session_messages(str(user_id))
    return messages[-SHORT_TERM_WINDOW:]


async def persist_turn(user_id: int, user_message: str, final_output: str) -> None:
    await postgres.save_session_messages(
        str(user_id),
        [
            {"role": "user", "content": user_message},
            {"role": "assistant", "content": final_output},
        ],
    )


# ---------------------------------------------------------------------------
# Long-term memory extraction ("preferences extractor" box in the architecture)
# ---------------------------------------------------------------------------


async def extract_and_store_preferences(
    ctx: AgentContext, user_message: str, final_output: str
) -> None:
    try:
        settings = get_settings()
        conversation = json.dumps(
            [
                {"role": "user", "content": user_message},
                {"role": "assistant", "content": final_output},
            ],
            ensure_ascii=False,
        )
        extractor = Agent(
            name="PreferencesExtractor",
            instructions=EXTRACTION_PROMPT.format(conversation=conversation),
            model=settings.openai_model,
            model_settings=ModelSettings(reasoning=Reasoning(effort="minimal")),
        )
        result = await Runner.run(extractor, input="Extract memory now.")
        new_facts = json.loads(result.final_output.strip())
        if not isinstance(new_facts, dict):
            return
        merged = {**ctx.memory}
        for key, value in new_facts.items():
            if value not in (None, "", [], {}):
                merged[key] = value
        if merged != ctx.memory:
            await mongodb.save_facts(str(ctx.user_id), merged)
            ctx.memory = merged
            logger.info("Stored %s new facts for user_id=%s", len(new_facts), ctx.user_id)
    except (AgentsException, json.JSONDecodeError, Exception) as exc:  # noqa: BLE001
        logger.warning("Memory extraction skipped: %s", exc)
