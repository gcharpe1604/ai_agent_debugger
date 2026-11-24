"""Who is calling: the two authentication dependencies. Written by the user (handoff action 6).

Contract the routes and tests rely on:

current_user
    The user of the session cookie: `request.session["user_id"]` (set by
    POST /auth/register and /auth/login as `str(user.id)`). No session, an
    unknown user or a malformed value -> HTTPException 401.
    Used by GET /auth/me, POST /auth/key/rotate and every GET /projects... route.

ingest_user
    The user whose API key is in `Authorization: Bearer <key>`. Look the key up
    by `hash_key(key)` against `users.key_hash` (auth/security.py). Missing or
    malformed header, unknown or rotated key -> HTTPException 401.
    Used by POST /api/v1/traces; it runs before the request body is read.

Both return a `User` from `db`, the request's shared session (db/deps.py).
"""

from __future__ import annotations
from uuid import UUID

from fastapi import Depends, Request, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from agent_debugger_api.auth.security import KEY_PREFIX, hash_key
from agent_debugger_api.db.deps import get_db
from agent_debugger_api.db.models import User


def _not_authenticated() -> HTTPException:
    return HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated")


def _bad_key() -> HTTPException:
    return HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or missing API key", headers={"WWW-Authenticate": "Bearer"})


async def current_user(request: Request, db: AsyncSession = Depends(get_db)) -> User:
    raw = request.session.get("user_id")
    if raw is None:
        raise _not_authenticated()
    try:
        user = await db.get(User, UUID(raw))
    except ValueError:
        user = None
    if user is None:
        request.session.clear()
        raise _not_authenticated()
    return user


async def ingest_user(request: Request, db: AsyncSession = Depends(get_db)) -> User:
    schema, _, key = request.headers.get("authorization", "").partition(" ")
    key = key.strip()
    if schema.lower() != "bearer" or not key.startswith(KEY_PREFIX):
        raise _bad_key()
    try:
        user = await db.scalar(select(User).where(User.key_hash == hash_key(key)))
    except (SQLAlchemyError, OSError):
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, "Auth store unavailable; retry the batch.",
            headers={"Retry-After": "1"}
        ) from None
    if user is None:
        raise _bad_key()
    return user
