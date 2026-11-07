# Frontend design specification

- **Product:** AI Agent Execution Debugging & Trace Analysis Platform
- **Date:** space-efficiency/workflow refinement 16 October 2026, following the Explore/overlay and P0/P1 passes; research provenance below is retained.
- **Status:** product/UX requirements below are settled for this scope; visual values are review baselines. Backend/investigation contracts in section 11 remain provisional.
- **Scope:** design specification and isolated browser-rendered previews; original `ai-agent-debugger` repository. No production implementation.

Product scope/semantics remain in [PRD](../PRD.md), [HLD](../HLD.md), [LLD](../LLD.md), [trace protocol](../trace-protocol.md), and [analysis engine](../analysis-engine.md). This single frontend reference does not define investigator orchestration, prompts, models, endpoints, or wire schemas. Dimensions are proposed CSS pixels, not competitor measurements.

## 1. Direction and product boundaries

- Coordinated light and dark themes; identical semantic roles, geometry, density, and interactions.
- Compact project navigation; Run Explorer is the project landing page. No separate KPI dashboard.
- Trace-first inspection with an integrated investigation summary and a dedicated workspace for multiple cited sources.
- Predominantly neutral surfaces, typography and borders, with explicit state labels. Section 5 trials one restrained interaction accent, separate from the limited error accent. No gradients, glass effects, oversized cards, decorative motion, or copied branding.
- A **Run** is the logical execution/trace; a **Span** is an operation. Do not adopt LangSmith's different use of “run” for a span.
- Execution outcome, telemetry completeness, and investigation state are independent. `UNSET` does not mean success; a child error does not automatically fail the Run.
- Parentage means nesting. Timestamps do not establish dependency; show `depends_on`, `handoff_from`, `consumes`, and `retry_of` only when recorded.
- Grounding verifies cited references, not semantic correctness or causal proof. Priority is High/Medium/Low investigation priority, never a probability.
- Investigation failure preserves trace access and earlier results. Late spans do not rewrite evidence in an earlier analysis attempt.
- Ended spans are the primary export profile; do not imply complete visibility into active operations or infer a running agent from absent telemetry.

**Implementation baseline, inspected 14 October:** frontend App/routes/pages/API helpers are empty scaffolds; `main.jsx` imports absent root App/CSS files. The current [SDK](../../sdk/python/README.md) describes console export, with HTTP export/batching still a target. This specification describes future behavior, not a working frontend or hosted onboarding flow.

**Requirement maturity:** navigation, coordinated themes, authentication UX ownership, evidence separation, and state preservation are requirements. Pixel values and semantic-error accents are visual baselines for review. B/E/P identifiers in section 11 describe dependencies or open contracts, not approved endpoints, schemas, or investigator behavior. The static [design preview](design-preview/index.html) uses authored data; its [review notes](design-preview/review-notes.md) distinguish rendered, locally exercised, and unimplemented behavior.

**Refinement scope:** apply P0/P1 from the supplied [Langfuse comparison review](LANGFUSE_OJT_FRONTEND_UI_REFINEMENT_REVIEW.md). That is the actual local filename; the requested `langfuse-comparison-review.md` does not exist. Preserve the supplied review unchanged. P2 graphs, advanced 2D timeline rendering, saved views and analytics remain deferred. A visible **Sample data** badge discloses the static preview; review controls appear only with `review=1`, outside product navigation.

**Approved layout revision:** Trace Detail now defaults to full-width Explore with an optional non-modal overlay inspector and an explicit pinned split mode. This supersedes the permanent 336 px navigator/inspector default from the P0/P1 captures. Run Explorer, Evidence Focus, themes, operation glyphs and evidence semantics retain their responsibilities. Large-trace fixtures are local design simulations, not performance guarantees or evidence of backend paging/search support.

**Approved density revision, 16 October:** consolidate run/context identity and investigation entry; keep one pane-responsive execution toolbar, optional IDs, compact inspector identity and a rail-free single-finding evidence workspace. Preserve existing readable fonts, operation-row heights, independent states and captured evidence. The independent UX audit supplied in this conversation informed this pass; its measurements are rechecked locally in the [review log](design-preview/review-notes.md). Its competitor observations are attributed audit evidence, not a new live-competitor verification by this pass.

## 2. Research provenance

Previous 14 October research: **O** = live observation; **V** = official image; **D** = documentation claim. Later sections are **our proposed design**, not verified competitor behavior or automatically inherited requirements.

| Reference and exact source | Evidence retained | Design implication, not a claim about our implementation |
|---|---|---|
| [LangSmith article](https://blog.langchain.com/debugging-deep-agents-with-langsmith/) ([redirect](https://www.langchain.com/blog/debugging-deep-agents-with-langsmith)); [view docs](https://docs.langchain.com/langsmith/view-traces); [quickstart image](https://docs.langchain.com/langsmith/observability-quickstart) | D: context-preserving inspection, instrumentation-dependent views. V: tree/inspector (`LS-02`). O: workspace empty; no populated live trace tested. | Preserve context without requiring threads. |
| [Langfuse March 2025 redesign](https://langfuse.com/changelog/2025-03-19-new-trace-view) | D: tree/timeline, search, display settings; historical announcement. | Paired structure/timing views. |
| [Langfuse demo](https://langfuse.com/docs/demo); [shared trace](https://cloud.langfuse.com/project/clkpwwm0m000gmm094odg11gi/traces/8f9d29585229f964c312543def6f88fc) | O: view switch, child/URL selection, formatted/raw, search (`LF-02`–`LF-05`). Search removed ancestors. | Retain selection/ancestors; give inspection room. |
| [Phoenix tracing](https://arize.com/docs/phoenix/tracing) ([redirect](https://arize.com/docs/phoenix/tracing/tutorial)); [demo](https://phoenix-demo.arize.com/projects/UHJvamVjdDoy/spans?timeRangeKey=30d) | D: operation tracing. O: hierarchy, Attributes/JSON, zero Events (`PX-02`–`PX-04`); widening time range resolved empty results (`PX-01`). | Structured inspection and actionable empty states. |
| [Sentry Agents Dashboards](https://docs.sentry.io/product/dashboards/sentry-dashboards/ai/agents/) | D: AI Spans → full trace. V: waterfall/inspector (`SE-01`, `SE-02`). Email/terms gate; no live trace test. | Keep API/retrieval context accessible. |
| [Linear March 2024 redesign](https://linear.app/now/how-we-redesigned-the-linear-ui) | D/V: consistent headers, inverted-L chrome (`LI-02`); no live account. | Stable alignment; explanatory tints are not tokens. |
| [Vercel February 2026 redesign](https://vercel.com/changelog/dashboard-navigation-redesign-rollout) | D: hideable/resizable sidebar, scope navigation. V: image (`VE-01`); no live dashboard. | Persistent project scope, no MVP team aggregation. |

The original [evidence register](research/evidence-register.md) retains the source URLs and remaining repository-relative captures; LF/PX images were removed during cleanup. Selected references: Langfuse inspector (capture removed during cleanup), [LangSmith trace](research/LS-02-official-trace.jpg), Phoenix attributes (capture removed during cleanup), [Sentry waterfall](research/SE-02-full-waterfall-official.jpg), [Linear hierarchy](research/LI-02-inverted-l-official.jpg), [Vercel navigation](research/VE-01-official-navigation.jpg). These are research evidence, not mockups or implementation targets. Exact primary source URLs remain above; captures are dated 14 October. Competitor large-trace, accessibility, partial-trace, retry, and investigator behavior was not tested. Section 9 uses authored fixtures.

**Independent Langfuse recheck, 15 October:** the [official trace image](https://langfuse.com/images/docs/tracing-overview.png) was visually inspected (capture (capture removed during cleanup)); it shows a distinct operation header and stacked input/output. Its exact release marker was not verified; it is not proof of the current deployment. The [overview](https://langfuse.com/docs/observability/overview) describes nested observations and content/metadata inspection. The [2025 announcement](https://langfuse.com/changelog/2025-03-19-new-trace-view) documents tree/timeline parity and search. The [August 2026 timeline announcement](https://langfuse.com/changelog/2026-08-28-responsive-timeline) documents Fit/zoom behavior; large-trace performance was not tested. [Agent graph documentation](https://langfuse.com/docs/observability/features/agent-graphs) permits timing/nesting-based inference, which conflicts with our recorded-only relationship rule; it is not adopted.

The [demo entry](https://langfuse.com/docs/demo) and shared trace above were reopened. **O:** the live workspace identified v4.59.0; selecting `chat`, switching Formatted/Raw and then Timeline retained that selected observation (model (capture removed during cleanup), timeline (capture removed during cleanup)). One Raw tab measured 12/12 px system sans-serif; this is one control, not a complete type audit. The current hierarchy/inspector were visually compared with our previous captures. These observations support presentation refinements, not pixel-copy targets, backend features, or a claim of competitor equivalence.

## 3. Screen inventory and navigation

Hierarchy: **Sign in / Register → Projects → selected Project → Runs → Trace Detail → Evidence Focus**. Existing sessions resume an authorized intended workspace. Setup and Settings are project siblings; Knowledge is conditional. Inspector and investigation summary are Trace Detail surfaces, not extra global destinations.

| Screen/surface | Scope | Contents and navigation |
|---|---|---|
| Sign in / Register | MVP target | Email/password forms; submit/busy/backend validation states, password visibility control, switch between forms. No client-side password verification or account/session creation. |
| Session expired / Sign out | MVP target | Expiration explanation and sign-in return; sign-out reflects backend invalidation. Preserve a safe internal return destination, not passwords or protected response caches. |
| Project chooser + creation dialog | MVP | Project name/identity, access-aware selection, creation validation. Selecting a project opens Runs; no cross-project evidence mixing. |
| Run Explorer | MVP, landing | Execution table, search, filters, pagination; explicit links to Trace Detail. |
| Trace Detail | MVP | Run identity/summary, completeness warnings, tree/timeline, selected span inspector, investigation summary. |
| Evidence Focus | MVP | Selected attempt/finding, explanation and limitations, citation list, one or two visible source panes. Reachable from Trace Detail and a scoped deep link. |
| SDK Setup | MVP target | Supported Python instrumentation/capture guidance, integration configuration, first persisted-run confirmation. Do not publish the LLD's future constructor as current SDK syntax. |
| Project Settings | MVP target | Project identity and integration settings, subject to access policy. Provider/database credentials never appear here. |
| Knowledge list/upload + document/passage detail | Conditional | Project-owned sources, processing/availability state, bounded cited passages. Upload formats/lifecycle await approval; passage detail reuses Evidence Focus. |
| Access denied, unavailable/not found | MVP shared states | Safe explanation, project context, retry/back navigation; never leak another project's existence or data. |
| Attempt history selector | Subsequent improvement | Rich history/comparison. MVP must still preserve earlier results and reopen an attempt referenced by a finding. No separate history dashboard. |

Global navigation contains Project selector, Runs, Setup, conditional Knowledge, and Settings; theme/account controls are compact utilities. No prompts/playground, datasets/experiments, billing, dashboard builder, remediation, or replay.

Omit Knowledge when unavailable; never show an internal “Conditional” qualifier as a destination. Availability follows approved project configuration/access behavior (B8/B9), not a frontend authorization rule. Sample-data disclosure and design-review controls belong to preview chrome, not account/project labels.

### 3.1 Email/password and session UX

Sign-in and registration use a restrained 360–400 px form with visible labels, appropriate autocomplete, show/hide controls, a primary action, and a link to the alternate form. The user-approved registration flow (17 October) has two steps: **Name + Email → Continue → Username + Password + Confirm password + Terms and Conditions checkbox → Create account**. Continue validates the first step without submitting registration. The second step requires a username, matching password fields and the checkbox. These are form checks, not credential verification or username-availability checks. Back preserves identity fields and clears both passwords, visibility state and checkbox state. Login remains Email/Password. Password policy, email verification, recovery and automatic sign-in remain backend-dependent.

The user has not supplied terms content and explicitly requested a checkbox only. Do not fabricate a terms document/link or claim durable legal acceptance. The preview footer states that terms are unpublished and authentication is disconnected. A production integration must resolve terms/version/acceptance handling and registration fields with FastAPI before real signup is enabled. No endpoint or wire schema follows from the in-process form adapter.

**17 October account/settings refinement:** the historical reference review (removed during repository cleanup) supported a shared 384 px unframed account column, centered in the available page area, with a quiet product header. Account headings use 28/36 px on desktop and 26/34 px on mobile; controls are 42 px on desktop and at least 44 px for mobile form actions. Password visibility sits inside the field and retains an explicit accessible label/focus treatment. Expiration and denial reuse this composition with one dominant recovery action. Development-only limitations remain visible in secondary footer text rather than the task description. This does not enable account/session behavior.

**Signup usability follow-up:** registration uses a stable top-aligned column so changing steps does not recenter the heading. A compact ordered step indicator distinguishes current/completed steps by labels and shape as well as contrast; `aria-current="step"`, a status announcement and the document title expose progress. The credentials step shows the chosen email with wrapping for long addresses; Back provides correction. Email inputs suppress capitalization/spellcheck. Keep existing labels, autocomplete, explicit visibility controls and first-invalid-field focus. The desktop baseline fits the ordinary second step and development footer at 1280 × 800; validation and long text may extend vertically rather than clip.

Project creation/settings remain inside the existing project shell: content width up to 800 px, a form section up to 640 px, 24 px desktop field padding and a distinct action footer. Read-only Project ID is separate from the editable name. Empty-project entries share one presentation and one Create project action. Do not add a second settings navigation, unsupported categories, ownership labels, credentials or destructive actions to fill space. The development notice explicitly describes local, reset-on-reload project changes and their lack of ownership/access meaning.

On submit retain the email, show action-specific busy/error text, and prevent duplicate submission. Render safe backend-supplied field/general errors without echoing the password. Do not log/persist passwords, synthesize sessions/tokens, or store authentication state as a local boolean. React ultimately owns forms, session-aware navigation, and integration with approved APIs only. Session creation/validation/expiry, password verification, and authorization belong exclusively to FastAPI; endpoint shapes, session transport, recovery, and registration completion remain open in B10/P5.

When the backend reports an expired session, obscure protected content, clear sensitive rendered caches, announce expiration, and offer sign-in. Resume only a validated internal destination after the backend reauthorizes access. UI concealment is a privacy presentation measure, never access control. Sign-out must be confirmed by backend invalidation; a network failure is not successful sign-out. Visual previews cannot submit credentials and do not simulate authentication success.

### 3.2 Predictable project sidebar

Expanded width is 200 px; compact width is 56 px, consistently in Runs, Trace Detail, and Evidence Focus. A permanently located toggle names the next action and reports expanded state. The developer's explicit choice persists across workspace navigation/reloads as a non-sensitive presentation preference; no route forces collapse. Keep the project selector and destinations legible without an additional Project section label. First desktop preview uses expanded navigation, not an approved product preference default; compact mode must never be forced to meet density targets.

At narrow widths navigation temporarily becomes a sheet/compact header without overwriting the saved desktop choice. Returning to desktop restores it. Tooltips/accessible names identify collapsed destinations; selection remains visible. Expanding may trigger the documented stacked-pane layout rather than shrink evidence below its minima. Preview persistence is local UI state and has no authentication meaning.

## 4. Desktop layouts

Reference canvases: **1440 × 900** and **1280 × 800**, 100% zoom. Headers below have minimum heights and grow when content wraps; avoid clipping at zoom. Resizing must respect section 8 rather than preserve columns at any cost.

### 4.1 Run Explorer

At 1440 px: 200 px project sidebar, remaining workspace with 24 px horizontal inset. Sidebar collapses to 56 px. Vertical order:

| Region | Layout contract |
|---|---|
| Application header | 48 px minimum; project context left, theme/settings utilities right. |
| View header | 56 px minimum; “Runs”, understated result count when known, Refresh and Setup actions. No KPI tiles. |
| Query toolbar | 44 px minimum; name/trace-ID search (minimum 280 px), time range, execution status, completeness, duration range. Wrap when necessary. |
| Active filters | Removable labeled chips and Clear filters; appears only when needed. Clearing preserves an explicitly chosen time range; Reset query clears everything. |
| Execution table | Sticky 36 px header (supporting labels may wrap); 48 px two-line rows, 8 px horizontal/4 px vertical cell inset. Run name 14/20 px semibold, secondary identity 12/16 px; full trace ID through an explicit copy/detail affordance distinct from opening the Run. |
| Pagination/footer | 40 px minimum; result/page information only when supplied, previous/next controls, refresh status. No invented totals. |

Columns: **Run** (flexible, minimum 260 px), **Started** (156), **Execution status** (128), **Duration** (88), **Completeness** (128), **Recorded errors** (96), **Investigation** (136). Widths include padding: minimum 992 px. Right-align metrics with tabular numerals. Run hover/focus detail exposes service/agent identity; no compulsory extra column or third row line.

Search commits on Enter/Search, matching name/trace ID, not payloads. Filters use AND, values within a facet OR; invalid durations get inline errors. Query/sort changes reset pagination. Started defaults descending with stable server ordering. Clear search/refresh/browser return preserve the remaining query. Time window awaits P1.

Run names are real links; row activation may mirror them. No purposeless bulk selection. Status, completeness, and analysis labels remain independent.

Prefer short status text plus a glyph over a pill around every neutral value. Only positive finding counts link to Evidence Focus; completed zero findings and unrequested/failed analysis are state labels. Sample fixtures must have distinct workload names/IDs, ordered times, and corresponding consistent detail views. They may represent the existing refund, NovaCloud RAG, fulfillment and Meridian research domains without claiming those examples emitted telemetry or ran successfully. Empty space is preferable to filler rows.

### 4.2 Trace Detail

Use the chosen 200/56 px sidebar and 16 px inset. Consolidate breadcrumb and Run identity into one approximately 60 px header: compact Runs/Run-ID context, 20/28 px workload name, copyable trace ID, investigation control and preview disclosure. A separate approximately 36 px metadata row shows reported outcome, duration, Capture completeness, recorded date/timezone and supplied service. Do not repeat project/environment already shown in navigation or the Run name outside its legitimate recorded root operation. A conditional quality notice remains explicit (about 28 px plus spacing for the sampled one-line warning); long reasons wrap. Model name, tokens and cost require captured telemetry and are not placeholders.

| Mode | Layout / state contract |
|---|---|
| Explore, default | Execution tree/timeline uses the full workbench width. No reserved inspector column, automatic error selection or initial inspector. Sticky controls, scope/ancestor context and column/axis headers stay above the independently scrolling rows. |
| Overlay inspector | Selecting a span opens a non-modal panel at the workbench's right edge, above the explorer. Proposed width: about half the workbench, clamped to 480–640 px (600 px at 1440, about 524 px at 1280 with expanded sidebar). No scrim, body-scroll lock, explorer resize, horizontal shift, scroll reset or automatic zoom. Covered columns are intentionally occluded; pin when simultaneous comparison is needed. |
| Pinned split | Pin creates side-by-side explorer and inspector. Inspector range 480–640 px, explorer minimum 440 px, 8 px visual separator with an expanded pointer target. Unpin restores the overlay over the original full-width explorer. Preserve selected ID, expansion, filters, row anchor/scroll, time window, inspected content mode/tab and per-span payload scroll. |
| Narrow fallback | If both panes cannot meet 440 + 8 + 480 px, use a single inspector pane with Back to execution. Retain the explorer in state; restore its row anchor/zoom on return. A temporary width fallback never overwrites the requested desktop pin state. See section 8. |

- Execution controls use one approximately 44 px toolbar: Tree/Timeline, one name/span-ID search, Filters and Execution options. Adapt to pane width without wrapping this toolbar into extra bands at either desktop reference width, including a 440 px pinned explorer. Filters disclose operation and raw-status facets and show an active count. Options contain loaded expand/collapse, optional Span ID column, exceptional exact-ID jump and contextual Fit selected. Do not permanently show a second lookup form. Native disclosure/form behavior is acceptable; never apply ARIA menu roles without the corresponding keyboard model.
- One approximately 32 px context band combines loaded/known counts, declared loaded-only query scope, ancestor access and conditional controls. The full ancestor path is expandable/clickable; its compact text favors the active operation's tail. Focus inspector appears when inspection is open. Reveal appears when selection is excluded, collapsed or offscreen. Loaded previous/next-match controls appear only for an active query/filter; direct matches remain distinct from ancestors. Temporary filter relaxation and restored filters stay explicit. The footer is one approximately 28 px row for visible/expanded rows and local load-more status/action, never a second selected-operation headline.
- Rows remain 32 px with 16 px indentation, existing 16 px SVG operation glyphs and separate raw-error/retry labels. Names are 13/16 px; metadata 12 px. Child counts describe direct children, not errors or descendants. Show loaded/known children separately where supplied. Full-width Tree shows raw status, recorded start and duration; the optional Span ID column defaults hidden in this review baseline and has an explicit persisted presentation choice. IDs stay searchable and available for copying in Details. Compact pinned rows retain operation/type/status, start in the secondary line and duration. Indentation never shifts timing plots. Deep names may ellipsize; accessible labels, the path and inspector Details preserve identity.
- Inspector: one approximately 60 px operation/action header with type glyph, 16 px name, type/duration, raw status, Details, Back to execution, Pin/Unpin, options and Close. Remove the generic Span inspector / Overlay title band. Put full ID/copy, recorded start and secondary metadata in Details; put the width slider in Inspector options while retaining the keyboard/pointer splitter. Keep **Content, Attributes, Events, Errors** and independent scroll. Close/Escape/outside dismissal and direct row switching retain the section 6 contract; pinned outside/Escape do not dismiss.
- Content defaults to Readable, with a real Captured JSON switch. Recognized model messages retain supplied roles/text; tools show arguments and result/error; retrieval shows captured document IDs/excerpts; unknown/custom operations use the generic captured-data viewer. No prompt, role or missing context is reconstructed.
- Content layout adapts: short structured payloads may use paired cards, with a stacked option. Long model prompts/responses use full-width stacked sections in both modes. Readable prose is 14/22 px; captured JSON stays 13/20 px, preserving null/false/zero and availability markers. Input/Output jump controls scroll only the inspector. Copy uses the captured value, not displayed line numbers; long JSON offers local wrapping/scroll. The preview's model-string >200 characters or combined serialization >600 characters heuristic is a presentation study, not a payload/API limit.
- At inspector widths below 600 px, stack short payloads and omit ineffective pairing controls. Do not add a permanent explanatory stacking label. Restore the wider-layout choice when space permits; never change captured values or shrink JSON text to retain columns. Content does not repeat the complete Attributes table or full exception event; those remain in their respective tabs, with local attribute search. Keep one concise Content error summary and the explicit retry action.
- Investigation is a discoverable header control with current state/result count and anchored attempt/snapshot/limitations details. A positive finding count links directly to evidence, with a separate adjacent details disclosure; unrequested/zero/failed states open their details. There is no permanent investigation banner. Evidence links require supplied grounded findings. Request/retry entry explains unavailability in the disconnected prototype and cannot mutate analysis state, invent an attempt or simulate a request. Product request/retry remains B5/E4-dependent; history actions require actual earlier results.

Timeline adds one approximately 40 px band combining zoom in/out, Fit run, numerical window and overview navigation. Fit selected belongs to contextual options. Controls do not wrap into more desktop bands. The axis and original timing text remain readable; minimum drawing marks never change recorded duration. Reclaim space from repeated structure rather than fonts, warnings, capture markers or timing truth.

The optional ID-column control explains its wide-view constraint: below roughly 840 px of explorer width, retain the preference but omit the column and make the control unavailable, rather than silently accepting an ineffective toggle. ID lookup/copy remain available. The inspector's optional width slider uses one-pixel steps so its value matches constrained widths such as 523 px; the splitter's keyboard increment remains 16 px.

Retain unobscured headers. Pinned resizing supports pointer drag, keyboard Left/Right in 16 px steps, min/max/reset and a single-pointer width alternative. Left moves the separator left, enlarging the inspector; Right shrinks it. Resize changes layout only, never selection/time-window values. Overlay selection updates only its content and the selected row; the explorer scroll container remains mounted. Never sum nested duration or derive dependency arrows from timing.

### 4.3 Evidence Focus

Keep the chosen sidebar width, compact Run context, and explicit **Back to trace**. Attempt identity/state and the labeled analyzed snapshot remain visible globally; full attempt identifiers and the limited meaning of reference verification can expand in Details. With one finding, omit the findings rail and splitter. Show the finding title/category/supplied priority once. For multiple findings, provide a labeled selector with current position/title; a larger optional list remains a subsequent enhancement. Never fabricate more findings to fill a rail. The preview's multiple-findings variant is separately authored test data, not investigator output.

Workspace: finding title/priority/category → explanation → grounding/limitations → citations → sources. “References verified” requires backend confirmation; its limited meaning is explained in text.

- One citation: one full-width source pane. Two or more: two panes separated by 8 px when usable workspace width after insets is at least 728 px; each pane is at least 360 px.
- Keep all numbered citations; explicit A/B assignment starts with the first two in supplied order, not causal ranking. Reassignment never changes the finding.
- Each pane shows source kind/identity, field/passage, snapshot association, copy, and “Cited value”. Highlight the cited range with surrounding captured context when available.
- Wrapped readable content by default, alternate captured JSON, independent scroll. No frontend-generated semantic diff or causal claim.
- A/B are view assignments, not evidence rank. **Focus source A/B** temporarily expands one source to the full evidence workspace; **Compare sources** restores the pair without changing the finding, citation numbering or snapshot. Keep every citation reachable in focus mode.
- Preserve independent paired/focused reading positions per assigned source. A focused layout may fit all content and clamp its scroll to zero; that must not overwrite the narrower paired layout's saved position. Surrounding-context expansion survives source reassignment and navigation. Paragraph-anchor translation across arbitrary viewport reflow remains an implementation/accessibility review item.
- Compact provenance keeps source name, kind, exact field/passage and fixed document revision visible. Full IDs/copy and repeated snapshot association expand in source Details; source-specific mismatch/unavailability is always local and visible. Supporting text stays at least 12 px, cited values 16/24 px, JSON 13/20 px and prose 14/22 px. Do not collapse or truncate the finding limitation. Left/A and Right/B are visible comparison locations. Source selectors identify their destination; citation-chip activation explicitly names its existing Left/A assignment behavior. A redesigned Replace left/right interaction remains a separate review decision, not a silent semantic change.
- **Inspect in analyzed trace** requires confirmed snapshot resolution. The current prototype cannot resolve a historical backend snapshot: it says Historical inspection unavailable and offers separately labeled **Open current span**. That navigation does not replace the analyzed evidence or establish historical resolution. Never substitute newer evidence for an analyzed value.

Long explanations can expand; limitations and source identity must not disappear behind truncation. Citation load failure affects its pane, not the other sources or finding list.

### 4.4 Large-trace exploration

The design must distinguish **known trace structure**, **loaded structure**, **expanded rows**, **rows in the viewport**, **payload availability** and **telemetry completeness**. None implies another. A reported complete Run may have only some structural pages loaded; a fully loaded partial trace remains partial. Counts are shown only when supplied; do not derive total trace size from a page length.

| Concern | Required behavior / preview boundary |
|---|---|
| Windowed rows | Flatten the expanded, filtered loaded hierarchy in stable order. Render the viewport plus bounded overscan, with stable span IDs and a retained keyboard-active item. Collapsing a parent preserves descendant expansion and selected/inspected ID; expose Reveal if hidden. Virtualization is an implementation strategy, not a completeness state. |
| Deep hierarchy | Keep direct-child counts and missing-parent markers explicit. Search retains ancestors as context, even when they do not match. Offscreen ancestors remain available through a labeled path. Jump to span expands only its ancestor path and scrolls to its stable row; it does not invent parent spans. |
| Query scope | Default to explicitly labeled loaded-structure name/ID/type/raw-status search. Separate direct matches from retained ancestors. Unloaded spans are not searched. An entire-trace option requires an approved capability; until then, no trace-wide result or no-match claim. Payload text is outside structural search. |
| Progressive structure | Load more explicitly with known remaining/unknown-total states. Preserve the first visible stable row and offset when structure arrives; never reset scroll or assert capture is complete. The 2,100-span sample initially exposes 840 records and can reveal local batches; it is not a paging API demonstration. |
| Lazy inspection | Structural rows need no payload render. Product selection should initiate the approved bounded selected-span read, with loading/failure/retry and captured/redacted/truncated states; an older response cannot populate a newer selection. The prototype directly renders only the selected locally authored payload, removing its extra manual Load captured payload action. All data already exists locally: this demonstrates deferred rendering, not a network request, read contract, stale-response protection or latency. |
| Shared timeline | One labeled axis and time window for all rows. Plot start `(spanStart − windowStart) / windowDuration` and duration `spanDuration / windowDuration`, clipping only the drawing at window edges; text retains original timing. Out-of-window spans stay listed with an explicit marker. Fit run, zoom in/out, pan/overview and Fit selected preserve selection, expansion, filters and vertical anchor. No causality inferred. |
| Overview | Show the current window relative to the known Run duration and the selected recorded interval. This is a time-range navigator, not a fabricated activity chart. Unknown/invalid bounds disable unsupported timing controls with an explanation. Fit selected is explicit; selecting an off-window span never silently zooms. |
| Partial / limited | Show recorded capture-quality warnings separately from client loading limits. A missing parent is not a synthetic span. Do not suggest unloaded children are absent, or that fetching more repairs missing telemetry. Unknown total/children remain unknown. |

Review fixtures contain exactly 100, 1,000 and 2,100 authored structural spans, including deep nesting, an explicit recovered retry and model/tool/API/retrieval/state operations. Review scope, rendered row counts and any timings must be measured and described as local observations. No frame-rate, latency, memory ceiling or 1,000+ span production guarantee follows from a screenshot.

## 5. Semantic design system

Components consume shared semantic roles; light/dark share geometry and density. Base values remain neutral. Error and interaction accents are visual review proposals, not diagnostic classifications or final approved token values.

| Semantic token | Light | Dark |
|---|---|---|
| `surface.canvas` | `#F8F8F8` | `#111111` |
| `surface.panel` | `#FFFFFF` | `#181818` |
| `surface.subtle` | `#F0F0F0` | `#222222` |
| `surface.hover` | `#E8E8E8` | `#2A2A2A` |
| `surface.selected` | `#DEDEDE` | `#333333` |
| `surface.evidence` | `#DADADA` | `#383838` |
| `surface.disabled` | `#F1F1F1` | `#242424` |
| `text.primary` | `#171717` | `#EEEEEE` |
| `text.secondary` | `#525252` | `#B8B8B8` |
| `text.muted` | `#5F5F5F` | `#A3A3A3` |
| `text.disabled` | `#8A8A8A` | `#777777` |
| `border.subtle` | `#D6D6D6` | `#333333` |
| `border.control` | `#858585` | `#737373` |
| `border.strong` | `#616161` | `#999999` |
| `interactive.text` / `interactive.indicator` / `focus.ring` (Steel trial) | `#4E6375` | `#B0C0CD` |
| `action.solid` | `#1A1A1A` | `#E8E8E8` |
| `action.on-solid` | `#FFFFFF` | `#111111` |
| `error.text` | `#B42318` | `#FCA5A5` |
| `error.surface` | `#FEF3F2` | `#2C1919` |
| `error.border` | `#FDA29B` | `#7F3F3F` |

Use `error.text` sparingly for recorded explicit errors or form/read failures, with text and an error glyph; limit the tinted surface to the badge/local error notice. Do not tint entire Runs red because a child failed, or color an investigator's High priority as an execution error. Partial/recovered/priority badges remain neutral with distinct labels/glyphs. Error borders are supplemental; use a strong neutral boundary where contrast is required. No green “correct” badge for grounding. `border.subtle` is decorative; meaningful boundaries use `border.control` on panels or `border.strong` on selected surfaces. The monochrome alternative remains reviewable by removing the error accent, without changing semantics.

Trial exactly one interaction family at a time: **Steel** above, or **Cool blue** (`#315B85` light / `#9CBBD8` dark). Use it for active tabs, actionable evidence links, focus rings and the selected-row indicator; keep selected surfaces neutral and operation types differentiated by shape/text. Cited content retains a neutral highlight. Both candidates must be inspected in both themes; Steel is the proposed restrained baseline, not a new approved brand color. Do not color Recovered as an error merely because its adjacent failed attempt remains red.

Token contrast calculation: primary/secondary/muted text across the six enabled surfaces has minimum ratios **4.56:1 light / 4.64:1 dark** (rounded down); control border against panel is **3.69:1 / 3.74:1**. These numerical checks are not a rendered accessibility audit. Disabled text is excluded; placeholders/help use readable muted text, never disabled styling.

| Geometry/type role | Specification |
|---|---|
| Typeface | System sans-serif, with Segoe UI on Windows; system monospace for IDs, paths, captured JSON. No required font download. |
| Page / section / interface | 20/28 px semibold; 16/24 px semibold; 14/20 px regular. |
| Explanation / data / metadata | 14/22 px; 13/20 px monospace; 12/18 px. Use tabular numerals for metrics. |
| Compact labels | Product metadata, IDs, provenance, durations and badges have a 12 px floor; primary data uses 13–14 px. Only nonessential group labels and separate design-review chrome may be smaller. Preserve the 32 px operation/48 px table rhythms rather than scaling every surface. |
| Spacing | 4, 8, 12, 16, 24, 32 px; pane padding 16, compact cell inset 8. |
| Borders / radii | 1 px structural border; 2 px selected/focus indicator. Radius 4 px rows/badges, 6 px controls, 8 px dialogs. |
| Controls | Standard desktop controls 32 px; compact toolbar actions 28–32 px and secondary icon/disclosure targets at least 24 × 24 px. Touch controls 44 px. Glyphs stay 16 px and text retains its existing readable size; this scoped compact-control baseline replaces the earlier blanket 32 px minimum. |
| Elevation/motion | Pane separation by borders. Menus/dialogs may use a restrained neutral shadow; background scrim uses a fixed neutral color. No entrance animation, shimmer, or smooth-scrolling dependency. |

| Component state | Required treatment |
|---|---|
| Default / hover / pressed | Panel/subtle surface → hover surface → selected surface; keep text readable. Primary action uses solid/on-solid roles. |
| Selected | Selected fill plus persistent 2 px strong indicator; not interchangeable with hover. |
| Focus-visible | 2 px ring, 2 px offset, on top of selection. Never remove focus to simplify the visual. |
| Disabled | Disabled roles and unavailable semantics; explain why when material. No misleading active affordance. |
| Busy | Retain label and geometry, identify the pending action, expose busy status. Prevent duplicate submissions without disabling unrelated inspection. |
| Invalid / failed | Error icon, strong boundary, inline readable explanation and recovery action. Do not rely on color or a transient toast. |

Theme controls expose Light/Dark/System, preserve current navigation and selection, and do not change data. Default preference awaits P1.

## 6. Interaction contracts

**Shared navigation:** state is scoped by project and Run. Deep links restore Run/span, view, selected attempt/finding, snapshot context, and citation pair where applicable; never place credentials or payload text in URLs. Workspace transitions add browser-history entries; in-workspace selections replace location state so Back returns to the prior workspace. Back to trace restores its filters, selected span, expansion, and scroll. Project changes discard incompatible selection. Resolve stale links with an explicit unavailable state, never a different span/finding.

Trace → Evidence entry must read the current selected span at activation, not a link generated before selection changed. Restore the selected stable ID, view, expansion, query/filter scope, row anchor, time window, overlay/pin state and inspector tab/presentation. Returning from a current-span source link intentionally selects that named current span and can explicitly reveal it; ordinary Back restores the previous investigation context. Evidence retains finding, citation pair, focused source and per-source reading position. Prototype memory stores authored UI identifiers/positions in tab-scoped browser storage, never payloads, passwords or session authorization; production lifecycle/project/snapshot scoping and cache clearing still require integration review.

Workspace-navigation links save the pre-navigation inspection state rather than treating departure as an outside-click dismissal. Outside activation within the current workspace retains normal overlay dismissal. This allows the direct finding link and Back to trace to restore an open overlay, while keeping dismissal predictable during local exploration.

| Surface | Contract |
|---|---|
| Trace tree | Select row/name to inspect; disclosure control only expands/collapses. Search matches name/ID; operation and raw-status filters combine. Keep matching ancestors as labeled context, show matched/loaded counts only when known. Missing-parent groups are UI organization, not fabricated spans. |
| Tree selection | Expand ancestors on explicit jump/reveal, retaining prior descendant expansion. If filters hide a selected/cited span, offer Reveal and clearly indicate temporarily relaxed filters; Restore reinstates the earlier query. Focus and selection are distinct. Closing the inspector retains selection. |
| Timeline | Same structural set, query, selection and hierarchy as Tree. All rows/axis use section 4.4's shared window. Zoom/Fit/pan never reset vertical navigation or infer causality. Zero duration uses a point; a minimum 1 px positive marker is visual, not a changed duration. Invalid/unavailable timing is labeled. Local preview zoom is not a high-scale rendering or backend capability claim. |
| Inspector | Selection updates identity/content without collapsing the tree. Preserve raw `OK`, `ERROR`, `UNSET`, missing and unrecognized statuses. Only explicit `OK` is labeled OK; unknown is not success. Show unrecognized raw text in Details and accessible labels. Show local loading during a real bounded fetch; older responses cannot cross selections. Attributes supports local key/value search and table/captured-JSON views. Events/Errors distinguish empty from unavailable and do not double-count a status/exception pair. |
| Overlay / pin | Pointer/keyboard row activation opens or directly switches the same non-modal inspector. Close/Escape/outside click dismiss overlay; preserve explorer and inspected ID. A disclosure click performs expansion without selecting. Pin deliberately reflows into split mode; Unpin restores full-width exploration under the overlay. Both preserve the inspector's content state. |
| Payloads | Preserve null, empty string, false, zero, and empty collections. Mark capture disabled/redacted/truncated/unsupported/error when recorded; otherwise say unavailable, reason not recorded. “Captured JSON” means the bounded stored representation, not unredacted provider data. Copy acts on available captured content only. |
| Investigation | Explicit user request, pending/running/completed/failed per attempt. No streaming candidates, invented progress percentage, causal-confidence score, or frontend recomputation of priority/category. New analysis creates a distinct attempt; selected earlier results remain available. Grounding/candidate policy awaits E1. |
| Evidence | Citation activation opens that exact source for the selected attempt. Stable source numbering, explicit A/B reassignment, persistent highlight with text label, keyboard-accessible surrounding context. Snapshot mismatch/missing citation stays visible; no fallback to current trace or newest document. |

Refresh is explicit and preserves valid selections. If late telemetry extends the current trace, display that earlier analysis used a different input when the backend can establish it. No claim that refresh completes telemetry. Escape/Back closes only the current overlay/workspace; never clears an investigation or modifies recorded data.

Captured content is untrusted. Display it as inert text/structured data; do not execute code, activate embedded HTML, or automatically fetch URLs/media contained in payloads. Provider/database credentials stay backend-only.

## 7. Empty, loading, failure, and quality states

| State | Presentation and recovery |
|---|---|
| First project / no persisted Runs | “No runs recorded”; Setup action. Do not infer that the SDK is disconnected from an empty query alone. |
| No query matches | Preserve query, distinguish from first-use empty state; Clear filters/widen time range. |
| Initial load / refresh | Static row/pane placeholders and busy announcement. Refresh may retain previously loaded data labeled as refreshing; errors label it as previously loaded, not fresh. |
| Read failure | Local error explanation with Retry; keep working panes/results accessible. Access denial does not offer an ineffective retry. |
| Partial trace | Independent completeness warning, known reasons/counts, inspectable orphan/multiple-root groups; no asserted complete execution or fabricated relations. |
| Recovered retry | Keep failed and succeeding attempt separate; mark recovered only with supported recorded association/outcome. No whole-Run failure derived from that child error. |
| Payload unavailable | Reason marker from section 6; no placeholder value pretending to be evidence. |
| Pending/running analysis | Attempt/status, non-blocking busy indication; no diagnosis shown early. |
| Completed, zero findings | “No grounded findings returned”, limitations available. Never “Run is correct” or “No errors occurred”. |
| Failed analysis | Failed attempt and safe failure information; trace and previous findings remain inspectable. New retry is explicit. |
| Missing/unresolvable evidence | Source-specific reason; retain finding and other citations. Do not describe that source as resolved; precise aggregate grounding presentation awaits E1/E2. |
| Large/limited trace | Separate viewport/expanded/loaded/known counts where available, scope-labeled query, progressive structure and lazy payloads. Hidden selected spans remain identified/revealable. Display actual limits explicitly; loading is not capture completeness. |

## 8. Responsive behavior and accessibility

| Viewport width (CSS px) | Behavior |
|---|---|
| At least 1280 px | Preserve chosen 200/56 px navigation. Trace Explore fills the workbench; inspector overlays at 480–640 px or pins when minima fit. Evidence pairing is unchanged. |
| 1024–1279 px | Trace overlay remains within available width; pin only if workbench width is at least 928 px. Otherwise use the single-pane fallback without changing the saved desktop navigation/pin preference. |
| 768–1023 px | Compact top navigation and project menu; Trace uses a single active Execution/Inspector pane when minima fail. Evidence retains its existing stacked-source behavior. Preserve all selections, zoom and anchors. |
| Below 768 px | Navigation sheet; one active workbench pane, full-width inspector, stacked evidence. Search stays visible; secondary filters open a labeled sheet. All columns/data remain reachable through local table scrolling or Run detail. |

The execution table/timeline may scroll horizontally inside their labeled regions; headings, controls, explanations, and warnings reflow. No page-wide horizontal scroll. Long text wraps; captured JSON can opt into local scrolling. Dialogs fit the viewport; switching widths/themes does not reset investigation context.

Target [WCAG 2.2 AA](https://www.w3.org/TR/WCAG22/): normal text contrast at least 4.5:1; required non-text indicators at least 3:1; keyboard access, visible unobscured focus, labeled controls, and status announcements. Reflow ordinary content at 320 CSS px; the two-dimensional-layout exception is limited to relevant data regions. Product targets are at least 24 × 24 px, expanded to 44 px for touch controls. These are acceptance requirements, not achieved conformance.

Follow the [WAI-ARIA tree pattern](https://www.w3.org/WAI/ARIA/apg/patterns/treeview/): Up/Down traverse visible nodes; Right expands/enters a branch; Left collapses/moves to parent; Home/End reach first/last visible node; type-ahead finds names. Enter/Space selects. Provide one tree tab stop, announced level/expansion/selection, and stable focus during bounded loading. Unknown set sizes must not be announced as known totals.

Use table headers/sort announcements; avoid turning the entire table into an unnecessary keyboard grid. Tabs expose selected state; manual activation avoids fetches merely from focus. Resize handles need keyboard and single-pointer alternatives. Overlays restore focus to the invoking control; citation navigation focuses its source heading. A text/table timing alternative accompanies graphical bars. No hover-only access to identifiers, errors, or citations; support reduced motion and text-spacing/zoom overrides.

**Non-modal inspector:** expose a named region, not `aria-modal=true`; keep desktop explorer controls and background tree keyboard navigation available. Opening from a row keeps focus on the tree and announces the selected operation; a visible Focus inspector control (F6 alternative) moves into the region. F6/Back to execution returns to the retained tree focus. Tab/Shift+Tab follow normal document order without trapping. Escape closes the overlay only when no inner control consumes it; do not clear queries or pop the workspace. If focus was inside a closing panel, return to the invoker when mounted, otherwise the labeled explorer without changing its scroll. Outside pointer activation keeps focus on its intended target. In the fully covering single-pane fallback, make covered explorer content unavailable to focus/assistive reading until Back; this is navigational replacement, not a desktop modal-dialog contract.

**Virtualized focus:** use one composite tree tab stop, distinguish active focus from selection and retain the active item's accessible representation while windowing. Declare accurate level/position/set-size for dynamically present rows; unknown sibling size is not a page count. Production must preserve logical parent/group ownership and test announcements with actual screen readers. Follow [APG tree guidance](https://www.w3.org/WAI/ARIA/apg/patterns/treeview/), [keyboard focus guidance](https://www.w3.org/WAI/ARIA/apg/practices/keyboard-interface/) and the [window splitter pattern](https://www.w3.org/WAI/ARIA/apg/patterns/windowsplitter/). The prototype's declared row metadata and keyboard checks do not establish assistive-technology interoperability.

Overlay occlusion must not leave keyboard focus behind the panel. Keep Focus inspector/Reveal at the visible left edge. Temporarily omit covered background controls from sequential focus and assistive reading, restoring them on dismissal without shifting their layout; visible controls and the tree remain available. An outside pointer click first dismisses the panel and can activate its intended background control in the same interaction. Do not make the entire desktop explorer inert.

Compact disclosures retain explicit accessible names, Enter/Space activation and ordinary Tab access to controls. Escape first closes an open disclosure and returns to its summary; a subsequent Escape can dismiss an unpinned inspector. Outside activation closes the disclosure without stealing intended focus. Filters and options are form/disclosure surfaces rather than falsely labeled ARIA menus. Resize remains usable through both the keyboard splitter and the optional visible slider; removing permanent slider chrome must not remove that alternative. Do not clip a disclosure within an occluded pane or put essential identity exclusively in a tooltip.

## 9. Review scenarios

These are synthetic design fixtures with illustrative payload fields, not approved wire schemas, executed agents, or investigator-quality tests. Candidate categories/priorities are supplied fixture data; the UI must not derive them.

### S1 — Incorrect reasoning

A support Run is reported completed with no explicit exception. Tool span T records `eligible: false`; the downstream model M receives that value but outputs `eligible: true` and recommends approval. A supplied candidate finding cites T's output and M's input/output as a potential reasoning inconsistency.

Review: locate the Run without an error-only filter → inspect T/M in tree and timeline → open the finding → compare the two cited values → return to the same span. Expected: completed status is not changed to failed; grounding does not prove the tool/business policy correct or establish causal root cause. Variant: M's input is redacted; show the missing evidence and supplied limitation, not a reconstructed prompt.

### S2 — Recovered retry

Tool attempt A1 records a timeout/error; A2 is a separate successful span with a recorded `retry_of` relationship; the enclosing application reports completion. Both payloads and the exception event are retained.

Review: locate the recorded error → inspect A1 → follow the explicit retry relationship to A2 → verify recovery without hiding A1. Expected: one failed attempt remains visible, not two failures created from status plus exception event; Run outcome remains separately reported. Variant: omit association metadata; keep both spans but do not assert recovery merely because names/times resemble retries. Equivalent transport redelivery must not create A3.

### S3 — Multiple cited sources

A retrieval span quotes a 30-day refund window; a model input repeats it. An optional project-authoritative document states 14 days for the same applicable policy; a 21-day request is approved. A supplied finding cites retrieval output, model input, and a fixed document passage, with limitations about applicability.

Review: open Evidence Focus → pair retrieval/document → switch Source A to model input → inspect the analyzed span when available. Expected: all three citations remain accessible, identity/snapshot context persists, and the frontend does not relabel the model as the cause simply because it followed bad retrieved context. Variant: current telemetry/document changes; show analyzed values or an explicit unavailable state, never substitute new values.

## 10. Reusable component inventory

Logical responsibilities, not prescribed React files or a dependency choice:

| Component family | Responsibility |
|---|---|
| AppShell, ProjectNavigation, Breadcrumbs, ThemeControl | Project context, landmarks, responsive shell, coordinated themes. |
| SignInForm, RegistrationForm, SessionNotice | Labeled email/password presentation, safe backend validation/busy state, session-aware return navigation. No password verification or access-control logic. |
| QueryToolbar, FilterChip, DurationRange, Pagination | Shared query state and validated input; no invented totals. |
| RunTable, MetricValue, IdentityLabel | Dense semantic rows, tabular metrics, full identity access. |
| StateBadge, QualityNotice, AsyncRegion | Independent outcome/completeness/analysis meanings and section 7 states. |
| SplitWorkspace, ResizeHandle, InspectorOverlay, PaneHeader, TabStrip | Full-width/overlay/pinned modes, non-modal focus, keyboard resizing and single-pane fallback. |
| ExecutionNavigator, TraceTree, TraceTimeline, VirtualRowWindow, AncestorPath | Stable selection/filter/row-anchor model, windowed hierarchy, counts and shared timing scale. |
| SpanInspector, PayloadViewer, AttributeTable, EventList | Typed and generic captured evidence, availability markers, safe copy. |
| OperationGlyph, ContentModeSwitch, SourceFocus | Consistent type/status shapes, adaptive readable/JSON inspection, paired/single source presentation without new evidence semantics. |
| InvestigationSummary, FindingList, FindingDetail | Attempt status, supplied priorities/categories, limitations and citations. |
| EvidenceWorkspace, CitationList, SourcePane | Snapshot-aware resolution, source pairing and focused excerpts. |
| SetupChecklist, KnowledgeSourceList, FormDialog | Narrow onboarding/conditional knowledge flows; accessible validation. |

Every applicable family supports both themes and relevant hover/focus/selected/disabled/busy/error states. Shares behavior and tokens, not one universal component for unrelated data. SourcePane reuses payload/attribute rendering; it does not duplicate investigator logic.

## 11. Dependencies and unresolved decisions

Data below describes frontend needs, not finalized API field names or endpoints. The browser uses project-scoped platform APIs only; it does not query databases, Kafka, or model providers directly.

| ID | Dependency | Required capability / unresolved boundary |
|---|---|---|
| B1 | Run summaries | Identity, times/duration, service/agent, reported outcome, independent completeness/warnings, recorded error counts. Outcome/completeness vocabulary and aggregation await P2. |
| B2 | Explorer query | Project/time/name/ID/status/duration/completeness filtering, stable sorting, bounded pages, explicit total availability. Global search must not secretly mean loaded-page search. |
| B3 | Reconstructed execution | Stable IDs/parentage/order, raw statuses, valid/unavailable timing, explicit links/retries, loaded/total indicators. Limits and ancestor lookup await P3. |
| B4 | Span inspection | Bounded payloads plus availability reasons, attributes, events/errors and relationships; distinguish empty from not loaded. Error counting awaits P2. |
| B5 | Analysis lifecycle | Attempt identity/state, safe failure/retry information, retained earlier results, analyzed input identity, current-input change indication. Polling/refresh and request concurrency await E4/P3. |
| B6 | Findings/evidence | Supplied category/priority/explanation/limitations; source IDs, stable field/path/excerpt and grounding outcome. Candidate policy and excerpt semantics await E1/E3. |
| B7 | Snapshot resolution | Resolve the evidence used by an attempt; optionally inspect that snapshot's spans/hierarchy. No silent fallback; retention/document version policy awaits E2. |
| B8 | Project onboarding/access | Authorized project selection/creation, integration setup, persisted-run confirmation, browser access/error policy. Current console exporter is not hosted readiness. |
| B9 | Conditional knowledge | Project-owned document/chunk identity, processing/availability, fixed cited passage and access. Upload format/lifecycle awaits P4; historical resolution awaits E2. |
| B10 | Backend-owned authentication | Approved sign-in/registration/session/sign-out integration, safe validation and expiration responses, reauthorization of project reads. No routes, transport, or password policy invented here. |

Large-trace UI depends on B3/B4/P3 agreeing structural load boundaries, known/unknown counts, ancestor lookup, search scope and bounded selected-payload availability. Section 4.4 describes presentation needs only; it neither chooses pagination/search contracts nor claims those capabilities exist. Evidence snapshot dependencies remain E1–E4 unchanged.

### Investigation-engine approval required

| ID | Open question | Frontend boundary until resolved |
|---|---|---|
| E1 | Final category/priority presentation and policy for rejected or ungrounded candidates; aggregate grounding when a previously verified source becomes unavailable. | Never promote an unverified candidate into a grounded finding; no frontend diagnosis/ranking rules. Primary grounded results remain distinct from any approved diagnostic view. |
| E2 | Stable analysis-input/evidence lookup, retention, authoritative source version binding, and whether full snapshot trace inspection is supported. | Evidence availability is explicit; snapshot-sensitive features cannot use current values as replacements. |
| E3 | Citation path/excerpt/range representation and renderer normalization guarantees. | Highlight only resolvable captured ranges; do not guess paths or reconstruct missing text. |
| E4 | Completed-but-limited investigation semantics, retryable failures, and permitted concurrent/repeated requests. | Show supplied limitations/state; do not invent a new analysis state, automatic retry, budget progress, or engine execution mode. |

No approval of models, prompts, tool budgets, orchestration, or investigator architecture is implied by this specification.

### Product/API questions, separate from engine approval

| ID | Open question | Proposed direction / consequence |
|---|---|---|
| P1 | Initial time window, timezone preference, and default theme. | Recommend System theme and explicitly labeled local time with UTC available; time-window choice needs review. Both explicit themes are required regardless. |
| P2 | Execution outcome/completeness labels, recovered-retry summary, event-versus-error counting. | Backend owns objective semantics; `UNSET`/missing root never becomes frontend success and an error event/status must not be double-counted. |
| P3 | Browser authorization, query pagination/search guarantees, trace/payload limits, and status refresh contract. | Confirm B2/B3/B5/B8 before final API-dependent interaction acceptance; do not advertise unsupported global queries or live completeness. |
| P4 | Minimum optional knowledge delivery, permitted formats, upload limits, and processing/error vocabulary. | PRD lists knowledge as Should but includes an authoritative scenario in success criteria. Defer rich management; explicitly account for the minimum scenario before claiming full PRD completion. |
| P5 | Auth/session API, password policy, registration completion, recovery/email-verification scope, expiration and sign-out contract. | Email/password form and expiration UX are required; FastAPI exclusively verifies passwords, manages sessions, and authorizes data. Preview forms remain disconnected. |
| P6 | First-use sidebar preference, scope/lifetime of pin/width preference, citation-chip destination redesign and optional multi-finding list. | Preserve existing explicit navigation preference. Current review baseline starts expanded, uses per-Run return context, and retains explicit Left/A citation-chip assignment; new defaults or Replace left/right behavior need separate review. |

## 12. Acceptance criteria

These are product review gates. The isolated static preview provides the dated evidence recorded in its review notes; it is not production functionality, backend integration, or an accessibility-conformance claim.

### Visual fidelity

- **V1:** Review all three workspaces at both reference desktop sizes in Light and Dark. Retain earlier captures as history; the 16 October Evidence Focus density renders supersede its earlier rail layout. Trace Detail uses V5's four-mode matrix. Match section 4 geometry and section 5 type/spacing/borders; fixed dimensions within 2 px at 100% zoom. Flexible panes use remaining width, not copied screenshot proportions.
- **V2:** The same component/state uses the same semantic role in both themes. Inspect selected+hover, selected+focus, invalid, busy, and disabled combinations; no light-only panel/tooltip or low-contrast placeholder.
- **V3:** Review long names/IDs, deep nesting, long JSON, one/two/three citations, and every section 7 state in both themes. Essential identity, warning, or limitation is neither clipped nor available only on hover.
- **V4:** Check 1024 × 768, 768 × 1024, 390 × 844, and 320 px reflow; 200% text/zoom and 400% reflow checks. Overflow is restricted to intentional data regions. No gradients, glass effects, KPI cards, unnecessary motion, or competitor branding.
- **V5:** Capture Trace Detail's full-width Tree, full-width Timeline, open overlay and pinned split in both themes at 1440×900 and 1280×800 (16 captures). Inspect native resolution, overlay bounds/occlusion, sticky controls, compact pinned labels and common timeline origin. Retain older Trace/Evidence captures as historical references; preserve Run Explorer's table rhythm and data semantics.
- **V6:** Record matched before/after row-viewport height, fully visible 32 px operation count, inspector-body height and available payload area at both desktop sizes/themes. Include the 2,100-span partial pinned timeline and rail-free evidence source widths/heights. The pinned desktop toolbar stays one 44 px band; timing stays one 40 px band. Footer/filters cannot overlap or clip. No improvement may come from smaller readable type, removed warnings, fabricated completeness or distorted timing. Measurements apply to sampled fixtures, not a production size/performance guarantee.

### Functional UX and accessibility

- **U1:** Project change, filtering/sorting/pagination, reload, deep link, and browser return preserve the correct scoped state from sections 4/6; denied/stale links never reveal unrelated data.
- **U2:** Tree/timeline select the same stable span. Expansion does not change selection; filters retain ancestor context; keyboard traversal and citation reveal work without a pointer.
- **U3:** Inspector handles all initial operation types (`run`, `agent`, `model`, `retrieval`, `tool`, `api`, `state`, `custom`), unknown types via generic rendering, and all payload availability/value distinctions. Late fetch responses cannot cross selections.
- **U4:** Execute S1–S3 as UI fixtures in both themes. Outcome/error/recovery remain distinct; every cited source is reachable; pairing/back navigation preserves context. No inferred causal or probability labels appear.
- **U5:** Analysis failure, zero findings, new attempts, late telemetry, and unavailable citations follow section 7. Earlier findings stay accessible and immutable. Snapshot/document changes cannot alter displayed analyzed evidence silently.
- **U6:** Test bounded large traces and payloads after B2/B3 limits are agreed: unloaded data/counts stay explicit, hidden selection can be revealed, filters cover their declared scope, and navigation remains available during loading. Record actual performance separately; no undocumented size guarantee.
- **U7:** Keyboard and screen-reader review covers table, tree, tabs, timeline alternative, splitters, filters/dialogs, analysis announcements, source pairing, and focus return. Check contrast on actual rendered states and verify zoom/reflow, not only token arithmetic.
- **U8:** With real approved read/analysis contracts, verify first persisted Run, span fetch, analysis lifecycle, snapshot evidence, and conditional authority end to end. Fixture success is not backend integration or investigator accuracy evidence.
- **U9:** Sidebar expansion/collapse survives all workspace transitions/reload; responsive overrides preserve the developer's desktop choice. Sign-in/register/expired views have labeled, legible states; only backend-confirmed session/authorization results unlock protected data in the eventual product.
- **U10:** At both desktop widths, long model content defaults to stacked full-width reading, with the same captured values in JSON mode. Timeline plots align to one measured axis and match fixture timestamps. A zero-findings attempt exposes no finding-evidence link. Source focus/reassignment preserves all citations and the finding's meaning. Treat these local preview checks separately from API/investigator verification.
- **U11:** Default Trace shows no inspector column. Selecting/switching/closing an overlay leaves explorer width, DOM scroll container, expanded rows, query and time window intact. Outside row activation switches directly; outside controls still act. Escape/Close retain selected ID; pinned outside/Escape behavior is distinct and labeled.
- **U12:** Pin/unpin and keyboard/pointer resize retain context and per-span content state. Check min/max/reset, constrained-width fallback and restoration of desktop mode. Focus can move between explorer/inspector without trapping or landing on removed/covered content.
- **U13:** Exercise 100/1,000/2,100 fixtures at start/middle/end, deep collapsed branches, filtered ancestors and offscreen jump/reveal. Record actual DOM row counts and sample environment; no performance guarantee. Distinguish client-loaded structure from viewport rows, unloaded matches and capture quality.
- **U14:** Validate shared timing numerically at Fit and zoomed windows, including clipped and out-of-window operations. Zoom/pan/view changes preserve selected span and vertical anchor. Progressive structure and payload inspection are explicitly local simulation until approved B3/B4 contracts are integrated.
- **U15:** Exercise raw OK/ERROR/UNSET/missing/unrecognized fixtures, latest selected-span evidence links, pinned and overlay return context, optional ID/search/copy access, disclosure Escape/focus, loaded-match navigation, and single/multiple-finding selection. Investigation request/retry remains explicitly disconnected in the preview; historical inspection stays unavailable without B7/E2 resolution. Record any incomplete acceptance behavior separately.

Resolve relevant section 11 questions before claiming the dependent criteria pass. Later approved renders may become golden references; the competitive screenshots remain research evidence, not pixel-copy targets.
