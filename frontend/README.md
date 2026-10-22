# Agent Debugger frontend

The normal application reads captured SDK executions through `src/data/apiRepository.js` and the FastAPI `/api/v1/local/` profile. Start with `npm.cmd run dev` from this directory, then open http://127.0.0.1:5175/. No source flag, special mode or seeded telemetry is used.

[Backend and all four live-agent commands](../docs/local-development.md). The server must explicitly enable loopback capture. Its memory storage is temporary; authenticated projects, Kafka/ClickHouse persistence, authentication and investigation remain separate integration work. A disconnected/failed backend never falls back to authored records.

Historical synthetic data is isolated to explicitly injected regression tests and design previews. The notes below describe earlier milestone work, not the current runtime source configuration.

## Historical milestone notes

# Agent Debugger frontend · Milestones 1–3

Functional React shell, Run Explorer, execution tree/timeline, span inspector and Evidence Focus, backed exclusively by deterministic local sample data. Authentication, live telemetry and investigation request/retry actions remain deferred.

From this directory with the lockfile dependencies installed:

```powershell
npm.cmd run dev -- --host 127.0.0.1 --port 5173 --strictPort
```

Open http://127.0.0.1:5173/. If that command is already running, reuse it. `npm.cmd ci` restores dependencies when needed; it was not used as a verification command in this pass.

```powershell
npm.cmd test
npm.cmd run lint
npm.cmd run build
```

Search commits on Enter or the search button. Filters combine with AND; investigation selections combine with OR. Time options refer to the visibly dated sample window, not the computer clock. Sorting and query changes reset pagination; Clear filters retains the time window and sorting, while Reset query resets the query. Page sizes are 5/10/25/50, with 25 initially. Eight default-project records are preserved from the approved study, with three separate Sandbox records and an empty sample project for scope/empty-state review.

Navigation uses scoped hash URLs so direct links work without server rewrite rules. Run links open Trace Detail and preserve the Runs query; positive supplied finding counts open Evidence Focus. Project selection is UI scoping, not backend authorization.

Light/Dark/System and the explicit 200/56 px sidebar preference persist in local storage. First use selects System and expanded desktop navigation as reversible initial preferences. Narrow screens temporarily use a compact rail without changing the desktop preference. No account/session values or payloads are stored.

## Source boundaries

| Files | Responsibility |
|---|---|
| `src/main.jsx`, `src/app/App.jsx`, `src/app/routes.jsx` | Vite entry, dependency composition, scoped URL navigation and explicit unavailable/milestone destinations |
| `src/components/AppShell.jsx`, `src/app/preferences.js` | Project context, breadcrumbs, navigation, appearance, sidebar, focus and disclosure dismissal |
| `src/components/Icon.jsx`, `src/index.css`, `public/debugger.svg` | Shared glyphs, semantic theme tokens, component states, responsive geometry and product favicon |
| `src/pages/RunExplorerPage.jsx` | Query orchestration, result/read/empty states, pagination and refresh |
| `src/features/runs/RunToolbar.jsx`, `RunTable.jsx` | Committed search, filters, validation, sortable semantic table and copyable IDs |
| `src/features/runs/query.js`, `useRuns.js` | Validated URL query model, cancellation and stale-response isolation |
| `src/data/fixtures.js`, `runRepository.js` | Authored records and replaceable in-process data-access interface |
| `src/app/*.test.*`, `src/data/runs.test.js`, `src/test/setup.js`, `vitest.config.js` | Focused regression tests and test environment |

`repository.projects` supplies sample project context. `repository.listRuns({ projectId, query, signal })` resolves `{ items, total, projectTotal, page, pageSize }`. These are internal view models, **not HTTP API proposals**. Replacing adapters requires approved server contracts and normalization. Outcome, capture, supplied error-operation counts and investigation fields are never derived from each other. Existing empty `src/api/` helpers remain untouched.

See [verification and screenshot index](verification/README.md) for measured fidelity, limitations and exact results. The original specification, static study and SDK/backend work are preserved.

## Execution tree and span inspector

Trace Detail starts with full-width exploration. Click or Enter a span to inspect; Escape, Close or an outside click dismisses the overlay. F6 switches focus between explorer and inspector. Pin creates a split without resetting selection, expansion or scroll. Drag the splitter, use Left/Right (16 px), Home/End, or the Inspector options width slider; Enter resets automatic width. The explicit mode/width preference persists. Narrow layouts temporarily show one pane; Back to execution restores tree focus.

Arrow keys navigate and expand/collapse, Home/End and Page Up/Down move through the visible hierarchy. Loaded name/ID, type and raw-status filters retain ancestors. Reveal explicitly opens hidden/offscreen selection; Restore filters reverses temporary relaxation during retry or ID navigation. Only recorded retry relationships create links.

Execution options expose 100/1,000/2,100-span fixture studies. The partial fixture starts with 840 loaded records; loading another 420 is a local fixture operation, not server pagination. Its missing-parent warning remains even after all structure is loaded. Windowed 32 px rows limit mounted DOM; all synthetic source data still resides in local memory.

`src/data/{authoredTraces,scaleTraces,traceRepository}.js` owns fixtures and separate asynchronous structural/detail reads. `src/features/trace/treeModel.js` owns hierarchy, filtering and row windows; `traceState.js` owns UI context; hooks guard stale reads. Tree, toolbar, inspector, payload and resize components are separate. `App` caches per-project/run UI context in memory; preferences persist only presentation choices, never payloads. Full expansion, tab and reading context survives in-app navigation, not a complete browser-process restart.

See [Milestone 2A verification and screenshots](verification/milestone-2a/README.md). The earlier Milestone 1 verification record is historical and preserved.

## Execution Timeline

Tree and Timeline share one virtualized hierarchy, selected span, filters, expansion, row anchor and inspector. Switching view preserves payload format/tab/scroll and the explicit time window. Timeline uses a common relative-millisecond axis; the fixture adapter supplies relative starts/durations, with explicit endpoints supported. A duration-derived endpoint is identified in Details; this does not define a backend timestamp contract.

Fit uses the reported run bounds, or explicitly labeled loaded timing when run bounds are unavailable. Zoom centers the current window; arrow buttons pan by half a window. The overview's highlighted interval and keyboard range control navigate time without inventing an activity chart. Execution options contains Fit selected interval. Selecting an off-window span never automatically zooms. Navigation can reach loaded clock outliers while Fit run retains the reported bounds. Zero spans use points; invalid/missing timing and before/after-window spans remain listed with explicit labels. Original durations remain visible, and no timing-based causal or retry relationships are inferred.

Loaded previous/next matches wrap, expand the target's ancestor path and preserve filter scope. Explicit Reveal may temporarily relax filters with Restore available. Full names/IDs remain in accessible row identity, the named selected-operation path and inspector Details. Child counts have explicit units separate from raw status. Deep Timeline indentation caps after three indents with an actual-depth marker; names may still ellipsize in narrow pinned panes.

New timing logic lives in `src/features/trace/timelineModel.js`; controls, axis/tracks and styles are separate from hierarchy/fixture state. Execution options also exposes an eight-span authored timing-quality study. No dependency or backend endpoint was added. See [Milestone 2B results and screenshots](verification/milestone-2b/README.md), including browser-native performance observations and limitations.

## Evidence Focus and investigation presentation

Trace Detail exposes a compact investigation control with supplied status, attempt, analyzed snapshot and limitations. Request/retry remains disabled and explained. Positive findings in Runs or Trace open `#/projects/agent-examples/runs/R-1042/evidence` (three sources) or `R-1041/evidence` (incorrect reasoning). R-1040 has zero findings despite its recorded recovered error; Sandbox R-2040 is pending. The R-1042 attempt selector also exposes an explicitly authored earlier review sample with missing and mismatched sources.

Evidence uses a compact finding selector, explicit Left/A and Right/B assignment, independent reading regions, Readable/Captured JSON and source focus. Assigning a citation already in the other slot swaps the assignments; the numbered citations and finding stay unchanged. References are labeled verified only where the fixture explicitly supplies that outcome. Snapshot mismatch/unavailability blocks captured-value display and copying; it never falls back to `traceRepository`. Open current span is separately labeled and does not resolve an analyzed snapshot.

`src/data/investigationRepository.js` is a replaceable in-process presentation adapter over immutable authored captures. Its methods and local view models are not proposed backend endpoints or citation schemas. `src/features/evidence/` owns presentation, tagged/cancelled reads and UI-only state. Scoped in-memory caches retain evidence assignments, focus/format and reading positions; the existing trace cache retains exploration/inspection context across navigation. Reload retains URL identities and presentation preferences, but not all reading positions/expansion. See [Milestone 3 verification](verification/milestone-3/README.md) for tests, screenshots, design deviations and pending contracts.
