"""Never let an editable install select a sibling checkout."""

import sys
from pathlib import Path

SOURCE = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SOURCE))

import ai_agent_debugger_sdk  # noqa: E402

if not Path(ai_agent_debugger_sdk.__file__).resolve().is_relative_to(SOURCE):
    raise RuntimeError("SDK tests imported a different checkout")
