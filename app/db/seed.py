"""Seeds the sample menu and the chef account on first start."""

from __future__ import annotations

import logging

from app.config import get_settings
from app.db import postgres
from app.security import hash_password

logger = logging.getLogger("dineflow.seed")

SAMPLE_MENU = [
    ("Margherita Pizza", "Classic tomato, mozzarella, fresh basil", 9.99, "Mains"),
    ("Pepperoni Pizza", "Tomato, mozzarella, pepperoni", 11.99, "Mains"),
    ("Veggie Burger", "Grilled veggie patty, lettuce, tomato, house sauce", 8.49, "Mains"),
    ("Chicken Burger", "Grilled chicken breast, cheddar, lettuce", 9.49, "Mains"),
    ("Garlic Bread", "Toasted baguette, garlic butter, herbs", 4.49, "Starters"),
    ("Crispy Fries", "Golden fries with ketchup", 3.99, "Starters"),
    ("Caesar Salad", "Romaine, parmesan, croutons, caesar dressing", 6.99, "Starters"),
    ("Cold Coffee", "Iced coffee with milk and sugar", 3.49, "Beverages"),
    ("Fresh Lemonade", "Freshly squeezed lemons, mint, ice", 2.99, "Beverages"),
    ("Chocolate Brownie", "Warm brownie with vanilla ice cream", 4.99, "Desserts"),
    ("Cheesecake", "Creamy baked cheesecake with berry compote", 5.49, "Desserts"),
]


async def seed_menu_if_empty() -> None:
    pool = await postgres.get_pool()
    count = await pool.fetchval("SELECT COUNT(*) FROM menu_items")
    if count and count > 0:
        return
    async with pool.acquire() as conn:
        async with conn.transaction():
            await conn.executemany(
                "INSERT INTO menu_items (name, description, price, category) "
                "VALUES ($1, $2, $3, $4)",
                SAMPLE_MENU,
            )
    logger.info("Seeded %d menu items", len(SAMPLE_MENU))


async def seed_chef_user() -> None:
    """Create the hardcoded chef account if it doesn't exist yet."""
    settings = get_settings()
    existing = await postgres.get_user_by_email(settings.chef_email)
    if existing:
        return
    user = await postgres.create_user(
        settings.chef_email,
        hash_password(settings.chef_password),
        name="Dineflow Chef",
        role="chef",
    )
    if user:
        logger.info("Seeded chef user: %s", settings.chef_email)
