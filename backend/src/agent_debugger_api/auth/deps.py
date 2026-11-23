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

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from agent_debugger_api.db.deps import get_db
from agent_debugger_api.db.models import User


async def current_user(request: Request, db: AsyncSession = Depends(get_db)) -> User:
    raise NotImplementedError("current_user is not written yet (agent_debugger_api/auth/deps.py)")


async def ingest_user(request: Request, db: AsyncSession = Depends(get_db)) -> User:
    raise NotImplementedError("ingest_user is not written yet (agent_debugger_api/auth/deps.py)")
