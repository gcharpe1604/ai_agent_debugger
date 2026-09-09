import argparse
import sys

from .scenarios import build_agent, load_scenario


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Offline Meridian field-station research"
    )
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run")
    run.add_argument("scenario_id")
    run.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    try:
        scenario = load_scenario(args.scenario_id)
        result = build_agent(scenario).run(scenario.request)
    except (ValueError, OSError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    if args.json:
        print(result.model_dump_json(indent=2))
    else:
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
