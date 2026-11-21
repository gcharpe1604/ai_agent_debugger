"""Investigator: one controlled LLM call over a bounded snapshot, then deterministic grounding.

Design: `docs/proposals/investigator.md` (a proposal; only D1 and D7 are decided).
This package replaces the rule-engine scaffold in `analysis/`, which stays
empty and unused (proposal C12).

    snapshot.py   bounded input snapshot and deterministic facts (§3, §4)
    schema.py     structured output of the model (§5)
    provider.py   provider port and the scripted stub (§7)
    attempts.py   analysis attempt record and store port
    engine.py     attempt lifecycle (§2)
    grounding.py  grounding rules (§6): signatures only, written by the user
"""
