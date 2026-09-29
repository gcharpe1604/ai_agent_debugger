import json
from typing import Any

from opentelemetry.trace import Span


class SpanHandle:
    def __init__(self, span: Span) -> None:
        self._span = span

    def set_input(self, value: Any) -> None:
        self._span.set_attribute(
            "debugger.input",
            self._serialize(value),
        )

    def set_output(self, value: Any) -> None:
        self._span.set_attribute(
            "debugger.output",
            self._serialize(value),
        )

    def set_attribute(self, key: str, value: str | int | float | bool) -> None:
        self._span.set_attribute(key, value)

    @staticmethod
    def _serialize(value: Any) -> str:
        try:
            return json.dumps(
                value,
                ensure_ascii=False,
                default=str,
            )
        except (TypeError, ValueError):
            return repr(value)