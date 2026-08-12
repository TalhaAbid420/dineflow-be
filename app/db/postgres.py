"""PostgreSQL access layer.

Short-term memory (recent conversation per session) plus the operational
ordering data (menu items, orders, order items) live here.
"""

from __future__ import annotations

import asyncio
import datetime as _dt
import json
import time
from decimal import Decimal
from typing import Any

import asyncpg

from app.config import get_settings

_pool: asyncpg.Pool | None = None
_keepalive_task: asyncio.Task | None = None


def _serializable(value: Any) -> Any:
    """Recursively convert DB-native types (e.g. Decimal, datetime) to JSON-safe ones."""
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (_dt.datetime, _dt.date, _dt.time)):
        return value.isoformat()
    if isinstance(value, dict):
        return {k: _serializable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_serializable(v) for v in value]
    return value

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS users (
    id            SERIAL PRIMARY KEY,
    email         TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    role          TEXT NOT NULL DEFAULT 'customer',
    name          TEXT NOT NULL DEFAULT '',
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS menu_items (
    id          SERIAL PRIMARY KEY,
    name        TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    price       NUMERIC(10, 2) NOT NULL,
    category    TEXT NOT NULL,
    available   BOOLEAN NOT NULL DEFAULT TRUE,
    image_data  BYTEA,
    image_mime  TEXT NOT NULL DEFAULT 'image/jpeg'
);

ALTER TABLE menu_items ADD COLUMN IF NOT EXISTS image_data BYTEA;
ALTER TABLE menu_items ADD COLUMN IF NOT EXISTS image_mime TEXT NOT NULL DEFAULT 'image/jpeg';

CREATE TABLE IF NOT EXISTS orders (
    id           SERIAL PRIMARY KEY,
    session_id   TEXT NOT NULL,
    user_id      INTEGER REFERENCES users(id),
    customer_name TEXT NOT NULL DEFAULT '',
    status       TEXT NOT NULL DEFAULT 'pending',
    total        NUMERIC(10, 2) NOT NULL DEFAULT 0,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

ALTER TABLE orders ADD COLUMN IF NOT EXISTS user_id INTEGER REFERENCES users(id);

CREATE TABLE IF NOT EXISTS order_items (
    order_id     INTEGER NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
    menu_item_id INTEGER,
    name         TEXT NOT NULL,
    price        NUMERIC(10, 2) NOT NULL,
    quantity     INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS sessions (
    session_id TEXT PRIMARY KEY,
    user_id    INTEGER REFERENCES users(id),
    messages   JSONB NOT NULL DEFAULT '[]',
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

ALTER TABLE sessions ADD COLUMN IF NOT EXISTS user_id INTEGER REFERENCES users(id);
"""


async def get_pool() -> asyncpg.Pool:
    global _pool, _keepalive_task
    if _pool is None:
        settings = get_settings()
        _pool = await asyncpg.create_pool(
            settings.postgres_database_url,
            min_size=1,
            max_size=10,
        )
        _keepalive_task = asyncio.get_running_loop().create_task(_keep_pool_warm(_pool))
    return _pool


async def _keep_pool_warm(pool: asyncpg.Pool) -> None:
    """Neon serverless compute can autosuspend; ping it so queries stay fast."""
    while True:
        await asyncio.sleep(25)
        try:
            async with pool.acquire() as conn:
                await conn.fetchval("SELECT 1")
        except Exception:  # noqa: BLE001
            pass


async def init_db() -> None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(SCHEMA_SQL)


async def close_db() -> None:
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None


# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------


async def create_user(
    email: str,
    password_hash: str,
    name: str = "",
    role: str = "customer",
) -> dict[str, Any] | None:
    pool = await get_pool()
    try:
        row = await pool.fetchrow(
            "INSERT INTO users (email, password_hash, name, role) "
            "VALUES ($1, $2, $3, $4) "
            "RETURNING id, email, role, name, created_at",
            email,
            password_hash,
            name,
            role,
        )
    except asyncpg.UniqueViolationError:
        return None
    return dict(row) if row else None


async def get_user_by_email(email: str) -> dict[str, Any] | None:
    pool = await get_pool()
    row = await pool.fetchrow(
        "SELECT id, email, password_hash, role, name, created_at "
        "FROM users WHERE email = $1",
        email,
    )
    return dict(row) if row else None


_user_cache: dict[int, tuple[float, dict[str, Any] | None]] = {}
_USER_CACHE_TTL_S = 30.0


async def get_user_by_id(user_id: int) -> dict[str, Any] | None:
    now = time.monotonic()
    cached = _user_cache.get(user_id)
    if cached and now - cached[0] < _USER_CACHE_TTL_S:
        return cached[1]
    pool = await get_pool()
    row = await pool.fetchrow(
        "SELECT id, email, password_hash, role, name, created_at "
        "FROM users WHERE id = $1",
        user_id,
    )
    user = dict(row) if row else None
    _user_cache[user_id] = (now, user)
    return user


# ---------------------------------------------------------------------------
# Menu
# ---------------------------------------------------------------------------


async def list_menu(category: str | None = None) -> list[dict[str, Any]]:
    pool = await get_pool()
    if category:
        rows = await pool.fetch(
            "SELECT id, name, description, price, category, available, "
            "(image_data IS NOT NULL) AS has_image "
            "FROM menu_items WHERE category = $1 AND available = TRUE "
            "ORDER BY id",
            category,
        )
    else:
        rows = await pool.fetch(
            "SELECT id, name, description, price, category, available, "
            "(image_data IS NOT NULL) AS has_image "
            "FROM menu_items WHERE available = TRUE ORDER BY id"
        )
    return [_menu_item_with_image_url(row) for row in rows]


async def get_menu_item(item_id: int) -> dict[str, Any] | None:
    pool = await get_pool()
    row = await pool.fetchrow(
        "SELECT id, name, description, price, category, available, "
        "(image_data IS NOT NULL) AS has_image "
        "FROM menu_items WHERE id = $1",
        item_id,
    )
    return _menu_item_with_image_url(row) if row else None


async def get_menu_item_image(item_id: int) -> dict[str, Any] | None:
    """Return the stored image bytes + mime for a menu item, if any."""
    pool = await get_pool()
    row = await pool.fetchrow(
        "SELECT image_data, image_mime FROM menu_items WHERE id = $1",
        item_id,
    )
    if not row or row["image_data"] is None:
        return None
    return {"data": row["image_data"], "mime": row["image_mime"]}


async def set_menu_item_image_by_name(
    name: str, data: bytes, mime: str, force: bool = False
) -> int:
    """Store image bytes for every menu item with the given name.

    Returns the number of rows updated. Existing images are kept unless
    ``force`` is True.
    """
    pool = await get_pool()
    clause = "AND image_data IS NULL" if not force else ""
    rows = await pool.fetch(
        f"UPDATE menu_items SET image_data = $1, image_mime = $2 "
        f"WHERE name = $3 {clause} RETURNING id",
        data,
        mime,
        name,
    )
    return len(rows)


def _menu_item_with_image_url(row: asyncpg.Record) -> dict[str, Any]:
    item = _serializable(dict(row))
    has_image = item.pop("has_image", False)
    item["image_url"] = f"/api/menu/{item['id']}/image" if has_image else None
    return item


# ---------------------------------------------------------------------------
# Orders
# ---------------------------------------------------------------------------


async def create_order(
    user_id: int, customer_name: str = "", items: list[dict[str, Any]] | None = None
) -> int:
    pool = await get_pool()
    total = round(sum(float(i["price"]) * int(i["quantity"]) for i in items or []), 2)
    async with pool.acquire() as conn:
        async with conn.transaction():
            order_id = await conn.fetchval(
                "INSERT INTO orders (session_id, user_id, customer_name, total) "
                "VALUES ($1, $2, $3, $4) RETURNING id",
                str(user_id),
                user_id,
                customer_name,
                total,
            )
            for item in items or []:
                await conn.execute(
                    "INSERT INTO order_items (order_id, menu_item_id, name, price, quantity) "
                    "VALUES ($1, $2, $3, $4, $5)",
                    order_id,
                    item.get("menu_item_id"),
                    item["name"],
                    float(item["price"]),
                    int(item["quantity"]),
                )
            return order_id


async def add_item_to_order(
    order_id: int, item: dict[str, Any]
) -> dict[str, Any]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            await conn.execute(
                "INSERT INTO order_items (order_id, menu_item_id, name, price, quantity) "
                "VALUES ($1, $2, $3, $4, $5)",
                order_id,
                item.get("menu_item_id"),
                item["name"],
                float(item["price"]),
                int(item["quantity"]),
            )
            new_total = await conn.fetchval(
                "SELECT COALESCE(SUM(price * quantity), 0) FROM order_items WHERE order_id = $1",
                order_id,
            )
            await conn.execute(
                "UPDATE orders SET total = $1 WHERE id = $2", new_total, order_id
            )
            return await _fetch_order(conn, order_id)


async def get_order(order_id: int) -> dict[str, Any] | None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await _fetch_order(conn, order_id)


async def _fetch_order(conn: asyncpg.Connection, order_id: int) -> dict[str, Any] | None:
    order = await conn.fetchrow(
        "SELECT id, session_id, user_id, customer_name, status, total, created_at "
        "FROM orders WHERE id = $1",
        order_id,
    )
    if not order:
        return None
    items = await conn.fetch(
        "SELECT menu_item_id, name, price, quantity FROM order_items "
        "WHERE order_id = $1",
        order_id,
    )
    data = dict(order)
    data["items"] = [_serializable(dict(i)) for i in items]
    return _serializable(data)


async def update_order_status(order_id: int, status: str) -> dict[str, Any] | None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE orders SET status = $1 WHERE id = $2", status, order_id
        )
        return await _fetch_order(conn, order_id)


async def list_orders(user_id: int) -> list[dict[str, Any]]:
    pool = await get_pool()
    rows = await pool.fetch(
        """
        SELECT o.id, o.session_id, o.user_id, o.customer_name, o.status,
               o.total, o.created_at,
               COALESCE(
                 json_agg(
                   json_build_object('menu_item_id', oi.menu_item_id,
                                     'name', oi.name,
                                     'price', oi.price,
                                     'quantity', oi.quantity)
                 ) FILTER (WHERE oi.order_id IS NOT NULL),
                 '[]'
               ) AS items
        FROM orders o
        LEFT JOIN order_items oi ON oi.order_id = o.id
        WHERE o.user_id = $1
        GROUP BY o.id
        ORDER BY o.created_at DESC
        LIMIT 25
        """,
        user_id,
    )
    return [_order_with_items(row) for row in rows]


async def list_all_orders() -> list[dict[str, Any]]:
    """All orders, newest first, with the owning user's email/name. For the chef."""
    pool = await get_pool()
    rows = await pool.fetch(
        """
        SELECT o.id, o.session_id, o.user_id, o.customer_name, o.status,
               o.total, o.created_at, u.email AS user_email, u.name AS user_name,
               COALESCE(
                 json_agg(
                   json_build_object('menu_item_id', oi.menu_item_id,
                                     'name', oi.name,
                                     'price', oi.price,
                                     'quantity', oi.quantity)
                 ) FILTER (WHERE oi.order_id IS NOT NULL),
                 '[]'
               ) AS items
        FROM orders o
        LEFT JOIN users u ON u.id = o.user_id
        LEFT JOIN order_items oi ON oi.order_id = o.id
        GROUP BY o.id, u.email, u.name
        ORDER BY o.created_at DESC
        LIMIT 100
        """
    )
    return [_order_with_items(row) for row in rows]


def _order_with_items(row: asyncpg.Record) -> dict[str, Any]:
    data = dict(row)
    raw_items = data.get("items")
    if isinstance(raw_items, str):
        data["items"] = _serializable(json.loads(raw_items)) if raw_items else []
    return _serializable(data)


# ---------------------------------------------------------------------------
# Short-term memory (per-session conversation)
# ---------------------------------------------------------------------------


async def load_session_messages(session_id: str) -> list[dict[str, Any]]:
    pool = await get_pool()
    row = await pool.fetchrow(
        "SELECT messages FROM sessions WHERE session_id = $1", session_id
    )
    if row is None:
        return []
    return json.loads(row["messages"])


async def save_session_messages(
    session_id: str, messages: list[dict[str, Any]]
) -> None:
    pool = await get_pool()
    await pool.execute(
        "INSERT INTO sessions (session_id, messages, updated_at) "
        "VALUES ($1, $2::jsonb, NOW()) "
        "ON CONFLICT (session_id) "
        "DO UPDATE SET messages = sessions.messages || EXCLUDED.messages, updated_at = NOW()",
        session_id,
        json.dumps(messages),
    )
