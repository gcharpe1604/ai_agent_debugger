"""Provider port and the scripted stub (`docs/proposals/investigator.md` §7).

The real provider is undecided (handoff §1). A provider turns one request into
one response and does not validate the output: the engine does, which is what
lets a stub return invalid output on purpose.
"""

from __future__ import annotations

import copy
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal, Protocol, runtime_checkable

ProviderErrorKind = Literal["timeout", "rate_limited", "unavailable", "auth", "bad_response"]
# Retried once by the engine. `auth` and `bad_response` fail the same way again.
TRANSIENT_KINDS = frozenset({"timeout", "rate_limited", "unavailable"})


class ProviderError(Exception):
    """The investigator's own provider failed. Never a finding, never evidence.

    The engine stores `kind` only; the message stays in the process.
    """

    def __init__(self, kind: ProviderErrorKind, message: str = "") -> None:
        super().__init__(message or kind)
        self.kind = kind


@dataclass(frozen=True)
class InvestigationRequest:
    instructions: str  # fixed system text; its version is the engine's PROMPT_VERSION
    snapshot_json: str  # evidence; passed as data, never merged into the instructions
    output_schema: dict  # JSON Schema of InvestigatorOutput
    max_output_tokens: int
    timeout_s: float


@dataclass(frozen=True)
class ProviderResponse:
    output: dict | str  # a parsed object, or raw text the engine will parse
    input_tokens: int | None = None
    output_tokens: int | None = None
    latency_ms: int = 0


@runtime_checkable
class InvestigatorProvider(Protocol):
    """Synchronous, like TraceStore. Async callers use a thread."""

    name: str  # e.g. "stub-scripted", "bedrock", "openai-compatible"
    model_id: str

    def investigate(self, request: InvestigationRequest) -> ProviderResponse:
        """One model call. Raises ProviderError; returns the output unvalidated."""
        ...


class ScriptedProvider:
    """Test double: answers each call with the next item of `script`.

    An item is a `ProviderError` (raised), a `ProviderResponse` (returned), or
    a dict / str (returned as the response's output). Requests are recorded in
    `requests`. A call past the end of the script is a test bug and raises
    AssertionError, which the engine does not catch.
    """

    name = "stub-scripted"
    model_id = "scripted-1"

    def __init__(
        self, script: Sequence[ProviderError | ProviderResponse | dict | str], *, repeat_last: bool = False
    ) -> None:
        self._script = list(script)
        self._repeat_last = repeat_last
        self.requests: list[InvestigationRequest] = []

    def investigate(self, request: InvestigationRequest) -> ProviderResponse:
        self.requests.append(request)
        if len(self.requests) > len(self._script) and not (self._repeat_last and self._script):
            raise AssertionError(f"ScriptedProvider was called {len(self.requests)} times; the script has {len(self._script)} items")
        item = self._script[min(len(self.requests), len(self._script)) - 1]
        if isinstance(item, ProviderError):
            raise item
        if isinstance(item, ProviderResponse):
            return item
        return ProviderResponse(output=copy.deepcopy(item))
