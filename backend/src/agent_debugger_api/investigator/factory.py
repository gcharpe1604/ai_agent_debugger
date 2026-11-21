"""Pick the investigator provider from `INVESTIGATOR_PROVIDER` (`bedrock` | `scripted`, default `scripted`)."""

from __future__ import annotations

import os
from collections.abc import Mapping

from .provider import InvestigatorProvider, ScriptedProvider

# What the default provider answers to every call: it abstains, and says why.
SCRIPTED_DEFAULT_OUTPUT = {
    "schema_version": 1,
    "verdict": "insufficient_evidence",
    "findings": [],
    "limitations": ["No model was called: INVESTIGATOR_PROVIDER is 'scripted'."],
}


def provider_from_env(environ: Mapping[str, str] | None = None) -> InvestigatorProvider:
    env = os.environ if environ is None else environ
    choice = (env.get("INVESTIGATOR_PROVIDER") or "scripted").strip().lower()
    if choice == "scripted":
        return ScriptedProvider([SCRIPTED_DEFAULT_OUTPUT], repeat_last=True)
    if choice == "bedrock":
        from .bedrock_provider import BedrockProvider

        return BedrockProvider.from_env(env)
    raise ValueError("INVESTIGATOR_PROVIDER must be 'bedrock' or 'scripted'")
