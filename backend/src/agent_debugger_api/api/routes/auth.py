"""Accounts and sessions: /api/v1/auth.

    POST /auth/register     {name, email, password} -> 201 {user, api_key}; starts a session
    POST /auth/login        {email, password} -> 204; starts a session
    POST /auth/logout       -> 204; ends the session
    GET  /auth/me           -> {id, name, email, key_prefix}
    POST /auth/key/rotate   -> {api_key, key_prefix}; the old key stops working

The session is a signed cookie (SessionMiddleware, main.py) holding only
`user_id`. The API key is shown once, at register and rotate; only its
SHA-256 is stored. Errors are {"detail": ...}.
"""

from __future__ import annotations

import asyncio
import secrets
from functools import lru_cache

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.exception_handlers import request_validation_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from agent_debugger_api.auth.deps import current_user
from agent_debugger_api.auth.schemas import (
    KeyOut,
    LoginIn,
    RegisterIn,
    RegisterOut,
    UserOut,
)
from agent_debugger_api.auth.security import hash_password, new_key, verify_password
from agent_debugger_api.auth.settings import AuthSettings, get_auth_settings
from agent_debugger_api.auth.users import EmailTaken, create_user
from agent_debugger_api.db.deps import get_db
from agent_debugger_api.db.models import User, normalize_email

router = APIRouter(prefix="/auth", tags=["auth"])

PATH_PREFIX = "/api/v1/auth/"
INVALID_LOGIN = "Invalid email or password"


@lru_cache(maxsize=1)
def _dummy_hash() -> str:
    # An unknown email still costs one argon2 verify, so its 401 takes as long as a wrong password's.
    return hash_password(secrets.token_urlsafe(16))


def _start_session(request: Request, user: User) -> None:
    request.session.clear()
    request.session["user_id"] = str(user.id)


def signup_allowed(settings: AuthSettings = Depends(get_auth_settings)) -> None:
    if not settings.allow_signup:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Sign-up is disabled")


async def validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
    """422 without the submitted values for /auth requests (they contain passwords); default elsewhere."""
    if not request.url.path.startswith(PATH_PREFIX):
        return await request_validation_exception_handler(request, exc)
    errors = [{"loc": list(e["loc"]), "msg": e["msg"], "type": e["type"]} for e in exc.errors()]
    return JSONResponse(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, content={"detail": errors})


@router.post("/register", status_code=status.HTTP_201_CREATED, dependencies=[Depends(signup_allowed)])
async def register(body: RegisterIn, request: Request, db: AsyncSession = Depends(get_db)) -> RegisterOut:
    try:
        user, key = await create_user(db, name=body.name, email=body.email, password=body.password)
    except EmailTaken:
        raise HTTPException(status.HTTP_409_CONFLICT, "Email already registered") from None
    _start_session(request, user)
    return RegisterOut(user=UserOut.model_validate(user), api_key=key)


@router.post("/login", status_code=status.HTTP_204_NO_CONTENT)
async def login(body: LoginIn, request: Request, db: AsyncSession = Depends(get_db)) -> Response:
    user = await db.scalar(select(User).where(User.email == normalize_email(body.email)))
    password_hash = user.password_hash if user is not None else _dummy_hash()
    matches = await asyncio.to_thread(verify_password, body.password, password_hash)
    if user is None or not matches:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, INVALID_LOGIN)
    _start_session(request, user)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(request: Request) -> Response:
    request.session.clear()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/me")
async def me(user: User = Depends(current_user)) -> UserOut:
    return UserOut.model_validate(user)


@router.post("/key/rotate")
async def rotate_key(user: User = Depends(current_user), db: AsyncSession = Depends(get_db)) -> KeyOut:
    key, prefix, key_hash = new_key()
    await db.execute(update(User).where(User.id == user.id).values(key_prefix=prefix, key_hash=key_hash))
    await db.commit()
    return KeyOut(api_key=key, key_prefix=prefix)
