"""Creating a user: shared by POST /api/v1/auth/register and scripts/create_user.py."""

from __future__ import annotations

import asyncio
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from agent_debugger_api.auth.security import hash_password, new_key
from agent_debugger_api.db.models import User
from agent_debugger_api.ingest.settings import get_ingest_settings


class EmailTaken(Exception):
    """Another user already has this email (after normalization)."""


def _violated_constraint(exc: IntegrityError) -> str | None:
    # asyncpg's UniqueViolationError, wrapped by SQLAlchemy's DBAPI adapter.
    return getattr(exc.orig.__cause__, "constraint_name", None)


async def create_user(db: AsyncSession, *, name: str, email: str, password: str) -> tuple[User, str]:
    """Insert a user; return it with its API key (the only time the key exists in clear).

    The first user ever gets DEFAULT_PROJECT_ID, so traces written before
    accounts existed stay readable; every later user gets a new uuid4. If the
    project_id is taken (two first users at once, or a uuid4 collision), the
    insert is retried once with a new uuid4. Email uniqueness is the unique
    constraint, so a concurrent duplicate is EmailTaken too.
    """
    password_hash = await asyncio.to_thread(hash_password, password)  # argon2 is CPU-bound
    key, prefix, key_hash = new_key()
    first = await db.scalar(select(User.id).limit(1)) is None
    project_id = get_ingest_settings().default_project_id if first else uuid4()
    for attempt in range(2):
        user = User(
            name=name,
            email=email,
            password_hash=password_hash,
            project_id=project_id,
            key_prefix=prefix,
            key_hash=key_hash,
        )
        db.add(user)
        try:
            await db.commit()
        except IntegrityError as exc:
            await db.rollback()
            constraint = _violated_constraint(exc)
            if constraint == "uq_users_email":
                raise EmailTaken from None
            if constraint == "uq_users_project_id" and attempt == 0:
                project_id = uuid4()
                continue
            raise
        return user, key
    raise AssertionError("unreachable: the second attempt returns or raises")
