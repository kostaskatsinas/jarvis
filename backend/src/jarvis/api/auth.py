import time
from collections import defaultdict, deque

import structlog
from fastapi import APIRouter, Header, HTTPException, Request, Response
from pydantic import BaseModel
from sqlalchemy import select

from jarvis.config import get_settings
from jarvis.core.security import (
    ACCESS,
    REFRESH,
    InvalidToken,
    create_token,
    decode_token,
    hash_password,
    verify_password,
)
from jarvis.db.models import User
from jarvis.db.session import get_sessionmaker

log = structlog.get_logger()
router = APIRouter(prefix="/api/auth", tags=["auth"])

REFRESH_COOKIE = "jarvis_refresh"

# Brute-force throttle on login, per client IP. In-memory is fine: one
# backend process, and a restart resetting the window is harmless.
_LOGIN_MAX_ATTEMPTS = 5
_LOGIN_WINDOW_SECONDS = 60
_attempts: dict[str, deque] = defaultdict(deque)


def _throttle(ip: str) -> None:
    now = time.monotonic()
    window = _attempts[ip]
    while window and now - window[0] > _LOGIN_WINDOW_SECONDS:
        window.popleft()
    if len(window) >= _LOGIN_MAX_ATTEMPTS:
        raise HTTPException(status_code=429, detail="too many login attempts, wait a minute")
    window.append(now)


class LoginRequest(BaseModel):
    email: str
    password: str


def _issue_tokens(response: Response, email: str) -> dict:
    settings = get_settings()
    access = create_token(email, ACCESS, settings.access_token_ttl_minutes * 60)
    refresh = create_token(email, REFRESH, settings.refresh_token_ttl_days * 86400)
    response.set_cookie(
        REFRESH_COOKIE,
        refresh,
        max_age=settings.refresh_token_ttl_days * 86400,
        httponly=True,
        secure=settings.env == "prod",
        samesite="strict",
        path="/api/auth",
    )
    return {"access_token": access, "token_type": "bearer"}


@router.post("/login")
async def login(body: LoginRequest, request: Request, response: Response) -> dict:
    _throttle(request.client.host if request.client else "unknown")
    async with get_sessionmaker()() as session:
        user = (
            await session.execute(select(User).where(User.email == body.email))
        ).scalar_one_or_none()
    if user is None or not verify_password(user.password_hash, body.password):
        log.warning("login_failed", email=body.email)
        raise HTTPException(status_code=401, detail="invalid credentials")
    log.info("login_succeeded", email=body.email)
    return _issue_tokens(response, user.email)


@router.post("/refresh")
async def refresh(request: Request, response: Response) -> dict:
    token = request.cookies.get(REFRESH_COOKIE)
    if not token:
        raise HTTPException(status_code=401, detail="no refresh token")
    try:
        email = decode_token(token, REFRESH)
    except InvalidToken:
        raise HTTPException(status_code=401, detail="invalid refresh token")
    return _issue_tokens(response, email)


@router.post("/logout")
async def logout(response: Response) -> dict:
    response.delete_cookie(REFRESH_COOKIE, path="/api/auth")
    return {"ok": True}


async def require_user(authorization: str | None = Header(None)) -> str:
    """Dependency protecting REST routes. Returns the user's email."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="missing bearer token")
    try:
        return decode_token(authorization.removeprefix("Bearer "), ACCESS)
    except InvalidToken:
        raise HTTPException(status_code=401, detail="invalid or expired token")


@router.get("/me")
async def me(authorization: str | None = Header(None)) -> dict:
    return {"email": await require_user(authorization)}


async def bootstrap_admin() -> None:
    """Create the single user from JARVIS_ADMIN_EMAIL/_PASSWORD if the users
    table is empty. Runs at startup; changing the password later means
    updating the row (or dropping it and rebooting)."""
    settings = get_settings()
    if not (settings.admin_email and settings.admin_password):
        return
    async with get_sessionmaker()() as session:
        existing = (await session.execute(select(User.id).limit(1))).scalar_one_or_none()
        if existing is not None:
            return
        session.add(
            User(email=settings.admin_email, password_hash=hash_password(settings.admin_password))
        )
        await session.commit()
        log.info("admin_bootstrapped", email=settings.admin_email)
