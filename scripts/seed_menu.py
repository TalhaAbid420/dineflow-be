"""Manual menu seeder: uv run scripts/seed_menu.py"""

from __future__ import annotations

import asyncio

from app.db import postgres, seed


async def main() -> None:
    await postgres.init_db()
    await seed.seed_menu_if_empty()
    await postgres.close_db()
    print("Menu seeded.")


if __name__ == "__main__":
    asyncio.run(main())
