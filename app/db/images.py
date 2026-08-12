"""Menu item images.

Pictures live inside the database (``menu_items.image_data``) and are served
through ``GET /api/menu/{item_id}/image``. This module imports the bundled
image files and associates each one with the menu items it depicts, so the
chat UI can show a picture next to every dish. To add more pictures later,
drop a file into ``dineflow-be/images/`` and run::

    uv run scripts/import_images.py

and map the new filename to menu item names in ``IMAGE_MAP``.
"""

from __future__ import annotations

import logging
from pathlib import Path

from app.db import postgres

logger = logging.getLogger("dineflow.images")

# filename in the images folder -> menu item names it depicts.
# Add new files here as more pictures are provided.
IMAGE_MAP: dict[str, list[str]] = {
    "pizza 🍕.jpg": ["Margherita Pizza", "Pepperoni Pizza"],
    "Burger.jpg": ["Veggie Burger", "Chicken Burger"],
    "Fries, bread, salad.jpg": ["Garlic Bread", "Crispy Fries", "Caesar Salad"],
    "chocolate cake.jpg": ["Chocolate Brownie", "Cheesecake"],
    "coffee.jpg": ["Cold Coffee"],
    "lemonade.jpg": ["Fresh Lemonade"],
}

DEFAULT_IMAGE_DIR = Path(__file__).resolve().parents[2] / "images"


def _mime_for(path: Path) -> str:
    return "image/png" if path.suffix.lower() == ".png" else "image/jpeg"


async def import_images(dir_path: str | Path | None = None, force: bool = False) -> int:
    """Import the bundled menu images into the database (idempotent).

    Returns the number of menu items updated. Files without a matching menu
    item are skipped with a warning.
    """
    img_dir = Path(dir_path) if dir_path else DEFAULT_IMAGE_DIR
    if not img_dir.is_dir():
        logger.info("No image folder at %s — skipping image import", img_dir)
        return 0

    updated = 0
    for filename, item_names in IMAGE_MAP.items():
        path = img_dir / filename
        if not path.is_file():
            logger.warning("Image file not found: %s", path)
            continue
        data = path.read_bytes()
        mime = _mime_for(path)
        for name in item_names:
            count = await postgres.set_menu_item_image_by_name(name, data, mime, force=force)
            if count:
                updated += count
                logger.info("Attached %s to menu item '%s'", filename, name)
    logger.info("Imported images for %d menu items", updated)
    return updated
