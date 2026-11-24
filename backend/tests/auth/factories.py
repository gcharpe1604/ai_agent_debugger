"""Users and helpers for auth tests."""

import base64
import json
from http.cookies import SimpleCookie
from uuid import uuid4

from itsdangerous import TimestampSigner

from agent_debugger_api.auth.settings import SESSION_COOKIE, get_auth_settings
from agent_debugger_api.db.models import User
from agent_debugger_api.ingest.settings import DEFAULT_PROJECT_ID


def make_user(**overrides) -> User:
    """A transient User (never stored) for app.dependency_overrides of current_user / ingest_user."""
    fields = {
        "id": uuid4(),
        "email": "ada@example.com",
        "name": "Ada",
        "password_hash": "unused",
        "project_id": DEFAULT_PROJECT_ID,
        "key_prefix": "adbg_sk_test",
        "key_hash": "0" * 64,
    }
    fields.update(overrides)
    return User(**fields)


def session_cookie(response) -> SimpleCookie | None:
    """The adbg_session morsel of a response's Set-Cookie, or None."""
    for header in response.headers.get_list("set-cookie"):
        cookie = SimpleCookie()
        cookie.load(header)
        if SESSION_COOKIE in cookie:
            return cookie[SESSION_COOKIE]
    return None


def session_data(response) -> dict:
    """What SessionMiddleware stored in the cookie: checks its signature with SESSION_SECRET and decodes it."""
    signer = TimestampSigner(get_auth_settings().session_secret.get_secret_value())
    data = signer.unsign(session_cookie(response).value.encode())
    return json.loads(base64.b64decode(data))
