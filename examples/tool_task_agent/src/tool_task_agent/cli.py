import argparse
import json
import sys

from .tools import ToolError


def _ask(request):
    import httpx

    from .agent import TaskAgent
    from .live_model import LiveConfig, LiveModelClient, LiveResult
    from .tools import LocalTools

    from ai_agent_debugger_sdk import TraceSession

    config = LiveConfig.from_env()
    with TraceSession.local("tool-task-agent", model=config.model, provider=config.base_url, local_dependencies=True) as tracing, httpx.Client() as client:
        tracing.instrument(client, {"post": ("api", "POST chat/completions")})
        model = tracing.instrument(LiveModelClient(config, client), {"_request": ("model", "model.request")})
        def tools_factory():
            return tracing.instrument(LocalTools(), {"invoke": ("tool", "LocalTools.invoke")})
        with tracing.operation("agent", "TaskAgent.run"):
            result = TaskAgent(model, tools_factory).run(request)
        tracing.record_result(result)
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
            from ai_agent_debugger_sdk import TraceSession

            with TraceSession.local("tool-task-agent", execution_mode="controlled", local_dependencies=True) as tracing:
                agent = build_agent(scenario)
                tracing.instrument(agent.model, {name: ("custom", "controlled." + name) for name in ("plan", "respond")})
                original_factory = agent.tools_factory
                def tools_factory():
                    return tracing.instrument(original_factory(), {"invoke": ("tool", "LocalTools.invoke")})
                agent.tools_factory = tools_factory
                with tracing.operation("agent", "TaskAgent.run"):
                    result = agent.run(scenario.request)
                tracing.record_result(result)
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
