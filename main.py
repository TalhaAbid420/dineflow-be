"""Dineflow — FastAPI backend entrypoint.

Serves the OpenAI Agents SDK restaurant-ordering agent over SSE, backed by
PostgreSQL (short-term memory + ordering) and MongoDB (long-term memories).
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.db import images, mongodb, postgres
from app.routers.auth import router as auth_router
from app.routers.chat import router as chat_router
from app.routers.events import router as events_router
from app.routers.menu import router as menu_router
from app.routers.orders import router as orders_router

logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    logging.getLogger("dineflow.main").info("Starting Dineflow backend")
    await postgres.init_db()
    if settings.seed_menu_on_start:
        from app.db import seed

        await seed.seed_menu_if_empty()
    await images.import_images()
    from app.db import seed as seed_users

    await seed_users.seed_chef_user()
    await mongodb.ping()
    yield
    await postgres.close_db()


app = FastAPI(title="Dineflow", version="0.1.0", lifespan=lifespan)

settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chat_router, prefix="/api")
app.include_router(auth_router, prefix="/api")
app.include_router(orders_router, prefix="/api")
app.include_router(events_router, prefix="/api")
app.include_router(menu_router, prefix="/api")


@app.get("/health")
async def health() -> dict:
    return {
        "status": "ok",
        "app": settings.app_name,
        "environment": settings.environment,
    }
