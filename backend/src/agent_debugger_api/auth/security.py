"""Password and API-key primitives. No I/O; callers decide where hashes are stored."""

from __future__ import annotations

import hashlib
import secrets

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

KEY_PREFIX = "adbg_sk_"

_hasher = PasswordHasher()


def hash_password(password: str) -> str:
    """argon2id hash (argon2-cffi defaults), salt included in the returned string."""
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    """True when `password` matches; False for a wrong password or a malformed hash. Never raises."""
    try:
        return _hasher.verify(password_hash, password)
    except (VerificationError, InvalidHashError):
        return False


def hash_key(key: str) -> str:
    """SHA-256 hex of an API key: what `users.key_hash` stores and lookups compare."""
    return hashlib.sha256(key.encode()).hexdigest()


def new_key() -> tuple[str, str, str]:
    """A fresh API key as (key, prefix, key_hash). Show `key` once; store only prefix and hash."""
    key = KEY_PREFIX + secrets.token_urlsafe(32)
    return key, key[:12], hash_key(key)
