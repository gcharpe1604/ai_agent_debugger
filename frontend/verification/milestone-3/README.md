# Milestone 3 verification — 16 October 2026

Fixture-backed investigation presentation and Evidence Focus are implemented. This is presentation over authored sample data, not investigator output, backend integration or live telemetry. Existing Run Explorer, Tree, Timeline, overlay/pinned inspector and themes are retained. No dependencies, commits, merges or pushes; no SDK/backend/architecture or approved static-preview edits.

## Verified behavior

- Runs positive finding counts open the scoped Evidence route; other investigation states remain independent from execution outcome, capture and recorded error-operation counts. Trace uses a compact status/details control, with attempt/snapshot/limitations. Disconnected request/retry cannot mutate the supplied analysis.
- Evidence uses no permanent findings rail. A selector appears for multiple supplied findings; one source uses full width, two or more use two panes. All numbered citations remain reachable. Explicit A/B selectors swap occupied assignments; activating a numbered citation names its Source A destination. Source focus/compare retains per-source paired/focused reading positions.
- Captured sources are immutable fixture copies, read through a separate adapter. Source name, exact field/passage, document revision and analyzed snapshot are visible; full identifiers and resolved snapshot association expand in Details. No current trace read resolves evidence. Historical inspection is unavailable; Open current span is explicitly separate.
- Exact own-property paths or validated quote ranges control highlights. False, zero, null, empty strings and arrays retain their values. Readable and Captured JSON remain inert text; HTML-like content does not produce an element or request. An unresolved path keeps captured context readable without guessing a highlight. Missing/mismatched historical sources expose no value, highlight or copy action.
- Tagged, cancelled source reads prevent older responses from populating a newly assigned source. A failed pane has its own Retry; the finding and other pane stay available. Pending, not-requested, completed-positive, completed-zero, failed and skipped/unavailable presentations are covered.

## Automated checks

**104 tests passed in 12 files**, including all 79 Milestone 1/2A/2B tests. ESLint passed (exit 0); production build passed (57 modules). Final bundle: **317.66 kB JS / 97.26 kB gzip; 40.81 kB CSS / 7.96 kB gzip**. Scoped `git diff --check -- frontend` passed; Git emitted informational LF/CRLF notices.

Full test results (historical report removed during cleanup) include project scoping, cancellation, immutable sources, exact resolution, one/two/three citations, source pairing/focus/reading, missing/mismatched evidence, local read failure, stale responses, keyboard citation assignment, trace restoration and all supplied investigation states. Existing tree, timeline, retry, resize, filtering, pagination and preference tests passed unchanged. After that suite, the only product edit was a mobile-only CSS target-size rule; its build and browser layout were checked without repeating the entire suite.

## Browser checks

Production Vite preview at `http://127.0.0.1:5174/`. Observed interaction record (historical report removed during cleanup). No backend/provider calls. Browser warning/error logs were empty in the final sampled session.

| Workflow | Observed result |
|---|---|
| S1 · Incorrect reasoning, both themes/sizes | Tool false and model output true are highlighted in distinct sources. Run remains Completed; limitations do not assert business-rule correctness or causal proof. Third model-input citation stays reachable. |
| S2 · Recovered retry, both themes/sizes | Recorded A1 ERROR → A2 OK link keeps the inspector open. A1 remains listed; Run stays Completed and there is no finding-evidence link for zero findings. |
| S3 · Multi-source | Retrieval/document show 30/14 days. Assigning model input to A leaves the fixed document in B. Captured JSON parses to the stored value 30 and highlights its exact field. |
| Reading restoration | B scrolled to **180 px**, A remained at 0. Focus B → Compare restored 180 px; current-span navigation and evidence return also restored it. |
| Ordinary Back to trace | Restored `classify-request` ID `7b83c2d900000003`, pinned Timeline, Attributes, `classify` query and exact 1.071–3.213 s time window. No stale compose selection. |
| Cited current span → evidence | Intentionally selected compose-response while retaining the prior filter/window/pin. Reveal stayed explicit. Back to evidence restored model/document assignments, same finding and 180 px reading. Browser Back/Forward also retained context. |
| Historical variants | Revision 6 unavailable and mismatched source snapshot are explicit, with no substitution/highlight/copy. Earlier review sample has two findings and a single-source layout. |
| Existing workspaces | Run Explorer finding link opened the correct scoped run. Overlay Tree → Timeline retained A2 and overlay mode. All baseline retry captures retained the pinned inspector. |
| Narrow layout | At 390×844, sources stack and content scrolls vertically; document width did not exceed the viewport. Evidence assignment controls measured 44 px high. This is a spot check, not full mobile/reflow conformance. |

## Screenshots

**18 real browser PNGs**, individually displayed and visually inspected at native output dimensions. All dimensions passed; no horizontal page overflow in the sampled captures. CDP viewport/DPR settings were normalized at capture to one output pixel per CSS pixel; no image generation, compositing or post-processing. Geometry and URL records (historical report removed during cleanup). Temporary viewport overrides were cleared afterward. The 12 baselines precede only the mobile-only CSS adjustment; desktop styles/behavior were unchanged.

| Scenario | 1440 light | 1440 dark | 1280 light | 1280 dark |
|---|---|---|---|---|
| S1 · Incorrect reasoning | [PNG](incorrect-reasoning-light-1440x900.png) | [PNG](incorrect-reasoning-dark-1440x900.png) | [PNG](incorrect-reasoning-light-1280x800.png) | [PNG](incorrect-reasoning-dark-1280x800.png) |
| S2 · Recovered retry | [PNG](recovered-retry-light-1440x900.png) | [PNG](recovered-retry-dark-1440x900.png) | [PNG](recovered-retry-light-1280x800.png) | [PNG](recovered-retry-dark-1280x800.png) |
| S3 · Multiple sources | [PNG](multi-source-light-1440x900.png) | [PNG](multi-source-dark-1440x900.png) | [PNG](multi-source-light-1280x800.png) | [PNG](multi-source-dark-1280x800.png) |

Focused checks: [historical unavailable](historical-unavailable-light-1280x800.png), [snapshot mismatch](snapshot-mismatch-dark-1280x800.png), [captured JSON](multi-source-json-dark-1440x900.png), [Run Explorer](run-explorer-light-1280x800.png), [Tree overlay](tree-overlay-light-1280x800.png), [stacked evidence](stacked-evidence-dark-390x844.png).

## Fidelity, compromises and integration requirements

The approved rail-free layout, typography, semantic themes, restrained highlights and source identities remain. S3 reading regions measured **586×384 px at 1440** and **506×284 px at 1280**, matching across themes (integer client sizes). The approved static preview reported about 585.6×386.4 / 505.6×286.4 px; the selectable presentation control costs approximately 2–3 px of reading height. Formats use a compact labeled select within the cited-value row, avoiding another toolbar. The optional attempt selector appears because this fixture actually supplies an earlier result. S1 separates input and output into exact individual citations rather than combining both fields in one source.

UI-only evidence/trace caches last for the mounted app session, not across reloads or devices. URLs retain scoped attempt/finding/source/span/window identities; expanded branches and exact reading positions need the in-memory context. Extremely long findings/identifiers, 200%/400% reflow and screen-reader interoperability are not comprehensively audited. The narrow shell retains its compact rail and nested workspace/content scrolling; mobile reading ergonomics remain an integration review item. No production latency, payload-size or investigator-quality guarantee follows from these fixtures.

Pending **B5–B7 / E1–E4**: approved attempt lifecycle/refresh/request/retry behavior and retained results; grounding/category/priority meanings; exact immutable analysis-input/source binding and retention; citation normalization/ranges; bounded evidence reads and access/error policy; whether historical full-trace inspection is supported. The adapter's local methods/objects are not proposed wire contracts. Request execution, polling, analysis generation, historical trace reconstruction, auth and live telemetry remain unimplemented by design. No new product approval is needed for this presentation milestone; those integration contracts require owner approval before real-data work.

## Changed files

New: `src/data/{investigationFixtures.js,investigationRepository.js,investigationRepository.test.js}`; `src/features/evidence/{EvidencePage.jsx,EvidenceWorkspace.jsx,SourcePane.jsx,CapturedEvidence.jsx,InvestigationControl.jsx,useInvestigationRead.js,evidenceState.js,evidence.css,Evidence.test.jsx,evidenceState.test.js}`; `MILESTONE-3.md`; this verification directory.

Updated: `src/app/{App.jsx,routes.jsx}`, `src/components/AppShell.jsx` (inline evidence disclosures persist while popovers retain dismissal), `src/pages/RunDetailPage.jsx`, `src/features/runs/RunTable.jsx`, `src/features/trace/traceState.js` (strip evidence keys from Runs return query), and frontend `README.md`. Earlier uncommitted milestone files and SDK/backend/docs work were not restored or rewritten.
