# Design preview review log

## Space-efficiency and workflow refinement — 16 October 2026

**Status:** focused documentation/static-preview pass, with 24 matched before/after desktop pairs and two long-response captures. All 26 final after images and eight representative before comparisons were opened at native resolution. The final 24 desktop JPEGs were regenerated after the reading-state repairs and were byte-identical to the already inspected versions. This is not a production frontend, backend integration, performance benchmark or accessibility-conformance claim.

The independent UX audit supplied by the user in this conversation was read completely. Its reported 1280 partial-pinned defect was reproduced locally at 96 px / three full rows. Its competitor observations remain attributed audit evidence. For visual quality, the retained [Langfuse official image](../research/LF-06-official-overview-2026-10-15.jpg) and [LangSmith official trace image](../research/LS-02-official-trace.jpg) were visually reviewed; this pass does not claim a new live competitor verification or adopt their branding.

The sections dated 15 October below are historical. Their geometry, manual payload-load step and analyzed-span navigation are superseded here; their screenshots/research remain preserved. Live preview URLs render the latest study.

### What changed

- Combined breadcrumb/workload identity into a 60 px header and execution metadata into a 36 px row. Investigation state is a compact header control; positive findings open evidence directly, with separate attempt/limitations details. Request/retry is disabled with an explicit disconnected-preview explanation.
- Kept full-width Explore, 600/523 px overlay widths, and optional resizable pinning. One 44 px execution toolbar holds view/search/filters/options; one 32 px scope/path band and one 40 px timing band replace wrapped control stacks. Expand/collapse, exact-ID jump, optional columns and Fit selected live in accessible disclosures. Load-more joins the 28 px footer.
- Made IDs an explicit wide-view preference; search and full ID/copy in Details remain available. A too-narrow pane disables the column control with an explanation rather than accepting an ineffective toggle. Optional width adjustment is behind Inspector options; its slider now matches constrained pixel values exactly.
- Combined operation identity/actions into one inspector header. Content no longer repeats the Attributes table or full exception event. Kept raw status, readable/JSON values, capture markers, concise error/retry summaries, attribute search and the dedicated Events/Errors tabs. Selecting an authored span renders its local payload immediately; this is selected-only rendering, not a network read.
- Removed the single-finding rail and repeated source snapshot bands. Finding meaning/limitations, analyzed snapshot, exact source field/passage and document revision remain visible. Full identifiers expand in Details; each source retains its own reading region. The multiple-findings selector is demonstrated through a separately authored variant.
- Corrected the non-ERROR-to-OK status mapping and stale evidence links. Current selection is captured at navigation, with tab-scoped presentation memory for expansion, filters, scroll, time window, inspector mode/tab and evidence assignments. Ordinary local outside clicks dismiss an overlay; workspace-navigation links save its pre-departure context.

Shared shell copy/navigation was compacted; Run Explorer's table columns, eight authored rows and 48 px row rhythm are unchanged. The 56 px sidebar remains an explicit persisted preference, with 200 px expanded navigation used for every matched comparison. No compact preference was forced to improve the measurements.

### Measured space improvements

CSS pixels at approximately DPR 1. Theme geometry matched. Counts below include only vertically fully visible 32 px operation rows; a footer range can include the next partially visible row. Overlay row counts describe the unchanged vertical explorer viewport, while the right portion is intentionally covered.

| State | 1440×900: before → after | 1280×800: before → after |
|---|---|---|
| Full-width Tree | 466.0 → 653.6 px; **14 → 20 rows** | 366.0 → 553.6 px; **11 → 17 rows** |
| Full-width Timeline | 389.2 → 613.6 px; **12 → 19 rows** | 289.2 → 513.6 px; **9 → 16 rows** |
| Overlay Tree | 466.0 → 653.6 px; **14 → 20 rows** | 366.0 → 553.6 px; **11 → 17 rows** |
| Pinned Tree | 391.2 → 653.6 px; **12 → 20 rows** | 263.2 → 553.6 px; **8 → 17 rows** |
| Partial pinned Timeline | 194.0 → 577.6 px; **6 → 18 rows** | 96.0 → 477.6 px; **3 → 14 rows** |

| Reading region | 1440×900: before → after | 1280×800: before → after |
|---|---|---|
| Overlay inspector body | 524.4 → 689.2 px | 424.4 → 589.2 px |
| Pinned inspector body | 487.6 → 689.2 px | 387.6 → 589.2 px |
| Partial-pinned inspector body | 438.0 → 653.2 px | 338.0 → 553.2 px |
| A1 available payload area, overlay | 327.4 → 568.2 px | 209.4 → 468.2 px |
| A1 available payload area, pinned | 290.6 → 568.2 px | 172.6 → 468.2 px |
| A1 available payload area, partial pinned | 241.0 → 532.2 px | 123.0 → 432.2 px |
| Each inner evidence reading region | 451.6×286.8 → 585.6×386.4 px | 371.6×186.8 → 505.6×286.4 px |

Inspector body includes its local controls/error notice. Available payload area means space below the first payload grid down to the viewport bottom; short content need not fill it. Evidence dimensions measure the actual scrollable content, excluding source headers/footer. Source outer widths are approximately 587/507 px after the rail is removed.

Operation names remain 13/16 px, metadata 12 px, JSON 13/20 px and long prose 14/22 px. The documented compact-control exception uses 24–32 px targets instead of the old blanket 32 px minimum, with at least 24×24 px pointer targets. No readable font or operation-row height was reduced.

### Locally exercised debugging workflows

| Review | Observed result |
|---|---|
| S1 · Incorrect answer, both themes | R-1041 remains Completed. Model input false / output true and the cited contradiction remain inspectable. Direct evidence entry and Back restore compose, the open overlay and presentation context. No business-rule or causal-correctness claim is added. |
| S2 · Recovered retry, both themes | A1 ERROR → explicit recorded retry → A2 OK. Recovery does not hide A1 or change the reported Completed Run outcome. Restore filters reinstates ERROR while retaining A2 as the hidden/revealable selection. |
| S3 · Multiple sources, both themes | R-1042 returns to classify-request (triage), not the former stale compose selection. A 616 px pin, Attributes tab, classify query and 1.071–3.213 s window return unchanged. Model/document assignments and focused-source mode persist; a collapsed evaluate-refund-policy branch also survives return. |
| Raw-status variants, both themes | Exact OK, ERROR and UNSET are retained. Missing status displays Unknown; VENDOR_PENDING displays Unknown with its raw value, never OK. These are authored review variants, not a backend schema. |
| Large traces | 100 / 1,000 / 2,100 cases exercised at start, End and an offscreen ID jump. Sampled DOM windows contain 22–28 rows including overscan/active row. Loading 840 → 1,260 preserves order-16-label-api and scroll 13,312 px; capture remains Partial with the missing-parent warning. |
| Matching/navigation | Six loaded shipping-quote/ERROR matches retain ancestors. Next/previous switches A1 → order-7-A1 → A1 without clearing scope/filter. No unloaded or whole-trace search claim. |
| Overlay/resize/keyboard | Native row switching preserves 1046.4 px explorer width and scroll. Escape/outside dismissal retains selected A1; focus returns to the explorer. Pin/unpin and Close/reopen preserve long-output scroll 404.8 px. Width alternative starts at 523 px; Home/min 480, constrained max 598, reset 523, with 440.4 px explorer minimum and an unclipped footer. |
| Long output | The 2,413-character response matches the authored SHA-256 in both Readable reconstruction and parsed JSON. Native-pointer format switches preserve reading position. The sticky toolbar's neutral backdrop prevents prior input text peeking above it; the long response remains 14/22 px. |
| Evidence reading | An actual overflowing S1 source initially lost 13.6 px paired scroll after focus widened it. Separate paired/focused position keys repair this: **13.6 → 13.6 px in both themes**. Inline surrounding-context disclosure is retained rather than treated as an outside-dismissed popup. |
| Navigation preference / investigation | Explicit compact sidebar remains 56 px across Trace, Runs, Evidence and reload, then restores to 200 px. Request investigation is discoverable but disabled and explained; no result, attempt or request success is fabricated. |
| Timing | Shared axis/track origins match; maximum measured width difference is 0.013 px rounding. Bar percentages match recorded start/duration within 0.00005 percentage points. The 16× window retains the precise 21.025 s endpoint; Fit restores 0–336.400 s and A1. |

Sticky-control locator clicks can auto-scroll in the browser adapter; native-pointer checks were used to distinguish that effect from actual UI resets. These are authored-UI checks, not end-to-end platform tests. Historical snapshot resolution is explicitly unavailable: the source footer offers a distinct Open current span action instead of claiming that a fixture URL resolves a backend analysis snapshot.

### Before / after screenshot index

Each cell links the same authored state, size and theme before and after refinement. All are real browser JPEGs without cropping, compositing or generated imagery.

| State | Light 1440×900 | Dark 1440×900 | Light 1280×800 | Dark 1280×800 |
|---|---|---|---|---|
| Tree, 1,000 spans | [before](screenshots/space-efficiency/before/tree-light-1440x900.jpg) / [after](screenshots/space-efficiency/after/tree-light-1440x900.jpg) | [before](screenshots/space-efficiency/before/tree-dark-1440x900.jpg) / [after](screenshots/space-efficiency/after/tree-dark-1440x900.jpg) | [before](screenshots/space-efficiency/before/tree-light-1280x800.jpg) / [after](screenshots/space-efficiency/after/tree-light-1280x800.jpg) | [before](screenshots/space-efficiency/before/tree-dark-1280x800.jpg) / [after](screenshots/space-efficiency/after/tree-dark-1280x800.jpg) |
| Timeline, 1,000 spans | [before](screenshots/space-efficiency/before/timeline-light-1440x900.jpg) / [after](screenshots/space-efficiency/after/timeline-light-1440x900.jpg) | [before](screenshots/space-efficiency/before/timeline-dark-1440x900.jpg) / [after](screenshots/space-efficiency/after/timeline-dark-1440x900.jpg) | [before](screenshots/space-efficiency/before/timeline-light-1280x800.jpg) / [after](screenshots/space-efficiency/after/timeline-light-1280x800.jpg) | [before](screenshots/space-efficiency/before/timeline-dark-1280x800.jpg) / [after](screenshots/space-efficiency/after/timeline-dark-1280x800.jpg) |
| Inspector overlay | [before](screenshots/space-efficiency/before/overlay-light-1440x900.jpg) / [after](screenshots/space-efficiency/after/overlay-light-1440x900.jpg) | [before](screenshots/space-efficiency/before/overlay-dark-1440x900.jpg) / [after](screenshots/space-efficiency/after/overlay-dark-1440x900.jpg) | [before](screenshots/space-efficiency/before/overlay-light-1280x800.jpg) / [after](screenshots/space-efficiency/after/overlay-light-1280x800.jpg) | [before](screenshots/space-efficiency/before/overlay-dark-1280x800.jpg) / [after](screenshots/space-efficiency/after/overlay-dark-1280x800.jpg) |
| Pinned tree | [before](screenshots/space-efficiency/before/pinned-light-1440x900.jpg) / [after](screenshots/space-efficiency/after/pinned-light-1440x900.jpg) | [before](screenshots/space-efficiency/before/pinned-dark-1440x900.jpg) / [after](screenshots/space-efficiency/after/pinned-dark-1440x900.jpg) | [before](screenshots/space-efficiency/before/pinned-light-1280x800.jpg) / [after](screenshots/space-efficiency/after/pinned-light-1280x800.jpg) | [before](screenshots/space-efficiency/before/pinned-dark-1280x800.jpg) / [after](screenshots/space-efficiency/after/pinned-dark-1280x800.jpg) |
| Partial pinned timeline, 2,100 known | [before](screenshots/space-efficiency/before/partial-pinned-timeline-light-1440x900.jpg) / [after](screenshots/space-efficiency/after/partial-pinned-timeline-light-1440x900.jpg) | [before](screenshots/space-efficiency/before/partial-pinned-timeline-dark-1440x900.jpg) / [after](screenshots/space-efficiency/after/partial-pinned-timeline-dark-1440x900.jpg) | [before](screenshots/space-efficiency/before/partial-pinned-timeline-light-1280x800.jpg) / [after](screenshots/space-efficiency/after/partial-pinned-timeline-light-1280x800.jpg) | [before](screenshots/space-efficiency/before/partial-pinned-timeline-dark-1280x800.jpg) / [after](screenshots/space-efficiency/after/partial-pinned-timeline-dark-1280x800.jpg) |
| Evidence Focus, one finding | [before](screenshots/space-efficiency/before/evidence-light-1440x900.jpg) / [after](screenshots/space-efficiency/after/evidence-light-1440x900.jpg) | [before](screenshots/space-efficiency/before/evidence-dark-1440x900.jpg) / [after](screenshots/space-efficiency/after/evidence-dark-1440x900.jpg) | [before](screenshots/space-efficiency/before/evidence-light-1280x800.jpg) / [after](screenshots/space-efficiency/after/evidence-light-1280x800.jpg) | [before](screenshots/space-efficiency/before/evidence-dark-1280x800.jpg) / [after](screenshots/space-efficiency/after/evidence-dark-1280x800.jpg) |

Long response reading captures: [light 1280×800](screenshots/space-efficiency/after/long-output-light-1280x800.jpg), [dark 1280×800](screenshots/space-efficiency/after/long-output-dark-1280x800.jpg). The partial-pinned and evidence before images were the eight native-resolution before comparisons; all 24 before states were captured/measured and receive JPEG-dimension checks.

### Inspectable sources and remaining decisions

Updated files: [design-spec.md](../design-spec.md), [preview.js](preview.js), [preview.css](preview.css), [trace-preview.js](trace-preview.js), [trace-preview.css](trace-preview.css), this log and [density-browser-qa.json](density-browser-qa.json). Open through the unchanged [index.html](index.html) / [local server](serve.mjs). Original fixtures, scale-fixture generator, prior QA and screenshot sets remain preserved.

Useful review URLs: [ordinary Explore](http://127.0.0.1:8766/?screen=trace&size=1000&theme=dark), [partial pinned timeline](http://127.0.0.1:8766/?screen=trace&size=2100&view=timeline&span=a1&panel=pinned&from=0&to=43600&theme=light), [multiple-findings authored variant](http://127.0.0.1:8766/?screen=evidence&run=1042&variant=multiple-findings&theme=light), [raw-status authored variant](http://127.0.0.1:8766/?screen=trace&size=100&variant=raw-statuses&theme=dark).

- **Product review (P6):** first-use expanded/compact default, lifetime/scope of pin/width preference, optional multi-finding list and a redesigned Replace left/right citation interaction remain open. Existing explicit sidebar preferences are preserved. Current citation chips explicitly name their retained Left/A assignment and possible pair exchange.
- **Counting (P2):** Runs' supplied recorded-error groups and individual ERROR span matches have different units; no frontend aggregation policy was invented. Exact production vocabulary remains unresolved.
- **Backend/investigation dependencies:** B3/B4/P3 must settle structural bounds/counts, ancestor lookup, whole-trace search and selected-payload reads. B5/E4 govern actual investigation request/retry; B7/E2 govern historical inspection. E1–E4 investigation/evidence decisions remain open. No endpoints, response schemas or investigator architecture were added.
- **Design trade-offs:** the overlay covers right-side exploration data; Pin provides simultaneous views. Narrow pinned timelines still ellipsize deep names, with full identity in the ancestor path/Details/inspector. The label/time divider remains fixed. Infrequent controls and full provenance need an explicit disclosure action. The wider evidence view may fit a source completely; no artificial content was added to manufacture scrolling.
- **Unverified gates:** full screen-reader interoperability of the virtualized tree, phone/touch layouts, 200%/400% zoom, text-spacing, every asynchronous failure/redaction/late-response case and paragraph anchoring across arbitrary reflow. Local disclosure/resize/focus tests are not WCAG conformance.
- **Simulation boundary:** all data exists locally. Row windowing and selected-payload rendering do not establish network paging, latency, memory ceilings or production large-trace performance. Browser presentation memory is not authentication, authorization or an approved production cache lifecycle.

**Spec deltas:** the compact secondary-control baseline, automatic rendering of available local selected content, collapsed single-finding rail and compact metadata are explicit approved presentation refinements. Historical-resolution gating and raw-status truth fulfill existing semantics. No intentional evidence/timing deviation is introduced. The remaining product gates above are not declared complete.

**Scope verification:** changes stay in docs/frontend. All 77 tracked production/core-document files in the protected baseline retain their hashes; the Git path/status list retains pre-existing work. No production React/backend/SDK edits, dependency installation, commits or pushes.

## Trace Explore / overlay refinement — 15 October 2026

**Scope:** the approved Trace Detail layout change only. The specification and isolated HTML/CSS/JavaScript study were refined; production code and API contracts were not implemented. Run Explorer and Evidence Focus retain their previous rendering. The P0/P1 review below is historical: its permanent 336 px Trace navigator and four Trace captures are superseded by this section. Its Run Explorer/Evidence Focus captures and research provenance remain valid historical evidence.

### Open and inspect the current Trace study

Use the existing `node docs/frontend/design-preview/serve.mjs` command from the repository root. Reuse an already running server; it serves files on `127.0.0.1:8766` and provides no product API. Open the [100-span tree](http://127.0.0.1:8766/?screen=trace&size=100&theme=light), [1,000-span Explore](http://127.0.0.1:8766/?screen=trace&size=1000&theme=dark), or [2,100-span partial fixture](http://127.0.0.1:8766/?screen=trace&size=2100&theme=light&view=timeline&from=0&to=43600). Theme controls use the existing coordinated tokens. The Sample data badge remains visible.

| Updated artifact | Exact repository path |
|---|---|
| Design requirements | [docs/frontend/design-spec.md](../design-spec.md), sections 4.2, 4.4, 6, 8, 10–12 |
| Entry and shared renderer integration | [docs/frontend/design-preview/index.html](index.html), [preview.js](preview.js) |
| Trace-only layout and interactions | [docs/frontend/design-preview/trace-preview.css](trace-preview.css), [trace-preview.js](trace-preview.js) |
| Authored scale fixtures | [docs/frontend/design-preview/trace-fixtures.js](trace-fixtures.js) |
| Current measurements and interaction evidence | [docs/frontend/design-preview/trace-browser-qa.json](trace-browser-qa.json) |
| Current screenshots | `docs/frontend/design-preview/screenshots/trace-explore/` |

`preview.css`, the original `fixtures.js`, earlier screenshots and research captures are preserved. The new module is a design study, not a proposed production component or dependency choice.

### Concrete before / after

| Area | Previous Trace preview | Current observed result |
|---|---|---|
| Default workspace | Permanent 336 px execution navigator beside the inspector. | Full-width tree/timeline; no initial inspector or automatic error selection. Tree gains ID, raw status and recorded start columns. |
| Occasional inspection | Persistent split consumed execution width. | Non-modal overlay measures 600 px at 1440 and 523 px at 1280. Underlying explorer width stays 1206.4 / 1046.4 px respectively. It is occluded, not shifted. |
| Comparison | One fixed arrangement. | Explicit Pin/Unpin; keyboard and pointer resizing, plus a width slider. Explorer minimum 440 px; inspector range 480–640 px subject to available workspace. |
| Trace size | Ten authored operations in the principal retry example. | Exact 100 / 1,000 / 2,100-span fixtures, nine hierarchy levels, direct-child counts, ancestor context, loaded-scope filters and ID jump. Actual DOM row windowing is exercised. |
| Timing | Common axis for the small fixture. | Common measured axis through zoom, Fit and overview panning, with original timing text and explicit out-of-window rows. No duration aggregation or causal arrows. |
| Loading/completeness | Small fully present fixture. | The 2,100 sample exposes 840 structural records first; local Load next 420 retains the visible anchor. Partial capture and missing-parent warning remain independent. Payload is revealed separately on demand. |
| Narrow inspection | Short payloads could still advertise pairing despite enforced stacking. | Below 600 px the inspector displays Compact · Stacked; 14/22 px long prose and 13/20 px JSON retain their size. |

### Desktop screenshot matrix — 16 captures

All images are actual browser JPEG captures at their stated CSS-pixel dimensions, approximately DPR 1, without cropping or compositing. Every image was opened at native resolution after its final revision. The tree is the default 1,000-span Explore state. Timeline captures deliberately show a 16× window (0–21.025 s) so short operations are visible; a fresh Timeline starts at Fit run. Overlay shows failed A1 with a recorded recovery link; pinned view shows A2 and captured JSON. These are alternative review states of the same authored Run.

| State | Light 1440×900 | Dark 1440×900 | Light 1280×800 | Dark 1280×800 |
|---|---|---|---|---|
| Full-width tree | [image](screenshots/trace-explore/full-tree-light-1440x900.jpg) | [image](screenshots/trace-explore/full-tree-dark-1440x900.jpg) | [image](screenshots/trace-explore/full-tree-light-1280x800.jpg) | [image](screenshots/trace-explore/full-tree-dark-1280x800.jpg) |
| Full-width timeline | [image](screenshots/trace-explore/full-timeline-light-1440x900.jpg) | [image](screenshots/trace-explore/full-timeline-dark-1440x900.jpg) | [image](screenshots/trace-explore/full-timeline-light-1280x800.jpg) | [image](screenshots/trace-explore/full-timeline-dark-1280x800.jpg) |
| Inspector overlay | [image](screenshots/trace-explore/inspector-overlay-light-1440x900.jpg) | [image](screenshots/trace-explore/inspector-overlay-dark-1440x900.jpg) | [image](screenshots/trace-explore/inspector-overlay-light-1280x800.jpg) | [image](screenshots/trace-explore/inspector-overlay-dark-1280x800.jpg) |
| Pinned split | [image](screenshots/trace-explore/pinned-split-light-1440x900.jpg) | [image](screenshots/trace-explore/pinned-split-dark-1440x900.jpg) | [image](screenshots/trace-explore/pinned-split-light-1280x800.jpg) | [image](screenshots/trace-explore/pinned-split-dark-1280x800.jpg) |

Eight supplemental captures were also opened at native resolution:

| Focus | Light | Dark |
|---|---|---|
| 100-span tree, 1280×800 | [image](screenshots/trace-explore/scale-100-tree-light-1280x800.jpg) | [image](screenshots/trace-explore/scale-100-tree-dark-1280x800.jpg) |
| 2,100-span partial timeline, 1440×900 | [image](screenshots/trace-explore/scale-2100-partial-timeline-light-1440x900.jpg) | [image](screenshots/trace-explore/scale-2100-partial-timeline-dark-1440x900.jpg) |
| Long model response, 1280×800 | [image](screenshots/trace-explore/long-output-overlay-light-1280x800.jpg) | [image](screenshots/trace-explore/long-output-overlay-dark-1280x800.jpg) |
| Single-pane fallback, 768×1024 | [image](screenshots/trace-explore/single-pane-light-768x1024.jpg) | [image](screenshots/trace-explore/single-pane-dark-768x1024.jpg) |

### Locally verified interactions and geometry

- **Overlay, both themes:** direct pointer selection A1 → A2 switches in one action. Open/switch/pin/unpin/Escape/outside dismissal retain a 416 px explorer scroll and the 0–21.025 s time window. Overlay opening does not replace the explorer scroll container or change its width. Closing retains the selected ID. A visible search control receives focus from the same outside click that dismisses the overlay.
- **Pin and resize:** selected span and Attributes tab survive pin/unpin. ArrowLeft changes a 600 px pinned inspector to 616 px. Escape leaves pinned inspection open. Pointer drag changes 598 → 566 px at 1280. At the constrained maximum, the explorer remains 440.4 px wide, timeline rows have no horizontal overflow, and the footer remains inside the workspace.
- **Hierarchy/windowing:** start, middle jump and End were exercised for all three sizes. The sampled windows contained 17–25 DOM rows rather than all loaded records. This includes overscan and an offscreen active item. The 2,100 fixture initially searches 840 records; loading to 1,260 retains `order-16-label-api` and scroll 13,312 px. A missing recorded parent remains a warning, not a manufactured span.
- **Filters/reveal:** the 1,000 fixture's shipping-quote + ERROR query produces six direct matches with ancestors retained separately. An excluded A2 stays selected; Reveal temporarily relaxes filters and Restore recovers them. Searching an unloaded order returns zero matches explicitly within loaded structure. An unknown-total variant says total unknown rather than deriving it from local records.
- **Timing:** all measured track origins agree with the axis; their width difference is below 0.02 px rounding at 1440. Fit selected uses a minimum 1/64-Run window; overview End pans to the Run end, retains A1 and labels it Outside window. Fit run restores 0–336.400 s and disables unnecessary panning. Tree → Timeline retains selection and a middle-list scroll of 416 px. At list end, scroll pixels clamp to each view's different viewport height; returning restores the end position.
- **Inspector:** Content/Attributes/Events/Errors, Readable/Captured JSON, capture markers and explicit retry navigation remain available. Long-content pin/unpin retains 380 px inspector reading position and 608 px explorer scroll. Close/reopen was rechecked at 380 → 380 px after fixing hidden-panel scroll restoration. The same-width reading position is preserved; paragraph anchoring across a responsive reflow is not established.
- **Responsive/focus:** at 768×1024 the single pane fits its 680 px workbench without page overflow; Pin is unavailable, covered execution is inert/hidden to assistive reading, and Back returns focus to the explorer. Growing back restores the requested desktop pin mode and selected span. Desktop F6/Focus inspector and Escape return were exercised without a modal focus trap.
- **Scope preservation:** Run Explorer and Evidence Focus rendered application-markup hashes match their before-change values in both themes. Original shared CSS/fixtures and protected production files are checked separately from this DOM comparison.

Native-resolution inspection found legible hierarchy/type labels, bounded footers, readable error/retry content and consistent theme geometry in the captured states. Workbench-only scroll is intentional. No text-size reduction was used to force panes to fit.

### Review repairs, trade-offs and remaining requirements

During review, pinned grid rows initially pushed the footer below the workspace; bounded grid sizing corrected it. Covered toolbar controls were removed from Tab order while occluded. Payload reading position was initially restored while the inspector was hidden; revealing the panel before restoring scroll corrected the measured 380 → 0 reset. Non-retry fixture branches now describe successful quote capture rather than borrowing the retry branch's recovery narrative. These repairs are recorded in the QA artifact; they do not establish product-wide regression coverage.

The overlay intentionally covers right-side execution columns/controls. The left-edge focus/reveal controls and hierarchy remain usable; Pin provides simultaneous visibility. Pinned controls wrap and reduce the visible row count at 1280; deep names can ellipsize, with the inspector/path providing identity. Short payloads stack below 600 px. Fit run compresses short spans in a multi-minute Run, making explicit zoom/overview navigation necessary. These are layout trade-offs within the approved direction, not silent changes to evidence semantics.

**Accessibility requirements remain:** actual screen-reader review of virtualized parent/group ownership, active-descendant announcements, tree disclosure controls, range controls and focus return; full 200%/400% zoom, text-spacing and 390/320 px reflow checks; rendered-state contrast and touch-target audits. The local tree declares levels/positions/set sizes and preserves an active row, but flat DOM windowing is not proof of complete tree accessibility. See the specification's linked WAI-ARIA guidance. Narrow fallback and keyboard checks are evidence for those exercised cases only.

**Simulation limits:** every fixture and payload already exists in local JavaScript. Windowing reduces rendered rows; Load next and Load captured payload simulate availability. No network paging, trace-wide search, payload latency/race protection, retention, live updates, authorization, FPS, memory ceiling or production 1,000+ span performance has been verified. Loading/failure/redaction semantics are specified but not all asynchronous variants are exercised. Full history/reload restoration of expansion and cross-workspace pin preference remain implementation work. Do not treat these screenshots as backend capability evidence.

**Approval / contract questions:** exact pane widths and the 928 px workbench fallback are review baselines; confirm whether pin/width preference should persist per Run, workspace or developer across sessions. B3/B4/P3 must settle structural bounds, trustworthy known/unknown counts, ancestor lookup, whole-trace query support and selected-payload availability before API-dependent acceptance. Existing P2 error/retry aggregation and E1–E4 investigation/evidence questions remain open. This refinement does not choose those contracts or reopen the approved overlay layout.

**Spec deviations / unfulfilled product gates:** no intentional layout or semantic deviation in the captured desktop states. The preview exercises a bounded subset of the specification: AT interoperability, all failure/late-response cases, narrow-phone reflow and production persistence/performance remain unverified. Acceptance criteria are product gates, not a claim that this visual study completes them.

## Historical P0/P1 visual refinement review — 15 October 2026

**Status:** one focused refinement pass. All 12 revised desktop baselines and six focused captures were opened individually at native resolution. No unresolved P0 defect was found in the exercised desktop fixtures. This is a static design review, not product implementation, investigator validation, or accessibility conformance. Exact accents and broader acceptance gates remain open.

## Open and inspect

From the original repository root, using the existing Node runtime (no installation):

```powershell
node docs/frontend/design-preview/serve.mjs
```

Open [Runs](http://127.0.0.1:8766/?screen=runs&theme=light&accent=steel), [Trace Detail](http://127.0.0.1:8766/?screen=trace&run=1040&span=a1&theme=light&accent=steel), or [Evidence Focus](http://127.0.0.1:8766/?screen=evidence&run=1042&theme=dark&accent=steel). The server binds only to `127.0.0.1:8766`, serves design files and implements no product API. Reuse it if already running; stop a server you started with Ctrl+C. The HTML also loads its relative scripts/styles directly.

Append `review=1` to expose separate scenario/accent controls, hidden from baseline product surfaces. `accent=steel` and `accent=blue` trial one interaction family at a time. The **Sample data** badge remains visible. Disabled project/setup/settings/refresh actions make no requests.

| Artifact | Exact repository path / source |
|---|---|
| Requirements | [docs/frontend/design-spec.md](../design-spec.md) |
| Supplied comparison review | [docs/frontend/LANGFUSE_OJT_FRONTEND_UI_REFINEMENT_REVIEW.md](../LANGFUSE_OJT_FRONTEND_UI_REFINEMENT_REVIEW.md) |
| Static entry | [docs/frontend/design-preview/index.html](index.html) |
| Shared themes/geometry | [docs/frontend/design-preview/preview.css](preview.css) |
| Local rendering/interactions | [docs/frontend/design-preview/preview.js](preview.js) |
| Authored fixtures | [docs/frontend/design-preview/fixtures.js](fixtures.js) |
| Read-only artifact server | [docs/frontend/design-preview/serve.mjs](serve.mjs) |
| Measurements/local checks | [docs/frontend/design-preview/browser-qa.json](browser-qa.json) |
| Research URLs and 20 captures | [docs/frontend/research/evidence-register.md](../research/evidence-register.md) |

The requested `langfuse-comparison-review.md` was absent. The uppercase file above contains that execution brief; it was read completely and preserved unchanged. The full specification, existing previews, HLD/PRD context and prior research were inspected before refinement.

## Independently verified references

The [official tracing image](https://langfuse.com/images/docs/tracing-overview.png) visibly separates selected-operation identity and stacks input/output ([LF-06](../research/LF-06-official-overview-2026-10-15.jpg)). Its exact release marker was not independently verified. The [overview](https://langfuse.com/docs/observability/overview), [March 2025 announcement](https://langfuse.com/changelog/2025-03-19-new-trace-view), [August 2026 timeline announcement](https://langfuse.com/changelog/2026-08-28-responsive-timeline), [agent-graph documentation](https://langfuse.com/docs/observability/features/agent-graphs) and [demo entry](https://langfuse.com/docs/demo) were accessible and checked as documentation claims.

The shared live trace showed v4.59.0. Selecting `chat` and switching Formatted → Raw → Timeline retained that observation ([LF-07](../research/LF-07-model-2026-10-15.jpg), [LF-08](../research/LF-08-timeline-2026-10-15.jpg)): directly observed behavior. One Raw tab measured 12/12 px system sans-serif, not a full typography audit. Official images support hierarchy, historical announcements are not current deployment proof. No competitor scale, retry or accessibility test was performed. Documented timing/nesting-based graph inference conflicts with our recorded-only rule and was not adopted. No Langfuse equivalent is claimed for our evidence workspace.

## Concrete before / after

The [previous measurements](screenshots/before-p0-p1/browser-qa.json) and all 12 previous images remain under `screenshots/before-p0-p1/`, with the same filenames as the revised set.

| Area | Before | Revised result |
|---|---|---|
| Run identity | Ten rows displayed one hard-coded workload name and similar ID fragments. | Eight distinct, linked workload fixtures across refund, NovaCloud RAG, fulfillment and Meridian research. Names 14/20 px; IDs 12/16 px with separate copy. Empty table space is intentional. |
| Operation hierarchy | Mixed text/Unicode symbols; 12 px names. | One SVG glyph language, explicit type/error/retry text. Names 13/16 px, supporting type/duration 12 px; hierarchy and 32 px rows retained. |
| Header hierarchy | Run identity, full trace ID and actions competed. | 20 px Run title, compact copyable trace ID, independent outcome/completeness/time; 16/24 px selected-span heading. |
| Content | Paired JSON was the general layout; presentation labels did not switch rendering. | Real Readable/Captured JSON modes; recorded roles/messages, arguments/results and retrieval context; full-width stacked long model content. Pair/stack choice for short structured values. |
| Timeline | Relative formulas existed, but flex-sized labels shifted plot origins and widths. | Fixed grid aligns all ten tracks with the axis: x=378.4 px, width=106.4 px at 1280. A1 starts at 9.10%, spans 49.63%; A2 starts at 60.38%, spans 13.23%, matching 2.418 s timing. No causal arrows. |
| Investigation entry | Trace header exposed Evidence Focus even with zero findings. | Only positive grounded findings expose evidence links. Zero/unrequested/failed states preserve trace access. Direct zero-findings evidence URL gives an explicit empty state; no invented history. |
| Supporting text | Several IDs, provenance labels and controls used 11 px. | No visible product text below 12 px in the 12 baselines or six focused captures. Primary data remains 13–14 px without enlarging rows. |
| Evidence readability | Values 13 px; prose 13/21 px; about 148 px reading height at 1280. | Values 16/24 px; prose 14/22 px. Compact provenance provides 187 px reading height at 1280 and 287 px at 1440 (previously about 248). Source widths remain 373/453 px; stronger neutral highlights. |
| Evidence navigation | Two fixed visible sources; internal preview qualifiers competed. | Explicit A/B view slots, full-width focus/pair restore, all citations reachable, source-heading focus; per-source scroll retained on local rerenders. |
| Shell/accent | Unavailable Knowledge and internal workspace/reviewer labels; neutral emphasis. | Knowledge omitted; consistent project context plus Sample data disclosure. Steel and Cool blue trialed in both themes, separately from explicit-error red. |

These are authored presentation fixtures, not emitted telemetry, API schemas or investigator output. Existing example documentation supplied workload domains only; no example/provider was run. Eight runs / 63 spans pass ID format/uniqueness, parentage, service identity, timing containment, duration and retry-target checks, allowing R-1039's explicitly partial missing parent. S1–S3 meanings remain unchanged.

## Screenshot index

Real viewport-only browser JPEGs at 100% zoom, effective DPR approximately 1. JPEG dimensions were checked; capture settled after network idle and state-aware observation. No cropping, generation, compositing or resizing. All 18 final saved images were opened individually with original-resolution inspection.

| Screen | 1440 × 900 light | 1440 × 900 dark | 1280 × 800 light | 1280 × 800 dark |
|---|---|---|---|---|
| Run Explorer | [Image](screenshots/run-explorer-light-1440x900.jpg) | [Image](screenshots/run-explorer-dark-1440x900.jpg) | [Image](screenshots/run-explorer-light-1280x800.jpg) | [Image](screenshots/run-explorer-dark-1280x800.jpg) |
| Trace Detail | [Image](screenshots/trace-detail-light-1440x900.jpg) | [Image](screenshots/trace-detail-dark-1440x900.jpg) | [Image](screenshots/trace-detail-light-1280x800.jpg) | [Image](screenshots/trace-detail-dark-1280x800.jpg) |
| Evidence Focus | [Image](screenshots/evidence-focus-light-1440x900.jpg) | [Image](screenshots/evidence-focus-dark-1440x900.jpg) | [Image](screenshots/evidence-focus-light-1280x800.jpg) | [Image](screenshots/evidence-focus-dark-1280x800.jpg) |

Baselines use Steel, S2/R-1040/A1 in Trace Detail, and S3/R-1042 retrieval/document pairing in Evidence Focus.

| Focused state | Light | Dark |
|---|---|---|
| Long response, Readable, 1280 × 800 | [Image](screenshots/focused/long-output-light-1280x800.jpg) | [Image](screenshots/focused/long-output-dark-1280x800.jpg) |
| Recovered A2, explicit relation, Timeline/JSON, 1440 × 900 | [Image](screenshots/focused/recovered-retry-timeline-light-1440x900.jpg) | [Image](screenshots/focused/recovered-retry-timeline-dark-1440x900.jpg) |
| Cool blue, same A1/Tree state as Steel baseline, 1280 × 800 | [Image](screenshots/focused/accent-cool-blue-light-1280x800.jpg) | [Image](screenshots/focused/accent-cool-blue-dark-1280x800.jpg) |

## Validation and limits

| Check | Observed result |
|---|---|
| Geometry | All 12 baseline JPEGs match requested dimensions; no page overflow. Sidebar 200 px, navigator 336 px, inspector 866/706 px. Eight table rows remain 48 px; operation rows 32 px in both themes/sizes. Source panes exceed the 360 px minimum. |
| S1, both themes | Tool false → model input false / output true; Run Completed, zero recorded errors. Evidence compares false / false→true. Tree/Timeline retains compose-response; evidence return preserves that span and Timeline. No business-rule correctness or causal conclusion added. |
| S2, both themes | A1 timeout → explicit Recovered by attempt 2 → A2 recorded `retry_of` → return A1. A2 retained across views. Run Completed, telemetry Complete, supplied error group 1, findings 0; no evidence link. Counts are supplied fixtures, not frontend aggregation policy. |
| S3, both themes | Initial 30/14 days; model/retrieval reassignment retains three citations and snapshot identity. Focus A expands 373 px to 754 px at 1280; Compare restores pair. A citation activated while B is focused reveals A and focuses its heading. B scrolled 92 px while A stayed at zero. |
| Long output, both themes | R-1036: 374 words / 2,413 characters, two recorded message roles. Stacked panes share 659 px inner width at 1280, prose 14/22 px. Readable reconstruction and Captured JSON each match fixture SHA-256. Output jump scrolls only inspector, below sticky toolbar. Wrap-off overflows only the code region; page stays 1280 px. |
| Local interaction | Disclosure preserves inspector selection; Reveal restores hidden ancestors. Search retains matching ancestors and persists into Timeline; reveal is announced and Restore restores query. ArrowDown moves focus without selection; Enter selects. Theme switch retains A1. Sidebar choice survives navigation/reload, expanded again for capture. Failed filter returns R-1038 and retains visible value. |
| Fallback samples | R-1039 missing-parent warning; R-1038 independently failed execution/analysis; unavailable fixed B retains A, marks absence and disables copy. Zero-findings URL is explicit. These are sampled local checks, not a full state matrix. |
| Contrast samples | Steel interaction on panel: 6.24:1 light / 9.53:1 dark; on selected: 4.64 / 6.78. Cool blue: 7.08 / 8.89; on selected: 5.26 / 6.33. Error on notice: 6.05 / 8.78. Cited JSON on highlight: 12.82 / 10.11. Samples clear relevant thresholds; no WCAG-conformance claim. |
| Source checks | Node syntax and fixture consistency checks passed; browser console returned no errors/warnings at the end. No production build/test or API/provider call was appropriate to this design-only pass. |

## Compromises, deviations and open decisions

- **Palette approval:** recommend Steel for quieter interaction emphasis; Cool blue is more prominent. Exact tokens and explicit-error red remain proposals. Neither changes evidence/status meaning.
- **Pane geometry:** long names ellipsize, particularly in Timeline's 148 px label column. Full selected headers, accessible labels and textual timing retain identity. The 106 px plot is an overview. Static splitters do not resize; Fit/zoom and advanced rendering remain future work.
- **Illustrative states:** Trace baselines intentionally start at A1 rather than default Run overview. UTC/two-hour window is a fixture label. Duration filters, operation/status facets, sorting, pagination and time selection remain requirements; omitted/disabled controls do not advertise functioning backend behavior.
- **Bounded state preservation:** selection/view survives evidence return; pane scroll survives local rerenders; sidebar/theme preferences survive navigation/reload. Full browser-history restoration of queries, expansion, source pairs and scroll is unimplemented. Surrounding-context disclosure may reset on rerender; no cross-device preference claim.
- **Bounded coverage:** long model, short tool, failure and evidence cases above were exercised. Degenerate/invalid timing, every availability distinction, payload limits and large-trace performance are not exhaustively covered. Full custom/unknown renderer coverage remains an acceptance gate.
- **Accessibility:** tree focus/selection and citation heading focus are exercised. Type-ahead, complete tabs/screen-reader behavior, resizing alternatives, announcements, 200%/400% zoom and V4 mobile/reflow remain unverified. Do not infer full V1–V4/U1–U10 acceptance from desktop images.
- **Snapshot dependencies:** Inspect analyzed span opens the matching immutable local fixture, not a historical backend snapshot. No newer evidence is substituted. E1–E4 still govern grounding, retention/resolution, citation ranges and lifecycle; no investigator architecture is chosen.
- **Backend ownership:** disconnected email/password/expiration studies remain unchanged with disabled credential entry/submission. FastAPI exclusively verifies passwords, manages sessions and authorizes data. B10/P5 and other B/P dependencies stay provisional; no endpoints or client access-control scheme added. Clipboard behavior was not tested.

## Scope check

Changes are confined to `docs/frontend/`: targeted specification edits, isolated previews, dated research evidence, regenerated screenshots and this record. The supplied comparison review and prior captures are preserved. No dependencies, production frontend/backend/SDK/investigator edits, commits, merges or pushes. All 71 tracked frontend/backend/SDK files retain their starting SHA-256 hashes; Git's path/status list matches the baseline, including pre-existing uncommitted work. Local-link, JPEG-dimension/count, authored-fixture and changed-text whitespace checks returned no issues. Unrelated SDK changes were not edited.
