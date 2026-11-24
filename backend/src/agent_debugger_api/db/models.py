"""PostgreSQL control-plane tables. Schema changes go through an Alembic migration."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, Text, UniqueConstraint, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, validates

from agent_debugger_api.db.base import Base


def normalize_email(email: str) -> str:
    """The stored and looked-up form of an email: stripped and lowercased."""
    return email.strip().lower()


class User(Base):
    """One account = one project. `project_id` scopes every durable span the user's key writes.

    Only hashes are stored: `password_hash` (argon2) and `key_hash` (SHA-256 of
    the API key). `key_prefix` is the key's first 12 characters, for display.
    """

    __tablename__ = "users"
    __table_args__ = (
        UniqueConstraint("email", name="uq_users_email"),
        UniqueConstraint("project_id", name="uq_users_project_id"),
        UniqueConstraint("key_hash", name="uq_users_key_hash"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    email: Mapped[str] = mapped_column(Text)
    name: Mapped[str] = mapped_column(Text)
    password_hash: Mapped[str] = mapped_column(Text)
    project_id: Mapped[UUID] = mapped_column(Uuid)
    key_prefix: Mapped[str] = mapped_column(Text)
    key_hash: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    @validates("email")
    def _normalize_email(self, _key: str, value: str) -> str:
        return normalize_email(value)
