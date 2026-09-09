import argparse
import json
import sys

from .tools import ToolError


def _ask(request):
    import httpx

    from .agent import TaskAgent
    from .live_model import LiveConfig, LiveModelClient, LiveResult
    from .tools import LocalTools

    config = LiveConfig.from_env()
    with httpx.Client() as client:
        result = TaskAgent(LiveModelClient(config, client), LocalTools).run(request)
        return LiveResult(**result.model_dump(), original_request=request)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Tool-using task agent")
    subcommands = parser.add_subparsers(dest="command", required=True)
    subcommands.add_parser("list", help="List selectable scenarios")
    run = subcommands.add_parser("run", help="Run a fresh scenario")
    run.add_argument("scenario_id")
    run.add_argument("--json", action="store_true")
    ask = subcommands.add_parser("ask", help="Use the configured live model")
    ask.add_argument("request")
    ask.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    if args.command == "list":
        from .scenarios import DATA_DIR

        print("\n".join(path.stem for path in sorted(DATA_DIR.glob("*.json"))))
        return 0
    try:
        if args.command == "ask":
            result = _ask(args.request)
        else:
            from .scenarios import build_agent, load_scenario

            scenario = load_scenario(args.scenario_id)
            result = build_agent(scenario).run(scenario.request)
    except (OSError, ValueError, ToolError) as exc:
        subject = "request" if args.command == "ask" else "scenario"
        print(f"Cannot run {subject}: {exc}", file=sys.stderr)
        return 1
    if args.json:
        payload = result.model_dump()
        if args.command == "run":
            payload = {"scenario_id": scenario.scenario_id, **payload}
        print(
            json.dumps(
                payload,
                indent=2,
                sort_keys=True,
            )
        )
    else:
        if args.command == "run":
            print(f"{scenario.scenario_id}: {result.request}")
        else:
            print(f"Request: {result.original_request}")
        for event in result.events:
            attempt = f" attempt={event.attempt}" if event.attempt else ""
            error = f" ({event.error_code})" if event.error_code else ""
            print(
                f"{event.sequence:02} {event.step_id}/{event.operation}{attempt}: {event.status}{error}"
            )
        print(result.final_response.message)
    # An intentionally failed workload is a successful CLI execution, as in RAG.
    return 0
