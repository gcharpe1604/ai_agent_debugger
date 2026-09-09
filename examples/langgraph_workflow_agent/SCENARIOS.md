# Scenario specification (defined before implementation)

The fictional Beacon service accepts structured incident requests: a service name,
an incident (`worker_stalled` or `host_unavailable`), and telemetry availability
(`ready`, `delayed`, `denied`, or `unavailable`). Restart fixes a stalled worker;
failover fixes an unavailable host. All operations are local simulations.

Paths below are expected **observed paths under injection**, not ideal paths.
`C=classify`, `G=gather_context`, `E=evaluate`, `R=retry_context`,
`X=execute_action`, `A=abort`, `V=validate`, `F=respond`.
All paths start at START; paths reaching END say so explicitly. The retry budget
is two retries (three total context acquisitions); the framework ceiling is 18
node executions. Response generation is a separate final node so a valid graph
state can be followed by an inconsistent response.

| ID | Request (service / incident / telemetry) | Injected behavior | Expected path | Expected terminal outcome | Failure category | Suspicious operations |
|---|---|---|---|---|---|---|
| LG-01 | beacon / worker_stalled / ready | None | C G E X V F END | resolved; restart succeeds | none | none |
| LG-02 | beacon / host_unavailable / delayed | None; first acquisition is retryable, next is ready | C G E R G E X V F END | resolved; failover after one retry | none | none |
| LG-03 | beacon / worker_stalled / ready | evaluate chooses abort despite ready context | C G E A V F END | aborted, silently incorrect; should resolve | wrong_branch | evaluate |
| LG-04 | beacon / worker_stalled / ready | classify routes directly to evaluate | C E A V F END | blocked; missing_context detected | skipped_node | classify, validate |
| LG-05 | beacon / host_unavailable / delayed | second context acquisition returns ready data with revision 1, not 2 | C G E R G E X V F END | blocked; stale_context detected after action | stale_state | gather_context, validate |
| LG-06 | beacon / worker_stalled / ready | execute_action's state update overwrites its successful action result with null | C G E X V F END | blocked; missing_action_result detected | lost_state_update | execute_action, validate |
| LG-07 | beacon / worker_stalled / denied | evaluate routes a terminal telemetry denial to retry | C G E R V F END | blocked; terminal_retry detected before reacquisition | incorrect_failure_transition | evaluate, retry_context, validate |
| LG-08 | beacon / worker_stalled / unavailable | evaluate always chooses retry, ignoring two-retry limit | C G E (R G E) x 5; recursion guard | graph remains running, no answer; recursion_limit execution error | retry_limit_ignored | evaluate, retry_context |
| LG-09 | beacon / worker_stalled / ready | classify routes to END | C END | running, unvalidated, no answer; silently incomplete | premature_termination | classify |
| LG-10 | beacon / worker_stalled / denied | respond claims resolution after a validated abort | C G E A V F END | state aborted, response resolved; silently incorrect | response_state_contradiction | respond |

Evaluation-only JSON manifests record paths, outcomes, ideal statuses, detection
operations, retry counts, issues and suspicious operations. Runtime configuration
contains only inputs and explicit dependency/node/routing overrides. Scenario IDs
are loader labels and never reach graph nodes or dependencies.

The validator checks state consistency, not whether every policy decision was
optimal. LG-03 exercises that deliberate blind spot. LG-05 detects stale state
after the simulated action; it does not roll back or claim to prevent execution.
LG-09 and LG-10 preserve incorrect results for later external evaluation.
