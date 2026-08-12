"""Dineflow backend.

FastAPI service that runs the restaurant-ordering agent (OpenAI Agents SDK
+ GPT-5) with PostgreSQL for short-term memory + ordering, and MongoDB for
long-term memories (preferences extractor).

Run locally:
    uv sync
    uv run uvicorn main:app --reload --port 8000

Endpoints:
    GET  /health       liveness probe
    POST /api/chat     SSE streamed agent conversation
"""
