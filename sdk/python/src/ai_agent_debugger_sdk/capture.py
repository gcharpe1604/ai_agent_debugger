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


# Hard maximum for one payload. Three payloads, each at most doubled when the
# JSON text is embedded as a JSON string, stay under the 1 MiB Kafka record
# limit with room for the rest of the span (clickhouse-span-record.md §9).
MAX_PAYLOAD_BYTES = 131_072

# Room kept for a value before a key or list item is started: the longest
# marker, "[unsupported]" with its quotes, is 15 bytes.
_MARKER_ROOM = 16


def _escaped(value: str) -> int:
    """Bytes of the string's content inside ASCII-escaped JSON, without quotes."""
    return len(json.dumps(value, ensure_ascii=True)) - 2


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
    # Exception type and message as the error payload (durable export only).
    capture_errors: bool = True

    def __post_init__(self) -> None:
        for name in ("capture_inputs", "capture_outputs", "capture_errors"):
            if type(getattr(self, name)) is not bool:
                raise ValueError(f"{name} must be a bool")
        for name, minimum, maximum in (
            ("max_payload_bytes", 64, MAX_PAYLOAD_BYTES),
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
    """Builds a JSON-safe copy whose serialized form fits `max_payload_bytes`.

    `remaining` counts bytes of the final ASCII-escaped JSON, including quotes,
    commas, colons and brackets, so the result is cut inside the structure
    (strings clipped to a prefix, later items dropped) and stays valid JSON.
    """

    def __init__(self, config: CaptureConfig) -> None:
        self.config = config
        self.nodes = 0
        self.remaining = config.max_payload_bytes
        self.active: set[int] = set()
        self.redacted = False
        self.truncated = False
        self.unsupported = False

    def _take(self, cost: int) -> None:
        self.remaining = max(0, self.remaining - cost)

    def _marker(self, text: str, flag: str) -> str:
        setattr(self, flag, True)
        self._take(len(text) + 2)
        return text

    def _string(self, value: str) -> str:
        budget = max(0, self.remaining - 2)
        piece = value[:budget]  # every character costs at least one byte
        cost = _escaped(piece)
        if cost > budget:
            # Escapes cost 2, 6 or 12 bytes: find the longest prefix that fits.
            low, high = 0, len(piece)
            while low < high:
                middle = (low + high + 1) // 2
                if _escaped(piece[:middle]) <= budget:
                    low = middle
                else:
                    high = middle - 1
            piece = piece[:low]
            cost = _escaped(piece)
        if len(piece) != len(value):
            self.truncated = True
        self._take(cost + 2)
        return piece

    def visit(self, value: Any, depth: int = 0) -> Any:
        if self.nodes >= self.config.max_nodes:
            return self._marker("[truncated]", "truncated")
        self.nodes += 1
        if depth > self.config.max_depth:
            return self._marker("[truncated]", "truncated")
        kind = type(value)
        if value is None or kind is bool:
            self._take(5)
            return value
        if kind is str:
            return self._string(value)
        if kind is int:
            # Prevent enormous integer conversion, including Python's digit-limit error.
            if value.bit_length() > min(max(0, self.remaining - 2) * 3, 1024):
                return self._marker("[truncated]", "truncated")
            self._take(len(json.dumps(value)))
            return value
        if kind is float and math.isfinite(value):
            text = json.dumps(value)
            if len(text) > self.remaining:
                return self._marker("[truncated]", "truncated")
            self._take(len(text))
            return value
        if kind not in (dict, list, tuple):
            return self._marker("[unsupported]", "unsupported")
        if id(value) in self.active:
            return self._marker("[circular]", "truncated")
        self.active.add(id(value))
        self._take(2)
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
                    # Quotes, colon and comma, plus room for at least a marker value.
                    room = self.remaining - 4 - _MARKER_ROOM
                    if len(key) > room or _escaped(key) > room:
                        self.nodes += 1
                        self.truncated = True
                        continue
                    self._take(_escaped(key) + 4)
                    if self.config.is_secret(key):
                        self.nodes += 1
                        result[key] = self._marker("[redacted]", "redacted")
                    else:
                        result[key] = self.visit(item, depth + 1)
                return result
            result = []
            for item in value:
                if self.nodes >= self.config.max_nodes or self.remaining <= _MARKER_ROOM:
                    self.truncated = True
                    break
                self._take(1)
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
        # Not expected: the sanitizer budgets every serialized byte.
        text = '"[truncated]"'
        sanitizer.truncated = True
    return CapturedValue(
        text, sanitizer.redacted, sanitizer.truncated, sanitizer.unsupported
    )
