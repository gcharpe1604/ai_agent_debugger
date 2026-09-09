# Controlled scenario definitions

Every scenario uses this exact request:

> Recommend the cheapest eligible field station between Ridge and Vale for 40 people, requiring 10 kW, a daily budget of 1000 credits, open access and an approved permit as of 2026-06-01.

The fictional Meridian field-station decision requires capacity, power, daily cost,
access and permit evidence for both sites. Permit collection depends on the site's
access evidence. Ridge is cheaper but its current capacity is only 30. Vale fits
the constraints, but its initial permit records disagree. A follow-up registry
decision explicitly supersedes both records. Initial research also encounters
Ridge's superseded capacity of 80 and an irrelevant visitor-capacity record.

Model replacements are typed responses at an operation boundary. They never
change the orchestrator or receive scenario IDs. Source exclusions simulate
unavailable records. Normal validation independently checks collected evidence;
selected scenarios replace that validation response so faulty drafts can survive.
Operational status is not an evaluation verdict.

| ID | Runtime override / injected behavior | Expected execution behavior | Expected outcome | Failure origin / category | Suspicious operations |
| --- | --- | --- | --- | --- | --- |
| RP-01 | None | Collect ten required facts; surface Vale permit conflict; revise to registry follow-up; resolve and synthesize Vale | Correct, completed; Vale recommended | None | None |
| RP-02 | Exclude all three Vale permit records | Detect missing permit; attempt one follow-up; preserve missing fact and abstain | Correct, incomplete; no recommendation | None (source evidence unavailable) | None |
| RP-03 | Assessments select Ridge's superseded capacity record; validation returns no issues | Conflict still triggers revision; stale selection survives and the cheaper but ineligible Ridge recommendation completes | Failure, completed; Ridge recommended | assess_evidence / stale_selection | assess_evidence, synthesize_report, validate_support |
| RP-04 | First assessment accepts one conflicting Vale permit record and suppresses the conflict; validation returns no issues | Revision is skipped and the contested Vale recommendation completes | Failure, completed; Vale recommended | assess_evidence / conflict_suppressed | assess_evidence, synthesize_report, validate_support |
| RP-05 | Initial plan omits Vale access while retaining its dependent permit step | Required-fact coverage check rejects plan before collection | Failure, blocked | create_plan / required_dependency_omitted | create_plan, check_plan |
| RP-06 | Initial plan puts Vale permit before Vale access | Earlier research succeeds; permit is blocked before source access because prerequisite evidence has not been resolved | Failure, blocked; partial evidence retained | create_plan / dependency_order | create_plan, resolve_dependencies |
| RP-07 | Revision changes required capacity from 40 to 20 | Initial conflict detected; proposed revision retained but rejected for changing original task | Failure, blocked | revise_plan / task_drift | revise_plan, check_revision |
| RP-08 | Revision returns no follow-up steps for the detected conflict | Conflict stays observable; revision rejected for making no progress | Failure, blocked | revise_plan / revision_no_progress | revise_plan, check_revision |
| RP-09 | Synthesis claims Vale has 99 kW while citing the 12 kW evidence; validation returns no issues | Healthy research completes with the unsupported 99 kW claim in the terminal report | Failure, completed; Vale recommended | synthesize_report / unsupported_claim | synthesize_report, validate_support |
| RP-10 | Synthesis omits collected Ridge capacity evidence and recommends Ridge; validation returns no issues | Healthy research completes with an ineligible Ridge recommendation that ignores collected evidence | Failure, completed; Ridge recommended | synthesize_report / ignored_evidence | synthesize_report, validate_support |

Evaluation manifests under `ground_truth/` encode these expectations separately
from runtime JSON. Runtime never imports the evaluation schema or reads manifests.
The wheel includes only runtime code, scenario configuration and local corpus.

Coverage beyond the existing samples: multi-candidate constraint coverage,
evidence-bearing prerequisites, contradictory sources with explicit supersession,
task-preserving research revision, and decision completeness across collected facts.
This is not a second retrieval ranker or a stateful fulfillment/tool framework.
