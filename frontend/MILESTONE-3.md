# Milestone 3 — Evidence presentation

Implements the approved `docs/frontend/design-spec.md` sections 4.3, 6–9. Native execution in this checkout; no commits, new packages, backend changes or investigator logic.

- [x] Add a project/run-scoped investigation adapter with immutable authored snapshots. Keep lifecycle, grounding and citation resolution as supplied presentation data, not a proposed wire schema. Test unavailable, mismatched and aborted reads.
- [x] Extend scoped routes and compact investigation entry in Runs/Trace. Retain trace UI cache; evidence links use the latest selection. Test all supplied states and return navigation.
- [x] Build rail-free Evidence Focus, attempt/finding selectors, explicit A/B assignment, source focus and independent reading positions. Reuse semantic tokens and safe payload primitives. Test pairing, missing historical sources, inert content and stale responses.
- [x] Run the complete frontend tests, lint and build; exercise S1–S3 and capture/inspect desktop light/dark screenshots. Record deviations, limits and exact changed files in `verification/milestone-3/README.md`.

Review risks: snapshots must never fall back to current trace data; project IDs must scope every read; old async responses must not cross selections; pair/focus state must survive workspace navigation; analysis state must not change reported execution outcome. Request/retry actions remain explicitly disconnected.
