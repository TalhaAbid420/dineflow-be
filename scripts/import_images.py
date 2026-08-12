"""Import menu item pictures into the database.

Usage:
    uv run scripts/import_images.py                  # read dineflow-be/images/
    uv run scripts/import_images.py --dir <folder>   # read another folder
    uv run scripts/import_images.py --force          # overwrite existing images

Reads the image files, maps each one to the menu items it depicts (see
``app/db/images.py`` ``IMAGE_MAP``), and stores the bytes in PostgreSQL so the
chat UI can show a picture next to every dish.
"""

from __future__ import annotations

import argparse
import asyncio

from app.db import images, postgres


async def main() -> None:
    parser = argparse.ArgumentParser(description="Import menu images into the DB")
    parser.add_argument("--dir", default=None, help="Folder to read images from")
    parser.add_argument("--force", action="store_true", help="Overwrite existing images")
    args = parser.parse_args()

    await postgres.init_db()
    updated = await images.import_images(args.dir, force=args.force)
    await postgres.close_db()
    print(f"Imported images for {updated} menu items.")


if __name__ == "__main__":
    asyncio.run(main())
