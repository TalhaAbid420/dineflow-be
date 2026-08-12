"""Menu images: served straight from the database so the chat UI can show pictures."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response

from app.db import postgres

router = APIRouter(prefix="/menu", tags=["menu"])


@router.get("/{item_id}/image")
async def menu_item_image(item_id: int) -> Response:
    """Return the stored picture for a menu item (raw bytes)."""
    image = await postgres.get_menu_item_image(item_id)
    if image is None:
        raise HTTPException(status_code=404, detail="No image for this menu item")
    return Response(
        content=image["data"],
        media_type=image["mime"],
        headers={"Cache-Control": "public, max-age=3600"},
    )
