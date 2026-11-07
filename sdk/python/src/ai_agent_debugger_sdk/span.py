import math
from typing import Any

from opentelemetry.trace import Span

from ai_agent_debugger_sdk.capture import CaptureConfig, serialize_capture


class SpanHandle:
    def __init__(self, span: Span, capture: CaptureConfig | None = None) -> None:
        self._span = span
        self._capture = capture if capture is not None else CaptureConfig()
        self._captured: set[str] = set()

    def set_input(self, value: Any) -> None:
        self._set_capture("debugger.input", value, self._capture.capture_inputs)

    def set_output(self, value: Any) -> None:
        self._set_capture("debugger.output", value, self._capture.capture_outputs)

    def set_attribute(self, key: str, value: str | int | float | bool) -> None:
        try:
            if (
                type(key) is not str
                or not key
                or len(key) > self._capture.max_payload_bytes
            ):
                return
            if key == "debugger.input":
                self.set_input(value)
            elif key == "debugger.output":
                self.set_output(value)
            elif self._capture.is_secret(key):
                self._set_attribute(key, "[redacted]")
            elif type(value) in (str, int, float, bool):
                if type(value) is float and not math.isfinite(value):
                    return
                if type(value) is int and value.bit_length() > 1024:
                    return
                if type(value) is str and (
                    len(value) > self._capture.max_payload_bytes
                    or len(value.encode("utf-8", errors="replace"))
                    > self._capture.max_payload_bytes
                ):
                    value = "[truncated]"
                self._set_attribute(key, value)
        except Exception:
            # Never log captured values or exception text from application objects.
            return

    def _set_attribute(self, key: str, value: str | int | float | bool) -> None:
        try:
            self._span.set_attribute(key, value)
        except Exception:
            pass

    def _set_capture(self, key: str, value: Any, enabled: bool) -> None:
        flags = {
            "redacted": False,
            "truncated": False,
            "unsupported": False,
            "capture_error": False,
            "disabled": not enabled,
        }
        if enabled:
            try:
                captured = serialize_capture(value, self._capture)
                self._set_attribute(key, captured.text)
                self._captured.add(key)
                flags.update(
                    redacted=captured.redacted,
                    truncated=captured.truncated,
                    unsupported=captured.unsupported,
                )
            except Exception:
                if key in self._captured:
                    self._set_attribute(key, '"[capture unavailable]"')
                flags["capture_error"] = True
        for flag, present in flags.items():
            self._set_attribute(f"{key}.{flag}", present)
