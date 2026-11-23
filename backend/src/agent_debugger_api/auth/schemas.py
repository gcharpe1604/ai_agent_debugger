"""Request and response bodies of /api/v1/auth."""

from __future__ import annotations

import re
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator

from agent_debugger_api.db.models import normalize_email

# A format check, not deliverability: one @, no spaces, a dot in the domain.
_EMAIL = re.compile(r"[^@\s]+@[^@\s]+\.[^@\s]+")
MAX_EMAIL = 254

Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=80)]


class RegisterIn(BaseModel):
    name: Name
    email: str
    password: Annotated[str, Field(min_length=8)]

    @field_validator("email")
    @classmethod
    def _email(cls, value: str) -> str:
        value = normalize_email(value)
        if len(value) > MAX_EMAIL or not _EMAIL.fullmatch(value):
            raise ValueError("not a valid email address")
        return value


class LoginIn(BaseModel):
    # No format or length rules: a malformed value gets the same 401 as a wrong password.
    email: str
    password: str


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    email: str
    key_prefix: str


class RegisterOut(BaseModel):
    user: UserOut
    api_key: str  # shown once; only its hash is stored


class KeyOut(BaseModel):
    api_key: str  # shown once; only its hash is stored
    key_prefix: str
