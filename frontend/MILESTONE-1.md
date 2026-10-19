# Frontend Milestone 1

Implement the approved Run Explorer and shell in place. `docs/frontend/design-spec.md` and the 16 October preview refinements are the visual authority; those documents and previews stay unchanged.

## Execution plan

- [x] Test project-scoped selection, committed search, AND filters, stable sorting, pagination and URL round trips against an empty implementation, then implement the fixture repository/query model.
- [x] Repair the entry point; implement semantic theme tokens, persistent Light/Dark/System and sidebar preferences, project context, breadcrumbs and scoped navigation.
- [x] Test and implement the Run Explorer: real controls, independent supplied states, read/retry/empty states, copyable IDs and bounded milestone destinations.
- [x] Run lint, the complete frontend test suite and production build. Review React hooks/accessibility and inspect 1440×900 / 1280×800 browser captures in both themes against the current static preview.

Execution used the approved frontend spec and direct Milestone 1 instruction; no additional design approval or Git operation was required. Native hash navigation avoids a new runtime router dependency. System/expanded are reversible first-use presentation defaults. In-process paging/time choices are explicitly sample-scoped. The responsive rail is temporary and does not overwrite the saved desktop preference. See `verification/README.md` for evidence and integration gates.

## Boundaries and review focus

No authentication, telemetry ingestion, server APIs, Trace Detail, Evidence Focus or investigation actions. The repository is an in-process fixture adapter, not a proposed HTTP contract. No commits/pushes or changes outside `frontend/`.

Watch for cross-project stale results, stale responses after query changes, page reset/clamping, browser-history restoration, blocked preference storage, system appearance changes, focus after navigation and locally scrolling wide tables. Use deterministic fixtures, not generated metrics or duplicate filler rows. Test-only deferred/failing adapters exercise actual UI read states.
