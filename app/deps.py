"""Shared FastAPI dependencies for authentication / authorization."""

from __future__ import annotations

from typing import Any

import jwt as pyjwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.db import postgres
from app.security import decode_access_token

_bearer = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> dict[str, Any]:
    if credentials is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated")
    try:
        payload = decode_access_token(credentials.credentials)
        user = await postgres.get_user_by_id(int(payload["sub"]))
    except (pyjwt.PyJWTError, ValueError, TypeError):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired token")
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "User not found")
    return user


async def require_chef(
    user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    if user["role"] != "chef":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Chef access required")
    return user
