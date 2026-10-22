# Milestone 1 verification · 16 October 2026

## Executed checks

| Check, from `frontend/` | Observed result |
|---|---|
| `npm.cmd test` | **28 passed**, three test files; no skipped tests in the complete run |
| `npm.cmd run lint` | Exit 0, no diagnostics |
| `npm.cmd run build` | Exit 0; Vite 8.2.2, 27 modules; CSS 14.62 kB / 3.65 kB gzip; JS 218.04 kB / 68.33 kB gzip |
| Browser desktop review | All four final captures below opened at their native requested dimensions; eight authored default-project rows, all seven columns, one 44 px toolbar, no page-wide horizontal overflow |
| Narrow reflow | 390×844 screenshot inspected; 320 px geometry checked. Wide table scrolls locally. Saved expanded sidebar restores on return to desktop. Not a complete mobile/device audit. |

Runtime used: Node 26.2.0, React/React DOM 19.2.8. Added test-only Vitest 5.0.5, Testing Library React/user-event and jsdom; no runtime UI/router dependencies. Npm also refreshed the existing transitive sourcemap-codec 1.5.5→1.6.0 and picomatch 4.0.5→4.0.7 lock entries. The initial sandboxed registry request was denied; the approved retry installed the test tools successfully.

## Desktop screenshot index

| Size | Light | Dark |
|---|---|---|
| 1440×900 | [Run Explorer](run-explorer-light-1440x900.png) | [Run Explorer](run-explorer-dark-1440x900.png) |
| 1280×800 | [Run Explorer](run-explorer-light-1280x800.png) | [Run Explorer](run-explorer-dark-1280x800.png) |

Additional [390×844 reflow capture](run-explorer-dark-390x844.png). Measurements and browser observations are in browser-qa.json (historical report removed during cleanup).

Images are actual full-viewport browser renders captured through CUA/CDP. The host uses DPR 1.25; capture scale 0.8 normalizes one CSS pixel to one output pixel. No subsequent image resizing, compositing or generated imagery. Earlier wrapper captures had a viewport/scale mismatch and were excluded. Final PNG headers and live DOM viewport sizes are checked independently.

## Visual comparison

Reviewed the four retained [Run Explorer references](../../docs/frontend/design-preview/screenshots/run-explorer-light-1440x900.jpg), the latest live static Run Explorer, the design specification and 16 October review notes. The retained images show older repeated Project/environment/helper chrome; the latest refinement supersedes that chrome.

- Same neutral light/dark palette, Steel focus family, restrained explicit-error accents, system typography, 200/56 px navigation, column proportions, compact borders and two-line run identity. Names, trace IDs, times, durations and supplied states match the study's eight default records.
- Application header 48 px; view heading 56 px; toolbar 44 px; table starts at y=164 versus y=184 in the current static Run Explorer. The compact heading omits repeated project/helper text and the duplicate Setup action. No KPI cards or filler rows.
- Operation table rows have a 48 px minimum; the captured host renders approximately **48.4–48.8 px**, versus 48 px in the study, to accommodate 24 px keyboard/pointer targets. Primary names remain 14/20 px, metadata 12 px. No font reduction was used to gain space.
- Functional native project/appearance/time controls, Filters disclosure, sort buttons and page-size control replace fixed/disabled demonstrations. Native arrows and focus appearance differ slightly. Finding counts remain text, without a misleading evidence link.
- At both desktop sizes, the table fits all columns and the footer remains inside the viewport. The narrow layout deliberately permits a two-dimensional local data region and taller touch controls; it uses a temporary compact rail rather than an unimplemented modal navigation sheet.

## Functional and accessibility evidence

Automated tests cover project scope, case-insensitive name/trace lookup, AND/OR semantics, duration/time filtering, stable tie ordering, numeric sorting, page reset/clamping, URL round trips, navigation/return query, independent statuses, first-use versus query-empty states, cancellation/late responses, read/retry/failed refresh, System changes, explicit theme overrides, persistence and blocked storage.

Browser checks additionally exercised Enter on search and Run links, native Back, sorting/page navigation, Escape on Filters, Tab focus, project switching, compact navigation and reload persistence. Search now keeps its input mounted; sortable headers remain mounted during reads. Pagination uses guarded `aria-disabled` so reaching the final page does not drop keyboard focus. Route changes focus the main landmark; query changes preserve the initiating control. Busy/read results are announced separately from the sample-data badge.

Two focus defects were reproduced with failing regression tests and corrected: search/Filters remounting, and table/pagination focus loss during query reads. The browser capture-scaling issue was a verification-tool issue, not a product layout workaround.

These checks establish local UI behavior, not screen-reader interoperability or WCAG conformance. Full assistive-technology testing, 200%/400% zoom, text spacing, touch devices and cross-browser coverage remain outstanding. CSS specifies a 2 px focus ring; this host's DPR rounding can report 1.6 CSS px for the painted outline.

## Integration boundaries and remaining decisions

- No HTTP calls, authentication, actual telemetry, investigation requests, Trace Detail or Evidence Focus implementation. Run destinations are explicit milestone-boundary pages; unsupported routes/projects explain unavailability rather than substituting data.
- The default date window is a fixed sample window. Real time bounds, authoritative totals/order, server filters/pagination, error-count units, access policy and refresh/completeness semantics require approved backend contracts. No endpoints or response schemas were invented.
- The supplied error count represents authored error-operation groups; it is not a count of individual ERROR spans. Unknown outcome/capture/error counts remain explicit in the Sandbox fixture. Recovery never changes a supplied Run outcome or hides recorded errors.
- First-use System/expanded preferences are reversible implementation defaults. Their product defaults remain reviewable. These preferences are presentation state, not sessions or authorization.
- The small fixture set and in-process promise adapter establish neither server integration nor large-data performance. Failure and delayed-response cases use injected test adapters; there is no production failure simulator or fabricated server success.

## Changed files

All changes are under `frontend/`: `index.html`, `package.json`, `package-lock.json`, `eslint.config.js`, `vitest.config.js`, `README.md`, `MILESTONE-1.md`, `public/debugger.svg`; `src/main.jsx`, `src/index.css`, `src/app/{App.jsx,routes.jsx,preferences.js,App.test.jsx,preferences.test.js}`, `src/components/{AppShell.jsx,Icon.jsx}`, `src/pages/RunExplorerPage.jsx`, `src/data/{fixtures.js,runRepository.js,runs.test.js}`, `src/features/runs/{query.js,useRuns.js,RunToolbar.jsx,RunTable.jsx}`, `src/test/setup.js`; and this verification directory's notes, JSON and five PNGs.

The 208-file protected baseline (tracked backend/SDK/core documents plus existing frontend research/previews) retains every starting hash. This pass writes only under `frontend/`; the pre-existing SDK/backend/documentation status paths remain unchanged. No commits, merges or pushes.
