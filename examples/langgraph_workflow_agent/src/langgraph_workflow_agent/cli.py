import argparse
import sys


def _ask(text):
    import httpx

    from .agent import WorkflowAgent
    from .live_model import LiveConfig, LiveModelClient, LiveResult

    config = LiveConfig.from_env()
    with httpx.Client() as client:
        model = LiveModelClient(config, client)
        result = WorkflowAgent(model).run(model.parse_request(text))
        return LiveResult(
            **result.model_dump(),
            original_request=text,
        )


def main(argv=None):
    parser = argparse.ArgumentParser(description="Beacon service remediation workload")
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run")
    run.add_argument("scenario_id")
    run.add_argument("--json", action="store_true")
    ask = sub.add_parser("ask", help="Use the configured live model")
    ask.add_argument("request")
    ask.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    try:
        if args.command == "ask":
            result = _ask(args.request)
        else:
            from .scenarios import build_agent, load_scenario

            scenario = load_scenario(args.scenario_id)
            result = build_agent(scenario).run(scenario.request)
    except (ValueError, OSError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    if args.json:
        print(result.model_dump_json(indent=2))
    else:
        print(f"Graph path: {' -> '.join(result.path)}")
        print(f"State status: {result.state['final_status']}")
        print(f"Retries: {result.state['retry_count']}")
        print(f"Validation: {result.state['validation']}")
        response = result.state["response"]
        print(f"Response: {response.model_dump() if response else None}")
        if result.execution_error:
            print(f"Execution error: {result.execution_error}")
    # Controlled failures are valid workload results, including the bounded loop.
    return 0
