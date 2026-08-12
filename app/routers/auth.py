"""Authentication: register, login, and current-user endpoints."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.db import postgres
from app.deps import get_current_user
from app.security import create_access_token, hash_password, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])


class RegisterRequest(BaseModel):
    name: str = ""
    email: str
    password: str


class LoginRequest(BaseModel):
    email: str
    password: str


def _public_user(user: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in user.items() if k != "password_hash"}


def _issue_token(user: dict[str, Any]) -> dict[str, Any]:
    token = create_access_token(user["id"], user["role"])
    return {"token": token, "user": _public_user(user)}


@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register(req: RegisterRequest) -> dict:
    email = req.email.strip().lower()
    if "@" not in email or len(email) < 5:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Enter a valid email address")
    if len(req.password) < 8:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Password must be at least 8 characters")

    user = await postgres.create_user(
        email, hash_password(req.password), name=req.name.strip(), role="customer"
    )
    if user is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "An account with this email already exists")
    return _issue_token(user)


@router.post("/login")
async def login(req: LoginRequest) -> dict:
    email = req.email.strip().lower()
    user = await postgres.get_user_by_email(email)
    if user is None or not verify_password(req.password, user["password_hash"]):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid email or password")
    return _issue_token(user)


@router.get("/me")
async def me(user: dict[str, Any] = Depends(get_current_user)) -> dict[str, Any]:
    return _public_user(user)
