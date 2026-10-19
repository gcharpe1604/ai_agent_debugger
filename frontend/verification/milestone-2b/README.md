# Milestone 2B verification · 16 October 2026

Execution Timeline extends the existing virtualized explorer. Run Explorer, Tree, inspector, shell and themes remain in place. Evidence Focus, authentication, investigator actions, backend integration and live telemetry are absent. No packages, commits, merges or pushes.

## Implemented and exercised

- Same virtual row window, hierarchy, loaded-only filters, selection and retry relationships in Tree and Timeline. Timing is indexed once per structural read; zoom/view changes do not reconstruct hierarchy or read another payload.
- Shared relative-time axis with numeric bounds, overlaps, drawing-only clipping, original duration text and zero-duration points. Missing/invalid timing and before/after-window rows remain explicit. Endpoint/duration disagreement is labeled rather than silently reconciled.
- Fit run, centered zoom, half-window pan and a compact time-range overview/range input. Fit selected is explicit in Execution options. Reported run bounds stay distinct from the navigation domain, which may include loaded clock outliers. Without valid bounds, controls are disabled with an explanation; fallback bounds are explicitly loaded-only.
- Tree/Timeline switches retain inspector mode, selected ID, expansion, filters, vertical anchor and time window. Overlay keeps the underlying explorer width; the timing controls remain reachable to its visible left. Pin/unpin and resize reuse the existing behavior.
- Previous/next loaded matches wrap. Fixed the pre-existing Previous-with-no-selection error (it formerly chose the penultimate match). Reveal expands ancestors and temporarily relaxes incompatible filters with explicit Restore. Selection does not infer a time-window change.
- Full operation identity is available in row accessibility labels, the named path disclosure and copyable inspector Details. Child counts say child/children and are separated from raw status. Timing Details retain raw duration and captured/calculated end provenance.

## Automated verification

Full Vitest: **79 tests passed in 9 files**, retaining all 62 Milestone 1/2A cases (one obsolete assertion expecting Timeline to be absent was updated). ESLint and production build passed. Timing tests cover endpoints, missing/null/nonfinite/reversed timing, floating-point tolerance, overlap percentages, clipping, points, outlier bounds, zoom/pan/fit and deep links. UI tests cover overlay/pinned switching, payload-read count, stable scroll/selection/format, keyboard navigation, explicit Fit selected, missing timing, Previous matching and browser return context.

Final checks: Vitest 79/79, ESLint exit 0, Vite exit 0 (**289.96 kB JavaScript / 89.47 kB gzip**), scoped Git whitespace check exit 0, and **17 screenshots / zero dimension failures**.

All edits for this milestone are under `frontend/`. Existing SDK/backend/documentation work was not edited or restored. Approved design documents and static previews remain unchanged. An interrupted session discarded the in-memory initial hash inventory, so this record does not claim a complete before/after hash comparison.

The last native retry check exposed and fixed a dismissal race: React could replace the clicked retry control before the document listener ran. The handler now uses the original composed event path. A regression test reproduces this discrete-event commit, and [forward/back native checks](retry-navigation-check.json) confirm the inspector stays open with the correct attempt selected.

## Browser evidence

The local production build was served with `npm.cmd run preview -- --host 127.0.0.1 --port 5174 --strictPort`. No provider or backend was called. The interruption closed the first preview/browser session; saved screenshots/performance files were retained, and the local preview was restarted for the remaining edge-case checks.

Observed:

- On 1,000 spans, switching both views retained overlay payload scroll **296.8 px**, selected ID `a10003e800000016` and the 0–42.05 s window. Pinned switching retained tree scroll **30,944 px**, payload scroll and the same selected ID/window.
- The 2,100 fixture progressed 840→1,260→1,680→2,100 locally. The first load retained scrollTop **26,434.4 px**. Capture stayed Partial; loading did not repair the missing parent. Fully loaded End/search/view switches stayed bounded at 19–27 mounted treeitems in the sampled states.
- The authored timing study plotted concurrent intervals at **10%/40%** and **25%/40%** on the same x=580.5 px, width=563.5 px track. Missing/reversed timestamps and zero duration had distinct treatments. Fit selected reached the 1.1–1.2 s outlier with a 1.08–1.2 s view; Fit run restored 0–1 s without changing reported duration.
- Browser warning/error log returned no entries in the final sampled session. This is not a screen-reader or accessibility-conformance audit.

### Actual browser work versus automation latency

[Raw production measurements](performance.json) retain both columns. Renderer measurements are CDP `Performance` metric deltas across the action, DOM readback and two animation frames; they include browser/automation bookkeeping and are not isolated React CPU profiles. [Native Event Timing](https://developer.mozilla.org/en-US/docs/Web/API/PerformanceEventTiming) separately reports input-to-presentation durations (8 ms rounding, 16 ms observation threshold). Missing fast events are not zero latency.

| Production sample | Renderer main-thread work | Automation + readback/frame wait |
|---|---:|---:|
| 100: zoom / End / loaded search | 42.24 / 27.77 / 27.72 ms | 243 / 135 / 102 ms |
| 1,000: zoom / End / loaded search | 18.19 / 20.55 / 29.44 ms | 199 / 154 / 98 ms |
| 840 loaded: End / load another 420 | 20.81 / 21.89 ms | 111 / 380 ms |
| 2,100 loaded: zoom / End / loaded search | 20.05 / 17.48 / 29.50 ms | 189 / 144 / 171 ms |
| 2,100 loaded: Tree / Timeline switch | 30.26 / 32.42 ms | 219 / 282 ms |

Native click/keydown samples reported **16–48 ms** to presentation, with **0–11.5 ms** event processing and no emitted long tasks in that sampled sequence. These are single observations on this machine, not a percentile study, SLO, memory ceiling or production guarantee. All fixture data was in memory; this does not establish network paging or whole-trace search. Earlier [development-mode measurements](development-measurements.json) are retained separately. The performance sample preceded the final outlier-domain/accessibility refinements; the final build's outlier behavior was verified separately in the browser.

A [late production-build browser check](final-browser-smoke.json), with all 2,100 spans loaded and 25 treeitems mounted, measured a native zoom click at **48 ms to presentation / 13.5 ms processing / 1.6 ms input delay**. Renderer main-thread work was 37.37 ms and automation plus frame wait 358 ms. This records the `index-DSYo1xSk.js` build separately from the earlier sequence; the final retry-dismissal correction was verified afterward.

## Screenshots and visual fidelity

All **17 PNGs** were browser-rendered, dimension-checked and visually inspected: 12 desktop Timeline baselines, one recovered-retry inspection, one timing-quality study, two partial pinned captures and final recovered-retry verification. The host DPR was overridden to 1.25 and normalized at capture to one output pixel per CSS pixel; no post-processing, generated images or composites. [Geometry records](screenshot-geometry.json).

| Timeline state | 1440 light | 1440 dark | 1280 light | 1280 dark |
|---|---|---|---|---|
| Explore | [PNG](timeline-light-1440x900.png) | [PNG](timeline-dark-1440x900.png) | [PNG](timeline-light-1280x800.png) | [PNG](timeline-dark-1280x800.png) |
| Overlay | [PNG](overlay-light-1440x900.png) | [PNG](overlay-dark-1440x900.png) | [PNG](overlay-light-1280x800.png) | [PNG](overlay-dark-1280x800.png) |
| Pinned | [PNG](pinned-light-1440x900.png) | [PNG](pinned-dark-1440x900.png) | [PNG](pinned-light-1280x800.png) | [PNG](pinned-dark-1280x800.png) |

Focused: [recovered retry](recovered-retry-light-1280x800.png), [timing edge cases](timing-edge-cases-light-1280x800.png), [partial pinned light](partial-pinned-light-1280x800.png), [partial pinned dark](partial-pinned-dark-1280x800.png), [final retry navigation](retry-navigation-final-dark-1280x800.png).

Baselines use the 1,000-span fixture, an explicitly zoomed 0–42.05 s window and the first recorded failed tool attempt; this is not automatic initial selection or initial zoom. Partial screenshots use 840/2,100 loaded, 0–43.6 s. Fonts and 32 px operation rows retain M2A density; no page overflow was observed. The execution toolbar stays 44 px; the separate timing band is 40 px including its border.

| Available space, same across themes | 1440×900 | 1280×800 |
|---|---:|---:|
| Ordinary Timeline row viewport, all modes | 614 px / 19 full rows | 514 px / 16 full rows |
| Inspector reading height | 686 px | 586 px |
| Partial pinned Timeline | Not captured | 478 px / 14 full rows; 550 px inspector reading height |

The approved compact preview's pane responsibilities, typography, palette and shared-axis behavior are retained. Deliberate differences: Timeline indentation caps after three levels with actual depth markers; raw status/counts sit on the operation's secondary line; the overview is a simple window/selected-interval navigator, not a histogram. Narrow pinned names may ellipsize; the full identity/path/Details remains keyboard-accessible. No inferred dependency arrows or recovery claims were introduced.

## Remaining limitations and dependencies

Timeline is a row-based virtual renderer, not an unrestricted two-axis canvas. The label/time divider is fixed. Minimum positive marks and zero points are drawing aids only; short spans need zoom or Fit selected. Rows entirely outside the window stay listed rather than being removed. At the bottom of a trace, a viewport-height change may clamp scroll to the available end; ordinary anchors are retained.

Screen-reader interoperability, full touch/mobile coverage, 200%/400% reflow and performance percentiles are not established. Existing narrow single-pane behavior is reused; no general accessibility-conformance claim. UI state remains session-memory scoped with URL view/window/selection and existing persistent presentation preferences.

Real timestamp units/clock origin, ordering, structural load/search bounds and bounded payload retrieval await approved B3/B4/P3 contracts. This implementation normalizes only authored relative-ms fixtures; duration-derived ends are arithmetic over captured fixture values. Evidence Focus, historical snapshot resolution, investigator lifecycle, authentication and live telemetry remain outside this milestone. No investigator architecture or backend wire contract was chosen.

## Changed files

New: `src/features/trace/{timelineModel.js,timelineModel.test.js,TimelineControls.jsx,TimelineTrack.jsx,Timeline.test.jsx,timeline.css}`, `src/data/timingFixture.js`, `MILESTONE-2B.md`, and this verification directory. Updated: `src/features/trace/{ExecutionTree.jsx,TraceToolbar.jsx,TraceWorkspace.jsx,traceState.js,SpanInspector.jsx,TraceDetail.test.jsx}`, `src/data/traceRepository.js`, and frontend `README.md`. Earlier verification artifacts are preserved.
