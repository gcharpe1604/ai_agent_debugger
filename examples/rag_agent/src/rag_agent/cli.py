import argparse
import asyncio
import re
import sys
from pathlib import Path

import yaml

from .live_model import LiveModelError


async def _ask(question: str):
    import httpx

    from .agent import RAGAgent
    from .knowledge_base import KnowledgeBase
    from .live_model import LiveConfig, LiveModelClient
    from .retrieval import LocalRetriever

    from ai_agent_debugger_sdk import TraceSession

    config = LiveConfig.from_env()
    kb = KnowledgeBase(Path(__file__).with_name("data") / "knowledge_base")
    with TraceSession.local("rag-agent", model=config.model, provider=config.base_url, local_dependencies=True) as tracing:
        async with httpx.AsyncClient() as client:
            tracing.instrument(client, {"post": ("api", "POST chat/completions")})
            model = tracing.instrument(LiveModelClient(config, client), {"_request": ("model", "model.request")})
            retriever = tracing.instrument(LocalRetriever(kb), {"search": ("retrieval", "LocalRetriever.search")})
            with tracing.operation("agent", "RAGAgent.run"):
                result = await RAGAgent(model, retriever).run(question)
            tracing.record_result(result)
            return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="NovaCloud RAG support agent")
    subparsers = parser.add_subparsers(dest="command", required=True)
    run = subparsers.add_parser("run", help="Execute a controlled scenario")
    run.add_argument("scenario_id", help="RAG-01 through RAG-07")
    run.add_argument(
        "--json", action="store_true", help="Print the complete domain result as JSON"
    )
    ask = subparsers.add_parser(
        "ask", help="Ask a question using the configured live model"
    )
    ask.add_argument("question", help="NovaCloud support question")
    ask.add_argument(
        "--json", action="store_true", help="Print the complete domain result as JSON"
    )
    args = parser.parse_args(argv)
    try:
        if args.command == "ask":
            result = asyncio.run(_ask(args.question))
            heading = "Mode: live"
        else:
            from .factory import DATA_DIR, build_agent
            from .knowledge_base import KnowledgeBase
            from .scenarios import load_scenario

            if not re.fullmatch(r"RAG-\d{2}", args.scenario_id):
                raise ValueError("Expected a scenario ID such as RAG-01")
            kb = KnowledgeBase(DATA_DIR / "knowledge_base")
            scenario = load_scenario(
                DATA_DIR / "scenarios" / f"{args.scenario_id}.yaml", kb
            )
            if scenario.scenario_id != args.scenario_id:
                raise ValueError("Scenario filename and scenario_id disagree")
            from ai_agent_debugger_sdk import TraceSession

            with TraceSession.local("rag-agent", execution_mode="controlled", local_dependencies=True) as tracing:
                agent = build_agent(scenario, kb)
                tracing.instrument(agent.model, {name: ("custom", "controlled." + name) for name in ("classify_question", "formulate_query", "assess_evidence", "refine_query", "generate_answer")})
                tracing.instrument(agent.retriever, {"search": ("retrieval", "ScenarioAwareRetriever.search")})
                with tracing.operation("agent", "RAGAgent.run"):
                    result = asyncio.run(agent.run(scenario.question))
                tracing.record_result(result)
            heading = f"Scenario: {scenario.scenario_id}\nMode: controlled"
    except (OSError, ValueError, yaml.YAMLError, LiveModelError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    if args.json:
        print(result.model_dump_json(indent=2))
        return 0
    print(f"{heading}\n\nQuestion:\n{result.question}")
    print(f"\nRetrieval attempts: {len(result.context.retrieval_attempts)}")
    for attempt in result.context.retrieval_attempts:
        print(f"\nAttempt {attempt.attempt_number}: {attempt.query}")
        for item in attempt.results:
            print(
                f"  {item.document.document_id} - {item.document.title} ({item.score:.3f})"
            )
        if not attempt.results:
            print("  No matching documents")
        print(
            f"Evidence: {'sufficient' if attempt.assessment.sufficient else 'insufficient'}"
        )
        print(f"Missing facts: {', '.join(attempt.assessment.missing_facts) or 'none'}")
    print(f"\nAnswer:\n{result.answer}\n\nStatus: {result.status}")
    print(
        f"Supporting documents: {', '.join(result.supporting_document_ids) or 'none'}"
    )
    return 0
