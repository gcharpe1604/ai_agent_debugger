"""Session and sign-up settings, from the environment or the repo-root `.env`."""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

from agent_debugger_api.config import PROJECT_ROOT

SESSION_COOKIE = "adbg_session"
SESSION_MAX_AGE_S = 7 * 24 * 60 * 60


class AuthSettings(BaseSettings):
    # Signs the session cookie. Required, at least 32 characters: the app does not
    # start without it.
    session_secret: SecretStr = Field(min_length=32)
    # True when the UI is served over https: the cookie then gets the Secure flag.
    session_cookie_secure: bool = False
    # False turns POST /api/v1/auth/register off (403); scripts/create_user.py still works.
    allow_signup: bool = True

    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_auth_settings() -> AuthSettings:
    return AuthSettings()
