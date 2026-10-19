# Milestone 2A verification · 16 October 2026

Implemented the execution tree and span inspector over disclosed local fixtures. No production backend/SDK, documentation study, investigator, authentication or HTTP contracts were changed. Timeline and Evidence Focus controls are absent.

## Verification results

- Complete Vitest suite: **62 passed, 7 files**, including the existing 28 Milestone 1 tests. Covers scope, navigation, hierarchy/cycles/missing parents, loaded filtering/ancestors, keyboard selection, virtualization, anchor retention, dismissal, pin/resize, payload values/markers, retry reveal/restore, failed-read retry and stale-detail isolation.
- ESLint and Vite production build: successful. No dependencies added for Milestone 2A.
- Final run: 62/62 tests, ESLint exit 0, Vite exit 0 (278.11 kB JS / 85.90 kB gzip), and `git diff --check -- frontend` exit 0. All **213 protected backend/SDK/documentation files** retain their starting SHA-256 hashes. Existing SDK work and static previews are untouched. No commits, merges or pushes.
- Actual browser: 100, 1,000 and 2,100 fixture studies, 840→1,260→1,680→2,100 local loading, End navigation, name/status search, next match, exact offscreen ID jump, recorded retry links, Restore/Reveal, direct switching, outside/Close/Escape dismissal, browser Back, tabs, pointer/keyboard resizing and responsive focus return.
- Pointer resize: 524→564 px; selection and scroll retained. Narrow Back restores focus to the execution tree. Returning to desktop preserves the requested split preference.
- Wrong-answer fixture R-1041: captured model input `eligible: false`, output `eligible: true`; execution remains Completed. No semantic finding or investigation was generated.
- Sandbox R-2040: Unknown execution/capture, raw UNSET and `VENDOR_PENDING`, captured false/zero, redacted input, truncated output and a recorded event. Unknown status is never presented as OK.
- Long response R-1036: 2,413 captured characters preserved in JSON; readable prose 14/22 px, JSON 13/20 px. Long fields/messages use full payload width. Input/Output jump scrolls only inspection. Wrap-off scrolls inside code, with no page overflow.
- Final browser console check: no errors or warnings returned.

Browser checks caught and fixed a real event-ordering issue: dismissing the overlay on pointer-down could move Restore filters before activation. Dismissal now follows the click; explicit inspection triggers remain open, and URL updates merge current query state. Column headers now account for the scrollbar gutter. Responsive dismissal restores focus after the hidden tree becomes visible.

## Measured local behavior

| Sample | Observed automation action + DOM readback |
|---|---:|
| 100 spans: navigation / End / name search | 180 / 118 / 101 ms |
| 1,000 spans: navigation / End / name search | 179 / 112 / 89 ms |
| 2,100 fixture: initial 840 navigation / End | 332 / 227 ms |
| Three additional 420-record local loads | 375 / 379 / 379 ms |
| Fully loaded 2,100: End / name search / ERROR facet / exact ID jump | 214 / 204 / 217 / 285 ms |

Single samples from the existing local Vite development server. These include automation overhead and DOM readback; they are **not isolated render timings, frame-rate measurements, network measurements or production performance guarantees**. The sampled large states mounted 24–32 treeitems; the complete fixture remained in memory. The 840→1,260 load retained scrollTop **26,294.4 px**. Searching `shipping-quote` plus ERROR at 2,100 loaded returned 12 direct matches with ancestors retained. A missing-parent group appears at the hierarchy end, so End does not imply highest span ID.

Raw results: [browser measurements](browser-measurements.json), [screenshot geometry](screenshot-geometry.json).

## Visual review

All 18 PNGs below were displayed and visually inspected. The 12 desktop baselines cover Explore/overlay/pinned in both sizes/themes. Screenshots use real browser capture, CSS viewport 1440×900 or 1280×800, host DPR 1.25 normalized at capture to one output pixel per CSS pixel. PNG dimensions were checked. No generated images, post-processing, compositing or crops.

| Layout | 1440 light | 1440 dark | 1280 light | 1280 dark |
|---|---|---|---|---|
| Explore | [PNG](tree-light-1440x900.png) | [PNG](tree-dark-1440x900.png) | [PNG](tree-light-1280x800.png) | [PNG](tree-dark-1280x800.png) |
| Overlay | [PNG](overlay-light-1440x900.png) | [PNG](overlay-dark-1440x900.png) | [PNG](overlay-light-1280x800.png) | [PNG](overlay-dark-1280x800.png) |
| Pinned | [PNG](pinned-light-1440x900.png) | [PNG](pinned-dark-1440x900.png) | [PNG](pinned-light-1280x800.png) | [PNG](pinned-dark-1280x800.png) |

Additional inspection: [partial pinned light](partial-pinned-light-1280x800.png), [partial pinned dark](partial-pinned-dark-1280x800.png), [long output light](long-output-light-1280x800.png), [long output dark](long-output-dark-1280x800.png), [incorrect answer](incorrect-answer-light-1280x800.png), [responsive single pane](single-pane-light-820x900.png).

| Geometry, same in both themes | 1440×900 | 1280×800 |
|---|---:|---:|
| Ordinary row viewport, all three modes | 654 px / 20 full rows | 554 px / 17 full rows |
| Inspector width / body reading height | 600 / 686 px | 524 / 586 px |
| Pinned explorer width | 598 px | 514 px |
| Partial pinned row viewport / reading height | Not captured | 518 px / 16 rows / 550 px |
| Execution toolbar | 44 px, one band | 44 px, one band |

Overlay screenshots retain the explorer's original 1,206 / 1,046 px width and scroll position. All sampled desktop captures have no page overflow. Names, JSON, payload markers, footer and inspector controls were inspected at native resolution.

Compared with the authoritative `docs/frontend/design-preview/screenshots/space-efficiency/after/` study: retained 200/56 px shell, 60/36 px run context, 44/32/28 px controls/context/headers, 32 px rows, 16 px indentation, operation glyphs, restrained accents and coordinated M1 theme tokens. Pinned controls remain in one band.

Deliberate differences: Execution heading replaces the unsupported Tree/Timeline toggle; investigation is supplied status text without request/evidence actions; separate full-width type/start columns become inline type/start in narrow panes; tabs omit counts; hierarchy connector lines are not drawn. Compact SVG actions have accessible names. These preserve the approved responsibilities but are not pixel-identical copies of the static prototype. No specification files were changed.

## Accessibility and limits

Tree uses a single keyboard stop, active descendant, levels, selected/expanded states and sibling positions with a bounded row window. Offscreen active rows stay mounted. Tab arrows/Home/End, F6, Escape, explicit Close/Back, visible focus, non-modal background navigation and keyboard/range resize alternatives are implemented. Overlay occlusion is intentional: close or pin to reach covered explorer controls. Full IDs/names remain in accessible labels and copyable Details. Matching ancestor paths stay expanded during filtering; saved collapse state is retained.

Desktop and an 820 px single-pane fallback were exercised. Screen-reader compatibility, full touch/mobile testing, 200%/400% reflow and complete accessibility conformance are **not established**. Per-run UI context and optional-column choice survive navigation in memory; process restart restores URL selection/query plus stored mode/width/theme/sidebar, not every expansion or payload scroll position.

Milestone 2B dependencies remain Timeline and Evidence Focus, with approved timing/evidence semantics. Real structure paging, whole-trace lookup/search, bounded payload retrieval/retention, raw telemetry normalization, investigation lifecycle and historical snapshot resolution need approved backend contracts. The local adapter proposes no endpoints or wire schema. Source fixtures are authored, loaded in memory and never passed off as real telemetry or investigation results.

## Changed files

New `src/data/{authoredTraces.js,scaleTraces.js,traceRepository.js,traceRepository.test.js}`; new `src/features/trace/{treeModel.js,treeModel.test.js,traceState.js,useTraceRead.js,useElementSize.js,ExecutionTree.jsx,TraceToolbar.jsx,TraceWorkspace.jsx,SpanInspector.jsx,InspectorResize.jsx,Payload.jsx,Payload.test.jsx,TraceDetail.test.jsx,trace.css}`; `MILESTONE-2A.md`; this verification directory. Updated `src/app/{App.jsx,App.test.jsx}`, `src/components/{AppShell.jsx,Icon.jsx}`, `src/pages/RunDetailPage.jsx`, and frontend `README.md`. Earlier Milestone 1 work and verification artifacts are preserved.
