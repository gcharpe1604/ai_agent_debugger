"""Bounded capture of trusted built-in shapes, without application callbacks."""

import json
import math
from dataclasses import dataclass
from typing import Any

_SECRET_FIELDS = frozenset(
    {
        "password",
        "passwd",
        "secret",
        "token",
        "access_token",
        "refresh_token",
        "id_token",
        "api_key",
        "authorization",
        "proxy_authorization",
        "cookie",
        "set_cookie",
        "client_secret",
        "private_key",
        "x_api_key",
        "auth_token",
        "session_token",
        "credentials",
    }
)


def _normalize(key: str) -> str:
    return "".join(char for char in key.lower() if char.isalnum())


@dataclass(frozen=True)
class CaptureConfig:
    """Capture switches and limits; secret_fields extends the default denylist."""

    capture_inputs: bool = True
    capture_outputs: bool = True
    max_payload_bytes: int = 16_384
    max_depth: int = 8
    max_nodes: int = 512
    secret_fields: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for name in ("capture_inputs", "capture_outputs"):
            if type(getattr(self, name)) is not bool:
                raise ValueError(f"{name} must be a bool")
        for name, minimum, maximum in (
            ("max_payload_bytes", 64, 1_048_576),
            ("max_depth", 0, 32),
            ("max_nodes", 1, 10_000),
        ):
            value = getattr(self, name)
            if type(value) is not int or not minimum <= value <= maximum:
                raise ValueError(f"{name} must be an integer in [{minimum}, {maximum}]")
        if type(self.secret_fields) is not tuple or any(
            type(key) is not str or not key or len(key) > 256
            for key in self.secret_fields
        ):
            raise ValueError(
                "secret_fields must be a tuple of nonempty strings (at most 256 characters)"
            )

    def is_secret(self, key: str) -> bool:
        fields = {
            _normalize(field)
            for field in _SECRET_FIELDS | frozenset(self.secret_fields)
        }
        return _normalize(key) in fields or _normalize(key.rsplit(".", 1)[-1]) in fields


@dataclass(frozen=True)
class CapturedValue:
    text: str
    redacted: bool
    truncated: bool
    unsupported: bool


class _Sanitizer:
    def __init__(self, config: CaptureConfig) -> None:
        self.config = config
        self.nodes = 0
        self.remaining = config.max_payload_bytes
        self.active: set[int] = set()
        self.redacted = False
        self.truncated = False
        self.unsupported = False

    def visit(self, value: Any, depth: int = 0) -> Any:
        if self.nodes >= self.config.max_nodes:
            self.truncated = True
            return "[truncated]"
        self.nodes += 1
        if depth > self.config.max_depth:
            self.truncated = True
            return "[truncated]"
        kind = type(value)
        if value is None or kind is bool:
            return value
        if kind is str:
            clipped = value[: self.remaining]
            self.remaining -= len(clipped)
            if len(clipped) != len(value):
                self.truncated = True
            return clipped
        if kind is int:
            # Prevent enormous integer conversion, including Python's digit-limit error.
            if value.bit_length() > min(self.remaining * 3, 1024):
                self.truncated = True
                return "[truncated]"
            self.remaining = max(0, self.remaining - len(json.dumps(value)))
            return value
        if kind is float and math.isfinite(value):
            self.remaining = max(0, self.remaining - len(json.dumps(value)))
            return value
        if kind not in (dict, list, tuple):
            self.unsupported = True
            return "[unsupported]"
        if id(value) in self.active:
            self.truncated = True
            return "[circular]"
        self.active.add(id(value))
        try:
            if kind is dict:
                result = {}
                for key, item in value.items():
                    if self.nodes >= self.config.max_nodes:
                        self.truncated = True
                        break
                    if type(key) is not str:
                        self.nodes += 1
                        self.unsupported = True
                        continue
                    if len(key) > self.remaining:
                        self.nodes += 1
                        self.truncated = True
                        continue
                    self.remaining -= len(key)
                    if self.config.is_secret(key):
                        self.nodes += 1
                        self.redacted = True
                        result[key] = "[redacted]"
                    else:
                        result[key] = self.visit(item, depth + 1)
                return result
            result = []
            for item in value:
                if self.nodes >= self.config.max_nodes:
                    self.truncated = True
                    break
                result.append(self.visit(item, depth + 1))
            return result
        finally:
            self.active.remove(id(value))


def serialize_capture(value: Any, config: CaptureConfig) -> CapturedValue:
    sanitizer = _Sanitizer(config)
    safe_value = sanitizer.visit(value)
    # ASCII escapes support even lone surrogates and make bytes == string length.
    text = json.dumps(
        safe_value, ensure_ascii=True, allow_nan=False, separators=(",", ":")
    )
    if len(text) > config.max_payload_bytes:
        text = '"[truncated]"'
        sanitizer.truncated = True
    return CapturedValue(
        text, sanitizer.redacted, sanitizer.truncated, sanitizer.unsupported
    )
