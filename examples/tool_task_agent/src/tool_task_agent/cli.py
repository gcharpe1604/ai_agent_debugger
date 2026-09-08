import argparse
import json
import sys

from .scenarios import DATA_DIR, build_agent, load_scenario
from .tools import ToolError


def main() -> int:
    parser = argparse.ArgumentParser(description="Deterministic tool-using task agent")
    subcommands = parser.add_subparsers(dest="command", required=True)
    subcommands.add_parser("list", help="List selectable scenarios")
    run = subcommands.add_parser("run", help="Run a fresh scenario")
    run.add_argument("scenario_id")
    run.add_argument("--json", action="store_true")
    args = parser.parse_args()
    if args.command == "list":
        print("\n".join(path.stem for path in sorted(DATA_DIR.glob("*.json"))))
        return 0
    try:
        scenario = load_scenario(args.scenario_id)
        result = build_agent(scenario).run(scenario.request)
    except (OSError, ValueError, ToolError) as exc:
        print(f"Cannot run scenario: {exc}", file=sys.stderr)
        return 1
    if args.json:
        print(
            json.dumps(
                {"scenario_id": scenario.scenario_id, **result.model_dump()},
                indent=2,
                sort_keys=True,
            )
        )
    else:
        print(f"{scenario.scenario_id}: {result.request}")
        for event in result.events:
            attempt = f" attempt={event.attempt}" if event.attempt else ""
            error = f" ({event.error_code})" if event.error_code else ""
            print(
                f"{event.sequence:02} {event.step_id}/{event.operation}{attempt}: {event.status}{error}"
            )
        print(result.final_response.message)
    # An intentionally failed workload is a successful CLI execution, as in RAG.
    return 0
