import argparse
import sys


def _ask(request):
    import httpx

    from .agent import ResearchPlanningAgent
    from .evidence import EvidenceSource, load_evidence
    from .live_model import LiveConfig, LiveModelClient, LiveResult

    from ai_agent_debugger_sdk import TraceSession

    config = LiveConfig.from_env()
    with TraceSession.local("research-planning-agent", model=config.model, provider=config.base_url, local_dependencies=True) as tracing, httpx.Client() as client:
        tracing.instrument(client, {"post": ("api", "POST chat/completions")})
        model = tracing.instrument(LiveModelClient(config, client), {"_request": ("model", "model.request"), "validate_support": ("custom", "validate_support")})
        source = tracing.instrument(EvidenceSource(load_evidence()), {"collect": ("retrieval", "EvidenceSource.collect")})
        with tracing.operation("agent", "ResearchPlanningAgent.run"):
            result = ResearchPlanningAgent(model, source).run(request)
        tracing.record_result(result)
        return LiveResult(**result.model_dump(), original_request=request)


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Controlled and live Meridian field-station research"
    )
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run")
    run.add_argument("scenario_id")
    run.add_argument("--json", action="store_true")
    ask = sub.add_parser("ask")
    ask.add_argument("request")
    ask.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    try:
        if args.command == "ask":
            result = _ask(args.request)
        else:
            from .scenarios import build_agent, load_scenario

            scenario = load_scenario(args.scenario_id)
            from ai_agent_debugger_sdk import TraceSession

            with TraceSession.local("research-planning-agent", execution_mode="controlled", local_dependencies=True) as tracing:
                agent = build_agent(scenario)
                tracing.instrument(agent.model, {name: ("custom", "controlled." + name) for name in ("decompose", "create_plan", "assess_evidence", "revise_plan", "synthesize_report", "validate_support")})
                tracing.instrument(agent.evidence_source, {"collect": ("retrieval", "EvidenceSource.collect")})
                with tracing.operation("agent", "ResearchPlanningAgent.run"):
                    result = agent.run(scenario.request)
                tracing.record_result(result)
    except (ValueError, OSError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    if args.json:
        print(result.model_dump_json(indent=2))
    else:
        if args.command == "ask":
            print(f"Original request: {args.request}")
        print(f"Status: {result.status}")
        for operation in result.operations:
            print(f"  {operation}")
        for index, assessment in enumerate(result.assessments, 1):
            print(
                f"Assessment {index}: missing={assessment.missing}, conflicts={assessment.conflicts}, stale={assessment.stale}"
            )
        if result.revision:
            print(f"Revision: {result.revision.reason}")
        if result.draft:
            label = (
                "Rejected draft recommendation" if result.issues else "Recommendation"
            )
            print(f"{label}: {result.draft.recommendation or 'none'}")
            for claim in result.draft.claims:
                print(
                    f"  {claim.fact} = {claim.value} [{', '.join(claim.evidence_ids)}]"
                )
            if result.draft.unresolved:
                print(f"Unresolved: {', '.join(result.draft.unresolved)}")
        if result.issues:
            print(f"Issues: {', '.join(result.issues)}")
    return 0
