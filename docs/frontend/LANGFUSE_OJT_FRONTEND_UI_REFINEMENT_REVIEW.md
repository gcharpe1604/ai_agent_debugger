# OJT Agent Debugger — Langfuse UI Comparison & Targeted Refinement Review

**Review date:** 15 October 2026
**Status:** Proposed refinements to an approved design direction; **not** a new frontend architecture or permission to implement production React.
**Recommended repository destination:** `docs/frontend/langfuse-comparison-review.md`
**Primary local source of truth:** `docs/frontend/design-spec.md` (latest version in original repository).
**Evidence reviewed:** Twelve supplied visual-preview JPGs at 1440×900 and 1280×800, light and dark, across Run Explorer, Trace Detail, Evidence Focus. These are static captures, so behavioral proposals below are **not** claims of implemented interaction.

## 1. Sources and evidence boundary

**Competitor references:**
- Langfuse official trace screenshot: https://langfuse.com/images/docs/tracing-overview.png — visual reference, not proof that its exact version is today's deployed UI. The image identifies Langfuse v3.82.0.
- Langfuse official tracing overview: https://langfuse.com/docs/observability/overview — documented trace tree, timing, input/output, metadata.
- Langfuse redesigned trace viewer: https://langfuse.com/changelog/2025-03-19-new-trace-view — documented tree/timeline, search, hierarchy, and display controls; historical 2025 design.
- Langfuse responsive timeline: https://langfuse.com/changelog/2026-08-28-responsive-timeline — documented overview/zoom approach for large traces; **not** an MVP implementation requirement.
- Langfuse agent graphs: https://langfuse.com/docs/observability/features/agent-graphs — documented overview/expanded patterns; graphs are **deferred** for OJT unless supported by recorded relationships.
- Langfuse live example project: https://langfuse.com/docs/demo — research entry; the earlier Codex research reported live Tree/Timeline, formatted/raw, operation search, and selection, but we have not repeated those interactive tests in this review.

**Our visuals:** `run-explorer-{dark|light}-{1440x900|1280x800}.jpg`, `trace-detail-...`, `evidence-focus-...` from the supplied screenshot archive. Compare original screenshots at native resolution; do not use compressed contact sheets for final typography decisions.

**Method:** Direct screenshot-to-image visual comparison + official documented interaction capabilities. The review can judge layout, density, hierarchy and visible states, **not** runtime correctness, keyboard behavior or backend API semantics. Do not treat Langfuse's sessions, pricing, scores, usage, annotations, graphs, or data model as requirements for our product.

## 2. Overall assessment

**Keep the architecture and visual direction.** Our mockups already resemble a serious developer tool: neutral surfaces, consistent shell, excellent separate Run/Span semantics, nested workflow, accessible-looking structural controls, and a useful dual-source evidence comparison.

**The polish gap relative to Langfuse:** operational differentiation, adaptive information presentation and fine visual hierarchy. Langfuse's inspector gives the selected observation a distinct identity and presents useful data immediately; its trace navigation distinguishes model/tool/retrieval operations and timing without requiring users to parse undifferentiated rows. Our design is well organized but comparatively flat, especially in monochrome metadata and the repeated fixtures.

**Design principle:** Match the **quality of information presentation**, not a pixel-perfect competitor skin. Preserve our unique debugging/investigation strengths and correctness guarantees.

## 3. Side-by-side findings and precise changes

| Surface | Our screenshot observation | Langfuse reference observation / claim | Targeted refinement | Priority |
|---|---|---|---|---|
| Application shell | 200px persistent sidebar; compact 48px top bar; very few destinations. | Official reference separates workspace/project context, tracing navigation, inspector workspace. | Keep our restrained shell; improve active context, icon alignment, truncation and collapse behavior. **Do not add filler menu items.** Hide unavailable Knowledge rather than showing `Knowledge Conditional`. | P1 |
| Run list | Good table geometry, search and filters; many rows repeat `refund-eligibility-review`, similar ID fragments, similar durations. | Langfuse tables prioritize discoverable trace IDs, time, sortable measures and richer trace identity. | Retain columns; use coherent, varied fixtures from existing controlled agent types; ensure unique IDs, times, outcomes, and corresponding detail links. Increase contrast between primary run name and secondary ID. | P1 |
| Run controls | Some weak/deactivated-looking filters (e.g. Duration), and one small line of compressed controls. | Langfuse exposes clear view/filter/search affordances. | Distinguish enabled, disabled, active-filter and hover styles. Avoid controls that look interactive but do nothing in visual demo. Tighten alignment; consider active-filter chips only when applied. | P2 |
| Trace hierarchy | Deep tree, useful recovered-retry linkage and duration column, but many similar grey symbols and small labels. | Official Langfuse trace UI differentiates observation types, hierarchy, selected observations; 2025 update describes hierarchy/search customization. | Adopt a consistent, small operation glyph set (run/agent/model/tool/retrieval/API/error/retry) and deliberate type labels. Preserve hierarchy lines, 32px row rhythm, clear selected row, failure vs recovery annotations. Not a rainbow icon system. | **P0** |
| Trace header | Run title, status, duration, trace ID and quality context exist, but secondary elements are squeezed. | Langfuse shows selected item identity and useful observation metadata near its detail area. | Introduce clearer hierarchy between run ID, outcome, completeness, selected span name/type, duration, and contextual metadata. Make trace ID easy to copy, not dominate. Additional model/tokens/cost fields ONLY where telemetry exists. | P1 |
| Trace timing | Tree/Timeline toggle visible; native timeline interactions cannot be verified from screenshot. | Langfuse documents tree/timeline parity; Aug 2026 describes overview → zoom for large traces. | Real timeline mock must use actual fixture-relative start/end positions and common scale. Keep selected span/filter state, add Fit/zoom as appropriate; NEVER infer causality from time overlap. Postpone high-scale 2D rendering. | **P0** |
| Span inspector | Input/output side-by-side works for short JSON; long messages would be too narrow. Content, Attributes, Events, Errors tabs are present. | Official Langfuse reference prioritizes human-readable input/output and alternate formatted/raw views. | Use **content-adaptive rendering**: stacked full-width input/output for long model prompts/responses; side-by-side option for short structured payloads. Provide readable and captured-JSON modes, clear availability markers, copy, line wrapping/scroll. Use operation-specific headers, generic fallback. | **P0** |
| Text density | Some muted labels, tree text, JSON and citation metadata are difficult at native 1280 screenshots. | Reference achieves dense but legible text and distinct foreground roles. | Verify computed size, weight, line-height and contrast in browser, not by guessing from JPEG. Target ~13–14px for primary data and 12px for supporting labels; monospace should remain readable. Don't blindly enlarge all rows. | **P0** |
| Visual accents | Dark and light modes consistent but selected items and inactive secondary controls blend into surrounding neutral surfaces. | Langfuse uses restrained type/selection accents plus recognizable observation glyphs. | Keep neutrals as dominant surfaces. Trial ONE controlled interactive/focus accent in both themes, separate from existing muted-red error accent. Pair every status color with text/glyph. Avoid purple-gradient AI-dashboard look. | P1 |
| Investigation entry | Trace screen contains a zero-grounded-findings status and an apparent Evidence Focus action. | Langfuse exposes context-specific actions for trace detail; no direct equivalent to our immutable evidence workflow. | Define action logic: zero grounded findings → no dead “view evidence” destination; earlier-attempt history when it exists must be explicitly labeled. Pending/failed must not block trace. | **P0** |
| Evidence focus | Side-by-side sources, cited values, stable finding + snapshot context are already strong. At 1280 the panes are narrow and some prose/JSON wraps awkwardly. | No claim of matching Langfuse feature; this is our differentiation. | Preserve source cards and verified-snapshot semantics. Enlarge relevant cited passages/highlights; compact provenance headers, explicit A/B assignment, source-select controls, focus in document, and independent scrolling. Permit single-source full-width view when narrow. | P1 |
| Product language | Some internal artifacts/labels appear in UI (`Knowledge Conditional`, `Review`, `Synthetic workspace`), appropriate only for preview mode. | Professional product interfaces avoid exposing implementation qualifiers to end users. | Remove internal terminology from product surfaces; retain a small visible **Sample data** badge in preview builds only. Do not remove truthful disclosure that data is synthetic. | P1 |

## 4. Screen-specific design instructions

### A. Run Explorer — refine, do not redesign

**Keep:** consistent application shell, Run/Started/Execution status/Duration/Completeness/Recorded errors/Investigation table, controls directly above table, no giant KPI banner.

**Improve:**
1. Make sample data look like plausible observed executions: e.g. refund agent, RAG agent, tool-task agent, research-planning agent, LangGraph workflow. Distinct names/IDs and valid timestamp ordering; statuses must agree with each linked trace fixture. Don't imply tested live production data.
2. Use a strong two-line run cell: recognizable operation/workload label above a small, copyable unique trace ID. Distinguish clicking the run from any investigation-only action.
3. Avoid repeated tiny monochrome badges when a short label plus glyph would read better. Show independent execution outcome, completeness and investigator state.
4. Active filters visibly differ from available filter controls; eliminate fake interactive affordances in the final functional prototype. Support long names, unknown counts and overflow gracefully.
5. Empty table space below a small result set is fine. Do not invent extra rows just to fill a 1440px capture.

### B. Trace Detail — primary refinement target

**Keep:** selected operation hierarchy left; content inspector right; independent scroll; explicit child-error + recovered attempt; non-blocking investigation status.

**Improve:**
1. Establish a 3-level scan: run header (run-wide status/quality) → operation list (types/status/duration) → selected span inspector (name/type/identity/content). Reduce visually competing labels and horizontal dividers.
2. Use one coherent micro-icon language for root/agent/model/tool/retrieval/API/retry/error; prioritize status and hierarchy over decorative icons.
3. For selected **model** span, show structured messages/roles in readable text; for **tool** span, show arguments and result/error; for **retrieval**, show matched document/context IDs and bounded excerpts; for unknown/custom, use a robust generic captured-data viewer. Show only recorded data.
4. Use inline tabs for Content / Attributes / Events / Errors; give clear empty vs unavailable vs redacted vs truncated states. Keep full stable span ID accessible and copyable.
5. Offer **stacked readable content as default for long text**, paired cards only for short payloads. Keep both light/dark text hierarchy, proper word wrapping and copy controls.
6. Timeline mode must plot relative positions and durations consistently, not generic equal-looking bars. A failure does not automatically imply the enclosing run failed; a retry-of link must be recorded, not inferred.
7. If a completed attempt has 0 grounded findings, display that state and limitations without suggesting there are findings to inspect. If earlier attempts exist, offer a clearly distinct attempt-history action.

### C. Evidence Focus — preserve our differentiator

**Keep:** finding list, explanation + limitations, stable snapshot/attempt context, citation chips, paired source panes, independent scroll, no causal-confidence score.

**Improve:**
1. Make source identity, source type, analyzed snapshot, citation ordinal, exact cited field/passage and highlighted value easy to scan. Use a stronger but restrained highlight that works in both themes.
2. At 1440px use dual-pane comparison. At 1280px, keep dual-pane only if both remain genuinely readable; allow a one-pane focus action. Below adequate width, stack rather than squeezing.
3. Clarify whether Source A/B is a view assignment versus evidence rank. Switching A/B must not change the finding's meaning.
4. Avoid truncating limitations or silently swapping in newer spans/documents when analyzed evidence is missing.
5. Keep this a source-comparison workspace—not a chat assistant, generic diagnosis card, or simulated causal graph.

## 5. Visual system refinements

- **Maintain coordinated light/dark themes** and current shared semantic tokens. No theme-specific layout drift.
- **Typography:** Verify real computed sizes in browser. Start with body/data 13–14px, quiet metadata at least 12px for normal desktop use, JSON monospace ~12–13px with ~1.5 line height. Adjust density surgically rather than scaling everything. Mobile/zoom tests remain required.
- **Information hierarchy:** One strong screen title, quieter context, distinct section headings; reduce repetitive all-caps micro-labels where they add noise. Use muted text for support, not crucial evidence.
- **Interaction emphasis:** Keep neutral backgrounds. Trial ONE restrained cool-blue/steel interactive accent for active tabs, links, focus/selection (evaluate 2 candidates in both themes); retain limited red for errors. These are *proposals*, not new approved exact token values. Success/recovered/partial must still have text and glyphs.
- **Dividers and surfaces:** Use borders for major sections, not every nested piece of metadata. Tune spacing in 4px increments, but don't change approved overall pane geometry unnecessarily.
- **Icons:** Use one consistently-sized icon system; do not rely on arbitrary ASCII or emoji for production operation types.
- **No generic AI-generated styling:** no gradients, glows, glass, giant metric cards, gratuitous charts, floating chat bubble, universal 16px+ rounding, random pill-badge decoration or marketing-copy headers.
- **No false metrics:** Tokens, cost, model name, completion state, confidence, completeness, and counts appear only if captured/provided by the platform. Preserve null/unavailable semantics.

## 6. Priority and implementation boundary

**P0 — Must resolve before accepting final mockups:** operation differentiation; legibility; content-adaptive inspector; real timeline visual semantics; zero-findings/action consistency. These are concrete UX flaws, not new backend features.

**P1 — Strong polish improvements:** run fixtures/identity; shell alignment; restrained interaction accent; evidence provenance/readability; removal of internal labels; header metadata hierarchy.

**P2 — Optional after MVP:** sophisticated responsive 2D timeline navigation, aggregate/expanded graph visualization, user-configurable density, saved views and extensive analytics. These require product and technical justification; do not adopt them merely because Langfuse offers them.

**Do not change:** Run=trace semantics, one-trace scope; separate outcome/completeness/investigation; recorded-only relationships; analysis-attempt/snapshot evidence identity; safe rendering of untrusted captured content; backend ownership of authentication; separate research ownership of investigator contracts.

## 7. Screenshot-based acceptance gate

1. Update the **latest local** `docs/frontend/design-spec.md` with the approved refinements, keeping unresolved decisions clearly labeled. Put this comparison review alongside it if useful; do not replace the specification.
2. Update only `docs/frontend/design-preview/` visual prototype files. **No production `frontend/` code yet.**
3. Re-render **Run Explorer, Trace Detail, Evidence Focus** in light and dark at **1440×900 and 1280×800** (12 baseline images) using a real browser. Use native-resolution inspection; check truncation, data density, line wrapping, relative timing, state labels and token contrast.
4. Add two **focused** extra states (not necessarily 12×2): long model prompt/output and a recovered retry with explicit `retry_of` association. Exercise incorrect reasoning, recovered retry and three-source evidence scenarios (S1–S3).
5. Ensure demonstrable interaction for tree selection vs expansion, Tree/Timeline switch with consistent selection, readable/captured-JSON switching, Evidence A/B reassignment, and theme switch—or explicitly mark each as preview-only/inert. Never claim functional verification from a screenshot.
6. Compare revised images with both our prior capture set and official Langfuse reference. Record before/after design differences and any deviations from the spec. Avoid pixel-copy targets and subjective unsupported claims such as "equivalent to Langfuse".
7. Check computed font size/line-height/contrast, 1280/1440 clipping, keyboard focus and resized panes if prototype supports them; leave genuine behavioral/accessibility testing for React implementation.
8. Stop after **one focused revision pass** unless a P0 issue remains. After approval, implement design using reusable React components; do not transpose static HTML wholesale.

## 8. Codex execution brief (copyable)

> Act as a senior UI/design-systems engineer and critical observability UX reviewer. In the original `ai-agent-debugger` repository, read `docs/frontend/design-spec.md` and `docs/frontend/langfuse-comparison-review.md`, then inspect the existing `docs/frontend/design-preview/` HTML/CSS/screenshots. Cross-check the precise Langfuse URLs cited in the review. Apply only the **P0/P1 targeted refinements**, preserving the already approved shell, light/dark themes, tracing semantics and Evidence Focus. Update the design specification to reflect deliberate choices; don't invent backend or investigator contracts. Regenerate and inspect 12 native-resolution screenshots (three screens, two themes, 1440×900 and 1280×800), plus focused long-output and recovered-retry states. Report a before/after comparison and any unresolved P0 issues. **Do not edit production frontend/backend/SDK, install unnecessary packages, commit, or push.**

---

**Review outcome:** Keep existing layouts; refine to Langfuse-level clarity in the trace navigator and span inspection while protecting our unique, evidence-first debugging workflow. "Langfuse-level" is a quality target, **not** a claim of matching every Langfuse feature or current deployment.
